"""Offline regressions for packed texture precedence and safe theme authoring.

All generated fixtures are temporary. Runtime notification code uses mocked
Kodi APIs; these checks do not claim device rendering or lifecycle acceptance.
"""
import contextlib
from io import BytesIO, StringIO
import importlib.util
import json
import re
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

from PIL import Image, ImageChops
import build_theme_assets as assets
import build_theme_xml as xml
import check_texture_bundle as bundle

ROOT = Path(__file__).resolve().parents[1]

HOLLOW_RIMS = {
    'infuse/theme-ui/home/focus-ring.png': 'infuse/mask_landscape.png',
    'infuse/theme-ui/home/focus-ring-portrait.png': 'infuse/mask_portrait.png',
    'infuse/theme-ui/home/focus-ring-genre.png': 'infuse/genre50/mask.png',
}


def check_hollow_masks(skin):
    """A matching PNG/XBT pair must also preserve the hollow-rim contract."""
    masks = json.loads((skin / 'resources/theme-ui.json').read_text(encoding='utf-8'))['masks']
    for name, source in HOLLOW_RIMS.items():
        if masks.get(name) != {'source': source, 'mask': 'hollow'}:
            raise ValueError('Hollow rim classification changed: ' + name)
    names = [name for name, item in masks.items() if item['mask'] == 'hollow']
    for name in names:
        with Image.open(skin / 'media' / name) as image:
            alpha = image.convert('RGBA').getchannel('A')
        with Image.open(skin / 'media' / masks[name]['source']) as image:
            artwork = image.convert('RGBA').getchannel('A')
        if alpha.size != artwork.size or not alpha.getbbox():
            raise ValueError('Empty or incorrectly sized hollow rim: ' + name)
        w, h = alpha.size
        if alpha.crop((w // 4, h // 4, 3 * w // 4, 3 * h // 4)).getbbox():
            raise ValueError('Hollow rim centre alpha must be zero: ' + name)
        if ImageChops.subtract(alpha, artwork).getbbox():
            raise ValueError('Hollow rim extends outside artwork: ' + name)
    return names


class HollowRimChecks(unittest.TestCase):
    def setUp(self):
        self.skin = ROOT / 'source/skin.yoplayer.infuse'

    def fixture(self, root):
        skin = root / 'source/skin.yoplayer.infuse'
        (skin / 'resources').mkdir(parents=True)
        masks = {name: {'source': source, 'mask': 'hollow'} for name, source in HOLLOW_RIMS.items()}
        (skin / 'resources/theme-ui.json').write_text(json.dumps({'masks': masks}), encoding='utf-8')
        for name in set(masks) | set(HOLLOW_RIMS.values()):
            path = skin / 'media' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((self.skin / 'media' / name).read_bytes())
        return skin

    def test_delivered_rims_have_empty_centres_and_stay_inside_artwork(self):
        self.assertEqual(set(check_hollow_masks(self.skin)), set(HOLLOW_RIMS))

    def test_filled_centre_is_rejected_even_when_colour_is_neutral(self):
        with tempfile.TemporaryDirectory() as temporary:
            skin = self.fixture(Path(temporary))
            path = skin / 'media' / next(iter(HOLLOW_RIMS))
            image = Image.open(path).convert('RGBA')
            image.putpixel((image.width // 2, image.height // 2), (255, 255, 255, 28))
            image.save(path)
            with self.assertRaisesRegex(ValueError, 'centre alpha must be zero'):
                check_hollow_masks(skin)

    def test_focus_classification_cannot_bypass_the_hollow_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            skin = self.fixture(Path(temporary))
            path = skin / 'resources/theme-ui.json'
            data = json.loads(path.read_text())
            data['masks'][next(iter(HOLLOW_RIMS))]['mask'] = 'focus'
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'classification changed'):
                check_hollow_masks(skin)

    def test_generator_preserves_hollow_rim_semantics(self):
        import theme_ui_assets
        with tempfile.TemporaryDirectory() as temporary:
            skin = self.fixture(Path(temporary))
            for name, raw in theme_ui_assets.outputs(skin).items():
                (Path(temporary) / 'source' / name).write_bytes(raw)
            self.assertEqual(set(check_hollow_masks(skin)), set(HOLLOW_RIMS))

    def test_inner_rim_has_no_outward_offset_or_nine_slice(self):
        root = ET.parse(self.skin / '1080p/Includes_Infuse.xml')
        ring = root.find("./include[@name='YoPlayerCardFocusRing']/definition/control")
        self.assertEqual(ring.findtext('left'), '0')
        self.assertEqual(ring.findtext('top'), '0')
        self.assertEqual(ring.findtext('width'), '$PARAM[width]')
        self.assertEqual(ring.findtext('height'), '$PARAM[height]')
        self.assertIsNone(ring.find('texture').get('border'))
        self.assertEqual(ring.findtext('visible'), '[$PARAM[focused]]')
        card = root.find("./include[@name='YoPlayerBrowseLandscapeCard']")
        call = card.find(".//include[@content='YoPlayerCardFocusRing']")
        self.assertEqual(call.find("param[@name='width']").get('value'), '$PARAM[width]')
        self.assertEqual(call.find("param[@name='height']").get('value'), '$PARAM[height]')


def png(colour, size=(2, 3)):
    image = Image.new('RGBA', size, colour)
    stream = BytesIO()
    image.save(stream, 'PNG')
    return stream.getvalue()


def entry(colour, size=(2, 3)):
    raw = Image.new('RGBA', size, colour).tobytes('raw', 'BGRA')
    return (0, [((*size, 0x10, len(raw), len(raw), 0, 0), raw)])


class TextureChecks(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.skin = self.root / 'source/skin.yoplayer.infuse'
        self.media = self.skin / 'media'
        self.media.mkdir(parents=True)
        (self.skin / 'resources').mkdir()
        (self.root / 'tools').mkdir()
        (self.skin / 'resources/themes.json').write_text('{"aliases":{"sand":"mist"}}')
        (self.root / 'tools/texture-check-baseline.json').write_text('{"exceptions":{}}')

    def write_image(self, name, colour):
        path = self.media / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(png(colour))

    def write_bundle(self, entries):
        (self.media / 'Textures.xbt').write_bytes(bundle.encode(entries))

    def test_reader_decodes_known_bgra_layout(self):
        path = b'pixel.png'.ljust(256, b'\0')
        raw = b'\x03\x02\x01\xff'
        data = (b'XBTF2' + struct.pack('<I', 1) + path + struct.pack('<II', 0, 1) +
                struct.pack('<IIIQQIQ', 1, 1, 0x10, 4, 4, 0, 313) + raw)
        self.assertEqual(bundle.pixels(bundle.parse(data)['pixel.png']), ((1, 1), raw))

    def test_gate_rejects_stale_pixels_even_with_valid_paths(self):
        self.write_image('infuse/themes/ink/preview.png', 'white')
        self.write_bundle({'infuse/themes/ink/preview.png': entry('black')})
        with self.assertRaisesRegex(ValueError, 'pixels differ'):
            bundle.check(self.root)

    def test_gate_rejects_retired_and_unbundled_themes(self):
        self.write_bundle({'infuse/themes/sand/preview.png': entry('white')})
        with self.assertRaisesRegex(ValueError, 'Retired theme'):
            bundle.check(self.root)
        self.write_bundle({'blackback.png': entry('black')})
        self.write_image('infuse/themes/ink/preview.png', 'black')
        with self.assertRaisesRegex(ValueError, 'not bundled'):
            bundle.check(self.root)

    def test_gate_rejects_orphan_theme_while_preserving_legacy_bundle_only(self):
        self.write_image('infuse/themes/ink/preview.png', 'white')
        entries = {'infuse/themes/ink/preview.png': entry('white'),
                   'blackback.png': entry('black')}
        self.write_bundle(entries)
        self.assertEqual(bundle.check(self.root)['bundle_only_entries_preserved'], 1)
        entries['infuse/themes/ink/orphan.png'] = entry('black')
        self.write_bundle(entries)
        with self.assertRaisesRegex(ValueError, 'no loose source: infuse/themes/ink/orphan.png'):
            bundle.check(self.root)

    def test_deleting_last_loose_theme_cannot_leave_a_silent_bundle_entry(self):
        name = 'infuse/themes/ink/preview.png'
        self.write_image(name, 'white')
        self.write_bundle({name: entry('white'), 'blackback.png': entry('black')})
        self.assertEqual(bundle.check(self.root)['theme_images_checked'], 1)
        (self.media / name).unlink()
        target = self.media / 'Textures.xbt'
        before = target.read_bytes(), target.stat().st_mtime_ns
        with self.assertRaisesRegex(ValueError, 'no loose source: ' + name):
            bundle.check(self.root)
        self.assertEqual((target.read_bytes(), target.stat().st_mtime_ns), before)

    def test_sync_preserves_bundle_only_animation_and_is_idempotent(self):
        animation = (2, [((2, 3, 0x10, 24, 24, 70, 0), bytes(24)),
                         ((2, 3, 0x10, 24, 24, 90, 0), bytes([255]) * 24)])
        original = {'old-animation.gif': animation, 'blackback.png': entry('black'),
                    'infuse/themes/mist/preview.png': entry('red'),
                    'infuse/themes/sand/preview.png': entry('yellow')}
        self.write_bundle(original)
        for name, colour in [('infuse/themes/mist/preview.png', 'white'),
                             ('infuse/themes/ink/preview.png', 'black'),
                             ('infuse/progress_fill_white.png', 'white'),
                             ('infuse/home/focus-ring.png', 'white')]:
            self.write_image(name, colour)
        report = bundle.sync_themes(self.root)
        self.assertEqual(report['updated'], ['infuse/themes/mist/preview.png'])
        self.assertEqual(report['retired'], ['infuse/themes/sand/preview.png'])
        self.assertEqual(report['preserved_original_entries'], 2)
        after = bundle.parse((self.media / 'Textures.xbt').read_bytes())
        for name in ['old-animation.gif', 'blackback.png']:
            self.assertEqual(after[name][0], original[name][0])
            self.assertEqual([(f[:-1], b) for f, b in after[name][1]],
                             [(f[:-1], b) for f, b in original[name][1]])
        self.assertEqual(bundle.check(self.root)['status'], 'passed')
        self.assertEqual(bundle.sync_themes(self.root)['status'], 'current')

    def test_modified_legacy_exception_is_rejected(self):
        self.write_image('legacy.png', 'white')
        self.write_bundle({'legacy.png': entry('black')})
        (self.root / 'tools/texture-check-baseline.json').write_text(
            '{"exceptions":{"legacy.png":{"loose_sha256":"old"}}}')
        with self.assertRaisesRegex(ValueError, 'pixels differ'):
            bundle.check(self.root)

    def test_invalid_offsets_do_not_decode(self):
        raw = bytearray(bundle.encode({'a.png': entry('white')}))
        struct.pack_into('<Q', raw, 9 + 264 + 32, 1)
        with self.assertRaisesRegex(ValueError, 'overlaps'):
            bundle.parse(bytes(raw))


class AuthoringChecks(unittest.TestCase):
    def test_palette_change_with_old_pngs_is_rejected_without_writing(self):
        data = json.loads((assets.SKIN / 'resources/themes.json').read_text(encoding='utf-8'))
        next(t for t in data['themes'] if t['id'] == 'ink')['onAccent'] = '#000000'
        output = StringIO()
        with patch.object(assets.json, 'loads', return_value=data), \
                patch.object(Path, 'write_bytes', side_effect=AssertionError('unexpected write')), \
                patch.object(Path, 'mkdir', side_effect=AssertionError('unexpected mkdir')), \
                contextlib.redirect_stdout(output):
            self.assertEqual(assets.main(['--check']), 1)
        result = json.loads(output.getvalue())
        self.assertEqual(result['writes'], 0)
        self.assertEqual(set(result['files']), {
            'skin.yoplayer.infuse/media/infuse/themes/ink/settings_a/switch_on.png',
            'skin.yoplayer.infuse/media/infuse/themes/ink/mute64/switch-on.png',
            'skin.yoplayer.infuse/media/infuse/themes/ink/stage1_utility/on.png',
        })

    def test_assets_check_and_unknown_options_cannot_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skin = root / 'source/skin.yoplayer.infuse'
            (skin / 'resources').mkdir(parents=True)
            (skin / 'resources/themes.json').write_text('{"themes":[]}')
            target = skin / 'test.png'
            target.write_bytes(png('black'))
            before = target.read_bytes(), target.stat().st_mtime_ns
            with patch.object(assets, 'ROOT', root), patch.object(assets, 'SKIN', skin), \
                    patch.object(assets, 'build', return_value={'skin.yoplayer.infuse/test.png': png('white')}) as build, \
                    patch.object(Path, 'write_bytes', side_effect=AssertionError('unexpected write')), \
                    patch.object(Path, 'mkdir', side_effect=AssertionError('unexpected mkdir')), \
                    contextlib.redirect_stdout(StringIO()), contextlib.redirect_stderr(StringIO()):
                self.assertEqual(assets.main(['--check']), 1)
                self.assertEqual(build.call_count, 1)
                with self.assertRaises(SystemExit) as raised:
                    assets.main(['--typo'])
                self.assertEqual(raised.exception.code, 2)
                self.assertEqual(build.call_count, 1)
            self.assertEqual((target.read_bytes(), target.stat().st_mtime_ns), before)

    def test_xml_unknown_options_rejected_before_read_or_write(self):
        with patch.object(xml, 'outputs', side_effect=AssertionError('unexpected generation')), \
                contextlib.redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as raised:
                xml.main(['--typo'])
            self.assertEqual(raised.exception.code, 2)

    def test_select_tint_and_choice_format_follow_theme_contract(self):
        skin = ROOT / 'source/skin.yoplayer.infuse'
        root = ET.parse(skin / '1080p/IncludesDialogSelect.xml')
        tint = root.find(".//control[@id='11800']/texture").get('colordiffuse')
        self.assertEqual(tint, '$VAR[YoPlayerUi_surface]')
        choices = json.loads((skin / 'resources/ui-preferences.json').read_text(encoding='utf-8'))['YoPlayerTheme']['choices']
        self.assertEqual(choices, ['', 'classic', 'ink', 'graphite', 'mist', 'ocean', 'sand'])


class UpgradeNoticeChecks(unittest.TestCase):
    def setUp(self):
        self.visible = {'Window.IsActive(home)': True, 'Skin.HasSetting(FirstTimeRun)': True}
        self.saved = ''
        self.props = {}
        self.commands = []
        self.notice = Mock()
        home = types.SimpleNamespace(getProperty=lambda k: self.props.get(k, ''),
                                     setProperty=lambda k, v: self.props.__setitem__(k, v),
                                     clearProperty=lambda k: self.props.pop(k, None))
        xbmc = types.SimpleNamespace(getCondVisibility=lambda k: self.visible.get(k, False),
                                     getInfoLabel=lambda k: self.saved,
                                     executebuiltin=self.execute_builtin)
        gui = types.SimpleNamespace(Window=lambda n: home, NOTIFICATION_INFO='info',
                                    Dialog=lambda: types.SimpleNamespace(notification=self.notice))
        api = patch.dict(sys.modules, xbmc=xbmc, xbmcgui=gui)
        api.start()
        self.addCleanup(api.stop)
        path = ROOT / 'source/skin.yoplayer.infuse/scripts/infuse_preferences.py'
        spec = importlib.util.spec_from_file_location('theme_preferences_fixture', path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def execute_builtin(self, action):
        self.commands.append(action)
        match = re.fullmatch(r'Skin.SetBool\(([^)]+)\)', action)
        if match:
            self.visible['Skin.HasSetting(' + match[1] + ')'] = True

    def enter_home(self):
        """Replay actual XML using Kodi's prefiltered, ordered load actions.

        Simulate startup finishing before queued Python notices run, so the
        test covers the original FirstTimeRun race instead of only static flags.
        """
        def matches(condition):
            for term in condition.split('+'):
                term = term.strip()
                negate = term.startswith('!')
                predicate = term[1:] if negate else term
                if predicate == 'String.IsEmpty(Skin.String(YoPlayerTheme))':
                    value = not self.saved
                elif re.fullmatch(r'Skin.HasSetting\([A-Za-z0-9]+\)', predicate):
                    value = self.visible.get(predicate, False)
                else:
                    raise AssertionError('Unexpected load predicate: ' + predicate)
                if value == negate:
                    return False
            return True

        root = ET.parse(ROOT / 'source/skin.yoplayer.infuse/1080p/Home.xml').getroot()
        actions = [n.text for n in root.findall('onload')
                   if not n.get('condition') or matches(n.get('condition'))]
        notices = 0
        for action in actions:
            if action.startswith('Skin.SetBool('):
                self.execute_builtin(action)
            elif action == 'RunScript(special://skin/scripts/infuse.py,startup)':
                self.visible['Skin.HasSetting(FirstTimeRun)'] = True
            elif action == 'RunScript(special://skin/scripts/infuse_preferences.py,theme-upgrade-notice)':
                notices += 1
            else:
                raise AssertionError('Unexpected Home load action: ' + action)
        for _ in range(notices):
            self.module.theme_upgrade_notice()
        return notices

    def test_fresh_install_skips_notice_after_startup_and_later_home_entry(self):
        self.visible['Skin.HasSetting(FirstTimeRun)'] = False
        self.visible['Player.HasMedia'] = True
        self.assertEqual(self.enter_home(), 0)
        self.assertTrue(self.visible['Skin.HasSetting(YoPlayerThemeDefaultNotice143)'])
        self.assertEqual(self.commands, ['Skin.SetBool(YoPlayerThemeDefaultNotice143)'])
        self.visible['Player.HasMedia'] = False
        self.assertEqual(self.enter_home(), 0)
        self.notice.assert_not_called()
        self.assertEqual(self.saved, '')

    def test_old_user_deferred_notice_is_not_consumed_and_then_only_runs_once(self):
        for blocker in ('Player.HasMedia', 'System.HasVisibleModalDialog'):
            self.visible[blocker] = True
            self.assertEqual(self.enter_home(), 1)
            self.notice.assert_not_called()
            self.assertEqual(self.commands, [])
            del self.visible[blocker]
        self.assertEqual(self.enter_home(), 1)
        self.notice.assert_called_once()
        self.assertEqual(self.commands, ['Skin.SetBool(YoPlayerThemeDefaultNotice143)'])
        self.assertEqual(self.enter_home(), 0)

    def test_existing_choice_or_notice_flag_prevents_script_dispatch(self):
        for theme in ('classic', 'ink', 'graphite', 'mist', 'ocean', 'sand'):
            self.saved = theme
            self.assertEqual(self.enter_home(), 0)
        self.saved = ''
        self.visible['Skin.HasSetting(YoPlayerThemeDefaultNotice143)'] = True
        self.assertEqual(self.enter_home(), 0)
        self.notice.assert_not_called()
        self.assertEqual(self.commands, [])

    def test_empty_legacy_theme_gets_one_notice_without_theme_write(self):
        self.module.theme_upgrade_notice()
        self.module.theme_upgrade_notice()
        self.notice.assert_called_once()
        self.assertEqual(self.commands, ['Skin.SetBool(YoPlayerThemeDefaultNotice143)'])
        self.assertEqual(self.notice.call_args.args[-1], False)  # No sound.

    def test_saved_themes_and_unsafe_contexts_do_not_notify(self):
        for saved in ('classic', 'ink', 'graphite', 'mist', 'ocean', 'sand'):
            self.saved = saved
            self.module.theme_upgrade_notice()
        self.saved = ''
        for key in ('Player.HasMedia', 'System.HasVisibleModalDialog',
                    'Skin.HasSetting(YoPlayerThemeDefaultNotice143)'):
            self.visible[key] = True
            self.module.theme_upgrade_notice()
            del self.visible[key]
        self.visible['Window.IsActive(home)'] = False
        self.module.theme_upgrade_notice()
        self.notice.assert_not_called()
        self.assertEqual(self.commands, [])

    def test_failed_notification_does_not_consume_notice(self):
        self.notice.side_effect = RuntimeError('fixture')
        with self.assertRaises(RuntimeError):
            self.module.theme_upgrade_notice()
        self.assertFalse(self.props)
        self.assertEqual(self.commands, [])


if __name__ == '__main__':
    unittest.main()
