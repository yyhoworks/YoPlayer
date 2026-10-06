"""Branch-owned focus and player helpers; no global keymap is installed."""
import os
import sys
import time
import uuid
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

SKIN_ID = 'skin.yoplayer.infuse'
PREFIX = 'YoPlayer.Infuse.'
ROW_ORDER = (301, 302, 309, 304, 303, 305, 308, 306, 307)
COUNTERS = {301: 9301, 302: 9302, 304: 9304, 303: 9303, 309: 9309, 305: 9305, 308: 9308, 306: 9306, 307: 9307}
OPTIONAL = {301: 'InfuseHideContinue', 302: 'InfuseHideLibraries', 304: 'InfuseHideRecentMovies', 303: 'InfuseHideRecentEpisodes', 309: 'InfuseHidePicks', 305: 'InfuseHideGenres', 308: 'InfuseHideShowGenres', 306: 'InfuseHideSets', 307: 'InfuseHideUnwatched'}


def window():
    return xbmcgui.Window(10000)


def number(label):
    try:
        return int(xbmc.getInfoLabel(label) or 0)
    except ValueError:
        return 0


def available():
    rows = []
    for row in ROW_ORDER:
        if row in OPTIONAL and xbmc.getCondVisibility('Skin.HasSetting({})'.format(OPTIONAL[row])):
            continue
        if row == 302:
            if number('Container(9302).NumItems'):
                rows.append(302)
        elif number('Container({}).NumItems'.format(COUNTERS[row])):
            rows.append(row)
    return rows


def focus_content(first=False):
    rows = available()
    old = window().getProperty(PREFIX + 'FocusRow')
    target = int(old) if old.isdigit() and int(old) in rows and not first else rows[0] if rows else 801
    xbmc.executebuiltin('SetFocus({}{})'.format(target, ',0' if first else ''))


def navigate(row, step):
    rows = available()
    current = 302 if row == 312 else row
    order = [302 if value == 312 else value for value in rows]
    if current not in order:
        focus_content()
        return
    target = order.index(current) + step
    if target < 0:
        xbmc.executebuiltin('SetFocus(801)')
    elif target < len(rows):
        xbmc.executebuiltin('SetFocus({})'.format(rows[target]))


def streams(record=False):
    # Closing a window must never write persistent track preferences.
    if record:
        return
    import epsub
    epsub.update_skin_episode_title()


class Changes(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        from infuse_stream_memory import PlaybackMemory
        from infuse_preplay import PlaybackDefaults
        self.memory = PlaybackDefaults(PlaybackMemory())

    def onNotification(self, sender, method, data):
        if method == 'Player.OnAVStart':
            self.memory.started(data)
        elif method in {'Player.OnPlay', 'Player.OnStop'}:
            self.memory.cancel()
        if method in {'VideoLibrary.OnScanFinished', 'VideoLibrary.OnUpdate', 'VideoLibrary.OnRemove',
                      'Player.OnStop', 'Favourites.OnUpdated'}:
            window().setProperty(PREFIX + 'DataChanged', str(time.monotonic()))


def runtime():
    from infuse_device import publish
    publish()
    from infuse_preferences import initialise
    initialise()
    import_actions()
    from home_settings import migrate_genre_display
    try:migrate_genre_display()
    except (ValueError,RuntimeError,OSError):xbmc.log('YoPlayer genre visibility migration not confirmed',xbmc.LOGWARNING)
    from infuse_rating import DetailRatings
    detail_ratings = DetailRatings()
    home = window()
    home.setProperty(PREFIX + 'RestoreAt', str(time.monotonic()))
    try:
        heartbeat = float(home.getProperty(PREFIX + 'Heartbeat') or 0)
    except ValueError:
        heartbeat = 0
    if time.monotonic() - heartbeat < 2:
        return
    owner = uuid.uuid4().hex
    home.setProperty(PREFIX + 'Owner', owner)
    monitor = Changes()
    last_refresh = 0
    initialised = False
    favourites_file = xbmcvfs.translatePath('special://profile/favourites.xml')
    last_favourites_time = None
    last_favourites_check = 0
    last_capability_check = 0
    from infuse_selection import SelectionPolicy
    policy = SelectionPolicy()
    from infuse_browse import BrowseRouter
    from infuse_series import open_series
    browse_router = BrowseRouter(open_series)
    try:
        policy.acquire()
    except Exception:
        xbmc.log('YoPlayer Infuse: unable to set native detail selection', xbmc.LOGWARNING)
    try:
        while not monitor.abortRequested() and xbmc.getSkinDir() == SKIN_ID and home.getProperty(PREFIX + 'Owner') == owner:
            monitor.memory.poll()
            detail_ratings.poll()
            try:
                browse_router.poll()
            except Exception as exc:
                xbmc.log('Infuse browse routing: ' + str(exc), xbmc.LOGWARNING)
            if time.monotonic() - last_capability_check > 3:
                publish()
                last_capability_check = time.monotonic()
            home.setProperty(PREFIX + 'Heartbeat', str(time.monotonic()))
            if xbmc.getCondVisibility('Window.IsActive(Home)'):
                # Kodi manages the grouplist's actual scroll position. Do not rebuild
                # the window or reset list positions when entering a child window.
                for row in ROW_ORDER:
                    if xbmc.getCondVisibility('Control.HasFocus({})'.format(row)):
                        home.setProperty(PREFIX + 'FocusRow', str(row))
                        if row == 302:
                            home.setProperty(PREFIX + 'LibraryId', xbmc.getInfoLabel('Container(302).ListItem.Property(Infuse.LibraryId)'))
                            home.setProperty(PREFIX + 'LibraryPosition', str(max(0, number('Container(302).CurrentItem')-1)))
                        break
                pending = home.getProperty(PREFIX + 'RestoreAt')
                elapsed = time.monotonic() - float(pending) if pending else 0
                loaded = bool(home.getProperty(PREFIX + 'Count.libraries') or home.getProperty(PREFIX + 'Error.libraries'))
                loaded = loaded and bool(home.getProperty(PREFIX + 'Count.continue') or home.getProperty(PREFIX + 'Error.continue'))
                modal = xbmc.getCondVisibility('System.HasVisibleModalDialog')
                if pending and elapsed > 0.5 and (loaded or elapsed > 4) and not modal:
                    try:
                        if not initialised:
                            xbmc.executebuiltin('Skin.SetBool(FirstTimeRun)')
                            initialised = True
                        focus_content()
                        home.clearProperty(PREFIX + 'RestoreAt')
                    except Exception as exc:
                        xbmc.log('YoPlayer Infuse focus: {}'.format(type(exc).__name__), xbmc.LOGWARNING)
                        home.clearProperty(PREFIX + 'RestoreAt')
                if time.monotonic() - last_favourites_check > 3:
                    try:
                        current = os.stat(favourites_file).st_mtime_ns
                    except OSError:
                        current = 0
                    if last_favourites_time is not None and current != last_favourites_time:
                        home.setProperty(PREFIX + 'DataChanged', str(time.monotonic()))
                    last_favourites_time = current
                    last_favourites_check = time.monotonic()
                refresh_pending = home.getProperty(PREFIX + 'RefreshPending')
                ready = home.getProperty(PREFIX + 'Loaded.libraries') == home.getProperty(PREFIX + 'Revision')
                if refresh_pending and time.monotonic() - float(refresh_pending) > 0.5 and ready and not modal:
                    if xbmc.getCondVisibility('Control.HasFocus(302)'):
                        try:
                            import_actions()
                            from provider import get_libraries
                            libraries = get_libraries()
                            key = home.getProperty(PREFIX + 'RestoreLibraryId')
                            index = next((i for i, item in enumerate(libraries) if item['id'] == key),
                                         min(int(home.getProperty(PREFIX + 'RestoreLibraryPosition') or 0), max(0, len(libraries)-1)))
                            xbmc.executebuiltin('SetFocus(302,{})'.format(index)) if libraries else focus_content()
                        except Exception:
                            pass
                    home.clearProperty(PREFIX + 'RefreshPending')
                changed = home.getProperty(PREFIX + 'DataChanged')
                if changed and time.monotonic() - float(changed) > 0.8 and time.monotonic() - last_refresh > 2:
                    try:
                        import_actions().refresh()
                        home.clearProperty(PREFIX + 'DataChanged')
                        last_refresh = time.monotonic()
                    except Exception:
                        home.clearProperty(PREFIX + 'DataChanged')
            if monitor.waitForAbort(0.25):
                break
    finally:
        if home.getProperty(PREFIX + 'Owner') == owner:
            try:
                policy.release()
            except Exception:
                xbmc.log('YoPlayer Infuse: unable to restore native selection', xbmc.LOGWARNING)
    if home.getProperty(PREFIX + 'Owner') == owner:
        home.clearProperty(PREFIX + 'Owner')
        home.clearProperty(PREFIX + 'Heartbeat')


def import_actions():
    addon = xbmcaddon.Addon('plugin.video.yoplayer.home')
    lib = os.path.join(xbmcvfs.translatePath(addon.getAddonInfo('path')), 'resources', 'lib')
    if lib not in sys.path:
        sys.path.insert(0, lib)
    import actions
    return actions


def main():
    if xbmc.getSkinDir() != SKIN_ID:
        return
    action = sys.argv[1] if len(sys.argv) > 1 else 'startup'
    if action == 'startup':
        runtime()
    elif action in {'focus-content', 'home-top'}:
        focus_content(first=action == 'home-top')
    elif action == 'navigate' and len(sys.argv) > 3:
        navigate(int(sys.argv[2]), int(sys.argv[3]))
    elif action in {'record-streams', 'apply-streams'}:
        streams(record=action == 'record-streams')
    elif action == 'open-library' and len(sys.argv) > 2:
        actions = import_actions()
        key = sys.argv[2]
        library = next((row for row in actions.get_libraries() if row['id'] == key), None)
        if library is not None:
            actions.activate(library['path'])
        else:
            xbmcgui.Dialog().notification('媒体分库', '分库已变化，请重新选择')
    elif action == 'browse-seasons' and len(sys.argv) > 2:
        showid = int(sys.argv[2])
        window().setProperty(PREFIX + 'BrowseShow', str(showid))
        xbmc.executebuiltin('Dialog.Close(2003)')
        xbmc.executebuiltin('ActivateWindow(Videos,videodb://tvshows/titles/{}/,return)'.format(showid))
    elif action == 'browse-options-back':
        from infuse_browse import options_back
        options_back()
    elif action == 'browse-options-enter' and len(sys.argv) > 2:
        from infuse_browse import options_enter
        options_enter(sys.argv[2])
    elif action in {'settings', 'search-menu', 'power-menu'}:
        from infuse_home_menu import run
        run(action)
    elif action == 'home-settings':
        import_actions()
        from home_settings import home_layout
        home_layout()
    else:
        argument = sys.argv[2] if len(sys.argv) > 2 else ''
        if action == 'library' and not argument:
            argument = window().getProperty(PREFIX + 'LibraryId')
        try:
            import_actions().dispatch(action, argument)
        except Exception as exc:
            xbmc.log('YoPlayer Infuse helper: {}'.format(type(exc).__name__), xbmc.LOGWARNING)
            xbmcgui.Dialog().ok('首页数据插件不可用', '请先安装并启用随皮肤提供的 YoPlayer 首页数据插件。')


if __name__ == '__main__':
    main()
