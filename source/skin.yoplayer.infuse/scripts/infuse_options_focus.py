"""Recover an empty Options-page focus after Kodi refreshes its visibility."""
import sys
import uuid
import xbmc
import xbmcgui

TARGETS = {'options':11100, 'playback':11110, 'continuous':11160, 'video':11120,
           'technical':11140, '3d':11200}
OWNER = 'YoPlayer.OptionsFocusOwner'
# Kodi Control.IsVisible(child) does not include ancestor visibility. Keep the
# mutually exclusive page ownership explicit; an offline check verifies this
# table against the XML controls and each page's scrollbar.
PAGE_CONTROLS = {
    11100: (11100, 205, 11150, 11151, 11152, 208, 206, 106, 22400),
    11110: (11110, 11101, 11136,
            103, 1031, 108, 1081, 101, 102, 109, 110, 111, 104,
            107, 11135, 22410),
    11160: (11160, 11105, 11106, 22460),
    11120: (11120, 201, 1110200, 1110201, 1110202, 1110203, 11103, 203, 22420),
    11140: (11140, 11102, 11107, 11104, 22440),
    11200: (11200, 11201, 11202, 11203, 22500),
}


def recover(mode):
    target = TARGETS.get(mode)
    if target is None:
        return
    home = xbmcgui.Window(10000)
    window = xbmcgui.Window(11114)
    monitor = xbmc.Monitor()
    token = uuid.uuid4().hex

    def current(check_owner=True):
        if (xbmc.getSkinDir() != 'skin.yoplayer.infuse'
                or xbmcgui.getCurrentWindowDialogId() != 11114
                or not xbmc.getCondVisibility('Window.IsActive(1114)')
                or home.getProperty('optionsdialog_content') != mode
                or (check_owner and home.getProperty(OWNER) != token)):
            return False
        try:
            focused = window.getFocusId()
        except RuntimeError:
            focused = 0
        owner = next((group for group, controls in PAGE_CONTROLS.items()
                      if focused in controls), None)
        if owner is not None and (owner != target or not xbmc.getCondVisibility('Control.IsVisible(%s)' % owner)):
            return True
        if (focused == 11191 and mode != 'options') or (focused == 11192 and mode == 'options'):
            return True
        # Preserve all valid focus, including the return button and any child
        # reached by a remote key while this short visibility wait is running.
        return not (focused > 0
                    and xbmc.getCondVisibility('Control.IsVisible(%s)' % focused)
                    and xbmc.getCondVisibility('Control.IsEnabled(%s)' % focused))

    if not current(False):
        return
    home.setProperty(OWNER, token)
    try:
        for _ in range(20):
            if monitor.waitForAbort(.03) or not current():
                return
            if xbmc.getCondVisibility('Control.IsVisible(%s)' % target):
                if current():
                    xbmc.executebuiltin('SetFocus(%s)' % target, True)
                return
    finally:
        if home.getProperty(OWNER) == token:
            home.clearProperty(OWNER)


if __name__ == '__main__':
    recover(sys.argv[1] if len(sys.argv) > 1 else '')
