"""D172: real planner/controller with fictional transport; network forbidden."""
import copy
import unittest
import test_conversation_planner as harness
from chat import ModelUnavailable
import conversation_planner as planner
import conversation_tasks
import test_semantic_guidance as semantic


class GuidedDirection(unittest.TestCase):
    for name in ('payload', 'take', 'turn', 'message', 'choice', 'task',
                 'stage_payloads', 'extracted_context', 'composed_context'):
        locals()[name] = getattr(harness.ConversationPlannerTests, name)
    setUp = semantic.SemanticGuidance.setUp
    ask = semantic.SemanticGuidance.ask
    interpreted = semantic.SemanticGuidance.interpreted

    def timing(self, text, **extra):
        return self.message(text, extraction=self.interpreted(text,task="timing",checks=["payer_order","job_loss","drug_gap","coverage_change"]), **extra)
    update = staticmethod(harness.ConversationPlannerTests.update)
    extraction = staticmethod(harness.ConversationPlannerTests.extraction)

    def job_context(self):
        self.choice('RC01', choice='self')
        self.choice('T05', choice='employer')
        self.choice('RC09', choice='my_job')

    def retirement_learning(self):
        text = 'I am retiring next week. Explain the two coverage paths.'
        return self.ask(text,mode='suggest',task='timing',focus='coverage_paths',situation_proposals=[dict(
            kind='retirement', subject='beneficiary', scope='current', quote=text,
            uncertain=False, correction=False, month=None, year=None, status='retiring', when='next week')])

    def test_learning_retirement_offer_then_short_acceptance_starts_forms(self):
        self.job_context()
        out = self.retirement_learning()
        self.assertEqual(out['generated']['status'], 'complete', out.get('generated'))
        q = out['assessment']['nextQuestion']
        self.assertIsNone(q)
        self.assertEqual(out['conversationPlanner']['suggested_task'],'timing')
        out = self.timing('Yes please.')
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'RC04')
        self.assertTrue(out['assessment']['nextQuestion']['choices'])
        self.assertNotIn('signup_route', [c['kind'] for c in out.get('cards', [])])
        self.assertEqual(out['coveragePath']['state'], 'undecided')

    def test_explicit_timing_reuses_reports_and_keeps_unknown_end_separate(self):
        self.job_context()
        self.choice('RC04', choice='neither')
        self.choice('RC11', jobEnd='2026-11-20')
        out = self.timing('Settle on timing!')
        q = out['assessment']['nextQuestion']
        self.assertEqual(q['id'], 'RC11')
        self.assertEqual([f['key'] for f in q['fields']], ['coverageEnd'])
        self.assertEqual(out['coveragePath']['state'], 'undecided')
        out = self.turn({'type':'unknown','id':'RC11'}, aiConsent=False)
        self.assertNotEqual((out['assessment'].get('nextQuestion') or {}).get('id'), 'RC11')
        self.assertEqual(self.flow.report(self.r, 'RC11')['jobEnd'], '2026-11-20')

    def test_failure_keeps_practical_question_and_one_prompt(self):
        self.job_context()
        out = self.timing('Work through my Medicare timing', compose=ModelUnavailable('Offline declared failure'))
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'RC04')
        self.assertEqual(out['conversationPlanner']['answer_state'], 'unresolved')
        self.assertNotIn('rephrase', str(out['assessment']['nextQuestion']))
        self.assertNotIn('What would you like to understand next?', out['reply'])

    def test_valid_answer_with_recovered_question_is_not_failed_answer(self):
        self.job_context()
        out = self.timing('Work through my Medicare timing', compose={
            'reply':'We can work through your timing together.', 'question_target':None, 'question':''})
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'RC04')
        self.assertNotEqual(out['conversationPlanner']['answer_state'], 'unresolved')

    def test_presenting_a_question_does_not_count_as_answering_it(self):
        self.job_context()
        for _ in range(2):
            out = self.timing('Work through my Medicare timing', compose=ModelUnavailable('Offline declared failure'))
            self.assertEqual(out['assessment']['nextQuestion']['id'], 'RC04')
            self.assertFalse(self.flow.report(self.r,'RC04'))
        out = self.timing('Work through my Medicare timing', compose=ModelUnavailable('Offline declared failure'))
        self.assertNotEqual((out['assessment'].get('nextQuestion') or {}).get('id'),'RC04')
        self.assertFalse(self.flow.report(self.r,'RC04'))
        self.assertTrue(any(row['question_id']=='RC04' and row['state']=='parked' for row in out['questionProgress']))

    def test_generic_model_followup_cannot_displace_requested_work(self):
        self.job_context()
        out = self.timing('Settle on timing!', compose={
            'reply':'We can work through the timing together.', 'question_target':None,
            'question':'What would help you make your next decision?'})
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'RC04')
        self.assertNotIn('What would help you make your next decision?', out['reply'])

    def test_learning_instead_respects_direction_and_explicit_later_restart(self):
        self.job_context()
        self.retirement_learning()
        out = self.ask('Keep explaining my coverage options',mode='discuss')
        self.assertIsNone(out['assessment']['nextQuestion'])
        out = self.timing('Work out my timing now.')
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'RC04')

    def test_timing_preview_preserves_engine_branches_and_does_not_mutate(self):
        self.job_context()
        self.choice('RC06', choice='disability')
        before = copy.deepcopy((self.g, self.r))
        moves = conversation_tasks.candidates(self.flow,self.g,self.r,'timing',['payer_order','job_loss'])
        size = next(c for c in moves if c['id'] == 'RC10')['question']
        self.assertIn('100', size['question'])
        self.assertEqual((self.g, self.r), before)
        self.choice('RC09', choice='cobra')
        self.assertNotIn('RC10', [c['id'] for c in conversation_tasks.candidates(self.flow,self.g,self.r,'timing',['payer_order','job_loss'])])

    def test_concept_detour_keeps_timing_task_for_the_next_report(self):
        self.job_context()
        self.timing('Work out my timing.')
        text = 'What is Original Medicare?'
        self.message(text, extraction=self.extraction(discussion=harness.ConversationPlannerTests.proposal(
            text, focus='original', question_quote=text)))
        text = 'I have neither Part A nor Part B.'
        out = self.ask(text,task='timing',checks=['payer_order','job_loss'],
            updates=[self.update('RC04', {'choice':'neither'}, text)],target='RC11')
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'RC11')
        self.assertEqual(out['coveragePath']['state'], 'undecided')

    def test_education_only_has_no_personal_intake(self):
        self.job_context()
        out = self.ask('Just explain enrollment timing. I am not ready to give personal details.',mode='discuss')
        self.assertIsNone(out['assessment']['nextQuestion'])

    def test_declining_the_offer_overrides_model_task_hint(self):
        self.job_context()
        self.retirement_learning()
        text = 'Not now. I am not ready to give personal details.'
        extraction=self.interpreted(text,mode='discuss')
        extraction['discussion'].update(purpose='problem',focus='enrollment')
        out = self.message(text,extraction=extraction)
        self.assertTrue(out['conversationPlanner']['education_only'])
        self.assertIsNone(out['assessment']['nextQuestion'])

    def test_process_suggestion_allowed_but_insurance_choice_still_rejected(self):
        self.job_context()
        out = self.timing('Settle on timing!', compose={'reply':'I suggest working through your Medicare timing next.'})
        self.assertEqual(out['generated']['status'], 'complete')
        for reply in ('I suggest dropping your employer coverage.',
                      'I would choose Medicare Advantage.',
                      'I suggest checking your current coverage and dropping it.',
                      'I suggest checking your current coverage. You should switch.'):
            out = self.timing('Work through my timing.', compose={'reply':reply})
            self.assertEqual(out['generated']['status'], 'unavailable', reply)


if __name__ == '__main__': unittest.main()
