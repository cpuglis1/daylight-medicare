"""ALT74 reported-input gates. Server derived, no eligibility/ranking/insurance policy.
Uses the existing guest guide + readiness companion. No parallel customer database.
"""
import copy,json,re
from pathlib import Path
from guest_profiles import ProfileError,validate_guide
from readiness_profiles import validate as validate_record
VERSION='customer-input-gates-20261023-v1'
UNKNOWN={'','unknown','unsure','not sure','idk','later','add later','check later','not provided','declined'}
CAPABILITIES={
 'availability':{'label':'Plan availability','external':['validated_service_area_and_benefit_year']},
 'route_comparison':{'label':'Coverage comparison','external':['validated_market_scope','comparison_and_independence_acceptance']},
 'timing':{'label':'Enrollment/timing review','external':['official_enrollment_evidence','reviewed_timing_policy']},
 'provider_fit':{'label':'Doctor and hospital access','external':['provider_identity_resolution','current_plan_network_verification']},
 'drug_coverage':{'label':'Prescription coverage','external':['prescription_identity_resolution','plan_formulary_verification']},
 'drug_pricing':{'label':'Prescription costs','external':['exact_pharmacy_resolution','validated_formulary_and_pricing_adapter']},
 'medigap_rights':{'label':'Medigap rights review','external':['reviewed_federal_and_state_rights_policy','official_history_evidence']},
 'snp':{'label':'Special Needs Plan qualification','external':['program_or_plan_qualification_verification','reviewed_SNP_policy']},
}
DEPENDENCIES={'RC02':['comparison.scope.zip','comparison.scope.county'],'RC03':['coverage.requestedStart','coverage.requestedStartMonth'],'RC04':['coverage.current'],'RC05':['coverage.current'],'RC07':['coverage.current'],'RC08':['coverage.current'],'RC09':['coverage.current'],'RC10':['coverage.current'],'RC11':['coverage.current'],'RC12':['coverage.current'],'RC13':['coverage.current'],'RC14':['coverage.current'],'RC15':['coverage.current'],'RC16':['coverage.current'],'RC17':['coverage.current'],'RC20':['needs.travel'],'RC21':['needs.providersStatus','needs.providers'],'RC22':['needs.medicinesStatus','needs.medications','needs.medicationDetails'],'RC23':['needs.medicinesStatus','needs.medications','needs.pharmacies'],'RC24':['needs.medications'],'RC26':['coverage.current']}
PARENTS={'RC05':['RC04'],'RC10':['RC06','RC09'],'RC11':['RC09'],'RC13':['RC09'],'RC14':['RC09'],'RC15':['RC05'],'RC16':['RC07'],'RC23':['RC22'],'RC24':['RC22']}
def known(value):return value is not None and str(value).strip().casefold()not in UNKNOWN

def reject_sensitive(value):
 text=json.dumps(value,ensure_ascii=False)if not isinstance(value,str)else value
 if re.search(r'\b\d{3}-\d{2}-\d{4}\b|\b(?:ssn|social security (?:number|no)|medicare (?:number|id)|password|api[_ -]?key)\s*[:=]',text,re.I)or re.search(r'\b[1-9][A-Z][A-Z0-9][0-9][A-Z][A-Z0-9][0-9][A-Z]{2}[0-9]{2}\b',text,re.I):raise ProfileError('Remove government ID numbers or credentials. They are not needed here.')

class ProfileReadiness:
 def __init__(self,profiles,readiness,contract,content,samples):
  self.profiles=profiles;self.readiness=readiness;self.contract=contract;self.content={t['id']:t for t in content['triggers']};self.samples=samples
 def validate_inputs(self,guide,record):
  guide=validate_guide(guide,self.contract);record=validate_record(record);reject_sensitive({'fields':guide['fields'],'facts':record['facts']})
  for name in ['coverage.current','needs.travel','needs.priorities']:
   e=guide['fields'].get(name)
   if e and (not isinstance(e.get('value'),list)or any(not isinstance(v,str)for v in e['value'])):raise ProfileError('Use the existing answer choices for coverage, travel and priorities.')
  for id,fact in record['facts'].items():
   value=fact['value'];choices=dict(self.content[id]['choices']);allowed={f[0]for f in self.content[id]['fields']}|{'choice','items','programs'}
   if value.get('choice')not in choices or set(value)-allowed:raise ProfileError('A reported detail does not match the existing question definition.')
   if any(not isinstance(v,str)for k,v in value.items()if k not in {'items','programs'}):raise ProfileError('Reported detail fields must be text, not verification claims.')
   for item in value.get('items',[]):
    if any(not isinstance(v,str)for v in item.values()):raise ProfileError('Reported entity fields must be text.')
    if item.get('choice',value['choice'])not in choices:raise ProfileError('Unsupported entity report.')
  return guide,record
 def assess_saved(self,token):
  saved=self.profiles.get(token);companion=self.readiness.get(token)
  if not saved['guide']:
   return {'profileVersion':saved['version'],'readinessVersion':companion['version'],'assessment':self.assess(None,None)}
  return {'profileVersion':saved['version'],'readinessVersion':companion['version'],'assessment':self.assess(saved['guide'],companion['record'])}
 def assess(self,guide,record,requested=None):
  if guide is None:
   guide={'schemaVersion':2,'stateVersion':0,'fields':{},'flow':{'node':'R00','history':[],'queue':[],'lessonReturn':None,'personalReview':False,'guideOpen':True,'origin':'T01','invalidations':[],'scroll':0},'topics':{},'preferences':{'saveGuide':False,'saveSensitive':False,'noticeVersion':'guest-notice-2026-10-21-v1'}}
  if record is None:
   record={'schemaVersion':1,'ruleVersion':'readiness-inputs-20261022-v1','stateVersion':0,'guideFingerprint':'','facts':{},'entityDispositions':{},'requests':[],'detailsRequested':False,'completeness':{},'dispositions':{},'queue':[],'index':0,'shown':[],'pass':0,'history':[],'mode':'summary','editNotice':False,'reviewOnly':False}
  g,r=self.validate_inputs(guide,record);fields=g['fields'];facts=r['facts'];dispositions=r['dispositions'];requests=set(r.get('requests',[]));field_states={}
  try:old=json.loads(r.get('guideFingerprint')or '{}')
  except (ValueError,TypeError):old={}
  def fvalue(name):
   e=fields.get(name)
   if not e:return None
   if e.get('status')in {'unknown','skipped','stale'}or e.get('confirmation')!='confirmed_by_user':return None
   return e.get('value')
  def fstate(name):
   e=fields.get(name)
   return 'unanswered'if not e else {'skipped':'deferred','unknown':'unknown','stale':'needs_review','derived':'reported_from_reference'}.get(e.get('status'),'reported')
  def stale(id):
   fact=facts.get(id)
   if not fact:return False
   if fact.get('stale')or dispositions.get(id,{}).get('state')in {'needs_review','not_saved'}:return True
   for dep in DEPENDENCIES.get(id,[]):
    current=fields.get(dep);prior=old.get(dep)
    if prior is not None and (current is None or any(prior.get(k)!=current.get(k)for k in ['revision','status','confirmation'])):return True
   for parent in PARENTS.get(id,[]):
    p=facts.get(parent)
    if p and p.get('source')!='existing_confirmed_guide' and fact.get('source')!='existing_confirmed_guide'and p.get('revision',0)>fact.get('revision',0):return True
   return False
  def rv(id):
   if stale(id):return {}
   disposition=dispositions.get(id,{}).get('state')
   if disposition in {'not_saved','blocked_dependency'}or disposition in {'explicit_unknown','deferred'}and not(id in {'RC21','RC22','RC23'}and r.get('entityDispositions',{}).get(id)):return {}
   return facts.get(id,{}).get('value',{})
  def rstate(id,entity=None):
   if stale(id):return 'needs_review'
   if entity:
    d=r.get('entityDispositions',{}).get(id,{}).get(entity,{}).get('state')
    if d:return 'unknown'if d=='explicit_unknown'else d
   d=dispositions.get(id,{}).get('state')
   if d:return {'explicit_unknown':'unknown','resolved_report':'reported','not_saved':'unanswered'}.get(d,d)
   return 'reported'if facts.get(id)else 'unanswered'
  for key,e in fields.items():field_states['guide.fields.'+key]={'state':fstate(key),'source':e.get('source'),'revision':e.get('revision'),'confirmation':e.get('confirmation'),'evidence':'not_verified'}
  for id,e in facts.items():field_states['readiness.facts.'+id]={'state':rstate(id),'source':e.get('source'),'revision':e.get('revision'),'confirmation':e.get('confirmation'),'evidence':'not_verified'}
  role=rv('RC01').get('choice')or fvalue('subject.role');goal=fvalue('intent.goal');current=fvalue('coverage.current')or[];priorities=fvalue('needs.priorities')or[]
  if requested is not None:
   if not isinstance(requested,list)or not requested or len(set(requested))!=len(requested)or any(c not in CAPABILITIES for c in requested):raise ProfileError('Choose an existing comparison capability.')
   caps=list(requested)
  elif goal=='learn'and not requests:caps=[]
  else:
   caps=['availability','route_comparison']
   if fvalue('needs.providersStatus')=='list' or 'doctors'in priorities:caps.append('provider_fit')
   if fvalue('needs.medicinesStatus')=='yes'or 'drugs'in priorities:caps.append('drug_coverage')
   if requests&{'timing','payer_order','job_loss','event'}:caps.append('timing')
   if 'personal_pricing'in requests:caps.extend(['drug_coverage','drug_pricing'])
   if requests&{'medigap','leaving_advantage','replacing_medigap'}:caps.append('medigap_rights')
   if 'snp'in requests and rv('RC19').get('choice')!='declined':caps.append('snp')
  caps=list(dict.fromkeys(caps));missing=[];requirements={c:[]for c in caps};states={}
  def need(cap,key,label,okay,q,state='unanswered',entity=None):
   if not okay and state=='reported':state='unresolved'
   item={'key':key,'label':label,'questionId':q,'state':'reported'if okay else state,'entity':entity,'verified':False}
   requirements[cap].append(item)
   if not okay:missing.append({**item,'capability':cap})
  def report(cap,id,label,keys=None,choices=None):
   value=rv(id);okay=known(value.get('choice'))and(not choices or value.get('choice')in choices)and all(known(value.get(k))for k in keys or[])
   for key in keys or[]:
    if key in {'month','jobEnd','coverageEnd','start','eventDate'} and not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])(?:-(0[1-9]|[12][0-9]|3[01]))?',str(value.get(key)or'')):okay=False
   need(cap,'readiness.'+id,label,okay,id,rstate(id));return okay
  def scope(cap):
   loc=rv('RC02');zip=loc.get('zip')or fvalue('comparison.scope.zip');county=loc.get('county')or fvalue('comparison.scope.county');county_ok=isinstance(county,str)and known(county)or isinstance(county,dict)and all(isinstance(county.get(k),str)and known(county[k])for k in ['fips','name','state']);year=rv('RC03');year=year.get('year')if year.get('choice')=='other'else year.get('choice');start=fvalue('coverage.requestedStartMonth');year=year or (start[:4]if isinstance(start,str)and re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])',start)else None)
   need(cap,'home.zip','Home ZIP',bool(isinstance(zip,str)and re.fullmatch(r'\d{5}',zip)),'T03',fstate('comparison.scope.zip'))
   need(cap,'home.county','Home county',bool(county_ok),'RC02',rstate('RC02')if loc else fstate('comparison.scope.county'))
   need(cap,'comparison.year','Comparison year',bool(isinstance(year,str)and re.fullmatch(r'20\d{2}',year)),'RC03',rstate('RC03'))
  def parts(cap):
   choice=rv('RC04').get('choice')
   if not choice and 'original'in current:choice='both'
   need(cap,'enrollment.parts','Actual reported Medicare parts',choice in {'both','a_only','b_only','neither','pending'},'RC04',rstate('RC04'));return choice
  def timing(cap):
   choice=parts(cap);report(cap,'RC06','Eligibility basis')
   if choice in {'both','b_only'}:report(cap,'RC05','Actual Part B start month',['month'])
   if any(v in current for v in ['employer','retiree','cobra']):
    report(cap,'RC09','Current work or continuation coverage')
    if 'payer_order'in requests and rv('RC09').get('choice')in {'my_job','spouse_job','family_job'}and rv('RC06').get('choice')in {'age65','disability'}:report(cap,'RC10','Relevant reported employer-size threshold')
    if 'job_loss'in requests or rv('RC09').get('choice')in {'retiree','cobra'}:report(cap,'RC11','Separate job and health-coverage end dates',['jobEnd','coverageEnd'])
    if rv('RC09').get('choice')in {'my_job','spouse_job','family_job'}:report(cap,'RC14','HSA contribution status')
   if 'event'in requests:report(cap,'RC08','Coverage-change event and date',['eventDate'])
   if any(v in current for v in ['employer','retiree','cobra','drug','military']):
    v=rv('RC12');report(cap,'RC12','Drug coverage notice and gap',[]if v.get('choice')=='none'else['gap'])
   if 'military'in current:report(cap,'RC26','Specific military/VA program')
  def entities(id,field,prefix):
   raw=fvalue(field);rows=raw if isinstance(raw,list)else [x.strip()for x in str(raw or'').split(';')if x.strip()]
   rows=[{'label':x}if isinstance(x,str)else x for x in rows];out=[{**x,'entity':x.get('entity')or prefix+'-'+str(i+1),'label':x.get('label')or x.get('name')or x.get('practice')}for i,x in enumerate(rows)]
   saved=rv(id);items=saved.get('items',[])or([saved]if saved.get('choice')=='details'else[])
   for item in items:
    match=next((e for e in out if e['entity']==item.get('entity')),None)
    if match is None and len(out)==1 and not item.get('entity'):match=out[0]
    if match is not None:match.update(item)
    elif item.get('name')or item.get('practice'):out.append({**item,'entity':item.get('entity')or prefix+'-extra-'+str(len(out)+1),'label':item.get('name')or item.get('practice')})
   return out
  def providers(cap):
   status=fvalue('needs.providersStatus');need(cap,'providers.scope','Doctors to check, or explicit none',status in {'list','none'},'T06',fstate('needs.providersStatus'))
   if status=='list':
    rows=entities('RC21','needs.providers','doctor');need(cap,'providers.list','All requested doctor/hospital names',bool(rows),'T06',fstate('needs.providers'))
    for row in rows:
     for key,label in [('practice','Exact practice/doctor'),('city','Office city and state')]:need(cap,row['entity']+'.'+key,label,known(row.get(key))and not stale('RC21'),'RC21',rstate('RC21',row['entity']),row['entity'])
  def medicines(cap,pricing=False):
   status=fvalue('needs.medicinesStatus');need(cap,'medicines.scope','Prescriptions to check, or explicit none',status in {'yes','no'},'T07',fstate('needs.medicinesStatus'))
   if status=='yes':
    rows=entities('RC22','needs.medications','medicine');need(cap,'medicines.list','All prescription names',bool(rows),'T07',fstate('needs.medications'))
    for row in rows:
     literal=str(row.get('label')or'');row.setdefault('name',literal)
     if 'strength'not in row:
      m=re.search(r'\b\d+(?:\.\d+)?\s*(?:mcg|mg|g|ml|units)\b',literal,re.I)
      if m:row['strength']=m[0]
     if 'form'not in row:
      m=re.search(r'\b(?:tablets?|capsules?|inhaler|cream|solution|injection)\b',literal,re.I)
      if m:row['form']=m[0]
     for key,label in [('name','Exact medicine name'),('strength','Medicine strength'),('form','Medicine form')]:need(cap,row['entity']+'.'+key,label,known(row.get(key))and not stale('RC22'),'RC22',rstate('RC22',row['entity']),row['entity'])
     if pricing:
      fills=rv('RC23');fills=fills.get('items',[])or([fills]if fills.get('choice')else[]);fill=next((x for x in fills if x.get('entity')==row['entity']),{})
      for key,label in [('quantity','Fill quantity'),('daysSupply','Days supply'),('pharmacy','Exact pharmacy and location'),('channel','Retail or mail order')]:need(cap,row['entity']+'.'+key,label,known(fill.get(key))and (key not in {'quantity','daysSupply'}or bool(re.fullmatch(r'[0-9]+(?:\.[0-9]+)?(?:\s*[A-Za-z]+)?',str(fill.get(key)or'')))and float(re.match(r'[0-9]+(?:\.[0-9]+)?',str(fill.get(key)or'0'))[0])>0)and not stale('RC23'),'RC23',rstate('RC23',row['entity']),row['entity'])
  for cap in caps:
   if cap in {'availability','route_comparison','provider_fit','drug_coverage','drug_pricing','medigap_rights','snp'}:scope(cap)
   if cap=='route_comparison':
    need(cap,'goal','Requested comparison goal',goal in {'compare','review','job'},'T01',fstate('intent.goal'));need(cap,'subject','Who coverage is for',role in {'self','someone'},'RC01',rstate('RC01'));need(cap,'coverage.current','Current coverage, or explicit none',bool(current)and all(x!='unknown'for x in current),'T05',fstate('coverage.current'));parts(cap)
    mode=fvalue('coverage.requestedStart');month=fvalue('coverage.requestedStartMonth');need(cap,'coverage.requestedStart','Requested timing or already on Medicare',mode=='already'or mode=='month'and bool(isinstance(month,str)and re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])',month)),'T04',fstate('coverage.requestedStart'))
    need(cap,'providers.scope','Doctors to check, or explicit none',fvalue('needs.providersStatus')in {'list','none'},'T06',fstate('needs.providersStatus'));need(cap,'medicines.scope','Prescriptions to check, or explicit none',fvalue('needs.medicinesStatus')in {'yes','no'},'T07',fstate('needs.medicinesStatus'));need(cap,'travel.scope','Routine-care travel needs',bool(fvalue('needs.travel'))and 'unknown'not in fvalue('needs.travel'),'T08',fstate('needs.travel'))
    if 'coverage_change'in requests and any(v in current for v in ['employer','retiree','cobra']):report(cap,'RC13','Reported administrator check of family/retiree consequences',choices=['yes','no'])
   if cap=='timing':timing(cap)
   if cap=='provider_fit':providers(cap)
   if cap in {'drug_coverage','drug_pricing'}:medicines(cap,cap=='drug_pricing')
   if cap=='medigap_rights':
    parts(cap);report(cap,'RC06','Relevant eligibility basis');report(cap,'RC05','Actual Part B start month',['month']);v=rv('RC15');report(cap,'RC15','Relevant rights history or explicit no known event',[]if v.get('choice')=='none'else['event'])
    if 'leaving_advantage'in requests:report(cap,'RC16','First Advantage plan and prior Medigap history',['start','priorMedigap'])
    if 'replacing_medigap'in requests:report(cap,'RC17','Existing Medigap replacement intention')
   if cap=='snp':report(cap,'RC19','Specific program/plan qualification report',['qualification'],['details'])
   if cap in {'route_comparison','provider_fit'}and any(v in (fvalue('needs.travel')or[])for v in ['another_state','outside_us']):report(cap,'RC20','Routine-care travel location',['location'])
   if 'drug_problem'in requests and cap in {'drug_coverage','drug_pricing'}:report(cap,'RC24','Reported clinic/pharmacy setting')
   if 'continuity'in requests and cap in {'timing','route_comparison'}:report(cap,'RC27','Current continuity/interruption report')
   state_missing=[m for m in missing if m['capability']==cap];states[cap]={'label':CAPABILITIES[cap]['label'],'intakeReady':not state_missing,'requiredInformation':requirements[cap],'missing':state_missing,'externalVerificationReady':False,'externalHolds':CAPABILITIES[cap]['external'],'comparisonReady':False}
  missing.sort(key=lambda m:({'goal':0,'subject':1,'home.zip':2,'home.county':3,'comparison.year':4}.get(m['key'],5)))
  dedup=[];seen=set()
  for m in missing:
   identity=(m['key'],m.get('entity'))
   if identity not in seen:dedup.append(m);seen.add(identity)
  ready=bool(caps)and not missing;next_question={'id':dedup[0]['questionId'],'entity':dedup[0]['entity'],'reason':dedup[0]['label']}if dedup else None
  if not caps:message='This visit is for learning. You can review your information or browse labeled samples.'
  elif dedup:message='A personal comparison still needs '+dedup[0]['label'].lower()+'. You can add it, review your answers, or browse labeled samples.'
  else:message='Your reported information is recorded. Personalized comparison is held while plan data and verification remain unavailable.'
  return {'version':VERSION,'authority':'server_derived','state':'missing_information'if missing else 'external_validation_held'if caps else 'education_only','requestedCapabilities':caps,'intakeInformationReady':ready,'externalVerificationReady':False,'personalizedRecommendationAllowed':False,'capabilities':states,'missingInformation':dedup,'nextQuestion':next_question,'message':message,'fieldStates':field_states,'sampleBrowsing':{'allowed':True,'requiresExplicitAction':True,'label':'Browse sample plans','notRecommendation':True},'sourceStatus':'Research only; domain policy and external plan validation are not approved.','sourceBoundary':{'catalog':'five unvalidated 2027 Collier County sample records','comprehensive':False,'networkVerified':False,'formularyPricingVerified':False},'independence':'Commercial economics excluded from inclusion, eligibility, ranking, explanation and personal fit.','preferencesOptional':['knowledge.general','needs.costPreference','needs.priorities','needs.priorityOther','RC25','brand_generic_preference'],'evaluatedRevisions':{'guide':g['stateVersion'],'readiness':r['stateVersion']}}
