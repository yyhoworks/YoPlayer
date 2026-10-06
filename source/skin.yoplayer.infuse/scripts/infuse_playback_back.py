"""Confirm a physical Back key in full-screen video; never install keymaps.

The separately deployed keymap supplies the original native action for other
skins. Semantic Input.Back bypasses keymaps and is not a test of this entry.
"""
import json
import sys
import xbmc
import xbmcgui

SKIN_ID = 'skin.yoplayer.infuse'
BUSY = 'YoPlayer.Infuse.PlaybackBackBusy'
COMPACT = 'YoPlayer.Infuse.CompactConfirm'
FALLBACK_ACTIONS = {'Back': 'Action(Back)', 'FullScreen': 'Action(FullScreen)',
                    'Legacy1126': 'ActivateWindow(1126)'}


def rpc(method, params=None):
    response = json.loads(xbmc.executeJSONRPC(json.dumps({
        'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}})))
    if 'error' in response:
        raise RuntimeError('Player state is unavailable')
    return response.get('result', {})


def identity():
    players = rpc('Player.GetActivePlayers')
    if not any(p.get('playerid') == 1 and p.get('type') == 'video' for p in players):
        return None
    item = rpc('Player.GetItem', {'playerid': 1, 'properties': ['file']}).get('item', {})
    if not item.get('file'):
        return None
    return (1, item.get('type'), item.get('id'), item['file'])


class PlaybackSession(xbmc.Monitor):
    changed = False

    def onNotification(self, sender, method, data):
        # Even restarting the same URL invalidates this confirmation. We never
        # log the item URL because it can contain media-server credentials.
        if method in ('Player.OnStop', 'Player.OnAVStart', 'Player.OnPlay'):
            self.changed = True


def confirm_exit():
    session = PlaybackSession()
    original = identity()
    if original is None:
        return
    home = xbmcgui.Window(10000)
    home.setProperty(COMPACT, 'true')
    try:
        accepted = xbmcgui.Dialog().yesno(
            '退出播放？', '', nolabel='继续播放', yeslabel='确定退出',
            defaultbutton=xbmcgui.DLG_YESNO_NO_BTN)
    finally:
        home.clearProperty(COMPACT)
    if not accepted or session.changed or session.abortRequested():
        return
    if xbmc.getSkinDir() != SKIN_ID or not xbmc.getCondVisibility('Window.IsActive(fullscreenvideo)'):
        return
    if identity() == original and not session.changed:
        rpc('Player.Stop', {'playerid': 1})


def main(fallback='Back'):
    fallback_action = FALLBACK_ACTIONS.get(fallback, FALLBACK_ACTIONS['Back'])
    if xbmc.getSkinDir() != SKIN_ID:
        xbmc.executebuiltin(fallback_action)
        return
    # OSD/track/settings dialogs keep their ordinary Back action. No pause,
    # resume, seek or window-switch command runs on the confirmation path.
    if (not xbmc.getCondVisibility('Window.IsActive(fullscreenvideo)')
            or xbmc.getCondVisibility('System.HasVisibleModalDialog')
            or xbmc.getCondVisibility('Window.IsVisible(videoosd)')):
        xbmc.executebuiltin('Action(Back)')
        return
    home = xbmcgui.Window(10000)
    if home.getProperty(BUSY):
        return
    home.setProperty(BUSY, 'true')
    try:
        confirm_exit()
    except (RuntimeError, ValueError, TypeError, KeyError):
        xbmc.log('YoPlayer: playback exit confirmation cancelled; player state unavailable', xbmc.LOGWARNING)
    finally:
        home.clearProperty(BUSY)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'Back')
