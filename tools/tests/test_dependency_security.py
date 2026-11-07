"""Offline failure probes; no provider or vulnerability-service calls."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("audit_dependencies", Path(__file__).resolve().parents[1] / "audit_dependencies.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class DependencySecurity(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="daylight-dependency-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.output = self.root / "reports"
        for rel in (*AUDIT.TARGETS.values(), "tools/security/requirements.txt"):
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fictional-package==1.0\n")

    def test_rejects_remote_requirement_before_any_network(self):
        (self.root / AUDIT.TARGETS["research"]).write_text("-r https://example.invalid/private\n")
        with patch.object(AUDIT.subprocess, "run") as run:
            self.assertEqual(AUDIT.audit(self.root, self.output), 1)
            run.assert_not_called()

    def test_input_lock_drift_fails_before_network(self):
        (self.root / "tools/security/requirements.txt").write_text("fictional-package==2.0\n")
        with patch.object(AUDIT.subprocess, "run") as run:
            self.assertEqual(AUDIT.audit(self.root, self.output), 1)
            run.assert_not_called()

    def test_failed_or_missing_report_cannot_pass(self):
        for code in (0, 1, 2):
            with self.subTest(code=code), patch.object(AUDIT.subprocess, "run", return_value=subprocess.CompletedProcess([], code)):
                self.assertEqual(AUDIT.audit(self.root, self.output), 1)
                self.assertFalse(json.loads((self.output / "summary.json").read_text())["passed"])

    def test_previous_successful_report_cannot_mask_failure(self):
        self.output.mkdir()
        (self.output / "research.audit.json").write_text('{"dependencies": []}')
        with patch.object(AUDIT.subprocess, "run", side_effect=subprocess.TimeoutExpired("fictional", 240)):
            self.assertEqual(AUDIT.audit(self.root, self.output), 1)
        self.assertFalse((self.output / "research.audit.json").exists())


if __name__ == "__main__":
    unittest.main()
