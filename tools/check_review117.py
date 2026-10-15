"""Offline fakes only. No Kodi, accounts, network, real databases or playback."""
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SKIN = ROOT / 'source/skin.yoplayer.infuse'


@contextmanager
def acquired():
    yield True


class RuntimeCase(unittest.TestCase):
    def setUp(self):
        self.properties = {}
        self.labels = {'ListItem.DBType': 'movie', 'ListItem.DBID': '7',
                       'ListItem.FileNameAndPath': '/films/A/movie.iso',
                       'ListItem.Title': 'Movie A'}
        self.flags = {'Window.IsVisible(movieinformation)': True,
                      'Window.IsActive(movieinformation)': True,
                      'Window.IsVisible(1130)': True}
        self.playing = ''
        self.actions = []
        self.seeks = []
        self.stops = 0
        self.row = {'movieid': 7, 'file': '/films/A/movie.iso',
                    'resume': {'position': 125.5}}
        self.player_row = {'type': 'movie', 'id': 7, 'file': '/films/A/movie.iso'}
        env = self

        class Window:
            def __init__(self, ident):
                self.data = env.properties.setdefault(ident, {})
            def getProperty(self, key):
                return self.data.get(key, '')
            def setProperty(self, key, value):
                self.data[key] = value
            def clearProperty(self, key):
                self.data.pop(key, None)

        class Monitor:
            def abortRequested(self):
                return False
            def waitForAbort(self, seconds):
                return True  # tests never sleep or run a real monitor

        class Player:
            def isPlaying(self):
                return bool(env.playing)
            def isPlayingVideo(self):
                return bool(env.playing)
            def getPlayingFile(self):
                return env.playing
            def stop(self):
                env.stops += 1
                env.playing = ''
            def seekTime(self, position):
                env.seeks.append(position)

        self.window = Window
        self.dialog = Mock()
        self.dialog.contextmenu.return_value = -1
        self.rpc = Mock(side_effect=self.respond)
        self.builtin = Mock(side_effect=self.action)
        self.modules = {
            'xbmc': types.SimpleNamespace(
                Monitor=Monitor, Player=Player, getSkinDir=lambda: 'skin.yoplayer.infuse',
                getInfoLabel=lambda k: self.labels.get(k, ''),
                getCondVisibility=lambda k: self.flags.get(k, False),
                executebuiltin=self.builtin, log=Mock(), LOGINFO=1, LOGWARNING=2,
                LOGERROR=3, LOGDEBUG=0, sleep=Mock()),
            'xbmcgui': types.SimpleNamespace(Window=Window, Dialog=lambda: self.dialog),
            'xbmcaddon': types.SimpleNamespace(),
            'xbmcvfs': types.SimpleNamespace(translatePath=lambda p: p, exists=lambda p: False),
            'infuse_detail_play': types.SimpleNamespace(exclusive=acquired, rpc=self.rpc),
        }
        self.module_patch = patch.dict(sys.modules, self.modules)
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        self.window(12003).setProperty('YoPlayer.Detail.Identity', 'movie:7')
        self.window(12003).setProperty('YoPlayer.Detail.Path', '/films/A/movie.iso')
        self.window(12003).setProperty('YoPlayer.Detail.TrailerTitle', 'Movie A')
        self.window(11130).setProperty('YoPlayer.Trailer.Active', 'true')
        self.resume = self.load('resumeplay')

    def load(self, name):
        spec = importlib.util.spec_from_file_location(name, SKIN / 'scripts' / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    def respond(self, method, params):
        if method == 'VideoLibrary.GetMovieDetails':
            return {'moviedetails': self.row.copy()}
        if method == 'Player.GetActivePlayers':
            return [{'type': 'video', 'playerid': 1}]
        if method == 'Player.GetItem':
            return {'item': self.player_row.copy()}
        raise AssertionError('Unexpected RPC: ' + method)

    def action(self, command, *args, **kwargs):
        self.actions.append(command)
        if command == 'Dialog.Close(movieinformation,true)':
            self.flags['Window.IsVisible(movieinformation)'] = False
            self.window(12003).clearProperty('YoPlayer.Detail.Identity')
        if command.startswith('PlayMedia(') and hasattr(self, 'attempt'):
            self.attempt.session.onNotification('xbmc', 'Player.OnPlay', '{}')
            self.attempt.session.onNotification('xbmc', 'Player.OnAVStart', '{}')


class ResumeTests(RuntimeCase):
    def test_exact_identity_position(self):
        self.assertEqual(self.resume.ISOResumeExtractor().resume_position(), 125.5)

    def test_same_filename_other_directory_is_rejected(self):
        self.row['file'] = '/films/B/movie.iso'
        self.assertIsNone(self.resume.ISOResumeExtractor().resume_position())

    def test_wrong_dbid_is_rejected(self):
        self.row['movieid'] = 8
        self.assertIsNone(self.resume.ISOResumeExtractor().resume_position())

    def test_invalid_positions_rejected(self):
        for position in (-1, 0, float('inf'), float('nan'), 'bad'):
            with self.subTest(position=position):
                self.row['resume']['position'] = position
                self.assertIsNone(self.resume.ISOResumeExtractor().resume_position())

    def test_cancel_has_no_play_seek_or_simulated_click(self):
        self.resume.ISOResumeExtractor().run()
        self.assertEqual(self.actions, [])
        self.assertEqual(self.seeks, [])

    def test_native_choice_uses_scoped_native_control(self):
        self.dialog.contextmenu.return_value = 2
        self.resume.ISOResumeExtractor().run()
        self.assertEqual(self.actions, ['SendClick(12003,8)'])

    def test_unverified_version_retains_native_choice(self):
        self.row['file'] = '/films/A/other-version.iso'
        self.resume.ISOResumeExtractor().run()
        self.assertEqual(self.actions, ['SendClick(12003,8)'])
        self.dialog.contextmenu.assert_not_called()

    def test_compatibility_resume_is_absolute_once(self):
        self.dialog.contextmenu.return_value = 0
        self.attempt = self.resume.ISOResumeExtractor()
        self.attempt.run()
        self.assertEqual(self.seeks, [125.5])
        self.assertEqual(sum(a.startswith('PlayMedia(') for a in self.actions), 1)
        self.assertTrue(self.actions[-1].endswith(',noresume)'))
        self.assertFalse(any(a.startswith('Seek(') for a in self.actions))

    def test_start_from_beginning_has_no_seek(self):
        self.dialog.contextmenu.return_value = 1
        self.attempt = self.resume.ISOResumeExtractor()
        self.attempt.run()
        self.assertEqual(self.seeks, [])
        self.assertEqual(sum(a.startswith('PlayMedia(') for a in self.actions), 1)

    def test_replacement_playback_cancels_seek(self):
        attempt = self.resume.ISOResumeExtractor()
        attempt.session.armed = True
        for _ in range(2):
            attempt.session.onNotification('xbmc', 'Player.OnPlay', '{}')
        attempt.session.ready = True
        self.assertFalse(attempt.seek_once(12))
        self.assertEqual(self.seeks, [])

    def test_stop_before_avstart_cancels_seek(self):
        attempt = self.resume.ISOResumeExtractor()
        attempt.session.armed = True
        attempt.session.onNotification('xbmc', 'Player.OnStop', '{}')
        attempt.session.ready = True
        self.assertFalse(attempt.seek_once(12))
        self.assertEqual(self.seeks, [])

    def test_wrong_playing_identity_is_not_sought(self):
        for key, value in (('file', '/films/B/movie.iso'), ('id', 8), ('type', 'episode')):
            with self.subTest(key=key):
                original = self.player_row.copy()
                self.player_row[key] = value
                attempt = self.resume.ISOResumeExtractor()
                attempt.session.ready = True
                self.assertFalse(attempt.seek_once(12))
                self.player_row = original
        self.assertEqual(self.seeks, [])

    def test_detail_replaced_during_menu_cancels_play(self):
        def choose(items):
            self.window(12003).setProperty('YoPlayer.Detail.Identity', 'movie:8')
            return 0
        self.dialog.contextmenu.side_effect = choose
        self.resume.ISOResumeExtractor().run()
        self.assertEqual(self.actions, [])

    def test_other_play_during_menu_cancels_play(self):
        self.attempt = self.resume.ISOResumeExtractor()
        def choose(items):
            self.attempt.session.onNotification('xbmc', 'Player.OnPlay', '{}')
            return 0
        self.dialog.contextmenu.side_effect = choose
        self.attempt.run()
        self.assertEqual(self.actions, [])

    def test_context_menu_closes_only_itself(self):
        with patch.object(sys, 'argv', ['resumeplay.py', 'folderplay']):
            self.resume.ISOResumeExtractor().run()
        self.assertEqual(self.actions, ['Dialog.Close(contextmenu,true)'])


class PreviewTests(RuntimeCase):
    def preview(self):
        return self.load('infuse_trailer_session').Preview('movie:7')

    def test_background_film_not_replaced_or_stopped(self):
        self.playing = '/films/background.mkv'
        preview = self.preview()
        self.assertFalse(preview.begin())
        preview.close()
        self.assertEqual(self.stops, 0)

    def test_duplicate_preview_does_not_replace_owner(self):
        first = self.preview()
        self.assertTrue(first.begin())
        second = self.preview()
        self.assertFalse(second.begin())
        self.assertEqual(self.window(11130).getProperty('YoPlayer.Trailer.Token'), first.token)

    def test_close_only_stops_owned_exact_path(self):
        preview = self.preview()
        self.assertTrue(preview.begin())
        self.playing = '/trailers/A.mp4'
        preview.owned_path = self.playing
        preview.close()
        self.assertEqual(self.stops, 1)

    def test_replaced_media_never_stopped(self):
        preview = self.preview()
        preview.begin()
        preview.owned_path = '/trailers/A.mp4'
        self.playing = '/films/B.mkv'
        preview.close()
        self.assertEqual(self.stops, 0)

    def test_same_url_new_play_is_not_owned(self):
        preview = self.preview()
        preview.begin()
        preview.owned_path = self.playing = '/trailers/A.mp4'
        preview.onPlayBackStarted()
        preview.onPlayBackStarted()
        preview.close()
        self.assertEqual(self.stops, 0)

    def test_delayed_result_after_close_does_not_play(self):
        preview = self.preview()
        preview.begin()
        self.window(11130).clearProperty('YoPlayer.Trailer.Active')
        preview.play_preview('/trailers/A.mp4')
        preview.error('late')
        self.assertEqual(self.actions, [])
        self.assertEqual(self.window(11130).getProperty('YoPlayer.Trailer.Error'), '')

    def test_delayed_result_after_detail_switch_does_not_play(self):
        preview = self.preview()
        preview.begin()
        self.window(12003).setProperty('YoPlayer.Detail.Identity', 'movie:8')
        preview.play_preview('/trailers/A.mp4')
        self.assertEqual(self.actions, [])

    def test_intervening_play_during_network_does_not_get_replaced(self):
        preview = self.preview()
        preview.begin()
        self.playing = '/films/B.mkv'
        preview.play_preview('/trailers/A.mp4')
        preview.close()
        self.assertEqual(self.actions, [])
        self.assertEqual(self.stops, 0)

    def test_manual_stop_cancels_loop(self):
        preview = self.preview()
        preview.begin()
        preview.onPlayBackStopped()
        preview.play_preview('/trailers/A.mp4')
        self.assertEqual(self.actions, [])

    def test_old_request_does_not_clear_new_token(self):
        preview = self.preview()
        preview.begin()
        self.window(11130).setProperty('YoPlayer.Trailer.Token', 'new-request')
        preview.close()
        self.assertEqual(self.window(11130).getProperty('YoPlayer.Trailer.Token'), 'new-request')

    def test_resolved_plugin_requires_original_file_proof(self):
        preview = self.preview()
        preview.begin()
        self.playing = 'https://cdn.example/video'
        self.player_row['file'] = 'plugin://plugin.video.bili/video/BV1/'
        self.assertTrue(preview.identify(self.player_row['file']))
        self.assertEqual(preview.owned_path, self.playing)
        preview.owned_path = ''
        self.assertFalse(preview.identify('plugin://plugin.video.bili/video/BV2/'))

    def test_local_smb_scheme_is_preserved(self):
        module = self.load('trailer')
        module.safe_listdir = lambda path: ([], ['Movie-trailer.mkv'])
        result = module.find_trailer_file('smb://server/share/Movie', 'movie', 'Movie.mkv')
        self.assertEqual(result, 'smb://server/share/Movie/Movie-trailer.mkv')

    def test_bili_disabled_requires_manual_enable(self):
        module = self.load('bili')
        preview = self.preview()
        preview.begin()
        self.assertFalse(module.prepare_preview(preview))
        self.assertEqual(self.actions, [])
        self.assertIn('手动', self.window(11130).getProperty('YoPlayer.Trailer.Error'))

    def test_bili_no_credentials_and_handles_public_denial(self):
        module = self.load('bilitrailer')
        module.get_json = Mock(return_value={'code': -412})
        self.assertIsNone(module.search_bili('movie'))
        self.assertEqual(self.actions, [])
        source = (SKIN / 'scripts/bilitrailer.py').read_text(encoding='utf-8')
        self.assertNotIn("headers['Cookie']", source)
        self.assertNotIn('get_cookie_from_file', source)

    def test_bili_result_title_is_path_encoded(self):
        module = self.load('bilitrailer')
        module.get_json = Mock(return_value={'code': 0, 'data': {'result': [
            {'bvid': 'BV1234', 'title': '<em>A</em>/B,")'}]}})
        url = module.search_bili('movie')
        self.assertIn('A%2FB%2C%22%29', url)
        self.assertNotIn('<em>', url)

    def test_demo_only_stops_verified_owned_playback(self):
        module = self.load('demotrailer')
        demo = module.DemoTrailer()
        home = self.window(10000)
        home.setProperty('YoPlayer.Demo.Owner', demo.owner)
        home.setProperty('YoPlayer.Demo.PlayingOwner', demo.owner)
        home.setProperty('YoPlayer.Demo.PlayingPath', '/trailers/demo.mp4')
        self.playing = '/films/user.mkv'
        demo.stop_owned()
        self.assertEqual(self.stops, 0)
        home.setProperty('YoPlayer.Demo.PlayingOwner', demo.owner)
        home.setProperty('YoPlayer.Demo.PlayingPath', '/trailers/demo.mp4')
        self.playing = '/trailers/demo.mp4'
        demo.stop_owned()
        self.assertEqual(self.stops, 1)

    def test_demo_replacement_play_revokes_same_path_ownership(self):
        module = self.load('demotrailer')
        demo = module.DemoTrailer()
        home = self.window(10000)
        for key, value in (('Owner', demo.owner), ('PlayingOwner', demo.owner),
                           ('PlayingPath', '/trailers/demo.mp4')):
            home.setProperty('YoPlayer.Demo.' + key, value)
        self.playing = '/trailers/demo.mp4'
        demo.monitor.onNotification('xbmc', 'Player.OnPlay', '{}')
        demo.stop_owned()
        self.assertEqual(self.stops, 0)


class PublicationTests(RuntimeCase):
    def test_delayed_director_cannot_publish_into_next_detail(self):
        module = self.load('castphoto')
        publisher = module.DetailPublication()
        self.window(12003).setProperty('YoPlayer.Detail.Identity', 'movie:8')
        publisher.publish('directorname', 'old')
        self.assertEqual(self.window(12003).getProperty('YoPlayer.Cast.directorname'), '')
        self.assertEqual(self.actions, [])

    def test_closed_detail_rejects_publication(self):
        module = self.load('castphoto')
        publisher = module.DetailPublication()
        self.window(12003).clearProperty('YoPlayer.Cast.Owner')
        publisher.publish('directorurl', 'old')
        self.assertEqual(self.window(12003).getProperty('YoPlayer.Cast.directorurl'), '')

    def test_current_director_is_window_local_no_skin_setting_write(self):
        module = self.load('castphoto')
        module.PUBLISHER = module.DetailPublication()
        module.set_skin_string('directorname', 'A, "B"')
        self.assertEqual(self.window(12003).getProperty('YoPlayer.Cast.directorname'), 'A, "B"')
        self.assertEqual(self.actions, [])

    def test_single_rating_row_still_requires_media_type(self):
        import sqlite3
        module = self.load('castphoto')
        module.PUBLISHER = module.DetailPublication()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'fixture.db'
            with sqlite3.connect(path) as conn:
                conn.execute('CREATE TABLE rating (media_id, rating, rating_type, media_type)')
                conn.execute("INSERT INTO rating VALUES (7, 9.5, 'imdb', 'episode')")
            conn.close()
            module.execute_task2(str(path), 'movie', 7)
        self.assertEqual(self.window(12003).getProperty('YoPlayer.Cast.embyimdb'), '')


class ContractTests(unittest.TestCase):
    def xml(self, name):
        return ET.parse(SKIN / '1080p' / name).getroot()

    def test_all_115_control_geometry_is_preserved(self):
        import hashlib
        import re
        baseline = json.loads(Path(__file__).with_name('review117_baseline.json').read_text(encoding='utf-8'))
        tags = ('left', 'top', 'width', 'height', 'font', 'itemgap', 'orientation',
                'texture', 'texturefocus', 'texturenofocus', 'aspectratio', 'textoffsetx', 'textoffsety')
        for name, expected in baseline['control_geometry'].items():
            with self.subTest(file=name):
                # Only the reviewed dynamic artwork scope changes. Geometry and
                # the artwork role itself must still equal the delivered115 tree.
                def binding(text):
                    return re.sub(r'Window\(movieinformation\).Property\(YoPlayer.Cast.(directorurl)\)',
                                  r'Skin.String(\1)', text)
                values = [(c.attrib, [(n.tag, n.attrib, binding((n.text or '').strip()))
                           for n in c if n.tag in tags]) for c in self.xml(name).iter('control')]
                actual = hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                self.assertEqual(actual, expected)

    def test_confirmation_mode_frozen_cancel_default(self):
        root = self.xml('custom_1143_Confirm.xml')
        self.assertEqual(root.findtext('defaultcontrol'), '10')
        for button in root.findall('.//control[@type="button"]'):
            visible = button.findtext('visible')
            self.assertIn('YoPlayer.ConfirmMode', visible)
            self.assertNotIn('Player.Has', visible)
            self.assertNotIn('Player.Playing', visible)
        actions = [node.text for node in root.iter('onclick')]
        self.assertNotIn('Dialog.Close(1126)', actions)
        self.assertIn('Skin.ResetSettings', actions)  # explicit reset remains

    def test_details_and_preview_have_no_unowned_unload_stop(self):
        for name in ('DialogVideoInfo.xml', 'custom_1130_trailer.xml'):
            self.assertFalse(any((n.text or '').lower() == 'stop'
                                 for n in self.xml(name).findall('onunload')))
        self.assertIn('CancelAlarm(1130auto,true)',
                      [n.text for n in self.xml('DialogVideoInfo.xml').findall('onunload')])

    def test_fontsets_have_all_named_roles(self):
        sets = self.xml('Font.xml').findall('fontset')
        required = {n.findtext('name').lower() for n in sets[0].findall('font')}
        for fontset in sets:
            names = [n.findtext('name').lower() for n in fontset.findall('font')]
            self.assertEqual(len(names), len(set(names)))
            self.assertTrue(required <= set(names), fontset.get('id'))
        massive = next(s for s in sets if s.get('id') == 'Massive')
        self.assertEqual(massive.findtext("font[name='font6']/size"), '16')
        self.assertEqual(massive.findtext("font[name='font13']/size"), '38')

    def test_home_has_error_empty_loading_in_order(self):
        values = self.xml('Variables.xml').find("variable[@name='YoPlayerHomeLibraryStatus']").findall('value')
        self.assertIn('Error.libraries', values[0].get('condition'))
        self.assertIn('Loaded.libraries', values[1].get('condition'))
        self.assertIn('Count.libraries', values[1].get('condition'))
        self.assertEqual(values[2].text, '$LOCALIZE[32026]')
        self.assertEqual(self.xml('Home.xml').findtext(".//control[@id='811']/label"),
                         '$VAR[YoPlayerHomeLibraryStatus]')

    def test_context_menu_viewport_retained(self):
        self.assertEqual(self.xml('DialogContextMenu.xml').findtext(".//control[@id='996']/height"), '496')

    def test_custom_ids_use_declarations_and_five_digit_runtime_band(self):
        from repository_checks import check_window_handles, declared_custom_ids
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            (directory / 'custom_9999_not_the_id.xml').write_text('<window><id>1122</id></window>')
            (directory / 'Home.xml').write_text('<window id="1199"/>')
            self.assertEqual(declared_custom_ids(directory), {1122})
        check_window_handles('xbmcgui.Window(11122)', {1122})
        check_window_handles('xbmcgui.Window(12003)', set())
        check_window_handles('xbmcgui.Window(variable)', set())
        with self.assertRaises(ValueError):
            check_window_handles('xbmcgui.Window(11122)', {1130})
        with self.assertRaises(ValueError):
            check_window_handles('xbmcgui.Window(11999)', {1122})

    def test_cross_directory_same_version_guard(self):
        from repository_checks import guard_delivered_versions, ADDONS
        metadata = {a: {'version': '1.0.0'} for a in ADDONS}
        payload = {'source/' + a + '/addon.xml': b'current' for a in ADDONS}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            delivery = root / 'dist' / 'older'
            delivery.mkdir(parents=True)
            zip_path = delivery / 'YoPlayer-Skin-1.0.0.zip'
            with ZipFile(zip_path, 'x') as archive:
                archive.writestr('skin.yoplayer.infuse/addon.xml', b'delivered')
            before = zip_path.read_bytes()
            with self.assertRaises(ValueError):
                guard_delivered_versions(payload, metadata, {root})
            self.assertEqual(zip_path.read_bytes(), before)
            payload['source/skin.yoplayer.infuse/addon.xml'] = b'delivered'
            reusable = guard_delivered_versions(payload, metadata, {root})
            self.assertEqual(reusable['skin.yoplayer.infuse'], zip_path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
