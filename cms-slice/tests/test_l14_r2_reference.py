"""Consequential L14 boundary cases and retained finite-population safeguards."""
import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from l14_r2_validate import BUILD,VAL,load,guard_reference,guard_state,guard_msa,guard_profile,guard_claim,guard_audit,guard_summary

class L14R2Tests(unittest.TestCase):
    def reject(self,name,guard,key,value,index=None):
        r=load(BUILD/(name+'.json'))
        if index is not None:r=r[index]
        r=copy.deepcopy(r);r[key]=value
        with self.assertRaises(ValueError):guard(r)
    def test_wrong_year_rejected(self):self.reject('reference',guard_reference,'benefit_year',2027)
    def test_wrong_county_rejected(self):self.reject('reference',guard_reference,'county_fips','12071')
    def test_complete_claim_rejected(self):self.reject('reference',guard_reference,'full_l14_complete',True)
    def test_invented_human_receipt_rejected(self):self.reject('reference',guard_reference,'human_acceptance',{'approved':True})
    def test_specialist_review_not_inferred(self):self.reject('reference',guard_reference,'qualified_R19_review','tests passed')
    def test_source_gap_not_waived(self):self.reject('reference',guard_reference,'data_gap_ids',[])
    def test_consumer_release_rejected(self):self.reject('reference',guard_reference,'consumer_release_enabled',True)
    def test_slot_difference_not_vacancy(self):self.reject('state-observation',guard_state,'reported_open_slots',25)
    def test_capitation_not_personal_price(self):self.reject('state-observation',guard_state,'personal_premium',4141.48)
    def test_historical_capacity_not_live(self):self.reject('state-observation',guard_state,'live_capacity',120)
    def test_latest_reference_not_relabelled_live_october(self):self.reject('state-observation',guard_state,'source_period','2026-10')
    def test_conflicting_deductible_not_released(self):self.reject('Fenyx-comparisons',guard_msa,'unified_plan_deductible',5000,0)
    def test_deposit_agreement_not_design_acceptance(self):self.reject('Fenyx-comparisons',guard_msa,'numeric_agreement_is_design_acceptance',True,1)
    def test_conditional_deposit_not_guaranteed(self):self.reject('Fenyx-comparisons',guard_msa,'deposit_is_guaranteed',True,0)
    def test_segment_zero_not_lost(self):self.reject('Fenyx-comparisons',guard_msa,'CMS_segment_id_source',None,0)
    def test_hotel_cannot_inherit_UHS_PDP_permission(self):
        rows=load(BUILD/'HCPP-profiles.json');r=next(x for x in rows if x['id']=='H6334');r['PDP_interaction']='2025_UHS_brochure_allows_standalone_PDP'
        with self.assertRaises(ValueError):guard_profile(r)
    def test_national_note_not_public_enrollment(self):self.reject('HCPP-profiles',guard_profile,'unrestricted_public_enrollment',True,0)
    def test_no_invented_Collier_provider(self):self.reject('HCPP-profiles',guard_profile,'Collier_provider_confirmed',True,2)
    def test_UHS_2025_edition_preserved(self):
        r=next(x for x in load(BUILD/'claims.json') if x['id']=='UHS-MEMBERSHIP');r['source_edition']='2026'
        with self.assertRaises(ValueError):guard_claim(r)
    def test_claim_extraction_not_external_acceptance(self):self.reject('claims',guard_claim,'acceptance','validated',0)
    def test_partial_pagination_not_complete(self):self.reject('federal-register-searches',guard_audit,'total_pages',2,0)
    def test_proposed_rule_not_final(self):
        r=next(x for x in load(BUILD/'federal-register-searches.json') if x['part']=='423');r['final_ids']+=r['proposed_ids']
        with self.assertRaises(ValueError):guard_audit(r)
    def test_summary_not_local_availability(self):self.reject('CMS-summary-observation',guard_summary,'Collier_availability_proven_by_summary',True)
    def test_summary_not_pilot_absence(self):self.reject('CMS-summary-observation',guard_summary,'zero_pilots_proven',True)
    def test_summary_does_not_explain_35_ids(self):self.reject('CMS-summary-observation',guard_summary,'area_only_ids_resolved',True)
    def test_public_media_and_wrong_year_EOCs(self):
        rows=load(BUILD/'public-PDF-inventories.json');self.assertEqual([x['total'] for x in rows],[99,7]);self.assertTrue(all(x['candidate_2026_EOC_ids']==[] for x in rows))
        f=rows[0]['items'];self.assertTrue(any(x['EOC_name_match'] and '2027' in x['edition_year_tokens'] for x in f))
    def test_all_group_columns_preserved(self):
        p=load(BUILD/'pbp-section-d.json');self.assertEqual(len(p['retained_rows']),18);self.assertEqual(p['original_cells'],8334)
        self.assertTrue(all(len(r['values'])==len(p['headers'])==463 for r in p['retained_rows']))
    def test_every_summary_column_and_conflict_retained(self):
        rows=load(BUILD/'Fenyx-comparisons.json');self.assertEqual(len(rows),22);self.assertTrue(all(not r['deductible_numeric_agreement'] for r in rows));self.assertEqual(sum(r['deposit_numeric_agreement'] for r in rows),19)
    def test_state_measures_not_conflated(self):
        s=load(BUILD/'state-observation.json');self.assertEqual((s['slots_funded'],s['enrollment_first_of_month'],s['fiscal_year_unique_individuals']),(120,95,97))
        self.assertEqual(s['estimated_claims_source_cells'][-1],'$770,650.28')

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(L14R2Tests))
    if '--receipt' in sys.argv:
        if (BUILD/'manifest.json').exists():raise ValueError('Sealed; cannot rewrite test receipt')
        VAL.mkdir(exist_ok=True);(VAL/'tests.json').write_text(json.dumps(dict(passed=result.wasSuccessful(),tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors)),indent=2,sort_keys=True)+'\n')
    sys.exit(0 if result.wasSuccessful() else 1)
