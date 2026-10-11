"""Explicit, profile-local episode track memory. Never touches legacy episodesub.xml."""
import json
import os
import re
import tempfile
import time

import xbmc
import xbmcaddon
import xbmcvfs


def rpc(method, params=None):
    response = json.loads(xbmc.executeJSONRPC(json.dumps(dict(
        jsonrpc='2.0', id=1, method=method, params=params or {}))))
    if 'error' in response:
        raise RuntimeError('播放资料暂不可用，请稍后重试')
    return response.get('result')


def live():
    players = rpc('Player.GetActivePlayers') or []
    player = next((p for p in players if p.get('type') == 'video'), None)
    if not player:
        raise RuntimeError('当前没有正在播放的视频')
    ident = player['playerid']
    item = rpc('Player.GetItem', {'playerid': ident,
               'properties': ['tvshowid', 'season', 'file', 'title']}).get('item', {})
    show, season = item.get('tvshowid'), item.get('season')
    if item.get('type') == 'episode' and isinstance(show, int) and isinstance(season, int) and show >= 0 and season >= 0:
        key = 'show:{}:season:{}'.format(show, season)
        scope = '本剧第 {} 季'.format(season) if season else '本剧特别篇'
    else:
        if item.get('type') in ('movie', 'musicvideo'):
            raise RuntimeError('仅可记住剧集轨道')
        title = item.get('title') or xbmc.getInfoLabel('Player.Title')
        folder = xbmc.getInfoLabel('Player.Folderpath')
        if not folder or not re.search(r'S\d+E\d+', title, re.I):
            raise RuntimeError('仅可记住剧集轨道；当前媒体无法识别季或剧集目录')
        key, scope = 'folder:' + folder, '同一剧集目录'
    token = (ident, item.get('type'), item.get('id'), item.get('file'), show, season)
    return ident, key, scope, token


def context():
    return live()[:3]


def path():
    return os.path.join(xbmcvfs.translatePath(
        xbmcaddon.Addon('plugin.video.yoplayer.home').getAddonInfo('profile')), 'stream-memory.json')


def load():
    try:
        with open(path(), encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        return {'version': 1, 'selections': {}}
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('selections'), dict):
        raise ValueError('轨道偏好格式无效，未覆盖原文件')
    return data


def identity(track):
    # An index alone can refer to a different language in the next episode.
    return {key: track.get(key, '') for key in ('language', 'name', 'codec', 'channels')}


def save(kind):
    if kind not in {'audio', 'subtitle'}:
        raise ValueError('不支持的轨道类型')
    player, key, scope, token = live()  # Validate before creating any directory/file.
    state = rpc('Player.GetProperties', {'playerid': player, 'properties': [
        'audiostreams', 'currentaudiostream', 'subtitles', 'currentsubtitle', 'subtitleenabled']})
    enabled = kind != 'subtitle' or bool(state.get('subtitleenabled'))
    current = state.get('currentsubtitle' if kind == 'subtitle' else 'currentaudiostream') or {}
    tracks = state.get('subtitles' if kind == 'subtitle' else 'audiostreams') or []
    index = current.get('index')
    track = next((t for t in tracks if t.get('index') == index), None)
    if enabled and track is None:
        raise RuntimeError('当前轨道已变化，请重新选择后再记住')
    selection = {'enabled': enabled, 'index': index,
                 'identity': identity(track) if track else None}
    if live()[3] != token:
        raise RuntimeError('播放内容已变化，请在当前剧集重新选择')
    destination = path()
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    from infuse_filelock import exclusive
    temporary = None
    try:
        with exclusive(destination):
            data = load()
            data['selections'].setdefault(key, {})[kind] = selection
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False,
                                             dir=os.path.dirname(destination), suffix='.tmp') as f:
                temporary = f.name
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, destination)
            temporary = None
    finally:
        if temporary and os.path.exists(temporary):
            os.remove(temporary)
    return scope  # Only returned after the atomic write succeeds.


def apply(only=None, expected=None, completed=None):
    """Read only preference storage; apply only an identifiable live track."""
    try:
        player, key, _, token = live()
        if expected is not None and token != expected:
            return True
        saved = load()['selections'].get(key, {})
        if not saved:
            return True
        state = rpc('Player.GetProperties', {'playerid': player,
                    'properties': ['audiostreams', 'subtitles']})
        ready=True
        for kind, selection in saved.items():
            if completed is not None and kind in completed:continue
            if only and kind != only:
                continue
            if kind not in {'audio', 'subtitle'}:
                continue
            if live()[3] != token:
                return True
            if kind == 'subtitle' and not selection.get('enabled'):
                rpc('Player.SetSubtitle', {'playerid': player, 'subtitle': 'off'})
                if completed is not None:completed.add(kind)
                continue
            tracks = state.get('subtitles' if kind == 'subtitle' else 'audiostreams') or []
            if not tracks:
                ready=False
                continue  # AVStart may precede track enumeration; bounded retry.
            matches = [t for t in tracks if identity(t) == selection.get('identity')]
            # A stored index cannot disambiguate identical tracks across episodes.
            track = matches[0] if len(matches) == 1 else None
            if track is not None:
                params = {'playerid': player, 'subtitle' if kind == 'subtitle' else 'stream': track['index']}
                if kind == 'subtitle':
                    params['enable'] = True
                rpc('Player.SetSubtitle' if kind == 'subtitle' else 'Player.SetAudioStream', params)
            if completed is not None:completed.add(kind)
        return ready
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        xbmc.log('Infuse stream memory: {}'.format(exc), xbmc.LOGWARNING)
        return True


class PlaybackMemory:
    """Apply once for each AVStart, never on opening/closing an OSD panel."""
    def __init__(self):
        self.cancel()

    def cancel(self):
        self.pending = None
        self.token = None
        self.deadline = 0
        self.completed = set()

    def started(self, data):
        self.cancel()
        try:
            notice = json.loads(data)
            self.pending = notice.get('item', {})
            self.deadline = time.monotonic() + 3
        except (ValueError, TypeError, AttributeError):
            pass

    def poll(self):
        if self.pending is None:
            return
        if time.monotonic() > self.deadline:
            self.cancel()
            return
        try:
            token = live()[3]
            if self.token is None:
                # Reject delayed notifications that name a previous episode.
                if any(self.pending.get(k) is not None and self.pending[k] != v
                       for k, v in (('type', token[1]), ('id', token[2]))):
                    self.cancel()
                    return
                self.token = token
            if token != self.token or apply(expected=self.token, completed=self.completed):
                self.cancel()
        except (OSError, ValueError, TypeError, KeyError, RuntimeError):
            self.cancel()
