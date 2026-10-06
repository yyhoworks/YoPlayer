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
    api_error = None
    try:
        # Kodi returns null, rather than [], when the collection is empty.
        entries = rpc('Favourites.GetFavourites', {'properties': ['window', 'windowparameter', 'thumbnail', 'path']}).get('favourites') or []
    except RuntimeError as exc:
        entries, api_error = [], exc
    # Legacy Minsk editors write this file directly; Kodi's RPC cache can lag.
    if xbmcvfs.exists('special://profile/favourites.xml'):
        source = xbmcvfs.File('special://profile/favourites.xml')
        try:
            return favourites_from_xml(source.read())
        finally:
            source.close()
    if api_error:
        raise api_error
    return entries


def get_libraries(include_hidden=False):
    nodes=emby_libraries(xbmcvfs.translatePath('special://profile/library/video/'))
    return libraries(get_favourites(), preferences(), nodes, include_hidden=include_hidden)


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
    prefs=preferences();all_libraries=get_libraries(include_hidden=True)
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


def filter_legacy_history(records):
    """Resolve old JSON entries only by verified path/ID; never change the JSON."""
    membership=display_membership();result=[]
    for record in records:
        if not isinstance(record,dict):continue
        row=dict(record,file=record.get('file') or record.get('video',''),kind=record.get('type'))
        if not membership.visible(row):continue
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


def cached_media(route):
    window = xbmcgui.Window(10000)
    key = PREFIX + 'Cache.' + route
    membership=display_membership()
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


def cached_home_media(route):
    """Filter before taking the native row limit; randomize a stable full pool."""
    import random
    window=xbmcgui.Window(10000);key=PREFIX+'Cache.'+route
    membership=display_membership()
    try:
        cached=json.loads(window.getProperty(key))
        if time.time()-cached['at']<15 and cached.get('membership')==membership.signature:
            return cached['rows']
    except (ValueError,KeyError,TypeError):pass
    episode=route=='recent-episodes'
    kind,collection,method=('episode','episodes','VideoLibrary.GetEpisodes') if episode else ('movie','movies','VideoLibrary.GetMovies')
    fields=['title','plot','art','file','resume','playcount','lastplayed','dateadded','rating','originaltitle']
    fields+=['showtitle','season','episode','tvshowid','firstaired'] if episode else ['year']
    limit=12 if route=='daily' else 25
    rows=[];start=0;seen=set()
    while True:
        args={'properties':fields,'sort':{'method':'title' if route=='daily' else 'dateadded',
                                                     'order':'ascending' if route=='daily' else 'descending'},
              'limits':{'start':start,'end':start+500}}
        if route=='unwatched':args['filter']={'field':'playcount','operator':'is','value':'0'}
        result=rpc(method,args)
        found=result.get(collection) or []
        for row in found:
            candidate=dict(row,kind=kind);ident=row.get(kind+'id')
            if ident not in seen and row.get('file') and membership.visible(candidate):
                rows.append(candidate);seen.add(ident)
        start+=len(found)
        if not found or start>=result.get('limits',{}).get('total',start) or (route!='daily' and len(rows)>=limit):break
    if route=='daily':rows=random.sample(rows,min(limit,len(rows)))
    else:rows=rows[:limit]
    window.setProperty(key,json.dumps({'at':time.time(),'rows':rows,'membership':membership.signature},ensure_ascii=False))
    return rows


def movie_item(row, kind=None):
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
    decorate(item, row, kind)
    tag.setDbId(int(row.get(kind + 'id', -1)))
    tag.setYear(int(row.get('year') or 0))
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


def plugin_url(route, **params):
    return 'plugin://{}/?{}'.format(ADDON_ID, urlencode(dict(params, route=route)))


def directory(handle, route, query='', revision='', stream_type=''):
    window = xbmcgui.Window(10000)
    if route in {'genres','genres-all','tvshow-genres','tvshow-genres-all','genre-items'}:
        try:
            from genre_directory import directory as genre_directory
            genre_directory(handle,route,query)
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
            revised = xbmcgui.Dialog().input('搜索电影或剧集', defaultt=query)
            query = revised.strip() if revised else query
        else:
            xbmcgui.Dialog().textviewer('媒体搜索', window.getProperty(PREFIX+'Search.Status') or '按标题搜索当前电影与剧集；每类最多显示前 100 条。')
        route = 'search'
    error_key = PREFIX + 'Error.' + route
    window.clearProperty(error_key)
    count = 0
    try:
        if route in {'playback','series-episodes'}:
            import sys
            sys.path.insert(0,xbmcvfs.translatePath('special://home/addons/'+SKIN_ID+'/scripts'))
            if route=='playback':
                from infuse_playback import panel_entries
                entries=panel_entries()
            else:
                from infuse_series import episode_entries
                entries=episode_entries()
            xbmcplugin.setContent(handle,'files')
            for entry in entries:
                entry['revision'] = revision
                item=xbmcgui.ListItem(label=entry['title'],label2=entry.get('detail',''),offscreen=True)
                for key,value in entry.items():
                    item.setProperty(key,str(value).lower() if isinstance(value,bool) else str(value))
                xbmcplugin.addDirectoryItem(handle,plugin_url(route,entry=entry.get('episodeid',str(count))),item,isFolder=False)
                count+=1
        elif route == 'detail-seasons':
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
            entries = get_libraries()
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
            for row in cached_home_media(route):
                xbmcplugin.addDirectoryItem(handle,row['file'],movie_item(row),isFolder=False)
                count+=1
        elif route in {'continue', 'history'}:
            rows = cached_media(route)
            membership=display_membership()
            if route=='continue':
                profile=xbmcvfs.translatePath(xbmcaddon.Addon(ADDON_ID).getAddonInfo('profile'))
                try:
                    with open(os.path.join(profile,'queued-episodes.json'),encoding='utf-8') as f:queued=json.load(f)
                except (OSError,ValueError):queued=[]
                existing={('episode',r.get('episodeid')) for r in rows if r.get('kind')=='episode'}
                for saved in reversed(queued):
                    if ('episode',saved.get('episodeid')) in existing:continue
                    # Fetch live metadata; never display a deleted/stale queued file.
                    try:
                        current=rpc('VideoLibrary.GetEpisodeDetails',dict(episodeid=int(saved['episodeid']),properties=['title','file','art','season','episode','tvshowid','showtitle','resume','playcount','firstaired','plot']))['episodedetails']
                    except (RuntimeError,ValueError,KeyError):continue
                    candidate=dict(current,kind='episode')
                    if membership.visible(candidate):rows.insert(0,candidate)
                    existing.add(('episode',saved.get('episodeid')))
            rows=[r for r in rows if membership.visible(r)][:25]
            xbmcplugin.setContent(handle, 'videos')
            for row in rows:
                if not row.get('file'):
                    continue
                xbmcplugin.addDirectoryItem(handle, row['file'], movie_item(row), isFolder=False)
                count += 1
        elif route == 'search':
            xbmcplugin.setContent(handle, 'videos')
            if query:
                fields = ['title', 'year', 'plot', 'art', 'file', 'playcount', 'resume']
                args = {'filter': {'field': 'title', 'operator': 'contains', 'value': query},
                        'sort': {'method': 'title', 'order': 'ascending'}, 'limits': {'start': 0, 'end': 100}}
                movie_result = rpc('VideoLibrary.GetMovies', dict(args, properties=fields))
                show_result = rpc('VideoLibrary.GetTVShows', dict(args, properties=['title', 'year', 'plot', 'art', 'playcount']))
                movies = movie_result.get('movies') or []
                shows = show_result.get('tvshows') or []
                for row in movies:
                    if row.get('file'):
                        xbmcplugin.addDirectoryItem(handle, row['file'], movie_item(row), isFolder=False)
                        count += 1
                for row in shows:
                    path = 'videodb://tvshows/titles/{}/'.format(int(row['tvshowid']))
                    xbmcplugin.addDirectoryItem(handle, path, movie_item(row, 'tvshow'), isFolder=True)
                    count += 1
                totals = (movie_result.get('limits', {}).get('total', len(movies)), show_result.get('limits', {}).get('total', len(shows)))
                status = '关键词：{}\n电影 {} 条 · 剧集 {} 条'.format(query, *totals)
                if not count:
                    status += '\n没有找到匹配内容，请更换关键词。'
                if any(n > 100 for n in totals):
                    status += '\n每类仅显示前 100 条；可缩小关键词范围。'
                window.setProperty(PREFIX+'Search.Status', status)
                summary = xbmcgui.ListItem(label='没有找到匹配内容 · 更换关键词' if not count else '搜索：{} · 电影 {} / 剧集 {}'.format(query, *totals), offscreen=True)
                summary.setProperty('IsPlayable', 'false')
                xbmcplugin.addDirectoryItem(handle, plugin_url('search-summary', q=query), summary, isFolder=True)
            else:
                window.setProperty(PREFIX+'Search.Status', '请输入关键词搜索电影或剧集。')
            search_again = xbmcgui.ListItem(label='修改关键词 / 重新搜索', offscreen=True)
            xbmcplugin.addDirectoryItem(handle, plugin_url('search-edit', q=query), search_again, isFolder=True)
        else:
            raise ValueError('Unknown route')
        window.setProperty(PREFIX + 'Count.' + route, str(count))
        window.setProperty(PREFIX + 'Loaded.' + route, revision)
        xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
    except Exception as exc:
        window.setProperty(error_key, '内容暂时无法加载，请检查来源或重试')
        frames=' > '.join('{}:{}:{}'.format(os.path.basename(f.filename),f.lineno,f.name) for f in traceback.extract_tb(exc.__traceback__))
        xbmc.log('YoPlayer Infuse provider {}: {} {} [{}]'.format(route, type(exc).__name__,str(exc)[:240],frames), xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False, cacheToDisc=False)
