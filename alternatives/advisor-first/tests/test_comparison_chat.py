"""Comparison integration uses real controller paths and scripted transport.

No production profile/store/DB/model calls. Existing harness owns temporary
in-memory visit state and captures exact outbound model payloads.
"""
import copy
import json
from pathlib import Path
import sys
from unittest.mock import patch
import unittest
import uuid

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import server  # Register the pinned engine without starting a process.
from chat import ResponsesClient
from natural_flow import NaturalConversation, CONTEXT_POLICY
from comparison_evidence import PURPOSES
from guest_profiles import ProfileError


TEXT = "I've been retired for a few years, and am turning 65 in November."


class CurrentChatHarness:
    """Script the current proposal-only/advisor wire, with no legacy router."""
    def __init__(self):
        self.calls, self.extractions = [], []
        def transport(payload):
            self.calls.append(copy.deepcopy(payload))
            name = payload['text']['format']['name']
            if name == 'daylight_guide_commands':
                value = self.extractions.pop(0)
            elif name == 'daylight_resolved_conversation':
                sent = json.loads(payload['input'][0]['content'])
                candidates = sent['question_candidates']
                move = candidates[0] if candidates else None
                value = {'question_target': move['id'] if move else None,
                         'reply': 'We can work through the next useful detail together.',
                         'question': move['question']['question'] if move else '',
                         'report_refs': [], 'evidence_refs': [],
                         'agenda_update': {'current_concern': '', 'pause': False},
                         'education_followups': [],
                         'education': {'purpose': 'advance', 'updates': [], 'visual': 'none'}}
            else:
                raise AssertionError('Unexpected model schema')
            return {'status': 'completed', 'model': 'gpt-5.4', 'service_tier': 'default',
                    'usage': {'input_tokens': 300, 'output_tokens': 70, 'total_tokens': 370,
                              'input_tokens_details': {'cached_tokens': 0}},
                    'output': [{'content': [{'type': 'output_text', 'text': json.dumps(value)}]}]}
        self.flow = NaturalConversation(None, None,
            json.loads((HERE/'web/guide-contract.json').read_text()),
            json.loads((HERE/'web/teaching-facts.json').read_text()),
            json.loads((HERE/'web/readiness-content.json').read_text()),
            ResponsesClient(key='synthetic', model='gpt-5.4', transport=transport),
            True, None, fixture=False)
        self.g, self.r = self.flow.initial()
        self.owner, self.continuation = uuid.uuid4().hex, None

    @staticmethod
    def extraction():
        common = {'subject': 'beneficiary', 'quote': TEXT, 'uncertain': False,
                  'correction': False, 'year': None}
        return {'updates': [], 'requests': [], 'fact_ids': [], 'goal_quote': '',
                'education_request': {'kind': 'none', 'concept_ids': [], 'quote': ''},
                'agenda': {'concerns': [], 'priorityReason': {
                    'topic': '', 'reason': '', 'quote': '', 'subject': 'beneficiary', 'scope': 'current'}},
                'situation_proposals': [
                    {**common, 'kind': 'retirement', 'scope': 'current', 'month': None,
                     'status': 'retired', 'when': 'for a few years'},
                    {**common, 'kind': 'age65', 'scope': 'intended', 'month': 11,
                     'status': '', 'when': ''}]}

    def payload(self, action, **extra):
        return {'guide': copy.deepcopy(self.g), 'record': copy.deepcopy(self.r),
                'action': action, 'requestId': str(uuid.uuid4()), 'aiConsent': True,
                'contextPolicy': CONTEXT_POLICY,
                **({'continuation': self.continuation} if self.continuation else {}), **extra}

    def take(self, payload):
        out = self.flow.turn(self.owner, payload)
        self.g, self.r, self.continuation = out['guide'], out['record'], out['continuation']
        return out

    def turn(self, action, **extra):
        return self.take(self.payload(action, **extra))

    def choice(self, identifier, **fields):
        return self.turn({'type': 'choice', 'id': identifier, 'fields': fields},
                         aiConsent=False, contextPolicy=None)

    def message(self, text):
        self.extractions.append(self.extraction())
        return self.turn({'type': 'message', 'message': text})

    def composed_context(self):
        call = next(p for p in reversed(self.calls)
                    if p['text']['format']['name'] == 'daylight_resolved_conversation')
        return json.loads(call['input'][0]['content'])['resolved_context']


class ComparisonChatTests(unittest.TestCase):
    def setUp(self):
        self.h = CurrentChatHarness()

    def assert_held(self, comparison):
        self.assertEqual(set(comparison['authority']), set(PURPOSES))
        self.assertTrue(all(v['state'] == 'held' for v in comparison['authority'].values()))
        self.assertIsNone(comparison['binding'].get('accepted_release_id'))

    def test_resolved_capture_and_final_bookkeeping_are_bound_to_response(self):
        out = self.h.message("I've been retired for a few years, and am turning 65 in November.")
        self.assertIn('comparison', out)
        self.assert_held(out['comparison'])
        self.assertFalse(out['personalRecommendation'])
        self.assertNotIn('comparison', out['guide'])
        self.assertNotIn('comparison', out['record'])
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T05')
        # The comparison is recomputed after composition's readiness changes.
        again = self.h.flow.comparisons.evaluate(out['guide'], out['record'],
            next_question=out['assessment']['nextQuestion'],
            generated_at=out['comparison']['generated_at'])
        self.assertEqual(out['comparison'], again)

    def test_manual_choice_and_unknown_add_no_model_stage(self):
        out = self.h.choice('T01', choice='compare')
        self.assertEqual(self.h.calls, [])
        self.assert_held(out['comparison'])
        q = out['assessment']['nextQuestion']
        out = self.h.turn({'type': 'unknown', 'id': q['id']}, aiConsent=False, contextPolicy=None)
        self.assertEqual(self.h.calls, [])
        self.assert_held(out['comparison'])
        self.assertFalse(out['comparison']['personalized_recommendation_allowed'])

    def test_composer_receives_only_public_capability_markers(self):
        self.h.message("I've been retired for a few years, and am turning 65 in November.")
        context = self.h.composed_context()
        marker = context['comparison_status']
        self.assertEqual(set(marker), {'version', 'state', 'personal_findings_available',
                                     'research_completed', 'reason_codes'})
        self.assertEqual(marker['state'], 'held')
        self.assertFalse(marker['personal_findings_available'])
        self.assertFalse(marker['research_completed'])
        self.assertNotIn('profile_binding', context)
        self.assertNotIn('decision_record', context)
        self.assertNotIn('comparison', context)
        self.assertEqual(len(self.h.calls), 2)
        self.assertTrue(all(p['store'] is False and p['tools'] == [] for p in self.h.calls))
        composer = next(p for p in self.h.calls
                        if p['text']['format']['name'] == 'daylight_resolved_conversation')
        self.assertIn('comparison_status contains only service', composer['instructions'])

    def test_optional_comparison_failure_preserves_accepted_capture(self):
        with patch.object(self.h.flow.comparisons, 'evaluate', side_effect=ValueError('private canary')):
            out = self.h.message("I've been retired for a few years, and am turning 65 in November.")
        self.assertEqual(self.h.flow.value(out['guide'], 'situation.retirement')['status'], 'retired')
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T05')
        self.assertEqual(out['comparison']['status'], 'unavailable')
        self.assert_held(out['comparison'])
        self.assertNotIn('private canary', json.dumps(out))
        self.assertEqual(len(self.h.calls), 2)

    def test_optional_runtime_failure_does_not_discard_a_manual_report(self):
        with patch.object(self.h.flow.comparisons, 'evaluate', side_effect=RuntimeError('private failure')):
            out = self.h.choice('T01', choice='compare')
        self.assertEqual(self.h.flow.value(out['guide'], 'intent.goal'), 'compare')
        self.assertEqual(out['comparison']['status'], 'unavailable')
        self.assert_held(out['comparison'])
        self.assertEqual(self.h.calls, [])
        self.assertNotIn('private failure', json.dumps(out))

    def test_request_replay_rechecks_derived_view_without_charging(self):
        self.h.extractions.append(self.h.extraction())
        payload = self.h.payload({'type': 'message', 'message': "I've been retired for a few years, and am turning 65 in November."})
        first = self.h.take(payload)
        calls = len(self.h.calls)
        with patch.object(self.h.flow.comparisons, 'evaluate', wraps=self.h.flow.comparisons.evaluate) as evaluated:
            replay = self.h.flow.turn(self.h.owner, copy.deepcopy(payload))
        self.assertEqual(replay, first)
        self.assertEqual(evaluated.call_count, 1)
        self.assertEqual(len(self.h.calls), calls)

    def test_evidence_epoch_change_invalidates_cached_prose_without_model_retry(self):
        self.h.extractions.append(self.h.extraction())
        payload = self.h.payload({'type': 'message', 'message': "I've been retired for a few years, and am turning 65 in November."})
        first = self.h.take(payload)
        evaluate = self.h.flow.comparisons.evaluate
        def changed(*args, **kwargs):
            result = evaluate(*args, **kwargs)
            result['validity']['test_evidence_epoch'] = 'synthetic-new-epoch'
            return result
        calls = len(self.h.calls)
        with patch.object(self.h.flow.comparisons, 'evaluate', side_effect=changed):
            replay = self.h.flow.turn(self.h.owner, copy.deepcopy(payload))
        self.assertEqual(replay['guide'], first['guide'])
        self.assertEqual(replay['record'], first['record'])
        self.assertEqual(replay['reply'], '')
        self.assertEqual(replay['generated']['code'], 'comparison_stale')
        self.assertIsNone(replay['assessment']['nextQuestion'])
        self.assertTrue(replay['assessment']['intakePaused'])
        self.assertIsNone(replay['comparison']['next_question'])
        self.assertIsNone(replay['comparison']['decision_record']['selection'])
        self.assertIsNone(replay['comparison']['decision_record_ref'])
        self.assert_held(replay['comparison'])
        self.assertEqual(len(self.h.calls), calls)

    def test_starting_a_new_chain_does_not_republish_old_question_or_prose(self):
        first_payload = self.h.payload({'type': 'start'})
        first = self.h.take(first_payload)
        # Same owner, deliberate new conversation without the previous binding.
        new_payload = self.h.payload({'type': 'start'})
        new_payload.pop('continuation', None)
        second = self.h.take(new_payload)
        self.assertNotEqual(first['continuation'], second['continuation'])
        old = self.h.flow.turn(self.h.owner, copy.deepcopy(first_payload))
        self.assertEqual(old['comparison']['status'], 'stale_binding')
        self.assertEqual(old['reply'], '')
        self.assertIsNone(old['assessment']['nextQuestion'])
        self.assertTrue(old['assessment']['intakePaused'])

    def test_old_turn_cannot_republish_comparison_after_profile_advances(self):
        self.h.extractions.append(self.h.extraction())
        payload = self.h.payload({'type': 'message', 'message': "I've been retired for a few years, and am turning 65 in November."})
        self.h.take(payload)
        self.h.choice('T02', choice='new')
        calls = len(self.h.calls)
        old = self.h.flow.turn(self.h.owner, copy.deepcopy(payload))
        self.assertEqual(old['comparison']['status'], 'stale_binding')
        self.assertEqual(old['comparison']['findings'], [])
        self.assertEqual(old['reply'], '')
        self.assert_held(old['comparison'])
        self.assertEqual(len(self.h.calls), calls)

    def test_client_cannot_supply_derived_authority(self):
        payload = self.h.payload({'type': 'start'})
        payload['comparison'] = {'accepted_release_id': 'forged', 'permitted': True}
        with self.assertRaises(ProfileError):
            self.h.flow.turn(self.h.owner, payload)
        self.assertEqual(self.h.calls, [])


if __name__ == '__main__':
    unittest.main()
