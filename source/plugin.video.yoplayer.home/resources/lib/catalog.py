"""Media-library identity and branch-local preferences, independent of Kodi UI."""
import csv
import hashlib
import json
import os
import re
import uuid
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET


VIDEO_WINDOWS = {'10025', 'videos', 'video', 'videolibrary', 'myvideonav'}
VIDEO_SUFFIXES = {'.mkv', '.mp4', '.avi', '.mov', '.m4v', '.ts', '.m2ts', '.strm', '.iso', '.wmv'}


def parse_command(command):
    """Parse a favourite's builtin as data; never execute the command."""
    match = re.fullmatch(r'\s*ActivateWindow\s*\((.*)\)\s*', command or '', re.I | re.S)
    if not match:
        return None
    try:
        args = next(csv.reader([match.group(1)], skipinitialspace=True))
    except (csv.Error, StopIteration):
        return None
    if len(args) < 2 or args[0].strip().lower() not in VIDEO_WINDOWS:
        return None
    return args[1].strip()


def media_directory(path):
    if not isinstance(path, str) or not path.strip() or any(c in path for c in '\r\n\x00'):
        return False
    path = path.strip()
    parsed = urlsplit(path)
    scheme = parsed.scheme.lower()
    suffix = os.path.splitext(unquote(parsed.path).rstrip('/\\'))[1].lower()
    if suffix in VIDEO_SUFFIXES:
        return False
    if scheme in {'library', 'videodb'}:
        return path.lower() not in {'videodb://', 'library://', 'library://video/'}
    if scheme == 'plugin':
        return (parsed.netloc.startswith('plugin.video.') and parsed.netloc != 'plugin.video.yoplayer.home') or parsed.netloc=='plugin.service.emby-next-gen'
    if suffix == '.xsp':
        return scheme in {'', 'special', 'smb', 'nfs', 'file'} or bool(re.match(r'^[A-Za-z]:[\\/]', path))
    if scheme in {'smb', 'nfs', 'special', 'file'}:
        return path.endswith(('/', '\\')) or not suffix
    return (not scheme or bool(re.match(r'^[A-Za-z]:[\\/]', path))) and (path.endswith(('/', '\\')) or not suffix)


def identity(path):
    # A trailing slash does not change the identity of a Kodi library node.
    return hashlib.sha256(path.strip().rstrip('/\\').encode('utf-8')).hexdigest()[:20]


def favourites_from_xml(text):
    result = []
    for node in ET.fromstring(text).findall('favourite'):
        path = parse_command(node.text)
        if path:
            result.append({'title': node.get('name', ''), 'type': 'window', 'window': 10025,
                           'windowparameter': path, 'thumbnail': node.get('thumb', '')})
    return result


def emby_libraries(node_directory):
    """Read Emby-generated node definitions without guessing library membership.

    Synced all.xml nodes preserve the addon-authored filter exactly. Dynamic
    browse nodes are a fallback only for a library lacking a synced node.
    """
    result=[];synced_names=set()
    try:folders=sorted(os.listdir(node_directory))
    except OSError:return result
    for dynamic in (False,True):
        for folder in folders:
            match=re.fullmatch(r'emby_'+('dynamic_' if dynamic else '')+r'(movies|tvshows|musicvideos)_(.+)',folder)
            if not match:continue
            kind,name=match.groups()
            if dynamic and (kind,name) in synced_names:continue
            base=os.path.join(node_directory,folder)
            filename={'movies':'movie_movie.xml','tvshows':'series_series.xml','musicvideos':'musicvideo_musicvideo.xml'}[kind] if dynamic else 'all.xml'
            try:
                node=ET.parse(os.path.join(base,filename)).getroot()
                index=ET.parse(os.path.join(base,'index.xml')).getroot()
            except (OSError,ET.ParseError):continue
            if not dynamic:
                if node.get('type')!='filter' or node.findtext('content')!=kind:continue
                path='library://video/'+folder+'/all.xml/'
                synced_names.add((kind,name))
            else:
                path=node.findtext('path') or ''
                if node.get('type')!='folder' or not media_directory(path):continue
            result.append(dict(type='local',path=path,title=node.findtext('label') if not dynamic else name,
                               thumbnail=index.findtext('icon') or '',source='emby',kind=kind))
    return result


def library_visible(key, source, preferences):
    selected = preferences.get('selected')
    return not (preferences.get('items', {}).get(key, {}).get('hidden')
                or (selected is not None and key not in selected)
                or (selected is None and source == 'emby'))


def libraries(favourites, preferences=None, discovered=None, include_hidden=False):
    prefs = preferences or {}
    overrides = prefs.get('items', {})
    candidates = list(favourites or []) + [dict(item, type='local') for item in prefs.get('custom', [])] + list(discovered or [])
    selected=prefs.get('selected')
    result, seen = [], set()
    for entry in candidates:
        kind = entry.get('type', '')
        if kind not in {'window', 'local'}:
            continue
        if kind == 'window' and str(entry.get('window', '')).lower() not in VIDEO_WINDOWS:
            continue
        path = entry.get('windowparameter', '') if kind == 'window' else entry.get('path', '')
        if not media_directory(path):
            continue
        key = identity(path)
        if key in seen:
            continue
        seen.add(key)
        override = overrides.get(key, {})
        if not include_hidden and not library_visible(key, entry.get('source'), prefs):
            continue
        result.append({'id': key, 'path': path, 'name': override.get('name') or entry.get('title') or '未命名分库',
                       'thumb': override.get('thumb') or entry.get('thumbnail', ''), 'source': entry.get('source') or kind})
    order = {key: i for i, key in enumerate(prefs.get('order', []))}
    result.sort(key=lambda item: order.get(item['id'], len(order)))
    return result


def merge_recent(movies, episodes, limit=25, inprogress=False):
    result = []
    for kind, rows in [('movie', movies), ('episode', episodes)]:
        for row in rows:
            position = (row.get('resume') or {}).get('position', 0) or 0
            if inprogress and position <= 0:
                continue
            if not inprogress and not row.get('lastplayed'):
                continue
            result.append(dict(row, kind=kind))
    result.sort(key=lambda item: (item.get('lastplayed', ''), item.get('dateadded', '')), reverse=True)
    return result[:limit]


def validate_preferences(data):
    if not isinstance(data, dict):
        raise ValueError('Expected preferences object')
    for key, expected in [('items', dict), ('custom', list), ('order', list), ('selected',list), ('genres', dict)]:
        if key in data and not isinstance(data[key], expected):
            raise ValueError('Invalid preferences field: ' + key)
    if 'revision' in data and (type(data['revision']) is not int or data['revision'] < 0):
        raise ValueError('Invalid preferences revision')
    if any(not isinstance(value, dict) for value in data.get('items', {}).values()):
        raise ValueError('Invalid library overrides')
    if any(not isinstance(value, dict) or not isinstance(value.get('path'), str) for value in data.get('custom', [])):
        raise ValueError('Invalid custom libraries')
    if any(not isinstance(value, str) for key in ('order', 'selected') for value in data.get(key, [])):
        raise ValueError('Invalid library identities')
    config = data.get('genres', {})
    if any(key in config and type(config[key]) is not bool for key in ('hidden', 'show_all')):
        raise ValueError('Invalid genre visibility')
    if 'selected' in config and (not isinstance(config['selected'], list) or any(
            not isinstance(row, dict) or type(row.get('id')) is not int or row['id'] < 0
            or not isinstance(row.get('name'), str) or not row['name'] for row in config['selected'])):
        raise ValueError('Invalid selected genres')
    return data


def load_preferences(path):
    try:
        with open(path, encoding='utf-8') as source:
            data = json.load(source)
        return validate_preferences(data)
    except FileNotFoundError:
        return {'items': {}, 'custom': [], 'order': []}


def save_preferences(path, data, expected=None):
    """Serialize writers and reject a stale draft before atomically replacing it."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lock = path + '.lock'
    # Keep the same lock inode: OS locks release after a crash, whereas an
    # exclusive-create sentinel would leave all future editors blocked.
    descriptor = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
    acquired = False
    temporary = path + '.' + uuid.uuid4().hex + '.tmp'
    try:
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as exc:
            raise FileExistsError('Preferences are being edited') from exc
        current = load_preferences(path)
        if expected is not None and current != expected:
            raise ValueError('Preferences changed; reopen the editor')
        data = dict(data, revision=int(current.get('revision', 0)) + 1)
        with open(temporary, 'w', encoding='utf-8') as destination:
            json.dump(data, destination, ensure_ascii=False, indent=2)
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)
        try:
            if acquired:
                if os.name == 'nt':
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)
