"""Private, cookie-owned guest guides. No credentials or chat transcript storage."""
import copy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time

SENSITIVE = {'coverage.requestedStartMonth','needs.medicationDetails','intent.goalDetail','needs.priorityOther','subject.displayLabel','coverage.birth','coverage.birth.firstDay','needs.medications','needs.pharmacies','needs.providers','outcome.drafts','comparison.requestedNames'}
ENVELOPE_KEYS = {'value','status','confirmation','rawText','source','revision','confirmedAt'}
STATUSES = {'reported','unknown','skipped','stale','derived'}

class ProfileError(ValueError):
    def __init__(self,message,code=422):super().__init__(message);self.code=code

def bounded(value,depth=0):
    if depth>5:raise ProfileError('Guide structure is too deep.')
    if value is None or isinstance(value,bool):return
    if isinstance(value,(int,float)):
        if not -1000000<=value<=10000000:raise ProfileError('Invalid numeric value.')
    elif isinstance(value,str):
        if len(value)>2400 or '\x00' in value:raise ProfileError('A guide value is too long.')
        if re.search(r'\b\d{3}-\d{2}-\d{4}\b',value):raise ProfileError('Remove ID numbers before saving or sending.')
    elif isinstance(value,list):
        if len(value)>100:raise ProfileError('Guide list is too long.')
        for x in value:bounded(x,depth+1)
    elif isinstance(value,dict):
        if len(value)>100 or any(not isinstance(k,str) or len(k)>90 or k in {'__proto__','constructor','prototype'} for k in value):raise ProfileError('Unsupported guide object.')
        for x in value.values():bounded(x,depth+1)
    else:raise ProfileError('Unsupported guide value.')

def validate_guide(guide,contract):
    if not isinstance(guide,dict) or set(guide)-{'schemaVersion','stateVersion','fields','flow','topics','preferences'}:raise ProfileError('Unsupported guide document.')
    if guide.get('schemaVersion')!=2 or type(guide.get('stateVersion')) is not int or guide.get('stateVersion',-1)<0:raise ProfileError('Unsupported guide version.')
    fields=guide.get('fields'); allowed={f for n in contract['nodes'] for f in n['writes']}|{'knowledge.general','privacy.persistenceChoice','intent.goal','subject.role','subject.displayLabel','intent.timingQuestion'}
    if not isinstance(fields,dict) or set(fields)-allowed:raise ProfileError('Unsupported profile field.')
    for name,e in fields.items():
        if not isinstance(e,dict) or set(e)-ENVELOPE_KEYS or e.get('status') not in STATUSES or e.get('confirmation')!='confirmed_by_user':raise ProfileError('Only confirmed reports or explicit unknowns can be recorded.')
        bounded(e.get('value'));bounded(e.get('rawText',''))
        if e.get('source') not in {'user_choice','confirmed_agent_interpretation','user_text','location_reference'}:raise ProfileError('Unsupported fact provenance.')
        if e.get('status')=='derived' or e.get('source')=='location_reference':
            if name not in {'comparison.scope.county','comparison.scope.locationEvidence'} or e.get('source')!='location_reference' or e.get('status')!='derived':raise ProfileError('Only a published ZIP reference can derive county context.')
            reference=json.loads((Path(__file__).resolve().parents[1]/'apps/chat/zip-counties.json').read_text());zip_value=fields.get('comparison.scope.zip',{}).get('value');matches=reference['zips'].get(zip_value,[])
            if len(matches)!=1:raise ProfileError('An ambiguous ZIP requires an explicit county choice.')
            expected={'fips':matches[0][0],'name':matches[0][1],'state':matches[0][2]} if name=='comparison.scope.county' else {'source':reference['source_url'],'period':reference['period'],'method':'unique_zip_reference'}
            if e.get('value')!=expected:raise ProfileError('County context does not match the published reference.')
        if name=='intent.goal' and e.get('value') not in {'learn','compare','review','job','unresolved'}:raise ProfileError('Unknown goal.')
        if name=='knowledge.general' and e.get('value') not in {'new','some','comfortable','unknown'}:raise ProfileError('Unknown familiarity.')
        if name=='subject.role' and e.get('value') not in {'self','someone','other'}:raise ProfileError('Unknown recipient.')
    flow=guide.get('flow',{});nodes={n['id'] for n in contract['nodes']}|{'X01'}
    if not isinstance(flow,dict) or set(flow)-{'node','history','queue','lessonReturn','personalReview','guideOpen','origin','invalidations','scroll'} or flow.get('node') not in nodes:raise ProfileError('Unknown guide location.')
    for frame in flow.get('history',[]):
        if not isinstance(frame,dict) or set(frame)-{'node','scroll','queue','lessonReturn','personalReview'} or frame.get('node') not in nodes:raise ProfileError('Invalid Back history.')
    if not isinstance(flow.get('queue',[]),list) or any(x not in nodes for x in flow.get('queue',[])):raise ProfileError('Unknown lesson queue.')
    if flow.get('lessonReturn') is not None and flow['lessonReturn'] not in nodes:raise ProfileError('Unknown lesson return.')
    if not isinstance(guide.get('topics',{}),dict) or any(k not in nodes for k in guide.get('topics',{})):raise ProfileError('Unknown teaching topic.')
    prefs=guide.get('preferences',{})
    if not isinstance(prefs,dict) or set(prefs)-{'saveSensitive','saveGuide','noticeVersion'} or any(not isinstance(v,bool) for k,v in prefs.items() if k!='noticeVersion') or prefs.get('noticeVersion')!='guest-notice-2026-10-21-v1':raise ProfileError('Invalid save choices.')
    bounded(flow);bounded(guide.get('topics',{}))
    if len(json.dumps(guide).encode())>65000:raise ProfileError('Guide is too large.',413)
    return copy.deepcopy(guide)

def for_storage(guide):
    value=copy.deepcopy(guide)
    if not value.get('preferences',{}).get('saveSensitive'):
        value['fields']={k:v for k,v in value['fields'].items() if k not in SENSITIVE}
    for e in value['fields'].values():e.pop('rawText',None)
    # Free-text drafts, conversation history, pending interpretations and identifiers are never persisted.
    return value

class GuestProfiles:
    def __init__(self,path,contract,retention_days=7,clock=time.time):
        if not 1<=retention_days<=30:raise ProfileError('Choose a retention period from 1 to 30 days.')
        self.path=Path(path);self.contract=contract;self.retention_days=retention_days;self.clock=clock;self.lock=threading.RLock()
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if self.path.parent.stat().st_mode & 0o077:raise ProfileError('Use a private database directory accessible only to this user.')
        if self.path.is_symlink():raise ProfileError('Profile database cannot be a symlink.')
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS guests (token_hash TEXT PRIMARY KEY, csrf TEXT NOT NULL, expires REAL NOT NULL, version INTEGER NOT NULL DEFAULT 0, guide TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS requests (token_hash TEXT NOT NULL, op TEXT NOT NULL, version INTEGER NOT NULL, signature TEXT NOT NULL, PRIMARY KEY(token_hash,op))')
        os.chmod(self.path,0o600)
    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=5)
        try:
            db.execute('PRAGMA secure_delete=ON');db.execute('PRAGMA journal_mode=DELETE');db.execute('PRAGMA foreign_keys=ON')
            with db:yield db
        finally:db.close()
    @staticmethod
    def digest(token):return hashlib.sha256(token.encode()).hexdigest()
    def purge_expired(self):
        with self.lock,self.db() as db:
            expired=[r[0] for r in db.execute('SELECT token_hash FROM guests WHERE expires<=?',(self.clock(),))]
            for h in expired:db.execute('DELETE FROM requests WHERE token_hash=?',(h,))
            db.execute('DELETE FROM guests WHERE expires<=?',(self.clock(),))
            return len(expired)
    def session(self,token=None):
        with self.lock,self.db() as db:
            expired=[r[0] for r in db.execute('SELECT token_hash FROM guests WHERE expires<=?',(self.clock(),))]
            for h in expired:db.execute('DELETE FROM requests WHERE token_hash=?',(h,))
            db.execute('DELETE FROM guests WHERE expires<=?',(self.clock(),))
            if isinstance(token,str) and re.fullmatch(r'[A-Za-z0-9_-]{43}',token):
                row=db.execute('SELECT csrf,expires,version,guide FROM guests WHERE token_hash=?',(self.digest(token),)).fetchone()
                if row:return token,self.info(row),False
            token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32);expires=self.clock()+self.retention_days*86400
            db.execute('INSERT INTO guests VALUES(?,?,?,0,NULL)',(self.digest(token),csrf,expires))
            return token,{'csrf':csrf,'expiresAt':expires,'version':0,'hasSaved':False,'retentionDays':self.retention_days},True
    def info(self,row):return {'csrf':row[0],'expiresAt':row[1],'version':row[2],'hasSaved':row[3] is not None,'retentionDays':self.retention_days}
    def require(self,token,csrf=None):
        if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',token):raise ProfileError('This guest session expired. Reload before saving.',401)
        with self.db() as db:row=db.execute('SELECT csrf,expires,version,guide FROM guests WHERE token_hash=?',(self.digest(token),)).fetchone()
        if not row or row[1]<=self.clock():raise ProfileError('This guest session expired. Reload before saving.',401)
        if csrf is not None and not secrets.compare_digest(row[0],csrf):raise ProfileError('Reload this page before changing the saved guide.',403)
        return row
    def get(self,token):
        row=self.require(token);return {**self.info(row),'guide':json.loads(row[3]) if row[3] else None}
    def save(self,token,csrf,expected,operation,guide):
        self.require(token,csrf)
        if type(expected) is not int or not isinstance(operation,str) or not re.fullmatch(r'[a-zA-Z0-9-]{10,80}',operation):raise ProfileError('A version and operation key are required.')
        value=for_storage(validate_guide(guide,self.contract))
        if value.get('preferences',{}).get('saveGuide') is not True:raise ProfileError('Choose saving before storing a guide.')
        h=self.digest(token);signature=hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
        with self.lock,self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            previous=db.execute('SELECT version,signature FROM requests WHERE token_hash=? AND op=?',(h,operation)).fetchone()
            if previous:
                if previous[1]!=signature:raise ProfileError('Operation key already used for another guide.',409)
                return {'version':previous[0],'saved':True,'replayed':True}
            row=db.execute('SELECT version,expires FROM guests WHERE token_hash=?',(h,)).fetchone()
            if not row or row[1]<=self.clock():raise ProfileError('Guest session expired.',401)
            if row[0]!=expected:raise ProfileError('Another tab changed this guide. Review the saved version before replacing it.',409)
            version=expected+1;db.execute('UPDATE guests SET version=?,guide=? WHERE token_hash=?',(version,json.dumps(value,ensure_ascii=False),h));db.execute('INSERT INTO requests VALUES(?,?,?,?)',(h,operation,version,signature))
            db.execute('DELETE FROM requests WHERE token_hash=? AND version<?',(h,max(0,version-20)))
        return {'version':version,'saved':True,'savedAt':self.clock(),'expiresAt':row[1],'omittedSensitive':not value['preferences'].get('saveSensitive',False)}
    def delete(self,token,csrf,expected):
        self.require(token,csrf);h=self.digest(token)
        with self.lock,self.db() as db:
            db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT version FROM guests WHERE token_hash=?',(h,)).fetchone()
            if not row or row[0]!=expected:raise ProfileError('Saved guide changed. Review it before deleting.',409)
            db.execute('DELETE FROM requests WHERE token_hash=?',(h,));db.execute('DELETE FROM guests WHERE token_hash=?',(h,))
        return {'deleted':True,'scope':'This browser guest guide and its session; no outside account or insurer data.'}
