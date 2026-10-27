"""Kodi adapters for native media nodes and selected media metadata."""
import json
import os
import time
import traceback
from urllib.parse import urlencode
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
from catalog import favourites_from_xml, libraries, emby_libraries, load_preferences, merge_recent
import hashlib


ADDON_ID = 'plugin.video.yoplayer.home'
SKIN_ID = 'skin.yoplayer.infuse'
PREFIX = 'YoPlayer.Infuse.'


def rpc(method, params=None):
    response = json.loads(xbmc.executeJSONRPC(json.dumps(
        {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}}, ensure_ascii=False)))
    if 'error' in response:
        # Avoid logging media paths, server tokens or entire request payloads.
        raise RuntimeError('{}: {} {}'.format(method, response['error'].get('code', 'unknown'), response['error'].get('message','')))
    return response.get('result', {})


def preferences_path():
    profile = xbmcaddon.Addon(ADDON_ID).getAddonInfo('profile')
    return os.path.join(xbmcvfs.translatePath(profile), 'libraries.json')


def preferences():
    return load_preferences(preferences_path())


def get_favourites():
    # Legacy Minsk editors write this file directly; Kodi's RPC cache can lag.
    # The file already takes precedence, so avoid an RPC whose result is discarded.
    if xbmcvfs.exists('special://profile/favourites.xml'):
        source = xbmcvfs.File('special://profile/favourites.xml')
        try:
            return favourites_from_xml(source.read())
        finally:
            source.close()
    # Kodi returns null, rather than [], when the collection is empty.
    return rpc('Favourites.GetFavourites', {'properties': ['window', 'windowparameter', 'thumbnail', 'path']}).get('favourites') or []


def get_libraries(include_hidden=False, config=None):
    nodes=emby_libraries(xbmcvfs.translatePath('special://profile/library/video/'))
    return libraries(get_favourites(), preferences() if config is None else config, nodes, include_hidden=include_hidden)


def get_genres(include_empty=False, kind='movie'):
    from genre_directory import snapshot
    # Legacy include_empty callers also get only populated visible metadata.
    return snapshot(rpc,display_membership(),kind,preferences().get('genres',{}) if kind=='movie' else {})[0]


def genre_path(genre):
    """Typed provider path: filtering protects the result, not just its label."""
    names = genre.get('names') or [genre['name']]
    return plugin_url('genre-items',q=json.dumps({'kind':genre.get('kind','movie'),'names':names},ensure_ascii=False))


def display_membership():
    from visibility import Membership, native_filter
    from urllib.parse import urlsplit, unquote
    prefs=preferences();all_libraries=get_libraries(include_hidden=True, config=prefs)
    window=xbmcgui.Window(10000)
    fingerprints=[]
    def lookup(library):
        path=library['path'];parsed=urlsplit(path)
        if parsed.scheme=='library' and parsed.netloc=='video':
            relative=unquote(parsed.path).strip('/')
            if '..' in relative.split('/'):return None
            source=os.path.join(xbmcvfs.translatePath('special://profile/library/video/'),relative)
        elif path.lower().endswith('.xsp'):source=xbmcvfs.translatePath(path)
        else:return None
        try:
            handle=xbmcvfs.File(source)
            try:text=handle.read()
            finally:handle.close()
            specification=native_filter(text)
            if specification is None:return None
            kind,criteria=specification
            fingerprint=hashlib.sha256((text+str(prefs.get('revision',0))).encode('utf-8')).hexdigest()
            fingerprints.append(fingerprint)
            cache_key=PREFIX+'Membership.'+library['id']
            try:
                cached=json.loads(window.getProperty(cache_key))
                if cached['fingerprint']==fingerprint and time.time()-cached['at']<15:
                    return kind,set(cached['ids'])
            except (ValueError,KeyError,TypeError):pass
            from emby_membership import synced_members
            synced=synced_members(xbmcvfs.translatePath('special://database/'),library,text)
            method,key=('VideoLibrary.GetMovies','movieid') if kind=='movies' else ('VideoLibrary.GetTVShows','tvshowid')
            members=set();start=0
            while True:
                result=rpc(method,{'filter':criteria,'limits':{'start':start,'end':start+500}})
                rows=result.get(kind) or []
                members.update(row[key] for row in rows if isinstance(row.get(key),int))
                total=result.get('limits',{}).get('total',start+len(rows))
                start+=len(rows)
                if not rows or start>=total:break
            if synced is not None and synced[0]==kind:members.update(synced[1])
            window.setProperty(cache_key,json.dumps({'at':time.time(),'fingerprint':fingerprint,'ids':sorted(members)}))
            return kind,members
        except (OSError,ValueError,KeyError,TypeError,RuntimeError):
            return None
    membership=Membership(all_libraries,prefs,lookup)
    membership.signature=hashlib.sha256(json.dumps([prefs,all_libraries,fingerprints],sort_keys=True).encode()).hexdigest()
    return membership


def membership_signature(prefs=None, all_libraries=None):
    """Signature only, without deserialising any library member ID set.

    This is the fast path for result-cache checks (cached_home_media,
    cached_libraries, search cache): on a result-cache hit the caller must
    not pay for display_membership()'s full ID-set loads and database
    scans just to compare a cache key. The fingerprint logic mirrors
    display_membership().lookup(); a divergence can only cause a cache
    miss (safe direction), never a false hit, because the signature is
    only ever compared for equality against a stored signature.
    """
    from visibility import native_filter, hidden, directory_identity
    from urllib.parse import urlsplit, unquote
    prefs = preferences() if prefs is None else prefs
    all_libraries = get_libraries(include_hidden=True, config=prefs) if all_libraries is None else all_libraries
    # Mirror display_membership().lookup() exactly, so this signature is
    # identical to membership.signature (not just usually equal): the
    # Membership constructor never calls lookup() when no library is
    # hidden, and it skips directory-path libraries without fingerprinting
    # them. Without this mirroring the fast path below would silently
    # never hit for the common no-hidden-libraries setup.
    if not any(hidden(library, prefs) for library in all_libraries):
        return hashlib.sha256(json.dumps([prefs, all_libraries, []], sort_keys=True).encode()).hexdigest()
    fingerprints = []
    for library in all_libraries:
        lib_path = library['path']; parsed = urlsplit(lib_path)
        if directory_identity(lib_path) is not None:
            continue
        if parsed.scheme == 'library' and parsed.netloc == 'video':
            relative = unquote(parsed.path).strip('/')
            if '..' in relative.split('/'): continue
            source = os.path.join(xbmcvfs.translatePath('special://profile/library/video/'), relative)
        elif lib_path.lower().endswith('.xsp'):
            source = xbmcvfs.translatePath(lib_path)
        else:
            continue
        try:
            handle = xbmcvfs.File(source)
            try: lib_text = handle.read()
            finally: handle.close()
            if native_filter(lib_text) is None: continue
            fingerprints.append(hashlib.sha256((lib_text + str(prefs.get('revision', 0))).encode('utf-8')).hexdigest())
        except Exception:
            continue
    return hashlib.sha256(json.dumps([prefs, all_libraries, fingerprints], sort_keys=True).encode()).hexdigest()


def filter_legacy_history(records):
    """Resolve old JSON entries only by verified path/ID; never change the JSON."""
    membership=display_membership();result=[]
    for record in records:
        if not isinstance(record,dict):continue
        row=dict(record,file=record.get('file') or record.get('video',''),kind=record.get('type'))
        # Resolve reliable identity before applying visible-overlap precedence.
        if membership.entries and row.get('file'):
            try:
                info=rpc('Files.GetFileDetails',{'file':row['file'],'media':'video'}).get('filedetails',{})
                kind=info.get('type');ident=info.get('id')
                if kind in ('movie','episode') and isinstance(ident,int) and ident>0 and info.get('file')==row['file']:
                    if kind=='episode':
                        info=rpc('VideoLibrary.GetEpisodeDetails',{'episodeid':ident,'properties':['file','tvshowid']}).get('episodedetails',{})
                        if info.get('file')!=row['file']:raise ValueError('Changed file')
                    row.update(info,kind=kind,**{kind+'id':ident})
            except (RuntimeError,ValueError,TypeError,KeyError):pass
        if membership.visible(row):result.append(record)
    return result


def cached_media(route, membership=None):
    window = xbmcgui.Window(10000)
    key = PREFIX + 'Cache.' + route
    if membership is None:
        # C-06: on a result-cache hit, do not build the full membership
        # (ID-set deserialisation + database scans) just to compare a key.
        try:
            cached = json.loads(window.getProperty(key))
            if time.time() - cached['at'] < 15 and cached.get('membership')==membership_signature():
                return cached['rows']
        except (ValueError, KeyError, TypeError):
            pass
    membership=display_membership() if membership is None else membership
    try:
        cached = json.loads(window.getProperty(key))
        if time.time() - cached['at'] < 15 and cached.get('membership')==membership.signature:
            return cached['rows']
    except (ValueError, KeyError, TypeError):
        pass
    fields = ['title', 'year', 'plot', 'art', 'file', 'resume', 'playcount', 'lastplayed', 'dateadded', 'rating', 'originaltitle']
    args = {'properties': fields, 'sort': {'method': 'lastplayed', 'order': 'descending'}, 'limits': {'start': 0, 'end': 50}}
    if route == 'continue':
        args['filter'] = {'field': 'inprogress', 'operator': 'true', 'value': ''}
    # Movie and episode fields differ in Kodi's API; episodes have firstaired,
    # not year. One invalid field rejects the entire mixed continuation row.
    episode_fields=[field for field in fields if field!='year']+['showtitle','season','episode','tvshowid','firstaired']
    def page(method,key,fields,kind):
        kept=[];start=0
        while True:
            result=rpc(method,dict(args,properties=fields,limits={'start':start,'end':start+100}))
            found=result.get(key) or []
            for row in found:
                candidate=dict(row,kind=kind)
                if membership.visible(candidate) and (route=='continue' or row.get('lastplayed')):
                    kept.append(row)
            start+=len(found)
            total=result.get('limits',{}).get('total',start)
            # Read through timestamp ties before choosing the mixed top 25.
            if not found or start>=total or (len(kept)>=25 and found[-1].get('lastplayed','')<kept[24].get('lastplayed','')):break
        return kept
    movies=page('VideoLibrary.GetMovies','movies',fields,'movie')
    episodes=page('VideoLibrary.GetEpisodes','episodes',episode_fields,'episode')
    rows = merge_recent(movies, episodes, inprogress=route == 'continue')
    window.setProperty(key, json.dumps({'at': time.time(), 'rows': rows, 'membership':membership.signature}, ensure_ascii=False))
    return rows


def daily_details(selected, fields, membership):
    """Read only the sampled movies; match batch replies by request identity."""
    if not selected:
        return []
    requests = [{'jsonrpc': '2.0', 'id': index, 'method': 'VideoLibrary.GetMovieDetails',
                 'params': {'movieid': row['movieid'], 'properties': fields}}
                for index, row in enumerate(selected)]
    response = json.loads(xbmc.executeJSONRPC(json.dumps(requests, ensure_ascii=False)))
    if not isinstance(response, list) or len(response) != len(selected):
        raise RuntimeError('每日精选资料未完整返回')
    replies = {reply.get('id'): reply for reply in response if isinstance(reply, dict)}
    if len(replies) != len(selected) or set(replies) != set(range(len(selected))):
        raise RuntimeError('每日精选资料身份不符')
    rows = []
    for index, candidate in enumerate(selected):
        reply = replies[index]
        if 'error' in reply:
            if reply['error'].get('code') == -32602:
                continue  # A movie removed between listing and detail read.
            raise RuntimeError('每日精选资料暂时无法读取')
        row = reply.get('result', {}).get('moviedetails', {})
        if row.get('movieid') != candidate['movieid'] or row.get('file') != candidate['file']:
            continue
        current = dict(row, kind='movie')
        if membership.visible(current):
            rows.append(current)
    return rows


def batch_episode_details(episodeids, fields):
    """One batch JSON-RPC for many episodes, like daily_details().

    Returns {episodeid: row} for replies that arrived intact. A reply
    carrying an error, or an identity mismatch, is dropped for that item
    only (the continue branch's per-item skip behaviour). A batch-level
    failure raises, so the caller can fall back to serial fetching.
    """
    if not episodeids:
        return {}
    requests = [{'jsonrpc': '2.0', 'id': index, 'method': 'VideoLibrary.GetEpisodeDetails',
                 'params': {'episodeid': ident, 'properties': fields}}
                for index, ident in enumerate(episodeids)]
    response = json.loads(xbmc.executeJSONRPC(json.dumps(requests, ensure_ascii=False)))
    if not isinstance(response, list) or len(response) != len(episodeids):
        raise RuntimeError('排队剧集资料未完整返回')
    replies = {reply.get('id'): reply for reply in response if isinstance(reply, dict)}
    if len(replies) != len(episodeids) or set(replies) != set(range(len(episodeids))):
        raise RuntimeError('排队剧集资料身份不符')
    found = {}
    for index, ident in enumerate(episodeids):
        reply = replies[index]
        if 'error' in reply:
            continue
        row = reply.get('result', {}).get('episodedetails', {})
        if row.get('episodeid') == ident:
            found[ident] = row
    return found


def cached_home_media(route):
    """Filter before taking the native row limit; daily picks stay stable per day.

    A-H3/A-H4: validity no longer depends on the global Revision token.
    Revision is bumped by every actions.refresh() (skin reload trigger)
    and would otherwise kill every row on any change. Invalidation now
    comes from (a) actions.refresh() explicitly clearing a route's cache
    key, (b) DataChanged (a real library notification), (c) the
    membership signature, and (d) the 15s window (daily: the calendar day
    instead, and refresh() does not clear the daily key at all, so a
    progress-only or manual refresh never re-scans the movie library
    for the daily snapshot). Daily re-picks only on day / membership /
    DataChanged change; on that miss a full candidate scan is still
    required, because the 12 picks are a random sample of the library.
    """
    import random
    window=xbmcgui.Window(10000);key=PREFIX+'Cache.'+route
    def epoch():
        return [window.getProperty(PREFIX+'DataChanged')]
    current_epoch=epoch()
    day=time.strftime('%Y%m%d')
    try:
        cached=json.loads(window.getProperty(key))
        fresh=time.time()-cached['at']<15
        if route=='daily':fresh=cached.get('day')==day
        if fresh and cached.get('membership')==membership_signature() and cached.get('epoch')==current_epoch:
            return cached['rows']
    except (ValueError,KeyError,TypeError):pass
    membership=display_membership()
    try:
        cached=json.loads(window.getProperty(key))
        fresh=time.time()-cached['at']<15
        if route=='daily':fresh=cached.get('day')==day
        if fresh and cached.get('membership')==membership.signature and cached.get('epoch')==current_epoch:
            return cached['rows']
    except (ValueError,KeyError,TypeError):pass
    episode=route=='recent-episodes'
    kind,collection,method=('episode','episodes','VideoLibrary.GetEpisodes') if episode else ('movie','movies','VideoLibrary.GetMovies')
    fields=['title','plot','art','file','resume','playcount','lastplayed','dateadded','rating','originaltitle']
    fields+=['showtitle','season','episode','tvshowid','firstaired'] if episode else ['year']
    limit=12 if route=='daily' else 25
    rows=[];start=0;seen=set()
    # A-H4: recent/unwatched only need 25 visible rows, so page in 100s and
    # stop as soon as the limit is reached (existing break below); daily
    # keeps 500-row pages because its cache miss must see all candidates.
    page_size=500 if route=='daily' else 100
    while True:
        args={'properties':['file'] if route=='daily' else fields,'sort':{'method':'title' if route=='daily' else 'dateadded',
                                                     'order':'ascending' if route=='daily' else 'descending'},
              'limits':{'start':start,'end':start+page_size}}
        if route=='unwatched':args['filter']={'field':'playcount','operator':'is','value':'0'}
        result=rpc(method,args)
        found=result.get(collection) or []
        for row in found:
            candidate=dict(row,kind=kind);ident=row.get(kind+'id')
            if ident not in seen and row.get('file') and membership.visible(candidate):
                rows.append(candidate);seen.add(ident)
        start+=len(found)
        if not found or start>=result.get('limits',{}).get('total',start) or (route!='daily' and len(rows)>=limit):break
    if route=='daily':rows=daily_details(random.Random(day).sample(rows,min(limit,len(rows))),fields,membership)
    else:rows=rows[:limit]
    if epoch()==current_epoch:
        payload={'at':time.time(),'rows':rows,'membership':membership.signature,'epoch':current_epoch}
        if route=='daily':payload['day']=day
        window.setProperty(key,json.dumps(payload,ensure_ascii=False))
    return rows


def cached_libraries():
    """Library entries for the home row and its hidden count list.

    Both containers call this route on every home open; without a cache
    the favourites file, preferences and node files were re-read twice.
    Same 15s + membership + DataChanged guard as the other home rows.
    A-H3: the epoch no longer includes the global Revision token, so a
    scoped refresh that does not clear this key serves the cached rows
    instead of re-reading; a full refresh clears Cache.libraries
    explicitly in actions.refresh().
    """
    window = xbmcgui.Window(10000); key = PREFIX + 'Cache.libraries'
    def epoch():
        return [window.getProperty(PREFIX + 'DataChanged')]
    current_epoch = epoch()
    try:
        cached = json.loads(window.getProperty(key))
        if time.time() - cached['at'] < 15 and cached.get('membership') == membership_signature() and cached.get('epoch') == current_epoch:
            return cached['rows']
    except (ValueError, KeyError, TypeError):
        pass
    membership = display_membership()
    try:
        cached = json.loads(window.getProperty(key))
        if time.time() - cached['at'] < 15 and cached.get('membership') == membership.signature and cached.get('epoch') == current_epoch:
            return cached['rows']
    except (ValueError, KeyError, TypeError):
        pass
    rows = get_libraries()
    if epoch() == current_epoch:
        window.setProperty(key, json.dumps({'at': time.time(), 'rows': rows, 'membership': membership.signature, 'epoch': current_epoch}, ensure_ascii=False))
    return rows


def movie_item(row, kind=None, rating_score=None, defer_plot=False):
    kind = kind or row.get('kind', 'movie')
    label = row.get('title') or row.get('label') or '未命名媒体'
    item = xbmcgui.ListItem(label=label, offscreen=True)
    art = row.get('art') or {}
    item.setArt(dict(art, thumb=art.get('thumb') or art.get('fanart') or art.get('poster', '')))
    tag = item.getVideoInfoTag()
    tag.setMediaType(kind)
    tag.setTitle(label)
    tag.setOriginalTitle(row.get('originaltitle') or '')
    from emby_rating import decorate
    decorate(item, row, kind, rating_score)
    tag.setDbId(int(row.get(kind + 'id', -1)))
    tag.setYear(int(row.get('year') or 0))
    # E-05 (search lazy): plot is re-read from the database by the native
    # detail dialog, so search items may omit it for first paint.
    if not defer_plot:
        tag.setPlot(row.get('plot', ''))
    tag.setPlaycount(int(row.get('playcount') or 0))
    if kind == 'episode':
        episode = row.get('episode')
        if type(episode) is int and episode >= 0:
            generic = label in ('第{}集'.format(episode), '第 {} 集'.format(episode))
            item.setProperty('YoPlayer.HomeEpisodeTitleSuffix', '' if generic else ' · ' + label)
            item.setProperty('YoPlayer.HomeEpisodeSummaryReady', 'true')
        tag.setTvShowTitle(row.get('showtitle', ''))
        tag.setSeason(int(row.get('season') or 0))
        tag.setEpisode(int(row.get('episode') or 0))
        item.setProperty('TVShowDBID', str(row.get('tvshowid', '')))
    resume = row.get('resume') or {}
    tag.setResumePoint(float(resume.get('position') or 0), float(resume.get('total') or 0))
    if row.get('lastplayed'):
        tag.setLastPlayed(row['lastplayed'])
    if kind != 'tvshow':
        item.setProperty('IsPlayable', 'true')
    if kind in ('movie','episode') and isinstance(row.get(kind+'id'),int) and row[kind+'id']>0 and row.get('file'):
        fingerprint=hashlib.sha256(row['file'].encode()).hexdigest()
        item.addContextMenuItems([('影片快捷菜单','RunScript(special://skin/scripts/infuse_quick_menu.py,{},{},{})'.format(kind,row[kind+'id'],fingerprint))])
    return item


def media_entries(rows, lazy=False):
    """Validate scores and close databases, then build complete native items.

    lazy=True (search only): skip the Emby database pass and the plot
    (E-05). Detail re-reads both from the database, so nothing is lost;
    all other callers keep the full behaviour.
    """
    if lazy:
        scores = [''] * len(rows)
    else:
        from emby_rating import list_ratings
        scores = list_ratings([(row, kind) for row, kind, path, folder in rows])
    return [(detail_path(kind, row.get(kind + 'id'), path), movie_item(row, kind, score, defer_plot=lazy), folder and kind != 'tvshow')
            for (row, kind, path, folder), score in zip(rows, scores)]


def detail_path(kind, ident, original):
    """Keep shows out of Kodi's non-folder videodb episode lookup.

    The plugin information item retains its tvshow tag and DBID. Its route is
    deliberately not playable; native Info displays that tag without a scraper
    interpreting the same numeric ID as an episode ID.
    """
    if kind == 'tvshow':
        if type(ident) is not int or ident <= 0:
            raise ValueError('Missing TV show identity')
        return plugin_url('tvshow-details', q=ident)
    return original


def visible_search(query, membership=None):
    """Read until each visible result limit is filled; preserve media/preferences.

    E-02: visibility cannot be pushed fully into one query, because
    Membership.visible() treats unknown membership as visible, so the
    visible set is not a union of library queries and Kodi filters
    cannot express "id not in a hidden set". The loop therefore
    still filters plugin-side, but stops at 100 visible rows + 1
    (the +1 only decides the "more" flag), and the strict page
    validation below is kept verbatim: a bad page still fails the
    whole search instead of returning partial results.
    E-03: no search-only membership cache exists; this reuses the
    same display_membership() (and its per-library window cache)
    as the home routes. E-04: plot is dropped from both queries;
    file is kept because Membership.visible() needs it for
    directory-kind libraries, even though the tvshow result item
    itself never carries it (its path is synthetic).
    """
    membership = display_membership() if membership is None else membership
    # E-02 fast path: with no hidden libraries every row is visible.
    has_hidden = bool(membership.entries)
    results, more = [], []
    for method, key, kind, fields in (
        ('VideoLibrary.GetMovies', 'movies', 'movie', ['title', 'year', 'art', 'file', 'playcount', 'resume']),
        ('VideoLibrary.GetTVShows', 'tvshows', 'tvshow', ['title', 'year', 'art', 'file', 'playcount'])):
        kept, seen, start = [], set(), 0
        while True:
            response = rpc(method, {'properties': fields,
                'filter': {'field': 'title', 'operator': 'contains', 'value': query},
                'sort': {'method': 'title', 'order': 'ascending'},
                'limits': {'start': start, 'end': start + 100}})
            rows = response.get(key) or []
            limits = response.get('limits', {})
            total = limits.get('total')
            if (type(total) is not int or total < start + len(rows)
                    or limits.get('start') != start or limits.get('end') != start + len(rows)
                    or (not rows and start < total)):
                raise RuntimeError('Incomplete search page')
            for row in rows:
                ident = row.get(kind + 'id')
                if type(ident) is not int or ident <= 0 or ident in seen:
                    continue
                seen.add(ident)
                if kind == 'movie' and not row.get('file'):
                    continue
                if not has_hidden or membership.visible(dict(row, kind=kind)):
                    kept.append(row)
                    if len(kept) > 100:
                        break
            start += len(rows)
            if len(kept) > 100 or start >= total:
                break
        results.append(kept[:100])
        more.append(len(kept) > 100)
    return results[0], results[1], more


def plugin_url(route, **params):
    return 'plugin://{}/?{}'.format(ADDON_ID, urlencode(dict(params, route=route)))


def directory(handle, route, query='', revision='', stream_type='', probe=False):
    window = xbmcgui.Window(10000)
    if route == 'tvshow-details':
        # Explicit Play on a show is also information, never a guessed episode.
        import sys
        sys.path.insert(0, xbmcvfs.translatePath('special://home/addons/' + SKIN_ID + '/scripts'))
        from infuse_series import open_series
        try:
            open_series(int(query))
        finally:
            xbmcplugin.endOfDirectory(handle, succeeded=False, cacheToDisc=False)
        return
    if route in {'genres','genres-all','tvshow-genres','tvshow-genres-all','genre-items'}:
        try:
            from genre_directory import directory as genre_directory
            genre_directory(handle,route,query,probe)
        except (ValueError,TypeError,KeyError,RuntimeError):
            window.setProperty(PREFIX+'Error.'+route,'分类资料暂不可用')
            xbmcplugin.endOfDirectory(handle,succeeded=False,cacheToDisc=False)
        return
    if route == 'native-browse':
        try:
            from browse_directory import directory as native_directory
            native_directory(handle, query)
        except (ValueError, TypeError, KeyError, RuntimeError) as exc:
            xbmc.log('YoPlayer full-directory sorting: ' + type(exc).__name__, xbmc.LOGWARNING)
            xbmcgui.Dialog().notification('排序未完成', '目录已变化或未返回完整内容，请重新打开原列表。')
            xbmcplugin.endOfDirectory(handle, succeeded=False, cacheToDisc=False)
        return
    if route in {'search-edit', 'search-summary'}:
        if route == 'search-edit':
            # E-08: reuse the first-search self-drawn sheet. Dialog.input
            # falls back to the native keyboard when the skin is not
            # Infuse or extra arguments are given, so the old fallback
            # path is preserved exactly.
            from home_dialog import Dialog as HomeDialog
            revised = HomeDialog().input('搜索电影或剧集', defaultt=query)
            query = revised.strip() if revised else query
        else:
            xbmcgui.Dialog().textviewer('媒体搜索', window.getProperty(PREFIX+'Search.Status') or '按标题搜索当前电影与剧集；每类最多显示前 100 条。')
        route = 'search'
    error_key = PREFIX + 'Error.' + route
    window.clearProperty(error_key)
    count = 0
    try:
        if route == 'detail-seasons':
            showid = int(query)
            if showid <= 0 or not revision:
                raise ValueError('Missing season-tab identity')
            rows = rpc('VideoLibrary.GetSeasons', {'tvshowid': showid, 'properties': ['season']}).get('seasons') or []
            numbers = sorted({int(row['season']) for row in rows if int(row.get('season', -1)) >= 0})
            xbmcplugin.setContent(handle, 'files')
            for number in numbers + ([-1] if numbers else []):
                label = '全部剧集' if number == -1 else '特别篇' if number == 0 else '第 {} 季'.format(number)
                item = xbmcgui.ListItem(label=label, offscreen=True)
                item.setProperty('season', str(number))
                item.setProperty('revision', revision)
                item.setProperty('IsPlayable', 'false')
                xbmcplugin.addDirectoryItem(handle, plugin_url(route, q=showid, revision=revision, season=number), item, isFolder=False)
                count += 1
        elif route == 'player-streams':
            from player_streams import stream_entries
            xbmcplugin.setContent(handle, 'files')
            for row in stream_entries(rpc, stream_type):
                item = xbmcgui.ListItem(label=row['title'], label2=row['detail'], offscreen=True)
                for key, value in row['properties'].items():
                    item.setProperty(key, value)
                item.setProperty('IsPlayable', 'false')
                xbmcplugin.addDirectoryItem(handle, plugin_url('player-streams', stream_type=stream_type), item, isFolder=False)
                count += 1
        elif route == 'libraries':
            entries = cached_libraries()
            if probe: entries = entries[:1]
            xbmcplugin.setContent(handle, 'files')
            for library in entries:
                item = xbmcgui.ListItem(label=library['name'], offscreen=True)
                fallback = 'special://home/addons/{}/media/infuse/library_placeholder.png'.format(SKIN_ID)
                thumb = library['thumb'] or fallback
                item.setArt({'thumb': thumb, 'icon': thumb, 'fanart': thumb})
                item.setProperty('Infuse.LibraryId', library['id'])
                item.setProperty('Infuse.LibraryPath', library['path'])
                item.setProperty('Infuse.LibrarySource', library['source'])
                item.addContextMenuItems([('管理此分库', 'RunScript(special://skin/scripts/infuse.py,library,{})'.format(library['id']))])
                xbmcplugin.addDirectoryItem(handle, library['path'], item, isFolder=True)
                count += 1
        elif route in {'daily','recent-movies','recent-episodes','unwatched'}:
            xbmcplugin.setContent(handle, 'videos')
            rows = cached_home_media(route)
            if probe: rows = rows[:1]
            entries = media_entries([(row, row.get('kind','movie'), row['file'], False)
                                     for row in rows])
            xbmcplugin.addDirectoryItems(handle, entries, totalItems=len(entries))
            count = len(entries)
        elif route in {'continue', 'history'}:
            rows = list(cached_media(route))
            if route=='continue':
                profile=xbmcvfs.translatePath(xbmcaddon.Addon(ADDON_ID).getAddonInfo('profile'))
                try:
                    with open(os.path.join(profile,'queued-episodes.json'),encoding='utf-8') as f:queued=json.load(f)
                except (OSError,ValueError):queued=[]
                existing={('episode',r.get('episodeid')) for r in rows if r.get('kind')=='episode'}
                # C-08: collect the missing queued episodes first, then fetch
                # them in one batch JSON-RPC (like daily_details) instead of
                # one serial GetEpisodeDetails per item. Order and skip
                # behaviour are unchanged: the front segment below is built
                # in queued order, and any item whose fetch fails is skipped.
                # Fetch live metadata; never display a deleted/stale queued file.
                missing = []
                for saved in queued:
                    try:
                        ident = int(saved.get('episodeid'))
                    except (ValueError, TypeError):
                        continue
                    if ('episode', saved.get('episodeid')) in existing or ident in missing:
                        continue
                    missing.append(ident)
                if missing:
                    membership = display_membership()
                    queued_fields = ['title', 'file', 'art', 'season', 'episode', 'tvshowid', 'showtitle', 'resume', 'playcount', 'firstaired', 'plot']
                    try:
                        fetched = batch_episode_details(missing, queued_fields)
                    except Exception:
                        # Batch-level failure: fall back to the old serial path,
                        # which skips failed items one by one.
                        fetched = {}
                        for ident in missing:
                            try:
                                fetched[ident] = rpc('VideoLibrary.GetEpisodeDetails', dict(episodeid=ident, properties=queued_fields))['episodedetails']
                            except (RuntimeError, ValueError, KeyError):
                                continue
                    for ident in reversed(missing):
                        current = fetched.get(ident)
                        if current is None:
                            continue
                        candidate = dict(current, kind='episode')
                        if membership.visible(candidate):
                            rows.insert(0, candidate)
                        existing.add(('episode', ident))
            rows = rows[:25]
            if probe: rows = rows[:1]
            xbmcplugin.setContent(handle, 'videos')
            entries = media_entries([(row, row.get('kind','movie'), row['file'], False)
                                     for row in rows if row.get('file')])
            xbmcplugin.addDirectoryItems(handle, entries, totalItems=len(entries))
            count = len(entries)
        elif route == 'search':
            xbmcplugin.setContent(handle, 'videos')
            entries = []
            summary_entry = None
            result_entries = []
            if query:
                # E-01: same query within 15s reuses the last search rows
                # (cancelled re-search and summary return therefore do not
                # re-scan). The cache is keyed by the exact query plus the
                # membership signature, so a library-visibility change
                # invalidates it; library content changes are bounded by
                # the 15s window, matching the home rows. ListItems are
                # still rebuilt per directory call; only the RPC scan and
                # the rating pass are skipped on a hit (see lazy below).
                movies = shows = more = status = None
                try:
                    cached_search = json.loads(window.getProperty(PREFIX + 'Search.Cache'))
                    if cached_search.get('query') == query and time.time() - cached_search['at'] < 15 and cached_search.get('membership') == membership_signature():
                        movies, shows, more, status = cached_search['movies'], cached_search['shows'], cached_search['more'], cached_search['status']
                except (ValueError, KeyError, TypeError):
                    pass
                if movies is None:
                    movies, shows, more = visible_search(query)
                    totals = [str(len(rows)) + ('+' if extra else '') for rows, extra in zip((movies, shows), more)]
                    status = '关键词：{}\n电影 {} 条 · 剧集 {} 条'.format(query, *totals)
                    if not movies and not shows:
                        status += '\n没有找到匹配内容，请更换关键词。'
                    if any(more):
                        status += '\n每类仅显示前 100 条；可缩小关键词范围。'
                    try:
                        window.setProperty(PREFIX + 'Search.Cache', json.dumps({'at': time.time(), 'query': query, 'movies': movies, 'shows': shows, 'more': more, 'status': status, 'membership': membership_signature()}, ensure_ascii=False))
                    except Exception:
                        pass
                window.setProperty(PREFIX + 'Search.Status', status)
                # E-05: first paint skips the rating database pass and plot.
                result_entries = media_entries(
                    [(row, row.get('kind', 'movie'), row['file'], False) for row in movies if row.get('file')] +
                    [(row, 'tvshow', 'videodb://tvshows/titles/{}/'.format(int(row['tvshowid'])), True) for row in shows], lazy=True)
                count = len(result_entries)
                totals = [str(len(rows)) + ('+' if extra else '') for rows, extra in zip((movies, shows), more)]
                summary = xbmcgui.ListItem(label='没有找到匹配内容 · 更换关键词' if not count else '搜索：{} · 电影 {} / 剧集 {}'.format(query, *totals), offscreen=True)
                summary.setProperty('IsPlayable', 'false')
                summary_entry = (plugin_url('search-summary', q=query), summary, True)
            else:
                window.setProperty(PREFIX + 'Search.Status', '请输入关键词搜索电影或剧集。')
            search_again = xbmcgui.ListItem(label='修改关键词 / 重新搜索', offscreen=True)
            # E-06: the re-search entry is pinned to the top (with the
            # summary directly after it), instead of after all results,
            # so changing the keyword no longer requires paging through
            # up to 200 results. count above still counts media only.
            entries = [(plugin_url('search-edit', q=query), search_again, True)] + ([summary_entry] if summary_entry else []) + result_entries
            xbmcplugin.addDirectoryItems(handle, entries, totalItems=len(entries))
        else:
            raise ValueError('Unknown route')
        if not probe or count == 0:
            window.setProperty(PREFIX + 'Count.' + route, str(count))
            window.setProperty(PREFIX + 'Loaded.' + route, revision)
        xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
    except Exception as exc:
        window.setProperty(error_key, '内容暂时无法加载，请检查来源或重试')
        frames=' > '.join('{}:{}:{}'.format(os.path.basename(f.filename),f.lineno,f.name) for f in traceback.extract_tb(exc.__traceback__))
        xbmc.log('YoPlayer Infuse provider {}: {} {} [{}]'.format(route, type(exc).__name__,str(exc)[:240],frames), xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False, cacheToDisc=False)

