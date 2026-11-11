"""Adversarial identity, period, quote and source-fidelity boundaries for r5."""
from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import l10_targeted_build as build
import l10_targeted_reconcile as reconcile
import l10_targeted_validate as audit
from l10_targeted_intake import BASE, OUT, read
from l10_targeted_reference import TargetedArchive, TargetedReferenceHeld, source_state


class TargetedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schedules = read(OUT / 'schedules.json')
        cls.rates = read(OUT / 'rate-cells.json')
        cls.by_schedule = {s['id']: s for s in cls.schedules}

    def fixture_archive(self):
        # Isolate request admission; the actual sealed reader is probed after sealing.
        archive = TargetedArchive.__new__(TargetedArchive)
        archive.schedules = self.by_schedule
        archive.rates = {r['id']: r for r in self.rates}
        archive.verify = lambda: None
        return archive

    def test_base_form_does_not_match_high_deductible_form(self):
        self.assertFalse(reconcile.exact_form_mention('FLMESNM10F', 'FLMESNM10F(HD)'))
        self.assertFalse(reconcile.exact_form_mention('FLMESNM10G', 'FLMESNM10G(HD)'))
        self.assertTrue(reconcile.exact_form_mention('FLMESNM10F(HD)', 'Policy FLMESNM10F(HD) 3'))

    def test_fragmented_pdf_currency_is_reassembled(self):
        records = [(10, 100, '$'), (15, 102, '1'), (20, 102, ','), (25, 102, '2'), (30, 102, '3'),
                   (35, 102, '4'), (40, 102, '.'), (45, 102, '5'), (50, 102, '6')]
        self.assertEqual(list(audit.native_money_rows(records).values()), [[(10, '$1,234.56')]])

    def test_fragmented_age_header_keeps_source_position(self):
        self.assertEqual(audit.native_age_anchor([(50, 100, 'A'), (56, 100, 'g'), (61, 100, 'e')]), 50)

    def test_blue_exhibit_date_cannot_supply_approved_interval(self):
        row = next(r for r in self.rates if r['case'] == '25-043172' and r['source_status'] == 'APPROVED')
        self.assertIn('approved_rate_period_unresolved', source_state(self.by_schedule[row['schedule_id']], row, '2026-01-01'))

    def test_source_zero_is_never_a_free_offer(self):
        row = next(r for r in self.rates if r['annual_premium_cents'] == 0)
        self.assertIn('source_zero_meaning_unresolved', source_state(self.by_schedule[row['schedule_id']], row))

    def test_replaced_sources_remain_held(self):
        row = next(r for r in self.rates if r['source_status'] == 'REPLACED')
        self.assertIn('unapproved_or_replaced_source', source_state(self.by_schedule[row['schedule_id']], row))

    def test_prior_period_boundary_is_enforced(self):
        row = next(r for r in self.rates if r['case'] == '25-007663' and r['source_status'] == 'APPROVED')
        s = self.by_schedule[row['schedule_id']]
        self.assertNotIn('outside_sourced_rate_period', source_state(s, row, '2026-07-31'))
        self.assertIn('outside_sourced_rate_period', source_state(s, row, '2026-08-01'))

    def test_research_flag_is_mandatory(self):
        with self.assertRaises(TargetedReferenceHeld):
            self.fixture_archive().observation({'rate_id': self.rates[0]['id']})

    def test_malformed_source_identifier_is_rejected(self):
        for value in [None, [], 7]:
            with self.subTest(value=value), self.assertRaises(TargetedReferenceHeld):
                self.fixture_archive().observation({'rate_id': value}, research=True)

    def test_commercial_or_personal_query_fields_are_rejected(self):
        for key in ['commission', 'age', 'tobacco', 'household_discount']:
            with self.subTest(key=key), self.assertRaises(TargetedReferenceHeld):
                self.fixture_archive().observation({'rate_id': self.rates[0]['id'], key: 1}, research=True)

    def test_wrong_year_and_non_iso_date_are_rejected(self):
        for value in ['2025-12-31', '2027-01-01', '01/01/2026']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                source_state(self.schedules[0], self.rates[0], value)

    def test_blue_auto_payment_amounts_are_not_promoted(self):
        rows = read(OUT / 'blue-carrier-comparisons.json')
        held = [r for r in rows if r['status'] == 'APO_billing_precision_and_conditions_held']
        self.assertEqual(len(held), 340)
        self.assertTrue(all(r['same_arithmetic_amount'] is None and not r['approved_rate_interval_established'] for r in held))

    def test_source_audit_rejects_corrupt_annual_amount(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'build'; shutil.copytree(OUT, out)
            rows = read(out / 'rate-cells.json'); rows[0]['annual_premium_cents'] += 1
            (out / 'rate-cells.json').write_text(json.dumps(rows))
            with self.assertRaises(AssertionError):
                audit.validate(out)

    def test_source_audit_rejects_inferred_original_rate_period(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'build'; shutil.copytree(OUT, out)
            rows = read(out / 'schedules.json'); rows[0]['rate_effective_from'] = '2026-01-01'
            (out / 'schedules.json').write_text(json.dumps(rows))
            with self.assertRaises(AssertionError):
                audit.validate(out)

    def test_sealed_build_and_reconciliation_refuse_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp); (out / 'SEALED').touch()
            with self.assertRaises(ValueError): build.build(out)
            with self.assertRaises(ValueError): reconcile.reconcile(out)


if __name__ == '__main__':
    unittest.main()
