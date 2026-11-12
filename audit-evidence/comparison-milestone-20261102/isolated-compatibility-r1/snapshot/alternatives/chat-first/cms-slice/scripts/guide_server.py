#!/usr/bin/env python3
"""Daylight guide/profile/agent service, independent of gated plan integrations.
Local development only by default. No transcript logger and no research-mode bypass.
"""
import argparse
from collections import defaultdict,deque
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlsplit
from chat import ResponsesClient,ModelUnavailable
from guest_profiles import GuestProfiles,ProfileError
from guide_agent import GuideAgent
from readiness_profiles import ReadinessProfiles
from readiness_agent import ReadinessAgent
from readiness_conversation import ReadinessConversation
from ai_budget import DailyBudget,DEFAULT_LEDGER
from runtime_env import load_model_env

ROOT=Path(__file__).resolve().parents[1];WEB=ROOT/'apps/chat'

def make_server(port=8890,*,database=None,client=None,enable_live=False,retention_days=7,public_origin=None,production=False,web=WEB,live_limit=6,test_cookie_namespace=None,budget_database=None,count_tokens=None,cookie_namespace=None,ui_config=None,conversation_class=ReadinessConversation,allow_microphone=False,profile_gate_class=None,adaptive_class=None):
    web=Path(web);contract=json.loads((web/'guide-contract.json').read_text());facts=json.loads((web/'teaching-facts.json').read_text());samples=json.loads((web/'sample-plans.json').read_text())
    if production and (not public_origin or not public_origin.startswith('https://')):raise ValueError('Production requires an explicit HTTPS origin and a reviewed deployment.')
    if live_limit is not None and not 1<=live_limit<=6:raise ValueError('An optional run request limit may only tighten the daily cap.')
    budget=DailyBudget(budget_database or DEFAULT_LEDGER) if enable_live or budget_database else None
    if budget:budget.seed([('approved-smoke-20261021-1','2026-10-21',2649,0,97),('approved-smoke-20261021-2','2026-10-21',2547,0,65),('approved-smoke-20261021-3','2026-10-21',2587,0,96)])
    profiles=GuestProfiles(database or ROOT/'var/guest-profiles/guides.sqlite3',contract,retention_days)
    agent=GuideAgent(contract,facts,client,enable_live,live_limit,budget=budget,count_tokens=count_tokens);readiness=ReadinessProfiles(profiles) if (web/'readiness-content.json').is_file() else None;readiness_content=json.loads((web/'readiness-content.json').read_text()) if readiness else None;readiness_agent=ReadinessAgent(contract,facts,readiness_content,client=agent.client,enabled=enable_live,max_calls=live_limit,budget=budget,count_tokens=count_tokens) if readiness else None;conversation=conversation_class(contract,facts,readiness_content,client=agent.client,enabled=enable_live,max_calls=live_limit,budget=budget,count_tokens=count_tokens) if readiness else None;slots=threading.BoundedSemaphore(2);arrivals=defaultdict(deque);rate_lock=threading.Lock();cookie_name='__Host-daylight_guest' if production else 'daylight_guest_dev'
    profile_gate=profile_gate_class(profiles,readiness,contract,readiness_content,samples) if profile_gate_class else None
    adaptive=adaptive_class(profiles,readiness,contract,facts,readiness_content,agent.client,enable_live,budget,count_tokens,fixture=bool((ui_config or {}).get('mockAI'))) if adaptive_class else None
    if cookie_namespace is not None:
        if production or test_cookie_namespace is not None or not re.fullmatch(r'daylight_[a-z0-9_]{1,40}',cookie_namespace):raise ValueError('A separate cookie namespace is for local development only.')
        cookie_name=cookie_namespace
    if production and ui_config is not None:raise ValueError('UI test configuration is local-development-only.')
    if test_cookie_namespace is not None:
        if production or not re.fullmatch(r'daylight_test_[a-z0-9_]{1,30}',test_cookie_namespace):raise ValueError('Test cookie namespace is local-development-only.')
        cookie_name=test_cookie_namespace
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass # Neither submitted text nor profile identifiers are logged.
        def setup(self):super().setup();self.connection.settimeout(45)
        def origin(self):return public_origin or 'http://'+self.headers.get('Host','')
        def safe(self):
            host=self.headers.get('Host','');allowed={urlsplit(public_origin).netloc} if public_origin else {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
            if self.command=='GET' and not self.path.startswith('/api/'):return host in allowed
            return host in allowed and self.headers.get('Origin',self.origin())==self.origin() and self.headers.get('Sec-Fetch-Site','same-origin') not in {'cross-site'}
        def token(self):
            raw=self.headers.get('Cookie','')
            if raw.count(cookie_name+'=')>1:raise ProfileError('Ambiguous guest cookie.',401)
            c=SimpleCookie()
            try:c.load(raw)
            except Exception:raise ProfileError('Invalid guest cookie.',401) from None
            return c[cookie_name].value if cookie_name in c else None
        def headers_for(self,code,mime,length=None,cookie=None):
            self.send_response(code)
            headers={'Content-Type':mime,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",'Permissions-Policy':('camera=(), microphone=(self), geolocation=()' if allow_microphone else 'camera=(), microphone=(), geolocation=()')}
            if length is not None:headers['Content-Length']=str(length)
            else:headers['Connection']='close'
            if cookie is not None:headers['Set-Cookie']=cookie
            for k,v in headers.items():self.send_header(k,v)
            self.end_headers()
        def respond(self,code,value,mime='application/json; charset=utf-8',cookie=None):
            raw=value if isinstance(value,bytes) else json.dumps(value,ensure_ascii=False).encode();self.headers_for(code,mime,len(raw),cookie);self.wfile.write(raw)
        def body(self):
            if self.headers.get('Transfer-Encoding') or self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ProfileError('Use a bounded JSON request.',415)
            try:size=int(self.headers.get('Content-Length','0'))
            except ValueError:raise ProfileError('Invalid body length.') from None
            if not 1<=size<=80000:raise ProfileError('Request is too large.',413)
            try:value=json.loads(self.rfile.read(size))
            except (ValueError,UnicodeError):raise ProfileError('Invalid JSON.') from None
            if not isinstance(value,dict):raise ProfileError('Use a JSON object.')
            return value
        def csrf(self):
            value=self.headers.get('X-Daylight-CSRF','');profiles.require(self.token(),value);return value
        def do_GET(self):
            try:
                if not self.safe():return self.respond(403,{'error':'Request origin rejected.'})
                url=urlsplit(self.path)
                if url.query:return self.respond(422,{'error':'Do not put guide details or tokens in URLs.'})
                path=url.path
                if path=='/ten-config.json' and ui_config is not None:return self.respond(200,ui_config)
                if path in {'/api/status','/api/ai/usage'}:
                    usage=budget.summary(agent.client.model) if budget else None
                    if path=='/api/ai/usage':return self.respond(200,{'enabled':agent.enabled and agent.client.available,'budget':usage})
                    available=agent.enabled and agent.client.available and bool(usage and usage['canRequest'])
                    return self.respond(200,{'consumer_ready':False,'plan_validation_status':'pending','catalog_count':0,'agent_available':available,'live_conversation_available':available,'model_configured':agent.client.available,'model_id':agent.client.model if agent.client.available else None,'provider':'OpenAI','conversation_logging':False,'guest_profiles':True,'sample_count':len(samples['plans']),'live_requests_remaining':max(0,agent.max_calls-agent.calls) if agent.max_calls is not None else None,'ai_budget':usage,'automatic_retries':False})
                if path=='/api/conversation/initial' and adaptive:
                    profiles.require(self.token());g,r=adaptive.initial();return self.respond(200,{'guide':g,'record':r,'assessment':adaptive.assess(g,r)})
                if path=='/api/guest/session':
                    token,info,new=profiles.session(self.token());cookie=f'{cookie_name}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={retention_days*86400}'+('; Secure' if production else '') if new else None
                    return self.respond(200,info,cookie=cookie)
                if path=='/api/profile/readiness' and profile_gate:return self.respond(200,profile_gate.assess_saved(self.token()))
                if path=='/api/recommendations' and profile_gate:
                    assessment=profile_gate.assess_saved(self.token())['assessment'];return self.respond(409 if not assessment['intakeInformationReady'] else 503,{'error':'Personalized recommendations remain held.','assessment':assessment})
                if path=='/api/guest/readiness' and readiness:return self.respond(200,readiness.get(self.token()))
                if path=='/api/guest/profile':return self.respond(200,profiles.get(self.token()))
                if path=='/api/sample-plans':return self.respond(200,samples)
                if path.startswith('/api/'):return self.respond(503,{'error':'Personalized plan comparisons and verification are held for validated data integration.','validation_status':'pending'})
                relative='index.html' if path=='/' else path.lstrip('/');target=(web/relative).resolve()
                if not target.is_relative_to(web.resolve()) or target.suffix not in {'.html','.js','.css','.json','.svg','.jpg','.woff2'} or any(p.startswith('.') for p in Path(relative).parts) or not target.is_file():return self.respond(404,{'error':'No such resource.'})
                mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml','.jpg':'image/jpeg','.woff2':'font/woff2'}[target.suffix]
                return self.respond(200,target.read_bytes(),mime)
            except ProfileError as e:return self.respond(e.code,{'error':str(e)})
            except (BrokenPipeError,ConnectionResetError):return
        def do_POST(self):self.mutate()
        def do_PUT(self):self.mutate()
        def do_DELETE(self):self.mutate()
        def mutate(self):
            streaming=False
            try:
                if not self.safe():return self.respond(403,{'error':'Request origin rejected.'})
                if '?' in self.path:return self.respond(422,{'error':'Guide URLs cannot contain private parameters.'})
                if self.path not in (({'/api/conversation/turn','/api/conversation/save'} if adaptive else set())|{'/api/guest/profile','/api/agent','/api/agent/confirm'}|({'/api/guest/readiness','/api/readiness/interpret','/api/readiness/confirm','/api/readiness/conversation'} if readiness else set())|({'/api/profile/readiness','/api/recommendations'} if profile_gate else set())):return self.respond(503,{'error':'Personalized comparisons remain unavailable pending validated integration.','validation_status':'pending'})
                csrf=self.csrf();token=self.token();owner=profiles.digest(token);payload=self.body()
                if self.path in {'/api/conversation/turn','/api/conversation/save'} and adaptive:
                    if self.command!='POST':raise ProfileError('Use POST for conversation actions.',405)
                    if self.path.endswith('/save'):return self.respond(200,adaptive.save(token,csrf,payload))
                    if (payload.get('action') or {}).get('type')=='message':
                        with rate_lock:
                            q=arrivals[owner];now=time.monotonic()
                            while q and q[0]<now-60:q.popleft()
                            if len(q)>=8:raise ProfileError('Please wait a moment before sending again.',429)
                            q.append(now)
                    if not slots.acquire(blocking=False):raise ProfileError('Daylight is busy. Your message and reports are preserved.',429)
                    try:return self.respond(200,adaptive.turn(owner,payload))
                    finally:slots.release()
                if self.path in {'/api/profile/readiness','/api/recommendations'} and profile_gate:
                    if self.command!='POST' or set(payload)-{'requestedCapabilities'}!={'guide','record'}:raise ProfileError('Use the current reported profile and existing comparison capabilities.')
                    assessment=profile_gate.assess(payload['guide'],payload['record'],payload.get('requestedCapabilities'))
                    if self.path=='/api/recommendations':return self.respond(409 if not assessment['intakeInformationReady'] else 503,{'error':'Personalized recommendations remain held.','assessment':assessment})
                    return self.respond(200,assessment)
                if self.path=='/api/guest/readiness':
                    if self.command=='PUT' and set(payload)=={'record','expectedVersion','operationId'}:
                        if profile_gate:profile_gate.validate_inputs(profiles.get(token)['guide'],payload['record'])
                        return self.respond(200,readiness.save(token,csrf,payload['expectedVersion'],payload['operationId'],payload['record']))
                    raise ProfileError('Unsupported readiness action.')
                if self.path=='/api/guest/profile':
                    if self.command=='PUT' and set(payload)=={'expectedVersion','operationId','guide'}:
                        if profile_gate:
                            from profile_readiness import reject_sensitive
                            reject_sensitive(payload['guide'].get('fields',{}))
                        receipt=profiles.save(token,csrf,payload['expectedVersion'],payload['operationId'],payload['guide'])
                        if readiness:receipt['readinessVersion']=readiness.apply_preferences(token)
                        return self.respond(200,receipt)
                    if self.command=='DELETE' and set(payload)=={'expectedVersion','confirmed'} and payload['confirmed'] is True:return self.respond(200,profiles.delete(token,csrf,payload['expectedVersion']),cookie=f'{cookie_name}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0'+('; Secure' if production else ''))
                    raise ProfileError('Unsupported profile action.')
                if self.command!='POST':raise ProfileError('Use POST for this action.',405)
                if self.path=='/api/readiness/conversation':
                    if set(payload)!={'message','guide','context','requestId','aiConsent'}or payload['aiConsent']is not True or not re.fullmatch(r'[a-zA-Z0-9-]{10,80}',str(payload.get('requestId',''))):raise ProfileError('Confirm transfer and use the current conversation request.')
                    if profile_gate:
                        from profile_readiness import reject_sensitive
                        reject_sensitive(payload['message'])
                    with rate_lock:
                        q=arrivals[owner];now=time.monotonic()
                        while q and q[0]<now-60:q.popleft()
                        if len(q)>=8:raise ProfileError('Please wait a moment before sending again.',429)
                        q.append(now)
                    if not slots.acquire(blocking=False):raise ProfileError('Daylight is busy. You can see plans now.',429)
                    try:return self.respond(200,conversation.converse(owner,payload['message'],payload['guide'],payload['context'],payload['requestId']))
                    finally:slots.release()
                if self.path=='/api/readiness/confirm':
                    if set(payload)!={'proposalId','expectedStateVersion','expectedReadinessRevision'}:raise ProfileError('Unsupported readiness confirmation.')
                    with readiness_agent.lock:proposal=readiness_agent.pending.get(payload['proposalId'])
                    if not proposal or proposal.get('readinessRevision')!=payload['expectedReadinessRevision']:raise ProfileError('Readiness changed. Review a new interpretation.',409)
                    return self.respond(200,readiness_agent.confirm(owner,payload['proposalId'],payload['expectedStateVersion']))
                if self.path=='/api/readiness/interpret':
                    if set(payload)!={'message','guide','triggerId','recordRevision','requestId','aiConsent'} or payload['aiConsent']is not True or payload['triggerId']not in readiness_agent.details or type(payload['recordRevision'])is not int or payload['recordRevision']<0 or not re.fullmatch(r'[a-zA-Z0-9-]{10,80}',str(payload.get('requestId',''))):raise ProfileError('Use the current readiness request contract.')
                    with rate_lock:
                        q=arrivals[owner];now=time.monotonic()
                        while q and q[0]<now-60:q.popleft()
                        if len(q)>=8:raise ProfileError('Please wait a moment before asking again.',429)
                        q.append(now)
                    if not slots.acquire(blocking=False):raise ProfileError('Daylight is busy. Your reports are unchanged.',429)
                    try:
                        result=readiness_agent.run(owner,payload['message'],payload['guide'],[payload['triggerId']],payload['requestId'])
                        result['expectedReadinessRevision']=payload['recordRevision'];result['triggerId']=payload['triggerId']
                        if result.get('proposalId'):
                            with readiness_agent.lock:readiness_agent.pending[result['proposalId']]['readinessRevision']=payload['recordRevision']
                        return self.respond(200,result)
                    finally:slots.release()
                if self.path=='/api/agent/confirm':
                    if set(payload)!={'proposalId','expectedStateVersion'}:raise ProfileError('Unsupported confirmation.')
                    return self.respond(200,agent.confirm(owner,payload['proposalId'],payload['expectedStateVersion']))
                if set(payload)!={'message','guide','eligible','requestId','aiConsent'} or payload['aiConsent'] is not True or not re.fullmatch(r'[a-zA-Z0-9-]{10,80}',str(payload.get('requestId',''))) or not isinstance(payload['eligible'],list) or any(not isinstance(x,str) for x in payload['eligible']):raise ProfileError('Confirm AI transfer and use the current guide request contract.')
                with rate_lock:
                    q=arrivals[owner];now=time.monotonic()
                    while q and q[0]<now-60:q.popleft()
                    if len(q)>=8:raise ProfileError('Please wait a moment before asking again.',429)
                    q.append(now)
                if not slots.acquire(blocking=False):raise ProfileError('Daylight is busy. Your guide is unchanged; retry shortly.',429)
                try:
                    if 'text/event-stream' not in self.headers.get('Accept',''):return self.respond(200,agent.run(owner,payload['message'],payload['guide'],payload['eligible'],payload['requestId']))
                    self.headers_for(200,'text/event-stream; charset=utf-8');streaming=True;self.close_connection=True
                    def emit(kind,data):self.wfile.write(('event: '+kind+'\ndata: '+json.dumps(data,ensure_ascii=False)+'\n\n').encode());self.wfile.flush()
                    emit('status',{'message':'Request received. Your guide has not changed.'});answer=agent.run(owner,payload['message'],payload['guide'],payload['eligible'],payload['requestId'],emit);emit('complete',answer)
                finally:slots.release()
            except (ProfileError,ModelUnavailable) as e:
                if streaming:
                    try:self.wfile.write(('event: error\ndata: '+json.dumps({'error':str(e),'code':getattr(e,'code',503)})+'\n\n').encode());self.wfile.flush()
                    except (BrokenPipeError,ConnectionResetError):pass
                else:self.respond(getattr(e,'code',503),{'error':str(e)})
            except (BrokenPipeError,ConnectionResetError):return
            except Exception:
                if not streaming:return self.respond(500,{'error':'The service could not complete this request. Your guide is unchanged.'})
    maintenance_stop=threading.Event()
    class Server(ThreadingHTTPServer):
        def server_close(self):maintenance_stop.set();super().server_close()
    server=Server(('127.0.0.1',port),Handler);server.profiles=profiles;server.agent=agent;server.budget=budget;server.readiness=readiness;server.readiness_agent=readiness_agent;server.readiness_conversation=conversation;server.profile_gate=profile_gate;server.adaptive=adaptive
    def maintain():
        while not maintenance_stop.wait(60):
            try:profiles.purge_expired()
            except Exception:pass # No private exception bodies or identifiers in logs.
    threading.Thread(target=maintain,daemon=True).start()
    return server

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',type=int,default=8890);p.add_argument('--database',type=Path);p.add_argument('--model-env',type=Path);p.add_argument('--enable-live',action='store_true');p.add_argument('--retention-days',type=int,default=7);p.add_argument('--live-request-limit',type=int,default=None);a=p.parse_args()
    if a.model_env:load_model_env(a.model_env)
    server=make_server(a.port,database=a.database,enable_live=a.enable_live,retention_days=a.retention_days,live_limit=a.live_request_limit)
    print(f'Daylight guide at http://127.0.0.1:{server.server_port}/; profiles enabled; live={server.agent.enabled and server.agent.client.available}; plan comparisons held; no chat logging',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
if __name__=='__main__':main()
