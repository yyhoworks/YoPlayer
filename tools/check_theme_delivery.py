"""Offline regressions for packed texture precedence and safe theme authoring.

All generated fixtures are temporary. Runtime notification code uses mocked
Kodi APIs; these checks do not claim device rendering or lifecycle acceptance.
"""
import contextlib
from io import BytesIO, StringIO
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

from PIL import Image
import build_theme_assets as assets
import build_theme_xml as xml
import check_texture_bundle as bundle

ROOT = Path(__file__).resolve().parents[1]


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
        root = ET.parse(skin / '1080p/Variables.xml')
        condition = root.find("variable[@name='YoPlayerSelectPanelDiffuse']/value").get('condition')
        self.assertIn('$EXP[YoPlayerThemeIs_ocean]', condition)
        self.assertNotIn('Skin.String', condition)
        choices = json.loads((skin / 'resources/ui-preferences.json').read_text(encoding='utf-8'))['YoPlayerTheme']['choices']
        self.assertEqual(choices, ['', 'classic', 'ink', 'graphite', 'mist', 'ocean', 'sand'])


class UpgradeNoticeChecks(unittest.TestCase):
    def setUp(self):
        self.visible = {'Window.IsActive(home)': True}
        self.saved = ''
        self.props = {}
        self.commands = []
        self.notice = Mock()
        home = types.SimpleNamespace(getProperty=lambda k: self.props.get(k, ''),
                                     setProperty=lambda k, v: self.props.__setitem__(k, v),
                                     clearProperty=lambda k: self.props.pop(k, None))
        xbmc = types.SimpleNamespace(getCondVisibility=lambda k: self.visible.get(k, False),
                                     getInfoLabel=lambda k: self.saved,
                                     executebuiltin=self.commands.append)
        gui = types.SimpleNamespace(Window=lambda n: home, NOTIFICATION_INFO='info',
                                    Dialog=lambda: types.SimpleNamespace(notification=self.notice))
        api = patch.dict(sys.modules, xbmc=xbmc, xbmcgui=gui)
        api.start()
        self.addCleanup(api.stop)
        path = ROOT / 'source/skin.yoplayer.infuse/scripts/infuse_preferences.py'
        spec = importlib.util.spec_from_file_location('theme_preferences_fixture', path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

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
