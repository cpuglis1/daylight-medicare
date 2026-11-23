"""D154: one ordinary visit reaches both checks; no model/network calls."""
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from unittest import TestCase

import test_http as support
from demo_server import REPO, build_demo
from daylight_data.serving.part_d_local import local_candidate
from daylight_data.serving.pilot_doctors import PilotDoctors


class ConversationCheckTests(TestCase):
    request = support.HttpTests.request
    setUp = support.HttpTests.setUp
    turn = support.HttpTests.turn

    @classmethod
    def setUpClass(cls):
        stack = cls.enterClassContext(ExitStack())
        scratch = stack.enter_context(TemporaryDirectory())
        cls.drugs = local_candidate(REPO)
        cls.doctors = PilotDoctors(cls.drugs.foundation)
        cls.server = stack.enter_context(build_demo(0, fixture=True,
            database=Path(scratch) / 'guest.sqlite3', doctor_service=cls.doctors,
            conversation_checks=True, prescription_service=cls.drugs))
        Thread(target=cls.server.serve_forever, daemon=True).start()
        stack.callback(cls.server.shutdown)

    def choice(self, identifier, *, entity=None, **fields):
        return self.turn({'type':'choice', 'id':identifier, 'fields':fields,
                          **({'entity':entity} if entity else {})})

    def scope(self, task='compare'):
        self.turn({'type':'task', 'task':task, 'preparing':True})
        self.choice('RC01', choice='self')
        self.choice('T03', zip='34102')
        self.choice('RC03', year='2026')

    def answer(self, field, value):
        question = self.state['conversationCheck']['question']
        self.assertEqual(question['field'], field, question)
        return self.turn({'type':'check_answer', 'token':question['token'], 'value':value})

    def test_doctor_report_enters_the_next_question_without_a_launcher(self):
        self.scope()
        self.choice('T06', text='Jovan Baker')
        if self.state['conversationCheck']['question']['field']=='doctor_location':
            self.answer('doctor_location','Bonita Springs')
        question = self.state['conversationCheck']['question']
        self.assertEqual(question['field'], 'doctor')
        self.assertNotIn('name', question['question'].lower())
        self.assertTrue(question['choices'])
        self.answer('doctor', question['choices'][0]['value'])
        question = self.state['conversationCheck']['question']
        if question:
            self.answer('office', question['choices'][0]['value'])
        result = self.state['conversationCheck']['results'][0]
        self.assertEqual(result['kind'], 'doctor_matrix')
        self.assertEqual(len(result['plans']), 72)
        self.assertTrue(any(plan['state'] == 'unknown' for plan in result['plans'].values()))
        self.assertNotIn((self.state['assessment']['nextQuestion'] or {}).get('id'), ['T06','RC21'])
        self.assertFalse(self.state['consumerReady'] if 'consumerReady' in self.state else False)
        self.turn({'type':'refresh'})
        self.assertTrue(self.state['conversationCheck']['results'])
        from unittest.mock import patch
        from daylight_data.serving.binding import ResearchServingError
        with patch.object(self.doctors,'network_matrix',side_effect=ResearchServingError('PILOT_SOURCE_STOP')):
            status,view=self.request('/api/conversation/checks',{'continuation':self.state['continuation']})
            self.assertEqual(status,200)
            self.assertFalse(view['results'])
            self.assertEqual(view['question']['field'],'doctor_retry')
        self.turn({'type':'check_edit','key':'doctor:doctor-1','field':'office'})
        self.assertEqual(self.state['conversationCheck']['results'][0]['kind'], 'doctor_matrix')

    def test_drug_reports_check_all_plans_and_withdraw_on_correction(self):
        self.scope('drug_pricing')
        self.choice('T07', text='Metformin')
        self.choice('RC22', entity='medicine-1', name='Metformin', strength='500 mg', form='tablet')
        self.choice('RC23', entity='medicine-1', quantity='30 tablets', daysSupply='30',
                    pharmacy='Publix, Naples, FL 34102', channel='retail')
        self.choice('RC18', choice='none')
        self.answer('formulary_product', '861007')
        result = self.state['conversationCheck']['results'][0]
        self.assertEqual(result['kind'], 'formulary')
        self.assertEqual(len(result['plans']), 71)
        self.assertEqual(sum(plan.startswith('2026:S') for plan in result['plans']), 10)
        medicine = result['plans']['2026:S5884:105:000']['medicines'][0]
        self.assertEqual((medicine['rxcui'], medicine['state'], medicine['evidence_date']),
                         ('861007', 'covered', '2026-09-16'))
        scope = {'inputs': self.state['recommendationInputs'], 'continuation': self.state['continuation']}
        status, sorted_plans = self.request('/api/recommendation', scope)
        self.assertEqual(status, 200, sorted_plans)
        pdp = sorted_plans['part_d']
        fit = next(c for c in pdp['plans']['2026:S5884:105:000']['checks'] if c['id'] == 'medicines')
        self.assertEqual(fit['state'], 'met')
        self.assertEqual(pdp['recommended_ids'], [])
        self.assertFalse(result['participant_release'])
        from unittest.mock import patch
        from daylight_data.serving.binding import ResearchServingError
        with patch.object(self.drugs,'_scope',side_effect=ResearchServingError('PILOT_EVIDENCE_STALE')):
            status,view=self.request('/api/conversation/checks',{'continuation':self.state['continuation']})
            self.assertEqual(status,200)
            self.assertFalse(view['results'])
        self.turn({'type':'refresh'})
        self.turn({'type':'check_edit','key':'formulary','field':'products'})
        self.assertFalse(self.state['conversationCheck']['results'])
        self.assertEqual(self.state['conversationCheck']['question']['field'],'formulary_product')
        current = {'inputs': self.state['recommendationInputs'], 'continuation': self.state['continuation']}
        status, sorted_plans = self.request('/api/recommendation', current)
        self.assertEqual(status, 200, sorted_plans)
        fit = next(c for c in sorted_plans['part_d']['plans']['2026:S5884:105:000']['checks']
                   if c['id'] == 'medicines')
        self.assertEqual(fit['state'], 'unknown')

    def test_unknown_and_later_do_not_loop_or_become_negative_evidence(self):
        self.scope()
        self.choice('T06', text='Jovan Baker')
        self.answer(self.state['conversationCheck']['question']['field'], '__later__')
        self.assertIsNone(self.state['conversationCheck']['question'])
        self.choice('T10', choice='total_cost')
        self.assertIsNone(self.state['conversationCheck']['question'])
        self.assertFalse(self.state['conversationCheck']['results'])

    def test_foreign_or_old_question_cannot_choose_an_identity(self):
        self.scope()
        self.choice('T06', text='Jovan Baker')
        if self.state['conversationCheck']['question']['field']=='doctor_location':
            self.answer('doctor_location','Bonita Springs')
        old = deepcopy(self.state['conversationCheck']['question'])
        self.choice('T06', text='Mark Speake')
        import uuid
        body = {'guide':self.state['guide'], 'record':self.state['record'],
                'continuation':self.state['continuation'], 'requestId':str(uuid.uuid4()),
                'action':{'type':'check_answer', 'token':old['token'], 'value':old['choices'][0]['value']}}
        self.assertEqual(self.request('/api/conversation/turn', body)[0], 409)

    def test_known_doctor_city_reuses_report_and_back_restores_exact_choice(self):
        self.scope()
        self.choice('T06', text='Jovan Baker')
        self.choice('RC21',entity='doctor-1',city='Bonita Springs')
        question=self.state['conversationCheck']['question']
        self.assertEqual(question['field'],'doctor')
        self.assertNotIn('What city',question['question'])
        _,view=self.request('/api/conversation/checks',{'continuation':self.state['continuation']})
        self.assertEqual(view['question']['token'],question['token'])
        self.answer('doctor',question['choices'][0]['value'])
        question = self.state['conversationCheck']['question']
        self.assertTrue(question and question['field'] == 'office' or self.state['conversationCheck']['results'])
        self.turn({'type':'check_back'})
        self.assertEqual(self.state['conversationCheck']['question']['field'],'doctor')
        self.assertFalse(self.state['conversationCheck']['results'])
        other=type(self)(methodName='test_known_doctor_city_reuses_report_and_back_restores_exact_choice')
        other.setUp()
        self.assertEqual(other.request('/api/conversation/checks',{'continuation':self.state['continuation']})[0],409)

