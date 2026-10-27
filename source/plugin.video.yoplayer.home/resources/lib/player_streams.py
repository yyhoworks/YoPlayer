"""Live native-player data, with media-bound stream identities."""
import hashlib
import json
import time

PROPERTIES = ['subtitles', 'currentsubtitle', 'subtitleenabled', 'audiostreams', 'currentaudiostream']


SNAPSHOT_PROPERTY = 'YoPlayer.Infuse.PlayerStreams.Snapshot'
SNAPSHOT_TTL = 15


def _snapshot_window():
    # Fail soft outside Kodi (unit tests pass a fake rpc and no xbmcgui):
    # without a window there is simply no snapshot cache, never an error.
    try:
        import xbmcgui
        return xbmcgui.Window(10000)
    except Exception:
        return None


def snapshot(rpc, use_cache=True):
    """Current player, media identity and track state (D-03).

    Two changes, both fail-closed on a media switch:
    - The second Player.GetItem is dropped (4 RPC -> 3). It only guarded
      the GetItem -> GetProperties race; if the media switches inside
      that window, the state belongs to the new media while the identity
      is the old one, so any stream key built from the pair cannot match
      a later fresh snapshot and select_stream refuses with a
      'media changed' error instead of applying a wrong track. The list
      case is transient: a switch bumps StreamRevision (see below) and
      the panel reloads under the new revision.
    - A short snapshot cache in a window property (the skin scripts run
      as fresh processes, so module state cannot carry it). A cached
      state is reused only when the freshly read media identity matches,
      the StreamRevision matches, and it is younger than 15s. Revision is
      bumped by the skin refresh only when the rendered track content
      changes (media, track list, current track, subtitle switch).
    """
    players = rpc('Player.GetActivePlayers') or []
    player = next((row for row in players if row.get('type') == 'video'), None)
    if player is None:
        raise RuntimeError('当前没有正在播放的视频')
    playerid = player['playerid']
    item = rpc('Player.GetItem', {'playerid': playerid, 'properties': ['file']}).get('item') or {}
    media = {key: item.get(key) for key in ('id', 'type', 'file')}
    window = _snapshot_window()
    revision = window.getProperty('YoPlayer.Infuse.StreamRevision') if window is not None else ''
    if use_cache and window is not None:
        try:
            cached = json.loads(window.getProperty(SNAPSHOT_PROPERTY))
            if (time.time() - cached['at'] < SNAPSHOT_TTL and cached.get('playerid') == playerid
                    and cached.get('media') == media and cached.get('revision') == revision
                    and isinstance(cached.get('state'), dict)):
                return playerid, media, cached['state']
        except Exception:
            pass
    state = rpc('Player.GetProperties', {'playerid': playerid, 'properties': PROPERTIES})
    if window is not None:
        try:
            window.setProperty(SNAPSHOT_PROPERTY, json.dumps(
                {'at': time.time(), 'playerid': playerid, 'media': media,
                 'revision': revision, 'state': state}, ensure_ascii=False))
        except Exception:
            pass
    return playerid, media, state


def stream_key(playerid, media, kind, track):
    identity = {key: track.get(key) for key in ('index', 'language', 'name', 'codec', 'channels')}
    data = json.dumps([playerid, media, kind, identity], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def language(value):
    return {'chi': '中文', 'zho': '中文', 'eng': 'English', 'jpn': '日本語', 'kor': '한국어'}.get(
        value, value if value and value != 'und' else '未标注语言')


def flag(value):
    return 'true' if value is True or value == 1 or value == 'true' else ''


def stream_entries(rpc, kind):
    if kind not in ('audio', 'subtitle'):
        raise ValueError('不支持的轨道类型')
    playerid, media, state = snapshot(rpc)
    current = state.get('currentaudiostream' if kind == 'audio' else 'currentsubtitle') or {}
    tracks = state.get('audiostreams' if kind == 'audio' else 'subtitles') or []
    entries = []
    for track in tracks:
        index = track.get('index')
        if not isinstance(index, int) or isinstance(index, bool) or index < 0:
            raise RuntimeError('播放器没有提供有效轨道编号')
        title = track.get('name') or language(track.get('language'))
        properties = {key: str(track.get(key) or '') for key in ('language', 'codec', 'channels')}
        # Kodi supplies bits/s; the skin's metadata label appends kbps.
        bitrate = track.get('bitrate')
        properties['bitrate'] = format(bitrate / 1000, 'g') if isinstance(bitrate, (int, float)) and not isinstance(bitrate, bool) and bitrate > 0 else ''
        for key in ('isdefault', 'isforced', 'isoriginal'):
            properties[key] = flag(track.get(key, track.get(key[2:])))
        properties.update(index=str(index), iscurrent='true' if index == current.get('index') else '',
                          **{'YoPlayer.StreamKey': stream_key(playerid, media, kind, track)})
        entries.append({'title': title, 'detail': '', 'properties': properties})
    return entries


def select_stream(rpc, kind, index, expected_key):
    if kind not in ('audio', 'subtitle'):
        raise ValueError('不支持的轨道类型')
    index = int(index)
    playerid, media, state = snapshot(rpc, use_cache=False)
    tracks = state.get('audiostreams' if kind == 'audio' else 'subtitles') or []
    track = next((row for row in tracks if row.get('index') == index), None)
    if track is None or stream_key(playerid, media, kind, track) != expected_key:
        raise RuntimeError('媒体或轨道已变化，请重新选择')
    if kind == 'audio':
        rpc('Player.SetAudioStream', {'playerid': playerid, 'stream': index})
    else:
        current = (state.get('currentsubtitle') or {}).get('index')
        if current == index and state.get('subtitleenabled'):
            rpc('Player.SetSubtitle', {'playerid': playerid, 'subtitle': 'off'})
        else:
            rpc('Player.SetSubtitle', {'playerid': playerid, 'subtitle': index, 'enable': True})
    window = _snapshot_window()
    if window is not None:
        try:
            window.clearProperty(SNAPSHOT_PROPERTY)
        except Exception:
            pass
