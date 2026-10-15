"""Anonymous trailer discovery; playback/authentication belongs to Bili addon.

No account.json, Cookie header, credential copying or automatic demo/login.
HTTP results are data only and are never run as builtin text.
"""
import json
import re
import sys
import time
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import xbmc
import xbmcgui


def get_json(url):
    request = Request(url, headers={'User-Agent': 'Mozilla/5.0',
                                    'Referer': 'https://www.bilibili.com/'})
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read(2 * 1024 * 1024).decode('utf-8'))


def search_bili(keyword):
    try:
        # Public discovery does not receive the plugin's login credential.
        data = get_json('https://api.bilibili.com/x/web-interface/search/type?' +
                        urlencode({'search_type': 'video', 'keyword': keyword,
                                   'page': 1, 'pagesize': 1}))
        if data.get('code') != 0:
            return None
        results = (data.get('data') or {}).get('result') or []
        if not results:
            return None
        bvid = results[0].get('bvid', '')
        if not re.fullmatch(r'BV[0-9A-Za-z]+', bvid):
            return None
        title = re.sub(r'<[^>]*>', '', results[0].get('title', ''))
        return 'plugin://plugin.video.bili/video/{}/0/false/false/False/{}/'.format(
            bvid, quote(title, safe=''))
    except Exception as exc:
        # No credentials or request URLs in logs.
        xbmc.log('YoPlayer anonymous trailer search: ' + type(exc).__name__, xbmc.LOGWARNING)
        return None


def clean_url(url):
    return url


def main():
    if 'demo' not in sys.argv:
        from trailerurl import main as preview_main
        preview_main()
        return
    from resumeplay import identity, quote as builtin_quote
    from infuse_detail_play import rpc
    if len(sys.argv) != 4:
        return  # demo playback must belong to the existing demo loop
    owner, request = sys.argv[2:]
    home = xbmcgui.Window(10000)
    selected = identity()
    def valid():
        return (identity() == selected
                and xbmc.getCondVisibility('Window.IsVisible(videos)')
                and xbmc.getInfoLabel('Skin.String(allowdemo)') == '1'
                and home.getProperty('YoPlayer.Demo.Owner') == owner
                and home.getProperty('YoPlayer.Demo.Request') == request)
    if not valid() or xbmc.Player().isPlaying():
        return
    title = xbmc.getInfoLabel('ListItem.TVShowTitle' if selected[0] == 'episode'
                              else 'ListItem.Title')
    url = search_bili(title + ' 预告') if title else None
    if url and valid() and not xbmc.Player().isPlaying():
        xbmc.executebuiltin('PlayMedia(' + builtin_quote(url) + ',1,noresume)')
        monitor = xbmc.Monitor()
        deadline = time.monotonic() + 10
        while valid() and time.monotonic() < deadline:
            try:
                if xbmc.Player().isPlayingVideo():
                    players = rpc('Player.GetActivePlayers', {})
                    videos = [p for p in players if p.get('type') == 'video']
                    if len(videos) != 1:
                        return
                    item = rpc('Player.GetItem', {'playerid': videos[0]['playerid'],
                                                 'properties': ['file']}).get('item', {})
                    actual = xbmc.Player().getPlayingFile()
                    if valid() and (actual == url or item.get('file') == url):
                        home.setProperty('YoPlayer.Demo.PlayingPath', actual)
                        home.setProperty('YoPlayer.Demo.PlayingOwner', owner)
                        return
            except (RuntimeError, ValueError, TypeError, KeyError):
                return
            if monitor.waitForAbort(.1):
                return


if __name__ == '__main__':
    main()
