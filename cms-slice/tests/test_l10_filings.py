"""Consequential date/unit/identity/integrity boundaries for filing research."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import l10_filings_reference as ref
import l10_filings_compare as compare
import l10_filings_packet as packet


class FilingBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive = ref.FilingArchive()
        cls.rates = list(cls.archive.rates.values())

    def sample(self, case, status='APPROVED', zero=False):
        return next((self.archive.schedules[r['schedule_id']], r) for r in self.rates
                    if r['case'] == case and r['source_status'] == status
                    and (r['annual_premium_cents'] == 0) == zero)

    def test_policy_issue_range_cannot_supply_rate_effective_period(self):
        s, r = self.sample('26-018953')
        self.assertEqual(s['policy_issue_range_from'], '8/1/2021')
        self.assertIn('outside_sourced_rate_period', ref.observation_state(s, r, '2026-08-31'))
        self.assertEqual(ref.observation_state(s, r, '2026-09-01'), [])

    def test_future_approved_gpm_is_not_current_october_rate(self):
        s, r = self.sample('26-036521')
        self.assertIn('outside_sourced_rate_period', ref.observation_state(s, r, '2026-10-31'))
        self.assertEqual(ref.observation_state(s, r, '2026-11-01'), [])

    def test_blue_action_date_does_not_create_rate_period(self):
        s, r = self.sample('26-037280')
        self.assertIn('rate_effective_period_unresolved', ref.observation_state(s, r, '2026-11-01'))

    def test_replaced_tables_stay_held(self):
        s, r = self.sample('26-018953', 'REPLACED')
        self.assertIn('superseded_or_unapproved_schedule', ref.observation_state(s, r))

    def test_source_zero_is_never_free_offer(self):
        s, r = self.sample('26-037280', zero=True)
        self.assertIn('source_zero_meaning_unresolved', ref.observation_state(s, r))
        self.assertEqual(r['zero_meaning'], 'unresolved_not_a_free_offer')

    def test_wrong_year_and_non_iso_dates_rejected(self):
        s, r = self.sample('26-007296')
        for d in ['2027-01-01', '2026-2-01', '20261101', 20261101, True]:
            with self.subTest(date=d), self.assertRaises(ValueError):
                ref.observation_state(s, r, d)

    def test_explicit_research_capability_required(self):
        for value in [False, None, 1, 'true']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.archive.observation(self.rates[0]['id'], research=value)

    def test_commercial_personal_and_monthly_inputs_rejected(self):
        for extra in [{'commission': 1}, {'age': 65}, {'form': 'G'}, {'unit': 'USD/month'}, {'year': 2027}]:
            with self.subTest(extra=extra), self.assertRaises(TypeError):
                self.archive.observation(self.rates[0]['id'], research=True, **extra)

    def test_unknown_exact_identity_cannot_return_rate(self):
        with self.assertRaises(ValueError):
            self.archive.observation('different-company:plan-G', research=True)

    def test_annual_observation_preserves_fee_and_acceptance_limits(self):
        s, r = self.sample('26-036521')
        result = self.archive.observation(r['id'], research=True, on_date='2026-11-01')
        self.assertEqual(result['unit'], 'USD/year')
        self.assertEqual(result['annual_premium_cents'], r['annual_premium_cents'])
        self.assertEqual(result['payment_and_fee_fields_raw']['Fee Amount'], '25.00')
        self.assertEqual(result['payment_and_fee_fields_raw']['Modal Factors/Monthly'], '0.0833')
        self.assertIsNone(result['human_acceptance'])
        self.assertIs(result['personal_quote'], False)
        self.assertIs(result['consumer_release_enabled'], False)

    def test_outside_period_lookup_has_no_premium(self):
        s, r = self.sample('26-036521')
        result = self.archive.observation(r['id'], research=True, on_date='2026-10-28')
        self.assertIsNone(result['annual_premium_cents'])
        self.assertIn('outside_sourced_rate_period', result['holds'])

    def test_changed_or_missing_sealed_payload_rejected(self):
        target = str((self.archive.path / 'schedules.json').relative_to(ref.ROOT))
        real = ref.digest
        with patch.object(ref, 'digest', side_effect=lambda p: '0'*64 if Path(p) == ref.ROOT/target else real(p)):
            with self.assertRaises(ref.FilingIntegrityError):
                self.archive.verify()

    def test_digest_audit_rejects_tamper_and_path_escape(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'cell'; p.write_text('annual:1250')
            wanted = ref.digest(p); ref.verify_hashes(d, {'cell': wanted})
            p.write_text('monthly:1250')
            with self.assertRaises(ref.FilingIntegrityError):
                ref.verify_hashes(d, {'cell': wanted})
            with self.assertRaises(ref.FilingIntegrityError):
                ref.verify_hashes(d, {'../outside': wanted})

    def test_sealed_revisions_cannot_be_enriched_or_recompared(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'SEALED').touch()
            with self.assertRaises(ValueError): packet.enrich(d)
            with self.assertRaises(ValueError): compare.run(d)


if __name__ == '__main__':
    unittest.main()
