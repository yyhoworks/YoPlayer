"""Live metrics for the home system overview; platform tools stay explicit."""
import ctypes
import json
import math
import os
import platform
import re
import sys
import time
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

PREFIX='YoPlayer.Infuse.System.'
HOME=xbmcgui.Window(10000)
LAST_CPU=None


def cpu_publish(current):
    global LAST_CPU
    n=len(current)
    if LAST_CPU and len(LAST_CPU)==n:
        loads=[max(0,min(100,100*(1-(idle-oldidle)/max(1,total-oldtotal)))) for (idle,total),(oldidle,oldtotal) in zip(current,LAST_CPU)]
        avg=sum(loads)/len(loads);put('CpuAvailable','true');put('CpuRing',round(avg));put('CpuAverage','CPU 平均 · {:.1f}%'.format(avg));put('CpuPercent','{:.1f}%'.format(avg))
        for i in range(4):
            lo=math.floor(i*n/4);hi=math.floor((i+1)*n/4);chunk=loads[lo:hi]
            if chunk:
                value=sum(chunk)/len(chunk);put('Core'+str(i),round(value));put('CoreText'+str(i),'{:.1f}%'.format(value));put('CoreLabel'+str(i),str(lo+1) if hi-lo==1 else '{}–{}'.format(lo+1,hi))
            else:put('Core'+str(i),0);put('CoreText'+str(i),'—');put('CoreLabel'+str(i),'—')
    LAST_CPU=current;put('CpuModel',str(n)+' 逻辑核心')


def put(name,value):HOME.setProperty(PREFIX+name,str(value))

def label(name,fallback='未提供'):
    value=xbmc.getInfoLabel(name).strip()
    return fallback if value.lower() in {'','busy','忙','忙碌'} else value
def rpc(method,params):
    r=json.loads(xbmc.executeJSONRPC(json.dumps(dict(jsonrpc='2.0',id=1,method=method,params=params))))
    if 'error' in r:raise RuntimeError(method)
    return r['result']


def library():
    for key,method in [('Movies','VideoLibrary.GetMovies'),('Shows','VideoLibrary.GetTVShows'),('Episodes','VideoLibrary.GetEpisodes'),('MusicVideos','VideoLibrary.GetMusicVideos')]:
        try:
            base=dict(limits={'start':0,'end':1})
            total=rpc(method,base)['limits']['total']
            unseen=rpc(method,dict(base,filter={'field':'playcount','operator':'is','value':'0'}))['limits']['total']
            put(key,total);put(key+'Unwatched',unseen);put(key+'Watched',total-unseen)
        except (RuntimeError,KeyError):put(key,'—');put(key+'Unwatched','—');put(key+'Watched','—')
    for key,method in [('Songs','AudioLibrary.GetSongs'),('Albums','AudioLibrary.GetAlbums'),
                       ('Artists','AudioLibrary.GetArtists')]:
        try:put(key,rpc(method,dict(limits={'start':0,'end':1}))['limits']['total'])
        except (RuntimeError,KeyError):put(key,'—')


def windows_metrics():
    class Mem(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(k,ctypes.c_ulonglong) for k in ['total','avail','totalpage','availpage','totalvirtual','availvirtual','extended']]
    m=Mem();m.length=ctypes.sizeof(m)
    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        put('MemoryAvailable','true')
        put('MemoryRing',m.load);put('MemoryPercent',str(m.load)+'%')
        put('MemoryDetail','{:.1f} / {:.1f} GB'.format((m.total-m.avail)/1073741824,m.total/1073741824))
        put('MemoryTotal','{:.1f} GB'.format(m.total/1073741824))
        put('MemoryUsage','{:.1f} GB 已用 · {:.1f} GB 可用'.format((m.total-m.avail)/1073741824,m.avail/1073741824))
    class Perf(ctypes.Structure):
        _fields_=[(k,ctypes.c_longlong) for k in ['idle','kernel','user','dpc','interrupt']]+[('count',ctypes.c_ulong)]
    n=os.cpu_count() or 1;a=(Perf*n)();size=ctypes.c_ulong()
    status=ctypes.windll.ntdll.NtQuerySystemInformation(8,ctypes.byref(a),ctypes.sizeof(a),ctypes.byref(size))
    if status==0:
        cpu_publish([(p.idle,p.kernel+p.user) for p in a])


def linux_metrics():
    with open('/proc/stat') as f:
        rows=[line.split()[1:] for line in f if line.startswith('cpu') and line.split()[0]!='cpu']
    values=[[int(v) for v in row] for row in rows]
    if values:cpu_publish([(v[3]+(v[4] if len(v)>4 else 0),sum(v[:8])) for v in values])


def metrics():
    put('CpuAvailable','false');put('CpuPercent','—')
    put('MemoryAvailable','false');put('MemoryPercent','—')
    put('MemoryTotal','—');put('MemoryUsage','设备未提供')
    put('Screen',label('System.ScreenWidth','—')+' × '+label('System.ScreenHeight','—'))
    mode=label('System.ScreenMode')
    rate=re.search(r'@\s*([\d.]+)\s*Hz',mode,re.I)
    put('ScreenMeta',(rate.group(1)+' Hz · ' if rate else '')+('全屏' if 'fullscreen' in mode.lower() else '窗口' if 'window' in mode.lower() else mode))
    put('IP',label('Network.IPAddress'));put('Link',label('Network.LinkState'))
    put('Connected','已连接' if xbmc.getCondVisibility('System.HasNetwork') else '未连接')
    put('Uptime',label('System.Uptime'));put('TotalUptime',label('System.TotalUptime'))
    temp=label('System.CPUTemperature','—')
    if temp.lower() in {'n/a','na','unknown','unavailable','not available','不可用','未提供','?','0°c'}:temp='—'
    put('Temperature',temp)
    put('TemperatureText','设备未提供' if temp=='—' else temp)
    put('HDR',label('System.SupportedHDRTypes','未提供').replace(',',' · '))
    ce=xbmc.getCondVisibility('System.HasAddon(service.coreelec.settings)')
    if ce:
        try:
            dv=rpc('Settings.GetSettingValue',{'setting':'coreelec.amlogic.dolbyvision.type'})['value']
            inject=rpc('Settings.GetSettingValue',{'setting':'coreelec.amlogic.dolbyvision.vsvdb.inject'})['value']
            put('DolbyVision',{0:'DV-std',1:'DV-LL',2:'HDR-444',3:'VS10 Only',4:'HDR-422'}.get(dv,'未提供')+' · VSVDB '+('ON' if inject else 'OFF'))
        except (RuntimeError,KeyError):put('DolbyVision','杜比视界模式未提供')
    else:put('DolbyVision','CoreELEC 杜比视界模式不适用')
    put('DisplayAction','杜比视界' if xbmc.getCondVisibility('System.HasAddon(service.coreelec.settings)') else '显示设置')
    put('LogAction','查看运行日志')
    put('VersionLabel','固件版本' if ce else '系统版本')
    if platform.system()=='Windows':
        try:windows_metrics()
        except (OSError,AttributeError,ValueError):pass
    else:
        try:linux_metrics()
        except (OSError,ValueError):pass
        raw=label('System.Memory(used.percent)','').replace('%','')
        try:
            mem=float(raw)
            if math.isfinite(mem) and 0<=mem<=100:
                put('MemoryAvailable','true');put('MemoryRing',round(mem));put('MemoryPercent','{:g}%'.format(mem))
        except ValueError:pass
        put('MemoryDetail',label('System.Memory(used)','—')+' / '+label('System.Memory(total)','—'))
        put('MemoryTotal',label('System.Memory(total)','—'))
        put('MemoryUsage',label('System.Memory(used)','—')+' 已用 · '+label('System.Memory(free)','—')+' 可用')
    put('Status','实时设备信息 · '+platform.system()+(' · '+str(os.cpu_count())+' 逻辑核心以四组平均负载显示' if (os.cpu_count() or 1)>4 else '')+' · '+time.strftime('%H:%M:%S'))
    # Prefer the original CE metadata; provide explicit read-only fallbacks when
    # this independent homepage has not run Minsk's original startup scripts.
    hardware=label('Skin.String(hwtype)','')
    if not hardware and ce:
        try:
            with open('/proc/device-tree/model') as f:hardware=f.read().strip('\x00\n ')
        except OSError:pass
    put('Hardware',hardware or platform.machine() or '未提供')
    put('Capacity',label('Skin.String(memtotal)',HOME.getProperty(PREFIX+'MemoryTotal') or '未提供')+
        (' + '+label('Skin.String(hdtotal)') if label('Skin.String(hdtotal)','') else ''))
    put('LinkSpeed',label('Skin.String(netspeed)','未提供'))
    put('Firmware',label('Skin.String(version)',HOME.getProperty(PREFIX+'PlatformVersion') or '未提供'))
    put('KernelBuild',label('Skin.String(BuildDate)',platform.version()))
    try:
        value=rpc('Settings.GetSettingValue',{'setting':'videoplayer.adjustrefreshrate'})['value']
        put('RefreshMode',{0:'关闭',1:'始终',2:'起播和停止',3:'起播时'}.get(value,'未提供'))
    except (RuntimeError,KeyError):put('RefreshMode',label('Skin.String(refreshrate)'))


def run(action):
    if action == 'native-versions':
        fields = [('Kodi', label('System.BuildVersion')), ('编译日期', label('System.BuildDate')),
                  ('操作系统', label('System.OSVersionInfo', platform.platform())),
                  ('内核', label('System.KernelVersion', platform.release())),
                  ('皮肤', xbmcaddon.Addon('skin.yoplayer.infuse').getAddonInfo('version')),
                  ('首页数据', xbmcaddon.Addon('plugin.video.yoplayer.home').getAddonInfo('version'))]
        xbmcgui.Dialog().textviewer('版本与构建信息', '\n\n'.join(k+'：'+v for k,v in fields))
        return
    ce=xbmc.getCondVisibility('System.HasAddon(service.coreelec.settings)')
    if action=='tools':
        from infuse_system_tools import show
        show()
        return
    if action in {'logs','speed','refreshnetwork','framerate'}:
        from infuse_system_tools import perform
        perform({'logs':'logs','speed':'speed','refreshnetwork':'detect','framerate':'refresh-rate'}[action])
        return
    scripts={'framerate':'refreshrate.py','kernel':'cetranscpm.py,select','display':'dvoption.py,set','network':'ipconfig.py','reset':'resettime.py','speed':'speedtest.py','refreshnetwork':'ethtool.py,refresh','changelog':'updatelog.py'}
    if action not in {'refresh','once'}:
        if action=='kernel':
            from infuse_device import dispatch
            dispatch('kernel')
            return
        if not ce and action in {'framerate','display','network'}:
            target={'framerate':'PlayerSettings','display':'SystemSettings','network':'ServiceSettings'}[action]
            xbmc.executebuiltin('Dialog.Close(1182)')
            xbmc.executebuiltin('ActivateWindow('+target+')')
            return
        if action=='changelog':
            xbmc.executebuiltin('RunScript(special://skin/scripts/updatelog.py)')
            return
        if not ce:
            xbmcgui.Dialog().ok('CoreELEC 工具','当前运行在 '+platform.system()+'，此工具仅用于 CoreELEC 设备。')
            return
        if action in scripts:xbmc.executebuiltin('RunScript(special://skin/scripts/'+scripts[action]+')')
        return
    token=str(time.monotonic())
    if action=='refresh':put('Owner',token)
    for k in ['CpuAvailable','MemoryAvailable']:put(k,'false')
    put('CpuPercent','—');put('MemoryPercent','—');put('MemoryUsage','正在读取内存信息');put('MemoryTotal','—')
    addon=xbmcaddon.Addon('skin.yoplayer.infuse');put('Skin','YoPlayer · Infuse  '+addon.getAddonInfo('version'))
    os_name=platform.system()
    if ce:
        try:
            with open('/etc/os-release') as f:
                release=dict(line.strip().split('=',1) for line in f if '=' in line)
            os_name=release.get('PRETTY_NAME','CoreELEC').strip('"')
        except (OSError,ValueError):os_name='CoreELEC（固件版本未提供）'
    put('OS',os_name+' · Kodi '+label('System.BuildVersion'))
    put('DeviceName','CoreELEC' if ce else platform.system())
    put('PlatformVersion',os_name)
    put('PlayerVersion',label('System.BuildVersion').split(' ')[0])
    put('SkinVersion',addon.getAddonInfo('version'))
    put('Kernel',platform.version() if platform.system()=='Windows' else label('System.KernelVersion',platform.release()))
    library();metrics()
    if action=='once':return
    monitor=xbmc.Monitor();tick=0
    while not monitor.abortRequested() and xbmc.getCondVisibility('Window.IsVisible(11182) | Window.IsVisible(11183) | Window.IsVisible(11184) | Window.IsVisible(11185) | Window.IsVisible(11194) | Window.IsVisible(SystemInfo)') and HOME.getProperty(PREFIX+'Owner')==token:
        if monitor.waitForAbort(1):break
        metrics();tick+=1
        if tick%30==0:library()


if __name__=='__main__':run(sys.argv[1] if len(sys.argv)>1 else 'refresh')
