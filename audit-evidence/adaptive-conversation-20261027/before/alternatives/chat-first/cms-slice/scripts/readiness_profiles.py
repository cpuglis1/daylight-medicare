"""D70 additive cookie-owned readiness records; no old guide fields are migrated."""
import copy,hashlib,json,re
from guest_profiles import ProfileError,bounded
VERSION='readiness-inputs-20261022-v1'
IDS={'RC%02d'%i for i in range(1,29)}
STATES={'resolved_report','explicit_unknown','deferred','blocked_dependency','needs_review','not_saved'}
def validate(record):
    allowed={'schemaVersion','ruleVersion','stateVersion','guideFingerprint','facts','dispositions','queue','index','shown','pass','history','mode','editNotice','reviewOnly','requests','completeness','entityDispositions','detailsRequested'}
    if not isinstance(record,dict) or set(record)-allowed or record.get('schemaVersion')!=1 or record.get('ruleVersion')!=VERSION:raise ProfileError('Unsupported readiness version. Your existing guide is unchanged.')
    if type(record.get('stateVersion'))is not int or record['stateVersion']<0:raise ProfileError('Invalid readiness revision.')
    if not isinstance(record.get('facts'),dict) or set(record['facts'])-IDS or not isinstance(record.get('dispositions'),dict) or set(record['dispositions'])-IDS:raise ProfileError('Unsupported readiness detail.')
    for fact in record['facts'].values():
        if not isinstance(fact,dict) or set(fact)-{'value','confirmation','source','revision','stale'} or fact.get('confirmation')!='confirmed_by_user' or fact.get('source') not in {'user_choice','confirmed_agent_interpretation','existing_confirmed_guide'} or type(fact.get('revision'))is not int:raise ProfileError('Only confirmed readiness reports may be saved.')
        if not isinstance(fact.get('value'),dict) or set(fact['value'])-{'choice','zip','county','year','month','ageBand','jobEnd','coverageEnd','location','practice','city','name','strength','form','supply','pharmacy','amount','includes','entity','items','programs','brand','quantity','daysSupply','channel','eventDate','event','gap','start','priorMedigap','qualification','homeStatus'}:raise ProfileError('Unsupported readiness fact value.')
        for item in fact['value'].get('items',[]):
            if not isinstance(item,dict) or set(item)-{'choice','entity','practice','city','name','strength','form','brand','quantity','daysSupply','pharmacy','channel','supply'}:raise ProfileError('Unsupported entity value.')
        if len(fact['value'].get('items',[]))>30:raise ProfileError('Too many listed entities.')
        if any(p not in {'medicaid','extra_help','part_b_help','ssi'} for p in fact['value'].get('programs',[])):raise ProfileError('Unsupported assistance program.')
        bounded(fact['value'])
    for d in record['dispositions'].values():
        if not isinstance(d,dict) or set(d)-{'state','automaticReopen'} or d.get('state')not in STATES or d.get('automaticReopen')is not False:raise ProfileError('Unsupported readiness disposition.')
    for key in ['queue','shown']:
        if not isinstance(record.get(key),list) or len(set(record[key]))!=len(record[key]) or any(x not in IDS for x in record[key]):raise ProfileError('Invalid readiness queue.')
    if len(record['shown'])>28 or type(record.get('index'))is not int or not 0<=record['index']<=len(record['queue']) or type(record.get('pass'))is not int or record['pass']<0 or record.get('mode')not in {'question','summary'}:raise ProfileError('Invalid readiness progress.')
    if len(record.get('history',[]))>100 or not isinstance(record.get('guideFingerprint',''),str) or len(record.get('guideFingerprint',''))>12000:raise ProfileError('Readiness state is too large.')
    bounded(record['history']);bounded(record['editNotice'])
    if 'reviewOnly'in record and type(record['reviewOnly'])is not bool:raise ProfileError('Invalid explicit review mode.')
    if 'detailsRequested' in record and type(record['detailsRequested']) is not bool:raise ProfileError('Unsupported readiness request scope.')
    from readiness_conversation import REQUESTS
    if not isinstance(record.get('requests',[]),list) or any(r not in REQUESTS for r in record.get('requests',[])):raise ProfileError('Unsupported requested check.')
    entity_dispositions=record.get('entityDispositions',{})
    if not isinstance(entity_dispositions,dict) or set(entity_dispositions)-{'RC21','RC22','RC23'}:raise ProfileError('Unsupported entity dispositions.')
    for items in entity_dispositions.values():
        if not isinstance(items,dict) or len(items)>30:raise ProfileError('Too many entity dispositions.')
        for entity,disposition in items.items():
            if not re.fullmatch(r'(?:doctor|medicine)-(?:extra-)?[0-9]{1,3}',entity) or set(disposition)!={'state','automaticReopen'} or disposition['state'] not in {'explicit_unknown','deferred'} or disposition['automaticReopen'] is not False:raise ProfileError('Invalid entity disposition.')
    completeness=record.get('completeness',{})
    if not isinstance(completeness,dict) or set(completeness)-{'checks','capabilities','remaining','baselineChecks'}:raise ProfileError('Unsupported completeness map.')
    states={'confirmed_reported','unresolved','not_applicable','tentative','resolved_report'}|STATES
    baseline=completeness.get('baselineChecks',{})
    if not isinstance(baseline,dict) or set(baseline)-{'T%02d'%i for i in range(1,11)} or any(v not in {'confirmed_reported','tentative','unknown','deferred','unresolved','not_saved','not_applicable'} for v in baseline.values()):raise ProfileError('Invalid baseline completeness.')
    for id,check in completeness.get('checks',{}).items():
        if id not in IDS or set(check)!={'state','dependencies','missing','evidence'} or check['state'] not in states or check['evidence']!='not_verified' or any(d not in IDS for d in check['dependencies']):raise ProfileError('Invalid completeness check.')
        for item in check['missing']:
            if set(item)!={'entity','fields'} or not isinstance(item['entity'],str) or not re.fullmatch(r'(?:profile|(?:doctor|medicine)-(?:extra-)?[0-9]{1,3})',item['entity']) or not isinstance(item['fields'],list) or any(f not in {'choice','practice','city','name','strength','form','brand','quantity','daysSupply','pharmacy','channel','zip','county','month','jobEnd','coverageEnd','start','priorMedigap','location','eventDate','gap','event','homeStatus'} for f in item['fields']):raise ProfileError('Invalid missing-detail metadata.')
    if any(v not in {'source_held','review_pending','network_data_missing','formulary_pricing_data_missing','expert_review_pending','program_source_gaps'} for v in completeness.get('capabilities',{}).values()):raise ProfileError('Unsupported evidence state.')
    # The persistence contract never accepts raw prompts, drafts, source truth or verified states.
    if len(json.dumps(record).encode())>50000:raise ProfileError('Readiness record is too large.',413)
    return copy.deepcopy(record)
class ReadinessProfiles:
    def __init__(self,profiles):
        self.profiles=profiles
        with profiles.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS readiness (token_hash TEXT PRIMARY KEY REFERENCES guests(token_hash) ON DELETE CASCADE, version INTEGER NOT NULL, record TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS readiness_requests (token_hash TEXT NOT NULL REFERENCES guests(token_hash) ON DELETE CASCADE, op TEXT NOT NULL, signature TEXT NOT NULL, version INTEGER NOT NULL, PRIMARY KEY(token_hash,op))')
    def get(self,token):
        self.profiles.require(token)
        with self.profiles.db() as db:row=db.execute('SELECT version,record FROM readiness WHERE token_hash=?',(self.profiles.digest(token),)).fetchone()
        return {'version':row[0] if row else 0,'record':json.loads(row[1]) if row else None}
    def save(self,token,csrf,expected,operation,record):
        with self.profiles.lock:return self._save(token,csrf,expected,operation,record)
    def _save(self,token,csrf,expected,operation,record):
        self.profiles.require(token,csrf)
        if type(expected)is not int or not isinstance(operation,str) or not re.fullmatch(r'[a-zA-Z0-9-]{10,80}',operation):raise ProfileError('A readiness version and operation key are required.')
        record=validate(record);guide=self.profiles.get(token)['guide'];prefs=(guide or {}).get('preferences',{})
        if prefs.get('saveGuide')is not True:raise ProfileError('Choose guide saving first.')
        if not prefs.get('saveSensitive'):
            for id in record['facts']:
                if record['dispositions'].get(id,{}).get('state')=='resolved_report':record['dispositions'][id]={'state':'not_saved','automaticReopen':False}
            record['facts']={}
            for check in record.get('completeness',{}).get('checks',{}).values():
                if check['state'] in {'resolved_report','confirmed_reported'}:check['state']='not_saved'
            record['history']=[{k:v for k,v in entry.items() if k!='previous'} for entry in record.get('history',[])]
        h=self.profiles.digest(token);signature=hashlib.sha256(json.dumps(record,sort_keys=True).encode()).hexdigest()
        with self.profiles.lock,self.profiles.db() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT signature,version FROM readiness_requests WHERE token_hash=? AND op=?',(h,operation)).fetchone()
            if old:
                if old[0]!=signature:raise ProfileError('Readiness operation already used.',409)
                return {'version':old[1],'saved':True,'replayed':True}
            current=db.execute('SELECT version FROM readiness WHERE token_hash=?',(h,)).fetchone()
            if (current[0] if current else 0)!=expected:raise ProfileError('Another tab changed readiness. Review the saved copy before replacing it.',409)
            # Recheck authorization/expiry while holding the write transaction.
            row=db.execute('SELECT expires FROM guests WHERE token_hash=?',(h,)).fetchone()
            if not row or row[0]<=self.profiles.clock():raise ProfileError('Guest session expired.',401)
            version=expected+1;db.execute('INSERT INTO readiness VALUES(?,?,?) ON CONFLICT(token_hash) DO UPDATE SET version=excluded.version,record=excluded.record',(h,version,json.dumps(record,ensure_ascii=False)))
            db.execute('INSERT INTO readiness_requests VALUES(?,?,?,?)',(h,operation,signature,version));db.execute('DELETE FROM readiness_requests WHERE token_hash=? AND version<?',(h,max(0,version-20)))
        return {'version':version,'saved':True,'omittedSensitive':not prefs.get('saveSensitive',False)}

    def apply_preferences(self,token):
        with self.profiles.lock,self.profiles.db() as db:
            h=self.profiles.digest(token);row=db.execute('SELECT guide FROM guests WHERE token_hash=?',(h,)).fetchone();saved=db.execute('SELECT version,record FROM readiness WHERE token_hash=?',(h,)).fetchone()
            if not saved:return 0
            prefs=json.loads(row[0]).get('preferences',{}) if row and row[0] else {}
            if prefs.get('saveSensitive'):return saved[0]
            record=json.loads(saved[1])
            if not record['facts'] and not any('previous' in entry for entry in record.get('history',[])):return saved[0]
            for id in record['facts']:
                if record['dispositions'].get(id,{}).get('state')=='resolved_report':record['dispositions'][id]={'state':'not_saved','automaticReopen':False}
            
            for check in record.get('completeness',{}).get('checks',{}).values():
                if check['state'] in {'resolved_report','confirmed_reported'}:check['state']='not_saved'
            record['facts']={};record['history']=[{k:v for k,v in entry.items() if k!='previous'} for entry in record.get('history',[])];version=saved[0]+1
            db.execute('UPDATE readiness SET version=?,record=? WHERE token_hash=?',(version,json.dumps(record),h))
            return version
