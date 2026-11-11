"""D66 synthetic persistence/isolation tests. Never read real guest databases or call OpenAI."""
import copy,http.client,json,sys,tempfile,threading,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from guest_profiles import GuestProfiles,ProfileError,validate_guide
from guide_server import make_server
from guide_agent import GuideAgent
TEN=ROOT/'apps/ten-question';CONTRACT=json.loads((TEN/'guide-contract.json').read_text());FACTS=json.loads((TEN/'teaching-facts.json').read_text())
def e(value,status='reported'):return {'value':value,'status':status,'confirmation':'confirmed_by_user','source':'user_choice','revision':1,'confirmedAt':'2026-10-21T00:00:00Z'}
def guide():return {'schemaVersion':2,'stateVersion':1,'fields':{'intent.goal':e('learn'),'knowledge.general':e('new'),'coverage.requestedStart':e('unknown','unknown'),'coverage.requestedStartMonth':e('2027-01'),'needs.providersStatus':e('list'),'needs.providers':e('Synthetic doctor'),'needs.medications':e('Synthetic medicine'),'intent.goalDetail':e('Synthetic wording'),'privacy.persistenceChoice':e('save')},'flow':{'node':'T07','history':[],'queue':[],'lessonReturn':None,'personalReview':False,'guideOpen':True,'origin':'T01','invalidations':[],'scroll':120},'topics':{},'preferences':{'saveGuide':True,'saveSensitive':False,'noticeVersion':'guest-notice-2026-10-21-v1'}}
class TenProfileTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'private/guide.db';self.store=GuestProfiles(self.path,CONTRACT);self.token,self.info,_=self.store.session()
 def tearDown(self):self.tmp.cleanup()
 def test_resume_exact_step_without_changing_confirmed_unknown(self):
  self.store.save(self.token,self.info['csrf'],0,'synthetic-save-0001',guide());saved=GuestProfiles(self.path,CONTRACT).get(self.token)['guide'];self.assertEqual(saved['flow']['node'],'T07');self.assertEqual(saved['fields']['coverage.requestedStart']['status'],'unknown');self.assertEqual(saved['flow']['scroll'],120)
 def test_sensitive_dates_and_notes_require_separate_choice(self):
  self.store.save(self.token,self.info['csrf'],0,'synthetic-save-0002',guide());g=self.store.get(self.token)['guide'];self.assertNotIn('coverage.requestedStartMonth',g['fields']);self.assertNotIn('intent.goalDetail',g['fields']);self.assertNotIn('needs.providers',g['fields']);self.assertEqual(g['fields']['needs.providersStatus']['value'],'list')
 def test_sensitive_optin_preserves_notes_and_optout_removes_saved_notes(self):
  g=guide();g['preferences']['saveSensitive']=True;self.store.save(self.token,self.info['csrf'],0,'synthetic-save-0003',g);self.assertIn('needs.providers',self.store.get(self.token)['guide']['fields']);g['preferences']['saveSensitive']=False;self.store.save(self.token,self.info['csrf'],1,'synthetic-save-0004',g);self.assertNotIn('needs.providers',self.store.get(self.token)['guide']['fields'])
 def test_legacy_state_remains_valid_storage_but_no_navigation_migration_is_run(self):
  g=guide();g['flow']['node']='E02';g['fields']['outcome.drafts']=e('Synthetic previous notes');self.assertEqual(validate_guide(g,CONTRACT)['flow']['node'],'E02')
 def test_stale_version_does_not_overwrite_saved_copy(self):
  self.store.save(self.token,self.info['csrf'],0,'synthetic-save-0005',guide())
  with self.assertRaises(ProfileError):self.store.save(self.token,self.info['csrf'],0,'synthetic-save-0006',guide())
  self.assertEqual(self.store.get(self.token)['version'],1)
 def test_agent_tools_remain_bounded_and_sensitive_context_excluded(self):
  a=GuideAgent(CONTRACT,FACTS);self.assertIn('needs.travel',a.fields);self.assertIn('needs.costPreference',a.fields);context=a.context(guide());self.assertNotIn('needs.providers',context);self.assertNotIn('coverage.requestedStartMonth',context);self.assertNotIn('intent.goalDetail',context)
 def test_runtime_namespace_is_local_only_and_production_cannot_enable_mock_ui(self):
  with self.assertRaises(ValueError):make_server(0,web=TEN,production=True,public_origin='https://example.com',cookie_namespace='daylight_ten_fixture')
  with self.assertRaises(ValueError):make_server(0,web=TEN,production=True,public_origin='https://example.com',ui_config={'mockAI':True})
 def test_travel_proposals_use_valid_arrays_and_keep_local_only_exclusive(self):
  a=GuideAgent(CONTRACT,FACTS);self.assertEqual(a.interpret_value('needs.travel','another_state,outside_us'),['another_state','outside_us'])
  with self.assertRaises(ProfileError):a.interpret_value('needs.travel','local,another_state')
class TenIsolationTests(unittest.TestCase):
 def test_cookie_and_database_cannot_access_the_other_surface(self):
  with tempfile.TemporaryDirectory() as tmp:
   old=make_server(0,web=ROOT/'apps/chat',database=Path(tmp)/'old/g.db',enable_live=False);new=make_server(0,web=TEN,database=Path(tmp)/'new/g.db',enable_live=False,cookie_namespace='daylight_ten_fixture',ui_config={'mockAI':True})
   threads=[threading.Thread(target=s.serve_forever,daemon=True)for s in [old,new]]
   for t in threads:t.start()
   try:
    def request(server,path,cookie=None):
     c=http.client.HTTPConnection('127.0.0.1',server.server_port);c.request('GET',path,headers={'Cookie':cookie}if cookie else {});r=c.getresponse();body=json.loads(r.read());headers=dict(r.getheaders());c.close();return r.status,body,headers
    _,first,h=request(old,'/api/guest/session');oldcookie=h['Set-Cookie'].split(';')[0];_,second,h2=request(new,'/api/guest/session',oldcookie);self.assertIn('daylight_ten_fixture=',h2['Set-Cookie']);self.assertFalse(second['hasSaved']);code,_,_=request(new,'/api/guest/profile',oldcookie);self.assertEqual(code,401);code,_,_=request(old,'/api/guest/profile',h2['Set-Cookie'].split(';')[0]);self.assertEqual(code,401);_,config,_=request(new,'/ten-config.json');self.assertTrue(config['mockAI'])
   finally:
    for s in [old,new]:s.shutdown();s.server_close()
    for t in threads:t.join()
if __name__=='__main__':unittest.main()
