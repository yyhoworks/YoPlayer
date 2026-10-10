"""Keep the existing credits countdown bound to its dialog and playing file."""
import time
import xbmc
import xbmcgui
from tvjump import current_video_path

WINDOW = 11122
PATH = 'YoPlayer.Infuse.Skip.Path'
TOKEN = 'YoPlayer.Infuse.Skip.Token'


def main():
    window = xbmcgui.Window(WINDOW)
    owner = window.getProperty(PATH)
    token = window.getProperty(TOKEN)
    if not owner:
        owner = current_video_path()
        if owner is None:
            xbmc.executebuiltin('Dialog.Close(1122)')
            return
        token = str(time.monotonic_ns())
        window.setProperty(PATH, owner)
        window.setProperty(TOKEN, token)

    def owns_dialog():
        return window.getProperty(PATH) == owner and window.getProperty(TOKEN) == token

    def visible():
        return xbmc.getCondVisibility('Window.IsVisible(1122)')

    def ready():
        return owns_dialog() and visible() and current_video_path(owner) is not None

    def action_focused():
        try:
            return window.getFocusId() == 11221
        except RuntimeError:
            return False

    monitor = xbmc.Monitor()
    try:
        if not ready():
            if owns_dialog() and visible():
                xbmc.executebuiltin('Dialog.Close(1122)')
            return
        episode = xbmc.getInfoLabel('VideoPlayer.Episode')
        # The XML supplies default focus. Preserve Cancel selected while the
        # Python invoker was starting rather than resetting that choice.
        if (episode.isdigit() and xbmc.getCondVisibility('Control.IsVisible(11220)')
                and window.getFocusId() != 11222):
            xbmc.executebuiltin(f'SetFocus(11220,{episode},absolute)')
            if ready():
                xbmc.executebuiltin('SetFocus(11221)')
        if monitor.waitForAbort(0.5):
            return
        focused_since = None
        automatic = True
        while not monitor.abortRequested():
            if not owns_dialog() or not visible():
                break
            if current_video_path(owner) is None:
                if owns_dialog() and visible():
                    xbmc.executebuiltin('Dialog.Close(1122)')
                break
            focused = action_focused()
            if automatic and focused:
                if focused_since is None:
                    focused_since = time.monotonic()
                if time.monotonic() - focused_since >= 3:
                    if ready() and action_focused():
                        xbmc.executebuiltin('Action(Select,11122)')
                    break
            elif focused_since is not None:
                # Keep stop detection alive after moving focus to Cancel,
                # without re-enabling the existing automatic selection.
                automatic = False
            if monitor.waitForAbort(0.2):
                break
    finally:
        if owns_dialog():
            window.clearProperty(PATH)
            window.clearProperty(TOKEN)


if __name__ == '__main__':
    main()
