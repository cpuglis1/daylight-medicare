"""Meaningful failure/ordering witnesses for the fictional-only reference."""
import copy
import unittest
from dataclasses import replace
from decimal import Decimal
from reference_recommender import Case, Plan, METRICS, demo, shortlist


class RecommendationReferenceTests(unittest.TestCase):
    def setUp(self):
        self.case, self.plans = demo()

    def test_priority_order_changes_tradeoff_and_no_inputs_mutated(self):
        before = copy.deepcopy((self.case, self.plans))
        self.assertEqual(shortlist(self.case, self.plans)['top_three'], ['fictional:A','fictional:B','fictional:C'])
        result = shortlist(replace(self.case, priorities=tuple(reversed(METRICS))), self.plans)
        self.assertEqual(result['top_three'], ['fictional:C','fictional:A','fictional:D'])
        self.assertFalse(result['consumer_usable'])
        self.assertEqual((self.case,self.plans), before)

    def test_correction_invalidates_confirmation(self):
        r = shortlist(replace(self.case, profile_revision='v2'), self.plans)
        self.assertEqual(r['top_three'], [])
        self.assertIn('CONFIRM_CURRENT_PROFILE', r['reason_codes'])

    def test_unordered_priorities_do_not_invent_preference(self):
        r = shortlist(replace(self.case, priorities=()), self.plans)
        self.assertEqual(r['top_three'], [])
        self.assertIn('EXPLICIT_PRIORITY_ORDER_REQUIRED', r['reason_codes'])

    def test_unknown_fourth_contender_holds_global_top_three(self):
        fourth = replace(self.plans[-1], metrics=((METRICS[0], None),(METRICS[1], Decimal('3000'))))
        r = shortlist(self.case, self.plans[:-1] + (fourth,))
        self.assertEqual(r['top_three'], [])
        self.assertIn('MATERIAL_UNKNOWN_CONTENDER', r['reason_codes'])
        self.assertEqual(len(r['plans']),4)

    def test_unknown_check_is_not_known_conflict(self):
        p = replace(self.plans[0], checks=tuple((k,'needs_check' if k=='doctor_site' else v) for k,v in self.plans[0].checks))
        r = shortlist(self.case, (p,) + self.plans[1:])
        self.assertEqual(r['plans'][0]['state'],'needs_check')
        self.assertEqual(r['top_three'],[])

    def test_explicit_conflict_visible_and_does_not_pad(self):
        plans = tuple(replace(p, checks=(('eligibility','known_conflict'),)) for p in self.plans[1:])
        r = shortlist(self.case, (self.plans[0],) + plans)
        self.assertEqual(r['top_three'],['fictional:A'])
        self.assertEqual(len(r['plans']),4)
        self.assertEqual([p['state'] for p in r['plans']].count('known_conflict'),3)

    def test_exact_tie_crossing_third_preserves_all_equally_ranked(self):
        plans = tuple(replace(p, metrics=self.plans[0].metrics) for p in reversed(self.plans))
        r = shortlist(self.case,plans)
        self.assertEqual(r['top_three'],['fictional:A','fictional:B','fictional:C'])
        self.assertEqual(r['tie_groups'],[['fictional:A','fictional:B','fictional:C','fictional:D']])

    def test_wrong_year_or_county_rejected(self):
        for p in [replace(self.plans[0],year=2027), replace(self.plans[0],county_fips='12099')]:
            with self.assertRaisesRegex(ValueError,'SCOPE_MISMATCH'):
                shortlist(self.case,(p,) + self.plans[1:])

    def test_real_catalog_and_untyped_authority_rejected(self):
        with self.assertRaisesRegex(ValueError,'REAL_PLAN'):
            shortlist(self.case,(replace(self.plans[0],id='2026:H1036:217:000'),))
        with self.assertRaisesRegex(ValueError,'TYPED_FIXTURE'):
            shortlist({'accepted':True},self.plans)

    def test_commercial_fields_cannot_enter_typed_contract(self):
        for field in ['commission','carrier_appointment','conversion_probability','referral_fee']:
            with self.assertRaises(TypeError):
                Plan('fictional:X',(),(),**{field:100})

    def test_nan_negative_and_float_are_not_accepted_values(self):
        for value in [Decimal('NaN'),Decimal('-1'),0.0]:
            p = replace(self.plans[0],metrics=((METRICS[0],value),))
            with self.assertRaisesRegex(ValueError,'INVALID_FINDING'):
                shortlist(self.case,(p,))

    def test_duplicate_ids_and_missing_required_check_contract_rejected(self):
        with self.assertRaisesRegex(ValueError,'INVALID_FIXTURE_IDENTITY'):
            shortlist(self.case,(self.plans[0],self.plans[0]))
        with self.assertRaisesRegex(ValueError,'INVALID_DECISION_BASIS'):
            shortlist(replace(self.case,checks=()),self.plans)


if __name__ == '__main__':
    unittest.main()
