"""Guarded Emby UserData update, with the installed plugin doing downsync.

The native PlayedItems endpoint also changes history. Use the supported
UserData endpoint with exact existing progress/time instead. Credentials are
read from the existing server configuration only in memory, never persisted.
Local media retains Kodi's native setter; an ambiguous Emby binding fails closed.
"""
from contextlib import closing
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import time
from urllib.parse import urlsplit, quote
from urllib.request import Request, build_opener, HTTPRedirectHandler
import xml.etree.ElementTree as ET
import xbmc
import xbmcvfs

TABLES={'movie':('Movie','Video'),'episode':('Episode',),'musicvideo':('MusicVideo',)}
LOCAL={'movie':('movie','idMovie'),'episode':('episode','idEpisode'),'musicvideo':('musicvideo','idMVideo')}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise RuntimeError('服务器重定向未受支持')


def binding(kind,ident):
    matches=[]
    for path in sorted(Path(xbmcvfs.translatePath('special://database/')).glob('emby_*.db')):
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=.5)) as db:
            db.execute('PRAGMA query_only=ON')
            for table in TABLES[kind]:
                if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone():continue
                for eid, in db.execute('SELECT EmbyId FROM '+table+' WHERE KodiId=?',(ident,)):
                    matches.append((path.stem[5:],str(eid)))
    if len(matches)>1:raise RuntimeError('Emby 媒体归属不唯一')
    return matches[0] if matches else None


def precision(kind,ident):
    paths=sorted(Path(xbmcvfs.translatePath('special://database/')).glob('MyVideos*.db'))
    # Highest schema matches Kodi's current video library. Never write SQLite.
    paths.sort(key=lambda p:int(p.stem[8:]))
    if not paths:raise RuntimeError('精确续播资料不可用')
    table,key=LOCAL[kind]
    with closing(sqlite3.connect(paths[-1].resolve().as_uri()+'?mode=ro',uri=True,timeout=.5)) as db:
        db.execute('PRAGMA query_only=ON');db.execute('BEGIN')
        rows=db.execute('SELECT m.idFile,f.playCount,f.lastPlayed,p.strPath||f.strFilename FROM '+table+
            ' m JOIN files f ON f.idFile=m.idFile JOIN path p ON p.idPath=f.idPath WHERE m.'+key+'=?',(ident,)).fetchall()
        if len(rows)!=1:raise RuntimeError('精确媒体身份不唯一')
        fid,count,last,file=rows[0]
        bookmarks=db.execute('SELECT timeInSeconds,totalTimeInSeconds,thumbNailImage,player,playerState,type FROM bookmark WHERE idFile=? ORDER BY idBookmark',(fid,)).fetchall()
    return {'file':file,'playcount':count or 0,'lastplayed':last or '', 'bookmarks':bookmarks}


def connection(server):
    root=Path(xbmcvfs.translatePath('special://profile/addon_data/plugin.service.emby-next-gen/'))
    config=json.loads((root/('servers_'+server+'.json')).read_text(encoding='utf-8'))
    if config.get('ServerId')!=server:raise RuntimeError('Emby 服务器身份变化')
    url=config.get('ServerUrl','').rstrip('/');parts=urlsplit(url)
    if parts.scheme not in ('http','https') or not parts.hostname or parts.username or parts.password:
        raise RuntimeError('Emby 连接资料无效')
    if not config.get('UserId') or not config.get('AccessToken'):raise RuntimeError('Emby 登录不可用')
    settings=ET.parse(root/'settings.xml').getroot()
    if settings.findtext('.//setting[@id="websocketenabled"]')!='true':raise RuntimeError('请启用 Emby 实时同步')
    jump=float(settings.findtext('.//setting[@id="resumeJumpBack"]','0'))
    return {'url':url,'user':config['UserId'],'authentication':config['AccessToken'],'jump':jump}


def request(conn,item,payload=None):
    path=conn['url']+'/Users/'+quote(conn['user'],safe='')+'/Items/'+quote(item,safe='')
    if payload is not None:path+='/UserData'
    req=Request(path,data=json.dumps(payload).encode('utf-8') if payload is not None else None,
        headers={'X-Emby-Token':conn['authentication'],'Content-Type':'application/json'})
    # Reject redirects and never include a URL/token or response body in errors.
    try:
        with build_opener(NoRedirect()).open(req,timeout=5) as response:
            raw=response.read(2*1024*1024+1)
            if len(raw)>2*1024*1024:raise RuntimeError('服务器响应过大')
            return json.loads(raw) if raw else {}
    except Exception:raise RuntimeError('Emby 观看状态请求未能确认') from None


def compatible(local,data,jump):
    resumes=[b for b in local['bookmarks'] if b[-1]==1]
    if len(resumes)>1:return False
    ticks=data.get('PlaybackPositionTicks')
    if type(ticks) is not int or ticks<0:return False
    expected=max(0,ticks/10000000.0-jump) if ticks else 0
    actual=resumes[0][0] if resumes else 0
    if abs(actual-expected)>.000001:return False
    last=data.get('LastPlayedDate')
    if last:
        try:last=datetime.fromisoformat(last.replace('Z','+00:00')).astimezone().strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError,TypeError):return False
    if local['lastplayed']!=(last or ''):return False
    return bool(local['playcount'])==bool(data.get('Played'))


def update(kind,ident,wanted,current,rpc,valid=lambda:True):
    bound=binding(kind,ident)
    if bound is None:
        method=kind.title() if kind!='musicvideo' else 'MusicVideo'
        if not valid() or rpc('Player.GetActivePlayers',{}):raise RuntimeError('媒体或播放状态变化')
        result=rpc('VideoLibrary.Set'+method+'Details',{kind+'id':ident,'playcount':wanted,'lastplayed':current.get('lastplayed','')})
        if result!='OK':raise RuntimeError('观看状态更新失败')
        return
    server,item=bound;conn=connection(server);before=precision(kind,ident)
    if before['file']!=current['file'] or before['playcount']!=current.get('playcount',0) or before['lastplayed']!=current.get('lastplayed',''):
        raise RuntimeError('媒体资料变化')
    row=request(conn,item)
    if str(row.get('Id'))!=item or row.get('Type','').lower()!=kind:raise RuntimeError('服务器媒体身份变化')
    data=row.get('UserData',{})
    if not compatible(before,data,conn['jump']):raise RuntimeError('两端续播或历史不同，未更改观看状态')
    if precision(kind,ident)!=before or request(conn,item).get('UserData')!=data or not valid() or rpc('Player.GetActivePlayers',{}):
        raise RuntimeError('媒体、服务器或播放状态变化')
    payload={k:data[k] for k in ('PlaybackPositionTicks','IsFavorite') if k in data}
    payload['LastPlayedDate']=data.get('LastPlayedDate')
    payload.update(Played=bool(wanted),PlayCount=wanted)
    request(conn,item,payload)
    after=request(conn,item).get('UserData',{})
    if any(after.get(k)!=v for k,v in payload.items()):raise RuntimeError('服务器观看状态需重新确认')
    monitor=xbmc.Monitor();deadline=time.monotonic()+8
    while time.monotonic()<deadline:
        actual=precision(kind,ident)
        if actual['file']!=before['file'] or actual['lastplayed']!=before['lastplayed'] or actual['bookmarks']!=before['bookmarks']:
            raise RuntimeError('本地续播或历史变化，请核对同步状态')
        if actual['playcount']==wanted:return
        if rpc('Player.GetActivePlayers',{}) or monitor.waitForAbort(.2):break
    raise RuntimeError('服务器已更新，本地同步尚未确认')
