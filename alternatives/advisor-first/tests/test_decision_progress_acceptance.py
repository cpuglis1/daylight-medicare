"""Decision-progress acceptance boundaries using synthetic transport/private ledgers.

These tests exercise the public turn contract. They do not call a provider, touch
the shared budget or establish the quality of unscripted model conversation.
"""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

import test_natural_flow as support
import test_natural_agent as agent_support
from ai_budget import DailyBudget
from chat import ModelUnavailable
from natural_flow import CONTEXT_POLICY, LEGACY_CONTEXT_POLICY
from natural_state import apply_agenda_reports, prune_for_storage


class DecisionProgressAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.case = support.NaturalFlowTests()
        self.case.setUp()
        self.case.turn({'type': 'task', 'task': 'timing', 'preparing': True},
                       aiConsent=False, contextPolicy=None)
        self.case.turn({'type': 'choice', 'id': 'RC01', 'fields': {'choice': 'self'}},
                       aiConsent=False, contextPolicy=None)

    def selected_start(self, **extra):
        return self.case.payload(
            {'type': 'choice', 'id': 'T04', 'fields': {'choice': 'soonest'}},
            **extra)

    def attach_private_budget(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        directory.chmod(0o700)
        pricing = json.loads((support.HERE.parents[1] /
            'alternatives/chat-first/cms-slice/config/ai-pricing.json').read_text())
        pricing['verified_at'] = '2026-10-30T00:00:00Z'
        pricing['valid_until'] = '2026-11-04T00:00:00Z'
        pricing_path = directory / 'pricing.json'
        pricing_path.write_text(json.dumps(pricing))
        budget = DailyBudget(directory / 'usage.sqlite3', pricing_path=pricing_path,
            clock=lambda: datetime(2026, 10, 31, 12, tzinfo=timezone.utc).timestamp())
        self.case.flow.agent.budget = budget
        self.case.flow.agent.count_tokens = lambda *_: 300
        return budget

    def test_deliberate_choice_send_composes_once_without_reextracting_the_answer(self):
        out = self.case.take(self.selected_start(aiConsent=True,
                                                contextPolicy=CONTEXT_POLICY))
        self.assertEqual([call['text']['format']['name'] for call in self.case.calls],
                         ['daylight_resolved_conversation'])
        self.assertEqual(out['generated']['status'], 'complete')
        self.assertEqual(self.case.flow.value(self.case.g, 'coverage.requestedStart'),
                         'soonest')
        self.assertNotIn('coverage.requestedStartMonth', self.case.g['fields'])
        self.assertEqual(self.case.g['fields']['coverage.requestedStart']['confirmation'],
                         'reported_by_user')
        self.assertNotIn('review', out)

    def test_absent_or_legacy_context_permission_never_starts_choice_generation(self):
        for permission in ({'aiConsent': False, 'contextPolicy': None},
                           {'aiConsent': True, 'contextPolicy': LEGACY_CONTEXT_POLICY}):
            with self.subTest(permission=permission):
                self.setUp()
                out = self.case.take(self.selected_start(**permission))
                self.assertEqual(self.case.calls, [])
                self.assertEqual(self.case.flow.value(self.case.g,
                                                     'coverage.requestedStart'),
                                 'soonest')
                self.assertNotIn('review', out)

    def test_choice_replay_never_reserves_or_charges_a_second_composition(self):
        budget = self.attach_private_budget()
        payload = self.selected_start(aiConsent=True, contextPolicy=CONTEXT_POLICY)
        first = self.case.take(payload)
        with budget.db() as db:
            original = [tuple(row) for row in db.execute('SELECT * FROM ai_charges')]
            self.assertEqual([tuple(row) for row in db.execute(
                'SELECT status,input_tokens,output_tokens FROM ai_charges')],
                [('settled', 300, 70)])
        self.assertEqual(len(original), 1)
        self.assertEqual(len(self.case.calls), 1)
        replay = self.case.flow.turn(self.case.owner, copy.deepcopy(payload))
        self.assertEqual(replay, first)
        self.assertEqual(len(self.case.calls), 1)
        chain = self.case.flow.current_chain[self.case.owner]
        self.assertEqual(len(self.case.flow.visit_memory[
            (self.case.owner, chain)]['exchanges']), 1)
        with budget.db() as db:
            self.assertEqual([tuple(row) for row in db.execute('SELECT * FROM ai_charges')],
                             original)

    def test_failed_choice_prose_keeps_the_report_without_starting_more_intake(self):
        self.case.compositions.append(ModelUnavailable('A synthetic interrupted reply.'))
        out = self.case.take(self.selected_start(aiConsent=True,
                                                contextPolicy=CONTEXT_POLICY))
        self.assertEqual(self.case.flow.value(self.case.g, 'coverage.requestedStart'),
                         'soonest')
        # Never-blank floor (November 8, 2026): one reviewed statement and the
        # server-selected approved question replace the empty reply.
        self.assertTrue(out['reply'])
        self.assertEqual(out['advisor']['reason'], 'recovery')
        self.assertEqual(out['generated']['status'], 'unavailable')
        # D157 (CV-03): a failed reply no longer shows "I couldn't finish that answer".
        self.assertNotIn('notice', out)
        self.assertEqual(out['generated']['status'], 'unavailable')
        self.assertIsNotNone(out['assessment']['nextQuestion'])
        self.assertNotIn('review', out)
        self.assertEqual(len(self.case.calls), 1)


class ResearchBoundaryAcceptanceTests(unittest.TestCase):
    def test_conversation_never_reports_research_that_no_tool_performed(self):
        for claim in ("I've researched every plan for you.",
                      "I've checked your doctor network.",
                      "I've compared all your options."):
            with self.subTest(claim=claim):
                case = agent_support.NaturalAgentTests()
                case.setUp()
                case.answer = case.composition(reply=claim)
                with self.assertRaises(ModelUnavailable):
                    case.compose()

    def test_future_conversation_about_tradeoffs_is_allowed(self):
        case = agent_support.NaturalAgentTests()
        case.setUp()
        reply = 'We can compare the tradeoffs that matter to you.'
        case.answer = case.composition(reply=reply)
        self.assertEqual(case.compose()['reply'], reply)


class TeachingProgressAcceptanceTests(unittest.TestCase):
    def test_available_or_unrendered_facts_do_not_count_as_shown_teaching(self):
        case = support.NaturalFlowTests()
        case.setUp()
        case.turn({'type': 'task', 'task': 'learn', 'preparing': False},
                  aiConsent=False, contextPolicy=None)
        previously_seen = set(case.r['conversation']['journey']['learningSeen'])
        out = case.message('What are the parts of Medicare and its two coverage routes?',
            extraction=case.extraction(mode='answer', fact_ids=['parts', 'routesintro']),
            compose={'move_id': 'answer', 'question': '',
                     'reply': 'We can begin with hospital and medical coverage.',
                     'education': {'purpose': 'teach', 'updates': [
                         {'concept_id': 'part_a', 'depth': 'introduced', 'reason': 'new', 'evidence_refs': ['parts']},
                         {'concept_id': 'part_b', 'depth': 'introduced', 'reason': 'new', 'evidence_refs': ['parts']}],
                         'visual': 'parts'},
                     'evidence_refs': ['parts']})
        self.assertEqual(out['generated']['status'], 'complete')
        shown = set(out.get('advisor', {}).get('teachingFactIds', []))
        shown.update(fact['id'] for fact in out.get('facts', []))
        seen = set(out['record']['conversation']['journey']['learningSeen'])
        self.assertIn('parts', shown)
        self.assertIn('parts', seen)
        self.assertTrue(seen - previously_seen <= shown)
        if 'routesintro' not in previously_seen | shown:
            self.assertNotIn('routesintro', seen)


class PriorityReasonAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.case = support.NaturalFlowTests()
        self.case.setUp()
        self.case.turn({'type': 'task', 'task': 'compare', 'preparing': True},
                       aiConsent=False, contextPolicy=None)
        self.case.turn({'type': 'choice', 'id': 'RC01', 'fields': {'choice': 'self'}},
                       aiConsent=False, contextPolicy=None)
        self.case.turn({'type': 'choice', 'id': 'T10', 'fields': {'choice': 'doctors'}},
                       aiConsent=False, contextPolicy=None)
        self.message = 'My specialist matters because she knows my history.'
        self.reason = 'she knows my history'
        self.proposal = {'concerns': [], 'priorityReason': {
            'topic': 'doctors', 'reason': self.reason, 'quote': self.message,
            'subject': 'beneficiary', 'scope': 'current'}}
        self.accepted = [{'id': 'T10', 'subject': 'beneficiary',
                          'scope': 'current', 'uncertain': False}]

    def report_reason(self, **extra):
        apply_agenda_reports(self.case.g, self.case.r, self.message,
                             extra.get('proposal', self.proposal),
                             extra.get('accepted_updates', self.accepted))
        # This service-level fixture write precedes the next public turn. Bind
        # the updated snapshot exactly as a completed turn would do.
        chain = self.case.flow.current_chain[self.case.owner]
        self.case.continuation = self.case.flow.bind(self.case.owner, self.case.g,
                                                    self.case.r, chain)
        self.case.flow.state_heads[(self.case.owner, chain)] = self.case.continuation

    def reasons(self):
        return self.case.r['natural'].get('agenda', {}).get('priorityReasons', [])

    def test_teaching_or_a_reason_proposal_alone_does_not_establish_agreement(self):
        self.report_reason(accepted_updates=[])
        self.assertEqual(self.reasons(), [])
        self.report_reason(accepted_updates=[{**self.accepted[0], 'subject': 'learner'}])
        self.assertEqual(self.reasons(), [])
        hypothetical = copy.deepcopy(self.proposal)
        hypothetical['priorityReason']['quote'] = 'If my specialist mattered, she knows my history.'
        apply_agenda_reports(self.case.g, self.case.r,
                             hypothetical['priorityReason']['quote'],
                             hypothetical, self.accepted)
        self.assertEqual(self.reasons(), [])

    def test_priority_correction_removes_its_superseded_reason(self):
        self.report_reason()
        old_revision = self.case.g['fields']['needs.priorities']['revision']
        self.assertEqual(self.reasons()[0]['priorityRevision'], old_revision)
        self.case.turn({'type': 'choice', 'id': 'T10',
                        'fields': {'choice': 'total_cost'}},
                       aiConsent=False, contextPolicy=None)
        self.assertEqual(self.case.flow.value(self.case.g, 'needs.priorities'),
                         ['total_cost'])
        self.assertEqual(self.reasons(), [])

    def test_reason_context_requires_current_permission_and_a_relevant_task(self):
        self.report_reason()
        question = self.case.flow.question('T10')
        current = self.case.flow.context(self.case.g, self.case.r, CONTEXT_POLICY, question)
        self.assertIn(self.reason, json.dumps(current))
        v1 = self.case.flow.context(self.case.g, self.case.r, LEGACY_CONTEXT_POLICY, question)
        self.assertNotIn(self.reason, json.dumps(v1))
        self.case.r['conversation']['task'] = 'timing'
        unrelated = self.case.flow.context(self.case.g, self.case.r,
                                           CONTEXT_POLICY, self.case.flow.question('T04'))
        self.assertNotIn(self.reason, json.dumps(unrelated))

    def test_saving_reason_text_requires_separate_sensitive_save_choice(self):
        self.report_reason()
        self.case.g['preferences']['saveSensitive'] = False
        _, minimal = prune_for_storage(self.case.g, self.case.r)
        self.assertNotIn(self.reason, json.dumps(minimal))
        self.case.g['preferences']['saveSensitive'] = True
        _, sensitive = prune_for_storage(self.case.g, self.case.r)
        self.assertIn(self.reason, json.dumps(sensitive))

    def test_helpers_own_concern_does_not_open_a_beneficiary_question(self):
        case = support.NaturalFlowTests()
        case.setUp()
        case.turn({'type': 'task', 'task': 'compare', 'preparing': True},
                  aiConsent=False, contextPolicy=None)
        case.turn({'type': 'choice', 'id': 'RC01', 'fields': {'choice': 'someone'}},
                  aiConsent=False, contextPolicy=None)
        message = 'I worry about keeping my own doctors.'
        apply_agenda_reports(case.g, case.r, message, {'concerns': [{
            'topic': 'doctors', 'subject': 'learner', 'scope': 'current',
            'status': 'open', 'quote': message}], 'priorityReason': {}}, [])
        moves = case.flow.eligible(case.owner, case.g, case.r)
        self.assertNotIn('concern:T06', [move['id'] for move in moves])


if __name__ == '__main__':
    unittest.main()
