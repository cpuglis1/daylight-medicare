"""Prepare an exact L03 reference allowlist; do not create acceptance."""
from __future__ import annotations
import collections,csv,datetime,gzip,io,json,pathlib,zipfile
from l03_close_sources import *
from l03_close_reference import verify as verify_r3
from l03_scoped_reference import ROOT,REPO,R3_PIN,REQUIRED_ACKS
from l03_validate import resolve,equal

PACKAGE='L03-PUBLISHED-COLLIER-2026-bounded-r4'
RULES={
'DSNP-PUBLISHED-BASIS':'Keep the carrier assistance-qualified schedule separate from raw nominal CMS charges. No universal or personal charge; uncorroborated nominal amounts remain unavailable.',
'HUMANA-WORLDWIDE':'Use only carrier-confirmed coverage and upfront-payment/reimbursement qualifications. Exact disputed foreign prices and waivers remain unknown; no domestic-price substitution.',
'PARTB-INSULIN-LOWER-BOUND':'Use supported published ceilings and qualifications only. An unconfirmed zero minimum stays unknown; no free-insulin or personal-price claim.',
'AETNA-OTHER1':'Use documented wellness/mammography services with exact age/frequency terms. Do not infer additional visits, broader eligibility or an extra entitlement.',
'AETNA-OTHER2':'Use documented stool-test, frequency, setting and cost statements only. The broader extra non-Medicare test entitlement remains unknown.',
'BLUE-MEDICAL-SUPPLIES':'Use supported supply subtype statements only. The blanket standalone 0% medical-supply claim remains unknown.',
}
def load(p):return json.loads(p.read_text())
def fieldkey(o,s):return (o,s['member'],s['record_ordinal'],s['field'])
def build():
    verify_r3(expected_manifest_sha256=R3_PIN);ROOT.mkdir(exist_ok=True)
    old=load(R2/'source-led-comparison-ledger.json');issues=load(R3/'amount-issue-decisions.json');eps=load(R3/'evidence-pages.json');contexts={r['offering_id']:r for r in load(R3/'plan-condition-packets.json')}
    entries=[]
    for r in old:
        if not r['equal']:continue
        f=r['field'];value=str(r.get('expected_from_SB',r.get('expected_from_carrier')))
        if f.endswith(('_begin_day','_end_day')):unit='day';basis='Boundary of the named hospital charge band; not a covered-day cap'
        elif 'band'in f and f.endswith('_amount'):unit='USD/day';basis='Per-day charge in the named inpatient hospital band; read all band endpoints and qualifications together'
        elif 'premium'in f:unit='USD/month';basis='Published gross plan premium; federal Part B separate; assistance can change member amount; MA-only uses Part C'
        elif 'MOOP'in f:unit='USD/year';basis='Published medical cost-sharing maximum; INN and combined limits distinct; premiums and Part D excluded where stated'
        elif 'deductible'in f:unit='USD/year';basis='Published combined medical deductible with its source service-selection exceptions; not applied to every service'
        else:unit='USD/stay';basis='Published PBP base inpatient stay copayment; applicable assistance, plan deductible and carrier conditions remain attached'
        ce=r['carrier_evidence'];docc=CATALOG[ce['document_sha256']];kind=docc['document_kind'];page=pages(r['offering_id'],kind)[ce['pdf_page']-1]
        if sha(page.encode())!=ce['text_sha256']:raise ValueError('Source page hash differs '+r['id'])
        entries.append({'id':r['id'].replace(':r2:',':r4:'),'offering_id':r['offering_id'],'kind':'published_source_value','field':f,'value':value,'unit':unit,'basis':basis,'qualifications':r['qualifications'],'source_check_id':r['id'],'CMS_source':r['source'],'carrier_evidence':[ce],'carrier_context_packet':r['offering_id'],'comparison':'named source values numerically agree; exact listed scope and qualifications required','scope_warning':'This is a named source field, not a verified complete benefit package or personal charge.'})
    for r in issues:
        if r['remaining_gap_id']:continue
        direct=r['literal_same_unit_amount_binding']
        entries.append({'id':r['issue_id'].replace('R3','R4'),'offering_id':r['offering_id'],'kind':'qualified_bound_value'if direct else 'reconciliation_note','field':r['category_code']+':'+r['r3_state'],'value':r['CMS_value']if direct else None,'unit':r['unit']if direct else None,'basis':r['r3_state'],'qualifications':[r['decision']],'source_check_id':r['issue_id'],'CMS_source_fields':r['source_fields'],'carrier_evidence':[{k:v for k,v in eps[i].items()if k!='text'}for i in r['carrier_evidence_ids']],'carrier_context_packet':r['offering_id'],'comparison':'specific amount/subservice binding'if direct else 'qualified source interpretation; raw numerical minimum not released','scope_warning':'No flat parent-category charge or personal applicability may be inferred.'})
    for e in entries:
        if e['basis']=='bound_carrier_percentage_range':
            e['value_role']='minimum_of_published_0_to_20_percent_range';e['universal_zero_charge_claim_permitted']=False
        elif e['basis']=='bound_exact_service_setting':e['value_role']='in_network_outpatient_hospital_nuclear_medicine_charge; not all diagnostic radiology'
        elif e['basis']=='bound_subservice_with_CMS_category_bridge':e['value_role']='Medicare_covered_acupuncture_copay; not every practitioner service'
        elif e['kind']=='reconciliation_note':e['value_role']='interpretation_note; no numeric model input'
        else:e['value_role']='exact_named_published_source_field_with_all_attached_qualifications'
        if 'hospital'in e['field']:
            e['qualifications'].append('Published hospital charge only. Any applicable plan or service deductible, assistance rule, authorization/network requirement and coverage limit remains separate; no all-in hospital bill is established.')
    dump(ROOT/'entries.json',entries);held=[{k:r[k]for k in ['issue_id','offering_id','category_code','CMS_value','unit','remaining_gap_id','decision','carrier_evidence_ids']}for r in issues if r['remaining_gap_id']];dump(ROOT/'held-claims.json',held)
    dispositions=[]
    for id,wording in RULES.items():
        hs=[h for h in held if h['remaining_gap_id']==id]
        dispositions.append({'id':id,'wording_for_review':wording,'issue_ids':[h['issue_id']for h in hs],'offering_ids':sorted({h['offering_id']for h in hs}),'source_truth_status':'unresolved','proposed_review_result':'accept held/narrow reference treatment; does not resolve missing source fact'})
    dump(ROOT/'dispositions.json',dispositions)
    plans=load(R3/'offering-status.json')
    for p in plans:
        p['candidate_entry_ids']=[e['id']for e in entries if e['offering_id']==p['offering_id']]
        p['all_benefits_complete']=False;p['accepted']=False;p['consumer_usable']=False
    dump(ROOT/'offering-status.json',plans)
    dump(ROOT/'scope.json',{'package_id':PACKAGE,'year':2026,'source_snapshot_date':'2026-10-25','purpose':'Proposed phased published-reference release under D77, not closure of full L03 comprehensive coverage','numeric_source_observations':sum(e['value']is not None for e in entries),'qualified_interpretation_notes':sum(e['value']is None for e in entries),'entries_total':len(entries),'documented_offerings':47,'observed_offerings':72,'restricted_offerings':25,'field_types_from_r2':sorted({r['field']for r in old if r['equal']}),'raw_data_in_parent_revisions_retained':True,'all_displayed_or_used_reference_entries_must_include_qualifications_and_evidence':True,'other_values_are_retained_only_or_held':True,'PA_referral_782_not_released_as_definite_requirements':True,'r2_value_occurrences_do_not_auto_release':True,'unmodeled_benefits_not_noncoverage':True,'L01_acceptance_inherited':False,'personal_applicability':False,'personal_total':False,'ranking':False,'all_market_complete':False,'whole_L03_complete':False,'UI_or_deployment_included':False})
    dump(ROOT/'review-packet.json',{'package_id':PACKAGE,'status':'candidate_requires_actual_L03_review','reviewer_name_proposed':'Chris Puglisi','reviewer_role_required':'Role/qualification for this narrow L03 published-reference review, with independence from sales incentives','decision_not_inferred_from_question':True,'accepted_entry_ids_proposed':sorted(e['id']for e in entries),'accepted_dispositions_proposed':{d['id']:sha(json.dumps(d,sort_keys=True,separators=(',',':')).encode())for d in dispositions},'required_acknowledgements':REQUIRED_ACKS,'remaining_source_gap_groups':len(held),'review_accepts_unknowns_as_unknowns_not_as_validated_values':True,'MVP_effect':'May supply a reviewed reference subset to a separately approved MVP integration. Does not establish complete plan comparison or authorize UI/deployment/personal advice.'})
    dump(ROOT/'candidate-review-receipt.json',{'schema':'l03-bounded-review/1','package_id':PACKAGE,'decision':'pending','reviewer_name':None,'reviewer_role':None,'reviewed_at_utc':None,'receipt':None,'accepted_entry_ids':[],'accepted_dispositions':{},'acknowledgements':{},'revoked':False,'manifest_sha256':None})
    # Independent source checks compare exact CMS JSON pointers or tabular locators.
    checks=[]
    def check(name,ok,detail):
        checks.append({'name':name,'passed':bool(ok),'detail':detail})
        if not ok:raise ValueError(name+': '+str(detail))
    check('input_partition',len(old)==438 and sum(r['equal']for r in old)==436 and len(issues)==252 and len(held)==153,'438 prior checks: 436 matching, two held; 252 issue groups: 99 candidate decisions, 153 holds')
    check('candidate_entry_inventory',len(entries)==535 and len({e['id']for e in entries})==535 and sum(e['value']is not None for e in entries)==451,'451 numeric observations plus 84 interpretation notes, not a benefit-completeness denominator')
    landscape=[]
    pbp_archive=REPO/'docs/data/l02-ma-availability-2026-10-25/acquisition-r1/raw/65077aeb8deb6e82eaeddc8e32b2b1a810d1df2ca814a69b1d24401f4f5cbbe3'
    assert sha(pbp_archive.read_bytes())==pbp_archive.name
    with zipfile.ZipFile(pbp_archive)as z:
        for e in entries:
            if 'CMS_source'not in e:continue
            ss=e['CMS_source']
            if 'pointer'not in ss:landscape.append(e);continue
            b=z.read(ss['member']);assert sha(b)==ss['member_sha256'];assert equal(resolve(json.loads(b),ss['pointer']),e['value'])
    ss=landscape[0]['CMS_source'];archive=REPO/'docs/data/l02-ma-availability-2026-10-25/acquisition-r1/raw'/ss['archive_sha256'];assert sha(archive.read_bytes())==ss['archive_sha256']
    with zipfile.ZipFile(archive)as z:b=z.read(ss['member'])
    assert sha(b)==ss['member_sha256'];wanted={e['CMS_source']['record_ordinal']for e in landscape};rr={n:r for n,r in enumerate(csv.DictReader(io.StringIO(b.decode('utf-8-sig'))),1)if n in wanted}
    for e in landscape:
        ss=e['CMS_source'];raw=rr[ss['record_ordinal']][ss['field']].strip().replace('$','').replace(',','');assert equal(raw,e['value'])
    check('436_CMS_JSON_and_Landscape_source_values',True,'Exact pinned archive/member hashes, JSON pointers or CSV record/field locators')
    tab={}
    with gzip.open(R1/'table-fields.jsonl.gz','rt')as f:
        for l in f:
            x=json.loads(l);tab[fieldkey(x['offering_id'],x['source'])]=x
    for e in entries:
        for f in e.get('CMS_source_fields',[]):
            row=tab[fieldkey(e['offering_id'],f['source'])];assert row['raw']==f['raw']
            if e['value']is not None:assert equal(row['raw'],e['value'])
    check('99_r3_source_decisions_exact_field_locators',True,'All listed tabular source fields remain exact; interpretation notes do not publish their raw bound as a number')
    check('all_47_documented_offerings_have_entries',len({e['offering_id']for e in entries})==47,'Coverage is entry scope only, not complete benefits')
    check('restricted_offerings_have_no_released_entries',sum(p['carrier_document_state']=='restricted'for p in plans)==25 and all(not p['candidate_entry_ids']for p in plans if p['carrier_document_state']=='restricted'),'All 72 offering states preserved; 25 restrictions visible')
    check('six_dispositions_cover_exact_153_holds',len(dispositions)==6 and sorted(i for d in dispositions for i in d['issue_ids'])==sorted(h['issue_id']for h in held),'Disposition review never marks source truth resolved')
    check('conditions_and_source_evidence_attached',all(e['qualifications']and e['carrier_evidence']and e['carrier_context_packet']in contexts for e in entries),'Each entry returns its qualifiers, source locator and plan context together')
    check('no_acceptance_inherited',load(ROOT/'candidate-review-receipt.json')['decision']=='pending','No production registry written, no owner acceptance invented')
    protected=load(DATA/'protected-before.json');changed=[f for f,h in protected.items()if not(REPO/f).is_file()or sha((REPO/f).read_bytes())!=h]
    check('protected_files_unchanged',not changed,{'checked':len(protected),'changed':changed})
    dump(ROOT/'validation.json',{'passed':True,'checks':checks,'scope':'Exact allowlist/provenance/accounting validation; final source interpretation acceptance pending; no comprehensive benefit approval'})
    return entries,dispositions
def seal():
    code=['cms-slice/scripts/l03_scoped_reference.py','cms-slice/scripts/l03_scoped_build.py','cms-slice/tests/test_l03_scoped_reference.py']
    m={'schema':'l03-bounded-manifest/1','package_id':PACKAGE,'parent_r3_manifest_sha256':R3_PIN,'files_sha256':{p.name:sha(p.read_bytes())for p in sorted(ROOT.iterdir())if p.is_file()and p.name!='manifest.json'},'code_sha256':{p:sha((REPO/p).read_bytes())for p in code},'review_status':'pending'}
    dump(ROOT/'manifest.json',m);return sha((ROOT/'manifest.json').read_bytes())
if __name__=='__main__':
    es,ds=build();print(json.dumps({'entries':len(es),'dispositions':len(ds),'manifest_sha256':seal()}))
