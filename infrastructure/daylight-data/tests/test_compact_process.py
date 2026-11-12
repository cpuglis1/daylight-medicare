import importlib.util
from pathlib import Path
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch

SPEC=importlib.util.spec_from_file_location('compact_process',Path(__file__).resolve().parents[1]/'tools/compact_process.py')
m=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(m)


class RestoreReserveTests(unittest.TestCase):
    def test_reserve_breach_cancels_only_owned_restore_backend(self):
        calls=[]
        class Database:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def execute(self,query,params):calls.append((query,params))
        process=SimpleNamespace(terminate=lambda:calls.append('terminate'))
        c=SimpleNamespace(ROOT=Path('/private/tmp'),RESERVE=1024,connect=lambda name:Database())
        with patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=0)):
            with self.assertRaisesRegex(RuntimeError,'reserve'):
                with m.reserve_watch(c,process,'fictional_restore_test','owned-label'):
                    time.sleep(.3)
        self.assertEqual(calls[0][1],('fictional_restore_test','owned-label'))
        self.assertIn('pg_cancel_backend',calls[0][0])
        self.assertEqual(calls[1],'terminate')

    def test_child_environment_excludes_credentials_and_unrelated_pg_options(self):
        with patch.dict(m.os.environ,{'OPENAI_API_KEY':'fictional','PGOPTIONS':'unrelated','PATH':'/bin'},clear=True):
            self.assertEqual(m.environment('owned-label'),{'PATH':'/bin','PGAPPNAME':'owned-label'})


if __name__=='__main__':unittest.main()
