"""Offline checks for fixture admission, visit isolation and transactional caps."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
import socketserver
from tempfile import TemporaryDirectory
import unittest
from threading import Barrier
from unittest.mock import patch

import run_live as runner
from ai_budget import DailyBudget
from natural_agent import TurnReservation
from comparison_profile import SOURCE_PATHS


class RunnerTest(unittest.TestCase):
    """Exercise the adapter and existing advisor without provider connections."""

    def test_reservation_rollback_keeps_run_ceiling_across_utc_dates(self):
        """Each charge, including a midnight rollover, must fit the same run cap."""
        with TemporaryDirectory() as directory:
            budget = DailyBudget(Path(directory) / 'usage.sqlite3')
            runner.AdvisorDailyBudget.adopt(
                budget, pricing_review_path=runner.ADVISOR / 'pricing-review.json')
            checked = datetime.fromisoformat(budget.rates['verified_at']).timestamp()
            budget.clock = lambda: checked
            runner.install_run_budget(budget, 'run', 20_000_000)
            budget.reserve(1000, 900, 'gpt-5.4')
            budget.clock = lambda: checked + 86400
            with self.assertRaisesRegex(runner.BudgetError, 'diagnostic run allowance'):
                budget.reserve(1000, 900, 'gpt-5.4')
            with budget.db() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM ai_charges').fetchone(), (1,))
                self.assertEqual(db.execute('SELECT COUNT(*) FROM diagnostic_charges').fetchone(), (1,))

    def test_counted_request_reprices_same_run_cap_concurrently(self):
        """Two simultaneously repriced calls cannot both pass the run cap."""
        with TemporaryDirectory() as directory:
            budget = DailyBudget(Path(directory) / 'usage.sqlite3')
            runner.AdvisorDailyBudget.adopt(
                budget, pricing_review_path=runner.ADVISOR / 'pricing-review.json')
            checked = datetime.fromisoformat(budget.rates['verified_at']).timestamp()
            budget.clock = lambda: checked
            runner.install_run_budget(budget, 'run', 70_000_000)
            stages = [TurnReservation(budget, 'gpt-5.4', stages=('compose',)).stage('compose')
                      for _ in range(2)]
            barrier = Barrier(2, timeout=5)

            def attempt(stage):
                """Try to fund and issue one stage after both contenders arrive."""
                barrier.wait()
                try:
                    stage.check_input(15000)
                except runner.BudgetError:
                    with self.assertRaisesRegex(runner.BudgetError, 'counted and funded'):
                        stage.issued()
                    return False
                stage.issued()
                return True

            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertCountEqual(pool.map(attempt, stages), [True, False])
            with budget.db() as db:
                self.assertEqual(db.execute('SELECT SUM(charged) FROM ai_charges').fetchone(),
                                 (64_500_000,))

    def test_unbound_case_refused_before_build(self):
        """Calibration-only context may never be treated as executable setup."""
        with patch.object(runner, 'build', side_effect=AssertionError('build called')):
            with self.assertRaises(SystemExit) as error:
                runner.main(['--case', 'question_timing-pause-2', '--owner-authorized-live'])
        self.assertEqual(error.exception.code, 2)

    def test_missing_profile_contract_refused_before_build(self):
        """A missing sealed source fails closed before the paid runtime opens."""
        with patch.object(runner, '_load_contract', side_effect=ValueError), \
                patch.object(runner, 'build', side_effect=AssertionError('build called')):
            with self.assertRaises(SystemExit) as error:
                runner.main(['--case', 'question_timing-pause-1', '--owner-authorized-live'])
        self.assertEqual(error.exception.code, 2)

    @unittest.skipUnless(
        all((runner.REPO / path).is_file() for path in SOURCE_PATHS.values()),
        'Provision the pinned local advisor sources in LIVE_ADAPTER.md.',
    )
    def test_typed_setup_and_history_do_not_cross_trial_owners(self):
        """Use normal state updates and keep fictional exchange history per visit."""
        # The fixture uses the normal pinned profile contract. Provision its
        # source files as documented before running this offline integration test.
        runner._load_contract()
        with TemporaryDirectory() as directory, \
                patch.object(socketserver.TCPServer, 'server_bind'), \
                patch.object(socketserver.TCPServer, 'server_activate'):
            with runner.build(0, fixture=True, database=Path(directory) / 'guest.sqlite3') as service:
                flow = service.adaptive
                pause = runner.STARTS['question_timing-pause-1']
                correction = runner.STARTS['conversational_continuity-correction-1']
                one = runner.seed(flow, 'owner-one', correction)
                two = runner.seed(flow, 'owner-two', pause)
                self.assertNotEqual(one['continuation'], two['continuation'])
                self.assertEqual(flow.value(one['guide'], 'comparison.scope.zip'), '34103')
                self.assertIsNone(flow.value(two['guide'], 'comparison.scope.zip'))
                self.assertEqual(one['record']['facts']['RC01']['value']['choice'], 'self')
                self.assertEqual(two['assessment']['nextQuestion']['id'], 'T10')
                self.assertEqual(len(flow.recent_exchanges('owner-one', None, runner.CONTEXT_POLICY)), 2)
                self.assertFalse(flow.recent_exchanges('owner-two', None, runner.CONTEXT_POLICY))
                with self.assertRaisesRegex(ValueError, 'conversation changed'):
                    runner.turn(flow, 'owner-two', one, {'type': 'refresh'})
                flow.forget_owner('owner-one')
                self.assertFalse(flow.recent_exchanges('owner-one', None, runner.CONTEXT_POLICY))


if __name__ == '__main__':
    unittest.main()
