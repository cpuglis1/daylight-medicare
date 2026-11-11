#!/usr/bin/env python3
"""Read-only metadata inventory and selected-path publication preflight.

Never reads selected file contents, stages files, modifies Git, or uploads data.
An eligible candidate still requires content, privacy, rights and history review.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess


MAX_BYTES = 50 * 1024 * 1024
PRIVATE_PARTS = {
    ".git", ".aws", ".ssh", ".codex", ".gemini", ".agents", ".venv", "venv",
    "node_modules", ".state", ".postgres18", ".build", "__pycache__",
    ".pytest_cache", "var", "tmp", "eval-private", "conversations",
    "demo-sessions", "local-checkpoints", "logs", "transcripts", "profiles",
    "ai-budget", "credentials",
}
PRIVATE_NAMES = {"config.local.json", "hook.cache.json", ".ds_store"}
BULK_SUFFIXES = {
    ".pdf", ".zip", ".gz", ".tgz", ".tar", ".bz2", ".xz", ".7z",
    ".sqlite", ".sqlite3", ".db", ".dump", ".backup", ".csv", ".tsv",
    ".jsonl", ".ndjson", ".parquet", ".xlsx", ".xls", ".log", ".xml",
    ".pem", ".key", ".p12", ".pfx", ".sqlite3-wal", ".sqlite3-shm",
    ".sqlite-wal", ".sqlite-shm", ".db-wal", ".db-shm",
}
CANDIDATES = {"code_review_candidate", "documentation_review_candidate"}


def git(root: Path, *arguments: str) -> bytes:
    result = subprocess.run(["git", "-C", str(root), *arguments],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise ValueError("Git metadata command failed; no publication decision made")
    return result.stdout


def under(name: str, roots: list[str]) -> bool:
    return any(name == root or name.startswith(root.rstrip("/") + "/") for root in roots)


def ignored_paths(root: Path, paths: list[str]) -> set[str]:
    """Check ignore rules in one process, including paths already in the index."""
    if not paths:
        return set()
    result = subprocess.run(["git", "-C", str(root), "check-ignore", "--no-index", "-z", "--stdin"],
                            input=b"\0".join(os.fsencode(path) for path in paths) + b"\0",
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode not in {0, 1}:
        raise ValueError("Batch ignore check failed; no publication decision made")
    return {os.fsdecode(path) for path in result.stdout.split(b"\0") if path}


def load_policy(path: Path) -> dict:
    policy = json.loads(path.read_text())
    if policy.get("schema") != "daylight-publication-policy/v1":
        raise ValueError("Unsupported publication policy")
    limit = policy.get("max_candidate_bytes")
    if type(limit) is not int or not 0 < limit <= MAX_BYTES:
        raise ValueError("Publication size bound must be between 1 byte and 50 MiB")
    for key in ("archive_roots", "code_roots", "documentation_roots", "code_extensions",
                "code_names", "root_names", "required_separate_reviews"):
        if not isinstance(policy.get(key), list) or not all(isinstance(x, str) for x in policy[key]):
            raise ValueError("Invalid publication policy list: " + key)
    return policy


def inspect_path(root: Path, name: str, policy: dict, *, ignored: bool = False) -> dict:
    """Classify using names and lstat only; reject symlinks including ancestors."""
    row = {"path": name, "category": "uncategorized", "bytes": 0, "reason": "unclassified"}
    relative = PurePosixPath(name)
    if (not name or name != relative.as_posix() or relative.is_absolute()
            or ".." in relative.parts or "\\" in name):
        return dict(row, reason="path_escape_or_invalid")
    target = root
    for part in relative.parts:
        target = target / part
        if target.is_symlink():
            return dict(row, category="private_local", reason="symlink")
    try:
        info = target.lstat()
    except OSError:
        return dict(row, reason="missing_or_unreadable")
    if not stat.S_ISREG(info.st_mode):
        return dict(row, reason="not_regular_file")
    row["bytes"] = info.st_size
    if ignored:
        return dict(row, category="private_local", reason="git_ignored")
    folded_parts = {part.casefold() for part in relative.parts}
    if (folded_parts & PRIVATE_PARTS or relative.name.casefold() in PRIVATE_NAMES
            or any(part == ".env" or part.startswith(".env.") and part != ".env.example"
                   for part in folded_parts)):
        return dict(row, category="private_local", reason="protected_local_path")
    if relative.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}:
        return dict(row, category="private_local", reason="credential_file_type")
    if info.st_size > policy["max_candidate_bytes"]:
        return dict(row, category="evidence_archive", reason="over_size_limit")
    if (under(name.casefold(), [path.casefold() for path in policy["archive_roots"]])
            or relative.suffix.lower() in BULK_SUFFIXES):
        return dict(row, category="evidence_archive", reason="archive_or_bulk_artifact")
    if relative.suffix.lower() == ".sql" and "migrations" not in relative.parts:
        return dict(row, category="evidence_archive", reason="sql_requires_migration_scope_review")
    if relative.suffix.lower() == ".md" and (len(relative.parts) == 1
            or under(name, policy["documentation_roots"] + policy["code_roots"])):
        return dict(row, category="documentation_review_candidate", reason="review_required")
    if (len(relative.parts) == 1 and name in policy["root_names"] or
            under(name, policy["code_roots"]) and
            (relative.suffix.lower() in policy["code_extensions"] or relative.name in policy["code_names"])):
        return dict(row, category="code_review_candidate", reason="review_required")
    if under(name, policy["documentation_roots"]) and relative.suffix.lower() == ".json":
        return dict(row, category="documentation_review_candidate", reason="review_required")
    return row


def inventory(root: Path, policy: dict) -> dict:
    groups = {
        "tracked": ("ls-files", "--cached", "-z"),
        "untracked": ("ls-files", "--others", "--exclude-standard", "-z"),
        "ignored": ("ls-files", "--others", "--ignored", "--exclude-standard", "-z"),
    }
    totals, by_category, by_directory = {}, defaultdict(lambda: {"files": 0, "bytes": 0}), {}
    listed = {group: [os.fsdecode(raw) for raw in git(root, *arguments).split(b"\0") if raw]
              for group, arguments in groups.items()}
    ignored = ignored_paths(root, listed["tracked"] + listed["untracked"])
    seen = set()
    for group, names in listed.items():
        counts = {"files": 0, "bytes": 0, "unavailable_or_nonregular": 0}
        dirs = defaultdict(lambda: {"files": 0, "bytes": 0})
        for name in names:
            if name in seen:
                continue
            seen.add(name)
            row = inspect_path(root, name, policy, ignored=group == "ignored" or name in ignored)
            counts["files"] += 1
            counts["bytes"] += row["bytes"]
            counts["unavailable_or_nonregular"] += row["reason"] in {"missing_or_unreadable", "not_regular_file", "symlink"}
            for bucket in (by_category[row["category"]], dirs[PurePosixPath(name).parts[0]]):
                bucket["files"] += 1
                bucket["bytes"] += row["bytes"]
        totals[group], by_directory[group] = counts, dict(dirs)
    return {"git_groups": totals, "categories": dict(by_category), "top_directories": by_directory,
            "byte_accounting": "Logical file sizes; no deduplication, physical allocation, .git objects or external runtime inventory."}


def check_paths(root: Path, policy: dict, paths: list[str]) -> dict:
    rows = []
    for name in paths:
        check = subprocess.run(["git", "-C", str(root), "check-ignore", "--no-index", "-q", "--", name],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        row = inspect_path(root, name, policy, ignored=check.returncode == 0)
        if check.returncode not in {0, 1}:
            row.update(category="uncategorized", reason="ignore_check_failed")
        rows.append(row)
    eligible = bool(rows) and all(row["category"] in CANDIDATES for row in rows)
    return {"selected_paths": rows, "eligible_for_content_review": eligible,
            "safe_to_publish": False, "required_separate_reviews": policy["required_separate_reviews"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--policy", type=Path, help="Defaults to ROOT/docs/project/publication-policy.json")
    parser.add_argument("--check-paths", type=Path, help="UTF-8 file with one repository-relative path per line")
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve(strict=True)
        if Path(os.fsdecode(git(root, "rev-parse", "--show-toplevel")).strip()).resolve() != root:
            raise ValueError("Root must be the exact repository working tree")
        policy = load_policy(args.policy or root / "docs/project/publication-policy.json")
        result = {"schema": "daylight-project-readiness/v1", "observed_at": datetime.now(timezone.utc).isoformat(),
                  "root": str(root), "destination": policy.get("destination"),
                  "destination_visibility": policy.get("destination_visibility"),
                  "metadata_only": True, "contents_reviewed": False, "git_modified": False}
        if args.check_paths:
            paths = [line for line in args.check_paths.read_text().splitlines() if line]
            result.update(check_paths(root, policy, paths))
        else:
            result.update(inventory(root, policy))
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if not args.check_paths or result["eligible_for_content_review"] else 1
    except (OSError, ValueError) as error:
        print(json.dumps({"error": str(error), "safe_to_publish": False, "git_modified": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
