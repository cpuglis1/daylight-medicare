"""Source-led and negative checks for the additive L03 r2 reference."""
import json,pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from l03_reconcile import OUT,R1,NAMES,role,qualified_unit,parent_cat,readlines
from l03_reconcile_reference import published_lookup

class L03ReconciliationTests(unittest.TestCase):
 def test_source_led_cases_cover_every_documented_offering(self):
  cases=json.loads((OUT/'source-led-comparison-ledger.json').read_text());mx=json.loads((R1/'plan-document-matrix.json').read_text())
  expected={x['offering_id'] for x in mx if x['document_matches']['SB']['status']=='matched_for_research'}
  self.assertEqual({x['offering_id'] for x in cases},expected)
  self.assertEqual(len(cases),438)
  differences={(x['offering_id'],x['field']) for x in cases if not x['equal']}
  self.assertEqual(differences,{('2026:H1036:340:000','INN_hospital_PBP_base_stay_copayment'),('2026:H1609:078:000','INN_hospital_PBP_base_stay_copayment')})
  self.assertTrue(all(x['status']=='basis_difference_held_for_review' for x in cases if not x['equal']))
 def test_adjacent_plan_columns_not_assigned(self):
  xs=json.loads((OUT/'source-led-comparison-ledger.json').read_text());idx={(x['offering_id'],x['field']):x for x in xs}
  self.assertEqual(idx[('2026:H5427:082:000','INN_hospital_band1_amount')]['expected_from_SB'],'195')
  self.assertEqual(idx[('2026:H5594:035:000','INN_annual_medical_MOOP')]['expected_from_SB'],'6800')
  self.assertNotEqual(idx[('2026:H5594:035:000','INN_annual_medical_MOOP')]['expected_from_SB'],'1750')
 def test_day_boundaries_do_not_inherit_currency_from_containing_title(self):
  f={'semantic_role':role('End Day Interval 1','pbp_b1a_copay_mcs_endd_int1_t1'),'normalized':{'type':'decimal','unit':'USD','value':'7'}}
  self.assertEqual(qualified_unit(f),'day_or_hour_count')
 def test_2026_dictionary_names_not_guessed_from_other_year(self):
  self.assertEqual(NAMES['14d'],'Kidney disease education services')
  self.assertEqual(NAMES['14c15'],'Wigs for hair loss related to chemotherapy')
  self.assertEqual(NAMES['14c21'],'In-home support services')
 def test_no_absent_consolidated_premium_becomes_zero(self):
  cases=json.loads((OUT/'source-led-comparison-ledger.json').read_text())
  x=next(x for x in cases if x['offering_id']=='2026:R5826:018:000' and 'premium' in x['field'])
  self.assertTrue(x['equal']);self.assertEqual(x['actual_CMS'],'42.00')
  self.assertTrue(any('absent consolidated' in q for q in x['qualifications']))
 def test_all_25_restricted_offerings_stay_present_and_flagged(self):
  xs=json.loads((OUT/'offering-reconciliation.json').read_text());held=[x for x in xs if x['original_document_status']=='restricted']
  self.assertEqual(len(xs),72);self.assertEqual(len(held),25)
  self.assertEqual(sum(x['parent']=='UnitedHealth Group, Inc.' for x in held),19)
  self.assertEqual(sum(x['parent']=='Centene Corporation' for x in held),6)
 def test_no_record_or_family_passage_is_accepted(self):
  self.assertTrue(all(x['accepted'] is False and x['consumer_usable'] is False for x in readlines(OUT/'benefit-records.jsonl.gz')))
  self.assertTrue(all(x['is_corroboration'] is False for x in readlines(OUT/'carrier-service-passages.jsonl.gz')))
 def test_consumer_lookup_stays_held(self):
  with self.assertRaises(PermissionError):published_lookup('2026:H1036:217:000')
 def test_shared_parent_caps_and_controls_not_dropped(self):
  self.assertEqual(parent_cat('16c10'),'16c');self.assertEqual(parent_cat('11c2'),'11c');self.assertEqual(parent_cat('4c3'),'4c')
if __name__=='__main__':unittest.main()
