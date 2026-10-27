"""Read-only rating provenance for the locally verified Emby sync contract.

Kodi's default rating is CommunityRating in Emby 11.1.27. The optional
rating_type alias 'imdb' is not provenance. Only an exact, unique mapping
of media kind and Kodi ID permits branding; unknown contracts fail closed.
"""
from contextlib import closing
import math
from pathlib import Path
import sqlite3

TABLES = {'movie': ('Movie', 'Video'), 'tvshow': ('Series',), 'episode': ('Episode',)}
VERIFIED_VERSIONS = {'11.1.27'}


def value(raw):
    if isinstance(raw, bool):
        return ''
    try:
        number = float(raw)
        return format(number, '.1f') if math.isfinite(number) and .05 <= number <= 10 else ''
    except (ValueError, TypeError, OverflowError):
        return ''


def mapped(database, kind, ident):
    if kind not in TABLES or type(ident) is not int or ident <= 0:
        return False
    matches = []
    try:
        native = sorted(Path(database).glob('MyVideos*.db'),
                        key=lambda p: int(p.stem[8:]))
        if not native:
            return False
        with closing(sqlite3.connect(native[-1].resolve().as_uri()+'?mode=ro', uri=True, timeout=.2)) as kodi:
            kodi.execute('PRAGMA query_only=ON')
            if kind == 'tvshow':
                identities = {r[0] for r in kodi.execute('SELECT idPath FROM tvshowlinkpath WHERE idShow=?', (ident,))}
            else:
                table, key = ('movie','idMovie') if kind == 'movie' else ('episode','idEpisode')
                rows = kodi.execute('SELECT idFile FROM '+table+' WHERE '+key+'=?', (ident,)).fetchall()
                if len(rows) != 1:
                    return False
                identities = {rows[0][0]}
        if not identities:
            return False
        for path in Path(database).glob('emby_*.db'):
            with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True, timeout=.2)) as db:
                db.execute('PRAGMA query_only=ON')
                for table in TABLES[kind]:
                    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
                        field = 'KodiPathId' if kind == 'tvshow' else 'KodiFileId'
                        for eid, native_id in db.execute('SELECT EmbyId,'+field+' FROM '+table+' WHERE KodiId=?', (ident,)):
                            if native_id not in identities:
                                return False
                            matches.append((path.name,str(eid)))
        return len(matches) == 1 and bool(matches[0][1]) and matches[0][1] != 'None'
    except (OSError, sqlite3.Error, ValueError):
        return False


def rating(database, version, kind, ident, raw):
    score = value(raw)
    return score if score and version in VERIFIED_VERSIONS and mapped(database, kind, ident) else ''


def batch_ratings(database, version, requests):
    """One list's read-only identities; no connections or cache escape this call.

    Requests are (kind, Kodi ID, raw score). A read snapshot per database keeps
    each identity/mapping scan consistent during sync. Branding still requires
    one exact mapping across all related tables and all servers.
    """
    result = [''] * len(requests)
    candidates = {}
    if version not in VERIFIED_VERSIONS:
        return result
    for kind, ident, raw in requests:
        if kind in TABLES and type(ident) is int and ident > 0 and value(raw):
            candidates.setdefault(kind, set()).add(ident)
    if not candidates:
        return result
    identities, matches, invalid = {}, {}, set()

    def chunks(ids):
        ordered = sorted(ids)
        for start in range(0, len(ordered), 400):
            yield ordered[start:start+400]

    try:
        native = sorted(Path(database).glob('MyVideos*.db'), key=lambda p: int(p.stem[8:]))
        if not native:
            return result
        with closing(sqlite3.connect(native[-1].resolve().as_uri()+'?mode=ro', uri=True, timeout=.2)) as kodi:
            kodi.execute('PRAGMA query_only=ON')
            kodi.execute('BEGIN')
            for kind, ids in candidates.items():
                table, key, field = ('tvshowlinkpath','idShow','idPath') if kind == 'tvshow' else (
                    ('movie','idMovie','idFile') if kind == 'movie' else ('episode','idEpisode','idFile'))
                native_rows = {ident: [] for ident in ids}
                try:
                    for group in chunks(ids):
                        query = 'SELECT '+key+','+field+' FROM '+table+' WHERE '+key+' IN ('+','.join('?' for _ in group)+')'
                        for ident, native_id in kodi.execute(query, group).fetchall():
                            native_rows[int(ident)].append(native_id)
                    for ident, rows in native_rows.items():
                        if rows and (kind == 'tvshow' or len(rows) == 1):
                            identities[(kind, ident)] = set(rows)
                except sqlite3.Error:
                    invalid.update((kind, ident) for ident in ids)
        for path in Path(database).glob('emby_*.db'):
            with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True, timeout=.2)) as db:
                db.execute('PRAGMA query_only=ON')
                db.execute('BEGIN')
                tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
                for kind, ids in candidates.items():
                    active = {ident for ident in ids if (kind, ident) in identities and (kind, ident) not in invalid}
                    try:
                        for table in TABLES[kind]:
                            if table not in tables:
                                continue
                            field = 'KodiPathId' if kind == 'tvshow' else 'KodiFileId'
                            for group in chunks(active):
                                query = 'SELECT KodiId,EmbyId,'+field+' FROM '+table+' WHERE KodiId IN ('+','.join('?' for _ in group)+')'
                                for ident, eid, native_id in db.execute(query, group).fetchall():
                                    identity = (kind, int(ident))
                                    if native_id not in identities[identity]:
                                        invalid.add(identity)
                                    matches.setdefault(identity, []).append((path.name, str(eid)))
                    except sqlite3.Error:
                        invalid.update((kind, ident) for ident in ids)
    except (OSError, sqlite3.Error, ValueError):
        return result
    for index, (kind, ident, raw) in enumerate(requests):
        if kind not in TABLES or type(ident) is not int or ident <= 0:
            continue
        identity = (kind, ident)
        found = matches.get(identity, [])
        if identity not in invalid and len(found) == 1 and found[0][1] not in ('', 'None'):
            result[index] = value(raw)
    return result


def list_ratings(rows):
    """Resolve a list's scores before any ListItem construction.

    C-07: batch results for a verified Emby version are cached for 15s
    in a window property keyed by version + the exact request list, so
    re-entering the same list does not re-open the databases. The
    no-Emby path is untouched: a failed version lookup still returns
    empty scores immediately with no cache read or write. An
    unverified version is likewise not cached (batch_ratings already
    returns empty without touching a database), so a later upgrade to
    a verified version is never masked by a cached empty result.
    Database changes within the 15s window are bounded by that window,
    matching the membership and home-row caches.
    """
    import hashlib
    import json
    import time
    import xbmcaddon
    import xbmcvfs
    try:
        version = xbmcaddon.Addon('plugin.service.emby-next-gen').getAddonInfo('version')
    except (RuntimeError, OSError):
        return [''] * len(rows)
    requests = [(kind, row.get(kind + 'id'), row.get('rating')) for row, kind in rows]
    if version not in VERIFIED_VERSIONS:
        return batch_ratings(xbmcvfs.translatePath('special://database/'), version, requests)
    window = None
    cache_key = None
    try:
        import xbmcgui
        fingerprint = hashlib.sha256(json.dumps([version, requests], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        cache_key = 'YoPlayer.Infuse.Cache.Ratings.' + fingerprint
        window = xbmcgui.Window(10000)
        cached = json.loads(window.getProperty(cache_key))
        if time.time() - cached['at'] < 15 and len(cached['scores']) == len(rows):
            return list(cached['scores'])
    except Exception:
        window = None
        cache_key = None
    scores = batch_ratings(xbmcvfs.translatePath('special://database/'), version, requests)
    if window is not None and cache_key is not None:
        try:
            window.setProperty(cache_key, json.dumps({'at': time.time(), 'scores': scores}, ensure_ascii=False))
        except Exception:
            pass
    return scores


def decorate(item, row, kind, score=None):
    import xbmcaddon
    import xbmcvfs
    if score is None:
        try:
            version = xbmcaddon.Addon('plugin.service.emby-next-gen').getAddonInfo('version')
            score = rating(xbmcvfs.translatePath('special://database/'), version, kind,
                           row.get(kind+'id'), row.get('rating'))
        except (RuntimeError, OSError):
            score = ''
    item.setProperty('YoPlayer.Rating', score)
    item.setProperty('YoPlayer.RatingSource', 'emby' if score else '')
