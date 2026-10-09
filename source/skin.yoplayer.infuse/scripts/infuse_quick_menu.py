"""Project-owned movie menu; verify library identity before each action."""
import hashlib
import json
import sys
import xbmc
import xbmcgui


def choose_actions(title, actions):
    """Only the project-owned media menu uses this compact dialog."""
    import xbmcvfs
    class Menu(xbmcgui.WindowXMLDialog):
        def onInit(self):
            count = len(actions)
            height = 112 + count * 80 + 48
            top = (1080 - height) // 2
            self.getControl(1010).setPosition(600, top)
            self.getControl(1010).setHeight(height)
            self.getControl(1001).setPosition(636, top + 20)
            self.getControl(1001).setLabel(title or '影片快捷菜单')
            self.getControl(1002).setPosition(1264, top + 22)
            listing = self.getControl(1003)
            listing.setPosition(628, top + 112)
            listing.setHeight(count * 80)
            icons = {'play':'play', 'start':'play', 'details':'list', 'watched':'eye'}
            for text, action in actions:
                item = xbmcgui.ListItem(label=text)
                item.setArt({'icon': 'special://skin/media/infuse/home_sheet/' + icons[action] + '.png'})
                item.setProperty('separator', 'true' if action == 'watched' else 'false')
                listing.addItem(item)
            self.getControl(1005).setPosition(636, top + height - 44)
            self.setFocusId(1003)

        def onClick(self, ident):
            if ident == 1003:
                self.result = self.getControl(1003).getSelectedPosition()
            if ident in (1002, 1003):
                self.close()

        def onAction(self, action):
            if action.getId() in (9, 10, 92):
                self.close()
    menu = Menu('YoPlayerQuickMenu.xml', xbmcvfs.translatePath('special://skin'), 'Default', '1080p')
    menu.result = -1
    menu.doModal()
    result = menu.result
    del menu
    return result


def rpc(method, params=None):
    response=json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params or {}})))
    if 'error' in response:raise RuntimeError('Media changed')
    return response.get('result')


def read(kind, ident):
    capital='Movie' if kind=='movie' else 'Episode'
    fields=['file','title','resume','playcount','lastplayed','art','plot']
    if kind=='episode':fields+=['tvshowid','season','episode']
    return rpc('VideoLibrary.Get'+capital+'Details',{kind+'id':ident,'properties':fields}).get(kind+'details',{})


def run(kind, raw_id, fingerprint):
    if kind not in ('movie','episode') or not raw_id.isascii() or not raw_id.isdecimal() or int(raw_id)<=0:return
    ident=int(raw_id);before=read(kind,ident)
    if not before.get('file') or hashlib.sha256(before['file'].encode()).hexdigest()!=fingerprint:return
    resumed=bool((before.get('resume') or {}).get('position'));watched=bool(before.get('playcount'))
    actions=[('继续播放' if resumed else '播放','play')]
    if resumed:actions.append(('从头播放','start'))
    actions += [('影片详情','details'),('标为未看' if watched else '标为已看','watched')]
    picked=choose_actions(before.get('title',''), actions)
    if not 0<=picked<len(actions):return
    after=read(kind,ident)
    if any(after.get(k)!=before.get(k) for k in ('file','playcount','lastplayed','resume','tvshowid','season','episode')):return
    action=actions[picked][1]
    if action in ('play','start'):
        if rpc('Player.GetActivePlayers'):return
        rpc('Player.Open',{'item':{kind+'id':ident},'options':{'resume':action=='play'}})
    elif action=='details':
        item=xbmcgui.ListItem(label=after.get('title',''),path=after['file'])
        tag=item.getVideoInfoTag();tag.setMediaType(kind);tag.setDbId(ident);tag.setTitle(after.get('title',''))
        item.setArt(after.get('art') or {});xbmcgui.Dialog().info(item)
    else:
        if rpc('Player.GetActivePlayers'):return
        wanted=0 if watched else 1
        from infuse_watched import update
        result=update(kind,ident,wanted,after,rpc)
        confirmed=read(kind,ident)
        if (confirmed.get('playcount',0)!=(result or {}).get('playcount',wanted) or
                confirmed.get('lastplayed','')!=after.get('lastplayed','')):raise RuntimeError('Update unverified')
        xbmcgui.Dialog().notification('观看状态已更新','已看' if wanted else '未看')
        from infuse import import_actions
        import_actions().refresh()


if __name__=='__main__' and xbmc.getSkinDir()=='skin.yoplayer.infuse':
    try:
        if len(sys.argv)==4:run(*sys.argv[1:])
    except (OSError,ValueError,TypeError,KeyError,RuntimeError):
        xbmcgui.Dialog().notification('操作未完成','媒体或播放状态已变化，请重新打开菜单。')
