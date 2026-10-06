"""Bounded, read-only diagnostics. Only an explicit Share confirmation sends data."""
from datetime import datetime
import json
import ipaddress
import os
from pathlib import Path
import re
import tempfile
import uuid
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from zipfile import ZipFile, ZIP_DEFLATED

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

MAX_LOG_BYTES = 256 * 1024
MAX_LOG_LINES = 200
SHARE_SERVICE = 'https://paste.kodi.tv'
LEVEL = re.compile(r'\b(DEBUG|INFO|NOTICE|WARNING|WARN|ERROR|FATAL)\s*:', re.I)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None


def redact(text):
    # Mask full URLs, not just passwords: query strings and filenames may be private.
    text = re.sub(r'(?i)\b(?:https?|smb|nfs|ftp|ftps|dav|davs|rtsp|plugin|special|image)://[^\s<>\"\']+', '[地址已隐藏]', text)
    text = re.sub(r'(?im)(\b(?:authorization|proxy-authorization|cookie|set-cookie)\s*:\s*)[^\n]+',r'\1[认证已隐藏]',text)
    text = re.sub(r'(?i)(\b(?:Bearer|Basic)\s+)[A-Za-z0-9+/=_\-.]+', r'\1[认证已隐藏]', text)
    secret = r'(?:access[_-]?token|token|x-emby-token|api[_-]?key|authorization|password|passwd|secret|username|userid)'
    text = re.sub(r'(?im)([\"\']?'+secret+r'[\"\']?\s*[:=]\s*)(?:\"[^\"]*\"|\'[^\']*\'|[^,;\s}]+)', r'\1[认证已隐藏]', text)
    text = re.sub(r'(?i)(<'+secret+r'[^>]*>)[^<]*(</[^>]+>)', r'\1[认证已隐藏]\2', text)
    text = re.sub(r'(?i)(<setting\s+[^>]*id=[\"\']'+secret+r'[\"\'][^>]*>)[^<]*(</setting>)',r'\1[认证已隐藏]\2',text)
    # Quoted native paths, bare paths (including spaces), UNC and IPv4/IPv6.
    text = re.sub(r'([\"\'])(?:[A-Za-z]:[\\/]|/|\\\\)[^\n\"\']*\1', '[路径已隐藏]', text)
    text = re.sub(r'(?i)(?:[A-Z]:[\\/]|\\\\)[^\n,;<>\"\']+', '[路径已隐藏]', text)
    text = re.sub(r'(?<![\w:])/(?:[^\s/<>\"\']+)(?:/[^\n,;<>\"\']*)?', '[路径已隐藏]', text)
    def address(match):
        try:ipaddress.ip_address(match.group(0));return '[网络地址已隐藏]'
        except ValueError:return match.group(0)
    text = re.sub(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])', address, text)
    text = re.sub(r'(?<!\w)(?:[0-9a-f]{0,4}:){2,}[0-9a-f:]{0,39}(?:%\w+)?', address, text, flags=re.I)
    # Kodi-labelled media paths without an absolute root (relative files too).
    text = re.sub(r'(?im)(\b(?:filename|filepath|strpath|strfilename|playing|opening)\s*[:=]\s*)[^\n]+', r'\1[媒体路径已隐藏]', text)
    return text


def log_tail(path=None):
    path = path or xbmcvfs.translatePath('special://logpath/kodi.log')
    try:
        with open(path, 'rb') as f:
            size = f.seek(0, os.SEEK_END)
            start = max(0, size - MAX_LOG_BYTES)
            f.seek(start); raw = f.read(MAX_LOG_BYTES)
        if start: raw = raw.split(b'\n', 1)[-1]
        lines = raw.decode('utf-8', errors='replace').splitlines()
        if len(lines) > MAX_LOG_LINES:
            lines = lines[-MAX_LOG_LINES:]
            # Do not show a chopped exception as if it were a new record.
            first = next((i for i, line in enumerate(lines) if LEVEL.search(line)), None)
            if first is not None: lines = lines[first:]
        return '\n'.join(lines), ('empty' if not lines else 'ok')
    except FileNotFoundError: return '', 'missing'
    except PermissionError: return '', 'permission'
    except OSError: return '', 'unreadable'


def filtered(text, mode='all'):
    records=[]
    for line in text.splitlines():
        level=LEVEL.search(line)
        if level or not records: records.append([level.group(1).upper() if level else '', [line]])
        else: records[-1][1].append(line)
    allowed={'all':None,'warn':{'WARNING','WARN','ERROR','FATAL'},'error':{'ERROR','FATAL'}}[mode]
    return '\n'.join('\n'.join(lines) for level,lines in records if allowed is None or level in allowed)


def view_logs():
    from infuse import import_actions
    import_actions()
    from home_dialog import Dialog
    mode='all';position=0
    states={'empty':'日志当前为空。','missing':'日志文件尚不存在。','permission':'没有读取日志的权限。','unreadable':'暂时无法读取日志，请稍后刷新。'}
    while True:
        selected=Dialog().select('运行日志 · 最后至多 200 行', ['查看日志','筛选：'+{'all':'全部','warn':'警告与错误','error':'仅错误'}[mode],'刷新日志'],preselect=position)
        if selected<0:return
        position=selected
        if selected==1:
            choice=Dialog().select('日志筛选',['全部','警告与错误','仅错误'],preselect=('all','warn','error').index(mode))
            if choice>=0:mode=('all','warn','error')[choice]
            continue
        text,state=log_tail();body=filtered(text,mode) if state=='ok' else states[state]
        xbmcgui.Dialog().textviewer('Kodi 运行日志 · '+{'all':'全部','warn':'警告与错误','error':'仅错误'}[mode], body or '当前范围没有符合条件的日志。')


def metadata():
    data={'created':datetime.now().isoformat(timespec='seconds'),'scope':'bounded redacted log; runtime versions and selected addon availability', 'addons':{}}
    for ident in ('skin.yoplayer.infuse','plugin.video.yoplayer.home','plugin.service.emby-next-gen','service.coreelec.settings','plugin.video.themoviedb.helper'):
        if not xbmc.getCondVisibility('System.HasAddon('+ident+')'):
            data['addons'][ident]={'installed':False};continue
        try:
            data['addons'][ident]={'installed':True,'enabled':bool(xbmc.getCondVisibility('System.AddonIsEnabled('+ident+')')),
                                  'version':xbmcaddon.Addon(ident).getAddonInfo('version')}
        except RuntimeError:data['addons'][ident]={'installed':True,'version':'设备未提供'}
    data['kodi']=xbmc.getInfoLabel('System.BuildVersion')
    return data


def diagnostic_content():
    text,state=log_tail()
    return {'kodi-redacted.log':redact(text or '日志状态：'+state),
            'runtime.json':redact(json.dumps(metadata(),ensure_ascii=False,indent=2)),
            'README.txt':'仅有界日志尾部、版本与五项插件可用状态。认证、地址及已识别媒体路径默认隐藏；没有原始连接配置、数据库、历史或续播。脱敏不能保证清除任意自由文本，请分享前检查。'}


def export():
    dialog=xbmcgui.Dialog()
    if not dialog.yesno('导出诊断包','包含：最后至多 200 行日志、版本、五项插件状态。默认脱敏认证、网络地址与已识别媒体路径；不含连接配置和观看记录。',nolabel='取消',yeslabel='选择保存目录',defaultbutton=xbmcgui.DLG_YESNO_NO_BTN):return
    destination=dialog.browse(0,'诊断包保存目录','files')
    if not destination:return
    name='YoPlayer-diagnostics-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]+'.zip'
    target=destination.rstrip('/\\')+'/'+name
    temporary=None
    try:
        content=diagnostic_content()
        with tempfile.NamedTemporaryFile(delete=False,suffix='.zip') as f:temporary=f.name
        with ZipFile(temporary,'w',ZIP_DEFLATED) as z:
            for member,text in content.items():z.writestr(member,text)
        with ZipFile(temporary) as z:
            if z.testzip() or set(z.namelist())!=set(content):raise OSError('archive')
        if xbmcvfs.exists(target) or not xbmcvfs.copy(temporary,target):raise OSError('copy')
        dialog.ok('诊断包已导出',name+'\n包含脱敏日志、runtime.json 与范围说明；请分享前检查。')
    except (OSError,RuntimeError):dialog.ok('导出未完成','保存目录不可用或写入失败，请选择可写目录重试。')
    finally:
        if temporary:
            try:os.unlink(temporary)
            except OSError:pass


def share():
    dialog=xbmcgui.Dialog();text,state=log_tail()
    if state!='ok':dialog.ok('无法分享日志','当前没有可读取的运行日志。');return
    payload=redact(text)
    dialog.textviewer('待分享的脱敏日志 · 请检查',payload)
    if not dialog.yesno('分享运行日志','目的服务：'+SHARE_SERVICE+'（公开链接）\n范围：最后至多 200 行、至多 64 KiB 脱敏日志。\n认证、网络地址和已识别媒体路径已隐藏；自由文本请自行检查。',nolabel='取消',yeslabel='上传脱敏日志',defaultbutton=xbmcgui.DLG_YESNO_NO_BTN):return
    if len(payload.encode('utf-8'))>64*1024:
        dialog.ok('日志过长','脱敏内容超过分享上限，请使用本地导出。');return
    try:
        req=Request(SHARE_SERVICE+'/documents',data=json.dumps({'content':payload}).encode('utf-8'),headers={'Content-Type':'application/json'},method='POST')
        with build_opener(NoRedirect()).open(req,timeout=5) as response:
            raw=response.read(4097)
            if len(raw)>4096:raise ValueError('response')
            key=json.loads(raw).get('key','')
        if not isinstance(key,str) or not re.fullmatch('[a-zA-Z0-9_-]{1,80}',key):raise ValueError('key')
        dialog.textviewer('日志分享链接',SHARE_SERVICE+'/'+key+'\n链接持有人可以读取此份日志。')
    except (OSError,ValueError,RuntimeError):dialog.ok('分享未能确认','请求超时或服务响应无效。未自动重试；可本地导出后自行分享。')
