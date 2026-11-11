"""Exact bounded archive sources without extraction or invented loose paths."""
import hashlib
from pathlib import Path
import tempfile
import unittest
import warnings
import zipfile

from daylight_data.comparison_pipeline.common import canonical, file_hash, safe_json
from daylight_data.comparison_pipeline.preparation import prepare_batch
from daylight_data.comparison_pipeline.runner import verify_binding


class ArchiveSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.zip = self.root / "published.zip"
        self.data = b"contract,plan\nH5652,002\n"
        with zipfile.ZipFile(self.zip, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("published/plans.csv", self.data)
        self.binding = {"path": self.zip.name, "archive_sha256": file_hash(self.zip),
                        "member": "published/plans.csv", "member_bytes": len(self.data),
                        "sha256": hashlib.sha256(self.data).hexdigest(), "role": "published_member"}

    def test_exact_member_is_verified_without_writing_extracted_files(self):
        actual = verify_binding(self.root, self.binding)
        self.assertEqual(actual, self.binding)
        self.assertEqual(list(self.root.iterdir()), [self.zip])

    def test_member_hash_size_and_archive_pins_are_independent(self):
        for key, value in (("sha256", "0" * 64), ("archive_sha256", "1" * 64),
                           ("member_bytes", len(self.data) + 1), ("member", "not-present")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify_binding(self.root, {**self.binding, key: value})

    def test_unsafe_or_unbounded_member_descriptor_is_rejected(self):
        for patch in ({"member": "../outside"}, {"member": "/absolute"},
                      {"member_bytes": True}, {"member_bytes": 257 * 1024 * 1024}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                verify_binding(self.root, {**self.binding, **patch})

    def test_duplicate_zip_member_cannot_choose_an_arbitrary_occurrence(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.zip, "a") as archive:
                archive.writestr(self.binding["member"], self.data)
        self.binding["archive_sha256"] = file_hash(self.zip)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            verify_binding(self.root, self.binding)

    def test_preparation_binds_archive_bytes_and_retains_member_descriptor(self):
        record = {"artifact_type": "native_literal", "id": "source-literal", "offering_id": "2026:H5652:002:000",
                  "original_ids": ["CANONICAL-example"], "payload": {"raw": None}, "pointer": "/raw"}
        path = self.root / "input.json"
        path.write_bytes(canonical(record))
        spec = {"offerings": [record["offering_id"]], "catalogs": [{"path": path.name,
                "sha256": file_hash(path), "offering_id": record["offering_id"]}], "sources": [self.binding]}
        prepare_batch(self.root, spec, self.root / "prepared")
        manifest = safe_json((self.root / "prepared/batch-manifest.json").read_bytes())
        self.assertEqual(manifest["sources"][0], self.binding)
        provenance = safe_json((self.root / "prepared/preparation-provenance.json").read_bytes())
        self.assertEqual(provenance["input_byte_bindings"][self.zip.name], file_hash(self.zip))


if __name__ == "__main__":
    unittest.main()
