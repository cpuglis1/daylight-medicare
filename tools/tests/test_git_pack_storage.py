import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
import git_pack_storage as g


class GitPrefixTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.run=self.root/'infrastructure/daylight-data/.state/maintenance/test'; self.run.mkdir(parents=True)
        self.a=self.root/'.git/objects/pack/tmp_pack_abc'; self.a.parent.mkdir(parents=True)
        self.b=self.a.with_name('tmp_pack_def')
        self.a.write_bytes(b'A'*(2*1024**2)+b'B'*(1024**2))
        self.b.write_bytes(self.a.read_bytes()[:2*1024**2+100])
        self.hash=g.m.digest(self.b)
        rows=[{'path':str(p.relative_to(self.root)), 'bytes':p.stat().st_size,
               'mtime_ns':p.stat().st_mtime_ns} for p in (self.a,self.b)]
        (self.run/'git-garbage-census.json').write_text(json.dumps({'files':rows}))

    def test_prefix_recovery_and_cow_keep_every_original_byte_and_path(self):
        self.a.chmod(0o400); self.b.chmod(0o400)
        g.plan(self.root,self.run); g.recover(self.root,self.run)
        with patch.object(g,'ensure_closed'):
            g.apply(self.root,self.run)
        self.assertEqual(g.m.digest(self.b),self.hash)
        self.assertTrue(self.a.exists())
        self.assertNotEqual(self.a.stat().st_ino,self.b.stat().st_ino)
        self.a.chmod(0o600); self.a.write_bytes(b'changed')
        self.assertEqual(g.m.digest(self.b),self.hash)

    def test_shared_first_megabyte_does_not_establish_full_prefix_equivalence(self):
        with self.b.open('r+b') as f:
            f.seek(1024**2+100); f.write(b'different')
        rows=[{'path':str(p.relative_to(self.root)), 'bytes':p.stat().st_size,
               'mtime_ns':p.stat().st_mtime_ns} for p in (self.a,self.b)]
        (self.run/'git-garbage-census.json').write_text(json.dumps({'files':rows}))
        g.plan(self.root,self.run)
        self.assertEqual(json.loads((self.run/'git-prefix-plan.json').read_text())['groups'],[])

    def test_open_handle_or_inspection_error_prevents_replacement(self):
        result=type('Result',(),{'returncode':0,'stdout':'123','stderr':''})()
        with patch.object(g.subprocess,'run',return_value=result):
            with self.assertRaisesRegex(RuntimeError,'open handles'):
                g.ensure_closed([self.a])


if __name__=='__main__':
    unittest.main()
