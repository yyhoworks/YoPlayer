"""Connect original Infuse stream windows to Kodi, without transport side effects."""
import json
import os
import sys
import time
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs


def rpc(method, params=None):
    response = json.loads(xbmc.executeJSONRPC(json.dumps(
        {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}})))
    if 'error' in response:
        raise RuntimeError('播放器暂时无法完成此操作')
    return response.get('result')


def refresh():
    home = xbmcgui.Window(10000)
    prefix = 'YoPlayer.Infuse.Memory'
    keys = ('Ready', 'File', 'DBID', 'Kind', 'Scope')
    identity = (xbmc.getInfoLabel('Player.Filenameandpath'), xbmc.getInfoLabel('VideoPlayer.DBID'))
    def clear():
        for key in keys:
            home.clearProperty(prefix + key)
    if not xbmc.getCondVisibility('Player.HasVideo') or (
            home.getProperty(prefix + 'File'), home.getProperty(prefix + 'DBID')) != identity:
        clear()  # A changed/stopped media never borrows the previous context.
    try:
        from infuse_stream_memory import live
        _, key, scope, token = live()
        latest = (xbmc.getInfoLabel('Player.Filenameandpath'), xbmc.getInfoLabel('VideoPlayer.DBID'))
        if not token[3] or token[3] != identity[0] or latest != identity or live()[3] != token or not xbmc.getCondVisibility('Player.HasVideo'):
            raise RuntimeError('播放上下文已变化')
        values = {'File': token[3], 'DBID': identity[1],
                  'Kind': 'season' if key.startswith('show:') else 'folder', 'Scope': scope}
        if (home.getProperty(prefix + 'File'), home.getProperty(prefix + 'DBID')) != identity:
            home.clearProperty(prefix + 'Ready')
        for name, value in values.items():
            if home.getProperty(prefix + name) != value:
                home.setProperty(prefix + name, value)
        if home.getProperty(prefix + 'Ready') != 'true':
            home.setProperty(prefix + 'Ready', 'true')
    except (RuntimeError, ValueError, TypeError, KeyError, OSError):
        clear()  # Failed identification invalidates the whole context.
    home.setProperty('YoPlayer.Infuse.StreamRevision', str(time.time_ns()))


def next_episode_exists(call_rpc, episode_id):
    current = call_rpc('VideoLibrary.GetEpisodeDetails', {
        'episodeid': episode_id, 'properties': ['tvshowid', 'season', 'episode']
    }).get('episodedetails', {})
    show_id = current.get('tvshowid', -1)
    season = current.get('season', -1)
    episode = current.get('episode', -1)
    if not all(isinstance(value, int) and value >= 0 for value in (show_id, season, episode)):
        return False
    candidates = call_rpc('VideoLibrary.GetEpisodes', {
        'tvshowid': show_id, 'season': season, 'properties': ['season', 'episode'],
        'filter': {'field': 'episode', 'operator': 'is', 'value': str(episode + 1)}
    }).get('episodes', [])
    return any(item.get('season') == season and item.get('episode') == episode + 1
               for item in candidates)


def osd_context():
    window = xbmcgui.Window(10000)
    property_name = 'YoPlayer.Infuse.NextEpisodeAvailable'
    window.clearProperty(property_name)
    identity = (xbmc.getInfoLabel('VideoPlayer.DBID'), xbmc.getInfoLabel('Player.Filenameandpath'))
    if not xbmc.getCondVisibility('VideoPlayer.Content(episodes)') or not identity[0].isdigit():
        return
    try:
        available = next_episode_exists(rpc, int(identity[0]))
    except (RuntimeError, ValueError, TypeError, KeyError):
        return
    latest = (xbmc.getInfoLabel('VideoPlayer.DBID'), xbmc.getInfoLabel('Player.Filenameandpath'))
    if available and latest == identity and xbmc.getCondVisibility('Window.IsVisible(videoosd)'):
        window.setProperty(property_name, 'true')


def confirm_stop():
    current = rpc('Player.GetItem', {'playerid': 1, 'properties': ['file']}).get('item', {})
    if not current.get('file'):
        return
    home = xbmcgui.Window(10000)
    compact = 'YoPlayer.Infuse.CompactConfirm'
    home.setProperty(compact, 'true')
    try:
        accepted = xbmcgui.Dialog().yesno('退出播放？', '', nolabel='继续播放', yeslabel='确定退出',
                                         defaultbutton=xbmcgui.DLG_YESNO_NO_BTN)
    finally:
        home.clearProperty(compact)
    if not accepted:
        return
    latest = rpc('Player.GetItem', {'playerid': 1, 'properties': ['file']}).get('item', {})
    if latest.get('file') == current['file']:
        rpc('Player.Stop', {'playerid': 1})


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else 'refresh'
    if command == 'osd-context':
        osd_context()
        return
    try:
        if command == 'stop':
            confirm_stop()
        elif command in ('audio', 'subtitle') and len(sys.argv) == 4:
            addon = xbmcaddon.Addon('plugin.video.yoplayer.home')
            folder = os.path.join(xbmcvfs.translatePath(addon.getAddonInfo('path')), 'resources', 'lib')
            if folder not in sys.path:
                sys.path.insert(0, folder)
            from player_streams import select_stream
            select_stream(rpc, command, sys.argv[2], sys.argv[3])
        elif command in ('remember-audio', 'remember-subtitle'):
            from infuse_stream_memory import save
            scope = save('audio' if command == 'remember-audio' else 'subtitle')
            xbmcgui.Dialog().notification('轨道选择已保存', '作用范围：' + scope)
        elif command != 'refresh':
            raise ValueError('不支持的播放操作')
    except (RuntimeError, ValueError, OSError) as exc:
        xbmcgui.Dialog().notification('播放轨道', str(exc), xbmcgui.NOTIFICATION_WARNING)
    finally:
        refresh()


if __name__ == '__main__' and xbmc.getSkinDir() == 'skin.yoplayer.infuse':
    main()
