"""Seal L12 r2 and its exact immutable parent dependencies."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from l12_build import sha,load,write
from l12_r2_build import ROOT,BASE,BUILD,PARENT,PARENT_HASH

def fp(p):return {'sha256':sha(p),'bytes':p.stat().st_size}

def seal():
    target=BUILD/'manifest.json'
    if target.exists():raise ValueError('Already sealed')
    if not load(BUILD/'validation.json')['passed'] or not load(BUILD/'tests.json')['passed']:raise ValueError('Checks incomplete')
    paths={ROOT/p for p in load(PARENT/'manifest.json')['files']};paths.add(PARENT/'manifest.json')
    for base in [BUILD,BASE/'acquisition-r2',BASE/'followup-r2']:
        paths.update(p for p in base.rglob('*') if p.is_file() and p.name!='manifest.json' and '__pycache__' not in p.parts)
    for p in (BUILD/'code').glob('*.py'):
        live=ROOT/('cms-slice/tests' if p.name.startswith('test_') else 'cms-slice/scripts')/p.name
        if p.read_bytes()!=live.read_bytes():raise ValueError('Snapshot mismatch '+p.name)
        paths.add(live)
    write(target,{'schema':'l12-exact-research-seal/2','reference_id':'L12-PUBLISHED-FL-2026-research-r2',
                  'sealed_at_utc':datetime.now(timezone.utc).isoformat(),'parent_manifest_sha256':PARENT_HASH,
                  'files':{str(p.relative_to(ROOT)):fp(p) for p in sorted(paths)},'human_acceptance':None,
                  'qualified_R17_review':None,'consumer_release_enabled':False,'full_l12_complete':False})
    return {'sealed':True,'files':len(paths),'manifest_sha256':sha(target)}

def verify():
    manifest=load(BUILD/'manifest.json');assert sha(PARENT/'manifest.json')==PARENT_HASH
    for p,f in manifest['files'].items():
        if fp(ROOT/p)!=f:raise ValueError('Changed exact dependency '+p)
    pointer=load(BASE/'CURRENT_REFERENCE.json')
    if pointer['reference_id']==manifest['reference_id']:
        if pointer['manifest_sha256']!=sha(BUILD/'manifest.json') or pointer['human_acceptance'] is not None or pointer['consumer_release_enabled'] is not False:raise ValueError('Current pointer mismatch')
    return {'verified':True,'files':len(manifest['files']),'manifest_sha256':sha(BUILD/'manifest.json')}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--verify',action='store_true');a=p.parse_args();print(json.dumps(verify() if a.verify else seal(),indent=2))
