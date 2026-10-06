"""Select the playing library item once. Never send global direction actions."""
import re
import xbmc


def number(value):
    return int(value) if str(value).isdigit() else None


def episode(season, index, title=''):
    pair = number(season), number(index)
    if None not in pair:
        return pair
    match = re.search(r'\bS(\d+)E(\d+)\b', title, re.I)
    return tuple(map(int, match.groups())) if match else None


def identity():
    return tuple(xbmc.getInfoLabel(key) for key in
                 ('Player.Filenameandpath', 'VideoPlayer.DBID', 'VideoPlayer.Season', 'VideoPlayer.Episode'))


def run():
    monitor = xbmc.Monitor()
    original = identity()
    target_id = number(original[1])
    target_episode = episode(original[2], original[3], xbmc.getInfoLabel('Player.Title'))
    if target_id in (None, 0) and target_episode is None:
        return
    for attempt in range(20):
        if (not xbmc.getCondVisibility('Window.IsVisible(1140)') or
                not xbmc.getCondVisibility('Control.HasFocus(6401)') or identity() != original):
            return
        count = number(xbmc.getInfoLabel('Container(6401).NumItems')) or 0
        selection = xbmc.getInfoLabel('Container(6401).CurrentItem')
        matches = []
        for index in range(min(count, 2000)):
            prefix = 'Container(6401).ListItemAbsolute(%d).' % index
            item_id = number(xbmc.getInfoLabel(prefix+'DBID'))
            item_episode = episode(xbmc.getInfoLabel(prefix+'Season'), xbmc.getInfoLabel(prefix+'Episode'),
                                   xbmc.getInfoLabel(prefix+'Label'))
            if target_id not in (None, 0) and item_id == target_id:
                matches = [index]
                break
            # Known disagreeing IDs must never fall back to matching episode numbers.
            if (target_id in (None, 0) or item_id in (None, 0)) and target_episode is not None and item_episode == target_episode:
                matches.append(index)
        if len(matches) == 1:
            if (identity() == original and xbmc.getCondVisibility('Window.IsVisible(1140)') and
                    xbmc.getCondVisibility('Control.HasFocus(6401)') and
                    xbmc.getInfoLabel('Container(6401).CurrentItem') == selection):
                xbmc.executebuiltin('SetFocus(6401,%d,absolute)' % matches[0])
            return
        if count or monitor.waitForAbort(.1):
            return


if __name__ == '__main__':
    run()
