"""Fingerprint a technically validated L12 research packet, without acceptance."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/data/l12-help-with-costs-2026-10-28'
BUILD=BASE/'build-r1'

def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def files():
    # A current pointer contains this manifest's hash and is therefore outside
    # the manifest to avoid a circular fingerprint. Its fields are checked on
    # verification. Later revisions do not silently rewrite this packet.
    paths={p for p in BASE.rglob('*') if p.is_file() and p.name not in ('manifest.json','CURRENT_REFERENCE.json') and '__pycache__' not in p.parts}
    for s in load(BUILD/'sources.json').values():
        for key in ['path','receipt_path']:
            if key in s:paths.add(ROOT/s[key])
    for p in (BUILD/'code').iterdir():
        if p.suffix=='.py':paths.add(ROOT/('cms-slice/tests' if p.name.startswith('test_') else 'cms-slice/scripts')/p.name)
    return {str(p.relative_to(ROOT)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(paths)}

def seal():
    dest=BUILD/'manifest.json'
    if dest.exists():raise ValueError('Already sealed; verify or create a new revision')
    if not load(BUILD/'validation.json')['passed']:raise ValueError('Validation did not pass')
    tests=load(BUILD/'tests.json')
    if tests['failures'] or tests['errors'] or tests['tests_run']<20:raise ValueError('Tests incomplete')
    for p in (BUILD/'code').glob('*.py'):
        live=ROOT/('cms-slice/tests' if p.name.startswith('test_') else 'cms-slice/scripts')/p.name
        if p.read_bytes()!=live.read_bytes():raise ValueError('Code snapshot differs '+p.name)
    record={'schema':'l12-seal/1','reference_id':load(BUILD/'summary.json')['reference_id'],
            'sealed_at_utc':datetime.now(timezone.utc).isoformat(),'files':files(),
            'human_acceptance':None,'independent_R17_review':None,'consumer_release_enabled':False,
            'meaning':'Integrity and technical validation only; open source/interpretation gaps and review remain.'}
    dest.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'sealed_files':len(record['files']),'manifest_sha256':sha(dest)}))

def verify():
    record=load(BUILD/'manifest.json')
    current={p:{'sha256':sha(ROOT/p),'bytes':(ROOT/p).stat().st_size} for p in record['files']}
    if record['files']!=current:
        changed=[p for p in sorted(set(record['files'])|set(current)) if record['files'].get(p)!=current.get(p)]
        raise ValueError('Seal mismatch '+repr(changed))
    for p in (BUILD/'code').glob('*.py'):
        live=ROOT/('cms-slice/tests' if p.name.startswith('test_') else 'cms-slice/scripts')/p.name
        if p.read_bytes()!=live.read_bytes():raise ValueError('Current r1 code differs from sealed snapshot '+p.name)
    pointer=load(BASE/'CURRENT_REFERENCE.json')
    if pointer['reference_id']==record['reference_id']:
        if pointer['manifest_sha256']!=sha(BUILD/'manifest.json') or pointer['consumer_release_enabled'] is not False or pointer['human_acceptance'] is not None:raise ValueError('Current research pointer changed')
    print(json.dumps({'verified':True,'files':len(current),'manifest_sha256':sha(BUILD/'manifest.json')}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--verify',action='store_true');a=p.parse_args()
    verify() if a.verify else seal()
