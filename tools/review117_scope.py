"""Portable 115 -> 117 repair gate; no historic generator or device access."""
import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

from repository_checks import ROOT, SKIN, HOME, check, runtime_files, digest

MODIFIED = {
    '1080p/custom_1143_Confirm.xml', '1080p/DialogVideoInfo.xml',
    '1080p/custom_1130_trailer.xml', '1080p/Home.xml', '1080p/Font.xml',
    '1080p/Includes_2.xml', '1080p/Includes_Infuse_VideoInfo.xml', '1080p/Variables.xml',
    'scripts/resumeplay.py', 'scripts/trailerurl.py', 'scripts/trailer.py',
    'scripts/bili.py', 'scripts/bilitrailer.py', 'scripts/castphoto.py', 'scripts/demotrailer.py',
    'scripts/infuse_playback_return.py', 'addon.xml', 'changelog.txt',
    'language/resource.language.zh_cn/strings.po',
    'language/resource.language.en_gb/strings.po',
}
ADDED = {'scripts/infuse_trailer_session.py'}


def verify_delta(root=ROOT):
    baseline = json.loads(Path(__file__).with_name('review117_baseline.json').read_text(encoding='utf-8'))
    previous = baseline['files']
    actual = {name: digest(path.read_bytes()) for name, path in runtime_files(root).items()}
    modified = {name for name in previous.keys() & actual.keys() if previous[name] != actual[name]}
    added = actual.keys() - previous.keys()
    removed = previous.keys() - actual.keys()
    prefix = 'source/' + SKIN + '/'
    if modified != {prefix + name for name in MODIFIED}:
        raise ValueError('Unexpected or missing 115->117 modifications: ' + repr(sorted(modified ^ {prefix + name for name in MODIFIED})))
    if added != {prefix + name for name in ADDED} or removed:
        raise ValueError('Unexpected added/retired runtime members')
    skin = ET.parse(root / 'source' / SKIN / 'addon.xml').getroot()
    home = ET.parse(root / 'source' / HOME / 'addon.xml').getroot()
    if skin.get('version') != '2026.10.3.117' or home.get('version') != '1.0.37':
        raise ValueError('117/Home37 version mismatch')
    if skin.find("requires/import[@addon='plugin.video.yoplayer.home']").get('version') != '1.0.37':
        raise ValueError('Home dependency mismatch')
    return {'baseline_commit': baseline['commit'], 'baseline_archives': baseline['archives'],
            'modified': sorted(modified), 'added': sorted(added), 'retired': sorted(removed),
            'unchanged_runtime_members': len(actual) - len(modified) - len(added),
            'home_1_0_37_unchanged': True, 'source_sha256': actual}


def main():
    sys.dont_write_bytecode = True
    destination = ROOT / 'docs/structure-validation.json'
    try:
        delta = verify_delta()
        report = check()
        from check_review117 import ContractTests, ResumeTests, PreviewTests, PublicationTests
        suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls)
                                   for cls in (ContractTests, ResumeTests, PreviewTests, PublicationTests))
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        if not result.wasSuccessful():
            raise ValueError('117 regression failures: {} errors: {}'.format(len(result.failures), len(result.errors)))
        if delta['source_sha256'] != {n: digest(p.read_bytes()) for n, p in runtime_files().items()}:
            raise ValueError('Runtime bytes changed during offline checks')
        report.update(delta)
        report.update(mode='review117-offline', tests_run=result.testsRun,
                      validation_rebuilds_source=False, packaged=False, deployed=False,
                      coreelec_acceptance='not-run-117', television_remote_cec='pending-human',
                      exclusions=['Kodi callback timing and focus engine', 'real ISO/version/track playback',
                                  'live Bili public lookup and resolved-URL identity',
                                  'physical television, remote and CEC'])
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({k: report[k] for k in ('status', 'mode', 'tests_run', 'runtime_files',
                         'unchanged_runtime_members', 'home_1_0_37_unchanged', 'retired',
                         'validation_rebuilds_source', 'coreelec_acceptance')}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, ET.ParseError) as exc:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps({'status': 'failed', 'mode': 'review117-offline',
                                          'error': str(exc), 'validation_rebuilds_source': False},
                                         ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('117 check failed: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
