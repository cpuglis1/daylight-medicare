#!/usr/bin/env python3
"""Narrow, reproducible carrier-document corroboration for the inspected Naples sample."""

import argparse
from collections import Counter
from decimal import Decimal
import html
import json
from pathlib import Path
import re
import subprocess
import urllib.request
from datetime import datetime, timezone

import cms_slice as cms

ROOT = cms.ROOT
CONFIG = ROOT / "data-sources/validation.json"
AMOUNT = r"\$\d[\d,]*(?:\.\d{2})?"


def compact(text):
    return " ".join(text.split())


def pdf_pages(path):
    result = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, check=True)
    return result.stdout.decode("utf-8").split("\f")


def context_errors(pages, record, year):
    cover = compact(pages[0])
    errors = []
    if not re.search(rf"\b{year} Summary of Benefits\b", cover) or not re.search(rf"1/1/{year}\s*[–-]\s*12/31/{year}", cover):
        errors.append("benefit_year_mismatch")
    ident = record["identity"]
    if f"{ident['contract']}-{ident['plan']}" not in re.findall(r"\b[A-Z]\d{4}-\d{3}\b", cover):
        errors.append("plan_identity_mismatch")
    if record["landscape_raw"]["County Name"] == "All Counties":
        if "State of Florida" not in cover:
            errors.append("geography_mismatch")
    elif not re.search(r"\bCollier\b", cover):
        errors.append("geography_mismatch")
    return errors


def pdf_amount(text, pattern):
    match = re.search(pattern, compact(text))
    if not match:
        raise cms.SourceError("Inspected PDF field anchor changed; no generic extraction fallback")
    raw = match.group(1)
    return {"raw": raw, "value_cents": int(Decimal(raw.replace("$", "").replace(",", "")) * 100)}


def observed_money(pages, record, spec):
    text = pages[2]
    category = record["landscape_raw"]["Contract Category Type"]
    if category == "PDP":
        headers = [re.findall(r"S\d{4}-\d{3}", line) for line in text.splitlines()]
        if spec.get("columns") not in headers:
            raise cms.SourceError("PDP column identity/order changed; refuse adjacent-plan substitution")
        index = spec["columns"].index(record["identity"]["contract"] + "-" + record["identity"]["plan"])
        found = {}
        for key, label in (("part_d_total_premium", "Monthly Plan Premium"), ("annual_part_d_deductible", "Deductible")):
            lines = [line for line in text.splitlines() if line.strip().startswith(label)]
            if len(lines) != 1:
                raise cms.SourceError("Ambiguous PDP benefit row")
            values = re.findall(AMOUNT, lines[0])
            if len(values) != len(spec["columns"]):
                raise cms.SourceError("PDP monetary column count changed")
            raw = values[index]
            found[key] = {"raw": raw, "value_cents": int(Decimal(raw.replace("$", "").replace(",", "")) * 100), "source_column": index + 1}
        return found
    premium_field = "part_c_premium" if category == "MA" else "consolidated_premium"
    premium_lines = [line for line in text.splitlines() if line.strip().startswith("Monthly Plan")]
    if len(premium_lines) != 1 or "•" not in premium_lines[0]:
        raise cms.SourceError("Single-plan table column anchor changed")
    detail_start = premium_lines[0].index("•")
    # The inspected table has left-column row labels interleaved with wrapped right-column text.
    # Keep the full page for the premium label; isolate the measured right column for the MOOP sentence.
    detail_text = "\n".join(line[detail_start:] for line in text.splitlines())
    found = {
        premium_field: pdf_amount(text, rf"Monthly Plan\s+[•·]?\s*({AMOUNT})"),
        "in_network_medical_moop": pdf_amount(detail_text, rf"({AMOUNT}) is the most you pay for Medicare-covered medical services from in-network providers for the year"),
    }
    if category == "MA-PD":
        found["annual_part_d_deductible"] = pdf_amount(text, rf"({AMOUNT}) per year for Part D prescription drugs")
    return found


def verify_inputs(config, root=ROOT):
    for name, spec in config["artifacts"].items():
        path = root / spec["path"]
        if not path.is_file() or path.stat().st_size != spec["bytes"] or cms.file_hash(path) != spec["sha256"]:
            raise cms.SourceError(f"Missing/changed validation artifact {name}; run validation fetch or recover pinned bytes")
        if "discovery_page" in spec:
            page_spec = config["artifacts"][spec["discovery_page"]]
            page = html.unescape((root / page_spec["path"]).read_text())
            if spec["url"] not in page:
                raise cms.SourceError(f"Carrier discovery page does not link {name}")


def fetch(config):
    for name, spec in config["artifacts"].items():
        path = ROOT / spec["path"]
        if path.exists():
            if path.stat().st_size != spec["bytes"] or cms.file_hash(path) != spec["sha256"]:
                raise cms.SourceError(f"Changed cached validation artifact {name}; not overwritten")
            print(f"Verified cached {name}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(spec["url"], timeout=60) as response:
            raw = response.read(spec["bytes"] + 1)
            receipt = {"url": spec["url"], "final_url": response.url, "received_at_utc": datetime.now(timezone.utc).isoformat(),
                       "sha256": cms.sha256(raw), "bytes": len(raw), "content_type": response.headers.get("Content-Type")}
        if len(raw) != spec["bytes"] or cms.sha256(raw) != spec["sha256"]:
            raise cms.SourceError(f"Mutable validation URL changed for {name}; inspect a new snapshot before accepting")
        path.write_bytes(raw)
        cms.write_json(path.with_suffix(path.suffix + ".receipt.json"), receipt)
        print(f"Downloaded and verified {name}")


def validate(config, catalog, root=ROOT):
    if catalog["release_id"] != config["release_id"] or catalog["benefit_year"] != config["year"] or catalog["market"]["county_fips"] != config["county_fips"]:
        raise cms.SourceError("Validation/catalog release, year or county mismatch")
    verify_inputs(config, root)
    records = {(r["identity"]["contract"], r["identity"]["plan"], r["identity"]["segment_join"]): r for r in catalog["options"] + catalog["exclusions"]}
    documents = {name: pdf_pages(root / spec["path"]) for name, spec in config["artifacts"].items() if spec["path"].endswith(".pdf")}
    samples = []
    for sample in config["samples"]:
        record = records[(sample["contract"], sample["plan"], sample["segment"])]
        spec = config["artifacts"][sample["document"]]
        pages = documents[sample["document"]]
        errors = context_errors(pages, record, config["year"])
        if errors:
            raise cms.SourceError(f"Positive carrier candidate rejected: {sample}: {errors}")
        cover = compact(pages[0])
        category = record["landscape_raw"]["Contract Category Type"]
        category_phrase = {"MA": "Medicare Advantage Plan without Part D Prescription Drug Coverage",
                           "MA-PD": "Medicare Advantage Plan with Part D Prescription Drug Coverage",
                           "PDP": "Medicare Prescription Drug Plans"}[category]
        if category_phrase not in cover or record["landscape_raw"]["Plan Name"] not in cover:
            raise cms.SourceError("Plan name/type/category differs in carrier cover; inspect before continuing")
        comparisons = []
        for field, observed in observed_money(pages, record, spec).items():
            cms_fact = record["facts"][field]
            comparisons.append({"field": field, "status": "agrees" if cms_fact["value_cents"] == observed["value_cents"] else "conflict",
                                "cms": cms_fact, "carrier": {**observed, "pdf_page": 3, "url": spec["url"], "sha256": spec["sha256"]}})
        samples.append({"identity": record["identity"], "name": record["landscape_raw"]["Plan Name"], "category": category,
                        "document": sample["document"], "cover_checks": {"benefit_year": "agrees", "contract_plan": "agrees", "geography": "agrees", "name_type_category": "agrees"},
                        "segment_corroboration": "Not printed in carrier summary; CMS 000 payload join remains the segment evidence",
                        "money_checks": comparisons,
                        "uncompared_monetary_fields": [f for f in record["facts"] if "value_cents" in record["facts"][f] and f not in {c["field"] for c in comparisons}]})
    negatives = []
    for candidate in config["negative_candidates"]:
        record = records[(candidate["contract"], candidate["plan"], candidate["segment"])]
        errors = context_errors(documents[candidate["document"]], record, config["year"])
        if errors != candidate["expected_errors"]:
            raise cms.SourceError(f"Negative carrier candidate no longer rejects as inspected: {candidate}: {errors}")
        negatives.append({**candidate, "observed_errors": errors, "status": "rejected"})
    statuses = Counter(check["status"] for sample in samples for check in sample["money_checks"])
    return {"validation_id": config["validation_id"], "release_id": config["release_id"], "year": config["year"], "county_fips": config["county_fips"],
            "status": "sample_conflicts_require_review" if statuses["conflict"] else "sample_corroborated_with_open_gates",
            "counts": {"sample_records": len(samples), "source_market_records": len(records), "unsampled_records": len(records) - len(samples),
                       "carrier_document_pdfs_used": len({s["document"] for s in config["samples"]}), "monetary_checks": sum(statuses.values()),
                       "monetary_agreements": statuses["agrees"], "monetary_conflicts": statuses["conflict"], "negative_candidates_rejected": len(negatives)},
            "sampling": config["sampling"], "review": config["review"], "artifacts": config["artifacts"],
            "samples": samples, "candidate_rejections": negatives, "limits": config["limits"],
            "display_decisions": ["Published plan premium uses consolidated C+D for MA-PD, Part C for MA-only and Part D total for PDP; these are different source fields, never a synthesized quote",
                                  "Keep inapplicable C+D/Part D fields in their original states; no zero substitution",
                                  "A Part D deductible needs a tier/drug applicability note; a published amount is not medicine-specific evidence",
                                  "Medical MOOP is scoped to medical services and excludes premiums/drug costs; do not label it an all-in annual cap",
                                  "No sample result upgrades other fields, unsampled plans, opaque PBP codes, rankings or purchase readiness"],
            "input_hashes": {"validation_config": cms.file_hash(root / "data-sources/validation.json"), "validator_script": cms.file_hash(__file__),
                             "catalog": cms.file_hash(root / f"reports/work-package-1/market-{config['county_fips']}-{config['year']}.json")}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["fetch", "run"])
    parser.add_argument("--out", type=Path, default=ROOT / "reports/work-package-2/validation.json")
    args = parser.parse_args()
    try:
        config = cms.load_json(CONFIG)
        if args.command == "fetch":
            fetch(config)
        else:
            sources = cms.Sources()
            cms.verify_report(sources, ROOT / "reports/work-package-1")
            catalog = cms.load_json(ROOT / f"reports/work-package-1/market-{config['county_fips']}-{config['year']}.json")
            report = validate(config, catalog)
            cms.write_json(args.out, report)
            print(json.dumps({"report": str(args.out), "status": report["status"], "counts": report["counts"]}, indent=2))
            return 1 if report["counts"]["monetary_conflicts"] else 0
    except (cms.SourceError, OSError, KeyError, ValueError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
