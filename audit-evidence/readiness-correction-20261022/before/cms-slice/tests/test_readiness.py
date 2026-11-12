"""Synthetic readiness companion/API tests. No real guest data or external model calls."""
import copy,http.client,json,sys,tempfile,threading,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from guest_profiles import GuestProfiles,ProfileError
from readiness_profiles import ReadinessProfiles,VERSION,validate
from readiness_agent import ReadinessAgent
from guide_server import make_server
from chat import ResponsesClient
WEB=ROOT/'apps/ten-question';CONTRACT=json.loads((WEB/'guide-contract.json').read_text());FACTS=json.loads((WEB/'teaching-facts.json').read_text());CONTENT=json.loads((WEB/'readiness-content.json').read_text())
def guide(sensitive=True):return {'schemaVersion':2,'stateVersion':1,'fields':{},'flow':{'node':'R10','history':[],'queue':[],'lessonReturn':None,'personalReview':False,'guideOpen':True,'origin':'T01','invalidations':[],'scroll':0},'topics':{},'preferences':{'saveGuide':True,'saveSensitive':sensitive,'noticeVersion':'guest-notice-2026-10-21-v1'}}
def record():return {'schemaVersion':1,'ruleVersion':VERSION,'stateVersion':1,'guideFingerprint':'{}','facts':{'RC09':{'value':{'choice':'spouse_job'},'confirmation':'confirmed_by_user','source':'user_choice','revision':1,'stale':False}},'dispositions':{'RC09':{'state':'resolved_report','automaticReopen':False},'RC04':{'state':'deferred','automaticReopen':False}},'queue':['RC09'],'index':1,'shown':['RC09'],'pass':1,'history':[],'mode':'summary','editNotice':False}
class PersistenceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.p=GuestProfiles(Path(self.tmp.name)/'private/g.db',CONTRACT);self.r=ReadinessProfiles(self.p);self.token,self.info,_=self.p.session();self.p.save(self.token,self.info['csrf'],0,'save-guide-00001',guide())
 def tearDown(self):self.tmp.cleanup()
 def save(self,data=None,version=0,op='save-readiness-00001'):return self.r.save(self.token,self.info['csrf'],version,op,data or record())
 def test_roundtrip_restart_and_original_guide_unchanged(self):
  before=self.p.get(self.token)['guide'];self.save();r=ReadinessProfiles(GuestProfiles(self.p.path,CONTRACT));self.assertEqual(r.get(self.token)['record'],record());self.assertEqual(self.p.get(self.token)['guide'],before)
 def test_other_guest_and_csrf_cannot_access_or_write(self):
  self.save();other,info,_=self.p.session();self.assertIsNone(self.r.get(other)['record'])
  with self.assertRaises(ProfileError):self.r.save(self.token,info['csrf'],1,'wrong-owner-00001',record())
 def test_optout_strips_fact_values_retains_unknown_dispositions(self):
  self.p.save(self.token,self.info['csrf'],1,'save-optout-00001',guide(False));self.save();data=self.r.get(self.token)['record'];self.assertEqual(data['facts'],{});self.assertEqual(data['dispositions']['RC09']['state'],'not_saved');self.assertEqual(data['dispositions']['RC04']['state'],'deferred')
 def test_changed_privacy_removes_existing_saved_values(self):
  self.save();self.p.save(self.token,self.info['csrf'],1,'save-optout-00002',guide(False));v=self.r.apply_preferences(self.token);self.assertEqual(v,2);self.assertFalse(self.r.get(self.token)['record']['facts'])
 def test_stale_version_and_replayed_operations(self):
  self.save();self.assertTrue(self.save()['replayed'])
  with self.assertRaises(ProfileError):self.save(version=0,op='stale-save-00001')
  self.assertEqual(self.r.get(self.token)['version'],1)
 def test_concurrent_updates_only_one_wins(self):
  results=[]
  def save(op):
   try:self.save(op=op);results.append('saved')
   except ProfileError as e:results.append(e.code)
  threads=[threading.Thread(target=save,args=('concurrent-save-%04d'%i,))for i in range(2)]
  for t in threads:t.start()
  for t in threads:t.join()
  self.assertEqual(sorted(map(str,results)),['409','saved'])
 def test_delete_guest_cascades_companion_and_expiration(self):
  self.save();self.p.delete(self.token,self.info['csrf'],1)
  with self.p.db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM readiness').fetchone()[0],0)
 def test_fabricated_verification_raw_drafts_and_unbounded_queues_rejected(self):
  for change in [lambda x:x.update(rawText='not allowed'),lambda x:x['facts']['RC09'].update(verified=True),lambda x:x.update(shown=['RC%02d'%i for i in range(1,8)]),lambda x:x['dispositions']['RC04'].update(automaticReopen=True)]:
   data=record();change(data)
   with self.assertRaises(ProfileError):validate(data)
class ApiTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.server=make_server(0,web=WEB,database=Path(self.tmp.name)/'private/g.db',enable_live=False,cookie_namespace='daylight_test_readiness',ui_config={'mockAI':True});self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();_,self.session,h=self.request('GET','/api/guest/session');self.cookie=h['Set-Cookie'].split(';')[0]
 def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
 def request(self,method,path,data=None,csrf=True):
  c=http.client.HTTPConnection('127.0.0.1',self.server.server_port);headers={'Content-Type':'application/json','Origin':'http://127.0.0.1:'+str(self.server.server_port)}
  if hasattr(self,'cookie'):headers['Cookie']=self.cookie
  if hasattr(self,'session') and csrf:headers['X-Daylight-CSRF']=self.session['csrf']
  c.request(method,path,body=json.dumps(data)if data is not None else None,headers=headers);r=c.getresponse();raw=r.read();out=json.loads(raw)if r.getheader('Content-Type','').startswith('application/json')else raw;h=dict(r.getheaders());status=r.status;c.close();return status,out,h
 def test_http_storage_and_privacy_pruning(self):
  self.assertEqual(self.request('PUT','/api/guest/profile',{'guide':guide(),'expectedVersion':0,'operationId':'api-guide-00001'})[0],200)
  self.assertEqual(self.request('PUT','/api/guest/readiness',{'record':record(),'expectedVersion':0,'operationId':'api-ready-00001'})[0],200)
  status,data,_=self.request('GET','/api/guest/readiness');self.assertEqual(status,200);self.assertEqual(data['record']['facts']['RC09']['value']['choice'],'spouse_job')
  status,data,_=self.request('PUT','/api/guest/profile',{'guide':guide(False),'expectedVersion':1,'operationId':'api-guide-00002'});self.assertEqual(status,200);self.assertEqual(data['readinessVersion'],2);self.assertFalse(self.request('GET','/api/guest/readiness')[1]['record']['facts'])
 def test_csrf_fail_closed_and_ai_disabled_manual_contract_stays_available(self):
  self.assertEqual(self.request('PUT','/api/guest/readiness',{'record':record(),'expectedVersion':0,'operationId':'api-ready-00002'},csrf=False)[0],403)
  status,data,_=self.request('POST','/api/readiness/interpret',{'message':'My spouse is still working','guide':guide(),'triggerId':'RC09','recordRevision':1,'requestId':'api-interpret-00001','aiConsent':True});self.assertEqual(status,503)
  self.assertEqual(self.request('GET','/readiness-content.json')[0],200);self.assertFalse(self.request('GET','/api/status')[1]['consumer_ready'])
class AgentTests(unittest.TestCase):
 def test_current_choice_only_exact_quote_and_confirmation_no_fact_write(self):
  a=ReadinessAgent(CONTRACT,FACTS,CONTENT);message='My spouse is still working.';value={'acknowledgment':'review','fact_ids':[],'patches':[{'field':'readiness.RC09','value':'spouse_job','status':'reported','quote':message}],'suggested_node':None};g=guide();before=copy.deepcopy(g);result=a.validate_output(value,message,g,[],['RC09'],'synthetic-owner');self.assertEqual(g,before);self.assertEqual(a.confirm('synthetic-owner',result['proposalId'],1)['patches'][0]['value'],'spouse_job')
  with self.assertRaises(ProfileError):a.confirm('other-owner',result['proposalId'],1)
  with self.assertRaises(ProfileError):a.validate_output(value,message,g,[],['RC01'],'synthetic-owner')
 def test_payload_budget_is_bounded_with_mocked_provider_only(self):
  captured=[]
  def transport(payload):
   captured.append(payload);answer={'acknowledgment':'review','fact_ids':[],'patches':[{'field':'readiness.RC01','value':'self','status':'reported','quote':'myself'}],'suggested_node':None};return {'output':[{'content':[{'type':'output_text','text':json.dumps(answer)}]}]}
  a=ReadinessAgent(CONTRACT,FACTS,CONTENT,client=ResponsesClient(key='synthetic',model='gpt-5.4',transport=transport),enabled=True,max_calls=1);out=a.run('owner','This is for myself.',guide(),['RC01'],'mock-request-00001');self.assertEqual(out['patches'][0]['value'],'self');self.assertLess(len(json.dumps(captured[0]).encode()),24000);self.assertEqual(a.calls,1)
if __name__=='__main__':unittest.main()
