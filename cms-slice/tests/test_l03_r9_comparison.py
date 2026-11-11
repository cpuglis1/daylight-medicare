import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from test_l03_inventory_contract import observation
from l03_r9_comparison import compare

class ScopeBeforeAgreement(unittest.TestCase):
    def test_matching_source_network_placeholders_cannot_agree(self):
        a,b=observation(),observation('carrier');a['context']['network']=b['context']['network']='source_default_network'
        self.assertEqual(compare(a,b)['outcome'],'insufficient_evidence')
    def test_generic_source_basis_cannot_agree(self):
        a,b=observation(),observation('carrier');a['context']['population']=b['context']['population']='CMS_submission_basis'
        self.assertEqual(compare(a,b)['outcome'],'insufficient_evidence')
    def test_unidentified_optional_rider_cannot_agree(self):
        a,b=observation(),observation('carrier');a['variant']['identifier']=b['variant']['identifier']='named_optional_rider_section'
        self.assertEqual(compare(a,b)['outcome'],'insufficient_evidence')
    def test_complete_meaning_still_uses_existing_adversarial_contract(self):
        a,b=observation(),observation('carrier');self.assertEqual(compare(a,b)['outcome'],'exact_agreement')
        b['unit']['denominator']='stay';r=compare(a,b);self.assertEqual(r['outcome'],'conflict');self.assertFalse(r['accepted_for_reference'])

if __name__=='__main__':unittest.main()
