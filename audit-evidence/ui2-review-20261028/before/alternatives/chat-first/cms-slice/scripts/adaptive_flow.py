"""D79 server-owned conversation. Reports prepare checks; no insurance adjudication.

The two original aggregates remain the only durable records. Turns are visit-only
unless the existing explicit save choices are enabled. No transcript is stored.
"""
import copy
import hashlib
import json
import re
import secrets
import threading
import time
from pathlib import Path
from datetime import datetime
from adaptive_agent import AdaptiveAgent, TASKS, CHECKS
from chat import ModelUnavailable
from guest_profiles import ProfileError, validate_guide, for_storage
from readiness_profiles import validate as validate_record
from profile_readiness import reject_sensitive
import conversation_journey as journey

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT/'config/profile/adaptive-flow.json').read_text())
TEMPLATE = json.loads((ROOT/'config/profile/customer-profile.template.json').read_text())
BASELINE = json.loads((ROOT/'apps/chat-alternative/baseline-content.json').read_text())
Q = {q['id']:q for q in CONTRACT['questions']}
FIELD = {q['id']:q['field'] for q in BASELINE}
MONTHS = ['january','february','march','april','may','june','july','august','september','october','november','december']
DETAIL_KEYS = {f'G{i:02}' for i in range(1,15)}
META_KEYS = {'version','task','preparing','baselineDispositions','skippedDetails','details','editing','checks','itemRevisions','itemInvalidations','lastFactIds','journey'}
LABELS = {'zip':'Home ZIP code','county':'County and state','month':'Month and year',
    'jobEnd':'When the job ends','coverageEnd':'When that health insurance ends',
    'start':'When that Medicare Advantage coverage first started',
    'priorMedigap':'Did you leave Medigap to join that Advantage plan?',
    'event':'The relevant coverage change or notice','eventDate':'Date of that change',
    'gap':'Any relevant gap in drug coverage','qualification':'Named program or plan confirmation',
    'location':'Where routine care is needed','practice':'Doctor, hospital or practice',
    'city':'Office city and state','name':'Prescription name','strength':'Strength on the label',
    'form':'Form, such as tablet or inhaler','quantity':'Quantity and units, such as 30 tablets',
    'daysSupply':'Days supply','pharmacy':'Pharmacy name and exact location',
    'channel':'Retail or mail order','amount':'Monthly amount or range',
    'includes':'What that limit includes','text':'Type your answer','year':'Coverage year'}
HOLDS = {
    'browse':'Exact availability depends on accepted sources for the requested location and year. The connected plan cards are five unvalidated 2027 Collier County samples.',
    'compare':'A personal comparison is held for complete market data, accepted benefits and independent comparison review. A checklist can prepare your information; it cannot verify personal fit.',
    'review':'Keeping your current coverage remains an option. Exact policy evidence and an accepted comparison are needed before recommending a change.',
    'timing':'I can organize the dates and questions for your transition. An exact enrollment deadline, start date or payer-order finding needs official evidence and reviewed rules.',
    'providers':'These are reported provider details. A trusted identity/office match and exact plan/year access evidence are still needed; a name alone does not verify participation.',
    'drug_coverage':'These are reported medicine details. Exact product identity and accepted plan/year formulary and restriction evidence are still needed to establish coverage.',
    'drug_pricing':'These details prepare a fill scenario. Exact pharmacy identity, network, pricing evidence and an accepted model are still needed for a price.',
    'medigap':'Reported dates and history do not establish a buying or return right. Exact federal/state rules, official history and carrier availability remain separate checks.',
    'snp':'A specific plan type, year and accepted qualification evidence are needed. Unknown or unverified status does not mean ineligible; no diagnosis interview is needed here.',
    'costs':'Published components are not a comprehensive personal total. Exact scenario, period, omitted components and accepted applicability/model evidence remain necessary.'}

def metadata(record):
    meta = record.setdefault('conversation', {'version':1,'task':'','preparing':False,
        'baselineDispositions':{},'skippedDetails':{},'details':{},'editing':'','checks':[],
        'itemRevisions':{id+'.'+item['entity']:fact['revision'] for id,fact in record.get('facts',{}).items() for item in fact.get('value',{}).get('items',[])},'itemInvalidations':{},'lastFactIds':[]})
    meta.setdefault('journey', journey.initial())
    return meta

def validate_metadata(meta):
    if isinstance(meta,dict) and meta.get('version')==1:
        meta.setdefault('itemRevisions',{});meta.setdefault('itemInvalidations',{})
        meta.setdefault('lastFactIds',[])
        meta.setdefault('journey',journey.initial())
    if not isinstance(meta,dict) or set(meta)!=META_KEYS or meta.get('version')!=1 or meta.get('task') not in TASKS or type(meta.get('preparing')) is not bool or meta.get('editing') not in ['',*Q]:
        raise ProfileError('Unsupported conversation state.')
    if not journey.valid(meta['journey']):raise ProfileError('Unsupported journey progress.')
    for key in ['baselineDispositions','skippedDetails']:
        if not isinstance(meta[key],dict) or len(meta[key])>200:
            raise ProfileError('Unsupported conversation dispositions.')
        for field,state in meta[key].items():
            if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',field) or state not in {'unknown','deferred'}:
                raise ProfileError('Unsupported conversation disposition.')
    if set(meta['baselineDispositions'])-set(FIELD) or not isinstance(meta['details'],dict) or set(meta['details'])-DETAIL_KEYS:
        raise ProfileError('Unsupported additional report.')
    if not isinstance(meta['checks'],list) or len(meta['checks'])>len(CHECKS) or any(c not in CHECKS for c in meta['checks']):raise ProfileError('Unsupported requested check.')
    for key in ['itemRevisions','itemInvalidations']:
        if not isinstance(meta[key],dict) or len(meta[key])>100 or any(not re.fullmatch(r'RC(?:21|22|23)\.(?:doctor|medicine)-[0-9]{1,3}',k) or type(v) is not int or v<0 for k,v in meta[key].items()):raise ProfileError('Unsupported item revision metadata.')
    if not isinstance(meta['lastFactIds'],list) or len(meta['lastFactIds'])>3 or any(not isinstance(x,str) or not re.fullmatch(r'[a-z_]{1,40}',x) for x in meta['lastFactIds']):raise ProfileError('Unsupported teaching context.')
    for entries in meta['details'].values():
        if not isinstance(entries,list) or len(entries)>30:raise ProfileError('Too many additional reports.')
        for entry in entries:
            if set(entry)!={'value','entity','revision','source','confirmation'} or not isinstance(entry['value'],str) or len(entry['value'])>1800 or not re.fullmatch(r'(?:profile|doctor-[0-9]{1,3}|medicine-[0-9]{1,3})',entry['entity']) or type(entry['revision']) is not int or entry['source'] not in {'user_choice','confirmed_agent_interpretation'} or entry['confirmation']!='confirmed_by_user':
                raise ProfileError('Additional details must remain bounded user reports.')
    return meta

def known(value):
    return value is not None and value!='' and value not in ['unknown','later','not sure']

def month(value):
    """Normalize explicit precision; never supply an unstated day or year."""
    value=value.strip()
    short=re.fullmatch(r'(0?[1-9]|1[0-2])[/.-]((?:19|20)?\d{2})',value)
    compact=re.fullmatch(r'(0[1-9]|1[0-2])(\d{2})',value)
    if short or compact:
        match=short or compact
        # Two-digit years are a disclosed 2000–2099 input convention, not a birthday inference.
        year=match[2] if len(match[2])==4 else '20'+match[2]
        return year+'-'+match[1].zfill(2)
    if value.strip().casefold() in {'no scheduled end','still working','ongoing'}:return value.strip().casefold()
    if re.fullmatch(r'(?:19|20)\d{2}-(?:0[1-9]|1[0-2])(?:-(?:0[1-9]|[12]\d|3[01]))?',value):
        try:datetime.strptime(value,'%Y-%m-%d' if len(value)==10 else '%Y-%m')
        except ValueError:raise ProfileError('That date is not valid.') from None
        return value
    full=re.fullmatch(r'(?i)('+ '|'.join(MONTHS)+r')\s+(\d{1,2})(?:,)?\s+((?:19|20)\d{2})',value.strip())
    if full:
        date=full[3]+'-'+str(MONTHS.index(full[1].lower())+1).zfill(2)+'-'+full[2].zfill(2)
        try:datetime.strptime(date,'%Y-%m-%d')
        except ValueError:raise ProfileError('That date is not valid.') from None
        return date
    match = re.fullmatch(r'(?i)('+ '|'.join(MONTHS)+r')\s+((?:19|20)\d{2})',value.strip())
    if match:return match[2]+'-'+str(MONTHS.index(match[1].lower())+1).zfill(2)
    raise ProfileError('Use the month and year you know, such as January 2027, or leave this detail unknown. No day is assumed.')

def explicit_task(message):
    """Strong task requests are actions, not inferred insurance facts."""
    if re.match(r'(?i)\s*(?:if|suppose|for example|hypothetically)\b',message):return ''
    patterns=[('timing',r"(?:i (?:need|want)(?: help)?|help me|let.s|can you help me)\s+(?:with |to |preparing |prepare )*(?:a |my |the )?(?:medicare |coverage )?transition"),
        ('drug_pricing',r'(?:help me|i (?:want|need)(?: help)? to)\s+(?:prepare |check |compare )?(?:my |a )?(?:prescription |drug |medicine )(?:price|cost)'),
        ('compare',r'(?:i (?:want|need) to|let.s|help me)\s+compare (?:my )?(?:coverage|plans|options)'),
        ('review',r'(?:i (?:want|need) to|let.s|help me)\s+review (?:my )?coverage')]
    return next((task for task,pattern in patterns if re.search(pattern,message,re.I)),'')

class AdaptiveConversation:
    def __init__(self,profiles,readiness,contract,facts,content,client,enabled,budget,count_tokens=None,fixture=False):
        self.profiles,self.readiness,self.contract = profiles,readiness,contract
        self.facts = {f['id']:f for f in facts['facts']}
        self.content = {t['id']:t for t in content['triggers']}
        self.reference = json.loads((ROOT/'apps/chat-alternative/zip-counties.json').read_text())
        definitions=[{'id':q['id'],'options':q.get('choices',[]),'fields':q['fieldNames']} for q in Q.values() if q['kind']!='documented_child']
        self.agent = AdaptiveAgent(contract,facts,client=client,enabled=enabled,max_calls=None,budget=budget,count_tokens=count_tokens,definitions=definitions)
        self.fixture=fixture; self.lock=threading.RLock(); self.cache={};self.pending={};self.active=set()
        self.baseline=BASELINE

    def initial(self):
        guide=copy.deepcopy(TEMPLATE['guide']);guide['flow']['node']='R00'
        record=copy.deepcopy(TEMPLATE['readiness']);metadata(record)
        return guide,record

    def validate(self,guide,record):
        legacy='conversation' not in record
        guide=validate_guide(guide,self.contract);record=validate_record(record)
        reject_sensitive({'fields':guide['fields'],'facts':record['facts'],'conversation':record.get('conversation',{})})
        for name in ['coverage.current','needs.travel','needs.priorities']:
            if name in guide['fields'] and not isinstance(guide['fields'][name]['value'],list):raise ProfileError('Use the supported answer choices.')
        metadata(record);validate_metadata(record['conversation'])
        if legacy:
            m=metadata(record);goal=self.value(guide,'intent.goal')
            m['task']={'learn':'learn','compare':'compare','review':'review','job':'timing'}.get(goal,'')
            m['checks']=[x for x in record.get('requests',[]) if x in CHECKS]
            for id,key in FIELD.items():
                status=guide['fields'].get(key,{}).get('status')
                if status in {'unknown','skipped'}:m['baselineDispositions'][id]='unknown' if status=='unknown' else 'deferred'
        return guide,record

    @staticmethod
    def value(guide,key):
        field=guide['fields'].get(key,{})
        return field.get('value') if field.get('status') not in {'unknown','skipped','stale'} else None

    @staticmethod
    def report(record,id):
        fact=record['facts'].get(id,{})
        return fact.get('value',{}) if not fact.get('stale') else {}

    def put(self,guide,key,value,source):
        old=guide['fields'].get(key)
        if old and old.get('value')==value and old.get('status') not in {'stale','unknown','skipped'}:return
        guide['stateVersion']+=1
        guide['fields'][key]={'value':value,'status':'reported','source':source,'confirmation':'confirmed_by_user','revision':guide['stateVersion']}

    def fact(self,record,id,value,source):
        record['stateVersion']+=1
        record['facts'][id]={'value':value,'source':source,'confirmation':'confirmed_by_user','revision':record['stateVersion'],'stale':False}
        record['dispositions'].pop(id,None)

    def item_stale(self,record,id,entity):
        m=metadata(record);key=id+'.'+entity
        return m['itemInvalidations'].get(key,-1)>m['itemRevisions'].get(key,record['facts'].get(id,{}).get('revision',0))

    def invalidate(self,record,key):
        from profile_readiness import DEPENDENCIES
        for id,deps in DEPENDENCIES.items():
            if key in deps and id in record['facts']:record['facts'][id]['stale']=True

    def apply(self,guide,record,update,source='user_choice'):
        id=update['id'].split('.')[0];data=dict(update['fields']);entity=update.get('entity') or 'profile'
        if id not in Q:raise ProfileError('Unsupported question.')
        allowed=set(Q[id]['fieldNames'])|({'text','month','zip','county'} if id in FIELD else set())
        if set(data)-allowed:raise ProfileError('That question does not collect these details.')
        if id in {'RC21','RC22','RC23'} and entity in {'profile','new',''}:
            prefix='doctor' if id=='RC21' else 'medicine';items=self.report(record,id).get('items',[]);name=data.get('practice' if id=='RC21' else 'name','')
            match=next((x for x in items if name and x.get('practice' if id=='RC21' else 'name','').casefold()==name.casefold()),None)
            if match:entity=match['entity']
            elif id=='RC23':
                medicines=self.report(record,'RC22').get('items',[])
                if len(medicines)!=1:raise ProfileError('Please identify which medicine these details belong to.')
                entity=medicines[0]['entity']
            elif not name and len(items)==1:entity=items[0]['entity']
            else:entity=prefix+'-'+str(max([int(x['entity'].split('-')[-1]) for x in items]+[0])+1)
        meta=metadata(record);meta['baselineDispositions'].pop(id,None)
        meta['editing']=''
        if not data:raise ProfileError('No reported detail was supplied. Leave it unknown rather than selecting a default.')
        if data.get('choice') in {'unknown','deferred'}:
            state=data.pop('choice')
            if id in FIELD:
                meta['baselineDispositions'][id]=state
                if FIELD[id] in guide['fields']:guide['fields'][FIELD[id]]['status']='unknown'
            else:
                meta['skippedDetails'][id+'.'+entity+'.choice']=state
                record['dispositions'][id]={'state':'explicit_unknown' if state=='unknown' else 'deferred','automaticReopen':False}
            record['stateVersion']+=1
            if not data:return
        left_open={k:('deferred' if v.casefold() in {'deferred','check later'} else 'unknown') for k,v in data.items() if k!='choice' and isinstance(v,str) and v.casefold() in {'unknown','deferred','not sure','check later'}}
        if left_open:
            if id in FIELD:
                meta['baselineDispositions'][id]=next(iter(left_open.values()))
                for key in [FIELD[id],*(['coverage.requestedStartMonth'] if id=='T04' else [])]:
                    if key in guide['fields']:guide['fields'][key]['status']='unknown'
                record['stateVersion']+=1
                return
            old=copy.deepcopy(self.report(record,id))
            for field,state in left_open.items():
                meta['skippedDetails'][id+'.'+entity+'.'+field]=state;data.pop(field)
                target=next((x for x in old.get('items',[]) if x.get('entity')==entity),old)
                if field in target:
                    record['history'].append({'triggerId':id,'revision':record['stateVersion'],'previous':{field:target.pop(field),'entity':entity}})
                if id=='RC22' and field in {'name','strength','form'}:meta['itemInvalidations']['RC23.'+entity]=record['stateVersion']+1
            if old:self.fact(record,id,old,source)
            else:record['stateVersion']+=1
            if not data:return
        for key in list(meta['skippedDetails']):
            if key.startswith(id+'.'+entity+'.') and key.rsplit('.',1)[-1] in data:meta['skippedDetails'].pop(key)
        if id in FIELD:
            key=FIELD[id];choice=data.get('choice','')
            if id in {'T06','T07'}:
                text=data.get('text','').strip();none=choice in {'none','no'}
                if not text and not none:raise ProfileError('Enter the names, choose none, or leave this for later.')
                self.put(guide,key,('none' if id=='T06' else 'no') if none else ('list' if id=='T06' else 'yes'),source)
                if text:
                    target='needs.providers' if id=='T06' else 'needs.medications'
                    old=self.value(guide,target)
                    if old and not update.get('correction') and text.casefold() not in old.casefold():text=old+'; '+text
                    if self.value(guide,target)!=text:self.invalidate(record,target)
                    self.put(guide,target,text,source)
                return
            if id=='T03':
                zip=data.get('zip','')
                if not re.fullmatch(r'\d{5}',zip):raise ProfileError('Enter a five-digit home or reference ZIP, or choose not sure.')
                if self.value(guide,key)!=zip:self.invalidate(record,key)
                self.put(guide,key,zip,source);rows=self.reference['zips'].get(zip,[])
                county=data.get('county');matches=[row for row in rows if county in [row[0],row[1],row[1]+', '+row[2]]]
                if len(rows)==1 or len(matches)==1:
                    row=rows[0] if len(rows)==1 else matches[0]
                    self.put(guide,'comparison.scope.county',{'fips':row[0],'name':row[1],'state':row[2]},source)
                    self.put(guide,'comparison.scope.locationEvidence',{'source':self.reference['source_url'],'period':self.reference['period'],'method':'unique_zip_reference' if len(rows)==1 else 'user_county_selection'},source)
                    if len(rows)==1:
                        for f in ['comparison.scope.county','comparison.scope.locationEvidence']:guide['fields'][f].update(status='derived',source='location_reference')
                else:
                    for f in ['comparison.scope.county','comparison.scope.locationEvidence']:
                        if f in guide['fields']:guide['fields'][f]['status']='stale'
                return
            if id=='T04':
                if choice not in {'month','already','unknown'}:raise ProfileError('Choose intended start, already on Medicare, or not sure.')
                if choice=='month':
                    supplied=data.get('month','').strip()
                    year=self.report(record,'RC03').get('year')
                    if year and supplied.casefold() in MONTHS:supplied=supplied+' '+year
                    elif year and re.fullmatch(r'0?[1-9]|1[0-2]',supplied):supplied=year+'-'+supplied.zfill(2)
                    actual=month(supplied)
                    if self.value(guide,'coverage.requestedStartMonth')!=actual:self.invalidate(record,'coverage.requestedStartMonth')
                    self.put(guide,'coverage.requestedStartMonth',actual,source)
            options=dict(Q[id].get('choices',[]))
            if id in {'T05','T08','T10'}:
                values=choice.split(',') if isinstance(choice,str) else choice
                if not values or len(set(values))!=len(values) or any(v not in options for v in values) or len(values)>1 and any(v in {'none','unknown','local'} for v in values):raise ProfileError('Those choices need clarification.')
                choice=values
            elif id not in {'T03','T04'} and choice not in options:raise ProfileError('Choose a supported answer or type an explanation.')
            if self.value(guide,key)!=choice:self.invalidate(record,key)
            self.put(guide,key,choice,source)
            if id=='T01':
                meta['task']={'learn':'learn','compare':'compare','review':'review','unresolved':''}[choice]
                meta['preparing']=choice in {'compare','review'}
                meta['journey']['samplesVisible']=False
                if data.get('text'):self.put(guide,'intent.goalDetail',data['text'],source)
            if id=='T05' and choice in [['cobra'],['retiree']]:
                # The explicit coverage type already answers the continuation-vs-current-job distinction.
                # It says nothing about A/B enrollment, the worker, or an employment end date.
                self.fact(record,'RC09',{'choice':choice[0]},source)
            if id=='T10' and data.get('text'):self.put(guide,'needs.priorityOther',data['text'],source)
            return
        if id=='RC01' and self.report(record,id).get('choice') not in {None,data.get('choice')} and len(guide['fields'])>2:
            raise ProfileError('These reports belong to the person already identified. Open a separate visit for another person; the existing information is preserved.')
        choices=dict(self.content[id]['choices'])
        if id=='RC03':
            year=data.get('year') or data.get('choice')
            if year and not re.fullmatch(r'(?:19|20)\d{2}',year):
                date=month(year)
                if re.fullmatch(r'(?:19|20)\d{2}-\d{2}(?:-\d{2})?',date):
                    year=date[:4]
                    self.put(guide,'coverage.requestedStartMonth',date,source)
                    self.put(guide,'coverage.requestedStart','month',source)
            if not re.fullmatch(r'20\d{2}',year or ''):raise ProfileError('Enter an explicit coverage year, or leave it unknown.')
            data={'choice':year if year in choices else 'other','year':year}
        elif id=='RC02' and 'county' in data:
            self.apply(guide,record,{'id':'T03','fields':{'zip':self.value(guide,'comparison.scope.zip') or data.get('zip',''),'county':data['county']}},source)
            data['choice']='details'
        else:
            if not data.get('choice'):
                if id in {'RC02','RC05','RC11','RC15','RC20','RC21','RC22','RC23','RC25'}:
                    data['choice']={'RC11':'dates','RC20':'us','RC25':'amount'}.get(id,'details')
                    if id=='RC20':data['choice']=self.report(record,id).get('choice') or ('abroad' if 'outside_us' in (self.value(guide,'needs.travel') or []) and 'elsewhere_us' not in (self.value(guide,'needs.travel') or []) else 'partial')
                elif id in {'RC06','RC08','RC12','RC16'}:data['choice']=self.report(record,id).get('choice') or 'partial'
                else:raise ProfileError('That status was not supplied. Choose an answer or keep it unknown.')
            if data['choice'] not in choices:raise ProfileError('Unsupported reported detail.')
        for k in ['month','jobEnd','coverageEnd','eventDate','start']:
            if data.get(k):data[k]=month(data[k])
        for key,value in data.items():
            if not isinstance(value,str) or len(value)>1800:raise ProfileError('Keep each reported detail within its input limit.')
            if key=='daysSupply' and value and (not re.fullmatch(r'\d{1,3}',value) or not 1<=int(value)<=365):raise ProfileError('Enter a known days supply from 1 to 365, or leave it unknown.')
        if id in {'RC21','RC22','RC23'}:
            prefix='doctor' if id=='RC21' else 'medicine'
            old=copy.deepcopy(self.report(record,id));items=old.get('items',[])
            name=data.get('practice' if id=='RC21' else 'name','')
            if id=='RC23' and entity in {'profile','new',''}:
                medicines=self.report(record,'RC22').get('items',[])
                if len(medicines)==1:entity=medicines[0]['entity']
                elif len(medicines)>1:raise ProfileError('Please identify which listed medicine these fill details belong to.')
            if entity in {'profile','new',''}:
                match=next((x for x in items if name and x.get('practice' if id=='RC21' else 'name','').casefold()==name.casefold()),None)
                entity=match['entity'] if match else prefix+'-'+str(max([int(x['entity'].split('-')[-1]) for x in items]+[0])+1)
            if not re.fullmatch(prefix+r'-\d{1,3}',entity):raise ProfileError('Use the active item or name the new item.')
            item=next((x for x in items if x['entity']==entity),None)
            if item is None:
                if len(items)>=30:raise ProfileError('This visit supports 30 items per group. Your existing list is preserved; split the remaining work into a separate check.')
                item={'entity':entity};items.append(item)
            previous=copy.deepcopy(item)
            if id=='RC23' and self.item_stale(record,id,entity) or id=='RC22' and data.get('name') and item.get('name') and data['name'].casefold()!=item['name'].casefold():
                record['history'].append({'triggerId':id,'revision':record['stateVersion'],'previous':previous})
                for k in list(item):
                    if k!='entity':item.pop(k)
            if id=='RC23' and data.get('quantity') and not re.search(r'\d',data['quantity']) and re.fullmatch(r'\d+(?:\.\d+)?',previous.get('quantity','')):
                data['quantity']=previous['quantity']+' '+data['quantity']
            item.update(data)
            self.fact(record,id,{'choice':'details','items':items},source)
            meta['itemRevisions'][id+'.'+entity]=record['stateVersion']
            if id=='RC22':
                if any(previous.get(k)!=item.get(k) for k in ['name','strength','form']):meta['itemInvalidations']['RC23.'+entity]=record['stateVersion']
                self.put(guide,'needs.medicinesStatus','yes',source)
                names='; '.join(x['name'] for x in items if x.get('name'))
                if names:self.put(guide,'needs.medications',names,source)
            if id=='RC21':
                self.put(guide,'needs.providersStatus','list',source)
                names='; '.join(x['practice'] for x in items if x.get('practice'))
                if names:self.put(guide,'needs.providers',names,source)
            return
        old=copy.deepcopy(self.report(record,id));old.update(data)
        if id=='RC18':
            programs=set(old.get('programs',[]))
            if data['choice'] in {'none','declined'}:programs=set()
            else:programs.add(data['choice'])
            old['programs']=sorted(programs)
        self.fact(record,id,old,source)
        if id=='RC01' and data['choice'] in {'self','someone'}:self.put(guide,'subject.role',data['choice'],source)
        if id=='RC01' and data['choice']=='research':meta['task']='browse';meta['preparing']=False
        if id=='RC26':
            entries=meta['details'].setdefault('G13',[])
            if not any(x['value']==data['choice'] for x in entries):entries.append({'value':data['choice'],'entity':'profile','revision':record['stateVersion'],'source':source,'confirmation':'confirmed_by_user'})

    def question(self,id,fields=None,entity='profile',text=None):
        parent=id.split('.')[0];base=Q[parent]
        q={'id':parent,'inventoryIds':[id],'question':text or base['question'],'why':'This missing detail can help prepare the specific check you requested.','choices':base.get('choices',[]),'multi':parent in {'T05','T08','T10','RC18'},'entity':entity,'fields':[]}
        q['why']={'T01':'','T03':'Plans differ by county. This helps identify the area you want to look into.','T04':'This is when you want the new coverage to begin. It may be different from when your current insurance ends.','T05':'We’ll use this to understand what you have before looking at other options.','T06':'You can name the doctors or hospitals you want to keep, or leave this for later.','T07':'You can list the medicines you want included, or leave this for later.','T08':'This helps identify whether access to routine care in another place matters to you.','RC01':'We’ll keep the coverage details focused on that person.','RC11':'Your desired Medicare start, the job’s end and the insurance’s end can be different. We’ll keep the dates you actually know separate.','RC23':'These are the fill details still needed for the prescription price question you asked.'}.get(parent,q['why'])
        if parent=='T01':q['choices']=[['learn','Understand Medicare and my options'],['compare','Find coverage'],['review','Review my current coverage'],['unresolved','Something else']]
        if parent in {'T06','T07'}:
            q['question']='Are there doctors or hospitals you’d like to keep?' if parent=='T06' else 'Are there prescriptions you’d like included when looking at options?'
            q['choices']=[['none' if parent=='T06' else 'no','No doctors to include' if parent=='T06' else 'No prescriptions to include']];fields=['text']
        if parent in {'T03'}:fields=['zip'];q['choices']=[]
        if parent=='T04':
            fields=['month'];q['choices']=[['already','I already have Medicare']]
        if parent in {'RC02','RC03','RC05','RC11','RC15','RC20','RC21','RC22','RC23','RC25'}:q['choices']=[]
        if parent=='RC16' and fields:q['choices']=[]
        for key in fields or []:
            field={'key':key,'label':LABELS.get(key,key),'type':'text','options':[]}
            if key=='daysSupply':field.update(type='select',options=[['30','30 days'],['60','60 days'],['90','90 days'],['other','Another amount']])
            if key=='channel':field.update(type='select',options=[['retail','Retail pharmacy'],['mail','Mail order']])
            if key=='priorMedigap':field.update(type='select',options=[['yes','Yes'],['no','No'],['unknown',"I don’t know"]])
            if key=='includes':field.update(type='select',options=[['all_premiums_with_part_b','All monthly premiums, including Part B'],['additional_premiums','Additional plan premiums only'],['premiums_and_care','Premiums and care costs'],['drugs','Prescription spending'],['other','Another scope']])
            if key=='text':field['type']='textarea'
            if key=='month':field['hint']='For example, December 2026 or 12/26. You can also type your answer below.'
            if key=='year' and parent=='RC03':field.update(label='When you need coverage',hint='A month and year, such as December 2026 or 12/26. A year alone is enough if you are only browsing.')
            if key=='pharmacy':field['type']='search';field['hint']='No pharmacy directory is connected. Enter the exact store or mail service you mean; it remains unverified.'
            q['fields'].append(field)
        q['signature']=parent+'.'+entity+'.'+'.'.join(fields or ['choice'])
        q['atomicRequests']=len(fields or ['choice'])
        return q

    def assess(self,guide,record,edit=None):
        m=metadata(record);task=m['task'];v=lambda k:self.value(guide,k);r=lambda id:self.report(record,id)
        decisions={id:{'treatment':q['reviewTreatment'],'state':'not_requested'} for id,q in Q.items()}
        def missing(id,keys=None,entity='profile',text=None):
            requested_keys=bool(keys)
            if id in FIELD:
                lost_sensitive=id=='T06' and v('needs.providersStatus')=='list' and not v('needs.providers') or id=='T07' and v('needs.medicinesStatus')=='yes' and not v('needs.medications') or id=='T04' and v('coverage.requestedStart')=='month' and not v('coverage.requestedStartMonth')
                if (v(FIELD[id]) is not None and not lost_sensitive) or id in m['baselineDispositions']:return None
            elif not keys:
                if id=='RC01' and v('subject.role') in {'self','someone'}:return None
                if r(id) or record['dispositions'].get(id,{}).get('state') in {'explicit_unknown','deferred'}:return None
            keys=[k for k in (keys or []) if not m['skippedDetails'].get(id+'.'+entity+'.'+k) and not (r(id).get(k) if entity=='profile' else next((x.get(k) for x in r(id).get('items',[]) if x.get('entity')==entity),None))]
            if requested_keys and not keys:return None
            if keys==[] and id not in FIELD and any(x.startswith(id+'.'+entity+'.') for x in m['skippedDetails']):return None
            q=self.question(id,keys or None,entity,text)
            if id=='T04' and v('coverage.requestedStart')=='month' and not v('coverage.requestedStartMonth'):
                q['why']='Your saved details include a start-month choice, but not the date. Add the month and year if you want to continue; you can keep it unknown.'
            decisions[id]['state']='missing';return q
        nextq=None;edit=edit or m.get('editing')
        if edit:
            if edit not in Q:raise ProfileError('Unknown review item.')
            nextq=self.question(edit, self.content[edit]['fields'] and [f[0] for f in self.content[edit]['fields'] if f[0]!='entity'] if edit.startswith('RC') else None)
        elif not task:nextq=missing('T01')
        elif task=='learn':pass
        elif task in {'compare','review'} and not m['preparing']:pass
        elif task=='snp':pass # No concrete accepted candidate/type: do not solicit diagnosis/proof.
        else:
            todo=[]
            if task!='browse':todo.append(missing('RC01'))
            if task in {'compare','review'}:
                if task!='review':todo.append(missing('T04'))
                todo.append(missing('T05'))
            if task in {'browse','compare','review','medigap'}:
                todo.append(missing('T03'))
                zip=v('comparison.scope.zip');rows=self.reference['zips'].get(zip,[]) if zip else []
                if zip and not v('comparison.scope.county') and len(rows)>1:
                    q=missing('RC02',['county'],text='Which county is the home or reference location in?')
                    if q:q['fields'][0].update(type='select',options=[[x[0],x[1]+', '+x[2]] for x in rows])
                    todo.append(q)
            if task=='browse':
                if not r('RC03').get('year') and not v('coverage.requestedStartMonth'):todo.append(missing('RC03',['year'],text='When would you need this coverage?'))
            if task in {'timing','medigap'}:
                if task!='review':todo.append(missing('T04'))
                todo.append(missing('T05'))
            coverage=v('coverage.current') or []
            if task in {'compare','review'}:
                todo.extend([missing('T06'),missing('T07'),missing('T08')])
            if task=='providers':todo.append(missing('T06'))
            if task in {'drug_coverage','drug_pricing'}:todo.append(missing('T07'))
            if task=='timing':
                # Organizing a transition is not itself a supported Part-A/B adjudication.
                # COBRA never implies either presence or absence of Medicare enrollment.
                if 'payer_order' in m['checks'] and not r('RC04') and not any(c in coverage for c in ['original','advantage','medigap']):todo.append(missing('RC04'))
                if any(c in coverage for c in ['employer','retiree','cobra']):
                    employment_kind=r('RC09').get('choice') or (coverage[0] if coverage in [['cobra'],['retiree']] else None)
                    if not employment_kind:todo.append(missing('RC09',text='Whose job is the health insurance through, and is that person still working?'))
                    if employment_kind in {'my_job','spouse_job','family_job','retiree','cobra'}:
                        needed=['jobEnd','coverageEnd'] if employment_kind in {'my_job','spouse_job','family_job'} or 'job_loss' in m['checks'] else ['coverageEnd']
                        fields=[k for k in needed if not r('RC11').get(k) and not m['skippedDetails'].get('RC11.profile.'+k)]
                        if fields:todo.append(self.question('RC11',fields,text=('When does the job end, and when does the health insurance through that job end?' if len(fields)==2 else 'When does '+('that job' if fields[0]=='jobEnd' else 'that health insurance')+' end?')))
                checks=set(m['checks'])
                if 'payer_order' in checks:
                    todo.append(missing('RC06'))
                    if r('RC09').get('choice') in {'my_job','spouse_job','family_job'} and r('RC06').get('choice') in {'age65','disability'}:
                        q=missing('RC10')
                        if q and r('RC06').get('choice')=='disability':q['question']='Does that employer have 100 or more employees?';q['choices']=[['yes','100 or more'],['no','Fewer than 100']]
                        todo.append(q)
                if 'drug_gap' in checks and set(coverage)&{'employer','retiree','cobra','military'}:
                    todo.append(missing('RC12',text='What has the plan or benefits office told you about whether your current drug coverage counts as creditable?'))
                if 'coverage_change' in checks and set(coverage)&{'employer','retiree','cobra'}:
                    todo.append(missing('RC13',text='Has the benefits office told you how this change could affect your coverage, or a spouse’s or dependent’s coverage?'))
                if checks & {'event','residence_change'} and r('RC08').get('choice') not in {None,'none'}:
                    todo.append(missing('RC08',['eventDate'],text='When does that reported coverage change or move happen?'))
                if set(coverage)&{'military'} and checks & {'payer_order','coverage_change','drug_gap'}:todo.append(missing('RC26',text='Which current VA, TRICARE, CHAMPVA or other program is involved in this check?'))
            if task=='medigap':
                if not r('RC04'):todo.append(missing('RC04'))
                if r('RC04').get('choice') in {'both','b_only'}:todo.append(missing('RC05',['month'],text='What month and year did Part B start?'))
                if 'advantage' in coverage:
                    fields=[k for k in ['start','priorMedigap'] if not r('RC16').get(k) and not m['skippedDetails'].get('RC16.profile.'+k)]
                    if fields:todo.append(self.question('RC16',fields,text='For that Advantage episode, '+('when did it start, and did you leave Medigap to join it?' if len(fields)==2 else 'when did it start?' if fields[0]=='start' else 'did you leave a Medicare supplement (Medigap) policy to join it?')))
            if task in {'drug_coverage','drug_pricing'}:
                meds=r('RC22').get('items',[])
                for item in meds:
                    missing_identity=[k for k in ['name','strength','form'] if not item.get(k) and not m['skippedDetails'].get('RC22.'+item['entity']+'.'+k)]
                    if missing_identity:todo.append(self.question('RC22',missing_identity,item['entity'],'For '+item.get('name','this medicine')+', which missing label details can you add?'))
                for item in meds if task=='drug_pricing' else []:
                    if not all(item.get(k) for k in ['name','strength','form']):continue
                    fill=next((x for x in r('RC23').get('items',[]) if x.get('entity')==item['entity']),{})
                    stale=self.item_stale(record,'RC23',item['entity'])
                    fields=[k for k in ['quantity','daysSupply','pharmacy','channel'] if (stale or not fill.get(k) or k=='quantity' and not re.search(r'[A-Za-z]',fill[k])) and not m['skippedDetails'].get('RC23.'+item['entity']+'.'+k)]
                    if fields:
                        q=self.question('RC23',fields,item['entity'],'For '+item.get('name','this medicine')+', what fill details should we prepare?')
                        if not stale and 'quantity' in fields and re.fullmatch(r'\d+(?:\.\d+)?',fill.get('quantity','')):q['fields'][fields.index('quantity')]['label']='What units does the reported quantity of '+fill['quantity']+' use?'
                        todo.append(q)
                # If no product details exist, one missing-product preparation group, never a fabricated match.
                if not meds and v('needs.medicinesStatus')=='yes' and not record['dispositions'].get('RC22'):
                    todo.append(missing('RC22',['name','strength','form'],entity='medicine-1',text='What exact name, strength and form are on the medicine label?'))
                if task=='drug_pricing' and 'adjusted_costs' in m['checks']:todo.append(missing('RC18',text='Do you currently receive benefits from any of these programs?'))
            if task in {'compare','review'} and any(x in (v('needs.travel') or []) for x in ['elsewhere_us','another_state','outside_us']):todo.append(missing('RC20',['location'],text='Where will you need that routine care away from home?'))
            if task=='costs' and r('RC25').get('amount') and not r('RC25').get('includes'):todo.append(missing('RC25',['includes'],text='What should the monthly limit you reported include?'))
            nextq=next((q for q in todo if q),None)
            if nextq and nextq['id']=='T04' and r('RC03').get('year'):
                nextq['question']='You mentioned '+r('RC03')['year']+'. Which month of that year would you like coverage to begin?'
                nextq['why']='We already have the year. The month is the additional detail for your timing question; a full date can change the year if needed.'
                nextq['knownYear']=r('RC03')['year']
        if nextq:decisions[nextq['id']]['state']='missing'
        for id,row in decisions.items():
            if id in FIELD and v(FIELD[id]) is not None or id.startswith('RC') and r(id.split('.')[0]):row['state']='reported_reused' if row['state']!='missing' else 'missing'
            if row['treatment']=='internal_only' and row['state']=='not_requested':row['state']='internal_no_supported_missing_dependency'
            if row['treatment']=='optional' and row['state']=='not_requested':row['state']='optional_not_blocking'
        for id in ['RC11.C1','RC16.C1','RC16.C2']:decisions[id]['state']='within_parent'
        relevant={'browse':{'T03','RC02','RC03'},'compare':{'RC01','T03','T04','T05','T06','T07','T08','RC20'},'review':{'RC01','T03','T05','T06','T07','T08','RC20'},'timing':{'RC01','T04','T05','RC04','RC05','RC06','RC08','RC09','RC10','RC11','RC12','RC13','RC26'},'providers':{'RC01','T06','RC21'},'drug_coverage':{'RC01','T07','RC22','RC24'},'drug_pricing':{'RC01','T07','RC22','RC23','RC18'},'medigap':{'RC01','T03','T04','T05','RC04','RC05','RC15','RC16','RC17'},'costs':{'RC25','RC18'}}.get(task,set())
        unresolved=[{'label':Q[id]['question'],'state':state,'id':id} for id,state in m['baselineDispositions'].items() if id in relevant]
        for key,state in m['skippedDetails'].items():
            id,entity,field=key.split('.',2)
            if id in relevant:unresolved.append({'label':Q[id]['question'] if field=='choice' else LABELS.get(field,field),'state':state,'id':id,'entity':entity})
        presentation=journey.presentation(self,guide,record,nextq)
        return {'version':CONTRACT['version'],'task':task,'preparing':m['preparing'],'nextQuestion':nextq,
            'state':'missing_information' if nextq else 'education' if task=='learn' else 'external_validation_held' if task else 'task_unknown',
            'limitation':HOLDS.get(task,''),'personalizedRecommendationAllowed':False,'externalVerificationReady':False,
            'unresolvedReportedInputs':unresolved,
            'ruleDecisions':decisions,'gapIds':sorted(DETAIL_KEYS),'journey':presentation,'sampleBrowsing':{'allowed':True,'requiresExplicitAction':True,'year':2027,'location':'Collier County, Florida','notRecommendation':True}}

    def turn(self,owner,payload):
        allowed={'guide','record','action','requestId','aiConsent','pendingId'}
        if not isinstance(payload,dict) or set(payload)-allowed or not re.fullmatch(r'[A-Za-z0-9-]{10,80}',str(payload.get('requestId',''))):raise ProfileError('Use a current conversation request.')
        guide,record=self.validate(payload['guide'],payload['record']);action=payload.get('action',{})
        if not isinstance(action,dict) or set(action)-{'type','id','fields','entity','message','task','preparing','step'}:raise ProfileError('Unsupported conversation action.')
        key=(owner,payload['requestId']);signature=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
        with self.lock:
            self.cache={k:v for k,v in self.cache.items() if v['expires']>time.time()}
            self.pending={k:v for k,v in self.pending.items() if v['expires']>time.time()}
            if len(self.cache)>128:self.cache.pop(next(iter(self.cache)))
            if key in self.cache:
                if self.cache[key]['signature']!=signature:raise ProfileError('This request key already belongs to another turn.',409)
                return copy.deepcopy(self.cache[key]['result'])
            if key in self.active:raise ProfileError('This turn is still running. Your information is unchanged.',409)
            self.active.add(key)
        started=time.monotonic();facts=[];ack='';ai_used=False;pending_id=payload.get('pendingId');edit=None;kind=action.get('type');ui_action=''
        try:
            before=(guide['stateVersion'],record['stateVersion']);m=metadata(record);assessment=self.assess(guide,record);current=assessment['nextQuestion']
            if kind=='start':ack="Hi, I’m Daylight, your AI Medicare guide. I’ll help you understand your options, one step at a time.\n\nWe’ll build your profile from the answers you share. You can review or change them at any time."
            elif kind=='task':
                if action.get('task') not in TASKS or not action.get('task'):raise ProfileError('Choose the work you want help with.')
                m['task']=action['task'];m['preparing']=action.get('preparing',False) is True;record['stateVersion']+=1
                m['journey']['samplesVisible']=False
                self.put(guide,'intent.goal', 'learn' if m['task']=='learn' else 'review' if m['task']=='review' else 'compare','user_choice')
                if m['task']=='learn' and journey.next_lesson(m):facts=[self.facts[journey.next_lesson(m)]]
            elif kind=='next':
                step=action.get('step')
                if step not in {'explore','learn_next','samples','review','resume'}:raise ProfileError('Choose a current next step.')
                if step=='explore':
                    m['task']='review' if self.value(guide,'intent.goal')=='review' else 'compare';m['preparing']=True
                    m['journey']['samplesVisible']=False
                    self.put(guide,'intent.goal',m['task'],'user_choice')
                    ack='Let’s build a picture of your situation. The current plan cards are samples for browsing.'
                elif step=='learn_next':
                    lesson=journey.next_lesson(m)
                    if lesson:facts=[self.facts[lesson]]
                    m['task']='learn';m['journey']['samplesVisible']=False
                elif step=='samples':m['journey']['samplesVisible']=True
                elif step=='resume':m['journey']['samplesVisible']=False
                elif step=='review':ui_action='review'
                record['stateVersion']+=1
            elif kind=='choice':
                id=action.get('id')
                if id not in Q:raise ProfileError('Unknown question.')
                self.apply(guide,record,{'id':id,'fields':action.get('fields',{}),'entity':action.get('entity') or (current['entity'] if current and current['id']==id else 'profile'),'correction':True})
                if id=='T01' and m['task']=='learn' and journey.next_lesson(m):facts=[self.facts[journey.next_lesson(m)]]
                elif id=='T01' and m['task'] in {'compare','review'}:ack='I’ll ask only the details needed to explore your options. The current plan cards are samples for browsing.'
            elif kind in {'unknown','defer'}:
                if not current or action.get('id')!=current['id']:raise ProfileError('Use the current question when leaving a detail open.')
                state='unknown' if kind=='unknown' else 'deferred'
                if current['id'] in FIELD:m['baselineDispositions'][current['id']]=state
                elif current['fields']:
                    for f in current['fields']:m['skippedDetails'][current['id']+'.'+current['entity']+'.'+f['key']]=state
                else:record['dispositions'][current['id']]={'state':'explicit_unknown' if kind=='unknown' else 'deferred','automaticReopen':False}
                record['stateVersion']+=1;ack='We’ll leave that open and continue with what you know.'
                if current['id']=='T01':
                    m['task']='learn';lesson=journey.next_lesson(m)
                    if lesson:facts=[self.facts[lesson]]
            elif kind=='edit':
                edit=action.get('id');m['editing']=edit;m['journey']['samplesVisible']=False
                if pending_id and self.pending.get(pending_id,{}).get('owner')==owner:self.pending.pop(pending_id,None)
                pending_id=None
            elif kind in {'confirm','reject'}:
                proposal=self.pending.get(payload.get('pendingId'))
                if not proposal or proposal['owner']!=owner or proposal['expires']<time.time() or proposal['versions']!=before:raise ProfileError('That interpretation expired or the information changed. Your reports are preserved.',409)
                if kind=='confirm':
                    for update in proposal['updates']:self.apply(guide,record,update,'confirmed_agent_interpretation')
                self.pending.pop(payload['pendingId'],None);ack='I’ve used those details.' if kind=='confirm' else 'I’ve kept your previous reports.'
            elif kind=='message':
                message=action.get('message','').strip()
                if not message or len(message)>1200:raise ProfileError('Use 1–1200 characters; longer lists can be added in several messages.')
                reject_sensitive(message)
                offered=assessment['journey']['nextStep']
                matching=next((c for c in (offered or {}).get('choices',[]) if message.casefold()==c['label'].casefold()),None)
                if matching:
                    response=self.turn(owner,{**payload,'requestId':payload['requestId']+'-next','action':{'type':'next','step':matching['value']}})
                    response['expectedStateVersion'],response['expectedReadinessRevision']=before
                    with self.lock:self.cache[key]={'signature':signature,'result':copy.deepcopy(response),'expires':time.time()+600}
                    return response
                if pending_id and re.fullmatch(r'(?i)(?:yes|no)[.!]?',message):
                    response=self.turn(owner,{**payload,'requestId':payload['requestId']+'-confirm','action':{'type':'confirm' if message.casefold().startswith('yes') else 'reject'}})
                    response['expectedStateVersion'],response['expectedReadinessRevision']=before
                    with self.lock:self.cache[key]={'signature':signature,'result':copy.deepcopy(response),'expires':time.time()+600}
                    return response
                direct=self.direct(message,current)
                if direct:
                    if direct.get('disposition'):
                        response=self.turn(owner,{**payload,'requestId':payload['requestId']+'-direct','action':{'type':direct['disposition'],'id':current['id']}})
                        response['expectedStateVersion'],response['expectedReadinessRevision']=before
                        with self.lock:self.cache[key]={'signature':signature,'result':copy.deepcopy(response),'expires':time.time()+600}
                        return response
                    for update in direct['updates']:self.apply(guide,record,update)
                else:
                    if not self.fixture and (not self.agent.enabled or not self.agent.client.available):raise ModelUnavailable('Live AI is unavailable. Your message is preserved; controls, reviewed help and sample browsing remain available.')
                    if payload.get('aiConsent') is not True:raise ProfileError('AI transfer needs your permission. Buttons and reviewed explanations still work.',428)
                    safe=copy.deepcopy(guide);safe['fields']={k:v for k,v in guide['fields'].items() if k in {'intent.goal','knowledge.general','subject.role','coverage.current'}}
                    # No previous health lists, dates, location or raw transcript are attached.
                    context={'task':m['task'],'preparing':m['preparing'],'lastFactIds':m['lastFactIds'],'activeQuestion':{'id':current['id'],'fields':[f['key'] for f in current['fields']],'entity':current['entity']} if current else None,
                        'knownReports':{id:{'fields':sorted(f['value'].keys()),'entities':[{'entity':x['entity'],'fields':sorted(x)} for x in f['value'].get('items',[])]} for id,f in record['facts'].items() if not f.get('stale')},
                        'definitions':self.agent.definitions,'safeReports':{k:v['value'] for k,v in safe['fields'].items()},'pending':bool(payload.get('pendingId'))}
                    previous_task=m['task']
                    if self.fixture:result=self.fixture_result(message,current)
                    else:result=self.agent.interpret(owner,message,safe,context,payload['requestId']);ai_used=True
                    m['checks']=sorted(set(m['checks'])|{r['id'] for r in result.get('requests',[]) if r['id']!='coverage_change' or re.search(r'(?i)\bjoin|drop|cancel|switch|replace',r['quote'])})
                    if result['mode']=='answer' and result['fact_ids'] and not m['task']:m['task']='learn';record['stateVersion']+=1
                    learning_switch=bool(re.search(r'(?i)(?:i want to|let.s|instead.*)(?:\s+just)?\s+(?:learn|understand)',message))
                    if result['task'] and (not m['task'] or result['task']!='learn' or learning_switch):
                        m['task']=result['task'];m['preparing']=result['task'] not in {'learn','browse'};record['stateVersion']+=1
                    requested_task=explicit_task(message)
                    if requested_task:
                        m['task']=requested_task;m['preparing']=requested_task not in {'learn','browse'};record['stateVersion']+=1
                        self.put(guide,'intent.goal','review' if requested_task=='review' else 'compare','confirmed_agent_interpretation')
                    selected_task,selected_preparing=m['task'],m['preparing']
                    updates=[]
                    for update in result['updates']:
                        d={f['key']:f['value'] for f in update['fields']}
                        if any(k not in Q[update['id']]['fieldNames'] for k in d):raise ModelUnavailable('A proposed field is outside this question’s scope.')
                        # Narrative values must be grounded in the exact submitted quote.
                        for k,val in d.items():
                            if k not in {'choice','month','jobEnd','coverageEnd','eventDate','start','daysSupply','channel','ageBand','year','zip','county','priorMedigap'} and val and val.casefold() not in {'unknown','deferred','not sure','check later'} and val.casefold() not in update['quote'].casefold():raise ModelUnavailable('A detail was not explicitly supplied. Your information is unchanged.')
                            if val.casefold() in {'unknown','deferred','not sure','check later'} and not re.search(r'(?i)don.t know|do not know|unknown|not sure|check later|defer',update['quote']):raise ModelUnavailable('A missing detail was not explicitly left unknown or deferred.')
                            if k in {'month','jobEnd','coverageEnd','eventDate','start'} and val and val.casefold() not in {'unknown','deferred','not sure','check later'}:
                                date=month(val)
                                candidates=re.findall(r'(?:19|20)\d{2}-(?:0[1-9]|1[0-2])(?:-\d{2})?|(?:'+ '|'.join(MONTHS)+r')\s+(?:\d{1,2},?\s+)?(?:19|20)\d{2}|\b(?:0?[1-9]|1[0-2])[/.-](?:(?:19|20)?\d{2})\b|\b(?:0[1-9]|1[0-2])\d{2}\b|no scheduled end|still working|ongoing',update['quote'],re.I)
                                if date not in {month(v) for v in candidates}:raise ModelUnavailable('An actual date could not be traced to the stated month and year. Your reports are unchanged.')
                        updates.append({**update,'fields':d})
                    pending=[u for u in updates if u.get('uncertain')]
                    if payload.get('pendingId') and result['confirmation'] in {'yes','no'}:
                        p=self.pending.get(payload['pendingId'])
                        if not p or p['owner']!=owner or p['versions']!=before:raise ProfileError('The interpretation changed. Review it again.',409)
                        if result['confirmation']=='yes':updates=[{**u,'uncertain':False} for u in p['updates']]+updates
                        self.pending.pop(payload['pendingId'],None)
                        pending_id=None
                    # Apply baseline dependencies first, independent of model output order.
                    for update in sorted(updates,key=lambda u:0 if u['id'] in FIELD else 1):
                        if not update.get('uncertain'):self.apply(guide,record,update,'confirmed_agent_interpretation')
                    # A broad T01 compatibility label cannot override the actual task.
                    if selected_task:
                        m['task'],m['preparing']=selected_task,selected_preparing
                        self.put(guide,'intent.goal','learn' if selected_task=='learn' else 'review' if selected_task=='review' else 'compare','confirmed_agent_interpretation')
                    if not self.report(record,'RC01') and not self.value(guide,'subject.role'):
                        helper=bool(re.search(r'(?i)(?:for|helping) my (?:mother|father|parent|spouse|husband|wife)\b',message))
                        own=bool(re.search(r'(?i)\bmy (?:insurance|health coverage|medicare|prescriptions)\b|\bi (?:don.t|do not) have medicare\b',message))
                        if helper!=own:self.apply(guide,record,{'id':'RC01','fields':{'choice':'someone' if helper else 'self'}},'confirmed_agent_interpretation')
                    own_job=re.search(r'(?i)\bmy (?:health )?(?:insurance|coverage)\s+(?:is\s+)?(?:through|from)\s+my (?:own )?current job\b',message)
                    if own_job and not re.search(r'(?i)\bif|suppose|hypothetical|example\b',message) and self.value(guide,'subject.role')=='self' and not self.report(record,'RC09'):
                        self.apply(guide,record,{'id':'RC09','fields':{'choice':'my_job'}},'confirmed_agent_interpretation')
                        pending=[u for u in pending if u['id']!='RC09']
                    if pending:
                        pending_id=secrets.token_urlsafe(24)
                        self.pending[pending_id]={'owner':owner,'versions':(guide['stateVersion'],record['stateVersion']),'updates':pending,'expires':time.time()+600}
                    educational=not requested_task or bool(re.search(r'(?i)what (?:is|are)|how does|why|explain',message))
                    facts=[self.facts[fid] for fid in result['fact_ids']] if result['mode']=='answer' and educational else []
                    ack='' if facts or updates else 'Let’s focus on that and use what you’ve already shared.' if requested_task or selected_task!=previous_task else 'I don’t have a checked explanation for that question yet. Your information is still here.'
                    if any(u.get('correction') for u in updates):ack='I’ve updated those reported details.'
                    if result['mode'] in {'unknown','defer'} and current and not updates:
                        response=self.turn(owner,{**payload,'requestId':payload['requestId']+'-state','guide':guide,'record':record,'action':{'type':'unknown' if result['mode']=='unknown' else 'defer','id':current['id']}})
                        response['expectedStateVersion'],response['expectedReadinessRevision']=before
                        response['metrics']['llmCalls']=int(ai_used)
                        with self.lock:self.cache[key]={'signature':signature,'result':copy.deepcopy(response),'expires':time.time()+600}
                        return response
            elif kind=='help':
                facts=[self.facts[fid] for fid in ['routesintro','original','advantage'] if fid in self.facts]
                ack='Here’s how to tell these coverage arrangements apart.'
            elif kind!='refresh':raise ProfileError('Unsupported conversation action.')
            if facts:
                m['lastFactIds']=[f['id'] for f in facts];journey.remember(m,facts);record['stateVersion']+=1
            assessment=self.assess(guide,record,edit)
            pending=self.pending.get(pending_id)
            response={'guide':guide,'record':record,'assessment':assessment,'reply':ack,'facts':facts,'pendingId':pending_id,
                'pendingUpdates':[{'id':u['id'],'fields':u['fields'],'entity':u.get('entity','profile')} for u in pending['updates']] if pending else [],
                'expectedStateVersion':before[0],'expectedReadinessRevision':before[1],'uiAction':ui_action,
                'metrics':{'llmCalls':int(ai_used),'processingMs':round((time.monotonic()-started)*1000),'synthetic':self.fixture},
                'personalRecommendation':False}
            self.validate(guide,record)
            with self.lock:self.cache[key]={'signature':signature,'result':copy.deepcopy(response),'expires':time.time()+600}
            return response
        finally:
            with self.lock:self.active.discard(key)

    def direct(self,message,current):
        """Only whole-message matches. Mixed text always reaches the language adapter."""
        if not current:return None
        if re.fullmatch(r'(?i)(?:not sure|i don.t know|unknown)[.!]?',message):return {'disposition':'unknown'}
        if re.fullmatch(r'(?i)(?:check later|add later|defer)[.!]?',message):return {'disposition':'defer'}
        if current['id'] in {'T06','T07'} and re.fullmatch(r'(?i)(?:no|none)[.!]?',message):return {'updates':[{'id':current['id'],'fields':{'choice':'none' if current['id']=='T06' else 'no'}}]}
        for value,label in current['choices']:
            if message.casefold()==label.casefold():return {'updates':[{'id':current['id'],'fields':{'choice':value},'entity':current['entity']}]}
        if current['id']=='T03' and re.fullmatch(r'\d{5}',message):return {'updates':[{'id':'T03','fields':{'zip':message}}]}
        if current['id']=='RC03':
            try:value=message if re.fullmatch(r'20\d{2}',message) else month(message)
            except ProfileError:return None
            return {'updates':[{'id':'RC03','fields':{'year':value}}]}
        if len(current['fields'])==1 and current['fields'][0]['key'] in {'month','jobEnd','coverageEnd','start'}:
            try:value=month(message if not current.get('knownYear') or message.casefold() not in MONTHS else message+' '+current['knownYear'])
            except ProfileError:return None
            return {'updates':[{'id':current['id'],'fields':{current['fields'][0]['key']:value,**({'choice':'month'} if current['id']=='T04' else {})}}]}
        return None

    def fixture_result(self,message,current):
        """Explicit fixture interpreter for UI mechanics. Never used by the live service."""
        result={'mode':'report','task':'','task_quote':'','requests':[],'updates':[],'fact_ids':[],'reflection':'','confirmation':''}
        def add(id,fields):result['updates'].append({'id':id,'fields':[{'key':k,'value':v} for k,v in fields.items()],'entity':'profile','quote':message,'uncertain':False,'correction':False})
        if re.search(r'(?i)what is medicare|what.*advantage|difference',message):result.update(mode='answer',fact_ids=['advantage'] if 'advantage' in message.lower() else ['basics'])
        elif current and current['id'] in {'T06','T07'}:add(current['id'],{'text':message})
        elif 'retir' in message.lower():
            result.update(task='timing',task_quote=message);add('RC01',{'choice':'self'});add('T05',{'choice':'employer'});add('RC09',{'choice':'my_job'})
            match=re.search(r'(?i)(january|february|march|april|may|june|july|august|september|october|november|december) (20\d{2})',message)
            if match:add('T04',{'choice':'month','month':month(match[0])})
        else:result['mode']='unsupported'
        return result

    def save(self,token,csrf,payload):
        if set(payload)!={'guide','record','expectedVersion','expectedReadinessVersion','operationId'}:raise ProfileError('Use the complete save request.')
        guide,record=self.validate(payload['guide'],payload['record']);self.profiles.require(token,csrf)
        if guide['preferences'].get('saveGuide') is not True:raise ProfileError('Choose saving before storing information.')
        expected=payload['expectedVersion'];expected_r=payload['expectedReadinessVersion'];op=payload['operationId']
        if type(expected) is not int or type(expected_r) is not int or not re.fullmatch(r'[A-Za-z0-9-]{10,80}',str(op)):raise ProfileError('Use current save versions and operation key.')
        guide=for_storage(guide)
        if not guide['preferences'].get('saveSensitive'):
            record['facts']={};record['conversation']['details']={}
            record['history']=[{k:v for k,v in h.items() if k!='previous'} for h in record['history']]
        signature=hashlib.sha256(json.dumps([guide,record],sort_keys=True).encode()).hexdigest();h=self.profiles.digest(token)
        with self.profiles.lock,self.profiles.db() as db:
            db.execute('BEGIN IMMEDIATE')
            previous=db.execute('SELECT signature,version FROM requests WHERE token_hash=? AND op=?',(h,op)).fetchone()
            previous_r=db.execute('SELECT signature,version FROM readiness_requests WHERE token_hash=? AND op=?',(h,op)).fetchone()
            if previous or previous_r:
                if not previous or not previous_r or previous[0]!=signature or previous_r[0]!=signature:raise ProfileError('Save operation already used.',409)
                return {'saved':True,'version':previous[1],'readinessVersion':previous_r[1],'replayed':True}
            guest=db.execute('SELECT version,expires FROM guests WHERE token_hash=?',(h,)).fetchone();r=db.execute('SELECT version FROM readiness WHERE token_hash=?',(h,)).fetchone()
            if not guest or guest[1]<=self.profiles.clock():raise ProfileError('Guest session expired.',401)
            if guest[0]!=expected or (r[0] if r else 0)!=expected_r:raise ProfileError('Another tab changed the saved copy. Your current information is preserved.',409)
            version=expected+1;rv=expected_r+1
            db.execute('UPDATE guests SET version=?,guide=? WHERE token_hash=?',(version,json.dumps(guide),h))
            db.execute('INSERT INTO readiness VALUES(?,?,?) ON CONFLICT(token_hash) DO UPDATE SET version=excluded.version,record=excluded.record',(h,rv,json.dumps(record)))
            db.execute('INSERT INTO requests VALUES(?,?,?,?)',(h,op,version,signature));db.execute('INSERT INTO readiness_requests VALUES(?,?,?,?)',(h,op,signature,rv))
            db.execute('DELETE FROM requests WHERE token_hash=? AND version<?',(h,max(0,version-20)));db.execute('DELETE FROM readiness_requests WHERE token_hash=? AND version<?',(h,max(0,rv-20)))
        return {'saved':True,'version':version,'readinessVersion':rv,'omittedSensitive':not guide['preferences'].get('saveSensitive',False)}

