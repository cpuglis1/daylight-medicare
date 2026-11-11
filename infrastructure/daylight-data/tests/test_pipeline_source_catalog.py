"""Bounded explicit source discovery; manifests cannot self-authorize hashes."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from daylight_data.comparison_pipeline.source_catalog import resolve_source_bindings


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class SourceCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="daylight-source-catalog-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "repository"
        self.root.mkdir()

    def file(self, path, content=b"source bytes"):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return sha(content)

    def manifest(self, path, value):
        return self.file(path, json.dumps(value, sort_keys=True).encode())

    def resolve(self, hashes, manifests=None, **kwargs):
        return resolve_source_bindings(self.root, set(hashes), manifests or ["manifest.json"], **kwargs)

    def test_objects_maps_and_absolute_inside_paths_resolve_actual_bytes(self):
        a = self.file("data/a.pdf", b"A")
        b = self.file("data/b.txt", b"B")
        c = self.file("data/c.xlsx", b"C")
        self.manifest("manifest.json", {"files": [
            {"path": "data/a.pdf", "sha256": a},
            {"path": str(self.root / "data/b.txt"), "file_sha256": b}],
            "map": {"data/c.xlsx": c}})
        result = self.resolve([a, b, c])
        self.assertEqual([row["path"] for row in result["sources"]], ["data/a.pdf", "data/b.txt", "data/c.xlsx"])
        self.assertEqual(result["unresolved_hashes"], [])
        self.assertTrue(all(row["role"] == "exact_cited_source_bytes" for row in result["sources"]))
        self.assertFalse(result["accepted_for_reference"])

    def test_false_embedded_hash_cannot_become_verified_source(self):
        actual = self.file("data/source.pdf", b"actual")
        false = "f" * 64
        self.manifest("manifest.json", {"path": "data/source.pdf", "source_sha256": false})
        result = self.resolve([actual, false])
        self.assertEqual(result["sources"][0]["sha256"], actual)
        self.assertEqual(result["unresolved_hashes"], [false])
        self.assertTrue(any(row["code"] == "DECLARED_HASH_MISMATCH" for row in result["diagnostics"]))

    def test_equal_bytes_at_multiple_paths_keep_every_path_and_provenance(self):
        expected = self.file("data/a", b"same")
        self.file("data/b", b"same")
        self.manifest("manifest.json", [{"path": "data/b", "sha256": expected},
                                        {"path": "data/a", "sha256": expected}])
        result = self.resolve([expected])
        self.assertEqual([row["path"] for row in result["sources"]], ["data/a", "data/b"])
        self.assertEqual(result["metrics"]["resolved_hash_count"], 1)
        self.assertEqual(result["metrics"]["verified_source_path_count"], 2)
        self.assertEqual({row["declaring_manifest"] for row in result["candidate_provenance"]
                          if row["actual_sha256"] == expected}, {"manifest.json"})

    def test_missing_file_and_escapes_are_explicit_and_never_read(self):
        outside = Path(self.temporary.name) / "outside"
        outside.write_bytes(b"outside")
        wanted = sha(b"outside")
        self.manifest("manifest.json", [{"path": "missing.pdf", "sha256": wanted},
                                        {"path": "../outside", "sha256": wanted},
                                        {"path": str(outside), "sha256": wanted},
                                        {"path": "https://example.test/source.pdf", "sha256": wanted}])
        result = self.resolve([wanted])
        self.assertEqual(result["sources"], [])
        self.assertEqual(result["unresolved_hashes"], [wanted])
        self.assertEqual(result["metrics"]["files_hashed"], 1)  # Only the selected manifest.
        self.assertIn("REFERENCED_FILE_UNAVAILABLE", {row["code"] for row in result["diagnostics"]})
        self.assertIn("REJECTED_PATH", {row["code"] for row in result["diagnostics"]})

    def test_symlink_escape_rejected_and_inside_alias_keeps_reference_lineage(self):
        outside = Path(self.temporary.name) / "outside"
        outside.write_bytes(b"outside")
        inside = self.file("data/inside", b"inside")
        (self.root / "escaped").symlink_to(outside)
        (self.root / "alias").symlink_to(self.root / "data/inside")
        self.manifest("manifest.json", [{"path": "escaped", "sha256": sha(b"outside")},
                                        {"path": "alias", "sha256": inside}])
        result = self.resolve([inside, sha(b"outside")])
        self.assertEqual([row["path"] for row in result["sources"]], ["data/inside"])
        self.assertTrue(any(row["referenced_path"] == "alias" for row in result["candidate_provenance"]))
        self.assertEqual(result["unresolved_hashes"], [sha(b"outside")])

    def test_only_correctly_pinned_explicit_json_children_are_followed(self):
        source = self.file("data/source.pdf", b"needed")
        child = self.manifest("nested/child.json", {"data/source.pdf": source})
        self.manifest("manifest.json", {"child": {"path": "nested/child.json", "sha256": child}})
        result = self.resolve([source])
        self.assertTrue(result["all_wanted_hashes_resolved"])
        self.assertEqual(result["metrics"]["manifests_parsed"], 2)
        self.manifest("manifest.json", {"child": {"path": "nested/child.json", "sha256": "e" * 64}})
        blocked = self.resolve([source])
        self.assertEqual(blocked["unresolved_hashes"], [source])
        self.assertEqual(blocked["metrics"]["manifests_parsed"], 1)

    def test_plain_existing_string_paths_are_candidates_not_child_traversal_permission(self):
        source = self.file("source.pdf", b"needed")
        child = self.manifest("child.json", {"source.pdf": source})
        self.manifest("manifest.json", ["child.json", "source.pdf"])
        result = self.resolve([source, child])
        self.assertEqual(result["unresolved_hashes"], [])
        self.assertEqual(result["metrics"]["manifests_parsed"], 1)
        self.assertTrue(any(row["untrusted_path_only"] for row in result["candidate_provenance"]
                            if row["path"] == "child.json"))

    def test_freeze_member_paths_can_be_relative_to_the_manifest(self):
        source = self.file("packet/member.pdf", b"member")
        self.manifest("packet/freeze.json", {"files_sha256": {"member.pdf": source}})
        result = self.resolve([source], ["packet/freeze.json"])
        self.assertEqual(result["sources"][0]["path"], "packet/member.pdf")
        self.assertTrue(any(row["resolution_anchor"] == "manifest_relative" for row in result["candidate_provenance"]
                            if row["path"] == "packet/member.pdf"))

    def test_duplicate_json_keys_reject_the_entire_manifest_payload(self):
        source = self.file("source.pdf", b"source")
        self.file("manifest.json", ('{"file":"source.pdf","file":"other.pdf"}').encode())
        result = self.resolve([source])
        self.assertEqual(result["sources"], [])
        self.assertIn("MANIFEST_UNREADABLE_OR_INVALID_JSON", {row["code"] for row in result["diagnostics"]})

    def test_manifest_byte_count_and_total_limits_prevent_unbounded_json_reading(self):
        source = self.file("source.pdf", b"needed")
        child = self.manifest("child.json", {"source.pdf": source})
        self.manifest("manifest.json", {"path": "child.json", "sha256": child})
        oversized = self.resolve([source], max_manifest_bytes=4)
        self.assertEqual(oversized["metrics"]["manifests_parsed"], 0)
        self.assertEqual(oversized["unresolved_hashes"], [source])
        bounded = self.resolve([source], max_manifests=1)
        self.assertEqual(bounded["metrics"]["manifests_parsed"], 1)
        self.assertIn("MANIFEST_COUNT_LIMIT_REACHED", {row["code"] for row in bounded["diagnostics"]})
        total = self.resolve([source], max_total_manifest_bytes=(self.root / "manifest.json").stat().st_size)
        self.assertIn("MANIFEST_TOTAL_BYTE_LIMIT_REACHED", {row["code"] for row in total["diagnostics"]})

    def test_no_repository_scan_or_unreferenced_file_hashing_and_stable_output(self):
        source = self.file("data/source.pdf", b"wanted")
        self.file("unreferenced-large-file", b"not a candidate")
        self.manifest("a.json", {"path": "data/source.pdf", "sha256": source})
        self.manifest("b.json", {"path": "data/source.pdf", "sha256": source})
        with patch.object(Path, "rglob", side_effect=AssertionError("repository scan forbidden")), \
                patch.object(Path, "glob", side_effect=AssertionError("repository scan forbidden")):
            one = self.resolve([source], ["b.json", "a.json"])
            two = self.resolve([source], ["a.json", "b.json"])
        self.assertEqual(one, two)
        self.assertEqual(one["metrics"]["files_hashed"], 3)
        self.assertFalse(one["source_inventory_mutated"])

    def test_hash_case_normalization_and_invalid_limits_or_hashes(self):
        source = self.file("source.pdf", b"source")
        self.manifest("manifest.json", {"source.pdf": source.upper()})
        self.assertEqual(self.resolve([source.upper()])["unresolved_hashes"], [])
        for kwargs in ({"max_manifest_bytes": True}, {"max_manifests": 0}, {"max_candidate_files": -1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.resolve([source], **kwargs)
        with self.assertRaises(ValueError):
            self.resolve(["not-a-SHA256"])


if __name__ == "__main__":
    unittest.main()
