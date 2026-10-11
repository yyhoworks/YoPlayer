"""Real series metadata for the native detail page.

Only open_series is live: provider.py route 'tvshow-details' and the home
browse router both open shows through it. The legacy five-card command layer
was retired in 2026.10.3.111 after the route and every XML caller were
removed in 109.
"""
import json
import sys
import xbmc
import xbmcgui


def rpc(method,params):
    result=json.loads(xbmc.executeJSONRPC(json.dumps(dict(jsonrpc='2.0',id=1,method=method,params=params))))
    if 'error' in result:raise RuntimeError('媒体库资料暂不可用')
    return result.get('result',{})


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


if __name__=='__main__':
    if xbmc.getSkinDir()=='skin.yoplayer.infuse' and sys.argv[1:2]==['open']:
        try:open_series(sys.argv[2])
        except Exception as exc:
            xbmc.log('Infuse series: '+str(exc),xbmc.LOGWARNING)
            xbmcgui.Dialog().notification('剧集',str(exc),xbmcgui.NOTIFICATION_WARNING)
