#!/usr/bin/env python3
"""Import pinned CMS 2027 contract stars, independently checking CSV against XLSX."""

import argparse
from collections import Counter
import csv
from decimal import Decimal, InvalidOperation
import io
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

import cms_slice as cms
from evidence_store import PublicSources

REPORTS = cms.ROOT / "reports/collier-gap-20261019/c04"
RAW = cms.ROOT / "data-sources/raw/collier-stars"
SUMMARY = "2027 Star Ratings Data Table - Summary Ratings (Oct 8 2026).csv"
MASTER = "2027_Report_Card_Master_Table_2026_09_30.xlsx"
FIELDS = {"part_c_summary": "2027 Part C Summary", "part_d_summary": "2027 Part D Summary", "overall": "2027 Overall"}
REASONS = {"Not Applicable": "not_applicable", "Not enough data available": "not_enough_data", "Plan too new to be measured": "too_new"}
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
SOURCES = {
    "cms-stars-2027-tables": ("https://www.cms.gov/files/zip/2027-star-ratings-data-tables-oct-8-2026.zip", "2704032d3f72e71a763aac075a8449e382ca07834417b1da53995b70d54e9967"),
    "cms-stars-2027-tech-notes": ("https://www.cms.gov/files/document/2027-tech-notes-2026-09-30.pdf", "93c12ef74a70e026f09f707ed57feb4ba90f2ee8a5d3f15d3c612e36476b5f4c"),
}


def rating(raw):
    token = raw.strip()
    if token in REASONS:
        return {"state": REASONS[token], "value": None, "reason": token, "raw": raw}
    try:
        value = Decimal(token)
    except InvalidOperation as error:
        raise cms.SourceError("Unknown CMS rating state: " + repr(raw)) from error
    if not value.is_finite() or value < 1 or value > 5 or value * 2 != (value * 2).to_integral():
        raise cms.SourceError("CMS rating is outside the inspected half-star scale: " + repr(raw))
    return {"state": "rated", "value": float(value), "reason": None, "raw": raw}


def csv_contracts(raw):
    rows = list(csv.reader(io.StringIO(raw.decode("cp1252"))))
    if rows[0][0] != "2027 Summary Star View: Medicare Report Card Master Table":
        raise cms.SourceError("Star CSV title/year changed")
    headers = rows[1]
    if headers[:6] != ["Contract Number", "Organization Type", "Contract Name", "Organization Marketing Name", "Parent Organization", "SNP"] or any(c not in headers for c in FIELDS.values()):
        raise cms.SourceError("Star CSV layout changed")
    contracts = {}
    for ordinal, row in enumerate(rows[2:], 3):
        if not row or not row[0].strip():
            continue
        contract = row[0].strip()
        if not re.fullmatch(r"[EHRS]\d{4}", contract) or contract in contracts or len(row) != len(headers):
            raise cms.SourceError("Invalid, duplicate or malformed star contract row")
        contracts[contract] = {"csv_row": ordinal, "contract_name": row[2].strip(),
                               "ratings": {k: rating(row[headers.index(c)]) for k, c in FIELDS.items()}}
    return contracts


def workbook_contracts(raw):
    # Independent XML/cell extraction, with sheet selected by name and relationship.
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        sheets = [s for s in workbook.findall("s:sheets/s:sheet", NS) if s.get("name") == "Summary_Rating"]
        if len(sheets) != 1:
            raise cms.SourceError("Independent CMS Summary_Rating worksheet missing/ambiguous")
        rid = sheets[0].get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = [r.get("Target") for r in rels if r.get("Id") == rid]
        if len(targets) != 1 or targets[0] != "worksheets/sheet4.xml":
            raise cms.SourceError("CMS summary worksheet relationship changed; inspect before importing")
        strings = ["".join(si.itertext()) for si in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        rows, contracts = {}, {}
        for row in ET.fromstring(archive.read("xl/" + targets[0])).findall("s:sheetData/s:row", NS):
            cells = {}
            for cell in row.findall("s:c", NS):
                if cell.find("s:f", NS) is not None:
                    raise cms.SourceError("Unexpected formula in CMS summary source; cached result is insufficient")
                value = cell.findtext("s:v", "", NS)
                cells[re.sub(r"\d", "", cell.get("r"))] = strings[int(value)] if cell.get("t") == "s" else value
            rows[int(row.get("r"))] = cells
        if [rows[2].get(c) for c in ("A", "I", "J", "K")] != ["Contract Number", *FIELDS.values()]:
            raise cms.SourceError("Independent CMS workbook headers changed")
        for ordinal, cells in rows.items():
            if ordinal <= 2 or not cells.get("A", "").strip():
                continue
            contract = cells["A"].strip()
            if contract in contracts:
                raise cms.SourceError("Duplicate contract in independent CMS workbook")
            contracts[contract] = {"xlsx_row": ordinal, "values": {k: cells.get(c, "").strip() for k, c in zip(FIELDS, ("I", "J", "K"))}}
    return contracts


def build(catalog=None):
    catalog = catalog or cms.load_json(cms.ROOT / "reports/work-package-2/catalog.json")
    sources, specs = PublicSources(REPORTS / "sources.json", RAW), {}
    for key, (url, digest) in SOURCES.items():
        spec, raw = sources.read(key)
        if spec["requested_url"] != url or spec["sha256"] != digest:
            raise cms.SourceError("Star source differs from inspected publication; review a new version")
        specs[key] = spec
    spec, raw = sources.read("cms-stars-2027-tables")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        csv_raw, xlsx_raw = archive.read(SUMMARY), archive.read(MASTER)
    primary, check = csv_contracts(csv_raw), workbook_contracts(xlsx_raw)
    contracts = sorted({r["identity"]["contract"] for r in catalog["options"] + catalog["exclusions"]})
    if len(contracts) != 24:
        raise cms.SourceError("Collier contract universe changed; inspect the star join")
    selected, checks = {}, []
    for contract in contracts:
        if contract not in primary or contract not in check:
            raise cms.SourceError("Captured contract is absent from the CMS star source: " + contract)
        row, independent = primary[contract], check[contract]
        for field, value in row["ratings"].items():
            if value["raw"].strip() != independent["values"][field]:
                raise cms.SourceError("CSV/workbook rating conflict: " + contract + " " + field)
            checks.append({"contract": contract, "field": field, "status": "agrees", "csv_raw": value["raw"],
                           "xlsx_raw": independent["values"][field], "csv_row": row["csv_row"], "xlsx_row": independent["xlsx_row"]})
        selected[contract] = {**row, "independent_check": "CSV agrees with CMS workbook cells", "xlsx_row": independent["xlsx_row"]}
    result = {"rating_year": "2027", "published_on": "2026-10-08", "technical_notes_revision": "2026-09-30",
              "catalog_snapshot_id": catalog["snapshot_id"], "source": spec, "technical_notes": specs["cms-stars-2027-tech-notes"],
              "summary_member": SUMMARY, "master_member": MASTER, "contracts": selected,
              "counts": {"contracts": len(selected), "plans": len(catalog["options"] + catalog["exclusions"]), "independently_checked_cells": len(checks)},
              "limits": ["Contract-level ratings; individual plans and SNP eligibility are separate.",
                         "CSV and XLSX checks are independent extractions of the same CMS publication, not separate market observations.",
                         "These are 2027 ratings, not recalculated 2026 quality-bonus-payment ratings. Raw landscape blanks are preserved."]}
    cms.write_json(REPORTS / "ratings.json", result)
    cms.write_json(REPORTS / "independent-check.json", {"csv_sha256": cms.sha256(csv_raw), "workbook_sha256": cms.sha256(xlsx_raw), "checks": checks})
    cms.write_json(REPORTS / "manifest.json", {"parser_sha256": cms.file_hash(__file__), "catalog_snapshot_id": catalog["snapshot_id"],
                   "sources_sha256": cms.file_hash(REPORTS / "sources.json"),
                   "outputs_sha256": {name: cms.file_hash(REPORTS / name) for name in ("ratings.json", "independent-check.json")}})
    return result


def load(catalog):
    manifest = cms.load_json(REPORTS / "manifest.json")
    if manifest["parser_sha256"] != cms.file_hash(__file__) or manifest["catalog_snapshot_id"] != catalog["snapshot_id"] or manifest["sources_sha256"] != cms.file_hash(REPORTS / "sources.json"):
        raise cms.SourceError("Star source/parser/catalog changed; rebuild and review")
    for name, digest in manifest["outputs_sha256"].items():
        if cms.file_hash(REPORTS / name) != digest:
            raise cms.SourceError("Star output changed: " + name)
    sources = PublicSources(REPORTS / "sources.json", RAW)
    for key in SOURCES:
        sources.read(key)
    return cms.load_json(REPORTS / "ratings.json")


def for_plan(data, row):
    if not data:
        return {"state": "unavailable", "value": None, "reason": "Star source not included in this historical release"}
    field = "part_d_summary" if row["category"] == "PDP" else "part_c_summary" if row["category"] == "MA" else "overall"
    contract = row["identity"]["contract"]
    record = data["contracts"][contract]
    return {**record["ratings"][field], "rating_year": data["rating_year"], "published_on": data["published_on"],
            "contract": contract, "rating_type": field,
            "label": {"part_c_summary": "Part C summary", "part_d_summary": "Part D summary", "overall": "Overall"}[field],
            "evidence": {"id": "cms-stars-2027-" + contract + "-" + field, "url": data["source"]["requested_url"],
                         "sha256": data["source"]["sha256"], "retrieved_at_utc": data["source"]["retrieved_at_utc"],
                         "review_after_utc": data["source"]["review_after_utc"], "member": data["summary_member"],
                         "row": record["csv_row"], "column": FIELDS[field], "independent_check": record["independent_check"]}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("fetch", "build", "verify"))
    args = parser.parse_args()
    if args.command == "fetch":
        sources = PublicSources(REPORTS / "sources.json", RAW)
        for key, (url, digest) in SOURCES.items():
            spec, _ = sources.capture(key, url, max_bytes=60_000_000)
            if spec["sha256"] != digest:
                raise cms.SourceError("New CMS source bytes need inspection before import")
    else:
        result = build() if args.command == "build" else load(cms.load_json(cms.ROOT / "reports/work-package-2/catalog.json"))
        print(result["counts"])
