"""The same context serves every role/task without canned response replacement."""
import json
import unittest

import test_curriculum_flow as support
from test_learner_state import observation
from natural_flow import CONTEXT_POLICY
from chat import ModelUnavailable


class AdvisorFrameworkTests(unittest.TestCase):
    setUp = support.CurriculumFlowTests.setUp
    update = staticmethod(support.CurriculumFlowTests.update)
    payload = support.CurriculumFlowTests.payload
    take = support.CurriculumFlowTests.take
    turn = support.CurriculumFlowTests.turn
    message = support.CurriculumFlowTests.message
    stage_payloads = support.CurriculumFlowTests.stage_payloads
    composed_context = support.CurriculumFlowTests.composed_context

    def send(self, text, observations=(), updates=(), **kwargs):
        extraction = support.CurriculumFlowTests.extraction(updates)
        extraction['learner_observations'] = list(observations)
        return self.message(text, extraction=extraction, **kwargs)

    def memory(self):
        return self.flow.memory.learner(self.owner, self.flow.current_chain[self.owner], CONTEXT_POLICY)

    def test_same_framework_for_self_helper_and_research_at_different_goals(self):
        for role, task in [('self', 'timing'), ('someone', 'review'), ('research', 'learn')]:
            with self.subTest(role=role, task=task):
                self.setUp()
                self.turn({'type': 'task', 'task': task, 'preparing': True}, aiConsent=False, contextPolicy=None)
                self.turn({'type': 'choice', 'id': 'RC01', 'fields': {'choice': role}},
                          aiConsent=False, contextPolicy=None)
                item = observation('coverage_paths', ['public_private_delivery'], 'uncertain',
                                   'I am unsure how the two coverage paths differ.')
                reply = 'We can work through that distinction together.'
                out = self.send(item['quote'], [item], compose={'question_target': None,
                    'question': 'Which part of that distinction is unclear?', 'reply': reply})
                context = self.composed_context()
                self.assertEqual(context['learner_context']['observations'], [item])
                self.assertIn('task_work', context)
                self.assertIn('comparison_status', context)
                self.assertEqual(out['reply'], reply + '\n\nWhich part of that distinction is unclear?')
                self.assertEqual(self.memory()['observations'], [item])
                self.assertNotIn('learner_context', json.dumps([out['guide'], out['record']]))

    def test_information_and_understanding_can_advance_together(self):
        self.turn({'type': 'choice', 'id': 'RC01', 'fields': {'choice': 'self'}},
                  aiConsent=False, contextPolicy=None)
        item = observation()
        text = item['quote'] + ' My home ZIP is 34102.'
        out = self.send(text, [item], [self.update('T03', {'zip': '34102'}, 'My home ZIP is 34102.')],
            compose={'question_target': 'T05', 'question': 'What health insurance do you have now?',
                     'reply': 'That gives us a useful starting point.'})
        self.assertEqual(self.flow.value(out['guide'], 'comparison.scope.zip'), '34102')
        self.assertEqual(self.memory()['observations'], [item])
        self.assertEqual(out['metrics']['llmCalls'], 2)

    def test_failed_composition_does_not_commit_a_new_learner_assessment(self):
        item = observation()
        out = self.send(item['quote'], [item], compose=ModelUnavailable('fixture failure'))
        self.assertEqual(out['generated']['status'], 'unavailable')
        self.assertEqual(self.memory()['observations'], [])

    def test_topic_knowledge_does_not_force_teaching_but_the_model_cannot_pause_alone(self):
        # Nov 9, 2026: a pause the person did not ask for in their own words is
        # not honoured; the educational continuation keeps the conversation open.
        item = observation()
        out = self.send(item['quote'], [item], compose={'question_target': None,
            'question': '', 'reply': 'We can leave it there for today.',
            'agenda_update': {'current_concern': '', 'pause': True}})
        # D157 (CV-25): the turn still ends with a question, but it is the next
        # real question, not a menu of topics appended to the reply.
        self.assertEqual(out['reply'], 'We can leave it there for today.')
        self.assertTrue(out['assessment']['nextQuestion'])
        self.assertEqual(out['advisor']['teachingFactIds'], [])

    def test_person_requested_pause_is_honoured_without_a_question(self):
        item = observation(quote="That's enough for today, thank you.")
        out = self.send(item['quote'], [item], compose={'question_target': None,
            'question': '', 'reply': 'We can leave it there for today.',
            'agenda_update': {'current_concern': '', 'pause': True}})
        self.assertEqual(out['reply'], 'We can leave it there for today.')
        self.assertIsNone(out['assessment']['nextQuestion'])

    def test_learning_uncertainty_can_support_further_explanation_without_a_script(self):
        self.turn({'type': 'choice', 'id': 'RC01', 'fields': {'choice': 'self'}},
                  aiConsent=False, contextPolicy=None)
        for number, text in enumerate(('I am unsure what a deductible does.',
                                      'I still cannot explain the deductible.')):
            item = observation(aspects=['deductible'], signal='uncertain', quote=text)
            reply = ('A deductible is an amount you pay before coverage pays its share under the benefit rules.'
                     if number == 0 else
                     'The deductible applies before coverage pays its share; the exact benefit rules determine how it applies.')
            out = self.send(text, [item], compose={'question_target': None, 'question': '',
                'reply': reply, 'evidence_refs': ['costs'],
                'education': {'purpose': 'clarify', 'updates': [{
                    'concept_id': 'cost_components', 'depth': 'introduced' if number == 0 else 'explored',
                    'reason': 'new' if number == 0 else 'clarify',
                    'aspect_ids': ['deductible'], 'evidence_refs': ['costs']}], 'visual': 'none'},
                'task_work': {'check_ids': ['personal_cost'], 'blocking_concepts': ['cost_components'],
                              'next_step': 'teach'}})
            self.assertEqual(out['reply'].split('\n\n')[0], reply)
            self.assertEqual(out['advisor']['teachingFactIds'], ['costs'])
            self.assertEqual(self.memory()['observations'][0]['signal'], 'uncertain')
            self.assertIn('cost_components', self.composed_context()['task_work']['blocking_concepts'])
