#!/usr/bin/env python3
"""Offline, additive L03 r2 reconciliation of every retained PBP service.

No candidate passage, token agreement or successful extraction is promoted to
carrier corroboration. The comparison ledger records each field's disposition;
source-led decisions are an additional, separately authored input.
"""
from __future__ import annotations
import collections, csv, gzip, hashlib, io, json, pathlib, re, zipfile
from decimal import Decimal, InvalidOperation
from l03_reference_build import DATA, L02, PBP_SHA, leaves, sha, dump

OUT=DATA/'reconciliation-r2'
R1=DATA/'build-r1'
# Service names identify CMS categories, never imply that an extra is offered.
NAMES={
'1a':'Acute inpatient hospital','1b':'Inpatient psychiatric hospital','2':'Skilled nursing facility',
'3':'Rehabilitation','3-1':'Cardiac rehabilitation','3-2':'Intensive cardiac rehabilitation','3-3':'Pulmonary rehabilitation','3-4':'Supervised exercise therapy for PAD',
'4':'Emergency and urgent services','4a':'Emergency care','4b':'Urgently needed services','4c':'Worldwide emergency and urgent care','4c1':'Worldwide emergency care','4c2':'Worldwide urgently needed care','4c3':'Worldwide emergency transportation',
'5a':'Partial hospitalization','5b':'Intensive outpatient services','6':'Home health',
'7a':'Primary care','7b':'Chiropractic','7b1':'Routine chiropractic','7c':'Occupational therapy','7d':'Physician specialist','7e':'Outpatient mental health','7e1':'Individual outpatient mental health','7e2':'Group outpatient mental health','7f':'Podiatry','7g':'Other health practitioners','7h':'Outpatient psychiatric services','7h1':'Individual outpatient psychiatric services','7h2':'Group outpatient psychiatric services','7i':'Physical and speech therapy','7j':'Additional telehealth','7k':'Opioid treatment',
'8a':'Diagnostic tests and laboratory services','8a1':'Diagnostic tests and procedures','8a2':'Laboratory services','8b':'Radiology','8b1':'Diagnostic radiology','8b2':'Therapeutic radiology','8b3':'Outpatient X-rays',
'9a1':'Outpatient hospital','9a2':'Observation services','9b':'Ambulatory surgical center','9c':'Outpatient substance use treatment','9c1':'Individual outpatient substance use treatment','9c2':'Group outpatient substance use treatment','9d':'Blood',
'10a':'Ambulance','10a1':'Ground ambulance','10a2':'Air ambulance','10b1':'Nonemergency transportation',
'11a':'Durable medical equipment','11b':'Prosthetics and medical supplies','11b1':'Prosthetics','11b2':'Medical supplies','11c':'Diabetes supplies and services','11c1':'Diabetes monitoring supplies','11c2':'Diabetes therapeutic shoes and inserts','12':'Renal dialysis',
'13a':'Acupuncture','13b':'Over-the-counter benefits','13c':'Meals','13d':'Other supplemental service 1','13e':'Other supplemental service 2',
'14a':'Medicare preventive services','14b':'Routine physical exam','14c':'Additional supplemental benefits','14c1':'Health education','14c3':'Smoking cessation','14c4':'Fitness','14c7':'Remote access technologies','14c8':'Home and bathroom safety devices and modifications','14c11':'Personal emergency response system','14c15':'Wigs for hair loss related to chemotherapy','14c16':'Weight management','14c17':'Alternative therapies','14c21':'In-home support services','14c22':'Support for caregivers of enrollees',
'14d':'Kidney disease education services','14e1':'Medicare-covered glaucoma screening','14e2':'Medicare-covered diabetes self-management training','14e4':'Medicare-covered digital rectal exam','14e5':'Medicare-covered EKG following Welcome Visit',
'15':'Part B prescription drugs','15-1':'Part B insulin','15-1-I':'Part B insulin','15-2':'Part B chemotherapy','15-3':'Other Part B drugs',
'16a':'Medicare-covered dental','16b':'Preventive dental','16b1':'Oral examinations','16b2':'Dental X-rays','16b3':'Other dental diagnostics','16b4':'Dental prophylaxis','16b5':'Fluoride','16b6':'Other preventive dental',
'16c':'Comprehensive dental','16c1':'Restorative dental','16c2':'Endodontics','16c3':'Periodontics','16c4':'Removable prosthodontics','16c5':'Maxillofacial prosthetics','16c6':'Dental implants','16c7':'Fixed prosthodontics','16c8':'Oral and maxillofacial surgery','16c9':'Orthodontics','16c10':'Adjunctive dental',
'17a':'Eye examinations','17a1':'Routine eye exam','17a2':'Other eye exam','17b':'Eyewear','17b1':'Contact lenses','17b2':'Eyeglasses frames and lenses','17b3':'Eyeglass lenses','17b4':'Eyeglass frames','17b5':'Eyewear upgrades',
'18a':'Hearing examinations','18a1':'Routine hearing exam','18a2':'Hearing aid fitting','18b':'Hearing aids','18b1':'All types of hearing aid','18b2':'Inner ear hearing aids','18b3':'Outer ear hearing aids','18b4':'Over-the-ear hearing aids','18c':'Over-the-counter hearing aids',
'1a1':'Additional acute inpatient days'}
# Exact service anchors. Broad section anchors retrieve evidence but never
# establish child-service equivalence, network, benefit activation or amounts.
ANCHORS={
'1a':r'inpatient hospital|acute inpatient','1b':r'inpatient mental|psychiatric hospital|inpatient psychiatric',
'2':r'skilled nursing|nursing facility','3':r'rehabilitation','3-1':r'cardiac rehab','3-2':r'intensive cardiac','3-3':r'pulmonary rehab','3-4':r'supervised exercise|peripheral arter',
'4a':r'emergency care|emergency room|emergency services','4b':r'urgent(ly)? (needed |care|services)',
'4c':r'worldwide|outside the united states','4c1':r'worldwide|outside the united states','4c2':r'worldwide|outside the united states','4c3':r'worldwide|outside the united states',
'5a':r'partial hospitalization','5b':r'intensive outpatient','6':r'home health',
'7a':r'primary care|PCP','7b':r'chiropract','7c':r'occupational therapy','7d':r'specialist',
'7e':r'mental health|psychiatric|psychotherapy','7h':r'mental health|psychiatric|psychotherapy','7f':r'podiatr|foot care','7g':r'other health.*practitioner','7i':r'physical.*therapy|speech.*therapy','7j':r'telehealth|virtual','7k':r'opioid',
'8a':r'diagnostic test|laboratory|lab service','8a1':r'diagnostic test|diagnostic procedure','8a2':r'laboratory|lab service','8b':r'radiology|x.ray','8b1':r'diagnostic radiology|MRI|CT scan','8b2':r'therapeutic radiology|radiation','8b3':r'x.ray',
'9a1':r'outpatient hospital','9a2':r'observation','9b':r'ambulatory surgical|ASC','9c':r'substance (abuse|use)|chemical dependen','9d':r'\bblood\b',
'10a':r'ambulance','10a1':r'ambulance','10a2':r'air ambulance|ambulance','10b1':r'transportation',
'11a':r'durable medical|DME','11b':r'prosthetic|medical supplies','11b1':r'prosthetic','11b2':r'medical supplies','11c':r'diabet','11c1':r'diabet.*suppl|glucose','11c2':r'therapeutic shoes|diabet.*shoes','12':r'dialysis|renal',
'13a':r'acupuncture','13b':r'over.the.counter|OTC','13c':r'\bmeals?\b','13d':r'other supplemental','13e':r'other supplemental',
'14a':r'preventive services|preventive care','14b':r'routine physical|annual physical','14c':r'supplemental|extra benefit',
'14c1':r'health education','14c3':r'smoking cessation|tobacco','14c4':r'fitness|SilverSneakers|Silver.?Fit|Renew Active','14c7':r'nurse.*line|remote access','14c8':r'bathroom safety|home safety','14c11':r'emergency response|PERS','14c15':r'wig|hair loss','14c16':r'weight management','14c17':r'alternative therap','14c21':r'in.home support','14c22':r'caregiver',
'14d':r'kidney disease education|kidney disease','14e':r'preventive','15':r'Part B.*drug|drug.*Part B','15-1':r'insulin','15-2':r'chemotherap','15-3':r'other.*Part B|Part B.*drug',
'16':r'dental|oral exam|prophylaxis|endodont|periodont|prosthodont|orthodont|fluoride',
'17':r'vision|eye exam|eyewear|eyeglass|contact lens','18':r'hearing|hearing aid',
'1a1':r'additional.*days|unlimited.*days|inpatient hospital'}

def readlines(path):
    with gzip.open(path,'rt',encoding='utf-8') as f:
        for l in f:yield json.loads(l)
def writelines(path,records):
    with gzip.open(path,'wt',encoding='utf-8') as f:
        for r in records:f.write(json.dumps(r,ensure_ascii=False)+'\n')
def parent_cat(code):
    explicit={'3-1':'3','3-2':'3','3-3':'3','3-4':'3','4c1':'4c','4c2':'4c','4c3':'4c','7e1':'7e','7e2':'7e','7h1':'7h','7h2':'7h','8a1':'8a','8a2':'8a','8b1':'8b','8b2':'8b','8b3':'8b','9c1':'9c','9c2':'9c','10a1':'10a','10a2':'10a','11b1':'11b','11b2':'11b','11c1':'11c','11c2':'11c','14e1':'14e','14e2':'14e','14e4':'14e','14e5':'14e','15-1':'15','15-2':'15','15-3':'15'}
    for stem,last in [('16b',6),('16c',10),('17b',5),('18b',4)]:
        if code in [stem+str(i) for i in range(1,last+1)]:return stem
    return explicit.get(code)
def role(label,name=''):
    s=(str(label)+' '+name).lower()
    for k,pat in [('authorization',r'authoriz'),('referral',r'referr'),('exclusion_or_exception',r'exclud|except|waiv'),('activation',r'yesno|_yn\b|does .*provide|type of benefit|enhanced benefits|offer.*benefit'),('period_or_frequency',r'period|frequency|number of visit|number of treatment'),('day_band',r'begin.*day|end.*day|day.*interval|days? (start|end)|number of days|days or hours'),('deductible',r'deduct'),('coinsurance',r'coinsurance|coins.*pct'),('copayment',r'copay'),('premium',r'premium|reduction amount'),('limit',r'maximum|moop|out.of.pocket|unlimited'),('network_or_setting',r'network|setting|location'),('qualification',r'eligib|chronic|condition|SSBCI|vbid')]:
        if re.search(pat,s):return k
    return 'source_detail'

def qualified_unit(field):
    # The original primitive mapper inferred USD from a containing title such
    # as "Copayment" even for Begin/End Day fields. Explicit field semantics
    # take priority over that title inference in this additive revision.
    r=field['semantic_role'];n=field['normalized']
    if n.get('type')!='decimal':return None
    if r=='day_band':return 'day_or_hour_count'
    if r=='period_or_frequency':return 'period_or_frequency_count'
    if r=='coinsurance':return 'percent'
    if r in ['copayment','deductible','premium']:return 'USD'
    return n.get('unit')

def number(v):
    try:
        x=Decimal(str(v));return str(x) if x.is_finite() else None
    except InvalidOperation:return None

def component_costs(details):
    """Compose known CMS JSON component contracts; unsupported components stay raw.
    Ranges retain lower/upper, inpatient retains tier and stay/reserve day basis.
    No copay flag is never converted into zero total cost.
    """
    out=[]
    for comp,body in details.items():
        if not isinstance(body,dict):continue
        for typ,unit in [('Copayment','USD'),('Coinsurance','percent')]:
            if comp==typ+'Component':
                pre='bd'+typ;flag=body.get(pre+'AmountYesNoMinMax')
                if flag=='1':
                    value=body.get(pre+'Amount');out.append({'component':comp,'kind':typ.lower(),'state':'amount' if number(value) else 'unknown_amount','amount':number(value),'unit':unit,'source_control':flag,'basis':'service basis requires carrier passage','network':'default PBP component; explicit offering/network context attached'})
                elif flag=='3':out.append({'component':comp,'kind':typ.lower(),'state':'range','minimum':number(body.get(pre+'MinAmount')),'maximum':number(body.get(pre+'MaxAmount')),'unit':unit,'source_control':flag,'basis':'setting/condition range; not a single flat charge','network':'default PBP component; explicit offering/network context attached'})
                elif flag=='2':out.append({'component':comp,'kind':typ.lower(),'state':'no_this_cost_type','amount':None,'unit':unit,'source_control':flag,'basis':'does not establish zero total cost','network':'default PBP component; explicit offering/network context attached'})
            if comp=='Tier'+typ+'Component':
                for field,value in body.items():
                    if isinstance(value,dict) and ('IntervalStay' in field or 'IntervalReserve' in field):
                        for i in range(1,4):
                            stem=f'bdDayInterval{i}';amount=value.get(stem+('CopaymentAmount' if typ=='Copayment' else 'CoinsurancePercentage'))
                            begin=value.get(stem+'BeginDay');end=value.get(stem+'EndDay')
                            if any(v not in [None,''] for v in [amount,begin,end]):out.append({'component':comp,'subcomponent':field,'kind':typ.lower(),'state':'day_band','amount':number(amount),'unit':unit,'begin_day':number(begin),'end_day':number(end),'basis':'per day','stay_or_reserve':'reserve' if 'Reserve' in field else 'stay','source_controls':{k:v for k,v in body.items() if not isinstance(v,dict)},'network':'default PBP component; explicit offering/network context attached'})
                    elif re.fullmatch('bd'+typ+r'Tier\d+(Amt|Percentage)',field) and value not in [None,'']:
                        out.append({'component':comp,'field':field,'kind':typ.lower(),'state':'tier_amount_control_qualified','amount':number(value),'unit':unit,'source_controls':{k:v for k,v in body.items() if not isinstance(v,dict)},'basis':'tier controls decide amount versus day bands; never sum the two','network':'default PBP component; explicit offering/network context attached'})
        if comp in ['OutOfNetworkCostShareComponent','CostShareABComponent','CostShareABPOSComponent']:
            out.append({'component':comp,'kind':'network_cost_sharing','state':'explicit_network_component','network':'out_of_network' if 'OutOfNetwork' in comp or comp=='CostShareABComponent' else 'point_of_service','raw':body,'basis':'raw nested controls, deductible, caps and day bands remain inseparable'})
    return out

def anchor_for(code):
    if code in ANCHORS:return ANCHORS[code]
    pc=parent_cat(code)
    if pc in ANCHORS:return ANCHORS[pc]
    for p in ['16','17','18','14e']:
        if code.startswith(p):return ANCHORS[p]
    return re.escape(NAMES.get(code,code))

def page_evidence(code,pages,custom_anchor=None):
    pat=re.compile(custom_anchor or anchor_for(code),re.I);out=[]
    for pg in pages:
        lines=pg['text'].splitlines();hits=[i for i,l in enumerate(lines) if pat.search(l)]
        # Contents/index matches never count as a cost/condition comparison.
        for i in hits:
            chunk='\n'.join(lines[max(0,i-2):min(len(lines),i+15)])
            if re.search(r'\.{4}|\s{3,}\d{1,3}\s*$',lines[i]) and not re.search(r'\$|copay|coinsurance',chunk,re.I):continue
            if not re.search(r'\$\s?\d|\d\s?%|copay|coinsurance|prior author|referral|limited|unlimited|not cover|per (year|month|day|stay|visit)|every (year|month|two|three)|covered service',chunk,re.I):continue
            out.append({'document_sha256':pg['document_sha256'],'pdf_page':pg['pdf_page'],'text_sha256':pg['text_sha256'],'line_start':max(0,i-2)+1,'line_end':min(len(lines),i+15),'text':chunk,'document_kind':pg['document_kind'],'anchor':lines[i].strip(),'binding':'service-family passage; multi-column, footnote, setting and child-service binding require decision'})
    # No top-N clipping: every qualifying passage is retained.
    return out

def value_support(v,unit,evidence):
    n=number(v)
    if n is None:return []
    d=Decimal(n);s=format(d,'f').rstrip('0').rstrip('.') if '.' in format(d,'f') else format(d,'f')
    if not s:s='0'
    forms={s,format(d,',f').rstrip('0').rstrip('.') if '.' in format(d,',f') else format(d,',f')}
    token='(?:'+'|'.join(re.escape(x) for x in forms)+r')(?:\.00)?(?![\d.])'
    pat=re.compile((r'\$\s*'+token) if unit=='USD' else (r'(?<![\d.])'+token+r'\s*%'))
    return [i for i,e in enumerate(evidence) if pat.search(e['text'])]

def build():
    OUT.mkdir(exist_ok=True)
    pinned='84c84fb2801e3135a48bce0067afcb26cb72ea763630e3d78ecd7472efc22912'
    if sha((R1/'package-manifest.json').read_bytes())!=pinned:raise ValueError('r1 package changed')
    offerings=json.loads((R1/'market-manifest.json').read_text())['observed_offerings']
    dictionary=json.loads((R1/'field-dictionary.json').read_text())['fields'];names={};name_basis={}
    for d in dictionary:
        label=str(d.get('field_title') or '')
        if label.startswith('Type of benefit for '):
            key=str(d['service_category']);names.setdefault(key,label[len('Type of benefit for '):]);name_basis.setdefault(key,{'file':d['file'],'field':d['name'],'dictionary_rows':d['dictionary_rows']})
    matrix=json.loads((R1/'plan-document-matrix.json').read_text());mx={r['offering_id']:r for r in matrix}
    documented={r['offering_id'] for r in matrix if all(r['document_matches'][k]['status']=='matched_for_research' for k in ['SB','EOC'])}
    catalog=json.loads((R1/'carrier-document-catalog.json').read_text());cat={d['sha256']:d for d in catalog}
    allpages=collections.defaultdict(list)
    for p in readlines(R1/'carrier-pages.jsonl.gz'):
        p['document_kind']=cat[p['document_sha256']]['document_kind'];allpages[p['document_sha256']].append(p)
    bundles=collections.defaultdict(list);globalbundles=collections.defaultdict(list);fieldcount=0
    for b in readlines(R1/'normalized-source-bundles.jsonl.gz'):
        for f in b['fields']:f['semantic_role']=role(f['label'],f['source']['field'])
        bundles[(b['offering_id'],b['service_category'])].append(b)
        if b['service_category']=='source_context' or b['source_table'].startswith(('pbp_Section_','pbp_b19')):globalbundles[b['offering_id']].append(b)
        fieldcount+=len(b['fields'])
    plans={};z=zipfile.ZipFile(L02/'acquisition-r1/raw'/PBP_SHA)
    for o in offerings:plans[o['id']]=json.loads(z.read(f"{o['contract']}-{o['plan']}-{o['segment']}-2026.json"))['pbp'][0]
    instances=list(readlines(R1/'benefit-instances.jsonl.gz'));records=[];evrecords=[];fieldledger=[];contextrecords=[];evidence_cache={}
    for x in instances:
        oid=x['offering_id'];p=plans[oid]
        if 'category_code' not in x:
            contextrecords.append({'id':x['id'],'offering_id':oid,'section':x['section'],'pbp':x['pbp'],'raw':x['raw'],'accepted':False});continue
        code=x['category_code'];typeid=x['category_type_id_raw'];family='medicare' if typeid==1 else 'nonMedicare' if typeid==2 else None
        bcode=('15-1-I' if code=='15-1' and typeid==1 else code)+('(NMC)' if typeid==2 else '')
        sourcebundles=bundles.get((oid,bcode),[])+bundles.get((oid,(parent_cat(code) or '__none__')+('(NMC)' if typeid==2 else '')),[])
        fields=[f for b in sourcebundles for f in b['fields']]
        bo=p.get('benefitOfferings',{}).get(family or '__none__',{}).get((family or '')+'BenefitOfferingDetails',[])
        bo_match=[b for b in bo if b['categoryCode']==code or b['categoryCode']==parent_cat(code)]
        auth=p.get('priorAuthorizationAndReferral',{})
        serviceflags={}
        for typ,inner,pre in [('priorAuthorization','priorAuthorizationDetails','inNetworkAuth'),('priorReferral','priorReferralDetails','inNetworkReferral')]:
            a=auth.get(typ,{}).get(inner,{})
            serviceflags[typ]={'required_control_raw':a.get(pre+'ServiceCategoryRequired'),'selected_service':code in a.get(pre+'ServiceCategorySelections',{}).get(family,[]),'source_selections':a.get(pre+'ServiceCategorySelections',{}).get(family,[]),'scope':'in-network; selected list is not a claim that every service instance requires authorization'}
        docs=mx[oid]['document_matches'];pages=[]
        for k in ['SB','EOC']:
            if docs[k].get('sha256'):pages.extend(allpages[docs[k]['sha256']])
        dynamic_name=next((f['raw'] for f in fields if f['label']=='Service Name' and f['raw']),None)
        custom_anchor=re.escape(dynamic_name) if dynamic_name else None
        cachekey=(oid,code,custom_anchor)
        if cachekey not in evidence_cache:evidence_cache[cachekey]=page_evidence(code,pages,custom_anchor) if oid in documented else []
        evidence=evidence_cache[cachekey]
        evid=x['id']+':carrier-passages';evrecords.append({'id':evid,'offering_id':oid,'category_code':code,'passages':evidence,'is_corroboration':False})
        costs=component_costs(x['raw']['benefitDetails'])
        r={'id':x['id'],'offering_id':oid,'year':2026,'category_code':code,'category_type_id_raw':typeid,'service_name':dynamic_name or names.get(bcode,NAMES.get(code,code)),'service_name_basis':{'type':'plan_source_service_name' if dynamic_name else 'official_dictionary' if bcode in names else 'CMS_service_category_label','source':name_basis.get(bcode)},'category_type_interpretation':family,'category_type_basis':'cross-check to named Medicare/nonMedicare offering lists; never a network ID','pbp':x['pbp'],
           'coverage':{'state':'source_present','offering_controls_raw':bo_match,'not_offered_inference':False,'personal_eligibility':'out_of_scope'},
           'cost_sharing':costs,'source_components':x['raw']['benefitDetails'],
           'conditions':{'authorization_and_referral':serviceflags,'dictionary_qualified_fields':fields,'global_context_id':oid+':global-context','blank_does_not_mean_no':True,'unlimited_does_not_remove_cost_bands':True},
           'carrier_evidence_id':evid,'carrier_comparison':'restricted' if oid not in documented else 'field_comparison_recorded_conditions_not_globally_approved','accepted':False,'consumer_usable':False}
        records.append(r)
        # Account for every semantic table field, including blanks and unknowns.
        support_cache={}
        for f in fields:
            n=f['normalized'];s=n['state'];role_=f['semantic_role'];unit=qualified_unit(f)
            sk=(str(n.get('value')),unit)
            if sk not in support_cache:support_cache[sk]=value_support(n.get('value'),unit,evidence) if unit in ['USD','percent'] else []
            support=support_cache[sk]
            if oid not in documented:state='carrier_source_restricted'
            elif s in ['source_blank','source_null']:state='source_blank_retained_not_a_claim'
            elif s in ['unresolved_code','unmapped_field','unresolved_number']:state='opaque_or_unmapped_held'
            elif support:state='typed_value_occurs_in_service_passage_condition_binding_unresolved'
            elif n.get('type')=='decimal' and unit in ['USD','percent']:state='typed_value_not_located_in_service_passage'
            else:state='condition_or_source_detail_retained_for_exact_interpretation'
            fieldledger.append({'benefit_record_id':r['id'],'offering_id':oid,'category_code':code,'source':f['source'],'label':f['label'],'semantic_role':role_,'normalized':n,'qualified_unit':unit,'raw':f['raw'],'comparison_state':state,'passage_indices':support,'evidence_id':evid,'carrier_corroborated':False,'accepted':False})
    # Global fields (premium components, deductibles, limits, OON/POS, SSBCI,
    # cost-share groups, RX, visitor/travel) are never discarded or flattened.
    globals_=[]
    for o in offerings:
        oid=o['id'];p=plans[oid]
        globals_.append({'id':oid+':global-context','offering_id':oid,'raw_json':{k:p.get(k) for k in ['planCharacteristics','standardBid','planLevelCostSharing','benefitOfferings','priorAuthorizationAndReferral','visitorTravel','costShareGroups','vbid','rx']},'dictionary_bundles':globalbundles[oid],'network_warning':'OON and POS differ; a missing node is unknown, not noncoverage','accepted':False})
    writelines(OUT/'benefit-records.jsonl.gz',records);writelines(OUT/'carrier-service-passages.jsonl.gz',evrecords);writelines(OUT/'field-comparison-ledger.jsonl.gz',fieldledger);writelines(OUT/'plan-global-context.jsonl.gz',globals_);writelines(OUT/'source-context-sections.jsonl.gz',contextrecords)
    counters=collections.Counter(x['comparison_state'] for x in fieldledger)
    byplan=[]
    for o in offerings:
        oid=o['id'];rs=[x for x in records if x['offering_id']==oid];fs=[x for x in fieldledger if x['offering_id']==oid];es=[x for x in evrecords if x['offering_id']==oid]
        byplan.append({'offering_id':oid,'name':o['name'],'parent':o['parent'],'original_document_status':'documented' if oid in documented else 'restricted','document_matches':mx[oid]['document_matches'],'benefit_records':len(rs),'typed_cost_entries':sum(len(x['cost_sharing']) for x in rs),'comparison_field_instances':len(fs),'field_states':dict(collections.Counter(x['comparison_state'] for x in fs)),'service_records_with_passages':sum(bool(x['passages']) for x in es),'passages':sum(len(x['passages']) for x in es),'rider_amendment_inventory':'only observed revisions; not proven exhaustive','accepted':False,'consumer_usable':False})
    dump(OUT/'offering-reconciliation.json',byplan)
    summary={'revision':'L03-PUBLISHED-COLLIER-2026-reconciliation-r2','r1_manifest_sha256':pinned,'input_offerings':len(offerings),'documented_offerings':len(documented),'restricted_offerings':len(offerings)-len(documented),'benefit_records':len(records),'documented_benefit_records':sum(x['offering_id'] in documented for x in records),'source_dictionary_field_instances':fieldcount,'service_field_comparison_instances':len(fieldledger),'field_states':dict(counters),'typed_cost_entries':sum(len(x['cost_sharing']) for x in records),'service_records_with_passages':sum(bool(x['passages']) for x in evrecords),'service_passages':sum(len(x['passages']) for x in evrecords),'accepted_fields':0,'consumer_usable_fields':0,'comprehensive':False,'status':'full_source_service_pass_and_field_dispositions; exact_semantic_approval_not_established','limitation':'Presence and amount tokens are evidence retrieval, not complete semantic reconciliation. Conditions/network/footnotes and carrier-only terms must be adjudicated before display.'}
    dump(OUT/'reconciliation-summary.json',summary)
    return summary
if __name__=='__main__':print(json.dumps(build(),indent=2))
