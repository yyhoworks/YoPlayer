"""Home refresh behaviour through the existing module interfaces; no Kodi writes."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'source/plugin.video.yoplayer.home/resources/lib'
sys.path.insert(0, str(LIB))
import home_rows


class Window:
    def __init__(self):
        self.values = {}
    def getProperty(self, key):
        return self.values.get(key, '')
    def setProperty(self, key, value):
        self.values[key] = value
    def clearProperty(self, key):
        self.values.pop(key, None)


class HomeRows(unittest.TestCase):
    def actions(self, window):
        fake = {'xbmc': types.SimpleNamespace(), 'xbmcaddon': types.SimpleNamespace(),
                'xbmcgui': types.SimpleNamespace(Window=lambda _: window),
                'home_dialog': types.SimpleNamespace(Dialog=Mock()),
                'provider': types.SimpleNamespace(PREFIX=home_rows.PREFIX, get_libraries=Mock(),
                    preferences=Mock(), preferences_path=Mock(), rpc=Mock())}
        with patch.dict(sys.modules, fake):
            spec = importlib.util.spec_from_file_location('row_actions_fixture', LIB / 'actions.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        return module, fake

    def test_scoped_refresh_leaves_other_rows_and_focus_request_untouched(self):
        win = Window()
        for route in home_rows.ROWS:
            win.setProperty(home_rows.PREFIX + 'RowRevision.' + route, 'previous')
            win.setProperty(home_rows.PREFIX + 'Loaded.' + route, 'previous')
        win.setProperty(home_rows.PREFIX + 'RefreshPending', 'old-focus')
        module, fake = self.actions(win)
        with patch.dict(sys.modules, fake):
            module.refresh(('continue', 'history'))
        changed = [route for route in home_rows.ROWS if win.getProperty(home_rows.PREFIX + 'RowRevision.' + route) != 'previous']
        self.assertEqual(changed, ['continue'])
        self.assertEqual(win.getProperty(home_rows.PREFIX + 'Loaded.continue'), '')
        self.assertEqual(win.getProperty(home_rows.PREFIX + 'RefreshPending'), 'old-focus')

    def test_full_refresh_reloads_eight_rows_but_keeps_daily_selection(self):
        win = Window()
        win.setProperty(home_rows.PREFIX + 'Cache.daily', 'daily-snapshot')
        module, fake = self.actions(win)
        with patch.dict(sys.modules, fake):
            module.refresh()
        revisions = {win.getProperty(home_rows.PREFIX + 'RowRevision.' + route) for route in home_rows.ROWS}
        self.assertEqual(len(revisions), 1)
        self.assertNotIn('', revisions)
        self.assertEqual(win.getProperty(home_rows.PREFIX + 'Cache.daily'), 'daily-snapshot')

    def test_empty_error_and_initial_completion_and_stale_result(self):
        win = Window()
        self.assertTrue(home_rows.finish(win, 'continue', '', 0))
        self.assertEqual(win.getProperty(home_rows.PREFIX + 'Loaded.continue'), 'initial')
        self.assertEqual(win.getProperty(home_rows.PREFIX + 'Count.continue'), '0')
        win.setProperty(home_rows.PREFIX + 'RowRevision.continue', 'next')
        before = dict(win.values)
        self.assertFalse(home_rows.finish(win, 'continue', 'old', 5))
        self.assertEqual(before, win.values)
        self.assertTrue(home_rows.finish(win, 'continue', 'next', 0, 'unavailable'))
        self.assertEqual(win.getProperty(home_rows.PREFIX + 'Error.continue'), 'unavailable')

    def test_home_has_eight_main_providers_and_no_probe_or_global_revision(self):
        skin = ROOT / 'source/skin.yoplayer.infuse/1080p'
        home = ET.parse(skin / 'Home.xml')
        contents = list(home.iter('content'))
        self.assertEqual(len(contents), 8)
        variables = ET.parse(skin / 'Includes_Infuse_Home.xml')
        for route, (row, setting) in home_rows.ROWS.items():
            container = home.find(".//control[@id='%d']" % row)
            self.assertEqual(container.findtext('content'), '$VAR[YoPlayerHomeUrl%d]' % row)
            var = variables.find("variable[@name='YoPlayerHomeUrl%d']" % row)
            self.assertEqual(var.find('value').get('condition'), 'Skin.HasSetting(' + setting + ')')
            self.assertFalse(var.find('value').text)
            url = var.findall('value')[1].text
            self.assertIn('widget=1', url)
            self.assertIn('RowRevision.' + route, url)
        raw = (skin / 'Home.xml').read_text(encoding='utf-8')
        self.assertNotIn('probe=1', raw)
        self.assertNotIn('Container(930', raw)

    def test_hidden_widget_exits_before_loading_membership_or_rpc(self):
        win = Window()
        api = {'xbmc': types.SimpleNamespace(getCondVisibility=lambda _: True),
               'xbmcaddon': types.SimpleNamespace(), 'xbmcgui': types.SimpleNamespace(Window=lambda _: win),
               'xbmcplugin': types.SimpleNamespace(endOfDirectory=Mock()), 'xbmcvfs': types.SimpleNamespace()}
        with patch.dict(sys.modules, api):
            spec = importlib.util.spec_from_file_location('row_provider_fixture', LIB / 'provider.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.display_membership = Mock(side_effect=AssertionError('hidden row fetched'))
            module.cached_home_media = Mock(side_effect=AssertionError('hidden row fetched'))
            module.directory(1, 'daily', widget=True)
        self.assertEqual(win.getProperty(home_rows.PREFIX + 'Count.daily'), '0')
        api['xbmcplugin'].endOfDirectory.assert_called_once_with(1, succeeded=True, cacheToDisc=False)

    def test_reveal_publishes_revision_before_the_url_can_become_visible(self):
        state = {'hidden': True}
        calls = []
        def builtin(command, **_):
            calls.append(('visible', command))
            state['hidden'] = command.endswith(',true)')
        api = {'xbmc': types.SimpleNamespace(Monitor=lambda: types.SimpleNamespace(abortRequested=lambda: False),
                    getCondVisibility=lambda _: state['hidden'], executebuiltin=builtin),
               'xbmcgui': types.SimpleNamespace(), 'home_dialog': types.SimpleNamespace(Dialog=Mock()),
               'actions': types.SimpleNamespace(refresh=lambda routes: calls.append(('refresh', tuple(routes))))}
        with patch.dict(sys.modules, api):
            spec = importlib.util.spec_from_file_location('row_settings_fixture', LIB / 'home_settings.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.assertTrue(module.set_hidden('InfuseHidePicks', False))
        self.assertEqual(calls, [('refresh', ('daily',)), ('visible', 'Skin.SetBool(InfuseHidePicks,false)')])

    def test_visibility_acknowledgement_can_arrive_on_a_later_gui_round(self):
        state = {'hidden': True, 'pending': False, 'waits': 0}
        def pause(_):
            state['waits'] += 1
            state['hidden'] = False
            return False
        api = {'xbmc': types.SimpleNamespace(Monitor=lambda: types.SimpleNamespace(abortRequested=lambda: False, waitForAbort=pause),
                    getCondVisibility=lambda _: state['hidden'], executebuiltin=lambda *a, **k: None),
               'xbmcgui': types.SimpleNamespace(), 'home_dialog': types.SimpleNamespace(Dialog=Mock()),
               'actions': types.SimpleNamespace(refresh=lambda _: None)}
        with patch.dict(sys.modules, api):
            spec = importlib.util.spec_from_file_location('row_later_gui_fixture', LIB / 'home_settings.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.assertTrue(module.set_hidden('InfuseHidePicks', False))
        self.assertEqual(state['waits'], 1)


if __name__ == '__main__':
    unittest.main()
