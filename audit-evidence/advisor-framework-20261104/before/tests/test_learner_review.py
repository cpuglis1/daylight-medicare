"""Caregiver review journeys through the actual interpreter and delivery gates."""
import json
import unittest

import test_curriculum_flow as support
from natural_flow import CONTEXT_POLICY
from learner_review import APPLY, CONTINUE, LESSONS, PROBE


class LearnerReviewTests(unittest.TestCase):
    setUp = support.CurriculumFlowTests.setUp
    update = staticmethod(support.CurriculumFlowTests.update)
    payload = support.CurriculumFlowTests.payload
    take = support.CurriculumFlowTests.take
    turn = support.CurriculumFlowTests.turn
    message = support.CurriculumFlowTests.message
    stage_payloads = support.CurriculumFlowTests.stage_payloads
    composed_context = support.CurriculumFlowTests.composed_context

    def send(self, text, updates=(), signal=None, quote=None, subject='learner', **kwargs):
        extraction = support.CurriculumFlowTests.extraction(updates, goal=kwargs.pop('goal', ''),
            education_request=kwargs.pop('education_request', None))
        if signal:
            extraction['learner_observation'] = {
                'signal': signal, 'subject': subject, 'quote': text if quote is None else quote}
        return self.message(text, extraction=extraction, **kwargs)

    def opening(self, **kwargs):
        text = "I'm helping my mom review her existing coverage."
        return self.send(text, [self.update('RC01', {'choice': 'someone'}, text),
            self.update('T01', {'choice': 'review'}, text)],
            goal=text, compose={'question_target': 'T05',
                'question': 'What health insurance does the person you’re helping have now?'}, **kwargs)

    def coverage(self, **kwargs):
        text = 'She has Original Medicare and a Medicare supplement.'
        return self.send(text, [self.update('T05', {'choice': 'original,medigap'}, text)], **kwargs)

    def memory(self):
        return self.flow.memory.learner_review(
            self.owner, self.flow.current_chain[self.owner], CONTEXT_POLICY)

    def test_novice_learns_and_applies_before_zip(self):
        self.opening()
        probe = self.coverage()
        self.assertIn(PROBE, probe['reply'])
        self.assertIsNone(probe['assessment']['nextQuestion'])
        self.assertTrue(probe['assessment']['conversationOpen'])
        self.assertEqual(self.memory()['signal'], 'none', 'Naming coverage is not understanding.')
        uncertainty = "I don't know what it does. This is new to me."
        lesson = self.send(uncertainty, signal='unfamiliar',
            education_request={'kind': 'clarify', 'concept_ids': ['medigap'], 'quote': uncertainty})
        self.assertIn(LESSONS['teach'], lesson['reply'])
        self.assertIn(APPLY, lesson['reply'])
        self.assertEqual(lesson['advisor']['teachingFactIds'], ['medigap'])
        self.assertIn('medicare.gov', lesson['advisor']['sources'][0]['url'])
        self.assertEqual(self.memory()['signal'], 'unfamiliar', 'A delivered lesson cannot prove learning.')
        answer = 'I would check which bills she would have to pay a share of if she did not have it.'
        advanced = self.send(answer, signal='applied', compose={'question_target': 'T03'})
        self.assertEqual(advanced['assessment']['nextQuestion']['id'], 'T03')
        self.assertEqual(self.memory()['signal'], 'applied')
        self.assertNotIn(answer, json.dumps(self.memory()))
        self.assertNotIn('learner_review', json.dumps([advanced['guide'], advanced['record']]))
        self.assertEqual(advanced['metrics']['llmCalls'], 2)

    def test_experienced_learner_skips_lesson_after_concrete_explanation(self):
        self.opening()
        text = ('She has Original Medicare and a supplement. I know the supplement helps with '
                'some of the costs Medicare leaves her to pay.')
        out = self.send(text, [self.update('T05', {'choice': 'original,medigap'},
            'She has Original Medicare and a supplement.')], signal='applied',
            quote='the supplement helps with some of the costs Medicare leaves her to pay.',
            compose={'question_target': 'T03'})
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T03')
        self.assertEqual(out['advisor']['teachingFactIds'], [])
        self.assertEqual(self.memory()['signal'], 'applied')

    def test_misunderstanding_after_teaching_gets_different_example_once(self):
        self.opening()
        self.coverage()
        self.send('I am not sure what the supplement does.', signal='unclear')
        text = 'I thought her supplement would replace her Original Medicare.'
        out = self.send(text, signal='misconception')
        self.assertIn(LESSONS['repair'], out['reply'])
        self.assertEqual(out['advisor']['teachingFactIds'], ['medigap'])
        self.assertTrue(self.memory()['repaired'])
        out = self.send(text, signal='misconception', compose={'question_target': 'T03'})
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T03')
        self.assertNotIn(LESSONS['repair'], out['reply'])
        self.assertEqual(self.memory()['signal'], 'misconception')

    def test_decline_and_explicit_pause_do_not_impose_a_lesson(self):
        self.opening()
        self.coverage()
        out = self.send('Please skip the explanation and go straight to the review.', signal='declined',
            compose={'question_target': 'T03'})
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T03')
        self.assertEqual(self.memory()['signal'], 'declined')
        out = self.send('No more questions.')
        self.assertTrue(out['assessment']['intakePaused'])
        self.assertNotIn(CONTINUE, out['reply'])
        self.assertIsNone(out['assessment']['nextQuestion'])

    def test_beneficiary_or_unsupported_quote_is_not_learner_evidence(self):
        self.opening()
        self.coverage()
        out = self.send('Yes.', signal='applied', quote='I know exactly what these policies cover.')
        self.assertEqual(self.memory()['signal'], 'none')
        self.assertIn(APPLY, out['reply'])
        self.send('Mom knows the supplement pays some of the costs Medicare leaves.',
            signal='applied', subject='beneficiary')
        self.assertEqual(self.memory()['signal'], 'none')

    def test_concrete_continuation_offered_once_after_core_inputs(self):
        self.opening()
        self.coverage()
        self.send('Please skip the explanation.', signal='declined')
        text = 'Her ZIP is 34102, no doctors or prescriptions to check, and costs matter most.'
        updates = [self.update('T03', {'zip': '34102'}, 'Her ZIP is 34102'),
            self.update('T06', {'choice': 'none'}, 'no doctors'),
            self.update('T07', {'choice': 'no'}, 'no doctors or prescriptions to check'),
            self.update('T10', {'choice': 'total_cost'}, 'costs matter most')]
        out = self.send(text, updates, compose={'question_target': None, 'question': '',
            'reply': 'A recent premium notice would help establish what she pays today.'})
        self.assertIn(CONTINUE, out['reply'])
        self.assertTrue(out['assessment']['conversationOpen'])
        out = self.send('Yes, where should I look?', compose={'question_target': None, 'question': '',
            'reply': 'Look for the latest bill or renewal notice from the company that issues the supplement.'})
        self.assertIn('latest bill', out['reply'])
        self.assertNotIn(CONTINUE, out['reply'])
