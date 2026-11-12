"""Additive hospital/office normalization pass over a sealed review-pipeline run."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

import l03_benefit_normalization as normalize
import l03_review_pipeline as review

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "docs/data/l03-benefit-normalization-2026-11-03-r1/config.json"
SCHEMA = "l03-normalization-pipeline/1"


def build(config_path, output):
    config_path, output = config_path.resolve(), output.resolve()
    if output.exists():
        raise ValueError("Output must be a new directory")
    config_sha = review.file_hash(config_path)
    config = json.loads(config_path.read_text())
    if config["schema"] != SCHEMA:
        raise ValueError("Unsupported normalization configuration")
    required_paths = ["cms-slice/scripts/l03_benefit_normalization.py",
        "cms-slice/scripts/l03_normalization_pipeline.py", "cms-slice/scripts/l03_review_pipeline.py",
        config["profiles"], config["native_archive"], config["native_manifest"], config["field_dictionary"],
        config["parent_config"]]
    if any(path not in config["bindings"] for path in required_paths):
        raise ValueError("Unpinned adapter dependency")
    review.check_bindings(ROOT, config["bindings"])
    parent_config = review.read_json(ROOT, config["parent_config"])
    packet = review.repo_path(ROOT, config["input_packet"])
    manifest = review.verify_output(packet)
    if review.file_hash(packet / "manifest.json") != config["input_packet_manifest_sha256"]:
        raise ValueError("Parent preparation packet changed")
    # Parent guards replay the full canonical denominator and every preservation pin.
    review.check_bindings(ROOT, parent_config["bindings"])
    for path in parent_config["bindings"]:
        if output.is_relative_to(review.repo_path(ROOT, path).parent):
            raise ValueError("Output would modify a retained source/code packet")
    if output.is_relative_to(packet):
        raise ValueError("Output would modify the retained preparation run")
    summary_before = json.loads((packet / "summary.json").read_text())
    selected = summary_before["selected_offerings"]
    originals, _, binding = review.load_inventory(ROOT, parent_config, selected)
    profiles = review.read_json(ROOT, config["profiles"])
    if set(p["offering_id"] for p in profiles) != set(selected):
        raise ValueError("Carrier profiles must cover the exact prepared offering scope")
    if len({p["id"] for p in profiles}) != len(profiles):
        raise ValueError("Duplicate carrier profile ID")
    plan_manifest = {r["offering_id"]: r for r in review.read_json(ROOT, config["native_manifest"])}
    candidates, native_inputs, related = [], [], []
    with zipfile.ZipFile(review.repo_path(ROOT, config["native_archive"])) as archive:
        for offering in selected:
            expected = plan_manifest[offering]
            if expected["archive_sha256"] != config["bindings"][config["native_archive"]]:
                raise ValueError("Native manifest/archive mismatch")
            raw = archive.read(expected["member"])
            if hashlib.sha256(raw).hexdigest() != expected["member_sha256"]:
                raise ValueError("Native member bytes changed")
            obj = json.loads(raw)
            identity_binding = normalize.bind_native_identity(obj, offering)
            plan = obj["pbp"][0]
            native_inputs.append({"offering_id": offering, "source": expected, "raw_member": obj,
                                  "identity_binding": identity_binding})
            plan_context = {k: v for k, v in plan.items() if k != "benefitDetails"}
            found = set()
            for index, row in enumerate(plan["benefitDetails"]["benefitDetailsInfo"]):
                if row.get("categoryCode") in normalize.FAMILIES:
                    source = {"archive_sha256": expected["archive_sha256"], "member": expected["member"],
                        "member_sha256": expected["member_sha256"],
                        "pointer": f"/pbp/0/benefitDetails/benefitDetailsInfo/{index}",
                        "raw_object_sha256": normalize.fingerprint(row), "identity_binding": identity_binding}
                    candidates.append(normalize.normalize_native(offering, row, source, plan_context))
                    found.add(row["categoryCode"])
                elif str(row.get("categoryCode", "")).startswith("1a"):
                    related.append({"offering_id": offering, "pointer": f"/pbp/0/benefitDetails/benefitDetailsInfo/{index}",
                        "member_sha256": expected["member_sha256"], "record": row,
                        "state": "retained_related_hospital_source_not_normalized", "accepted_for_reference": False})
            if found != set(normalize.FAMILIES):
                raise ValueError("A required hospital/office family is missing from native input")
    # No CMS records or expected costs are passed into the carrier adapter.
    pages = {}
    for _, envelope in review.json_rows(packet / "carrier-pages.jsonl.gz"):
        key = (envelope["offering_id"], envelope["record"]["document_sha256"], envelope["record"]["pdf_page"])
        if key in pages and pages[key] != envelope["record"]:
            raise ValueError("Different retained page versions require an explicit selection")
        pages[key] = envelope["record"]
    for profile in profiles:
        page = pages[(profile["offering_id"], profile["document_sha256"], profile["pdf_page"])]
        rows = normalize.normalize_carrier(profile, page)
        for row in rows:
            row["source"]["complete_carrier_context_packet"] = {
                "path": str((packet / "carrier-pages.jsonl.gz").relative_to(ROOT)),
                "sha256": manifest["files_sha256"]["carrier-pages.jsonl.gz"],
                "scope": "Complete retained SB/EOC context, not an adopted condition interpretation"}
        candidates.extend(rows)
    if len({r["id"] for r in candidates}) != len(candidates):
        raise ValueError("Duplicate normalized candidate ID")
    candidates.sort(key=lambda r: (r["offering_id"], r["source_side"], r["family"], r["id"]))
    for row in candidates:
        normalize.validate_record(row)
    dictionary = review.read_json(ROOT, config["field_dictionary"])
    dictionary_support = {"source": {k: v for k, v in dictionary.items() if k != "fields"},
        "fields": [r for r in dictionary["fields"] if r.get("service_category") in normalize.FAMILIES],
        "native_mapping_status": "Flat dictionary scope is retained for review; no universal native enum equivalence adopted"}
    queue = [{"candidate_id": r["id"], "offering_id": r["offering_id"], "family": r["family"],
        "source_side": r["source_side"], "source_sha256": normalize.fingerprint(r["source"]),
        "candidate_sha256": normalize.fingerprint(r), "holds": r["holds"],
        "next_action": "Review source interpretation, all material conditions and exact original bindings before any complete comparison",
        "state": "source_interpretation_pending", "accepted_for_reference": False} for r in candidates]
    summary = {"schema": SCHEMA, "selected_offerings": selected,
        "required_originals_preserved": len(originals), "global_required_originals": binding["required_record_count"],
        "canonical_inventory_sha256": binding["inventory_digest"],
        "normalization_candidates": len(candidates),
        "candidates_by_side_and_family": dict(Counter(r["source_side"] + ":" + r["family"] for r in candidates)),
        "related_hospital_objects_retained": len(related), "inventory_records_changed": 0,
        "complete_original_comparisons_added": 0, "newly_verified_facts": 0, "newly_accepted_entries": 0,
        "independent_source_review_complete": False, "consumer_usable": False,
        "calculation_ready": False, "accepted_for_reference": False,
        "scope": "Reusable source-local hospital/office parser candidates; full source/condition review remains open"}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".l03-normalization-", dir=output.parent))
    try:
        review.write_rows(temporary / "normalization-candidates.jsonl.gz", candidates)
        review.write_rows(temporary / "cms-native-source.jsonl.gz", native_inputs)
        review.write_json(temporary / "related-hospital-source.json", related)
        review.write_json(temporary / "dictionary-review-support.json", dictionary_support)
        review.write_json(temporary / "review-queue.json", queue)
        review.write_json(temporary / "family-diagnostics.json", normalize.family_diagnostics(candidates))
        review.write_json(temporary / "summary.json", summary)
        review.write_json(temporary / "input-bindings.json", config["bindings"])
        review.write_json(temporary / "scope-accounting.json", {
            "parent_preparation_manifest_sha256": config["input_packet_manifest_sha256"],
            "before_canonical_inventory_sha256": binding["inventory_digest"],
            "after_canonical_inventory_sha256": binding["inventory_digest"],
            "originals_added": [], "originals_removed": [], "originals_split": [],
            "originals_merged": [], "originals_reclassified": [], "originals_changed": [],
            "required_originals_in_prepared_scope": len(originals),
            "global_required_originals": binding["required_record_count"],
            "new_normalization_candidates": len(candidates), "new_complete_original_comparisons": 0,
            "new_acceptance": False})
        review.write_json(temporary / "manifest.json", {"schema": SCHEMA, "config_sha256": config_sha,
            "files_sha256": review.output_manifest(temporary), "accepted_for_reference": False})
        review.check_bindings(ROOT, config["bindings"])
        review.check_bindings(ROOT, parent_config["bindings"])
        review.verify_output(packet)
        if review.file_hash(config_path) != config_sha:
            raise ValueError("Configuration changed during normalization")
        output.mkdir()
        for path in sorted(temporary.iterdir(), key=lambda p: p.name == "manifest.json"):
            shutil.move(str(path), str(output / path.name))
        verify(output)
        return summary
    finally:
        shutil.rmtree(temporary)


def verify(output):
    manifest = json.loads((output / "manifest.json").read_text())
    if manifest["schema"] != SCHEMA or manifest["files_sha256"] != review.output_manifest(output):
        raise ValueError("Normalization packet changed")
    if manifest.get("accepted_for_reference") is not False:
        raise ValueError("Normalization cannot grant acceptance")
    for _, row in review.json_rows(output / "normalization-candidates.jsonl.gz"):
        normalize.validate_record(row)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify(args.verify), sort_keys=True))
    elif args.output:
        print(json.dumps(build(args.config, args.output), sort_keys=True))
    else:
        parser.error("Provide --output or --verify")


if __name__ == "__main__":
    main()
