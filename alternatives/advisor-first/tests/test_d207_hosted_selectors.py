"""Hosted fictional HTTP journey: selectors must not depend on a pricing task."""
import functools
import json
import uuid
from unittest import TestCase
from unittest.mock import patch
import test_hosted_history as base
from hosted_server import build_hosted
from test_conversation_checks_ux import Directory, candidate
import conversation_planner as planner


class Drugs:
    def _scope(self): return None
    def products(self, offering_ids, *, name):
        return [{'rxcui':str(900000+i),'name':f'Fictional medicine {i} mg oral tablet',
                 'type':'SCD','route':'oral','strength_description':f'{i} mg','form':'tablet'} for i in range(1,10)]
    def formulary_matrix(self, medicines):
        return {'2026:S0000:001:000': {'name':'Fictional plan','medicines':[
            {**m,'state':'unknown','evidence_date':'2026-11-01'} for m in medicines]}}


class HostedSelectors(TestCase):
    setUp, app, join = base.HostedTests.setUp, base.HostedTests.app, base.HostedTests.join

    def start(self):
        self.directory=Directory(lambda _: [candidate(str(i),f'Fictional Doctor {i}') for i in range(9)])
        with patch.object(base,'build_hosted',functools.partial(build_hosted,checks=(self.directory,Drugs()),demo_policy='accelerator')):
            self.service=self.app(base.MemoryHistory())
        self.cookies,self.csrf=self.join(self.service)
        _,raw,_=base.request(self.service,'/api/conversation/initial',cookies=self.cookies)
        self.state=json.loads(raw)
        self.turn({'type':'task','task':'timing','preparing':True})
        self.choice('RC01',choice='self')

    def turn(self, action):
        p={k:self.state[k] for k in ('guide','record','continuation') if k in self.state}
        code,raw,_=base.request(self.service,'/api/conversation/turn',
            {**p,'requestId':str(uuid.uuid4()),'action':action},self.cookies,self.csrf)
        self.assertEqual(code,200,raw)
        self.state=json.loads(raw);return self.state

    def choice(self, identifier, **fields):
        return self.turn({'type':'choice','id':identifier,'fields':fields})

    def test_timing_journey_reaches_doctors_then_medicine_strength_choices(self):
        self.start()
        _,raw,_=base.request(self.service,'/',cookies=self.cookies)
        self.assertIn(b'/conversation-checks.js',raw)
        self.assertEqual(base.request(self.service,'/conversation-checks.js',cookies=self.cookies)[0],200)
        self.choice('T06',text='Fictional Doctor in Naples')
        self.choice('T07',text='Fictional medicine')
        self.assertFalse(self.state['conversationCheck']['question']) # geography still missing
        self.choice('T03',zip='34102')
        self.assertEqual(planner.state(self.service.adaptive,next(iter(self.service.adaptive.current_chain)))['active_task'],'timing')
        q=self.state['conversationCheck']['question']
        self.assertIsNotNone(q)
        self.assertEqual(q['field'],'doctor')
        self.assertGreater(len(q['choices']),8)
        self.assertEqual(self.state['conversationNext'],{'kind':'action','action':'check'})
        self.turn({'type':'check_answer','token':q['token'],'value':'__later__'})
        q=self.state['conversationCheck']['question']
        self.assertEqual(q['field'],'formulary_product')
        self.assertEqual(len(q['choices']),9)
        self.assertIn('mg oral tablet',q['choices'][0]['label'])
        self.turn({'type':'check_answer','token':q['token'],'value':q['choices'][0]['value']})
        self.assertTrue(any(r['kind']=='formulary' for r in self.state['conversationCheck']['results']))
        self.assertNotEqual(self.state['conversationCheck']['question'],q)

    def test_discussion_detour_pause_and_finish_do_not_trigger_checks(self):
        self.start();self.choice('T03',zip='34102');self.choice('T06',text='Fictional Doctor in Naples')
        flow=self.service.adaptive;owner=next(iter(flow.current_chain))
        s=planner.state(flow,owner)
        self.assertTrue(planner.checks_relevant(flow,owner,self.state['guide']))
        for mode in ('discuss','detour','pause'):
            s['guidance']['mode']=mode
            self.assertFalse(planner.checks_relevant(flow,owner,self.state['guide']))
        s['guidance']['mode']='work';s['finish_requested']='later'
        self.assertFalse(planner.checks_relevant(flow,owner,self.state['guide']))

import test_pending_questions as pending
from conversation_checks import ConversationChecks

class SpokenSelectors(pending.PendingBase):
    def test_reported_doctor_in_timing_turn_has_one_delivered_selector(self):
        self.choice('RC01',choice='self');self.choice('T03',zip='34102')
        directory=Directory(lambda _: [candidate(str(i),f'Fictional Doctor {i}') for i in range(9)])
        self.flow.conversation_checks=ConversationChecks(self.flow,directory,Drugs(),lambda:[])
        out=self.say('My doctor is Fictional Doctor in Naples.',
            updates=[self.update('T06',{'text':'Fictional Doctor in Naples'},'Fictional Doctor in Naples')],
            targets=['T07'],task='timing',disposition='none')
        self.assertEqual(out['conversationCheck']['question']['field'],'doctor')
        self.assertTrue(planner.valid_delivered_next(out))
        self.assertEqual(out['conversationNext'],{'kind':'action','action':'check'})
        self.assertTrue(directory.queries)
        out=self.say('What does a provider network mean?',mode='detour',task='timing',targets=[],disposition='detour')
        self.assertIsNone(out['conversationCheck']['question'])
