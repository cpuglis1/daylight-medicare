"""Provider-free operations failure and restore-contract checks; fictional IDs."""
from datetime import datetime,timezone,timedelta
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('hosted_operations',Path(__file__).with_name('hosted_operations.py'))
ops=importlib.util.module_from_spec(spec);spec.loader.exec_module(ops)


class OperationsTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.state=self.root/'state';self.state.mkdir()
        p=patch.object(ops,'STATE',self.state);p.start();self.addCleanup(p.stop)
        self.visit='a'*32
        for env in ops.ENVIRONMENTS:
            directory=self.state/'cohorts'/env;directory.mkdir(parents=True)
            with ops.sqlite_database(directory/'access.sqlite3',mode='rwc') as db:
                db.execute('CREATE TABLE invites(id TEXT PRIMARY KEY,revoked INTEGER NOT NULL DEFAULT 0)')
                db.execute('INSERT INTO invites(id) VALUES (?)',(self.visit,))
        self.config={'bucket':'fictional-private','kms_key':'fictional-key','region':'us-east-1'}

    def revoked(self):
        with ops.access('pilot') as db:return db.execute('SELECT revoked FROM invites').fetchone()[0]

    def test_journal_commit_precedes_revocation_and_database_delete(self):
        def put(path,key,config):
            self.assertEqual(self.revoked(),0)
            self.assertTrue((self.state/'operations/deletions/pilot'/('a'*32+'.pending')).exists())
        def pg(query,environment):
            self.assertEqual(self.revoked(),1)
            self.assertTrue((self.state/'operations/deletions/pilot'/('a'*32+'.json')).exists())
        with patch.object(ops,'put_once',side_effect=put) as upload,patch.object(ops,'pg',side_effect=pg):
            self.assertEqual(ops.delete_visit('pilot',self.visit,self.config),{'deleted':True})
            ops.delete_visit('pilot',self.visit,self.config)
            self.assertEqual(upload.call_count,1)

    def test_storage_failure_does_not_claim_delete_or_revoke(self):
        with patch.object(ops,'put_once',side_effect=RuntimeError),patch.object(ops,'aws',side_effect=RuntimeError),patch.object(ops,'pg') as pg:
            with self.assertRaises(RuntimeError):ops.delete_visit('pilot',self.visit,self.config)
            self.assertEqual(self.revoked(),0);pg.assert_not_called()
            self.assertTrue((self.state/'operations/deletions/pilot'/('a'*32+'.pending')).exists())

    def test_lost_put_acknowledgement_recovers_existing_immutable_marker(self):
        def read(args,config):
            Path(args[-1]).write_text(json.dumps({'schema':1,'environment':'pilot','visit':self.visit}))
            return b'{}'
        with patch.object(ops,'put_once',side_effect=RuntimeError),patch.object(ops,'aws',side_effect=read),patch.object(ops,'pg'):
            self.assertEqual(ops.delete_visit('pilot',self.visit,self.config),{'deleted':True})

    def test_wrong_remote_marker_refuses_deletion(self):
        def read(args,config):
            Path(args[-1]).write_text(json.dumps({'schema':1,'environment':'test','visit':self.visit}))
            return b'{}'
        with patch.object(ops,'put_once',side_effect=RuntimeError),patch.object(ops,'aws',side_effect=read),patch.object(ops,'pg') as pg:
            with self.assertRaises(ValueError):ops.delete_visit('pilot',self.visit,self.config)
            pg.assert_not_called();self.assertEqual(self.revoked(),0)

    def test_database_outage_revokes_access_and_maintenance_retries_without_another_put(self):
        with patch.object(ops,'put_once') as upload,patch.object(ops,'pg',side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):ops.delete_visit('pilot',self.visit,self.config)
            self.assertEqual(self.revoked(),1)
        with patch.object(ops,'put_once') as upload,patch.object(ops,'pg') as pg:
            ops.retry_deletions(self.config);upload.assert_not_called();pg.assert_called_once()

    def test_retry_allowance_survives_new_calls_and_leaves_no_extra_intent(self):
        with patch.object(ops,'MAX_DAILY_MARKER_ATTEMPTS',1),patch.object(ops,'put_once',side_effect=RuntimeError),patch.object(ops,'aws',side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):ops.delete_visit('pilot',self.visit,self.config)
            with self.assertRaisesRegex(RuntimeError,'daily retry'):ops.delete_visit('pilot',self.visit,self.config)
            self.assertEqual(json.loads((self.state/'operations/marker-attempts.json').read_text())['count'],1)

    def test_invalid_and_unknown_visits_never_call_aws(self):
        with patch.object(ops,'aws') as aws:
            for visit in ('../../bad','z'*32,'b'*32):
                with self.assertRaises(ValueError):ops.delete_visit('pilot',visit,self.config)
            aws.assert_not_called()

    def test_only_matching_owner_export_removed(self):
        directory=self.state/'owner-exports';directory.mkdir()
        (directory/'one.json').write_text(json.dumps({'visit':self.visit,'turns':[]}))
        (directory/'two.json').write_text(json.dumps({'visit':'b'*32,'turns':[]}))
        with patch.object(ops,'put_once'),patch.object(ops,'pg'):
            ops.delete_visit('pilot',self.visit,self.config)
        self.assertFalse((directory/'one.json').exists());self.assertTrue((directory/'two.json').exists())

    def test_put_is_immutable_encrypted_and_prefix_scoped(self):
        with patch.object(ops,'aws') as aws:
            ops.put_once(Path('/fictional'),'hosted-backups/deletions/pilot/'+self.visit+'.json',self.config)
            args=aws.call_args.args[0]
            self.assertIn('--if-none-match',args);self.assertIn('aws:kms',args)
            with self.assertRaises(ValueError):ops.put_once(Path('/fictional'),'other/key',self.config)

    def archive(self,age_days=0,bad_member=False):
        manifest={'schema':1,'created_at':(datetime.now(timezone.utc)-timedelta(days=age_days)).isoformat(),
            'budget_restore':'blocked_until_provider_reconciliation',
            'restore_requires':'latest_s3_deletions_then_expire_before_any_service_start'}
        database=self.root/'check.sqlite3'
        with ops.sqlite_database(database,mode='rwc') as db:db.execute('CREATE TABLE IF NOT EXISTS check_table(x)')
        files={'manifest.json':json.dumps(manifest).encode(),
               'pilot.dump':b'fictional pg dump','test.dump':b'fictional pg dump',
               'pilot-signing.key':b'a'*32,'test-signing.key':b'b'*32,
               **{name:database.read_bytes() for name in ('pilot-access.sqlite3','test-access.sqlite3','model-usage.sqlite3')}}
        if bad_member:files['../../unexpected']=b'bad'
        path=self.root/'backup.tar.gz'
        with tarfile.open(path,'w:gz') as archive:
            for name,data in files.items():
                member=tarfile.TarInfo(name);member.size=len(data);archive.addfile(member,io.BytesIO(data))
        return path,hashlib.sha256(path.read_bytes()).hexdigest()

    def test_archive_integrity_never_implies_service_resume(self):
        path,digest=self.archive()
        with patch.object(ops,'run') as run:
            report=ops.verify_archive(path,digest)
            self.assertTrue(report['archive_integrity_verified']);self.assertFalse(report['service_resume_permitted'])
            self.assertEqual(run.call_count,2)

    def test_old_backup_rejected_even_if_s3_has_not_physically_expired_it(self):
        path,digest=self.archive(age_days=29)
        with self.assertRaisesRegex(ValueError,'recovery window'):ops.verify_archive(path,digest)

    def test_traversal_and_digest_mismatch_rejected(self):
        path,digest=self.archive(bad_member=True)
        with self.assertRaisesRegex(ValueError,'inventory'):ops.verify_archive(path,digest)
        with self.assertRaisesRegex(ValueError,'digest'):ops.verify_archive(path,'0'*64)

    def test_lost_backup_ack_recovers_only_matching_metadata(self):
        directory=self.state/'operations';directory.mkdir()
        day=datetime.now(timezone.utc).strftime('%Y-%m-%d')
        info={'key':'hosted-backups/daily/'+day+'.tar.gz','sha256':'a'*64,'bytes':42}
        (directory/('backup-'+day+'.pending')).write_text(json.dumps(info))
        with patch.object(ops,'aws',return_value=json.dumps({'Metadata':{'sha256':'a'*64},'ContentLength':42}).encode()) as aws:
            self.assertEqual(ops.backup(self.config),info)
            self.assertEqual(aws.call_count,1)
        self.assertTrue((directory/('backup-'+day+'.json')).exists())

    def prepare_backup(self):
        for environment in ops.ENVIRONMENTS:
            (self.state/'cohorts'/environment/'signing.key').write_bytes(b's'*32)
        directory=self.state/'budget';directory.mkdir()
        with ops.sqlite_database(directory/'model-usage.sqlite3',mode='rwc') as db:
            db.execute('CREATE TABLE held_budget(amount INTEGER)')

    def test_generated_backup_has_encryption_digest_and_daily_idempotence(self):
        self.prepare_backup()
        def dump(args,**kwargs):
            kwargs['stdout'].write(b'fictional dump');return SimpleNamespace(returncode=0)
        with patch.object(ops,'expire'),patch.object(ops,'pg',return_value=b'100'), \
                patch.object(ops.subprocess,'run',side_effect=dump),patch.object(ops,'aws') as aws, \
                patch.object(ops.shutil,'disk_usage',return_value=SimpleNamespace(free=4*1024**3)):
            result=ops.backup(self.config)
            self.assertLess(result['bytes'],ops.MAX_BACKUP)
            args=aws.call_args.args[0]
            self.assertIn('sha256='+result['sha256'],args);self.assertIn('aws:kms',args)
            self.assertEqual(ops.backup(self.config),{'already_completed':True})
            self.assertEqual(aws.call_count,1)

    def test_oversized_backup_refuses_upload(self):
        self.prepare_backup()
        def dump(args,**kwargs):
            kwargs['stdout'].write(b'fictional dump');return SimpleNamespace(returncode=0)
        with patch.object(ops,'expire'),patch.object(ops,'pg',return_value=b'100'), \
                patch.object(ops.subprocess,'run',side_effect=dump),patch.object(ops,'aws') as aws, \
                patch.object(ops,'MAX_BACKUP',1), \
                patch.object(ops.shutil,'disk_usage',return_value=SimpleNamespace(free=4*1024**3)):
            with self.assertRaisesRegex(RuntimeError,'daily storage bound'):ops.backup(self.config)
            aws.assert_not_called()


if __name__=='__main__':unittest.main()
