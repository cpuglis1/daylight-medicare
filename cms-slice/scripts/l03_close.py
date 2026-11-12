"""Additive L03 r3: explicit decisions, source controls and rider dispositions.

An investigation disposition is deliberately separate from agreement, completeness
and acceptance. Carrier omissions remain gaps; a numeric occurrence is not proof.
"""
from __future__ import annotations
import collections,gzip,json,pathlib,re
from l03_close_sources import *

def read(p):
    with gzip.open(p,'rt') as f:
        for l in f:yield json.loads(l)
def write(p,rows):
    with gzip.GzipFile(filename=str(p),mode='wb',mtime=0) as g:
        for r in rows:g.write((json.dumps(r,ensure_ascii=False)+'\n').encode())
E={}
def ep(o,k,n):
    v=evidence(o,k,n);key=v['document_sha256']+':'+str(n)
    E[key]=v;return key
def hits(o,pat,k='EOC',medical=False):
    ns=[]
    for n,p in enumerate(pages(o,k),1):
        if medical and not (re.search(r'Chapter\s+4\b',p[:500],re.I) and n>25):continue
        if re.search(pat,p,re.I|re.M):ns.append(ep(o,k,n))
    return ns
ROWS=list(read(R2/'carrier-chart-rows.jsonl.gz'))
ROWMAP={r['id']:r for r in ROWS}
def chart_evidence(x):
    return sorted({ep(x['offering_id'],'EOC',n) for rid in x['EOC_chart_row_ids'] for n in ROWMAP[rid]['pages']})
def text(ids):return '\n'.join(E[i]['text']for i in ids)
def extra_source(id,page):
    s=next(x for x in json.loads((R3/'source-manifest.json').read_text())['sources']if x['id']==id)
    p=pathlib.Path(s['text_path']).read_text().split('\f')[page-1]
    k=s['sha256']+':'+str(page);E[k]={'document_sha256':s['sha256'],'url':s['url'],'kind':s['kind'],'pdf_page':page,'page_text_sha256':sha(p.encode()),'line_start':1,'line_end':len(p.splitlines()),'text':'\n'.join(p.splitlines())};return k

NUCLEAR={'H1036:217':6,'H1036:290':6,'H1036:310':7,'H1036:311':7,'H5216:257':9,'R5826:005':8,'R5826:018':8,'R5826:074':8}
DIABETES={'H5427:083':15,'H5427:091':17,'H5427:105':17,'H5594:035':20}
BASE={'2026:H1036:340:000','2026:H1609:078:000'}

def amount_decisions():
    out=[]
    for i,x in enumerate(json.loads((R2/'unlocated-amount-issues.json').read_text()),1):
        o=x['offering_id'];c=x['category_code'];cp=':'.join(o.split(':')[1:3]);ids=chart_evidence(x)
        state=None;decision=None;gap=None;literal=False
        if c=='8b1' and cp in NUCLEAR and x['triage'].startswith('diagnostic'):
            ids=[ep(o,'SB',NUCLEAR[cp])]
            state='bound_exact_service_setting';literal=True
            decision='Maximum is the in-network outpatient-hospital nuclear medicine charge, not a flat charge for every diagnostic radiology service. Freestanding nuclear medicine and MRI/CT have separate prices; retain PA and any plan deductible.'
        elif c=='11c1' and cp in DIABETES:
            ids=[ep(o,'SB',DIABETES[cp])];state='reconciled_channel_and_charge_type'
            decision='Carrier publishes $0 copayment for diabetic monitors, lancets and test strips through plan mail order, and 20% coinsurance at a retail pharmacy. PA may be required. Preserve $0 copay and 0% source bound as different typed statements; do not publish all-channel free supplies.'
        elif c=='7g' and o not in BASE:
            ids=hits(o,r'Acupuncture',medical=True)+hits(o,r'Physician/Practitioner services',medical=True)+[extra_source('CMS-2026-SERVICE-CATEGORY',4)]
            state='bound_subservice_with_CMS_category_bridge';literal=True
            decision='2026 CMS category instructions explicitly include Medicare-covered acupuncture by otherwise unlisted practitioners in 7g. EOC acupuncture row states $20 in-network per service, with chronic-low-back-pain criteria and visit limits. This binds the maximum to acupuncture; other practitioner visits must use their own applicable EOC row, never a blanket $20.'
        elif c=='14c4':
            ids=hits(o,r'SilverSneakers',medical=True);state='reconciled_no_charge_program'
            decision='EOC explicitly says no cost to participate in SilverSneakers. Basic membership/participating facilities and the described home alternative remain attached. No general gym reimbursement or cash allowance inferred.'
        elif c=='14c8':
            ids=hits(o,r'Everyday Options Allowance|Assistive and safety devices',medical=True);state='reconciled_shared_allowance'
            decision='Home safety items are eligible purchases from the shared $200 monthly Everyday Options Allowance, $0 copay to participate. Unused amounts expire monthly; approved vendor/payment rules apply. Food/utilities require separate SSBCI qualification. This is not an unlimited home modification entitlement or a second $200 allowance.'
        elif c=='13b':
            pat=r'Healthy Options Allowance|Over.the.Counter.*Wallet'
            ids=hits(o,pat,medical=True);state='reconciled_no_charge_limited_wallet'
            decision='EOC states no coinsurance/copayment/deductible to participate in the named OTC/Healthy Options wallet. Preserve its exact allowance, reset/expiry, approved products and vendors. SSBCI extensions are conditional and may replace or share the same wallet; zero participation charge does not make every product unlimited or free.'
        elif c=='14c15':
            ids=hits(o,r'^\s*Wigs\b',medical=True);state='reconciled_no_charge_allowance'
            decision='EOC covers wigs for chemotherapy-related hair loss with $400 annual allowance, no coinsurance/copayment/deductible within benefit; member pays above allowance. Supplier and receipt/reimbursement instructions remain attached.'
        elif c=='13d':
            ids=hits(o,r'Annual wellness visit|Breast cancer screening|screening mammogram',medical=True);state='held_supplemental_scope_ambiguity'
            gap='AETNA-OTHER1'
            decision='PBP Other 1 is named annual wellness exam and screening mammography. EOC prices its named screening/wellness services at no charge, but does not separately identify which extension makes Other 1 non-Medicare-covered. Retain the documented services and qualifications; do not promise an additional visit, expanded age eligibility or frequency from the PBP label alone.'
        elif c=='13e':
            ids=hits(o,r'Colorectal cancer screening|Screening Guaiac|fecal.occult|fecal immunochemical',medical=True);state='held_supplemental_scope_ambiguity'
            gap='AETNA-OTHER2'
            decision='PBP Other 2 says additional gFOBT/FIT not covered by Medicare. EOC retains twice-per-calendar-year stool screening and zero-charge FIT lab language where stated. It does not explicitly price the entire extra non-Medicare subset as a separate benefit. Preserve exact test, age, frequency and preventive/diagnostic distinctions; hold the broad extra-test claim.'
        elif c=='15-1' and o not in BASE:
            ids=sorted(set(ids+hits(o,r'Part B insulin|Part B drugs|rebatable',medical=True)))
            if o in {'2026:H5410:047:000','2026:H5410:055:000'}:
                ids+=hits(o,r'If you receive Medicaid cost sharing assistance|If you are eligible for Medicare cost sharing assistance',medical=True)
                state='reconciled_assistance_qualified_insulin_zero'
                decision='HealthSpring EOC attaches no-charge Medicare services to Medicaid cost-sharing assistance and separately caps one-month Part B insulin at $35 with no deductible. These are conditional published statements. Do not apply assistance-qualified $0 to an unqualified member.'
            else:
                state='held_insulin_lower_bound';gap='PARTB-INSULIN-LOWER-BOUND'
                decision='Carrier publishes the one-month Part B insulin ceiling and applicable no-deductible rule. The PBP lower 0% bound is not independently established for insulin by the generic rebatable-drug statement or the $35 ceiling. Keep those distinct; no zero-cost insulin promise or personal drug calculation.'
        elif c in ['15-2','15-3'] and o=='2026:H5410:047:000':
            ids=[ep(o,'EOC',48),ep(o,'EOC',35)];state='bound_carrier_percentage_range';literal=True
            decision='HealthSpring EOC explicitly prints $0 or 0–20% coinsurance for the named Part B chemotherapy/other drugs. The asterisk points to Medicaid cost-sharing assistance; retain the range, PA/step therapy and drug-administration qualifications. This is not a flat 0% promise.'
        elif c.startswith('15-'):
            ids=sorted(set(ids+hits(o,r'rebatable|Part B drugs|Part B insulin',medical=True)))
            if o in BASE:
                state='held_nominal_vs_assistance_schedule';gap='DSNP-PUBLISHED-BASIS'
                decision='PBP nominal drug percentage/range and EOC assistance-protected no-charge schedule have different published bases. Preserve each, including Part B insulin cap, drug administration and rebatable-drug qualifications. No personal Medicaid category or drug price inferred; raw nominal percentage lacks same-basis carrier corroboration.'
            elif re.search(r'rebatable|\$0.*Avastin|Avastin.*\$0',text(ids),re.I):
                state='reconciled_default_vs_conditional_lower_bound'
                decision='PBP records a lower coinsurance bound of 0; EOC publishes the usual charge and a lower-charge/rebatable or named zero-charge drug exception. Carrier language does not establish 0% for every covered drug. Retain default, insulin monthly cap, step therapy/PA and administration charge separately. Drug-specific price/quarterly determination belongs to L05/L06, outside this reference.'
            else:
                state='held_unconfirmed_PartB_lower_bound';gap='PARTB-LOWER-BOUND'
                decision='Full EOC Part B chart and SB inspected. A lower charge or $0 copay in another context cannot corroborate this 0% bound. Retain the published default and conditions; hold any free-drug or exact minimum claim.'
        elif c in ['4c2','4c3'] and o not in BASE or c in ['4c1','4c2','4c3'] and o in BASE:
            ids=sorted(set(ids+hits(o,r'worldwide|outside of the U.S.|outside of the United States')+hits(o,r'worldwide|outside of the U.S.',k='SB')))
            state='held_geographic_price_basis';gap='HUMANA-WORLDWIDE'
            decision='PBP selects worldwide benefit and foreign-service copayment. SB/EOC discuss worldwide coverage and up-front payment/reimbursement at plan rates; urgent-care/ambulance chart prices do not explicitly identify the same foreign-service copayment. Chapter 7 reimbursement instructions do not settle that price. Publish coverage/reimbursement caveat only; hold the exact foreign urgent/transport price and waiver as a same-basis claim.'
        elif o in BASE:
            if x['CMS_value'] in ['0','0.00']:
                state='reconciled_no_charge_vs_typed_zero'
                decision='EOC explicitly publishes no coinsurance/copayment/deductible for the matched covered service. Retain that carrier no-charge wording with the full-dual assistance basis; a numeric 0% is a PBP representation, not a separate universal eligibility assertion.'
            else:
                state='held_nominal_vs_assistance_schedule';gap='DSNP-PUBLISHED-BASIS'
                decision='Published PBP nominal Medicare cost sharing and carrier full-dual protected schedule differ. EOC assistance category and continuing-eligibility qualifications explain why a single personal amount cannot be inferred, but do not independently corroborate this nominal amount on the same basis. Preserve both schedules and hold the nominal consumer claim for qualified source-basis disposition.'
            ids=sorted(set(ids+([ep(o,'EOC',p)for p in [6,22,36,183]] if 'H1609'in o else [ep(o,'EOC',p)for p in [44,45,46]])))
        elif c=='11b2' and o=='2026:H1035:019:000':
            ids=[ep(o,'SB',18),ep(o,'SB',19),ep(o,'EOC',84),ep(o,'EOC',94),extra_source('CMS-2026-SERVICE-CATEGORY',6)]
            state='held_supply_subtype_scope';gap='BLUE-MEDICAL-SUPPLIES'
            decision='CMS 11b medical supplies include dressings/splints/casts, distinct from prosthetics and diabetes supplies. EOC prosthetic-related supplies cost 20%, hospital supplies are bundled in applicable outpatient cost, SB DME has its own 0%/20% distinction. None proves a universal standalone 0% medical-supply charge. Preserve these subtypes; hold the flat medical-supply claim.'
        if not state:raise ValueError('No reviewed disposition '+str(x))
        if not ids:raise ValueError('No carrier evidence '+str(x))
        out.append({**x,'issue_id':f'L03-R3-AMT-{i:03}','r3_state':state,'decision':decision,'remaining_gap_id':gap,'carrier_evidence_ids':sorted(set(ids)),'literal_same_unit_amount_binding':literal,'investigation_complete':True,'accepted':False,'consumer_usable':False,'reviewer':'AI source comparison; human acceptance pending'})
    dump(R3/'amount-issue-decisions.json',out)
    return out

def rider_class(context):
    s=context.lower()
    if re.search(r'personal information|your phi|amend your|privacy|correction.*information',s):return 'privacy_right_not_benefit_rider'
    if re.search(r'lis rider|low.income subsidy|extra help|prescription drugs',s):return 'member_specific_LIS_insert_outside_L03'
    if re.search(r'notices|affect your coverage|sometimes called',s):return 'generic_future_notice_not_identified_amendment'
    return 'unclassified_reference_requires_review'

def riders():
    out=[]
    for i,r in enumerate(json.loads((R2/'rider-and-revision-reference-register.json').read_text()),1):
        o=r['offering_id'];p=r['pdf_page'];ls=pages(o)[p-1].splitlines();n=r['line'];ctx='\n'.join(ls[max(0,n-6):min(len(ls),n+5)])
        cls=rider_class(ctx)
        out.append({**r,'id':f'L03-R3-RIDER-{i:03}','context':ctx,'classification':cls,'evidence_id':ep(o,'EOC',p),'action':{'privacy_right_not_benefit_rider':'No medical benefit rider acquisition required.','member_specific_LIS_insert_outside_L03':'Retain dependency and public plan premium reference; personalized Part D assistance insert is not an L03 missing medical rider.','generic_future_notice_not_identified_amendment':'Retain annual EOC plus as-of public route check; no dated/applicable amendment identified by this sentence.'}.get(cls,'Inspect full source page before closing.'),'accepted':False})
    dump(R3/'rider-dispositions.json',out);return out

def condition_rule(x):
    l=x['label'].lower();v=x['normalized'].get('value');f=x['source']['field'];role=x['semantic_role']
    if 'step therapy' in l:return 'step_therapy_control','A plan-level or benefit-family step-therapy selection. Preserve the selected step direction and exact carrier drug criteria reference. It never establishes an individual drug approval or denial.'
    if '3 day inpatient' in l or 'hospital days required prior' in l:return 'SNF_prior_hospital_stay','SNF qualifying-hospital-stay waiver/control only. Preserve the source required day count, benefit period and medically necessary skilled care; this is not an inpatient cost band or an automatic SNF admission.'
    if 'day of discharge' in l:return 'discharge_day_charge','Controls charging on the discharge day within this benefit. Preserve admission/day bands and benefit-period rules; do not infer all other services on that day are free.'
    if 'medicare-defined cost share' in l:return 'Medicare_defined_charge_control','Use Medicare-defined tier charge only where this source selects it. Federal charge constants are a dependency on L01, with year and benefit basis; do not overwrite negotiated copays.'
    if 'specified manufacturers' in l:return 'manufacturer_restriction','Manufacturer/brand restriction with medically necessary exception process where stated. A covered category does not establish every product or device is covered.'
    if 'additional telehealth' in l:return 'additional_telehealth_activation','Additional Part B telehealth selection is distinct from baseline Medicare telehealth. Retain selected services, approved platform/provider, setting and same-service cost-sharing qualifications.'
    if 'naloxone' in l or 'nicotine replacement' in l:return 'OTC_product_scope','Specific Part C OTC coverage selection. It is not prescription formulary coverage, a price feed or permission to spend outside the plan wallet/product rules.'
    if 'service name'==l:return 'plan_defined_service_name','Plan-defined Other benefit label. Preserve the entire label and source record; do not substitute a standard service or assume an additional entitlement beyond the EOC.'
    if 'select coverage'==l:return 'coverage_selection','Use selected benefits with their mandatory/optional and Medicare/non-Medicare scope. An unselected supplemental enhancement does not establish absence of basic Medicare coverage.'
    if 'other mode of delivery' in l:return 'delivery_description','Free-text delivery qualification for its own OTC/benefit context, not a coverage or price assertion.'
    if 'combined max plan benefit' in l:return 'shared_eyewear_limit_control','Combined eyewear payment allowance applies to its named group, with its period and network. Do not grant an additional allowance for every lens/frame/contact subcategory.'
    if 'preferred vendors' in l:return 'preferred_vendor_control','Vendor/manufacturer condition; never a referral requirement. Specific permitted brands and exceptions stay in carrier context.'
    if 'attestation' in l:return 'plan_attestation','Plan attestation in source submission, not an individual clinical approval or evidence every exception is modeled.'
    if 'periodicity' in l or 'period' in l and x['normalized'].get('type')=='enum':return 'period_qualified_limit','Attach the decoded period to its own allowance/visit limit. Other requires the adjacent description; never default to annual.'
    if 'copayment amount' in l and x['normalized'].get('type')=='decimal':return 'typed_charge_not_frequency','Currency amount despite earlier period/frequency heuristic. Preserve source service, network, setting and controls.'
    if role=='day_band':return 'day_or_hour_boundary','Begin/end boundaries qualify a charge band, not a cap on covered days. Preserve day/hour selector, reserve-day and benefit-period rules; 999 is retained as a source sentinel.'
    if 'waiv' in l:return 'conditional_waiver','Apply only to the named charge, named service and admission window/conditions. No waiver of unrelated charges or automatic hospital coverage inferred.'
    if 'count toward' in l:return 'accumulation_control','Controls deductible/MOOP accumulation, not whether a deductible or charge exists. Premiums, Part D and medical sharing remain distinct.'
    if 'which' in l or x['normalized'].get('type')=='enum_set':return 'selected_subservice_set','Leading-zero positions are retained and decoded with the exact 2026 dictionary. Shared parent selection applies only to named selected child services; no propagation to every sibling.'
    if 'authorization' in l:return 'conditional_prior_authorization','Yes marks a source benefit family subject to PA, not every instance. Carrier may-required language, network exceptions, emergency exceptions and transition rules remain attached. No PA is not no referral and not guaranteed payment.'
    if 'referral' in l:return 'conditional_referral','Referral is separate from prior authorization. Apply plan network/global exceptions and exact named services; no blanket requirement or absence assertion from a missing chart keyword.'
    if 'unlimited' in l:return 'scope_limited_unlimited_control','Unlimited qualifies the named covered visit/day/item count only. It does not remove medical necessity, cost sharing, other annual caps, network or benefit-period rules.'
    if 'maximum' in l or role=='limit':return 'scoped_limit','Plan payment maximum, member service MOOP and overall medical MOOP are different. Attach exact service/shared group, period, network and any over-limit member responsibility; do not add a shared cap twice.'
    if 'coinsurance' in l or 'copayment' in l or 'deductible' in l:return 'charge_type_activation','No for a charge type does not mean no total charge. Check each copay/coinsurance/service deductible and plan deductible control independently. Yes needs the corresponding typed amount and scope.'
    if 'supplemental' in l or 'type of benefit' in l:return 'benefit_scope_activation','Distinguish Medicare-covered and non-Medicare supplemental services and mandatory versus optional packages. A Part C supplemental flag does not imply the baseline Medicare service is absent.'
    if role=='network_or_setting':return 'transport_setting_or_count','Transport type/mode/trip count is not a provider participation assertion. Attach one-way/round-trip, approved destination, mileage and booking qualifications from carrier source.'
    if x['normalized'].get('type')=='decimal':return 'typed_count_or_amount','Preserve exact dictionary quantity/unit and source parent scope. Never infer a dollar amount from a numeric count or the title of a containing object.'
    if x['normalized'].get('type')=='source_text':return 'source_description','Retain complete carrier/source description and linked controls; no clinical interpretation, eligibility determination or flat benefit claim synthesized from it.'
    return 'dictionary_qualified_control','Use the exact source question and decoded answer together with its containing service and network controls. Do not turn a control into a standalone consumer benefit.'

def conditions():
    grouped={};refs=[]
    for x in read(R2/'field-comparison-complete-chart-ledger.jsonl.gz'):
        if x['comparison_state']!='condition_or_source_detail_retained_for_exact_interpretation':continue
        s=x['source'];k=(x['offering_id'],s['member'],s['record_ordinal'],s['field']);
        if k not in grouped:
            rule,meaning=condition_rule(x)
            grouped[k]={'id':'L03-R3-COND-'+sha(json.dumps(k).encode())[:20],'offering_id':x['offering_id'],'source':s,'source_label':x['label'],'raw':x['raw'],'decoded':x['normalized'],'interpretation_rule':rule,'interpretation':meaning,'benefit_record_ids':[],'category_codes':[],'EOC_chart_row_ids':[],'carrier_independent_verification':False,'consumer_usable':False,'accepted':False,'scope_state':'interpreted_source_control; carrier-native conditions retained; not independent clinical verification'}
        z=grouped[k];z['benefit_record_ids'].append(x['benefit_record_id']);z['category_codes'].append(x['category_code']);z['EOC_chart_row_ids']+=x['complete_chart_row_ids']
        refs.append({'benefit_record_id':x['benefit_record_id'],'condition_id':z['id']})
    for z in grouped.values():
        for f in ['benefit_record_ids','category_codes','EOC_chart_row_ids']:z[f]=sorted(set(z[f]))
    write(R3/'condition-interpretations.jsonl.gz',grouped.values());write(R3/'condition-service-links.jsonl.gz',refs)
    return list(grouped.values()),refs

def run():
    R3.mkdir(exist_ok=True);am=amount_decisions();ri=riders();co,links=conditions()
    dump(R3/'evidence-pages.json',E)
    s={'amount_issue_groups_investigated':len(am),'amount_dispositions':dict(collections.Counter(x['r3_state']for x in am)),'amount_same_unit_direct_bindings':sum(x['literal_same_unit_amount_binding']for x in am),'amount_remaining_source_gap_groups':sum(bool(x['remaining_gap_id'])for x in am),'amount_gap_groups_by_id':dict(collections.Counter(x['remaining_gap_id']for x in am if x['remaining_gap_id'])),'condition_field_references':len(links),'unique_source_conditions':len(co),'condition_rules':dict(collections.Counter(x['interpretation_rule']for x in co)),'rider_references':len(ri),'rider_classes':dict(collections.Counter(x['classification']for x in ri)),'evidence_pages':len(E),'accepted':False,'consumer_release':False,'market_comprehensive':False,'scope':'2026 published L03 reference, 47 documented offerings plus unchanged 25 restricted flags; research comparisons are not approval'}
    dump(R3/'decision-summary.json',s);print(json.dumps(s,indent=2))
if __name__=='__main__':run()
