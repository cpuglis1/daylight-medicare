"""Offline checks for the D199 deployment tool (no AWS, no host)."""
import json
import io
import os
from pathlib import Path
import tempfile
import tarfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import deploy_hosted_d199 as d

OLD = '/opt/daylight-pilot/releases/' + d.DEPLOYED
NEW = Path('/opt/daylight-pilot/releases/' + 'e' * 64)
UNIT = f"""[Unit]
Description=Daylight test private hosted application
[Service]
User=daylight-app
WorkingDirectory={OLD}
Environment=DAYLIGHT_MODEL_ENVIRONMENT=hosted-demo
Environment=DAYLIGHT_BLOCK_RELEASE=off
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart={d.PYTHON} {OLD}/alternatives/advisor-first/hosted_server.py --config /etc/daylight-pilot/runtime/test.json
Restart=on-failure
"""
CONFIG = json.dumps({'port': 19094, 'state': '/var/lib/daylight-state/cohorts/test', 'origin': 'https://test.daylightmedicare.com',
                     'ledger': '/var/lib/daylight-state/budget/model-usage.sqlite3', 'environment': 'test',
                     'history_dsn': 'x', 'display_dsn': 'y', 'binding': OLD + '/evidence/binding.json',
                     'release': d.DEPLOYED, 'key_file': '/run/credentials/daylight-test.service/openai'})


class DeployTests(unittest.TestCase):
    def test_reader_memory_limit_is_single_and_moves_with_checks(self):
        unit = UNIT.replace('[Service]', '[Service]\nMemoryMax=900M\nMemoryMax=850M\n'
            'LoadCredential=openai:/etc/daylight-pilot/credentials/openai\n'
            'IPAddressDeny=169.254.169.254\nIPAddressDeny=fd00:ec2::254').replace(
                '[Unit]', '[Unit]\nRequires=daylight-egress.service\nAfter=daylight-egress.service')
        on, _ = d.unit_text(unit, NEW, checks=True)
        self.assertEqual(on.count('MemoryMax='), 1)
        self.assertIn('MemoryMax=2G\n', on)
        self.assertNotIn('MemoryMax=900M', on)
        off, _ = d.unit_text(on, NEW, checks=False)
        self.assertEqual(off.count('MemoryMax='), 1)
        self.assertIn('MemoryMax=900M\n', off)
        for line in ('LoadCredential=openai:/etc/daylight-pilot/credentials/openai',
                     'IPAddressDeny=169.254.169.254', 'IPAddressDeny=fd00:ec2::254',
                     'Requires=daylight-egress.service', 'After=daylight-egress.service'):
            self.assertIn(line + '\n', on)
            self.assertIn(line + '\n', off)
        again, _ = d.unit_text(on, NEW, checks=True)
        self.assertEqual(on, again)

    def test_foundation_base_traversable_under_private_install_umask(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            binding = 'a' * 64
            base = state / 'foundation'
            archive = state / 'fictional-data.tar.gz'
            dump_bytes = b'fictional dump for filesystem-only installation check'
            with tarfile.open(archive, 'w:gz') as output:
                member = tarfile.TarInfo('foundation.dump.gz'); member.size = len(dump_bytes)
                output.addfile(member, io.BytesIO(dump_bytes))
            previous = os.umask(0o077)
            try:
                with patch.object(d, 'STATE', state), patch.object(d.pwd, 'getpwnam',
                        return_value=SimpleNamespace(pw_gid=os.getgid())), patch.object(d.os, 'chown'), \
                        patch.object(d.shutil, 'disk_usage', return_value=SimpleNamespace(free=9 * 1024**3)):
                    root, dump = d.install_foundation_files(state, {
                        'foundation_binding_id': binding, 'foundation_files': {},
                        'data_archive': archive.name, 'data_archive_sha256': d.file_sha(archive),
                        'foundation_dump_sha256': d.sha(dump_bytes)})
                self.assertEqual(base.stat().st_mode & 0o777, 0o750)
                self.assertEqual(root, base / binding[:12])
                self.assertEqual(dump.read_bytes(), dump_bytes)
            finally:
                os.umask(previous)

    def test_test_apply_refuses_second_index_before_staging_or_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory)
            (config / 'pilot.json').write_text(json.dumps({'foundation_binding': 'active-binding'}))
            with patch.object(d, 'CONFIG', config), patch.object(d, 'read_plan', return_value={}), \
                    patch.object(d, 'stage') as stage, patch.object(d, 'migrate_history') as migrate, \
                    patch.object(d, 'restore_foundation') as restore:
                with self.assertRaisesRegex(ValueError, 'second large index'):
                    d.apply(config, 'unused', 'test')
                stage.assert_not_called(); migrate.assert_not_called(); restore.assert_not_called()

    def test_unit_points_at_new_release_with_8895_runtime_settings(self):
        text, current = d.unit_text(UNIT, NEW)
        self.assertEqual(str(current), OLD)
        self.assertNotIn(OLD, text)
        self.assertIn(f'WorkingDirectory={NEW}\n', text)
        self.assertIn(f'ExecStart={d.PYTHON} {NEW}/alternatives/advisor-first/hosted_server.py', text)
        self.assertIn('Environment=DAYLIGHT_BLOCK_RELEASE=on\n', text)
        self.assertNotIn('DAYLIGHT_BLOCK_RELEASE=off', text)
        for line in d.ENVIRONMENT_LINES:
            self.assertEqual(text.count(line), 1)
        again, _ = d.unit_text(text, NEW)
        self.assertEqual(again, text)  # idempotent

    def test_unexpected_unit_is_refused(self):
        with self.assertRaises(ValueError):
            d.unit_text(UNIT.replace('Environment=DAYLIGHT_MODEL_ENVIRONMENT=hosted-demo\n', ''), NEW)

    def test_config_adds_checks_only_where_asked_and_keeps_secrets_path(self):
        on = json.loads(d.config_text(CONFIG, NEW, checks=True, foundation_root=Path('/var/lib/daylight-state/foundation/abc')))
        self.assertEqual(on['foundation_root'], '/var/lib/daylight-state/foundation/abc')
        with self.assertRaises(ValueError):
            d.config_text(CONFIG, NEW, checks=True)
        self.assertEqual(on['release'], NEW.name)
        self.assertEqual(on['binding'], f'{NEW}/evidence/binding.json')
        self.assertEqual(on['foundation_binding'], f'{NEW}/evidence/foundation-binding.json')
        self.assertIn(d.CONTROLS_DB, on['controls_dsn'])
        self.assertEqual(on['key_file'], '/run/credentials/daylight-test.service/openai')
        off = json.loads(d.config_text(json.dumps(on), NEW, checks=False))
        self.assertNotIn('foundation_binding', off)

    def test_migration_matches_the_application_source(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'alternatives/advisor-first'))
        import server  # noqa: F401
        from hosted_history import BLOCKS_SQL, BLOCKS_GRANT_SQL
        self.assertEqual(BLOCKS_SQL, d.BLOCKS_SQL)
        self.assertEqual(BLOCKS_GRANT_SQL.format('daylight_app'), d.BLOCKS_GRANT)


if __name__ == '__main__':
    unittest.main()
