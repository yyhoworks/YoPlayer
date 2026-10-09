"""Move focus after Kodi has made the requested settings page visible."""
import sys
import uuid
import xbmc
import xbmcgui

PAGE = 'YoPlayer.Settings.Page'
REQUEST = 'YoPlayer.Settings.FocusRequest'
TARGETS = {'branding': 1022, 'background': 3152, 'subtitles': 11968,
           'remote': 10111, 'compatibility': 101, 'dependencies': 501}
PARENTS = {11960, 11961, 11963, 11964, 11965, 11966}


def run(page, target):
    if (page and TARGETS.get(page) != target) or (not page and target not in PARENTS):
        return
    if xbmcgui.getCurrentWindowId() != 10035:
        return
    window = xbmcgui.Window(10035)
    token = uuid.uuid4().hex
    window.setProperty(REQUEST, token)
    window.setProperty(PAGE, page)
    monitor = xbmc.Monitor()
    for _ in range(20):
        if monitor.waitForAbort(.05):
            return
        if (xbmcgui.getCurrentWindowId() != 10035 or
                window.getProperty(REQUEST) != token or window.getProperty(PAGE) != page):
            return
        if (page == 'remote' and target == 10111 and
                not xbmc.getCondVisibility('Control.IsVisible(10111)') and
                xbmc.getCondVisibility('Control.IsVisible(9609)') and
                xbmc.getCondVisibility('Control.IsVisible(10112)')):
            window.setFocusId(10112)
            return
        if xbmc.getCondVisibility('Control.IsVisible(%d)' % target):
            window.setFocusId(target)
            return


if __name__ == '__main__' and xbmc.getSkinDir() == 'skin.yoplayer.infuse' and len(sys.argv) == 3:
    run('' if sys.argv[1] == 'parent' else sys.argv[1], int(sys.argv[2]))
