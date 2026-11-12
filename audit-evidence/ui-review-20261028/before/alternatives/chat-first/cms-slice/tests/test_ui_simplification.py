"""Synthetic grouped-location provenance and model-rule regressions. No paid calls."""
import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from guest_profiles import validate_guide,ProfileError
from guide_agent import GuideAgent
WEB=ROOT/'apps/chat';CONTRACT=json.loads((WEB/'guide-contract.json').read_text());FACTS=json.loads((WEB/'teaching-facts.json').read_text());REFERENCE=json.loads((WEB/'zip-counties.json').read_text())
def e(value,status='reported',source='user_choice'):
 return {'value':value,'status':status,'source':source,'confirmation':'confirmed_by_user','revision':1,'confirmedAt':'2026-10-21T00:00:00Z'}
def fixture():
 row=REFERENCE['zips']['34102'][0]
 return {'schemaVersion':2,'stateVersion':1,'fields':{'intent.goal':e('compare'),'privacy.persistenceChoice':e('save'),'comparison.scope.zip':e('34102'),'comparison.scope.county':e(dict(zip(['fips','name','state'],row)),'derived','location_reference'),'comparison.scope.locationEvidence':e({'source':REFERENCE['source_url'],'period':REFERENCE['period'],'method':'unique_zip_reference'},'derived','location_reference')},'flow':{'node':'O03','history':[],'queue':[],'lessonReturn':None,'personalReview':False,'guideOpen':True,'origin':'A01','invalidations':[],'scroll':0},'topics':{},'preferences':{'saveGuide':True,'saveSensitive':False,'noticeVersion':'guest-notice-2026-10-21-v1'}}
class SimplificationTests(unittest.TestCase):
 def test_exact_published_unique_county_can_save_as_derived(self):self.assertEqual(validate_guide(fixture(),CONTRACT)['fields']['comparison.scope.county']['status'],'derived')
 def test_forged_county_or_source_rejected(self):
  for key,value in [('comparison.scope.county',{'fips':'00000','name':'Wrong','state':'FL'}),('comparison.scope.locationEvidence',{'source':'wrong','period':'2025','method':'unique_zip_reference'})]:
   g=fixture();g['fields'][key]['value']=value
   with self.assertRaises(ProfileError):validate_guide(g,CONTRACT)
 def test_ambiguous_county_requires_explicit_report(self):
  g=fixture();g['fields']['comparison.scope.zip']['value']=next(k for k,v in REFERENCE['zips'].items() if len(v)>1)
  with self.assertRaises(ProfileError):validate_guide(g,CONTRACT)
 def test_derived_cannot_be_used_for_coverage_or_model_proposals(self):
  g=fixture();g['fields']['coverage.enrollment']=e('ab','derived','location_reference')
  with self.assertRaises(ProfileError):validate_guide(g,CONTRACT)
 def test_grouped_nodes_do_not_pollute_secondary_model_option_rules(self):
  rules=GuideAgent(CONTRACT,FACTS).field_rules();self.assertIn('keep',rules['intent.change']);self.assertNotIn('original',rules['intent.change']);self.assertIn('browse',rules['intent.comparisonMode']);self.assertNotIn('drugs',rules['intent.comparisonMode']);self.assertIn('prepare',rules['intent.jobTask']);self.assertNotIn('active',rules['intent.jobTask'])
if __name__=='__main__':unittest.main()
