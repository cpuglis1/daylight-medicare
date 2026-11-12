#!/usr/bin/env python3
"""Verified Collier PACE/SHINE resources and non-determinative coordination flags."""

import argparse
import copy
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import re
import subprocess
import zipfile

import cms_slice as cms
from evidence_store import PublicSources, html_text

CONFIG = cms.ROOT / "data-sources/local-programs.json"
REPORTS = cms.ROOT / "reports/collier-gap-20261019/c06-c08"
RAW = cms.ROOT / "data-sources/raw/local-programs"
PATTERNS = {
    "employer_union": r"\b(?:employer|union).{0,40}\b(?:coverage|insurance|health|retiree|plan|benefits)\b|\bretiree\s+(?:coverage|insurance|health|benefits|plan)\b",
    "va": r"\bva\s+(?:health(?:care)?|care|benefits|medical|drug|prescription|clinic|hospital|coverage)\b|\bveterans\s+(?:affairs|health|benefits)\b|\b(?:have|use|receive)\s+va\b",
    "tricare": r"\btricare(?:\s+for\s+life)?\b|\btfl\b",
    "existing_medigap": r"\b(?:my|our|her|his|their|have|has|old|older|existing|keep|drop|cancel|switch|replace).{0,65}\b(?:medigap|medicare supplement)\b|\b(?:medigap|medicare supplement).{0,45}\b(?:policy|older|before|19\d\d|20\d\d)\b",
}
LABELS = {"employer_union": "Employer or union coverage", "va": "VA health benefits", "tricare": "TRICARE / TRICARE For Life", "existing_medigap": "Existing Medigap policy"}
FACTS = {"employer_union": "coordination-employer", "va": "coordination-va", "tricare": "coordination-tricare", "existing_medigap": "coordination-medigap"}


def context(messages):
    """Mentions prompt a review, never an inferred benefit/eligibility determination.

    Latest explicit negatives clear earlier mentions. The app retains no new profile.
    """
    latest = {}
    for message in messages:
        if not isinstance(message, str):
            continue
        for clause in re.split(r"[.!?;\n]|\bbut\b|,\s*(?=(?:i|we|my|our)\b)|\band\s+(?=(?:i|we)\b)", message.casefold().replace("’", "'")):
            for key, pattern in PATTERNS.items():
                match = re.search(pattern, clause)
                if not match:
                    continue
                before = clause[:match.end()]
                negative = re.search(r"\b(?:do not|don't|does not|doesn't)\s+(?:currently\s+)?(?:have|use|receive|offer)|\bno longer\s+(?:have|use|using|receive)|\bnot\s+(?:on|covered by|enrolled in)|\bwithout\b|\bno\s+(?:retiree|employer|union|va|tricare|tfl|medigap)", before)
                if negative:
                    latest[key] = None
                else:
                    stated = bool(re.search(r"\b(?:have|has|use|using|receive|my|our|her|his|their)\b|covered by|enrolled in", clause))
                    latest[key] = {"key": key, "label": LABELS[key], "status": "reported_needs_review" if stated else "discussed_coverage_unconfirmed", "fact_id": FACTS[key], "eligibility_determined": False}
    return [latest[k] for k in PATTERNS if latest.get(k)]


def topics(message):
    result = []
    if re.search(r"\b(?:hope\s+)?pace\b", message, re.I):
        result.append("pace")
    if re.search(r"\bshine\b|\bcounsel(?:or|ing|ling)\b|unbiased (?:help|advice)", message, re.I):
        result.append("shine")
    result.extend("coordination_" + key for key, pattern in PATTERNS.items() if re.search(pattern, message.replace("’", "'"), re.I))
    return list(dict.fromkeys(result))


def source_text(spec, raw, support):
    if raw.startswith(b"%PDF"):
        text = subprocess.run(["pdftotext", "-layout", str(RAW / spec["sha256"]), "-"], capture_output=True, text=True, check=True).stdout
        pages = text.split("\f")
        return pages[support["pdf_page"] - 1] if "pdf_page" in support else text
    if raw.startswith(b"PK"):
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            return archive.read(support["member"]).decode("utf-8-sig")
    return html_text(raw)


def build():
    config, sources = cms.load_json(CONFIG), PublicSources(REPORTS / "sources.json", RAW)
    specs, documents = {}, {}
    for key, digest in config["source_sha256"].items():
        spec, raw = sources.read(key)
        if spec["sha256"] != digest:
            raise cms.SourceError("Local resource source changed; review facts before rebuilding: " + key)
        specs[key], documents[key] = spec, raw
    facts, checked = [], []
    for item in config["facts"]:
        evidence = []
        for support in item["support"]:
            key = support["source_id"]
            text = " ".join(source_text(specs[key], documents[key], support).split()).casefold()
            if any(" ".join(a.split()).casefold() not in text for a in support["anchors"]):
                raise cms.SourceError("Local resource support changed: " + item["id"] + " / " + key)
            evidence.append({**PublicSources.evidence(specs[key]), "url": specs[key]["requested_url"], **{k: support[k] for k in ("pdf_page", "member") if k in support}})
            checked.append({"fact_id": item["id"], "source_id": key, "status": "support_verified"})
        facts.append({k: v for k, v in item.items() if k != "support"} | {"evidence": evidence, "verification_state": "publisher_source_checked; qualified_domain_review_pending"})
    if len({f["id"] for f in facts}) != len(facts):
        raise cms.SourceError("Duplicate local-resource fact")
    with zipfile.ZipFile(io.BytesIO(documents["cms-ma-directory-october-2026"])) as archive:
        member = config["cms_directory_member"]
        rows = list(csv.DictReader(io.StringIO(archive.read(member).decode("utf-8-sig"))))
    matches = [r for r in rows if r["Contract Number"] == "H5934"]
    if len(matches) != 1 or matches[0]["Organization Marketing Name"] != "Hope PACE" or matches[0]["Organization Type"] != "National PACE" or matches[0]["Legal Entity State Code"] != "FL":
        raise cms.SourceError("Hope PACE CMS identity changed or is ambiguous")
    catalog_path = cms.ROOT / "reports/work-package-2/catalog.json"
    catalog = cms.load_json(catalog_path)
    records = catalog["options"] + catalog["exclusions"]
    other_types = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "benefit_year": "2027", "county_fips": "12021",
                   "catalog_sha256": cms.file_hash(catalog_path), "catalog_snapshot_id": catalog["snapshot_id"], "records_searched": len(records),
                   "observed_plan_types": sorted({r["plan_type"] for r in records}),
                   "cost_plan_ids": [r["id"] for r in records if "cost" in (r["category"] + " " + r["plan_type"]).casefold()],
                   "msa_plan_ids": [r["id"] for r in records if r["plan_type"].upper() == "MSA" or "medical savings" in r["plan_type"].casefold()],
                   "conclusion": "No cost-plan or MSA record found in this pinned Collier landscape; absence from this source is not a complete live-market exclusion. C18 remains the live-market check."}
    resources = copy.deepcopy(config["resources"])
    resources["pace"]["cms_identity"] = {k: matches[0][k] for k in ("Legal Entity Name", "Organization Marketing Name", "Contract Number", "Organization Type", "Parent Organization", "Directory Contact Last Update")}
    for resource in resources.values():
        resource["evidence"] = [PublicSources.evidence(specs[k]) | {"url": specs[k]["requested_url"]} for k in resource.pop("source_ids")]
    data = {"facts": facts, "resources": resources, "other_plan_types": other_types, "review_after_utc": min(s["review_after_utc"] for s in specs.values()),
            "checked_at_utc": datetime.now(timezone.utc).isoformat(), "qualified_domain_review": "pending"}
    cms.write_json(REPORTS / "resources.json", data)
    cms.write_json(REPORTS / "source-review.json", {"support_checks": checked, "cms_identity": matches[0], "other_plan_types": other_types,
                   "limits": config["source_decisions"]})
    cms.write_json(REPORTS / "manifest.json", {"code_sha256": cms.file_hash(__file__), "config_sha256": cms.file_hash(CONFIG),
                   "sources_registry_sha256": cms.file_hash(REPORTS / "sources.json"), "catalog_sha256": cms.file_hash(catalog_path),
                   "outputs_sha256": {name: cms.file_hash(REPORTS / name) for name in ("resources.json", "source-review.json")}})
    return data


def load():
    manifest = cms.load_json(REPORTS / "manifest.json")
    if manifest["code_sha256"] != cms.file_hash(__file__) or manifest["config_sha256"] != cms.file_hash(CONFIG) or manifest["sources_registry_sha256"] != cms.file_hash(REPORTS / "sources.json") or manifest["catalog_sha256"] != cms.file_hash(cms.ROOT / "reports/work-package-2/catalog.json"):
        raise cms.SourceError("Local resources changed; rebuild and review")
    for name, digest in manifest["outputs_sha256"].items():
        if cms.file_hash(REPORTS / name) != digest:
            raise cms.SourceError("Local resource output changed: " + name)
    sources = PublicSources(REPORTS / "sources.json", RAW)
    for key in cms.load_json(CONFIG)["source_sha256"]:
        sources.read(key)
    return cms.load_json(REPORTS / "resources.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "verify"))
    args = parser.parse_args()
    result = build() if args.command == "build" else load()
    print({"facts": len(result["facts"]), "resources": list(result["resources"]), "review_after_utc": result["review_after_utc"]})
