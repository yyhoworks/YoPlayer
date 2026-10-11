"""Source regressions; deliberately not a claim of Kodi UI acceptance."""
import sys

# The clone-only mode must run before importing local historical fixtures.
if __name__ == '__main__' and '--repository' in sys.argv:
    if sys.argv[1:] != ['--repository']:
        raise SystemExit('Usage: python tools/check_infuse_structure.py --repository')
    from repository_checks import main as repository_main
    raise SystemExit(repository_main())

# Select the reviewed current contract before importing historical projections.
# The 44-75 runner below is preserved for its matching inputs, not skipped tests
# credited to96. Unknown later versions must acquire a separately reviewed gate.
if __name__ == '__main__':
    from pathlib import Path
    import xml.etree.ElementTree as ET
    current_version = ET.parse(Path(__file__).resolve().parents[1] /
                              'source/skin.yoplayer.infuse/addon.xml').getroot().get('version')
    # Device evidence and frozen maintainer fixtures stay out of Git. A fresh
    # clone must have a usable default entry without importing those modules.
    local_gates = {'2026.10.3.96': 'runtime96_scope.py',
                   '2026.10.3.97': 'runtime96_scope.py',
                   '2026.10.3.98': 'runtime96_scope.py',
                   '2026.10.3.99': 'runtime96_scope.py',
                   '2026.10.3.100': 'runtime100_scope.py',
                   '2026.10.3.101': 'runtime101_scope.py',
                   '2026.10.3.102': 'runtime102_scope.py',
                   '2026.10.3.103': 'runtime103_scope.py',
                   '2026.10.3.104': 'runtime104_scope.py',
                   '2026.10.3.105': 'runtime105_scope.py',
                   '2026.10.3.106': 'runtime106_scope.py',
                   '2026.10.3.107': 'runtime107_scope.py',
                   '2026.10.3.108': 'runtime108_scope.py',
                   '2026.10.3.109': 'runtime109_scope.py',
                   '2026.10.3.110': 'runtime110_scope.py',
                   '2026.10.3.111': 'runtime111_scope.py'}
    gate = local_gates.get(current_version)
    if gate and not Path(__file__).with_name(gate).is_file():
        if sys.argv[1:]:
            raise SystemExit('Usage: python tools/check_infuse_structure.py [--repository]')
        print('Local maintainer fixtures are absent; running portable repository checks only.')
        from repository_checks import main as repository_main
        raise SystemExit(repository_main())
    gate = local_gates.get(current_version)
    if gate:
        if sys.argv[1:]:
            raise SystemExit('Usage: python tools/check_infuse_structure.py [--repository]')
        import importlib
        gate_module = importlib.import_module(gate.replace('.py', ''))
        raise SystemExit(gate_module.main())
                                    ('contracts/runtime'+current_version.rsplit('.',1)[1]+'-entry.json')).read_text(encoding='utf-8'))
        raise SystemExit(current_main(revision_entry=contract_entry))
    if tuple(map(int, current_version.split('.'))) > (2026, 10, 3, 75):
        raise SystemExit('No reviewed default contract for ' + current_version +
                         '; --repository checks syntax/resources only')

from collections import Counter
from zipfile import ZipFile
from unittest.mock import Mock, patch
import ast
import hashlib
import importlib
import importlib.util
import json
import types
import unittest
import xml.etree.ElementTree as ET
from restore_infuse_structure import BASE, ROOT, SKIN, REFERENCE, PREFIX, VERSION
from infuse_osd import PATCH_FILES, upgrade
from check_minsk_osd_features import MinskOSDTests, tree_signature
from check_detail_layout import DetailLayoutTests, assert_reference_components, normalize_detail_geometry
from ui_stage1 import CHANGED as STAGE1_CHANGED, assert_current_xml


def source_hashes():
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (BASE / 'source').rglob('*') if path.is_file()
            and '__pycache__' not in path.parts and path.suffix not in ('.pyc', '.pyo')}


def geometry(root, stream_labels=False, vs10_buttons=False):
    tags = ('left', 'top', 'width', 'height', 'font', 'textoffsetx', 'textoffsety',
            'itemgap', 'orientation', 'texturefocus', 'texturenofocus', 'texture')
    return Counter((node.get('type'), node.get('id'), tuple((tag, node.findtext(tag)) for tag in tags
                   if not (tag == 'width' and ((stream_labels and node.get('type') == 'label') or
                       (vs10_buttons and node.get('id') in ('1110200', '1110201', '1110202', '1110203'))))))
                   for node in root.iter('control'))


class LibraryCoverTests(unittest.TestCase):
    def test_library_layouts_use_the_cover_as_the_card_texture(self):
        home = ET.parse(SKIN / '1080p/Home.xml').getroot()
        panel = home.find('.//control[@id="302"]')
        for layout in ('itemlayout', 'focusedlayout'):
            tile = panel.find(layout + '/include[@content="InfuseHomeFavTile"]')
            self.assertIsNone(tile.find('param[@name="icon"]'))
            self.assertEqual(tile.find('param[@name="texture"]').get('value'), '$INFO[ListItem.Art(thumb)]')

    def test_cover_fills_the_card_without_a_folder_or_icon_overlay(self):
        root = ET.parse(SKIN / '1080p/Includes_Infuse_Home.xml').getroot()
        tile = root.find('include[@name="InfuseHomeFavTile"]')
        self.assertIsNone(tile.find('param[@name="icon"]'))
        self.assertEqual(tile.find('param[@name="texture"]').get('default'), 'infuse/library_placeholder.png')
        images = tile.findall('definition/control/control[@type="image"]')
        self.assertEqual(len(images), 2)
        cover = images[1]
        self.assertEqual([cover.findtext(tag) for tag in ('left', 'top', 'width', 'height')], ['0', '0', '380', '200'])
        texture = cover.find('texture')
        self.assertEqual(texture.text, '$PARAM[texture]')
        self.assertEqual(texture.attrib, {'diffuse': 'infuse/mask_landscape.png', 'fallback': 'infuse/library_placeholder.png', 'background': 'true'})
        self.assertEqual(cover.findtext('aspectratio'), 'scale')
        self.assertEqual(cover.find('aspectratio').get('scalediffuse'), 'false')

    def test_only_the_library_artwork_changes_from_the_reference(self):
        with ZipFile(REFERENCE) as archive:
            expected = ET.fromstring(archive.read(PREFIX + '1080p/Includes_Infuse_Home.xml'))
        actual = ET.parse(SKIN / '1080p/Includes_Infuse_Home.xml').getroot()
        from v50_settings_scope import before_v50
        actual = before_v50('Includes_Infuse_Home.xml',actual)
        expected_tile = expected.find('include[@name="InfuseHomeFavTile"]')
        actual_tile = actual.find('include[@name="InfuseHomeFavTile"]')
        expected_group = expected_tile.find('definition/control')
        actual_group = actual_tile.find('definition/control')
        expected_group.remove(expected_group.find('control[@type="image"][left="142"]'))
        expected_group.remove(expected_group.find('control[@type="image"][left="0"]'))
        actual_group.remove(actual_group.find('control[@type="image"][left="0"]'))
        self.assertEqual(geometry(expected), geometry(actual))
        def fingerprint(node):
            return (node.tag, node.attrib, (node.text or '').strip(), [fingerprint(child) for child in node])
        self.assertEqual(fingerprint(expected_group), fingerprint(actual_group))
        expected.remove(expected_tile)
        actual.remove(actual_tile)
        self.assertEqual(fingerprint(expected), fingerprint(actual))


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.flags = {'Window.IsActive(Videos) + !System.HasVisibleModalDialog': True}
        self.labels = {}
        self.builtin = Mock()
        sys.modules['xbmc'] = types.SimpleNamespace(
            getCondVisibility=lambda key: self.flags.get(key, False),
            getInfoLabel=lambda key: self.labels.get(key, ''), executebuiltin=self.builtin)
        modules=patch.dict(sys.modules,{'xbmcgui':Mock()})
        modules.start();self.addCleanup(modules.stop)
        spec = importlib.util.spec_from_file_location('browse_test', SKIN / 'scripts/infuse_browse.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.open = Mock()
        self.router = module.BrowseRouter(self.open)

    def visit(self, path, kind):
        self.labels['Container.FolderPath'] = path
        self.flags['Container.Content(tvshows)'] = kind == 'tvshows'
        self.flags['Container.Content(seasons) | Container.Content(episodes)'] = kind in ('seasons', 'episodes')
        self.router.poll()

    def test_filtered_library_restored_before_native_details(self):
        origin = 'videodb://tvshows/titles/?xsp=filtered-library'
        self.visit(origin, 'tvshows')
        self.visit('videodb://tvshows/titles/381/', 'seasons')
        self.open.assert_called_once_with(381)
        self.assertIn(origin, self.builtin.call_args.args[0])
        self.assertTrue(self.builtin.call_args.kwargs['wait'])
        self.router.poll()
        self.open.assert_called_once()

    def test_explicit_seasons_and_page_changes_do_not_reopen_details(self):
        self.labels['Window(Home).Property(YoPlayer.Infuse.BrowseShow)'] = '381'
        self.visit('videodb://tvshows/titles/381/', 'seasons')
        self.visit('videodb://tvshows/titles/381/2/', 'episodes')
        self.open.assert_not_called()
        self.builtin.assert_not_called()

    def test_movies_plugins_and_modal_are_not_rerouted(self):
        self.visit('videodb://movies/titles/', 'movies')
        self.visit('plugin://provider/show/381/', 'episodes')
        self.flags['Window.IsActive(Videos) + !System.HasVisibleModalDialog'] = False
        self.visit('videodb://tvshows/titles/381/', 'seasons')
        self.open.assert_not_called()


def main():
    from runtime_cleanup_scope import verify as verify_cleanup
    cleanup = verify_cleanup()
    stage1 = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.discover(str(BASE/'tools'), pattern='check_ui_stage1*.py'))
    assert stage1.wasSuccessful()
    stage2 = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.discover(str(BASE/'tools'), pattern='check_ui_stage2*.py'))
    assert stage2.wasSuccessful()
    from check_inline_seasons import InlineSeasonTests
    seasons = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(InlineSeasonTests))
    assert seasons.wasSuccessful()
    from infuse_detail_dialogs import FILES as DIALOG_FILES
    from check_detail_dialogs import DetailDialogTests
    dialogs = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(DetailDialogTests))
    assert dialogs.wasSuccessful()
    from infuse_settings import FILES as SETTINGS_FILES
    from check_settings_layout import SettingsLayoutTests
    settings = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SettingsLayoutTests))
    assert settings.wasSuccessful()
    restored = []
    exceptions = {'Home.xml', 'DialogVideoInfo.xml', 'Variables.xml', 'SkinSettings.xml', 'VideoOSD.xml',
                  'Custom_1144_OSD_subtitles.xml', 'Custom_1145_OSD_audio.xml', 'DialogButtonMenu.xml',
                  'custom_1141_VS10.xml', 'custom_OptionsDialog.xml'}
    osd_exact_files = PATCH_FILES - exceptions
    exceptions |= PATCH_FILES
    with ZipFile(REFERENCE) as archive:
        for name in archive.namelist():
            if name.endswith('/') or not name.startswith(PREFIX):
                continue
            relative = name[len(PREFIX):]
            if relative.split('/')[0] not in ('1080p', 'media', 'fonts', 'colors', 'language', 'playlists'):
                continue
            expected = archive.read(name)
            if relative.endswith('.xml'):
                expected = expected.replace(b'skin.confluence.minsk', b'skin.yoplayer.infuse')
            actual = (SKIN / relative).read_bytes()
            if ET.parse(SKIN/'addon.xml').getroot().get('version') in ('2026.10.3.66','2026.10.3.67','2026.10.3.68','2026.10.3.69','2026.10.3.70','2026.10.3.71','2026.10.3.72','2026.10.3.73','2026.10.3.74','2026.10.3.75'):
                from v66_scope import before_bytes
                actual=before_bytes(relative,actual)
            if relative == 'media/Textures.xbt':
                from ui_stage2_branding import remove_legacy_textures
                from ui_lucide_defaults import replace_defaults
                from ui_media_icons import replace_media
                assert actual == replace_media(replace_defaults(remove_legacy_textures(expected))), 'Unrelated packed texture changed'
                restored.append(relative)
                continue
            if relative in ('language/resource.language.zh_cn/strings.po', 'language/resource.language.en_gb/strings.po'):
                from ui_stage2_branding import language_metadata
                assert actual == language_metadata(expected, relative.split('/')[1]), 'Unrelated translation changed'
                restored.append(relative)
                continue
            if relative in STAGE1_CHANGED and relative.endswith('.xml'):
                # Validate the complete reviewed delta against the frozen .2 source,
                # rather than exempting a changed page from reference validation.
                assert_current_xml(relative)
                restored.append(relative)
                continue
            if relative.startswith('1080p/') and relative.split('/')[-1] in DIALOG_FILES:
                # .24 -> approved dialog visuals AND independent native contracts above.
                restored.append(relative)
                continue
            if relative.startswith('1080p/') and relative.split('/')[-1] in SETTINGS_FILES:
                # Replaced by exact .19 -> approved A migration AND native contract tests above.
                restored.append(relative)
                continue
            if relative == '1080p/Includes_Infuse_Home.xml':
                restored.append(relative)
                continue
            if relative == '1080p/Includes_Infuse_VideoInfo.xml':
                assert_reference_components(ET.fromstring(expected), ET.fromstring(actual))
                restored.append(relative)
                continue
            if relative.split('/')[-1] in exceptions and relative.startswith('1080p/'):
                if relative.split('/')[-1] != 'Variables.xml':
                    filename = relative.split('/')[-1]
                    reference_root = ET.fromstring(expected)
                    if filename in PATCH_FILES:
                        reference_root = upgrade(filename, reference_root)
                    actual_root = ET.fromstring(actual)
                    if filename == 'DialogVideoInfo.xml':
                        normalize_detail_geometry(actual_root)
                    if filename in osd_exact_files:
                        assert tree_signature(actual_root) == tree_signature(reference_root), relative
                    stream_labels = '1144' in relative or '1145' in relative
                    vs10_buttons = relative.endswith(('VideoOSD.xml', 'custom_1141_VS10.xml'))
                    reference_geometry = geometry(reference_root, stream_labels, vs10_buttons)
                    actual_geometry = geometry(actual_root, stream_labels, vs10_buttons)
                    assert not reference_geometry - actual_geometry, relative
            else:
                assert actual == expected, relative
            restored.append(relative)
    for path in list((SKIN / '1080p').glob('*.xml')) + list((SKIN / 'colors').glob('*.xml')) + [SKIN / 'addon.xml']:
        ET.parse(path)
    for path in (BASE / 'source').rglob('*.py'):
        ast.parse(path.read_text(encoding='utf-8-sig'))
    assert not list((SKIN / '1080p').glob('custom_119*_Infuse*.xml'))
    assert 'InfuseReferenceButtonInk208' not in (SKIN / '1080p/VideoOSD.xml').read_text(encoding='utf-8')
    for name in ('Custom_1144_OSD_subtitles.xml', 'Custom_1145_OSD_audio.xml'):
        root = ET.parse(SKIN / '1080p' / name).getroot()
        assert not any('script.skinvariables' in (node.text or '') for node in root.iter())
        assert not any(node.text in ('PlayerControl(Play)', 'seek(-2)') for node in root.iter('onclick'))
    home = ET.parse(SKIN / '1080p/Home.xml').getroot()
    assert 'open-library' in home.find('.//control[@id="302"]/onclick').text
    assert home.find('.//include/param[@name="onclick"][@value="RunScript(special://skin/scripts/infuse.py,power-menu)"]') is not None
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RoutingTests))
    assert result.wasSuccessful()
    from check_infuse_native_features import NativeFeaturesTests
    features = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NativeFeaturesTests))
    assert features.wasSuccessful()
    covers = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(LibraryCoverTests))
    assert covers.wasSuccessful()
    osd = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MinskOSDTests))
    assert osd.wasSuccessful()
    from check_compact_osd import CompactPlayerTests
    compact = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CompactPlayerTests))
    assert compact.wasSuccessful()
    from check_home_menus import HomeMenuTests
    menus = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HomeMenuTests))
    assert menus.wasSuccessful()
    from check_system_dashboard import SystemDashboardTests
    dashboard = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SystemDashboardTests))
    assert dashboard.wasSuccessful()
    detail = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(DetailLayoutTests))
    assert detail.wasSuccessful()
    from check_glass_osd import GlassOSDTests
    glass = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(GlassOSDTests))
    assert glass.wasSuccessful()
    from check_detail_playback import PlaybackTests
    playback = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PlaybackTests))
    assert playback.wasSuccessful()
    from check_ui_dialog_completion import DialogCompletionTests
    completion = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(DialogCompletionTests))
    assert completion.wasSuccessful()
    from check_options_focus import OptionsFocusTests
    options_focus = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(OptionsFocusTests))
    assert options_focus.wasSuccessful()
    from check_ui_subtitle_search_compact import SubtitleSearchTests
    subtitle_search = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SubtitleSearchTests))
    assert subtitle_search.wasSuccessful()
    from check_ui_stream_panel_refinement import StreamPanelRefinementTests
    stream_panel = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(StreamPanelRefinementTests))
    assert stream_panel.wasSuccessful()
    from check_ui_playback_info_refinement import PlaybackInfoRefinementTests
    playback_info = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PlaybackInfoRefinementTests))
    assert playback_info.wasSuccessful()
    from check_dialog_confirm_refinement import ConfirmTests
    confirm = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ConfirmTests))
    assert confirm.wasSuccessful()
    from check_reorder import ReorderTests
    reorder = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ReorderTests))
    assert reorder.wasSuccessful()
    from check_ui_v47_visual import Visual47Tests
    visual47=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Visual47Tests))
    assert visual47.wasSuccessful()
    from check_visibility import MembershipTests, PagingTests, SyncedTests
    visibility_suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in (MembershipTests,PagingTests,SyncedTests))
    visibility=unittest.TextTestRunner(verbosity=2).run(visibility_suite)
    assert visibility.wasSuccessful()
    from check_v50_settings_rating import RatingTests, PreferencesTests, ConfigTests, XMLTests
    v50_suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in (RatingTests,PreferencesTests,ConfigTests,XMLTests))
    v50=unittest.TextTestRunner(verbosity=2).run(v50_suite)
    assert v50.wasSuccessful()
    from check_v50_system_tools import SystemToolsTests
    system_tools=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SystemToolsTests))
    assert system_tools.wasSuccessful()
    from check_v50_genres import GenreTests
    genre_split=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(GenreTests))
    assert genre_split.wasSuccessful()
    from v66_classic_projection import disable
    disable()
    report = {'v50_genre_split_tests':genre_split.testsRun,'v50_system_tools_tests':system_tools.testsRun,'v50_settings_rating_tests':v50.testsRun, 'status': 'passed', 'runtime_cleanup': cleanup, 'skin_version': ET.parse(SKIN / 'addon.xml').getroot().get('version'), 'reference_files_verified': len(restored),
              'reference_files_checked': restored, 'validation_rebuilds_source': False,
              'baseline_page_frames_and_fonts_preserved': False, 'routing_tests': result.testsRun,
              'unmodified_reference_pages_preserved': True, 'approved_osd_xml_changes': sorted(PATCH_FILES),
              'minsk_osd_feature_tests': osd.testsRun,
              'stage1_tests': stage1.testsRun,
              'stage2_tests': stage2.testsRun,
              'approved_stage1_changes': sorted(STAGE1_CHANGED),
              'compact_osd_tests': compact.testsRun,
              'home_menu_tests': menus.testsRun,
              'system_dashboard_tests': dashboard.testsRun,
              'detail_layout_tests': detail.testsRun,
              'glass_osd_tests': glass.testsRun,
              'detail_playback_tests': playback.testsRun,
              'dialog_completion_tests': completion.testsRun,
              'options_focus_tests': options_focus.testsRun,
              'subtitle_search_compact_tests': subtitle_search.testsRun,
              'stream_panel_refinement_tests': stream_panel.testsRun,
              'playback_info_refinement_tests': playback_info.testsRun,
              'dialog_confirm_refinement_tests': confirm.testsRun,
              'reorder_tests': reorder.testsRun,
              'home_visibility_tests': visibility.testsRun,
              'settings_layout_tests': settings.testsRun,
              'detail_dialog_tests': dialogs.testsRun,
              'inline_season_tests': seasons.testsRun,
              'approved_detail_dialog_xml_changes': sorted(DIALOG_FILES),
              'detail_dialogs': 'B unified surfaces; native art/file flow retained; explicit rating clear; Kodi acceptance pending',
              'approved_settings_xml_changes': sorted(SETTINGS_FILES),
              'settings_layout': 'A; native IDs, actions, conditions, levels and list navigation retained; UI acceptance pending',
              'osd_layout': 'D; four glass utility buttons; bounded episode grid focus; Kodi UI acceptance pending',
              'detail_layout': 'B; native actions and navigation preserved against .17; no UI acceptance claim',
              'native_feature_tests': features.testsRun, 'library_cover_tests': covers.testsRun,
              'library_card_frames_and_labels_preserved': True, 'stream_label_widths_bounded': True,
              'source_sha256': source_hashes(), 'windows_ui_acceptance': 'pending', 'coreelec': 'not-tested'}
    (BASE / 'docs/structure-validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Original files and geometry verified:', len(restored))


if __name__ == '__main__':
    if ET.parse(SKIN/'addon.xml').getroot().get('version') in ('2026.10.3.66', '2026.10.3.67','2026.10.3.68','2026.10.3.69','2026.10.3.70','2026.10.3.71','2026.10.3.72','2026.10.3.73','2026.10.3.74','2026.10.3.75'):
        from v66_scope import verify as verify66
        verify66()
        from v66_classic_projection import classic
        with classic():main()
    else:main()
