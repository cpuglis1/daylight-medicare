"""Seal/verify the additive L11 r2 dependency closure without changing r1."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from l11_seal import fingerprint, verify

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/data/l11-medigap-rights-2026-10-28'


def seal(build):
    target=build/'manifest.json'
    if target.exists():raise ValueError('Revision already sealed')
    if json.loads((build/'validation.json').read_text())['status']!='passed':raise ValueError('Validation failed')
    if json.loads((build/'tests-result.json').read_text())['exit_code']!=0:raise ValueError('Tests failed')
    parent_path=BASE/'build-r1/manifest.json'
    verify(parent_path);parent=json.loads(parent_path.read_text())
    paths=set(parent['external_inputs'])
    paths.add(str(parent_path.relative_to(ROOT)))
    paths.update(str((parent_path.parent/n).relative_to(ROOT)) for n in parent['files'])
    paths.update(str(p.relative_to(ROOT)) for p in (BASE/'acquisition-r2').rglob('*') if p.is_file())
    for p in (build/'code').iterdir():
        paths.add('cms-slice/'+('tests/' if p.name.startswith('test_') else 'scripts/')+p.name)
    manifest={'schema':'l11-exact-research-manifest/2',
              'created_at_utc':datetime.now(timezone.utc).isoformat(),
              'parent_manifest_sha256':fingerprint(parent_path)['sha256'],
              'files':{str(p.relative_to(build)):fingerprint(p) for p in sorted(build.rglob('*')) if p.is_file()},
              'external_inputs':{p:fingerprint(ROOT/p) for p in sorted(paths)},
              'research_only':True,'reference_year':2026,'reference_date':'2026-10-28',
              'human_acceptance':None,'qualified_R16_review':None,'full_l11_complete':False,
              'consumer_release_enabled':False}
    target.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    return verify(target)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('path',type=Path);p.add_argument('--verify',action='store_true');args=p.parse_args()
    print(json.dumps(verify(args.path) if args.verify else seal(args.path),indent=2))
