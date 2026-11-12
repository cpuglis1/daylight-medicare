"""Complete catalog ordering, stateless live tool use, and credential handling."""

import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import cms_slice as cms
from chat import Chat, ResponsesClient, ModelUnavailable
from demo_tools import DemoTools
from live_conversation import LiveConversation
from naples_catalog import NaplesCatalog
from runtime_env import load_model_env
from research_http import make_research_test_server as make_server

INTAKE = {'recipient':'self','zip':'34102','medicare':'yes','drugs':'yes','hearing':'no','vision':'yes','dental':'yes'}

def response(value):
    return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(value)}]}]}

def tool(name,args):
    return {'output':[{'type':'function_call','name':name,'call_id':'public-test-call','arguments':json.dumps(args)}]}

def reply(**kwargs):
    return response({'reply':'Let’s look at the captured information.','question':'What would you like to explore next?','fact_ids':[], 'quick_replies':[], 'state_update':{}, **kwargs})


class NaplesMVPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools=DemoTools(research_mode=True)
        cls.catalog=NaplesCatalog(cls.tools)

    def client(self,outputs,payloads=None):
        iterator=iter(outputs)
        def transport(payload):
            if payloads is not None: payloads.append(copy.deepcopy(payload))
            return next(iterator,outputs[-1])
        return ResponsesClient(key='test-never-a-real-key',model='test-model',transport=transport)

    def test_all_70_are_present_and_restricted_plans_are_not_silently_omitted(self):
        result=self.catalog.list()
        self.assertEqual(result['count'],70)
        self.assertEqual(result['counts'],{'SNP':27,'MA-PD':23,'MA':9,'PDP':11})
        self.assertEqual({p['id'] for p in result['plans']},set(self.catalog.rows))
        self.assertTrue(all(p['eligibility']=='restricted_unconfirmed' for p in result['plans'] if p['category']=='SNP'))
        self.assertEqual(sum(p['benefit_validation']=='selected_fields_checked' for p in result['plans']),38)

    def test_pdp_monthly_price_order_is_numeric_complete_and_stable(self):
        result=self.catalog.list('PDP',['monthly_premium'])
        self.assertEqual(result['count'],11)
        values=[p['metrics']['monthly_premium']['value_cents'] for p in result['plans']]
        self.assertEqual(values,sorted(values))
        self.assertEqual(values[0],530)
        self.assertFalse(result['suitability_ranked'])

    def test_multiple_priorities_are_applied_in_the_explicit_order(self):
        result=self.catalog.list('MA-PD',['medical_limit','monthly_premium'])
        keys=[(p['metrics']['medical_limit']['value_cents'],p['metrics']['monthly_premium']['value_cents'],p['id']) for p in result['plans']]
        self.assertEqual(keys,sorted(keys))
        self.assertEqual(result['scored_criteria'],['medical_limit','monthly_premium'])

    def test_missing_values_and_source_conflicts_are_not_zeroes(self):
        result=self.catalog.list(priorities=['monthly_premium'])
        conflicts=[p for p in result['plans'] if p['premium_source_conflict']]
        self.assertTrue(conflicts)
        self.assertTrue(all(p['premium_source_conflict'] for p in result['plans'][-len(conflicts):]))
        pdp=self.catalog.list('PDP',['medical_limit'])
        self.assertTrue(all(p['metrics']['medical_limit']['value_cents'] is None for p in pdp['plans']))

    def test_unavailable_personal_priorities_are_explicitly_unscored(self):
        result=self.catalog.list(priorities=['doctors','dental','annual_cost'])
        self.assertEqual(result['unscored_priorities'],['doctors','dental','annual_cost'])
        self.assertEqual(result['scored_criteria'],[])
        self.assertEqual([p['id'] for p in result['plans']],sorted(self.catalog.rows))

    def test_compensation_metadata_cannot_change_order(self):
        before=[p['id'] for p in self.catalog.list(priorities=['monthly_premium'])['plans']]
        changed=copy.deepcopy(self.tools.snapshot)
        for index,row in enumerate(changed['options']+changed['exclusions']): row['commission']=index*1000000
        with patch.object(self.tools,'snapshot',changed):
            after=[p['id'] for p in NaplesCatalog(self.tools).list(priorities=['monthly_premium'])['plans']]
        self.assertEqual(before,after)

    def test_compare_keeps_exact_selected_ids_and_notes(self):
        ids=['S5904-001-000-2027','H0710-010-000-2027']
        result=self.catalog.compare(ids)
        self.assertEqual([p['id'] for p in result['plans']],sorted(ids))
        self.assertTrue(result['plans'][0]['notes'])
        with self.assertRaises(cms.SourceError): self.catalog.compare([ids[0],ids[0]])

    def test_real_model_contract_accepts_natural_words_and_keeps_history_stateless(self):
        payloads=[]
        live=LiveConversation(Chat(self.tools,self.client([reply(reply='You mentioned both doctors and prescriptions. We can look at each in turn.', question='Which doctors or hospitals do you want to keep?')],payloads)))
        history=[{'role':'user','content':'I take metformin and want to keep my doctor.'}]
        result=live.answer(INTAKE,history,'I would like to start with doctors')
        self.assertEqual(result['conversation_mode'],'live')
        self.assertTrue(result['model_request_completed'])
        self.assertIn('doctors or hospitals',result['question'])
        self.assertFalse(payloads[0]['store'])
        self.assertNotIn('conversation',payloads[0])
        self.assertNotIn('previous_response_id',payloads[0])
        self.assertEqual(payloads[0]['input'][1],history[0])
        self.assertEqual(json.loads(payloads[0]['input'][0]['content'])['state']['coverage_context']['zip'],'34102')

    def test_model_catalog_is_rendered_in_full_engine_order(self):
        outputs=[tool('catalog',{'category':'PDP','priorities':['monthly_premium']}),reply()]
        result=LiveConversation(Chat(self.tools,self.client(outputs))).answer(INTAKE,message='Show drug plans by monthly premium')
        self.assertEqual(result['tool_calls'],['catalog'])
        self.assertEqual(result['catalogs'][0]['count'],11)
        self.assertEqual([p['id'] for p in result['catalogs'][0]['plans']],[p['id'] for p in self.catalog.list('PDP',['monthly_premium'])['plans']])

    def test_model_cannot_invent_product_identity_plan_selection_or_fact_id(self):
        cases=[tool('drug_evidence',{'rxcui':'1551300','plan_ids':None,'pharmacy_npi':None}),tool('catalog_plan',{'plan_id':'H5434-002-000-2027'}),tool('medicine_candidates',{'name':'Eliquis'}),reply(fact_ids=['invented-fact'])]
        for output in cases:
            result=LiveConversation(Chat(self.tools,self.client([output]))).answer(INTAKE,message='Help me compare coverage')
            self.assertTrue(result['fallback'])

    def test_model_prices_are_rendered_from_records_instead_of_free_prose(self):
        self.assertTrue(LiveConversation(Chat(self.tools,self.client([reply(reply='Your personal cost is $0.')]))).answer(INTAKE,message='How much would I pay?')['fallback'])

    def test_model_failure_does_not_masquerade_as_live_chat(self):
        with self.assertRaises(ModelUnavailable): LiveConversation(Chat(self.tools,ResponsesClient(key='',model=''))).answer(INTAKE)
        self.assertTrue(LiveConversation(Chat(self.tools,self.client([{'status':'incomplete','output':[]}]))).answer(INTAKE)['fallback'])

    def test_only_model_settings_are_loaded_without_shell_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            env=Path(directory)/'.env'
            env.write_text('OPENAI_API_KEY="test-value"\nOPENAI_MODEL=test-model\nUNRELATED_SECRET=ignore\nCOMMAND=$(touch should-not-exist)\n')
            with patch.dict(os.environ,{},clear=True):
                state=load_model_env(env)
                self.assertEqual(state,{'OPENAI_API_KEY':True,'OPENAI_MODEL':True})
                self.assertEqual(set(os.environ),{'OPENAI_API_KEY','OPENAI_MODEL'})
            self.assertFalse((Path(directory)/'should-not-exist').exists())

    def test_http_complete_catalog_comparison_and_live_unavailable_are_explicit(self):
        server=make_server(Chat(self.tools,ResponsesClient(key='',model='')),0)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        def post(path,value,origin=None):
            headers={'Content-Type':'application/json'}
            if origin: headers['Origin']=origin
            request=Request(base+path,data=json.dumps(value).encode(),headers=headers)
            try:
                with urlopen(request) as r: return r.status,json.load(r)
            except HTTPError as error:
                with error: return error.code,json.load(error)
        try:
            code,catalog=post('/api/catalog',{'category':'all','priorities':['monthly_premium']})
            self.assertEqual((code,catalog['count']),(200,70))
            code,comparison=post('/api/catalog',{'action':'compare','plan_ids':['S4802-083-000-2027','S4802-146-000-2027']})
            self.assertEqual((code,comparison['count']),(200,2))
            self.assertEqual(post('/api/live-chat',{'message':'','intake':INTAKE})[0],503)
            self.assertEqual(post('/api/catalog',{},'https://untrusted.example')[0],403)
            self.assertEqual(post('/api/catalog',{'year':'2028'})[0],422)
        finally:
            server.shutdown();server.server_close();thread.join()


if __name__=='__main__': unittest.main()
