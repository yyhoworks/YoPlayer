"""Portable, offline source checks and addon-only builds for a fresh clone.

These checks complement the full maintainer regressions. They never execute
runtime Python, rebuild source, connect to Kodi, or read historical evidence.
"""
import ast
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
SKIN = 'skin.yoplayer.infuse'
HOME = 'plugin.video.yoplayer.home'
ADDONS = (HOME, SKIN)
# This inherited .xml-named resource is PO translation reference text.
TEXT_REFERENCES = {
    'source/skin.yoplayer.infuse/scripts/R4.xml':
        '667a6d41c2d6977e3624b7ee8e1a39cd52f0b310b7103a3bce53416711e15cfd',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def runtime_files(root=ROOT):
    source = root / 'source'
    if not source.is_dir():
        raise ValueError('Missing source directory')
    if {p.name for p in source.iterdir() if p.is_dir()} != set(ADDONS):
        raise ValueError('Source must contain exactly the two runtime addons')
    files = {}
    for path in sorted(source.rglob('*')):
        if '__pycache__' in path.parts or path.suffix in ('.pyc', '.pyo'):
            continue
        if path.is_symlink():
            raise ValueError('Runtime symlinks are unsupported: ' + path.relative_to(root).as_posix())
        if path.is_file():
            if path.relative_to(source).parts[0] not in ADDONS:
                raise ValueError('Unexpected runtime member')
            files[path.relative_to(root).as_posix()] = path
    return files


def version(value):
    if not value or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)+', value):
        raise ValueError('Invalid numeric addon version')
    return tuple(map(int, value.split('.')))


def check(root=ROOT):
    files = runtime_files(root)
    metadata = {}
    counts = {'python': 0, 'xml': 0, 'json': 0, 'preserved_text_reference': 0}
    for name, path in files.items():
        try:
            if path.suffix == '.py':
                ast.parse(path.read_text(encoding='utf-8-sig'), filename=name)
                counts['python'] += 1
            elif name in TEXT_REFERENCES:
                if digest(path.read_bytes()) != TEXT_REFERENCES[name]:
                    raise ValueError('Inherited translation reference changed')
                counts['preserved_text_reference'] += 1
            elif path.suffix == '.xml':
                ET.parse(path)
                counts['xml'] += 1
            elif path.suffix == '.json':
                json.loads(path.read_text(encoding='utf-8-sig'))
                counts['json'] += 1
        except (SyntaxError, UnicodeError, ValueError, ET.ParseError) as exc:
            raise ValueError('Invalid source syntax: ' + name) from exc

    for addon in ADDONS:
        node = ET.parse(root / 'source' / addon / 'addon.xml').getroot()
        if node.tag != 'addon' or node.get('id') != addon:
            raise ValueError('Unexpected addon ID: ' + addon)
        version(node.get('version'))
        dependencies = {p.get('addon'): p.get('version') for p in node.findall('requires/import')}
        if version(dependencies.get('xbmc.python')) < (3, 0, 0):
            raise ValueError('Python API 3.0.0 is required: ' + addon)
        metadata[addon] = {'version': node.get('version'), 'requires': dependencies}

    skin_requires = metadata[SKIN]['requires']
    if version(skin_requires.get('xbmc.gui')) < (5, 17, 0):
        raise ValueError('GUI API 5.17.0 is required')
    if version(skin_requires.get(HOME)) > version(metadata[HOME]['version']):
        raise ValueError('Skin requires a newer Home version than the bundled addon')
    skin = ET.parse(root / 'source' / SKIN / 'addon.xml').getroot()
    resolution = skin.find("extension[@point='xbmc.gui.skin']/res")
    if resolution is None or resolution.get('folder') != '1080p':
        raise ValueError('Missing 1080p skin entry')
    home = ET.parse(root / 'source' / HOME / 'addon.xml').getroot()
    entry = home.find("extension[@point='xbmc.python.pluginsource']")
    if entry is None or entry.get('library') != 'default.py':
        raise ValueError('Unexpected Home plugin entry')

    required = [
        'LICENSE',
        'source/' + HOME + '/default.py',
        'source/' + SKIN + '/1080p/Home.xml',
        'source/' + SKIN + '/scripts/infuse.py',
        'source/' + SKIN + '/media/Textures.xbt',
        'source/' + SKIN + '/LICENSE.txt',
        'source/' + SKIN + '/NOTICE.txt',
        'source/' + SKIN + '/fonts/README.txt',
        'source/' + SKIN + '/fonts/NotoSansSC-Regular.ttf',
        'source/' + SKIN + '/fonts/NotoSansSC-Medium.ttf',
        'source/' + SKIN + '/fonts/LICENCE-NotoSansSC.txt',
        'source/' + SKIN + '/fonts/LICENCE-Roboto.txt',
        'source/' + SKIN + '/licenses/Lucide.txt',
        'source/' + SKIN + '/licenses/media-icons-lucide.txt',
        'source/' + SKIN + '/licenses/media-icons-flag-icons.txt',
        'source/' + SKIN + '/licenses/media-icons-LICENCE-Roboto.txt',
        'source/' + SKIN + '/licenses/media-icons-LICENCE-NotoSansSC.txt',
    ]
    for name in required:
        path = root / name
        if not path.is_file() or path.stat().st_size < 32:
            raise ValueError('Missing or empty required resource: ' + name)
    if (root / 'LICENSE').read_text(encoding='utf-8') != (root / 'source' / SKIN / 'LICENSE.txt').read_text(encoding='utf-8'):
        raise ValueError('Root GPL text differs from the preserved skin license')

    # Only review the shareable documents, never the local evidence folders.
    documents = [root / n for n in ('README.md', 'INSTALL.md', 'CONTRIBUTING.md', 'THIRD_PARTY_NOTICES.md')]
    documents += sorted((root / 'docs' / 'github').glob('*.md'))
    for document in documents:
        text = document.read_text(encoding='utf-8')
        for target in re.findall(r'!?\[[^\]]*\]\(([^\s)]+)\)', text):
            target = target.strip('<>').split('#', 1)[0]
            if not target or re.match(r'[a-zA-Z]+:', target):
                continue
            resolved = (document.parent / target).resolve()
            if not resolved.is_relative_to(root.resolve()) or not resolved.exists():
                raise ValueError('Broken local documentation link in ' + document.relative_to(root).as_posix())

    # Wired entry points and packed/loose textures must resolve to real members.
    skin_root = root / 'source' / SKIN
    script_names = {p.name for p in (skin_root / 'scripts').iterdir() if p.is_file()}
    run_script = re.compile(r'RunScript\(\s*special://(?:skin|home/addons/skin\.yoplayer\.infuse)/scripts/([A-Za-z0-9_.\-]+)')
    wired_refs = 0
    texture_refs = 0
    for xml_path in sorted((skin_root / '1080p').glob('*.xml')):
        for match in run_script.finditer(xml_path.read_text(encoding='utf-8-sig')):
            wired_refs += 1
            if match.group(1) not in script_names:
                raise ValueError('Skin XML references a missing script: ' + match.group(1))
    for py_path in sorted((skin_root / 'scripts').glob('*.py')):
        for match in run_script.finditer(py_path.read_text(encoding='utf-8-sig')):
            wired_refs += 1
            if match.group(1) not in script_names:
                raise ValueError('Skin script references a missing script: ' + match.group(1))
    media_names = {p.relative_to(skin_root / 'media').as_posix().lower()
                   for p in (skin_root / 'media').rglob('*') if p.is_file()}
    texture = re.compile(r'infuse/([A-Za-z0-9_\-./]+\.(?:png|jpg|jpeg|webp|gif))', re.I)
    for xml_path in sorted((skin_root / '1080p').glob('*.xml')):
        for match in texture.finditer(xml_path.read_text(encoding='utf-8-sig')):
            texture_refs += 1
            if ('infuse/' + match.group(1)).lower() not in media_names:
                raise ValueError('Skin XML references a missing texture: ' + match.group(1))

    # Python window handles for custom dialogs must use Kodi's runtime ids:
    # Custom_#### resolves as ####+10000 (device-verified on 108: Custom_1122
    # opens as 11122). Standard windows keep their fixed ids, so only the
    # 11000-11999 custom band is checked here.
    declared_ids = {int(m.group(1)) for p in (skin_root / '1080p').glob('*.xml')
                    for m in [re.search(r'<window[^>]*\bid="([0-9]{4})"', p.read_text(encoding='utf-8-sig', errors='replace')[:400])] if m}
    window_ctor = re.compile(r'xbmcgui\.Window\((1[12][0-9]{2})\)')
    for py_path in sorted((skin_root / 'scripts').glob('*.py')):
        for match in window_ctor.finditer(py_path.read_text(encoding='utf-8-sig')):
            if int(match.group(1)) - 10000 not in declared_ids:
                raise ValueError('Skin script targets an undeclared custom dialog id: ' +
                                 match.group(1) + ' in ' + py_path.name)

    # Delivered metadata must state the same versions as the runtime sources.
    head = (skin_root / 'changelog.txt').read_text(encoding='utf-8-sig').splitlines()
    if not head or not head[0].strip().startswith(metadata[SKIN]['version'] + ' / Home ' + metadata[HOME]['version']):
        raise ValueError('Changelog head does not match addon versions: ' + (head[0].strip() if head else '<empty>'))
    project_path = root / 'project.json'
    if project_path.is_file():
        project = json.loads(project_path.read_text(encoding='utf-8-sig'))
        declared = project.get('skin_version')
        packaged = project.get('packaged_versions', {}).get('skin')
        if declared is not None and declared != metadata[SKIN]['version']:
            raise ValueError('project.json skin_version lags the runtime source: ' + str(declared))
        if packaged is not None and packaged != metadata[SKIN]['version']:
            raise ValueError('project.json packaged skin version lags the runtime source: ' + str(packaged))

    report = {
        'status': 'passed',
        'mode': 'repository',
        'validation_rebuilds_source': False,
        'kodi_ui_acceptance': 'not-run',
        'addons': metadata,
        'runtime_files': len(files),
        'syntax_checked': counts,
        'required_resources_checked': len(required),
        'documentation_files_checked': len(documents),
        'wired_script_refs_checked': wired_refs,
        'texture_refs_checked': texture_refs,
        'source_sha256': {name: digest(path.read_bytes()) for name, path in files.items()},
    }
    if (root / 'source' / SKIN / 'resources/themes.json').is_file():
        from check_themes import check as check_themes
        report['theme_checks'] = check_themes()
    destination = root / 'docs' / 'structure-validation.repository.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    try:
        report = check()
        print(json.dumps({k: v for k, v in report.items() if k != 'source_sha256'}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, ET.ParseError) as exc:
        print('Repository check failed: ' + str(exc), file=sys.stderr)
        return 1


def package_main(output=None):
    try:
        report = check()
        out = (ROOT / output).resolve() if output else ROOT / 'dist'
        if not out.is_relative_to((ROOT / 'dist').resolve()):
            raise ValueError('Repository build output must stay inside dist/')
        destinations = {
            addon: out / ('YoPlayer-' + ('Skin' if addon == SKIN else 'Home') + '-'
                          + report['addons'][addon]['version'] + '.zip')
            for addon in ADDONS
        }
        sums = out / 'SHA256SUMS.txt'
        for path in [*destinations.values(), sums]:
            if path.exists():
                raise ValueError('Build output exists; refusing to overwrite: ' + path.name)
        files = runtime_files()
        # Read a validated snapshot so concurrent edits cannot produce mixed bytes.
        payload = {name: path.read_bytes() for name, path in files.items()}
        if {name: digest(data) for name, data in payload.items()} != report['source_sha256']:
            raise ValueError('Source changed after validation')
        out.mkdir(parents=True, exist_ok=True)
        results = []
        for addon, destination in destinations.items():
            expected = {name[len('source/'):]: data for name, data in payload.items()
                        if name.startswith('source/' + addon + '/')}
            with ZipFile(destination, 'x', ZIP_DEFLATED, compresslevel=6) as archive:
                for member, data in expected.items():
                    archive.writestr(member, data)
            with ZipFile(destination) as archive:
                if archive.testzip() is not None or archive.namelist() != list(expected):
                    raise ValueError('Build archive failed member verification')
                if any(archive.read(name) != data for name, data in expected.items()):
                    raise ValueError('Build archive differs from validated source')
            results.append({'path': destination.relative_to(ROOT).as_posix(),
                            'sha256': digest(destination.read_bytes()), 'files': len(expected)})
        with sums.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(''.join(r['sha256'] + '  ' + Path(r['path']).name + '\n' for r in results))
        print(json.dumps({'status': 'packaged', 'mode': 'repository', 'addons': results,
                          'checksums': sums.relative_to(ROOT).as_posix(),
                          'kodi_ui_acceptance': 'not-run'}, indent=2))
        return 0
    except (OSError, ValueError, ET.ParseError) as exc:
        print('Repository packaging failed: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
