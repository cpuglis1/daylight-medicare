#!/usr/bin/env python3
"""Reproduce actual-input cold/warm runs and one explicitly synthetic condition delta.

Only a new work/evidence directory is written. Sealed input records stay intact.
The final run restores the exact original manifest, so the latest snapshot is
the actual-input run rather than the synthetic mutation.
"""
import argparse
import copy
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from daylight_data.comparison_pipeline.common import canonical, file_hash, repository_path, safe_json
from daylight_data.comparison_pipeline.runner import read_records, run_batch
from daylight_data.comparison_pipeline.store import Store


def concise(summary):
    return {key: summary[key] for key in (
        "run_id", "config_sha256", "rule_fingerprint", "measured_wall_seconds", "processing_seconds_before_publication", "task_count", "component_count",
        "cache_metrics", "mechanical_outcomes", "queue_group_count", "offerings", "accepted_for_reference", "consumer_usable")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args()
    root = args.repository.resolve()
    if args.workspace.exists() or args.evidence.exists():
        parser.error("Use new workspace and evidence directories for an honest cold benchmark")
    args.evidence.resolve().relative_to(root)
    args.evidence.mkdir(parents=True)
    config = safe_json(repository_path(root, args.manifest).read_bytes())
    def timed_run(value):
        start = time.perf_counter()
        result = run_batch(root, args.workspace, value)
        result["measured_wall_seconds"] = time.perf_counter() - start
        return result

    cold = timed_run(config)
    print("cold", {k: v for k, v in concise(cold).items() if k != "offerings"}, flush=True)
    warm = timed_run(config)
    print("warm", {k: v for k, v in concise(warm).items() if k != "offerings"}, flush=True)
    modified = copy.deepcopy(config)
    first = modified["inputs"][0]
    records = read_records(repository_path(root, first["path"]))
    record = records[0]
    component = record["components"][0] if record.get("artifact_type") == "r9_component_bundle" else record
    component["carrier"]["conditions"]["qualification"]["assertion"] += (
        " [SYNTHETIC ENGINEERING MUTATION: condition changed, same amount; not a source assertion.]")
    delta_input = args.evidence / "SYNTHETIC-condition-change-input.json"
    delta_input.write_bytes(canonical(records))
    first["path"], first["sha256"] = str(delta_input.resolve().relative_to(root)), file_hash(delta_input)
    modified["title"] = "SYNTHETIC engineering condition mutation; no source or release authority"
    delta = timed_run(modified)
    print("synthetic_delta", {k: v for k, v in concise(delta).items() if k != "offerings"}, flush=True)
    restored = timed_run(config)
    store = Store(args.workspace / "comparisons.sqlite3")
    try:
        before = time.perf_counter()
        query_offering = config["inputs"][0]["offering_id"]
        rows = store.results(restored["run_id"], offering_id=query_offering, limit=20)
        query_seconds = time.perf_counter() - before
        report = {"schema": "daylight-comparison-benchmark/1", "manifest": args.manifest,
            "manifest_sha256": file_hash(repository_path(root, args.manifest)),
            "cold": concise(cold), "warm": concise(warm), "synthetic_delta": concise(delta),
            "restored_actual_inputs": concise(restored), "query_20_rows_seconds": query_seconds,
            "query_row_count": len(rows), "query_offering_id": query_offering,
            "inventory_cold": cold["inventory"], "inventory_warm": warm["inventory"],
            "synthetic_delta_detail": delta["delta"], "measures_human_review_time": False,
            "claims_future_plan_end_to_end_latency": False, "accepted_for_reference": False, "consumer_usable": False}
    finally:
        store.close()
    (args.evidence / "benchmark.json").write_bytes(canonical(report) + b"\n")
    print("evidence", args.evidence / "benchmark.json", flush=True)


if __name__ == "__main__":
    main()
