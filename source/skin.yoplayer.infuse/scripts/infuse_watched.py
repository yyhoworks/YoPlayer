"""Guarded Emby UserData update, with the installed plugin doing downsync.

The native PlayedItems endpoint also changes history. Use the supported
UserData endpoint with exact existing progress/time instead. Credentials are
read from the existing server configuration only in memory, never persisted.
Local media retains Kodi's native setter; an ambiguous Emby binding fails closed.
"""
from contextlib import closing
from datetime import datetime
import json
import math
from pathlib import Path
import sqlite3
import time
from urllib.parse import urlsplit, quote
from urllib.request import Request, build_opener, HTTPRedirectHandler
import xml.etree.ElementTree as ET
import xbmc
import xbmcaddon
import xbmcvfs

TABLES={'movie':('Movie','Video'),'episode':('Episode',),'musicvideo':('MusicVideo',)}
LOCAL={'movie':('movie','idMovie'),'episode':('episode','idEpisode'),'musicvideo':('musicvideo','idMVideo')}


class WatchedStateError(RuntimeError):
    """A safe user-facing reason; never contains credentials or server URLs."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise WatchedStateError('服务器重定向未受支持')


def binding(kind,ident):
    database=Path(xbmcvfs.translatePath('special://database/'))
    paths=sorted(database.glob('MyVideos*.db'),key=lambda p:int(p.stem[8:]))
    if not paths:raise WatchedStateError('当前影片的文件资料不可用，未更改观看状态')
    table,key=LOCAL[kind]
    with closing(sqlite3.connect(paths[-1].resolve().as_uri()+'?mode=ro',uri=True,timeout=.5)) as db:
        db.execute('PRAGMA query_only=ON')
        rows=db.execute('SELECT idFile FROM '+table+' WHERE '+key+'=?',(ident,)).fetchall()
    if len(rows)!=1 or type(rows[0][0]) is not int or rows[0][0]<=0:
        raise WatchedStateError('当前影片的文件身份不唯一，未更改观看状态')
    file_id=rows[0][0]
    matches=[];mapped=False
    for path in sorted(database.glob('emby_*.db')):
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=.5)) as db:
            db.execute('PRAGMA query_only=ON')
            for table in TABLES[kind]:
                if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone():continue
                # Emby versions can share KodiId while referring to different
                # files. Only the current native file may own this action.
                for eid,fid in db.execute('SELECT EmbyId,KodiFileId FROM '+table+' WHERE KodiId=?',(ident,)):
                    mapped=True
                    if fid==file_id and eid is not None and str(eid):matches.append((path.stem[5:],str(eid)))
    if len(matches)>1:raise WatchedStateError('当前文件的 Emby 媒体归属不唯一，未更改观看状态')
    if mapped and not matches:raise WatchedStateError('当前版本的 Emby 文件映射不可用，请等待同步后重试')
    return matches[0] if matches else None


def precision(kind,ident):
    paths=sorted(Path(xbmcvfs.translatePath('special://database/')).glob('MyVideos*.db'))
    # Highest schema matches Kodi's current video library. Never write SQLite.
    paths.sort(key=lambda p:int(p.stem[8:]))
    if not paths:raise WatchedStateError('精确续播资料不可用')
    table,key=LOCAL[kind]
    with closing(sqlite3.connect(paths[-1].resolve().as_uri()+'?mode=ro',uri=True,timeout=.5)) as db:
        db.execute('PRAGMA query_only=ON');db.execute('BEGIN')
        rows=db.execute('SELECT m.idFile,f.playCount,f.lastPlayed,p.strPath||f.strFilename FROM '+table+
            ' m JOIN files f ON f.idFile=m.idFile JOIN path p ON p.idPath=f.idPath WHERE m.'+key+'=?',(ident,)).fetchall()
        if len(rows)!=1:raise WatchedStateError('精确媒体身份不唯一')
        fid,count,last,file=rows[0]
        bookmarks=db.execute('SELECT timeInSeconds,totalTimeInSeconds,thumbNailImage,player,playerState,type FROM bookmark WHERE idFile=? ORDER BY idBookmark',(fid,)).fetchall()
    return {'file':file,'playcount':count or 0,'lastplayed':last or '', 'bookmarks':bookmarks}


def connection(server):
    if xbmcaddon.Addon('plugin.service.emby-next-gen').getAddonInfo('version') != '11.1.27':
        raise WatchedStateError('当前 Emby 同步版本尚未支持此观看状态接口，未更改状态')
    root=Path(xbmcvfs.translatePath('special://profile/addon_data/plugin.service.emby-next-gen/'))
    config=json.loads((root/('servers_'+server+'.json')).read_text(encoding='utf-8'))
    if config.get('ServerId')!=server:raise WatchedStateError('Emby 服务器身份变化')
    url=config.get('ServerUrl','').rstrip('/');parts=urlsplit(url)
    if parts.scheme not in ('http','https') or not parts.hostname or parts.username or parts.password:
        raise WatchedStateError('Emby 连接资料无效')
    if not config.get('UserId') or not config.get('AccessToken'):raise WatchedStateError('Emby 登录不可用')
    settings=ET.parse(root/'settings.xml').getroot()
    if settings.findtext('.//setting[@id="websocketenabled"]')!='true':raise WatchedStateError('请启用 Emby 实时同步')
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
            if len(raw)>2*1024*1024:raise WatchedStateError('服务器响应过大')
            return json.loads(raw) if raw else {}
    except Exception:raise WatchedStateError('Emby 观看状态请求未能确认') from None


def history_stamp(data):
    last=data.get('LastPlayedDate')
    if not last:return ''
    try:
        return datetime.fromisoformat(last.replace('Z','+00:00')).astimezone().strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError,TypeError,AttributeError):
        raise WatchedStateError('服务器历史时间不可用，未更改观看状态') from None


def resume_ticks(local,data,jump):
    """Retain the precise native stop point across a subsecond server lag.

    Installed Emby updates every bookmark when progress differs. Encode the
    existing native point exactly so its downsync leaves all bookmarks alone.
    Larger differences and missing/duplicate resume points remain conflicts.
    """
    resumes=[b for b in local['bookmarks'] if b[-1]==1]
    ticks=data.get('PlaybackPositionTicks')
    if len(resumes)>1 or type(ticks) is not int or ticks<0:
        raise WatchedStateError('两端续播资料不同，未更改观看状态')
    if not resumes:
        if ticks:return None
        return 0
    actual=resumes[0][0]
    if (not ticks or not isinstance(actual,(int,float)) or not math.isfinite(actual) or
            actual<=0 or not math.isfinite(jump)):
        return None
    expected=max(0,(float(ticks)-float(jump))/10000000.0)
    if abs(actual-expected)>=1.0:return None
    aligned=int(round(actual*10000000.0+jump))
    # Exact inversion is required: even a tiny progress delta makes installed
    # Emby rewrite chapter positions. Never approximate a native resume point.
    if aligned<=0 or (float(aligned)-float(jump))/10000000.0!=actual:return None
    return aligned


def compatible(local,data,jump):
    try:
        stamp=history_stamp(data)
        aligned=resume_ticks(local,data,jump)
    except (WatchedStateError,ValueError,TypeError,OverflowError):return False
    if aligned is None:return False
    if not local['lastplayed'] and stamp:return False
    # A different server point with a later history date may be newer viewing.
    if aligned!=data['PlaybackPositionTicks'] and stamp>local['lastplayed']:return False
    return bool(local['playcount'])==bool(data.get('Played'))


def update(kind,ident,wanted,current,rpc,valid=lambda:True):
    bound=binding(kind,ident)
    if bound is None:
        method=kind.title() if kind!='musicvideo' else 'MusicVideo'
        if not valid() or rpc('Player.GetActivePlayers',{}):raise WatchedStateError('媒体或播放状态变化')
        result=rpc('VideoLibrary.Set'+method+'Details',{kind+'id':ident,'playcount':wanted,'lastplayed':current.get('lastplayed','')})
        if result!='OK':raise WatchedStateError('观看状态更新失败')
        return
    server,item=bound;conn=connection(server);before=precision(kind,ident)
    if before['file']!=current['file'] or before['playcount']!=current.get('playcount',0) or before['lastplayed']!=current.get('lastplayed',''):
        raise WatchedStateError('媒体资料变化')
    row=request(conn,item)
    if str(row.get('Id'))!=item or row.get('Type','').lower()!=kind:raise WatchedStateError('服务器媒体身份变化')
    data=row.get('UserData',{})
    if not compatible(before,data,conn['jump']):raise WatchedStateError('两端续播或观看资料不同，未更改观看状态')
    if precision(kind,ident)!=before or request(conn,item).get('UserData')!=data or not valid() or rpc('Player.GetActivePlayers',{}):
        raise WatchedStateError('媒体、服务器或播放状态变化')
    payload={k:data[k] for k in ('PlaybackPositionTicks','IsFavorite') if k in data}
    payload['LastPlayedDate']=data.get('LastPlayedDate')
    payload['PlaybackPositionTicks']=resume_ticks(before,data,conn['jump'])
    count=data.get('PlayCount',0)
    if type(count) is not int or count<0:raise WatchedStateError('服务器观看次数不可用，未更改观看状态')
    # Played controls the badge; preserve historical play starts/counts.
    count=max(1,count) if wanted else count
    payload.update(Played=bool(wanted),PlayCount=count)
    request(conn,item,payload)
    after=request(conn,item).get('UserData',{})
    if any(after.get(k)!=v for k,v in payload.items()):raise WatchedStateError('服务器观看状态需重新确认')
    monitor=xbmc.Monitor();deadline=time.monotonic()+8
    synced_stamp=history_stamp(after)
    expected_count=count if wanted else 0
    history_retained=False
    while time.monotonic()<deadline:
        actual=precision(kind,ident)
        if actual['file']!=before['file'] or actual['bookmarks']!=before['bookmarks']:
            raise WatchedStateError('本地续播或文件变化，请核对同步状态')
        if actual['lastplayed'] not in (before['lastplayed'],synced_stamp):
            raise WatchedStateError('本地历史出现其他变化，请核对同步状态')
        if actual['playcount']==expected_count:
            if actual['lastplayed']!=before['lastplayed']:
                if (history_retained or not before['lastplayed'] or
                        rpc('Player.GetActivePlayers',{}) or precision(kind,ident)!=actual or
                        request(conn,item).get('UserData',{})!=after):
                    raise WatchedStateError('观看状态已更新，历史保留尚未确认')
                # The server GET can take seconds; recheck after it completes.
                if precision(kind,ident)!=actual or rpc('Player.GetActivePlayers',{}):
                    raise WatchedStateError('观看状态已更新，当前播放或历史已变化')
                # Undo only this action's known LastPlayedDate downsync.
                # Kodi21.3 includes playcount only if that count changes;
                # Emby11.1.27 ignores an item-only OnUpdate for upsync.
                # No playcount, resume, SQLite or configuration fields are set.
                method=kind.title() if kind!='musicvideo' else 'MusicVideo'
                reply=rpc('VideoLibrary.Set'+method+'Details',
                    {kind+'id':ident,'lastplayed':before['lastplayed']})
                if reply!='OK':raise WatchedStateError('观看状态已更新，历史保留尚未确认')
                history_retained=True
                verified=precision(kind,ident)
                if (verified['file']!=before['file'] or verified['bookmarks']!=before['bookmarks'] or
                        verified['lastplayed']!=before['lastplayed'] or verified['playcount']!=expected_count):
                    raise WatchedStateError('观看状态已更新，本地资料需核对')
                actual=verified
            if (not valid() or rpc('Player.GetActivePlayers',{}) or precision(kind,ident)!=actual):
                raise WatchedStateError('观看状态已更新，当前播放或资料已变化')
            return {'playcount':expected_count,'lastplayed':before['lastplayed']}
        if rpc('Player.GetActivePlayers',{}) or monitor.waitForAbort(.2):break
    raise WatchedStateError('服务器已更新，本地同步尚未确认')
