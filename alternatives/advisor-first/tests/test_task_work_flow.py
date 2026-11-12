"""Current advisor journeys using injected scripted transport, no paid calls."""
import copy
import unittest

import test_curriculum_flow as support
from advisor_memory import CONTEXT_POLICY
from chat import ModelUnavailable
from task_work import VERSION


class TaskWorkFlowTests(unittest.TestCase):
    setUp = support.CurriculumFlowTests.setUp
    update = staticmethod(support.CurriculumFlowTests.update)
    payload = support.CurriculumFlowTests.payload
    take = support.CurriculumFlowTests.take
    turn = support.CurriculumFlowTests.turn
    message = support.CurriculumFlowTests.message
    stage_payloads = support.CurriculumFlowTests.stage_payloads
    extracted_context = support.CurriculumFlowTests.extracted_context
    composed_context = support.CurriculumFlowTests.composed_context
    extraction = staticmethod(support.CurriculumFlowTests.extraction)
    delivery = staticmethod(support.CurriculumFlowTests.delivery)
    education = staticmethod(support.CurriculumFlowTests.education)
    composition = support.CurriculumFlowTests.composition
    opening = support.CurriculumFlowTests.opening
    INSURANCE = support.CurriculumFlowTests.INSURANCE
    BENEFICIARY = support.CurriculumFlowTests.BENEFICIARY
    OPENING = support.CurriculumFlowTests.OPENING
    OVERVIEW = support.CurriculumFlowTests.OVERVIEW

    def work(self):
        return self.flow.memory.task_work(self.owner,self.flow.current_chain[self.owner],CONTEXT_POLICY)

    def provider_question(self):
        return self.message('Does this office take my insurance?',
            extraction=self.extraction(goal='Does this office take my insurance?'),
            compose={**self.composition(target=None,
                reply='The exact plan and office need checking before relying on coverage.',refs=['checks']),
                'task_work':{'check_ids':['coverage_identity','provider_identity','provider_participation'],
                             'blocking_concepts':[],'next_step':'prepare'}})

    def test_simple_opening_can_connect_checks_without_inventing_verified_results(self):
        out = self.provider_question()
        self.assertEqual(out['generated']['status'],'complete',out.get('generated'))
        self.assertEqual([row['check_id'] for row in out['task_work']['checks']],
            ['coverage_identity','provider_identity','provider_participation'])
        self.assertTrue(all(row['verification_state']=='not_verified' for row in out['task_work']['checks']))
        self.assertEqual(out['task_work']['completed_external_actions'],[])
        self.assertFalse(out['task_work']['task_resolved'])
        self.assertEqual(len(self.calls),2)
        sent = self.composed_context()['task_work']
        self.assertFalse(sent['external_actions_available'])
        self.assertNotIn('task_binding',str(sent))
        self.assertNotIn('task_work',out['guide'])
        self.assertNotIn('task_work',out['record'])

    def test_current_confusion_teaches_in_context_and_keeps_the_return_point(self):
        first = self.opening(role_known=True)
        pending = first['assessment']['nextQuestion']['id']
        quote = 'I do not understand Medicare Advantage.'
        out = self.message(quote, extraction=self.extraction(
            education_request={'kind':'clarify','concept_ids':['medicare_advantage'],'quote':quote}),
            compose={**self.composition(target=None,
                reply='Medicare Advantage provides Parts A and B through a private plan. Doctors, costs and rules vary by plan.',
                refs=['advantage'],education=self.education('clarify',[self.delivery(
                    'medicare_advantage',reason='clarify',refs=('advantage',))],'advantage')),
                'task_work':{'check_ids':['provider_participation'],'blocking_concepts':['medicare_advantage'],
                             'next_step':'teach'}})
        self.assertEqual(out['generated']['status'],'complete',out.get('generated'))
        self.assertEqual(out['task_work']['return_point'],pending)
        self.assertEqual(out['task_work']['teaching'],[{'concept_id':'medicare_advantage',
            'state':'explanation_delivered_not_comprehension'}])
        self.assertEqual(out['task_work']['checks'][0]['verification_state'],'not_verified')

    def test_free_local_lesson_preserves_work_and_visit_permission_without_new_generation(self):
        self.provider_question()
        before = copy.deepcopy(self.work())
        calls = len(self.calls)
        out = self.turn({'type':'read_concept','id':'costs'},aiConsent=False,contextPolicy=None)
        self.assertEqual(self.work(),before)
        self.assertEqual(len(self.calls),calls)
        self.assertEqual([row['check_id'] for row in out['task_work']['checks']],before['selection']['check_ids'])

    def test_failed_turn_keeps_open_work_but_does_not_issue_a_fresh_result(self):
        self.provider_question()
        before = copy.deepcopy(self.work())
        out = self.message('Please continue.',extraction=self.extraction(),
                           compose=ModelUnavailable('Synthetic failure'))
        self.assertEqual(out['generated']['status'],'unavailable')
        self.assertNotIn('task_work',out)
        self.assertEqual(self.work(),before)

    def test_callback_or_contact_fabrication_is_rejected_without_paid_retry(self):
        for reply in ('I called the office.',"I'll get back to you tomorrow."):
            with self.subTest(reply=reply):
                before = len(self.calls)
                out = self.message('Can you help?',extraction=self.extraction(),
                    compose=self.composition(target=None,reply=reply))
                self.assertEqual(out['generated']['status'],'unavailable')
                self.assertEqual(out['generated']['code'],'unsupported_finding')
                self.assertNotIn('task_work',out)
                self.assertEqual(len(self.calls)-before,2)

    def test_existing_authorized_preparation_is_an_actual_local_receipt_only(self):
        self.provider_question()
        review = self.turn({'type':'review_preparation'},aiConsent=False,contextPolicy=None)
        out = self.turn({'type':'run_preparation','token':review['review']['token']},
                        aiConsent=False,contextPolicy=None)
        self.assertEqual(out['preparation']['status'],'prepared')
        self.assertEqual(out['task_work']['outcome'],'preparation_completed')
        self.assertEqual(out['task_work']['local_operation']['receipt_ref'],out['preparation']['id'])
        self.assertFalse(out['task_work']['task_resolved'])
        self.assertEqual(out['task_work']['completed_external_actions'],[])

    def test_same_request_replay_preserves_current_work_and_historical_replay_suppresses_it(self):
        text = 'Does this office take my insurance?'
        self.extractions.append(self.extraction(goal=text))
        self.compositions.append({**self.composition(target=None,reply='We can prepare the specific checks.'),
            'task_work':{'check_ids':['provider_participation'],'blocking_concepts':[],'next_step':'prepare'}})
        payload = self.payload({'type':'message','message':text})
        out = self.take(payload)
        calls = len(self.calls)
        replay = self.flow.turn(self.owner,copy.deepcopy(payload))
        self.assertEqual(replay['task_work'],out['task_work'])
        self.assertEqual(len(self.calls),calls)
        self.turn({'type':'read_concept','id':'costs'},aiConsent=False,contextPolicy=None)
        historical = self.flow.turn(self.owner,copy.deepcopy(payload))
        self.assertNotIn('task_work',historical)
        self.assertEqual(len(self.calls),calls)

    def test_agent_cannot_write_completed_finding_metadata(self):
        out = self.message('Can you help?',extraction=self.extraction(),
            compose={**self.composition(target=None,reply='We can work through the specific checks.'),
                'task_work':{'check_ids':['provider_participation'],'blocking_concepts':[],
                             'next_step':'answer','verified':True}})
        self.assertEqual(out['generated']['status'],'complete',out.get('generated'))
        self.assertEqual(out['task_work']['supported_findings'],[])
        self.assertFalse(out['task_work']['task_resolved'])
        self.assertEqual(out['task_work']['checks'],[])


if __name__ == '__main__':
    unittest.main()
