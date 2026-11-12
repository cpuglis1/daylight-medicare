"""D134 fictional source, profile and HTTP checks; no network model transport."""
import copy
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import test_http as support
import test_natural_flow as harness
from part_d_pilot import BUILD, published_plans
from part_d_profile import profile
from guest_profiles import ProfileError

SCOPE = {'zipcode':'34101','county_fips':'12021','year':2026}
ZIPS = {'34101':[['12021','Collier County','FL']]}


def field(value,basis='',money=False):
    return {'value':value,'state':'published','value_encoding':'integer_cents' if money else 'literal',
            'basis':basis,'raw':str(value),'unit':'USD/month' if money else None}


class FictionalRepository:
    def __init__(self):
        self.calls=[];self.fail=False;self.mutate=lambda x:x
    def query(self,body):
        self.calls.append(copy.deepcopy(body))
        if self.fail:raise RuntimeError('SOURCE_STOP')
        rows=[]
        for i in range(10):
            identifier=f'2026:S9000:{i:03d}:000'
            if body['kind']=='pdp_offering':
                fields={k:field(v,k) for k,v in {'year':2026,'plan_type':'PDP','plan_name':f'Fictional Drug Plan {i}','marketing_name':'Fictional Company','has_tier_without_deductible':'Yes','drug_benefit_type':'Basic'}.items()}
                fields.update({k:field(v,k,True) for k,v in {'total_premium':i*100,'annual_deductible':61500,'basic_premium':-2150,'supplemental_premium':2150+i*100}.items()})
                rows.append({'cms_offering_id':identifier,'region':'11','holds':[], 'artifact_sha256':'a'*64,
                    'payload':{'offering_id':identifier,'region':'11','state':'FL','fields':fields,
                    'source':{'member':'fictional.csv','record_ordinal':i+1}}})
            elif body['kind']=='pdp_restriction':
                rows.append({'cms_offering_id':identifier,'payload':{'checks':[{'as_of':'2026-10-25','result':'no_applicable_published_restriction_found','applicable_restriction_notices':[],'unresolved_restriction_questions':[]}]}})
        if body['kind']=='pdp_county':rows=[{'county_fips':'12021','region':'11'}]
        result={'build_id':BUILD,'next_after':None,'source_review_due':False,'personal_quote':False,
                'records':rows,'unresolved_checks':['SOURCE_USE_REVIEW_REQUIRED','METHOD_REVIEW_REQUIRED'],
                'source_policy':{'consumer_release':'held'}}
        return self.mutate(result)


class PartDSourceTests(unittest.TestCase):
    def test_all_plans_preserve_zero_negative_and_unknown_terms(self):
        repo=FictionalRepository();out=published_plans(repo,SCOPE,ZIPS)
        self.assertEqual(len(out['plans']),10);self.assertEqual(out['plans'][0]['fields']['total_premium']['value'],0)
        self.assertEqual(out['plans'][0]['fields']['basic_premium']['value'],-2150)
        self.assertFalse(out['personal_costs_available']);self.assertEqual(out['display_authorization'],'D134')
        self.assertIn('METHOD_REVIEW_REQUIRED',out['source_review_holds'])
        self.assertTrue(all(set(call)=={'reference_year','county_fips','intended_use','kind','page_size'} for call in repo.calls))
    def test_wrong_scope_and_personal_inputs_do_not_query_source(self):
        repo=FictionalRepository()
        for body in [{**SCOPE,'year':2027},{**SCOPE,'county_fips':'12099'}]:
            self.assertNotEqual(published_plans(repo,body,ZIPS)['status'],'published_plans')
        for body in [{**SCOPE,'age':75},{**SCOPE,'year':True},{**SCOPE,'zipcode':'00000'}, {**SCOPE,'medicines':'private'}]:
            with self.assertRaises(ProfileError):published_plans(repo,body,ZIPS)
        self.assertEqual(repo.calls,[])
    def test_partial_stopped_stale_wrong_build_and_population_fail_closed(self):
        for change in [lambda x:{**x,'build_id':'b'*64},lambda x:{**x,'source_review_due':True},
                       lambda x:{**x,'next_after':'cursor'},lambda x:{**x,'records':x['records'][:-1]}]:
            repo=FictionalRepository();repo.mutate=change
            with self.assertRaises(RuntimeError):published_plans(repo,SCOPE,ZIPS)
        repo=FictionalRepository();repo.fail=True
        with self.assertRaises(RuntimeError):published_plans(repo,SCOPE,ZIPS)
    def test_dated_restriction_claim_requires_its_actual_check(self):
        repo=FictionalRepository()
        def mutate(x):
            for row in x['records']:
                if 'checks' in row.get('payload',{}):row['payload']['checks']=[]
            return x
        repo.mutate=mutate
        out=published_plans(repo,SCOPE,ZIPS)
        self.assertIn('needs checking',out['plans'][0]['restriction_summary'])


class PartDProfileTests(unittest.TestCase):
    setUp=harness.NaturalFlowTests.setUp
    for name in ('payload','take','turn','choice'):
        locals()[name]=getattr(harness.NaturalFlowTests,name)
    def test_entry_asks_only_missing_location_then_reuses_medicines(self):
        out=self.turn({'type':'task','task':'drug_pricing','preparing':True},aiConsent=False)
        self.assertEqual(out['assessment']['nextQuestion']['id'],'RC01')
        self.choice('RC01',choice='self')
        self.assertEqual(self.flow.assess(self.g,self.r)['nextQuestion']['id'],'T03')
        self.choice('T03',zip='34101');self.choice('T07',text='Fictional medicine')
        out=profile(self.g,self.r);self.assertEqual(out['status'],'ready');self.assertEqual(out['inputs'],SCOPE)
        self.assertEqual(out['medicines'],'Fictional medicine');self.assertEqual(self.calls,[])
    def test_no_medigap_age_limit_and_reported_year_wins(self):
        self.choice('RC01',choice='self');self.choice('T03',zip='34101');self.choice('MG_AGE',choice='80')
        self.assertEqual(profile(self.g,self.r)['status'],'ready')
        self.choice('RC03',year='2027');self.assertEqual(profile(self.g,self.r)['status'],'unsupported')
        self.choice('RC03',year='2026');self.assertEqual(profile(self.g,self.r)['status'],'ready')
    def test_unknown_zip_is_not_reasked_or_used_for_prices(self):
        self.choice('RC01',choice='self')
        self.turn({'type':'task','task':'drug_pricing','preparing':True},aiConsent=False)
        self.turn({'type':'unknown','id':'T03'},aiConsent=False)
        out=self.turn({'type':'task','task':'drug_pricing','preparing':True},aiConsent=False)
        self.assertEqual(out['partDProfile']['status'],'missing');self.assertIn('T03',out['partDProfile']['held'])
        self.assertNotEqual((out['assessment']['nextQuestion'] or {}).get('id'),'T03')
    def test_conflicting_year_does_not_substitute_2026(self):
        self.choice('RC01',choice='self');self.choice('T03',zip='34101');self.choice('RC03',year='2026')
        self.choice('T04',choice='month',month='2027-01')
        self.assertIsNone(profile(self.g,self.r)['inputs']['year']);self.assertEqual(profile(self.g,self.r)['status'],'missing')
    def test_start_date_change_keeps_invalidated_year_open_until_reconfirmed(self):
        self.choice('RC01',choice='self');self.choice('T03',zip='34101');self.choice('RC03',year='2026')
        self.turn({'type':'edit','id':'T04'},aiConsent=False)
        self.turn({'type':'unknown','id':'T04'},aiConsent=False)
        self.assertIsNone(profile(self.g,self.r)['inputs']['year'])
        self.choice('RC03',year='2026')
        self.assertEqual(profile(self.g,self.r)['inputs']['year'],2026)
        self.assertEqual(profile(self.g,self.r)['status'],'ready')


class PartDHttpTests(unittest.TestCase):
    request=support.HttpTests.request
    turn=support.HttpTests.turn
    setUp=support.HttpTests.setUp
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.repository=FictionalRepository()
        cls.server=support.build(0,fixture=True,database=Path(cls.tmp.name)/'profiles.sqlite3',part_d_repository=cls.repository)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()
    def test_initial_profile_answers_and_scope_correction(self):
        self.assertEqual(self.state['partDProfile']['status'],'missing')
        self.turn({'type':'choice','id':'RC01','fields':{'choice':'self'}})
        self.turn({'type':'choice','id':'T03','fields':{'zip':'34101'}})
        code,out=self.request('/api/plans/part-d',self.state['partDProfile']['inputs'])
        self.assertEqual(code,200);self.assertEqual(len(out['plans']),10)
        self.assertNotIn('partDProfile',self.state['guide']);self.assertNotIn('plans',self.state['record'])
        self.turn({'type':'choice','id':'RC03','fields':{'year':'2027'}})
        self.assertEqual(self.state['partDProfile']['status'],'unsupported')
    def test_url_csrf_extra_input_and_unavailable_keep_fixed_errors(self):
        for url,body in [('/api/plans/part-d?zipcode=34101',SCOPE),('/api/plans/part-d',{**SCOPE,'medicines':'private'})]:
            self.assertEqual(self.request(url,body)[0],422)
        self.repository.fail=True
        try:
            code,out=self.request('/api/plans/part-d',SCOPE);self.assertEqual(code,503);self.assertNotIn('SOURCE_STOP',str(out))
        finally:self.repository.fail=False
        self.cookie=None
        self.assertIn(self.request('/api/plans/part-d',SCOPE)[0],(401,403))

if __name__=='__main__':unittest.main()
