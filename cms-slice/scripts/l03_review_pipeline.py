"""Repeatable, research-only L03 preparation and comparison replay.

Consumes immutable exports; never writes to a database, app or source packet.
Source work batches and comparison dependency links are NOT completed claims.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
R9 = "docs/data/l03-ma-benefits-2026-10-25/semantic-inventory-r9"
OPEN = "docs/data/l03-ma-benefits-2026-11-02-whole-offering-r12/open-band-comparison-contract-r2"
DEFAULT_CONFIG = "docs/data/l03-review-pipeline-2026-11-03-r1/config.json"
SCHEMA = "l03-review-pipeline/1"
CMS_ADAPTERS = {
    "normalized_pbp_table": ["offering_id", "source_table", "record_ordinal", "service_category",
                             "fields", "source_condition_context", "context_tables"],
    "pbp_service_record": ["offering_id", "category_code", "service_name", "PBP_source",
                           "PBP_cost_sharing", "PBP_coverage_controls", "PBP_authorization_referral"],
}


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def repo_path(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Input outside repository: {relative}")
    return path


def read_json(root, relative):
    return json.loads(repo_path(root, relative).read_text())


def json_rows(path):
    with gzip.open(path, "rt") as stream:
        for index, line in enumerate(stream):
            yield index, json.loads(line)


def write_json(path, value):
    path.write_bytes(encoded(value) + b"\n")


def write_rows(path, rows):
    # Stable bytes across runs, including gzip headers.
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as stream:
            for row in rows:
                stream.write(encoded(row) + b"\n")


def check_bindings(root, bindings):
    for name, expected in sorted(bindings.items()):
        if file_hash(repo_path(root, name)) != expected:
            raise ValueError(f"Input changed; use an explicit new revision: {name}")


def load_inventory(root, config, selected):
    """Stream the full denominator once, retaining only selected full records."""
    frozen = read_json(root, f"{R9}/freeze.json")
    binding = read_json(root, f"{R9}/inventory-binding.json")
    # The source freeze, not this run's requested scope, determines the universe.
    for name in ("master-inventory.jsonl.gz", "inventory-binding.json",
                 "offering-inventory.json", "pilot-contract.json", "work-policies.json"):
        if config["bindings"].get(f"{R9}/{name}") != frozen["files_sha256"][name]:
            raise ValueError(f"Binding does not match r9 freeze: {name}")
    expected = {r["offering_id"]: r for r in read_json(root, f"{R9}/offering-inventory.json")}
    if not selected or len(set(selected)) != len(selected) or set(selected) - expected.keys():
        raise ValueError("Select unique exact offering IDs from the frozen universe")
    records, counts = {}, defaultdict(Counter)
    h = hashlib.sha256(b"[")
    previous, total = None, 0
    for _, row in json_rows(repo_path(root, f"{R9}/master-inventory.jsonl.gz")):
        key = row["id"]
        if previous is not None and key <= previous:
            raise ValueError("Duplicate or unsorted canonical identity")
        if row["offering_id"] not in expected or row["kind"] not in {"claim", "condition"}:
            raise ValueError("Unexpected offering/kind in frozen inventory")
        if row.get("accepted_for_reference") is not False:
            raise ValueError("New acceptance cannot be inherited")
        if total:
            h.update(b",")
        h.update(encoded(row))
        counts[row["offering_id"]][row["kind"]] += 1
        if row["offering_id"] in selected:
            records[key] = row
        previous, total = key, total + 1
    h.update(b"]")
    if h.hexdigest() != binding["inventory_digest"] or total != binding["required_record_count"]:
        raise ValueError("Complete canonical denominator changed")
    if h.hexdigest() != frozen["inventory_digest"] or total != frozen["required_total"]:
        raise ValueError("Inventory does not match freeze")
    for offering, row in expected.items():
        if dict(counts[offering]) != row["required"]:
            raise ValueError(f"Per-offering denominator changed: {offering}")
    return records, expected, binding


def source_side(row):
    basis = row["detail"].get("source_basis", "")
    if basis == "carrier_only_blind_to_CMS_expected_amounts":
        return "carrier"
    if basis in {"CMS_JSON", "CMS_narrative_field", "retained_normalized_source_amount"}:
        return "cms"
    return "unresolved"  # Includes missing predicates; never guess their source.


def work_batches(records, policies):
    batches = {}
    for key, row in sorted(records.items()):
        context = row["context"]
        # Routing only: no text normalization or cross-plan semantic equivalence.
        scope = {"offering_id": row["offering_id"], "side": source_side(row),
                 "subject": row["subject"], "network": context.get("network"),
                 "variant": context.get("variant"), "source_section": context.get("source_section")}
        batch_id = "WORK-" + digest(scope)[:24]
        batch = batches.setdefault(batch_id, {"id": batch_id, "scope": scope,
                  "inventory_ids": [], "state": "interpretation_required",
                  "semantic_equivalence_asserted": False, "accepted_for_reference": False})
        if batch["scope"] != scope:
            raise ValueError("Work-batch identity collision")
        batch["inventory_ids"].append(key)
        if row["work_policy_id"] not in policies:
            raise ValueError("Unknown pinned work policy")
    return sorted(batches.values(), key=lambda row: row["id"])


def load_engines(root):
    """Only named repository engines; no config-selected executable path."""
    def module(name, path):
        spec = importlib.util.spec_from_file_location(name, repo_path(root, path))
        result = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(result)
        return result
    base = module("_pipeline_r9_base", f"{R9}/code/l03_comparison_contract.py")
    # The sealed guard imports this exact name. Restore any caller's module.
    prior = sys.modules.get("l03_comparison_contract")
    sys.modules["l03_comparison_contract"] = base
    try:
        r9 = module("_pipeline_r9", f"{R9}/code/l03_r9_comparison.py")
    finally:
        if prior is None:
            sys.modules.pop("l03_comparison_contract", None)
        else:
            sys.modules["l03_comparison_contract"] = prior
    return {"r9": r9, "open_band_r2": module("_pipeline_open_band", f"{OPEN}/open_band_comparison.py")}


def engine_paths():
    return [f"{R9}/code/l03_comparison_contract.py", f"{R9}/code/l03_r9_comparison.py",
            f"{OPEN}/open_band_comparison.py", f"{OPEN}/comparison-record.schema.json",
            "cms-slice/scripts/l03_review_pipeline.py"]


def unknown_paths(value, path="$"):
    found = []
    if value is None:
        return [path]
    if isinstance(value, dict):
        if value.get("state") in {"unknown", "unresolved", "missing"}:
            found.append(path)
        for key, child in value.items():
            found.extend(unknown_paths(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(unknown_paths(child, f"{path}[{index}]"))
    return found


def replay_candidates(root, config, records):
    engines = load_engines(root)
    source_paths = (config.get("document_catalogs", []) + config.get("carrier_page_exports", [])
                    + [s["path"] for s in config.get("cms_exports", [])])
    if config.get("document_matrix"):
        source_paths.append(config["document_matrix"])
    source_signature = digest({name: config["bindings"][name] for name in source_paths})
    results, seen = [], set()
    for adapter in config["candidate_inputs"]:
        if adapter["engine"] not in engines:
            raise ValueError("Unknown comparison engine")
        if adapter.get("link_role") != "dependency_only":
            raise ValueError("This adapter cannot promote dependency links into completed originals")
        payload = read_json(root, adapter["path"])
        rows = payload if isinstance(payload, list) else [payload]
        for index, row in enumerate(rows):
            if row["id"] in seen:
                raise ValueError("Duplicate comparison identity")
            seen.add(row["id"])
            if row.get("accepted_for_reference") is not False:
                raise ValueError("Candidate cannot inherit acceptance")
            dependencies = row["inventory_root_ids"]
            if not dependencies or len(set(dependencies)) != len(dependencies):
                raise ValueError("Empty/duplicate original dependencies")
            if any(key not in records or records[key]["offering_id"] != adapter["offering_id"]
                   for key in dependencies):
                raise ValueError("Out-of-scope or wrong-offering dependency")
            # A known identity disagreement is a hard input error; unknown stays unknown.
            year, contract, plan, segment = adapter["offering_id"].split(":")
            for side in ("cms", "carrier"):
                identity = (row.get(side) or {}).get("identity", {})
                for key, expected in {"year": int(year), "contract": contract,
                                      "plan": plan, "segment": segment}.items():
                    if key in identity and identity[key] != expected:
                        raise ValueError("Candidate observation belongs to a different offering")
            engine = engines[adapter["engine"]]
            expected_identity = adapter.get("expected_identity")
            if expected_identity is not None:
                for key, expected in {"year": int(year), "contract": contract,
                                      "plan": plan, "segment": segment}.items():
                    if expected_identity.get(key) != expected:
                        raise ValueError("Wrong expected identity")
            result = engine.compare(row.get("cms"), row.get("carrier"), expected_identity=expected_identity)
            if result["outcome"] != row["outcome"]:
                raise ValueError(f"Frozen candidate outcome changed: {row['id']}")
            unknowns = {side: unknown_paths(row.get(side)) for side in ("cms", "carrier")}
            results.append({"id": row["id"], "offering_id": adapter["offering_id"],
                "input": {"path": adapter["path"], "array_index": index if isinstance(payload, list) else None,
                          "record_sha256": digest(row), "file_sha256": config["bindings"][adapter["path"]]},
                "engine": adapter["engine"], "engine_signature": digest({
                    name: config["bindings"][name] for name in engine_paths()}),
                "source_preparation_signature": source_signature,
                "dependency_ids": dependencies, "dependency_sha256": digest([
                    [key, digest(records[key])] for key in sorted(dependencies)]),
                "link_role": "dependency_only", "mechanical_result": result,
                "unknown_paths": unknowns, "originals_completed": 0,
                "interpretation_review_verified_by_pipeline": False,
                "accepted_for_reference": False})
    return sorted(results, key=lambda row: row["id"])


def envelope(path, index, record, **extra):
    return {"source_export": path, "source_row": index,
            "source_record_sha256": digest(record), "record": record, **extra}


def prepare_source_inputs(root, config, selected, output):
    """Separate source-native workspaces. No aligned expectations enter carrier input."""
    validate_source_adapters(config)
    matrix = {r["offering_id"]: r for r in read_json(root, config["document_matrix"])}
    catalogs = {}
    for name in config["document_catalogs"]:
        for row in read_json(root, name):
            catalogs.setdefault(row["sha256"], []).append(row)
    wanted, documents = defaultdict(list), []
    for offering in selected:
        for kind in ("SB", "EOC"):
            match = matrix[offering]["document_matches"][kind]
            sha = match.get("sha256")
            if not sha or sha not in catalogs:
                raise ValueError(f"Required carrier document not mapped: {offering}/{kind}")
            catalog = catalogs[sha][0]
            raw = Path(catalog["path"])
            # These retained paths are local, never followed as network URLs.
            if not raw.resolve().is_relative_to(root.resolve()) or file_hash(raw) != sha:
                raise ValueError("Carrier PDF bytes do not match retained identity")
            wanted[sha].append((offering, kind))
            documents.append({"offering_id": offering, "kind": kind, "document_sha256": sha,
                "raw_path": str(raw.relative_to(root)), "expected_pages": catalog["pdf_pages"],
                "identity_evidence": match, "accepted_for_reference": False})
    pages, page_counts, seen = [], defaultdict(set), set()
    for path in config["carrier_page_exports"]:
        for index, row in json_rows(repo_path(root, path)):
            sha = row["document_sha256"]
            if sha not in wanted:
                continue
            page = row["pdf_page"]
            if isinstance(page, bool) or not isinstance(page, int) or page < 1:
                raise ValueError("Invalid carrier page")
            # Original export text_sha256 conventions differ: pin the whole row
            # and export, without inventing a new interpretation of that field.
            key = (path, sha, page)
            if key in seen:
                raise ValueError("Duplicate page inside a source export")
            seen.add(key)
            page_counts[sha].add(page)
            for offering, kind in wanted[sha]:
                pages.append(envelope(path, index, row, offering_id=offering, document_kind=kind))
    for doc in documents:
        actual = page_counts[doc["document_sha256"]]
        if actual != set(range(1, doc["expected_pages"] + 1)):
            raise ValueError(f"Incomplete carrier page export: {doc['offering_id']}/{doc['kind']}")
    write_rows(output / "carrier-pages.jsonl.gz", pages)
    cms = []
    for spec in config["cms_exports"]:
        for index, row in json_rows(repo_path(root, spec["path"])):
            if row["offering_id"] in selected:
                if any(key not in row for key in spec["fields"]):
                    raise ValueError("CMS export adapter fields changed")
                # Explicit allowlist excludes carrier corroboration/alignment.
                source_only = {key: row[key] for key in spec["fields"]}
                cms.append({"source_export": spec["path"], "source_row": index,
                    "source_record_sha256": digest(row), "offering_id": row["offering_id"],
                    "record": source_only, "projected_record_sha256": digest(source_only)})
    if set(r["offering_id"] for r in cms) != set(selected):
        raise ValueError("Missing CMS input for selected offering")
    write_rows(output / "cms-source-inputs.jsonl.gz", cms)
    write_json(output / "document-bindings.json", sorted(documents, key=lambda r: (r["offering_id"], r["kind"])))
    return {"carrier_page_records": len(pages), "cms_source_records": len(cms),
            "document_slots": len(documents)}


def validate_source_adapters(config):
    for spec in config["cms_exports"]:
        if spec.get("adapter") not in CMS_ADAPTERS or spec.get("fields") != CMS_ADAPTERS[spec["adapter"]]:
            raise ValueError("CMS adapter must use its complete source-only field allowlist")


def output_manifest(directory):
    return {p.name: file_hash(p) for p in sorted(directory.iterdir())
            if p.is_file() and p.name != "manifest.json"}


def verify_output(directory):
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest["schema"] != SCHEMA or manifest["files_sha256"] != output_manifest(directory):
        raise ValueError("Pipeline output changed or has missing/extra files")
    if manifest["accepted_for_reference"] is not False:
        raise ValueError("Pipeline output cannot grant acceptance")
    return manifest


def change_report(previous, records, results, bindings):
    if previous is None:
        return {"previous": None, "comparison_jobs_to_replay": [r["id"] for r in results]}
    manifest = verify_output(previous)
    old_summary = json.loads((previous / "summary.json").read_text())
    old_records = {r["inventory_id"]: r["original_sha256"]
                   for _, r in json_rows(previous / "original-work-queue.jsonl.gz")}
    new_records = {key: digest(row) for key, row in records.items()}
    if old_summary["selected_offerings"] != sorted({r["offering_id"] for r in records.values()}):
        raise ValueError("Previous run has a different selected scope")
    if old_records != new_records:
        raise ValueError("Previous run has different original scope/content; explicit inventory revision required")
    old_results = {row["id"]: row for row in json.loads((previous / "comparison-results.json").read_text())}
    changed = [row["id"] for row in results if old_results.get(row["id"]) != row]
    removed = sorted(old_results.keys() - {r["id"] for r in results})
    old_bindings = json.loads((previous / "input-bindings.json").read_text())
    return {"previous_manifest_sha256": digest(manifest), "originals_added": 0, "originals_removed": 0,
            "originals_changed": 0, "comparison_jobs_to_replay": changed,
            "removed_comparison_jobs": removed,
            "unchanged_mechanical_jobs": sorted({r["id"] for r in results} - set(changed)),
            "changed_inputs": sorted(k for k in old_bindings.keys() | bindings.keys()
                                     if old_bindings.get(k) != bindings.get(k)),
            "cached_acceptance_reused": False,
            "execution_policy": "All mechanical comparisons are rerun; unchanged is a change-detection result, not review reuse."}


def build(root, config_path, output, selected=None, previous=None):
    root, config_path, output = root.resolve(), config_path.resolve(), output.resolve()
    if output.exists():
        raise ValueError("Output must be a new directory; never overwrite a prior packet")
    config_sha256 = file_hash(config_path)
    config = json.loads(config_path.read_text())
    if config["schema"] != SCHEMA:
        raise ValueError("Unknown configuration schema")
    if not config_path.is_relative_to(root):
        raise ValueError("Configuration must be in this repository")
    required_inputs = engine_paths() + [str(Path(__file__).resolve().relative_to(root))]
    required_inputs += [f"{R9}/{name}" for name in ("freeze.json", "master-inventory.jsonl.gz",
        "inventory-binding.json", "offering-inventory.json", "pilot-contract.json", "work-policies.json")]
    required_inputs += [config["document_matrix"]] + config["document_catalogs"] + config["carrier_page_exports"]
    required_inputs += [spec["path"] for spec in config["cms_exports"] + config["candidate_inputs"]]
    for name in required_inputs:
        if name not in config["bindings"]:
            raise ValueError(f"Unpinned executable dependency: {name}")
    # No output can be nested inside a retained input packet.
    for name in config["bindings"]:
        parent = repo_path(root, name).parent
        if output.is_relative_to(parent):
            raise ValueError(f"Output would modify an input directory: {parent}")
    check_bindings(root, config["bindings"])
    offerings = selected if selected is not None else config["selected_offerings"]
    records, universe, binding = load_inventory(root, config, offerings)
    active = {**config, "candidate_inputs": [a for a in config["candidate_inputs"] if a["offering_id"] in offerings]}
    results = replay_candidates(root, active, records)
    policies = read_json(root, f"{R9}/work-policies.json")
    batches = work_batches(records, policies)
    dependencies = defaultdict(list)
    for result in results:
        for key in result["dependency_ids"]:
            dependencies[key].append(result["id"])
    queue = []
    for key, row in sorted(records.items()):
        missing = "required_evidence_missing" in row["states"]
        conflict = "preserved_source_conflict" in row["states"]
        action = "resolve_named_missing_source" if missing else (
            "review_preserved_source_conflict" if conflict else (
            "complete_linked_candidate_interpretation" if dependencies[key] else "author_structured_interpretation"))
        queue.append({"inventory_id": key, "offering_id": row["offering_id"], "kind": row["kind"],
            "original_sha256": digest(row), "original_states": row["states"], "source_side": source_side(row),
            "subject": row["subject"], "predicate": row["predicate"],
            "specific_missing_source_work": row["detail"] if missing else None,
            "source_ids": row["source_ids"], "observation_ids": row["observation_ids"],
            "next_action": action, "work_policy_id": row["work_policy_id"],
            "work_policy": policies[row["work_policy_id"]],
            "dependency_candidate_ids": sorted(dependencies[key]), "dependency_is_completion": False,
            "comparison_state": "evidence_missing" if missing else ("conflicting" if conflict else "pending"),
            "accepted_for_reference": False})
    delta = change_report(previous, records, results, config["bindings"])
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".l03-pipeline-", dir=output.parent))
    try:
        write_rows(temporary / "original-work-queue.jsonl.gz", queue)
        write_json(temporary / "work-batches.json", batches)
        for side in ("cms", "carrier", "unresolved"):
            write_rows(temporary / f"{side}-inventory-inputs.jsonl.gz",
                       (row for row in records.values() if source_side(row) == side))
        counts = prepare_source_inputs(root, config, offerings, temporary)
        pilot = read_json(root, f"{R9}/pilot-contract.json")
        matrix = {r["offering_id"]: r for r in read_json(root, config["document_matrix"])}
        summary = {"schema": SCHEMA, "selected_offerings": sorted(offerings),
            "global_inventory": {"required": binding["required_record_count"], "offerings": len(universe),
                                 "canonical_sha256": binding["inventory_digest"]},
            "selected_inventory": {offering: {"required": universe[offering]["required"],
                "name": matrix[offering]["name"], "parent": matrix[offering]["parent"],
                "work_actions": dict(Counter(r["next_action"] for r in queue if r["offering_id"] == offering)),
                "named_missing_predicates": sum(r["comparison_state"] == "evidence_missing"
                                               for r in queue if r["offering_id"] == offering)}
                for offering in sorted(offerings)},
            "required_originals_preserved": len(records), "work_batches": len(batches),
            "candidate_comparisons_replayed": len(results), "source_input_counts": counts,
            "mechanical_outcomes": dict(Counter(r["mechanical_result"]["outcome"] for r in results)),
            "required_pilot_offerings": len(pilot["offerings"]), "whole_offering_pilots_completed": 0,
            "original_comparisons_completed_by_this_pipeline": 0, "newly_verified_facts": 0,
            "newly_accepted_entries": 0, "accepted_for_reference": False,
            "consumer_usable": False, "independent_source_review_complete": False,
            "boundary": "Research preparation and mechanical replay only; no source interpretation, calculator, recommendation, app or database release."}
        write_json(temporary / "summary.json", summary)
        write_json(temporary / "comparison-results.json", results)
        write_json(temporary / "change-report.json", delta)
        write_json(temporary / "input-bindings.json", config["bindings"])
        write_json(temporary / "manifest.json", {"schema": SCHEMA, "config_sha256": config_sha256,
                   "files_sha256": output_manifest(temporary), "accepted_for_reference": False})
        check_bindings(root, config["bindings"])
        if file_hash(config_path) != config_sha256:
            raise ValueError("Configuration changed during build")
        # A concurrent run must not replace an already-created destination.
        output.mkdir()
        for path in sorted(temporary.iterdir(), key=lambda path: path.name == "manifest.json"):
            shutil.move(str(path), str(output / path.name))
        verify_output(output)
        return summary
    finally:
        shutil.rmtree(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--offering", action="append", help="Exact ID; repeat to select multiple offerings")
    parser.add_argument("--all", action="store_true", help="Prepare the unchanged complete 72-offering universe")
    parser.add_argument("--previous", type=Path, help="Prior output to compare; does not reuse acceptance")
    parser.add_argument("--verify", type=Path, help="Check output hashes without writing")
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify_output(args.verify), sort_keys=True))
        return
    if not args.output or (args.all and args.offering):
        parser.error("Provide --output and choose either --all or --offering")
    selected = sorted(r["offering_id"] for r in read_json(ROOT, f"{R9}/offering-inventory.json")) if args.all else args.offering
    summary = build(ROOT, args.config, args.output, selected, args.previous)
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
