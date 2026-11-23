"""Network-forbidden whole-journey controller contracts, not live quality scores.

The response meanings below were authored before any execution. Injected prose
tests that the real controller can preserve a useful journey and its boundaries;
it does not establish that a model chooses these responses or a person learns.
"""
import copy
import importlib.util
import json
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

import test_natural_flow as support
from natural_flow import CONTEXT_POLICY

PACKET = support.HERE.parents[1] / 'audit-evidence/advisor-conversation-quality-20261102'


class ConversationQualityJourneyTests(unittest.TestCase):
    def setUp(self):
        self.network_calls = []
        def forbidden(*args, **kwargs):
            self.network_calls.append(True)
            raise AssertionError('No network is allowed in controlled conversation quality tests.')
        for owner, name in ((socket, 'create_connection'), (socket, 'getaddrinfo'),
                            (socket.socket, 'connect'), (socket.socket, 'connect_ex')):
            patched = patch.object(owner, name, forbidden)
            patched.start()
            self.addCleanup(patched.stop)
        self.case = support.NaturalFlowTests()
        self.case.setUp()
        self.spec = json.loads((PACKET / 'journey-spec.json').read_text())

    @staticmethod
    def extraction(updates=(), *, birthday=None, goal='', facts=(), request=None):
        return {'updates': list(updates), 'requests': [], 'fact_ids': list(facts),
                'agenda': {'concerns': [], 'priorityReason': {}},
                'situation_proposals': [birthday] if birthday else [], 'goal_quote': goal,
                'education_request': request or {'kind': 'none', 'concept_ids': [], 'quote': ''}}

    @staticmethod
    def birthday(text, month, correction=False):
        return {'kind': 'age65', 'subject': 'beneficiary', 'scope': 'intended',
                'quote': text, 'uncertain': False, 'correction': correction,
                'month': month, 'year': None, 'status': '', 'when': ''}

    @staticmethod
    def response(text, *, refs=(), concept=None, reason='new', target=None, question='', pause=False):
        return {'question_target': target, 'question': question, 'reply': text,
                'report_refs': [], 'evidence_refs': list(refs), 'education_followups': [],
                'agenda_update': {'current_concern': 'understanding the two coverage paths', 'pause': pause},
                'education': {'purpose': 'answer', 'updates': [] if concept is None else [{
                    'concept_id': concept, 'depth': 'explored' if reason != 'new' else 'introduced',
                    'reason': reason, 'evidence_refs': list(refs)}], 'visual': 'none'}}

    def take(self, index, extraction, response):
        message = self.spec['events'][index]['message']
        out = self.case.message(message, extraction=extraction, compose=response)
        self.assertEqual(out['generated']['status'], 'complete', out.get('generated'))
        self.assertTrue(out['reply'].startswith(response['reply']), 'Validated useful prose survives with its follow-up.')
        self.assertFalse(out['assessment']['personalizedRecommendationAllowed'])
        self.assertFalse(out['assessment']['externalVerificationReady'])
        self.assertNotIn('review', out, 'No routine capture confirmation is inserted.')
        self.assertEqual(len(self.case.calls), (index + 1) * 2)
        return out

    def opening(self):
        message = self.spec['events'][0]['message']
        return self.take(0, self.extraction([
            self.case.update('RC01', {'choice': 'self'}, message),
            self.case.update('T05', {'choice': 'none'}, message)],
            birthday=self.birthday(message, 11), facts=['routesintro'],
            goal='want to understand my Medicare choices'),
            self.response('Original Medicare and Medicare Advantage are two coverage paths with different rules and costs.',
                          refs=['routesintro'], concept='coverage_paths', target='T04',
                          question='When would you like Medicare coverage to start?'))

    def test_seven_turn_journey_preserves_learning_unknown_defer_correction_and_stop(self):
        self.opening()
        unknown = self.spec['events'][1]['message']
        out = self.take(1, self.extraction([
            self.case.update('T04', {'choice': 'unknown'}, unknown, scope='intended')],
            facts=['routesintro'], request={'kind': 'clarify', 'concept_ids': ['coverage_paths'], 'quote': unknown}),
            self.response('These are two ways to receive Medicare benefits, rather than two policies to buy together.',
                          refs=['routesintro'], concept='coverage_paths', reason='clarify'))
        self.assertIsNone(out['assessment']['nextQuestion'], 'An answer-only educational turn is useful progress.')
        self.assertIsNone(self.case.flow.value(self.case.g, 'coverage.requestedStart'))
        self.assertNotIn('coverage.requestedStartMonth', self.case.g['fields'])
        self.assertNotIn('T04', {item['id'] for item in self.case.stage_payloads('daylight_resolved_conversation')[-1]['question_candidates']})

        self.take(2, self.extraction(facts=['checks']),
            self.response('Doctor participation needs checking for the exact plan. Travel and provider rules are useful differences to compare.',
                          refs=['checks'], concept='provider_checks'))
        deferred = self.spec['events'][3]['message']
        out = self.take(3, self.extraction([
            self.case.update('T04', {'choice': 'deferred'}, deferred, scope='intended')], request={
                'kind': 'explain', 'concept_ids': ['prescription_coverage'], 'quote': deferred}),
            self.response('Prescription drug coverage can come through a separate drug plan or be included in a Medicare Advantage plan.',
                          refs=['drugbasics'], concept='prescription_coverage'))
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertIsNone(self.case.flow.value(self.case.g, 'coverage.requestedStart'))
        self.assertEqual(self.case.r['conversation']['baselineDispositions']['T04'], 'deferred',
                         'Explicit defer must not be masked by the preceding unknown disposition.')
        self.assertNotIn('T04', {item['id'] for item in self.case.stage_payloads('daylight_resolved_conversation')[-1]['question_candidates']})

        misconception = self.spec['events'][4]['message']
        self.take(4, self.extraction(facts=['costs', 'checks'], request={
            'kind': 'clarify', 'concept_ids': ['cost_components', 'provider_checks'], 'quote': misconception}),
            self.response('A premium is only one part of total cost. A plan list does not establish doctor participation; that needs checking for the exact plan.',
                          refs=['costs', 'checks'], concept='cost_components'))
        correction = self.spec['events'][5]['message']
        self.take(5, self.extraction(birthday=self.birthday(correction.split(' Can')[0], 12, correction=True), facts=['routesintro']),
            self.response('We can return to the two coverage paths and the differences that matter to you.', refs=['routesintro']))
        self.assertEqual(self.case.flow.value(self.case.g, 'situation.age65'), {'month': 12, 'year': None})
        changes = self.case.composed_context()['resolved_changes']
        self.assertIn({'report_id': 'guide.situation.age65', 'previous_value': {'month': 11, 'year': None},
                       'current_value': {'month': 12, 'year': None}, 'status': 'superseded'}, changes)

        out = self.take(6, self.extraction(facts=['routesintro', 'checks']),
            self.response('The two paths have different rules and costs. Doctor participation remains unverified. An optional next step is to check the exact plan with the doctor.',
                          refs=['routesintro', 'checks'], pause=True))
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertEqual(out['advisor']['educationFollowups'], [])
        brief = self.case.flow.memory.brief(self.case.owner, self.case.flow.current_chain[self.case.owner], CONTEXT_POLICY)
        self.assertTrue(brief['paused'])
        self.assertEqual(brief['goal'], 'want to understand my Medicare choices')
        self.assertFalse(self.network_calls)

    def test_history_rollover_retains_authoritative_profile_and_learning_without_reasking(self):
        self.opening()
        first = self.spec['events'][0]['message']
        for index in range(8):
            message = f'Please stay with the difference between the coverage paths, explanation {index + 1}.'
            self.case.message(message, extraction=self.extraction(facts=['routesintro']),
                compose=self.response('The coverage paths have different rules and costs.', refs=['routesintro']))
        recent = self.case.flow.memory.recent(self.case.owner, self.case.flow.current_chain[self.case.owner], CONTEXT_POLICY)
        # D155 Q11: the whole visit chat is sent each turn (only a RAM guard and the
        # request byte bound drop the oldest), so all 9 exchanges, the first included,
        # are still recent. The profile and learning below must hold regardless.
        self.assertEqual(len(recent), 9)
        self.assertTrue(any(item['user'] == first for item in recent))
        self.assertEqual(self.case.flow.value(self.case.g, 'subject.role'), 'self')
        self.assertEqual(self.case.flow.value(self.case.g, 'coverage.current'), ['none'])
        self.assertEqual(self.case.flow.value(self.case.g, 'situation.age65'), {'month': 11, 'year': None})
        context = self.case.composed_context()
        self.assertEqual(context['advisor_brief']['goal'], 'want to understand my Medicare choices')
        self.assertTrue(context['education_context']['learning'])
        candidates = self.case.stage_payloads('daylight_resolved_conversation')[-1]['question_candidates']
        self.assertNotIn('RC01', {item['id'] for item in candidates})
        self.assertNotIn('T05', {item['id'] for item in candidates})
        stored = json.dumps({'guide': self.case.g, 'record': self.case.r})
        self.assertNotIn(first, stored, 'Raw conversation is not a saved profile.')
        self.assertFalse(self.network_calls)

    def test_frozen_persona_branches_only_wording_without_inventing_answers(self):
        spec = importlib.util.spec_from_file_location('quality_journey_harness', PACKET / 'evaluate_journey.py')
        harness = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(harness)
        event = self.spec['events'][1]
        plain, policy = harness.action_for(event, {})
        prompted, other = harness.action_for(event, {'assessment': {'nextQuestion': {'id': 'T04'}}})
        self.assertEqual(plain['message'], event['message'])
        self.assertEqual(prompted['message'], event['when_previous_target']['T04'])
        self.assertEqual(plain['type'], prompted['type'])
        self.assertEqual(other['wording_branch'], 'T04')
        self.assertFalse(policy['facts_added_to_rescue_route'])
        self.assertFalse(other['facts_added_to_rescue_route'])
        self.assertEqual(len(self.spec['events']), 7)
        self.assertEqual(self.spec['maximum_generation_stages'], 14)
        self.assertTrue(self.spec['evaluation']['scoring_requires_independent_transcript_review'])
        self.assertTrue(self.spec['evaluation']['comprehension_requires_human_participant_observation'])
        self.assertFalse(self.network_calls)


if __name__ == '__main__':
    unittest.main()
