#!/usr/bin/env python3
"""Create a new local-only source snapshot for Paperclip, without private stores.

Uses the existing reviewed publication path manifest, with explicit code and
current-context additions. This is a development copy, not publication approval.
Never overwrites an existing workspace or alters the source repository.
"""
import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[2]
    destination = args.destination.expanduser().absolute()
    if destination.exists():
        parser.error("Destination already exists; create a new revision instead.")
    baseline_path = source / "docs/project/source-baseline.2026-11-02.json"
    baseline = json.loads(baseline_path.read_text())
    paths = {item["path"] for item in baseline["files"]}
    # Include current implementation additions, never runtime directories.
    for root in ("alternatives/advisor-first", "tools"):
        paths.update(str(p.relative_to(source)) for p in (source / root).glob("*.py"))
        paths.update(str(p.relative_to(source)) for p in (source / root / "tests").glob("*.py"))
        paths.update(str(p.relative_to(source)) for p in (source / root / "tests").glob("*.mjs"))
    paths.update(str(p.relative_to(source)) for p in (source / "tools/paperclip").glob("*.md"))
    paths.update(str(p.relative_to(source)) for p in (source / "docs/project").glob("*.md"))
    for root in (source / "docs/product").glob("recommendation-scope-2026-11-04-r*"):
        paths.update(str(p.relative_to(source)) for p in root.glob("*.md"))
    paths.add(".gitignore")
    paths.add("docs/project/source-baseline.2026-11-02.json")
    paths.add("docs/project/publication-policy.json")
    records = []
    for relative in sorted(paths):
        path = source / relative
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Missing/non-regular source: {relative}")
        if not path.resolve().is_relative_to(source):
            raise ValueError(f"Source escape: {relative}")
        if (path.name.startswith(".env") and path.name != ".env.example") or path.suffix in {".db", ".sqlite", ".sqlite3", ".pem", ".key"}:
            raise ValueError(f"Private/runtime file rejected: {relative}")
        content = path.read_bytes()
        if len(content) > 50 * 1024 * 1024:
            raise ValueError(f"Oversize source: {relative}")
        records.append({"path": relative, "bytes": len(content),
                        "sha256": hashlib.sha256(content).hexdigest()})
    destination.mkdir(parents=True)
    for record in records:
        target = destination / record["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / record["path"], target)
        if hashlib.sha256(target.read_bytes()).hexdigest() != record["sha256"]:
            raise RuntimeError(f"Source changed during copy: {record['path']}")
    manifest = {
        "schema": "daylight-paperclip-workspace/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source), "baseline_path_manifest": str(baseline_path),
        "scope": "Current bytes at selected code/docs paths; local development only.",
        "private_stores_included": False, "publication_approved": False,
        "files": records,
        "missing_material": "Full research corpus, raw evidence, guest stores, provider credentials and live service bindings are intentionally absent. Linked historical evidence may be unavailable."
    }
    (destination / "PAPERCLIP_WORKSPACE.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (destination / "CLAUDE.md").write_text("Read tools/paperclip/AGENT_INSTRUCTIONS.md and AGENTS.md before working.\n")
    print(json.dumps({"destination": str(destination), "files": len(records),
                      "bytes": sum(r["bytes"] for r in records)}, indent=2))


if __name__ == "__main__":
    main()
