"""Consequential boundary fixtures and adversarial L13 reference checks."""
from copy import deepcopy
from datetime import date
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from l13_cases import run_cases
from l13_validate import dataset,check_data,sqlite_checks,check_clock_models
from l13_synthetic import part_d_gap,part_b_increment,part_a_increment

class L13ReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.data=dataset()
    def test_source_scoped_reference(self):check_data(self.data)
    def test_independent_calendar_penalty_fixtures(self):
        cases=run_cases();self.assertEqual(len(cases),53)
        self.assertFalse([r for r in cases if not r['passed']])
    def test_sqlite_all_field_parity(self):sqlite_checks(self.data)
    def reject(self,change):
        d=deepcopy(self.data);change(d)
        with self.assertRaises(ValueError):check_data(d)
    def test_missing_whole_sep_detected(self):self.reject(lambda d:d['regulatory-SEP-inventory.json'].pop())
    def test_nested_condition_loss_detected(self):
        self.reject(lambda d:d['regulatory-SEP-inventory.json'][2].update(source_native_conditions='(3) approval'))
    def test_parent_condition_loss_detected(self):
        self.reject(lambda d:d['AB-exceptional-SEP-inventory.json'][0].update(parent_conditions=''))
    def test_changed_quantity_detected(self):self.reject(lambda d:d['quantities.json'][17].update(value='37.00'))
    def test_changed_clock_detected(self):
        self.reject(lambda d:d['clocks.json'][10]['modeled_fields'].update(end='end_before_AB_entitlement'))
    def test_invented_acceptance_detected(self):self.reject(lambda d:d['rules.json'][0].update(acceptance='approved'))
    def test_truncated_source_quote_detected(self):
        self.reject(lambda d:d['rules.json'][0]['source_conditions'][0].update(text='short summary'))
    def test_rare_deadline_hold_cannot_be_removed(self):
        self.reject(lambda d:d['summary.json'].update(known_published_exact_date_hold=[]))
    def test_expired_esrd_sep_cannot_be_revived(self):
        self.reject(lambda d:next(r for r in d['regulatory-SEP-inventory.json'] if r['id']=='MA:b:9').update(temporal_status='active'))
    def test_unmodeled_2027_catalog_cannot_be_claimed(self):
        self.reject(lambda d:d['annual-windows.json'][1].update(plan_inventory_in_this_reference=True))
    def test_fall_election_year_cannot_be_shifted(self):
        self.reject(lambda d:d['annual-windows.json'][0].update(election_start='2026-10-15'))
    def test_database_disagreement_detected(self):
        d=deepcopy(self.data);d['rules.json'][0]['meaning']='different'
        with self.assertRaises(ValueError):sqlite_checks(d)
    def test_unknown_is_not_zero(self):
        self.assertIsNone(part_d_gap(date(2026,1,1),date(2026,5,1)))
        self.assertIsNone(part_b_increment(None));self.assertIsNone(part_a_increment(None))
    def test_boolean_months_and_nonboolean_evidence_rejected(self):
        with self.assertRaises(ValueError):part_b_increment(True)
        with self.assertRaises(ValueError):part_d_gap(date(2026,1,1),date(2026,5,1),after_iep=True,d_eligible=True,no_creditable='yes',no_d=True,reset_applies=False)
    def test_known_creditable_gap_excluded(self):
        result=part_d_gap(date(2026,1,1),date(2026,5,1),after_iep=True,d_eligible=True,no_creditable=False,no_d=True,reset_applies=False)
        self.assertFalse(result['trigger']);self.assertEqual(result['monthly_2026_usd'],'0.00')
    def test_separate_short_gaps_do_not_add_to_63(self):
        flags=dict(after_iep=True,d_eligible=True,no_creditable=True,no_d=True,reset_applies=False)
        one=part_d_gap(date(2026,1,1),date(2026,1,31),**flags)
        two=part_d_gap(date(2026,3,1),date(2026,4,1),**flags)
        self.assertFalse(one['trigger']);self.assertFalse(two['trigger'])
        self.assertEqual(one['consecutive_days']+two['consecutive_days'],63)
    def test_gap_before_start_rejected(self):
        with self.assertRaises(ValueError):part_d_gap(date(2026,4,1),date(2026,3,1),after_iep=True,d_eligible=True,no_creditable=True,no_d=True,reset_applies=False)
if __name__=='__main__':unittest.main()
