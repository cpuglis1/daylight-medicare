#!/usr/bin/env python3
"""Replay the preserved Collier release baseline without changing historical data."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

import cms_slice as cms
import demo_release


def replay(release, out):
    path, out = demo_release.resolve(release), Path(out)
    if out.exists():
        raise cms.SourceError("Baseline output exists; preserve it and choose a new directory")
    manifest = cms.load_json(path / "manifest.json")
    basis = {k: manifest[k] for k in ("files_sha256", "code_sha256", "source_receipt")}
    if manifest["release_id"] != "naples-" + cms.sha256(json.dumps(basis, sort_keys=True).encode())[:20]:
        raise cms.SourceError("Historical release identity does not match its manifest")
    for name, digest in manifest["files_sha256"].items():
        if not (path / name).resolve().is_relative_to(path.resolve()) or cms.file_hash(path / name) != digest:
            raise cms.SourceError("Historical release file differs: " + name)
    catalog, prescription = (cms.load_json(path / p) for p in ("catalog.json", "prescription.json"))
    rows = catalog["options"] + catalog["exclusions"]
    joins = prescription["report"]["joins"]
    counts = {"catalog": len(rows), "drug_bearing": sum(bool(j["selected_plan"]) for j in joins),
              "medical": sum(r["category"] != "PDP" for r in rows),
              "packaged_pharmacy_networks": sum(n.endswith("-pharmacy.psv.gz") for n in manifest["files_sha256"])}
    if counts != {"catalog": 70, "drug_bearing": 61, "medical": 59, "packaged_pharmacy_networks": 31}:
        raise cms.SourceError("Baseline differs from the plan: " + str(counts))
    now = datetime.now(timezone.utc).isoformat()
    result = {"extracted_at_utc": now, "release_id": manifest["release_id"], "release_manifest_sha256": cms.file_hash(path / "manifest.json"),
              "counts": counts, "categories": dict(Counter(r["category"] for r in rows)),
              "contracts": sorted({r["identity"]["contract"] for r in rows}),
              "historical_scope": {"options": len(catalog["options"]), "exclusions": len(catalog["exclusions"])},
              "sources": catalog["sources"], "prescription_source": prescription["config"]["source"],
              "parser_and_runtime_sha256": manifest["code_sha256"],
              "workspace_code_differs_from_historical_release": [p for p, h in manifest["code_sha256"].items() if not (cms.ROOT / p).exists() or cms.file_hash(cms.ROOT / p) != h],
              "verified_release_files": len(manifest["files_sha256"]),
              "limits": ["Historical packaged evidence verified against its own manifest; current workspace code may differ.",
                         "This baseline does not certify live-market completeness or close consumer-fact issues.",
                         "Candidate app/audit alignment is a later C34 release gate."]}
    out.mkdir(parents=True)
    cms.write_json(out / "baseline.json", result)
    layers = [
        ("Original Medicare A/B", "not captured", "not integrated", "pending", "CMS annual cost publication", "R1 coverage gap", "analyst", "C29: published 2027 figures only"),
        ("Advantage plan list", "59 records", "59 browsable", "live-market check pending", "CMS landscape / PBP", "DQ-005, DQ-006", "data engineering + analyst", "C17–C18: two-way ZIP market check"),
        ("Advantage benefit detail", "59 full PBP payloads", "selected landscape fields", "carrier sample: 16 records / 3 parents", "CMS PBP; carrier documents", "DQ-006", "analyst", "C19: field dictionary and reviewed matrix"),
        ("Standalone Part D list", "11 records", "11 browsable", "live-market check pending", "CMS landscape", "DQ-005", "data engineering + analyst", "C18: reconcile statewide PDPs"),
        ("Formularies", "61 drug plans", "31 legacy-scope drug plans", "limited drug samples", "CMS monthly Part D PUF", "DQ-010", "data + app engineering", "C05: enable all 61"),
        ("Drug prices", "no 2027 pricing table", "unavailable", "source feasibility pending", "CMS monthly / quarterly inspections", "DQ-007, DQ-008", "data engineering + supplier owner", "C14: source decision; H01 held"),
        ("Pharmacy networks", "61 captured", "31 packaged", "C05 extracted-bundle replay pending", "CMS monthly Part D PUF", "DQ-010", "data + app engineering", "C05: package 61 with capability-based access"),
        ("Doctor/hospital networks", "dated hospital notices", "notices; exact participation unresolved", "59 plan mappings pending", "Hospital pages; directory discovery", "DQ-009", "data engineering + analyst", "C15, C26–C28: hospital table and qualified APIs"),
        ("Stars", "landscape columns blank", "unavailable", "24 contract joins pending", "CMS 2027 star data tables", "DQ-002", "data engineering", "C04: sourced numeric or nonnumeric state"),
        ("Medigap products/rates", "source diligence only", "no product/rate dataset", "pending", "Florida OIR / CHOICES", "DQ-011", "supplier owner + analyst", "C09, C22–C24: request, capture, reconcile"),
        ("Medigap buying rules", "limited education", "limited education", "full rules review pending", "Medicare / Florida guidance", "DQ-011", "analyst", "C25: sourced rules and boundaries"),
        ("Help programs", "not captured", "not integrated", "pending", "SSA / Florida DCF / SHINE", "R1 coverage gap", "analyst + app engineering", "C31: may-qualify screener and referral"),
        ("Enrollment/penalties", "limited education", "limited education", "pending", "Medicare official guidance", "R1 coverage gap", "analyst + app engineering", "C30: windows and compatibility checks"),
        ("Other plan types", "not reconciled", "not integrated", "pending", "AHCA / CMS", "R1 coverage gap", "analyst", "C06: Hope PACE and dated searches"),
        ("Local counseling", "not verified", "not integrated", "pending", "Official Collier SHINE directory", "R1 coverage gap", "analyst", "C07: verify usable referral"),
    ]
    text = ["# Collier coverage baseline", "", f"Release: `{result['release_id']}`. Extracted: {now}.", "",
            "Historical baseline: 70 catalog / 61 drug-bearing / 59 medical / 31 packaged networks. The original 38/32 evidence scope is retained as history.", "",
            "This table records C02 status before C03–C05. Later closure receipts supplement it; they do not rewrite these counts. Source publication dates are distinct from this extraction date.", "",
            "| Layer | Captured | In app | Reviewed | Source | Retrieval date | Open issues | Owner | Next action |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    receipts = {}
    for key, relative in (("landscape", "data-sources/raw/landscape.receipt.json"), ("pbp", "data-sources/raw/pbp.receipt.json"),
                          ("prescription", "data-sources/raw/prescription/2027_20261008.zip.receipt.json")):
        source = cms.ROOT / relative
        receipts[key] = {"path": relative, "receipt_sha256": cms.file_hash(source), "receipt": cms.load_json(source)}
    cms.write_json(out / "source-receipts.json", receipts)
    for layer, captured, app, reviewed, source, issues, owner, action in layers:
        key = "prescription" if source == "CMS monthly Part D PUF" else "landscape" if source.startswith(("CMS landscape", "CMS PBP")) else None
        retrieved = receipts[key]["receipt"]["received_at_utc"] if key else "Not captured" if captured == "not captured" else "See source-specific receipt; no date inferred"
        text.append(f"| {layer} | {captured} | {app} | {reviewed} | {source} | {retrieved} | {issues} | {owner} | {action} |")
    text += ["", "## Existing issue ownership", "", "| Issue | Owner | Next action |", "| --- | --- | --- |"]
    issue_actions = [
        ("DQ-001", "national data engineering", "H06: retain national missing-PBP issue; outside Collier gate"),
        ("DQ-002", "data engineering", "C04: import and independently check all 24 contracts"),
        ("DQ-003 / DQ-004", "analyst", "C21: explain premium basis or display both values"),
        ("DQ-005", "data engineering", "C17–C18: extend Medicare.gov observation and reconcile market"),
        ("DQ-006", "analyst", "C19: carrier checks for all displayed core fields"),
        ("DQ-007", "data engineering + supplier owner", "C14: price feasibility; H01 remains held"),
        ("DQ-008", "data engineering", "C14: retain separate filename, publication, period and retrieval dates"),
        ("DQ-009", "data engineering + analyst", "C15, C26–C28: mapped network evidence"),
        ("DQ-010", "data + app engineering", "C05: 61 packaged and queryable networks; extracted-bundle proof"),
        ("DQ-011", "supplier owner + analyst", "C09, C22–C25: product universe and rates/quote routes"),
        ("DQ-012", "qualified domain reviewer", "C36: named review of exact candidate hash and scope"),
        ("DQ-013", "national data engineering", "H06: retain 148-identity field-variation issue"),
        ("DQ-014", "data engineering", "C03: new catalog retrieval, change assessment and deadline"),
    ]
    text.extend(f"| {issue} | {owner} | {action} |" for issue, owner, action in issue_actions)
    text += ["", "Owners are role assignments from the plan, not claims of named staffing. Source hashes and historical parser versions are in baseline.json. C34 will align the regenerated workbook with the eventual candidate release.", ""]
    (out / "coverage.md").write_text("\n".join(text))
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", default="current")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(replay(args.release, args.out))
