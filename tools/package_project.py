"""Package validated YoPlayer source without changing the immutable baseline."""
import sys

if __name__ == '__main__' and '--candidate' in sys.argv:
    if len(sys.argv) != 3 or sys.argv[1] != '--candidate':
        raise SystemExit('Usage: python tools/package_project.py --candidate docs/<candidate>/source')
    import json
    from package_candidate import package
    print(json.dumps(package(sys.argv[2]), ensure_ascii=False, indent=2))
    raise SystemExit(0)

if __name__ == '__main__' and '--repository' in sys.argv:
    output = None
    if len(sys.argv) == 4 and sys.argv[1:3] == ['--repository', '--output']:
        output = sys.argv[3]
    elif sys.argv[1:] != ['--repository']:
        raise SystemExit('Usage: python tools/package_project.py --repository [--output dist/<new-folder>]')
    from repository_checks import package_main
    raise SystemExit(package_main(output))

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import json
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
OUT = ROOT / 'releases'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def source_files():
    return {path.relative_to(ROOT).as_posix(): path for path in (ROOT / 'source').rglob('*')
            if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc', '.pyo')}


def main():
    provenance = json.loads((DOCS / 'baseline-provenance.json').read_text(encoding='utf-8'))
    baseline = ROOT / provenance['baseline_bundle']
    if digest(baseline.read_bytes()) != provenance['bundle_sha256']:
        raise RuntimeError('Immutable baseline checksum mismatch')
    validation = json.loads((DOCS / 'structure-validation.json').read_text(encoding='utf-8'))
    files = source_files()
    actual_hashes = {name: digest(path.read_bytes()) for name, path in files.items()}
    if validation.get('status') != 'passed' or actual_hashes != validation.get('source_sha256'):
        raise RuntimeError('Source has not passed current validation; run tools/check_infuse_structure.py')
    payloads = []
    with ZipFile(baseline) as bundle:
        for original in provenance['addons']:
            addon_id = original['addon_id']
            folder = ROOT / 'source' / addon_id
            metadata = ET.parse(folder / 'addon.xml').getroot()
            version = metadata.get('version', '')
            if metadata.get('id') != addon_id or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)+', version):
                raise RuntimeError('Unexpected addon ID or version: ' + addon_id)
            baseline_bytes = bundle.read(original['archive_member'])
            if digest(baseline_bytes) != original['sha256']:
                raise RuntimeError('Baseline addon checksum mismatch: ' + addon_id)
            with ZipFile(BytesIO(baseline_bytes)) as archive:
                previous = {member.filename: digest(archive.read(member)) for member in archive.infolist()
                            if not member.is_dir()}
            paths = sorted(path for name, path in files.items() if name.startswith('source/' + addon_id + '/'))
            current = {path.relative_to(ROOT / 'source').as_posix(): digest(path.read_bytes()) for path in paths}
            changed = current != previous
            if changed and tuple(map(int, version.split('.'))) <= tuple(map(int, original['version'].split('.'))):
                raise RuntimeError('Runtime files changed without a version bump: ' + addon_id)
            payloads.append({'addon_id': addon_id, 'version': version, 'paths': paths,
                             'runtime_changed_from_baseline': changed})
    if sum(len(addon['paths']) for addon in payloads) != len(files):
        raise RuntimeError('Unexpected source folder outside the two runtime addons')
    skin_version = next(addon['version'] for addon in payloads if addon['addon_id'] == 'skin.yoplayer.infuse')
    destinations = [OUT / ('YoPlayer-' + ('Skin' if addon['addon_id'].startswith('skin.') else 'Home')
                           + '-' + addon['version'] + '.zip') for addon in payloads]
    bundle_path = OUT / ('YoPlayer-' + skin_version + '-bundle.zip')
    if bundle_path.exists():
        raise RuntimeError('Release bundle already exists; refusing to overwrite delivered archives')
    for addon, destination in zip(payloads, destinations):
        if destination.exists():
            expected = {path.relative_to(ROOT / 'source').as_posix(): digest(path.read_bytes())
                        for path in addon['paths']}
            with ZipFile(destination) as archive:
                existing = {member.filename: digest(archive.read(member)) for member in archive.infolist()
                            if not member.is_dir()}
            if existing != expected:
                raise RuntimeError('Same-version addon ZIP differs from source; bump its version: ' + addon['addon_id'])
    OUT.mkdir(exist_ok=True)
    report_addons = []
    for addon, destination in zip(payloads, destinations):
        if not destination.exists():
            with ZipFile(destination, 'x', ZIP_DEFLATED, compresslevel=6) as archive:
                for path in addon['paths']:
                    archive.write(path, path.relative_to(ROOT / 'source').as_posix())
        with ZipFile(destination) as archive:
            if archive.testzip() is not None:
                raise RuntimeError('Generated addon ZIP failed verification')
        report_addons.append({'addon_id': addon['addon_id'], 'version': addon['version'],
                              'path': str(destination), 'files': len(addon['paths']),
                              'sha256': digest(destination.read_bytes()),
                              'runtime_changed_from_baseline': addon['runtime_changed_from_baseline']})
    with ZipFile(bundle_path, 'x', ZIP_DEFLATED) as archive:
        for destination in destinations:
            archive.write(destination, destination.name)
        archive.write(ROOT / 'README.md', 'project-readme.md')
        archive.write(ROOT / 'INSTALL.md', 'installation.md')
        for name in ('baseline-provenance.json', 'structure-validation.json', 'cleanup-backlog.md', 'osd-migration.md', 'home-menu-migration.md', 'detail-layout-migration.md', 'glass-osd-migration.md', 'settings-migration.md', 'detail-dialogs-migration.md'):
            archive.write(DOCS / name, 'docs/' + name)
    with ZipFile(bundle_path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('Generated bundle failed verification')
    report = {'project': 'YoPlayer', 'status': 'packaged', 'addons': report_addons,
              'bundle': str(bundle_path), 'bundle_sha256': digest(bundle_path.read_bytes()),
              'installation_order': ['plugin.video.yoplayer.home', 'skin.yoplayer.infuse'],
              'deployed': False, 'kodi_ui_acceptance': 'not-run',
              'baseline_bundle_sha256': provenance['bundle_sha256']}
    (DOCS / 'package.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
