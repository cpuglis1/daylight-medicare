"""Application-wide $1 UTC-day cap. No transcript, profile IDs or secrets in this ledger."""
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen
from chat import ModelUnavailable

NANO=1_000_000_000
CAP=NANO
DEFAULT_PRICING=Path(__file__).resolve().parents[1]/'config/ai-pricing.json'
DEFAULT_LEDGER=Path(__file__).resolve().parents[1]/'var/ai-budget/usage.sqlite3'
class BudgetError(ModelUnavailable):pass

def token_int(value):
    if type(value) is not int or value<0:raise BudgetError('AI usage could not be verified. Its reservation remains held.')
    return value

class DailyBudget:
    def __init__(self,path=DEFAULT_LEDGER,pricing_path=DEFAULT_PRICING,clock=time.time):
        self.path=Path(path);self.clock=clock;self.rates=json.loads(Path(pricing_path).read_text())
        # This reviewed local authorization cannot be enlarged by an environment variable or API input.
        if self.rates.get('daily_cap_nano_usd')!=CAP or self.rates.get('reset_timezone')!='UTC':raise BudgetError('AI budget configuration is not the approved $1 UTC-day policy.')
        self.path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        if self.path.parent.stat().st_mode&0o077 or self.path.is_symlink():raise BudgetError('AI ledger requires a private directory and regular database.')
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS ai_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS ai_charges(id TEXT PRIMARY KEY, day TEXT NOT NULL, finished_day TEXT, reserved INTEGER NOT NULL, charged INTEGER NOT NULL, measured INTEGER, status TEXT NOT NULL, input_bound INTEGER NOT NULL, output_bound INTEGER NOT NULL, input_tokens INTEGER, cached_tokens INTEGER, output_tokens INTEGER)')
        os.chmod(self.path,0o600)
    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=10)
        try:
            db.execute('PRAGMA journal_mode=DELETE');db.execute('PRAGMA synchronous=FULL');db.execute('BEGIN IMMEDIATE')
            yield db;db.commit()
        except BaseException:db.rollback();raise
        finally:db.close()
    def day(self):return datetime.fromtimestamp(self.clock(),timezone.utc).date().isoformat()
    def check_rates(self,model):
        r=self.rates;now=datetime.fromtimestamp(self.clock(),timezone.utc)
        try:checked=datetime.fromisoformat(r['verified_at'].replace('Z','+00:00'));until=datetime.fromisoformat(r['valid_until'].replace('Z','+00:00'))
        except (KeyError,ValueError,TypeError):raise BudgetError('AI pricing needs review. Manual guidance remains available.') from None
        if model!='gpt-5.4' or r.get('model')!=model or r.get('service_tier')!='default' or not checked<=now<until or until-checked>timedelta(days=7) or r.get('input_nano_usd_per_token')!=2500 or r.get('cached_nano_usd_per_token')!=250 or r.get('output_nano_usd_per_token')!=15000 or r.get('max_input_tokens')!=8000 or r.get('max_output_tokens')!=900:
            raise BudgetError('AI pricing is unknown or its review expired. Manual guidance remains available.')
    def _clock(self,db,day):
        row=db.execute("SELECT value FROM ai_meta WHERE key='latest_day'").fetchone()
        if row and row[0]>day:raise BudgetError('AI budget clock moved backward. Paid requests are paused.')
        db.execute("INSERT INTO ai_meta VALUES('latest_day',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(day,))
    def _amounts(self,db,day):
        # Uncertain/in-flight charges carry across midnight. Late completions also count on completion day.
        rows=db.execute("SELECT charged,measured,status FROM ai_charges WHERE day=? OR (day<? AND (status IN ('reserved','uncertain') OR finished_day=?))",(day,day,day)).fetchall()
        return sum(x[0] for x in rows),sum(x[1] or 0 for x in rows),sum(x[0] for x in rows if x[2] in {'reserved','uncertain'}),len(rows)
    def summary(self,model='gpt-5.4'):
        day=self.day();reason='';ready=True
        try:
            self.check_rates(model)
            with self.db() as db:
                self._clock(db,day);total,measured,held,count=self._amounts(db,day);blocked=db.execute("SELECT value FROM ai_meta WHERE key='blocked'").fetchone()
                if blocked:reason='AI usage needs reconciliation. Paid requests are paused.';ready=False
        except (BudgetError,sqlite3.Error,OSError):
            ready=False;reason='AI pricing or the persistent budget could not be verified. Paid requests are paused.'
            try:
                with self.db() as db:total,measured,held,count=self._amounts(db,day)
            except Exception:total=CAP;measured=0;held=CAP;count=0
        remaining=max(0,CAP-total)
        if ready and remaining<900*15000:ready=False;reason='The shared daily AI allowance is used. Manual guidance remains available until 00:00 UTC.'
        return {'day':day,'timezone':'UTC','resetAt':(datetime.fromisoformat(day).replace(tzinfo=timezone.utc)+timedelta(days=1)).isoformat(),'dailyLimitUsd':1,'estimatedUsd':measured/NANO,'reservedOrUncertainUsd':held/NANO,'accountedUsd':total/NANO,'remainingUsd':remaining/NANO,'requestCount':count,'canRequest':ready,'reason':reason,'pricingVerifiedAt':self.rates['verified_at'],'pricingValidUntil':self.rates['valid_until'],'label':'USD estimates from measured tokens; held amounts include requests without final usage. Not an invoice.'}
    def reserve(self,input_tokens,output_tokens,model):
        self.check_rates(model);i=token_int(input_tokens);o=token_int(output_tokens)
        if not 1<=i<=8000 or o!=900:raise BudgetError('AI request exceeds the reviewed token limits. Use a shorter question or manual guidance.')
        amount=i*2500+o*15000;key=secrets.token_hex(24);day=self.day()
        try:
            with self.db() as db:
                self._clock(db,day)
                if db.execute("SELECT value FROM ai_meta WHERE key='blocked'").fetchone():raise BudgetError('AI usage needs reconciliation. Manual guidance remains available.')
                total,*_=self._amounts(db,day)
                if total+amount>CAP:raise BudgetError('This request could exceed the shared $1 daily AI limit. Try after 00:00 UTC or use manual guidance.')
                db.execute('INSERT INTO ai_charges VALUES(?,?,NULL,?,?,NULL,?,?,?,NULL,NULL,NULL)',(key,day,amount,amount,'reserved',i,o))
            return key
        except sqlite3.Error:raise BudgetError('The persistent AI budget is unavailable. No paid request was started.') from None
    def settle(self,key,response):
        valid=False;i=c=o=cost=0
        try:
            u=response['usage'];i=token_int(u['input_tokens']);o=token_int(u['output_tokens']);c=token_int(u['input_tokens_details']['cached_tokens']);w=token_int(u['input_tokens_details'].get('cache_write_tokens',0))
            valid=response.get('status')=='completed' and response.get('model') in self.rates['response_models'] and response.get('service_tier')=='default' and w==0 and c<=i and token_int(u['total_tokens'])==i+o
            cost=(i-c)*2500+c*250+o*15000
        except (KeyError,TypeError,BudgetError):pass
        with self.db() as db:
            row=db.execute('SELECT reserved,status,input_bound,output_bound FROM ai_charges WHERE id=?',(key,)).fetchone()
            if not row:raise BudgetError('AI reservation could not be found. Paid requests are paused.')
            if row[1]=='settled':return
            valid=valid and i<=row[2] and o<=row[3] and cost<=row[0]
            if valid:db.execute("UPDATE ai_charges SET status='settled',finished_day=?,charged=?,measured=?,input_tokens=?,cached_tokens=?,output_tokens=? WHERE id=?",(self.day(),cost,cost,i,c,o,key))
            else:
                db.execute("UPDATE ai_charges SET status='uncertain' WHERE id=?",(key,));db.execute("INSERT OR REPLACE INTO ai_meta VALUES('blocked','unverified usage')")
        if not valid:raise BudgetError('AI returned unverified usage. Its maximum reservation remains held and paid requests are paused.')
    def uncertain(self,key):
        # Network failures, cancellation and process death never refund a possibly submitted request.
        with self.db() as db:db.execute("UPDATE ai_charges SET status='uncertain' WHERE id=? AND status='reserved'",(key,))
    def seed(self,entries):
        """Idempotent audited historic token usage only; no user text/identifiers."""
        with self.db() as db:
            for entry in entries:
                key,day,i,c,o=entry;i=token_int(i);c=token_int(c);o=token_int(o)
                if c>i:raise BudgetError('Invalid historical usage.')
                amount=(i-c)*2500+c*250+o*15000
                old=db.execute('SELECT day,charged,input_tokens,cached_tokens,output_tokens FROM ai_charges WHERE id=?',(key,)).fetchone()
                if old and old!=(day,amount,i,c,o):raise BudgetError('Historical usage changed; reconciliation required.')
                db.execute("INSERT OR IGNORE INTO ai_charges VALUES(?,?,?,?,?,?,'settled',?,?,?,?,?)",(key,day,day,amount,amount,amount,i,o,i,c,o))

def count_input_tokens(client,payload):
    """Exact provider count, same input/instructions/tools/schema; no retry and no generation."""
    body={k:payload[k] for k in ['model','instructions','input','tools','text']}
    try:
        request=Request('https://api.openai.com/v1/responses/input_tokens',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+client.key,'Content-Type':'application/json'},method='POST')
        with urlopen(request,timeout=15) as response:raw=response.read(10001)
        if len(raw)>10000:raise BudgetError('AI token count exceeded its bound.')
        count=json.loads(raw)
        if count.get('object')!='response.input_tokens':raise BudgetError('AI input token count is unavailable.')
        return token_int(count.get('input_tokens'))
    except (HTTPError,URLError,TimeoutError,ValueError,KeyError,TypeError):raise BudgetError('AI input token count could not be verified. No paid generation was started; manual guidance remains available.') from None
