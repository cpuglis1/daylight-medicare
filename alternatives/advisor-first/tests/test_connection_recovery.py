"""One separately funded recovery of the failed stage, without repeating work."""
import copy
import unittest
import uuid
import tempfile
from pathlib import Path
from unittest.mock import patch

import test_natural_agent as support
from chat import ModelUnavailable
from provider_transport import ProviderTransportError
from advisor_budget import AdvisorDailyBudget
from ai_budget import DailyBudget


class ConnectionRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.case = support.NaturalAgentTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.agent = self.case.agent
        self.agent.budget = self.case.ledger()
        self.agent.connection_retries = 1
        self.transport = self.agent.client.transport

    def statuses(self):
        with self.agent.budget.db() as db:
            return [row[0] for row in db.execute('SELECT status FROM ai_charges ORDER BY rowid')]

    def flaky(self, *, always=False):
        calls = []
        def transport(payload):
            calls.append(payload)
            if always or len(calls) == 1:
                raise ProviderTransportError('receive', 56)
            return self.transport(payload)
        self.agent.client.transport = transport
        return calls

    def test_extraction_reconnects_once_and_accounts_both_attempts(self):
        self.case.answer = self.case.extraction([])
        calls = self.flaky()
        with patch('natural_agent.time.sleep'), self.agent.reserve_turn() as reservation:
            self.agent.extract('owner', 'A fictional report.', self.case.g, {}, str(uuid.uuid4()), reservation)
            self.assertEqual(reservation.stage('extract').attempts, 2)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0], calls[1])
        self.assertEqual(self.statuses(), ['uncertain', 'cancelled', 'settled'])

    def test_composition_reconnects_without_repeating_extraction(self):
        before = copy.deepcopy(self.case.context)
        with patch('natural_agent.time.sleep'), self.agent.reserve_turn() as reservation:
            self.case.answer = self.case.extraction([])
            self.agent.extract('owner', 'A fictional report.', self.case.g, {}, str(uuid.uuid4()), reservation)
            self.case.answer = self.case.composition()
            calls = self.flaky()
            self.agent.compose('owner', self.case.context, self.case.moves, str(uuid.uuid4()), reservation)
            self.assertEqual(reservation.stage('extract').attempts, 1)
            self.assertEqual(reservation.stage('compose').attempts, 2)
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.case.context, before)
        self.assertEqual(self.statuses(), ['settled', 'uncertain', 'settled'])

    def test_persistent_disconnect_stops_after_two_attempts(self):
        calls = self.flaky(always=True)
        with patch('natural_agent.time.sleep'), self.agent.reserve_turn() as reservation:
            with self.assertRaises(ModelUnavailable):
                self.agent.extract('owner', 'A fictional report.', self.case.g, {}, str(uuid.uuid4()), reservation)
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.statuses(), ['uncertain', 'cancelled', 'uncertain'])

    def test_cap_can_deny_recovery_without_another_request(self):
        calls = self.flaky(always=True)
        transport = self.agent.client.transport
        def exhaust_after_submission(payload):
            self.agent.budget.daily_cap_nano_usd = 1
            return transport(payload)
        self.agent.client.transport = exhaust_after_submission
        with patch('natural_agent.time.sleep'), self.agent.reserve_turn() as reservation:
            with self.assertRaises(ModelUnavailable):
                self.agent.extract('owner', 'A fictional report.', self.case.g, {}, str(uuid.uuid4()), reservation)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.statuses(), ['uncertain', 'cancelled'])

    def test_rejected_answer_is_not_retried(self):
        self.case.answer = {**self.case.composition(), 'evidence_refs': ['unreviewed']}
        with self.agent.reserve_turn(stages=('compose',)) as reservation:
            with self.assertRaises(ModelUnavailable):
                self.agent.compose('owner', self.case.context, self.case.moves, str(uuid.uuid4()), reservation)
        self.assertEqual(len(self.case.calls), 1)
        self.assertEqual(self.statuses(), ['settled'])

    def test_selected_premium_models_keep_separate_recovery_receipts(self):
        # Exact 300-token preflight plus each model's output allowance; input
        # is no longer reserved at the removed fixed 16,000-token ceiling.
        for model, hold in [('gpt-6.1-sol', 24_750_000), ('claude-opus-5-5', 49_200_000)]:
            with self.subTest(model=model), tempfile.TemporaryDirectory() as directory:
                self.agent.client.model = model
                self.agent.budget = AdvisorDailyBudget.adopt(DailyBudget(Path(directory) / 'usage.db'),
                    pricing_review_path=Path(__file__).resolve().parents[1] / 'pricing-review.json')
                self.case.answer = self.case.composition()
                calls = []
                def transport(payload):
                    calls.append(payload)
                    if len(calls) == 1:
                        raise ProviderTransportError('receive', 56)
                    return {**self.transport(payload), 'model': model}
                self.agent.client.transport = transport
                with patch('natural_agent.time.sleep'), self.agent.reserve_turn(stages=('compose',)) as reservation:
                    self.agent.compose('owner', self.case.context, self.case.moves, str(uuid.uuid4()), reservation)
                with self.agent.budget.db() as db:
                    rows = db.execute('SELECT status,reserved,charged FROM ai_charges ORDER BY rowid').fetchall()
                self.assertEqual(rows[0], ('uncertain', hold, hold))
                self.assertEqual(rows[1][0], 'settled')
                self.assertEqual(len(calls), 2)
