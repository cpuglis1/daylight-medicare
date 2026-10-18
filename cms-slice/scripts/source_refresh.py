#!/usr/bin/env python3
"""Discover candidate CMS releases without importing changed data or mixing benefit years."""

import argparse
from datetime import date
from pathlib import PurePosixPath
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


def discover(sources=None, refresh=False, offline=False):
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
    cms.write_json(OUT, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    try:
        r = discover(refresh=args.refresh, offline=args.offline)
        print({k: r[k] for k in ("monthly_status", "quarterly_pricing_status")})
    except (cms.SourceError, OSError, ValueError, KeyError) as error:
        parser.exit(2, "Release discovery failed: " + str(error) + "\n")
