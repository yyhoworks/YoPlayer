"""Sort complete native directories, retaining members, IDs and media paths."""
import math
from library_state import SORTS, TVSHOW_SORTS, normalize, filtered, summary
FIELDS = ['title', 'year', 'rating', 'votes', 'file', 'playcount', 'lastplayed', 'resume',
          'art', 'plot', 'plotoutline', 'genre', 'runtime', 'director', 'writer', 'studio',
          'mpaa', 'country', 'cast', 'imdbnumber', 'premiered', 'season', 'episode',
          'showtitle', 'tvshowid', 'streamdetails', 'dateadded', 'sorttitle',
          'watchedepisodes', 'tag', 'setid', 'uniqueid', 'originaltitle',
          'tagline', 'trailer', 'set', 'firstaired', 'specialsortseason', 'specialsortepisode']


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
    rows = complete_directory(rpc, selection['origin'], selection['method'], selection['order'])
    total = len(rows)
    rows = filtered(rows, selection)
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
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
    return len(rows)
