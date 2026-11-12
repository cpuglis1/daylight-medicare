"""Actual atomic cutover/rollback tests, entirely on generated fictional rows."""
import importlib.util
import hashlib
import json
import os
import gzip
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from psycopg import sql

PACKAGE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fictional_compact',PACKAGE/'tests/test_compact_database_r2.py')
support=importlib.util.module_from_spec(spec);spec.loader.exec_module(support)
spec=importlib.util.spec_from_file_location('deploy_compact',PACKAGE/'tools/deploy_compact.py')
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)


@unittest.skipUnless(os.environ.get('DAYLIGHT_COMPACT_TESTS') == '1', 'Explicit local fictional PostgreSQL fixture run required')
class DeploymentTests(unittest.TestCase):
    def test_atomic_cutover_drop_dependencies_and_real_rollback_keep_all_columns(self):
        fixture=support.CompactBlockPostgresTests
        fixture.setUpClass()
        try:
            support.c.load_chunk(fixture.source,fixture.target,fixture.source_set,3,20)
            with tempfile.TemporaryDirectory() as directory:
                run=Path(directory)
                dump=subprocess.run([str(PACKAGE/'.postgres18/bin/pg_dump'),'--format=custom','--compress=none',
                    '--dbname='+support.c.dsn(fixture.target.info.dbname)],capture_output=True,check=True).stdout
                archive=run/'full.dump.gz'
                with gzip.open(archive,'wb') as out:out.write(dump)
                selected=d.stage_selection(archive,run/'selected.list')
                subprocess.run([str(PACKAGE/'.postgres18/bin/pg_restore'),'--single-transaction','--exit-on-error',
                    '--no-owner','--use-list='+str(selected),'--dbname='+support.c.dsn(fixture.source.info.dbname)],input=dump,capture_output=True,check=True)
                (run/'recovery-verified.json').write_text('{"fictional_test_only":true}')
                (run/'stage-verified.json').write_text(json.dumps({'passed':True,'every_staged_logical_column_matches_original_hashes':True,'frozen_live_controls_and_population_unchanged':True,
                    'read_adapter_sha256':d.c.hashfile(PACKAGE/'redesign/r3/read_views.sql'),'operator_sha256':d.c.hashfile(Path(d.__file__))}))
                params=('b'*64,'fixture',1,20)
                before=support.c.binary_hash(fixture.source,support.c.RAW_QUERY,params)
                contracts={name:d.column_contract(fixture.source,'dl_evidence',name) for name in ('source_record','observation','offering')}
                with patch.object(d.c,'SOURCE',fixture.source.info.dbname),patch.object(d.c,'RUN',run),\
                     patch.object(d.c,'source_contract',return_value={'fictional_test_only':True}),\
                     patch.object(d,'gate',return_value=({},{})):
                    d.cutover()
                    for name,contract in contracts.items():
                        self.assertEqual(d.column_contract(fixture.source,'dl_evidence',name),contract)
                    self.assertEqual(support.c.binary_hash(fixture.source,support.c.RAW_QUERY,params),before)
                    self.assertEqual(fixture.source.execute("SELECT relkind FROM pg_class WHERE oid='dl_evidence.source_record'::regclass").fetchone()['relkind'],'v')
                    self.assertEqual(fixture.source.execute("SELECT count(*) AS n FROM dl_legacy_d94.source_record").fetchone()['n'],20)
                    self.assertEqual(fixture.source.execute("SELECT count(*) AS n FROM dl_released.offerings").fetchone()['n'],0)
                    # Actual dependency test is rolled back; no original is retired.
                    class RollbackProbe(Exception):pass
                    try:
                        with fixture.source.transaction():
                            fixture.source.execute('DROP TABLE dl_legacy_d94.offering,dl_legacy_d94.observation,dl_legacy_d94.source_record')
                            raise RollbackProbe()
                    except RollbackProbe:pass
                    (run/'live-serving-audit.json').write_text('{"passed":false,"plans":0}')
                    (run/'live-final-checks.json').write_text('{"passed":false}')
                    with self.assertRaisesRegex(ValueError,'validation'):
                        d.retire_legacy()
                    d.rollback()
                    self.assertEqual(support.c.binary_hash(fixture.source,support.c.RAW_QUERY,params),before)
                    self.assertEqual(fixture.source.execute("SELECT relkind FROM pg_class WHERE oid='dl_evidence.source_record'::regclass").fetchone()['relkind'],'r')
        finally:
            fixture.tearDownClass()


class RetirementGateTests(unittest.TestCase):
    def test_corrupt_archive_or_incomplete_recovery_cannot_authorize_retirement(self):
        with tempfile.TemporaryDirectory() as directory:
            run=Path(directory);archive=run/'verified.dump.gz';archive.write_bytes(b'fictional recovered archive')
            fingerprint=hashlib.sha256(archive.read_bytes()).hexdigest()
            (run/'backup.json').write_text(json.dumps({'archive':str(archive),'sha256':fingerprint}))
            recovery={'passed':True,'full_integrated_restore':True,'every_logical_column_rehashed':True,'backup_sha256':fingerprint}
            (run/'recovery-verified.json').write_text(json.dumps(recovery))
            with patch.object(d.c,'RUN',run):
                self.assertTrue(d.gate()[0]['passed'])
                archive.write_bytes(b'corrupt')
                with self.assertRaisesRegex(ValueError,'recovery proof'):
                    d.gate()
                archive.write_bytes(b'fictional recovered archive')
                recovery['full_integrated_restore']=False
                (run/'recovery-verified.json').write_text(json.dumps(recovery))
                with self.assertRaisesRegex(ValueError,'recovery proof'):
                    d.gate()


if __name__=='__main__':unittest.main()
