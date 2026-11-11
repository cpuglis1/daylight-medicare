"""Exercise native full backup/restore on complete, generated fictional data."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

from psycopg import sql

PACKAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PACKAGE/'tools'))
spec=importlib.util.spec_from_file_location('fictional_compact',PACKAGE/'tests/test_compact_database_r2.py')
support=importlib.util.module_from_spec(spec);spec.loader.exec_module(support)
spec=importlib.util.spec_from_file_location('compact_recovery',PACKAGE/'tools/compact_recovery.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
import verify_recovered_compact as standalone


@unittest.skipUnless(os.environ.get('DAYLIGHT_COMPACT_TESTS') == '1', 'Explicit local fictional PostgreSQL fixture run required')
class FullRecoveryTests(unittest.TestCase):
    def test_native_backup_clean_restore_and_all_fixture_columns_match(self):
        fixture=support.CompactBlockPostgresTests;fixture.setUpClass()
        restored='daylight_compact_recovery_fixture_'+uuid.uuid4().hex[:10]+'_test'
        try:
            support.c.load_chunk(fixture.source,fixture.target,fixture.source_set,3,20)
            with tempfile.TemporaryDirectory() as directory:
                run=Path(directory)
                (run/'complete.json').write_text(json.dumps({'passed':True,'database_bytes':fixture.target.execute('SELECT pg_database_size(current_database()) AS n').fetchone()['n']}))
                with patch.object(r.c,'TARGET',fixture.target.info.dbname),patch.object(r.c,'RUN',run),patch.object(r,'RESTORED',restored):
                    r.backup();r.restore()
                    self.assertTrue(json.loads((run/'restore-loaded.json').read_text())['passed'])
                    with r.c.connect(restored,True) as recovered:
                        self.assertEqual(r.count_rows(recovered),r.count_rows(fixture.target))
                        for table in r.c.CONTROL+['dl_migrations.applied','dl_compact.load_checkpoint']:
                            self.assertEqual(r.metadata_hash(recovered,table),r.metadata_hash(fixture.target,table))
                        for first,last in ((1,2),(3,20)):
                            params=('b'*64,'fixture',first,last)
                            self.assertEqual(r.packed_raw_hash(recovered,params),r.c.binary_hash(fixture.source,r.c.RAW_QUERY,params))
                            self.assertEqual(r.c.binary_hash(recovered,r.c.OBS_QUERY,params),r.c.binary_hash(fixture.source,r.c.OBS_QUERY,params))
                    tables=r.c.CONTROL+['dl_migrations.applied','dl_compact.source_set','dl_compact.symbol','dl_compact.evidence_state','dl_compact.migration','dl_compact.load_checkpoint']
                    expected={'passed':True,'full_integrated_restore':True,'every_logical_column_rehashed':True,
                        'counts':r.count_rows(fixture.target),'verified_chunks':2,
                        'metadata_sha256':{table:r.metadata_hash(fixture.target,table) for table in tables},
                        'offering_binary_sha256':r.c.binary_hash(fixture.target,sql.SQL('SELECT * FROM dl_evidence.offering ORDER BY derivation_id,offering_id'))[0]}
                    with patch.object(standalone.c,'SOURCE','nonexistent_original'),patch.object(standalone.c,'TARGET','nonexistent_candidate'):
                        proof=standalone.verify(restored,expected)
                        self.assertTrue(proof['passed']);self.assertFalse(proof['original_database_required'])
        finally:
            if fixture.admin.execute('SELECT 1 FROM pg_database WHERE datname=%s',(restored,)).fetchone():
                fixture.admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(restored)))
            fixture.tearDownClass()


if __name__=='__main__':unittest.main()
