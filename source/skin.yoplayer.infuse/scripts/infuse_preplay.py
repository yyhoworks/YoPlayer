"""Media-bound pre-play choices from a verified, read-only Emby stream cache.

No server credentials, Emby database writes, or cached-index player setters.
Concrete cached streams are exposed only for one unambiguous media source.
"""
import hashlib
from contextlib import closing
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time
import xbmc
import xbmcaddon
import xbmcvfs

METHODS={'movie':('Movie','movieid','moviedetails'),'episode':('Episode','episodeid','episodedetails'),
         'musicvideo':('MusicVideo','musicvideoid','musicvideodetails')}


def rpc(method,params=None):
    r=json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params or {}})))
    if 'error' in r:raise RuntimeError('媒体资料暂不可用')
    return r.get('result')


def fingerprint(value):return hashlib.sha256(value.encode('utf-8')).hexdigest()


def details(kind,ident):
    method,key,result=METHODS[kind]
    row=rpc('VideoLibrary.Get'+method+'Details',{key:ident,'properties':['file','streamdetails']}).get(result,{})
    if row.get(key)!=ident or not row.get('file'):raise RuntimeError('影片身份已变化')
    return row


def target(kind,ident,file):return kind+':'+str(ident)+':'+fingerprint(file)


def store_path():
    return Path(xbmcvfs.translatePath(xbmcaddon.Addon('plugin.video.yoplayer.home').getAddonInfo('profile')))/'preplay-tracks.json'


def load():
    try:data=json.loads(store_path().read_text(encoding='utf-8'))
    except FileNotFoundError:return {'version':1,'items':{}}
    if not isinstance(data,dict) or data.get('version')!=1 or not isinstance(data.get('items'),dict):
        raise ValueError('开播前偏好格式无效，原文件未改动')
    for key,selection in data['items'].items():
        if not isinstance(key,str) or not re.fullmatch(r'(movie|episode|musicvideo):[0-9]+:[0-9a-f]{64}',key):
            raise ValueError('开播前偏好媒体身份无效，原文件未改动')
        if not isinstance(selection,dict) or set(selection)-{'audio','subtitle'}:
            raise ValueError('开播前偏好轨道格式无效，原文件未改动')
        for stream_type,choice in selection.items():validate_choice(stream_type,choice)
    return data


def validate_choice(stream_type,choice):
    if not isinstance(choice,dict) or choice.get('mode') not in ('default','off','track'):
        raise ValueError('开播前偏好选择无效，原文件未改动')
    if choice['mode']=='off' and stream_type!='subtitle':raise ValueError('只有字幕可关闭')
    if not isinstance(choice.get('label',''),str):raise ValueError('轨道名称无效')
    if choice['mode']!='track':return
    source,identity=choice.get('source'),choice.get('identity')
    if not isinstance(source,dict) or not isinstance(identity,dict):raise ValueError('轨道来源无效')
    if not all(isinstance(source.get(k),str) and source[k] for k in ('database','id','path_hash')):
        raise ValueError('轨道来源身份无效')
    if not isinstance(source.get('item'),int) or isinstance(source['item'],bool):raise ValueError('轨道媒体身份无效')
    index=choice.get('server_index')
    if not isinstance(index,int) or isinstance(index,bool) or index<0:raise ValueError('轨道序号无效')
    if not isinstance(identity.get('name'),str) or not identity['name']:raise ValueError('轨道名称无效')
    for field in ('codec','language'):
        if field in identity and not isinstance(identity[field],str):raise ValueError('轨道描述无效')
    if 'channels' in identity and (type(identity['channels']) is not int or identity['channels']<0):raise ValueError('声道描述无效')


def save(kind,ident,file,stream_type,choice):
    if stream_type not in {'audio','subtitle'}:raise ValueError('Invalid stream type')
    validate_choice(stream_type,choice)
    data=load();data['items'].setdefault(target(kind,ident,file),{})[stream_type]=choice
    p=store_path();p.parent.mkdir(parents=True,exist_ok=True);tmp=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=p.parent,delete=False,suffix='.tmp') as f:
            tmp=f.name;json.dump(data,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
        os.replace(tmp,p)
    finally:
        if tmp and os.path.exists(tmp):os.remove(tmp)


def cached(kind,ident,database_root=None):
    """Read the exact installed v11 cache schema; unknown/multi-source is empty."""
    tables={'movie':('Movie','Video'),'episode':('Episode',),'musicvideo':('MusicVideo',)}.get(kind,())
    root=Path(database_root or xbmcvfs.translatePath('special://database/'))
    matches=[]
    for path in sorted(root.glob('emby*.db')):
        try:
            with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=.2)) as db:
                db.execute('PRAGMA query_only=ON')
                for table in tables:
                    exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()
                    if not exists:continue
                    for row in db.execute('SELECT EmbyId FROM '+table+' WHERE KodiId=?',(ident,)):
                        eid=row[0]
                        sources=db.execute('SELECT MediaSourceId,Path FROM MediaSources WHERE EmbyId=?',(eid,)).fetchall()
                        if len(sources)!=1:return None
                        source={'database':path.name,'item':eid,'id':sources[0][0],'path_hash':fingerprint(sources[0][1])}
                        audio=db.execute('SELECT StreamIndex,DisplayTitle,Codec FROM AudioStreams WHERE EmbyId=? ORDER BY StreamIndex',(eid,)).fetchall()
                        subs=db.execute('SELECT StreamIndex,DisplayTitle,Codec,Language,External FROM Subtitles WHERE EmbyId=? ORDER BY StreamIndex',(eid,)).fetchall()
                        matches.append({'source':source,'audio':audio,'subtitle':subs})
        except (OSError,sqlite3.Error,TypeError):
            # Fail closed for a changed cache schema; default/off still work.
            return None
    return matches[0] if len(matches)==1 else None


def choices(kind,ident,row,database_root=None):
    cache=cached(kind,ident,database_root)
    answer={'audio':[{'mode':'default','label':'默认（沿用播放器）'}],
            'subtitle':[{'mode':'default','label':'默认（沿用播放器）'},{'mode':'off','label':'关闭字幕'}]}
    names = {'audio': '音轨', 'subtitle': '字幕'}
    answer['notes'] = {}
    if not cache:
        answer['notes'] = {k: '未能确认此媒体的单一轨道来源，可在播放后选择'
                           for k in names}
        return answer
    for stream_type, name in names.items():
        if not cache[stream_type]:
            answer['notes'][stream_type] = '此来源未提供' + name + '资料，可在播放后选择'
    # Kodi streamdetails come from this single source during the same Emby
    # sync. Correlate codec/language/channels only when the association is unique.
    for kind,streams in ((k,cache[k]) for k in ('audio','subtitle')):
        metadata=(row.get('streamdetails') or {}).get(kind,[])
        for stream in streams:
            index,label,codec=stream[:3]
            if not isinstance(index,int) or index<0:continue
            descriptor={'name':label,'codec':codec}
            if kind=='subtitle':descriptor.update(language=stream[3],external=bool(stream[4]))
            else:
                matching=[m for m in metadata if normalize_codec(m.get('codec',''))==normalize_codec(codec)]
                # Display titles include channel labels; narrow equal-codec
                # tracks to 5.1/7.1/stereo when unambiguous.
                channel=next((n for token,n in (('7.1',8),('5.1',6),('stereo',2),('mono',1)) if token in label.lower()),None)
                if channel is not None:matching=[m for m in matching if m.get('channels')==channel]
                if matching and len({(m.get('language',''),m.get('channels',0)) for m in matching})==1:
                    descriptor.update(language=matching[0].get('language',''),channels=matching[0].get('channels',0))
            answer[kind].append({'mode':'track','label':label,'source':cache['source'],'server_index':index,'identity':descriptor})
    return answer


def normalize_codec(value):return {'dts':'dca','dtshd_ma':'dca','dtshd_hra':'dca','subrip':'srt','aac_lc':'aac'}.get(str(value).lower(),str(value).lower())


def normalized_name(value):
    value=re.sub(r'默认|default','',value,flags=re.I)
    return re.sub(r'[^\w]','',value,flags=re.UNICODE).casefold()


def language(value):return {'chi':'zho','zh':'zho','undefined':'und','':'und'}.get(str(value).lower(),str(value).lower())



def subtitle_form(value):
    forms=set()
    if re.search(r'繁[体體]|\btraditional\b|\b(?:cht|zh[-_]hant)\b',str(value),re.I):forms.add('hant')
    if re.search(r'[简簡][体體]|\bsimplified\b|\b(?:chs|zh[-_]hans)\b',str(value),re.I):forms.add('hans')
    return next(iter(forms)) if len(forms)==1 else 'ambiguous' if forms else ''


def match_track(choice,tracks,kind=None):
    wanted=choice['identity'];matches=[];named=[];aliased=[]
    for track in tracks:
        # Metadata fields missing from Kodi's subtitle RPC cannot be guessed.
        name_ok=normalized_name(track.get('name',''))==normalized_name(wanted.get('name',''))
        alias_ok=False
        if kind=='subtitle' and language(wanted.get('language',''))=='zho' and language(track.get('language',''))=='zho':
            wanted_form=subtitle_form(wanted.get('name',''));live_form=subtitle_form(track.get('name',''))
            if 'ambiguous' in (wanted_form,live_form):continue
            if wanted_form and live_form:
                if wanted_form!=live_form:continue
                alias_ok=True
        meaningful=False;valid=True
        for field in ('codec','language','channels'):
            if wanted.get(field) in (None,'',0,'und','undefined') or track.get(field) in (None,'',0):continue
            a,b=wanted[field],track[field]
            if field=='codec':a,b=normalize_codec(a),normalize_codec(b)
            if field=='language':a,b=language(a),language(b)
            meaningful=True;valid=valid and a==b
        if valid and (name_ok or meaningful):
            matches.append(track)
            if name_ok:named.append(track)
            elif alias_ok:aliased.append(track)
    matches=named or aliased or matches
    return matches[0] if len(matches)==1 else None


def labels(kind,ident,file,win):
    try:selection=load()['items'].get(target(kind,ident,file),{})
    except (OSError,ValueError,TypeError):
        selection={k:{'label':'偏好不可用'} for k in ('audio','subtitle')}
        xbmc.log('YoPlayer pre-play preferences unavailable; preserving original file',xbmc.LOGWARNING)
    win.setProperty('YoPlayer.Preplay.Target',kind+':'+str(ident))
    win.setProperty('YoPlayer.Preplay.Kind',kind)
    win.setProperty('YoPlayer.Preplay.DBID',str(ident))
    for stream_type in ('audio','subtitle'):
        win.setProperty('YoPlayer.Preplay.'+stream_type,selection.get(stream_type,{}).get('label','默认'))


def live():
    player=next((p for p in rpc('Player.GetActivePlayers') or [] if p.get('type')=='video'),None)
    if not player:raise RuntimeError('No live video')
    pid=player['playerid'];item=rpc('Player.GetItem',{'playerid':pid,'properties':['file']}).get('item',{})
    if item.get('type') not in METHODS or not isinstance(item.get('id'),int) or not item.get('file'):raise RuntimeError('Unbound live media')
    return pid,item,(pid,item['type'],item['id'],item['file'])


class PlaybackDefaults:
    """One item override followed by remaining season defaults at AVStart."""
    def __init__(self,season):self.season=season;self.cancel()

    def cancel(self):
        self.pending=None;self.token=None;self.deadline=0;self.done=set();self.saved=None;self.season.cancel()

    def started(self,data):
        self.cancel();self.season.started(data)
        try:self.pending=json.loads(data).get('item',{});self.deadline=time.monotonic()+3
        except (ValueError,TypeError,AttributeError):self.cancel()

    def poll(self):
        if self.pending is not None:
            try:
                pid,item,token=live()
                if time.monotonic()>self.deadline or (self.token is not None and token!=self.token):self.cancel();return
                if any(self.pending.get(k) is not None and self.pending[k]!=item.get(k) for k in ('id','type')):self.cancel();return
                if self.token is None:
                    self.token=token
                    self.saved=load()['items'].get(target(item['type'],item['id'],item['file']),{})
                    # Explicit item default also overrides a remembered season.
                    self.season.completed.update(self.saved)
                state=rpc('Player.GetProperties',{'playerid':pid,'properties':['audiostreams','subtitles']})
                for kind,choice in self.saved.items():
                    if kind in self.done or kind not in {'audio','subtitle'}:continue
                    if live()[2]!=self.token:self.cancel();return
                    if choice.get('mode')=='default':self.done.add(kind);continue
                    if choice.get('mode')=='off' and kind=='subtitle':
                        rpc('Player.SetSubtitle',{'playerid':pid,'subtitle':'off'});self.done.add(kind);continue
                    if choice.get('mode')!='track':self.done.add(kind);continue
                    cache=cached(item['type'],item['id'])
                    if not cache or cache['source']!=choice.get('source'):self.done.add(kind);continue
                    tracks=state.get('audiostreams' if kind=='audio' else 'subtitles') or []
                    if not tracks:continue
                    track=match_track(choice,tracks,kind)
                    if track is not None and live()[2]==self.token:
                        params={'playerid':pid,'stream' if kind=='audio' else 'subtitle':track['index']}
                        if kind=='subtitle':params['enable']=True
                        rpc('Player.SetAudioStream' if kind=='audio' else 'Player.SetSubtitle',params)
                    else:xbmc.log('YoPlayer pre-play choice has no unique live stream match',xbmc.LOGWARNING)
                    self.done.add(kind)
                if set(self.saved)<=self.done:self.pending=None
            except (OSError,sqlite3.Error,ValueError,TypeError,KeyError,RuntimeError):self.pending=None
        self.season.poll()
