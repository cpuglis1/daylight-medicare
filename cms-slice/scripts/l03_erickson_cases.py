"""Source-led 2026 Erickson transcriptions, with exact CMS comparisons.

The expected amounts were read from the SB, not computed from the CMS values.
Scalar headlines do not silently become prices for every child procedure.
"""
import collections, decimal, json, re, zipfile
import l03_erickson_documents as d
from l03_erickson_reconcile import source_evidence, value_occurs
from l03_reference_build import L02, PBP_SHA, leaves
from l03_validate import equal, resolve

# SB pp2-4,6-10. Medical drug amounts are maximum published cost shares,
# never an exact drug price or a finding that authorization will be granted.
PLANS={
 '001':dict(premium=182,inn=2900,oon=5300,deductible=0,hospital=0,hospital_end=None,mental=0,mental_end=None,pcp=0,specialist=0,asc=150,outpatient=200,observation=200,diagnostic=5,lab=0,radiology=150,therapeutic=35,xray=25,chiropractic=20,podiatry=0,rehab=0,rehab_unit='USD',occupational=0,dme=20,dme_unit='percent',prosthetics=20,shoes=20,shoes_unit='percent',mental_individual=0,substance_individual=0,chemotherapy=15,otc=40,otc_period='quarter'),
 '002':dict(premium=0,inn=6750,oon=9450,deductible=1000,hospital=375,hospital_end=7,mental=375,mental_end=6,pcp=0,specialist=65,asc=325,outpatient=375,observation=375,diagnostic=50,lab=0,radiology=260,therapeutic=20,therapeutic_unit='percent',xray=30,chiropractic=15,podiatry=45,rehab=20,rehab_unit='percent',occupational=20,dme=20,dme_unit='percent',prosthetics=20,shoes=20,shoes_unit='percent',mental_individual=30,substance_individual=30,chemotherapy=20,giveback=20),
 '004':dict(premium=182,inn=3400,oon=10000,deductible=0,hospital=0,hospital_end=None,mental=0,mental_end=None,pcp=0,specialist=25,asc=50,outpatient=100,observation=100,diagnostic=40,lab=0,radiology=100,therapeutic=35,xray=25,chiropractic=20,podiatry=0,rehab=0,rehab_unit='USD',occupational=0,dme=0,dme_unit='USD',prosthetics=20,shoes=0,shoes_unit='USD',mental_individual=30,substance_individual=30,chemotherapy=15,otc=35,otc_period='month'),
 '006':dict(premium=89,inn=4900,oon=10000,deductible=0,hospital=275,hospital_end=7,mental=275,mental_end=7,pcp=0,specialist=50,asc=225,outpatient=275,observation=275,diagnostic=0,lab=0,radiology=170,therapeutic=40,xray=0,chiropractic=15,podiatry=30,rehab=20,rehab_unit='percent',occupational=20,dme=20,dme_unit='percent',prosthetics=20,shoes=20,shoes_unit='percent',mental_individual=40,substance_individual=40,chemotherapy=20,otc=30,otc_period='quarter'),
 '008':dict(premium=14,inn=6750,oon=9450,deductible=0,hospital=375,hospital_end=7,mental=375,mental_end=6,pcp=0,specialist=65,asc=325,outpatient=375,observation=375,diagnostic=20,lab=0,radiology=260,therapeutic=75,xray=30,chiropractic=15,podiatry=45,rehab=20,rehab_unit='percent',occupational=20,dme=20,dme_unit='percent',prosthetics=20,shoes=20,shoes_unit='percent',mental_individual=40,substance_individual=40,chemotherapy=20),
}

# field, category, exact SB page (No Rx page override), unit, qualification
SERVICES=[
 ('pcp','7a',3,3,'USD','Published in-network PCP office visit; separate tests and other professional services can have separate charges.'),
 ('specialist','7d',3,3,'USD','Published in-network specialist office headline; hearing/balance, telehealth and other subservices keep their own schedules.'),
 ('asc','9b',2,3,'USD','Otherwise charge; colonoscopy is separately published at $0. Other services can add charges.'),
 ('outpatient','9a1',3,3,'USD','Otherwise charge; colonoscopy is separately published at $0. Preserve inpatient/outpatient admission distinction.'),
 ('observation','9a2',3,3,'USD','Hospital observation is outpatient care, not an inpatient admission.'),
 ('diagnostic','8a1',4,4,'USD','In-network diagnostic tests/procedures; exact EOC service and setting qualifications retained.'),
 ('lab','8a2',4,4,'USD','In-network laboratory service charge, not a promise that an entire visit is free.'),
 ('radiology','8b1',4,4,'USD','Otherwise charge; diagnostic mammogram is separately published at $0.'),
 ('therapeutic','8b2',4,4,'USD','In-network therapeutic radiology; this is not diagnostic imaging.'),
 ('xray','8b3',4,4,'USD','In-network outpatient X-ray.'),
 ('chiropractic','7b',9,8,'USD','Medicare-covered manual spinal manipulation to correct subluxation, not every chiropractic procedure.'),
 ('podiatry','7f',9,8,'USD','Medicare-covered foot exams/treatment; routine six-visit benefit remains a separate supplemental qualification.'),
 ('rehab','7i',6,7,'USD','Physical and speech/language therapy visits; separate from occupational therapy.'),
 ('occupational','7c',6,7,'USD','Occupational therapy visit.'),
 ('dme','11a',9,8,'percent','In-network DME; equipment type, supplier, rental/ownership and EOC authorization conditions remain attached.'),
 ('prosthetics','11b1',9,8,'percent','Prosthetic devices; no equation with the separate medical-supplies benefit.'),
 ('shoes','11c2',9,8,'percent','Diabetes therapeutic shoes/inserts, subject to Medicare coverage conditions.'),
 ('mental_individual','7e1',6,6,'USD','Individual mental-health therapy; group therapy has its own published charge.'),
 ('substance_individual','9c1',10,9,'USD','Individual outpatient substance-use therapy; group therapy has its own published charge.'),
 ('chemotherapy','15-2',7,7,'percent','Maximum in-network Part B chemotherapy cost sharing; member may pay less for certain drugs. Step therapy and authorization remain conditional.'),
]

def build():
    if (d.ROOT/'manifest.json').exists():raise RuntimeError('Sealed r7 is immutable')
    matrix={x['offering_id']:x for x in d.load(d.ROOT/'plan-document-matrix.json')}
    pages={(p['document_sha256'],p['pdf_page']):p for p in d.rows(d.ROOT/'new-source-pages.jsonl.gz')}
    svc=collections.defaultdict(list)
    for x in d.rows(d.ROOT/'service-reconciliation.jsonl.gz'):svc[(x['offering_id'],x['category_code'])].append(x)
    amounts=d.load(d.R1/'normalized-amount-observations.json');out=[]
    with zipfile.ZipFile(L02/'acquisition-r1/raw'/PBP_SHA)as archive:
      for plan,expect in PLANS.items():
        oid=f'2026:H5652:{plan}:000';m=matrix[oid];member=f'H5652-{plan}-000-2026.json';raw=archive.read(member);obj=json.loads(raw);bs=obj['pbp'][0]['benefitDetails']['benefitDetailsInfo']
        sbh=m['document_matches']['SB']['sha256'];eh=m['document_matches']['EOC']['sha256']
        def add(field,value,unit,sbpage,cat=None,pointer=None,source=None,qualifier='',network='in_network'):
            sb=pages[(sbh,sbpage)];assert value_occurs(value,unit,sb['text']),(oid,field,'transcription absent',sbpage)
            actual=None;src=None
            if pointer:
                actual=resolve(obj,pointer);src={'archive_sha256':PBP_SHA,'member':member,'member_sha256':d.sha(raw),'pointer':pointer}
            elif source:actual=source['value'];src=source['source']
            equal_value=equal(actual,value)if actual not in [None,'']else None
            if plan=='002':qualifier+=' Liberty no Rx has a $1,000 INN annual deductible only on inpatient hospital, inpatient mental health, SNF, ASC, outpatient hospital and observation; diagnostic colonoscopy is excepted, and EOC also excepts Medicare-covered FQHC services. No OON medical deductible. Charges below do not waive that deductible.'
            ss=svc[(oid,cat)]if cat else[];ev=list({(e['document_sha256'],e['pdf_page']):e for s in ss for e in s['EOC_source_evidence']}.values())
            out.append({'id':oid+':r7:'+field,'offering_id':oid,'field':field,'value':str(value),'unit':unit,'network':network,'SB_evidence':source_evidence(sb),'EOC_service_evidence':ev,'CMS_source':src,'CMS_actual':actual,'CMS_value_equal':equal_value,'comparison_state':'named_value_agrees_with_explicit_CMS_pointer'if equal_value is True else'CMS_different_or_less_specific; hold_equivalence'if equal_value is False else'carrier_native_statement; no_CMS_equivalence_claim','qualifications':[qualifier,'All exact EOC coverage, deductible, network and conditional PA/referral rules remain attached. Reference only; no individual applicability or total.'],'accepted_for_reference':False,'consumer_usable':False})
        prem=[a for a in amounts if a['offering_id']==oid and a['field']=='consolidated_premium'and a['value']is not None]
        if not prem:prem=[a for a in amounts if a['offering_id']==oid and a['field']=='part_c_premium']
        add('monthly_published_plan_premium',expect['premium'],'USD/month',2,source=prem[0]if len(prem)==1 else None,qualifier='Base plan premium; optional $44 dental premium, federal A/B costs, IRMAA and penalties are separate.')
        if plan=='002':
            pre='/pbp/0/planLevelCostSharing/planDeductible/planDeductibleDetails/'
            add('INN_medical_deductible',1000,'USD/year',10,pointer=pre+'inNetworkDedAmount',qualifier='Selective annual medical deductible; not applied to every medical service.')
            details=resolve(obj,pre.rstrip('/'))
            selected={x['categoryCode']for x in details['medicareServices']if x.get('inNetwork')=='1'}
            assert selected=={'1a','1b','2','9a1','9a2','9b'}
            assert details['hasOutOfNetworkDed']=='2'
            d.dump(d.ROOT/'Liberty-no-Rx-deductible-conditions.json',{'offering_id':oid,'amount':'1000','unit':'USD/year','network':'in_network','selected_CMS_categories':sorted(selected),'SB_evidence':source_evidence(pages[(sbh,10)]),'EOC_evidence':[source_evidence(pages[(eh,n)])for n in [39,40]],'exceptions':['Diagnostic colonoscopy under ASC and outpatient hospital','Medicare-covered services provided at FQHC'],'out_of_network_deductible':'none_published','CMS_source':{'archive_sha256':PBP_SHA,'member':member,'member_sha256':d.sha(raw),'pointer':pre.rstrip('/')},'accepted_for_reference':False})
        moop='/pbp/0/planLevelCostSharing/maxEnrolleeCostLimit/maxEnrolleeCostLimitDetails/'
        for label,key,pointer in [('in_network_medical_MOOP','inn','inNWMoopAmount'),('out_of_network_medical_MOOP','oon','outOfNWMoopAmount')]:
            add(label,expect[key],'USD/year',2,pointer=moop+pointer,network='in_network'if key=='inn'else'out_of_network',qualifier='Separate network-specific limit, NOT a combined-network limit. Premiums and Part D do not count; EOC specifies included services.')
        for label,cat,n,nn,unit,meaning in SERVICES:
            value=expect[label];unit=expect.get(label+'_unit',expect['rehab_unit']if label=='occupational'else unit)
            b=next((i for i,x in enumerate(bs)if x['categoryCode']==cat and x['categoryTypeId']==1),None)
            pointer=None
            if b is not None:
                c='Coinsurance'if unit=='percent'else'Copayment';comp=bs[b]['benefitDetails'].get(c+'Component',{});ctl=comp.get('bd'+c+'AmountYesNoMinMax')
                fld='bd'+c+('Amount'if ctl=='1'else'MaxAmount'if ctl=='3'else'Amount')
                if ctl in ['1','3']and comp.get(fld)not in [None,'']:pointer=f'/pbp/0/benefitDetails/benefitDetailsInfo/{b}/benefitDetails/{c}Component/{fld}'
                if ctl=='3':meaning+=' CMS comparison is its range MAXIMUM only; no claim that every point or child service equals this headline.'
            add('INN_'+label,value,unit,nn if plan=='002'else n,cat,pointer,qualifier=meaning)
        for label,cat,page in [('hospital','1a',3 if plan=='002'else 2),('mental','1b',6)]:
            b=next(i for i,x in enumerate(bs)if x['categoryCode']==cat and x['categoryTypeId']==1);pre=f'/pbp/0/benefitDetails/benefitDetailsInfo/{b}/benefitDetails/TierCopaymentComponent/'
            end=expect[label+'_end'];pointer=pre+('bdCopaymentTier1DayIntervalStay/bdDayInterval1CopaymentAmount'if end else'bdCopaymentTier1Amt')
            add('INN_'+label+'_first_charge',expect[label],'USD/day'if end else'USD/stay',page,cat,pointer,qualifier=f'Days 1-{end}; later band is $0.'if end else'Per inpatient stay, not per day; covered-day conditions retained.')
            if end:
                for boundary,value,leaf in [('begin_day',1,'bdDayInterval1BeginDay'),('end_day',end,'bdDayInterval1EndDay')]:
                    ptr=pre+'bdCopaymentTier1DayIntervalStay/'+leaf;actual=resolve(obj,ptr)
                    out.append({'id':oid+':r7:INN_'+label+'_'+boundary,'offering_id':oid,'field':'INN_'+label+'_'+boundary,'value':str(value),'unit':'day','network':'in_network','SB_evidence':source_evidence(pages[(sbh,page)]),'CMS_source':{'archive_sha256':PBP_SHA,'member':member,'member_sha256':d.sha(raw),'pointer':ptr},'CMS_actual':actual,'CMS_value_equal':equal(actual,value),'comparison_state':'source_led_day_boundary_comparison','qualifications':['Charge interval endpoint, not a covered-day cap.'],'accepted_for_reference':False,'consumer_usable':False})
        # Fixed, named SB medical rows with EOC context; all non-CMS-linked
        # statements are kept distinct rather than fabricating a source pointer.
        for field,value,unit,page,cat,meaning in [
          ('INN_emergency_visit',130,'USD',4,'4a','If admitted within 24 hours the inpatient copay replaces the emergency copay; worldwide emergency is separately $0.'),
          ('INN_urgent_visit',50,'USD',4,'4b','Domestic visit; worldwide urgent care is separately $0.'),
          ('INN_ground_ambulance',275,'USD',7,'10a1','Non-emergency transport requires provider prior authorization.'),
          ('INN_air_ambulance',275,'USD',7,'10a2','Non-emergency transport requires provider prior authorization.'),
          ('INN_home_health',0,'USD',8 if plan=='002'else 9,'6','Medicare-covered home health, not custodial/home support care.'),
          ('INN_dialysis',20,'percent',9 if plan=='002'else 10,'12','Renal dialysis; acute and chronic setting coverage remains in EOC.'),
          ('routine_eyewear_budget',100,'USD/2years',6,'17b','One pair of frames or contacts every two years; standard lenses have separate terms; all costs outside UHC Vision network are member responsibility.'),
        ]:add(field,value,unit,page,cat,qualifier=meaning)
        if 'giveback'in expect:add('Part_B_premium_reduction_up_to',20,'USD/month',2,qualifier='Up to $20, applied to Social Security or Part B bill; not a cash allowance or an assurance of an individual reduction.')
        if 'otc'in expect:
            add('shared_OTC_budget',expect['otc'],'USD/'+expect['otc_period'],10,'13b',qualifier='One shared budget with approved products/stores. Champion food use is for qualifying members; no individual qualification inferred.')
    d.dump(d.ROOT/'erickson-source-led-comparisons.json',out)
    stats={'offerings':5,'named_comparisons':len(out),'CMS_value_agreements':sum(x['CMS_value_equal']is True for x in out),'CMS_value_differences':sum(x['CMS_value_equal']is False for x in out),'carrier_statements_without_CMS_equivalence_claim':sum(x['CMS_value_equal']is None for x in out),'all_benefits_complete':False}
    d.dump(d.ROOT/'erickson-source-led-summary.json',stats);print(json.dumps(stats));return out

if __name__=='__main__':build()
