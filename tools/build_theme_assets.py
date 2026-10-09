"""Build the four approved static theme sets. Explicit authoring tool only.

The classic resources remain the source for masks and sizes. This tool does not
rebuild XML, package, deploy, connect to Kodi or change user preferences.
"""
from io import BytesIO
import json
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SKIN = ROOT / 'source/skin.yoplayer.infuse'

# Content artwork, media flags, fonts, gradients over video, and licensed icon
# geometry are deliberately excluded. These are UI surfaces or monochrome icons.
SURFACES = {
    'home_background.png': 'bg',
    'capsule_white.png': 'focus_fill', 'circle_white.png': 'focus_fill',
    'glass_capsule_dark.png': 'surface', 'glass_capsule_light.png': 'surface',
    'glass_circle_dark.png': 'surface', 'glass_circle_light.png': 'surface',
    'glass_card_dark.png': 'surface',
    'home/dashboard.png': 'surface', 'home/device.png': 'hover',
    'home/white.png': 'hover', 'home/close-focus.png': 'focus',
    'home/focus-72.png': 'outline', 'home/focus-188.png': 'outline',
    'home/row.png': 'surface', 'home/row-focus.png': 'focus',
    'settings_final/card.png': 'surface', 'settings_final/row.png': 'surface',
    'settings_final/focus.png': 'focus',
    'settings_a/dialog.png': 'surface', 'settings_a/row.png': 'surface',
    'settings_a/row_focus.png': 'focus',
    'settings_a/switch_on.png': 'switch_on', 'settings_a/switch_off.png': 'switch_off',
    'mute64/switch-on.png': 'switch_on', 'mute64/switch-off.png': 'switch_off',
    'stage1_management/panel.png': 'surface', 'stage1_management/row.png': 'surface',
    'stage1_management/focus.png': 'focus', 'stage1_management/field.png': 'surface',
    'stage1_management/scroll.png': 'line', 'stage1_management/scroll_focus.png': 'accentFill',
    'stage1_utility/panel.png': 'surface', 'stage1_utility/row.png': 'surface',
    'stage1_utility/focus.png': 'focus', 'stage1_utility/on.png': 'switch_on',
    'stage1_utility/off.png': 'switch_off',
    'stage1_utility/seek_bar.png': 'accentFill',
    'stage1_utility/seek_nib.png': 'text', 'stage1_utility/seek_nib_focus.png': 'accentFill',
    'stage2_views/panel.png': 'surface', 'stage2_views/row.png': 'surface',
    'stage2_views/focus.png': 'focus',
    'detail_dialogs/panel.png': 'surface', 'detail_dialogs/row.png': 'surface',
    'detail_dialogs/focus.png': 'focus', 'detail_dialogs/field.png': 'surface',
    'detail_dialogs/scroll.png': 'line', 'detail_dialogs/scroll_focus.png': 'accentFill',
    'unified/panel.png': 'surface', 'unified/row.png': 'surface', 'unified/focus.png': 'focus',
    'stream59/panel.png': 'surface', 'osd_d/drawer.png': 'surface',
    'osd_d/row.png': 'focus', 'osd_d/circle.png': 'surface', 'osd_d/circle_focus.png': 'focus',
    'progress_track.png': 'line', 'progress_fill.png': 'accentFill',
    'tab_pill.png': 'surface', 'tab_pill_white.png': 'focus',
    'reorder/moving-border.png': 'outline', 'badge_unwatched.png': 'accentFill',
}

for height in (48, 50, 54, 56, 60):
    SURFACES[f'visual47/pill-glass-{height}.png'] = 'focus'
for height in (54, 56, 66, 68):
    SURFACES[f'visual47/pill-light-{height}.png'] = 'focus'
for height in (62, 72, 80):
    SURFACES[f'visual47/pill-white-{height}.png'] = 'focus'
ICONS = ('circle-play', 'cog', 'hard-drive', 'info', 'library', 'network', 'palette',
         'panels-top-left', 'puzzle', 'tv-minimal', 'folder-plus', 'refresh-cw',
         'search', 'wrench')
for icon in ICONS:
    SURFACES[f'settings_final/{icon}.png'] = 'text'
for icon in ('up', 'up_focus', 'down', 'down_focus'):
    SURFACES[f'settings_a/{icon}.png'] = 'text'
for icon in ('arrow-up-focus', 'arrow-down-focus', 'arrow-right'):
    SURFACES[f'theme/{icon}.png'] = 'text'


def png(im):
    out = BytesIO()
    im.save(out, 'PNG', compress_level=9)
    return out.getvalue()


def native_focus(fill, rim, fill_alpha=31, rim_alpha=255, size=128, radius=16):
    """Native 60px rows use border20: keep every curved pixel inside it."""
    scale = 8
    im = Image.new('RGBA', (size*scale, size*scale))
    from PIL import ImageColor
    ImageDraw.Draw(im).rounded_rectangle(
        (scale, scale, (size-1)*scale-1, (size-1)*scale-1), radius=radius*scale,
        fill=ImageColor.getrgb(fill)+(fill_alpha,),
        outline=ImageColor.getrgb(rim)+(rim_alpha,), width=2*scale)
    return png(im.resize((size, size), Image.Resampling.LANCZOS))


def recolour(raw, name, role, palette):
    original = Image.open(BytesIO(raw)).convert('RGBA')
    w, h = original.size
    if role == 'bg':
        return png(Image.new('RGB', (w, h), palette['bg']))
    if role.startswith('switch_'):
        scale = 4
        im = Image.new('RGBA', (w*scale, h*scale))
        d = ImageDraw.Draw(im)
        pad = 2*scale
        colour = palette['accentFill'] if role == 'switch_on' else palette['line'] if palette['dark'] else palette['secondary']
        d.rounded_rectangle((pad, pad, w*scale-pad-1, h*scale-pad-1),
                            radius=(h*scale-2*pad)//2, fill=colour)
        radius = (h*scale)//2-5*scale
        cx = w*scale-h*scale//2 if role == 'switch_on' else h*scale//2
        cy = h*scale//2
        handle = palette['onAccent'] if role == 'switch_on' else '#F5F5F7' if palette['dark'] else '#FFFFFF'
        d.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), fill=handle)
        return png(im.resize((w, h), Image.Resampling.LANCZOS))
    alpha = original.getchannel('A')
    if role == 'outline':
        im = Image.new('RGBA', (w, h), palette['accent'])
        im.putalpha(alpha)
        return png(im)
    if role == 'focus':
        # A finite static outline; no new controls or animations are required.
        scale = 4
        im = Image.new('RGBA', (w, h), palette['hover'])
        im.putalpha(alpha)
        im = im.resize((w*scale, h*scale), Image.Resampling.NEAREST)
        box = alpha.getbbox()
        if box:
            x0, y0, x1, y1 = box
            box = (x0*scale, y0*scale, (x1-1)*scale, (y1-1)*scale)
            round_shape = any(k in name for k in ('pill', 'capsule', 'circle', 'focus-72', 'focus-188'))
            rad = (y1-y0)//2 if round_shape else min(32, (y1-y0)//4)
            d = ImageDraw.Draw(im)
            d.rounded_rectangle(box, radius=rad*scale,
                                fill=None,
                                outline=palette['accent'], width=2*scale)
        return png(im.resize((w, h), Image.Resampling.LANCZOS))
    colour = palette['hover'] if role == 'focus_fill' else palette[role]
    im = Image.new('RGBA', (w, h), colour)
    # Retain the incumbent glass, antialiasing and rim opacity. A colour preset
    # changes pigment, never turns translucent glass into an opaque flat slab.
    im.putalpha(alpha)
    return png(im)


def thumbnail(palette, logo):
    im = Image.new('RGB', (520, 292), palette['bg'])
    d = ImageDraw.Draw(im)
    mark = Image.open(BytesIO(logo)).convert('RGBA')
    mark.thumbnail((100, 40))
    im.paste(mark, (24, 19), mark)
    for x in (388, 420, 452, 484):
        d.ellipse((x-9, 25, x+9, 43), fill=palette['surface'])
    # Thumbnail demonstrates only interface roles, with neutral media areas.
    for y in (90, 188):
        for x in (24, 184, 344):
            d.rounded_rectangle((x, y, x+150, y+72), radius=6, fill=palette['surface'])
            d.line((x+46, y+82, x+104, y+82), fill=palette['secondary'], width=3)
    d.ellipse((379, 16, 405, 50), outline=palette['accent'], width=2)
    return png(im)


def material_assets(palettes, classic):
    """Final material scope: no added rims; preserve composite arrow semantics.

    Historical payload stays unchanged for its immutable migration proofs.
    This explicit current-authoring override supplies the reviewed new assets.
    """
    from PIL import ImageColor
    result = {}
    for theme in palettes[1:]:
        prefix = 'skin.yoplayer.infuse/media/infuse/themes/' + theme['id'] + '/'
        for name, role in SURFACES.items():
            raw = classic['skin.yoplayer.infuse/media/infuse/' + name]
            if role == 'outline' or name.startswith('glass_'):
                result[prefix + name] = raw
            elif role == 'focus':
                base = Image.open(BytesIO(raw)).convert('RGBA')
                image = Image.new('RGBA', base.size, theme['hover'])
                image.putalpha(base.getchannel('A'))
                result[prefix + name] = png(image)
            elif name in ('settings_a/up_focus.png', 'settings_a/down_focus.png'):
                base = Image.open(BytesIO(raw)).convert('RGBA')
                bg, fg = ImageColor.getrgb(theme['hover']), ImageColor.getrgb(theme['text'])
                pixels = []
                for r,g,b,a in base.getdata():
                    ratio = (r+g+b)/(3*255)
                    pixels.append(tuple(round(fg[i]*(1-ratio)+bg[i]*ratio) for i in range(3))+(a,))
                base.putdata(pixels)
                result[prefix + name] = png(base)
        base = Image.open(BytesIO(classic['skin.yoplayer.infuse/media/infuse/settings_a/row_focus.png'])).convert('RGBA')
        size, scale = base.width, 8
        image = Image.new('RGBA', (size*scale,size*scale))
        ImageDraw.Draw(image).rounded_rectangle((0,0,size*scale-1,size*scale-1),radius=16*scale,fill=ImageColor.getrgb(theme['hover'])+(255,))
        result[prefix+'settings_a/row_focus.png'] = png(image.resize((size,size),Image.Resampling.LANCZOS))
        base = Image.open(BytesIO(classic['skin.yoplayer.infuse/media/infuse/detail_dialogs/focus.png'])).convert('RGBA')
        # These white material rims exist in classic65; do not add an accent rim.
        result[prefix+'detail_dialogs/focus.png'] = native_focus('#FFFFFF','#FFFFFF',fill_alpha=32,size=base.width,radius=8)
        result[prefix+'unified/native-focus.png'] = native_focus('#FFFFFF','#FFFFFF',rim_alpha=245)
    return result


def payload(palettes, classic, logos):
    """Pure output function also used by the scope checks before packaging."""
    result = {}
    for theme in palettes:
        if theme['id'] == 'classic':
            continue
        prefix = 'skin.yoplayer.infuse/media/infuse/themes/' + theme['id'] + '/'
        for name, role in SURFACES.items():
            key = 'skin.yoplayer.infuse/media/infuse/' + name
            if key not in classic:
                raise ValueError('Missing classic shape: ' + name)
            result[prefix + name] = recolour(classic[key], name, role, theme)
        result[prefix + 'preview.png'] = thumbnail(theme, logos[theme['dark']])
    return result


def main():
    data = json.loads((SKIN / 'resources/themes.json').read_text(encoding='utf8'))
    classic = {'skin.yoplayer.infuse/media/infuse/' + n:
               (SKIN / 'media/infuse' / n).read_bytes() for n in SURFACES}
    logos = {False: (SKIN / 'media/infuse/brand/logo-light.png').read_bytes(),
             True: (SKIN / 'media/infuse/brand/logo-white.png').read_bytes()}
    files = payload(data['themes'], classic, logos)
    for name, raw in files.items():
        path = ROOT / 'source' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    classic_theme = data['themes'][0]
    (SKIN / 'media/infuse/themes/classic').mkdir(exist_ok=True)
    (SKIN / 'media/infuse/themes/classic/preview.png').write_bytes(thumbnail(classic_theme, logos[False]))
    (SKIN / 'media/infuse/unified/native-focus.png').write_bytes(native_focus('#FFFFFF', '#FFFFFF', rim_alpha=245))
    for theme in data['themes']:
        if theme['id'] != 'classic':
            (SKIN / 'media/infuse/themes' / theme['id'] / 'unified/native-focus.png').write_bytes(native_focus(theme['hover'], theme['accent']))
            for name, radius in [('settings_a/row_focus.png',16),('detail_dialogs/focus.png',8)]:
                base=Image.open(SKIN / 'media/infuse' / name).convert('RGBA')
                size=base.width
                alpha=base.getpixel((size//2,size//2))[3]
                (SKIN / 'media/infuse/themes' / theme['id'] / name).write_bytes(native_focus(theme['hover'],theme['accent'],fill_alpha=alpha,size=size,radius=radius))
    for name, raw in material_assets(data['themes'],classic).items():
        (ROOT/'source'/name).write_bytes(raw)
    print(json.dumps({'static_theme_files': len(files) + 1, 'theme_ids': [t['id'] for t in data['themes']]}))


if __name__ == '__main__':
    main()
