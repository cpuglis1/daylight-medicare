"""Offline, append-only import of owner-authorized CSG quote workbook exports.

Licensed evidence stays in a separate private candidate, never the public-evidence
research schema or consumer runtime. No network access or price extrapolation.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import xml.etree.ElementTree as ET
import zipfile

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
HEADERS = ["Company", "Established Year", "AM Best Rating", "AM Best Outlook",
           "S&P Rating", "County", "NAIC", "Monthly Rate", "Annual Rate",
           "HH Discount", "Policy Fee", "Monthly Rate With Discounts",
           "Annual Rate With Discounts", "Rating Class", "Rate Type",
           "Med Select", "Effective Date"]
VARIANTS = ["A", "B", "C", "D", "F", "HDF", "G", "HDG", "K", "L", "M", "N"]
HOLDS = ["SOURCE_USE_EXACT_SCOPE_REVIEW_PENDING", "R15_METHOD_REVIEW_PENDING",
         "CONSUMER_OUTPUT_NOT_ACCEPTED", "POLICY_FORM_AND_EDITION_UNKNOWN",
         "FULL_MARKET_COVERAGE_UNPROVEN", "PERSONAL_ELIGIBILITY_NOT_DETERMINED"]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cells_from_xlsx(path):
    """Read exact source cell strings, without executing formulas or losing money precision."""
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:
            raise ValueError("Workbook CRC failure")
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("s:si", NS):
                shared.append("".join(t.text or "" for t in si.iterfind(".//s:t", NS)))
        relationships = {
            r.attrib["Id"]: r.attrib["Target"]
            for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        }
        result = {}
        for s in ET.fromstring(z.read("xl/workbook.xml")).findall("s:sheets/s:sheet", NS):
            rid = s.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = relationships[rid]
            target = target.lstrip("/") if target.startswith("/") else "xl/" + target
            cells = {}
            for c in ET.fromstring(z.read(target)).findall(".//s:sheetData/s:row/s:c", NS):
                if c.find("s:f", NS) is not None:
                    raise ValueError("Unexpected formula in source export")
                typ = c.attrib.get("t", "n")
                value = c.findtext("s:v", default=None, namespaces=NS)
                if typ == "s" and value is not None:
                    value = shared[int(value)]
                elif typ == "inlineStr":
                    value = "".join(t.text or "" for t in c.iterfind(".//s:t", NS))
                cells[c.attrib["r"]] = {"type": typ, "value": value}
            result[s.attrib["name"]] = cells
        return result


def money_cents(raw):
    if raw is None or raw in ("", "n/a", "N/A"):
        return None
    try:
        amount = Decimal(str(raw)) * 100
    except InvalidOperation as e:
        raise ValueError("Invalid source money") from e
    if not amount.is_finite() or amount < 0:
        raise ValueError("Source amount requires precision or sign review")
    nearest = amount.to_integral_value()
    # XLSX numeric cells contain IEEE-style tails (e.g. 78.43000000000001).
    # Preserve their lexical source values in raw; this tolerance is 1e-10 USD,
    # not a premium/billing rounding rule. Material sub-cent values still fail.
    if abs(amount - nearest) > Decimal("0.00000001"):
        raise ValueError("Source amount requires precision or sign review")
    return int(nearest)


def parse_scenario(label):
    match = re.fullmatch(r"Client Name or Quote Label - (\d+) - (Female|Male) - (Non-Tobacco|Tobacco User) - ZIP: (\d{5}) - ([A-Za-z]+ \d{1,2}, \d{4})", label or "")
    if not match:
        raise ValueError("Unexpected or non-anonymous scenario label")
    age, gender, tobacco, zipcode, date = match.groups()
    requested = datetime.strptime(date, "%B %d, %Y").date().isoformat()
    if not requested.startswith("2026-"):
        raise ValueError("Wrong reference year")
    return {"age": int(age), "gender": gender, "tobacco": tobacco,
            "source_label": label,
            "zip": zipcode, "requested_effective_date": requested,
            "fictional": True}


def normalize(raw, scenario, variant, source_hash, sheet, row):
    county = raw["County"]
    if not isinstance(county, str) or not re.fullmatch(r"[A-Z]+(?: [A-Z]+)*(?:;[A-Z]+(?: [A-Z]+)*)*", county):
        raise ValueError("Malformed source county list")
    counties = county.split(";")
    if "COLLIER" not in counties or len(set(counties)) != len(counties):
        raise ValueError("Unexpected source county")
    if not re.fullmatch(r"\d{5}", raw["NAIC"] or ""):
        raise ValueError("Missing or malformed NAIC")
    if raw["Med Select"] not in (None, "", "Yes"):
        raise ValueError("Unrecognized SELECT indicator")
    effective = datetime.strptime(raw["Effective Date"], "%B %d, %Y").date().isoformat()
    locator = f"{sheet}!A{row}:Q{row}"
    return {
        "id": hashlib.sha256(f"{source_hash}:{locator}".encode()).hexdigest(),
        "source_sha256": source_hash, "sheet": sheet, "row": row,
        "source_locator": locator, "scenario": scenario, "variant": variant,
        "standardized_variant": {"HDF": "F*", "HDG": "G*"}.get(variant, variant),
        "company_name_raw": raw["Company"], "naic": raw["NAIC"],
        "county_fips": "12021", "county_basis": "Exact COLLIER membership in CSG export County cell",
        "source_county_names": counties,
        "monthly_cents": money_cents(raw["Monthly Rate"]),
        "annual_cents": money_cents(raw["Annual Rate"]),
        "monthly_with_discounts_cents": money_cents(raw["Monthly Rate With Discounts"]),
        "annual_with_discounts_cents": money_cents(raw["Annual Rate With Discounts"]),
        "rating_class_raw": raw["Rating Class"], "rating_type_raw": raw["Rate Type"],
        "select_observed": True if raw["Med Select"] == "Yes" else None,
        "source_effective_date": effective, "effective_end": None,
        "policy_form": None, "policy_edition": None, "sale_status": "quote_observed_only",
        "discount_eligibility": "not_determined", "policy_fee_timing": "not_determined",
        "numeric_tail_fields": [key for key in ("Monthly Rate", "Annual Rate", "Monthly Rate With Discounts", "Annual Rate With Discounts") if raw[key] not in (None, "", "n/a", "N/A") and Decimal(raw[key])*100 != Decimal(money_cents(raw[key]))],
        "personal_quote": False, "consumer_release": "held", "holds": HOLDS,
        "raw": raw,
    }


def build(inputs, output):
    output = Path(output)
    if output.exists():
        raise ValueError("Output already exists; use a new candidate revision")
    records, sources, benefits = [], [], []
    expected_sheets = {f"Plan {v} {kind}" for v in VARIANTS for kind in ("Rates", "Details")}
    for path in sorted(Path(inputs).glob("*.xlsx")):
        before = digest(path)
        sheets = cells_from_xlsx(path)
        if set(sheets) != expected_sheets:
            raise ValueError("Missing or unexpected plan sheets")
        scenarios = []
        counts = {}
        for variant in VARIANTS:
            name = f"Plan {variant} Rates"
            cells = sheets[name]
            value = lambda address: cells.get(address, {}).get("value")
            if [value(f"{chr(65+i)}10") for i in range(17)] != HEADERS:
                raise ValueError("Unexpected rate schema")
            scenario = parse_scenario(value("A7"))
            scenarios.append(scenario)
            rows = sorted({int(re.search(r"\d+$", a).group()) for a in cells if int(re.search(r"\d+$", a).group()) > 10})
            counts[variant] = 0
            for row in rows:
                values = [value(f"{chr(65+i)}{row}") for i in range(17)]
                if all(v is None for v in values):
                    continue
                records.append(normalize(dict(zip(HEADERS, values)), scenario, variant, before, name, row))
                counts[variant] += 1
            detail = f"Plan {variant} Details"
            benefits.append({"source_sha256": before, "sheet": detail, "variant": variant,
                             "cells": sheets[detail], "consumer_release": "held",
                             "meaning": "CSG benefit text; not a replacement for accepted federal constants"})
        if any(s != scenarios[0] for s in scenarios):
            raise ValueError("Conflicting scenario labels across sheets")
        if before != digest(path):
            raise ValueError("Source changed while reading")
        sources.append({"filename": path.name, "sha256": before, "bytes": path.stat().st_size,
                        "scenario": scenarios[0], "rate_counts": counts, "sheets": 24})
    if not sources:
        raise ValueError("No completed XLSX sources")
    if len({json.dumps(s["scenario"], sort_keys=True) for s in sources}) != len(sources):
        raise ValueError("Duplicate scenario export; reconcile explicitly")
    for source in sources:
        if digest(Path(inputs) / source["filename"]) != source["sha256"]:
            raise ValueError("Source changed before candidate write")
    output.mkdir(parents=True)
    with (output / "rates.jsonl").open("x") as f:
        for record in records:
            f.write(json.dumps(record, sort_keys=True) + "\n")
    (output / "benefit-observations.json").write_text(json.dumps(benefits, indent=2) + "\n")
    with sqlite3.connect(output / "research.sqlite3") as db:
        db.execute("CREATE TABLE rate_observations (id TEXT PRIMARY KEY, source_sha256 TEXT NOT NULL, variant TEXT NOT NULL, naic TEXT NOT NULL, zip TEXT NOT NULL, age INTEGER NOT NULL, gender TEXT NOT NULL, tobacco TEXT NOT NULL, requested_date TEXT NOT NULL, monthly_cents INTEGER, annual_cents INTEGER, payload TEXT NOT NULL)")
        db.executemany("INSERT INTO rate_observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", [
            (r["id"], r["source_sha256"], r["variant"], r["naic"], r["scenario"]["zip"], r["scenario"]["age"], r["scenario"]["gender"], r["scenario"]["tobacco"], r["scenario"]["requested_effective_date"], r["monthly_cents"], r["annual_cents"], json.dumps(r, sort_keys=True)) for r in records])
        db.execute("CREATE INDEX scenario_lookup ON rate_observations(zip,age,gender,tobacco,requested_date,variant)")
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("SELECT COUNT(*) FROM rate_observations").fetchone()[0] == len(records)
    report = {"schema": "csg-medigap-private-candidate/1", "source_count": len(sources),
              "sources": sources, "rate_rows": len(records), "legal_company_naics": len({r["naic"] for r in records}),
              "counts_by_variant": dict(Counter(r["variant"] for r in records)),
              "select_yes_rows": sum(r["select_observed"] is True for r in records),
              "annual_amount_unknown_rows": sum(r["annual_cents"] is None for r in records),
              "numeric_tail_cells": sum(len(r["numeric_tail_fields"]) for r in records),
              "monthly_times_12_differs_from_source_annual_rows": sum(r["annual_cents"] is not None and r["monthly_cents"] is not None and r["monthly_cents"]*12 != r["annual_cents"] for r in records),
              "all_market_complete": False, "consumer_release": "held", "holds": HOLDS,
              "benefit_sheets": len(benefits), "code_sha256": digest(__file__),
              "files": {p.name: digest(p) for p in output.iterdir() if p.is_file()}}
    (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k:v for k,v in report.items() if k not in ("sources", "files", "holds")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    build(args.inputs, args.output)
