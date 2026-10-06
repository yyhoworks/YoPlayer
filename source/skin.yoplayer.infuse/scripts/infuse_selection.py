"""Use Kodi's native information action while Infuse owns the UI."""
import json
import os
import xbmc
import xbmcaddon
import xbmcvfs

SETTING = 'myvideos.selectaction'
INFO = 3  # Kodi Omega's ACTION_INFO, verified against system/settings/settings.xml.


def rpc(method, params):
    response = json.loads(xbmc.executeJSONRPC(json.dumps(dict(jsonrpc='2.0', id=1, method=method, params=params))))
    if 'error' in response:
        raise RuntimeError('Native select action unavailable')
    return response.get('result', {})


class SelectionPolicy:
    def __init__(self):
        profile = xbmcvfs.translatePath(xbmcaddon.Addon('skin.yoplayer.infuse').getAddonInfo('profile'))
        os.makedirs(profile, exist_ok=True)
        self.path = os.path.join(profile, 'select-action-lease.json')
        self.original = None

    def current(self):
        return rpc('Settings.GetSettingValue', {'setting': SETTING})['value']

    def acquire(self):
        current = self.current()
        try:
            with open(self.path, encoding='utf-8') as file:
                saved = json.load(file)['original']
        except (OSError, ValueError, KeyError):
            saved = current
        # Keep the original through a skin reload or an interrupted Kodi run.
        self.original = saved if current == INFO else current
        if current != INFO:
            with open(self.path, 'w', encoding='utf-8') as file:
                json.dump({'original': self.original}, file)
            rpc('Settings.SetSettingValue', {'setting': SETTING, 'value': INFO})

    def release(self):
        if self.original is not None and self.current() == INFO:
            rpc('Settings.SetSettingValue', {'setting': SETTING, 'value': self.original})
        if os.path.exists(self.path):
            os.remove(self.path)
