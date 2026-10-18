#!/usr/bin/env python3
"""Independently replay returned prescription rows directly against the pinned nested ZIPs."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
from zipfile import ZipFile

import cms_slice as cms
import prescription as rx


def audit(config, result):
    if result["release_id"] != config["release_id"]:
        raise cms.SourceError("Query release mismatch")
    nested = rx.prepare(config)
    expected = defaultdict(dict)
    reference = tuple(result["id"].split("-")[:3])
    selected = result["plan_join"]["selected_plan"]
    if selected:
        if rx.identity(selected["raw"]) != reference or not rx.market_plan(selected["raw"], config["geography_match"]):
            raise cms.SourceError("Selected plan identity/geography mismatch")
        expected["plan"][selected["source_row"]] = selected["raw"]
    fields = ["basic_formulary", "beneficiary_cost_rows", "insulin_cost_rows"]
    groups = [result.get(field, []) for field in fields]
    groups.extend(result.get("supplemental_and_indication_rows", {}).values())
    groups.append(result.get("pharmacy", {}).get("rows", []))
    for rows in groups:
        for item in rows:
            evidence, raw = item["evidence"], item["raw"]
            table, ordinal = evidence["table"], evidence["source_row"]
            if table not in config["members"] or not isinstance(ordinal, int) or ordinal < 2:
                raise cms.SourceError("Invalid source table/ordinal")
            if "CONTRACT_ID" in raw:
                keys = rx.IDENTITY if "SEGMENT_ID" in raw else rx.IDENTITY[:2]
                if tuple(raw[k] for k in keys) != reference[:len(keys)]:
                    raise cms.SourceError("Returned row belongs to a different plan/segment")
            if table == "formulary" and (not selected or raw["FORMULARY_ID"] != selected["raw"]["FORMULARY_ID"] or raw["CONTRACT_YEAR"] != config["benefit_year"]):
                raise cms.SourceError("Returned formulary/year does not belong to the selected source plan")
            if table == "formulary" and any(result["input"].get(field) is not None and result["input"][field] != raw[column] for field, column in (("ndc11", "NDC"), ("rxcui", "RXCUI"))):
                raise cms.SourceError("Returned medicine differs from exact query input")
            if table.startswith("pharmacy_") and (not result["input"].get("pharmacy_npi") or raw["PHARMACY_NUMBER"] != rx.pharmacy_number(result["input"]["pharmacy_npi"])):
                raise cms.SourceError("Returned pharmacy differs from exact query NPI")
            if ordinal in expected[table] and expected[table][ordinal] != raw:
                raise cms.SourceError("One source ordinal has conflicting returned rows")
            expected[table][ordinal] = raw
    checked = {}
    for table, targets in sorted(expected.items()):
        spec = config["members"][table]
        remaining = dict(targets)
        with ZipFile(nested / spec["outer_member"]) as archive:
            with archive.open(spec["inner_member"]) as source:
                header = source.readline().rstrip(b"\r\n").decode("ascii").split("|")
                if header != spec["columns"]:
                    raise cms.SourceError("Source header changed")
                for ordinal, line in enumerate(source, 2):
                    if ordinal not in remaining:
                        continue
                    cells = line.rstrip(b"\r\n").decode(spec["encoding"]).split("|")
                    if len(cells) != len(header) or dict(zip(header, cells)) != remaining.pop(ordinal):
                        raise cms.SourceError(f"Returned cells differ from {table} source row {ordinal}")
                    if not remaining:
                        break
        if remaining:
            raise cms.SourceError("Source row ordinal not found")
        checked[table] = {"rows_checked": len(targets), "source_ordinals": sorted(targets), "nested_sha256": spec["nested_sha256"]}
        print("Replayed", table, len(targets), "actual rows", flush=True)
    return {"release_id": config["release_id"], "id": result["id"], "status": "all_returned_raw_cells_replayed_to_pinned_source",
            "checked": checked, "source_archive_sha256": config["source"]["sha256"], "query_sha256": cms.sha256(json.dumps(result, sort_keys=True).encode()),
            "auditor_sha256": cms.file_hash(__file__), "limits": "Cell/join replay only; not source accuracy, quantity-unit approval, suitability, price or current network confirmation"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = audit(cms.load_json(rx.CONFIG), cms.load_json(args.query))
        cms.write_json(args.out, result)
        print(json.dumps(result, indent=2))
    except (cms.SourceError, OSError, ValueError, KeyError) as error:
        print("ERROR:", error)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
