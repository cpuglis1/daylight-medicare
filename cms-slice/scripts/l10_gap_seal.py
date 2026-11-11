"""Seal an exact audited L10 gap-research revision without selecting prices."""
from pathlib import Path
import json

from l10_gap_sources import ROOT, BASE, WORK, read, write, sha


def seal():
    out=WORK/'build-r1';selector=BASE/'CURRENT_GAP_RESEARCH.json'
    if (out/'SEALED').exists() or selector.exists():raise ValueError('Preserve existing revision; create a new revision')
    validation=read(WORK/'validation.json');assurance=read(WORK/'assurance.json')
    assert validation['passed'] and assurance['passed'] and validation['full_l10_complete'] is False
    files=[p for p in WORK.rglob('*') if p.is_file() and p.name not in ['manifest.json','SEALED']]
    files += [ROOT/p for p in read(WORK/'preservation-before.json')]
    files += list((ROOT/'cms-slice/scripts').glob('l10_gap_*.py'))
    files += [ROOT/'cms-slice/tests/test_l10_gaps.py']
    manifest={'schema':'l10-gap-research-manifest/1','revision':'L10-COLLIER-2026-gap-research-r4-build-r1',
              'scope':'426 metadata indexes, retained company/form source accounting, qualified public sources and exact download handoff',
              'files':{str(p.relative_to(ROOT)):sha(p) for p in sorted(set(files))},
              'research_only':True,'human_acceptance':None,'consumer_release_enabled':False,'full_l10_complete':False}
    write(out/'manifest.json',manifest);write(out/'SEALED',{'manifest_sha256':sha(out/'manifest.json'),'revision':manifest['revision']})
    write(selector,{'package':str(out.relative_to(ROOT)),'manifest_sha256':sha(out/'manifest.json'),
                    'seal_sha256':sha(out/'SEALED'),'research_only':True,'human_acceptance':None,
                    'consumer_release_enabled':False,'full_l10_complete':False})
    assert all(sha(ROOT/p)==wanted for p,wanted in manifest['files'].items())
    print(json.dumps({'manifest_sha256':sha(out/'manifest.json'),'sealed_files_verified':len(manifest['files'])},indent=2))


if __name__=='__main__':seal()
