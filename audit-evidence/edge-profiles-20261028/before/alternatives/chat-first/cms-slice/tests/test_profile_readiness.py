"""Focused reported-profile gate fixtures. No real guest records or paid requests."""
import copy,json,subprocess,sys,tempfile,threading,http.client,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from profile_readiness import ProfileReadiness,CAPABILITIES,VERSION
from guest_profiles import GuestProfiles,ProfileError
from readiness_profiles import ReadinessProfiles
from chat_server import build
WEB=ROOT/'apps/chat-alternative';CONTRACT=json.loads((WEB/'guide-contract.json').read_text());CONTENT=json.loads((WEB/'readiness-content.json').read_text());SAMPLES=json.loads((WEB/'sample-plans.json').read_text())
def fixture(kind='none'):
 script="""const C=require('./cms-slice/apps/chat-alternative/chat-core.js'),P=require('./cms-slice/apps/chat-alternative/ten-state.js'),fs=require('fs');let s=C.create();const ref=JSON.parse(fs.readFileSync('./cms-slice/apps/chat-alternative/zip-counties.json'));const kind=process.argv[1];for(const q of P.Q){const d={T01:{value:'compare'},T02:{value:'comfortable'},T03:{zip:'34102'},T04:{value:'month',month:'2027-01'},T05:{value:['original']},T06:{value:'none'},T07:{value:'no'},T08:{value:['local']},T09:{value:'no_preference'},T10:{value:['unknown']}}[q.id];if(kind==='unknown')C.unknown(s,{...q,baseline:true},'unknown');else C.applyBaseline(s,q.id,d,ref);}if(kind!=='unknown')C.stage(s,[],[{triggerId:'RC01',value:{choice:'self'}}],ref);C.summary(s);process.stdout.write(JSON.stringify({guide:s.guide,record:s.readiness}));"""
 return json.loads(subprocess.check_output(['node','-e',script,kind],cwd=ROOT.parent,text=True))
class GateTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.store=GuestProfiles(Path(self.tmp.name)/'private/g.db',CONTRACT);self.companion=ReadinessProfiles(self.store);self.gate=ProfileReadiness(self.store,self.companion,CONTRACT,CONTENT,SAMPLES)
 def tearDown(self):self.tmp.cleanup()
 def assess(self,data,caps=None):return self.gate.assess(data['guide'],data['record'],caps)
 def test_all_unknown_is_missing_not_ready_and_no_verified_recommendation(self):
  d=fixture('unknown');d['record']['completeness']={'remaining':0};a=self.assess(d);self.assertFalse(a['intakeInformationReady']);self.assertFalse(a['personalizedRecommendationAllowed']);self.assertEqual(a['nextQuestion']['id'],'T01');self.assertTrue(a['sampleBrowsing']['requiresExplicitAction']);self.assertIn('personal comparison still needs',a['message'])
 def test_explicit_none_is_known_and_preferences_not_required(self):
  d=fixture();d['guide']['fields'].pop('needs.costPreference');d['guide']['fields'].pop('needs.priorities');a=self.assess(d,['availability','route_comparison','provider_fit','drug_coverage','drug_pricing']);self.assertTrue(a['intakeInformationReady'],a['missingInformation']);self.assertFalse(a['externalVerificationReady']);self.assertFalse(a['personalizedRecommendationAllowed']);self.assertEqual(a['state'],'external_validation_held')
 def test_capabilities_differ_and_unknown_is_not_explicit_none(self):
  d=fixture();d['guide']['fields']['needs.medicinesStatus']['value']='unknown';d['guide']['fields']['needs.medicinesStatus']['status']='unknown';self.assertTrue(self.assess(d,['availability'])['intakeInformationReady']);self.assertFalse(self.assess(d,['drug_coverage'])['intakeInformationReady']);self.assertFalse(self.assess(d,['timing'])['intakeInformationReady'])
 def test_partial_provider_and_drug_lists_require_every_entity(self):
  d=fixture();f=d['guide']['fields'];base=copy.deepcopy(f['needs.providersStatus']);f['needs.providersStatus']['value']='list';f['needs.providers']={**base,'value':'Dr One; Dr Two'};f['needs.medicinesStatus']['value']='yes';f['needs.medications']={**base,'value':'ExampleOne; ExampleTwo'};r=d['record'];r['guideFingerprint']='';r['facts']['RC21']={'value':{'choice':'details','items':[{'choice':'details','entity':'doctor-1','practice':'One Clinic','city':'Naples FL'}]},'confirmation':'confirmed_by_user','source':'user_choice','revision':5,'stale':False}
  a=self.assess(d,['provider_fit','drug_coverage']);self.assertFalse(a['intakeInformationReady']);self.assertTrue(any(m['entity']=='doctor-2'for m in a['missingInformation']));self.assertTrue(any(m['key']=='medicine-2.strength'for m in a['missingInformation']))
 def test_full_inputs_still_have_external_holds_and_medicine_edit_invalidates_fill(self):
  d=fixture();f=d['guide']['fields'];e=copy.deepcopy(f['needs.medicinesStatus']);f['needs.medicinesStatus']['value']='yes';f['needs.medications']={**e,'value':'ExampleOne'};r=d['record'];r['guideFingerprint']=''
  def fact(value,revision):return {'value':value,'confirmation':'confirmed_by_user','source':'user_choice','revision':revision,'stale':False}
  r['facts']['RC22']=fact({'choice':'details','items':[{'entity':'medicine-1','choice':'details','name':'ExampleOne','strength':'5 mg','form':'tablet'}]},5);r['facts']['RC23']=fact({'choice':'details','items':[{'entity':'medicine-1','choice':'details','quantity':'30','daysSupply':'30','pharmacy':'Example Pharmacy Naples FL','channel':'retail'}]},6)
  a=self.assess(d,['drug_pricing']);self.assertTrue(a['intakeInformationReady'],a['missingInformation']);self.assertFalse(a['personalizedRecommendationAllowed']);r['facts']['RC22']['revision']=7;r['facts']['RC22']['value']['items'][0]['strength']='10 mg';a=self.assess(d,['drug_pricing']);self.assertFalse(a['intakeInformationReady']);self.assertTrue(any(m['state']=='needs_review'for m in a['missingInformation']))
 def test_changed_baseline_invalidates_office_report_even_if_client_stale_flag_false(self):
  d=fixture();f=d['guide']['fields'];f['needs.providersStatus']['value']='list';f['needs.providers']={**f['needs.providersStatus'],'value':'Dr One'};r=d['record'];r['guideFingerprint']=json.dumps({'needs.providers':{'revision':f['needs.providers']['revision'],'status':'reported','confirmation':'confirmed_by_user'}});r['facts']['RC21']={'value':{'choice':'details','items':[{'entity':'doctor-1','choice':'details','practice':'One Clinic','city':'Naples FL'}]},'confirmation':'confirmed_by_user','source':'user_choice','revision':5,'stale':False};self.assertTrue(self.assess(d,['provider_fit'])['intakeInformationReady']);f['needs.providers']['value']='Dr Different';f['needs.providers']['revision']+=1;self.assertFalse(self.assess(d,['provider_fit'])['intakeInformationReady'])
 def test_same_guest_saved_records_reused_and_sensitive_omission_remains_missing(self):
  d=fixture();token,info,_=self.store.session();d['guide']['preferences'].update(saveGuide=True,saveSensitive=True);self.store.save(token,info['csrf'],0,'synthetic-profile-save-001',d['guide']);self.companion.save(token,info['csrf'],0,'synthetic-profile-save-002',d['record']);saved=self.gate.assess_saved(token);self.assertTrue(saved['assessment']['intakeInformationReady']);self.assertEqual(saved['profileVersion'],1);d['guide']['preferences']['saveSensitive']=False;self.store.save(token,info['csrf'],1,'synthetic-profile-save-003',d['guide']);self.companion.apply_preferences(token);self.assertFalse(self.gate.assess_saved(token)['assessment']['intakeInformationReady'])
 def test_deferred_optional_brand_does_not_erase_known_required_drug_details(self):
  d=fixture();f=d['guide']['fields'];f['needs.medicinesStatus']['value']='yes';f['needs.medications']={**f['needs.medicinesStatus'],'value':'ExampleOne'};r=d['record'];r['guideFingerprint']='';r['facts']['RC22']={'value':{'choice':'details','items':[{'entity':'medicine-1','choice':'details','name':'ExampleOne','strength':'5 mg','form':'tablet'}]},'confirmation':'confirmed_by_user','source':'user_choice','revision':5,'stale':False};r['entityDispositions']={'RC22':{'medicine-1':{'state':'explicit_unknown','automaticReopen':False}}};r['dispositions']['RC22']={'state':'explicit_unknown','automaticReopen':False};self.assertTrue(self.assess(d,['drug_coverage'])['intakeInformationReady']);del r['facts']['RC22']['value']['items'][0]['strength'];self.assertFalse(self.assess(d,['drug_coverage'])['intakeInformationReady'])
 def test_sensitive_ids_and_verified_forgery_rejected(self):
  d=fixture();d['guide']['fields']['intent.goal']['source']='verified_source'
  with self.assertRaises(ProfileError):self.assess(d)
  d=fixture();d['guide']['fields']['needs.providers']={**d['guide']['fields']['needs.providersStatus'],'value':'SSN: 123-45-6789'}
  with self.assertRaises(ProfileError):self.assess(d)
class GateHttpTests(unittest.TestCase):
 def test_authoritative_gate_ignores_client_completion_and_blocks_recommendations(self):
  with tempfile.TemporaryDirectory()as tmp:
   server=build(0,fixture=True,database=Path(tmp)/'private/g.db');t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
   def request(path,body=None,cookie=None,csrf=None):
    c=http.client.HTTPConnection('127.0.0.1',server.server_port);h={}
    if cookie:h['Cookie']=cookie
    if csrf:h['X-Daylight-CSRF']=csrf
    if body is not None:h['Content-Type']='application/json'
    c.request('POST'if body is not None else'GET',path,json.dumps(body)if body is not None else None,h);response=c.getresponse();data=json.loads(response.read());headers=dict(response.getheaders());c.close();return response.status,data,headers
   try:
    _,session,h=request('/api/guest/session');cookie=h['Set-Cookie'].split(';')[0];bad=fixture('unknown');bad['record']['completeness']={'remaining':0};code,a,_=request('/api/profile/readiness',bad,cookie,session['csrf']);self.assertEqual(code,200,a);self.assertFalse(a['intakeInformationReady']);code,a,_=request('/api/recommendations',bad,cookie,session['csrf']);self.assertEqual(code,409);full=fixture();code,a,_=request('/api/recommendations',full,cookie,session['csrf']);self.assertEqual(code,503);self.assertFalse(a['assessment']['personalizedRecommendationAllowed']);code,_,_=request('/api/profile/readiness');self.assertEqual(code,401);code,samples,_=request('/api/sample-plans');self.assertEqual(code,200);self.assertTrue(samples['not_recommendation'])
   finally:server.shutdown();server.server_close();t.join()
if __name__=='__main__':unittest.main()
