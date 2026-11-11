import json,pathlib,sqlite3,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from l03_semantic_package import reconcile_same_source_amounts

class SameFieldIdentity(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.db.executescript('''
        create table semantic_unit(id text,offering_id text,kind text);
        create table observation(unit_id text,source_id text,layer text,payload text);
        create table canonical_unit(unit_id text,canonical_id text);
        create table equivalence(id text primary key,unit_id text,decision text,payload text);
        ''')
        self.src={'archive_sha256':'A','member':'H5652-002-000-2026.json','member_sha256':'B','pointer':'/pbp/0/planDeductible/inNetworkDedAmount'}
        self.add('N','cms_named_amount',{'offering_id':'P','source':self.src,'raw':'1000'})
        self.add('S','cms_json',{'locator':{k:v for k,v in self.src.items()if k!='archive_sha256'},'raw':'1000'})
    def add(self,uid,layer,payload,oid='P'):
        self.db.execute('insert into semantic_unit values (?,?,?)',(uid,oid,'claim'))
        self.db.execute('insert into observation values (?,?,?,?)',(uid,'SOURCE-'+uid,layer,json.dumps(payload)))
        self.db.execute('insert into canonical_unit values (?,?)',(uid,'CANONICAL-'+uid))
    def alias(self):return reconcile_same_source_amounts(self.db)
    def test_exact_field_alias_preserves_every_observation(self):
        self.assertEqual(len(self.alias()['same_source_field_aliases']),1)
        self.assertEqual(self.db.execute('select count(*) from observation').fetchone()[0],2)
        self.assertEqual(self.db.execute('select count(distinct canonical_id) from canonical_unit').fetchone()[0],1)
    def test_matching_amount_wrong_pointer_is_not_equivalence(self):
        x={**self.src,'pointer':'/another/service'};self.db.execute("update observation set payload=? where layer='cms_json'",(json.dumps({'locator':x,'raw':'1000'}),))
        self.assertEqual(len(self.alias()['same_source_field_aliases']),0)
    def test_wrong_member_hash_is_not_same_field(self):
        x={**self.src,'member_sha256':'DIFFERENT'};self.db.execute("update observation set payload=? where layer='cms_json'",(json.dumps({'locator':x,'raw':'1000'}),))
        self.assertFalse(self.alias()['same_source_field_aliases'])
    def test_wrong_offering_is_not_same_field(self):
        self.db.execute("update semantic_unit set offering_id='OTHER' where id='S'")
        self.assertFalse(self.alias()['same_source_field_aliases'])
    def test_ambiguous_inventory_grain_stays_separate(self):
        self.add('S2','cms_json',{'locator':self.src,'raw':'1000'})
        r=self.alias();self.assertFalse(r['same_source_field_aliases']);self.assertEqual(len(r['non_equivalences_retained']),1)
    def test_source_identity_never_approves_factual_value(self):
        self.alias();p=json.loads(self.db.execute('select payload from equivalence').fetchone()[0])
        self.assertFalse(p['accepted_for_reference']);self.assertFalse(p['amount_presence_used'])

if __name__=='__main__':unittest.main()
