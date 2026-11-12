"""Bounded synthetic ALT73 integration checks. No real guest records or paid AI requests."""
import copy,http.client,json,subprocess,sys,tempfile,threading,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from guide_server import make_server
from chat_server import build,SHARED_BUDGET,ORIGINAL
from chat_conversation import ChatConversation
from chat import ResponsesClient,ModelUnavailable
from guest_profiles import ProfileError
from ai_budget import DailyBudget
WEB=ROOT/'apps/chat-alternative';CONTRACT=json.loads((WEB/'guide-contract.json').read_text());FACTS=json.loads((WEB/'teaching-facts.json').read_text());CONTENT=json.loads((WEB/'readiness-content.json').read_text())
def state():return json.loads(subprocess.check_output(['node',str(ROOT/'tests/test_chat_alternative_core.js'),'--fixture'],text=True))
def response(**changes):return {'reflection':'Thanks. I have those reports.','intent':'answer','confirmation':'not_requested','clarifying_question':'','fact_ids':[],'requests':[],'reports':[],'baseline_reports':[],**changes}
def baseline(id,value='',**changes):return {'id':id,'value':value,'values':[],'certainty':'explicit','quote':'Find coverage','zip':'','countyFips':'','month':'','text':'','details':'','pharmacy':'','other':'',**changes}
def context(**changes):return {'triggerId':'RC01','baselineId':'T01','recordRevision':0,'eligibleIds':['RC01'],'protectedIds':[],'pendingProposalId':None,'questionVariant':'standard','knownReports':{},'currentEntity':'profile','detailsRequested':True,**changes}
def blank():
 g=state()['guide'];g['fields']={};g['stateVersion']=0;return g
class ModelContract(unittest.TestCase):
 def agent(self,value):
  self.seen=[]
  def transport(payload):self.seen.append(payload);return {'output':[{'content':[{'type':'output_text','text':json.dumps(value)}]}]}
  return ChatConversation(CONTRACT,FACTS,CONTENT,client=ResponsesClient(key='synthetic',model='gpt-5.4',transport=transport),enabled=True,max_calls=3)
 def test_all_baseline_and_readiness_definitions_share_one_bounded_mock_request(self):
  message='Find coverage. New to Medicare. ZIP 34102. For myself.'
  value=response(baseline_reports=[baseline('T01','compare'),baseline('T02','new',quote='New to Medicare'),baseline('T03',quote='34102',zip='34102')],reports=[{'triggerId':'RC01','choice':'self','quote':'myself','certainty':'explicit','details':[]}]);a=self.agent(value);g=blank();old=copy.deepcopy(g);out=a.converse('synthetic',message,g,context(),'synthetic-chat-turn-001')
  self.assertEqual(g,old);self.assertEqual(len(out['baselineReports']),3);self.assertEqual(out['reports'][0]['value']['choice'],'self');p=self.seen[0];self.assertLess(len(json.dumps(p).encode()),24000);ctx=json.loads(p['input'][0]['content'])['confirmed_context'];self.assertEqual(len(ctx['baselineDefinitions']),10);self.assertEqual(len(ctx['readiness']['details']),28);self.assertEqual(p['tools'],[]);self.assertFalse(p['store']);self.assertEqual(a.calls,1)
 def test_untraceable_names_and_unconfirmed_date_invention_are_rejected(self):
  for b in [baseline('T06','list',text='Unmentioned Doctor'),baseline('T04','month',month='2027-01')]:
   a=self.agent(response(baseline_reports=[b]))
   with self.assertRaises(ModelUnavailable):a.converse('synthetic','Find coverage',blank(),context(),'synthetic-chat-turn-002')
 def test_lists_keep_all_entries_in_single_report(self):
  text='ExampleOne 5 mg tablet; ExampleTwo 10 mg capsule';a=self.agent(response(baseline_reports=[baseline('T07','yes',quote=text,text=text)]));out=a.converse('synthetic',text,blank(),context(),'synthetic-chat-turn-003');self.assertEqual(out['baselineReports'][0]['data']['text'],text)
class HttpContract(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();base=Path(self.tmp.name);self.current=make_server(0,web=ROOT/'apps/ten-question',database=base/'current/g.db',cookie_namespace='daylight_test_current',budget_database=base/'budget/usage.db');self.alt=make_server(0,web=WEB,database=base/'alternative/g.db',cookie_namespace='daylight_chat_alt_fixture',budget_database=base/'budget/usage.db',conversation_class=ChatConversation,ui_config={'mockAI':True},allow_microphone=True);self.servers=[self.current,self.alt]
  self.threads=[threading.Thread(target=s.serve_forever,daemon=True)for s in self.servers]
  for t in self.threads:t.start()
 def tearDown(self):
  for s in self.servers:s.shutdown();s.server_close()
  for t in self.threads:t.join()
  self.tmp.cleanup()
 def req(self,s,path,method='GET',body=None,cookie=None,csrf=None):
  c=http.client.HTTPConnection('127.0.0.1',s.server_port);h={}
  if cookie:h['Cookie']=cookie
  if csrf:h['X-Daylight-CSRF']=csrf
  if body is not None:h['Content-Type']='application/json'
  c.request(method,path,json.dumps(body)if body is not None else None,h);r=c.getresponse();raw=r.read();headers=dict(r.getheaders());c.close();return r.status,json.loads(raw)if headers.get('Content-Type','').startswith('application/json')else raw,headers
 def test_cookie_ownership_profile_save_resume_and_progress_map(self):
  _,s,h=self.req(self.alt,'/api/guest/session');cookie=h['Set-Cookie'].split(';')[0];self.assertTrue(cookie.startswith('daylight_chat_alt_fixture='));fixture=state()
  code,receipt,_=self.req(self.alt,'/api/guest/profile','PUT',{'guide':fixture['guide'],'expectedVersion':0,'operationId':'synthetic-alt-save-001'},cookie,s['csrf']);self.assertEqual(code,200,receipt)
  code,receipt,_=self.req(self.alt,'/api/guest/readiness','PUT',{'record':fixture['record'],'expectedVersion':0,'operationId':'synthetic-alt-save-002'},cookie,s['csrf']);self.assertEqual(code,200,receipt)
  _,restored,_=self.req(self.alt,'/api/guest/profile',cookie=cookie);self.assertIn('ExampleTwo',restored['guide']['fields']['needs.medications']['value']);_,r,_=self.req(self.alt,'/api/guest/readiness',cookie=cookie);self.assertEqual(len(r['record']['completeness']['baselineChecks']),10);self.assertNotIn('messages',r['record']);self.assertEqual(r['record']['completeness']['checks']['RC20']['evidence'],'not_verified')
  code,_,_=self.req(self.current,'/api/guest/profile',cookie=cookie);self.assertEqual(code,401)
  _,cur,curh=self.req(self.current,'/api/guest/session',cookie=cookie);self.assertFalse(cur['hasSaved']);curcookie=curh['Set-Cookie'].split(';')[0];code,_,_=self.req(self.alt,'/api/guest/profile',cookie=curcookie);self.assertEqual(code,401)
  code,_,_=self.req(self.alt,'/api/guest/profile','PUT',{'guide':fixture['guide'],'expectedVersion':0,'operationId':'synthetic-alt-save-003'},cookie,s['csrf']);self.assertEqual(code,409)
 def test_same_budget_reservations_and_plan_gate_and_mic_policy(self):
  self.assertEqual(self.alt.budget.path,self.current.budget.path);key=self.alt.budget.reserve(1000,900,'gpt-5.4');self.assertEqual(self.alt.budget.summary()['accountedUsd'],self.current.budget.summary()['accountedUsd']);self.assertGreater(self.current.budget.summary()['reservedOrUncertainUsd'],0);self.current.budget.uncertain(key);self.assertEqual(self.alt.budget.summary()['reservedOrUncertainUsd'],self.current.budget.summary()['reservedOrUncertainUsd'])
  code,plans,h=self.req(self.alt,'/api/sample-plans');self.assertEqual(code,200);self.assertEqual(len(plans['plans']),5);self.assertTrue(plans['not_recommendation']);self.assertIn('microphone=(self)',h['Permissions-Policy']);code,_,_=self.req(self.alt,'/api/compare');self.assertEqual(code,503)
 def test_no_automatic_copy_of_original_storage_or_port(self):
  self.assertEqual(SHARED_BUDGET,ORIGINAL/'cms-slice/var/ai-budget/usage.sqlite3');self.assertFalse(self.alt.profiles.path.is_relative_to(ORIGINAL))
  with self.assertRaises(ValueError):build(8890,fixture=True)
if __name__=='__main__':unittest.main()
