import json,pathlib,sqlite3,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from l03_semantic_package import refine_scalar_amount_roles

class ScalarAmountRole(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.db.executescript('create table semantic_unit(id text,offering_id text,kind text,subject text,predicate text,context text,state text,payload text);create table canonical_unit(unit_id text,canonical_id text);create table observation(payload text);')
        for uid,leaf in [('A','costShareDeductibleAmount'),('B','hasInNetworkDed'),('C','numberOfVisitsAmount')]:
            self.db.execute('insert into semantic_unit values (?,?,?,?,?,?,?,?)',(uid,'P','condition','Source question',leaf,'{}','evidence_reconciliation_pending',json.dumps({'source_basis':'CMS_JSON','source_component':'/source/'+leaf})))
            self.db.execute('insert into canonical_unit values (?,?)',(uid,'OLD-'+uid))
        self.db.execute('insert into observation values (?)',(json.dumps({'raw_amount':'0.00','activation_control':'2','meaning':'unknown until control review'}),))
    def test_monetary_field_is_claim_and_controls_are_separate(self):
        changes=refine_scalar_amount_roles(self.db)
        self.assertEqual([r['unit_id']for r in changes],['A'])
        self.assertEqual(dict(self.db.execute('select id,kind from semantic_unit')),{'A':'claim','B':'condition','C':'condition'})
    def test_neither_zero_nor_control_is_reinterpreted(self):
        before=self.db.execute('select payload from observation').fetchone()[0];refine_scalar_amount_roles(self.db)
        self.assertEqual(self.db.execute('select payload from observation').fetchone()[0],before)
        self.assertEqual({r[0]for r in self.db.execute('select state from semantic_unit')},{'evidence_reconciliation_pending'})
    def test_role_refinement_is_idempotent(self):
        refine_scalar_amount_roles(self.db);self.assertEqual(refine_scalar_amount_roles(self.db),[])

if __name__=='__main__':unittest.main()
