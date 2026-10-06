"""Publish exact current-detail ratings; no server requests or persistent cache."""
import json
import time
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

METHODS = {'movie': ('Movie', 'moviedetails'), 'tvshow': ('TVShow', 'tvshowdetails'),
           'episode': ('Episode', 'episodedetails')}


def adapter():
    from infuse import import_actions
    import_actions()
    import emby_rating
    return emby_rating


def read(kind, raw_id):
    if kind not in METHODS or not raw_id.isascii() or not raw_id.isdecimal() or int(raw_id) <= 0:
        return ''
    ident = int(raw_id)
    try:
        mod = adapter()
        version = xbmcaddon.Addon('plugin.service.emby-next-gen').getAddonInfo('version')
        if version not in mod.VERIFIED_VERSIONS or not mod.mapped(xbmcvfs.translatePath('special://database/'), kind, ident):
            return ''
        method, result = METHODS[kind]
        response = json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': '2.0', 'id': 1,
            'method': 'VideoLibrary.Get'+method+'Details',
            'params': {kind+'id': ident, 'properties': ['rating']}})))
        row = response.get('result', {}).get(result, {})
        return mod.value(row.get('rating')) if row.get(kind+'id') == ident else ''
    except (RuntimeError, OSError, ValueError, TypeError):
        return ''


class DetailRatings:
    def __init__(self):
        self.key = None
        self.at = 0

    def poll(self):
        win = xbmcgui.Window(12003)
        if not xbmc.getCondVisibility('Window.IsVisible(movieinformation)'):
            self.key = None
            return
        key = (win.getProperty('YoPlayer.DetailSeasons.Identity'),
               xbmc.getInfoLabel('ListItem.DBType'), xbmc.getInfoLabel('ListItem.DBID'))
        # At most one local query per identity / five seconds, never network.
        if key == self.key and time.monotonic()-self.at < 5:
            return
        self.key, self.at = key, time.monotonic()
        win.clearProperty('YoPlayer.Rating')
        score = read(key[1], key[2])
        current = (win.getProperty('YoPlayer.DetailSeasons.Identity'),
                   xbmc.getInfoLabel('ListItem.DBType'), xbmc.getInfoLabel('ListItem.DBID'))
        if current == key and xbmc.getCondVisibility('Window.IsVisible(movieinformation)'):
            win.setProperty('YoPlayer.Rating', score)
