"""Live native-player data, with media-bound stream identities."""
import hashlib
import json

PROPERTIES = ['subtitles', 'currentsubtitle', 'subtitleenabled', 'audiostreams', 'currentaudiostream']


def snapshot(rpc):
    players = rpc('Player.GetActivePlayers') or []
    player = next((row for row in players if row.get('type') == 'video'), None)
    if player is None:
        raise RuntimeError('当前没有正在播放的视频')
    playerid = player['playerid']
    item = rpc('Player.GetItem', {'playerid': playerid, 'properties': ['file']}).get('item') or {}
    media = {key: item.get(key) for key in ('id', 'type', 'file')}
    state = rpc('Player.GetProperties', {'playerid': playerid, 'properties': PROPERTIES})
    latest = rpc('Player.GetItem', {'playerid': playerid, 'properties': ['file']}).get('item') or {}
    if media != {key: latest.get(key) for key in ('id', 'type', 'file')}:
        raise RuntimeError('正在切换媒体，请重新打开轨道列表')
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
    playerid, media, state = snapshot(rpc)
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
