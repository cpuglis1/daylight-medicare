"""Fictional repositories prove installation preserves hooks and blocks secrets."""
from pathlib import Path
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("install_git_hooks", ROOT / "tools/install_git_hooks.py")
INSTALLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALLER)


class SecurityHook(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="daylight-hook-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.git("init", "-q", "--template=")
        for rel in (".githooks/pre-commit", "tools/baseline_checks.py", "tools/project_readiness.py",
                    "docs/project/publication-policy.json", "docs/project/owners.json", ".github/CODEOWNERS"):
            dest = self.root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, dest)

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], capture_output=True,
                              text=True, check=True).stdout.strip()

    def hook(self):
        return subprocess.run([str(self.root / ".githooks/pre-commit")], cwd=self.root,
                              env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True)

    def test_installs_idempotently_without_changing_index(self):
        self.git("add", ".")
        before = self.git("ls-files", "--stage")
        INSTALLER.install(self.root)
        INSTALLER.install(self.root)
        self.assertEqual(self.git("config", "--get", "core.hooksPath"), ".githooks")
        self.assertEqual(before, self.git("ls-files", "--stage"))
        self.assertEqual(self.hook().returncode, 0)

    def test_refuses_other_hooks_path(self):
        self.git("config", "core.hooksPath", "custom-hooks")
        with self.assertRaises(ValueError):
            INSTALLER.install(self.root)
        self.assertEqual(self.git("config", "--get", "core.hooksPath"), "custom-hooks")

    def test_preserves_existing_executable_hook(self):
        target = self.root / ".git/hooks/pre-push"
        target.parent.mkdir(exist_ok=True)
        target.write_text("#!/bin/sh\nexit 0\n")
        target.chmod(0o755)
        with self.assertRaises(ValueError):
            INSTALLER.install(self.root)
        self.assertEqual(target.read_text(), "#!/bin/sh\nexit 0\n")

    def test_staged_secret_is_blocked_even_when_working_copy_is_clean(self):
        # Split construction so this fixture contains no literal scanner canary.
        token = "gh" + "p_" + "F" * 36
        target = self.root / "tools/fictional.py"
        target.write_text('value = "' + token + '"\n')
        self.git("add", ".")
        target.write_text('value = "redacted-example"\n')
        INSTALLER.install(self.root)
        result = self.hook()
        self.assertEqual(result.returncode, 1)
        self.assertIn("secret:github_token", result.stdout)
        self.assertNotIn(token, result.stdout + result.stderr)

    def test_missing_snapshot_policy_fails_closed(self):
        self.git("add", "tools")
        INSTALLER.install(self.root)
        result = self.hook()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["error"], "configuration_or_git_error")


if __name__ == "__main__":
    unittest.main()
