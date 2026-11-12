"""Actual HTTP/session/save boundaries with an isolated synthetic database."""
import copy
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import build

class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.server=build(0,fixture=True,database=Path(cls.tmp.name)/'private/test.sqlite3')
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()
    def request(self,path,body=None,origin=None,csrf=True,method=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
        headers={'Origin':origin or f'http://127.0.0.1:{self.server.server_port}'}
        if getattr(self,'cookie',None):headers['Cookie']=self.cookie
        if body is not None:
            headers['Content-Type']='application/json'
            if csrf:headers['X-Daylight-CSRF']=self.session['csrf']
        connection.request(method or ('POST' if body is not None else 'GET'),path,json.dumps(body) if body is not None else None,headers)
        response=connection.getresponse();raw=response.read();cookie=response.getheader('Set-Cookie')
        if cookie:self.cookie=cookie.split(';')[0]
        connection.close()
        return response.status,json.loads(raw)
    def setUp(self):
        self.cookie=None;status,self.session=self.request('/api/guest/session');self.assertEqual(status,200)
        _,self.state=self.request('/api/conversation/initial')
    def turn(self,action):
        status,out=self.request('/api/conversation/turn',{'guide':self.state['guide'],'record':self.state['record'],'action':action,'requestId':str(uuid.uuid4()),**({'continuation':self.state['continuation']} if self.state.get('continuation') else {})})
        self.assertEqual(status,200,out);self.state=out;return out
    def test_cookie_is_separate_and_http_only(self):
        self.assertTrue(self.cookie.startswith('daylight_advisor_fixture='))
        _,other=self.request('/api/guest/session');self.assertEqual(other['csrf'],self.session['csrf'])
    def test_cross_origin_and_missing_csrf_rejected(self):
        payload={'guide':self.state['guide'],'record':self.state['record'],'action':{'type':'start'},'requestId':str(uuid.uuid4())}
        self.assertEqual(self.request('/api/conversation/turn',payload,origin='https://example.com')[0],403)
        self.assertEqual(self.request('/api/conversation/turn',payload,csrf=False)[0],403)
    def test_save_omits_sensitive_and_transcript(self):
        self.turn({'type':'choice','id':'T01','fields':{'choice':'compare'}})
        self.turn({'type':'choice','id':'RC01','fields':{'choice':'self'}})
        self.turn({'type':'choice','id':'T06','fields':{'text':'Private Doctor Canary'}})
        self.state['guide']['preferences'].update(saveGuide=True,saveSensitive=False)
        payload={'guide':self.state['guide'],'record':self.state['record'],'expectedVersion':0,'expectedReadinessVersion':0,'operationId':str(uuid.uuid4())}
        code,receipt=self.request('/api/conversation/save',payload);self.assertEqual(code,200,receipt)
        code,replay=self.request('/api/conversation/save',payload);self.assertEqual(receipt['version'],replay['version'])
        _,saved=self.request('/api/guest/profile');_,readiness=self.request('/api/guest/readiness')
        self.assertNotIn('Private Doctor Canary',json.dumps([saved,readiness]));self.assertNotIn('messages',saved['guide'])
        with self.server.profiles.db() as db:
            stored=' '.join(str(row) for row in db.execute('SELECT guide FROM guests'))
        self.assertNotIn('Private Doctor Canary',stored)
    def test_all_unknown_cannot_recommend(self):
        self.turn({'type':'task','task':'compare','preparing':True})
        for _ in range(20):
            q=self.state['assessment']['nextQuestion']
            if not q:break
            self.turn({'type':'unknown','id':q['id']})
        code,value=self.request('/api/recommendations',{'guide':self.state['guide'],'record':self.state['record']})
        self.assertIn(code,{409,503});self.assertIn('held',value['error'])
    def test_old_cookie_cannot_read_new_profile(self):
        cookie=self.cookie;self.cookie='daylight_chat_alt_dev='+cookie.split('=',1)[1]
        self.assertEqual(self.request('/api/guest/profile')[0],401)
    def test_form_preparation_http_review(self):
        review=self.turn({'type':'review_preparation'})['review']
        result=self.turn({'type':'run_preparation','token':review['token']})
        self.assertEqual(result['preparation']['status'],'prepared')
        self.assertFalse(result['personalRecommendation'])
    def test_save_conflict_does_not_overwrite_the_saved_copy(self):
        self.state['guide']['preferences'].update(saveGuide=True,saveSensitive=False)
        first={'guide':copy.deepcopy(self.state['guide']),'record':copy.deepcopy(self.state['record']),'expectedVersion':0,'expectedReadinessVersion':0,'operationId':str(uuid.uuid4())}
        code,receipt=self.request('/api/conversation/save',first);self.assertEqual(code,200)
        self.turn({'type':'choice','id':'T02','fields':{'choice':'comfortable'}})
        stale={**first,'guide':self.state['guide'],'record':self.state['record'],'operationId':str(uuid.uuid4())}
        self.assertEqual(self.request('/api/conversation/save',stale)[0],409)
        _,saved=self.request('/api/guest/profile');self.assertNotIn('knowledge.general',saved['guide']['fields'])

    def test_natural_reports_roundtrip_with_honest_status_and_orientation(self):
        self.turn({'type':'message','message':"I've been retired for a few years, and am turning 65 in November."})
        self.assertNotIn('review',self.state)
        self.state['guide']['preferences'].update(saveGuide=True,saveSensitive=True)
        payload={'guide':self.state['guide'],'record':self.state['record'],'expectedVersion':0,'expectedReadinessVersion':0,'operationId':str(uuid.uuid4())}
        code,receipt=self.request('/api/conversation/save',payload);self.assertEqual(code,200,receipt)
        _,saved=self.request('/api/guest/profile');_,ready=self.request('/api/guest/readiness')
        self.assertEqual(saved['guide']['fields']['situation.age65']['confirmation'],'reported_by_user')
        self.assertEqual(saved['guide']['fields']['situation.age65']['value'],{'month':11,'year':None})
        self.state={'guide':saved['guide'],'record':ready['record']}
        out=self.turn({'type':'refresh'})
        self.assertEqual(out['assessment']['nextQuestion']['id'],'T05')
        self.assertNotIn('review',out)

    def test_natural_sensitive_omission_retains_resumable_safe_provenance(self):
        self.turn({'type':'message','message':"I've been retired for a few years, and am turning 65 in November."})
        self.state['guide']['preferences'].update(saveGuide=True,saveSensitive=False)
        payload={'guide':self.state['guide'],'record':self.state['record'],'expectedVersion':0,'expectedReadinessVersion':0,'operationId':str(uuid.uuid4())}
        code,receipt=self.request('/api/conversation/save',payload);self.assertEqual(code,200,receipt)
        _,saved=self.request('/api/guest/profile');_,ready=self.request('/api/guest/readiness')
        self.assertNotIn('situation.age65',saved['guide']['fields'])
        self.assertNotIn('situation.retirement',saved['guide']['fields'])
        self.assertEqual(saved['guide']['fields']['subject.role']['confirmation'],'reported_by_user')
        self.assertEqual(ready['record']['facts'],{})
        self.state={'guide':saved['guide'],'record':ready['record']}
        self.turn({'type':'refresh'})

    def situation_guide(self,sensitive):
        guide=copy.deepcopy(self.state['guide'])
        guide['preferences'].update(saveGuide=True,saveSensitive=sensitive)
        guide['fields']['situation.age65']={'value':{'month':11,'year':None},'status':'reported','source':'confirmed_agent_interpretation','confirmation':'confirmed_by_user','revision':1}
        guide['stateVersion']=1
        return guide

    def test_situation_observations_require_sensitive_save_permission(self):
        guide=self.situation_guide(False)
        body={'guide':guide,'record':self.state['record'],'expectedVersion':0,'expectedReadinessVersion':0,'operationId':str(uuid.uuid4())}
        self.assertEqual(self.request('/api/conversation/save',body)[0],200)
        _,saved=self.request('/api/guest/profile')
        self.assertNotIn('situation.age65',saved['guide']['fields'])

    def test_opted_in_situation_round_trip_preserves_unknown_year(self):
        guide=self.situation_guide(True)
        body={'guide':guide,'record':self.state['record'],'expectedVersion':0,'expectedReadinessVersion':0,'operationId':str(uuid.uuid4())}
        self.assertEqual(self.request('/api/conversation/save',body)[0],200)
        _,saved=self.request('/api/guest/profile')
        self.assertEqual(saved['guide']['fields']['situation.age65']['value'],{'month':11,'year':None})
        self.assertEqual(self.request('/api/conversation/turn',{'guide':saved['guide'],'record':self.state['record'],'action':{'type':'refresh'},'requestId':str(uuid.uuid4())})[0],200)

    def test_retained_direct_profile_put_uses_same_sensitive_boundary(self):
        body={'guide':self.situation_guide(False),'expectedVersion':0,'operationId':str(uuid.uuid4())}
        self.assertEqual(self.request('/api/guest/profile',body,method='PUT')[0],200)
        _,saved=self.request('/api/guest/profile')
        self.assertNotIn('situation.age65',saved['guide']['fields'])

if __name__=='__main__':unittest.main()
