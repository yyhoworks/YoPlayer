"""User-triggered probes and bounded media reads; no playback or library writes."""
import json
import os
from pathlib import Path
import threading
import time
import uuid
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
from infuse_diagnostics import NoRedirect

TIMEOUT=5
READ_LIMIT=64*1024*1024
READ_SECONDS=8
CHUNK=256*1024
READ_OWNER='YoPlayer.Infuse.MediaReadOwner'


class ReadLock:
    """Keep the native lock until the last in-flight VFS call returns."""
    def __init__(self,path=None):
        if path is None:
            path=Path(xbmcvfs.translatePath(xbmcaddon.Addon('skin.yoplayer.infuse').getAddonInfo('profile')))/'media-read.lock'
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        self.fd=os.open(path,os.O_RDWR|os.O_CREAT,0o600)
        try:
            if os.name=='nt':
                import msvcrt
                if os.fstat(self.fd).st_size==0:os.write(self.fd,b'0')
                os.lseek(self.fd,0,0);msvcrt.locking(self.fd,msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            os.close(self.fd);self.fd=None;raise

    def release(self):
        if self.fd is None:return
        try:
            if os.name=='nt':
                import msvcrt
                os.lseek(self.fd,0,0);msvcrt.locking(self.fd,msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(self.fd,fcntl.LOCK_UN)
        finally:os.close(self.fd);self.fd=None


def connections():
    """Exact already-supported Emby config contract; credentials stay in memory."""
    if not xbmc.getCondVisibility('System.AddonIsEnabled(plugin.service.emby-next-gen)'):return [],'Emby 未配置或未启用'
    try:
        if xbmcaddon.Addon('plugin.service.emby-next-gen').getAddonInfo('version')!='11.1.27':return [],'此 Emby 插件版本的连接格式尚未核验'
        root=Path(xbmcvfs.translatePath('special://profile/addon_data/plugin.service.emby-next-gen/'))
        result=[];invalid=0
        for p in sorted(root.glob('servers_*.json'))[:4]:
            try:
                if p.stat().st_size>64*1024:raise ValueError('size')
                config=json.loads(p.read_text(encoding='utf-8'));url=config.get('ServerUrl','').rstrip('/')
                parsed=urlsplit(url)
                ident=config.get('ServerId');token=config.get('AccessToken')
                if not isinstance(ident,str) or not ident or p.stem!='servers_'+ident:raise ValueError('identity')
                if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:raise ValueError('url')
                if not isinstance(token,str) or not token or '\r' in token or '\n' in token:raise ValueError('token')
                result.append({'url':url,'id':ident,'token':token})
            except (OSError,ValueError,TypeError,AttributeError):invalid+=1
        return result, ('部分连接配置不可读或未受支持' if invalid else '没有已登录的 Emby 连接')
    except (OSError,RuntimeError):return [],'Emby 配置不可读取'


def probe(url, token=None, expected_id=None):
    headers={'X-Emby-Token':token} if token else {}
    start=time.monotonic()
    try:
        with build_opener(NoRedirect()).open(Request(url,headers=headers),timeout=TIMEOUT) as response:
            if expected_id:
                raw=response.read(64*1024+1)
                if len(raw)>64*1024 or str(json.loads(raw).get('Id'))!=expected_id:return '已响应，但服务器身份未确认'
            else:response.read(1024)
        return '已响应 · {:.0f} ms'.format((time.monotonic()-start)*1000)
    except HTTPError as exc:
        return '服务器已响应 · HTTP '+str(exc.code)+'（认证/路由需检查）'
    except (OSError,ValueError,RuntimeError):return '请求未确认（超时、解析或连接失败）'


def detect():
    dialog=xbmcgui.Dialog();progress=xbmcgui.DialogProgress();progress.create('检测网络状态','各项独立检测；每个请求最多 5 秒，取消后不再发起下一项。')
    rows=[]
    try:
        connected=xbmc.getCondVisibility('System.HasNetwork')
        ip=xbmc.getInfoLabel('Network.IPAddress').strip()
        rows.append('局域网链路：'+('已连接（不代表 NAS 或网关已响应）' if connected and ip not in {'','127.0.0.1','0.0.0.0','::1'} else '未确认有效本机地址/链路'))
        conns,reason=connections()
        if not conns:rows.append('Emby：'+reason)
        for i,conn in enumerate(conns):
            if progress.iscanceled() or xbmc.Monitor().abortRequested():rows.append('其余检测已取消');break
            progress.update(20+i*10,'正在检测已配置 Emby '+str(i+1))
            rows.append('Emby '+str(i+1)+'：'+probe(conn['url']+'/System/Info',conn['token'],conn['id']))
        if progress.iscanceled() or xbmc.Monitor().abortRequested():rows.append('外网探测：已取消')
        else:
            progress.update(80,'正在探测 Kodi 官网 HTTPS；不代表全部外网可用')
            rows.append('外网探测（www.kodi.tv）：'+probe('https://www.kodi.tv/'))
    finally:progress.close()
    dialog.textviewer('网络检测结果','\n\n'.join(rows)+'\n\n只读链路与 HTTP 请求，没有播放、扫描、刷新媒体或重启网络。取消在当前有界请求返回后生效；最多检测四个已配置 Emby。')


def readable_path(path):
    parsed=urlsplit(path)
    # Explicit set: an empty-string containment test must not admit all schemes.
    scheme=parsed.scheme.lower()
    if len(scheme)==1 and len(path)>2 and path[1]==':' and path[2] in '/\\':scheme=''
    return scheme in {'','smb','nfs','http','https'} and path.lower().split('?',1)[0].endswith(('.mkv','.mp4','.m2ts','.ts','.avi','.mov','.webm'))


def read_sample(path, stop, result, player, opener=xbmcvfs.File, clock=time.monotonic):
    stream=None;start=clock();count=0
    try:
        if stop.is_set() or player.isPlaying():raise RuntimeError('播放中止')
        # HTTP VFS timeouts are explicit. Other VFS providers own their I/O timeout.
        target=path+('|' if '|' not in path else '&')+'connection-timeout=5' if urlsplit(path).scheme in {'http','https'} else path
        stream=opener(target)
        while count<READ_LIMIT and clock()-start<READ_SECONDS:
            if stop.is_set() or player.isPlaying():raise RuntimeError('已取消或播放开始')
            chunk=stream.readBytes(min(CHUNK,READ_LIMIT-count))
            if not chunk:break
            count+=len(chunk);result['bytes']=count
        elapsed=max(.001,clock()-start)
        if stop.is_set() or player.isPlaying():raise RuntimeError('已取消或播放开始')
        result.update(status='ok' if count else 'empty',bytes=count,elapsed=elapsed,mbps=count/1048576/elapsed)
    except (OSError,RuntimeError):result['status']='cancelled' if stop.is_set() or player.isPlaying() else 'failed'
    finally:
        if stream:
            try:stream.close()
            except (OSError,RuntimeError):pass
        result['done']=True


def speed():
    dialog=xbmcgui.Dialog();player=xbmc.Player();home=xbmcgui.Window(10000)
    if player.isPlaying():dialog.ok('媒体读取测速','请结束播放后再测速，避免占用播放带宽。');return
    if home.getProperty(READ_OWNER):dialog.ok('媒体读取尚未结束','上一次取消的原生文件读取仍在返回，请稍后重试。');return
    if not dialog.yesno('媒体读取测速','读取所选 NAS/挂载网盘媒体：最多 64 MiB / 8 秒，每次 256 KiB。结果是文件读取速度，可能含缓存；不是宽带测速。取消或开始播放后停止下一次读取。',nolabel='取消',yeslabel='选择媒体',defaultbutton=xbmcgui.DLG_YESNO_NO_BTN):return
    path=dialog.browse(1,'选择可读媒体文件','video',mask='.mkv|.mp4|.m2ts|.ts|.avi|.mov|.webm')
    if not path:return
    if not readable_path(path):dialog.ok('媒体读取不可用','仅支持本地、SMB、NFS、HTTP(S)实际媒体文件；不读取插件路由或 STRM 清单。');return
    if player.isPlaying() or home.getProperty(READ_OWNER):dialog.ok('测速取消','播放或读取状态已改变。');return
    try:lock=ReadLock()
    except OSError:dialog.ok('测速不可用','另一个文件读取尚未结束，或测速互斥文件不可写。');return
    if player.isPlaying():lock.release();dialog.ok('测速取消','播放已经开始。');return
    token=uuid.uuid4().hex;home.setProperty(READ_OWNER,token)
    stop=threading.Event();result={};progress=xbmcgui.DialogProgress();progress.create('媒体读取测速','读取所选媒体；返回可取消')
    def worker():
        try:read_sample(path,stop,result,player)
        finally:
            if home.getProperty(READ_OWNER)==token:home.clearProperty(READ_OWNER)
            lock.release()
    threading.Thread(target=worker,daemon=True).start();start=time.monotonic();monitor=xbmc.Monitor()
    try:
        while not result.get('done'):
            if progress.iscanceled() or player.isPlaying() or monitor.abortRequested() or time.monotonic()-start>=READ_SECONDS:
                stop.set();break
            progress.update(min(99,int(100*result.get('bytes',0)/READ_LIMIT)),'已读 {:.1f} MiB'.format(result.get('bytes',0)/1048576))
            monitor.waitForAbort(.1)
    finally:progress.close()
    if not result.get('done'):
        dialog.ok('读取正在结束','已停止后续分块读取。当前 VFS 调用由系统返回后释放；原生 SMB/NFS 超时无法由皮肤强制缩短，期间禁止重开测速。');return
    if stop.is_set() or result.get('status')!='ok':dialog.ok('测速未完成','已取消、播放开始、文件为空或读取失败；没有可确认的平均速度。');return
    dialog.ok('媒体读取结果','平均 {:.2f} MiB/s\n读取 {:.1f} MiB · {:.2f} 秒\n样本可能来自系统缓存，未清除缓存。'.format(result['mbps'],result['bytes']/1048576,result['elapsed']))
