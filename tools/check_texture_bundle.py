"""Verify XBTF2 pixels against loose images; preserve bundle-only legacy assets.

Default invocation is read-only. --sync-themes is an explicit authoring action
that updates theme images in the existing bundle, never rebuilds from loose
images alone. Requires tools/requirements-checks.txt; never contacts Kodi.
"""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import struct

import lzokay
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FRAME = struct.Struct('<IIIQQIQ')
IMAGES = {'.png', '.jpg', '.jpeg'}


def parse(raw):
    if raw[:5] != b'XBTF2' or len(raw) < 9:
        raise ValueError('Unsupported or truncated texture bundle')
    count = struct.unpack_from('<I', raw, 5)[0]
    if not 0 < count <= 10000:
        raise ValueError('Invalid bundle entry count')
    cursor, entries = 9, {}
    for _ in range(count):
        if cursor + 264 > len(raw):
            raise ValueError('Truncated bundle path header')
        path = raw[cursor:cursor + 256]
        if b'\0' not in path:
            raise ValueError('Unterminated bundle path')
        name = path.split(b'\0', 1)[0].decode('utf-8')
        if (not name or name != name.lower() or '\\' in name or
                name.startswith('/') or '..' in name.split('/') or name in entries):
            raise ValueError('Invalid or duplicate bundle path: ' + name)
        loop, count_frames = struct.unpack_from('<II', raw, cursor + 256)
        cursor += 264
        if not 0 < count_frames <= 10000 or cursor + count_frames * FRAME.size > len(raw):
            raise ValueError('Invalid frame count: ' + name)
        frames = []
        for _ in range(count_frames):
            frame = FRAME.unpack_from(raw, cursor)
            cursor += FRAME.size
            width, height, fmt, packed, unpacked, duration, offset = frame
            if (not 0 < width <= 32768 or not 0 < height <= 32768 or not packed or
                    not 0 < unpacked <= 256 * 1024 * 1024 or offset + packed > len(raw)):
                raise ValueError('Invalid frame bounds: ' + name)
            frames.append((frame, raw[offset:offset + packed]))
        entries[name] = (loop, frames)
    if any(f[-1] < cursor for _, frames in entries.values() for f, _ in frames):
        raise ValueError('Frame overlaps bundle header')
    return entries


def encode(entries):
    """Relocate payloads without recompressing preserved frames."""
    cursor = 9 + sum(264 + FRAME.size * len(frames) for _, frames in entries.values())
    header = bytearray(b'XBTF2' + struct.pack('<I', len(entries)))
    payload, offsets = bytearray(), {}
    for name, (loop, frames) in entries.items():
        path = name.encode('utf-8')
        if len(path) >= 256:
            raise ValueError('Bundle path too long')
        header.extend(path.ljust(256, b'\0'))
        header.extend(struct.pack('<II', loop, len(frames)))
        for frame, data in frames:
            if data not in offsets:
                offsets[data] = cursor
                payload.extend(data)
                cursor += len(data)
            header.extend(FRAME.pack(*frame[:-1], offsets[data]))
    return bytes(header + payload)


def pixels(entry):
    _, frames = entry
    if len(frames) != 1:
        raise ValueError('Static loose image shadows an animated bundle entry')
    (width, height, fmt, packed, unpacked, _, _), data = frames[0]
    if fmt & 0xffff != 0x10 or unpacked != width * height * 4:
        raise ValueError('Expected BGRA8 frame')
    raw = lzokay.decompress(data, unpacked) if packed != unpacked else data
    if len(raw) != unpacked:
        raise ValueError('Decompressed frame length mismatch')
    return (width, height), raw


def image_pixels(raw):
    with Image.open(BytesIO(raw)) as source:
        if getattr(source, 'n_frames', 1) != 1:
            raise ValueError('Animated loose image requires a frame-aware check')
        image = source.convert('RGBA')
        return image.size, image.tobytes('raw', 'BGRA')


def loose_files(media):
    result = {}
    for path in media.rglob('*'):
        if not path.is_file() or path.suffix.lower() not in IMAGES:
            continue
        name = path.relative_to(media).as_posix().lower()
        if name in result:
            raise ValueError('Case-colliding loose texture: ' + name)
        result[name] = path
    return result


def check(root=ROOT):
    skin = root / 'source/skin.yoplayer.infuse'
    media = skin / 'media'
    entries = parse((media / 'Textures.xbt').read_bytes())
    loose = loose_files(media)
    exceptions = json.loads((root / 'tools/texture-check-baseline.json').read_text(encoding='utf-8'))['exceptions']
    spec = json.loads((skin / 'resources/themes.json').read_text(encoding='utf-8'))
    for alias in spec.get('aliases', {}):
        prefix = 'infuse/themes/' + alias + '/'
        if any(n.startswith(prefix) for n in entries):
            raise ValueError('Retired theme remains bundled: ' + alias)
    themes = {n for n in loose if n.startswith(('infuse/themes/', 'infuse/theme-ui/'))}
    bundled_themes = {n for n in entries if n.startswith(('infuse/themes/', 'infuse/theme-ui/'))}
    if bundled_themes - themes:
        raise ValueError('Bundled theme image has no loose source: ' + ', '.join(sorted(bundled_themes - themes)))
    if themes - entries.keys():
        raise ValueError('Theme image not bundled: ' + ', '.join(sorted(themes - entries.keys())))
    accepted = []
    for name in sorted(entries.keys() & loose.keys()):
        data = loose[name].read_bytes()
        actual = pixels(entries[name])
        if actual == image_pixels(data):
            continue
        baseline = {'bundle_size': list(actual[0]),
                    'bundle_bgra_sha256': hashlib.sha256(actual[1]).hexdigest(),
                    'loose_sha256': hashlib.sha256(data).hexdigest()}
        if name.startswith('infuse/themes/') or exceptions.get(name) != baseline:
            raise ValueError('XBT/loose image pixels differ: ' + name)
        accepted.append(name)
    if set(accepted) != set(exceptions):
        raise ValueError('Texture exception list is stale; review it explicitly')
    return {'status': 'passed', 'bundle_entries': len(entries),
            'same_path_images_checked': len(entries.keys() & loose.keys()),
            'theme_images_checked': len(themes), 'legacy_exceptions': accepted,
            'bundle_only_entries_preserved': len(entries.keys() - loose.keys())}


def sync_themes(root=ROOT):
    skin = root / 'source/skin.yoplayer.infuse'
    target = skin / 'media/Textures.xbt'
    before = target.read_bytes()
    original = parse(before)
    loose = loose_files(skin / 'media')
    spec = json.loads((skin / 'resources/themes.json').read_text(encoding='utf-8'))
    prefixes = tuple('infuse/themes/' + n + '/' for n in spec.get('aliases', {}))
    retired = {n for n in original if prefixes and n.startswith(prefixes)}
    result = {n: e for n, e in original.items() if n not in retired}
    updated, added = [], []
    targets = {n for n in loose if n.startswith(('infuse/themes/', 'infuse/theme-ui/'))}
    targets.update(('infuse/progress_fill_white.png', 'infuse/home/focus-ring.png'))
    for name in sorted(targets):
        size, raw = image_pixels(loose[name].read_bytes())
        if name in result and pixels(result[name]) == (size, raw):
            continue
        compressed = lzokay.compress(raw)
        payload = compressed if len(compressed) < len(raw) else raw
        opaque = all(raw[i] == 255 for i in range(3, len(raw), 4))
        frame = (*size, 0x10010 if opaque else 0x10, len(payload), len(raw), 0, 0)
        (updated if name in result else added).append(name)
        result[name] = (0, [(frame, payload)])
    if not (retired or updated or added):
        return {'status': 'current', 'updated': [], 'added': [], 'retired': []}
    rebuilt = encode(result)
    parsed = parse(rebuilt)
    def unchanged(entry):
        loop, frames = entry
        return loop, [(f[:-1], data) for f, data in frames]
    for name in original.keys() - retired - set(updated):
        if unchanged(original[name]) != unchanged(parsed[name]):
            raise ValueError('Unrelated packed entry changed: ' + name)
    for name in targets:
        if pixels(parsed[name]) != image_pixels(loose[name].read_bytes()):
            raise ValueError('Repacked pixels differ: ' + name)
    if target.read_bytes() != before:
        raise ValueError('Bundle changed concurrently')
    temporary = target.with_suffix('.xbt.tmp')
    with temporary.open('xb') as stream:
        stream.write(rebuilt)
    temporary.replace(target)
    return {'status': 'updated', 'updated': updated, 'added': added, 'retired': sorted(retired),
            'preserved_original_entries': len(original) - len(retired) - len(updated),
            'sha256': hashlib.sha256(rebuilt).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sync-themes', action='store_true', help='Explicitly update theme entries in the existing XBT.')
    args = parser.parse_args()
    print(json.dumps(sync_themes() if args.sync_themes else check(), ensure_ascii=False, indent=2))
