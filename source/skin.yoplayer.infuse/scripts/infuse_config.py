"""Scoped UI backup/restore. No Kodi database, auth, history or reboot writes.

Archives contain a versioned whitelist, exact Home preference files and only
referenced custom images. Imports never extract paths from the archive.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import sys
import tempfile
import time
import uuid
import zipfile
import xml.etree.ElementTree as ET
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

SCOPES = ('appearance', 'home', 'all')
LABELS = ('外观', '首页与分库', '全部界面偏好')
HOME_FILES = {'libraries.json', 'preplay-tracks.json', 'stream-memory.json'}
IMAGE_KEYS = {'logoimage', 'defaultbgimg'}
MAX_FILE = 16*1024*1024
MAX_TOTAL = 64*1024*1024


def schema():
    p = Path(xbmcvfs.translatePath('special://skin/resources/ui-preferences.json'))
    return json.loads(p.read_text(encoding='utf-8'))


def keys(scope):
    data = schema()
    return {k: v for k, v in data.items() if scope == 'all' or v['scope'] == scope}


def skin_values(scope):
    return {k: {'type': v['type'], 'value':
        ('true' if xbmc.getCondVisibility('Skin.HasSetting('+k+')') else 'false')
        if v['type'] == 'bool' else xbmc.getInfoLabel('Skin.String('+k+')')}
        for k, v in keys(scope).items()}


def paths():
    profile = Path(xbmcvfs.translatePath(xbmcaddon.Addon('plugin.video.yoplayer.home').getAddonInfo('profile')))
    own = Path(xbmcvfs.translatePath('special://profile/addon_data/skin.yoplayer.infuse/'))
    return profile, own/'ui-backups'


def validate_skin(data):
    if not isinstance(data, dict):
        raise ValueError('皮肤偏好格式无效')
    allowed = schema()
    result = {}
    for key, item in data.items():
        if key not in allowed:
            continue  # Legacy caches/history/auth are deliberately excluded.
        if not isinstance(item, dict) or item.get('type') != allowed[key]['type']:
            raise ValueError('皮肤偏好类型不匹配')
        value = item.get('value')
        if not isinstance(value, str) or len(value) > 8192 or '\x00' in value:
            raise ValueError('皮肤偏好值无效')
        if item['type'] == 'bool' and value not in ('true', 'false'):
            raise ValueError('皮肤开关值无效')
        result[key] = dict(item)
    return result


def validate_home(name, raw):
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError('Home 偏好格式无效')
    if name == 'libraries.json':
        from infuse import import_actions
        import_actions()
        from catalog import validate_preferences
        validate_preferences(data)
    elif name == 'preplay-tracks.json':
        if data.get('version') != 1 or not isinstance(data.get('items'), dict):
            raise ValueError('开播轨道偏好格式无效')
        from infuse_preplay import validate_choice
        for choices in data['items'].values():
            if not isinstance(choices, dict):
                raise ValueError('开播轨道偏好格式无效')
            for kind, choice in choices.items():
                if kind not in ('audio', 'subtitle'):
                    raise ValueError('轨道类型无效')
                validate_choice(kind, choice)
    elif name == 'stream-memory.json':
        if data.get('version') != 1 or not isinstance(data.get('selections'), dict):
            raise ValueError('本季轨道偏好格式无效')
        for choices in data['selections'].values():
            if not isinstance(choices, dict):
                raise ValueError('本季轨道偏好格式无效')
            for kind, row in choices.items():
                if kind not in ('audio', 'subtitle') or not isinstance(row, dict) or type(row.get('enabled')) is not bool:
                    raise ValueError('本季轨道偏好值无效')
                if row['enabled'] and (type(row.get('index')) is not int or row['index'] < 0 or not isinstance(row.get('identity'), dict)):
                    raise ValueError('本季轨道身份无效')
    else:
        raise ValueError('未允许的 Home 文件')
    return data


def local_file(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FILE:
        raise ValueError('备份包含非普通文件或大文件')
    return path.read_bytes()


def snapshot(scope):
    home, _ = paths()
    skin = skin_values(scope)
    files = {}
    if scope in ('home', 'all'):
        for name in sorted(HOME_FILES):
            path = home/name
            if path.exists():
                files['home/'+name] = local_file(path)
                validate_home(name, files['home/'+name])
    return skin, files


def image_refs(skin, files):
    refs = {v['value'] for k, v in skin.items() if k in IMAGE_KEYS and v['value']}
    if 'home/libraries.json' in files:
        data = json.loads(files['home/libraries.json'])
        refs.update(row.get('thumb', '') for row in data.get('items', {}).values())
        refs.update(row.get('thumb', '') for row in data.get('custom', []))
    return {r for r in refs if r}


def pack(scope, skin, files, collect_images=True):
    files = dict(files)
    images = {}
    if collect_images:
        for ref in sorted(image_refs(skin, files)):
            # Native/server artwork stays a reference. Only selected custom
            # local files are included; no downloads or arbitrary traversal.
            if ref.startswith(('http:', 'https:', 'image:', 'plugin:', 'smb:', 'nfs:')):
                continue
            path = Path(xbmcvfs.translatePath(ref))
            if not path.exists():
                raise ValueError('自定义图片不存在，请重新选择图片后备份')
            raw = local_file(path)
            suffix = path.suffix.lower()
            if suffix not in ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'):
                raise ValueError('自定义图片类型不支持')
            name = 'images/'+hashlib.sha256(raw).hexdigest()+suffix
            files[name] = raw
            images[ref] = name
    manifest = {'format': 'YoPlayer UI preferences', 'version': 1, 'scope': scope,
        'created': datetime.now(timezone.utc).isoformat(),
        'skin_version': xbmcaddon.Addon('skin.yoplayer.infuse').getAddonInfo('version'),
        'home_version': xbmcaddon.Addon('plugin.video.yoplayer.home').getAddonInfo('version'),
        'skin': validate_skin(skin), 'images': images,
        'files': {n: hashlib.sha256(b).hexdigest() for n, b in files.items()},
        'home_presence': {n: 'home/'+n in files for n in HOME_FILES} if scope in ('home','all') else {}}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        for name, raw in files.items():
            z.writestr(name, raw)
    if sum(len(b) for b in files.values()) > MAX_TOTAL:
        raise ValueError('备份总大小超出限制')
    return stream.getvalue()


def safe_members(raw):
    members = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if len(z.infolist()) > 256:
            raise ValueError('备份文件数量超出限制')
        total = 0
        names = set()
        for info in z.infolist():
            name = info.filename
            p = PurePosixPath(name)
            if info.is_dir():
                continue
            if (p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name
                    or name != p.as_posix() or name.casefold() in names
                    or (info.external_attr >> 16) & 0o170000 == 0o120000 or info.flag_bits & 1):
                raise ValueError('备份路径无效或包含重复/链接文件')
            total += info.file_size
            if info.file_size > MAX_FILE or total > MAX_TOTAL:
                raise ValueError('备份大小超出限制')
            names.add(name.casefold())
            members[name] = z.read(info)
    return members


def legacy_xml(raw):
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('旧配置包含不支持的 XML 声明')
    root = ET.fromstring(raw)
    if root.tag != 'settings':
        raise ValueError('旧备份不是皮肤设置')
    values = {}
    for n in root.findall('setting'):
        key = n.get('id', '').lower()
        if key in values:
            raise ValueError('旧备份有重复偏好')
        values[key] = {'type': n.get('type'), 'value': n.text or ''}
    return validate_skin(values)


def unpack(raw):
    if raw.lstrip().startswith(b'<'):
        return {'scope':'all','created':'旧 XML 备份','skin_version':'旧版','home_version':'无',
                'skin':legacy_xml(raw),'images':{},'home_presence':{}}, {}
    files = safe_members(raw)
    if 'manifest.json' not in files:
        # Legacy skinbackup export has timestamp folders and XML + images.
        options = sorted(n for n in files if Path(n).name.startswith('skinsettings-') and n.endswith('.xml'))
        if not options:
            raise ValueError('未找到 YoPlayer 或旧皮肤备份')
        name = options[-1]
        skin = legacy_xml(files[name]); images = {}; selected = {}
        for ref in image_refs(skin, {}):
            basename = ref.replace('\\','/').rsplit('/',1)[-1]
            member = str(PurePosixPath(name).parent/basename)
            if member in files:
                suffix = PurePosixPath(member).suffix.lower()
                if suffix not in ('.png','.jpg','.jpeg','.gif','.bmp','.webp'):
                    raise ValueError('旧图片类型无效')
                target = 'images/'+hashlib.sha256(files[member]).hexdigest()+suffix
                images[ref]=target;selected[target]=files[member]
        return {'scope':'all','created':'旧导出备份（最新一份）','skin_version':'旧版',
                'home_version':'无','skin':skin,'images':images,'home_presence':{}},selected
    meta = json.loads(files.pop('manifest.json'))
    if (meta.get('format') != 'YoPlayer UI preferences' or meta.get('version') != 1
            or meta.get('scope') not in SCOPES or not isinstance(meta.get('created'), str)):
        raise ValueError('备份版本或范围无效')
    meta['skin'] = validate_skin(meta.get('skin'))
    if set(meta['skin'])-set(keys(meta['scope'])):
        raise ValueError('皮肤偏好超出备份声明范围')
    if not isinstance(meta.get('files'),dict) or set(files) != set(meta['files']):
        raise ValueError('备份文件清单不完整')
    for n, b in files.items():
        if hashlib.sha256(b).hexdigest() != meta['files'][n]:
            raise ValueError('备份校验失败')
        if n.startswith('home/') and n[5:] in HOME_FILES:
            if meta['scope'] == 'appearance':
                raise ValueError('外观备份包含 Home 文件')
            validate_home(n[5:], b)
        elif n.startswith('images/'):
            if len(PurePosixPath(n).parts)!=2 or PurePosixPath(n).suffix not in ('.png','.jpg','.jpeg','.webp','.gif','.bmp'):
                raise ValueError('图片路径无效')
            if PurePosixPath(n).stem != hashlib.sha256(b).hexdigest():
                raise ValueError('图片身份不匹配')
        else:
            raise ValueError('备份包含范围外文件')
    presence = meta.get('home_presence', {})
    if not isinstance(presence,dict) or any(n not in HOME_FILES or type(v) is not bool or v != ('home/'+n in files) for n,v in presence.items()):
        raise ValueError('Home 文件存在状态无效')
    if meta['scope'] in ('home','all') and set(presence)!=HOME_FILES:
        raise ValueError('Home 文件存在清单不完整')
    if meta['scope'] == 'appearance' and presence:
        raise ValueError('外观备份包含 Home 存在清单')
    if not isinstance(meta.get('images'),dict) or any(n not in files or not n.startswith('images/') for n in meta['images'].values()):
        raise ValueError('图片引用不完整')
    if set(meta['images'])-image_refs(meta['skin'],files):
        raise ValueError('图片未被偏好引用')
    return meta, files


def atomic(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError('目标不能是符号链接')
    fd, temp = tempfile.mkstemp(prefix='.yoplayer-ui-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def saved_archive(raw, prefix='备份'):
    _, folder = paths()
    folder.mkdir(parents=True, exist_ok=True)
    if folder.is_symlink():
        raise ValueError('备份目录不能是链接')
    path = folder/(prefix+'_'+time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]+'.zip')
    with path.open('xb') as f:
        f.write(raw)
    unpack(path.read_bytes())
    return path


def apply_skin(values):
    for key, item in validate_skin(values).items():
        # Kodi's native parser accepts quoted, escaped parameters.
        value = item['value']
        if item['type'] == 'bool':
            action = 'Skin.SetBool('+key+','+value+')'
        elif not value:
            action = 'Skin.Reset('+key+')'
        else:
            action = 'Skin.SetString('+key+',"'+value.replace('\\','\\\\').replace('"','\\"')+'")'
        xbmc.executebuiltin(action, True)
    deadline = time.monotonic()+3
    monitor = xbmc.Monitor()
    while time.monotonic() < deadline:
        current = skin_values('all')
        if all(current[k] == v for k,v in values.items()):
            return
        if monitor.waitForAbort(.05):
            break
    raise RuntimeError('皮肤设置应用未能确认')


def stopped():
    response = json.loads(xbmc.executeJSONRPC('{"jsonrpc":"2.0","id":1,"method":"Player.GetActivePlayers"}'))
    return 'error' not in response and response.get('result') == []


@contextmanager
def exclusive():
    home, _ = paths();home.mkdir(parents=True,exist_ok=True)
    # Same persistent inode/OS lock as the library draft writer.
    with (home/'libraries.json.lock').open('a+b') as f:
        if os.name == 'nt':
            import msvcrt
            if f.tell() == 0:
                f.write(b'0');f.flush()
            f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == 'nt':
                f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
            else:
                fcntl.flock(f.fileno(),fcntl.LOCK_UN)


def restore(meta, files, scope, before):
    if scope not in SCOPES or not stopped():
        raise RuntimeError('请先停止播放再恢复界面偏好')
    home, folder = paths()
    wanted = {k:dict(v) for k,v in meta['skin'].items() if k in keys(scope)}
    incoming = {n:files['home/'+n] for n in HOME_FILES if 'home/'+n in files} if scope in ('home','all') else {}
    if 'libraries.json' in incoming and 'yoplayergenredisplaymigrated' not in wanted:
        # Pre-split backups stored effective movie visibility in two places.
        # Reload runs the idempotent migration; current-schema backups keep the
        # explicit movie/show switches and their completed migration marker.
        wanted['yoplayergenredisplaymigrated']={'type':'bool','value':'false'}
    presence = meta.get('home_presence',{}) if scope in ('home','all') else {}
    with exclusive():
        # The confirmation may outlive other preference edits.
        if snapshot(scope) != before or not stopped():
            raise RuntimeError('确认期间配置或播放状态已变化，请重新打开')
        skin, previous = before
        saved_archive(pack(scope, skin, previous), '恢复前回退')
        image_root = folder/'images'
        refs = image_refs(wanted, {'home/'+n:b for n,b in incoming.items()})
        remap = {}
        for ref, member in meta.get('images',{}).items():
            if ref in refs:
                destination = image_root/Path(member).name
                raw = files[member]
                if destination.exists() and local_file(destination) != raw:
                    raise ValueError('图片回退目录存在不一致文件')
                atomic(destination,raw);remap[ref]=str(destination)
        for k, v in wanted.items():
            if k in IMAGE_KEYS and v['value'] in remap:
                v['value']=remap[v['value']]
        if 'libraries.json' in incoming:
            data=json.loads(incoming['libraries.json'])
            for row in list(data.get('items',{}).values())+data.get('custom',[]):
                if row.get('thumb') in remap:row['thumb']=remap[row['thumb']]
            # Revision is a concurrency token, never restore an old generation.
            prior=json.loads(previous.get('home/libraries.json',b'{}'))
            data['revision']=max(data.get('revision',0),prior.get('revision',0))+1
            incoming['libraries.json']=json.dumps(data,ensure_ascii=False,indent=2).encode('utf-8')
        changed = {}
        try:
            for name in sorted(set(incoming)|set(presence)):
                path=home/name
                old=previous.get('home/'+name)
                if (local_file(path) if path.exists() else None) != old or not stopped():
                    raise RuntimeError('Home 偏好或播放状态变化')
                new=incoming.get(name)
                # An absent libraries.json is represented as default config with
                # a new revision so stale drafts cannot recreate old choices.
                if name=='libraries.json' and new is None:
                    prior=json.loads(old or b'{}')
                    new=json.dumps({'items':{},'custom':[],'order':[],
                                    'revision':prior.get('revision',0)+1}).encode()
                if new is None:
                    if path.exists():path.unlink()
                else:
                    atomic(path,new)
                changed[name]=(old,new)
            if not stopped() or skin_values(scope)!=skin:
                raise RuntimeError('皮肤偏好或播放状态变化')
            apply_skin(wanted)
        except Exception:
            # Roll back only files still equal to this operation's own writes;
            # never overwrite intervening user activity.
            conflicts=[]
            for name,(old,new) in changed.items():
                path=home/name
                if (local_file(path) if path.exists() else None)!=new:
                    conflicts.append(name);continue
                if old is None:
                    if path.exists():path.unlink()
                else:atomic(path,old)
            now=skin_values(scope)
            rollback={k:skin[k] for k,v in wanted.items() if now.get(k) in (v,skin[k])}
            conflicts.extend(k for k in wanted if k not in rollback)
            apply_skin(rollback)
            if conflicts:
                raise RuntimeError('有后续偏好修改，已保留；请使用恢复前回退备份人工核查') from None
            raise
    xbmc.executebuiltin('RunScript(special://skin/scripts/infuse.py,refresh)')
    xbmc.executebuiltin('ReloadSkin()')


def reset_payload(scope):
    values={k:{'type':v['type'],'value':v['default']} for k,v in keys(scope).items()}
    files={}
    presence={n:False for n in HOME_FILES} if scope in ('home','all') else {}
    return {'skin':values,'images':{},'home_presence':presence},files


def main(action='menu'):
    dialog=xbmcgui.Dialog()
    mode=2 if action=='reset' else dialog.select('YoPlayer 配置', ['备份界面偏好','恢复界面偏好','复位界面偏好'])
    if mode not in (0,1,2):return
    selected=dialog.select('选择范围',list(LABELS))
    if not 0<=selected<len(SCOPES):return
    scope=SCOPES[selected]
    try:
        before=snapshot(scope)
        if mode==0:
            path=saved_archive(pack(scope,*before))
            destination=dialog.browse(0,'可选：导出到文件夹（取消保留本机备份）','files')
            if destination:
                target=str(destination).rstrip('/\\')+'/'+path.name
                if xbmcvfs.exists(target) or not xbmcvfs.copy(str(path),target):
                    raise ValueError('导出未完成，本机备份仍保留')
            dialog.ok('备份完成',str(path)+'\n范围：'+LABELS[selected]);return
        if mode==1:
            path=dialog.browse(1,'选择 YoPlayer ZIP 或旧皮肤 XML 备份','files',mask='.zip|.xml',
                               defaultt=str(paths()[1]))
            if not path:return
            handle=xbmcvfs.File(path)
            try:
                if handle.size()>MAX_TOTAL:raise ValueError('备份文件过大')
                raw=bytes(handle.readBytes())
            finally:handle.close()
            meta,files=unpack(raw)
            details='\n时间：'+meta['created']+'\n版本：'+meta['skin_version']+' / '+meta['home_version']
        else:
            meta,files=reset_payload(scope);details='\n恢复所选范围的界面缺省值。'
        message=('恢复' if mode==1 else '复位')+'范围：'+LABELS[selected]+details+'\n观看记录、续播与登录保持。操作前自动备份。'
        if not dialog.yesno('确认界面偏好操作',message,nolabel='取消',yeslabel='继续',
                            defaultbutton=xbmcgui.DLG_YESNO_NO_BTN):return
        restore(meta,files,scope,before)
    except Exception as exc:
        xbmc.log('YoPlayer UI preferences: '+type(exc).__name__,xbmc.LOGWARNING)
        dialog.ok('配置操作未完成',str(exc))


if __name__=='__main__' and xbmc.getSkinDir()=='skin.yoplayer.infuse':
    main(sys.argv[1] if len(sys.argv)>1 else 'menu')
