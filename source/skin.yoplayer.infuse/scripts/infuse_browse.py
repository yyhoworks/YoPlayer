"""Route native Kodi show-folder entry into Infuse details, keeping browser history."""
import json
import uuid
from urllib.parse import urlsplit
import xbmc
import xbmcgui


MODE = 'YoPlayer.BrowseOptions.Mode'
RETURN = 'YoPlayer.BrowseOptions.Return'
OWNER = 'YoPlayer.BrowseOptions.Owner'
PAGES = {'sort': (9793, (9760, 9761, 9791)),
         'filter': (9794, (8, 531, 990, 42, 14, 16, 11, 9791)),
         'display': (9795, (21, 5114, 51141, 51142, 9796, 9791)),
         'native': (9796, (43, 45, 20, 41, 9791))}


def options_active():
    return xbmc.getCondVisibility('Window.IsActive(Videos) + !System.HasVisibleModalDialog')


def options_focus(win, mode, candidates, previous):
    """Wait for Kodi's visibility frame, bounded to one second and this action."""
    path = xbmc.getInfoLabel('Container.FolderPath')
    owner = uuid.uuid4().hex
    win.setProperty(OWNER, owner)
    monitor = xbmc.Monitor()
    selected = None
    try:
        # Kodi otherwise auto-focuses the content list when the source row
        # disappears. The existing always-visible mouse relay keeps focus valid
        # across a mode change, so a real user move can still cancel the wait.
        xbmc.executebuiltin('SetFocus(8999)', wait=True)
        for _ in range(6):
            if monitor.waitForAbort(.05):return False
            if (not options_active() or win.getProperty(OWNER) != owner or
                    xbmc.getInfoLabel('Container.FolderPath') != path):return False
            focus = xbmc.getInfoLabel('System.CurrentControlID')
            if focus == '8999':break
            if focus not in ('', '0', str(previous)):return False
        else:return False
        win.setProperty(MODE, mode) if mode else win.clearProperty(MODE)
        for _ in range(20):
            if monitor.waitForAbort(.05):
                return False
            if (not options_active() or win.getProperty(OWNER) != owner or
                    win.getProperty(MODE) != mode or
                    xbmc.getInfoLabel('Container.FolderPath') != path):
                return False
            focus = xbmc.getInfoLabel('System.CurrentControlID')
            # Empty focus is expected while the old page disappears. A valid
            # different focus means the user has already continued navigating.
            if focus not in ('', '0', '8999', str(selected)):
                return False
            if selected is not None and xbmc.getCondVisibility('Control.HasFocus({})'.format(selected)):
                return True
            if selected is None:
                selected = next((ident for ident in candidates
                                 if xbmc.getCondVisibility('Control.IsVisible({}) + Control.IsEnabled({})'.format(ident, ident))), None)
                if selected is not None:
                    # Kodi info conditions can lag the queued focus message.
                    # Send exactly once; repeated messages would later undo Back.
                    xbmc.executebuiltin('SetFocus({})'.format(selected), wait=True)
        return False
    finally:
        if win.getProperty(OWNER) == owner:
            win.clearProperty(OWNER)


def options_enter(page):
    if page not in PAGES or not options_active():
        return False
    win = xbmcgui.Window(10025)
    previous, candidates = PAGES[page]
    expected = 'display' if page == 'native' else ''
    if (win.getProperty(MODE) != expected or
            not xbmc.getCondVisibility('Control.HasFocus({})'.format(previous))):
        return False
    win.setProperty(RETURN, str(previous))
    return options_focus(win, page, candidates, previous)


def options_back():
    """Restore the immediate parent after its controls become visible."""
    if not options_active():
        return False
    win = xbmcgui.Window(10025)
    mode = win.getProperty(MODE)
    if mode not in PAGES:
        return False
    previous = xbmc.getInfoLabel('System.CurrentControlID')
    target = 9796 if mode == 'native' else PAGES[mode][0]
    parent = 'display' if mode == 'native' else ''
    return options_focus(win, parent, (target, 9791) if parent else (target, 9762), previous)


class BrowseRouter:
    def __init__(self, open_series):
        self.open_series = open_series
        self.origin = ''
        self.last_path = ''

    @staticmethod
    def show_id(path):
        url = urlsplit(path)
        parts = url.path.strip('/').split('/')
        if url.scheme == 'videodb' and url.netloc == 'tvshows' and len(parts) >= 2 and parts[0] == 'titles' and parts[1].isdigit():
            return int(parts[1])
        return None

    def poll(self):
        if not xbmc.getCondVisibility('Window.IsActive(Videos) + !System.HasVisibleModalDialog'):
            return
        if xbmc.getCondVisibility('Container.IsUpdating'):
            return
        path = xbmc.getInfoLabel('Container.FolderPath')
        if not path or path == self.last_path:
            return
        self.last_path = path
        if xbmc.getCondVisibility('Container.Content(tvshows)'):
            self.origin = path
            xbmc.executebuiltin('ClearProperty(YoPlayer.Infuse.BrowseShow,Home)')
            # Publish native show folders as information items before a click.
            # Retain the exact source (including library/playlist filters) and
            # current sort; subsequent detail opens never replace this list.
            if not path.startswith('plugin://') and not xbmc.getCondVisibility('Container.IsUpdating'):
                from infuse_library import source
                from infuse import import_actions
                import_actions()
                from library_state import normalize
                from provider import plugin_url
                from actions import builtin_argument
                before, selection = source()
                if before == path:
                    url = plugin_url('native-browse', q=json.dumps(normalize(selection, 'tvshows'), ensure_ascii=False))
                    xbmc.executebuiltin('Container.Update({},replace)'.format(builtin_argument(url)), wait=False)
            return
        if not xbmc.getCondVisibility('Container.Content(seasons) | Container.Content(episodes)'):
            return
        show_id = self.show_id(path)
        if show_id is None:
            return
        if xbmc.getInfoLabel('Window(Home).Property(YoPlayer.Infuse.BrowseShow)') == str(show_id):
            return
        # Kodi handles native folder clicks before skin onclick. Return to the
        # actual originating library (including its smart-playlist filter), then
        # open details. Selecting/cancelling never opens a player or changes progress.
        origin = self.origin or 'videodb://tvshows/titles/'
        xbmc.executebuiltin('Container.Update({},replace)'.format(json.dumps(origin)), wait=True)
        self.open_series(show_id)
