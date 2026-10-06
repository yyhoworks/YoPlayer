"""Read-only synced library identity; never infer membership from media names."""
from contextlib import closing
from pathlib import Path
import re
import sqlite3
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET


def synced_members(database_directory, library, text):
    parsed = urlsplit(library['path'])
    node = ET.fromstring(text)
    kind = node.findtext('content')
    # Only the addon-authored whole-library node has this identity contract.
    pattern = r'/emby_' + str(kind) + r'_[^/]+/all\.xml/?'
    rules = node.findall('rule')
    if (parsed.scheme != 'library' or parsed.netloc != 'video' or
            not re.fullmatch(pattern, unquote(parsed.path)) or
            kind not in ('movies', 'tvshows') or node.get('type') != 'filter' or
            len(rules) != 1 or rules[0].get('field') != 'tag' or
            rules[0].get('operator') != 'is' or list(rules[0]) or
            rules[0].text != node.findtext('label')):
        return None
    directory = Path(database_directory)
    matches = []
    table, media_type = ('Movie', 'Movie') if kind == 'movies' else ('Series', 'Series')
    for path in sorted(directory.glob('emby_*.db')):
        try:
            with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=.5)) as db:
                db.execute('PRAGMA query_only=ON'); db.execute('BEGIN')
                ids = db.execute('SELECT DISTINCT EmbyLibraryId FROM LibrarySynced '
                                 'WHERE EmbyLibraryName=? AND EmbyType=?',
                                 (node.findtext('label'), media_type)).fetchall()
                for ident, in ids:
                    columns = 'v.KodiId,v.KodiFileId' if kind == 'movies' else 'v.KodiId,v.KodiPathId'
                    rows = db.execute('SELECT ' + columns + ' FROM EmbyLibraryMapping m JOIN ' + table +
                                      ' v ON v.EmbyId=m.EmbyId WHERE m.EmbyLibraryId=?', (ident,)).fetchall()
                    # Supplemental videos can share a movie library, too.
                    if kind == 'movies':
                        rows += db.execute('SELECT v.KodiId,v.KodiFileId FROM EmbyLibraryMapping m '
                                           'JOIN Video v ON v.EmbyId=m.EmbyId WHERE m.EmbyLibraryId=?', (ident,)).fetchall()
                    matches.append(rows)
        except (sqlite3.Error, OSError):
            # A second unreadable server could have the same name: do not guess.
            return None
    if len(matches) != 1:
        return None
    videos = sorted(directory.glob('MyVideos*.db'), key=lambda p: int(p.stem[8:]) if p.stem[8:].isdigit() else -1)
    if not videos:
        return None
    try:
        with closing(sqlite3.connect(videos[-1].resolve().as_uri() + '?mode=ro', uri=True, timeout=.5)) as db:
            db.execute('PRAGMA query_only=ON'); db.execute('BEGIN')
            if kind == 'movies':
                live = set(db.execute('SELECT idMovie,idFile FROM movie'))
            else:
                live = set(db.execute('SELECT idShow,idPath FROM tvshowlinkpath'))
            members = {ident for ident, binding in matches[0]
                       if type(ident) is int and (ident, binding) in live}
    except (sqlite3.Error, OSError):
        return None
    return kind, members
