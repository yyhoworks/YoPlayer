"""Complete visible metadata genres and exact typed results; no media mutations."""
import hashlib
import json
import time
from genres import grouped, canonical, display_name

KINDS={'movie':('movies','VideoLibrary.GetMovies','movieid'),
       'tvshow':('tvshows','VideoLibrary.GetTVShows','tvshowid')}
PALETTE={'动作':0,'科幻':1,'犯罪':2,'动画':3,'纪录片':4,'喜剧':5,'爱情':6,'恐怖':7}


def artwork(group,rows,membership,window,exists=None):
    """Cache only a choice from the current visible snapshot, never old artwork."""
    import xbmcvfs
    from urllib.parse import urlsplit
    exists=exists or xbmcvfs.exists
    eligible=[];kind=group['kind'];names=set(group['names'])
    for row in rows:
        if row.get('kind')!=kind or not names&set((row.get('genre') or [])):continue
        art=row.get('art') or {}
        for field in ('fanart','landscape'):
            value=art.get(field)
            if not isinstance(value,str) or not value:continue
            parsed=urlsplit(value)
            local=parsed.scheme in ('','special') or (len(parsed.scheme)==1 and value[1:2]==':')
            if local and not exists(value):continue
            eligible.append((row[kind+'id'],field,value));break
    eligible.sort(key=lambda r:(r[0],r[1],r[2]))
    signature=hashlib.sha256(json.dumps([getattr(membership,'signature',''),eligible],sort_keys=True).encode()).hexdigest()
    key='YoPlayer.Infuse.GenreArt.'+hashlib.sha256((kind+'\0'+group['name']).encode()).hexdigest()
    try:
        cached=json.loads(window.getProperty(key))
        if cached.get('signature')==signature and cached.get('art','') in {r[2] for r in eligible}:return cached['art']
    except (ValueError,TypeError):pass
    chosen=eligible[0][2] if eligible else ''
    window.setProperty(key,json.dumps({'signature':signature,'art':chosen},ensure_ascii=False))
    return chosen


def gradient(group):
    index=PALETTE.get(group['name'],int(hashlib.sha256(group['name'].encode()).hexdigest()[:8],16)%8)
    return 'infuse/genre50/gradient-'+str(index)+'.png'


def purge_art_cache(window,kind,groups):
    registry='YoPlayer.Infuse.GenreArt.Keys.'+kind
    current={'YoPlayer.Infuse.GenreArt.'+hashlib.sha256((kind+'\0'+g['name']).encode()).hexdigest() for g in groups}
    try:old=set(json.loads(window.getProperty(registry)))
    except (ValueError,TypeError):old=set()
    for key in old-current:
        if isinstance(key,str) and key.startswith('YoPlayer.Infuse.GenreArt.'):window.clearProperty(key)
    window.setProperty(registry,json.dumps(sorted(current)))


def complete(rpc,kind,summary=False,criteria=None):
    collection,method,key=KINDS[kind];start=0;seen=set();rows=[]
    fields=['title','genre','art','file','plot','playcount','year','rating','originaltitle','dateadded']
    if summary:fields=['title','genre','art','file']
    elif kind=='tvshow':fields+=['episode','watchedepisodes']
    else:fields+=['resume','lastplayed']
    while True:
        args={'properties':fields,'limits':{'start':start,'end':start+500},'sort':{'method':'title','order':'ascending'}}
        if criteria is not None:args['filter']=criteria
        result=rpc(method,args)
        page=result.get(collection) or [];new=0
        for row in page:
            ident=row.get(key)
            if type(ident) is int and ident>=0 and ident not in seen:
                seen.add(ident);rows.append(dict(row,kind=kind));new+=1
        total=result.get('limits',{}).get('total',start+len(page))
        start+=len(page)
        if start>=total:break
        if not page or not new:raise RuntimeError('分类资料未完整返回')
    return rows


def cached_summary(rpc,kind,window):
    """Reuse only unfiltered widget metadata; each request applies live membership."""
    prefix='YoPlayer.Infuse.'
    key=prefix+'Cache.GenreSummary.'+kind
    def epoch():
        return [window.getProperty(prefix+'Revision'),window.getProperty(prefix+'DataChanged')]
    current=epoch()
    try:
        cached=json.loads(window.getProperty(key))
        elapsed=time.monotonic()-cached['at']
        if 0<=elapsed<15 and cached['epoch']==current and isinstance(cached['rows'],list):
            return cached['rows']
    except (ValueError,KeyError,TypeError):pass
    rows=complete(rpc,kind,summary=True)
    # Don't publish a page snapshot after a refresh/library notification races it.
    if epoch()==current:
        payload=json.dumps({'at':time.monotonic(),'epoch':current,'rows':rows},ensure_ascii=False)
        # Large libraries still work; bound optional Window-property cache memory.
        if len(payload.encode('utf-8'))<=2*1024*1024:window.setProperty(key,payload)
        else:window.clearProperty(key)
    return rows


def snapshot(rpc,membership,kind,config=None,rows=None):
    if kind not in KINDS:raise ValueError('分类媒体类型无效')
    rows=[r for r in (complete(rpc,kind,summary=True) if rows is None else rows) if membership.visible(r)]
    names=sorted({g for r in rows for g in (r.get('genre') or []) if isinstance(g,str) and g.strip()},key=str.casefold)
    # Display-only identity; route identity is (kind, exact source names), never
    # Kodi's possibly overlapping movie/show genreid or a guessed native filter.
    values=[{'genreid':int(hashlib.sha256((kind+'\0'+name).encode()).hexdigest()[:15],16),'label':name} for name in names]
    groups=grouped(values)
    order=[canonical(x.get('name','')) for x in (config or {}).get('selected',[]) if isinstance(x,dict)]
    groups.sort(key=lambda g:(order.index(g['name']) if g['name'] in order else len(order),g['name'].casefold()))
    for group in groups:
        group['kind']=kind;group['count']=sum(bool(set(group['names'])&set((r.get('genre') or []))) for r in rows)
    return groups,rows


def request(text):
    value=json.loads(text)
    if not isinstance(value,dict) or set(value)!={'kind','names'} or value['kind'] not in KINDS:raise ValueError('分类路由无效')
    names=value['names']
    if not isinstance(names,list) or not 1<=len(names)<=100 or not all(isinstance(n,str) and 0<len(n)<=512 for n in names):raise ValueError('分类名称无效')
    return value['kind'],set(names)


def results(rpc,membership,text):
    kind,names=request(text)
    criteria={'field':'genre','operator':'is','value':sorted(names)}
    return kind,[r for r in complete(rpc,kind,criteria=criteria) if membership.visible(r) and names&set((r.get('genre') or []))]


def directory(handle,route,query=''):
    import xbmcgui
    import xbmcplugin
    from provider import rpc,display_membership,preferences,plugin_url,movie_item
    membership=display_membership()
    if route=='genre-items':
        from browse_directory import item
        kind,rows=results(rpc,membership,query)
        xbmcplugin.setContent(handle,KINDS[kind][0]);entries=[]
        for row in rows:
            ident=row[kind+'id'];folder=kind=='tvshow'
            path='videodb://tvshows/titles/{}/'.format(ident) if folder else row.get('file','')
            if not path:continue
            native=dict(row,type=kind,id=ident,file=path,filetype='directory' if folder else 'file')
            entries.append((path,item(native,movie_item,xbmcgui),False))
        xbmcplugin.addDirectoryItems(handle,entries,totalItems=len(entries))
        xbmcplugin.setPluginCategory(handle,'剧集类型' if kind=='tvshow' else '电影类型')
        count=len(entries)
    else:
        kind='tvshow' if route.startswith('tvshow-') else 'movie'
        prefs=preferences()
        import xbmc
        window=xbmcgui.Window(10000)
        groups,visible_rows=snapshot(rpc,membership,kind,prefs.get('genres',{}) if kind=='movie' else {},
                                    rows=cached_summary(rpc,kind,window))
        if route=='genres' and not xbmc.getCondVisibility('Skin.HasSetting(YoPlayerGenreDisplayMigrated)') and prefs.get('genres',{}).get('hidden',False):groups=[]
        xbmcplugin.setContent(handle,'files');entries=[]
        purge_art_cache(window,kind,groups)
        for group in groups:
            info=xbmcgui.ListItem(label=display_name(group['name']),offscreen=True)
            info.setProperty('YoPlayer.GenreKind',kind);info.setProperty('YoPlayer.GenreCount',str(group['count']))
            art=artwork(group,visible_rows,membership,window)
            info.setArt({'fanart':art,'landscape':art,'thumb':art})
            info.setProperty('YoPlayer.GenreGradient',gradient(group))
            payload=json.dumps({'kind':kind,'names':group['names']},ensure_ascii=False,separators=(',',':'))
            entries.append((plugin_url('genre-items',q=payload),info,True))
        xbmcplugin.addDirectoryItems(handle,entries,totalItems=len(entries));count=len(entries)
        xbmcgui.Window(10000).setProperty('YoPlayer.Infuse.Count.'+route,str(count))
    xbmcplugin.endOfDirectory(handle,succeeded=True,cacheToDisc=False)
    return count
