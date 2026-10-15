"""Identity-scoped compatibility resume; no database writes or synthetic clicks.

The native option retains Kodi's selected video version / disc-menu flow.
Compatibility resume starts that exact file without a saved disc state, then
seeks once, absolutely, only after Kodi identifies the expected media.
"""
import math
import sys
import time

import xbmc
import xbmcgui

from infuse_detail_play import exclusive, rpc


def identity():
    return tuple(xbmc.getInfoLabel('ListItem.' + key).strip()
                 for key in ('DBType', 'DBID', 'FileNameAndPath'))


def detail_identity():
    window = xbmcgui.Window(12003)
    pair = window.getProperty('YoPlayer.Detail.Identity').split(':', 1)
    return tuple(pair + [window.getProperty('YoPlayer.Detail.Path')]) if len(pair) == 2 else ('', '', '')


def quote(value):
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


class PlaybackAttempt(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self.started = 0
        self.ready = False
        self.cancelled = False
        self.armed = False

    def onNotification(self, sender, method, data):
        if not self.armed:
            if method in ('Player.OnPlay', 'Player.OnStop', 'Player.OnAVStart'):
                self.cancelled = True
            return
        if method in ('Player.OnStop', 'Player.OnError'):
            self.cancelled = True
        elif method == 'Player.OnPlay':
            self.started += 1
            if self.started > 1:
                self.cancelled = True
        elif method == 'Player.OnAVStart':
            self.ready = True


class ISOResumeExtractor:
    """Keep the public entry used by infuse_playback_return and context menus."""
    def __init__(self):
        self.in_video_info = xbmc.getCondVisibility('Window.IsVisible(movieinformation)')
        self.context = detail_identity() if self.in_video_info else identity()
        self.folder_play = 'folderplay' in sys.argv[1:]
        self.session = PlaybackAttempt()

    def same_selection(self):
        return (xbmc.getSkinDir() == 'skin.yoplayer.infuse'
                and not self.session.cancelled
                and not self.session.abortRequested()
                and (detail_identity() if self.in_video_info else identity()) == self.context
                and (not self.in_video_info
                     or xbmc.getCondVisibility('Window.IsVisible(movieinformation)')))

    def resume_position(self):
        kind, ident, path = self.context
        if kind not in ('movie', 'episode') or not ident.isdigit() or int(ident) <= 0 or not path:
            return None
        method = 'VideoLibrary.Get' + kind.title() + 'Details'
        try:
            row = rpc(method, {kind + 'id': int(ident),
                              'properties': ['file', 'resume']}).get(kind + 'details', {})
            # No basename, LIKE, nearest-time or default-version guessing.
            if row.get(kind + 'id') != int(ident) or row.get('file') != path:
                return None
            position = float((row.get('resume') or {}).get('position', 0))
            return position if math.isfinite(position) and position > 0 else None
        except (RuntimeError, ValueError, TypeError, KeyError):
            return None

    def native(self):
        if not self.same_selection():
            return
        if self.in_video_info:
            xbmc.executebuiltin('SendClick(12003,8)')
        elif self.context[2]:
            xbmc.executebuiltin('PlayMedia(' + quote(self.context[2]) + ')')

    def matches_playing(self):
        kind, ident, path = self.context
        try:
            players = rpc('Player.GetActivePlayers', {})
            videos = [p for p in players if p.get('type') == 'video']
            if len(videos) != 1:
                return False
            row = rpc('Player.GetItem', {'playerid': videos[0]['playerid'],
                                        'properties': ['file']}).get('item', {})
            # RPC must retain the typed library identity AND the exact file.
            # Resolved plugin/disc paths without that proof are not guessed.
            return (row.get('type') == kind and str(row.get('id')) == ident
                    and row.get('file') == path)
        except (RuntimeError, ValueError, TypeError, KeyError):
            return False

    def seek_once(self, position):
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if (self.session.cancelled or self.session.abortRequested()
                    or xbmc.getSkinDir() != 'skin.yoplayer.infuse'):
                return False
            if self.session.ready:
                if not self.matches_playing():
                    return False
                # Recheck immediately before the absolute Python API operation.
                if self.session.cancelled or not self.matches_playing():
                    return False
                xbmc.Player().seekTime(position)
                return True
            if self.session.waitForAbort(.1):
                return False
        return False

    def run(self):
        with exclusive() as acquired:
            if not acquired or not self.same_selection():
                return
            position = self.resume_position()
            if not self.same_selection():
                return
            if self.folder_play:
                # Close only the context menu; never synthesize Select/Down.
                xbmc.executebuiltin('Dialog.Close(contextmenu,true)', True)
            if position is None:
                self.native()
                return
            stamp = '{}:{:02d}:{:02d}'.format(int(position)//3600,
                                             int(position)//60%60, int(position)%60)
            choice = xbmcgui.Dialog().contextmenu([
                '从 {} 续播（兼容字幕/音轨）'.format(stamp),
                '从头播放当前版本', '原生播放选项'])
            if choice not in (0, 1, 2) or not self.same_selection():
                return
            if choice == 2:
                self.native()
                return
            # Re-read after the user's choice; do not reuse a stale resume value.
            current = self.resume_position()
            if current is None or not self.same_selection():
                return
            if self.in_video_info:
                xbmc.executebuiltin('Dialog.Close(movieinformation,true)', True)
                # Closing is asynchronous. A newly opened detail cancels this handoff.
                deadline = time.monotonic() + 2
                while xbmc.getCondVisibility('Window.IsVisible(movieinformation)'):
                    if time.monotonic() >= deadline or self.session.waitForAbort(.05):
                        return
                if xbmcgui.Window(12003).getProperty('YoPlayer.Detail.Identity'):
                    return
            if self.session.cancelled or self.session.abortRequested():
                return
            self.session.armed = True
            xbmc.executebuiltin('PlayMedia(' + quote(self.context[2]) + ',noresume)', True)
            if choice == 0 and not self.seek_once(current) and not self.session.cancelled:
                xbmc.log('YoPlayer: compatibility resume not applied; exact playback identity unavailable',
                         xbmc.LOGWARNING)


if __name__ == '__main__':
    ISOResumeExtractor().run()
