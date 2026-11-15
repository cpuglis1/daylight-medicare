#!/usr/bin/env python3
"""Pick local Daylight code files that GitHub's dev branch does not have yet.

The nightly sync (tools/nightly/run.sh) calls this twice:

  select  list new or locally changed files that differ from the base branch,
          after the publication filters below; writes candidates JSON.
  record  after PRs are opened, remember each pushed or deliberately excluded
          file's content hash so it is not offered again until it changes.

Only files that are untracked, modified or staged in the local checkout are
considered, so tracked files the local branch merely lags behind on are never
pushed back over newer dev content. Selection is not publication acceptance:
the pre-commit baseline checks and CI still decide.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import time

DEFAULT_MAX_BYTES = 5 * 1024 * 1024
# Code only: data, evidence captures and generated output stay local; they
# need a separate backup policy (owner decision, 2026-11-14).
EXCLUDED_ROOTS = ("docs/data", "plans", "infrastructure/daylight-data/.state",
                  "archive", "daylight_obsidian", "audit-evidence", "outputs",
                  "_to_delete")


def load_policy(repo: Path):
    sys.path.insert(0, str(repo / "tools"))
    try:
        from project_readiness import BULK_SUFFIXES, PRIVATE_NAMES, PRIVATE_PARTS
    except Exception:  # fall back to a conservative copy if the module moved
        PRIVATE_PARTS = {".git", ".aws", ".ssh", ".codex", ".gemini", ".agents", ".venv",
                         "venv", "node_modules", ".state", ".postgres18", ".build",
                         "__pycache__", ".pytest_cache", "var", "tmp", "eval-private",
                         "conversations", "demo-sessions", "local-checkpoints", "logs",
                         "transcripts", "profiles", "ai-budget", "credentials"}
        PRIVATE_NAMES = {"config.local.json", "hook.cache.json", ".ds_store"}
        BULK_SUFFIXES = {".pdf", ".zip", ".gz", ".csv", ".tsv", ".jsonl", ".parquet",
                         ".xlsx", ".db", ".sqlite", ".sqlite3", ".log", ".pem", ".key"}
    return set(PRIVATE_PARTS), {n.lower() for n in PRIVATE_NAMES}, set(BULK_SUFFIXES)


def git(repo: Path, *args: str, data: bytes | None = None) -> bytes:
    # Explicit --work-tree keeps this working even if core.bare is set.
    cmd = ["git", "--git-dir", str(repo / ".git"), "--work-tree", str(repo), *args]
    result = subprocess.run(cmd, input=data, cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if result.returncode:
        raise SystemExit(f"git {' '.join(args[:2])} failed: {result.stderr.decode()[:300]}")
    return result.stdout


def z(out: bytes) -> list[str]:
    return [p for p in out.decode("utf-8", "surrogateescape").split("\0") if p]


def under(name: str, roots) -> bool:
    return any(name == r or name.startswith(r + "/") for r in roots)


def load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        return {"schema": "daylight-nightly-state/v1", "files": {}}


def select(args) -> None:
    repo = Path(args.repo).resolve()
    private_parts, private_names, bulk = load_policy(repo)
    state = load_state(Path(args.state))["files"]

    paths = set(z(git(repo, "ls-files", "-o", "--exclude-standard", "-z")))
    paths |= set(z(git(repo, "ls-files", "-m", "-z")))
    paths |= set(z(git(repo, "diff", "--cached", "--name-only", "--diff-filter=AM", "-z", "HEAD")))

    skipped: dict[str, int] = {}
    def skip(reason: str) -> None:
        skipped[reason] = skipped.get(reason, 0) + 1

    kept: list[tuple[str, int, float]] = []
    for name in sorted(paths):
        pure = PurePosixPath(name)
        if under(name, EXCLUDED_ROOTS):
            skip("data_root"); continue
        if any(part in private_parts for part in pure.parts) or pure.name.lower() in private_names:
            skip("private_path"); continue
        if pure.suffix.lower() in bulk:
            skip("bulk_or_data_type"); continue
        full = repo / name
        try:
            st = os.lstat(full)
        except FileNotFoundError:
            skip("missing"); continue
        if not os.path.isfile(full) or os.path.islink(full):
            skip("not_regular_file"); continue
        if st.st_size > args.max_bytes:
            skip("too_large"); continue
        kept.append((name, st.st_size, st.st_mtime))

    hashes = z(git(repo, "hash-object", "--stdin-paths", data="\n".join(n for n, _, _ in kept).encode()).replace(b"\n", b"\0")) if kept else []
    base_sha = git(repo, "rev-parse", args.base).decode().strip()
    base_blobs = {}
    for entry in z(git(repo, "ls-tree", "-r", "-z", base_sha)):
        meta, path = entry.split("\t", 1)
        base_blobs[path] = meta.split()[2]

    # Latest commit time on the base branch for each path it touched.
    touched: dict[str, int] = {}
    stamp = 0
    for line in git(repo, "log", "--format=@%ct", "--name-only", base_sha).decode("utf-8", "surrogateescape").splitlines():
        if line.startswith("@"):
            stamp = int(line[1:])
        elif line and line not in touched:
            touched[line] = stamp

    candidates, dev_newer = [], []
    for (name, size, mtime), digest in zip(kept, hashes):
        base_blob = base_blobs.get(name)
        if base_blob == digest:
            skip("already_on_base"); continue
        previous = state.get(name)
        if previous and previous.get("hash") == digest:
            skip("already_handled"); continue
        conflict = False
        if base_blob:
            if previous and previous.get("hash") != base_blob:
                conflict = True  # base changed since we last pushed this file
            elif not previous and touched.get(name, 0) > mtime:
                dev_newer.append(name); skip("base_newer"); continue
        candidates.append({"path": name, "size": size, "hash": digest,
                           "kind": "update" if base_blob else "new", "conflict": conflict})

    deferred = max(0, len(candidates) - args.limit)
    out = {"schema": "daylight-nightly-candidates/v1", "repo": str(repo), "base": args.base,
           "base_sha": base_sha, "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "candidates": candidates[: args.limit], "deferred_to_next_run": deferred,
           "skipped": skipped, "base_newer_sample": dev_newer[:200]}
    Path(args.out).write_text(json.dumps(out, indent=1))
    print(f"{len(out['candidates'])} candidates, {deferred} deferred, skipped {skipped}")


def record(args) -> None:
    state_path = Path(args.state)
    state = load_state(state_path)
    candidates = {c["path"]: c for c in json.loads(Path(args.candidates).read_text())["candidates"]}
    manifest = json.loads(Path(args.manifest).read_text())
    pushed = set(json.loads(args.pushed_branches)) if args.pushed_branches else set()
    now = time.strftime("%Y-%m-%d")
    count = 0
    for pr in manifest.get("prs", []):
        if pr.get("branch") not in pushed:
            continue
        for path in pr.get("files", []):
            if path in candidates:
                state["files"][path] = {"hash": candidates[path]["hash"], "status": "pushed",
                                        "branch": pr["branch"], "date": now}
                count += 1
    for item in manifest.get("excluded", []):
        path = item.get("path")
        if path in candidates:
            state["files"][path] = {"hash": candidates[path]["hash"], "status": "excluded",
                                    "reason": item.get("reason", ""), "date": now}
            count += 1
    tmp = state_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1))
    tmp.replace(state_path)
    print(f"recorded {count} files")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("select")
    s.add_argument("--repo", required=True)
    s.add_argument("--base", default="origin/dev")
    s.add_argument("--state", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    s.add_argument("--limit", type=int, default=3000)
    r = sub.add_parser("record")
    r.add_argument("--state", required=True)
    r.add_argument("--candidates", required=True)
    r.add_argument("--manifest", required=True)
    r.add_argument("--pushed-branches", default="")
    args = parser.parse_args()
    select(args) if args.command == "select" else record(args)


if __name__ == "__main__":
    main()
