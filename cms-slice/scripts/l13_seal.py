"""Seal/verify the exact L13 research reference without implying acceptance."""
import argparse
from datetime import datetime,timezone
import json,shutil
from pathlib import Path
from l13_validate import ROOT,BASE,BUILD,load,digest,need,parent_checks

def fp(p):return {'bytes':p.stat().st_size,'sha256':digest(p)}
def write(p,obj):p.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')
def seal():
    target=BUILD/'manifest.json';need(not target.exists(),'Already sealed; use a new revision')
    v=load(BASE/'validation-r1/validation.json');t=load(BASE/'validation-r1/tests.json')
    need(v['passed'] and not v['failures'] and t['passed'] and t['tests_run']==20,'Validation/tests incomplete')
    for path,value in v['validated_inputs'].items():need(fp(ROOT/path)==value,'Changed after validation '+path)
    code=BUILD/'code';code.mkdir(exist_ok=True)
    live=list(ROOT.joinpath('cms-slice/scripts').glob('l13_*.py'))+[ROOT/'cms-slice/scripts/l12_sources.py',ROOT/'cms-slice/tests/test_l13_reference.py']
    for p in live:shutil.copyfile(p,code/p.name)
    paths=set(live)
    paths.update(p for p in BASE.rglob('*') if p.is_file() and p.name not in ['manifest.json','CURRENT_REFERENCE.json'] and '__pycache__' not in p.parts)
    paths.update(ROOT/p for p in v['validated_inputs'])
    paths.update([ROOT/'docs/data/l11-medigap-rights-2026-10-28/build-r2/manifest.json',ROOT/'docs/data/l12-help-with-costs-2026-10-28/build-r1/manifest.json',ROOT/'docs/data/l12-help-with-costs-2026-10-28/build-r2/manifest.json'])
    m=dict(schema='l13-exact-published-research-seal/1',reference_id='L13-PUBLISHED-COLLIER-2026-research-r1',reference_year=2026,
       sealed_at_utc=datetime.now(timezone.utc).isoformat(),files={str(p.relative_to(ROOT)):fp(p) for p in sorted(paths)},
       qualified_R18_review=None,human_acceptance=None,full_l13_complete=False,consumer_release_enabled=False)
    write(target,m)
    write(BASE/'CURRENT_REFERENCE.json',dict(schema='l13-selected-published-research-reference/1',reference_id=m['reference_id'],
       package=str(BUILD.relative_to(ROOT)),manifest_sha256=digest(target),validation_sha256=digest(BASE/'validation-r1/validation.json'),
       reference_year=2026,legal_snapshot='2026-10-27',collection_and_bounded_reference_implementation_complete=True,
       full_l13_complete=False,known_published_exact_date_hold=['RC06'],qualified_R18_review=None,human_acceptance=None,
       research_only=True,personal_applicability_enabled=False,consumer_release_enabled=False))
    return verify()
def verify():
    m=load(BUILD/'manifest.json')
    for path,value in m['files'].items():need(fp(ROOT/path)==value,'Changed exact L13 dependency '+path)
    p=load(BASE/'CURRENT_REFERENCE.json')
    need(p['reference_id']==m['reference_id'] and p['manifest_sha256']==digest(BUILD/'manifest.json'),'Pointer identity mismatch')
    need(p['validation_sha256']==digest(BASE/'validation-r1/validation.json'),'Validation pointer mismatch')
    need(m['human_acceptance'] is None and m['qualified_R18_review'] is None and not m['consumer_release_enabled'] and not m['full_l13_complete'],'Acceptance invented')
    need(p['human_acceptance'] is None and p['qualified_R18_review'] is None and not p['consumer_release_enabled'] and not p['personal_applicability_enabled'] and not p['full_l13_complete'] and p['known_published_exact_date_hold']==['RC06'],'Pointer gates changed')
    parents=parent_checks()
    return dict(verified=True,pinned_files=len(m['files']),manifest_sha256=digest(BUILD/'manifest.json'),**parents,qualified_R18_review=None,human_acceptance=None,consumer_release_enabled=False,full_l13_complete=False)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--verify',action='store_true');a=p.parse_args();print(json.dumps(verify() if a.verify else seal(),indent=2))
