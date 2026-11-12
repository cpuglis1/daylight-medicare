"""Provider accounting tests; temporary ledgers only, no provider requests."""
import unittest

import test_advisor_budget as fixtures
from advisor_budget import AdvisorDailyBudget
from advisor_models import MODELS
from ai_budget import BudgetError
from natural_agent import ReservedStage, TurnReservation


class ProviderBudgetTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.AdvisorBudgetTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.budget = self.case.local()

    def test_exhausted_openai_blocks_both_gpt_models_and_allows_anthropic(self):
        self.case.seed_usd(1500)
        for model in ('gpt-5.4', 'gpt-6.1-sol'):
            self.assertFalse(self.budget.summary(model)['canRequest'])
            with self.assertRaisesRegex(BudgetError, 'OpenAI allowance'):
                TurnReservation(self.budget, model)
        with TurnReservation(self.budget, 'claude-opus-5-5') as turn:
            turn.stage('compose').check_input(1000)
            self.assertEqual(self.budget.summary('gpt-5.4')['accountedUsd'], 15)
            self.assertTrue(self.budget.summary('claude-opus-5-5')['canRequest'])

    def test_exhausted_anthropic_does_not_consume_openai_allowance(self):
        self.case.seed_usd(1500, model='claude-opus-5-5')
        self.assertFalse(self.budget.summary('claude-opus-5-5')['canRequest'])
        with self.assertRaisesRegex(BudgetError, 'Anthropic allowance'):
            self.budget.reserve(1000, 2400, 'claude-opus-5-5')
        with TurnReservation(self.budget, 'gpt-6.1-sol') as turn:
            turn.stage('extract').check_input(1000)
            self.assertEqual(self.budget.summary('claude-opus-5-5')['accountedUsd'], 15)
        self.assertEqual(self.budget.summary('gpt-6.1-sol')['remainingUsd'], 15)

    def test_gpt_models_share_provider_but_keep_their_exact_prices(self):
        for model in ('gpt-5.4', 'gpt-6.1-sol'):
            key = self.budget.reserve(1000, MODELS[model].output_tokens, model)
            self.budget.settle_model(key, {**fixtures.completed(), 'model': model}, model)
        summaries = self.budget.provider_summaries()
        self.assertEqual(summaries['OpenAI']['estimatedUsd'], .007)
        self.assertEqual(summaries['Anthropic']['estimatedUsd'], 0)
        self.assertEqual(self.budget.summary('gpt-5.4')['accountedUsd'],
                         self.budget.summary('gpt-6.1-sol')['accountedUsd'])
        self.assertEqual(summaries['Anthropic']['maxOutputTokens'], 2400)

    def test_uncertain_holds_stay_with_provider_across_midnight(self):
        for model, spec in MODELS.items():
            key = self.budget.reserve(1000, spec.output_tokens, model)
            self.budget.uncertain(key)
        self.case.now[0] += 86400
        self.assertEqual(self.budget.summary('gpt-6.1-sol')['reservedOrUncertainUsd'], .0425)
        self.assertEqual(self.budget.summary('claude-opus-5-5')['reservedOrUncertainUsd'], .052)
        with self.budget.db() as db:
            self.assertEqual(self.budget._amounts(db, self.budget.day())[0], 94_500_000)

    def test_legacy_attribution_is_additive_and_idempotent(self):
        with self.budget.db() as db:
            for key, reserved, output in [('old-sol', 64_000_000, 2400),
                                           ('old-claude', 112_000_000, 2400),
                                           ('old-gpt', 53_500_000, 900)]:
                db.execute('INSERT INTO ai_charges VALUES(?,?,NULL,?,?,NULL,?,?,?,NULL,NULL,NULL)',
                           (key, self.budget.day(), reserved, reserved, 'uncertain', 16000, output))
        before = self.case.rows()
        for _ in range(2):
            AdvisorDailyBudget.adopt(self.budget)
            self.assertEqual(self.case.rows(), before)
        with self.budget.db() as db:
            rows = db.execute('SELECT charge_id,model,provider,attribution FROM advisor_charge_models ORDER BY charge_id').fetchall()
        self.assertEqual(rows, [
            ('old-claude', 'claude-opus-5-5', 'Anthropic', 'legacy_unique_rate_match'),
            ('old-gpt', 'gpt-5.4', 'OpenAI', 'legacy_unique_rate_match'),
            ('old-sol', 'gpt-6.1-sol', 'OpenAI', 'legacy_unique_rate_match')])

    def test_unattributable_cost_stays_visible_and_never_becomes_free_allowance(self):
        with self.budget.db() as db:
            db.execute('INSERT INTO ai_charges VALUES(?,?,NULL,?,?,NULL,?,?,?,NULL,NULL,NULL)',
                       ('unknown', self.budget.day(), 10_000_000, 10_000_000, 'uncertain', 0, 0))
        for model in MODELS:
            summary = self.budget.summary(model)
            self.assertEqual(summary['unattributedUsd'], .01)
            self.assertFalse(summary['canRequest'])
            with self.assertRaisesRegex(BudgetError, 'provider reconciliation'):
                TurnReservation(self.budget, model)
        self.assertEqual(len(self.case.rows()), 1)

    def test_charge_cannot_be_recounted_or_settled_as_another_model(self):
        key = self.budget.reserve(1000, 2400, 'claude-opus-5-5')
        before = self.case.rows()
        with self.assertRaisesRegex(BudgetError, 'different or unknown model'):
            ReservedStage(self.budget, key, 'gpt-5.4').check_input(1000)
        with self.assertRaisesRegex(BudgetError, 'different or unknown model'):
            self.budget.settle_model(key, fixtures.completed(), 'gpt-5.4')
        self.assertEqual(self.case.rows(), before)


if __name__ == '__main__':
    unittest.main()
