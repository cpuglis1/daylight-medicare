"""Fault-injection checks of validation/receipts; no live models or tone scoring."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_natural_agent as fixtures
import test_natural_flow as flow_fixtures
from advisor_budget import AdvisorDailyBudget, APPROVED_CAP
from advisor_models import MODELS
from ai_budget import BudgetError
from chat import ModelUnavailable
from composition_recovery import CompositionRejected
from natural_agent import _question_candidates


class CompositionRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.NaturalAgentTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.agent = self.fixture.agent
        self.agent.budget = AdvisorDailyBudget.adopt(self.fixture.ledger())
        self.agent.composition_recovery = True
        self.agent.connection_retries = 1
        self.context = {'reports': [], 'evidence': [], 'revision': [1, 1],
                        # The person's own words must not name the invented figure:
                        # a figure the person states is echoable (own-words grounding, Nov 9).
                        'current_message': 'Please invent an amount for me.'}
        self.moves = [{'id': 'T05', 'question': {'id': 'T05',
                       'question': 'What health insurance do you have now?'}}]
        self.request_id = str(uuid.uuid4())
        self.calls, self.responses = [], []
        self.counts = []
        self.agent.count_tokens = self.count
        self.agent.client.transport = self.transport
        self.addCleanup(patch.stopall)
        patch('urllib.request.urlopen', side_effect=AssertionError('No network calls in fault injection')).start()
        patch('natural_agent.time.sleep').start()

    def count(self, _, payload):
        self.counts.append(copy.deepcopy(payload))
        return 300

    def draft(self, **changes):
        return {'reply': 'We can work through the next step.', 'question_target': 'T05',
                'question': 'What health insurance do you have now?', 'report_refs': [], 'evidence_refs': [],
                'agenda_update': {'current_concern': '', 'pause': False},
                'education': {'purpose': 'advance', 'updates': [], 'visual': 'none'}, **changes}

    def transport(self, payload):
        self.calls.append(copy.deepcopy(payload))
        self.assertTrue(self.responses, 'Unexpected additional generation')
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, tuple):
            item, overrides = item
        else:
            overrides = {}
        text = item if isinstance(item, str) else json.dumps(item)
        model = self.agent.client.model
        return {'status': 'completed', 'model': model,
                'service_tier': 'standard' if MODELS[model].provider == 'Anthropic' else 'default',
                'usage': {'input_tokens': 300, 'output_tokens': 70, 'total_tokens': 370,
                          'input_tokens_details': {'cached_tokens': 0}},
                'output': [{'content': [{'type': 'output_text', 'text': text}]}], **overrides}

    def compose(self):
        with self.agent.reserve_turn(stages=('compose',)) as reservation:
            self.reservation = reservation
            return self.agent.compose('fictional-owner', self.context, self.moves, self.request_id, reservation)

    def rows(self):
        with self.agent.budget.db() as db:
            return db.execute('SELECT status,charged,measured,input_bound FROM ai_charges').fetchall()

    def test_same_repair_path_for_every_selectable_model_and_guard_category(self):
        invalid = ['An example amount is $777777.', 'The review happens in February.',
                   'Ask Invented Provider for details.', 'We have verified your coverage.']
        for model in MODELS:
            for reply in invalid:
                with self.subTest(model=model, reply=reply):
                    self.agent.client.model = model
                    self.agent.max_output_tokens = MODELS[model].output_tokens
                    self.request_id = str(uuid.uuid4())
                    self.responses = [self.draft(reply=reply), self.draft()]
                    before = copy.deepcopy(self.context)
                    start = len(self.calls)
                    answer = self.compose()
                    self.assertEqual(answer['reply'], self.draft()['reply'])
                    self.assertEqual(answer['validation_recovery']['replacement'], 'validated_model_repair')
                    self.assertEqual(len(self.calls) - start, 2)
                    self.assertEqual(self.reservation.stage('compose').attempts, 2)
                    inputs = [json.loads(call['input'][0]['content']) for call in self.calls[start:]]
                    self.assertEqual(inputs[0]['resolved_context'], inputs[1]['resolved_context'])
                    self.assertEqual(inputs[0]['question_candidates'], inputs[1]['question_candidates'])
                    self.assertNotIn('validation_feedback', inputs[0])
                    self.assertIn('validation_feedback', inputs[1])
                    self.assertEqual(self.context, before)
        self.assertTrue(all(row[0] == 'settled' and row[1] == row[2] for row in self.rows()))

    def test_valid_whole_reply_survives_invalid_question_without_paid_repair(self):
        self.responses = [self.draft(question_target='unavailable', question='Which invented option?')]
        answer = self.compose()
        self.assertEqual(answer['reply'], self.draft()['reply'])
        self.assertEqual(answer['question'], '')
        self.assertEqual(answer['validation_recovery']['component'], 'reply')
        self.assertEqual(len(self.calls), 1)

    def test_failed_repair_preserves_only_the_independently_checked_question(self):
        bad = self.draft(reply='An example amount is $777777.',
                         education={'purpose': 'teach', 'updates': [{'unearned': 'credit'}], 'visual': 'none'})
        self.responses = [bad, copy.deepcopy(bad)]
        answer = self.compose()
        self.assertEqual(answer['reply'], '')
        self.assertEqual(answer['question'], self.draft()['question'])
        self.assertEqual(answer['education']['updates'], [])
        self.assertEqual(answer['task_work']['check_ids'], [])
        self.assertEqual(answer['validation_recovery']['component'], 'question')
        self.assertEqual(len(self.calls), 2)
        replay = self.compose()
        self.assertEqual(replay, answer)
        self.assertEqual(len(self.calls), 2, 'Replay must not charge for recovery again')
        self.assertNotIn('777777', json.dumps(list(self.agent.cache.values())))

    def test_both_invalid_components_stay_held_after_one_repair(self):
        bad = self.draft(reply='An example amount is $777777.',
                         question='With your $888888 premium, what insurance do you have now?')
        self.responses = [bad, copy.deepcopy(bad)]
        with self.assertRaises(CompositionRejected):
            self.compose()
        self.assertEqual(len(self.calls), 2)
        self.assertFalse(self.agent.cache)
        self.assertTrue(all(row[0] == 'settled' for row in self.rows()))

    def test_freeform_orphan_question_cannot_survive_an_invalid_answer(self):
        bad = self.draft(reply='An example amount is $777777.', question_target=None,
                         question='Would that work for you?')
        self.responses = [bad, copy.deepcopy(bad)]
        with self.assertRaises(CompositionRejected):
            self.compose()
        self.assertFalse(self.agent.cache)

    def test_question_premises_receive_the_answer_factual_checks(self):
        bad = self.draft(reply='An example amount is $777777.',
            question='Your insurance is employer coverage. What insurance do you have now?')
        self.responses = [bad, copy.deepcopy(bad)]
        with self.assertRaises(CompositionRejected):
            self.compose()
        self.assertFalse(self.agent.cache)

    def test_malformed_completed_json_is_settled_then_repaired(self):
        self.responses = ['{broken', self.draft()]
        answer = self.compose()
        self.assertEqual(answer['reply'], self.draft()['reply'])
        self.assertEqual(answer['validation_recovery']['reason'], 'invalid_structure')
        self.assertTrue(all(row[0] == 'settled' for row in self.rows()))

    def test_optional_metadata_failure_does_not_discard_core_or_add_a_call(self):
        draft = self.draft(education={'wrong': 'shape'}, task_work={'wrong': True}, education_followups=9)
        self.responses = [(draft, {'structured_output_error': 'schema_constraints'})]
        answer = self.compose()
        self.assertEqual(answer['reply'], draft['reply'])
        self.assertEqual(answer['education']['updates'], [])
        self.assertEqual(answer['education_followups'], [])
        self.assertEqual(len(self.calls), 1)

    def test_missing_education_is_neutral_metadata(self):
        draft = self.draft()
        draft.pop('education')
        self.responses = [draft]
        answer = self.compose()
        self.assertEqual(answer['reply'], draft['reply'])
        self.assertEqual(answer['education']['updates'], [])

    def test_repair_count_failure_keeps_safe_question_and_cancels_unissued_hold(self):
        self.responses = [self.draft(reply='An example amount is $777777.')]
        def count(_, payload):
            self.counts.append(copy.deepcopy(payload))
            return 0 if 'validation_feedback' in json.loads(payload['input'][0]['content']) else 300
        self.agent.count_tokens = count
        answer = self.compose()
        self.assertEqual(answer['question'], self.draft()['question'])
        self.assertEqual(answer['reply'], '')
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(sorted(row[0] for row in self.rows()), ['cancelled', 'settled'])
        self.assertEqual(self.agent.budget.summary()['reservedOrUncertainUsd'], 0)

    def test_repair_accounting_hold_keeps_safe_question_without_another_call(self):
        self.responses = [self.draft(reply='An example amount is $777777.')]
        transport = self.agent.client.transport
        def exhaust_after_submission(payload):
            response = transport(payload)
            with self.agent.budget.db() as db:
                db.execute("INSERT OR REPLACE INTO ai_meta VALUES('blocked','unverified usage')")
            return response
        self.agent.client.transport = exhaust_after_submission
        answer = self.compose()
        self.assertEqual(answer['reply'], '')
        self.assertEqual(answer['question'], self.draft()['question'])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual([row[0] for row in self.rows()], ['settled'])

    def test_repair_and_connection_recovery_share_one_attempt_slot(self):
        self.responses = [ConnectionResetError(54, 'fictional disconnect'),
                          self.draft(reply='An example amount is $777777.')]
        answer = self.compose()
        self.assertEqual(answer['reply'], '')
        self.assertEqual(answer['question'], self.draft()['question'])
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(sorted(row[0] for row in self.rows()), ['settled', 'uncertain'])

    def test_disconnect_during_repair_retains_original_safe_component(self):
        self.responses = [self.draft(reply='An example amount is $777777.'),
                          ConnectionResetError(54, 'fictional disconnect')]
        answer = self.compose()
        self.assertEqual(answer['reply'], '')
        self.assertEqual(answer['question'], self.draft()['question'])
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(sorted(row[0] for row in self.rows()), ['settled', 'uncertain'])

    def test_provider_billing_failure_does_not_trigger_repair(self):
        self.responses = [({}, {'status': 'failed', 'error': {'code': 'credit_balance_exhausted'}})]
        with self.assertRaises(ModelUnavailable):
            self.compose()
        self.assertEqual(len(self.calls), 1)

    def test_admitted_repair_can_cross_daily_threshold_for_every_model(self):
        for model in MODELS:
            with self.subTest(model=model):
                self.agent.budget = AdvisorDailyBudget.adopt(self.fixture.ledger())
                spec = MODELS[model]
                count = (APPROVED_CAP - 1) // spec.input_rate
                key = self.agent.budget.reserve(count, spec.output_tokens, model)
                self.agent.budget.settle_model(key, {'model': model, 'status': 'completed',
                    'service_tier': 'standard' if spec.provider == 'Anthropic' else 'default',
                    'usage': {'input_tokens': count, 'output_tokens': 0, 'total_tokens': count,
                              'input_tokens_details': {'cached_tokens': 0}}}, model)
                self.agent.client.model = model
                self.agent.max_output_tokens = MODELS[model].output_tokens
                self.request_id = str(uuid.uuid4())
                self.responses = [self.draft(reply='An example amount is $777777.'), self.draft()]
                start = len(self.calls)
                answer = self.compose()
                self.assertEqual(answer['validation_recovery']['replacement'], 'validated_model_repair')
                self.assertEqual(len(self.calls) - start, 2)
                self.assertGreater(self.agent.budget.summary(model)['accountedUsd'], APPROVED_CAP / 1_000_000_000)
                self.assertEqual(self.agent.budget.summary(model)['reservedOrUncertainUsd'], 0)
                self.assertFalse(self.agent.budget.summary(model)['canRequest'])
                with self.assertRaisesRegex(BudgetError, 'has been reached'):
                    self.agent.reserve_turn()

    def test_logs_contain_categories_and_never_rejected_text(self):
        self.responses = [self.draft(reply='An example amount is $777777.'), self.draft()]
        with self.assertLogs('natural_agent', level='WARNING') as logs:
            self.compose()
        output = '\n'.join(logs.output)
        self.assertIn('ungrounded_literal', output)
        self.assertNotIn('777777', output)
        self.assertNotIn('fictional-owner', output)

    def test_standalone_guards_still_reject_unresolved_reports_and_unsupported_findings(self):
        for reply in ('Your premium is $777777.', 'We have verified your coverage.',
                      'Your coverage starts in February.', 'Your insurance is employer coverage.'):
            with self.subTest(reply=reply), self.assertRaises(ModelUnavailable):
                self.agent._validate_composition_core({key: value for key, value in self.draft(reply=reply).items()
                    if key != 'education'}, self.context, _question_candidates(self.moves))


class RecoveryControllerTests(unittest.TestCase):
    """One injected transaction checks state writes, not dialogue quality."""
    def test_completed_turn_replay_is_free_after_crossing_daily_threshold(self):
        budget_fixture = fixtures.NaturalAgentTests()
        budget_fixture.setUp()
        self.addCleanup(budget_fixture.doCleanups)
        fixture = flow_fixtures.NaturalFlowTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        budget = AdvisorDailyBudget.adopt(budget_fixture.ledger())
        budget.seed([('prior', budget.day(), 5_999_999, 0, 0)])
        fixture.flow.agent.budget = budget
        fixture.flow.agent.count_tokens = lambda *_: 300
        fixture.flow.agent.composition_recovery = True
        fixture.extractions = [fixture.extraction([
            fixture.update('RC01', {'choice': 'self'}, 'This is for me.')])]
        fixture.compositions = [{'reply': 'An example amount is $777777.'}, {}]
        payload = fixture.payload({'type': 'message', 'message': 'This is for me.'})
        with patch('urllib.request.urlopen', side_effect=AssertionError('No network calls in fault injection')):
            out = fixture.take(payload)
            self.assertEqual(out['generated']['status'], 'complete')
            self.assertEqual(out['metrics']['llmCalls'], 3)
            self.assertGreater(budget.summary()['accountedUsd'], 15)
            replay = fixture.flow.turn(fixture.owner, payload)
            self.assertEqual(replay['reply'], out['reply'])
            self.assertEqual(len(fixture.calls), 3)
            with self.assertRaisesRegex(BudgetError, 'has been reached'):
                fixture.turn({'type': 'message', 'message': 'Continue.'})
            self.assertEqual(len(fixture.calls), 3)

    def test_profile_evidence_and_delivery_accounting_survive_repair_or_question_only(self):
        for repaired in (True, False):
            with self.subTest(repaired=repaired), patch('urllib.request.urlopen',
                    side_effect=AssertionError('No network calls in fault injection')):
                fixture = flow_fixtures.NaturalFlowTests()
                fixture.setUp()
                self.addCleanup(fixture.doCleanups)
                fixture.flow.agent.composition_recovery = True
                bad = {'reply': 'An example amount is $777777.', 'question_target': 'T05',
                       'question': 'What health insurance do you have now?',
                       'evidence_refs': ['routesintro'],
                       'education': {'purpose': 'teach', 'visual': 'none', 'updates': [{
                           'concept_id': 'coverage_paths', 'depth': 'introduced',
                           'reason': 'new', 'evidence_refs': ['routesintro']}]}}
                good = {**bad, 'reply': 'Original Medicare is the federal program for Parts A and B.'}
                fixture.compositions = [bad, good if repaired else copy.deepcopy(bad)]
                out = fixture.message('This is for me.',
                    [fixture.update('RC01', {'choice': 'self'}, 'This is for me.')])
                self.assertEqual(out['generated']['status'], 'complete')
                self.assertEqual(fixture.flow.value(out['guide'], 'subject.role'), 'self')
                self.assertEqual(out['guide']['fields']['subject.role']['confirmation'], 'reported_by_user')
                self.assertEqual(out['assessment']['nextQuestion']['id'], 'T05')
                self.assertEqual([call['text']['format']['name'] for call in fixture.calls],
                    ['daylight_guide_commands', 'daylight_resolved_conversation', 'daylight_resolved_conversation'])
                self.assertEqual(out['metrics']['llmCalls'], 3)
                contexts = fixture.stage_payloads('daylight_resolved_conversation')
                self.assertEqual(contexts[0]['resolved_context'], contexts[1]['resolved_context'])
                for key in ('reports', 'evidence', 'education_context', 'learner_context'):
                    self.assertIn(key, contexts[1]['resolved_context'])
                self.assertEqual(out['advisor']['visual'], 'none')
                self.assertEqual(out['facts'], [])
                self.assertNotIn('understanding', out)
                self.assertNotIn('777777', json.dumps(out))
                self.assertEqual(bool(out['education']['covered']), repaired)
                self.assertEqual(bool(out['advisor']['teachingFactIds']), repaired)
                # Nov 8, 2026: a question-only retention still shows one reviewed statement.
                self.assertTrue(out['reply'])
                self.assertNotIn('777777', out['reply'])


if __name__ == '__main__':
    unittest.main()
