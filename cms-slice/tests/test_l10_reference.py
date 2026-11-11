"""Release-boundary and source-meaning regressions for the L10 research packet."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import l10_reference as ref
import l10_build as builder

BASE = Path(__file__).resolve().parents[2] / 'docs/data/l10-medigap-2026-10-28'
PACKAGE = Path(os.environ.get('L10_TEST_PACKAGE', BASE / 'build-r2'))


def read(p): return json.loads(Path(p).read_text())


def replace_json(path, data):
    # Replace rather than modifying a hard link to the preserved release.
    tmp = path.with_suffix('.replacement')
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')
    tmp.replace(path)


class L10ReferenceTests(unittest.TestCase):
    def lookup(self, **fields):
        return ref.lookup({'year': 2026, **fields}, PACKAGE, research=True)

    def clone(self, temp):
        p = Path(temp) / 'candidate'
        shutil.copytree(PACKAGE, p, copy_function=os.link)
        shutil.copy2(PACKAGE.parent / (PACKAGE.name + '-validation.json'), p.parent / 'candidate-validation.json')
        return p

    def reseal(self, package, manifest):
        replace_json(package / 'manifest.json', manifest)
        seal = package / 'SEALED'; seal.unlink(); seal.write_text(ref.sha(package / 'manifest.json') + '\n')

    def test_01_default_consumer_access_is_held(self):
        with self.assertRaises(ref.ReferenceHeld): ref.lookup({'year': 2026}, PACKAGE)

    def test_02_research_flag_requires_literal_true(self):
        for flag in [1, 'true', None, False]:
            with self.assertRaises(ref.ReferenceHeld): ref.lookup({'year': 2026}, PACKAGE, research=flag)

    def test_03_wrong_year_county_and_boolean_year_rejected(self):
        for request in [{'year': 2027}, {'year': True}, {'year': '2026'}, {'year': 2026, 'county_fips': '12071'}]:
            with self.assertRaises(ref.ReferenceHeld): ref.lookup(request, PACKAGE, research=True)

    def test_04_personal_and_commercial_inputs_are_rejected(self):
        for key in ['commission', 'carrier_contract', 'preferred_partner', 'health_status', 'income', 'age', 'rank', 'quote']:
            with self.assertRaises(ValueError): self.lookup(**{key: 'x'})

    def test_05_bounded_integer_pagination(self):
        for fields in [{'limit': True}, {'limit': 0}, {'limit': 251}, {'offset': -1}, {'offset': False}]:
            with self.assertRaises(ValueError): self.lookup(**fields)

    def test_06_exact_zip_and_company_identity(self):
        for fields in [{'zip': '33901'}, {'company_names': ['Florida Blue']}, {'variants': ['G', 'G']}, {'variants': None}]:
            with self.assertRaises(ref.ReferenceHeld): self.lookup(**fields)

    def test_07_discovery_is_not_confirmed_sale_or_form_identity(self):
        result = self.lookup(kind='products', limit=250)
        self.assertFalse(result['consumer_release_enabled']); self.assertIsNone(result['human_acceptance'])
        self.assertTrue(all(x['sale_status'] == 'unknown' and not x['complete_product_identity'] for x in result['records']))
        self.assertTrue(all(x['policy_form'] is None for x in result['records']))

    def test_08_high_deductible_and_pre2020_conditions_survive(self):
        result = self.lookup(kind='benefits', variants=['F*', 'G*'])
        self.assertEqual(result['total'], 18)
        self.assertTrue(all('high-deductible' in x['condition_ids'] for x in result['records']))
        self.assertTrue(all('pre-2020' in x['condition_ids'] for x in result['records'] if x['variant'] == 'F*'))
        condition = next(x for x in result['conditions'] if x['id'] == 'high-deductible')
        self.assertEqual(condition['values']['annual_plan_deductible_cents'], 295000)
        self.assertFalse(condition['values']['separate_foreign_deductible_covered'])

    def test_09_foreign_check_does_not_mean_all_billed_charges(self):
        result = self.lookup(kind='benefits', variants=['G'])
        foreign = next(x for x in result['conditions'] if x['id'] == 'foreign')
        self.assertEqual(foreign['values']['covered_charge_percent'], 80)
        self.assertEqual(foreign['values']['first_trip_days'], 60)
        self.assertEqual(foreign['values']['lifetime_limit_cents'], 5000000)

    def test_10_kl_part_b_requirement_and_n_inpatient_exception(self):
        result = self.lookup(kind='benefits', variants=['K', 'L', 'N'])
        c = {x['id']: x for x in result['conditions']}
        self.assertTrue(c['kl-limits']['values']['part_b_deductible_also_required'])
        self.assertTrue(c['n-copays']['values']['er_inpatient_exception'])

    def test_11_mixed_select_booklet_columns_are_not_all_select(self):
        rows = read(PACKAGE / 'carrier-table-observations.json')
        mixed = [x for x in rows if x['source_id'] == 'florida-blue-select-2026']
        self.assertEqual(len(mixed), 280)
        self.assertEqual({x['variant'] for x in mixed if x['select']}, {'B', 'C', 'D', 'M'})
        self.assertEqual({x['variant'] for x in mixed if not x['select']}, {'A', 'C', 'F'})

    def test_12_monthly_carrier_rates_stay_unquoted_and_undated(self):
        result = self.lookup(kind='carrier_tables', variants=['G'])
        self.assertTrue(all(x['unit'] == 'USD/month' and x['actual_filed_rate_effective_date'] is None and not x['personal_quote'] and not x['filed_table_reproduction'] for x in result['records']))
        self.assertEqual({x['payment_basis'] for x in result['records']}, {'regular_monthly', 'automatic_payment_option'})

    def test_13_no_silent_filter_ignoring(self):
        for fields in [{'kind': 'benefits', 'company_names': ['BLUE CROSS & BLUE SHIELD OF FLORIDA, INC.']}, {'kind': 'insurers', 'variants': ['G']}, {'kind': 'products', 'zip': '34102'}]:
            with self.assertRaises(ValueError): self.lookup(**fields)

    def test_14_source_underwriting_flag_is_not_personal_gi(self):
        rows = read(PACKAGE / 'source-listings.json')
        self.assertTrue(any(x['raw_underwriting_code'] == 'y' for x in rows))
        self.assertTrue(all(x['source_ui_underwriting_label'] == 'Underwritten' for x in rows if x['raw_underwriting_code'] == 'y'))
        self.assertTrue(all(x['source_ui_label_is_personal_right'] is False and x['personal_eligibility'] == 'not_determined' for x in rows))

    def test_15_unknown_and_zero_and_fractional_money(self):
        self.assertIsNone(builder.money(None)); self.assertEqual(builder.money('0.00'), 0)
        self.assertEqual(builder.money('2893.98'), 289398)
        for value in ['-1', 'NaN', 'Infinity', '1.001']:
            with self.assertRaises(ValueError): builder.money(value)

    def test_16_missing_products_and_display_omissions_stay_visible(self):
        anomaly = read(PACKAGE / 'source-anomalies.json')
        self.assertEqual(anomaly['raw_rows_omitted_from_CHOICES_display'], 4000)
        self.assertEqual(len(anomaly['carrier_only_discovery_products']), 4)
        ledger = read(PACKAGE / 'required-coverage-ledger.json')
        self.assertEqual(len(ledger['listings']), len(read(PACKAGE / 'source-listings.json')))
        self.assertFalse(ledger['universe']['complete_2026_effective_Collier_denominator'])
        self.assertTrue(ledger['internal_work_remaining'])

    def test_17_historical_filings_are_not_current_sale(self):
        rows = read(PACKAGE / 'insurer-catalog.json')
        self.assertTrue(any(x['choices_observation_count'] == 0 for x in rows))
        self.assertTrue(all(x['current_collier_sale'] == 'unknown' and not x['complete_2026_forms'] for x in rows))

    def test_18_missing_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p = self.clone(temp); (p / 'product-discovery-map.json').unlink()
            with self.assertRaises(ref.ReferenceHeld): ref.verify(p)

    def test_19_resealed_promoted_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p = self.clone(temp); m = read(p / 'manifest.json'); m['consumer_release_enabled'] = True
            self.reseal(p, m)
            with self.assertRaises(ref.ReferenceHeld): ref.verify(p)

    def test_20_resealed_changed_data_needs_new_independent_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            p = self.clone(temp); data = read(p / 'standardized-benefits.json')
            data['plans'][0]['annual_plan_deductible_cents'] = 1
            replace_json(p / 'standardized-benefits.json', data)
            m = read(p / 'manifest.json'); m['files_sha256']['standardized-benefits.json'] = ref.sha(p / 'standardized-benefits.json')
            self.reseal(p, m)
            with self.assertRaises(ref.ReferenceHeld): ref.verify(p)

    def test_21_stale_validation_receipt_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p = self.clone(temp); v = read(p.parent / 'candidate-validation.json')
            v['manifest_sha256'] = '0' * 64
            replace_json(p.parent / 'candidate-validation.json', v)
            with self.assertRaises(ref.ReferenceHeld): ref.verify(p)

    def test_22_under65_age_bands_do_not_imply_right_to_buy(self):
        rows = read(PACKAGE / 'carrier-table-observations.json')
        self.assertTrue(any(x['age_band_raw'] == 'Under 65' for x in rows))
        self.assertTrue(all(not x['personal_quote'] for x in rows))
        self.assertEqual(read(PACKAGE / 'coverage.json')['verified_filed_rate_models'], 0)


if __name__ == '__main__': unittest.main(verbosity=2)
