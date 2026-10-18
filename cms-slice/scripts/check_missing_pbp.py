#!/usr/bin/env python3
"""Check the known PBP gap against the independently published October Part D source."""

from collections import defaultdict
import json

import cms_slice as cms
import prescription as rx


def inspect():
    cms.verify_report(cms.Sources(), cms.ROOT / "reports/work-package-1")
    config = cms.load_json(rx.CONFIG)
    nested = rx.prepare(config)
    ledger = cms.ROOT / "reports/work-package-1/landscape-without-pbp.jsonl"
    missing = [json.loads(line) for line in ledger.read_text().splitlines()]
    targets = {(r["identity"]["contract"], r["identity"]["plan"], r["identity"]["segment_join"]) for r in missing}
    stats = {}
    geography = {row["COUNTY_CODE"]: {"source_row": n, "raw": row} for n, row, _ in rx.source_rows(config, nested, "geography", stats)}
    matches = defaultdict(list)
    alternates = defaultdict(set)
    for ordinal, row, _ in rx.source_rows(config, nested, "plan", stats):
        key = rx.identity(row)
        if key in targets:
            matches[key].append({"source_row": ordinal, "raw": row, "geographic_locator": geography.get(row["COUNTY_CODE"])})
        for target in targets:
            if key[:2] == target[:2] and key[2] != target[2]:
                alternates[target].add(key[2])
    findings = []
    for key in sorted(targets):
        landscape = [r for r in missing if (r["identity"]["contract"], r["identity"]["plan"], r["identity"]["segment_join"]) == key]
        geographic_checks = []
        for source in landscape:
            raw = source["landscape_raw"]
            corresponding = [r for r in matches[key] if r["geographic_locator"] and r["raw"]["STATE"] == raw["State Territory Abbreviation"]
                             and r["geographic_locator"]["raw"]["STATENAME"] == raw["State Territory Name"] and r["geographic_locator"]["raw"]["COUNTY"] == raw["County Name"]]
            geographic_checks.append({"source_county": raw["County Name"], "landscape_evidence": source["evidence"], "exact_puf_county_matches": len(corresponding),
                                      "puf_plan_source_rows": [r["source_row"] for r in corresponding],
                                      "puf_ssa_codes": [r["raw"]["COUNTY_CODE"] for r in corresponding]})
        findings.append({"id": rx.option_id(key), "missing_pbp_member": landscape[0]["expected_member"], "landscape_geographic_rows": len(landscape),
                         "puf_geographic_rows": len(matches[key]), "puf_rows": matches[key], "alternate_segments": sorted(alternates[key]), "geographic_checks": geographic_checks,
                         "name_agreement": all(r["raw"]["PLAN_NAME"] == landscape[0]["landscape_raw"]["Plan Name"] for r in matches[key]),
                         "suppression_values": sorted({r["raw"]["PLAN_SUPPRESSED_YN"] for r in matches[key]}),
                         "disposition": "The exact plan/segment independently appears in this Part D release. The PBP member is still missing from its pinned source. This is not proof of withdrawal, marketability or complete benefits; do not fill the missing PBP from another plan or source family."})
    return {"checked_on": "2026-10-17", "status": "additional_source_evidence; pbp_gap_remains_unresolved", "findings": findings,
            "source_release": config["release_id"], "source_archive": config["source"], "source_tables": stats,
            "input_hashes": {"missing_ledger": cms.file_hash(ledger), "source_configuration": cms.file_hash(rx.CONFIG), "probe_code": cms.file_hash(__file__), "reader_code": cms.file_hash(rx.__file__)}}


def main():
    try:
        report = inspect()
        cms.write_json(cms.ROOT / "reports/source-diligence/missing-pbp-followup.json", report)
        print(json.dumps({"status": report["status"], "findings": [{"id": r["id"], "puf_rows": r["puf_geographic_rows"], "landscape_rows": r["landscape_geographic_rows"], "exact_county_matches": sum(c["exact_puf_county_matches"] for c in r["geographic_checks"])} for r in report["findings"]]}, indent=2))
    except (cms.SourceError, OSError, ValueError, KeyError) as error:
        print("ERROR:", error)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
