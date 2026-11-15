"""Exact r2 activation and held-deadline regressions; fictional offline transport."""
import copy
from datetime import date
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pilot_knowledge import ROOT, CONTROLS, HELD_MA_DEADLINE, PilotKnowledge, held_deadline_claim
from chat import ModelUnavailable
import test_pilot_knowledge as support
import test_conversation_claims as claims

DAY = date(2026, 11, 12)
# Reuse the sealed review packet's topic cases, not its historical staging assertions.
spec = importlib.util.spec_from_file_location('r2_review_cases', ROOT / 'verify.py')
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.index = PilotKnowledge(surface='unified-8895')

    def test_exact_additions_preserve_original_acceptance(self):
        old = json.loads(CONTROLS.with_name('pilot-knowledge-review-8895.json').read_text())
        new = json.loads(CONTROLS.read_text())
        self.assertEqual(set(new['approved_facts']) - set(old['approved_facts']), review.NEW)
        self.assertEqual(len(review.NEW), 31)
        for key, receipt in old['approved_facts'].items():
            self.assertEqual(new['approved_facts'][key], receipt)
        self.assertTrue(review.HELD.isdisjoint(new['approved_facts']))
        self.assertEqual(self.index.status(today=DAY)['held_claim_ids'], [HELD_MA_DEADLINE])

    def test_actual_approval_retrieves_every_new_topic_and_situation(self):
        for query, expected in review.CASES:
            with self.subTest(query=query):
                found = self.index.select(query, today=DAY)
                self.assertIn(expected, [f['id'] for f in found])
                self.assertLessEqual(len(found), 3)
                fact = next(f for f in found if f['id'] == expected)
                self.assertEqual(fact['conditions'], review.FACTS[expected]['conditions'])
                self.assertTrue(fact['sources'])
        for row in json.loads((ROOT/'enrollment-situations.json').read_text())['situations']:
            with self.subTest(situation=row['id']):
                found = self.index.select(row['example_query'], today=DAY)
                self.assertTrue(set(row['fact_ids']) & {f['id'] for f in found})

    def test_all_three_holds_and_raw_conflicting_passages_stay_out(self):
        for key in review.HELD:
            for alias in review.FACTS[key]['aliases']:
                found = self.index.select('Florida '+alias, state='FL', today=DAY)
                self.assertNotIn(key, [f['id'] for f in found])
        found = self.index.select('What happens when adding Part B later?', today=DAY)
        fact = next(f for f in found if f['id'] == 'pk_new_part_b_plan_window')
        self.assertNotIn('support', fact)
        self.assertNotIn('two months', json.dumps(fact).lower())
        self.assertNotIn('2 months', json.dumps(fact).lower())

    def test_hold_survives_kill_switch_and_is_surface_scoped(self):
        with patch.dict('os.environ', {'DAYLIGHT_DISABLE_PILOT_KNOWLEDGE': '1'}):
            self.assertEqual(self.index.select('adding Part B later', today=DAY), [])
            self.assertIn(HELD_MA_DEADLINE, self.index.response_limits()['held_claim_ids'])
        self.assertEqual(PilotKnowledge(surface='advisor-8893').response_limits(), {})

    def test_worded_numeric_and_user_echoed_deadlines_are_rejected(self):
        case = claims.ConversationClaimTests(); case.setUp()
        message = 'I already have Part A. Adding Part B later, do I get two months to join Medicare Advantage?'
        facts = self.index.select(message, today=DAY)
        case.context.update(evidence=facts, current_message=message,
                            knowledge_limits=self.index.response_limits(message, facts))
        for reply in (
            'People adding Part B later generally have two months after Part B starts to join Medicare Advantage.',
            'The Medicare Advantage enrollment window closes two months after Part B starts.',
            'You have a 2-month window to join Medicare Advantage.',
            'The deadline is May 31.',
            'The enrollment window closes on 2026-05-31.',
            'Enroll by the end of the month.',
        ):
            with self.subTest(reply=reply), self.assertRaises(ModelUnavailable):
                case.validate(reply=reply, evidence_refs=['pk_new_part_b_plan_window'])

    def test_supported_effective_dates_and_other_clocks_are_separate(self):
        limits = self.index.response_limits('adding Part B later')
        for reply in (
            'Coverage generally starts the first of the month after the plan receives the request.',
            'A request before Part B starts can take effect with Part B.',
            'Medigap open enrollment lasts six months.',
            'The Part B special enrollment window extends eight months after current employment or coverage ends.',
            'The General Enrollment Period runs January through March.',
            'There may be an initial Medicare Advantage enrollment opportunity when both parts begin.',
        ):
            with self.subTest(reply=reply):
                self.assertFalse(held_deadline_claim(reply, limits))
        self.assertFalse(held_deadline_claim('Annual open enrollment is October 15 through December 7.',
                                           self.index.response_limits('annual open enrollment')))


class ActivationConversationTests(unittest.TestCase):
    setUp = support.ConversationTests.setUp
    payload = support.ConversationTests.payload
    take = support.ConversationTests.take
    turn = support.ConversationTests.turn
    message = support.ConversationTests.message
    stage_payloads = support.ConversationTests.stage_payloads
    composed_context = support.ConversationTests.composed_context
    update = staticmethod(support.ConversationTests.update)
    extraction = staticmethod(support.ConversationTests.extraction)

    def test_new_fact_citation_and_continuation_use_existing_two_stages(self):
        out = self.message('What is a tiering exception?', compose={
            'reply': 'A tiering exception asks a drug plan to cover a non-preferred drug at a lower cost-sharing tier.',
            'evidence_refs': ['pk_tiering_exception']})
        self.assertEqual(out['generated']['status'], 'complete')
        self.assertIn('pk_tiering_exception', out['knowledgeReceipts'])
        self.assertTrue(out['advisor']['sources'])
        self.assertTrue(out['assessment']['nextQuestion'])
        self.assertEqual(len(self.calls), 2)

    def test_supported_ma_answer_has_limits_in_actual_packed_context(self):
        out = self.message('What happens when adding Part B later?', compose={
            'reply': 'An initial Medicare Advantage enrollment opportunity is tied to first having both Part A and Part B.',
            'evidence_refs': ['pk_new_part_b_plan_window']})
        self.assertEqual(out['generated']['status'], 'complete')
        self.assertTrue(self.composed_context()['knowledge_limits']['late_part_b_context'])
        self.assertTrue(out['assessment']['nextQuestion'])
        self.assertEqual(len(self.calls), 2)
        # Withdraw even a receipt-valid cached response if it contains a held clock.
        poisoned = copy.deepcopy(out)
        poisoned['reply'] = 'The Medicare Advantage window closes two months after Part B starts.'
        replay = self.flow.replay_response(self.owner, poisoned)
        self.assertEqual(replay['generated']['code'], 'knowledge_claim_held')
        self.assertEqual(replay['guide'], out['guide'])
        self.assertEqual(replay['assessment']['nextQuestion'], out['assessment']['nextQuestion'])
        self.assertNotIn('two months', replay['reply'])
        self.assertEqual(len(self.calls), 2)

    def test_invalid_deadline_recovery_keeps_next_question(self):
        bad = {'reply': 'People adding Part B later have two months to join Medicare Advantage.',
               'evidence_refs': ['pk_new_part_b_plan_window']}
        self.compositions.extend([copy.deepcopy(bad), copy.deepcopy(bad)])
        out = self.message('Adding Part B later, do I have two months to join Medicare Advantage?')
        self.assertNotIn('two months', out['reply'])
        self.assertTrue(out['assessment']['nextQuestion'])
        self.assertNotIn('pk_new_part_b_plan_window', out.get('knowledgeReceipts', {}))


if __name__ == '__main__':
    unittest.main()
