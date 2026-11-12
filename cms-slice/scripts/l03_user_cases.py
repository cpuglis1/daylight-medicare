"""Independent SB transcriptions for the 20 newly supplied offerings.

Values below were read from the carrier SB, not generated from CMS. Exact
source pages, the full EOC service context, and assistance/network qualifiers
are attached to every comparison. These cases do not certify other fields.
"""
import collections, decimal, json, pathlib, re, zipfile
import l03_user_documents as d
from l03_reference_build import L02,PBP_SHA,leaves
from l03_validate import resolve,equal
from l03_user_reconcile import value_occurs

# contract-plan-segment: premium, INN MOOP, combined MOOP, hospital amount,
# hospital first-band end (None means stay), PCP charge, specialist charge,
# charge type, Part B reduction (None = no source assertion).
EXPECTED={
 'H0710-010-000':('4.80',9250,13900,2200,None,20,20,'percent',None),
 'H1045-028-000':(0,3800,None,250,7,0,45,'USD',12),
 'H1045-034-000':(0,3400,None,245,7,0,30,'USD',9),
 'H1045-039-000':(0,9250,None,1965,None,20,20,'percent','.20'),
 'H1045-048-002':(0,3400,None,245,7,0,30,'USD',43),
 'H1045-059-000':(0,6700,None,550,5,0,60,'USD',None),
 'H1889-002-002':('4.80',9250,13900,1795,None,20,20,'percent',None),
 'H1889-026-000':(0,0,13900,0,None,0,0,'USD','.50'),
 'H2406-009-000':(0,6700,10100,495,5,0,45,'USD',None),
 'H2406-130-000':(0,8900,13900,535,4,0,55,'USD',130),
 'H2509-003-000':(0,0,None,0,None,0,0,'USD','.60'),
 'R0759-001-000':(62,9250,13900,485,5,0,55,'USD',None),
 'R0759-002-000':(0,9250,13900,595,4,0,55,'USD',47),
 'R0759-003-000':('4.80',9250,13900,1860,None,20,20,'percent',None),
 'H1032-198-000':(0,7200,None,400,6,0,35,'USD',77),
 'H1032-199-000':(0,3000,None,175,7,0,15,'USD',None),
 'H1032-202-000':('4.80',3000,None,0,None,0,0,'USD',None),
 'H1032-239-000':(0,5000,None,400,6,0,20,'USD',130),
 'H1032-241-000':(0,9250,None,0,None,0,0,'USD',None),
 'H1032-243-000':(0,9250,None,0,None,0,0,'USD',None),
}
def build():
    if (d.ROOT/'manifest.json').exists():raise RuntimeError('Sealed r6 is immutable')
    matrices={x['offering_id']:x for x in d.load(d.ROOT/'plan-document-matrix.json')}
    sb=collections.defaultdict(list)
    for p in d.rows(d.ROOT/'SB-exact-plan-pages.jsonl.gz'):sb[p['offering_id']].append(p)
    services=collections.defaultdict(list)
    for x in d.rows(d.ROOT/'service-reconciliation.jsonl.gz'):services[x['offering_id']].append(x)
    amounts=d.load(d.R1/'normalized-amount-observations.json');out=[]
    with zipfile.ZipFile(L02/'acquisition-r1/raw'/PBP_SHA)as z:
      for cp,values in EXPECTED.items():
        o='2026:'+cp.replace('-',':');m=matrices[o]
        if not m['documented']:continue
        premium,moop,comb,hospital,end,pcp,specialist,unit,giveback=values
        member=cp+'-2026.json';raw=z.read(member);obj=json.loads(raw)
        def add(name,expected,unit,pat,pointer=None,source=None,category=None,qualifier=None):
            candidates=[p for p in sb[o]if re.search(pat,p['text'],re.I|re.S)]
            if not candidates:raise ValueError((o,name,'no SB section'))
            candidates=[p for p in candidates if value_occurs(expected,unit,p['text'])]
            if not candidates:raise ValueError((o,name,expected,'SB transcription not found in exact-plan page'))
            ev=[p['source_evidence']for p in candidates]
            if pointer:
                actual=resolve(obj,pointer);src={'archive_sha256':PBP_SHA,'member':member,'member_sha256':d.sha(raw),'pointer':pointer}
            elif source:actual=source['value'];src=source['source']
            else:actual=None;src=None
            agree=equal(actual,expected)if actual is not None else None
            sr=[s for s in services[o]if s['category_code']==category]if category else[]
            quals=['Published 2026 plan reference; all exact SB/EOC coverage conditions remain attached. No personal amount or recommendation.','Medical MOOP excludes premiums and Part D; combined limit is not added to INN limit.','Copay, coinsurance, plan/service deductibles and allowances have different units and scopes.']
            if re.search(r'Dual|D-SNP',m['name']):quals.append('Keep assistance-qualified $0 and base schedules separate. Medicaid category and provider Medicaid acceptance can affect the published charge, especially out of network. No individual assistance determination.')
            if cp.startswith('H1032-'):quals.append('Wellcare shared SB uses this exact plan column; * = PA may be required, square = referral may be required. Emergency and other exceptions remain separate.')
            if giveback is not None and name=='Part_B_premium_reduction':quals.append('Published reduction is up to the stated amount where UHC says up to. It is not an added cash allowance; third-party payment of Part B can prevent the member seeing it.')
            if qualifier:quals.append(qualifier)
            out.append({'id':o+':r6:'+name,'offering_id':o,'field':name,'expected_from_SB':str(expected),'unit':unit,'CMS_actual':actual,'CMS_source':src,'source_values_equal':agree,'SB_evidence':ev,'EOC_service_evidence':[e for s in sr for e in s['EOC_source_evidence']],'EOC_chart_row_ids':[i for s in sr for i in s['EOC_chart_row_ids']],'qualifications':quals,'comparison_state':'named_source_field_values_agree'if agree is True else'published_basis_difference_or_unconfirmed_exact_field'if agree is False else'carrier_published_value; no_CMS_pointer_equivalence_claim','exact_field_scope_only':True,'accepted_for_reference':False,'consumer_usable':False})
        af=[a for a in amounts if a['offering_id']==o and a['field']=='consolidated_premium'and a['value']is not None]
        if not af:af=[a for a in amounts if a['offering_id']==o and a['field']=='part_c_premium']
        assert len(af)==1,(o,'premium source')
        add('published_plan_premium',premium,'USD/month',r'Monthly\s+Plan\s+Premium',source=af[0],qualifier='Carrier SB premium basis may be gross or assistance-qualified; any different CMS gross premium remains separate and held as a combined claim.')
        for key,val,suffix in [('INN_annual_medical_MOOP',moop,('/inNWMoopAmount','/meclInnMoopAmount')),('combined_annual_medical_MOOP',comb,('/combinedMoopAmount','/meclCombMoopAmount'))]:
            if val is None:continue
            paths=[p for p,v in leaves(obj)if p.endswith(suffix)and v not in [None,'']]
            assert len(paths)==1,(o,key,paths)
            add(key,val,'USD/year',r'Maximum\s+out.of.pocket',pointer=paths[0])
        if giveback is not None:
            af=[a for a in amounts if a['offering_id']==o and a['field']=='part_b_reduction']
            add('Part_B_premium_reduction',giveback,'USD/month',r'Part\s+B\s+(?:premium\s+reduction|Premium\s+Reduction)',source=af[0]if len(af)==1 else None)
        bs=obj['pbp'][0]['benefitDetails']['benefitDetailsInfo'];ix=next(i for i,b in enumerate(bs)if b['categoryCode']=='1a'and b['categoryTypeId']==1);base=f'/pbp/0/benefitDetails/benefitDetailsInfo/{ix}/benefitDetails/TierCopaymentComponent/'
        if end is None:
            if cp=='H1032-202-000':
                add('carrier_INN_hospital_daily_copayment',hospital,'USD/day',r'Inpatient\s+hospital',category='1a',qualifier='SB explicitly publishes $0 per day for days 1–90. A PBP stay component is not asserted to have the same unit merely because both numbers are zero.')
            else:add('INN_hospital_base_stay_copayment',hospital,'USD/stay',r'Inpatient\s+hospital',pointer=base+'bdCopaymentTier1Amt',category='1a',qualifier='Per stay, with the exact assistance-dependent alternatives and admission/benefit-period conditions; no all-in hospital bill.')
        else:
            pre=base+'bdCopaymentTier1DayIntervalStay/'
            add('INN_hospital_band1_copayment',hospital,'USD/day',r'Inpatient\s+hospital',pointer=pre+'bdDayInterval1CopaymentAmount',category='1a',qualifier=f'First published band: days 1–{end}; later bands and covered-day rules remain separate.')
            # Day boundaries are source-led expectations, but not currency tokens.
            for name,v,fld in [('INN_hospital_band1_begin_day',1,'bdDayInterval1BeginDay'),('INN_hospital_band1_end_day',end,'bdDayInterval1EndDay')]:
                actual=resolve(obj,pre+fld);out.append({'id':o+':r6:'+name,'offering_id':o,'field':name,'expected_from_SB':str(v),'unit':'day','CMS_actual':actual,'CMS_source':{'archive_sha256':PBP_SHA,'member':member,'member_sha256':d.sha(raw),'pointer':pre+fld},'source_values_equal':equal(actual,v),'SB_evidence':[p['source_evidence']for p in sb[o]if re.search(r'Inpatient\s+hospital',p['text'],re.I)],'qualifications':['Boundary of a charge band, not a covered-day cap; all remaining day bands and admission conditions retained.'],'comparison_state':'named_source_field_values_agree'if equal(actual,v)else'boundary_difference_held','accepted_for_reference':False,'consumer_usable':False})
        for cat,label,amount in [('7a','INN_primary_care',pcp),('7d','INN_specialist',specialist)]:
            ix=next(i for i,b in enumerate(bs)if b['categoryCode']==cat and b['categoryTypeId']==1);pre=f'/pbp/0/benefitDetails/benefitDetailsInfo/{ix}/benefitDetails/'
            ctype='Coinsurance'if unit=='percent'else'Copayment';component=bs[ix]['benefitDetails'].get(ctype+'Component',{})
            control=component.get('bd'+ctype+'AmountYesNoMinMax')
            field='bd'+ctype+('Amount'if control=='1'else'MaxAmount'if control=='3'else'Amount')
            pointer=pre+ctype+'Component/'+field
            if control not in ['1','3']or component.get(field)in ['',None]:pointer=None
            add(label,amount,unit,r'Primary\s+Care|Doctor\s+Visits|Specialists',pointer=pointer,category=cat,qualifier='Named INN office headline/base only. CMS range compares its maximum to this headline, never every point of the range. Hearing/balance, telehealth, nursing-home, tests during a visit and other subservices retain their own EOC schedules. An assistance-dependent 20% base is not a universal charge.')
    d.dump(d.ROOT/'source-led-comparisons.json',out)
    stats={'offerings_compared':len({x['offering_id']for x in out}),'named_field_comparisons':len(out),'source_value_agreements':sum(x['source_values_equal']is True for x in out),'source_basis_or_boundary_differences':sum(x['source_values_equal']is False for x in out),'carrier_statements_without_same_pointer_claim':sum(x['source_values_equal']is None for x in out),'new_accepted_entries':0}
    d.dump(d.ROOT/'source-led-summary.json',stats);print(json.dumps(stats,indent=2))
    return out
if __name__=='__main__':build()
