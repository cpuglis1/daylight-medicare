"""Synthetic HTTP checks of the actual local research/owner-state boundaries."""
import copy
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import build
from comparison_research import RESEARCH_SCOPE


class FixtureRepository:
    def __init__(self):
        self.calls = []
        self.failure = False
        self.on_read = None

    def list_plans(self, scope, after_ordinal=None, limit=20, expected_snapshot_id=None):
        self.calls.append(('list', copy.deepcopy(scope)))
        if self.failure:
            raise RuntimeError('DO_NOT_EXPOSE_SOURCE_OR_CREDENTIAL_CANARY')
        if self.on_read:
            self.on_read()
        if expected_snapshot_id not in {None, 'fixture:research-snapshot'}:
            raise ValueError('STALE_RESEARCH_SNAPSHOT')
        plans = [{'offering_id': f'2026:H0000:{n:03}:000',
            'display_name': f'Fictional transport record {n}',
            'identity': {'kind':'cms_offering','year':2026,'contract_id':'H0000','plan_id':f'{n:03}','segment_id':'000'},
            'source_ordinal': n, 'plan_type':'Fictional', 'source_native_fields': {'fixture': True},
            'restrictions': {'qualification':'Retain this entire fictional source condition.'},
            'lineage': {'source_table':'fixture','artifact_sha256':'f'*64,'source_row_ordinal':n}}
            for n in range(1,4)]
        plans = [p for p in plans if p['source_ordinal'] > (after_ordinal or 0)]
        page = plans[:limit]
        return {'contract_id':'fixture:research-contract','status':'research_only','scope':copy.deepcopy(scope),
            'binding':{'snapshot_id':'fixture:research-snapshot','build_id':'fixture:research-build',
                       'accepted_release_id':None},'total':3,'plans':page,
            'page':{'has_more':len(plans)>limit,'next_after_ordinal':page[-1]['source_ordinal'] if len(plans)>limit else None},
            'authority':{'published_display':{'state':'held'}}}

    def inspect_plan(self, offering_id, **kwargs):
        self.calls.append(('inspect', offering_id))
        if kwargs.get('expected_snapshot_id') not in {None,'fixture:research-snapshot'}:
            raise ValueError('STALE_RESEARCH_SNAPSHOT')
        return {'status':'research_only','offering_id':offering_id,
            'binding':{'snapshot_id':'fixture:research-snapshot','accepted_release_id':None},
            'evidence_by_layer':{'L03':{'records':[{'conditions':{
                'root':{'op':'and','children':[{'meaning':'Fictional INN only'},
                    {'meaning':'Fictional service exception'}]},'context':'Full retained fictional context'},
                'lineage':{'artifact_sha256':'f'*64,'source_row_ordinal':1},'output_authority':'held'}],
                'has_more':True,'next_after_entity_id':'fixture:next'}}}


class FixtureReferenceAdapter:
    """Synthetic transport only; real original-authority replay has separate tests."""
    def __init__(self):
        self.calls = []
        self.failure = False

    def lookup(self, offering_id, *, year=2026, entry_ids=None):
        self.calls.append({'offering_id':offering_id,'year':year,'entry_ids':copy.deepcopy(entry_ids)})
        if self.failure:
            raise RuntimeError('DO_NOT_EXPOSE_REFERENCE_SOURCE_OR_CREDENTIAL_CANARY')
        if (offering_id != '2026:H0000:001:000' or type(year) is not int or year != 2026
                or entry_ids is not None and entry_ids != ['fixture:entry']):
            raise ValueError('DO_NOT_EXPOSE_INVALID_REFERENCE_DETAIL')
        return {'purpose':'reference_lookup','audience':'internal_research_workspace',
            'binding':{'manifest_sha256':'fixture:original-manifest'},
            'reference':{'offering':{'offering_id':offering_id},
                'entries':[{'id':'fixture:entry','value':'0','unit':'USD/day',
                    'qualifications':['Fictional INN qualification'],
                    'carrier_evidence':[{'pdf_page':7,'text_sha256':'f'*64}]}],
                'related_reference_entries':[{'id':'fixture:end-day','value':'5','unit':'day'}],
                'holds':[{'value':None,'state':'unknown_held','issue_id':'fixture:hold'}]},
            'authority':{'reference_lookup':{'state':'accepted_exact_subset'},
                         'published_display':{'state':'held'},'personal_comparison':{'state':'held'}}}


class ResearchHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.repository = FixtureRepository()
        cls.reference = FixtureReferenceAdapter()
        cls.server = build(0,fixture=True,database=Path(cls.temporary.name)/'fixture.sqlite3',
                           research_repository=cls.repository,reference_adapter=cls.reference)
        cls.thread = threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.temporary.cleanup()

    def request(self,path,payload=None,*,csrf=True,cookie=None,origin=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
        headers={'Origin':origin or f'http://127.0.0.1:{self.server.server_port}'}
        use_cookie=self.cookie if cookie is None else cookie
        if use_cookie:headers['Cookie']=use_cookie
        if payload is not None:
            headers['Content-Type']='application/json'
            if csrf:headers['X-Daylight-CSRF']=self.session['csrf']
        connection.request('POST' if payload is not None else 'GET',path,
                           json.dumps(payload) if payload is not None else None,headers)
        response=connection.getresponse();new_cookie=response.getheader('Set-Cookie')
        if new_cookie:self.cookie=new_cookie.split(';')[0]
        body=json.loads(response.read());status=response.status;connection.close();return status,body

    def setUp(self):
        self.cookie=None;self.repository.calls.clear();self.repository.failure=False;self.repository.on_read=None
        self.reference.calls.clear();self.reference.failure=False
        _,self.session=self.request('/api/guest/session')
        _,self.state=self.request('/api/conversation/initial')
        status,self.state=self.request('/api/conversation/turn',{
            'guide':self.state['guide'],'record':self.state['record'],
            'requestId':str(uuid.uuid4()),'action':{'type':'start'}})
        self.assertEqual(status,200,self.state)

    def review_payload(self,scope=None):
        return {'guide':copy.deepcopy(self.state['guide']),'record':copy.deepcopy(self.state['record']),
            'requestId':str(uuid.uuid4()),
            **({'continuation':self.state['continuation']} if self.state.get('continuation') else {}),
            **({'scope':copy.deepcopy(scope)} if scope is not None else {})}

    def test_guest_ownership_origin_and_csrf_precede_database_reads(self):
        self.assertEqual(self.request('/api/research/status',cookie='')[0],401)
        self.assertEqual(self.request('/api/research/status',origin='https://outside.invalid')[0],403)
        self.assertEqual(self.request('/api/research/query',{'operation':'list','scope':RESEARCH_SCOPE},csrf=False)[0],403)
        self.assertEqual(self.repository.calls,[])

    def test_exact_scope_and_no_sql_or_authority_fields(self):
        for scope in [{**RESEARCH_SCOPE,'year':2027},{**RESEARCH_SCOPE,'year':'2026'},
                      {**RESEARCH_SCOPE,'county_fips':'12011'}, {**RESEARCH_SCOPE,'authority':'permitted'}]:
            self.assertEqual(self.request('/api/research/query',{'operation':'list','scope':scope})[0],422)
        self.assertEqual(self.request('/api/research/query',{'operation':'list','scope':RESEARCH_SCOPE,'sql':'SELECT anything'})[0],422)
        self.assertEqual(self.repository.calls,[])

    def test_catalog_has_research_identity_but_no_consumer_authority(self):
        status,out=self.request('/api/research/query',{'operation':'list','scope':RESEARCH_SCOPE,'limit':20})
        self.assertEqual(status,200);self.assertEqual(out['total'],3)
        self.assertIsNone(out['binding']['accepted_release_id'])
        self.assertEqual(out['authority']['published_display']['state'],'held')

    def test_conditions_lineage_and_explicit_page_boundary_survive_http(self):
        status,out=self.request('/api/research/query',{'operation':'inspect','offering_id':'2026:H0000:001:000','expected_snapshot_id':'fixture:research-snapshot'})
        self.assertEqual(status,200);page=out['evidence_by_layer']['L03']
        self.assertTrue(page['has_more']);self.assertEqual(page['records'][0]['conditions']['root']['children'][1]['meaning'],'Fictional service exception')
        self.assertEqual(page['records'][0]['lineage']['artifact_sha256'],'f'*64)

    def test_snapshot_mismatch_does_not_fall_back_to_latest(self):
        status,out=self.request('/api/research/query',{'operation':'list','scope':RESEARCH_SCOPE,'expected_snapshot_id':'fixture:old'})
        self.assertEqual(status,422);self.assertNotIn('plans',out)

    def test_review_without_research_scope_does_not_query_database_or_model(self):
        status,out=self.request('/api/comparison/review',self.review_payload())
        self.assertEqual(status,200,out);self.assertEqual(self.repository.calls,[])
        self.assertIn('continuation',out);self.assertEqual(out['comparison']['research']['state'],'not_connected')
        self.assertTrue(all(p['state']=='held' for p in out['comparison']['authority'].values()))

    def test_review_preserves_the_resolved_pause_target_and_journal(self):
        owner=self.server.profiles.digest(self.cookie.split('=',1)[1])
        with self.server.adaptive.lock:
            entries=[entry for (entry_owner,_),entry in self.server.adaptive.turn_journal.items() if entry_owner==owner]
            entries[-1]['response']['assessment'].update(nextQuestion=None,intakePaused=True,conversationOpen=True)
            before=len(self.server.adaptive.turn_journal)
        status,out=self.request('/api/comparison/review',self.review_payload())
        self.assertEqual(status,200,out)
        self.assertNotIn('guide',out);self.assertNotIn('record',out);self.assertNotIn('assessment',out)
        self.assertIsNone(entries[-1]['response']['assessment']['nextQuestion'])
        self.assertTrue(entries[-1]['response']['assessment']['intakePaused'])
        self.assertTrue(entries[-1]['response']['assessment']['conversationOpen'])
        self.assertEqual(out['continuation'],self.state['continuation'])
        self.assertEqual(len(self.server.adaptive.turn_journal),before)

    def test_missing_trusted_snapshot_holds_review_without_refreshing(self):
        owner=self.server.profiles.digest(self.cookie.split('=',1)[1])
        with self.server.adaptive.lock:
            for (entry_owner,_),entry in self.server.adaptive.turn_journal.items():
                if entry_owner==owner:entry['expires']=0
        self.assertEqual(self.request('/api/comparison/review',self.review_payload(RESEARCH_SCOPE))[0],409)
        self.assertEqual(self.repository.calls,[])

    def test_scoped_review_connects_research_but_keeps_consumer_units_empty(self):
        status,out=self.request('/api/comparison/review',self.review_payload(RESEARCH_SCOPE))
        self.assertEqual(status,200,out);comparison=out['comparison']
        self.assertEqual(comparison['research']['retained_identity_count'],3)
        self.assertEqual(comparison['research']['consumer_evaluated_count'],0)
        self.assertEqual([unit['unit_id'] for unit in comparison['units']],['current-arrangement'])
        self.assertTrue(all(f['value'] is None for f in comparison['findings']))
        self.assertEqual(comparison['binding']['scope'],RESEARCH_SCOPE)

    def test_optional_repository_failure_preserves_current_continuation(self):
        self.repository.failure=True
        status,out=self.request('/api/comparison/review',self.review_payload(RESEARCH_SCOPE))
        self.assertEqual(status,200,out);self.assertEqual(out['comparison']['research']['state'],'unavailable')
        self.assertNotIn('DO_NOT_EXPOSE',json.dumps(out))
        status,next_out=self.request('/api/comparison/review',self.review_payload())
        self.assertEqual(status,200,next_out)

    def test_changed_head_during_research_read_suppresses_old_response(self):
        owner=self.server.profiles.digest(self.cookie.split('=',1)[1])
        def change_head():
            with self.server.adaptive.lock:self.server.adaptive.current_chain[owner]='fixture:changed-chain'
        self.repository.on_read=change_head
        status,out=self.request('/api/comparison/review',self.review_payload(RESEARCH_SCOPE))
        self.assertEqual(status,409);self.assertNotIn('comparison',out);self.assertNotIn('continuation',out)

    def test_same_head_newer_journal_response_suppresses_old_snapshot(self):
        owner=self.server.profiles.digest(self.cookie.split('=',1)[1])
        def new_response():
            with self.server.adaptive.lock:
                key=next(key for key in reversed(self.server.adaptive.turn_journal) if key[0]==owner)
                entry=copy.deepcopy(self.server.adaptive.turn_journal[key])
                entry['signature']='fixture:newer-resolved-response'
                entry['response']['assessment'].update(nextQuestion=None,intakePaused=True)
                self.server.adaptive.turn_journal[(owner,'fixture-new-response')]=entry
        self.repository.on_read=new_response
        status,out=self.request('/api/comparison/review',self.review_payload(RESEARCH_SCOPE))
        self.assertEqual(status,409);self.assertNotIn('comparison',out)

    def test_cached_privacy_choices_are_never_returned_over_current_choices(self):
        owner=self.server.profiles.digest(self.cookie.split('=',1)[1])
        with self.server.adaptive.lock:
            entry=next(entry for key,entry in reversed(list(self.server.adaptive.turn_journal.items())) if key[0]==owner)
            entry['response']['guide']['preferences'].update(saveGuide=True,saveSensitive=True)
        self.state['guide']['preferences'].update(saveGuide=False,saveSensitive=False)
        status,out=self.request('/api/comparison/review',self.review_payload())
        self.assertEqual(status,200,out);self.assertEqual(set(out),{'comparison','continuation'})
        self.assertFalse(self.state['guide']['preferences']['saveGuide'])
        self.assertFalse(self.state['guide']['preferences']['saveSensitive'])

    def test_foreign_or_invalid_continuation_cannot_trigger_research(self):
        payload=self.review_payload(RESEARCH_SCOPE);payload['continuation']='0'*32+'.'+'0'*64
        self.assertEqual(self.request('/api/comparison/review',payload)[0],409)
        self.assertEqual(self.repository.calls,[])

    def test_client_cannot_supply_new_derived_or_permission_fields(self):
        payload=self.review_payload();payload['authority']={'recommendation':'permitted'}
        self.assertEqual(self.request('/api/comparison/review',payload)[0],422)

    def test_scope_in_url_is_rejected_without_read(self):
        self.assertEqual(self.request('/api/research/status?year=2026')[0],422)
        self.assertEqual(self.repository.calls,[])

    def test_reference_guards_precede_original_verifier_or_database(self):
        payload={'operation':'reference','offering_id':'2026:H0000:001:000','year':2026}
        self.assertEqual(self.request('/api/research/query',payload,cookie='')[0],401)
        self.assertEqual(self.request('/api/research/query',payload,origin='https://outside.invalid')[0],403)
        self.assertEqual(self.request('/api/research/query',payload,csrf=False)[0],403)
        self.assertEqual(self.request('/api/research/query?research=true',payload)[0],422)
        self.assertEqual(self.reference.calls,[]);self.assertEqual(self.repository.calls,[])

    def test_reference_forwards_only_exact_args_and_preserves_original_payload(self):
        self.repository.failure=True
        before=copy.deepcopy(self.state)
        status,out=self.request('/api/research/query',{'operation':'reference',
            'offering_id':'2026:H0000:001:000','year':2026,'entry_ids':['fixture:entry']})
        self.assertEqual(status,200,out)
        self.assertEqual(self.reference.calls,[{'offering_id':'2026:H0000:001:000',
            'year':2026,'entry_ids':['fixture:entry']}])
        self.assertEqual(self.repository.calls,[])
        self.assertEqual(out['purpose'],'reference_lookup')
        self.assertEqual(out['reference']['entries'][0]['qualifications'],['Fictional INN qualification'])
        self.assertEqual(out['reference']['related_reference_entries'][0]['unit'],'day')
        self.assertIsNone(out['reference']['holds'][0]['value'])
        self.assertEqual(out['authority']['published_display']['state'],'held')
        self.assertEqual(out['authority']['personal_comparison']['state'],'held')
        self.assertNotIn('source_native_fields',out);self.assertNotIn('comparison',out)
        self.assertEqual(self.state,before)

    def test_reference_rejects_permissions_personal_inputs_and_native_db_overrides(self):
        forbidden={'research':True,'accepted':True,'authority':{'reference_lookup':'accepted'},
            'registry':'other','now':'2026-01-01','guide':{},'record':{},'profile':{},
            'source_native_fields':{'accepted':True},'sql':'SELECT anything',
            'scope':RESEARCH_SCOPE,'layers':['L03'],'expected_snapshot_id':'fixture:any',
            'binding':{'adapter':'injected'}}
        for name,value in forbidden.items():
            with self.subTest(name=name):
                status,out=self.request('/api/research/query',{'operation':'reference',
                    'offering_id':'2026:H0000:001:000','year':2026,name:value})
                self.assertEqual(status,422,out)
        self.assertEqual(self.reference.calls,[]);self.assertEqual(self.repository.calls,[])

    def test_reference_adapter_rejections_and_failure_stay_safe_without_research_fallback(self):
        for invalid in ({'year':2027},{'year':True},{'year':'2026'},
                        {'offering_id':'2026:H0000:999:000'},{'entry_ids':['fixture:held']}):
            with self.subTest(invalid=invalid):
                status,out=self.request('/api/research/query',{'operation':'reference',
                    'offering_id':'2026:H0000:001:000','year':2026,**invalid})
                self.assertEqual(status,422);self.assertNotIn('DO_NOT_EXPOSE',json.dumps(out))
                self.assertNotIn('reference',out)
        self.reference.failure=True
        calls=len(self.reference.calls)
        status,out=self.request('/api/research/query',{'operation':'reference',
            'offering_id':'2026:H0000:001:000','year':2026})
        self.assertEqual(status,503);self.assertNotIn('DO_NOT_EXPOSE',json.dumps(out))
        self.assertNotIn('reference',out);self.assertEqual(len(self.reference.calls),calls+1)
        self.assertEqual(self.repository.calls,[])


if __name__=='__main__':unittest.main()
