"""Reviewed local cap changes, with synthetic ledgers and no provider requests."""
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import server  # Registers the read-only pinned imports.
from ai_budget import BudgetError, DailyBudget, NANO
from advisor_budget import AdvisorDailyBudget, APPROVED_CAP
from natural_agent import TurnReservation
from advisor_models import MODELS
from request_limits import INPUT_TOKENS, OUTPUT_TOKENS, REQUEST_BYTES


NOW = datetime(2026, 10, 30, 16, tzinfo=timezone.utc).timestamp()


def completed(i=1000, o=100):
    return {'status': 'completed', 'model': 'gpt-5.4', 'service_tier': 'default',
            'usage': {'input_tokens': i, 'output_tokens': o, 'total_tokens': i + o,
                      'input_tokens_details': {'cached_tokens': 0}}}


class AdvisorBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'budget/usage.sqlite3'
        self.now = [NOW]
        self.base = DailyBudget(self.path, clock=lambda: self.now[0])

    def local(self, budget=None):
        return AdvisorDailyBudget.adopt(self.base if budget is None else budget)

    def rows(self):
        with sqlite3.connect(self.path) as db:
            return db.execute('SELECT * FROM ai_charges ORDER BY id').fetchall()

    def seed_usd(self, cents, key='prior'):
        # Verified input-only price: 4,000 tokens per cent.
        self.base.seed([(key, self.base.day(), cents * 4000, 0, 0)])

    def policy(self, value):
        path = Path(self.temp.name) / 'policy.json'
        path.write_text(json.dumps(value))
        return path

    def test_adoption_preserves_identity_rows_inode_and_existing_holds(self):
        key = self.base.reserve(1000, 900, 'gpt-5.4')
        self.base.uncertain(key)
        self.seed_usd(120)
        before, inode = self.rows(), self.path.stat().st_ino
        references = [self.base, SimpleNamespace(budget=self.base)]
        closed_over_budget = lambda: self.base.summary()
        local = self.local()
        self.assertIs(local, references[0])
        self.assertIs(local, references[1].budget)
        self.assertEqual(self.rows(), before)
        self.assertEqual(self.path.stat().st_ino, inode)
        self.assertEqual(closed_over_budget()['dailyLimitUsd'], 5)
        self.assertEqual(local.summary()['accountedUsd'], 1.216)
        self.assertEqual(local.summary()['reservedOrUncertainUsd'], .016)
        self.assertEqual(local.summary()['remainingUsd'], 3.784)

    def test_original_writers_keep_one_dollar_policy_on_the_same_aggregate(self):
        self.seed_usd(120)
        local = self.local()
        original = DailyBudget(self.path, clock=lambda: self.now[0])
        self.assertEqual(original.summary()['dailyLimitUsd'], 1)
        self.assertFalse(original.summary()['canRequest'])
        with self.assertRaises(BudgetError):
            original.reserve(1000, 900, 'gpt-5.4')
        local.reserve(1000, 900, 'gpt-5.4')
        self.assertEqual(local.summary()['accountedUsd'], original.summary()['accountedUsd'])
        self.assertEqual(local.summary()['remainingUsd'], 3.784)

    def test_single_request_accepts_exact_five_dollar_boundary_then_rejects(self):
        self.base.seed([('prior', self.base.day(), 1986600, 0, 0)])
        local = self.local()
        local.reserve(8000, 900, 'gpt-5.4')
        self.assertEqual(local.summary()['accountedUsd'], 5)
        before = self.rows()
        with self.assertRaises(BudgetError):
            local.reserve(1, 900, 'gpt-5.4')
        self.assertEqual(self.rows(), before)

    def test_complete_two_stage_turn_can_spend_above_one_dollar(self):
        self.seed_usd(120)
        local = self.local()
        with TurnReservation(local, 'gpt-5.4') as reservation:
            self.assertIsNotNone(reservation.stage('extract').key)
            self.assertIsNotNone(reservation.stage('compose').key)
            self.assertEqual(local.summary()['reservedOrUncertainUsd'], .027)
        self.assertEqual(local.summary()['accountedUsd'], 1.2)
        self.assertEqual([row[6] for row in self.rows()].count('cancelled'), 2)

    def test_complete_turn_rejection_is_atomic_with_one_stage_of_headroom(self):
        self.seed_usd(498)
        local = self.local()
        before = self.rows()
        with self.assertRaises(BudgetError):
            TurnReservation(local, 'gpt-5.4')
        self.assertEqual(self.rows(), before)

    def test_concurrent_turns_cannot_each_claim_the_same_headroom(self):
        self.seed_usd(496)
        self.local()
        barrier, results, reservations, errors = threading.Barrier(4), [], [], []
        lock = threading.Lock()
        def attempt():
            try:
                budget = self.local(DailyBudget(self.path, clock=lambda: NOW))
                barrier.wait(timeout=10)
                reservation = TurnReservation(budget, 'gpt-5.4')
                with lock:
                    results.append('reserved')
                    reservations.append(reservation)
            except BudgetError:
                with lock:
                    results.append('rejected')
            except BaseException as error:
                with lock:
                    errors.append(error)
        workers = [threading.Thread(target=attempt) for _ in range(4)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=15)
        try:
            self.assertFalse(errors)
            self.assertFalse(any(worker.is_alive() for worker in workers))
            self.assertEqual(results.count('reserved'), 1)
            self.assertEqual(results.count('rejected'), 3)
            self.assertEqual(self.base.summary()['accountedUsd'], 4.987)
        finally:
            for reservation in reservations:
                reservation.close()

    def test_settlement_is_idempotent_and_uncertain_holds_cross_midnight(self):
        local = self.local()
        key = local.reserve(1000, 900, 'gpt-5.4')
        local.settle(key, completed())
        local.settle(key, completed())
        held = local.reserve(1000, 900, 'gpt-5.4')
        local.uncertain(held)
        self.assertEqual(local.summary()['estimatedUsd'], .004)
        self.now[0] += 86400
        self.assertEqual(local.summary()['estimatedUsd'], 0)
        self.assertEqual(local.summary()['reservedOrUncertainUsd'], .016)
        self.assertEqual(local.summary()['remainingUsd'], 4.984)

    def test_missing_usage_still_holds_and_blocks_all_paid_requests(self):
        local = self.local()
        key = local.reserve(1000, 900, 'gpt-5.4')
        with self.assertRaises(BudgetError):
            local.settle(key, {})
        self.assertFalse(local.summary()['canRequest'])
        self.assertEqual(local.summary()['reservedOrUncertainUsd'], .016)
        with self.assertRaises(BudgetError):
            local.reserve(1000, 900, 'gpt-5.4')
        with self.assertRaises(BudgetError):
            TurnReservation(local, 'gpt-5.4')

    def test_rate_expiry_and_clock_rollback_cannot_create_allowance(self):
        local = self.local()
        local.summary()
        self.now[0] -= 86400
        self.assertFalse(local.summary()['canRequest'])
        with self.assertRaises(BudgetError):
            local.reserve(1000, 900, 'gpt-5.4')
        self.now[0] = NOW + 8 * 86400
        self.assertFalse(local.summary()['canRequest'])
        with self.assertRaises(BudgetError):
            TurnReservation(local, 'gpt-5.4')

    def test_policy_must_be_exact_reviewed_integer_five_and_utc(self):
        approved = {'version': 1, 'daily_cap_nano_usd': APPROVED_CAP, 'reset_timezone': 'UTC'}
        invalid = [
            {**approved, 'version': True}, {**approved, 'version': 2},
            {**approved, 'daily_cap_nano_usd': NANO},
            {**approved, 'daily_cap_nano_usd': 10 * NANO},
            {**approved, 'daily_cap_nano_usd': float(APPROVED_CAP)},
            {**approved, 'reset_timezone': 'America/New_York'},
            {**approved, 'request_override': 5},
        ]
        for policy in invalid:
            with self.subTest(policy=policy):
                with self.assertRaises(BudgetError):
                    AdvisorDailyBudget.adopt(self.base, policy_path=self.policy(policy))
                self.assertIs(type(self.base), DailyBudget)
        with self.assertRaises(BudgetError):
            AdvisorDailyBudget.adopt(self.base, policy_path=Path(self.temp.name) / 'absent')

    def test_environment_and_instance_assignment_cannot_increase_policy(self):
        with patch.dict('os.environ', {'DAYLIGHT_AI_DAILY_CAP': '500', 'OPENAI_DAILY_LIMIT': '500'}):
            local = self.local()
            self.assertEqual(local.summary()['dailyLimitUsd'], 5)
            with self.assertRaises(AttributeError):
                local.daily_cap_nano_usd = 500 * NANO
        self.assertEqual(local.summary()['dailyLimitUsd'], 5)

    def test_local_input_headroom_keeps_output_model_and_invalid_usage_guards(self):
        local = self.local()
        for i, o in [(0, 900), (-1, 900), (1000, 901), (1000, 899), (True, 900)]:
            with self.assertRaises(BudgetError):
                local.reserve(i, o, 'gpt-5.4')
        with self.assertRaises(BudgetError):
            local.reserve(1000, 900, 'another-model')
        self.assertFalse(self.rows())

    def test_larger_input_settles_and_original_variant_stays_at_eight_thousand(self):
        local = self.local()
        self.assertIsNone(INPUT_TOKENS)
        self.assertIsNone(local.summary()['maxInputTokens'])
        key = local.reserve(20000, OUTPUT_TOKENS, 'gpt-5.4')
        self.assertEqual(local.summary()['reservedOrUncertainUsd'], .0635)
        local.settle(key, completed(i=20000, o=OUTPUT_TOKENS))
        self.assertEqual(local.summary()['estimatedUsd'], .0635)
        self.assertEqual(local.summary()['dailyLimitUsd'], 5)
        original = DailyBudget(self.path, clock=lambda: self.now[0])
        with self.assertRaises(BudgetError):
            original.reserve(8001, 900, 'gpt-5.4')
        self.assertEqual(original.rates['max_input_tokens'], 8000)
        from natural_agent import NaturalAgent, ReservedStage
        from narrative_agent import NarrativeAgent
        self.assertEqual(NaturalAgent.max_input_bytes, REQUEST_BYTES)
        self.assertEqual(NarrativeAgent.max_input_bytes, REQUEST_BYTES)
        ReservedStage(None).check_input(20000)
        for count in (0, -1, True, 1.5, '20000'):
            with self.assertRaises(BudgetError):
                ReservedStage(None).check_input(count)

    def test_large_count_funds_each_model_and_settles_exact_usage(self):
        local = self.local()
        for model, spec in MODELS.items():
            with self.subTest(model=model):
                with TurnReservation(local, model, stages=('compose',)) as reservation:
                    stage = reservation.stage('compose')
                    with self.assertRaisesRegex(BudgetError, 'counted and funded'):
                        stage.issued()
                    stage.check_input(50000)
                    amount = 50000 * max(spec.input_rate, spec.cache_write_rate) + spec.output_tokens * spec.output_rate
                    with local.db() as db:
                        self.assertEqual(db.execute('SELECT reserved,charged,input_bound,output_bound FROM ai_charges WHERE id=?',
                            (stage.key,)).fetchone(), (amount, amount, 50000, spec.output_tokens))
                    stage.issued()
                    response = completed(i=50000, o=100)
                    response.update(model=model, service_tier='standard' if spec.provider == 'Anthropic' else 'default')
                    stage.settle(response)
                with local.db() as db:
                    self.assertEqual(db.execute('SELECT measured,status FROM ai_charges WHERE id=?',
                        (stage.key,)).fetchone(), (50000 * spec.input_rate + 100 * spec.output_rate, 'settled'))
                self.assertEqual(local.summary()['reservedOrUncertainUsd'], 0)

    def test_exact_count_refunding_is_idempotent_before_submission_only(self):
        local = self.local()
        with TurnReservation(local, 'claude-opus-5-5', stages=('compose',)) as reservation:
            stage = reservation.stage('compose')
            for count in (30000, 20000, 20000):
                stage.check_input(count)
                self.assertEqual(local.summary()['accountedUsd'], (count * 4000 + 48_000_000) / NANO)
            stage.issued()
            with self.assertRaises(BudgetError):
                stage.check_input(1)
        self.assertEqual(local.summary()['reservedOrUncertainUsd'], .128)

    def test_opus_exact_daily_boundary_accepts_then_refuses_one_extra_token(self):
        self.seed_usd(486)
        local = self.local()
        with TurnReservation(local, 'claude-opus-5-5', stages=('compose',)) as reservation:
            stage = reservation.stage('compose')
            stage.check_input(23000)
            self.assertEqual(local.summary()['accountedUsd'], 5)
            before = self.rows()
            with self.assertRaisesRegex(BudgetError, 'shared \\$5 daily'):
                stage.check_input(23001)
            self.assertEqual(self.rows(), before)
            with self.assertRaisesRegex(BudgetError, 'counted and funded'):
                stage.issued()
        self.assertEqual(local.summary()['accountedUsd'], 4.86)

    def test_later_stage_budget_failure_keeps_the_completed_receipt(self):
        self.seed_usd(494)
        local = self.local()
        with TurnReservation(local, 'gpt-5.4') as reservation:
            extraction = reservation.stage('extract')
            extraction.check_input(10000)
            extraction.issued()
            extraction.settle(completed(i=10000))
            with self.assertRaisesRegex(BudgetError, 'shared \\$5 daily'):
                reservation.stage('compose').check_input(30000)
        with local.db() as db:
            self.assertEqual(db.execute('SELECT status,charged FROM ai_charges WHERE id=?',
                (extraction.key,)).fetchone(), ('settled', 26_500_000))
        self.assertEqual(local.summary()['accountedUsd'], 4.9665)
        self.assertEqual(local.summary()['reservedOrUncertainUsd'], 0)

    def test_recovery_requires_new_count_and_preserves_original_hold(self):
        local = self.local()
        with TurnReservation(local, 'claude-opus-5-5', stages=('compose',)) as reservation:
            stage = reservation.stage('compose')
            stage.check_input(20000)
            stage.issued()
            first_key = stage.key
            self.assertTrue(stage.recover())
            self.assertNotEqual(stage.key, first_key)
            with self.assertRaisesRegex(BudgetError, 'counted and funded'):
                stage.issued()
            stage.check_input(25000)
            self.assertEqual(local.summary()['reservedOrUncertainUsd'], .276)
        self.assertEqual(local.summary()['reservedOrUncertainUsd'], .128)
        self.now[0] += 86400
        self.assertEqual(local.summary()['reservedOrUncertainUsd'], .128)

    def test_concurrent_count_funding_cannot_spend_the_same_headroom(self):
        self.seed_usd(480)
        local = self.local()
        reservations = [TurnReservation(local, 'claude-opus-5-5', stages=('compose',)) for _ in range(4)]
        barrier, results, errors = threading.Barrier(4), [], []
        lock = threading.Lock()
        def fund(reservation):
            try:
                barrier.wait(timeout=10)
                reservation.stage('compose').check_input(1000)
                with lock:
                    results.append('funded')
            except BudgetError:
                with lock:
                    results.append('rejected')
            except BaseException as error:
                with lock:
                    errors.append(error)
        workers = [threading.Thread(target=fund, args=(reservation,)) for reservation in reservations]
        try:
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(timeout=15)
            self.assertFalse(errors)
            self.assertFalse(any(worker.is_alive() for worker in workers))
            self.assertEqual(sorted(results), ['funded', 'funded', 'rejected', 'rejected'])
            self.assertEqual(local.summary()['accountedUsd'], 5)
        finally:
            for reservation in reservations:
                reservation.close()
        self.assertEqual(local.summary()['accountedUsd'], 4.8)

    def service_stub(self):
        budget = self.base
        agent = SimpleNamespace(budget=budget)
        adaptive = SimpleNamespace(agent=SimpleNamespace(budget=budget),
                                   validate=lambda guide, record: (guide, record),
                                   initial=lambda: ({}, {}))
        return SimpleNamespace(
            RequestHandlerClass=type('FixtureHandler', (), {}),
            budget=budget, agent=agent,
            readiness_agent=SimpleNamespace(budget=budget),
            readiness_conversation=SimpleNamespace(agent=SimpleNamespace(budget=budget)),
            adaptive=adaptive,
            profile_gate=SimpleNamespace(validate_inputs=lambda guide, record: (guide, record)),
            profiles=SimpleNamespace(save=lambda *args: None, delete=lambda *args: None),
            handler_status=lambda: budget.summary(),
            server_close=lambda: None)

    def test_local_service_adopts_one_object_for_status_and_every_agent(self):
        service = self.service_stub()
        review = json.loads((HERE / 'pricing-review.json').read_text())
        self.now[0] = datetime.fromisoformat(review['verified_at']).timestamp()
        original = DailyBudget(self.path, clock=lambda: self.now[0])
        with self.assertRaisesRegex(BudgetError, 'review expired'):
            original.check_rates('gpt-5.4')
        with patch.object(server, 'make_server', return_value=service):
            built = server.build(0, fixture=True, database=Path(self.temp.name) / 'guides.sqlite3')
        self.assertIs(built, service)
        references = [built.agent.budget, built.readiness_agent.budget,
                      built.readiness_conversation.agent.budget, built.adaptive.agent.budget]
        self.assertTrue(all(value is built.budget for value in references))
        self.assertEqual(built.handler_status()['dailyLimitUsd'], 5)
        self.assertTrue(built.handler_status()['canRequest'])
        self.assertIs(type(built.budget), AdvisorDailyBudget)
        self.assertEqual(built.budget.rates, {**original.rates, **review})
        with TurnReservation(built.budget, 'gpt-5.4'):
            self.assertEqual(built.handler_status()['reservedOrUncertainUsd'], .027)
        self.now[0] = datetime.fromisoformat(review['valid_until']).timestamp()
        self.assertFalse(built.handler_status()['canRequest'])
        with self.assertRaisesRegex(BudgetError, 'review expired'):
            TurnReservation(built.budget, 'gpt-5.4')

    def test_local_pricing_review_cannot_override_pinned_rates(self):
        review = json.loads((HERE / 'pricing-review.json').read_text())
        with self.assertRaisesRegex(BudgetError, 'pricing review is invalid'):
            AdvisorDailyBudget.adopt(
                self.base, pricing_review_path=self.policy({**review, 'input_nano_usd_per_token': 0}))
        self.assertIs(type(self.base), DailyBudget)

    def test_policy_startup_failure_closes_service_before_return(self):
        service, closed = self.service_stub(), []
        service.server_close = lambda: closed.append(True)
        with patch.object(server, 'make_server', return_value=service), \
                patch.object(server.AdvisorDailyBudget, 'adopt', side_effect=BudgetError('policy unavailable')):
            with self.assertRaises(BudgetError):
                server.build(0, fixture=True, database=Path(self.temp.name) / 'guides.sqlite3')
        self.assertEqual(closed, [True])


if __name__ == '__main__':
    unittest.main()
