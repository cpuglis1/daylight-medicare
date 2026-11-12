"""Seal only an audited new research revision, preserving the r2 selector."""
import json
from pathlib import Path

from l10_filings_packet import ROOT, BASE, PACKET, OUT, read, write, sha


def seal():
    if (OUT / 'SEALED').exists() or (BASE / 'CURRENT_FILINGS.json').exists():
        raise ValueError('Existing filing selection must be preserved; create a new revision')
    audit_path = PACKET / 'build-r1-validation.json'
    audit = read(audit_path)
    assert audit['passed'] and audit['human_acceptance'] is None and audit['consumer_release_enabled'] is False
    files = list(OUT.glob('*.json')) + list(OUT.glob('*.jsonl'))
    files += [audit_path, PACKET/'intake.json', PACKET/'oir-followup-status.json',
              PACKET/'storage-deduplication.json', PACKET/'preservation-before.json',
              PACKET/'sparse-page-review.json', PACKET/'qa-review.json', PACKET/'replay.json']
    for directory in ['sources', 'text', 'qa', 'metadata-r1']:
        files += [p for p in (PACKET / directory).rglob('*') if p.is_file()]
    files += [ROOT / name for name in read(PACKET / 'preservation-before.json')]
    files += list((ROOT/'cms-slice/scripts').glob('l10_filings_*.py'))
    files += [ROOT/'cms-slice/tests/test_l10_filings.py']
    files += [PACKET/'README.md', PACKET/'REVIEW.md', PACKET/'SOURCES_NEEDED.md']
    manifest = {'schema': 'l10-owner-filings-manifest/1',
                'revision': 'L10-COLLIER-2026-owner-filings-r3-build-r1',
                'scope': 'Exact six supplied OIR packets; source-grid reconstruction only',
                'files': {str(p.relative_to(ROOT)): sha(p) for p in sorted(set(files))},
                'independent_audit': str(audit_path.relative_to(ROOT)),
                'human_acceptance': None, 'consumer_release_enabled': False, 'full_l10_complete': False}
    write(OUT / 'manifest.json', manifest)
    write(OUT / 'SEALED', {'revision': manifest['revision'], 'manifest_sha256': sha(OUT/'manifest.json')})
    write(BASE / 'CURRENT_FILINGS.json', {'package': str(OUT.relative_to(ROOT)),
                                        'manifest_sha256': sha(OUT/'manifest.json'), 'seal_sha256': sha(OUT/'SEALED'),
                                        'scope': manifest['scope'], 'human_acceptance': None, 'consumer_release_enabled': False})
    print(json.dumps({'manifest_sha256': sha(OUT/'manifest.json'), 'files_bound': len(manifest['files'])}, indent=2))


if __name__ == '__main__':
    seal()
