"""Restore the addon hub's source focus after native directory navigation."""
import time
import xbmc
import xbmcgui

NATIVE = {'50', '550', '551', '2', '3', '4', '5', '7', '8', '9', '990'}
HUB = {str(i) for i in range(9200, 9205)}
OWNER = 'YoPlayer.AddonFocus.Owner'


class Observer:
    def __init__(self):
        self.entered = None
        self.sent = False

    def target(self, now, root, focus, available, remembered):
        if not root:
            self.entered = None
            self.sent = False
            return None
        if not available:
            self.entered = None
            return None
        if self.entered is None:
            self.entered = now
        if focus in HUB:
            # The user or the native initial onload already chose a hub card.
            self.sent = True
        if self.sent or focus not in NATIVE or now-self.entered < .4:
            return None
        self.sent = True
        return remembered if remembered in HUB else '9200'


def run():
    window = xbmcgui.Window(10040)
    owner = str(time.monotonic())
    window.setProperty(OWNER, owner)
    observer = Observer()
    monitor = xbmc.Monitor()
    try:
        while not monitor.abortRequested() and window.getProperty(OWNER) == owner:
            if not xbmc.getCondVisibility('Window.IsVisible(AddonBrowser)'):
                break
            root = xbmc.getInfoLabel('Container.FolderPath') == 'addons://'
            available = (xbmcgui.getCurrentWindowId() == 10040 and
                         xbmcgui.getCurrentWindowDialogId() == 9999 and
                         not xbmc.getCondVisibility('Container.IsUpdating') and
                         xbmc.getCondVisibility('Control.IsVisible(9200)'))
            target = observer.target(time.monotonic(), root,
                        xbmc.getInfoLabel('System.CurrentControlID'), available,
                        window.getProperty('YoPlayer.AddonHomeFocus'))
            if target:
                xbmc.executebuiltin('SetFocus('+target+')')
            if monitor.waitForAbort(.1):
                break
    finally:
        if window.getProperty(OWNER) == owner:
            window.clearProperty(OWNER)


if __name__ == '__main__':
    run()
