"""Fictional temporary repositories only; never stage real Daylight files."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("project_readiness", HERE / "project_readiness.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
POLICY = MODULE.load_policy(HERE.parent / "docs/project/publication-policy.json")


class PublicationBoundaries(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def file(self, name, content="fictional"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def test_candidates_are_not_publication_approval(self):
        self.file("tools/example.py")
        result = MODULE.check_paths(self.root, POLICY, ["tools/example.py"])
        self.assertTrue(result["eligible_for_content_review"])
        self.assertFalse(result["safe_to_publish"])

    def test_private_nested_and_bulk_files_fail_closed(self):
        names = [".env", "alternatives/example/var/profiles/store", "infrastructure/example/.state/archive/object",
                 "docs/data/receipt.json", "docs/large.sqlite3", "tools/private.key", "unclassified.bin",
                 "infrastructure/database.sql", "alternatives/example/logs/diagnostics.json"]
        for name in names:
            self.file(name)
            with self.subTest(name=name):
                self.assertFalse(MODULE.check_paths(self.root, POLICY, [name])["eligible_for_content_review"])

    def test_ignored_even_when_tracked_is_blocked(self):
        self.file("tools/example.py")
        subprocess.run(["git", "-C", str(self.root), "add", "tools/example.py"], check=True)
        self.file(".gitignore", "tools/example.py\n")
        result = MODULE.check_paths(self.root, POLICY, ["tools/example.py"])
        self.assertEqual(result["selected_paths"][0]["reason"], "git_ignored")
        with patch.object(MODULE, "ignored_paths", wraps=MODULE.ignored_paths) as batch:
            inventory = MODULE.inventory(self.root, POLICY)
        self.assertEqual(batch.call_count, 1)
        self.assertEqual(inventory["git_groups"]["tracked"]["files"], 1)
        self.assertEqual(inventory["categories"]["private_local"]["files"], 1)
        self.assertEqual(inventory["categories"]["code_review_candidate"]["files"], 1)  # .gitignore only

    def test_noncanonical_paths_cannot_bypass_archive_roots(self):
        self.file("docs/data/a.json")
        for name in ["docs/./data/a.json", "docs//data/a.json", "./docs/data/a.json"]:
            with self.subTest(name=name):
                row = MODULE.inspect_path(self.root, name, POLICY)
                self.assertEqual(row["reason"], "path_escape_or_invalid")
                self.assertFalse(MODULE.check_paths(self.root, POLICY, [name])["eligible_for_content_review"])

    def test_casefolded_deny_paths_are_blocked_on_every_platform(self):
        names = ["docs/DATA/a.json", "tools/VAR/a.py", "tools/config.LOCAL.json", ".ENV"]
        for name in names:
            self.file(name)
            with self.subTest(name=name):
                self.assertFalse(MODULE.check_paths(self.root, POLICY, [name])["eligible_for_content_review"])
        mixed_policy = dict(POLICY, archive_roots=["DOCS/DATA"])
        self.assertEqual(MODULE.inspect_path(self.root, names[0], mixed_policy)["category"], "evidence_archive")

    def test_symlink_ancestors_and_escape_are_blocked(self):
        self.file("tools/real/example.py")
        (self.root / "tools/link").symlink_to(self.root / "tools/real", target_is_directory=True)
        for name in ["tools/link/example.py", "../outside.py", str(self.root / "tools/real/example.py")]:
            with self.subTest(name=name):
                self.assertFalse(MODULE.check_paths(self.root, POLICY, [name])["eligible_for_content_review"])

    def test_oversize_and_empty_selection_are_blocked(self):
        path = self.file("tools/large.py")
        with path.open("r+b") as stream:
            stream.truncate(MODULE.MAX_BYTES + 1)
        self.assertFalse(MODULE.check_paths(self.root, POLICY, ["tools/large.py"])["eligible_for_content_review"])
        self.assertFalse(MODULE.check_paths(self.root, POLICY, [])["eligible_for_content_review"])

    def test_inventory_metadata_does_not_include_contents(self):
        marker = "DO_NOT_PRINT_FICTIONAL_CONTENT"
        self.file("tools/example.py", marker)
        self.file(".gitignore", ".env\n")
        self.file(".env", marker)
        result = MODULE.inventory(self.root, POLICY)
        self.assertEqual(result["git_groups"]["untracked"]["files"], 2)
        self.assertEqual(result["git_groups"]["ignored"]["files"], 1)
        self.assertNotIn(marker, json.dumps(result))


if __name__ == "__main__":
    unittest.main()
