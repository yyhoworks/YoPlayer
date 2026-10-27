"""Sort complete native directories, retaining members, IDs and media paths."""
import math
from library_state import SORTS, TVSHOW_SORTS, normalize, filtered, summary
# B-04, trimmed only where provably unused: 'firstaired' (no browse,
# filter, sort or item consumer reads it), 'specialsortseason' and
# 'specialsortepisode' (same). 'cast' and 'streamdetails' stay, even
# though the wall itself does not show them: movie_item and
# detail_path do not read them, but the native detail dialog may
# render the ListItem tag they are attached to, and that cannot be
# ruled out from the plugin side alone (report存疑 S-04). Stripping
# them from the request would therefore risk an emptied detail
# page; see item() below for the same B-03 decision.
FIELDS = ['title', 'year', 'rating', 'votes', 'file', 'playcount', 'lastplayed', 'resume',
          'art', 'plot', 'plotoutline', 'genre', 'runtime', 'director', 'writer', 'studio',
          'mpaa', 'country', 'cast', 'imdbnumber', 'premiered', 'season', 'episode',
          'showtitle', 'tvshowid', 'streamdetails', 'dateadded', 'sorttitle',
          'watchedepisodes', 'tag', 'setid', 'uniqueid', 'originaltitle',
          'tagline', 'trailer', 'set']

def score(row):
    try:
        value = float(row.get('rating') or 0)
        return value if math.isfinite(value) and 0 < value <= 10 else None
    except (ValueError, TypeError):
        return None


def ordered(rows, method, order):
    if method != 'rating':
        return rows
    # Folders (e.g. parent/collection nodes) retain their original placement.
    # Real rated tvshow folders still participate through their known DB type.
    prefix = [r for r in rows if r.get('type') not in ('movie', 'tvshow', 'episode', 'musicvideo')]
    media = [r for r in rows if r.get('type') in ('movie', 'tvshow', 'episode', 'musicvideo')]
    rating = score
    rated = [r for r in media if rating(r) is not None]
    missing = [r for r in media if rating(r) is None]
    rated.sort(key=rating, reverse=order == 'descending')
    return prefix + rated + missing


def complete_directory(rpc, origin, method, order):
    if method not in {v for _, v in SORTS + TVSHOW_SORTS} | {'episode', 'rating'} or order not in ('ascending', 'descending'):
        raise ValueError('Unsupported sorting')
    if not origin or 'route=native-browse' in origin:
        raise ValueError('Invalid origin')
    # No UI-page limit: Files.GetDirectory sorts and returns the entire source.
    # Kodi's tvshow dateAdded is MAX(files.dateAdded) over that show's episodes,
    # as exposed by its native tvshowcounts/tvshow_view. Reuse that aggregate;
    # do not query every show's children or apply a latest-episodes page cap.
    native_method = 'dateadded' if method == 'last_episode_added' else method
    result = rpc('Files.GetDirectory', {'directory': origin, 'media': 'video',
                 'properties': FIELDS, 'sort': {'method': native_method, 'order': order}})
    rows = result.get('files') or []
    limits = result.get('limits', {})
    if limits.get('start', 0) != 0 or limits.get('end', len(rows)) != len(rows) or limits.get('total', len(rows)) != len(rows):
        raise RuntimeError('Incomplete native directory')
    return ordered(rows, method, order)


def item(row, factory, gui, rating_score=None):
    kind = row.get('type')
    data = dict(row)
    if kind in ('movie', 'episode', 'tvshow', 'musicvideo'):
        data[kind + 'id'] = row.get('id', -1)
        result = factory(data, kind, rating_score)
        tag = result.getVideoInfoTag()
        try:
            votes = max(0, int(str(row.get('votes') or 0).replace(',', '')))
        except (ValueError, TypeError):
            votes = 0
        tag.setRating(score(row) or 0, votes, 'default', True)
        tag.setGenres(row.get('genre') or [])
        tag.setDirectors(row.get('director') or [])
        tag.setWriters(row.get('writer') or [])
        tag.setStudios(row.get('studio') or [])
        tag.setCountries(row.get('country') or [])
        tag.setMpaa(row.get('mpaa') or '')
        tag.setDuration(int(row.get('runtime') or 0))
        tag.setIMDBNumber(row.get('imdbnumber') or '')
        tag.setDateAdded(row.get('dateadded') or '')
        tag.setUniqueIDs(row.get('uniqueid') or {})
        # Keep native detail metadata while using the established factory for
        # identity, real playback paths, history, resume and guarded menus.
        result.setInfo('video', {key: row[key] for key in
            ('plotoutline', 'sorttitle', 'originaltitle', 'tagline', 'trailer',
             'premiered', 'set', 'setid', 'tag') if key in row})
        # B-03, deliberately not stripped: cast/streamdetails are the only
        # detail-only fields here, but the native detail dialog may render
        # this ListItem's tag, and neither movie_item nor detail_path can
        # prove it re-reads them from the database. Removing them would
        # risk an emptied detail page, so they stay on the item (see the
        # FIELDS note above). The wall itself never displays them.
        if row.get('cast'):
            import xbmc
            tag.setCast([xbmc.Actor(actor.get('name', ''), actor.get('role', ''),
                                   actor.get('order', -1), actor.get('thumbnail', ''))
                         for actor in row['cast']])
        if kind == 'tvshow':
            total = int(row.get('episode') or 0)
            watched = int(row.get('watchedepisodes') or 0)
            for key, value in (('TotalEpisodes', total), ('WatchedEpisodes', watched),
                               ('UnWatchedEpisodes', max(0, total - watched))):
                result.setProperty(key, str(value))
        for stream_type, streams in (row.get('streamdetails') or {}).items():
            if stream_type in ('video', 'audio', 'subtitle'):
                for stream in streams:
                    result.addStreamInfo(stream_type, stream)
    else:
        result = gui.ListItem(label=row.get('label') or row.get('title') or '媒体节点', offscreen=True)
        result.setArt(row.get('art') or {})
    return result


def directory(handle, query):
    import json
    import xbmcgui
    import xbmcplugin
    from provider import rpc, movie_item, detail_path
    from emby_rating import list_ratings
    selection = normalize(json.loads(query))
    # B-01/B-02: plugin-layer short cache for the directory rows. The
    # full fetch is kept (no paging is forced on the UI), but a re-entry
    # within 15s skips the Files.GetDirectory RPC and the filter pass.
    # The key is a hash of the whole normalised selection (origin,
    # method, order, query, genre, year, watched, content), so a sort or
    # filter change can never return another selection's rows. Freshness:
    # a new library item may take up to the 15s window to appear on
    # re-entry; that bound matches the home rows' 15s windows. Only the
    # rows (plus the pre-filter total) are cached; ListItems are always
    # rebuilt, and ratings still go through list_ratings (itself cached).
    # Oversized payloads are not stored, mirroring the genre cache bound.
    import hashlib
    import time
    browse_window = xbmcgui.Window(10000)
    selection_hash = hashlib.sha256(json.dumps(selection, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    browse_key = 'YoPlayer.Infuse.Cache.Browse.' + selection_hash
    rows = None
    total = 0
    try:
        cached_browse = json.loads(browse_window.getProperty(browse_key))
        if 0 <= time.monotonic() - cached_browse['at'] < 15 and isinstance(cached_browse.get('rows'), list):
            rows = cached_browse['rows']
            total = cached_browse['total']
    except (ValueError, KeyError, TypeError):
        rows = None
    if rows is None:
        complete = complete_directory(rpc, selection['origin'], selection['method'], selection['order'])
        total = len(complete)
        rows = filtered(complete, selection)
        try:
            payload = json.dumps({'at': time.monotonic(), 'total': total, 'rows': rows}, ensure_ascii=False)
            if len(payload.encode('utf-8')) <= 2 * 1024 * 1024:
                browse_window.setProperty(browse_key, payload)
            else:
                browse_window.clearProperty(browse_key)
        except Exception:
            pass
    kinds = {r.get('type') for r in rows if r.get('type') in ('movie', 'episode', 'tvshow', 'musicvideo')}
    content = {'movie': 'movies', 'episode': 'episodes', 'tvshow': 'tvshows', 'musicvideo': 'musicvideos'}
    xbmcplugin.setContent(handle, content.get(next(iter(kinds)) if len(kinds) == 1 else '', selection['content']))
    xbmcplugin.setPluginCategory(handle, selection.get('title') or '资料库')
    xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.setProperty(handle, 'YoPlayer.Sort.Method', selection['method'])
    xbmcplugin.setProperty(handle, 'YoPlayer.Sort.Order', selection['order'])
    xbmcplugin.setProperty(handle, 'YoPlayer.Browse.Summary', summary(selection))
    xbmcplugin.setProperty(handle, 'YoPlayer.Browse.SourceCount', str(total))
    xbmcplugin.setProperty(handle, 'YoPlayer.Browse.Empty', 'true' if not rows else 'false')
    xbmcplugin.setProperty(handle, 'YoPlayer.Browse.RatingAvailable', str(sum(score(r) is not None for r in rows)))
    # Kodi accepts the complete directory in one call. Keep all tags and rows,
    # avoiding hundreds of separate Python/C++ directory publication calls.
    # A show is a detail item, not a season-folder click. Kodi checks folder
    # navigation before its native information selection action.
    # Resolve provenance once for this directory, with the same native IDs as
    # the item factory. Passing even an empty score avoids per-item DB opens.
    rating_rows = [dict(row, **{row['type'] + 'id': row.get('id', -1)})
                   if row.get('type') in ('movie', 'tvshow', 'episode', 'musicvideo') else row
                   for row in rows]
    scores = list_ratings([(row, row.get('type')) for row in rating_rows])
    entries = [(detail_path(row.get('type'), row.get('id'), row['file']), item(row, movie_item, xbmcgui, score),
                row.get('filetype') == 'directory' and row.get('type') != 'tvshow')
               for row, score in zip(rows, scores)]
    xbmcplugin.addDirectoryItems(handle, entries, totalItems=len(entries))
    # B-02: cacheToDisc stays False deliberately. Kodi's disc cache would
    # outlive the 15s plugin window with no invalidation hook for a
    # library scan or a selection change, so a stale disc entry could
    # survive indefinitely; the plugin-layer window above gives the
    # re-entry saving without that risk.
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
    return len(rows)
