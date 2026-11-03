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
            self.assertEqual(local.summary()['reservedOrUncertainUsd'], .067)
        self.assertEqual(local.summary()['accountedUsd'], 1.2)
        self.assertEqual([row[6] for row in self.rows()].count('cancelled'), 2)

    def test_complete_turn_rejection_is_atomic_with_one_stage_of_headroom(self):
        self.seed_usd(495)
        local = self.local()
        before = self.rows()
        with self.assertRaises(BudgetError):
            TurnReservation(local, 'gpt-5.4')
        self.assertEqual(self.rows(), before)

    def test_concurrent_turns_cannot_each_claim_the_same_headroom(self):
        self.seed_usd(490)
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
            self.assertEqual(self.base.summary()['accountedUsd'], 4.967)
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

    def test_original_token_limits_and_pricing_are_unchanged(self):
        local = self.local()
        for i, o in [(8001, 900), (0, 900), (1000, 901), (1000, 899), (True, 900)]:
            with self.assertRaises(BudgetError):
                local.reserve(i, o, 'gpt-5.4')
        with self.assertRaises(BudgetError):
            local.reserve(1000, 900, 'another-model')
        self.assertFalse(self.rows())

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
        with patch.object(server, 'make_server', return_value=service):
            built = server.build(0, fixture=True, database=Path(self.temp.name) / 'guides.sqlite3')
        self.assertIs(built, service)
        references = [built.agent.budget, built.readiness_agent.budget,
                      built.readiness_conversation.agent.budget, built.adaptive.agent.budget]
        self.assertTrue(all(value is built.budget for value in references))
        self.assertEqual(built.handler_status()['dailyLimitUsd'], 5)
        self.assertIs(type(built.budget), AdvisorDailyBudget)

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
