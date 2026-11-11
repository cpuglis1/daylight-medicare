"""Financial unit and missing-state safeguards for published cost schedules."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from l06_cost_build import BENEFICIARY, INSULIN, model_row
from l06_cost_validate import check_model


class CostScheduleTests(unittest.TestCase):
    def beneficiary(self):
        raw = {k: '0' for k in BENEFICIARY}
        raw.update(CONTRACT_ID='H9999', PLAN_ID='001', SEGMENT_ID='000', COVERAGE_LEVEL='1',
                   TIER='1', DAYS_SUPPLY='1', TIER_SPECIALTY_YN='N', DED_APPLIES_YN='N')
        return raw

    def test_zero_copay_is_distinct_from_channel_not_offered(self):
        raw = self.beneficiary()
        raw['COST_TYPE_NONPREF'] = '1'
        modeled = model_row('beneficiary', raw, 'EA')
        self.assertEqual(modeled['COST_AMT_NONPREF']['value'], '0')
        self.assertEqual(modeled['COST_AMT_NONPREF']['unit'], 'USD_per_source_supply')
        self.assertIsNone(modeled['COST_AMT_PREF']['value'])
        self.assertEqual(modeled['COST_AMT_PREF']['meaning'], 'channel_not_offered')
        check_model(raw, modeled, 'beneficiary', 'EA')

    def test_coinsurance_fraction_is_not_a_dollar_amount(self):
        raw = self.beneficiary()
        raw.update(COST_TYPE_NONPREF='2', COST_AMT_NONPREF='0.25')
        modeled = model_row('beneficiary', raw, 'EA')
        self.assertEqual(modeled['COST_AMT_NONPREF']['unit'], 'fraction')
        corrupted = copy.deepcopy(modeled)
        corrupted['COST_AMT_NONPREF']['unit'] = 'USD_per_source_supply'
        with self.assertRaisesRegex(ValueError, 'Dollars confused'):
            check_model(raw, corrupted, 'beneficiary', 'EA')

    def test_changed_numeric_amount_is_detected(self):
        raw = self.beneficiary()
        raw.update(COST_TYPE_NONPREF='1', COST_AMT_NONPREF='20.00')
        modeled = model_row('beneficiary', raw, 'EA')
        modeled['COST_AMT_NONPREF']['value'] = '21.00'
        with self.assertRaisesRegex(ValueError, 'Modeled amount changed'):
            check_model(raw, modeled, 'beneficiary', 'EA')

    def test_defined_standard_missing_tier_and_blank_prices_remain_distinct(self):
        raw = {k: ' ' for k in INSULIN}
        raw.update(CONTRACT_ID='H9999', PLAN_ID='001', SEGMENT_ID='000', TIER='.', DAYS_SUPPLY='1',
                   copay_amt_nonpref_insln='35.00', coin_amt_nonpref_insln='0.25')
        modeled = model_row('insulin', raw, 'DS')
        self.assertIsNone(modeled['TIER']['value'])
        self.assertEqual(modeled['TIER']['meaning'], 'tier_not_specified_for_defined_standard')
        self.assertEqual(modeled['copay_amt_pref_insln']['source_state'], 'source_blank')
        self.assertIsNone(modeled['copay_amt_pref_insln']['value'])
        check_model(raw, modeled, 'insulin', 'DS')

    def test_missing_source_field_is_detected(self):
        raw = self.beneficiary()
        modeled = model_row('beneficiary', raw, 'EA')
        del modeled['DED_APPLIES_YN']
        with self.assertRaisesRegex(ValueError, 'Dropped or invented'):
            check_model(raw, modeled, 'beneficiary', 'EA')

    def test_supply_codes_are_explicit(self):
        for code, days in [('1', 30), ('2', 90), ('3', None), ('4', 60)]:
            with self.subTest(code=code):
                raw = self.beneficiary(); raw['DAYS_SUPPLY'] = code
                modeled = model_row('beneficiary', raw, 'EA')
                self.assertEqual(modeled['DAYS_SUPPLY']['value'], days)
                check_model(raw, modeled, 'beneficiary', 'EA')

    def test_unknown_cost_code_fails_instead_of_becoming_zero(self):
        raw = self.beneficiary(); raw['COST_TYPE_NONPREF'] = '9'
        with self.assertRaises(KeyError):
            model_row('beneficiary', raw, 'EA')


if __name__ == '__main__':
    unittest.main()
