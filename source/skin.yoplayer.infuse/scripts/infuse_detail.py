"""Manual detail operations on the native dialog's current media item."""
import json
import sys
import xbmc
import xbmcgui
import xbmcvfs


def label(name):
    return xbmc.getInfoLabel('ListItem.'+name)


def run(action):
    dialog=xbmcgui.Dialog()
    if action=='more':
        path=xbmcvfs.translatePath('special://skin/scripts/infuse-detail-actions.json')
        with open(path,encoding='utf-8') as f:entries=json.load(f)
        choices=[]
        for entry in entries:
            if entry['visible'] and not xbmc.getCondVisibility(entry['visible']):continue
            commands=[xbmc.getInfoLabel(a['command']) if '$' in a['command'] else a['command'] for a in entry['actions'] if not a['condition'] or xbmc.getCondVisibility(a['condition'])]
            if commands:choices.append((entry['title'],commands))
        selected=dialog.select('更多',[entry[0] for entry in choices])
        if selected>=0:
            for command in choices[selected][1]:xbmc.executebuiltin(command)
    elif action=='plot':
        dialog.textviewer(label('Title') or label('Label'),label('Plot') or '媒体库尚未提供剧情资料。')
    elif action=='info':
        video=' · '.join(filter(None,[label('VideoResolution'),label('VideoCodec'),label('HdrType')]))
        audio=' · '.join(filter(None,[label('AudioCodec'),label('AudioChannels'),label('AudioLanguage')]))
        dialog.textviewer('媒体信息','视频：'+(video or '待播放时读取')+'\n音频：'+(audio or '待播放时读取')+'\n\n'+label('FileNameAndPath'))
    elif action=='favourite':
        title=label('Title') or label('Label')
        path=label('FileNameAndPath')
        if label('DBType')=='tvshow' and label('DBID').isdigit():
            params=dict(title=title,type='window',window='videos',windowparameter='videodb://tvshows/titles/'+label('DBID')+'/')
        elif path:
            params=dict(title=title,type='media',path=path)
        else:
            dialog.ok('收藏','当前媒体没有可用的来源。')
            return
        params['thumbnail']=label('Art(poster)')
        result=json.loads(xbmc.executeJSONRPC(json.dumps(dict(jsonrpc='2.0',id=1,method='Favourites.AddFavourite',params=params))))
        if 'error' in result:
            dialog.ok('收藏','未能修改收藏，请稍后重试。')
        else:
            dialog.notification('收藏','已切换当前媒体的收藏状态',time=2200)


if __name__=='__main__':
    run(sys.argv[1] if len(sys.argv)>1 else 'info')
