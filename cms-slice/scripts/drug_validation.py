#!/usr/bin/env python3
"""Reproduce a narrow carrier/NLM/CMS drug sample without treating quantity numbers as units."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlencode
from zipfile import ZipFile

import cms_slice as cms
from evidence_store import PublicSources
import prescription as rx
import reference_evidence as references

CONFIG = cms.ROOT / "data-sources/drug-validation.json"
OUT = cms.ROOT / "reports/drug-validation.json"
MANIFEST = OUT.with_name("drug-validation-manifest.json")
FIELDS = {"tier": "TIER_LEVEL_VALUE", "prior_authorization_marked": "PRIOR_AUTHORIZATION_YN",
          "step_therapy_marked": "STEP_THERAPY_YN", "quantity_limit_marked": "QUANTITY_LIMIT_YN", "days": "QUANTITY_LIMIT_DAYS"}


def carrier_row(page, row_name):
    matches = [line for line in page.splitlines() if re.match(re.escape(row_name)+r"\s{2,}", line)]
    if len(matches) != 1:
        raise cms.SourceError("Exact carrier product row is absent/ambiguous: "+row_name)
    match = re.fullmatch(re.escape(row_name)+r"\s+(\d+)\s+(?:(PA), )?QL \((\d+) (tablets|pens|vials)/(\d+) days\)\s*", matches[0])
    if not match:
        raise cms.SourceError("Uninspected carrier row format: "+row_name)
    return {"tier": match[1], "prior_authorization_marked": "Y" if match[2] else "N", "step_therapy_marked": "N",
            "quantity_limit_marked": "Y", "quantity": match[3], "quantity_unit": match[4], "days": match[5],
            "raw_line": matches[0].strip(), "meaning": "Symbols printed for this product row, not clinical approval or an exhaustive coverage decision"}


def replay_rows(config, rows):
    spec = config["members"]["formulary"]
    nested = rx.prepare(config)
    remaining = {item["evidence"]["source_row"]: item["raw"] for item in rows}
    ordinals = sorted(remaining)
    with ZipFile(nested / spec["outer_member"]) as archive, archive.open(spec["inner_member"]) as stream:
        header = stream.readline().decode("ascii").rstrip("\r\n").split("|")
        if header != spec["columns"]:
            raise cms.SourceError("National formulary header changed")
        for ordinal, line in enumerate(stream, 2):
            if ordinal in remaining:
                cells = line.decode(spec["encoding"]).rstrip("\r\n").split("|")
                if len(cells) != len(header) or dict(zip(header, cells)) != remaining.pop(ordinal):
                    raise cms.SourceError("Captured drug row differs from original national source")
            if not remaining:
                break
    if remaining:
        raise cms.SourceError("Drug sample source ordinals not found")
    return {"status": "all_selected_raw_cells_replayed", "rows": len(ordinals), "source_ordinals": ordinals,
            "nested_sha256": spec["nested_sha256"]}


def build(config_path=CONFIG, out=OUT, manifest_path=MANIFEST, sources=None):
    config, rx_config = cms.load_json(config_path), cms.load_json(rx.CONFIG)
    report = rx.verify(rx_config)
    ref_config = cms.load_json(references.CONFIG)
    references.verify(ref_config)
    sources = sources or PublicSources()
    spec = ref_config["artifacts"]["carrier_formulary"]
    pdf = cms.ROOT / spec["path"]
    pages = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], check=True, capture_output=True).stdout.decode().split("\f")
    if not all(t in pages[0] for t in ("2027", config["formulary_id"], "H5434-002, 045", "10/15/2026")):
        raise cms.SourceError("Carrier scope/year/formulary/date changed")
    joins = {j["id"]: j for j in report["joins"]}
    if any(joins[p]["selected_plan"]["raw"]["FORMULARY_ID"] != config["formulary_id"] for p in config["plan_ids"]):
        raise cms.SourceError("Drug sample plan/formulary join changed")
    wanted = {c["rxcui"] for c in config["cases"]}
    if len(wanted) != len(config["cases"]):
        raise cms.SourceError("Duplicate drug sample identity")
    rows = [{"evidence": e, "raw": r} for e, r in rx.captured_rows(rx.CACHE / "formulary.psv.gz")
            if r["FORMULARY_ID"] == config["formulary_id"] and r["RXCUI"] in wanted and r["CONTRACT_YEAR"] == "2027"]
    replay = replay_rows(rx_config, rows)
    cases, statuses, vocab_hashes = [], Counter(), {}
    for case in config["cases"]:
        url = "https://rxnav.nlm.nih.gov/REST/drugs.json?"+urlencode({"name": case["query"]})
        source_id = "rxnorm-"+cms.sha256(url.encode())[:16]
        vocab_spec, payload = sources.json(source_id)
        vocab_hashes[source_id] = vocab_spec["sha256"]
        candidates = [x for g in payload.get("drugGroup", {}).get("conceptGroup", []) for x in g.get("conceptProperties", []) or [] if x["rxcui"] == case["rxcui"] and x["name"] == case["vocabulary_name"]]
        if len(candidates) != 1:
            raise cms.SourceError("Exact vocabulary product identity changed")
        carrier = carrier_row(pages[case["pdf_page"]-1], case["row_name"])
        matched = [r for r in rows if r["raw"]["RXCUI"] == case["rxcui"]]
        if not matched:
            raise cms.SourceError("Sample product absent in basic capture; investigate rather than call it noncovered")
        checked = []
        for item in matched:
            checks = {field: "agrees" if carrier[field] == item["raw"][column] else "conflict" for field, column in FIELDS.items()}
            statuses.update(checks.values())
            checked.append({**item, "checks": checks, "quantity_comparison": {
                "cms_raw_amount": item["raw"]["QUANTITY_LIMIT_AMOUNT"], "cms_unit": None,
                "carrier_amount": carrier["quantity"], "carrier_unit": carrier["quantity_unit"],
                "numeric_amounts_equal": carrier["quantity"] == item["raw"]["QUANTITY_LIMIT_AMOUNT"],
                "status": "unit_unresolved_no_conversion_or_quantity_acceptance"}})
        cases.append({**case, "vocabulary_source": PublicSources.evidence(vocab_spec), "carrier": carrier, "cms_rows": checked})
    result = {"benefit_year": "2027", "county_fips": "12021", "formulary_id": config["formulary_id"], "plan_ids": config["plan_ids"],
              "carrier_source": spec, "visual_review": config["visual_review"], "product_cases": len(cases), "check_status_counts": dict(statuses),
              "source_replay": replay, "cases": cases, "domain_signoff": "pending", "live_personal_prices": "unavailable",
              "limits": ["One carrier/formulary only; no extrapolation to other products, formularies or complete plan coverage",
                         "Tier/PA/ST/QL/days symbols only; no authorization criteria, positive step-therapy sample or independent noncoverage decision",
                         "The PDF does not print NDCs; NLM connects selected RxCUI identity, not package interchangeability",
                         "All raw quantity units remain unresolved, even when the numbers happen to match"]}
    cms.write_json(out, result)
    cms.write_json(manifest_path, {"output_sha256": cms.file_hash(out), "code_sha256": cms.file_hash(__file__),
                                  "config_sha256": cms.file_hash(config_path), "rx_manifest_sha256": cms.file_hash(rx.REPORTS / "manifest.json"),
                                  "reference_manifest_sha256": cms.file_hash(references.REPORTS / "manifest.json"), "vocabulary_sources": vocab_hashes})
    if statuses["conflict"]:
        raise cms.SourceError("Drug sample conflict; preserve and investigate affected evidence")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    result = build()
    print(json.dumps({k: result[k] for k in ("product_cases", "check_status_counts", "source_replay", "domain_signoff")}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (cms.SourceError, OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        raise SystemExit("Drug validation unavailable: "+str(error))
