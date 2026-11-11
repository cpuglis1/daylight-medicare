"""Actual HTTP ownership/head guards with fictional adapter/source fixtures.

The injected adapter fixture isolates transport. Core tests independently use
the real profile adapter; actual-source full-journey verification is separate.
"""
import copy
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import uuid
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import build
from identity_http import install_identity_routes
from identity_journey import IdentityJourney, IdentityPurposeContract
from test_identity_journey import case, Discovery, Dictionary, Providers, ProviderDiscovery, ROOT


class IdentityHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory()
        cls.discovery=Discovery();cls.exact=Dictionary();cls.providers=Providers()
        cls.service=IdentityJourney(cls.discovery,cls.exact,cls.providers,
            provider_discovery=ProviderDiscovery(),purpose=IdentityPurposeContract.load(ROOT,internal_research=True))
        cls.server=build(0,fixture=True,database=Path(cls.temporary.name)/'fictional-guests.sqlite3')
        install_identity_routes(cls.server,cls.service)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.temporary.cleanup()

    def request(self,path,payload=None,*,csrf=True,cookie=None,origin=None,method=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
        headers={'Origin':origin or f'http://127.0.0.1:{self.server.server_port}'}
        token=self.cookie if cookie is None else cookie
        if token:headers['Cookie']=token
        if payload is not None:
            headers['Content-Type']='application/json'
            if csrf:headers['X-Daylight-CSRF']=self.session['csrf']
        connection.request(method or ('POST' if payload is not None else 'GET'),path,
            json.dumps(payload) if payload is not None else None,headers)
        response=connection.getresponse();new_cookie=response.getheader('Set-Cookie')
        if new_cookie:self.cookie=new_cookie.split(';')[0]
        body=json.loads(response.read());status=response.status;connection.close()
        return status,body

    def setUp(self):
        self.cookie=None;self.discovery.calls.clear();self.discovery.failure=False
        self.discovery.access=[];self.exact.calls.clear();self.exact.failure=False;self.exact.access=[]
        self.providers.__init__();self.service.purpose=IdentityPurposeContract.load(ROOT,internal_research=True)
        _,self.session=self.request('/api/guest/session')
        _,self.state=self.request('/api/conversation/initial')
        status,self.state=self.request('/api/conversation/turn',{'guide':self.state['guide'],'record':self.state['record'],
            'requestId':str(uuid.uuid4()),'action':{'type':'start'}})
        self.assertEqual(status,200,self.state)
        self.profile=case()
        self.adapter=patch('identity_http.build_comparison_profile',side_effect=lambda *args,**kw:copy.deepcopy(self.profile))
        self.adapter.start();self.addCleanup(self.adapter.stop)

    def payload(self,**extra):
        return {'guide':copy.deepcopy(self.state['guide']),'record':copy.deepcopy(self.state['record']),
            'continuation':self.state['continuation'],'requestId':str(uuid.uuid4()),**extra}

    def search(self):return self.request('/api/identity/drug/search',self.payload(itemId='medicine-1'))

    def test_cookie_origin_csrf_and_url_parameters_precede_source_queries(self):
        self.assertEqual(self.request('/api/identity/status',cookie='')[0],401)
        self.assertEqual(self.request('/api/identity/status',origin='https://outside.invalid')[0],403)
        self.assertEqual(self.request('/api/identity/drug/search',self.payload(itemId='medicine-1'),csrf=False)[0],403)
        self.assertEqual(self.request('/api/identity/drug/search?name=private',self.payload(itemId='medicine-1'))[0],422)
        self.assertEqual(self.discovery.calls,[])

    def test_consumer_capability_is_held_and_deliberate_search_does_not_query_sources(self):
        self.service.purpose=None
        status,out=self.request('/api/identity/status')
        self.assertEqual(status,200);self.assertEqual(out['identity']['capability']['state'],'held')
        status,out=self.search();self.assertEqual(status,200)
        self.assertEqual(out['identity']['candidates'],[]);self.assertEqual(self.discovery.calls,[])

    def test_internal_search_confirm_and_preparation_do_not_return_or_overwrite_profile(self):
        before=copy.deepcopy(self.state);status,out=self.search()
        self.assertEqual(status,200,out)
        self.assertEqual(set(out),{'identity','continuation'})
        identity=out['identity'];self.assertTrue(identity['candidates'][0]['selectable'])
        status,chosen=self.request('/api/identity/confirm',self.payload(choiceToken=identity['choice_token'],
            candidateId=identity['candidates'][0]['candidate_id'],confirmed=True))
        self.assertEqual(status,200,chosen)
        self.assertEqual(chosen['identity']['preparation']['selected_count'],1)
        self.assertEqual(chosen['identity']['preparation']['coverage_findings'],[])
        self.assertEqual(chosen['continuation'],self.state['continuation']);self.assertEqual(before,self.state)
        self.assertNotIn('raw_source_payload',json.dumps(chosen));self.assertNotIn('guide',chosen)
        self.assertFalse(chosen['identity']['ai_context_changed']);self.assertFalse(chosen['identity']['saved'])

    def test_request_cannot_supply_owner_source_rows_authority_scope_or_ai_permission(self):
        for key,value in [('owner','foreign'),('source',{}),('authority','permitted'),
                          ('scope',{'year':2027}),('consentVersion','invented'),('audience','internal_research')]:
            with self.subTest(key=key):
                status,_=self.request('/api/identity/drug/search',self.payload(itemId='medicine-1',**{key:value}))
                self.assertEqual(status,422)
        self.assertEqual(self.discovery.calls,[])

    def test_stale_or_missing_signed_snapshot_is_rejected_without_source_query(self):
        for change in ({'continuation':'0'*32+'.'+'0'*64},{'requestId':'short'}):
            self.assertEqual(self.request('/api/identity/drug/search',self.payload(itemId='medicine-1',**change))[0],409)
        owner=self.server.profiles.digest(self.cookie.split('=',1)[1])
        with self.server.adaptive.lock:
            for (entry_owner,_),entry in self.server.adaptive.turn_journal.items():
                if entry_owner==owner:entry['expires']=0
        self.assertEqual(self.search()[0],409);self.assertEqual(self.discovery.calls,[])

    def test_changed_head_during_source_lookup_suppresses_output_and_forgets_ram_offer(self):
        owner=self.server.profiles.digest(self.cookie.split('=',1)[1])
        before=set(self.service._offers)
        def change():
            with self.server.adaptive.lock:self.server.adaptive.current_chain[owner]='foreign-chain'
        self.discovery.on_read=change
        try:
            status,out=self.search()
            self.assertEqual(status,409);self.assertNotIn('identity',out)
            self.assertFalse(any(value['owner']==owner for value in self.service._offers.values()))
            self.assertEqual(set(self.service._offers),before)
        finally:self.discovery.on_read=None

    def test_changed_journal_signature_during_source_lookup_suppresses_cached_snapshot(self):
        owner=self.server.profiles.digest(self.cookie.split('=',1)[1])
        def change():
            with self.server.adaptive.lock:
                for (entry_owner,_),entry in self.server.adaptive.turn_journal.items():
                    if entry_owner==owner:entry['signature']='changed'
        self.discovery.on_read=change
        try:self.assertEqual(self.search()[0],409)
        finally:self.discovery.on_read=None

    def test_source_errors_are_fixed_and_ordinary_advisor_route_remains_usable(self):
        self.discovery.failure=True
        status,out=self.search();self.assertEqual(status,422)
        self.assertNotIn('PRIVATE_SOURCE_EXCEPTION_CANARY',json.dumps(out))
        self.assertEqual(out['identity']['personal_output_state'],'held')
        status,out=self.request('/api/identity/view',self.payload())
        self.assertEqual(status,200,out)
        self.assertEqual(self.request('/api/conversation/initial')[0],200)

    def test_privacy_preferences_are_not_replaced_from_the_cached_turn(self):
        payload=self.payload();payload['guide'].setdefault('preferences',{})['saveSensitive']=False
        status,out=self.request('/api/identity/view',payload)
        self.assertEqual(status,200,out)
        self.assertNotIn('guide',out);self.assertNotIn('record',out);self.assertNotIn('preferences',out)

    def test_new_signed_chain_immediately_forgets_old_offer_even_with_identical_reports(self):
        _,out=self.search();offer=out['identity'];old_chain=self.state['continuation'].split('.')[0]
        status,new_state=self.request('/api/conversation/turn',{
            'guide':self.state['guide'],'record':self.state['record'],
            'requestId':str(uuid.uuid4()),'action':{'type':'start'}})
        self.assertEqual(status,200,new_state);self.state=new_state
        self.assertNotEqual(self.state['continuation'].split('.')[0],old_chain)
        self.assertNotIn(offer['choice_token'],self.service._offers)
        status,out=self.request('/api/identity/confirm',self.payload(choiceToken=offer['choice_token'],
            candidateId=offer['candidates'][0]['candidate_id'],confirmed=True))
        self.assertEqual(status,422,out)

    def test_authenticated_delete_attempt_clears_choices_but_foreign_csrf_does_not(self):
        _,out=self.search();offer=out['identity']
        payload={'expectedVersion':999,'confirmed':True}
        self.assertEqual(self.request('/api/guest/profile',payload,method='DELETE',csrf=False)[0],403)
        self.assertIn(offer['choice_token'],self.service._offers)
        self.assertEqual(self.request('/api/guest/profile',payload,method='DELETE')[0],409)
        self.assertNotIn(offer['choice_token'],self.service._offers)

    def test_successful_guest_delete_clears_pending_and_selected_visit_data(self):
        _,out=self.search();offer=out['identity']
        status,_=self.request('/api/identity/confirm',self.payload(choiceToken=offer['choice_token'],
            candidateId=offer['candidates'][0]['candidate_id'],confirmed=True))
        self.assertEqual(status,200)
        status,out=self.request('/api/guest/profile',{'expectedVersion':0,'confirmed':True},method='DELETE')
        self.assertEqual(status,200,out)
        self.assertNotIn(offer['choice_token'],self.service._offers)
        self.assertFalse(any(value['offer_token']==offer['choice_token'] for value in self.service._selected.values()))

    def test_comparison_journey_uses_current_visit_and_trusted_snapshot_only(self):
        _,out=self.search();offer=out['identity']
        self.assertEqual(self.request('/api/identity/confirm',self.payload(choiceToken=offer['choice_token'],
            candidateId=offer['candidates'][0]['candidate_id'],confirmed=True))[0],200)
        visit_owner=self.service._offers[offer['choice_token']]['owner']
        seen=[]
        def compare(service,owner,response):
            seen.append((service,owner,copy.deepcopy(response)))
            return {'state':'preparation_only','personal_output_state':'held','coverage_findings':[]}
        with patch('comparison_journey.comparison_for_visit',side_effect=compare):
            status,out=self.request('/api/comparison/journey',self.payload())
            self.assertEqual(status,200,out)
            self.assertEqual(set(out),{'comparison','identity','continuation'})
            self.assertEqual(out['identity']['preparation']['selected_count'],1)
            self.assertEqual(out['comparison']['coverage_findings'],[])
            self.assertEqual(out['identity']['items'][0]['state'],'selected_needs_source_recheck')
            self.assertEqual(self.request('/api/comparison/journey',self.payload(owner='foreign'))[0],422)
        self.assertEqual(len(seen),1)
        self.assertIs(seen[0][0],self.service);self.assertEqual(seen[0][1],visit_owner)
        self.assertEqual(seen[0][2]['guide'],self.state['guide'])
        self.assertEqual(seen[0][2]['record'],self.state['record'])
        self.assertNotIn('guide',out);self.assertNotIn('record',out)

    def test_comparison_journey_changed_head_suppresses_comparison_and_clears_choices(self):
        _,out=self.search();offer=out['identity']
        owner=self.server.profiles.digest(self.cookie.split('=',1)[1])
        def compare(*args):
            with self.server.adaptive.lock:self.server.adaptive.current_chain[owner]='foreign-chain'
            return {'state':'PRIVATE_STALE_COMPARISON_CANARY'}
        with patch('comparison_journey.comparison_for_visit',side_effect=compare):
            status,out=self.request('/api/comparison/journey',self.payload())
        self.assertEqual(status,409,out)
        self.assertNotIn('comparison',out);self.assertNotIn('identity',out)
        self.assertNotIn(offer['choice_token'],self.service._offers)


if __name__=='__main__':unittest.main()
