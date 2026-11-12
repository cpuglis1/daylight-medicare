"""Author one review-only open-band source view; sealed inputs are read-only."""
from pathlib import Path
import copy
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l03-ma-benefits-2026-11-02-whole-offering-r12'
OUT = BASE / 'structured-inpatient-comparison-r3'
OLD = BASE / 'structured-inpatient-comparison-r1'
MODEL = BASE / 'open-band-comparison-contract-r2'
OUT.mkdir(exist_ok=True)
assert not (OUT / 'FREEZE_R3.json').exists(), 'Do not overwrite a frozen revision'

def read(p):
    if p.name.endswith('.jsonl.gz'):
        return [json.loads(x) for x in gzip.decompress(p.read_bytes()).decode().splitlines()]
    return json.loads(p.read_text())

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def fp(x):
    return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True,
        separators=(',', ':')).encode()).hexdigest()

def binding(p):
    return {'path':str(p.relative_to(ROOT)), 'sha256':sha(p), 'bytes':p.stat().st_size}

def write(name, x):
    (OUT/name).write_text(json.dumps(x, ensure_ascii=False, indent=2, sort_keys=True)+'\n')

leaf_path = BASE/'clinical-meaning-refinement-r2/material-leaves-corrected.jsonl.gz'
original_path = ROOT/'docs/data/l03-ma-benefits-2026-11-01-whole-offering-r11/source-preparation/generated-r2/offering-canonical.jsonl.gz'
leaves = read(leaf_path)
originals = {x['id']:x for x in read(original_path)}
old_records = read(OLD/'COMPARISON_RECORDS.json')
record = copy.deepcopy(old_records[0])
register = read(OLD/'EVIDENCE_REGISTER.json')
rule_leaf = next(x for x in leaves if x['item_key']=='ACUTE-UNLIMITED' and x['kind']=='condition')
claim_leaf = next(x for x in leaves if x['item_key']=='ACUTE-UNLIMITED' and x['kind']=='claim')
original_id = 'CANONICAL-658dd1331f5510b8acee1153870f'
assert originals[original_id]['kind']=='claim'
assert rule_leaf['id']=='CMR1-R12-PROPOSED-08faa7b894b8d2806aef341845ce-002'
assert {x['original_id'] for x in rule_leaf['novelty_and_equivalence']['exact_source_assertion_locator_correspondences']}=={original_id}
assert len(originals)==4675
spec = importlib.util.spec_from_file_location('_inpatient_r3_model', MODEL/'open_band_comparison.py')
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)

# All source-reference wrappers resolve back to the frozen evidence register.
# Their headers/footnotes remain incomplete: this is not a readiness promotion.
evidence = []
for key, item in register.items():
    if key.startswith('CMS-') or key.startswith('FLAT-'):
        continue
    if 'parents' in item:
        pages = [z for p in item['parents'] for z in p['original_source_page_images']]
        page = pages[0]['physical_page']
        document = '4da5fb8e022fde082317606d85f22bec561315c7fbf197d3b06944e9d960439d' if key.startswith('SB') else '7602dc081bd6d615dac7f43d3739234668e5701c5464cc89d061ac1f46ae75ba'
        locator = {'frozen_source_parents':item['parents'],
                   'original_parent_file':item['original_parent_file']}
    else:
        spans = item['spans']
        page = spans[0]['physical_page']
        document = spans[0]['document_sha256']
        locator = {'frozen_page_spans':spans}
    evidence.append({'id':key, 'source_sha256':document, 'side':'carrier',
        'interpretation_review_id':'INPATIENT-OPEN-BAND-PRODUCER-R3',
        'pdf_page':page,
        'passage_sha256':sha(OLD/'EVIDENCE_REGISTER.json'),
        'location':{'binding_scope':'Full frozen register dependency; representative page is not the whole passage.',
                    'register_key':key, 'register_entry_sha256':fp(item), **locator},
        'headers':[{'state':'unresolved','reason':'Exact header and contextual equivalence are not certified by this dependency wrapper; original pages and source parents control.'}],
        'footnotes':[{'state':'unresolved','reason':'Existing footer, marker and amendment dependencies remain in the frozen source record and condition families; no completeness promotion.'}]})

# For the schedule itself use the original passage hash, not the register hash.
for e in evidence:
    item = register[e['id']]
    if 'parents' in item:
        e['passage_sha256'] = fp([{'id':p['id'], 'quote':p['exact_source_quote']} for p in item['parents']])
        e['location']['passage_hash_scope'] = 'Canonical JSON array of exact parent IDs and quotes; each parent and word-binding digest retained.'
    else:
        e['passage_sha256'] = fp([{'physical_page':s['physical_page'], 'quote':s['exact_locator_text']} for s in item['spans']])
        e['location']['passage_hash_scope'] = 'Canonical JSON array of exact page numbers and layout locator text; source pixels control.'
record['schema'] = model.SCHEMA
record['id'] = 'R12-INPATIENT-STRUCTURED-IN-R3'
carrier = record['carrier']
carrier['evidence'] = evidence
carrier['cost'] = {'kind':'copayment', 'amount':{'state':'schedule_defined'},
    'range_basis':'The complete EOC in-network hospital daily copayment schedule, conditional on covered days and plan rules. This is not all admission spending, a deductible, professional charges or a personal estimate.'}
covered = carrier['conditions']['covered_days']
covered.update(assertion=originals[original_id]['detail']['assertion'],
    obligation_ids=[rule_leaf['id']], evidence_ids=['EOC68-69-IN'],
    interpretation_review_id='INPATIENT-OPEN-BAND-PRODUCER-R3')
rule_id = 'R12-INPATIENT-IN-COVERED-STAY-R3'
carrier['covered_stay_rules'] = [{'id':rule_id,
    'source_statement_kind':'explicit_unlimited_covered_stay',
    'predicate':covered['assertion'], 'condition_obligation_ids':[rule_leaf['id']],
    'evidence_ids':['EOC68-69-IN'],
    'interpretation_review_id':'INPATIENT-OPEN-BAND-PRODUCER-R3'}]
carrier['boundaries'] = {'day_bands':[
    {'begin':1, 'end':7, 'amount':'375', 'unit':'USD/day'},
    {'begin':8, 'end':{'state':'unbounded', 'covered_stay_rule_id':rule_id,
        'evidence_ids':['EOC68-69-IN'],
        'interpretation_review_id':'INPATIENT-OPEN-BAND-PRODUCER-R3'},
     'amount':'0', 'unit':'USD/day'}],
    'quantity':'No finite terminal day is stated for a stay covered according to plan rules; unlimited days are conditional, not a coverage entitlement.',
    'frequency':'The inpatient hospital cost-sharing schedule applies each time the member is admitted. Medicare hospital benefit periods do not apply to this schedule.',
    'reset':'Each admission; transfer to a separate facility type is a new admission.',
    'schedule_scope':{'state':'complete', 'start_day':1, 'terminal_end':{'state':'unbounded'},
        'evidence_ids':['EOC68-69-IN'],
        'interpretation_review_id':'INPATIENT-OPEN-BAND-PRODUCER-R3'}}
# A flat No remains a cross-source question, not carrier evidence.
carrier['conditions']['referral']['evidence_ids'] = ['EOC41-network-gate']
cms = record['cms']
components = read(BASE/'structured-inpatient-comparison-r2/SOURCE_COMPONENTS_EFFECTIVE_R2.json')
cms['evidence'] = [{'id':'CMS-1a' if i==0 else 'CMS-1a1',
    'source_sha256':components['CMS_member_sha256'], 'side':'cms',
    'interpretation_review_id':'INPATIENT-PRODUCER-R1',
    'member':components['CMS_member'], 'pointer':component['pointer']}
    for i,component in enumerate(components['native_components'])]
cms['boundaries']['schedule_scope'] = {'state':'partial',
    'reason':'Raw base 1a day operands remain separate from 1a1 and its controls. Complete native activation, period and additional-day interpretation is unresolved.'}
# All remaining old unknowns, family states, inventory roots and output holds stay.
record['outcome'] = 'insufficient_evidence'
record['interpretation_review_receipt'] = None
record['accepted_for_reference'] = False
write('COMPARISON_RECORD_R3.json',record)

write('MATERIAL_CONDITION_AND_ORIGINAL_LINEAGE.json',{
    'reference_array_semantics':'A retained source-material condition reference, not an adopted canonical condition ID.',
    'material_condition':{'id':rule_leaf['id'],'kind':rule_leaf['kind'],'sha256':fp(rule_leaf),
        'statement':rule_leaf['statement'],'source_parent_ids':rule_leaf['source_parent_ids'],
        'canonical_adoption':False},
    'qualified_claim_leaf':{'id':claim_leaf['id'],'kind':claim_leaf['kind'],'sha256':fp(claim_leaf)},
    'original_claim':{'id':original_id,'kind':'claim','sha256':fp(originals[original_id]),
        'assertion':originals[original_id]['detail']['assertion'],
        'states':originals[original_id]['states']},
    'original_claim_retyped_as_condition':False, 'new_canonical_obligations':0,
    'material_leaf_became_accepted_obligation':False,
    'source_leaf_file':binding(leaf_path), 'original_file':binding(original_path)})
write('CROSS_SOURCE_AND_OON_BOUNDARY.json',{
    'flat_referral_dependency':register['FLAT-pbp_b1a_refer_yn'],
    'flat_question_is_carrier_evidence':False,
    'OON_record':{'path':binding(OLD/'COMPARISON_RECORDS.json'), 'array_index':1,
        'record_sha256':fp(old_records[1]),'changed':False},
    'OON_per_stay_40_percent_projected_as_daily':False,
    'native_objects':components['native_components'],
    'native_999_is_unbounded':False,
    'native_1a_and_1a1_semantically_merged':False,
    'carrier_conditions_inherited_except': ['covered_days source-only predicate, material reference and evidence linkage',
        'referral evidence array moves flat question to this explicit cross-source dependency'],
    'unknown_family_states':{k:v['state'] for k,v in carrier['conditions'].items() if v['state']=='unknown'},
    'remaining':'Native control authority, source-specific referral/POS context, accumulators, exclusions, geography and amendment evidence remain unresolved.'})

def diff(a,b,path='$'):
    if type(a) is not type(b):return [{'path':path,'before':a,'after':b}]
    if isinstance(a,dict):
        out=[]
        for k in sorted(a.keys()|b.keys()):
            if k not in a:out.append({'path':path+'/'+k,'before_absent':True,'after':b[k]})
            elif k not in b:out.append({'path':path+'/'+k,'before':a[k],'after_absent':True})
            else:out.extend(diff(a[k],b[k],path+'/'+k))
        return out
    if a!=b:return [{'path':path,'before':a,'after':b}]
    return []
write('EXACT_RECORD_BEFORE_AFTER_R3.json',{
    'before_file':binding(OLD/'COMPARISON_RECORDS.json'),'before_index':0,
    'before_record_sha256':fp(old_records[0]),'after_record_sha256':fp(record),
    'changes':diff(old_records[0],record),
    'original_inventory_payload_or_state_changes':0,'original_inventory_count':4675,
    'global_inventory_count':392570,'accepted_reference_entry_changes':0})

freezes = [OLD/'FREEZE_R1.json',BASE/'structured-inpatient-comparison-r2/FREEZE_R2.json',
    BASE/'independent-structured-inpatient-review-r1/REVIEW_FREEZE_R1.json',
    BASE/'independent-structured-inpatient-review-r2/REVIEW_FREEZE_R2.json',
    MODEL/'FREEZE_R2.json',ROOT/'audit-evidence/comparison-milestone-20261102/open-band-independent-review-r2/REVIEW_FREEZE_R2.json']
native_path=original_path.parent/'CMS-native-member.json'
parent_path=BASE/'clinical-meaning-refinement-r2/exact-source-parents-unchanged.jsonl.gz'
inputs={p.resolve():binding(p) for p in [leaf_path,original_path,native_path,parent_path,Path(__file__),*freezes]}
for f in freezes:
    receipt = read(f)
    for m in receipt.get('members', receipt.get('files', [])):
        p=(f.parent/m['path']).resolve()
        assert sha(p)==m['sha256'] and p.stat().st_size==m['bytes']
        inputs[p]=binding(p)
images=[]
for name in ['eoc-068.png','eoc-069.png','sb-03.png']:
    p=BASE/'independent-carrier-dental/rendered'/name
    inputs[p.resolve()]=binding(p)
    images.append({**binding(p),'inspection':'Root read full retained original-resolution source pixels in this revision; text is a locator only.'})
write('INPUT_BINDINGS_R3.json',{'inputs':sorted(inputs.values(),key=lambda x:x['path']),
    'frozen_input_manifests':[binding(f) for f in freezes],
    'source_originals_unchanged':True,'source_exposure':'Prior producer/reviewer source knowledge disclosed; this assembly is not blind extraction.',
    'model_integration_scope':'New review-only file, not app/database/canonical adoption.'})
write('SOURCE_PIXEL_REVIEW_R3.json',{'images':images,
    'original_EOC_sha256':'7602dc081bd6d615dac7f43d3739234668e5701c5464cc89d061ac1f46ae75ba',
    'original_SB_sha256':'4da5fb8e022fde082317606d85f22bec561315c7fbf197d3b06944e9d960439d',
    'SB_summary_overrides_EOC_rules':False,'independent_review_of_new_projection':False})
print(json.dumps({'authored':str(OUT.relative_to(ROOT)), 'record':record['id'],
    'storage_errors':model.storage_errors(record),
    'carrier_ready_errors':model.readiness_errors(carrier,'carrier'),
    'cms_ready_errors':model.readiness_errors(cms,'cms')}))
