"""Freeze this exact additive L14 package without changing the r1 selector."""
import argparse,json,shutil,subprocess
from datetime import datetime,timezone
from l14_r2_validate import ROOT,PARENT,BASE,BUILD,VAL,PARENT_SHA,load,fp,sha,need,write,guard_reference

def verify():
    m=load(BUILD/'manifest.json');p=load(BASE/'CURRENT_REFERENCE.json');top=load(PARENT/'CURRENT_GAP_REFERENCE.json')
    need(p==top,'Additive selectors disagree')
    for path,want in m['files'].items():need(fp(ROOT/path)==want,'Changed sealed r2 file '+path)
    need(p['manifest_sha256']==sha((BUILD/'manifest.json').read_bytes()) and p['validation_sha256']==sha((VAL/'validation.json').read_bytes()),'Additive selector hash mismatch')
    need(p['reference_id']==m['reference_id'] and p['parent_manifest_sha256']==PARENT_SHA,'Reference/parent identity mismatch')
    for r in [m,p]:
        need(r['qualified_R19_review'] is None and r['human_acceptance'] is None and not r['full_l14_complete'] and not r['consumer_release_enabled'],'Invented acceptance/release')
    guard_reference(load(BUILD/'reference.json'))
    parent=json.loads(subprocess.run(['python3',str(ROOT/'cms-slice/scripts/l14_seal.py'),'--verify'],check=True,capture_output=True,text=True).stdout)
    need(parent['manifest_sha256']==PARENT_SHA,'Changed exact parent')
    return dict(verified=True,reference_id=m['reference_id'],manifest_sha256=sha((BUILD/'manifest.json').read_bytes()),
                pinned_files=len(m['files']),parent_seal=parent,full_l14_complete=False,qualified_R19_review=None,human_acceptance=None)

def seal():
    need(not (BUILD/'manifest.json').exists(),'Sealed; new revision required')
    v=load(VAL/'validation.json');t=load(VAL/'tests.json');replay=load(VAL/'replay.json')
    need(v['passed'] and not v['failures'] and t['passed'] and t['tests_run']==29 and replay['passed'],'Incomplete validation/tests/replay')
    for p,want in v['validated_inputs'].items():need(fp(ROOT/p)==want,'Changed since validation '+p)
    scripts=sorted((ROOT/'cms-slice/scripts').glob('l14_r2_*.py'))+[ROOT/'cms-slice/tests/test_l14_r2_reference.py']
    code=BUILD/'code';code.mkdir(exist_ok=True)
    for p in scripts:shutil.copyfile(p,code/p.name)
    files={p for p in BASE.rglob('*') if p.is_file() and p.name not in ['manifest.json','CURRENT_REFERENCE.json'] and '__pycache__' not in p.parts}
    files.update(scripts);files.add(PARENT/'GAP_UPDATE.md');files.add(PARENT/'build-r1/manifest.json')
    m=dict(schema='l14-additive-gap-reference-seal/2',reference_id='L14-PUBLISHED-COLLIER-2026-gap-r2',
           parent_manifest_sha256=PARENT_SHA,sealed_at_utc=datetime.now(timezone.utc).isoformat(),
           files={str(p.relative_to(ROOT)):fp(p) for p in sorted(files)},full_l14_complete=False,
           qualified_R19_review=None,human_acceptance=None,consumer_release_enabled=False)
    write(BUILD/'manifest.json',m)
    p=dict(schema='l14-additive-gap-selector/2',reference_id=m['reference_id'],parent_manifest_sha256=PARENT_SHA,
           package=str(BUILD.relative_to(ROOT)),manifest_sha256=sha((BUILD/'manifest.json').read_bytes()),
           validation_sha256=sha((VAL/'validation.json').read_bytes()),research_only=True,full_l14_complete=False,
           qualified_R19_review=None,human_acceptance=None,consumer_release_enabled=False,
           data_gap_ids=['G02','G03','G04'],national_expansion_gap_ids=['G06'],casework_gap_ids=['G05'],review_gap_ids=['G07'])
    write(BASE/'CURRENT_REFERENCE.json',p);write(PARENT/'CURRENT_GAP_REFERENCE.json',p)
    return verify()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--verify',action='store_true');a=parser.parse_args()
    print(json.dumps(verify() if a.verify else seal(),indent=2))
