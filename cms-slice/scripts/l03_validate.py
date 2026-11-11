#!/usr/bin/env python3
"""Evidence-led L03 validation. Technical passes do not establish completeness."""
from __future__ import annotations
import collections,csv,gzip,io,json,pathlib,zipfile
from decimal import Decimal,InvalidOperation
from l03_reference_build import DATA,L02,PBP_SHA,sha,dump,leaves,normalize

def resolve(obj,pointer):
    for k in pointer.strip('/').split('/'):
        k=k.replace('~1','/').replace('~0','~')
        obj=obj[int(k)] if isinstance(obj,list) else obj[k]
    return obj

def equal(a,b):
    if a in [None,''] or b in [None,'']:return a==b
    try:return Decimal(str(a))==Decimal(str(b))
    except InvalidOperation:return str(a)==str(b)

def run(root=DATA):
    out=root/'build-r1';checks=[];comparisons=[]
    def check(name,ok,detail=None):checks.append({'check':name,'passed':bool(ok),'detail':detail})
    market=json.loads((out/'market-manifest.json').read_text());offerings=market['observed_offerings'];ids={o['id'] for o in offerings}
    archive=L02/'acquisition-r1/raw'/PBP_SHA;check('PBP archive pinned',sha(archive.read_bytes())==PBP_SHA)
    objects={};raw_by_id={};member_hash={}
    with zipfile.ZipFile(archive) as z:
        for o in offerings:
            member=f"{o['contract']}-{o['plan']}-{o['segment']}-2026.json";b=z.read(member);obj=json.loads(b);objects[o['id']]=obj;member_hash[o['id']]=sha(b)
            raw_by_id[o['id']]=dict(leaves(obj))
    n=0;seen=collections.Counter();pointer_failures=[]
    for line in gzip.open(out/'json-leaves.jsonl.gz','rt'):
        rec=json.loads(line);n+=1;seen[rec['offering_id']]+=1
        if rec['member_sha256']!=member_hash[rec['offering_id']] or raw_by_id[rec['offering_id']].get(rec['pointer'],'ABSENT')!=rec['raw']:pointer_failures.append(rec['pointer'])
    check('Every retained JSON leaf equals its exact source pointer',not pointer_failures,{'leaf_instances':n,'failures':len(pointer_failures)})
    check('Every input plan retained every JSON leaf',all(seen[oid]==len(raw_by_id[oid]) for oid in ids),{'plans':len(ids)})
    rows={};field_instances=0;raw_blanks=0
    for line in gzip.open(out/'table-rows.jsonl.gz','rt'):
        rec=json.loads(line);rows.setdefault(rec['offering_id'],{}).setdefault(rec['source']['member'],[]).append(rec)
    for line in gzip.open(out/'table-fields.jsonl.gz','rt'):
        rec=json.loads(line);field_instances+=1
        if rec['raw']=='':raw_blanks+=1
        if rec['raw']=='' and rec['normalized']['value'] is not None and rec['normalized']['state']!='retained_other_layer_L02':raise ValueError('Blank became value')
    check('Table rows cover all input offerings',set(rows)==ids)
    check('Blank source fields remain explicit',raw_blanks>0,{'blank_instances':raw_blanks,'total_table_field_instances':field_instances})
    dd=json.loads((out/'field-dictionary.json').read_text())['fields'];dictionary={(d['file'].lower(),d['name']):d for d in dd}
    def table(oid,member,field):
        a=rows[oid].get(member,[])
        if len(a)!=1:raise ValueError(f'Nonunique table selection {oid} {member}')
        return a[0]['raw'].get(field)
    # Independent comparisons between official table and JSON representations.
    for oid,obj in objects.items():
        p=obj['pbp'][0];b=p['benefitDetails']['benefitDetailsInfo'];hospital=next(x for x in b if x['categoryCode']=='1a')
        interval=hospital.get('benefitDetails',{}).get('TierCopaymentComponent',{}).get('bdCopaymentTier1DayIntervalStay',{})
        for band in [1,2,3]:
            for j,tname in [('CopaymentAmount','amt'),('BeginDay','bgnd'),('EndDay','endd')]:
                jkey=f'bdDayInterval{band}{j}';tkey=f'pbp_b1a_copay_mcs_{tname}_int{band}_t1';a=table(oid,'pbp_b1a_inpat_hosp.txt',tkey);v=interval.get(jkey)
                if a not in [None,''] or v not in [None,'']:
                    comparisons.append({'offering_id':oid,'field':tkey,'kind':'CMS_table_vs_JSON_hospital_band','table_value':a,'json_value':v,'equal':equal(a,v),'carrier_corroborated':False})
        rx=p.get('rx',{}).get('rxDetails',{}).get('rxSetup',{}).get('rxCostShare',{}).get('rxCostShareDetails',{}) if p.get('rx',{}).get('rxDetails') else {}
        a=table(oid,'pbp_mrx.txt','mrx_alt_no_ded_tier') if 'pbp_mrx.txt' in rows[oid] else None;v=rx.get('costShareDeductibleTierExemptions')
        if a and v:
            decoded=normalize(a,dictionary[('pbp_mrx','mrx_alt_no_ded_tier')]);expected=['Tier '+x for x in v.split(',')]
            comparisons.append({'offering_id':oid,'field':'mrx_alt_no_ded_tier','kind':'CMS_documented_bit_positions_vs_JSON_tier_exemptions','table_raw':a,'dictionary_decoded':decoded['value'],'json_tiers':v,'equal':set(decoded['value'])==set(expected),'carrier_corroborated':False})
    amounts=json.loads((out/'normalized-amount-observations.json').read_text())
    amount_index={(x['offering_id'],x['field']):x for x in amounts if x['source'].get('field')}
    for oid,obj in objects.items():
        premium=amount_index[(oid,'part_c_premium')]['value']
        pbp_premium=table(oid,'pbp_Section_D.txt','pbp_d_mplusc_premium')
        if premium is not None and pbp_premium not in [None,'']:
            comparisons.append({'offering_id':oid,'field':'part_c_premium','kind':'CMS_PBP_table_vs_Landscape_part_C','table_value':pbp_premium,'landscape_value':premium,'equal':equal(pbp_premium,premium),'carrier_corroborated':False})
        pcs=obj['pbp'][0]['planLevelCostSharing'];moop=[]
        for path,value in leaves(pcs):
            if path.endswith('/inNWMoopAmount') or path.endswith('/meclInnMoopAmount'):
                if value not in [None,'']:moop.append((path,value))
        if len(moop)==1:
            a=table(oid,'pbp_Section_D.txt','pbp_d_out_pocket_amt');v=moop[0][1]
            comparisons.append({'offering_id':oid,'field':'medical_moop_source_amount','kind':'CMS_table_vs_JSON_named_INN_MOOP','table_value':a,'json_pointer':'/pbp/0/planLevelCostSharing'+moop[0][0],'json_value':v,'equal':equal(a,v),'carrier_corroborated':False})
        c=amount_index[(oid,'part_c_premium')]['value'];d=amount_index[(oid,'part_d_total_premium')]['value'];total=amount_index[(oid,'consolidated_premium')]['value']
        if c is not None and d is not None and total is not None:
            comparisons.append({'offering_id':oid,'field':'published_premium_components','kind':'CMS_Landscape_component_integrity_only','part_c':c,'part_d_total':d,'consolidated':total,'equal':Decimal(c)+Decimal(d)==Decimal(total),'carrier_corroborated':False,'personal_calculation':False})
    check('CMS published amount, day-band and tier-exemption comparisons',all(c['equal'] for c in comparisons),{'comparisons':len(comparisons),'differences':sum(not c['equal'] for c in comparisons),'interpretation':'Two official representations; not carrier corroboration.'})
    dump(out/'cms-format-comparison-ledger.json',comparisons)
    # Cases were hand-authored from actual carrier pages before running this validator.
    cases=json.loads((root/'review/source-expectations.json').read_text())['cases'];mf=json.loads((root/'source-manifest.json').read_text());ledger=[]
    amount_obs=json.loads((out/'normalized-amount-observations.json').read_text())
    for case in cases:
        sel=case['pbp_selector'];oid=case['offering_id'];obj=objects[oid];source={};actual=None
        if 'json_pointer' in sel:
            pointer=sel['json_pointer'];actual=resolve(obj,pointer);source={'member_sha256':member_hash[oid],'pointer':pointer}
        elif 'category' in sel:
            bs=obj['pbp'][0]['benefitDetails']['benefitDetailsInfo'];indices=[i for i,b in enumerate(bs) if b['categoryCode']==sel['category']]
            if len(indices)!=1:raise ValueError('Ambiguous category case')
            pointer=f'/pbp/0/benefitDetails/benefitDetailsInfo/{indices[0]}'+sel['relative_pointer'];actual=resolve(obj,pointer);source={'member_sha256':member_hash[oid],'pointer':pointer}
        elif 'table_member' in sel:
            rec=rows[oid][sel['table_member']][0];actual=rec['raw'][sel['field']];source={**rec['source'],'field':sel['field']}
        elif 'landscape_field' in sel:
            fact=next(x for x in amount_obs if x['offering_id']==oid and x['source'].get('field')==sel['landscape_field']);actual=fact['value'];source=fact['source']
        s=next(x for x in mf['sources'] if x['id']==case['carrier_source_id']);p=pathlib.Path(s['text_path']);p=p if p.is_absolute() else root/p;pages=p.read_text().split('\f')
        evidence=[{'document_id':s['id'],'url':s.get('final_url',s['url']),'sha256':s['sha256'],'pdf_page':i,'page_text_sha256':sha(pages[i-1].encode())} for i in case['pdf_pages']]
        for extra in case.get('additional_carrier_evidence',[]):
            es=next(x for x in mf['sources'] if x['id']==extra['source_id']);ep=pathlib.Path(es['text_path']);ep=ep if ep.is_absolute() else root/ep;pgs=ep.read_text().split('\f')
            evidence.extend({'document_id':es['id'],'url':es.get('final_url',es['url']),'sha256':es['sha256'],'pdf_page':i,'page_text_sha256':sha(pgs[i-1].encode())} for i in extra['pdf_pages'])
        ok=equal(actual,case['expected']);ledger.append({**case,'actual':actual,'source':source,'carrier_evidence':evidence,'value_check_passed':ok,'status':'AI_compared_qualified_subset_review_pending' if ok else 'source_difference_review_required','scope':'Only the specific value/band and published qualifications listed in this case; not full-plan benefit acceptance.'})
    dump(out/'qualified-comparison-ledger.json',ledger)
    check('Carrier-authored expected examples agree with exact CMS values',all(x['value_check_passed'] for x in ledger),{'cases':len(ledger),'plans':len({x['offering_id'] for x in ledger}),'accepted':0})
    docs=json.loads((out/'plan-document-matrix.json').read_text());check('Every offering retains document status',len(docs)==len(offerings) and {x['offering_id'] for x in docs}==ids)
    check('Restricted offerings retained, not excluded',sum(d['document_matches']['SB']['status']=='restricted' for d in docs)==25)
    check('Every documented offering has separate SB/EOC status',all(set(d['document_matches'])=={'SB','EOC'} for d in docs))
    protected=json.loads((root/'protected-before.json').read_text());base=pathlib.Path('/Users/cep4u/daylight');changed=[f for f,h in protected.items() if not (base/f).exists() or sha((base/f).read_bytes())!=h]
    check('Protected accepted L01, selected L02 and UI files unchanged',not changed,{'checked_files':len(protected),'changed':changed})
    summary={'technical_checks':len(checks),'technical_checks_passed':sum(x['passed'] for x in checks),'cms_cross_format_comparisons':len(comparisons),'cms_cross_format_differences':sum(not x['equal'] for x in comparisons),
             'qualified_carrier_case_checks':len(ledger),'qualified_carrier_case_checks_passed':sum(x['value_check_passed'] for x in ledger),'case_plan_count':len({x['offering_id'] for x in ledger}),
             'checks':checks,'complete_L03_validated':False,'owner_acceptance':'pending','meaning':'This report validates retained source integrity and the listed comparisons. It does not assert exhaustive benefit semantics, carrier corroboration, source freshness/rights acceptance or market completeness.'}
    dump(out/'validation-report.json',summary);print(json.dumps(summary,indent=2));return summary

if __name__=='__main__':run()
