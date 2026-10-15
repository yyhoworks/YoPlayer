"""A bounded owner for the detail preview only, not a playback service."""
import time
import uuid

import xbmc
import xbmcgui

from infuse_detail_play import rpc
from resumeplay import quote


class Preview(xbmc.Player):
    def __init__(self, expected):
        super().__init__()
        self.window = xbmcgui.Window(11130)
        self.detail = xbmcgui.Window(12003)
        self.monitor = xbmc.Monitor()
        self.expected = expected
        self.path = self.detail.getProperty('YoPlayer.Detail.Path')
        self.title = self.detail.getProperty('YoPlayer.Detail.TrailerTitle')
        self.kind = expected.split(':', 1)[0]
        self.url = self.detail.getProperty('YoPlayer.Detail.TrailerURL')
        self.token = uuid.uuid4().hex
        self.owned_path = ''
        self.starts = 0
        self.ended = False
        self.cancelled = False

    def begin(self):
        if (not self.expected or not self.path
                or self.window.getProperty('YoPlayer.Trailer.Active') != 'true'
                or self.window.getProperty('YoPlayer.Trailer.Token')
                or self.detail.getProperty('YoPlayer.Detail.Identity') != self.expected
                or not xbmc.getCondVisibility('Window.IsVisible(movieinformation)')
                or self.isPlaying()):
            return False
        self.window.setProperty('YoPlayer.Trailer.Token', self.token)
        self.window.clearProperty('YoPlayer.Trailer.Error')
        return self.valid()

    def valid(self):
        return (not self.cancelled and not self.monitor.abortRequested()
                and xbmc.getSkinDir() == 'skin.yoplayer.infuse'
                and self.window.getProperty('YoPlayer.Trailer.Active') == 'true'
                and self.window.getProperty('YoPlayer.Trailer.Token') == self.token
                and self.detail.getProperty('YoPlayer.Detail.Identity') == self.expected
                and self.detail.getProperty('YoPlayer.Detail.Path') == self.path
                and xbmc.getCondVisibility('Window.IsVisible(movieinformation)')
                and xbmc.getCondVisibility('Window.IsVisible(1130)'))

    def onPlayBackStarted(self):
        self.starts += 1
        if self.starts > 1:
            self.cancelled = True

    def onPlayBackStopped(self):
        self.cancelled = True

    def onPlayBackEnded(self):
        self.ended = True

    def onPlayBackError(self):
        self.cancelled = True

    def current_path(self):
        try:
            return self.getPlayingFile() if self.isPlayingVideo() else ''
        except RuntimeError:
            return ''

    def owns_playing(self):
        # A replaced player or a resolved URL we could not identify is never stopped.
        return bool(self.owned_path and self.starts <= 1
                    and self.current_path() == self.owned_path)

    def identify(self, requested):
        try:
            players = rpc('Player.GetActivePlayers', {})
            videos = [p for p in players if p.get('type') == 'video']
            if len(videos) != 1:
                return False
            item = rpc('Player.GetItem', {'playerid': videos[0]['playerid'],
                                         'properties': ['file']}).get('item', {})
            actual = self.current_path()
            if actual and (actual == requested or item.get('file') == requested):
                self.owned_path = actual
                return True
        except (RuntimeError, ValueError, TypeError, KeyError):
            pass
        return False

    def error(self, message):
        if self.valid():
            self.window.setProperty('YoPlayer.Trailer.Error', message)

    def play_preview(self, url):
        while self.valid():
            # Async directory/network work must never replace intervening playback.
            if self.isPlaying():
                return
            self.owned_path = ''
            self.starts = 0
            self.ended = False
            xbmc.executebuiltin('PlayMedia(' + quote(url) + ',1,noresume)', True)
            deadline = time.monotonic() + 10
            while self.valid() and time.monotonic() < deadline:
                if self.identify(url):
                    break
                if self.monitor.waitForAbort(.1):
                    return
            if not self.valid():
                return
            if not self.owned_path:
                self.error('无法确认预告片播放身份；请返回后使用原生播放控制。')
                return
            while self.valid() and self.owns_playing() and not self.ended:
                if self.monitor.waitForAbort(.2):
                    return
            if not self.valid() or not self.ended:
                return
            self.owned_path = ''
            if not xbmc.getCondVisibility('Skin.HasSetting(trailerloop)'):
                # Token is checked immediately before closing only our preview.
                if self.valid():
                    xbmc.executebuiltin('Dialog.Close(1130)')
                return

    def close(self):
        # Never stop a background movie merely because its detail was dismissed.
        if self.owns_playing():
            self.stop()
        if self.window.getProperty('YoPlayer.Trailer.Token') == self.token:
            self.window.clearProperty('YoPlayer.Trailer.Token')

