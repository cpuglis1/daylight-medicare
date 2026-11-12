#!/usr/bin/env python3
"""Discover candidate CMS releases without importing changed data or mixing benefit years."""

import argparse
from datetime import date
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlsplit

import cms_slice as cms
from evidence_store import PublicSources
import prescription as rx

OUT = cms.ROOT / "reports/cms-release-discovery.json"
CATALOG = "https://data.cms.gov/data.json"


def latest(dataset, prefix):
    candidates = []
    for item in dataset:
        title = item.get("title", "")
        if not title.startswith(prefix + " : "):
            continue
        token = title.rsplit(" : ", 1)[1]
        try:
            published = date.fromisoformat(token)
        except ValueError as error:
            raise cms.SourceError("CMS catalog date format needs inspection: " + title) from error
        for distribution in item.get("distribution", []):
            url = distribution.get("downloadURL", "")
            if not url:
                continue
            filename = PurePosixPath(urlsplit(url).path).name
            match = re.fullmatch(r"(?:SPUF_)?(\d{4})_.*\.zip", filename)
            candidates.append((published, {"dataset_title": title, "identifier": item.get("identifier"),
                                           "metadata_modified": item.get("modified"), "distribution": distribution,
                                           "filename_benefit_year_candidate": match[1] if match else None}))
    if not candidates:
        raise cms.SourceError("Required public release family is absent from the catalog")
    newest = max(d for d, _ in candidates)
    selected = [v for d, v in candidates if d == newest]
    if len(selected) != 1:
        raise cms.SourceError("Latest CMS distribution is ambiguous; do not choose silently")
    return selected[0]


def discover(sources=None, refresh=False, offline=False, out=OUT):
    sources = sources or PublicSources()
    spec, catalog = sources.json("cms-public-release-catalog", None if offline else CATALOG,
                                 **({} if offline else {"refresh": refresh, "review_days": 1, "max_bytes": 18_000_000}))
    monthly = latest(catalog.get("dataset", []), "Monthly Prescription Drug Plan Formulary and Pharmacy Network Information")
    quarterly = latest(catalog.get("dataset", []), "Quarterly Prescription Drug Plan Formulary, Pharmacy Network, and Pricing Information")
    config = cms.load_json(rx.CONFIG)
    result = {"catalog_evidence": PublicSources.evidence(spec), "code_sha256": cms.file_hash(__file__),
              "pinned_configuration_sha256": cms.file_hash(rx.CONFIG), "benefit_year": config["benefit_year"],
              "latest_monthly": monthly, "latest_quarterly": quarterly,
              "monthly_status": "pinned_url_matches_latest_catalog_candidate" if monthly["distribution"]["downloadURL"] == config["source"]["url"] else "new_candidate_requires_layout_identity_and_difference_review",
              "quarterly_pricing_status": "candidate_requires_content_inspection_not_a_price_feed" if quarterly["filename_benefit_year_candidate"] == config["benefit_year"] else "latest_filename_candidate_is_another_benefit_year",
              "limits": ["Metadata discovery only; no new dataset archive was downloaded or imported", "Filename year is a candidate, not an inspected table year", "A URL match is not a source freshness, rights or suitability certification", "Publish only after reviewed data differences and immutable release verification"]}
    cms.write_json(out, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--candidate-dir", type=Path, help="Preserve prior discovery and refresh in an isolated candidate directory")
    args = parser.parse_args()
    try:
        sources, out = None, OUT
        if args.candidate_dir:
            candidate = args.candidate_dir
            if candidate.exists():
                raise cms.SourceError("Candidate directory exists; preserve it and choose a new directory")
            previous = PublicSources()
            spec, raw = previous.read("cms-public-release-catalog")
            candidate.mkdir(parents=True)
            cms.write_json(candidate / "previous-catalog-receipt.json", spec)
            if OUT.exists():
                cms.write_json(candidate / "previous-discovery.json", cms.load_json(OUT))
            sources = PublicSources(candidate / "sources.json", candidate / "raw")
            sources.raw.mkdir()
            (sources.raw / spec["sha256"]).write_bytes(raw)
            cms.write_json(sources.registry, {"version": 1, "sources": {spec["id"]: spec}})
            out = candidate / "discovery.json"
        r = discover(sources=sources, refresh=args.refresh, offline=args.offline, out=out)
        if args.candidate_dir:
            previous_result = cms.load_json(candidate / "previous-discovery.json") if (candidate / "previous-discovery.json").exists() else {}
            comparison = {"previous_catalog_sha256": spec["sha256"], "current_catalog_sha256": r["catalog_evidence"]["sha256"],
                          "catalog_bytes_changed": spec["sha256"] != r["catalog_evidence"]["sha256"],
                          "monthly_distribution_changed": previous_result.get("latest_monthly", {}).get("distribution") != r["latest_monthly"]["distribution"],
                          "quarterly_distribution_changed": previous_result.get("latest_quarterly", {}).get("distribution") != r["latest_quarterly"]["distribution"],
                          "review_after_utc": r["catalog_evidence"]["review_after_utc"],
                          "assessment": "Catalog metadata and distribution differences inspected; no archive or benefit-year substitution. Dataset freshness and consumer review remain separate."}
            cms.write_json(candidate / "change-assessment.json", comparison)
        print({k: r[k] for k in ("monthly_status", "quarterly_pricing_status")})
    except (cms.SourceError, OSError, ValueError, KeyError) as error:
        parser.exit(2, "Release discovery failed: " + str(error) + "\n")
