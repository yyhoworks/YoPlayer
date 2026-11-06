"""Build colour-free masks for the existing skin's semantic UI bindings."""
from io import BytesIO
import json
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps


def inner_outline(alpha, stroke=2):
    """Keep the rim inside the artwork mask, with an empty centre."""
    padded = ImageOps.expand(alpha, border=stroke, fill=0)
    inner = padded.filter(ImageFilter.MinFilter(stroke * 2 + 1))
    inner = inner.crop((stroke, stroke, stroke + alpha.width, stroke + alpha.height))
    return ImageChops.subtract(alpha, inner)


def outputs(skin):
    spec = json.JSONDecoder().decode((skin / 'resources/theme-ui.json').read_text(encoding='utf-8'))
    result = {}
    bundled = None
    for name, item in spec['masks'].items():
        path = skin / 'media' / item['source']
        if path.is_file():
            source = Image.open(path).convert('RGBA')
        else:
            # Some inherited native shapes have only ever existed in XBT.
            # Read those original entries without altering or re-encoding them.
            from check_texture_bundle import parse, pixels
            if bundled is None:
                bundled = parse((skin / 'media/Textures.xbt').read_bytes())
            size, raw = pixels(bundled[item['source'].lower()])
            source = Image.frombytes('RGBA', size, raw, 'raw', 'BGRA')
        alpha = source.getchannel('A')
        if item['mask'] == 'hollow':
            alpha = inner_outline(alpha)
        elif item['mask'] == 'focus':
            # An opaque rim plus a light fill works with both light and dark
            # text. Its native filename is fixed and colour changes live.
            scale = 4
            w, h = source.size
            mask = Image.new('L', (w*scale, h*scale))
            box = alpha.getbbox()
            if box:
                x0, y0, x1, y1 = box
                b = (x0*scale, y0*scale, (x1-1)*scale, (y1-1)*scale)
                pill = any(k in name for k in ('pill', 'capsule', 'circle', 'focus-72', 'focus-188', 'close-focus'))
                radius = min(x1-x0, y1-y0)//2 if pill else min(24, (y1-y0)//4)
                ImageDraw.Draw(mask).rounded_rectangle(b, radius=radius*scale, fill=28, outline=255, width=2*scale)
            alpha = mask.resize(source.size, Image.Resampling.LANCZOS)
        elif item['mask'] == 'switch':
            # Track and handle are two opacity levels of the same pigment.
            # This keeps a clear handle without baking a second theme colour.
            scale=4;w,h=source.size;mask=Image.new('L',(w*scale,h*scale));d=ImageDraw.Draw(mask)
            pad=2*scale
            d.rounded_rectangle((pad,pad,w*scale-pad-1,h*scale-pad-1),radius=h*scale//2,fill=58)
            on = any(k in name for k in ('switch_on','switch-on','utility/on.png'))
            cx=w*scale-h*scale//2 if on else h*scale//2;cy=h*scale//2;r=h*scale//2-5*scale
            d.ellipse((cx-r,cy-r,cx+r,cy+r),fill=255)
            alpha=mask.resize(source.size,Image.Resampling.LANCZOS)
        image = Image.new('RGBA',source.size,'white');image.putalpha(alpha)
        stream=BytesIO();image.save(stream,'PNG',compress_level=9)
        result['skin.yoplayer.infuse/media/'+name]=stream.getvalue()
    return result
