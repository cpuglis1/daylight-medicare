import json,pathlib,sqlite3,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from l03_semantic_package import retain_empty_amount_annotations

class EmptySourceAmounts(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.db.executescript('''
        create table semantic_unit(id text);
        create table observation(id text,unit_id text,source_id text,layer text,payload text);
        create table canonical_unit(unit_id text,canonical_id text);
        create table lineage(root_id text,unit_id text);
        create table source_target(source_id text,unit_id text);
        create table source_disposition(source_id text,disposition text,rule text);
        ''')
        for uid,raw in [('A',None),('B',''),('C','0.00'),('D','($12.00)')]:
            p={'offering_id':'P','raw':raw,'value':None,'source':{'pointer':'/'+uid}}
            self.db.execute('insert into semantic_unit values (?)',(uid,));self.db.execute('insert into observation values (?,?,?,?,?)',(uid,uid,'S'+uid,'cms_named_amount',json.dumps(p)))
            self.db.execute('insert into canonical_unit values (?,?)',(uid,uid));self.db.execute('insert into source_target values (?,?)',('S'+uid,uid));self.db.execute('insert into source_disposition values (?,?,?)',('S'+uid,'required','original'))
    def test_blank_is_retained_unknown_instead_of_invented_claim(self):
        r=retain_empty_amount_annotations(self.db)
        self.assertEqual({x['source_id']for x in r},{'SA','SB'})
        self.assertEqual({x[0]for x in self.db.execute('select id from semantic_unit')},{'C','D'})
        self.assertEqual(self.db.execute('select count(*) from retained_amount_annotation').fetchone()[0],2)
    def test_numeric_zero_and_unparsed_nonblank_are_not_discarded(self):
        retain_empty_amount_annotations(self.db)
        rows=[json.loads(p)for p, in self.db.execute('select payload from observation')]
        self.assertEqual({x['raw']for x in rows},{'0.00','($12.00)'})
    def test_no_original_requirement_can_disappear_as_empty_annotation(self):
        self.db.execute("insert into lineage values ('ORIGINAL','A')")
        with self.assertRaises(ValueError):retain_empty_amount_annotations(self.db)

if __name__=='__main__':unittest.main()
