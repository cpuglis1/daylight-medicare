"""Preparation never weakens the exact hash or overwrites existing metadata."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("prepare_advisor", Path(__file__).parents[1] / "prepare_advisor.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.raw = json.dumps({"metadata": {"catalog_kind": "review_metadata_and_integration_proposal",
            "consumer_release": False, "personal_recommendations_enabled": False}}).encode()
        import hashlib
        self.digest = hashlib.sha256(self.raw).hexdigest()
        source = self.root / module.SOURCE
        source.parent.mkdir(parents=True)
        source.write_bytes(self.raw)
        self.patch = patch.object(module, "DIGEST", self.digest)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        journey = json.dumps({"fictional": True}).encode()
        destination = self.root / module.JOURNEY_SOURCE
        destination.parent.mkdir(parents=True)
        destination.write_bytes(journey)
        self.journey_patch = patch.object(module, "JOURNEY_DIGEST", hashlib.sha256(journey).hexdigest())
        self.journey_patch.start()
        self.addCleanup(self.journey_patch.stop)
        evaluator = b"# fictional evaluator stand-in for preparation safety tests\n"
        (self.root / module.EVALUATOR_SOURCE).write_bytes(evaluator)
        self.evaluator_patch = patch.object(module, "EVALUATOR_DIGEST", hashlib.sha256(evaluator).hexdigest())
        self.evaluator_patch.start()
        self.addCleanup(self.evaluator_patch.stop)

    def test_exact_copy_and_idempotent_repeat(self):
        first = module.prepare(self.root)
        second = module.prepare(self.root)
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertFalse(first["source_acceptance_changed"])
        self.assertEqual((self.root / module.TARGET).read_bytes(), self.raw)

    def test_source_digest_tampering_is_rejected(self):
        (self.root / module.SOURCE).write_bytes(self.raw + b" ")
        with self.assertRaises(ValueError):
            module.prepare(self.root)
        self.assertFalse((self.root / module.TARGET).exists())

    def test_existing_different_file_is_preserved(self):
        target = self.root / module.TARGET
        target.parent.mkdir(parents=True)
        target.write_bytes(b"preserve this original")
        with self.assertRaises(ValueError):
            module.prepare(self.root)
        self.assertEqual(target.read_bytes(), b"preserve this original")

    def test_symlink_parent_is_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.root / "docs").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            module.prepare(self.root)
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
