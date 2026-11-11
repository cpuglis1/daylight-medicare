"""One reusable batch path for any exact offering and registered source adapter."""
from __future__ import annotations

import collections
import copy
import gzip
import hashlib
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from . import PIPELINE_VERSION
from .adapters import adapter_version, normalize_task, stable_task_id
from .common import digest, file_hash, quarantine_tree, repository_path, safe_json
from .engine import SUPPORTED, evaluate, load_engine, rule_fingerprint, select_mapping
from .inventory import ensure_inventory, originals_for_offering
from .planning import build_work_queue, compare_snapshots
from .reviews import assess_source_review, source_meaning_fingerprint
from .store import Store

MANIFEST_SCHEMA = "daylight-comparison-batch/1"
REVIEW_SCHEMA = "daylight-source-review-receipt/1"


def verify_binding(repository, entry):
    if not isinstance(entry, dict) or not {"path", "sha256"} <= entry.keys():
        raise ValueError("Every artifact requires a path and byte SHA256")
    path = repository_path(repository, entry["path"])
    actual = file_hash(path)
    if "member" in entry:
        member, size = entry["member"], entry.get("member_bytes")
        if (not isinstance(member, str) or not member or Path(member).is_absolute() or
                ".." in Path(member).parts or "\\" in member or
                not isinstance(size, int) or isinstance(size, bool) or not 0 <= size <= 256 * 1024 * 1024):
            raise ValueError("Archive member needs an exact safe name and bounded byte length")
        if actual != entry.get("archive_sha256"):
            raise ValueError(f"Archive byte binding changed: {entry['path']}")
        h, total = hashlib.sha256(), 0
        with zipfile.ZipFile(path) as archive:
            matches = [info for info in archive.infolist() if info.filename == member]
            if len(matches) != 1 or matches[0].is_dir() or matches[0].file_size != size:
                raise ValueError("Archive member is missing, duplicate or has changed size")
            with archive.open(matches[0]) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    total += len(block)
                    if total > size:
                        raise ValueError("Archive member exceeded its pinned byte length")
                    h.update(block)
        if total != size or h.hexdigest() != entry["sha256"]:
            raise ValueError("Archive member byte binding changed")
        return {"path": entry["path"], "sha256": h.hexdigest(), "role": entry.get("role", "source"),
                "member": member, "member_bytes": size, "archive_sha256": actual}
    if actual != entry["sha256"]:
        raise ValueError(f"Artifact byte binding changed: {entry['path']}")
    return {"path": entry["path"], "sha256": actual, "role": entry.get("role", "source")}


def read_records(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        if path.name.endswith((".jsonl", ".jsonl.gz")):
            return [safe_json(line, exact_decimals=True) for line in stream if line.strip()]
        payload = safe_json(stream.read(), exact_decimals=True)
    return payload if isinstance(payload, list) else [payload]


def raw_roots(raw):
    value = raw.get("original_ids", raw.get("inventory_root_ids", [])) if isinstance(raw, dict) else []
    if isinstance(raw, dict) and raw.get("artifact_type") == "r9_component_bundle":
        declared = value if isinstance(value, list) and all(isinstance(x, str) for x in value) else []
        components = raw.get("components", [])
        components = components if isinstance(components, list) else []
        value = sorted(set(declared) | {key for component in components if isinstance(component, dict)
                                      for key in raw_roots(component)})
    return value if isinstance(value, list) and all(isinstance(x, str) for x in value) else []


def source_dependencies(task, sources, declared_paths):
    wanted = set()
    for component in task["components"]:
        for side in ("cms", "carrier"):
            for evidence in (component.get(side) or {}).get("evidence", []):
                if evidence.get("source_sha256"):
                    wanted.add(evidence["source_sha256"])
    selected = [s for s in sources if s["sha256"] in wanted or s["path"] in declared_paths]
    missing = sorted(wanted - {s["sha256"] for s in selected})
    holds = [{"code": "unbound_source_bytes", "category": "source_dependency",
              "path": "/components", "source_dependencies": [{"sha256": value}]} for value in missing]
    if declared_paths - {s["path"] for s in selected}:
        raise ValueError("Declared task dependency is absent from verified sources")
    return sorted(selected, key=lambda s: (s["path"], s["sha256"])), holds


def review_state(task, receipts, bindings):
    return assess_source_review(task, receipts, bindings)


def validate_manifest(config):
    allowed = {"schema", "title", "offerings", "inputs", "sources", "mapping_registries", "source_reviews"}
    if not isinstance(config, dict) or config.get("schema") != MANIFEST_SCHEMA or set(config) - allowed:
        raise ValueError("Unsupported comparison batch manifest")
    offerings = config.get("offerings", [])
    if not offerings or len(offerings) != len(set(offerings)) or not all(isinstance(x, str) for x in offerings):
        raise ValueError("Manifest needs unique exact offering identities")
    if not isinstance(config.get("inputs"), list):
        raise ValueError("Manifest inputs must be a list")
    for entry in config["inputs"]:
        if entry.get("offering_id") not in offerings:
            raise ValueError("Input offering is outside the manifest scope")
        if set(entry) - {"path", "sha256", "offering_id", "dependency_paths"}:
            raise ValueError("Unknown input adapter configuration")
        if not isinstance(entry.get("dependency_paths", []), list):
            raise ValueError("dependency_paths must be a list")


def run_batch(repository: Path, workspace: Path, config: dict) -> dict:
    """Validate sources, replay changed tasks, and atomically publish a local snapshot.

    The manifest is a reviewed work selection, not a new benefit denominator.
    Missing candidates remain in the full canonical inventory accounting.
    """
    started = time.perf_counter()
    repository, workspace = repository.resolve(), workspace.resolve()
    validate_manifest(config)
    config = copy.deepcopy(config)
    workspace.mkdir(parents=True, exist_ok=True)
    inventory = ensure_inventory(repository, workspace / "inventory.sqlite3")
    originals = {}
    by_offering = {}
    for offering in config["offerings"]:
        rows = originals_for_offering(workspace / "inventory.sqlite3", offering)
        by_offering[offering] = rows
        originals.update({r["id"]: r for r in rows})
    entries = [*config["inputs"], *config.get("sources", []),
               *config.get("mapping_registries", []), *config.get("source_reviews", [])]
    verified = [verify_binding(repository, entry) for entry in entries]
    offset = len(config["inputs"])
    sources = verified[offset:offset + len(config.get("sources", []))]
    # Source bytes may be the same object under more than one declared role.
    for path, member in {(s["path"], s.get("member")) for s in verified}:
        if len({s["sha256"] for s in verified if s["path"] == path and s.get("member") == member}) != 1:
            raise ValueError("Conflicting dependency bindings")
    registries = {}
    for entry in config.get("mapping_registries", []):
        payload = safe_json(repository_path(repository, entry["path"]).read_bytes())
        if not isinstance(payload, dict) or set(payload) & registries.keys():
            raise ValueError("Invalid or duplicate mapping registry")
        registries.update(payload)
    receipts = []
    for entry in config.get("source_reviews", []):
        receipts.extend(read_records(repository_path(repository, entry["path"])))
    engine, rules = load_engine(repository), rule_fingerprint(repository)
    metrics = collections.Counter()
    results, seen = [], set()
    store = Store(workspace / "comparisons.sqlite3")
    try:
        previous_id = store.latest_run()
        # This transaction includes caches and publication. No half-run task index.
        with store.connection:
            for entry in config["inputs"]:
                name = entry["path"]
                parse_key = digest({"sha256": entry["sha256"], "parser": "strict-json-exact-decimals/1", "rules": rules,
                                    "format": "jsonl" if name.endswith((".jsonl", ".jsonl.gz")) else "json",
                                    "compression": "gzip" if name.endswith(".gz") else "none"})
                records = store.get("artifacts", parse_key)
                if records is None:
                    records = read_records(repository_path(repository, entry["path"]))
                    store.put("artifacts", parse_key, records)
                    metrics["input_artifacts_parsed"] += 1
                else:
                    metrics["input_artifacts_reused"] += 1
                for raw in records:
                    if not isinstance(raw, dict):
                        raise ValueError("Input artifact contains a non-object record")
                    raw_hash = digest(raw)
                    key = digest({"record": raw_hash, "offering": entry["offering_id"],
                                  "adapter": adapter_version(), "rules": rules})
                    task = store.get("normalized", key)
                    if task is None:
                        try:
                            task = normalize_task(raw, offering_id=entry["offering_id"])
                        except ValueError as exc:
                            identifier = raw.get("id") or "INVALID-" + raw_hash[:24]
                            task = {"task_id": stable_task_id(entry["offering_id"], str(identifier)),
                                    "source_record_id": str(identifier), "offering_id": entry["offering_id"],
                                    "original_ids": raw_roots(raw), "components": [],
                                    "adapter_id": "quarantine", "adapter_version": adapter_version(),
                                    "input_fingerprint": raw_hash, "raw_record": quarantine_tree(raw),
                                    "holds": [{"code": "adapter_rejected", "category": "normalization",
                                               "path": "/", "detail": str(exc), "source_dependencies": []}]}
                        store.put("normalized", key, task)
                        metrics["tasks_normalized"] += 1
                    else:
                        metrics["normalized_tasks_reused"] += 1
                    # Cached normalization is data, and never a source review receipt.
                    task = copy.deepcopy(task)
                    task.update(research_only=True, accepted_for_reference=False, consumer_usable=False)
                    identifier = task["task_id"]
                    if identifier in seen:
                        raise ValueError(f"Duplicate batch task identity: {identifier}")
                    seen.add(identifier)
                    if task["offering_id"] != entry["offering_id"]:
                        raise ValueError("Adapter changed offering identity")
                    roots = task["original_ids"]
                    if len(roots) != len(set(roots)) or any(
                            r not in originals or originals[r]["offering_id"] != task["offering_id"] for r in roots):
                        raise ValueError("Unknown, duplicate or cross-offering original dependency")
                    task["original_bindings"] = [{"id": r, "sha256": originals[r]["original_sha256"]} for r in sorted(roots)]
                    task["task_input_sha256"] = digest(task)
                    # Preserve adapter diagnostics, but the selected, reviewed
                    # mapping and current receipt are evaluated below. These
                    # four annotations cannot act as permanent mechanical holds.
                    task["adapter_holds"] = copy.deepcopy(task.get("holds", []))
                    annotations = {"comparison_not_complete", "stored_outcome_mismatch",
                                   "independent_review_required", "reference_acceptance_held"}
                    task["holds"] = [h for h in task.get("holds", []) if h.get("code") not in annotations]
                    dependencies, holds = source_dependencies(task, sources, set(entry.get("dependency_paths", [])))
                    task["source_dependencies"] = dependencies
                    task["holds"] = [*task.get("holds", []), *holds]
                    mappings = {c["id"]: select_mapping(c, registries, verified) for c in task["components"]}
                    selected_mappings = {k: value for k, value in mappings.items() if value[0] is not None}
                    mapping_receipts = {value[1]["review_receipt_sha256"] for value in selected_mappings.values()}
                    task["mapping_fingerprint"] = digest({"entries": selected_mappings,
                        "receipts": [v for v in verified if v["sha256"] in mapping_receipts]})
                    task["rule_fingerprint"] = rules
                    task["source_meaning_sha256"] = source_meaning_fingerprint(task)
                    state, review_hash, review_holds = review_state(task, receipts, config.get("source_reviews", []))
                    task["review_state"], task["review_fingerprint"] = state, review_hash
                    task["holds"].extend(review_holds)
                    task["evaluation_key"] = digest({"input": task["task_input_sha256"], "rules": rules,
                        "source_meaning": task["source_meaning_sha256"],
                        "sources": dependencies, "holds": task["holds"],
                        "mapping": task["mapping_fingerprint"], "review": review_hash})
                    actual = store.get("evaluations", task["evaluation_key"])
                    if actual is None:
                        actual = evaluate(engine, task, mappings)
                        store.put("evaluations", task["evaluation_key"], actual)
                        metrics["tasks_evaluated"] += 1
                        metrics["components_evaluated"] += len(actual)
                    else:
                        metrics["task_evaluations_reused"] += 1
                        metrics["component_evaluations_reused"] += len(actual)
                    task["mechanical_results"] = actual
                    task["holds"].extend({"code": "comparison_outcome", "category": "semantics",
                        "path": f"/components/{index}", "outcome": row["outcome"],
                        "differences": row.get("differences", [])} for index, row in enumerate(actual)
                        if row["outcome"] not in SUPPORTED)
                    supported = bool(actual) and all(r["outcome"] in SUPPORTED for r in actual)
                    if task["adapter_id"] == "quarantine":
                        task["status"] = "quarantined"
                    elif task["holds"] or not supported:
                        task["status"] = "comparison_held"
                    elif state == "source_reviewed":
                        task["status"] = "source_reviewed_components"
                    elif state == "held":
                        task["status"] = "review_held"
                    else:
                        task["status"] = "awaiting_source_review"
                    task["input_artifact"] = {"path": entry["path"], "sha256": entry["sha256"], "record_sha256": raw_hash}
                    results.append(task)
            # Detect source/rule mutation during a long run before publishing it.
            for entry in entries:
                verify_binding(repository, entry)
            if rule_fingerprint(repository) != rules:
                raise ValueError("Comparison rules changed during execution")
            results.sort(key=lambda r: r["task_id"])
            queue = build_work_queue(results)
            prior = store.results(previous_id) if previous_id else []
            delta = compare_snapshots(prior, results)
            scopes = {}
            for offering, rows in by_offering.items():
                selected = [r for r in results if r["offering_id"] == offering]
                covered = {key for r in selected for key in r["original_ids"]}
                scopes[offering] = {"required_originals": len(rows),
                    "required_claims": sum(r["kind"] == "claim" for r in rows),
                    "required_conditions": sum(r["kind"] == "condition" for r in rows),
                    "originals_with_candidate_inputs": len(covered),
                    "originals_without_candidate_inputs": len(rows) - len(covered),
                    "whole_originals_completed_by_pipeline": 0,
                    "task_status_counts": dict(collections.Counter(r["status"] for r in selected))}
            summary = {"schema": PIPELINE_VERSION, "run_id": uuid.uuid4().hex,
                "created_at": datetime.now(timezone.utc).isoformat(), "config_sha256": digest(config),
                "previous_run_id": previous_id, "rule_fingerprint": rules,
                "inventory": inventory, "offerings": scopes, "task_count": len(results),
                "component_count": sum(len(r["components"]) for r in results),
                "mechanical_outcomes": dict(collections.Counter(x["outcome"] for r in results for x in r["mechanical_results"])),
                "cache_metrics": dict(metrics), "queue_group_count": len(queue),
                "delta": delta, "source_bindings": verified,
                "processing_seconds_before_publication": round(time.perf_counter() - started, 6),
                "review_queue_counts": dict(collections.Counter(q["category"] for q in queue)),
                "research_only": True, "accepted_for_reference": False, "consumer_usable": False,
                "whole_original_completion_authority": False, "new_reference_acceptances": 0}
            store.put("queues", summary["run_id"], queue)
            store.publish(summary, results)
        return summary
    finally:
        store.close()
