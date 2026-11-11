"""Recover complete fictional tables, verify them, then release scratch copies."""
import importlib.util
import gzip
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import nullcontext
from unittest.mock import patch,MagicMock
import uuid

from psycopg import sql

PACKAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PACKAGE/'tools'))
import compact_bounded_recovery as b
spec=importlib.util.spec_from_file_location('bounded_fixture',PACKAGE/'tests/test_compact_database_r2.py')
support=importlib.util.module_from_spec(spec);spec.loader.exec_module(support)


class SectionPipeTests(unittest.TestCase):
    def test_early_pipe_close_requires_successful_native_exit(self):
        for code in (0,1):
            with self.subTest(code=code),tempfile.TemporaryDirectory() as directory:
                run=Path(directory);archive=run/'fixture.gz'
                with gzip.open(archive,'wb') as out:out.write(b'fictional archive bytes')
                proc=MagicMock();proc.stdin.write.side_effect=BrokenPipeError();proc.wait.return_value=code;proc.poll.return_value=code
                with patch.object(b.c,'RUN',run),patch.object(b.subprocess,'Popen',return_value=proc),patch.object(b,'reserve_watch',return_value=nullcontext()):
                    if code:
                        with self.assertRaisesRegex(RuntimeError,'Bounded restore failed'):b.restore_part(archive,'fixture',[])
                        self.assertFalse((run/'bounded-fixture.json').exists())
                    else:
                        b.restore_part(archive,'fixture',[])
                        self.assertTrue(json.loads((run/'bounded-fixture.json').read_text())['passed'])


@unittest.skipUnless(os.environ.get('DAYLIGHT_COMPACT_TESTS')=='1','Explicit local fictional PostgreSQL fixture run required')
class BoundedRecoveryTests(unittest.TestCase):
    def test_full_restore_with_per_table_proof_before_scratch_retirement(self):
        f=support.CompactBlockPostgresTests;f.setUpClass()
        restored='daylight_bounded_fixture_'+uuid.uuid4().hex[:10]+'_test'
        try:
            support.c.load_chunk(f.source,f.target,f.source_set,3,20)
            f.target.execute('CREATE TEMP TABLE digest_fixture(value jsonb,note text)')
            f.target.execute("INSERT INTO digest_fixture VALUES ('{\"unknown\":null}',NULL),('{\"unknown\":\"null\"}','')")
            baseline=b.table_hash(f.target,'digest_fixture')
            f.target.execute('CREATE TEMP TABLE digest_reordered AS SELECT * FROM digest_fixture ORDER BY note NULLS LAST')
            self.assertEqual(b.table_hash(f.target,'digest_reordered'),baseline)
            f.target.execute("UPDATE digest_reordered SET value='{\"unknown\":false}' WHERE note IS NULL")
            self.assertNotEqual(b.table_hash(f.target,'digest_reordered'),baseline)
            f.target.execute('INSERT INTO digest_fixture SELECT * FROM digest_fixture LIMIT 1')
            self.assertEqual(b.table_hash(f.target,'digest_fixture')['rows'],3)
            self.assertNotEqual(b.table_hash(f.target,'digest_fixture'),baseline)
            with tempfile.TemporaryDirectory() as directory:
                run=Path(directory)
                (run/'complete.json').write_text(json.dumps({'passed':True}))
                (run/'compact-target.json').write_text(json.dumps({'marker':'fictional'}))
                expected={name:b.table_hash(f.target,'dl_compact.'+name) for name in b.BIG}
                with patch.object(b.c,'TARGET',f.target.info.dbname),patch.object(b.c,'SOURCE',f.source.info.dbname),patch.object(b.c,'RUN',run),patch.object(b.r,'RESTORED',restored),patch.object(b.c,'source_contract'),patch.object(b.c,'assert_target'):
                    b.r.backup();b.restore()
                    self.assertTrue(json.loads((run/'restore-loaded.json').read_text())['all_post_data_restored'])
                    with b.c.connect(restored,True) as recovered:
                        for name in b.BIG:
                            self.assertEqual(b.table_hash(recovered,'dl_compact.'+name),expected[name])
                            self.assertEqual(f.target.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier('dl_compact',name))).fetchone()['n'],0)
                        for first,last in ((1,2),(3,20)):
                            params=('b'*64,'fixture',first,last)
                            self.assertEqual(b.r.packed_raw_hash(recovered,params),b.c.binary_hash(f.source,b.c.RAW_QUERY,params))
                            self.assertEqual(b.c.binary_hash(recovered,b.c.OBS_QUERY,params),b.c.binary_hash(f.source,b.c.OBS_QUERY,params))
                        self.assertEqual(recovered.execute('SELECT count(*) AS n FROM pg_constraint WHERE NOT convalidated').fetchone()['n'],0)
                    with self.assertRaisesRegex(ValueError,'proof required'):
                        b.retire_temporary_tables(f.target,['source_page'],{}, {'marker':'fictional'})
        finally:
            if f.admin.execute('SELECT 1 FROM pg_database WHERE datname=%s',(restored,)).fetchone():
                f.admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(restored)))
            f.tearDownClass()


if __name__=='__main__':unittest.main()
