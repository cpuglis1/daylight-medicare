import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('mvp_serving_snapshot', Path(__file__).parents[1]/'mvp_serving_snapshot.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)
ROOT = Path(__file__).resolve().parents[2]


class SnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.temp.name)/'shadow.sqlite3'
        cls.result = m.build(ROOT, cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_all_feature_dependencies_and_holds_survive_actual_source_roundtrip(self):
        self.assertTrue(self.result['passed'])
        self.assertEqual(self.result['counts']['family'], 72*14)
        self.assertEqual(self.result['counts']['question'], 41)
        self.assertEqual(self.result['total_material_holds'], 229)
        self.assertFalse(self.result['new_acceptance'])

    def test_corrupt_query_state_is_detected_even_when_source_objects_are_untouched(self):
        db = sqlite3.connect(':memory:')
        with sqlite3.connect(self.path) as source:
            source.backup(db)
        try:
            db.execute("UPDATE benefit SET state='published_candidate' WHERE state='held' AND (offering_id,field) IN (SELECT offering_id,field FROM benefit WHERE state='held' LIMIT 1)")
            with self.assertRaisesRegex(ValueError, 'Query index differs'):
                m.verify(db, ROOT)
        finally:
            db.close()

    def test_existing_snapshot_cannot_be_overwritten(self):
        with self.assertRaises(FileExistsError):
            m.build(ROOT, self.path)


if __name__ == '__main__':
    unittest.main()
