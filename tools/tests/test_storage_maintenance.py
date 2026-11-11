import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('storage_maintenance', Path(__file__).parents[1]/'storage_maintenance.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class PreservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root/'infrastructure/daylight-data/.state/maintenance/test'
        self.run.mkdir(parents=True)
        self.a = self.root/'docs/data/r1/source.bin'
        self.b = self.root/'docs/data/r2/source.bin'
        for p in (self.a, self.b):
            p.parent.mkdir(parents=True)
            p.write_bytes(b'original-source\n' * 80000)
            p.chmod(0o640)
        self.before = m.digest(self.a)
        self.bmtime = self.b.stat().st_mtime_ns

    def inventory(self):
        m.inventory(self.root, self.run)

    def test_requires_verified_recovery_before_replacing_any_file(self):
        self.inventory()
        inode = self.b.stat().st_ino
        with self.assertRaises(FileNotFoundError):
            m.coalesce(self.root, self.run)
        self.assertEqual(inode, self.b.stat().st_ino)

    def test_real_restore_and_independent_cow_preserve_original_paths_and_metadata(self):
        self.inventory()
        m.recover(self.root, self.run)
        m.coalesce(self.root, self.run)
        m.verify(self.root, self.run)
        self.assertTrue(json.loads((self.run/'source-parity.json').read_text())['passed'])
        self.assertEqual(m.digest(self.b), self.before)
        self.assertEqual(self.b.stat().st_mode & 0o777, 0o640)
        self.assertEqual(self.b.stat().st_mtime_ns, self.bmtime)
        self.assertNotEqual(self.a.stat().st_ino, self.b.stat().st_ino)
        self.a.write_bytes(b'changed independently')
        self.assertEqual(m.digest(self.b), self.before)

    def test_corrupt_recovery_bundle_blocks_replacement(self):
        self.inventory()
        m.recover(self.root, self.run)
        with (self.run/'source-recovery.tar.gz').open('ab') as out:
            out.write(b'corruption')
        with self.assertRaisesRegex(ValueError, 'receipt'):
            m.coalesce(self.root, self.run)
        self.assertEqual(m.digest(self.b), self.before)

    def test_source_changed_after_inventory_is_rejected(self):
        self.inventory()
        m.recover(self.root, self.run)
        self.b.write_bytes(b'new source version')
        with self.assertRaisesRegex(ValueError, 'changed'):
            m.coalesce(self.root, self.run)
        self.assertEqual(self.b.read_bytes(), b'new source version')

    def test_live_state_secrets_and_symlinks_are_excluded(self):
        for rel in ('cms-slice/var/profiles/g.db', 'docs/.env', '.env',
                    'infrastructure/daylight-data/.state/pgdata/base/1'):
            p = self.root/rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b'private')
        (self.a.parent/'linked').symlink_to(self.a)
        paths = {rel for rel, _ in m.source_paths(self.root)}
        self.assertEqual(paths, {str(self.a.relative_to(self.root)), str(self.b.relative_to(self.root))})
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            m.regular(self.root, 'docs/data/r1/linked')

    def test_different_bytes_of_same_size_are_never_deduplicated(self):
        self.b.write_bytes(b'X' * self.a.stat().st_size)
        self.inventory()
        self.assertEqual(m.read_groups(self.run), [])

    def test_disk_reserve_is_enforced(self):
        usage = type('Usage', (), {'free': m.RESERVE - 1})()
        with patch.object(m.shutil, 'disk_usage', return_value=usage):
            with self.assertRaisesRegex(RuntimeError, 'reserve'):
                m.guard(self.root)


if __name__ == '__main__':
    unittest.main()
