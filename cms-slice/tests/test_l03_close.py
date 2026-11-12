"""Meaningful boundary regressions: source semantics, controls and release holds."""
import json,pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from l03_close import R3,condition_rule,rider_class
from l03_close_reference import published_lookup

class CloseBoundaries(unittest.TestCase):
    def rule(self,label,role='activation',typ='enum'):
        return condition_rule({'label':label,'source':{'field':'fixture'},'semantic_role':role,'normalized':{'value':'No','type':typ}})[0]
    def test_vendor_is_not_referral(self):self.assertEqual(self.rule('Are there preferred vendors/manufacturers for Durable Medical Equipment (DME)?','referral'),'preferred_vendor_control')
    def test_periodontic_amount_is_not_period(self):self.assertEqual(self.rule('Copayment amount for Periodontics','period_or_frequency','decimal'),'typed_charge_not_frequency')
    def test_no_charge_type_does_not_mean_free(self):self.assertEqual(self.rule('Is there a copayment?'),'charge_type_activation')
    def test_discharge_day_separate_from_covered_day_limit(self):self.assertEqual(self.rule('Do you charge cost sharing on the day of discharge?'),'discharge_day_charge')
    def test_SNF_stay_rule_separate_from_cost_band(self):self.assertEqual(self.rule('Do you allow less than 3 day inpatient hospital stay prior to SNF admission?'),'SNF_prior_hospital_stay')
    def test_waiver_scoped_to_named_charge(self):self.assertEqual(self.rule('Is this Copayment waived for Worldwide Emergency Transportation if admitted to hospital?'),'conditional_waiver')
    def test_privacy_amendment_is_not_missing_rider(self):self.assertEqual(rider_class('Amendment: You have the right to request that we amend your PHI.'),'privacy_right_not_benefit_rider')
    def test_LIS_not_medical_rider(self):self.assertEqual(rider_class('Ask for the LIS Rider for your drug coverage.'),'member_specific_LIS_insert_outside_L03')
    def test_generic_notice_not_applicable_amendment(self):self.assertEqual(rider_class('These notices are sometimes called riders or amendments.'),'generic_future_notice_not_identified_amendment')
    def test_published_reference_stays_held(self):
        with self.assertRaises(PermissionError):published_lookup('2026:H1035:019:000')
    def test_nuclear_maximum_not_flat_MRI_price(self):
        a=json.loads((R3/'amount-issue-decisions.json').read_text());expected={'H1036:217':'250.00','H1036:290':'325.00','H1036:310':'250.00','H1036:311':'250.00','H5216:257':'325.00','R5826:005':'325.00','R5826:018':'325.00','R5826:074':'325.00'}
        xs=[r for r in a if r['r3_state']=='bound_exact_service_setting'];self.assertEqual(len(xs),8)
        for r in xs:
            self.assertEqual(r['CMS_value'],expected[':'.join(r['offering_id'].split(':')[1:3])]);self.assertIn('nuclear medicine',r['decision']);self.assertIn('in-network',r['decision'])
    def test_diabetes_zero_remains_channel_qualified(self):
        a=json.loads((R3/'amount-issue-decisions.json').read_text());xs=[r for r in a if r['r3_state']=='reconciled_channel_and_charge_type'];self.assertEqual(len(xs),4)
        for r in xs:self.assertIn('20%',r['decision']);self.assertIn('mail order',r['decision']);self.assertFalse(r['literal_same_unit_amount_binding'])
    def test_drug_minimum_not_free_drug_claim(self):
        a=json.loads((R3/'amount-issue-decisions.json').read_text());xs=[r for r in a if r['r3_state']=='reconciled_default_vs_conditional_lower_bound'];self.assertTrue(xs)
        for r in xs:self.assertNotEqual(r['category_code'],'15-1');self.assertFalse(r['literal_same_unit_amount_binding']);self.assertFalse(r['consumer_usable'])
    def test_worldwide_not_replaced_with_domestic_price(self):
        a=json.loads((R3/'amount-issue-decisions.json').read_text());xs=[r for r in a if r['r3_state']=='held_geographic_price_basis'];self.assertEqual(len(xs),37)
        for r in xs:self.assertEqual(r['remaining_gap_id'],'HUMANA-WORLDWIDE');self.assertFalse(r['literal_same_unit_amount_binding'])
if __name__=='__main__':unittest.main()
