"""Return skin-owned detail playback to native information after it stops.

This helper observes Kodi notifications. It never stops, seeks or starts a
player, writes a media record, or changes audio/output settings.
"""
import hashlib
import json
import sys
import time
import uuid
import xbmc
import xbmcgui

SKIN = 'skin.yoplayer.infuse'
OWNER = 'YoPlayer.PlaybackReturn.Owner'


def rpc(method, params=None):
    response = json.loads(xbmc.executeJSONRPC(json.dumps({
        'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}})))
    if 'error' in response:
        raise RuntimeError('Native detail state unavailable')
    return response.get('result', {})


def capture(episode=None):
    """Capture only an explicit Play from the currently active detail."""
    if (xbmc.getSkinDir() != SKIN
            or not xbmc.getCondVisibility('Window.IsActive(movieinformation)')
            or rpc('Player.GetActivePlayers')):
        return None
    kind = xbmc.getInfoLabel('ListItem.DBType')
    ident = xbmc.getInfoLabel('ListItem.DBID')
    if not ident.isdigit() or int(ident) <= 0:
        return None
    context = {'base': xbmcgui.getCurrentWindowId()}
    if episode is not None:
        win = xbmcgui.Window(12003)
        if (kind not in ('tvshow', 'season', 'episode')
                or win.getProperty('YoPlayer.DetailSeasons.EpisodeID') != str(episode['episodeid'])
                or win.getProperty('YoPlayer.DetailSeasons.ShowID') != str(episode['tvshowid'])):
            return None
        context.update(kind='episode', ident=episode['episodeid'], show=episode['tvshowid'],
                       season=int(win.getProperty('YoPlayer.DetailSeasons.Current')))
    elif kind == 'movie':
        context.update(kind=kind, ident=int(ident))
    else:
        return None
    return context


def information(context):
    """Build a fresh typed native information item from the library readback."""
    fields = ['title', 'year', 'plot', 'genre', 'art', 'playcount', 'rating', 'votes',
              'userrating', 'cast', 'studio', 'mpaa', 'premiered', 'dateadded',
              'lastplayed', 'originaltitle', 'sorttitle', 'uniqueid', 'tag']
    if context['kind'] == 'episode':
        ident = context['show']
        row = rpc('VideoLibrary.GetTVShowDetails', {'tvshowid': ident,
                  'properties': fields + ['episode', 'watchedepisodes', 'season']})['tvshowdetails']
        kind, path = 'tvshow', 'videodb://tvshows/titles/{}/'.format(ident)
    else:
        kind, ident = 'movie', context['ident']
        row = rpc('VideoLibrary.GetMovieDetails', {'movieid': ident,
                  'properties': fields + ['file', 'plotoutline', 'tagline', 'runtime',
                      'director', 'writer', 'country', 'trailer', 'set', 'setid',
                      'resume', 'streamdetails', 'imdbnumber']})['moviedetails']
        path = 'videodb://movies/titles/{}/'.format(ident)
    item = xbmcgui.ListItem(label=row.get('title') or row.get('label') or '', path=path, offscreen=True)
    tag = item.getVideoInfoTag()
    tag.setDbId(ident)
    tag.setMediaType(kind)
    tag.setTitle(row.get('title') or row.get('label') or '')
    tag.setYear(row.get('year') or 0)
    tag.setPlot(row.get('plot') or '')
    tag.setGenres(row.get('genre') or [])
    tag.setPlaycount(row.get('playcount') or 0)
    # A videodb path alone does not guarantee a scraper-backed reload. Keep
    # the actual library metadata, version fields and resume in the info tag.
    info = {key: row[key] for key in ('originaltitle', 'sorttitle', 'plotoutline',
            'tagline', 'rating', 'votes', 'userrating', 'studio', 'mpaa', 'premiered',
            'dateadded', 'lastplayed', 'director', 'writer', 'country', 'trailer',
            'set', 'setid', 'status', 'tag') if key in row}
    info['castandrole'] = [(actor['name'], actor.get('role', '')) for actor in row.get('cast', [])]
    if 'runtime' in row:
        info['duration'] = row['runtime']
    if 'imdbnumber' in row:
        info['imdbnumber'] = row['imdbnumber']
    item.setInfo('video', info)
    if row.get('uniqueid'):
        tag.setUniqueIDs(row['uniqueid'])
    if row.get('file'):
        tag.setFilenameAndPath(row['file'])
    if row.get('resume'):
        tag.setResumePoint(row['resume'].get('position', 0), row['resume'].get('total', 0))
    for stream in row.get('streamdetails', {}).get('video', []):
        tag.addVideoStream(xbmc.VideoStreamDetail(width=stream.get('width', 0),
            height=stream.get('height', 0), aspect=stream.get('aspect', 0),
            duration=stream.get('duration', 0), codec=stream.get('codec', '')))
    for stream in row.get('streamdetails', {}).get('audio', []):
        tag.addAudioStream(xbmc.AudioStreamDetail(channels=stream.get('channels', 0),
            codec=stream.get('codec', ''), language=stream.get('language', '')))
    for stream in row.get('streamdetails', {}).get('subtitle', []):
        tag.addSubtitleStream(xbmc.SubtitleStreamDetail(language=stream.get('language', '')))
    if kind == 'tvshow':
        tag.setTvShowTitle(row.get('title') or '')
        item.setIsFolder(True)
        total, watched = row.get('episode', 0), row.get('watchedepisodes', 0)
        for key, value in [('totalepisodes', total), ('watchedepisodes', watched),
                           ('unwatchedepisodes', max(0, total - watched)),
                           ('totalseasons', row.get('season', 0))]:
            item.setProperty(key, str(value))
    item.setArt(row.get('art') or {})
    return item


class DetailReturn(xbmc.Monitor):
    def __init__(self, context):
        super().__init__()
        self.context = context
        self.token = uuid.uuid4().hex
        self.home = xbmcgui.Window(10000)
        self.bound = None
        self.stopped = None
        self.invalid = False
        self.fullscreen_seen = False
        self.bind_until = None
        self.browsing_since = None
        if context:
            self.home.setProperty(OWNER, self.token)
            self.log('captured')

    def log(self, outcome):
        # Fixed outcome codes and local library IDs only: no paths or URLs.
        context = self.context or {}
        xbmc.log('YoPlayer: detail return {} kind={} id={}'.format(
            outcome, context.get('kind', 'none'), context.get('ident', 0)), xbmc.LOGINFO)

    def cancel(self, reason):
        self.invalid = True
        self.log(reason)

    def bind(self):
        """Bind actual native video; allow its item metadata to become ready."""
        try:
            players = rpc('Player.GetActivePlayers')
            if not players:
                return
            # Kodi 21 includes required playertype (and may add more fields).
            # Compare the relevant fields, not the entire response dictionary.
            if (len(players) != 1 or players[0].get('playerid') != 1
                    or players[0].get('type') != 'video'
                    or players[0].get('playertype') != 'internal'):
                self.cancel('unsupported-player')
                return
            item = rpc('Player.GetItem', {'playerid': 1, 'properties': ['file']})['item']
            kind, ident = item.get('type'), item.get('id')
            if kind in (None, 'unknown') or not isinstance(ident, int) or not item.get('file'):
                return
            if kind != self.context['kind']:
                self.cancel('different-media')
                return
            if kind == 'episode':
                row = rpc('VideoLibrary.GetEpisodeDetails', {'episodeid': ident,
                          'properties': ['tvshowid', 'season']})['episodedetails']
                if row.get('tvshowid') != self.context['show']:
                    self.cancel('different-show')
                    return
                self.context['ident'] = ident
                if self.context['season'] != -1:
                    self.context['season'] = row['season']
            elif ident != self.context['ident']:
                self.cancel('different-movie')
                return
            self.bound = (kind, ident, hashlib.sha256(item['file'].encode('utf-8')).hexdigest())
            self.bind_until = None
            self.log('bound')
        except (RuntimeError, ValueError, TypeError, KeyError):
            # Native metadata may lag AVStart. Retry only within this start.
            return

    def owned(self):
        return (self.context and not self.invalid and not self.abortRequested()
                and xbmc.getSkinDir() == SKIN and self.home.getProperty(OWNER) == self.token)

    def onNotification(self, sender, method, data):
        if not self.owned():
            return
        if method == 'System.OnQuit':
            self.cancel('quit')
        elif method == 'Player.OnAVStart':
            self.stopped = None
            self.browsing_since = None
            self.bind_until = time.monotonic() + 3
            self.bind()
        elif method == 'Player.OnStop' and self.bound:
            try:
                item = json.loads(data).get('item', {})
                if any(item.get(k) not in (None, v) for k, v in zip(('type', 'id'), self.bound[:2])):
                    self.cancel('different-stop')
                    return
                self.stopped = time.monotonic()
                self.log('stopped')
            except (ValueError, TypeError, AttributeError):
                self.cancel('invalid-stop')

    def idle_here(self):
        return (self.owned() and not rpc('Player.GetActivePlayers')
                and not xbmc.getCondVisibility('Player.HasVideo')
                and xbmcgui.getCurrentWindowId() == self.context['base']
                and not xbmc.getCondVisibility('System.HasVisibleModalDialog')
                and not xbmc.getCondVisibility('Window.IsVisible(movieinformation)'))

    def follow(self):
        """Wait for the bound playback only; a replacement owner cancels us."""
        deadline = time.monotonic() + 40
        try:
            while self.owned():
                now = time.monotonic()
                if self.bind_until is not None and self.stopped is None:
                    self.bind()
                    if not self.owned():
                        return
                    if self.bind_until is not None and now >= self.bind_until:
                        self.cancel('metadata-timeout')
                        return
                if xbmc.getCondVisibility('Window.IsActive(fullscreenvideo)'):
                    self.fullscreen_seen = True
                    self.browsing_since = None
                elif (self.fullscreen_seen and self.stopped is None
                      and xbmc.getCondVisibility('Player.HasVideo')):
                    # Returning to browsing while video continues is the user's
                    # navigation. Allow the normal Stop notification to catch
                    # up with fullscreen teardown before classifying browsing.
                    if self.browsing_since is None:
                        self.browsing_since = now
                    if now - self.browsing_since >= .6 and rpc('Player.GetActivePlayers'):
                        self.log('background-browsing')
                        return
                else:
                    self.browsing_since = None
                if not self.bound and now > deadline:
                    self.log('start-timeout')
                    return
                if self.stopped is not None and now - self.stopped >= .4:
                    if not self.idle_here():
                        # OnStop can precede fullscreen/Player.HasVideo teardown.
                        # Retry only this native transition, never another page
                        # or an unrelated dialog, and only for three seconds.
                        if (now - self.stopped < 3 and not rpc('Player.GetActivePlayers')
                                and not xbmc.getCondVisibility('System.HasVisibleModalDialog')
                                and (xbmc.getCondVisibility('Window.IsActive(fullscreenvideo)')
                                     or (xbmcgui.getCurrentWindowId() == self.context['base']
                                         and xbmc.getCondVisibility('Player.HasVideo')))):
                            if self.waitForAbort(.1):
                                return
                            continue
                        self.log('stop-context-changed')
                        return
                    item = information(self.context)
                    if not self.idle_here():
                        self.log('return-context-changed')
                        return
                    if self.context['kind'] == 'episode':
                        key = 'YoPlayer.DetailSeasons.' + str(self.context['show'])
                        try:
                            cache = json.loads(self.home.getProperty(key) or '{}')
                        except ValueError:
                            cache = {}
                        selected = cache.get('selected', {})
                        selected[str(self.context['season'])] = self.context['ident']
                        self.home.setProperty(key, json.dumps({'season': self.context['season'], 'selected': selected}))
                    # Consume the owner before showing the modal. A new Play
                    # from the returned detail can then create its own owner.
                    self.home.clearProperty(OWNER)
                    self.log('opening-detail')
                    xbmcgui.Dialog().info(item)
                    return
                if self.waitForAbort(.1):
                    return
        except (RuntimeError, ValueError, TypeError, KeyError):
            xbmc.log('YoPlayer: detail return skipped; native context unavailable', xbmc.LOGWARNING)
        finally:
            self.close()

    def close(self):
        if self.home.getProperty(OWNER) == self.token:
            self.home.clearProperty(OWNER)


def movie(mode, expected):
    def same_detail():
        return (xbmc.getCondVisibility('Window.IsActive(movieinformation)')
                and xbmc.getInfoLabel('ListItem.DBType') + ':' + xbmc.getInfoLabel('ListItem.DBID') == expected)
    if not same_detail():
        return
    try:
        observer = DetailReturn(capture())
    except (RuntimeError, ValueError, TypeError, KeyError):
        observer = DetailReturn(None)
    try:
        if not same_detail():
            observer.close()
            return
        if mode == 'native':
            xbmc.executebuiltin('SendClick(12003,8)')
        elif mode == 'resume':
            # Identity-scoped compatibility resume retains a native-play option.
            from resumeplay import ISOResumeExtractor
            try:
                ISOResumeExtractor().run()
            except SystemExit:
                pass  # Existing helper exits after sending the native Play.
    finally:
        observer.follow()


if __name__ == '__main__' and xbmc.getSkinDir() == SKIN:
    if len(sys.argv) == 3 and sys.argv[1] in ('native', 'resume'):
        movie(sys.argv[1], sys.argv[2])
