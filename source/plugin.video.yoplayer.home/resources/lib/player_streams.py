"""Live native-player data, with media-bound stream identities."""
import hashlib
import json
import time
import re
from collections import Counter

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


LANGUAGES = {
    'chi': '中文', 'zho': '中文', 'chs': '简体中文', 'cht': '繁体中文', 'zh': '中文', 'cmn': '普通话', 'yue': '粤语',
    'eng': '英语', 'en': '英语', 'jpn': '日语', 'ja': '日语', 'kor': '韩语', 'ko': '韩语', 'fre': '法语', 'fra': '法语',
    'ger': '德语', 'deu': '德语', 'spa': '西班牙语', 'ita': '意大利语', 'rus': '俄语', 'tha': '泰语', 'por': '葡萄牙语',
}
EXTERNAL_MARKERS = ('（外挂）', '(外挂)', '(External)', '（External）')


def language(value):
    value = str(value or '').strip()
    if not value or value.lower() == 'und':
        return ''
    return LANGUAGES.get(value.lower(), value)


CODEC_NAMES = {
    'truehd': 'TrueHD', 'mlp': 'MLP', 'dca': 'DTS', 'dts': 'DTS', 'dtshd_ma': 'DTS-HD MA',
    'dtshd_hra': 'DTS-HD HRA', 'dts-hd': 'DTS-HD', 'eac3': 'E-AC3', 'ac3': 'AC3', 'aac': 'AAC',
    'aac_latm': 'AAC', 'aac_lc': 'AAC', 'aac_ltp': 'AAC', 'aac_ssr': 'AAC', 'he_aac': 'AAC',
    'he_aac_v2': 'AAC', 'aac_he': 'AAC', 'aac_he_v2': 'AAC', 'aac_xhe': 'AAC',
    'flac': 'FLAC', 'alac': 'ALAC', 'opus': 'Opus', 'vorbis': 'Vorbis',
    'mp3': 'MP3', 'mp2': 'MP2', 'subrip': 'SRT', 'srt': 'SRT', 'ass': 'ASS', 'ssa': 'SSA',
    'hdmv_pgs_subtitle': 'PGS', 'pgssub': 'PGS', 'pgs': 'PGS', 'dvd_subtitle': 'VobSub',
    'dvdsub': 'VobSub', 'dvb_subtitle': 'DVB', 'mov_text': 'Text', 'webvtt': 'WebVTT',
}


def codec_name(value):
    value = str(value or '').strip()
    if not value:
        return ''
    key = value.lower()
    if key.startswith('pcm'):
        return 'PCM'
    return CODEC_NAMES.get(key, value.upper() if len(value) <= 5 else value)


def channel_count(value):
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        return ''
    # Kodi provides a count, not speaker positions or an LFE flag.
    return '{} 声道'.format(value)


def bitrate_text(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        return ''
    if value >= 1000000:
        return '{:.1f} Mbps'.format(value / 1000000.0)
    return '{:d} kbps'.format(int(round(value / 1000.0)))


def audio_title_part(name):
    """Preserve raw container titles (CE) and strip appended codec text (Kodi)."""
    name = str(name or '').strip()
    return name.rsplit(' - ', 1)[0].strip() if ' - ' in name else name


def external_subtitle(track):
    name = str(track.get('name') or '')
    return any(marker in name for marker in EXTERNAL_MARKERS)


def subtitle_title_part(track):
    name = str(track.get('name') or '')
    for marker in EXTERNAL_MARKERS:
        name = name.replace(marker, '')
    return name.strip(' -·')


def audio_codec_text(track):
    codec = codec_name(track.get('codec'))
    if 'atmos' in str(track.get('name') or '').lower():
        codec = (codec + ' Atmos').strip()
    return codec


def summary(track, kind):
    """Display-only second line; never infer a speaker layout from a count."""
    if kind == 'subtitle':
        return '外挂' if external_subtitle(track) else '内嵌'
    head = ' '.join(part for part in (audio_codec_text(track), channel_count(track.get('channels'))) if part)
    return ' · '.join(part for part in (head, bitrate_text(track.get('bitrate'))) if part)


def row_text(tracks, kind):
    """Titles, second lines and tags as the plan A panel shows them.

    Audio: the language, plus the codec when several tracks share it
    ('中文 · TrueHD'); a track with its own container title (commentary)
    keeps that title and moves the language into the second line.
    Subtitles: the container title, else the language; second line says
    embedded or external.
    """
    langs = [language(track.get('language')) for track in tracks]
    counts = {}
    for lang in langs:
        counts[lang] = counts.get(lang, 0) + 1
    rows = []
    for track, lang in zip(tracks, langs):
        default = flag(track.get('isdefault', track.get('default'))) == 'true'
        if kind == 'audio':
            own = audio_title_part(track.get('name'))
            if own == lang:
                own = ''
            line = summary(track, kind)
            if own:
                title = own
                line = ' · '.join(part for part in (lang, line) if part)
            else:
                title = lang or '未标注语言'
                if counts[lang] > 1 or not lang:
                    extra = audio_codec_text(track) or channel_count(track.get('channels'))
                    title = '{} · {}'.format(title, extra) if extra else title
            if default:
                line = ' · '.join(part for part in (line, '默认') if part)
            low = (own + ' ' + str(track.get('name') or '')).lower()
            if '评论' in own or 'comment' in low:
                tag = '评论'
            elif 'atmos' in low:
                tag = 'Atmos'
            elif default:
                tag = '默认'
            else:
                tag = ''
        else:
            external = external_subtitle(track)
            title = subtitle_title_part(track) or lang or ('外挂字幕' if external else '未标注语言')
            line = summary(track, kind)
            extras = []
            if default:
                extras.append('默认')
            if flag(track.get('isforced', track.get('forced'))) == 'true':
                extras.append('强制')
            line = ' · '.join([line] + extras)
            tag = '外挂' if external else ('默认' if default else ('强制' if '强制' in extras else ''))
        rows.append((title, line, tag))
    return rows


def distinguish_rows(rows, tracks, kind):
    """Keep native indexes intact and make compact-mode titles distinguishable."""
    titles = [row[0] for row in rows]
    counts = Counter(titles)
    if kind == 'audio':
        for pos, (title, track) in enumerate(zip(titles, tracks)):
            if counts[title] > 1:
                codec = audio_codec_text(track)
                extra = ' '.join(part for part in (
                    codec if codec not in title else '', channel_count(track.get('channels'))) if part)
                if extra:
                    titles[pos] = '{} · {}'.format(title, extra)
    counts = Counter(titles)
    used = {title for title in titles if counts[title] == 1}
    for pos, (title, track) in enumerate(zip(titles, tracks)):
        if counts[title] > 1:
            base = '{} · 轨道 {}'.format(title, track['index'] + 1)
            candidate, suffix = base, 2
            while candidate in used:
                candidate = '{} ({})'.format(base, suffix)
                suffix += 1
            titles[pos] = candidate
            used.add(candidate)
    return [(title, row[1], row[2]) for title, row in zip(titles, rows)]


def flag(value):
    return 'true' if value is True or value == 1 or value == 'true' else ''


BRACKETS = re.compile(r'[\[【{（(][^\]】}）)]*[\]】}）)]')
SECOND = {'英': '英', 'eng': '英', 'en': '英', '日': '日', 'jpn': '日', 'jp': '日', '韩': '韩', '韓': '韩', 'kor': '韩'}
BILINGUAL = re.compile(r'(简|繁|chs|cht|sc|tc|中)[体體中文]*\s*[&/+／和_.-]?\s*(英|日|韩|韓|eng|jpn|jp|kor|en)(?![a-z])', re.I)
SUB_RULES = [
    (r'简[体體中]|简$|\bchs\b|\bzh[-_]?(?:hans|cn|sg)\b|\bsc\b|simplified', '简体'),
    (r'繁[體体中]|\bcht\b|\bzh[-_]?(?:hant|tw|hk)\b|\btc\b|traditional', '繁体'),
]
SUB_FLAGS = [(r'特效', '特效'), (r'\bsdh\b|听障|聽障|hearing', 'SDH'),
             (r'导评|導評', '导评'), (r'歌词|lyrics|signs', '歌词')]  # 默认/强制/评论 stay in tags
AUDIO_RULES = [(r'国语|國語|普通话|mandarin', '国语'), (r'粤语|粵語|cantonese', '粤语'),
               (r'台配|台湾|台灣', '台配'), (r'上译|上譯', '上译'), (r'长影|長影', '长影'), (r'八一', '八一'),
               (r'原声|原聲|original', '原声'), (r'导评|導評', '导评'),
               (r'国配|國配|中配', '国配')]


MANDARIN = {'中文', '普通话'}
COVERS = {'国语': MANDARIN, '台配': MANDARIN, '上译': MANDARIN, '长影': MANDARIN, '八一': MANDARIN,
          '国配': MANDARIN, '粤语': {'中文', '粤语'}, '简体': {'中文', '简体中文'}, '繁体': {'中文', '繁体中文'}}
for _head, _covers in (('简', {'中文', '简体中文'}), ('繁', {'中文', '繁体中文'}), ('中', {'中文'})):
    for _second in set(SECOND.values()):
        COVERS[_head + _second + '双语'] = _covers


def _hits(text, rules, limit):
    out = []
    for pattern, label in rules:
        if label not in out and re.search(pattern, text, re.I):
            out.append(label)
            if len(out) >= limit:
                break
    return out


def short_label(raw, lang, kind):
    """'中文 · 简英双语 · 特效' style title; falls back to language or a trimmed name."""
    raw = str(raw or '')
    if kind == 'subtitle':
        m = BILINGUAL.search(raw)
        if m:
            head = m.group(1).lower()
            head = '繁' if head in ('繁', 'cht', 'tc') else ('中' if head == '中' else '简')
            script = [head + SECOND[m.group(2).lower()] + '双语']
        else:
            script = _hits(raw, SUB_RULES, 1)
        flags = _hits(raw, SUB_FLAGS, 2)
        parts = script + flags
    else:
        parts = _hits(raw, AUDIO_RULES, 2)
    if parts:
        # Drop the language only when a distilled part already says it (国语 for
        # 中文/普通话, 简体 for 简体中文…); 原声/SDH/导评 keep the known language.
        covered = set().union(*(COVERS.get(part, set()) for part in parts))
        head = [] if not lang or lang in covered else [lang]
        return ' · '.join(head + parts)
    if lang:
        return lang
    plain = BRACKETS.sub('', raw).strip(' -_.·')
    plain = re.sub(r'\s+', ' ', plain)
    # A long release string carries no reader value here; the full name box shows it.
    return plain if 0 < len(plain) <= 16 else '未标注语言'


# Kodi appends ' - <codec> <layout>' (' - DTS 5.1(side)') to audio names. Strip it only
# when the codec word matches the track's own codec and the layout matches its channel
# count; anything else ('English - Audio Description 2.0') is part of the real name.
KODI_SUFFIX = re.compile(r'^(?P<name>.*) - (?P<codec>[A-Za-z0-9+-]+) (?:(?P<a>\d)\.(?P<b>\d)(?:\([a-z]+\))?|(?P<word>mono|stereo))$')
KODI_CODEC_WORDS = {
    'truehd': {'truehd'}, 'mlp': {'mlp'}, 'dca': {'dts', 'dts-hd', 'dtshd'}, 'dts': {'dts', 'dts-hd', 'dtshd'},
    'ac3': {'ac3', 'dd'}, 'eac3': {'eac3', 'e-ac3', 'dd+'}, 'aac': {'aac'}, 'flac': {'flac'},
    'opus': {'opus'}, 'vorbis': {'vorbis'}, 'mp3': {'mp3'}, 'mp2': {'mp2'}, 'alac': {'alac'}}


def kodi_audio_name(track):
    raw = str(track.get('name') or '')
    match = KODI_SUFFIX.match(raw)
    if not match:
        return raw
    codec = str(track.get('codec') or '').lower()
    words = KODI_CODEC_WORDS.get(codec, {'pcm', 'lpcm'} if codec.startswith('pcm') else set())
    channels = track.get('channels')
    count = {'mono': 1, 'stereo': 2}.get(match.group('word') or '') or (
        int(match.group('a')) + int(match.group('b')) if match.group('a') else 0)
    if match.group('codec').lower() in words and isinstance(channels, int) and count == channels:
        return match.group('name').rstrip()
    return raw


OFF_INDEX = 'off'


def panel_rows(tracks, kind):
    """Readable skin-only fields; raw titles and native track identities stay intact."""
    rows = []
    for track in tracks:
        lang = language(track.get('language'))
        raw = str(track.get('name') or '')
        own = audio_title_part(raw) if kind == 'audio' else subtitle_title_part(track)
        # Distil 国语/粤语/简英双语/SDH… from long container titles; display only.
        title = short_label(own, lang, kind)
        tags = []
        if kind == 'audio' and ('comment' in raw.lower() or '评论' in raw):
            tags.append('评论')
        if flag(track.get('isdefault', track.get('default'))) == 'true':
            tags.append('默认')
        if flag(track.get('isforced', track.get('forced'))) == 'true':
            tags.append('强制')
        if kind == 'audio':
            line = ' · '.join(part for part in (audio_codec_text(track),
                              channel_count(track.get('channels')), bitrate_text(track.get('bitrate'))) if part)
        else:
            line = summary(track, kind)
        rows.append({'display_title': title, 'display_summary': line,
                     'display_tags': ' · '.join(tags),
                     'original_name': (kodi_audio_name(track) if kind == 'audio' else raw) or own or lang or '未标注名称'})
    return rows


def number_duplicate_titles(properties_list):
    """Number equal short titles in final display order (call after any sorting)."""
    titles = [props['display_title'] for props in properties_list]
    duplicates = Counter(titles)
    seen = Counter()
    for props, title in zip(properties_list, titles):
        if duplicates[title] > 1:
            seen[title] += 1
            props['display_title'] = '{} {}'.format(title, seen[title])
    return properties_list


def stream_entries(rpc, kind):
    if kind not in ('audio', 'subtitle'):
        raise ValueError('不支持的轨道类型')
    playerid, media, state = snapshot(rpc)
    current = state.get('currentaudiostream' if kind == 'audio' else 'currentsubtitle') or {}
    tracks = state.get('audiostreams' if kind == 'audio' else 'subtitles') or []
    enabled = kind == 'audio' or bool(state.get('subtitleenabled'))
    for track in tracks:
        index = track.get('index')
        if not isinstance(index, int) or isinstance(index, bool) or index < 0:
            raise RuntimeError('播放器没有提供有效轨道编号')
    entries = []
    for track, (title, line, tag), display in zip(
            tracks, distinguish_rows(row_text(tracks, kind), tracks, kind), panel_rows(tracks, kind)):
        index = track.get('index')
        if not isinstance(index, int) or isinstance(index, bool) or index < 0:
            raise RuntimeError('播放器没有提供有效轨道编号')
        properties = {key: str(track.get(key) or '') for key in ('language', 'codec', 'channels')}
        # Kodi supplies bits/s; the skin's metadata label appends kbps.
        bitrate = track.get('bitrate')
        properties['bitrate'] = format(bitrate / 1000, 'g') if isinstance(bitrate, (int, float)) and not isinstance(bitrate, bool) and bitrate > 0 else ''
        properties['summary'] = line
        properties['tag'] = tag
        properties.update(display)
        for key in ('isdefault', 'isforced', 'isoriginal'):
            properties[key] = flag(track.get(key, track.get(key[2:])))
        properties.update(index=str(index), iscurrent='true' if enabled and index == current.get('index') else '',
                          **{'YoPlayer.StreamKey': stream_key(playerid, media, kind, track)})
        entries.append({'title': title, 'detail': '', 'properties': properties})
    if kind == 'subtitle' and entries:
        # External files last, as the mockup reads; Kodi indexes are unchanged.
        entries.sort(key=lambda entry: entry['properties']['tag'] == '外挂')
    number_duplicate_titles([entry['properties'] for entry in entries])
    if kind == 'subtitle' and entries:
        entries.insert(0, {'title': '关闭', 'detail': '', 'properties': {
            'summary': '', 'tag': '', 'index': OFF_INDEX, 'iscurrent': '' if enabled else 'true',
            'display_title': '关闭', 'display_summary': '', 'display_tags': '', 'original_name': '关闭字幕',
            'YoPlayer.StreamKey': stream_key(playerid, media, kind, {'index': OFF_INDEX})}})
    return entries


def select_stream(rpc, kind, index, expected_key):
    if kind not in ('audio', 'subtitle'):
        raise ValueError('不支持的轨道类型')
    if kind == 'subtitle' and str(index) == OFF_INDEX:
        playerid, media, state = snapshot(rpc, use_cache=False)
        if stream_key(playerid, media, kind, {'index': OFF_INDEX}) != expected_key:
            raise RuntimeError('媒体或轨道已变化，请重新选择')
        rpc('Player.SetSubtitle', {'playerid': playerid, 'subtitle': 'off'})
        _clear_snapshot()
        return
    index = int(index)
    playerid, media, state = snapshot(rpc, use_cache=False)
    tracks = state.get('audiostreams' if kind == 'audio' else 'subtitles') or []
    track = next((row for row in tracks if row.get('index') == index), None)
    if track is None or stream_key(playerid, media, kind, track) != expected_key:
        raise RuntimeError('媒体或轨道已变化，请重新选择')
    if kind == 'audio':
        rpc('Player.SetAudioStream', {'playerid': playerid, 'stream': index})
    else:
        # The panel has an explicit 关闭 row, so picking a track always turns it on.
        rpc('Player.SetSubtitle', {'playerid': playerid, 'subtitle': index, 'enable': True})
    _clear_snapshot()


def _clear_snapshot():
    window = _snapshot_window()
    if window is not None:
        try:
            window.clearProperty(SNAPSHOT_PROPERTY)
        except Exception:
            pass
