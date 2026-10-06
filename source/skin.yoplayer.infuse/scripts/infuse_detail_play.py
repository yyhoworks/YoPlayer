"""Play only the verified episode selected in the native detail container."""
from contextlib import contextmanager
import json
import os
import sys
import uuid
import xbmc
import xbmcgui
import xbmcvfs

PREFIX = 'YoPlayer.DetailSeasons.'
BUSY = 'YoPlayer.DetailPlay.Busy'
CLOSING = 'YoPlayer.DetailPlay.Closing'
LOCAL_CLOSING = 'YoPlayer.DetailPlay.ClosingToken'


def rpc(method, params):
    result = json.loads(xbmc.executeJSONRPC(json.dumps({
        'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params})))
    if 'error' in result:
        raise RuntimeError('Episode state unavailable')
    return result.get('result', {})


@contextmanager
def exclusive():
    """OS lock closes the get/set-property race, and releases after a crash.

    Keep the lock file: deleting it would let another process lock a new inode.
    It contains no media data and lives only in Kodi's temporary directory.
    """
    handle = open(xbmcvfs.translatePath('special://temp/yoplayer-detail-play.lock'), 'a+b')
    locked = False
    try:
        try:
            if os.name == 'nt':
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError:
            pass
        yield locked
    finally:
        if locked:
            if os.name == 'nt':
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


class Session(xbmc.Monitor):
    changed = False

    def onNotification(self, sender, method, data):
        if method in ('Player.OnStop', 'Player.OnAVStart', 'Player.OnPlay'):
            self.changed = True


def selected_context(win, identity, owner, season, episodeid):
    return (xbmc.getSkinDir() == 'skin.yoplayer.infuse'
            and xbmc.getCondVisibility('Window.IsActive(movieinformation)')
            and identity and owner
            and win.getProperty(PREFIX+'Identity') == identity
            and win.getProperty(PREFIX+'Owner') == owner
            and win.getProperty(PREFIX+'Current') == str(season)
            and win.getProperty(PREFIX+'EpisodeReady') == 'true'
            and win.getProperty(PREFIX+'EpisodeID') == str(episodeid)
            and xbmc.getInfoLabel('Container(9060).ListItem.DBID') == str(episodeid)
            and not win.getProperty(PREFIX+'Request'))


def details(episodeid, showid, season):
    row = rpc('VideoLibrary.GetEpisodeDetails', {'episodeid': episodeid,
              'properties': ['tvshowid', 'season', 'episode', 'file', 'resume']}).get('episodedetails', {})
    if (row.get('episodeid') != episodeid or row.get('tvshowid') != showid
            or not row.get('file') or (season != -1 and row.get('season') != season)):
        raise ValueError('Episode identity changed')
    return row


def time_label(seconds):
    seconds = max(0, int(seconds))
    return '{}:{:02d}:{:02d}'.format(seconds//3600, seconds//60%60, seconds%60)


def restore_cancel_focus(win, home, session, token, identity, owner, season, episodeid, target):
    """Wait for this cancelled resume menu to return; never steal valid focus."""
    if target not in (9001, 9004, 9060):
        return
    for _ in range(40):
        if (session.changed or session.abortRequested()
                or home.getProperty(BUSY) != token
                or xbmc.getSkinDir() != 'skin.yoplayer.infuse'
                or win.getProperty(PREFIX+'Identity') != identity
                or win.getProperty(PREFIX+'Owner') != owner
                or win.getProperty(PREFIX+'Current') != str(season)
                or win.getProperty(PREFIX+'EpisodeID') not in ('', str(episodeid))
                or win.getProperty(PREFIX+'Request')
                or not xbmc.getCondVisibility('Window.IsVisible(movieinformation)')):
            return
        if xbmcgui.getCurrentWindowDialogId() == 12003 and xbmc.getCondVisibility('Window.IsActive(movieinformation)'):
            selected = xbmc.getInfoLabel('Container(9060).ListItem.DBID')
            if selected not in ('', str(episodeid)):
                return
            # Kodi can retain a group's last focus ID while its actual focused
            # control chain is empty after the resume menu closes.
            focused = xbmc.getInfoLabel('System.CurrentControlID')
            if focused and (not focused.isdigit() or int(focused) > 0):
                return
            if (win.getProperty(PREFIX+'EpisodeReady') == 'true'
                    and win.getProperty(PREFIX+'EpisodeID') == str(episodeid)
                    and selected == str(episodeid)):
                try:
                    win.setFocusId(target)
                except RuntimeError:
                    pass
        if session.waitForAbort(.1):
            return


def play(identity, owner, season, episodeid):
    season, episodeid = int(season), int(episodeid)
    if episodeid <= 0 or season < -1:
        return
    win, home = xbmcgui.Window(12003), xbmcgui.Window(10000)
    with exclusive() as acquired:
        if not acquired:
            return
        # Holding the OS lock proves any old Busy value has no live owner.
        token = uuid.uuid4().hex
        home.setProperty(BUSY, token)
        try:
            session = Session()
            valid = lambda: (not session.changed and not session.abortRequested()
                             and home.getProperty(BUSY) == token
                             and selected_context(win, identity, owner, season, episodeid))
            if not valid(): return
            showid = int(win.getProperty(PREFIX+'ShowID') or 0)
            if showid <= 0: return
            row = details(episodeid, showid, season)
            if not valid() or win.getProperty(PREFIX+'ShowID') != str(showid): return
            resume = False
            position = (row.get('resume') or {}).get('position', 0)
            if position > 0:
                try:
                    return_focus = win.getFocusId()
                except RuntimeError:
                    return_focus = 0
                choice = xbmcgui.Dialog().contextmenu([
                    '从 {} 继续'.format(time_label(position)), '从头播放'])
                if choice not in (0, 1):
                    restore_cancel_focus(win, home, session, token, identity, owner, season, episodeid, return_focus)
                    return
                resume = choice == 0
            if not valid() or win.getProperty(PREFIX+'ShowID') != str(showid): return
            refreshed = details(episodeid, showid, season)
            if any(refreshed.get(key) != row.get(key) for key in ('file', 'season', 'episode')):
                return
            if not valid() or win.getProperty(PREFIX+'ShowID') != str(showid): return
            # Suppress only this detail instance's trailer-stop unload action.
            home.setProperty(CLOSING, token)
            win.setProperty(LOCAL_CLOSING, token)
            if not valid(): return
            xbmc.executebuiltin('Dialog.Close(movieinformation,true)', True)

            def closed_valid():
                return (not session.changed and not session.abortRequested()
                        and xbmc.getSkinDir() == 'skin.yoplayer.infuse'
                        and home.getProperty(BUSY) == token
                        and home.getProperty(CLOSING) == token
                        and win.getProperty(LOCAL_CLOSING) == token
                        and not win.getProperty(PREFIX+'Identity')
                        and not win.getProperty(PREFIX+'Owner')
                        and not xbmc.getCondVisibility('Window.IsVisible(movieinformation)'))

            for _ in range(40):
                if win.getProperty(LOCAL_CLOSING) != token or session.changed:
                    return
                if closed_valid(): break
                if session.waitForAbort(.05): return
            else:
                return
            # A post-close RPC plus repeated instance checks rejects a replaced
            # detail or library item during the asynchronous close boundary.
            current = details(episodeid, showid, season)
            if any(current.get(key) != row.get(key) for key in ('file', 'season', 'episode')):
                return
            if not closed_valid(): return
            rpc('Player.Open', {'item': {'episodeid': episodeid}, 'options': {'resume': resume}})
        finally:
            if win.getProperty(LOCAL_CLOSING) == token:
                win.clearProperty(LOCAL_CLOSING)
            for key in (CLOSING, BUSY):
                if home.getProperty(key) == token: home.clearProperty(key)


def main():
    if len(sys.argv) != 5 or xbmc.getSkinDir() != 'skin.yoplayer.infuse':
        return
    try:
        play(*sys.argv[1:])
    except (OSError, RuntimeError, ValueError, TypeError, KeyError):
        # Never log media URLs; they can contain server credentials.
        xbmc.log('YoPlayer: selected episode playback cancelled; context unavailable', xbmc.LOGWARNING)


if __name__ == '__main__':
    main()
