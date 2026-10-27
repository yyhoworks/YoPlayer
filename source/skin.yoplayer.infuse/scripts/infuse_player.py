"""Connect original Infuse stream windows to Kodi, without transport side effects."""
import hashlib
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


def _track_identity(track):
    # player-streams 列表每项的渲染字段（加当前项标记）就是这几项，
    # 所以它们是轨道签名的组成部分。
    if not isinstance(track, dict):
        return None
    return tuple(track.get(key) for key in ('index', 'language', 'name', 'codec', 'channels'))


def _current_track_state(playerid, return_raw=False):
    """当前轨道选择与轨道清单，读不到时返回 None。

    注意返回 None 而不是空 dict：读不到的状态绝不能与上一次读到的
    状态判为相等，调用方此时应 bump revision（宁可多刷一次，不用旧列表）。
    """
    try:
        state = rpc('Player.GetProperties', {'playerid': playerid, 'properties': [
            'audiostreams', 'currentaudiostream', 'subtitles', 'currentsubtitle',
            'subtitleenabled']})
        if not isinstance(state, dict):
            return (None, None) if return_raw else None
        current_audio = state.get('currentaudiostream') or {}
        current_subtitle = state.get('currentsubtitle') or {}
        summary = {
            'audio': [_track_identity(track) for track in state.get('audiostreams') or []],
            'subtitle': [_track_identity(track) for track in state.get('subtitles') or []],
            'current_audio': current_audio.get('index') if isinstance(current_audio, dict) else None,
            'current_subtitle': current_subtitle.get('index') if isinstance(current_subtitle, dict) else None,
            'subtitle_enabled': bool(state.get('subtitleenabled')),
        }
        return (summary, state) if return_raw else summary
    except (RuntimeError, ValueError, TypeError, KeyError, OSError):
        return (None, None) if return_raw else None


def _stream_signature(memory, media, tracks):
    """1144/1145 player-streams 列表所渲染内容的摘要。

    三部分缺一不可，缺了就会漏刷：
    - memory：refresh() 刚发布（或清空）的 Memory* 属性；
    - media：识别成功时为 live() token（含播放器、媒体 id、文件、剧/季），
      识别失败时为播放器文件/DBID 标签加 live-failed 标记，媒体变化仍能 bump；
    - tracks：当前音轨/字幕序号、字幕开关与全部轨道身份，因为列表每项
      都带 iscurrent 标记与自身的语言/名称/编码/声道。
    """
    payload = {'memory': list(memory), 'media': media, 'tracks': tracks}
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()


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
    playerid = None
    token = None
    try:
        from infuse_stream_memory import live
        _, key, scope, token = live()
        playerid = token[0]
        latest = (xbmc.getInfoLabel('Player.Filenameandpath'), xbmc.getInfoLabel('VideoPlayer.DBID'))
        # 只调一次 live()：原来第二次 live() 是在写属性前复核 token 未变，
        # 现由下面三项标签检查代替（live 文件等于打开时文件、标签未变、仍在播）。
        # 即使残留极小竞态窗口，写脏也是 fail-closed：1144/1145 的记忆条件
        # 还要求 MemoryFile/MemoryDBID 与当前播放器标签一致才会显示记住按钮。
        if not token[3] or token[3] != identity[0] or latest != identity or not xbmc.getCondVisibility('Player.HasVideo'):
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
    # Revision 只在列表渲染内容确实变化时才 bump。每次 RunScript 都是全新
    # 进程，模块级变量存不住上次签名，所以签名必须存在 Home 窗口属性里。
    memory = tuple(home.getProperty(prefix + key) for key in keys)
    if token is not None:
        media = token
    else:
        media = ('live-failed', identity[0], identity[1])
        if playerid is None and xbmc.getCondVisibility('Player.HasVideo'):
            try:
                players = rpc('Player.GetActivePlayers') or []
                video = next((row for row in players if row.get('type') == 'video'), None)
                playerid = video.get('playerid') if isinstance(video, dict) else None
            except (RuntimeError, ValueError, TypeError, KeyError, OSError):
                playerid = None
    tracks, raw_state = _current_track_state(playerid, return_raw=True) if playerid is not None else (None, None)
    signature = _stream_signature(memory, media, tracks)
    if home.getProperty('YoPlayer.Infuse.StreamSignature') != signature:
        home.setProperty('YoPlayer.Infuse.StreamSignature', signature)
        home.setProperty('YoPlayer.Infuse.StreamRevision', str(time.time_ns()))
    if token is not None and isinstance(raw_state, dict):
        try:
            home.setProperty('YoPlayer.Infuse.PlayerStreams.Snapshot', json.dumps({
                'at': time.time(),
                'playerid': playerid,
                'media': {'id': token[2], 'type': token[1], 'file': token[3]},
                'revision': home.getProperty('YoPlayer.Infuse.StreamRevision'),
                'state': raw_state,
            }, ensure_ascii=False))
        except Exception:
            pass


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
