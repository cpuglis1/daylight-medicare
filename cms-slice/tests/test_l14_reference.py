"""Adversarial source-integrity and consequential-claim boundaries for L14."""
import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from l14_validate import BUILD,load,guard_reference,guard_path,guard_state,compare_cells
class L14Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref=load(BUILD/'reference.json');cls.paths=load(BUILD/'paths.json');cls.states=load(BUILD/'state-observations.json')
    def test_reference_stays_research_only(self):guard_reference(self.ref)
    def test_future_year_cannot_be_2026_evidence(self):
        r=copy.deepcopy(self.ref);r['benefit_year']=2027
        with self.assertRaises(ValueError):guard_reference(r)
    def test_wrong_county_rejected(self):
        r=copy.deepcopy(self.ref);r['county_fips']='12071'
        with self.assertRaises(ValueError):guard_reference(r)
    def test_technical_validation_not_acceptance(self):
        for key,value in [('human_acceptance','approved'),('qualified_R19_review','approved'),('full_l14_complete',True),('consumer_release_enabled',True)]:
            r=copy.deepcopy(self.ref);r[key]=value
            with self.assertRaises(ValueError):guard_reference(r)
    def test_age_or_county_cannot_grant_eligibility(self):
        r=copy.deepcopy(next(r for r in self.paths if r['id']=='H5934'));r['personal_eligibility']=True
        with self.assertRaises(ValueError):guard_path(r)
    def test_slots_minus_enrollees_is_not_openings(self):
        r=copy.deepcopy(self.states[-1]);r['reported_open_slots']=r['slots_funded']-r['enrollment_first_of_month']
        with self.assertRaises(ValueError):guard_state(r)
    def test_state_capitation_is_not_personal_premium(self):
        r=copy.deepcopy(self.states[-1]);r['personal_premium']=r['actuarial_dual_rate_dollars']
        with self.assertRaises(ValueError):guard_state(r)
    def test_national_hcpp_note_does_not_grant_local_access(self):
        r=copy.deepcopy(next(r for r in self.paths if r['organization_type']=='HCPP - 1833 Cost'));r['status']='available_to_any_Collier_resident'
        with self.assertRaises(ValueError):guard_path(r)
    def test_employer_msa_restriction_cannot_disappear(self):
        r=copy.deepcopy(next(r for r in self.paths if r['id']=='H6130'));r['employer_group_only']=False
        with self.assertRaises(ValueError):guard_path(r)
    def test_contract_not_unverified_plan_segment(self):
        r=copy.deepcopy(next(r for r in self.paths if r['id']=='H6130'));r['individual_plan_segment']='H6130-807-000'
        with self.assertRaises(ValueError):guard_path(r)
    def test_blank_and_suppression_are_not_zero(self):
        for original in ['', '*']:
            with self.assertRaises(ValueError):compare_cells({'Enrollment':'0'},{'Enrollment':original})
    def test_raw_leading_zeros_preserved(self):
        with self.assertRaises(ValueError):compare_cells({'Plan ID':'1'},{'Plan ID':'001'})
    def test_no_silent_source_column_omission(self):
        with self.assertRaises(ValueError):compare_cells({'Contract ID':'H5934'},{'Contract ID':'H5934','Notes':''})
    def test_pace_current_people_and_unique_people_are_distinct(self):
        aug=next(r for r in self.states if r['report_month']=='2026-08')
        self.assertEqual((aug['enrollment_first_of_month'],aug['county_current_month_enrollees'],aug['fiscal_year_unique_individuals']),(94,94,95))
    def test_no_individual_cost_or_msa_does_not_erase_group(self):
        n=load(BUILD/'negative-search.json');self.assertEqual(n['individual_Cost_source_rows'],[]);self.assertEqual(n['individual_MSA_source_rows'],[]);self.assertEqual(len(n['collier_MSA_source_rows']),1)
    def test_pace_global_notes_remain_anomalies(self):
        a=load(BUILD/'source-anomalies.json');self.assertEqual(len(a['pace_area_only']),35);self.assertEqual(len(a['pace_national_note_records']),243)
    def test_conflicting_msa_ids_never_deduplicated_as_one_plan(self):
        docs=load(BUILD/'restricted-documents.json');self.assertEqual(len(docs),5)
        self.assertGreater(sum('807' in d['plan_ids'] for d in docs),1)
        self.assertTrue(all(d['unified_plan_join'].startswith('held_') for d in docs))
    def test_actual_gap_types_not_silent_defaults(self):
        gaps=load(BUILD/'gaps.json');self.assertEqual(len(gaps),7);self.assertTrue(all(r['needed_evidence'] and r['closure'] and r['status']=='open' for r in gaps))
    def test_existing_pbp_group_identities_not_called_missing(self):
        p=load(BUILD/'pbp-reuse-inventory.json');self.assertEqual([len(m['retained_rows']) for m in p['members']],[18,18])
        self.assertEqual({r['plan_id'] for r in p['members'][0]['retained_rows']},{str(i) for i in range(801,819)})
        self.assertTrue(all(r['group_flag']=='1' for m in p['members'] for r in m['retained_rows']))
    def test_repeated_pbp_columns_not_dropped(self):
        p=load(BUILD/'pbp-reuse-inventory.json');m=p['members'][1]
        self.assertEqual(m['headers'].count('segment_id'),2)
        self.assertTrue(all(len(r['values'])==len(m['headers'])==17 for r in m['retained_rows']))
if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(L14Tests))
    if '--receipt' in sys.argv:
        p=BUILD.parent/'validation-r1';p.mkdir(exist_ok=True)
        (p/'tests.json').write_text(json.dumps(dict(passed=result.wasSuccessful(),tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors)),indent=2)+'\n')
    sys.exit(0 if result.wasSuccessful() else 1)
