"""Verify page integration, literal native masks and resume display boundaries."""
import importlib.util
import json
import math
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SKIN = ROOT / 'source/skin.yoplayer.infuse'
PAGES = ['SkinSettings.xml', 'Settings.xml', 'SettingsCategory.xml', 'AddonBrowser.xml',
         'DialogAddonSettings.xml', 'DialogVideoInfo.xml', 'YoPlayerHomeSheet.xml',
         'YoPlayerLibraryMenu.xml', 'YoPlayerQuickMenu.xml', 'YoPlayerReorder.xml',
         'Custom_1144_OSD_subtitles.xml', 'Custom_1145_OSD_audio.xml', 'custom_OptionsDialog.xml']


def page_bindings(path):
    root = ET.parse(path).getroot()
    colours = [n.text or '' for n in root.iter() if n.tag in ('textcolor', 'focusedcolor', 'disabledcolor', 'selectedcolor')]
    visible = [c for c in colours if c and not re.fullmatch(r'00[0-9a-fA-F]{6}', c)]
    missing = [c for c in visible if not c.startswith(('$VAR[', '$PARAM[')) and c not in ('red', 'invalid', 'gold', 'orange') and c.upper() not in ('FFE5484D',)]
    if missing:
        raise ValueError(path.name + ': fixed text colours ' + repr(sorted(set(missing))))
    if not any('$VAR[YoPlayerUi_' in c or '$VAR[YoPlayerOverlay_' in c for c in colours):
        raise ValueError(path.name + ': page not connected to semantic roles')
    return root


class CoverageChecks(unittest.TestCase):
    def test_primary_pages_use_semantic_colours(self):
        for name in PAGES:
            with self.subTest(page=name):
                page_bindings(SKIN / '1080p' / name)

    def test_old_unintegrated_settings_is_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.xml'
            path.write_text('<window><textcolor>infuse_ink_light</textcolor></window>')
            with self.assertRaisesRegex(ValueError, 'fixed text colours'):
                page_bindings(path)

    def test_native_masks_are_literal_neutral_and_tinted(self):
        spec = json.loads((SKIN / 'resources/theme-ui.json').read_text())['masks']
        referenced = set()
        for path in (SKIN / '1080p').glob('*.xml'):
            if path.name == 'Includes_YoPlayer_Themes.xml':
                continue
            for n in ET.parse(path).getroot().iter():
                value = (n.text or '').strip()
                if n.tag.startswith('texture') or n.tag.startswith('alttexture') or n.tag in ('midtexture', 'bordertexture'):
                    if value.startswith('infuse/theme-ui/'):
                        self.assertIn(value, spec)
                        referenced.add(value)
                        self.assertRegex(n.get('colordiffuse', ''), r'^\$VAR\[YoPlayer(?:Ui|Overlay)_[a-z]+(?:_[0-9A-F]{2})?\]$')
        self.assertGreater(len(referenced), 100)
        for name in spec:
            image = Image.open(SKIN / 'media' / name).convert('RGBA')
            self.assertEqual(image.getchannel('R').getextrema(), (255, 255))
            self.assertEqual(image.getchannel('G').getextrema(), (255, 255))
            self.assertEqual(image.getchannel('B').getextrema(), (255, 255))

    def test_no_old_blue_panel_or_fixed_cyan_confirm(self):
        for name in ('Custom_1144_OSD_subtitles.xml', 'Custom_1145_OSD_audio.xml', 'custom_OptionsDialog.xml', 'DialogConfirm.xml'):
            text = (SKIN / '1080p' / name).read_text()
            self.assertNotIn('F51B2630', text)
            self.assertNotIn('FF65DCE7', text)

    def test_coreelec_settings_mark_is_foreground(self):
        root = ET.parse(SKIN / '1080p/service-CoreELEC-Settings-mainWindow.xml').getroot()
        node = next(n for n in root.iter('texture') if n.text == 'infuse/theme-ui/ce_window_private/logo.png')
        self.assertEqual(node.get('colordiffuse'), '$VAR[YoPlayerUi_text]')

    def test_every_theme_has_page_and_playback_roles(self):
        import build_theme_xml as generator
        data = generator.spec()
        root = ET.fromstring(generator.render((SKIN / '1080p/Includes_YoPlayer_Themes.xml').read_text(), data))
        for family in ('Ui', 'Overlay'):
            for role in ('bg', 'surface', 'text', 'muted', 'focus', 'state'):
                node = root.find("variable[@name='YoPlayer" + family + '_' + role + "']")
                self.assertIsNotNone(node)
                self.assertIsNone(node.findall('value')[-1].get('condition'))
                for ident in ('ink', 'graphite', 'mist', 'ocean'):
                    self.assertTrue(any('$EXP[YoPlayerThemeIs_' + ident + ']' == v.get('condition') for v in node))
        self.assertEqual(root.find("expression[@name='YoPlayerThemeScope']").text, 'true')

    def test_playback_glass_is_neutral_in_every_theme(self):
        import build_theme_xml as generator
        root = ET.fromstring(generator.render((SKIN / '1080p/Includes_YoPlayer_Themes.xml').read_text(), generator.spec()))
        for role in ('bg', 'surface', 'text', 'muted', 'focus', 'state'):
            values = root.find("variable[@name='YoPlayerOverlay_" + role + "']").findall('value')
            self.assertEqual(len({v.text for v in values}), 1, role)
        self.assertEqual(root.find("variable[@name='YoPlayerOverlay_panel']/value").text, 'FF191E24')
        glass = Image.open(SKIN / 'media/infuse/theme-ui/glass90/unified-panel-border20.png').convert('RGBA')
        self.assertEqual(glass.getpixel((glass.width // 2, glass.height // 2))[3], 166)

    def test_playback_primary_panels_use_transparent_glass(self):
        for name in ('Custom_1144_OSD_subtitles.xml', 'Custom_1145_OSD_audio.xml',
                     'Includes_Infuse_OSD.xml', 'Custom_1140_OSD_Playlist.xml',
                     'Custom_1142_OSD_Cast.xml', 'VideoOSDBookmarks.xml',
                     'Custom_1121_skipintro.xml', 'Custom_1122_skipend.xml',
                     'custom_1141_VS10.xml', 'custom_PlaySpeed.xml', 'DialogPlayerProcessInfo.xml'):
            text = (SKIN / '1080p' / name).read_text()
            self.assertIn('$VAR[YoPlayerOverlay_panel]', text, name)
            self.assertNotIn('$VAR[YoPlayerUi_', text, name)
            self.assertNotIn('infuse/theme-ui/plana/panel.png</texture>', text, name)

    def test_image_list_selected_tag_does_not_overlap_title(self):
        root = ET.parse(SKIN / '1080p/IncludesDialogSelect.xml').find("include[@name='DialogDefaultSelectLayout']")
        listing = root.find(".//control[@id='6']")
        for name in ('itemlayout', 'focusedlayout'):
            layout = listing.find(name)
            marker = next(c for c in layout.findall('control') if c.findtext('label') == '当前')
            title = next(c for c in layout.findall('control') if 'ListItem.Label]' in (c.findtext('label') or ''))
            self.assertLessEqual(int(title.findtext('left')) + int(title.findtext('width')), int(marker.findtext('left')))
            self.assertEqual(marker.findtext('visible'), 'ListItem.IsSelected + !Control.IsVisible(5)')
            self.assertEqual(marker.findtext('selectedcolor'), marker.findtext('textcolor'))
            self.assertTrue(any(c.findtext('label') == '已选' for c in layout.findall('control')))

    def test_light_detail_body_never_uses_dark_badge_foreground(self):
        root = ET.parse(SKIN / '1080p/DialogVideoInfo.xml').getroot()
        for label in root.iter('control'):
            if label.get('type') not in ('label', 'textbox'):
                continue
            if label.findtext('textcolor') == '$VAR[YoPlayerOverlay_text]':
                self.assertIn('YoPlayer.Rating', label.findtext('label') or '')


class RemainingChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('home_labels', ROOT / 'source/plugin.video.yoplayer.home/resources/lib/home_labels.py')
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_unknown_invalid_complete_and_unstarted_are_hidden(self):
        for value in (None, {}, {'position': 0, 'total': 500}, {'position': -1, 'total': 500},
                      {'position': 500, 'total': 500}, {'position': 600, 'total': 500},
                      {'position': math.nan, 'total': 500}, {'position': 2, 'total': math.inf},
                      {'position': 'bad', 'total': 500}, {'position': True, 'total': 500}):
            with self.subTest(value=value):
                self.assertEqual(self.module.remaining_label(value), '')

    def test_rounds_up_and_does_not_change_resume(self):
        for seconds, text in ((1, '剩余不足 1 分钟'), (59, '剩余不足 1 分钟'), (60, '剩余 1 分钟'), (61, '剩余 2 分钟'), (3300, '剩余 55 分钟')):
            resume = {'position': 200, 'total': 200 + seconds}
            before = dict(resume)
            self.assertEqual(self.module.remaining_label(resume), text)
            self.assertEqual(resume, before)


if __name__ == '__main__':
    unittest.main()
