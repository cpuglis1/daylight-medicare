"""Seal source expectations before opening the new native-control candidate."""
from pathlib import Path
from datetime import datetime, timezone
import collections
import hashlib
import json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE=ROOT/'docs/data/l03-ma-benefits-2026-11-02-whole-offering-r12'
assert not (HERE/'EXPECTED_FREEZE_R1.json').exists()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fp(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def bind(p):return {'path':str(p.relative_to(ROOT)),'sha256':sha(p),'bytes':p.stat().st_size}
def write(name,x):(HERE/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
native_path=ROOT/'docs/data/l03-ma-benefits-2026-11-01-whole-offering-r11/source-preparation/generated-r2/CMS-native-member.json'
authority_path=BASE/'native-format-authority-review-r1/PER_OBSERVATION_DECISIONS_1223.json'
projection_path=BASE/'native-format-authority-review-r1/FINAL_MODULE_PROJECTION_REPLAY.json'
sas_path=BASE/'native-format-authority-research-r1/extracted-cms-code/JSON_IMPORT_PBPB1.SAS'
native=json.loads(native_path.read_text())
leaves=[]
def walk(x,pointer):
    if isinstance(x,dict):
        for k,v in x.items():walk(v,pointer+'/'+k.replace('~','~0').replace('/','~1'))
    elif isinstance(x,list):
        for i,v in enumerate(x):walk(v,pointer+'/'+str(i))
    else:leaves.append({'pointer':pointer,'raw':x,'raw_type':type(x).__name__})
for i in (0,1):walk(native['pbp'][0]['benefitDetails']['benefitDetailsInfo'][i],f'/pbp/0/benefitDetails/benefitDetailsInfo/{i}')
controls=[x for x in leaves if '/benefitDetails/' in x['pointer'].split('/benefitDetailsInfo/',1)[1]]
descriptors=[x for x in leaves if x not in controls]
populated=[x for x in controls if x['raw'] not in ('',None)]
authority=[x for x in json.loads(authority_path.read_text())['records'] if x['pointer'] in {r['pointer'] for r in controls}]
assert len(controls)==204 and len(descriptors)==4 and len(populated)==34
assert len(authority)==34
assert {x['pointer'] for x in populated}=={x['pointer'] for x in authority}
assert all(next(v['raw'] for v in populated if v['pointer']==x['pointer'])==x['raw'] for x in authority)
expected=[]
for x in authority:
    expected.append({k:x[k] for k in ['pointer','raw','format_evidence_verdict','literal_retention','full_projection_references','new_native_enum_label_assigned','domain_truth_or_source_adoption','accepted_for_reference']})
rules=[
 ('exact_scope','Retain all 204 controls and four descriptors with exact types, whole-object hashes, category 1a/type 1 and 1a1/type 2 separately.'),
 ('blank_controls','All 170 blank control values remain individually retained; no blank means No, zero or inapplicable without an exact consuming rule.'),
 ('scoped_authority','The 18 scoped projections are specific model/source-path evidence with original guards, MAX, defaults and import normalization; they are not universal labels.'),
 ('literal_scope','The six numeric operands without projection authority remain literals with enclosing mode/period/network controls unresolved.'),
 ('unresolved_selectors','The ten selector meanings stay held, with a concrete exact-path next action; same names and digits do not establish authority.'),
 ('period','Raw 3 in the exact 1a/type 1 period path projects to flat PBP_B1A_HOSP_BEN_PERIOD 3, whose exact dictionary label is Per Admission or Per Stay.'),
 ('medicare_defined_cost_share','TierCopayment.bdCopaymentTier1YesNo raw 2 maps to the Medicare-defined cost-share question, not a claim that tier 1 is inactive.'),
 ('interval_counts','Native populated interval counts 2/1/0 and flat enum codes 3/2/1 are distinct representations; compare exact question and content, not digit identity.'),
 ('zero_stay','The raw 0.00 stay operand does not erase the positive 375.00/day band or establish a zero total admission bill.'),
 ('base_bands','Base native raw day bands 1–7/375.00 and 8–90/0.00 remain attached to their own activation and period controls.'),
 ('additional_band','Additional 1a1 raw day band 91–999/0.00 remains separate and finite as stored; 999 is not an authorized infinity sentinel.'),
 ('additional_unlimited','1a1/type 2 raw unlimited control 1 has its exact scoped Yes projection; that is not a reviewed merge with base 1a or carrier Medicare-covered unlimited stays.'),
 ('category_type','Do not erase additional benefit 1a1/type 2 scope when comparing its raw operands or unlimited selector with base 1a/type 1.'),
 ('auth_referral','Native authorization 1/referral 2 lack exact scoped projection authority in the retained decisions; flat Yes/No questions are a separate format.'),
 ('pos','POS raw 40 is a percentage operand, not a copayment; payment-rate base and selector meanings cannot be borrowed from carrier prose.'),
 ('pos_deductible','POS deductible 2 and empty amount require exact selector authority; no zero or No is inferred solely from code 2 or blank amount.'),
 ('moop','Native MoopAmount yes/no raw 2 and blank amount do not inherit a flat code label or waive the separate plan accumulator review.'),
 ('later_workbook','The later 34 conditional workbook uses require exact pointer/category binding. A name suffix or broad component match is insufficient.'),
 ('full_lineage','All source-control decisions bind original source IDs, raw observation IDs and exact payload hashes without treating a broad dependency as whole-original equivalence.'),
 ('source_vs_model','Static official SAS interpretation remains distinct from executed SAS/workbook behavior and from authoritative benefit truth.'),
 ('open_internal_work','Every unresolved control names useful internal work; no unperformed route is relabeled an external source-access blocker.'),
 ('preservation','Prior evidence/code, 4675 original payloads/states, 16 missing and the accepted reference remain unchanged; no app/database or consumer release.')]
write('SOURCE_CONTROL_CENSUS_EXPECTED.json',{'controls':controls,'descriptors':descriptors,
    'populated_controls':34,'blank_controls':170,'whole_objects':[{'index':i,'sha256':fp(native['pbp'][0]['benefitDetails']['benefitDetailsInfo'][i])} for i in (0,1)]})
write('PRIOR_EXACT_AUTHORITY_EXPECTED.json',{'records':expected,'counts':dict(collections.Counter(x['format_evidence_verdict'] for x in expected)),
    'scope':'Existing frozen independent source-format decisions; not new acceptance.'})
write('SOURCE_REVIEW_EXPECTATIONS.json',{'cases':[{'id':'NI-EXPECTED-'+str(i).zfill(2),'meaning':t,'name':n} for i,(n,t) in enumerate(rules,1)],
    'candidate_opened':False,'blind_source_review_claimed':False,
    'exposure':'Root previously authored the inpatient source assembly and reviewed model code. Producer status previews (including counts and three control conclusions) were received before this seal. Counts and raw controls were independently replayed from the original retained native member; prior frozen authority and three original SAS guard branches were read. No forthcoming native-control candidate file was opened.'})
lines=sas_path.read_text().splitlines()
write('ORIGINAL_SAS_GUARD_BINDINGS.json',{'file':bind(sas_path),'spans':[{'begin':a,'end':b,'text':'\n'.join(lines[a-1:b])} for a,b in [(222,226),(448,452),(1508,1512)]],
    'executed_downloaded_code':False})
write('EXPECTED_INPUT_BINDINGS.json',{'files':[bind(p) for p in [native_path,authority_path,projection_path,sas_path,Path(__file__)]],
    'candidate_file_reads':0})
members=[{'path':p.name,'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(HERE.iterdir()) if p.is_file()]
write('EXPECTED_FREEZE_R1.json',{'schema':'daylight.native-inpatient.independent-expected.freeze.r1',
    'observed_at':datetime.now(timezone.utc).isoformat(),'members':members,'expectations':len(rules),
    'controls_replayed':204,'candidate_opened':False,'source_acceptance':False})
print(json.dumps({'expected_freeze_sha256':sha(HERE/'EXPECTED_FREEZE_R1.json'),'members':len(members),'expectations':len(rules)}))
