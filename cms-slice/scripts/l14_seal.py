"""Seal the exact L14 research package, preserving all external review gates."""
import argparse,json,shutil
from datetime import datetime,timezone
from l14_validate import ROOT,BASE,BUILD,VAL,load,fp,digest,need,parents
def write(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def seal():
    need(not (BUILD/'manifest.json').exists(),'Sealed; new revision required')
    v=load(VAL/'validation.json');t=load(VAL/'tests.json')
    need(v['passed'] and not v['failures'] and t['passed'] and t['tests_run']==20,'Validation or tests incomplete')
    for p,f in v['validated_inputs'].items():need(fp(ROOT/p)==f,'Changed since validation '+p)
    scripts=list(ROOT.joinpath('cms-slice/scripts').glob('l14_*.py'))+[ROOT/'cms-slice/scripts/l12_sources.py',ROOT/'cms-slice/tests/test_l14_reference.py']
    code=BUILD/'code';code.mkdir(exist_ok=True)
    for p in scripts:shutil.copyfile(p,code/p.name)
    files={p for p in BASE.rglob('*') if p.is_file() and p.name not in ['manifest.json','CURRENT_REFERENCE.json'] and '__pycache__' not in p.parts}
    files.update(ROOT/p for p in v['validated_inputs']);files.update(scripts)
    files.update(ROOT/p for p in v['parent_manifest_hashes'])
    m=dict(schema='l14-exact-published-research-seal/1',reference_id='L14-PUBLISHED-COLLIER-2026-research-r1',sealed_at_utc=datetime.now(timezone.utc).isoformat(),
        files={str(p.relative_to(ROOT)):fp(p) for p in sorted(files)},qualified_R19_review=None,human_acceptance=None,full_l14_complete=False,consumer_release_enabled=False)
    write(BUILD/'manifest.json',m)
    write(BASE/'CURRENT_REFERENCE.json',dict(schema='l14-selected-research-reference/1',reference_id=m['reference_id'],package=str(BUILD.relative_to(ROOT)),manifest_sha256=digest(BUILD/'manifest.json'),
        validation_sha256=digest(VAL/'validation.json'),research_only=True,scoped_collection_and_reference_implementation_complete=True,
        full_l14_complete=False,qualified_R19_review=None,human_acceptance=None,personal_applicability_enabled=False,consumer_release_enabled=False,
        known_gap_ids=['G01','G02','G03','G04','G05','G06','G07']))
    return verify()
def verify():
    m=load(BUILD/'manifest.json');p=load(BASE/'CURRENT_REFERENCE.json')
    for path,f in m['files'].items():need(fp(ROOT/path)==f,'Changed exact L14 file '+path)
    need(p['reference_id']==m['reference_id'] and p['manifest_sha256']==digest(BUILD/'manifest.json') and p['validation_sha256']==digest(VAL/'validation.json'),'Pointer mismatch')
    for r in [m,p]:need(r['qualified_R19_review'] is None and r['human_acceptance'] is None and not r['full_l14_complete'] and not r['consumer_release_enabled'],'Invented approval')
    need(p['research_only'] and not p['personal_applicability_enabled'],'Consumer scope changed')
    return dict(verified=True,pinned_files=len(m['files']),manifest_sha256=digest(BUILD/'manifest.json'),**parents(),full_l14_complete=False,qualified_R19_review=None,human_acceptance=None)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--verify',action='store_true');a=p.parse_args();print(json.dumps(verify() if a.verify else seal(),indent=2))
