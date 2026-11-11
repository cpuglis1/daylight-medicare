"""Source-derived regressions for the additive 2026 Erickson evidence."""
import json,pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import l03_erickson_documents as d
from l03_erickson_reconcile import value_occurs
from l03_erickson_reference import published_lookup
import l03_scoped_reference as accepted

class EricksonEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matrix=d.load(d.ROOT/'plan-document-matrix.json')
        cls.cases=d.load(d.ROOT/'erickson-source-led-comparisons.json')
        cls.riders=d.load(d.ROOT/'optional-dental-rider-reconciliation.json')
    def case(self,plan,field):
        return next(x for x in self.cases if x['offering_id']==f'2026:H5652:{plan}:000'and x['field']==field)
    def test_72_exact_offerings_with_both_documents(self):
        self.assertEqual(len(self.matrix),72)
        self.assertTrue(all(p['documented']and not p['missing_document_kinds']for p in self.matrix))
    def test_five_Erickson_exact_segments(self):
        self.assertEqual({r['offering_id']for r in self.riders},{f'2026:H5652:{p}:000'for p in ['001','002','004','006','008']})
    def test_signature_separate_OON_MOOP(self):
        c=self.case('001','out_of_network_medical_MOOP')
        self.assertEqual((c['value'],c['network']),('5300','out_of_network'))
        self.assertTrue(c['CMS_source']['pointer'].endswith('/outOfNWMoopAmount'))
        self.assertIn('NOT a combined',' '.join(c['qualifications']))
    def test_no_combined_MOOP_fabricated(self):
        self.assertFalse(any('combined' in x['field']for x in self.cases))
    def test_no_Rx_hospital_and_psychiatric_intervals_differ(self):
        self.assertEqual(self.case('002','INN_hospital_end_day')['value'],'7')
        self.assertEqual(self.case('002','INN_mental_end_day')['value'],'6')
    def test_selective_deductible_keeps_FQHC_and_colonoscopy_exceptions(self):
        x=d.load(d.ROOT/'Liberty-no-Rx-deductible-conditions.json')
        self.assertEqual(set(x['selected_CMS_categories']),{'1a','1b','2','9a1','9a2','9b'})
        self.assertTrue(any('FQHC'in s for s in x['exceptions']))
        self.assertTrue(any('colonoscopy'in s for s in x['exceptions']))
        self.assertEqual(x['out_of_network_deductible'],'none_published')
    def test_MA_only_premium_uses_valid_CMS_field(self):
        c=self.case('002','monthly_published_plan_premium')
        self.assertTrue(c['CMS_value_equal']);self.assertEqual(c['value'],'0')
        self.assertNotEqual(c['CMS_actual'],'NotApplicable')
    def test_champion_DME_zero_copay_not_percentage(self):
        c=self.case('004','INN_dme');self.assertEqual((c['value'],c['unit']),('0','USD'))
    def test_DME_percentage_retained_for_Liberty(self):
        c=self.case('008','INN_dme');self.assertEqual((c['value'],c['unit']),('20','percent'))
    def test_short_substance_use_cost_row_not_discarded(self):
        s=next(s for s in d.rows(d.ROOT/'service-reconciliation.jsonl.gz')if s['offering_id']=='2026:H1045:028:000'and s['category_code']=='9c1')
        self.assertTrue(s['EOC_chart_row_ids']);self.assertTrue(any(e['pdf_page']==82 for e in s['EOC_source_evidence']))
    def test_rider_excluded_from_base_chart(self):
        starts={r['offering_id']:min(e['pdf_page']for e in r['EOC_evidence'])for r in self.riders}
        self.assertTrue(all(max(r['pages'])<starts[r['offering_id']]for r in d.rows(d.ROOT/'carrier-chart-rows.jsonl.gz')if r['offering_id']in starts))
    def test_rider_not_stacked(self):
        self.assertTrue(all(r['replaces_base_dental']and r['cannot_add_base_and_rider_allowances']for r in self.riders))
    def test_rider_specific_procedure_frequencies_held(self):
        self.assertTrue(all(r['full_procedure_rider_complete']is False and 'not acquired or validated'in r['frequency_detail_status']for r in self.riders))
    def test_code_two_not_assumed_No(self):
        f=next(f for f in d.load(d.R1/'field-dictionary.json')['fields']if f['file']=='pbp_b14_preventive'and f['name']=='pbp_b14c_bendesc_ihss')
        self.assertEqual(f['codes']['2'],'Mandatory')
    def test_amount_at_sentence_boundary(self):
        self.assertTrue(value_occurs(44,'USD/month','monthly premium of $44.00.'))
        self.assertFalse(value_occurs(44,'USD/month','$44.001'))
    def test_currency_percentage_and_cents_not_conflated(self):
        self.assertFalse(value_occurs(20,'USD','$0.20'))
        self.assertFalse(value_occurs(20,'USD','20%'))
        self.assertFalse(value_occurs(20,'percent','$20'))
        self.assertTrue(value_occurs('.20','USD','$0.20'))
    def test_no_new_acceptance_inherited(self):
        self.assertTrue(all(c['accepted_for_reference']is False for c in self.cases))
        self.assertEqual(len(accepted.lookup({'year':2026})['entries']),535)
        with self.assertRaises(PermissionError):published_lookup('2026:H5652:001:000')

if __name__=='__main__':unittest.main()
