"""Detail-instance guarded actions; preserve resume and keep the dialog open."""
import json
import sys
import time
import uuid
import xbmc
import xbmcgui
from infuse_detail_play import exclusive, selected_context, rpc, PREFIX

OWNER='YoPlayer.DetailAction.Owner'
STATE='YoPlayer.DetailAction.'
METHODS={'movie':('Movie','movieid','moviedetails'), 'episode':('Episode','episodeid','episodedetails'),
         'musicvideo':('MusicVideo','musicvideoid','musicvideodetails')}


def bind(identity):
    win=xbmcgui.Window(12003)
    if (xbmc.getSkinDir() != 'skin.yoplayer.infuse' or xbmcgui.getCurrentWindowDialogId() != 12003
            or not identity or win.getProperty(PREFIX+'Identity') != identity):return
    win.setProperty(OWNER,uuid.uuid4().hex)
    kind=xbmc.getInfoLabel('ListItem.DBType');ident=xbmc.getInfoLabel('ListItem.DBID')
    if kind in METHODS and ident.isdecimal():
        from infuse_preplay import labels,details
        row=details(kind,int(ident))
        labels(kind,int(ident),row['file'],win)


def context(win, identity, owner, kind, ident, season_owner='', season=''):
    if (not identity or not owner or xbmc.getSkinDir() != 'skin.yoplayer.infuse'
            or xbmcgui.getCurrentWindowDialogId() != 12003
            or not xbmc.getCondVisibility('Window.IsActive(movieinformation)')
            or win.getProperty(PREFIX+'Identity') != identity or win.getProperty(OWNER) != owner):return False
    if kind == 'episode':
        return selected_context(win,identity,season_owner,int(season),ident)
    return (kind in METHODS and xbmc.getInfoLabel('ListItem.DBType') == kind
            and xbmc.getInfoLabel('ListItem.DBID') == str(ident)
            and not xbmc.getInfoLabel('ListItem.FileNameAndPath').startswith('plugin://'))


def state(kind, ident, showid=0, season=-1):
    label,key,result=METHODS[kind]
    fields=['file','playcount','lastplayed']
    if kind == 'episode':fields+=['tvshowid','season','episode']
    row=rpc('VideoLibrary.Get'+label+'Details',{key:ident,'properties':fields}).get(result,{})
    if row.get(key) != ident or not row.get('file'):
        raise ValueError('Media identity unavailable')
    if kind == 'episode' and (row.get('tvshowid') != showid or (season != -1 and row.get('season') != season)):
        raise ValueError('Selected episode changed')
    return row


def restore_focus(win, valid):
    monitor=xbmc.Monitor()
    for _ in range(10):
        if not valid():return
        focused=xbmc.getInfoLabel('System.CurrentControlID')
        if focused and focused != '0':return
        try:win.setFocusId(9002)
        except RuntimeError:pass
        if monitor.waitForAbort(.05):return


def toggle(identity, owner, kind, raw_id, season_owner='', raw_season=''):
    if kind not in METHODS or not raw_id.isascii() or not raw_id.isdecimal() or int(raw_id) <= 0:return False
    ident=int(raw_id)
    season=int(raw_season) if kind == 'episode' else -1
    win=xbmcgui.Window(12003)
    valid=lambda:context(win,identity,owner,kind,ident,season_owner,season)
    with exclusive() as acquired:
        if not acquired or not valid():return False
        showid=int(win.getProperty(PREFIX+'ShowID') or 0) if kind == 'episode' else 0
        if kind == 'episode' and showid <= 0:return False
        target=kind+':'+str(ident)
        # Duplicate queued clicks from this instance must not immediately undo
        # a just-confirmed mark. It is memory-only, not media history.
        stamp=win.getProperty(STATE+'LastToggle')
        try:
            last=json.loads(stamp or '{}')
            if last.get('owner') == owner and last.get('target') == target and time.monotonic()-last.get('at',0) < .75:
                return False
        except (ValueError,TypeError):pass
        before=state(kind,ident,showid,season)
        if not valid():return False
        wanted=0 if before.get('playcount',0) > 0 else 1
        label='标为未看' if wanted == 0 else '标为已看'
        picked=xbmcgui.Dialog().contextmenu([label,'取消'])
        if picked != 0:
            restore_focus(win,valid)
            return False
        if not valid():return False
        current=state(kind,ident,showid,season)
        if any(current.get(key) != before.get(key) for key in ('file','playcount','lastplayed','tvshowid','season','episode')):
            return False
        # Do not overwrite any intervening user playback, including a trailer.
        if rpc('Player.GetActivePlayers',{}):
            xbmcgui.Dialog().notification('观看状态未更改','请先停止播放，再修改观看状态。')
            return False
        if not valid():return False
        from infuse_watched import update
        update(kind,ident,wanted,current,rpc,valid)
        after=state(kind,ident,showid,season)
        if after.get('playcount',0) != wanted or after.get('lastplayed','') != current.get('lastplayed',''):raise RuntimeError('Watched update could not be verified')
        same_instance=(win.getProperty(PREFIX+'Identity') == identity and win.getProperty(OWNER) == owner
                       and xbmc.getCondVisibility('Window.IsVisible(movieinformation)'))
        if not same_instance:return True
        if kind == 'episode' and win.getProperty(PREFIX+'Owner') == season_owner:
            # The live season worker reloads this row and restores by DBID.
            win.setProperty(PREFIX+'WatchedUpdate',json.dumps({'owner':season_owner,'episodeid':ident,
                'playcount':wanted,'lastplayed':after.get('lastplayed',''),'season':after.get('season'),'tvshowid':showid}))
        if not valid():return True
        for name,value in [('Kind',kind),('DBID',str(ident)),('Watched',str(wanted))]:win.setProperty(STATE+name,value)
        win.setProperty(STATE+'LastToggle',json.dumps({'owner':owner,'target':target,'at':time.monotonic()}))
        xbmcgui.Dialog().notification('观看状态已更新', '已看' if wanted else '未看')
        restore_focus(win,valid)
        return True


def tracks(stream_type,identity,owner,kind,raw_id,season_owner='',raw_season=''):
    if stream_type not in ('audio','subtitle') or kind not in METHODS or not raw_id.isdecimal():return False
    ident=int(raw_id);season=int(raw_season) if kind=='episode' else -1
    win=xbmcgui.Window(12003)
    valid=lambda:context(win,identity,owner,kind,ident,season_owner,season)
    from infuse_preplay import choices,details,load,target,save,labels
    with exclusive() as acquired:
        if not acquired or not valid():return False
        row=details(kind,ident);file=row['file']
        options=choices(kind,ident,row)
        rows=options[stream_type]
        note=options.get('notes',{}).get(stream_type,'')
        saved=load()['items'].get(target(kind,ident,file),{}).get(stream_type,{})
        selected=next((i for i,r in enumerate(rows) if r==saved),0)
        if not valid():return False
        display=[r['label'] for r in rows]
        if note:
            display=[]
            for index, option in enumerate(rows):
                item=xbmcgui.ListItem(label=option['label'],label2=note if index == 0 else '')
                display.append(item)
        picked=xbmcgui.Dialog().select('默认音轨（当前影片/单集）' if stream_type=='audio' else '默认字幕（当前影片/单集）',
            display,preselect=selected,useDetails=bool(note))
        if not 0<=picked<len(rows) or not valid():return False
        latest=details(kind,ident)
        if latest['file']!=file or choices(kind,ident,latest)[stream_type]!=rows:return False
        if rpc('Player.GetActivePlayers',{}):
            xbmcgui.Dialog().notification('偏好未更改','请在播放面板修改当前轨道，或停止播放后设置。');return False
        if not valid():return False
        save(kind,ident,file,stream_type,rows[picked])
        labels(kind,ident,file,win)
        return True


def main(args):
    try:
        if len(args)==2 and args[0]=='bind':bind(args[1])
        elif len(args)==7 and args[0]=='toggle':toggle(*args[1:])
        elif len(args)==8 and args[0]=='tracks':tracks(*args[1:])
    except (OSError,ValueError,TypeError,KeyError,RuntimeError):
        xbmc.log('YoPlayer: detail action cancelled; context or library unavailable',xbmc.LOGWARNING)
        xbmcgui.Dialog().notification('操作未完成','请在当前详情重新尝试；未清除续播点。')


if __name__=='__main__':main(sys.argv[1:])
