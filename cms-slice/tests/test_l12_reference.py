"""Consequential boundary and deliberate corruption tests for the L12 reference."""
import copy
from contextlib import closing
import json
from pathlib import Path
import sys
import unittest

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
import l12_validate as v


class L12ReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sqlite3
        with closing(sqlite3.connect('file:'+str(v.BUILD/'l12-reference.sqlite')+'?mode=ro',uri=True)) as db:
            cls.data={name:v.load(v.BUILD/name) for name, in db.execute('SELECT name FROM datasets')}

    def changed(self,filename,edit):
        data=copy.deepcopy(self.data);edit(data[filename])
        with self.assertRaises(ValueError):v.validate_data(data)

    def test_complete_reference(self):self.assertEqual(v.validate_data(self.data)['basis_comparisons'],6)
    def test_dropped_family_row_detected(self):self.changed('florida-msp-lis-tables.json',lambda x:x.pop())
    def test_blank_resource_not_zero(self):self.changed('florida-msp-lis-tables.json',lambda x:x[2]['fields']['MSP_resources'].update(value='0'))
    def test_wrong_year_and_period_detected(self):self.changed('florida-msp-lis-tables.json',lambda x:x[0].update(effective_start='2026-01-01'))
    def test_all_family_cells_checked(self):self.changed('federal-FPL-2026.json',lambda x:x[8]['values'].update({'145':'123'}))
    def test_countable_and_gross_not_swapped(self):self.changed('basis-reconciliations.json',lambda x:x[0].update(general_disregard='40'))
    def test_student_annual_cap_not_monthly(self):self.changed('florida-medicaid-standards.json',lambda x:x[32].update(unit='USD/month'))
    def test_wpwd_disregard_not_asset_cap(self):self.changed('florida-medicaid-standards.json',lambda x:x[8].update(field='asset_limit'))
    def test_may_law_not_financial_introduction_date(self):self.changed('florida-medicaid-standards.json',lambda x:x[8].update(effective_start='2026-05-21'))
    def test_historical_student_figures_do_not_replace_current(self):
        self.assertEqual(self.data['historical-January-medicaid-standards.json'][32]['value'],'9460')
        self.assertEqual(self.data['florida-medicaid-standards.json'][32]['value'],'9730')
        self.changed('January-cross-publication-comparisons.json',lambda x:x[-1].update(source_money_tokens=['+$708']))
    def test_meds_ad_qualifier_cannot_disappear(self):self.changed('rules.json',lambda x:x[23].update(meaning='88% FPL gives all Medicare recipients Medicaid.'))
    def test_full_condition_text_cannot_be_dropped(self):self.changed('rules.json',lambda x:x[0]['source_conditions'].pop())
    def test_qdwi_does_not_deem_lis(self):
        self.assertFalse(v.reference_deemed('QDWI_alone',True,True))
        self.changed('automatic-routes.json',lambda x:x[-1].update(deems_LIS=True))
    def test_ssdi_is_not_ssi(self):
        self.assertFalse(v.reference_deemed('SSDI',True,True));self.assertTrue(v.reference_deemed('SSI',True,True))
    def test_pending_and_unknown_are_not_denials(self):
        self.assertIsNone(v.reference_deemed('QMB',False,True))
        self.assertIsNone(v.reference_deemed('QMB',True,None))
        self.assertIsNone(v.synthetic_lis_boundary(None,'23940','100','16590'))
    def test_deemed_june_july_boundary(self):
        self.assertEqual(v.deemed_through('2026-06-30'),'2026-12-31')
        self.assertEqual(v.deemed_through('2026-07-01'),'2027-12-31')
    def test_burial_bases_and_unknowns(self):
        self.assertEqual(v.resource_basis('16590',1),18090)
        self.assertEqual(v.resource_basis('33100',0),33100)
        self.assertEqual(v.resource_basis('33100',1),34600)
        self.assertEqual(v.resource_basis('33100',2),36100)
        self.assertIsNone(v.resource_basis('33100',None))
        self.changed('LIS-resources-2026.json',lambda x:x[0].update(base_limit='18090'))
    def test_exact_lis_boundaries(self):
        self.assertFalse(v.synthetic_lis_boundary('23940','23940','16590','16590'))
        self.assertTrue(v.synthetic_lis_boundary('23939.99','23940','16590','16590'))
        self.assertFalse(v.synthetic_lis_boundary('23939.99','23940','16590.01','16590'))
    def test_lis_cost_category_mutation(self):self.changed('LIS-cost-sharing-2026.json',lambda x:x[1].update(brand_copayment_maximum='12.65'))
    def test_qmb_florida_election_not_invented(self):self.changed('rules.json',lambda x:x[29].update(meaning='Florida always uses the application month.'))
    def test_release_and_acceptance_not_inherited(self):
        self.changed('summary.json',lambda x:x.update(consumer_release_enabled=True))
        self.changed('summary.json',lambda x:x.update(human_acceptance={'approved':True}))
    def test_coverage_path_omission_detected(self):self.changed('medicaid-coverage-accounting.json',lambda x:x.pop())


if __name__=='__main__':unittest.main()
