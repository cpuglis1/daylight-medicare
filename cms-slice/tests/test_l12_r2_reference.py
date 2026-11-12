"""Source omission, historical-date, household and unresolved-election tests."""
from copy import deepcopy
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import l12_r2_validate as v

class L12R2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent=v.parent_data()
        with closing(sqlite3.connect('file:'+str(v.BUILD/'l12-reference.sqlite')+'?mode=ro',uri=True)) as db:
            cls.data={name:v.load(v.BUILD/name) for name, in db.execute('SELECT name FROM datasets')}
    def corrupt(self,name,edit):
        d=deepcopy(self.data);edit(d[name])
        with self.assertRaises(ValueError):v.validate_data(d,self.parent)
    def test_all_reference_checks(self):self.assertEqual(v.validate_data(self.data,self.parent)['A91_numeric_cells'],96)
    def test_parent_source_omission(self):self.corrupt('source-clause-ledger.json',lambda x:x.pop(0))
    def test_parent_numeric_field_change(self):self.corrupt('florida-msp-lis-tables.json',lambda x:x[0]['fields']['QMB'].update(value='1350'))
    def test_unlisted_rule_change(self):self.corrupt('rules.json',lambda x:x[0].update(meaning='changed'))
    def test_changed_rule_full_conditions(self):self.corrupt('rules.json',lambda x:x[18]['source_conditions'].pop())
    def test_all_additional_person_cells(self):self.corrupt('dated-A91-comparisons-r2.json',lambda x:x[-1]['source_money_tokens'].__setitem__(-1,'+$708'))
    def test_dated_family_row_omission(self):self.corrupt('dated-A91-comparisons-r2.json',lambda x:x.pop())
    def test_prior_spousal_value_not_july_value(self):self.corrupt('historical-April-medicaid-standards.json',lambda x:x[37].update(value='2705'))
    def test_july_boundary_is_explicit(self):self.corrupt('spousal-transitions-r2.json',lambda x:x[0].update(effective_end_exclusive='2026-04-01'))
    def test_student_correction_is_current_not_old_number(self):self.corrupt('historical-April-medicaid-standards.json',lambda x:x[32].update(value='9460'))
    def test_sibling_example_resource_cap_stays_individual(self):self.corrupt('MSP-family-examples-r2.json',lambda x:x[0].update(resource_limit_basis='couple'))
    def test_dependent_money_not_counted(self):self.corrupt('MSP-family-examples-r2.json',lambda x:x[2].update(dependent_income_and_resources_counted=True))
    def test_half_support_boundary(self):
        self.assertTrue(v.synthetic_supported_relative(True,True,'.5'))
        self.assertFalse(v.synthetic_supported_relative(True,True,'.4999'))
        self.assertFalse(v.synthetic_supported_relative(True,False,'.75'))
        self.assertIsNone(v.synthetic_supported_relative(True,True,None))
    def test_qmb_two_options_no_florida_selection(self):
        r=v.qmb_month_options('2026-01-01','2026-02-15')
        self.assertEqual(r['requirements_month_option'],'2026-02-01');self.assertEqual(r['decision_month_option'],'2026-03-01')
        self.assertIsNone(r['Florida_selected_option'])
    def test_qmb_year_end_and_unknown(self):
        self.assertEqual(v.qmb_month_options('2026-12-15','2026-12-20')['decision_month_option'],'2027-01-01')
        self.assertIsNone(v.qmb_month_options(None,'2026-12-20'))
        with self.assertRaises(ValueError):v.qmb_month_options('2026-12-21','2026-12-20')
    def test_generic_rule_cannot_close_state_election(self):self.corrupt('summary.json',lambda x:x.update(Florida_QMB_state_month_election_confirmed=True))
    def test_qualified_question_cannot_disappear(self):self.corrupt('review-questions-r2.json',lambda x:x.pop(0))
    def test_no_invented_acceptance(self):self.corrupt('summary.json',lambda x:x.update(human_acceptance={'approved':True}))
    def test_no_release(self):self.corrupt('summary.json',lambda x:x.update(consumer_release_enabled=True))

if __name__=='__main__':unittest.main()
