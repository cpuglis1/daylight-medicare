#!/usr/bin/env python3
"""Read-only L03 published-source research lookup. Never computes personal costs."""
from __future__ import annotations
import argparse,csv,gzip,hashlib,io,json,pathlib,re,zipfile
from decimal import Decimal,InvalidOperation
from l03_reference_build import DATA,L02,PBP_SHA,dump,leaves,sha

PREMIUMS={
 'part_c_premium':'Part C Premium','part_d_basic_premium':'Part D Basic Premium',
 'part_d_supplemental_premium':'Part D Supplemental Premium','part_d_total_premium':'Part D Total Premium',
 'consolidated_premium':'Monthly Consolidated Premium (Part C + D)',
 'lips_amount':'Low Income Premium Subsidy (LIPS) Amount','low_income_beneficiary_premium':'Part D Low Income Beneficiary Premium Amount',
}
SCALARS={
 'meclInnMoopAmount':('medical_moop_in_network','USD','year','in_network'),
 'meclCombMoopAmount':('medical_moop_combined','USD','year','combined_in_out'),
 'meclOonMoopAmount':('medical_moop_out_of_network','USD','year','out_of_network'),
 'otherTypeDedAmount':('medical_deductible_source_selected_type','USD','year','source_selected_type_not_yet_interpreted'),
 'inNWMoopAmount':('medical_moop_in_network','USD','year','in_network'),
 'combinedMoopAmount':('medical_moop_combined','USD','year','combined_in_out'),
 'outOfNWMoopAmount':('medical_moop_out_of_network','USD','year','out_of_network'),
 'nonNWMoopAmount':('medical_moop_non_network','USD','year','non_network'),
 'inNetworkDedAmount':('medical_deductible_in_network','USD','year','in_network'),
 'outOfNetworkDedAmount':('medical_deductible_out_of_network','USD','year','out_of_network'),
 'combinedDedAmount':('medical_deductible_combined','USD','year','combined_in_out'),
 'csbPartBPrmReducAmt':('part_b_reduction','USD','month','plan'),
 'costShareDeductibleAmount':('drug_deductible','USD','year','plan_level_part_d'),
}

def numeric(raw):
    if raw is None:return None,'source_null'
    if raw=='':return None,'source_blank'
    raw=str(raw)
    if raw.strip().lower() in ['not applicable','not available']:return None,'source_not_applicable'
    try:
        d=Decimal(re.sub(r'[$,\s]','',raw))
        if not d.is_finite():raise InvalidOperation
        return str(d),'source_amount'
    except InvalidOperation:return None,'uninterpreted_source_text'

def build_observations(root=DATA):
    out=root/'build-r1';offerings=json.loads((out/'market-manifest.json').read_text())['observed_offerings'];ids={o['id'] for o in offerings};facts=[]
    manifest=json.loads((L02/'build-r5/source-manifest.json').read_text())['sources']['landscape'];archive=L02/'acquisition-r1/raw'/manifest['sha256']
    if sha(archive.read_bytes())!=manifest['sha256']:raise ValueError('Landscape hash mismatch')
    with zipfile.ZipFile(archive) as z:
        member=next(n for n in z.namelist() if n.endswith('.csv'));b=z.read(member)
        for ordinal,row in enumerate(csv.DictReader(io.StringIO(b.decode('utf-8-sig'))),1):
            oid='2026:'+row['Contract ID']+':'+row['Plan ID'].zfill(3)+':'+row['Segment ID'].zfill(3)
            if oid not in ids or row.get('County Name')!='Collier':continue
            for field,label in PREMIUMS.items():
                raw=row.get(label);value,state=numeric(raw)
                facts.append({'id':oid+':'+field,'offering_id':oid,'field':field,'value':value,'value_state':state,'raw':raw,'unit':'USD','period':'month',
                    'basis':label,'network':'not_applicable','qualifications':'Published plan amount; not personal premium. Subsidy/member bases remain distinct; Part B federal premium, penalties and IRMAA are not included in the plan premium.',
                    'source':{'archive_sha256':manifest['sha256'],'member':member,'member_sha256':sha(b),'record_ordinal':ordinal,'field':label},'corroboration':'pending','accepted':False})
    with zipfile.ZipFile(L02/'acquisition-r1/raw'/PBP_SHA) as z:
        for o in offerings:
            member=f"{o['contract']}-{o['plan']}-{o['segment']}-2026.json";b=z.read(member);obj=json.loads(b)
            for pointer,raw in leaves(obj):
                k=pointer.split('/')[-1]
                if k not in SCALARS:continue
                field,unit,period,network=SCALARS[k];value,state=numeric(raw)
                facts.append({'id':o['id']+':'+pointer,'offering_id':o['id'],'field':field,'value':value,'value_state':state,'raw':raw,'unit':unit,'period':period,'network':network,
                    'basis':'source-named amount; activation and covered-service scope retained in enclosing PBP section',
                    'qualifications':'The enclosing raw section controls applicability, deductible/MOOP service lists, waivers, groups and Part D tier exemptions. Null is unknown; no unconditional plan-wide applicability is inferred.',
                    'source':{'archive_sha256':PBP_SHA,'member':member,'member_sha256':sha(b),'pointer':pointer},'corroboration':'pending','accepted':False})
    dump(out/'normalized-amount-observations.json',facts)
    print(json.dumps({'normalized_amount_observations':len(facts),'populated_source_amounts':sum(x['value_state']=='source_amount' for x in facts),'accepted':0}))
    return facts

def verify_package(root=DATA):
    manifest=root/'build-r1/package-manifest.json'
    if not manifest.exists():raise ValueError('Package manifest not established')
    m=json.loads(manifest.read_text())
    for rel,expected in m['files'].items():
        if sha((root/rel).read_bytes())!=expected:raise ValueError('L03 package content changed: '+rel)
    repo=pathlib.Path(__file__).resolve().parents[2]
    for rel,expected in m.get('code_files',{}).items():
        if sha((repo/rel).read_bytes())!=expected:raise ValueError('L03 bound code changed: '+rel)
    return sha(manifest.read_bytes())

def research_lookup(offering_id,root=DATA):
    if not re.fullmatch(r'2026:[HR]\d{4}:\d{3}:\d{3}',offering_id):raise ValueError('Exact 2026 offering identity required')
    verify_package(root)
    out=root/'build-r1';market=json.loads((out/'market-manifest.json').read_text())
    offer=next((o for o in market['observed_offerings'] if o['id']==offering_id),None)
    if not offer:raise KeyError(offering_id)
    return {'mode':'published_source_research','accepted':False,'offering':offer,
        'amount_observations':[x for x in json.loads((out/'normalized-amount-observations.json').read_text()) if x['offering_id']==offering_id],
        'documents':next(x for x in json.loads((out/'plan-document-matrix.json').read_text()) if x['offering_id']==offering_id),
        'gaps':[x for x in json.loads((out/'gap-register.json').read_text()) if offering_id in x.get('offering_ids',[]) or x.get('scope')=='package'],
        'personal_applicability':False,'calculations':False,'recommendations':False,'market_completeness_claim':False}

def published_lookup(offering_id,root=DATA):
    verify_package(root)
    receipt=json.loads((root/'review/acceptance.json').read_text())
    # No acceptance is created or inferred by the builder. A future release needs
    # an exact new reviewed artifact and a deliberate implementation change.
    raise PermissionError('L03 published release held: final review/accepted field scope not established')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build-observations',action='store_true');p.add_argument('--plan');a=p.parse_args()
    if a.build_observations:build_observations()
    elif a.plan:print(json.dumps(research_lookup(a.plan),indent=2))
    else:p.error('Choose --build-observations or --plan YEAR:CONTRACT:PLAN:SEGMENT')
