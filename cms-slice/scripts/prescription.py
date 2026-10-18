#!/usr/bin/env python3
"""Pinned 2027 Part D evidence: inspect, capture Collier rows, and query exact identifiers."""

import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import urllib.request
from zipfile import ZipFile

import cms_slice as cms

ROOT = cms.ROOT
CONFIG = ROOT / "data-sources/prescription.json"
REPORTS = ROOT / "reports/work-package-3"
CACHE = ROOT / "data-sources/raw/prescription/market-cache"
IDENTITY = ("CONTRACT_ID", "PLAN_ID", "SEGMENT_ID")


def identity(row):
    return tuple(row[k] for k in IDENTITY)


def record_key(record):
    r = record["identity"]
    return r["contract"], r["plan"], r["segment_join"]


def option_id(key, year="2027"):
    return "-".join((*key, year))


def raw_state(value):
    if value is None:
        return "absent"
    if value == "":
        return "empty"
    if value.isspace():
        return "blank_space"
    return "reported"


def cost_share(row, suffix):
    """Interpret type before amount; preserve raw zero even when service is not offered."""
    kind = row.get("COST_TYPE_" + suffix)
    amount = row.get("COST_AMT_" + suffix)
    result = {"raw_type": kind, "raw_amount": amount, "raw_amount_state": raw_state(amount),
              "raw_minimum": row.get("COST_MIN_AMT_" + suffix), "raw_maximum": row.get("COST_MAX_AMT_" + suffix)}
    if kind == "0":
        return {**result, "status": "not_offered", "value": None}
    if kind not in {"1", "2"}:
        return {**result, "status": "unknown_type", "value": None}
    if raw_state(amount) != "reported":
        return {**result, "status": "missing_amount", "value": None}
    try:
        value = Decimal(amount)
        if not value.is_finite() or value < 0 or (kind == "2" and value > 1):
            raise InvalidOperation
    except InvalidOperation:
        return {**result, "status": "rejected_amount", "value": None}
    return {**result, "status": "copay" if kind == "1" else "coinsurance",
            "unit": "USD" if kind == "1" else "fraction", "value": str(value)}


def pharmacy_number(npi):
    if not re.fullmatch(r"\d{10}", npi):
        raise cms.SourceError("Specify the exact 10-digit NPI as a string; no name/ZIP substitution")
    return "10" + npi


def verify_file(path, spec):
    if not path.is_file() or path.stat().st_size != spec["bytes"] or cms.file_hash(path) != spec["sha256"]:
        raise cms.SourceError(f"Missing or changed pinned artifact: {path}")


def fetch(config):
    for spec in [config["source"], *config["documentation"].values()]:
        path = ROOT / spec["path"]
        if path.exists():
            verify_file(path, spec)
            print("Verified cached", path.name, flush=True)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".partial")
        digest = hashlib.sha256()
        size = 0
        with urllib.request.urlopen(spec["url"], timeout=60) as response, temporary.open("wb") as output:
            while block := response.read(4 * 1024 * 1024):
                size += len(block)
                if size > spec["bytes"]:
                    raise cms.SourceError("Pinned source size exceeded; inspect a new release")
                digest.update(block)
                output.write(block)
            receipt = {"url": spec["url"], "final_url": response.url, "bytes": size, "sha256": digest.hexdigest(),
                       "received_at_utc": datetime.now(timezone.utc).isoformat(), "headers": dict(response.headers)}
        if size != spec["bytes"] or digest.hexdigest() != spec["sha256"]:
            raise cms.SourceError("Pinned source changed; partial bytes retained, existing evidence not replaced")
        os.replace(temporary, path)
        cms.write_json(path.with_suffix(path.suffix + ".receipt.json"), receipt)
        print("Downloaded and verified", path.name, flush=True)


def prepare(config):
    verify_file(ROOT / config["source"]["path"], config["source"])
    for spec in config["documentation"].values():
        verify_file(ROOT / spec["path"], spec)
    nested = ROOT / "data-sources/raw/prescription/nested"
    nested.mkdir(parents=True, exist_ok=True)
    with ZipFile(ROOT / config["source"]["path"]) as archive:
        for spec in config["members"].values():
            path = nested / spec["outer_member"]
            pin = {"bytes": spec["nested_bytes"], "sha256": spec["nested_sha256"]}
            if not path.exists():
                temporary = path.with_suffix(".zip.partial")
                with archive.open(spec["outer_member"]) as source, temporary.open("wb") as target:
                    shutil.copyfileobj(source, target)
                verify_file(temporary, pin)
                os.replace(temporary, path)
            verify_file(path, pin)
    return nested


def source_rows(config, nested, table, stats, wanted_keys=None):
    spec = config["members"][table]
    digest = hashlib.sha256()
    non_ascii = Counter()
    count = 0
    with ZipFile(nested / spec["outer_member"]) as archive:
        if archive.getinfo(spec["inner_member"]).file_size != spec["uncompressed_bytes"]:
            raise cms.SourceError("Inner file size changed")
        with archive.open(spec["inner_member"]) as source:
            header = source.readline()
            digest.update(header)
            if header.rstrip(b"\r\n").decode("ascii").split("|") != spec["columns"]:
                raise cms.SourceError(f"Inspected header changed: {table}")
            for ordinal, line in enumerate(source, 2):
                digest.update(line)
                # Raw delimiters/line endings are retained in the capture. No trim/coercion.
                if line.count(b"|") != len(spec["columns"]) - 1:
                    raise cms.SourceError(f"Malformed {table} row {ordinal}")
                count += 1
                if not line.isascii():
                    non_ascii.update(b for b in line if b > 127)
                if wanted_keys is not None and tuple(line.split(b"|", 3)[:3]) not in wanted_keys:
                    continue
                cells = line.rstrip(b"\r\n").split(b"|")
                yield ordinal, dict(zip(spec["columns"], (c.decode(spec["encoding"]) for c in cells))), line
    stats[table] = {"rows": count, "uncompressed_sha256": digest.hexdigest(), "non_ascii_bytes": dict(non_ascii),
                    "outer_member": spec["outer_member"], "inner_member": spec["inner_member"], "encoding": spec["encoding"],
                    "columns": spec["columns"]}


def market_plan(row, geography):
    if row["CONTRACT_ID"].startswith("H"):
        return row["STATE"] == "FL" and row["COUNTY_CODE"] == geography["COUNTY_CODE"]
    if row["CONTRACT_ID"].startswith("R"):
        return row["MA_REGION_CODE"] == geography["MA_REGION_CODE"]
    if row["CONTRACT_ID"].startswith("S"):
        return row["PDP_REGION_CODE"] == geography["PDP_REGION_CODE"]
    return False


def gzip_writer(stack, path, columns):
    raw = stack.enter_context(path.open("wb"))
    output = stack.enter_context(gzip.GzipFile(filename="", fileobj=raw, mode="wb", compresslevel=1, mtime=0))
    output.write(("source_table|source_row|" + "|".join(columns) + "\r\n").encode("ascii"))
    return output


def captured_rows(path, encoding="ascii"):
    with gzip.open(path, "rt", encoding=encoding, newline="") as source:
        columns = source.readline().rstrip("\r\n").split("|")
        for line in source:
            cells = line.rstrip("\r\n").split("|")
            if len(cells) != len(columns):
                raise cms.SourceError("Captured row shape changed")
            row = dict(zip(columns, cells))
            yield {"table": row.pop("source_table"), "source_row": int(row.pop("source_row"))}, row


def build(config, out=REPORTS, cache=CACHE):
    cms.verify_report(cms.Sources(), ROOT / "reports/work-package-1")
    nested = prepare(config)
    catalog_path = ROOT / "reports/work-package-1/market-12021-2027.json"
    catalog = cms.load_json(catalog_path)
    if catalog["benefit_year"] != config["benefit_year"] or catalog["market"]["county_fips"] != config["county_fips"]:
        raise cms.SourceError("Market/release mismatch")
    records = {record_key(r): r for r in catalog["options"] + catalog["exclusions"]}
    stats = {}
    geographies = [(n, r) for n, r, _ in source_rows(config, nested, "geography", stats)
                  if r["COUNTY"] == "Collier" and r["STATENAME"] == "Florida"]
    if len(geographies) != 1 or any(geographies[0][1][k] != v for k, v in config["geography_match"].items()):
        raise cms.SourceError("Collier SSA geography is missing/ambiguous/changed; never use FIPS in SSA field")
    geo_ordinal, geography = geographies[0]
    selected = defaultdict(list)
    full_plan_keys = Counter()
    market_contract_plans = {k[:2] for k in records}
    for ordinal, row, _ in source_rows(config, nested, "plan", stats):
        full_plan_keys[identity(row)] += 1
        if identity(row) in records and market_plan(row, geography):
            selected[identity(row)].append({"source_row": ordinal, "raw": row})
    if any(len(rows) != 1 for rows in selected.values()):
        raise cms.SourceError("Plan+segment+geography join is ambiguous; do not pick a row")
    plan_rows = {key: rows[0] for key, rows in selected.items()}
    premium_variants = defaultdict(Counter)
    alternate_segments = Counter()
    for _, row, _ in source_rows(config, nested, "plan", {}):
        key = identity(row)
        if key in plan_rows:
            premium_variants[key][row["PREMIUM"]] += 1
        if key[:2] in market_contract_plans and key not in records:
            alternate_segments[key[:2]] += 1
    active = {key for key, row in plan_rows.items() if row["raw"]["PLAN_SUPPRESSED_YN"] == "N"}
    active_contract_plans = {k[:2] for k in active}
    forms = {plan_rows[key]["raw"]["FORMULARY_ID"] for key in active}
    joins = []
    discrepancies = []
    comparison_totals = Counter()
    for key, record in sorted(records.items()):
        plan = plan_rows.get(key)
        drug = record["landscape_raw"]["Part D Coverage Indicator"]
        checks = {}
        if plan:
            for puf_field, landscape_field in (("PREMIUM", "Part D Total Premium"), ("DEDUCTIBLE", "Annual Part D Deductible Amount")):
                try:
                    agrees = Decimal(plan["raw"][puf_field]) == Decimal(record["landscape_raw"][landscape_field].replace("$", "").replace(",", ""))
                    status = "agrees" if agrees else "conflict"
                except InvalidOperation:
                    status = "not_comparable"
                checks[puf_field] = {"status": status, "puf_raw": plan["raw"][puf_field], "landscape_field": landscape_field,
                                     "landscape_raw": record["landscape_raw"][landscape_field]}
                comparison_totals[status] += 1
        status = "matched" if plan else ("not_applicable_non_part_d" if drug == "No" else "unresolved_missing_part_d_plan")
        joins.append({"id": option_id(key), "comparison_scope": record in catalog["options"], "landscape_part_d_indicator": drug,
                      "status": status, "all_geography_puf_rows_for_identity": full_plan_keys[key], "selected_plan": plan,
                      "cross_source_amount_checks": checks})
        if any(check["status"] == "conflict" for check in checks.values()):
            fields = ("Plan Name", "Contract Category Type", "Part D Basic Premium", "Part D Supplemental Premium", "Part D Total Premium",
                      "Part D LIPS (CMS Pays)", "Part D Low Income Beneficiary Premium Amount", "Part C Premium", "Monthly Consolidated Premium (Part C + D)")
            discrepancies.append({"id": option_id(key), "puf_rows_for_identity": full_plan_keys[key],
                                  "puf_premium_counts": dict(premium_variants[key]), "alternative_segment_rows_same_contract_plan": alternate_segments[key[:2]],
                                  "selected_plan": plan, "landscape_fields": {f: record["landscape_raw"][f] for f in fields},
                                  "landscape_evidence": record["landscape_evidence"],
                                  "disposition": "Exact identity/geography match; values retained. Different release dates and possible premium-basis differences require authoritative clarification. Matching the LIS-adjusted field is an observation, not an approved mapping. Exclusion remains in force."})
    cache = Path(cache)
    out = Path(out)
    cache.parent.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache.parent) as temp:
        staging = Path(temp)
        capture_counts = Counter()
        duplicates = Counter()
        blank_counts = defaultdict(Counter)
        versions = defaultdict(set)
        examples = {}
        seen = set()
        with ExitStack() as stack:
            outputs = {table: gzip_writer(stack, staging / (table + ".psv.gz"), config["members"][table]["columns"])
                       for table in ("formulary", "beneficiary", "excluded", "indication", "insulin")}
            for table in outputs:
                for ordinal, row, raw in source_rows(config, nested, table, stats):
                    if table == "formulary":
                        if row["CONTRACT_YEAR"] != config["benefit_year"]:
                            raise cms.SourceError("Formulary benefit year mismatch")
                        keep = row["FORMULARY_ID"] in forms
                    elif table in {"excluded", "indication"}:
                        keep = (row["CONTRACT_ID"], row["PLAN_ID"]) in active_contract_plans
                    else:
                        keep = identity(row) in active
                    if not keep:
                        continue
                    capture_counts[table] += 1
                    outputs[table].write(table.encode() + b"|" + str(ordinal).encode() + b"|" + raw)
                    for field, value in row.items():
                        if raw_state(value) != "reported":
                            blank_counts[table][field + ":" + raw_state(value)] += 1
                    if table == "formulary":
                        grain = row["FORMULARY_ID"], row["CONTRACT_YEAR"], row["NDC"]
                        if grain in seen:
                            duplicates[table] += 1
                        seen.add(grain)
                        versions[row["FORMULARY_ID"]].add(row["FORMULARY_VERSION"])
                        for label, field in (("prior_authorization", "PRIOR_AUTHORIZATION_YN"), ("quantity_limit", "QUANTITY_LIMIT_YN"),
                                             ("step_therapy", "STEP_THERAPY_YN"), ("selected_drug", "SELECTED_DRUG_YN")):
                            if row[field] == "Y" and label not in examples:
                                examples[label] = {"source_row": ordinal, "raw": row}
                    if table == "beneficiary":
                        for suffix in ("PREF", "NONPREF", "MAIL_PREF", "MAIL_NONPREF"):
                            result = cost_share(row, suffix)
                            label = "cost_" + result["status"]
                            if label not in examples:
                                examples[label] = {"source_row": ordinal, "raw": row, "interpretation": result}
            del seen
            pharmacy_writers = {key: gzip_writer(stack, staging / (option_id(key) + "-pharmacy.psv.gz"), config["members"]["pharmacy_1"]["columns"])
                                for key in sorted(active)}
            pharmacy_seen = defaultdict(set)
            pharmacy_counts = Counter()
            pharmacy_parts = defaultdict(set)
            wanted_keys = {tuple(x.encode() for x in key) for key in active}
            for table in sorted(t for t in config["members"] if t.startswith("pharmacy_")):
                # Each file is streamed; the 23+ GB uncompressed national networks are never expanded to disk.
                for ordinal, row, raw in source_rows(config, nested, table, stats, wanted_keys):
                    key = identity(row)
                    if key not in active:
                        continue
                    number = row["PHARMACY_NUMBER"]
                    if not re.fullmatch(r"10\d{10}", number):
                        raise cms.SourceError("Unexpected pharmacy-number prefix/length; no guessed NPI conversion")
                    if number in pharmacy_seen[key]:
                        duplicates["pharmacy"] += 1
                    pharmacy_seen[key].add(number)
                    pharmacy_counts[option_id(key)] += 1
                    pharmacy_parts[option_id(key)].add(table)
                    capture_counts[table] += 1
                    pharmacy_writers[key].write(table.encode() + b"|" + str(ordinal).encode() + b"|" + raw)
                print("Scanned", table, stats[table]["rows"], "rows; captured", capture_counts[table], flush=True)
        report = {"release_id": config["release_id"], "benefit_year": config["benefit_year"], "county_fips": config["county_fips"],
                  "geography": {"census_fips": config["county_fips"], "puf_ssa": geography, "source_row": geo_ordinal},
                  "counts": {"landscape_records": len(records), "matched_plan_identities": len(plan_rows), "active_unsuppressed": len(active),
                             "unique_formularies": len(forms), "capture_rows": dict(sorted(capture_counts.items())),
                             "pharmacy_rows_by_plan": dict(sorted(pharmacy_counts.items())), "cross_source_amount_checks": dict(comparison_totals)},
                  "pharmacy_parts_by_plan": {k: sorted(v) for k, v in sorted(pharmacy_parts.items())},
                  "joins": joins, "table_inspection": stats, "duplicate_candidate_grains": dict(duplicates),
                  "blank_states": {k: dict(v) for k, v in blank_counts.items()},
                  "formulary_versions": {k: sorted(v) for k, v in sorted(versions.items())}, "real_examples": examples,
                  "date_discrepancy": config["date_discrepancy"], "quarterly_pricing": config["quarterly_pricing"], "limits": config["limits"],
                  "open_gates": ["Publisher clarification of inner date token and layout/encoding differences", "Independent plan-specific drug/restriction confirmation",
                                 "Confirmed medicine/strength/form/quantity/days and exact pharmacy for a real researcher", "Current source-use and freshness review", "No 2027 price source; annual cost/ranking unavailable"]}
        # Copy only after all source scans succeed. Manifest is the last commit marker.
        cache.mkdir(parents=True, exist_ok=True)
        for path in staging.iterdir():
            os.replace(path, cache / path.name)
    cms.write_json(out / "quality.json", report)
    cms.write_json(out / "premium-discrepancies.json", discrepancies)
    manifest = {"release_id": config["release_id"], "code_sha256": cms.file_hash(__file__), "configuration_sha256": cms.file_hash(CONFIG),
                "upstream_sha256": cms.file_hash(catalog_path), "source_sha256": config["source"]["sha256"],
                "quality_sha256": cms.file_hash(out / "quality.json"),
                "premium_discrepancies_sha256": cms.file_hash(out / "premium-discrepancies.json"),
                "cache_sha256": {path.name: cms.file_hash(path) for path in sorted(cache.glob("*.psv.gz"))}}
    cms.write_json(out / "manifest.json", manifest)
    return report


def verify(config, out=REPORTS, cache=CACHE):
    manifest = cms.load_json(Path(out) / "manifest.json")
    if manifest["code_sha256"] != cms.file_hash(__file__) or manifest["configuration_sha256"] != cms.file_hash(CONFIG):
        raise cms.SourceError("Prescription code/config changed; rebuild and review")
    if manifest["upstream_sha256"] != cms.file_hash(ROOT / "reports/work-package-1/market-12021-2027.json"):
        raise cms.SourceError("Upstream market changed")
    if manifest["quality_sha256"] != cms.file_hash(Path(out) / "quality.json"):
        raise cms.SourceError("Prescription quality report changed")
    if manifest["premium_discrepancies_sha256"] != cms.file_hash(Path(out) / "premium-discrepancies.json"):
        raise cms.SourceError("Prescription discrepancy report changed")
    verify_file(ROOT / config["source"]["path"], config["source"])
    for spec in config["documentation"].values():
        verify_file(ROOT / spec["path"], spec)
    for name, digest in manifest["cache_sha256"].items():
        if cms.file_hash(Path(cache) / name) != digest:
            raise cms.SourceError("Captured prescription evidence changed: " + name)
    return cms.load_json(Path(out) / "quality.json")


def query(config, report, reference, ndc=None, rxcui=None, npi=None, cache=CACHE):
    if not re.fullmatch(r"[HRS]\d{4}-\d{3}-\d{3}-2027", reference):
        raise cms.SourceError("Specify the exact 2027 contract-plan-segment identity")
    matches = [r for r in report["joins"] if r["id"] == reference]
    if len(matches) != 1:
        raise cms.SourceError("Plan outside the pinned Collier snapshot")
    if (ndc is None) == (rxcui is None):
        raise cms.SourceError("Specify exactly one exact NDC11 or RxCUI")
    if ndc is not None and not re.fullmatch(r"\d{11}", ndc):
        raise cms.SourceError("NDC must contain exactly 11 digits; no automatic padding or hyphen guessing")
    if rxcui is not None and not re.fullmatch(r"[1-9]\d{0,7}", rxcui):
        raise cms.SourceError("RxCUI must be an exact numeric identifier string")
    number = pharmacy_number(npi) if npi is not None else None
    plan = matches[0]
    response = {"release_id": config["release_id"], "id": reference, "plan_join": plan, "input": {"ndc11": ndc, "rxcui": rxcui, "pharmacy_npi": npi},
                "pricing": {"status": "unavailable_for_2027", "annual_cost": None, "pharmacy_drug_price": None}, "limits": config["limits"],
                "source": config["source"], "source_tables": report["table_inspection"], "date_discrepancy": config["date_discrepancy"]}
    if not plan["selected_plan"]:
        return {**response, "status": plan["status"], "basic_formulary": [], "pharmacy": {"status": "not_applicable_or_missing_source", "rows": []}}
    raw_plan = plan["selected_plan"]["raw"]
    if raw_plan["PLAN_SUPPRESSED_YN"] != "N":
        return {**response, "status": "plan_data_suppressed_or_unknown", "basic_formulary": []}
    form = raw_plan["FORMULARY_ID"]
    basic = [{"evidence": n, "raw": row} for n, row in captured_rows(Path(cache) / "formulary.psv.gz")
             if row["FORMULARY_ID"] == form and (row["NDC"] == ndc if ndc else row["RXCUI"] == rxcui)]
    rxids = {r["raw"]["RXCUI"] for r in basic} | ({rxcui} if rxcui else set())
    supplements = {}
    for table in ("excluded", "indication"):
        supplements[table] = [{"evidence": n, "raw": row} for n, row in captured_rows(Path(cache) / (table + ".psv.gz"))
                              if (row["CONTRACT_ID"], row["PLAN_ID"]) == tuple(reference.split("-")[:2]) and row["RXCUI"] in rxids]
    tiers = {r["raw"]["TIER_LEVEL_VALUE"] for r in basic}
    costs = [{"evidence": n, "raw": row, "cost_shares": {suffix: cost_share(row, suffix) for suffix in ("PREF", "NONPREF", "MAIL_PREF", "MAIL_NONPREF")}}
             for n, row in captured_rows(Path(cache) / "beneficiary.psv.gz")
             if identity(row) == tuple(reference.split("-")[:3]) and row["TIER"] in tiers]
    insulin = [{"evidence": n, "raw": row} for n, row in captured_rows(Path(cache) / "insulin.psv.gz")
               if identity(row) == tuple(reference.split("-")[:3]) and (row["TIER"] in tiers or raw_state(row["TIER"]) != "reported")]
    pharmacy = []
    if number is not None:
        pharmacy = [{"evidence": n, "raw": row} for n, row in captured_rows(Path(cache) / (reference + "-pharmacy.psv.gz")) if row["PHARMACY_NUMBER"] == number]
    return {**response, "status": "listed_with_source_conditions" if basic else "not_listed_in_basic_formulary_not_a_noncoverage_conclusion",
            "basic_formulary": basic, "supplemental_and_indication_rows": supplements, "beneficiary_cost_rows": costs,
            "insulin_cost_rows": insulin,
            "cost_scope": "Plan/tier/phase/days schedules only; not an individual fill or annual cost. Insulin rules require product classification and price evidence before calculation.",
            "supplemental_lookup_status": "rxcui_checked" if rxids else "unresolved_no_rxcui_for_missing_ndc; no supplemental absence conclusion",
            "pharmacy": {"status": ("not_requested" if number is None else "listed_in_pinned_network" if pharmacy else "not_listed_in_pinned_network"), "rows": pharmacy},
            "identity_confirmation": "Exact source-code lookup only; researcher must confirm medicine/strength/form/quantity/days and location; no suitability or purchase conclusion"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["fetch", "build", "verify", "query"])
    parser.add_argument("--plan")
    parser.add_argument("--ndc")
    parser.add_argument("--rxcui")
    parser.add_argument("--pharmacy-npi")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--cache", type=Path, default=CACHE, help="Separate capture directory for an independent build/verify/query")
    parser.add_argument("--report-dir", type=Path, default=REPORTS, help="Manifest/quality directory to verify for a query using --cache")
    args = parser.parse_args()
    try:
        config = cms.load_json(CONFIG)
        if args.command == "fetch":
            fetch(config)
        elif args.command == "build":
            report = build(config, out=args.out or REPORTS, cache=args.cache)
            print(json.dumps(report["counts"], indent=2))
        elif args.command == "verify":
            verify(config, out=args.out or REPORTS, cache=args.cache)
            print("Verified pinned prescription sources, captures and lineage report")
        else:
            report = verify(config, out=args.report_dir, cache=args.cache)
            result = query(config, report, args.plan or "", args.ndc, args.rxcui, args.pharmacy_npi, cache=args.cache)
            if args.out:
                cms.write_json(args.out, result)
            else:
                print(json.dumps(result, indent=2))
    except (cms.SourceError, OSError, ValueError, KeyError) as error:
        print("ERROR:", error)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
