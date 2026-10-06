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


def decorate(item, row, kind):
    import xbmcaddon
    import xbmcvfs
    try:
        version = xbmcaddon.Addon('plugin.service.emby-next-gen').getAddonInfo('version')
        score = rating(xbmcvfs.translatePath('special://database/'), version, kind,
                       row.get(kind+'id'), row.get('rating'))
    except (RuntimeError, OSError):
        score = ''
    item.setProperty('YoPlayer.Rating', score)
    item.setProperty('YoPlayer.RatingSource', 'emby' if score else '')
