"""P1 playback panels: query live Kodi streams and dispatch explicit actions."""
import json
import sys
import xbmc
import xbmcgui

WINDOW_ID = 11196
PANELS = {'subtitles': '字幕', 'audio': '音轨', 'picture': '画面与 VS10', 'more': '更多操作'}
PREFIX = 'YoPlayer.Infuse.P1.'
PROPERTIES = ['subtitles', 'currentsubtitle', 'subtitleenabled', 'audiostreams', 'currentaudiostream', 'time', 'totaltime']
NATIVE = {
    'subtitle-delay': 'Action(SubtitleDelay)', 'audio-delay': 'Action(AudioDelay)',
    'gain': 'Action(VolAmp)', 'passthrough': 'ActivateWindow(OSDAudioSettings)',
    'download': 'ActivateWindow(SubtitleSearch)', 'video-settings': 'ActivateWindow(OSDVideoSettings)',
    'audio-settings': 'ActivateWindow(OSDAudioSettings)', 'subtitle-settings': 'ActivateWindow(OSDSubtitleSettings)',
    'zoom': 'Action(ZoomNormal)', 'info': 'ActivateWindow(PlayerProcessInfo)',
    'bookmarks': 'ActivateWindow(VideoBookmarks)', 'playlist': 'ActivateWindow(VideoPlaylist)',
    'intro-outro': 'RunScript(special://skin/scripts/tvjump.py,record)',
    'channels': 'ActivateWindow(PVROSDChannels)', 'guide': 'ActivateWindow(PVRChannelGuide)',
    'record': 'PVR.ToggleRecordPlayingChannel', 'disc-menu': 'PlayerControl(ShowVideoMenu)',
    'debug': 'PlayerDebug', 'previous': 'RunScript(special://skin/scripts/nextitem.py,Previous)',
    'next': 'RunScript(special://skin/scripts/nextitem.py,next)',
}


def rpc(method, params=None):
    response = json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}})))
    if 'error' in response:
        raise RuntimeError(response['error'].get('message', 'Kodi RPC failed'))
    return response.get('result')


def player_state():
    players = rpc('Player.GetActivePlayers')
    player = next((item for item in players if item.get('type') == 'video'), None)
    if player is None:
        raise RuntimeError('当前没有正在播放的视频')
    return player['playerid'], rpc('Player.GetProperties', {'playerid': player['playerid'], 'properties': PROPERTIES})


def language(value):
    return {'chi': '中文', 'zho': '中文', 'eng': 'English', 'jpn': '日本語', 'kor': '한국어'}.get(value, value if value and value != 'und' else '未标注语言')


def row(title, action='none', argument='', detail='', selected=False, enabled=True):
    return dict(title=title, action=action, argument=str(argument), detail=detail, selected=selected, enabled=enabled)


def rows(panel, state, vs10=False):
    if panel == 'subtitles':
        result = [row(track.get('name') or language(track.get('language')), 'subtitle', track.get('index', index),
                      track.get('codec', ''), state.get('subtitleenabled') and track.get('index', index) == state.get('currentsubtitle', {}).get('index'))
                  for index, track in enumerate(state.get('subtitles', []))]
        if not result:
            result.append(row('当前没有可用字幕轨道', detail='可以浏览本地字幕或下载字幕', enabled=False))
        result += [row('关闭字幕', 'subtitle-off', selected=not state.get('subtitleenabled')),
                   row('字幕延迟', 'subtitle-delay'), row('浏览本地字幕', 'browse'), row('下载字幕', 'download'),
                   row('记住当前选择', 'remember-subtitle', detail='用于本季或同一剧集目录；仅点击后保存'), row('字幕设置', 'subtitle-settings'),
                   row('完整轨道信息', 'track-info')]
        return result
    if panel == 'audio':
        result = [row(track.get('name') or language(track.get('language')), 'audio', track.get('index', index),
                      '{} · {} 声道'.format(track.get('codec', '').upper(), track.get('channels', '?')),
                      track.get('index', index) == state.get('currentaudiostream', {}).get('index'))
                  for index, track in enumerate(state.get('audiostreams', []))]
        if not result:
            result.append(row('当前没有可用音轨', enabled=False))
        result += [row('音频延迟', 'audio-delay'), row('音量增益', 'gain'),
                   row('允许直通输出', 'passthrough', detail='由原生音频设置管理'),
                   row('记住当前选择', 'remember-audio', detail='用于本季或同一剧集目录；仅点击后保存'), row('音频设置', 'audio-settings'),
                   row('完整轨道信息', 'track-info')]
        return result
    if panel == 'picture':
        return [row(title, 'vs10', mode, detail='' if vs10 else '当前设备未提供 VS10 能力', enabled=vs10)
                for title, mode in [('影片源格式', 'original'), ('SDR', 'sdr'), ('HDR10', 'hdr10'), ('Dolby Vision', 'dv')]] + [
                    row('画面比例与缩放', 'video-settings'), row('视频设置', 'video-settings')]
    return [row(title, action, argument) for title, action, argument in [
        ('选集、章节与书签', 'chapters', ''), ('VS10 画面转换', 'panel', 'picture'), ('播放信息', 'info', ''),
        ('视频设置', 'video-settings', ''), ('音频设置', 'panel', 'audio'), ('字幕设置', 'panel', 'subtitles'),
        ('播放列表', 'playlist', ''), ('片头／片尾记录', 'intro-outro', ''), ('上一项', 'previous', ''), ('下一项', 'next', ''),
        ('快退', 'rewind', ''), ('快进', 'forward', ''), ('调试信息', 'debug', '')]]


def vs10_available():
    mode = xbmc.getInfoLabel('Player.Process(amlogic.vs10.mode)').strip().lower()
    return mode not in {'', 'unknown', 'n/a', 'unsupported'} and xbmc.getInfoLabel('Player.Process(video.source.hdr.type.raw)').strip() != '2'


def panel_window():
    return xbmcgui.Window(WINDOW_ID)


def populate(focus=None):
    window = panel_window()
    panel = xbmcgui.Window(10000).getProperty(PREFIX + 'Panel') or 'subtitles'
    window.setProperty(PREFIX + 'Title', PANELS[panel])
    import time
    # A dynamic content provider owns the items so Kodi dispatches XML onclick.
    # Python addItems on a static custom window does not create that provider.
    revision = str(time.time_ns())
    home = xbmcgui.Window(10000)
    home.setProperty(PREFIX+'Revision', revision)
    # Wait for this provider revision rather than selecting an old list index.
    monitor = xbmc.Monitor()
    for _ in range(20):
        if home.getProperty(PREFIX+'Revision') != revision or not xbmc.getCondVisibility('Window.IsVisible(1196)'):
            return
        try:
            listing = window.getControl(500)
            items = [listing.getListItem(i) for i in range(listing.size())]
            if items and all(i.getProperty('revision') == revision for i in items):
                position = next((i for i, item in enumerate(items) if focus and
                    (item.getProperty('action'), item.getProperty('argument')) == focus), None)
                if position is None:
                    position = next((i for i, item in enumerate(items) if item.getProperty('selected') == 'true'), 0)
                current_focus = window.getFocusId()
                if current_focus == 500 or (focus is None and current_focus in (11, 12, 13)):
                    xbmc.executebuiltin('SetFocus(500,{})'.format(position))
                return
        except (RuntimeError, IndexError):
            pass
        if monitor.waitForAbort(0.1):
            return


def panel_entries():
    panel=xbmcgui.Window(10000).getProperty(PREFIX+'Panel') or 'subtitles'
    try:
        _, state = player_state()
        entries = rows(panel, state, vs10_available())
        if panel == 'more' and xbmc.getCondVisibility('VideoPlayer.Content(LiveTV)'):
            entries += [row('频道列表', 'channels'), row('节目指南', 'guide')]
            if xbmc.getCondVisibility('PVR.CanRecordPlayingChannel'):
                entries.append(row('录制当前频道', 'record'))
        if panel == 'more' and xbmc.getCondVisibility('VideoPlayer.HasMenu'):
            entries.append(row('光盘菜单', 'disc-menu'))
    except Exception as exc:
        entries = [row('播放数据暂不可用', detail=str(exc), enabled=False)]
    return entries


def open_panel(panel):
    if panel not in PANELS:
        return
    xbmcgui.Window(10000).setProperty(PREFIX + 'Panel', panel)
    windows = {'subtitles': 1144, 'audio': 1145, 'picture': 1141, 'more': 1114}
    if panel == 'more':
        xbmc.executebuiltin('SetProperty(optionsdialog_content,options,home)')
        xbmc.executebuiltin('SetProperty(optionsdialog_header,更多播放设置,home)')
    xbmc.executebuiltin('ActivateWindow({})'.format(windows[panel]))


def execute(action, argument=''):
    if action == 'none':
        return
    if action == 'panel':
        open_panel(argument)
        return
    playerid, state = player_state()
    if action in {'subtitle', 'audio'}:
        index = int(argument)
        tracks = state.get('subtitles' if action == 'subtitle' else 'audiostreams', [])
        if index not in [track.get('index', position) for position, track in enumerate(tracks)]:
            raise RuntimeError('该轨道已变化，请重新选择')
        params = {'playerid': playerid, 'subtitle' if action == 'subtitle' else 'stream': index}
        if action == 'subtitle':
            params['enable'] = True
        rpc('Player.SetSubtitle' if action == 'subtitle' else 'Player.SetAudioStream', params)
    elif action == 'subtitle-off':
        rpc('Player.SetSubtitle', {'playerid': playerid, 'subtitle': 'off'})
    elif action == 'vs10':
        if argument not in {'original', 'sdr', 'hdr10', 'dv'} or not vs10_available():
            raise RuntimeError('当前设备未提供可用的 VS10 转换')
        xbmc.executebuiltin('Action(vs10.{})'.format(argument))
    elif action in {'rewind', 'forward'}:
        xbmc.executebuiltin('PlayerControl({})'.format('Rewind' if action == 'rewind' else 'Forward'))
    elif action == 'browse':
        path = xbmcgui.Dialog().browse(1, '浏览本地字幕', 'files', '.srt|.ass|.ssa|.sub|.vtt')
        if path:
            xbmc.Player().setSubtitles(path)
    elif action.startswith('remember-'):
        from infuse_stream_memory import save
        try:
            scope = save('subtitle' if action == 'remember-subtitle' else 'audio')
        except (OSError, ValueError) as exc:
            xbmc.log('Infuse track preference write failed: {}'.format(exc), xbmc.LOGWARNING)
            raise RuntimeError('轨道选择未保存，请检查存储权限后重试') from exc
        xbmcgui.Dialog().notification('轨道选择已保存', '作用范围：' + scope)
    elif action == 'track-info':
        panel = xbmcgui.Window(10000).getProperty(PREFIX + 'Panel') or 'subtitles'
        tracks = state.get('audiostreams' if panel == 'audio' else 'subtitles', [])
        text = '\n\n'.join('{} · {}\n语言：{} · 编码：{} · 声道：{}'.format(track.get('index', i),
            track.get('name') or language(track.get('language')), language(track.get('language')),
            track.get('codec') or '未提供', track.get('channels', '未提供'))
            for i, track in enumerate(tracks))
        xbmcgui.Dialog().textviewer('完整轨道信息', text or '当前没有可用轨道。')
        return
    elif action == 'chapters':
        xbmc.executebuiltin('Dialog.Close(1196)')
        xbmc.executebuiltin('RunScript(special://skin/scripts/infuse.py,chapters)')
        return
    elif action in {'previous', 'next'}:
        episode = xbmc.getCondVisibility('VideoPlayer.Content(Episodes) | !String.IsEmpty(Skin.String(episodetitle))')
        xbmc.executebuiltin(NATIVE[action] if episode else 'PlayerControl({})'.format('Previous' if action == 'previous' else 'Next'))
    elif action in NATIVE:
        # Hide this modal before opening another native modal; keep VideoOSD alive.
        xbmc.executebuiltin('Dialog.Close(1196)')
        xbmc.executebuiltin(NATIVE[action])
        return
    if xbmc.getCondVisibility('Window.IsVisible(1196)'):
        populate(focus=(action, str(argument)))


def main():
    if xbmc.getSkinDir() != 'skin.yoplayer.infuse':
        return
    command = sys.argv[1] if len(sys.argv) > 1 else 'populate'
    try:
        if command == 'open':
            open_panel(sys.argv[2])
        elif command == 'select':
            item = panel_window().getControl(500).getSelectedItem()
            if item and item.getProperty('enabled') != 'false':
                execute(item.getProperty('action'), item.getProperty('argument'))
        elif command == 'populate':
            populate()
        else:
            execute(command)
    except Exception as exc:
        xbmc.log('YoPlayer P1 playback: {}'.format(exc), xbmc.LOGWARNING)
        xbmcgui.Dialog().notification('播放控制', str(exc), xbmcgui.NOTIFICATION_WARNING)


if __name__ == '__main__':
    main()
