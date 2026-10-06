"""Confirm the native clear-all command without changing Kodi's bookmark logic."""
import sys
import xbmc
import xbmcgui

# xbmc/guilib/WindowIDs.h, Kodi Omega: WINDOW_DIALOG_VIDEO_BOOKMARKS.
BOOKMARK_WINDOW = 10125


def context():
    path = xbmc.getInfoLabel('Player.Filenameandpath')
    active = xbmc.getCondVisibility('Window.IsActive(%s)' % BOOKMARK_WINDOW)
    playing = xbmc.getCondVisibility('Player.HasVideo')
    return path if path and active and playing else None


def confirm_clear():
    before = context()
    if before is None:
        return False
    accepted = xbmcgui.Dialog().yesno(
        '清空此视频的全部书签？',
        '将清空此视频的普通书签、续播位置和剧集书签。此操作无法撤销。',
        nolabel='取消', yeslabel='清空全部')
    # The native handler reads the current player item. Revalidate after the modal
    # closes so a changed/stopped video never receives the earlier confirmation.
    if not accepted or context() != before:
        return False
    xbmc.executebuiltin('SendClick(%s,3)' % BOOKMARK_WINDOW)
    return True


if __name__ == '__main__' and sys.argv[1:] == ['confirm-clear']:
    confirm_clear()
