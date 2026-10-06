"""Size the native shared power menu; no action is dispatched on opening."""
import xbmc
import xbmcgui
from infuse_device import capabilities, publish

POWER=('poweroff','reboot','android','fastoff')
MAINTENANCE=('quit','restartkodi','reload','kernel')
IDS={'poweroff':3,'reboot':8,'android':13,'fastoff':31,'quit':2,'restartkodi':14,'reload':85,'kernel':4}


def menu_layout(supported):
    available=dict(supported, poweroff=bool(supported.get('poweroff') or supported.get('powerdown')),reload=True)
    rows=[key for key in POWER+MAINTENANCE if available.get(key)]
    groups=int(any(key in rows for key in POWER))+int(any(key in rows for key in MAINTENANCE))
    body=min(540,max(106,len(rows)*106+groups*32+max(0,len(rows)+groups-1)*16))
    height=116+body+128
    return {'rows':rows,'body':body,'height':height,'top':(1080-height)//2}


def layout_window(window, supported):
    layout=menu_layout(supported)
    window.getControl(9005).setPosition(550,layout['top'])
    window.getControl(9100).setHeight(layout['height'])
    # Kodi's Python Window.getControl does not wrap native grouplists. Keep
    # their XML viewport at the 540px maximum; short menus contain only their
    # natural 446px (or fewer) rows, so the footer occupies empty list space.
    window.getControl(9101).setPosition(40,116+layout['body']+16)
    window.setFocus(window.getControl(IDS[layout['rows'][0]] if layout['rows'] else 1002))


def main():
    if xbmc.getSkinDir()!='skin.yoplayer.infuse':return
    publish()
    home=xbmcgui.Window(10000)
    home.setProperty('YoPlayer.Infuse.PowerHelp','方向键选择操作；返回键关闭菜单')
    # RunScript from native onload may be scheduled before all controls attach.
    monitor=xbmc.Monitor()
    for _ in range(10):
        if not xbmc.getCondVisibility('Window.IsVisible(ShutdownMenu)'):return
        try:
            layout_window(xbmcgui.Window(10111),capabilities())
            return
        except RuntimeError:
            if monitor.waitForAbort(0.1):return
    xbmc.log('YoPlayer power menu layout was not ready',xbmc.LOGWARNING)


if __name__=='__main__':main()
