"""Open read-only diagnostics and restore its summary-page focus on return."""
import sys
import xbmc
import xbmcgui

OWNER='YoPlayer.Diagnostics.Parent'


def run(mode):
    if xbmc.getSkinDir()!='skin.yoplayer.infuse':return
    home=xbmcgui.Window(10000)
    if mode=='open':
        if not xbmc.getCondVisibility('Window.IsActive(playerprocessinfo)'):return
        parent=xbmcgui.getCurrentWindowDialogId()
        if xbmcgui.Window(parent).getFocusId()!=303:return
        home.setProperty(OWNER,str(parent))
        xbmc.executebuiltin('ActivateWindow(1196)',False)
    elif mode=='return':
        owner=home.getProperty(OWNER)
        if not owner.isdigit():return
        monitor=xbmc.Monitor()
        for _ in range(20):
            if monitor.waitForAbort(.05) or home.getProperty(OWNER)!=owner:return
            if xbmc.getCondVisibility('Window.IsVisible(1196)'):continue
            if (xbmcgui.getCurrentWindowDialogId()!=int(owner) or
                    not xbmc.getCondVisibility('Window.IsActive(playerprocessinfo)')):break
            if xbmc.getCondVisibility('Control.IsVisible(303)'):
                xbmcgui.Window(int(owner)).setFocusId(303)
                break
        if home.getProperty(OWNER)==owner:home.clearProperty(OWNER)


if __name__=='__main__':run(sys.argv[1] if len(sys.argv)>1 else '')
