"""Author a bounded, unaccepted inpatient comparison; never mutate source inputs."""
from pathlib import Path
import copy
import gzip
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l03-ma-benefits-2026-11-02-whole-offering-r12'
PREP = ROOT / 'docs/data/l03-ma-benefits-2026-11-01-whole-offering-r11/source-preparation/generated-r2'
OUT = BASE / 'structured-inpatient-comparison-r1'
OUT.mkdir(exist_ok=True)
assert not (OUT/'FREEZE_R1.json').exists(), 'A sealed packet must never be overwritten'
sys.path.insert(0, str(ROOT / 'cms-slice/scripts'))
from l03_r9_comparison import compare
from l03_comparison_contract import CONDITION_FAMILIES, fingerprint

def read(p):
    if str(p).endswith('.jsonl.gz'):
        return [json.loads(x) for x in gzip.decompress(p.read_bytes()).decode().splitlines()]
    return json.loads(p.read_text())

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        while chunk := f.read(1024*1024): h.update(chunk)
    return h.hexdigest()

def binding(p):
    return {'path': str(p.relative_to(ROOT)), 'sha256': sha(p), 'bytes': p.stat().st_size}

def write(n, value):
    (OUT / n).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n')

leaf_path = BASE / 'clinical-meaning-refinement-r2/material-leaves-corrected.jsonl.gz'
parents_path = BASE / 'clinical-meaning-refinement-r2/exact-source-parents-unchanged.jsonl.gz'
original_path = PREP / 'offering-canonical.jsonl.gz'
native_path = PREP / 'CMS-native-member.json'
flat_path = BASE / 'clinical-review-r3/clinical-native-table-comparisons.jsonl.gz'
case_path = BASE / 'case-comparisons-r2/producer-case-comparisons.json'
pages_path = PREP / 'carrier-pages.jsonl.gz'
identity_path = ROOT / 'docs/data/l02-ma-availability-2026-10-25/build-r5/12021/offerings.json'
schema_path = ROOT / 'docs/data/l03-ma-benefits-2026-10-25/semantic-inventory-r9/comparison-record.schema.json'
leaves = read(leaf_path)
parents = {x['id']: x for x in read(parents_path)}
originals = {x['id']: x for x in read(original_path)}
native = read(native_path)
flat = [x for x in read(flat_path) if x['field'].startswith('pbp_b1a_')]
case = next(x for x in read(case_path) if x['id'] == 'R12-ACUTE')
identity = next(x for x in read(identity_path) if x['id'] == '2026:H5652:002:000')
page_rows = {(x['source_kind'], x['pdf_page']): x for x in read(pages_path)}
keys = {'SB-ACUTE', 'SB-DEDUCTIBLE-INN', 'SB-DEDUCTIBLE-SERVICE-LIST',
        'SB-MOOP-INN', 'SB-MOOP-OON', 'SB-PA-MARKER', 'R12-FOOTER-QMB',
        'R12-FOOTER-MEDICAID', 'R12-FOOTER-MAY-REDUCE'}
selected = [x for x in leaves if x['item_key'].startswith('ACUTE-') or x['item_key'] in keys]
parent_ids = sorted({i for x in selected for i in x['source_parent_ids']
                     if any(z.get('physical_page') in {68,69,70,71,112,3,9,10,2}
                            for z in parents[i]['original_source_page_images'])})
selected_parents = [parents[i] for i in parent_ids]
direct_ids = {e['original_id'] for x in selected
              for e in x['novelty_and_equivalence']['exact_source_assertion_locator_correspondences']}
scope_ids = set(case['canonical_ids']) | direct_ids
assert scope_ids <= originals.keys()
assert len(originals) == 4675
before = {i: fingerprint(x) for i,x in originals.items()}
inputs = [leaf_path, parents_path, original_path, native_path, flat_path, case_path,
          pages_path, identity_path, schema_path,
          ROOT/'cms-slice/scripts/l03_comparison_contract.py',
          ROOT/'cms-slice/scripts/l03_r9_comparison.py',
          ROOT/'cms-slice/tests/test_l03_inventory_contract.py',
          ROOT/'cms-slice/scripts/l03_inventory.py',
          BASE/'independent-clinical-refinement-review-r2/REVIEW_FREEZE_R2.json']
image_names = [('EOC',x) for x in [39,40,41,42,43,68,69,70,71,112]] + [('SB',x) for x in [2,3,9,10]]
image_bindings = []
for kind,page in image_names:
    p = BASE / f'independent-carrier-dental/rendered/{kind.lower()}-{page:03d}.png' if kind=='EOC' else BASE/f'independent-carrier-dental/rendered/sb-{page:02d}.png'
    image_bindings.append({**binding(p), 'kind':kind,'physical_page':page,
                           'personally_inspected_by_root':True,
                           'inspection_method':'full original rendered page pixels in view_image',
                           'OCR_is_locator_only':True})

write('INPUT_BINDINGS.json', {'inputs':[binding(p) for p in inputs], 'original_offering_record':identity,
      'original_offering_record_sha256':fingerprint(identity), 'source_originals_unchanged':True,
      'prior_CMS_and_carrier_exposure':True,
      'independent_blind_extraction_claimed':False})
write('SOURCE_PIXEL_REVIEW.json', {'reviewer':'root producer','images':image_bindings,
      'scope':'Bounded source rereading for structured assembly, not whole-offering source acceptance.',
      'source_EOC_sha256':'7602dc081bd6d615dac7f43d3739234668e5701c5464cc89d061ac1f46ae75ba',
      'source_SB_sha256':'4da5fb8e022fde082317606d85f22bec561315c7fbf197d3b06944e9d960439d'})

# These exact values remain in their original object and source format. Neither
# native selector names nor equal digits transfer a flat dictionary's meanings.
components = [{'pointer':f'/pbp/0/benefitDetails/benefitDetailsInfo/{i}',
               'raw_object':native['pbp'][0]['benefitDetails']['benefitDetailsInfo'][i],
               'raw_object_sha256':fingerprint(native['pbp'][0]['benefitDetails']['benefitDetailsInfo'][i])}
              for i in (0,1)]
write('SOURCE_COMPONENTS.json', {'CMS_archive_sha256':'65077aeb8deb6e82eaeddc8e32b2b1a810d1df2ca814a69b1d24401f4f5cbbe3',
      'CMS_member':'H5652-002-000-2026.json', 'CMS_member_sha256':sha(native_path),
      'native_components':components, 'flat_question_components':flat,
      'flat_native_code_identity_assumed':False,
      'native_1a1_endpoint_999_decoded_as_infinity':False,
      'component_cost_equalities_are_full_agreement':False})

def leaf_ref(x):
    return {'id':x['id'],'content_sha256':fingerprint(x),'kind':x['kind'],
            'key':x['item_key'],'statement':x['statement'],
            'source_parent_ids':[i for i in x['source_parent_ids'] if i in parent_ids],
            'direct_original_ids':sorted(e['original_id'] for e in x['novelty_and_equivalence']['exact_source_assertion_locator_correspondences']),
            'source_anchors':[a for a in x['source_anchors'] if a['parent_id'] in parent_ids]}

write('SOURCE_MEANINGS.json', {'leaves':[leaf_ref(x) for x in selected],
      'parents':[{'id':p['id'],'content_sha256':fingerprint(p),
                  'source_column':p.get('source_column', 'source role retained in original parent'),'exact_source_quote':p['exact_source_quote'],
                  'exact_quote_sha256':hashlib.sha256(p['exact_source_quote'].encode()).hexdigest(),
                  'original_source_page_images':p['original_source_page_images'],
                  'word_binding_sha256':p['word_binding_sha256']} for p in selected_parents],
      'direct_locator_match_is_whole_original_equivalence':False})

typed = {
 'EOC_IN': {'source_parent_id':'R12-SOURCE-CELL-f12a6de8b893c724e25d4aef',
   'cost_kind':'copayment','currency':'USD','denominator':'Medicare-covered inpatient day',
   'bands':[{'begin':1,'end':{'kind':'finite','value':7},'amount':'375'},
            {'begin':8,'end':{'kind':'no_numeric_endpoint_published','covered_day_rule':'unlimited only while stay covered in accordance with plan rules'},'amount':'0'}],
   'reset':'each admission; transfer to a separate facility type is a new admission',
   'Medicare_benefit_periods_apply_to_acute_schedule':False,
   'published_terminal_day':None,'numeric_terminal_inferred':False},
 'EOC_OON': {'source_parent_id':'R12-SOURCE-CELL-8dcf53a7c58fe86a02b4198a',
   'cost_kind':'coinsurance','percentage':'40','denominator':'each Medicare-covered hospital stay',
   'covered_days':'unlimited only while stay covered in accordance with plan rules',
   'reset':'each admission; transfer to a separate facility type is a new admission',
   'percentage_base':'Medicare payment rate for participating or nonparticipating OON provider, according to provider status (EOC41/42)',
   'exception':'authorized OON inpatient care after emergency stabilization uses network hospital sharing'},
 'CMS_1a_raw': {'source_pointer':components[0]['pointer'],
   'bands':[{'begin':'1','end':'7','amount':'375.00'}, {'begin':'8','end':'90','amount':'0.00'}],
   'native_interval_count_raw':'2','flat_interval_count_raw':'3',
   'cost_sharing_stay_amount_raw':'0.00','zero_stay_component_is_zero_total_admission':False,
   'basis':'Original nested raw controls retained in SOURCE_COMPONENTS; format-specific semantics stay separate.'},
 'CMS_1a1_raw': {'source_pointer':components[1]['pointer'],
   'bands':[{'begin':'91','end':'999','amount':'0.00'}],
   'bdBenefitUnlimitedYesNo_raw':'1','bdIndicateNumOfAddDays_raw':'',
   'raw_999_is_infinity':False,'1a_plus_1a1_equivalent_to_carrier_open_band':False},
 'SB': {'source':'SB physical3','IN_bands':'375/day days1–7;0/day days8andbeyond',
   'OON':'40% per stay','coverage':'unlimited inpatient days summary',
   'qualification':'SB is summary; exact EOC plan rules retained separately; no summary overrides detail.'}}
write('TYPED_SCHEDULES.json', typed)

def ids_for(*ks):
    return sorted({e['original_id'] for x in selected if x['item_key'] in ks
        for e in x['novelty_and_equivalence']['exact_source_assertion_locator_correspondences']})

def condition(state, assertion, ks=(), evidence=()):
    return {'state':state,'assertion':assertion,'obligation_ids':ids_for(*ks),
            'evidence_ids':list(evidence),'interpretation_review_id':'INPATIENT-PRODUCER-R1'}

carrier_conditions = {
 'authorization':condition('asserted',
    'The IN inpatient row carries double dagger: provider MAY need to request PA (EOC68/112). EOC41–42 gives IN approval rules; new enrollees have minimum90day no-PA transition for active treatment including preexisting OON courses; approved treatment PA lasts while medically reasonable/necessary under the stated criteria. EOC41–42 separately states no advance approval required for OON providers, with optional advance coverage decision. This does not erase the authorized post-stabilization cost exception or convert MAY to universal PA.',
    ('SB-PA-MARKER','ACUTE-POSTSTABLE'),('EOC68-IN-marker','EOC112-marker-key','EOC41-42-PA','SB9-marker-key')),
 'referral':condition('unknown',
    'Exact inpatient referral disposition remains open: flat pbp_b1a_refer_yn answers No; EOC41 generic network/referral gate and detailed POS exceptions need exact contextual reconciliation. Doctor admission order is a separate requirement and cannot be substituted for referral.',
    ('ACUTE-ADMISSION',),('EOC41-network-gate','FLAT-pbp_b1a_refer_yn')),
 'network_and_setting':condition('asserted',
    'The inpatient hospital row includes acute, rehabilitation, long-term care hospitals and other inpatient services. Separate printed IN and OON schedules apply. Formal doctor-ordered hospital admission starts inpatient care; an overnight observation stay alone is outpatient. Transplant network differs from general hospital network. Authorized OON inpatient care after emergency stabilization uses network hospital sharing.',
    ('ACUTE-ADMISSION','ACUTE-TRANSPLANT','ACUTE-POSTSTABLE'),('EOC68-71-service','EOC68-69-IN','EOC68-69-OON','EOC41-42-coinsurance-base')),
 'deductible':condition('asserted',
    'IN inpatient hospital care is selected for the single1000USD annual medical deductible (EOC39–40;SB10). Before it is paid, full covered-service cost applies; afterward applicable sharing applies for the rest of the calendar year. It is not1000USD per admission or per selected category. EOC39 explicitly excepts Medicare-covered FQHC services; SB separately states no OON deductible. Assistance qualifications remain conditional.',
    ('SB-DEDUCTIBLE-INN','SB-DEDUCTIBLE-SERVICE-LIST'),('EOC39-40-deductible','SB10-deductible','SB2-OON-deductible')),
 'frequency_and_quantity':condition('asserted',
    'The acute row does not state a finite covered-day maximum: unlimited days only while the stay is covered according to plan rules. Cost sharing resets at each admission and transfer to a separate facility type is a new admission. Do not import psychiatric90day/60reserve/190lifetime rules.',
    ('ACUTE-RESET','ACUTE-UNLIMITED'),('EOC68-69-IN','EOC68-69-OON')),
 'covered_days':condition('asserted',
    'Formal doctor-ordered inpatient admission starts care; day before discharge is last inpatient day. Unlimited days require the stay to remain covered in accordance with plan rules; additional IN Medicare-covered days have0copay. CMS raw90 and999 remain source-specific endpoints, not personal caps or an accepted infinity conversion.',
    ('ACUTE-ADMISSION','ACUTE-UNLIMITED','ACUTE-IN-BANDS'),('EOC68-71-service','EOC68-69-IN','CMS-1a','CMS-1a1')),
 'shared_allowance':condition('unknown',
    'Known linked accumulators are annual deductible and MOOP, not hospital allowances. EOC40 gives separate IN6750 and OON9450 scopes, exclusions and stopping rules. Complete CMS/carrier budget membership and exact cross-source identity are not established by this assembly; no combined budget is inferred.',
    ('SB-MOOP-INN','SB-MOOP-OON','SB-DEDUCTIBLE-SERVICE-LIST'),('EOC39-40-deductible','EOC40-MOOP')),
 'qualification':condition('asserted',
    'Medicare-covered services follow Medicare guidelines and must be medically necessary under EOC41–43, with all printed criteria and decision discretion retained. Inpatient admission requires doctor order; transplant coverage is under certain conditions and case review/candidacy is decided by Medicare-approved center. QMB OR full Medicaid footer says deductibles/coinsurance/copayments MAY be less for Original-Medicare-covered services, without asserting individual qualification or universal zero.',
    ('ACUTE-ADMISSION','ACUTE-TRANSPLANT','R12-FOOTER-MAY-REDUCE','R12-FOOTER-QMB','R12-FOOTER-MEDICAID'),('EOC41-43-necessity','EOC68-71-service','EOC68-71-footer')),
 'exclusion':condition('unknown',
    'Chapter4section3 exclusions and the complete plan-rule dependencies have not been individually projected into this paired comparison. The row explicitly links exclusions for transplant details. Private room is conditional on medical necessity; this does not attach that qualifier to personal items. No empty exclusion set or fully reconciled coverage entitlement is asserted.',
    ('ACUTE-TRAVEL',),('EOC68-71-service','EOC41-43-necessity')),
 'waiver_and_replacement':condition('asserted',
    'Authorized OON inpatient hospital care AFTER emergency stabilization uses network hospital sharing. Preserve the authorization and stabilization antecedents together; this is not every OON stay. The minimum90day active-course PA transition, conditional assistance footer, and annual MOOP stopping rules are separate source rules, not unconditional cost waivers.',
    ('ACUTE-POSTSTABLE','R12-FOOTER-MAY-REDUCE','SB-MOOP-INN','SB-MOOP-OON'),('EOC68-69-IN','EOC41-42-PA','EOC40-MOOP','EOC68-71-footer'))}
assert set(carrier_conditions)==set(CONDITION_FAMILIES)
write('CONDITION_MEANINGS.json', {'producer_interpretation_id':'INPATIENT-PRODUCER-R1',
      'role':'source-backed producer reading, not independent approval or factual mapping',
      'carrier':carrier_conditions,
      'unknown_family_states_preserved':['referral','shared_allowance','exclusion'],
      'every_asserted_family_exhaustive':False,
      'remaining':'Complete all linked controls, per-clause source obligations and contextual CMS/carrier comparison before evidence-ready state.'})

def page_spans(kind, specs, note):
    spans=[]
    for page,begin,end in specs:
        row=page_rows[(kind,page)]
        lines=row['layout_text'].splitlines()
        quote='\n'.join(lines[begin-1:end])
        spans.append({'kind':kind,'physical_page':page,'layout_line_start':begin,
                      'layout_line_end':end,'exact_locator_text':quote,
                      'locator_text_sha256':hashlib.sha256(quote.encode()).hexdigest(),
                      'carrier_page_record_sha256':fingerprint(row),
                      'document_sha256':row['document_sha256'],
                      'layout_text_sha256':row['layout_text_sha256']})
    return {'role':'source-specific passage locator;original pixels control',
            'spans':spans,'producer_pixel_interpretation':note,'independent_new_comparison_review':None}

def parent_evidence(*ids):
    return {'role':'exact source-column parent and word bindings',
            'parents':[{'id':i,'record_sha256':fingerprint(parents[i]),
                        'word_binding_sha256':parents[i]['word_binding_sha256'],
                        'exact_source_quote':parents[i]['exact_source_quote'],
                        'original_source_page_images':parents[i]['original_source_page_images']}
                       for i in ids],
            'original_parent_file':binding(parents_path),
            'source_column_parent_completes_full_comparison':False}

evidence={
 'EOC68-IN-marker':parent_evidence('R12-SOURCE-CELL-f12a6de8b893c724e25d4aef'),
 'EOC68-69-IN':parent_evidence('R12-SOURCE-CELL-f12a6de8b893c724e25d4aef'),
 'EOC68-69-OON':parent_evidence('R12-SOURCE-CELL-8dcf53a7c58fe86a02b4198a'),
 'EOC68-71-service':parent_evidence('R12-SOURCE-CELL-3566f6a948eb78fda79d2c3e'),
 'EOC112-marker-key':page_spans('EOC',[(112,41,42)],'Asterisk is MOOP exclusion; double dagger means provider MAY need to request prior authorization. The inpatient dagger is printed in the IN column.'),
 'EOC41-42-PA':page_spans('EOC',[(41,26,29),(41,35,42),(42,3,9)],'New-enrollee active-course minimum 90-day transition; IN approval may apply; no advance OON approval required; optional OON advance coverage decision; approved treatment validity qualifications.'),
 'EOC41-network-gate':page_spans('EOC',[(41,30,34)],'Generic network/referral and PCP duties; exact POS/inpatient reconciliation remains open.'),
 'EOC39-40-deductible':page_spans('EOC',[(39,24,35),(40,3,5)],'Single 1,000 USD deductible; full-cost then sharing stages; calendar year; explicit FQHC exception; complete six-category list and colonoscopy exceptions.'),
 'EOC40-MOOP':page_spans('EOC',[(40,6,32)],'Two source-described annual limits: IN 6,750 USD and OON 9,450 USD, with their contribution/exclusion/stopping rules. No combined limit identity inferred.'),
 'EOC41-43-necessity':page_spans('EOC',[(41,18,25),(42,36,42),(43,3,16)],'General Medicare guidelines and all medical-necessity criteria, source discretion, evidentiary standards and expert-opinion fallback remain attached.'),
 'SB9-marker-key':page_spans('SB',[(9,9,10)],'Superscript 2 may require provider PA for IN benefits; the separate combined marker is not applied to an unmarked hospital row.'),
 'SB10-deductible':page_spans('SB',[(10,1,25)],'Complete selected-service annual IN deductible summary, stages and category exceptions; not an independent amount per category.'),
 'SB2-OON-deductible':page_spans('SB',[(2,8,8),(2,15,26)],'Printed row has IN selective deductible and an OON No deductible cell; original column pixels inspected.'),
 'EOC41-42-coinsurance-base':page_spans('EOC',[(41,3,13),(42,11,21)],'OON percentage multiplies the Medicare payment rate according to provider participation status, not arbitrary billed charges.'),
 'EOC68-71-footer':parent_evidence(*[i for i in parent_ids if i.startswith('R12-CMR1-FOOTER-')]),
 'FLAT-pbp_b1a_refer_yn':{'role':'exact flat-table question only;not native code authority',
                          'record':next(x for x in flat if x['field']=='pbp_b1a_refer_yn')},
 'CMS-1a':{'role':'complete original native object;control interpretations not blanket-decoded',**components[0]},
 'CMS-1a1':{'role':'separate original additional-days object;raw endpoint remains raw',**components[1]}}
write('EVIDENCE_REGISTER.json', evidence)

# R9's incomplete-record storage is used honestly. This does not silently extend
# the sealed finite-band schema, coerce999 to infinity, or discard the zero band.
identity_hold = {'state':'unresolved','reason':'L02 build-r5 exact identity is pinned, but geography is county_published_extent_unverified and geographic_variant is not established. See INPUT_BINDINGS original record.'}
def carrier_evidence(parent):
    p=parents[parent]
    pages=sorted({x['physical_page'] for x in p['exact_source_words']})
    result=[]
    for page in pages:
        words=[x for x in p['exact_source_words'] if x['physical_page']==page]
        result.append({'source_sha256':p['document_sha256'],'side':'carrier',
          'interpretation_review_id':'INPATIENT-PRODUCER-R1','pdf_page':page,
          'passage_sha256':hashlib.sha256(p['exact_source_quote'].encode()).hexdigest(),
          'location':{'source_parent_id':parent,'source_parent_record_sha256':fingerprint(p),
                      'word_binding_sha256':p['word_binding_sha256'],
                      'source_column':p['source_column'],
                      'word_ordinals':[x['word_ordinal'] for x in words],
                      'passage_hash_scope':'complete multi-page source-column parent, not isolated page excerpt'},
          'headers':['Inpatient hospital care','What you pay in-network' if p['source_column']=='cost_in_network' else 'What you pay out-of-network'],
          'footnotes':[{'marker':'double_dagger','source':'EOC68 IN sibling and EOC112 key',
                       'printed_on_this_cost_column':p['source_column']=='cost_in_network',
                       'meaning':'IN marker: provider may need to request prior authorization;not an OON marker'},
                       {'source':'EOC68–71 full-width footer','meaning':'QMB OR full Medicaid; deductible/coinsurance/copayment may be less for Original-Medicare-covered services'},
                       {'state':'unresolved','reason':'Complete linked interpretation and amendment applicability remain open.'}]})
    return result

records=[]
for net in ['IN','OON']:
    c={'identity':copy.deepcopy(identity_hold),
       'service':{'category':'inpatient_hospital_care','subtype':'EOC row including acute, rehabilitation, long-term care and other inpatient services;separate psychiatric-hospital row excluded'},
       'context':{'network':'in_network' if net=='IN' else 'out_of_network',
                  'setting':'doctor-ordered inpatient hospital admission',
                  'population':'published nominal schedule for plan members; no personal applicability',
                  'assistance_basis':'nominal schedule with conditional QMB/full-Medicaid reduction retained separately'},
       'cost':{'kind':'copayment','amount':'375','range_basis':'partial first-band anchor only; complete375/0ordered schedule in TYPED_SCHEDULES;not uniform'} if net=='IN' else {'kind':'coinsurance','amount':'40','range_basis':'published nominal percentage per stay;qualified exceptions retained'},
       'unit':{'currency_or_percentage':'USD' if net=='IN' else 'percentage','denominator':'Medicare-covered inpatient day' if net=='IN' else 'Medicare payment rate according to OON provider participation status (EOC41–42 exact passage in evidence register)','period':'each admission'},
       'boundaries':{'state':'unresolved','reason':'The complete carrier schedule has no numeric later-band endpoint. Sealed r9 day_bands requires integer end. Full typed source schedule is retained; no finite terminal or999/infinity mapping is invented.'} if net=='IN' else {'day_bands':[],'quantity':'unlimited days only while hospital stay covered in accordance with plan rules','frequency':'each Medicare-covered hospital stay','reset':'each admission; transfer to a separate facility type is a new admission'},
       'conditions':copy.deepcopy(carrier_conditions),
       'exceptions':[{'authorized_post_stabilization_OON':'network hospital cost sharing;both antecedents required'},
                     {'conditional_assistance':'QMB OR full Medicaid may reduce nominal sharing;individual qualification not assessed'},
                     {'state':'unresolved','reason':'Complete applicable plan rules, exclusions, amendment applicability and all linked conditional scopes require review.'}],
       'variant':{'kind':'base','identifier':'2026:H5652:002:000:base','enrollment_basis':'plan membership;not optional dental rider','effective_period':'2026-01-01/2026-12-31'},
       'shared_budgets':[{'id':'2026:H5652:002:000:medical_deductible_candidate','state':'unresolved','reason':'Known shared1000annual deductible;complete source membership/cross-source identity review remains.'},
                         {'id':f'2026:H5652:002:000:{net}_MOOP_candidate','state':'unresolved','reason':'Source-specific annual maximum and stopping rules retained;not accepted CMS/carrier budget equivalence.'}],
       'evidence':carrier_evidence('R12-SOURCE-CELL-f12a6de8b893c724e25d4aef' if net=='IN' else 'R12-SOURCE-CELL-8dcf53a7c58fe86a02b4198a')}
    cms=copy.deepcopy(c)
    cms['service']={'category':'1a','subtype':'native categoryTypeId 1; complete mapping to broader carrier inpatient row is not yet reviewed'}
    cms['context']={'state':'unresolved','reason':'Exact native base/POS control interpretations and assistance/context mappings require source-specific review; raw components remain pinned.'}
    cms['unit']={'state':'unresolved','reason':'Numeric rate/day operands are retained exactly;the complete native period, activation and POS percentage-base interpretation remains open. Carrier unit is not copied as native authority.'}
    cms['shared_budgets']=[{'id':'2026:H5652:002:000:native-plan-accumulator-unresolved',
                           'state':'unresolved','reason':'Exact native global accumulator identity and membership are not inferred from carrier budget labels.'}]
    cms['conditions']={family:condition('unknown',
        f'{family}: Exact complete CMS controls and carrier relationship remain to be individually reconciled. SOURCE_COMPONENTS retains original native objects and exact flat questions; no native enum meaning is transferred from flat codebook.') for family in CONDITION_FAMILIES}
    cms['boundaries']={'day_bands':[{'begin':1,'end':7,'amount':'375.00','unit':'USD/day'},{'begin':8,'end':90,'amount':'0.00','unit':'USD/day'}],
                       'quantity':{'state':'unresolved','reason':'Base1a raw schedule ends90;additional1a1 raw91–999 and unlimited control remain separate;complete combined interpretation unresolved.'},
                       'frequency':{'state':'unresolved','reason':'Native benefit-period/control correspondence not inherited from flat enum.'},'reset':'unresolved'} if net=='IN' else {'state':'unresolved','reason':'POS controls retain40raw percentage but complete per-stay/application/network scope and additional-day interaction remain to be reviewed.'}
    cms['exceptions']=[{'state':'unresolved','reason':'All CMS activation, enclosing controls and exceptions remain attached to original native components;complete interpretation pending.'}]
    cms['evidence']=[{'source_sha256':'65077aeb8deb6e82eaeddc8e32b2b1a810d1df2ca814a69b1d24401f4f5cbbe3',
                     'side':'cms','interpretation_review_id':'INPATIENT-PRODUCER-R1',
                     'member':'H5652-002-000-2026.json',
                     'pointer':'/pbp/0/benefitDetails/benefitDetailsInfo/0/benefitDetails/'+('TierCopaymentComponent' if net=='IN' else 'CostShareABPOSComponent')}]
    result=compare(cms,c)
    assert result['outcome']=='insufficient_evidence'
    records.append({'id':f'R12-INPATIENT-STRUCTURED-{net}-R1','inventory_root_ids':sorted(scope_ids),
                    'cms':cms,'carrier':c,'outcome':result['outcome'],
                    'interpretation_review_receipt':None,'accepted_for_reference':False})
write('COMPARISON_RECORDS.json', records)
write('ORIGINAL_BINDINGS.json', {'original_count':4675,'case_scope_ids':case['canonical_ids'],
      'case_scope_is_fully_reconciled':False,'assembly_scope':[{'id':i,'kind':originals[i]['kind'],
      'content_sha256':before[i],'states':originals[i]['states'],
      'relationship':'source case or direct locator dependency;not whole-original approval'} for i in sorted(scope_ids)],
      'original_accepted_535_entries_inherited':False,'new_accepted':0,'inventory_changes':0,
      'original_universe_digest':fingerprint([originals[i] for i in sorted(originals)])})
write('SOURCE_PAGE_LOCATORS.json', [{'kind':kind,'physical_page':page,
      'carrier_page_record_sha256':fingerprint(page_rows[(kind,page)]),
      'source_document_sha256':page_rows[(kind,page)]['document_sha256'],
      'layout_text_sha256':page_rows[(kind,page)]['layout_text_sha256'],
      'layout_lines':[{'line':i+1,'text':line} for i,line in enumerate(page_rows[(kind,page)]['layout_text'].splitlines())],
      'whole_page_is_complete_meaning_evidence':False} for kind,page in image_names])

work=[
 ('MODEL-OPEN-END','Add a separately versioned schema/comparator representation for nonnumeric terminal/open band, with exact source basis and conditional unlimited coverage. Preserve sealed r9. Never decode999as infinity. Finite varying schedules remain representable by ordered finite bands.'),
 ('CMS-CONTROLS','Resolve native1a/1a1/base/POS activation and period controls against original official format evidence. Retain flat interval3=Two versus native raw2;no universal code transfer.'),
 ('CMS-CARRIER-SCHEDULE','Compare complete1a plus1a1 source roles with the carrier375/0schedule and each-admission reset. Keep the0stay component separate and all source-specific endpoints. Review any exact mapping with full fingerprints.'),
 ('REFERRAL-SCOPE','Reconcile exact flatNo referral with generic EOCnetwork/referral gate and full POS exceptions;doctor order remains different.'),
 ('AUTHORIZATION-SCOPE','Bind each PA clause/transition/validity/OON no-advance-approval statement and specific stabilized-emergency authorization exception;do not flatten modalities.'),
 ('GLOBAL-ACCUMULATORS','Project exact deductible/MOOP scope, all membership/exclusions/stopping rules into each source observation. One annual shared deductible is not one per admission/service.'),
 ('PLAN-RULES-EXCLUSIONS','Complete linked Chapter4section3 and applicable plan-rule/necessity/transplant/assistance clauses individually, preserving exceptions and nonexhaustive lists.'),
 ('GEOGRAPHIC-IDENTITY','Complete exact county extent/geographic-variant evidence;L02build-r5 currently records county_published_extent_unverified.'),
 ('AMENDMENT','Resolve original required-missing amendment applicability predicate through permitted applicable original sources;no source-stop bypass.'),
 ('INDEPENDENT-COMPARISON','Independently compare frozen source-expected decisions with this exact candidate and complete linked original dispositions before evidence-ready status.'),
 ('EXACT-RELEASE','Only after required evidence/comparison/review work, prepare exact new-release entry list and limitations for owner acceptance;build authorization does not inherit r4acceptance.')]
write('REMAINING_WORK.json', {'tasks':[{'id':i,'required_action':a,'state':'open','internal_work':i not in {'AMENDMENT','EXACT-RELEASE'}} for i,a in work],
      'all_case_obligations_complete':False,'all_remaining_work_external':False})
write('ASSEMBLY_RECEIPT.json', {'schema':'daylight.inpatient-comparison-assembly.v1',
      'offering_id':'2026:H5652:002:000','structured_records':2,
      'source_leaf_records':len(selected),'source_parents':len(selected_parents),
      'flat_question_records':len(flat),'native_whole_objects':2,
      'case_scope_originals':len(case['canonical_ids']),'assembly_scope_originals':len(scope_ids),
      'all_originals_retained':len(originals),'required_missing_unchanged':16,
      'outcome':'insufficient_evidence','new_fully_supported':0,'new_awaiting_review':0,
      'new_accepted':0,'proposed_inventory_delta':0,'actual_inventory_delta':0,
      'new_schema_or_comparator_adopted':False,'source_extraction_is_independent':False,
      'compared_originals_completed':0,'database_or_app_mutations':False})
assert before == {x['id']:fingerprint(x) for x in read(original_path)}
print(json.dumps({'output':str(OUT),'records':2,'scope_ids':len(scope_ids), 'leaves':len(selected)}))
