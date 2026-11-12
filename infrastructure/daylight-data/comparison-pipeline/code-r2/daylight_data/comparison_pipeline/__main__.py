"""Local operator CLI. No credentials, model calls or network are required."""
from __future__ import annotations

import argparse
import gzip
import json
import tempfile
from pathlib import Path

from .common import canonical, file_hash, repository_path, safe_json
from .inventory import originals_for_offering
from .planning import compare_snapshots
from .runner import read_records, run_batch
from .store import Store


def export_snapshot(workspace, output, run_id=None):
    """Publish a reviewable export only into a new directory."""
    if output.exists():
        raise ValueError("Snapshot export destination already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    with StoreContext(workspace) as store:
        summary = store.summary(run_id)
        identifier = summary["run_id"]
        results = store.results(identifier)
        queue = store.get("queues", identifier)
        with tempfile.TemporaryDirectory(prefix="comparison-export-", dir=output.parent) as temporary:
            staging = Path(temporary) / "snapshot"
            staging.mkdir()
            for name, data in (("summary.json", summary), ("review-queue.json", queue)):
                (staging / name).write_bytes(canonical(data) + b"\n")
            with gzip.GzipFile(filename=str(staging / "tasks.jsonl.gz"), mode="wb", mtime=0) as stream:
                for result in results:
                    stream.write(canonical(result) + b"\n")
            covered = {key for result in results for key in result["original_ids"]}
            with gzip.GzipFile(filename=str(staging / "originals-without-inputs.jsonl.gz"), mode="wb", mtime=0) as stream:
                for offering in summary["offerings"]:
                    for original in originals_for_offering(workspace / "inventory.sqlite3", offering):
                        if original["id"] not in covered:
                            stream.write(canonical(original) + b"\n")
            (staging / "README.txt").write_text(
                "Research-only batch snapshot. Mechanical outcomes do not establish source correctness, "
                "whole-original completion, reference acceptance or consumer release.\n", encoding="utf-8")
            files = {path.name: {"sha256": file_hash(path), "bytes": path.stat().st_size}
                     for path in sorted(staging.iterdir())}
            (staging / "MANIFEST.json").write_bytes(canonical({
                "schema": "daylight-comparison-export/1", "run_id": identifier, "files": files,
                "rule_fingerprint": summary["rule_fingerprint"],
                "accepted_for_reference": False, "consumer_usable": False}) + b"\n")
            staging.rename(output)
    return {"run_id": identifier, "output": str(output.resolve()), "accepted_for_reference": False}


class StoreContext:
    def __init__(self, workspace):
        self.workspace = workspace

    def __enter__(self):
        if not (self.workspace / "comparisons.sqlite3").is_file():
            raise ValueError("Comparison workspace does not exist")
        self.store = Store(self.workspace / "comparisons.sqlite3")
        return self.store

    def __exit__(self, *_):
        self.store.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--manifest", required=True)
    run.add_argument("--workspace", type=Path, required=True)
    run.add_argument("--export", type=Path)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--spec", required=True)
    prepare.add_argument("--output", type=Path, required=True)
    sources = commands.add_parser("sources")
    sources.add_argument("--spec", required=True)
    sources.add_argument("--seed", action="append", required=True)
    sources.add_argument("--output", type=Path, required=True)
    for name in ("status", "tasks", "queue", "diff", "export"):
        sub = commands.add_parser(name)
        sub.add_argument("--workspace", type=Path, required=True)
        sub.add_argument("--run-id")
        if name in {"tasks", "status"}:
            sub.add_argument("--offering")
        if name in {"tasks", "queue"}:
            sub.add_argument("--limit", type=int, default=20)
        if name == "tasks":
            sub.add_argument("--status")
        if name == "diff":
            sub.add_argument("--before", required=True)
        if name == "export":
            sub.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "sources":
            from .source_catalog import resolve_source_bindings
            spec = safe_json(repository_path(args.repository, args.spec).read_bytes())
            wanted = {entry["sha256"] for entry in spec.get("sources", [])}

            def citations(value):
                if isinstance(value, dict):
                    for key, child in value.items():
                        if key == "source_sha256" and isinstance(child, str) and len(child) == 64:
                            wanted.add(child)
                        citations(child)
                elif isinstance(value, list):
                    for child in value:
                        citations(child)

            for entry in spec["catalogs"]:
                citations(read_records(repository_path(args.repository, entry["path"])))
            result = resolve_source_bindings(args.repository, wanted, args.seed)
            if args.output.exists():
                raise ValueError("Source resolution output already exists")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("xb") as stream:
                stream.write(canonical(result) + b"\n")
            value = {"output": str(args.output.resolve()), "sources": len(result["sources"]),
                     "unresolved_hashes": result["unresolved_hashes"], "metrics": result["metrics"],
                     "accepted_for_reference": False}
        elif args.command == "prepare":
            from .preparation import prepare_batch
            spec = safe_json(repository_path(args.repository, args.spec).read_bytes())
            value = prepare_batch(args.repository, spec, args.output)
        elif args.command == "run":
            config = safe_json(repository_path(args.repository, args.manifest).read_bytes())
            summary = run_batch(args.repository, args.workspace, config)
            value = {k: v for k, v in summary.items() if k not in {"delta", "source_bindings", "inventory"}}
            value["inventory_mode"] = summary["inventory"].get("mode")
            if args.export:
                value["export"] = export_snapshot(args.workspace, args.export, summary["run_id"])
        elif args.command == "export":
            value = export_snapshot(args.workspace, args.output, args.run_id)
        else:
            with StoreContext(args.workspace) as store:
                summary = store.summary(args.run_id)
                identifier = summary["run_id"]
                if args.command == "status":
                    value = {k: v for k, v in summary.items() if k not in {"delta", "source_bindings", "inventory"}}
                    if args.offering:
                        if args.offering not in summary["offerings"]:
                            raise ValueError("Offering is outside this completed run")
                        value["offerings"] = {args.offering: summary["offerings"][args.offering]}
                elif args.command == "tasks":
                    value = store.results(identifier, offering_id=args.offering, status=args.status, limit=args.limit)
                elif args.command == "queue":
                    if args.limit < 1:
                        raise ValueError("Queue limit must be positive")
                    value = store.get("queues", identifier)[:args.limit]
                else:
                    value = compare_snapshots(store.results(args.before), store.results(identifier))
        print(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False))
        return 0
    except (ValueError, OSError) as exc:
        parser.exit(2, f"comparison pipeline: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
