"""Real series metadata for the approved overview and five-card episode page."""
import json
import os
import sys
import time
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

PREFIX='YoPlayer.Infuse.Series.'
WINDOW_ID=11198


def rpc(method,params):
    result=json.loads(xbmc.executeJSONRPC(json.dumps(dict(jsonrpc='2.0',id=1,method=method,params=params))))
    if 'error' in result:raise RuntimeError('媒体库资料暂不可用')
    return result.get('result',{})


def home():return xbmcgui.Window(10000)


def get_state():
    return json.loads(home().getProperty(PREFIX+'State') or '{}')


def season_episodes(state):
    return [e for e in state.get('episodes',[]) if e['season']==state.get('season')]


def update(state):
    w=home();episodes=season_episodes(state)
    max_page=max(0,(len(episodes)-1)//5)
    state['page']=max(0,min(max_page,state.get('page',0)))
    page=state['page'];visible=episodes[page*5:page*5+5]
    if not visible:state['selected']=None
    if visible and state.get('selected') not in [e['episodeid'] for e in visible]:state['selected']=visible[0]['episodeid']
    selected=next((e for e in episodes if e['episodeid']==state.get('selected')),None)
    w.setProperty(PREFIX+'State',json.dumps(state,ensure_ascii=False))
    props={'Title':state['show']['title'],'Plot':state['show'].get('plot') or '暂无简介',
           'Poster':state['show'].get('art',{}).get('poster',''),
           'Meta':'{} · {} 集'.format(state['show'].get('year') or '',len(state['episodes'])),
           'Genres':' / '.join(state['show'].get('genre',[])),
           'Watched':'已看过 {} / {} 集'.format(sum(bool(e.get('playcount')) for e in state['episodes']),len(state['episodes'])),
           'Season':'特别篇' if state['season']==0 else '第 {} 季'.format(state['season']),
           'Range':'{}–{} / {} 集'.format(page*5+1,min((page+1)*5,len(episodes)),len(episodes)) if episodes else '暂无分集',
           'Previous':'true' if page>0 else 'false','Next':'true' if page<max_page else 'false',
           'HasEpisodes':'true' if episodes else 'false',
           'HasPlayable':'true' if selected and selected.get('file') else 'false',
           'Selected':'第 {} 季 · 第 {} 集 · {}'.format(selected['season'],selected['episode'],selected['title']) if selected else '',
           'SelectedWatch':'已观看' if selected and selected.get('playcount') else '未观看',
           'Revision':str(time.time_ns())}
    for key,value in props.items():w.setProperty(PREFIX+key,str(value))


def open_series(showid):
    showid=int(showid)
    show=rpc('VideoLibrary.GetTVShowDetails',dict(tvshowid=showid,properties=['title','year','plot','genre','art','episode','playcount']))['tvshowdetails']
    item = xbmcgui.ListItem(label=show['title'], path='videodb://tvshows/titles/{}/'.format(showid), offscreen=True)
    tag = item.getVideoInfoTag()
    tag.setDbId(showid)
    tag.setMediaType('tvshow')
    tag.setTitle(show['title'])
    tag.setTvShowTitle(show['title'])
    tag.setYear(show.get('year') or 0)
    tag.setPlot(show.get('plot') or '')
    tag.setGenres(show.get('genre') or [])
    tag.setPlaycount(show.get('playcount') or 0)
    item.setArt(show.get('art') or {})
    xbmcgui.Dialog().info(item)


def episode_entries():
    state=get_state();episodes=season_episodes(state);page=state.get('page',0)
    entries=[]
    for e in episodes[page*5:page*5+5]:
        seconds=e.get('runtime') or 0
        entries.append(dict(title=e['title'],number=str(e['episode']).zfill(2),episodeid=e['episodeid'],
                            detail='{} 小时 {} 分'.format(seconds//3600,seconds//60%60) if seconds else '时长待获取',
                            watched='已观看' if e.get('playcount') else '未观看',selected=e['episodeid']==state.get('selected')))
    return entries


def queue_path():
    path=xbmcvfs.translatePath(xbmcaddon.Addon('plugin.video.yoplayer.home').getAddonInfo('profile'))
    os.makedirs(path,exist_ok=True)
    return os.path.join(path,'queued-episodes.json')


def run(command,argument=''):
    if command=='open':
        showid=argument or xbmc.getInfoLabel('ListItem.TVShowDBID') or xbmc.getInfoLabel('ListItem.DBID')
        return open_series(showid)
    state=get_state()
    if not state:return
    if command=='season':
        seasons=state['seasons'];index=xbmcgui.Dialog().select('选择季',['特别篇' if s==0 else '第 {} 季'.format(s) for s in seasons],preselect=seasons.index(state['season']))
        if index<0:return
        state.update(season=seasons[index],page=0,selected=None)
    elif command=='page':state['page']+=int(argument)
    elif command=='select':
        item=xbmcgui.Window(WINDOW_ID).getControl(500).getSelectedItem()
        if not item:return
        state['selected']=int(item.getProperty('episodeid'))
    elif command=='info':
        selected=next((e for e in season_episodes(state) if e['episodeid']==state.get('selected')),None)
        text=state['show']['title']+'\n\n'+(state['show'].get('plot') or '暂无剧集简介。')
        if selected:
            text+='\n\n第 {} 季 · 第 {} 集 · {}\n\n{}'.format(selected['season'],selected['episode'],selected['title'],selected.get('plot') or '暂无本集简介。')
        xbmcgui.Dialog().textviewer('完整剧情与分集信息',text)
        return
    elif command=='favorite':
        show=state['show']
        rpc('Favourites.AddFavourite',dict(title=show['title'],type='window',window='videos',windowparameter='videodb://tvshows/titles/{}/'.format(show['tvshowid']),thumbnail=show.get('art',{}).get('poster','')))
        xbmcgui.Dialog().notification('收藏','已切换剧集收藏状态')
        return
    elif command in {'queue','play'}:
        e=next((e for e in season_episodes(state) if e['episodeid']==state.get('selected')),None)
        if not e or not e.get('file'):
            xbmcgui.Dialog().notification('选集','暂无可播放分集，请选择其他季或返回列表')
            return
        if command=='queue':
            path=queue_path()
            try:
                with open(path,encoding='utf-8') as f:queued=json.load(f)
            except (OSError,ValueError):queued=[]
            queued=[r for r in queued if r.get('tvshowid')!=e['tvshowid']]
            queued.insert(0,e)
            temporary=path+'.tmp'
            with open(temporary,'w',encoding='utf-8') as f:json.dump(queued[:40],f,ensure_ascii=False)
            os.replace(temporary,path)
            home().setProperty('YoPlayer.Infuse.Revision',str(time.time_ns()))
            xbmcgui.Dialog().notification('继续观看','已加入所选集，未修改播放进度')
        else:
            resume=e.get('resume',{}).get('position',0)
            choice=xbmcgui.Dialog().select(e['title'],['继续播放','从头播放'] if resume else ['开始播放'])
            if choice<0:return
            rpc('Player.Open',dict(item={'episodeid':e['episodeid']},options={'resume':bool(resume and choice==0)}))
        return
    update(state)


if __name__=='__main__':
    if xbmc.getSkinDir()=='skin.yoplayer.infuse':
        try:run(sys.argv[1] if len(sys.argv)>1 else 'open',sys.argv[2] if len(sys.argv)>2 else '')
        except Exception as exc:
            xbmc.log('Infuse series: '+str(exc),xbmc.LOGWARNING)
            xbmcgui.Dialog().notification('剧集',str(exc),xbmcgui.NOTIFICATION_WARNING)
