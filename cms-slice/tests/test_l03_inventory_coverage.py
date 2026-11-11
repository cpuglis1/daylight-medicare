import copy,pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from l03_inventory_coverage import inventory_digest,progress
from l03_semantic_package import export_inventory,export_audit_sample,export_geometry

class FrozenCoverage(unittest.TestCase):
    def test_sealed_package_cannot_be_overwritten_by_any_export(self):
        with tempfile.TemporaryDirectory() as folder:
            root=pathlib.Path(folder);seal=root/'freeze.json';seal.write_text('protected')
            for action in [lambda:export_inventory('missing.sqlite3',root),lambda:export_audit_sample('missing.sqlite3','missing-parent.sqlite3',root),lambda:export_geometry('missing-parent.sqlite3',root,'missing-cache')]:
                with self.assertRaisesRegex(ValueError,'immutable'):action()
            self.assertEqual(seal.read_text(),'protected')
    def setUp(self):
        self.rows=[{'id':'C','offering_id':'2026:H5652:002:000','kind':'claim','subject':'Liberty deductible','predicate':'complete deductible schedule','context':{'network':'in_network'},'source_ids':['SB10','EOC39']},
                   {'id':'Q','offering_id':'2026:H5652:002:000','kind':'condition','subject':'FQHC','predicate':'deductible exception','context':{'network':'in_network'},'source_ids':['EOC39']}]
        self.digest=inventory_digest(self.rows)
    def status(self,key='C',**kwargs):
        row=next(r for r in self.rows if r['id']==key)
        return {'inventory_id':key,'offering_id':row['offering_id'],'kind':row['kind'],'state':'pending','accepted_for_reference':False,**kwargs}
    def run_progress(self,rows=None,dispositions=()):return progress(rows or self.rows,list(dispositions),expected_digest=self.digest)
    def test_condition_cannot_disappear_when_claim_has_a_result(self):
        r=self.run_progress(dispositions=[self.status()]);self.assertEqual(r['states']['condition'],{'pending':1});self.assertFalse(r['all_evidence_work_complete'])
    def test_denominator_removal_or_evidence_deletion_rejected(self):
        for rows in [self.rows[:1],copy.deepcopy(self.rows)]:
            if len(rows)==2:rows[1]['source_ids']=[]
            with self.assertRaises(ValueError):self.run_progress(rows)
    def test_amount_hit_does_not_make_evidence_ready(self):
        with self.assertRaises(ValueError):self.run_progress(dispositions=[self.status(state='awaiting_review',amount_found=True)])
    def test_inherited_acceptance_and_out_of_scope_id_rejected(self):
        for d in [self.status(accepted_for_reference=True),self.status(inventory_id='r4-old-entry')]:
            with self.assertRaises(ValueError):self.run_progress(dispositions=[d])
    def test_wrong_offering_and_duplicate_disposition_rejected(self):
        for ds in [[self.status(offering_id='2026:H5652:001:000')],[self.status(),self.status()]]:
            with self.assertRaises(ValueError):self.run_progress(dispositions=ds)
    def test_review_is_separate_from_evidence_complete(self):
        d=self.status(state='fully_supported',evidence_complete=True,structured_outcome='exact_agreement',comparison_record_id='SYNTHETIC',source_interpretation_record_id='SYNTHETIC')
        with self.assertRaises(ValueError):self.run_progress(dispositions=[d])

if __name__=='__main__':unittest.main()
