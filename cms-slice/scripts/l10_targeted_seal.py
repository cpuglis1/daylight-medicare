"""Seal the completed targeted intake as a separate, unaccepted research archive."""
from l10_targeted_intake import ROOT, BASE, PACKET, OUT, read, write, sha


def seal():
    selector = BASE / 'CURRENT_TARGETED_FILINGS.json'
    if (OUT / 'SEALED').exists() or selector.exists():
        raise ValueError('Existing r5 must remain immutable; create a new revision')
    audit = read(PACKET / 'validation.json'); assurance = read(PACKET / 'assurance.json')
    assert audit['passed'] and assurance['passed'] and assurance['tests_passed'] == 65
    assert audit['annual_source_cells_checked'] == 40700 and audit['unexplained_source_value_mismatches'] == 0
    assert assurance['independent_audit_sha256'] == sha(PACKET / 'validation.json')
    assert assurance['tests_log_sha256'] == sha(PACKET / 'tests.log')
    assert assurance['replay_sha256'] == sha(PACKET / 'replay.json')
    protected = read(PACKET / 'preservation-before.json')
    assert all(sha(ROOT / path) == wanted for path, wanted in protected.items())
    files = [p for p in PACKET.rglob('*') if p.is_file() and p.name not in ['manifest.json', 'SEALED']]
    files += [ROOT / p for p in protected]
    files += list((ROOT / 'cms-slice/scripts').glob('l10_targeted_*.py'))
    files += [ROOT / 'cms-slice/tests/test_l10_targeted.py']
    manifest = {'schema': 'l10-targeted-filings-manifest/1', 'revision': 'L10-COLLIER-2026-targeted-filings-r5-build-r1',
                'scope': 'Eleven targeted source packets plus unchanged parent six-file research archive; no full-market or personal quote release',
                'files': {str(p.relative_to(ROOT)): sha(p) for p in sorted(set(files))},
                'independent_audit': str((PACKET / 'validation.json').relative_to(ROOT)),
                'research_only': True, 'human_acceptance': None, 'consumer_release_enabled': False,
                'targeted_acquisition_complete': True, 'full_l10_complete': False}
    write(OUT / 'manifest.json', manifest)
    write(OUT / 'SEALED', {'revision': manifest['revision'], 'manifest_sha256': sha(OUT / 'manifest.json')})
    write(selector, {'package': str(OUT.relative_to(ROOT)), 'manifest_sha256': sha(OUT / 'manifest.json'),
                     'seal_sha256': sha(OUT / 'SEALED'), 'research_only': True, 'human_acceptance': None,
                     'consumer_release_enabled': False, 'targeted_acquisition_complete': True, 'full_l10_complete': False})
    assert all(sha(ROOT / path) == wanted for path, wanted in manifest['files'].items())
    print({'manifest_sha256': sha(OUT / 'manifest.json'), 'sealed_files_verified': len(manifest['files'])}, flush=True)


if __name__ == '__main__':
    seal()
