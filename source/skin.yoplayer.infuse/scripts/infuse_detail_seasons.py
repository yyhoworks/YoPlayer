"""Inline season tabs for native video information. Read-only library browsing.

The native episode container retains its playback/context actions. This controller
only changes its directory and restores each season's selected episode.
"""
import json
import sys
import uuid
from urllib.parse import urlencode
import xbmc
import xbmcgui

PREFIX = 'YoPlayer.DetailSeasons.'
WINDOW = 12003


def rpc(method, params):
    result = json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params})))
    if 'error' in result:
        raise RuntimeError('无法读取剧集资料')
    return result.get('result', {})


def season_numbers(rows):
    return sorted({int(row['season']) for row in rows if int(row.get('season', -1)) >= 0})


def choose_episode(episodes, remembered=None):
    ids = {row['episodeid'] for row in episodes}
    if remembered in ids:
        return remembered
    resumed = [row for row in episodes if (row.get('resume') or {}).get('position', 0) > 0]
    if resumed:
        return max(resumed, key=lambda row: row.get('lastplayed') or '')['episodeid']
    return next((row['episodeid'] for row in episodes if not row.get('playcount')),
                episodes[0]['episodeid'] if episodes else None)


def play_label(episode):
    action = '继续' if (episode.get('resume') or {}).get('position', 0) > 0 else '播放'
    return '{} S{} · E{}'.format(action, episode['season'], episode['episode'])


def restore_initial_focus(win, identity, owner):
    """Recover an empty initial focus after async play-button enablement.

    Never redirect an existing focus or a replacement detail instance. Call
    only once the previous frame already exposed the verified episode state.
    """
    if (win.getProperty(PREFIX + 'Identity') != identity
            or win.getProperty(PREFIX + 'Owner') != owner
            or not xbmc.getCondVisibility('Window.IsActive(movieinformation)')
            or win.getProperty(PREFIX + 'EpisodeReady') != 'true'
            or win.getProperty(PREFIX + 'Request')):
        return True
    try:
        focused = win.getFocusId()
    except RuntimeError:
        focused = 0
    if type(focused) is not int or focused > 0:
        return False
    target = 9004 if xbmc.getCondVisibility('ListItem.IsResumable') else 9001
    try:
        win.setFocusId(target)
    except RuntimeError:
        pass
    # Sending a focus message is not proof a slow GUI frame accepted it.
    # Confirm on the next controller tick, without disturbing a valid focus.
    return True


def start(showid, initial='', media_type='tvshow', identity=''):
    showid = int(showid)
    source_episode = showid if media_type == 'episode' else None
    if showid <= 0:
        return
    win = xbmcgui.Window(WINDOW)
    # A queued RunScript from an earlier detail window must not take ownership
    # after another media item has opened, even before any RPC has begun.
    if not identity or win.getProperty(PREFIX + 'Identity') != identity:
        return
    monitor = xbmc.Monitor()
    token = uuid.uuid4().hex
    win.setProperty(PREFIX + 'Owner', token)
    win.clearProperty(PREFIX + 'Request')
    win.clearProperty(PREFIX + 'Ready')
    win.clearProperty(PREFIX + 'Path')
    for key in ('ShowID', 'EpisodeReady', 'EpisodeID', 'PlayLabel', 'WatchedUpdate'):
        win.clearProperty(PREFIX + key)
    try:
        if media_type == 'episode':
            # Home/plugin items may not supply Kodi's native TVShowDBID label.
            # Resolve the selected episode's actual parent instead of reusing
            # another detail window's episode directory or list metadata.
            details = rpc('VideoLibrary.GetEpisodeDetails', {'episodeid': showid,
                          'properties': ['tvshowid', 'season']}).get('episodedetails', {})
            showid = int(details.get('tvshowid') or 0)
            initial = str(details.get('season', ''))
            if showid <= 0:
                return
        if win.getProperty(PREFIX + 'Owner') != token or win.getProperty(PREFIX + 'Identity') != identity:
            return
        win.setProperty(PREFIX + 'ShowID', str(showid))
        fallback_season = initial if initial.isdigit() else '-1'
        win.setProperty('infuse_detail_episodepath', 'videodb://tvshows/titles/{}/{}/'.format(showid, fallback_season))
        rows = rpc('VideoLibrary.GetSeasons', {'tvshowid': showid, 'properties': ['season', 'episode']}).get('seasons', [])
        numbers = season_numbers(rows)
        if not numbers:
            return
        episodes = rpc('VideoLibrary.GetEpisodes', {'tvshowid': showid,
            'properties': ['season', 'episode', 'playcount', 'resume', 'lastplayed', 'file']}).get('episodes', [])
        episodes.sort(key=lambda row: (row['season'], row['episode'], row['episodeid']))
        cache_key = PREFIX + str(showid)
        home = xbmcgui.Window(10000)
        try:
            cache = json.loads(home.getProperty(cache_key) or '{}')
        except ValueError:
            cache = {}
        remembered = cache.get('selected', {})
        preferred = choose_episode(episodes)
        preferred_season = next((e['season'] for e in episodes if e['episodeid'] == preferred), numbers[0])
        current = int(initial) if initial.lstrip('-').isdigit() and int(initial) in numbers else cache.get('season', preferred_season)
        if current not in numbers and current != -1:
            current = preferred_season
        # Native controls can become available just after the window's onload.
        for _ in range(30):
            try:
                tabs = win.getControl(9061)
                native = win.getControl(9060)
                break
            except RuntimeError:
                if monitor.waitForAbort(.1): return
        else:
            return
        if win.getProperty(PREFIX + 'Owner') != token or win.getProperty(PREFIX + 'Identity') != identity or not xbmc.getCondVisibility('Window.IsVisible(movieinformation)'):
            return
        choices = numbers + [-1]
        # Kodi only dispatches a native list's XML onclick when it has a list
        # provider. Let the directory own its items; never reset/addItems here.
        win.setProperty(PREFIX + 'Path', 'plugin://plugin.video.yoplayer.home/?' +
                        urlencode({'route': 'detail-seasons', 'q': showid, 'revision': token}))
        tabs_ready = False
        tab_waiting = 0
        pending = None
        waiting = 0
        initial_focus_pending = True
        initial_focus_attempts = 0

        def switch(number):
            for key in ('EpisodeReady', 'EpisodeID', 'PlayLabel'):
                win.clearProperty(PREFIX + key)
            subset = [e for e in episodes if number == -1 or e['season'] == number]
            win.setProperty(PREFIX + 'Current', str(number))
            win.setProperty('infuse_detail_episodepath', 'videodb://tvshows/titles/{}/{}/'.format(showid, number))
            return choose_episode(subset, remembered.get(str(number)))

        pending = switch(current)
        if source_episode is not None:
            # Direct episode entry must never silently select a cached sibling.
            pending = source_episode
        # Native dynamic content refresh is async. Match DBID, never guess position.
        while not monitor.abortRequested() and xbmc.getCondVisibility('Window.IsVisible(movieinformation)') and win.getProperty(PREFIX + 'Owner') == token and win.getProperty(PREFIX + 'Identity') == identity:
            update = win.getProperty(PREFIX+'WatchedUpdate')
            if update:
                win.clearProperty(PREFIX+'WatchedUpdate')
                try:
                    update = json.loads(update)
                    row = next((e for e in episodes if e['episodeid'] == update.get('episodeid')
                                and e['season'] == update.get('season')), None)
                    if row and update.get('owner') == token and update.get('tvshowid') == showid:
                        row['playcount'] = update['playcount']
                        row['lastplayed'] = update.get('lastplayed', '')
                        selected = xbmc.getInfoLabel('Container(9060).ListItem.DBID')
                        if not selected and (current == -1 or row['season'] == current):
                            pending = row['episodeid']
                            waiting = 0
                except (ValueError, TypeError, KeyError):
                    pass
            if initial_focus_pending and initial_focus_attempts < 20:
                initial_focus_pending = restore_initial_focus(win, identity, token)
                if win.getProperty(PREFIX + 'EpisodeReady') == 'true':
                    initial_focus_attempts += 1
            if not tabs_ready and tab_waiting < 100:
                tab_waiting += 1
                try:
                    count = int(xbmc.getInfoLabel('Container(9061).NumItems') or 0)
                    loaded = [(xbmc.getInfoLabel('Container(9061).ListItemAbsolute({}).Property(season)'.format(i)),
                               xbmc.getInfoLabel('Container(9061).ListItemAbsolute({}).Property(revision)'.format(i)))
                              for i in range(count)]
                    if loaded == [(str(n), token) for n in choices]:
                        tabs.selectItem(choices.index(current))
                        tabs_ready = True
                        win.setProperty(PREFIX + 'Ready', 'true')
                    elif tab_waiting >= 100:
                        # Failed provider: preserve native episode navigation.
                        win.clearProperty(PREFIX + 'Path')
                except (RuntimeError, ValueError):
                    pass
            request = win.getProperty(PREFIX + 'Request')
            if request:
                # Do not expose a ready old episode between dequeuing a season
                # request and updating the native directory.
                for key in ('EpisodeReady', 'EpisodeID', 'PlayLabel'):
                    win.clearProperty(PREFIX + key)
                win.clearProperty(PREFIX + 'Request')
                try:
                    request = json.loads(request)
                except ValueError:
                    request = {}
                if tabs_ready and request.get('owner') == token and request.get('season') in choices:
                    current = request['season']
                    tabs.selectItem(choices.index(current))
                    pending = switch(current)
                    waiting = 0
            if pending is not None and waiting < 60:
                waiting += 1
                try:
                    count = int(xbmc.getInfoLabel('Container(9060).NumItems') or 0)
                    expected = sum(current == -1 or e['season'] == current for e in episodes)
                    for index in range(count if count == expected else 0):
                        value = xbmc.getInfoLabel('Container(9060).ListItemAbsolute({}).DBID'.format(index))
                        if value == str(pending):
                            if xbmc.getInfoLabel('Container(9060).ListItem.DBID') == str(pending):
                                pending = None
                            else:
                                native.selectItem(index)
                            break
                except (RuntimeError, ValueError):
                    pass
            if pending is None and xbmc.getCondVisibility('Window.IsActive(movieinformation)'):
                selected = xbmc.getInfoLabel('Container(9060).ListItem.DBID')
                row = next((e for e in episodes if str(e['episodeid']) == selected and (current == -1 or e['season'] == current)), None)
                if row and not win.getProperty(PREFIX + 'Request'):
                    if win.getProperty(PREFIX + 'EpisodeID') != selected:
                        win.clearProperty(PREFIX + 'EpisodeReady')
                        if row.get('file'):
                            from infuse_preplay import labels
                            labels('episode',int(selected),row['file'],win)
                    win.setProperty(PREFIX + 'EpisodeID', selected)
                    win.setProperty(PREFIX + 'PlayLabel', play_label(row))
                    win.setProperty(PREFIX + 'EpisodeReady', 'true')
                    remembered[str(current)] = int(selected)
                    home.setProperty(cache_key, json.dumps({'season': current, 'selected': remembered}))
                else:
                    for key in ('EpisodeReady', 'EpisodeID', 'PlayLabel'):
                        win.clearProperty(PREFIX + key)
            if monitor.waitForAbort(.1):
                break
    except Exception as exc:
        xbmc.log('YoPlayer inline seasons: ' + str(exc), xbmc.LOGWARNING)
        # Keep the native episode list usable when metadata is unavailable.
    finally:
        if win.getProperty(PREFIX + 'Owner') == token:
            for key in ('Owner', 'Ready', 'Request', 'Current', 'Path', 'ShowID', 'EpisodeReady', 'EpisodeID', 'PlayLabel'):
                win.clearProperty(PREFIX + key)


def main():
    if xbmc.getSkinDir() != 'skin.yoplayer.infuse':
        return
    command = sys.argv[1] if len(sys.argv) > 1 else ''
    if command == 'start' and len(sys.argv) > 4:
        start(sys.argv[2], sys.argv[3], identity=sys.argv[4])
    elif command == 'start-episode' and len(sys.argv) > 3:
        start(sys.argv[2], media_type='episode', identity=sys.argv[3])
    elif command == 'switch' and len(sys.argv) > 3:
        value = sys.argv[2]
        owner = sys.argv[3]
        win = xbmcgui.Window(WINDOW)
        if value.lstrip('-').isdigit() and owner and win.getProperty(PREFIX + 'Owner') == owner and win.getProperty(PREFIX + 'Ready') == 'true':
            win.setProperty(PREFIX + 'Request', json.dumps({'owner': owner, 'season': int(value)}))


if __name__ == '__main__':
    main()
