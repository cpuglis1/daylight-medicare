#!/usr/bin/env python3
"""Offline Git baseline checks; passing is not publication or evidence acceptance.

Inspect staged blobs or a commit snapshot, never working customer/configuration
files. Metadata-rejected blobs are never opened. With --base (implicit HEAD for
--staged), enforce changed files and report inherited metadata debt separately.
Without a base, or with --full-audit, enforce the complete selected snapshot.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import tokenize

from project_readiness import BULK_SUFFIXES, MAX_BYTES, PRIVATE_NAMES, PRIVATE_PARTS, under


SCHEMA = "daylight-baseline-checks/v1"
DEFAULT_POLICY = "docs/project/publication-policy.json"
DEFAULT_OWNERS = "docs/project/owners.json"
REGULAR_MODES = {"100644", "100755"}
TEXT_SUFFIXES = {".py", ".json", ".md", ".txt", ".js", ".mjs", ".cjs", ".ts",
                 ".tsx", ".jsx", ".css", ".html", ".yaml", ".yml", ".toml",
                 ".sql", ".sh", ".lock", ".svg"}
TEXT_NAMES = {".gitignore", ".env.example", "CODEOWNERS", "Dockerfile", "Makefile",
              ".python-version", "pre-commit"}
SECRET_RULES = [
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----")),
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("openai_key", re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}\b")),
    ("url_credentials", re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|https?)://[^\s/:@]+:[^\s/@]{8,}@", re.I)),
]
ASSIGNMENT = re.compile(
    r'''(?ix)["']?\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password|passwd|secret[_-]?key)\b["']?\s*[:=]\s*["']([^"'\r\n]{12,})["']''')
PLACEHOLDER = re.compile(r"(?ix)^(?:\$\{[^}]+\}|<[^>]+>|(?:your|example|placeholder|fictional|dummy|test|fake|replace|change|redacted|not[_-]?a)[-_ ].*|[xX*]+)$")


def git(root: Path, *args: str, data: bytes | None = None) -> bytes:
    result = subprocess.run(["git", "-C", str(root), *args], input=data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if result.returncode:
        raise ValueError("Git operation failed; no contents or command output disclosed")
    return result.stdout


def canonical(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name and name == path.as_posix() and not path.is_absolute()
                and ".." not in path.parts and "\\" not in name
                and not any(ord(char) < 32 or ord(char) == 127 for char in name))


def classify(name: str, entry: dict, policy: dict) -> str | None:
    """Metadata only; same conservative boundaries as project_readiness.py."""
    if not canonical(name):
        return "path_escape_or_invalid"
    if entry["mode"] == "120000":
        return "symlink"
    if entry["mode"] == "160000":
        return "submodule"
    if entry["mode"] not in REGULAR_MODES or entry["type"] != "blob":
        return "not_regular_file"
    path = PurePosixPath(name)
    folded = {part.casefold() for part in path.parts}
    if (folded & PRIVATE_PARTS or path.name.casefold() in PRIVATE_NAMES
            or any(part == ".env" or part.startswith(".env.") and part != ".env.example" for part in folded)):
        return "protected_local_path"
    if path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}:
        return "credential_file_type"
    if entry["size"] > min(policy["max_candidate_bytes"], MAX_BYTES):
        return "over_size_limit"
    if under(name.casefold(), [p.casefold() for p in policy["archive_roots"]]) or path.suffix.lower() in BULK_SUFFIXES:
        return "archive_or_bulk_artifact"
    if path.suffix.lower() == ".sql" and "migrations" not in path.parts:
        return "sql_requires_migration_scope_review"
    if path.suffix.lower() == ".md" and (len(path.parts) == 1 or under(name, policy["documentation_roots"] + policy["code_roots"])):
        return None
    if (len(path.parts) == 1 and name in policy["root_names"] or
            under(name, policy["code_roots"]) and
            (path.suffix.lower() in policy["code_extensions"] or path.name in policy["code_names"])):
        return None
    if under(name, policy["documentation_roots"]) and path.suffix.lower() == ".json":
        return None
    return "uncategorized"


def strict_json(raw: bytes | str):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(_value):
        raise ValueError("nonfinite JSON number")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)


def validate_policy(policy: dict) -> None:
    if not isinstance(policy, dict) or policy.get("schema") != "daylight-publication-policy/v1":
        raise ValueError("Unsupported publication policy")
    limit = policy.get("max_candidate_bytes")
    if type(limit) is not int or not 0 < limit <= MAX_BYTES:
        raise ValueError("Publication size bound must be between 1 byte and 50 MiB")
    for key in ("archive_roots", "code_roots", "documentation_roots", "code_extensions",
                "code_names", "root_names", "required_separate_reviews"):
        if not isinstance(policy.get(key), list) or not all(isinstance(p, str) for p in policy[key]):
            raise ValueError("Invalid publication policy lists")


def revision_id(root: Path, ref: str) -> str:
    raw = git(root, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}").strip()
    if not re.fullmatch(rb"[0-9a-f]{40,64}", raw):
        raise ValueError("Invalid commit identifier")
    return raw.decode("ascii")


def snapshot(root: Path, revision: str | None) -> dict[str, dict]:
    entries = {}
    if revision is not None:
        for record in git(root, "ls-tree", "-rlz", revision).split(b"\0"):
            if not record:
                continue
            meta, raw_name = record.split(b"\t", 1)
            mode, kind, oid, size = meta.split()
            entries[os.fsdecode(raw_name)] = {"mode": mode.decode(), "type": kind.decode(),
                                             "oid": oid.decode(), "size": int(size) if size != b"-" else 0}
    else:
        for record in git(root, "ls-files", "--stage", "-z").split(b"\0"):
            if not record:
                continue
            meta, raw_name = record.split(b"\t", 1)
            mode, oid, stage = meta.split()
            if stage != b"0":
                raise ValueError("Unmerged index entries; resolve conflicts before checking")
            entries[os.fsdecode(raw_name)] = {"mode": mode.decode(), "oid": oid.decode()}
        blob_entries = [entry for entry in entries.values() if entry["mode"] != "160000"]
        object_ids = list(dict.fromkeys(entry["oid"] for entry in blob_entries))
        metadata = {}
        if object_ids:
            raw = git(root, "cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)",
                      data=("\n".join(object_ids) + "\n").encode())
            for line in raw.splitlines():
                oid, kind, size = line.split()
                metadata[oid.decode()] = (kind.decode(), int(size))
        for entry in entries.values():
            entry["type"], entry["size"] = ("commit", 0) if entry["mode"] == "160000" else metadata[entry["oid"]]
    return entries


def blob(root: Path, entry: dict) -> bytes:
    """Call only after metadata authorization; object IDs never include paths."""
    return git(root, "cat-file", "blob", entry["oid"])


def target_ignored(root: Path, entries: dict, allowed: set[str], candidates: set[str]) -> dict[str, str]:
    """Evaluate snapshot ignore files in an isolated repository, not the worktree."""
    if not candidates:
        return {}
    ignore_paths = set()
    unavailable_roots = set()
    for name in candidates:
        for parent in PurePosixPath(name).parents:
            path = str(parent / ".gitignore")
            if path in entries:
                if path in allowed:
                    ignore_paths.add(path)
                else:
                    unavailable_roots.add(str(parent))
    with tempfile.TemporaryDirectory(prefix="daylight-ignore-") as directory:
        isolated = Path(directory)
        git(isolated, "init", "-q", "--template=")

        def ignored_names(names):
            if not names:
                return set()
            result = subprocess.run(
                ["git", "-C", str(isolated), "-c", "core.excludesFile=/dev/null", "check-ignore", "--no-index", "-z", "--stdin"],
                input=b"\0".join(os.fsencode(name) for name in sorted(names)) + b"\0",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})
            if result.returncode not in {0, 1}:
                raise ValueError("Snapshot ignore evaluation failed")
            return {os.fsdecode(name) for name in result.stdout.split(b"\0") if name}

        blocked_roots = sorted(unavailable_roots)
        for name in sorted(ignore_paths, key=lambda path: (len(PurePosixPath(path).parts), path)):
            if "." in blocked_roots or under(name, blocked_roots) or name in ignored_names({name}):
                blocked_roots.append(str(PurePosixPath(name).parent))
                continue
            target = isolated / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(blob(root, entries[name]))
        result = {name: "ignore_rules_unavailable" for name in candidates
                  if "." in blocked_roots or under(name, blocked_roots)}
        result.update({name: "git_ignored" for name in ignored_names(candidates)})
        return result


def content_findings(name: str, raw: bytes) -> list[dict]:
    findings = []
    if b"\x00" in raw:
        return [{"path": name, "check": "binary_in_text_file"}]
    try:
        if PurePosixPath(name).suffix.lower() == ".py":
            encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
            text = raw.decode(encoding)
        else:
            text = raw.decode("utf-8-sig")
    except (UnicodeError, SyntaxError, LookupError):
        return [{"path": name, "check": "text_encoding"}]
    for rule, pattern in SECRET_RULES:
        for match in pattern.finditer(text):
            findings.append({"path": name, "check": "secret:" + rule,
                             "line": text.count("\n", 0, match.start()) + 1})
    for match in ASSIGNMENT.finditer(text):
        if not PLACEHOLDER.fullmatch(match.group(1)):
            findings.append({"path": name, "check": "secret:credential_assignment",
                             "line": text.count("\n", 0, match.start()) + 1})
    if name.lower().endswith(".py"):
        try:
            ast.parse(text, filename=name)
        except (SyntaxError, ValueError) as error:
            findings.append({"path": name, "check": "python_syntax", "line": getattr(error, "lineno", None)})
    if name.lower().endswith(".json"):
        try:
            strict_json(text)
        except (ValueError, RecursionError) as error:
            findings.append({"path": name, "check": "json_syntax", "line": getattr(error, "lineno", None)})
    return findings


def validate_owners(raw: bytes, codeowners: bytes | None) -> tuple[list[str], list[str]]:
    errors, vacancies = [], []
    try:
        registry = strict_json(raw)
    except (ValueError, UnicodeError, RecursionError):
        return ["owners_invalid_json"], vacancies
    if not isinstance(registry, dict) or registry.get("schema") != "daylight-owners/v1" or not isinstance(registry.get("roles"), list):
        return ["owners_schema"], vacancies
    roles = registry["roles"]
    identifiers = set()
    maintenance = None
    for role in roles:
        if not isinstance(role, dict) or not isinstance(role.get("id"), str) or not re.fullmatch(r"[a-z][a-z0-9_]*", role["id"]):
            errors.append("owners_role_id")
            continue
        role_id = role["id"]
        if role_id in identifiers:
            errors.append("owners_duplicate_role")
        identifiers.add(role_id)
        if not isinstance(role.get("scope"), str) or not role["scope"].strip():
            errors.append("owners_scope")
        paths = role.get("paths")
        if not isinstance(paths, list) or not all(isinstance(path, str) and canonical(path) for path in paths):
            errors.append("owners_paths")
        if role.get("status") == "assigned":
            if not isinstance(role.get("name"), str) or not role["name"].strip() or not isinstance(role.get("github"), str) or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", role["github"]):
                errors.append("owners_assignee")
        elif role.get("status") == "unassigned":
            if role.get("name") is not None or role.get("github") is not None:
                errors.append("owners_unassigned_identity")
            vacancies.append(role_id)
        else:
            errors.append("owners_status")
        if role_id == "repository_maintenance":
            maintenance = role
    if (maintenance is None or maintenance.get("status") != "assigned"
            or not isinstance(maintenance.get("paths"), list) or "*" not in maintenance["paths"]):
        errors.append("owners_maintenance_required")
    if codeowners is not None and maintenance and isinstance(maintenance.get("github"), str):
        try:
            lines = [line.split("#", 1)[0].split() for line in codeowners.decode("utf-8").splitlines()]
            rules = [line for line in lines if line]
            expected = "@" + maintenance["github"]
            if rules != [["*", expected]]:
                errors.append("codeowners_maintenance_mismatch")
        except UnicodeError:
            errors.append("codeowners_encoding")
    return sorted(set(errors)), sorted(vacancies)


def check(root: Path, *, staged: bool = False, revision: str = "HEAD", base: str | None = None,
          full_audit: bool = False, policy_path: str = DEFAULT_POLICY,
          owners_path: str = DEFAULT_OWNERS) -> dict:
    selected_revision = None if staged else revision_id(root, revision)
    entries = snapshot(root, selected_revision)
    # Bootstrap only this known, bounded, regular JSON policy object. No arbitrary
    # CLI path can turn the policy loader into a private-file content reader.
    if policy_path != DEFAULT_POLICY:
        raise ValueError("Policy must use the canonical reviewed repository path")
    policy_entry = entries.get(policy_path)
    if not policy_entry or policy_entry["mode"] not in REGULAR_MODES or policy_entry["type"] != "blob" or policy_entry["size"] > 1024 * 1024:
        raise ValueError("Canonical policy absent or unsafe in selected Git snapshot")
    bootstrap = {"max_candidate_bytes": 1024 * 1024, "archive_roots": [], "code_roots": [],
                 "documentation_roots": ["docs/project"], "code_extensions": [],
                 "code_names": [], "root_names": [".gitignore"]}
    bootstrap_allowed = {name for name, entry in entries.items() if classify(name, entry, bootstrap) is None}
    if policy_path in target_ignored(root, entries, bootstrap_allowed, {policy_path}):
        raise ValueError("Canonical policy excluded by snapshot ignore boundaries")
    policy = strict_json(blob(root, policy_entry))
    validate_policy(policy)
    if owners_path != DEFAULT_OWNERS:
        raise ValueError("Owners must use the canonical reviewed repository path")
    if base is None and staged and not full_audit:
        try:
            base = revision_id(root, "HEAD")
        except ValueError:
            if git(root, "rev-parse", "--is-inside-work-tree").strip() != b"true":
                raise
    parent = snapshot(root, revision_id(root, base)) if base else {}
    parent_policy = parent.get(policy_path)
    policy_changed_requires_full_review = bool(parent_policy and
        (policy_entry["oid"] != parent_policy["oid"] or policy_entry["mode"] != parent_policy["mode"]))
    incremental = bool(base) and not full_audit and not policy_changed_requires_full_review
    selected = {name for name, entry in entries.items()
                if not incremental or name not in parent or entry["oid"] != parent[name]["oid"] or entry["mode"] != parent[name]["mode"]}
    metadata = {name: classify(name, entry, policy) for name, entry in entries.items()}
    allowed = {name for name, reason in metadata.items() if reason is None}
    ignored = target_ignored(root, entries, allowed, allowed)
    metadata.update(ignored)
    allowed -= ignored.keys()
    parent_metadata = {name: classify(name, entry, policy) for name, entry in parent.items()}
    if parent:
        parent_allowed = {name for name, reason in parent_metadata.items() if reason is None}
        parent_metadata.update(target_ignored(root, parent, parent_allowed, parent_allowed))
        if incremental:
            # A changed ignore rule can change publication eligibility without
            # changing the affected blob. That is a new review obligation too.
            selected.update(name for name in entries
                            if name in parent_metadata and metadata[name] != parent_metadata[name])
    findings = [{"path": name, "check": "metadata:" + metadata[name]}
                for name in sorted(selected) if metadata[name] is not None]
    inherited = [{"path": name, "check": "metadata:" + reason}
                 for name, reason in sorted(metadata.items()) if reason is not None and name not in selected]
    scanned = set()
    checked_locks = 0
    read_cache = {}

    def read(name):
        if name not in allowed:
            raise ValueError("Attempt to read a metadata-rejected blob blocked")
        if name not in read_cache:
            read_cache[name] = blob(root, entries[name])
        return read_cache[name]

    def scan(name):
        path = PurePosixPath(name)
        if name not in scanned and (path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_NAMES):
            findings.extend(content_findings(name, read(name)))
            scanned.add(name)

    for name in sorted(selected & allowed):
        scan(name)
    for name in sorted(allowed):
        if PurePosixPath(name).name != "engine-lock.json":
            continue
        checked_locks += 1
        scan(name)
        try:
            lock = strict_json(read(name))
        except (ValueError, UnicodeError, RecursionError):
            findings.append({"path": name, "check": "engine_lock_schema"})
            continue
        if not isinstance(lock, dict) or not lock:
            findings.append({"path": name, "check": "engine_lock_schema"})
            continue
        for index, (dependency, digest) in enumerate(lock.items(), 1):
            if not isinstance(dependency, str) or not canonical(dependency) or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
                findings.append({"path": name, "check": "engine_lock_entry"})
            elif dependency not in entries:
                findings.append({"path": name, "check": "engine_dependency_missing", "entry": index})
            elif dependency not in allowed:
                findings.append({"path": dependency, "check": "engine_dependency_metadata_rejected"})
            else:
                scan(dependency)
                if hashlib.sha256(read(dependency)).hexdigest() != digest:
                    findings.append({"path": dependency, "check": "engine_dependency_hash"})
    owner_status, vacancies = "not_present", []
    codeowner_path = ".github/CODEOWNERS"
    if owners_path not in entries:
        findings.append({"path": owners_path, "check": "owners_required"})
    if codeowner_path not in entries:
        findings.append({"path": codeowner_path, "check": "codeowners_required"})
    for name in parent:
        if name not in entries and (name == owners_path or PurePosixPath(name).name == "engine-lock.json"):
            findings.append({"path": name, "check": "required_control_removed"})
    if owners_path in entries:
        owner_status = "rejected" if owners_path not in allowed else "checked"
        if owners_path not in allowed:
            findings.append({"path": owners_path, "check": "owners_metadata_rejected"})
        else:
            scan(owners_path)
            codeowners = None
            if codeowner_path in entries:
                if codeowner_path not in allowed:
                    findings.append({"path": codeowner_path, "check": "codeowners_metadata_rejected"})
                else:
                    scan(codeowner_path)
                    codeowners = read(codeowner_path)
            errors, vacancies = validate_owners(read(owners_path), codeowners)
            findings.extend({"path": owners_path, "check": error} for error in errors)

    history = {"commits_checked": 0, "changed_text_blobs_scanned": 0,
               "scope": "base_to_revision" if base and not staged else "not_checked"}
    if base and not staged:
        resolved_base = revision_id(root, base)
        git(root, "merge-base", "--is-ancestor", resolved_base, selected_revision)
        commits = git(root, "rev-list", "--reverse", resolved_base + ".." + selected_revision).decode().splitlines()
        checked = set()
        for commit in commits:
            historical = snapshot(root, commit)
            history["commits_checked"] += 1
            historical_metadata = {name: classify(name, entry, policy) for name, entry in historical.items()}
            historical_allowed = {name for name, reason in historical_metadata.items() if reason is None}
            historical_ignored = target_ignored(root, historical, historical_allowed, historical_allowed)
            historical_metadata.update(historical_ignored)
            historical_allowed -= historical_ignored.keys()
            for name, entry in sorted(historical.items()):
                if (name in parent and entry["oid"] == parent[name]["oid"]
                        and entry["mode"] == parent[name]["mode"]
                        and historical_metadata[name] == parent_metadata[name]):
                    continue
                identity = (name, entry["oid"], entry["mode"], historical_metadata[name])
                if identity in checked:
                    continue
                checked.add(identity)
                if historical_metadata[name] is not None:
                    findings.append({"path": name, "check": "history_metadata:" + historical_metadata[name], "commit": commit})
                    continue
                path = PurePosixPath(name)
                if path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_NAMES:
                    history["changed_text_blobs_scanned"] += 1
                    findings.extend({**finding, "commit": commit} for finding in content_findings(name, blob(root, entry)))
    unique_findings = [dict(items) for items in sorted({tuple(sorted(item.items())) for item in findings}, key=repr)]
    return {"schema": SCHEMA, "passed": not unique_findings, "git_modified": False,
            "safe_to_publish": False, "evidence_acceptance_changed": False,
            "policy_changed_requires_full_review": policy_changed_requires_full_review,
            "scope": "incremental" if incremental else "full_snapshot", "source": "index" if staged else selected_revision,
            "base": base, "counts": {"snapshot_paths": len(entries), "selected_paths": len(selected),
                                       "text_blobs_scanned": len(scanned), "engine_locks_checked": checked_locks,
                                       "deleted_paths": len(set(parent) - set(entries)), "findings": len(unique_findings)},
            "findings": unique_findings, "preexisting_metadata_debt": inherited,
            "preexisting_metadata_debt_count": len(inherited),
            "owners": {"status": owner_status, "unassigned_roles": vacancies}, "history": history,
            "limitations": ["Pattern scanning cannot prove absence of secrets or personal information.",
                            "Python and JSON syntax are checked; application behavior and other languages require their own tests.",
                            "Incremental checks do not certify inherited files or commits preceding the selected base.",
                            "Publication rights, independent evidence review and product release authority remain separate."]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--staged", action="store_true")
    group.add_argument("--revision", default="HEAD")
    parser.add_argument("--base")
    parser.add_argument("--full-audit", action="store_true")
    parser.add_argument("--owners", default=DEFAULT_OWNERS)
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve(strict=True)
        if Path(os.fsdecode(git(root, "rev-parse", "--show-toplevel")).strip()).resolve() != root:
            raise ValueError("Root must be the exact repository worktree")
        result = check(root, staged=args.staged, revision=args.revision, base=args.base,
                       full_audit=args.full_audit, owners_path=args.owners)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["passed"] else 1
    except (OSError, ValueError, RecursionError):
        # Never render parser exception strings, which can include source content.
        print(json.dumps({"schema": SCHEMA, "passed": False, "git_modified": False,
                          "error": "configuration_or_git_error", "safe_to_publish": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
