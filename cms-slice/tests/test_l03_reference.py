"""Regression checks for actual L03 evidence boundaries and corruption handling."""
import json,pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import l03_reference as reference
from l03_reference_build import normalize,sha

class L03ReferenceTests(unittest.TestCase):
 def test_blank_null_and_zero_do_not_collapse(self):
  d={'codes':{},'source_type':'NUM','field_title':'Copayment amount'}
  self.assertEqual(normalize(None,d)['state'],'source_null')
  self.assertEqual(normalize('',d)['state'],'source_blank')
  self.assertEqual(normalize('0.00',d)['value'],'0.00')
 def test_codebook_no_is_not_an_unknown(self):
  d={'codes':{'1':'Yes','2':'No'},'source_type':'CHAR'}
  self.assertEqual(normalize('2',d)['value'],'No')
  self.assertEqual(normalize('9',d)['state'],'unresolved_code')
 def test_legacy_n_does_not_become_no_without_evidence(self):
  d={'codes':{'1':'Yes','0':'No'},'source_type':'CHAR'}
  self.assertEqual(normalize('N',d)['state'],'unresolved_code')
 def test_official_checkbox_positions_preserve_leading_zero(self):
  d={'codes':{'1 in 2':'Tier 1','1 in 3':'Tier 2','1 in 4':'Tier 3','1 in 5':'Tier 4','1 in 6':'Tier 5','1 in 7':'Tier 6','1 in 1':'Tier 7'},'source_type':'CHAR'}
  self.assertEqual(normalize('0111000',d)['value'],['Tier 1','Tier 2','Tier 3'])
  self.assertEqual(normalize('1000000',d)['value'],['Tier 7'])
 def test_invalid_position_value_remains_unresolved(self):
  d={'codes':{'1 in 1':'One','1 in 3':'Three'},'source_type':'CHAR'}
  self.assertEqual(normalize('10',d)['state'],'unresolved_code')
 def test_2027_is_rejected(self):
  with self.assertRaises(ValueError):reference.research_lookup('2027:H1036:217:000')
 def test_unknown_plan_is_not_silently_substituted(self):
  with self.assertRaises(KeyError):reference.research_lookup('2026:H9999:999:999')
 def test_release_is_held_without_acceptance(self):
  with self.assertRaises(PermissionError):reference.published_lookup('2026:H1036:217:000')
 def test_research_lookup_cannot_claim_personal_applicability(self):
  r=reference.research_lookup('2026:H1036:217:000')
  self.assertFalse(r['accepted']);self.assertFalse(r['personal_applicability']);self.assertFalse(r['calculations']);self.assertFalse(r['recommendations'])
 def test_restricted_carrier_remains_visible(self):
  r=reference.research_lookup('2026:H0710:010:000')
  self.assertEqual(r['documents']['document_matches']['SB']['status'],'restricted')
  self.assertTrue(r['amount_observations'])
 def test_changed_package_is_detected(self):
  with tempfile.TemporaryDirectory() as t:
   r=pathlib.Path(t);(r/'build-r1').mkdir();(r/'example.json').write_text('{"value":0}')
   (r/'build-r1/package-manifest.json').write_text(json.dumps({'files':{'example.json':sha((r/'example.json').read_bytes())}}))
   reference.verify_package(r);(r/'example.json').write_text('{"value":99}')
   with self.assertRaises(ValueError):reference.verify_package(r)
 def test_source_based_day_band_and_setting_cases_remain_distinct(self):
  cases={x['id']:x for x in json.loads((reference.DATA/'review/source-expectations.json').read_text())['cases']}
  self.assertEqual(cases['HUMANA-HOSPITAL-END']['expected'],'5')
  self.assertEqual(cases['BLUE-HOSPITAL-END']['expected'],'7')
  self.assertEqual(cases['BLUE-OON-HOSPITAL-END']['expected'],'27')
  self.assertIn('nursing home',cases['AETNA-SPECIALIST-LOWER']['published_conditions'])
  self.assertEqual(cases['OPTIMUM-MOOP']['expected'],'6800')
  self.assertIn('028',cases['OPTIMUM-NO-GIVEBACK']['published_conditions'])

if __name__=='__main__':unittest.main()
