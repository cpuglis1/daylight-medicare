"""Exercise only fictional temporary Git repositories; never stage Daylight work."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("baseline_checks", HERE / "baseline_checks.py")
MODULE = importlib.util.module_from_spec(SPEC)
with patch.object(sys, "path", [str(HERE), *sys.path]):
    SPEC.loader.exec_module(MODULE)
POLICY = json.loads((HERE.parent / MODULE.DEFAULT_POLICY).read_text())
POLICY["code_names"] = list(set(POLICY["code_names"] + ["CODEOWNERS"]))


class BaselineChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="daylight-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Fictional Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.file(MODULE.DEFAULT_POLICY, json.dumps(POLICY))
        self.file(MODULE.DEFAULT_OWNERS, json.dumps(self.registry()))
        self.file(".github/CODEOWNERS", "* @fictional-owner\n")

    def git(self, *args, data=None):
        result = subprocess.run(["git", "-C", str(self.root), *args], input=data,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return result.stdout

    def file(self, path, content):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content if isinstance(content, bytes) else content.encode())
        self.git("add", "-f", "--", path)
        return target

    def commit(self):
        self.git("commit", "-qm", "Fictional fixture")
        return self.git("rev-parse", "HEAD").decode().strip()

    def run_check(self, **kwargs):
        return MODULE.check(self.root, **({"staged": True} | kwargs))

    @staticmethod
    def ids(result):
        return {item["check"] for item in result["findings"]}

    def test_clean_staged_snapshot_passes_without_claiming_publication(self):
        self.file("tools/example.py", "answer = 42\n")
        result = self.run_check()
        self.assertTrue(result["passed"])
        self.assertEqual(result["scope"], "full_snapshot")
        self.assertFalse(result["git_modified"])
        self.assertFalse(result["safe_to_publish"])

    def test_reads_staged_blob_not_working_file(self):
        path = self.file("tools/example.py", "answer = 42\n")
        path.write_text("bad python (\n")
        self.assertTrue(self.run_check()["passed"])
        self.git("add", "tools/example.py")
        path.write_text("answer = 42\n")
        self.assertIn("python_syntax", self.ids(self.run_check()))

    def test_commit_mode_ignores_index_and_worktree(self):
        self.file("tools/example.py", "answer = 42\n")
        commit = self.commit()
        self.file("tools/example.py", "bad python (\n")
        result = self.run_check(staged=False, revision=commit)
        self.assertTrue(result["passed"])

    def test_disallowed_blobs_never_read(self):
        names = [".env", "tools/.ENV.production", "alternatives/demo/var/profiles/customer.json",
                 "docs/data/evidence.json", "tools/private.key", "plans/source.pdf",
                 "infrastructure/database.sql", "tools/records.sqlite3", "unknown.bin"]
        for name in names:
            self.file(name, "DO_NOT_READ_PRIVATE_FIXTURE")
        objects = {entry["oid"] for name, entry in MODULE.snapshot(self.root, None).items() if name in names}
        original = MODULE.blob

        def protected(root, entry):
            self.assertNotIn(entry["oid"], objects)
            return original(root, entry)

        with patch.object(MODULE, "blob", side_effect=protected):
            result = self.run_check()
        self.assertEqual(len(result["findings"]), len(names))
        self.assertNotIn("DO_NOT_READ_PRIVATE_FIXTURE", json.dumps(result))

    def test_symlink_submodule_and_control_path_are_rejected(self):
        target = self.root / "tools/link.py"
        target.parent.mkdir(exist_ok=True)
        target.symlink_to("/not/a/real/file")
        self.git("add", "tools/link.py")
        self.file("tools/bad\nname.py", "pass\n")
        first = self.commit()
        self.git("update-index", "--add", "--cacheinfo", "160000," + first + ",tools/submodule")
        result = self.run_check(full_audit=True)
        self.assertTrue({"metadata:symlink", "metadata:submodule", "metadata:path_escape_or_invalid"} <= self.ids(result))

    def test_size_limit_checked_before_read(self):
        policy = dict(POLICY, max_candidate_bytes=2048)
        self.file(MODULE.DEFAULT_POLICY, json.dumps(policy))
        self.file("tools/large.py", b"#" * 2049)
        self.assertIn("metadata:over_size_limit", self.ids(self.run_check()))
        entry = {"mode": "100644", "type": "blob", "size": MODULE.MAX_BYTES + 1}
        self.assertEqual(MODULE.classify("tools/large.py", entry, POLICY), "over_size_limit")

    def test_private_names_casefold_and_canonical_boundaries(self):
        entry = {"mode": "100644", "type": "blob", "size": 1}
        for name in ["tools/VAR/a.py", "tools/config.LOCAL.json", ".ENV"]:
            self.assertEqual(MODULE.classify(name, entry, POLICY), "protected_local_path")
        for name in ["tools/../foo.py", "/tools/foo.py", "tools//foo.py", "tools/./foo.py", "tools\\foo.py"]:
            self.assertEqual(MODULE.classify(name, entry, POLICY), "path_escape_or_invalid")

    def test_incremental_enforces_changes_reports_inherited_debt(self):
        self.file("docs/data/historical.json", "DO_NOT_READ")
        base = self.commit()
        self.file("tools/new.py", "pass\n")
        result = self.run_check()
        self.assertTrue(result["passed"])
        self.assertEqual(result["scope"], "incremental")
        self.assertEqual(result["preexisting_metadata_debt_count"], 1)
        self.assertFalse(self.run_check(full_audit=True)["passed"])
        self.file("docs/data/historical.json", "CHANGED_PRIVATE")
        result = self.run_check()
        self.assertIn("metadata:archive_or_bulk_artifact", self.ids(result))
        self.assertEqual(result["base"], base)

    def test_deleting_bad_file_is_allowed(self):
        self.file(".env", "DO_NOT_READ")
        self.commit()
        self.git("rm", "-q", ".env")
        result = self.run_check()
        self.assertTrue(result["passed"])
        self.assertEqual(result["counts"]["deleted_paths"], 1)

    def test_ignore_rules_come_from_snapshot_not_unstaged_worktree(self):
        path = self.file(".gitignore", "tools/ignored.py\n")
        self.file("tools/ignored.py", "pass\n")
        path.write_text("")
        self.assertIn("metadata:git_ignored", self.ids(self.run_check()))
        self.git("add", ".gitignore")
        path.write_text("tools/ignored.py\n")
        self.assertTrue(self.run_check()["passed"])

    def test_nested_ignore_negation_works(self):
        self.file(".gitignore", "tools/blocked*\n")
        self.file("tools/.gitignore", "!blocked_allowed.py\n")
        self.file("tools/blocked_allowed.py", "pass\n")
        self.assertTrue(self.run_check()["passed"])

    def test_ignored_nested_ignore_is_not_opened_and_scope_is_blocked(self):
        self.file(".gitignore", "tools/.gitignore\n")
        self.file("tools/.gitignore", "DO_NOT_READ_NESTED_IGNORE")
        self.file("tools/source.py", "pass\n")
        private_oid = MODULE.snapshot(self.root, None)["tools/.gitignore"]["oid"]
        original = MODULE.blob

        def guarded(root, entry):
            self.assertNotEqual(entry["oid"], private_oid)
            return original(root, entry)

        with patch.object(MODULE, "blob", side_effect=guarded):
            result = self.run_check()
        self.assertIn("metadata:git_ignored", self.ids(result))
        self.assertIn("metadata:ignore_rules_unavailable", self.ids(result))

    def test_ignored_policy_is_never_read(self):
        self.file(".gitignore", MODULE.DEFAULT_POLICY + "\n")
        private_oid = MODULE.snapshot(self.root, None)[MODULE.DEFAULT_POLICY]["oid"]
        original = MODULE.blob

        def guarded(root, entry):
            self.assertNotEqual(entry["oid"], private_oid)
            return original(root, entry)

        with patch.object(MODULE, "blob", side_effect=guarded), self.assertRaises(ValueError):
            self.run_check()

    def test_symlink_root_ignore_fails_before_policy_read(self):
        (self.root / ".gitignore").symlink_to("/not/a/real/file")
        self.git("add", ".gitignore")
        with patch.object(MODULE, "blob", side_effect=AssertionError("No contents should be read")):
            with self.assertRaises(ValueError):
                self.run_check()

    def test_new_ignore_boundary_is_not_misreported_as_inherited_debt(self):
        self.file("tools/example.py", "pass\n")
        self.commit()
        self.file(".gitignore", "tools/example.py\n")
        result = self.run_check()
        self.assertIn("metadata:git_ignored", self.ids(result))
        self.assertEqual(result["preexisting_metadata_debt_count"], 0)

    def test_changed_existing_policy_forces_full_review_of_newly_eligible_files(self):
        token = "gh" + "p_" + "D" * 36
        self.file("docs/data/legacy.json", json.dumps({"value": token}))
        self.commit()
        changed_policy = dict(POLICY, archive_roots=[p for p in POLICY["archive_roots"] if p != "docs/data"])
        self.file(MODULE.DEFAULT_POLICY, json.dumps(changed_policy))
        result = self.run_check()
        self.assertTrue(result["policy_changed_requires_full_review"])
        self.assertEqual(result["scope"], "full_snapshot")
        self.assertIn("secret:github_token", self.ids(result))
        self.assertNotIn(token, json.dumps(result))

    def test_changed_policy_marks_new_restrictions_as_findings_not_inherited_debt(self):
        self.file("tools/example.py", "pass\n")
        self.commit()
        changed_policy = dict(POLICY, archive_roots=[*POLICY["archive_roots"], "tools"])
        self.file(MODULE.DEFAULT_POLICY, json.dumps(changed_policy))
        result = self.run_check()
        self.assertTrue(result["policy_changed_requires_full_review"])
        self.assertIn("metadata:archive_or_bulk_artifact", self.ids(result))
        self.assertEqual(result["preexisting_metadata_debt_count"], 0)

    def test_initial_policy_bootstrap_remains_incremental(self):
        self.git("rm", "-qf", MODULE.DEFAULT_POLICY)
        self.file("docs/data/legacy.json", "DO_NOT_READ_LEGACY")
        self.commit()
        self.file(MODULE.DEFAULT_POLICY, json.dumps(POLICY))
        result = self.run_check()
        self.assertFalse(result["policy_changed_requires_full_review"])
        self.assertEqual(result["scope"], "incremental")
        self.assertTrue(result["passed"])
        self.assertEqual(result["preexisting_metadata_debt_count"], 1)

    def test_secret_results_never_contain_matched_bytes(self):
        token = "gh" + "p_" + "A" * 36
        self.file("tools/example.py", 'value = "' + token + '"\n')
        result = self.run_check()
        self.assertIn("secret:github_token", self.ids(result))
        rendered = json.dumps(result)
        self.assertNotIn(token, rendered)
        self.assertEqual(result["findings"][0]["line"], 1)

    def test_credential_assignment_and_placeholder(self):
        content = 'password = "' + "this-is-a-realistic-secret" + '"\n'
        findings = MODULE.content_findings("tools/sample.py", content.encode())
        self.assertEqual(findings[0]["check"], "secret:credential_assignment")
        example = 'password = "' + "replace-with-your-secret" + '"\n'
        self.assertEqual(MODULE.content_findings("tools/sample.py", example.encode()), [])

    def test_json_duplicate_nonfinite_and_python_errors(self):
        self.file("tools/duplicate.json", '{"a":1,"a":2}')
        self.file("tools/nonfinite.json", '{"a":NaN}')
        self.file("tools/syntax.py", "def broken(\n")
        result = self.run_check()
        self.assertEqual(sum(f["check"] == "json_syntax" for f in result["findings"]), 2)
        self.assertIn("python_syntax", self.ids(result))

    def test_binary_text_and_encoding_fail_closed(self):
        self.file("tools/binary.py", b"pass\x00")
        self.file("tools/encoding.json", b"\xff")
        self.assertTrue({"binary_in_text_file", "text_encoding"} <= self.ids(self.run_check()))

    def add_engine(self, dependency=True):
        name = "tools/engine.py"
        data = b"answer = 42\n"
        if dependency:
            self.file(name, data)
        self.file("alternatives/advisor-first/engine-lock.json", json.dumps({name: hashlib.sha256(data).hexdigest()}))

    def test_missing_engine_dependency_fails_in_clean_clone(self):
        self.add_engine(dependency=False)
        self.assertIn("engine_dependency_missing", self.ids(self.run_check()))

    def test_engine_hash_checked_even_when_lock_unchanged(self):
        self.add_engine()
        self.assertTrue(self.run_check()["passed"])
        self.commit()
        self.file("tools/engine.py", "answer = 43\n")
        self.assertIn("engine_dependency_hash", self.ids(self.run_check()))

    def test_private_engine_dependency_is_not_opened(self):
        name = ".env"
        data = b"DO_NOT_READ"
        self.file(name, data)
        self.file("alternatives/advisor-first/engine-lock.json", json.dumps({name: hashlib.sha256(data).hexdigest()}))
        original = MODULE.blob
        private_oid = MODULE.snapshot(self.root, None)[name]["oid"]

        def guarded(root, entry):
            self.assertNotEqual(entry["oid"], private_oid)
            return original(root, entry)

        with patch.object(MODULE, "blob", side_effect=guarded):
            self.assertIn("engine_dependency_metadata_rejected", self.ids(self.run_check()))

    @staticmethod
    def registry():
        return {"schema": "daylight-owners/v1", "roles": [
            {"id": "repository_maintenance", "name": "Fictional Maintainer", "github": "fictional-owner",
             "status": "assigned", "scope": "Repository maintenance", "paths": ["*"]},
            {"id": "domain_review", "name": None, "github": None, "status": "unassigned",
             "scope": "Independent meaning review", "paths": []}]}

    def test_owners_vacancies_visible_without_granting_domain_authority(self):
        self.file(MODULE.DEFAULT_OWNERS, json.dumps(self.registry()))
        self.file(".github/CODEOWNERS", "* @fictional-owner\n")
        result = self.run_check()
        self.assertTrue(result["passed"])
        self.assertEqual(result["owners"]["unassigned_roles"], ["domain_review"])

    def test_owners_and_codeowners_must_agree(self):
        self.file(MODULE.DEFAULT_OWNERS, json.dumps(self.registry()))
        self.file(".github/CODEOWNERS", "* @different-owner\n")
        self.assertIn("codeowners_maintenance_mismatch", self.ids(self.run_check()))

    def test_codeowners_override_and_ownerless_rules_are_rejected(self):
        for extra in ["/** @different-owner\n", "/.github/\n"]:
            with self.subTest(extra=extra):
                self.file(".github/CODEOWNERS", "* @fictional-owner\n" + extra)
                self.assertIn("codeowners_maintenance_mismatch", self.ids(self.run_check()))

    def test_owner_controls_cannot_be_removed(self):
        self.commit()
        self.git("rm", "-q", MODULE.DEFAULT_OWNERS, ".github/CODEOWNERS")
        result = self.run_check()
        self.assertTrue({"owners_required", "codeowners_required", "required_control_removed"} <= self.ids(result))

    def test_codeowners_alone_cannot_be_removed(self):
        self.commit()
        self.git("rm", "-q", ".github/CODEOWNERS")
        self.assertIn("codeowners_required", self.ids(self.run_check()))

    def test_engine_lock_cannot_be_removed(self):
        self.add_engine()
        self.commit()
        self.git("rm", "-q", "alternatives/advisor-first/engine-lock.json")
        self.assertIn("required_control_removed", self.ids(self.run_check()))

    def test_history_rejects_secret_removed_before_final_snapshot(self):
        base = self.commit()
        token = "gh" + "p_" + "B" * 36
        self.file("tools/transient.py", 'value = "' + token + '"\n')
        introduced = self.commit()
        self.git("rm", "-q", "tools/transient.py")
        head = self.commit()
        result = self.run_check(staged=False, revision=head, base=base)
        self.assertIn("secret:github_token", self.ids(result))
        self.assertNotIn(token, json.dumps(result))
        self.assertEqual(result["history"]["commits_checked"], 2)
        self.assertEqual(result["findings"][0]["commit"], introduced)

    def test_history_rejects_deleted_private_file_without_reading(self):
        base = self.commit()
        self.file(".env", "NEVER_READ_HISTORY_PRIVATE")
        private_oid = MODULE.snapshot(self.root, None)[".env"]["oid"]
        self.commit()
        self.git("rm", "-q", ".env")
        head = self.commit()
        original = MODULE.blob

        def guarded(root, entry):
            self.assertNotEqual(entry["oid"], private_oid)
            return original(root, entry)

        with patch.object(MODULE, "blob", side_effect=guarded):
            result = self.run_check(staged=False, revision=head, base=base)
        self.assertIn("history_metadata:protected_local_path", self.ids(result))

    def test_history_unchanged_legacy_private_file_stays_unread_debt(self):
        self.file(".env", "NEVER_READ_LEGACY_PRIVATE")
        base = self.commit()
        self.file("tools/okay.py", "pass\n")
        head = self.commit()
        result = self.run_check(staged=False, revision=head, base=base)
        self.assertTrue(result["passed"])
        self.assertEqual(result["preexisting_metadata_debt_count"], 1)

    def test_missing_dependency_never_echoes_untrusted_lock_key(self):
        token = "gh" + "p_" + "C" * 36
        self.file("alternatives/advisor-first/engine-lock.json", json.dumps({token: "a" * 64}))
        result = self.run_check()
        self.assertIn("engine_dependency_missing", self.ids(result))
        self.assertNotIn(token, json.dumps(result))

    def test_missing_duplicate_or_unassigned_maintenance_fails(self):
        for kind in ["missing", "duplicate", "unassigned"]:
            registry = self.registry()
            if kind == "missing":
                registry["roles"].pop(0)
            elif kind == "duplicate":
                registry["roles"].append(registry["roles"][0])
            else:
                registry["roles"][0].update(status="unassigned", name=None, github=None)
            with self.subTest(kind=kind):
                self.file(MODULE.DEFAULT_OWNERS, json.dumps(registry))
                self.assertFalse(self.run_check()["passed"])

    def test_unmerged_index_fails(self):
        oid = self.git("hash-object", "-w", "--stdin", data=b"pass\n").strip()
        self.git("update-index", "--index-info", data=b"100644 " + oid + b" 1\ttools/conflict.py\n")
        with self.assertRaises(ValueError):
            self.run_check()

    def test_cli_missing_policy_has_redacted_error(self):
        self.git("rm", "-qf", MODULE.DEFAULT_POLICY)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = MODULE.main(["--root", str(self.root), "--staged"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())["error"], "configuration_or_git_error")


if __name__ == "__main__":
    unittest.main()
