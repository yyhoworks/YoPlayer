"""Portable checks for actual single-VI assets, colour roles and theme controls.

These checks inspect the candidate; they never rebuild it or touch a device.
Kodi rendering and remote interaction still require separate device evidence.
"""
import json
import hashlib
from zipfile import ZipFile
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SKIN = ROOT / 'source/skin.yoplayer.infuse'
IDS = ['classic', 'mist', 'sand', 'graphite', 'ocean']
EXPECTED = {
    'mist': ['#ECEDF1', '#F5F5F7', '#FFFFFF', '#1D1D1F', '#56565C', '#0A6B54'],
    'sand': ['#E8E2D8', '#F4F0E8', '#FFFBF5', '#292419', '#6B6252', '#8C5E2A'],
    'graphite': ['#141416', '#1D1D1F', '#2C2C2E', '#F5F5F7', '#B5B5BB', '#8FD4C2'],
    'ocean': ['#10161D', '#1A2530', '#243442', '#E8EDF2', '#9AA8B4', '#9CC4E4'],
}


def luminance(hex_colour):
    channels = [int(hex_colour[i:i+2], 16)/255 for i in (1, 3, 5)]
    linear = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in channels]
    return sum(c*w for c, w in zip(linear, (.2126, .7152, .0722)))


def contrast(a, b):
    low, high = sorted([luminance(a), luminance(b)])
    return (high+.05)/(low+.05)


def check_preview_assets(selector, skin=SKIN):
    """Resolve the literal chooser thumbnails, including non-selected cards."""
    actual = [(n.text or '').strip() for n in selector.iter('texture')
              if (n.text or '').strip().endswith('/preview.png')]
    expected = ['infuse/themes/'+name+'/preview.png' for name in IDS]
    assert actual == expected, 'Theme chooser preview bindings differ: '+repr(actual)
    assert all((skin/'media'/name).is_file() for name in actual), 'Missing chooser preview asset'


def check():
    spec = json.loads((SKIN / 'resources/themes.json').read_text(encoding='utf8'))
    assert spec['brand'] == 'y-negative-space' and spec['default'] == 'classic'
    assert spec['brandAuthority']['sha256'] == 'ab0e56ec39550c6940034f72e03774a999a37e62ca5a8f9f5bebec7357a1c74c'
    authority = ROOT / spec['brandAuthority']['file']
    assert hashlib.sha256(authority.read_bytes()).hexdigest() == spec['brandAuthority']['sha256']
    with ZipFile(authority) as vi:
        for path, member in {
            'source/skin.yoplayer.infuse/media/infuse/brand/logo-light.png': 'ppt/media/image-3-3.png',
            'source/skin.yoplayer.infuse/media/infuse/brand/logo-white.png': 'ppt/media/image-3-1.png',
            'source/skin.yoplayer.infuse/resources/icon.png': 'ppt/media/image-11-1.png',
            'source/plugin.video.yoplayer.home/resources/icon.png': 'ppt/media/image-11-1.png',
        }.items():
            assert (ROOT/path).read_bytes() == vi.read(member), 'Runtime VI differs from authority: '+path
    themes = spec['themes']
    assert [t['id'] for t in themes] == IDS
    evidence = []
    for theme in themes[1:]:
        ident = theme['id']
        assert [theme[r] for r in ('bg', 'surface', 'hover', 'text', 'secondary', 'accent')] == EXPECTED[ident]
        for background in ('bg', 'surface', 'hover'):
            for foreground in ('text', 'secondary', 'accentText'):
                ratio = contrast(theme[foreground], theme[background])
                assert ratio >= 4.5, (ident, foreground, background, ratio)
                evidence.append({'theme': ident, 'foreground': foreground, 'background': background, 'ratio': round(ratio, 3)})
            assert contrast(theme['accent'], theme[background]) >= 3
        assert contrast(theme['onAccent'], theme['accentFill']) >= 3
    include = ET.parse(SKIN / '1080p/Includes_YoPlayer_Themes.xml').getroot()
    variables = {v.get('name'): v for v in include.findall('variable')}
    assert len(variables) == len(include.findall('variable'))
    prefixes = ['infuse/'] + ['infuse/themes/' + name + '/' for name in IDS[1:]]
    for path in (SKIN / '1080p').glob('*.xml'):
        root = ET.parse(path).getroot()
        for node in root.iter():
            for value in [node.text or '', *node.attrib.values()]:
                for name in re.findall(r'\$VAR\[(YoPlayerTheme[^\],]+)', value):
                    assert name in variables, (path.name, name)
                if value.startswith('$VAR[YoPlayerThemeAssets]'):
                    relative = value[len('$VAR[YoPlayerThemeAssets]'):]
                    assert all((SKIN / 'media' / (prefix+relative)).is_file() for prefix in prefixes), (path.name, value)
    selector = ET.parse(SKIN / '1080p/custom_1187_ThemeColors.xml').getroot()
    check_preview_assets(selector, SKIN)
    assert selector.get('id') == '1187' and selector.findtext('defaultcontrol') == '6201'
    assert selector.findtext('onunload') == 'ClearProperty(YoPlayer.Theme.Preview,home)'
    for i, theme in enumerate(themes, 6201):
        node = selector.find('.//control[@id="' + str(i) + '"]')
        assert node is not None
        assert node.findtext('onfocus') == 'SetProperty(YoPlayer.Theme.Preview,' + theme['id'] + ',home)'
        actions = [n.text for n in node.findall('onclick')]
        required_actions = [
            'Skin.Reset(YoPlayerTheme)' if i == 6201 else 'Skin.SetString(YoPlayerTheme,' + theme['id'] + ')',
            'ClearProperty(YoPlayer.Theme.Preview,home)', 'Dialog.Close(1187)']
        assert actions in (required_actions, required_actions + ['ReloadSkin()'])
        assert node.findtext('onback') == 'Dialog.Close(1187)'
        for key in ('onleft', 'onright', 'onup', 'ondown'):
            assert selector.find('.//control[@id="' + node.findtext(key) + '"]') is not None
        assert (SKIN / 'media/infuse/themes' / theme['id'] / 'preview.png').is_file()
    cancel = selector.find('.//control[@id="6211"]')
    assert [n.text for n in cancel.findall('onclick')] == ['Dialog.Close(1187)']
    schema = json.loads((SKIN / 'resources/ui-preferences.json').read_text(encoding='utf8'))
    assert schema['YoPlayerTheme'] == {'type': 'string', 'scope': 'appearance', 'default': '',
                                      'choices': ['', *IDS]}
    row = ET.parse(SKIN / '1080p/SkinSettings.xml').find('.//control[@id="11969"]')
    assert row.findtext('onclick') == 'ActivateWindow(1187)' and row.findtext('label2') == '$VAR[YoPlayerThemeName]'
    # Preview uses only GUI events; a confirmed preset reloads once so native
    # texture properties are reconstructed with literal filenames.
    for node in selector.iter():
        assert not any(k in (node.text or '') for k in ('RunScript', 'UpdateLibrary', 'PlayerControl'))
        if (node.text or '') == 'ReloadSkin()':
            assert node.tag == 'onclick'
    reload_count = len(selector.findall('.//onclick[.="ReloadSkin()"]'))
    assert reload_count in (0, 6)
    definitions = ET.parse(SKIN/'1080p/Includes_YoPlayer_ThemeTextures.xml').getroot()
    texture_defs = {n.get('name'): n for n in definitions.findall('include')}
    assert len(texture_defs) == len(definitions)
    used = set()
    for path in (SKIN/'1080p').glob('*.xml'):
        for node in ET.parse(path).getroot().iter():
            value = (node.text or '').strip()
            if node.tag == 'include' and value.startswith('YoPlayerThemeNative_'):
                assert value in texture_defs and node.get('condition')
                used.add(value)
            if (node.tag.startswith('texture') and node.tag != 'texture' or node.tag in ('midtexture', 'bordertexture')):
                assert '$VAR[YoPlayerThemeAssets]' not in value, (path.name, node.tag, value)
                if value.startswith('infuse/themes/'):
                    assert (SKIN/'media'/value).is_file(), (path.name, value)
    assert used == set(texture_defs)
    if reload_count == 0:
        assert not texture_defs, 'No-reload presets require dynamically resolved image surfaces and fixed native bindings'
    return {'status': 'passed', 'themes': IDS, 'current_XML_inspected': True,
            'colour_contrasts': evidence, 'Kodi_UI_acceptance': 'separate-required'}


if __name__ == '__main__':
    result = check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
