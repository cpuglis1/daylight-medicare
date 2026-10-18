"""Verify the actual portable query artifact without national archives or PDF tools."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cms_slice as cms
import demo_release as release
from demo_tools import DemoTools


class PortableReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="naples-release-test-")
        cls.root = Path(cls.temp.name)
        cls.patch = patch.object(release, "RELEASES", cls.root / "releases")
        cls.patch.start()
        cls.snapshot = release.build()
        cls.bundle = release.bundle(cls.snapshot)

    @classmethod
    def tearDownClass(cls):
        cls.patch.stop()
        cls.temp.cleanup()

    def test_snapshot_has_only_needed_public_query_inputs(self):
        manifest = release.verify(self.snapshot)
        self.assertTrue(manifest["source_receipt"]["upstream_full_source_verification"])
        self.assertEqual(manifest["source_receipt"]["domain_signoff"], "pending")
        self.assertEqual(manifest["source_receipt"]["drug_product_cases_checked"], 9)
        self.assertFalse(any("2027_20261008.zip" in p for p in manifest["files_sha256"]))
        self.assertLess(sum(p.stat().st_size for p in self.snapshot.rglob("*") if p.is_file()), 40_000_000)

    def test_frozen_query_preserves_real_source_facts(self):
        tools = DemoTools(release=self.snapshot)
        result = tools.drug_evidence("1551300", ["H5434-002-000-2027"], "1609197854")
        self.assertEqual(result["results"][0]["products"][0]["prior_authorization"], "Y")
        self.assertEqual(result["results"][0]["pharmacy"]["status"], "listed_in_pinned_network")
        self.assertEqual(len(tools.provider_evidence("NCH")["facts"]), 4)

    def test_changed_snapshot_data_is_rejected(self):
        copy = self.root / "changed-snapshot"
        shutil.copytree(self.snapshot, copy)
        path = copy / "catalog.json"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(cms.SourceError, "release file changed"):
            release.verify(copy)

    def test_bundle_excludes_credentials_and_private_records(self):
        with tarfile.open(self.bundle) as archive:
            names = archive.getnames()
        self.assertFalse(any(".env" in n or "demo-sessions" in n or "raw/prescription" in n for n in names))
        self.assertTrue(all(not Path(n).is_absolute() and ".." not in Path(n).parts for n in names))

    def test_bundle_runs_without_workspace_sources_or_pdf_tools(self):
        directory = self.root / "isolated"
        directory.mkdir()
        with tarfile.open(self.bundle) as archive:
            archive.extractall(directory, filter="data")
        environment = {**os.environ, "PATH": "", "OPENAI_API_KEY": "", "OPENAI_MODEL": ""}
        for message in ["What changed at NCH for 2027?", "Find Trulicity"]:
            run = subprocess.run([sys.executable, "scripts/demo.py", "ask", message, "--release", "snapshot"],
                                 cwd=directory, env=environment, capture_output=True, text=True, timeout=20)
            self.assertEqual(run.returncode, 0, run.stderr)
            response = json.loads(run.stdout)
            self.assertTrue(response["facts"])
            self.assertFalse(response["personal_recommendation"])
        self.assertFalse((directory / "data-sources/raw/prescription").exists())

    def test_same_code_data_release_can_be_selected_and_rolled_back(self):
        newer = release.build()
        self.assertNotEqual(newer, self.snapshot)
        release.select(self.snapshot)
        self.assertEqual(release.resolve("current"), self.snapshot)
        release.select(newer)
        self.assertEqual(release.resolve("current"), newer)


if __name__ == "__main__":
    unittest.main()
