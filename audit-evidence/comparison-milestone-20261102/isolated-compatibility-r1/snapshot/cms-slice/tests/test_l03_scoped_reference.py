"""Actual release boundaries, with synthetic receipts kept in temporary files."""
import copy,datetime,json,pathlib,shutil,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import l03_scoped_reference as ref

class ScopedReference(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.registry=pathlib.Path(self.temp.name)/'synthetic-test-review.json'
    def tearDown(self):self.temp.cleanup()
    def synthetic(self):
        p=ref.read(ref.ROOT/'review-packet.json')
        r={'schema':'l03-bounded-review/1','package_id':p['package_id'],'manifest_sha256':ref.sha((ref.ROOT/'manifest.json').read_bytes()),'decision':'accepted','revoked':False,'reviewer_name':'Synthetic test fixture','reviewer_role':'Synthetic test only','reviewed_at_utc':'2026-10-25T00:00:00+00:00','receipt':'Synthetic test fixture, not a human acceptance receipt','accepted_entry_ids':p['accepted_entry_ids_proposed'],'accepted_dispositions':p['accepted_dispositions_proposed'],'acknowledgements':p['required_acknowledgements']}
        self.registry.write_text(json.dumps(r));return r
    def test_pending_review_rejects_published_lookup(self):
        with self.assertRaises(ref.ReferenceHeld):ref.lookup({'year':2026},registry=self.registry)
    def test_research_does_not_unlock_reference(self):
        r=ref.lookup({'year':2026,'offering_id':'2026:H1035:019:000'},research=True);self.assertFalse(r['accepted_for_reference']);self.assertFalse(r['comprehensive'])
    def test_exact_synthetic_receipt_permits_only_reference(self):
        self.synthetic();r=ref.lookup({'year':2026},registry=self.registry);self.assertTrue(r['accepted_for_reference']);self.assertEqual(len(r['entries']),535);self.assertFalse(r['personal_total']);self.assertFalse(r['recommendations']);self.assertFalse(r['app_deployed'])
    def test_question_or_empty_receipt_not_acceptance(self):
        r=self.synthetic();r['receipt']='';self.registry.write_text(json.dumps(r))
        with self.assertRaises(ref.ReferenceHeld):ref.require_review(registry=self.registry)
    def test_changed_manifest_pin_rejects_acceptance(self):
        r=self.synthetic();r['manifest_sha256']='0'*64;self.registry.write_text(json.dumps(r))
        with self.assertRaises(ref.ReferenceHeld):ref.require_review(registry=self.registry)
    def test_incomplete_entry_acceptance_rejected(self):
        r=self.synthetic();r['accepted_entry_ids'].pop();self.registry.write_text(json.dumps(r))
        with self.assertRaises(ref.ReferenceHeld):ref.require_review(registry=self.registry)
    def test_changed_disposition_rejected(self):
        r=self.synthetic();r['accepted_dispositions']['HUMANA-WORLDWIDE']='0'*64;self.registry.write_text(json.dumps(r))
        with self.assertRaises(ref.ReferenceHeld):ref.require_review(registry=self.registry)
    def test_scope_acknowledgement_is_not_inherited(self):
        r=self.synthetic();r['acknowledgements']['qualified_for_this_published_reference_review']=False;self.registry.write_text(json.dumps(r))
        with self.assertRaises(ref.ReferenceHeld):ref.require_review(registry=self.registry)
    def test_revoked_review_rejected(self):
        r=self.synthetic();r['revoked']=True;self.registry.write_text(json.dumps(r))
        with self.assertRaises(ref.ReferenceHeld):ref.require_review(registry=self.registry)
    def test_personal_and_commercial_inputs_rejected(self):
        for k,v in [('income',40000),('commission',1000),('drugs',['test']),('provider','test')]:
            with self.assertRaises(ref.ReferenceError):ref.lookup({'year':2026,k:v},research=True)
    def test_wrong_year_rejected(self):
        with self.assertRaises(ref.ReferenceError):ref.lookup({'year':2027},research=True)
    def test_all_25_restricted_offerings_remain_visible_with_no_entries(self):
        r=ref.lookup({'year':2026,'offering_id':'2026:H1032:198:000'},research=True);self.assertEqual(r['entries'],[]);self.assertEqual(r['offering']['carrier_document_state'],'restricted');self.assertFalse(r['offering']['all_benefits_complete'])
    def test_held_raw_value_not_exposed_as_approved_reference(self):
        self.synthetic();r=ref.lookup({'year':2026},registry=self.registry);self.assertEqual(len(r['holds']),153)
        for h in r['holds']:self.assertIsNone(h['value']);self.assertNotIn('CMS_value',h);self.assertEqual(h['state'],'unknown_held')
    def test_held_issue_id_not_allowlisted(self):
        h=ref.read(ref.ROOT/'held-claims.json')[0]['issue_id'].replace('R3','R4')
        with self.assertRaises(ref.ReferenceError):ref.lookup({'year':2026,'entry_ids':[h]},research=True)
    def test_note_does_not_become_numeric_drug_minimum(self):
        self.synthetic();r=ref.lookup({'year':2026},registry=self.registry);notes=[x for x in r['entries']if x['kind']=='reconciliation_note'];self.assertEqual(len(notes),84)
        for n in notes:self.assertIsNone(n['value']);self.assertTrue(n['qualifications']);self.assertTrue(all(set(x)=={'source'}for x in n['CMS_source_fields']))
    def test_tampered_data_rejected(self):
        root=pathlib.Path(self.temp.name)/'candidate';shutil.copytree(ref.ROOT,root);(root/'entries.json').write_text('[]')
        with self.assertRaises(ref.ReferenceHeld):ref.verify(root)
    def test_wrong_offering_cannot_select_another_offerings_entry(self):
        rows=ref.read(ref.ROOT/'entries.json');e=next(x for x in rows if x['offering_id']!='2026:H1035:019:000')
        with self.assertRaises(ref.ReferenceError):ref.lookup({'year':2026,'offering_id':'2026:H1035:019:000','entry_ids':[e['id']]},research=True)
    def test_single_day_band_amount_keeps_endpoints_and_qualifications(self):
        es=ref.read(ref.ROOT/'entries.json');e=next(x for x in es if x['field']=='INN_hospital_band1_amount');r=ref.lookup({'year':2026,'entry_ids':[e['id']]},research=True)
        context={x['field']:x for x in r['related_reference_entries']};self.assertIn('INN_hospital_band1_begin_day',context);self.assertIn('INN_hospital_band1_end_day',context);self.assertTrue(r['entries'][0]['qualifications']);self.assertEqual(r['entries'][0]['unit'],'USD/day')
    def test_percentage_lower_bound_keeps_range_role(self):
        xs=[x for x in ref.read(ref.ROOT/'entries.json')if x['basis']=='bound_carrier_percentage_range'];self.assertEqual(len(xs),2)
        for x in xs:self.assertEqual(x['value_role'],'minimum_of_published_0_to_20_percent_range');self.assertFalse(x['universal_zero_charge_claim_permitted'])
if __name__=='__main__':unittest.main()
