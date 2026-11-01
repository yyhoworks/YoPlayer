"""Open this skin's OSD at a native control; never seek on the entry press.

The separately deployed keymap covers only short Up/Down in FullscreenVideo.
Other skins and live TV retain Kodi's native chapter/large-step actions.
"""
import sys
import xbmc
import xbmcgui


def main(direction):
    if direction not in ('up', 'down'):
        return
    native = 'ChapterOrBigStepForward' if direction == 'up' else 'ChapterOrBigStepBack'
    if xbmc.getSkinDir() != 'skin.yoplayer.infuse' or xbmc.getCondVisibility('VideoPlayer.Content(livetv)'):
        xbmc.executebuiltin('Action(' + native + ')')
        return
    # A late key must not operate a dialog which has opened in the meantime.
    if xbmc.getCondVisibility('System.HasVisibleModalDialog'):
        return
    if xbmc.getCondVisibility('Window.IsVisible(videoosd)'):
        return  # A queued repeat must not reopen a just-closed control bar.
    if not xbmc.getCondVisibility('Window.IsActive(fullscreenvideo) + Player.HasVideo'):
        return
    if direction == 'down' and not xbmc.getCondVisibility('Player.SeekEnabled'):
        direction = 'up'
    xbmcgui.Window(10000).setProperty('YoPlayer.Infuse.OSDEntry', direction)
    xbmc.executebuiltin('ActivateWindow(videoosd)')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) == 2 else '')
