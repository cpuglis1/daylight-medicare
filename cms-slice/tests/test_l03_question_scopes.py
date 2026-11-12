import json,pathlib,sqlite3,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from l03_semantic_package import reconcile_question_scopes

class ExactQuestionScope(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.db.executescript('create table semantic_unit(id text,offering_id text,kind text,subject text,predicate text,context text,payload text);create table canonical_unit(unit_id text,canonical_id text);create table observation(unit_id text,layer text,payload text);')
        self.ctx={'service_ids':['S'],'network':'in_network','variant':'base','population_basis':'CMS_submission_basis'}
        self.add('N',self.ctx,True);self.add('T',self.ctx,False)
    def add(self,uid,ctx,native):
        data={'source_basis':'CMS_JSON'}if native else{'family':'authorization'}
        predicate='Authorization required for this benefit?'if native else'Is authorization required?'
        self.db.execute('insert into semantic_unit values (?,?,?,?,?,?,?)',(uid,'P','condition','Exact service',predicate,json.dumps(ctx),json.dumps(data)))
        self.db.execute('insert into canonical_unit values (?,?)',(uid,'C'+uid))
        if not native:self.db.execute('insert into observation values (?,?,?)',(uid,'cms_table',json.dumps({'normalized':{'type':'enum','value':'No'}})))
    def test_exact_known_question_one_inventory_scope(self):
        r=reconcile_question_scopes(self.db);self.assertEqual(len(r),1);self.assertEqual(set(r[0]['unit_ids']),{'N','T'});self.assertFalse(r[0]['factual_agreement'])
    def test_network_variant_and_service_are_material(self):
        for key,value in [('network','out_of_network'),('variant','optional_rider'),('service_ids',['OTHER'])]:
            self.db.execute('update semantic_unit set context=? where id=?',(json.dumps({**self.ctx,key:value}),'T'))
            self.assertEqual(reconcile_question_scopes(self.db),[])
    def test_free_text_exceptions_do_not_collapse_into_boolean(self):
        self.db.execute("update observation set payload=?",(json.dumps({'normalized':{'type':'text','value':'Authorization except diagnostic service'}}),))
        self.assertEqual(reconcile_question_scopes(self.db),[])
    def test_unknown_service_scope_is_not_equivalent(self):
        self.db.execute('update semantic_unit set context=?',(json.dumps({**self.ctx,'service_ids':[]}),))
        self.assertEqual(reconcile_question_scopes(self.db),[])

if __name__=='__main__':unittest.main()
