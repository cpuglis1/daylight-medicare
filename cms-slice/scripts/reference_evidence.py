#!/usr/bin/env python3
"""Replay inspected public identity/vocabulary evidence; never infer quotes or participation."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import urllib.request

import cms_slice as cms

ROOT = cms.ROOT
CONFIG = ROOT / "data-sources/reference-evidence.json"
REPORTS = ROOT / "reports/source-diligence"


def locations(provider, city="Naples", state="FL"):
    """Use explicit purpose, not array position; keep separate secondary-location provenance."""
    found = []
    for index, address in enumerate(provider.get("addresses", [])):
        if address.get("address_purpose") == "LOCATION" and address.get("city", "").casefold() == city.casefold() and address.get("state") == state:
            found.append({"json_pointer": f"/addresses/{index}", "role": "reported_primary_location", "raw": address})
    for index, address in enumerate(provider.get("practiceLocations", [])):
        if address.get("city", "").casefold() == city.casefold() and address.get("state") == state:
            found.append({"json_pointer": f"/practiceLocations/{index}", "role": "reported_secondary_location", "raw": address})
    return found


def drug_candidates(payload):
    # Empty/absent groups are distinct in the saved source. Neither produces an invented candidate.
    candidates = []
    for group in payload.get("drugGroup", {}).get("conceptGroup", []):
        for item in group.get("conceptProperties") or []:
            if not re.fullmatch(r"[1-9]\d{0,7}", item.get("rxcui", "")):
                raise cms.SourceError("Unexpected RxNorm candidate identifier")
            candidates.append(item)
    return {"status": "requires_specific_product_confirmation" if len(candidates) > 1 else "single_vocabulary_candidate_requires_confirmation" if candidates else "no_active_vocabulary_result",
            "candidates": candidates, "confirmed_rxcui": None, "coverage": None, "price": None}


def verify_inputs(config):
    for name, spec in config["artifacts"].items():
        path = ROOT / spec["path"]
        if not path.is_file() or path.stat().st_size != spec["bytes"] or cms.file_hash(path) != spec["sha256"]:
            raise cms.SourceError("Missing/changed public evidence snapshot: " + name)


def fetch(config):
    for name, spec in config["artifacts"].items():
        path = ROOT / spec["path"]
        if path.exists():
            if path.stat().st_size != spec["bytes"] or cms.file_hash(path) != spec["sha256"]:
                raise cms.SourceError("Changed cached public evidence: " + name)
            continue
        if spec.get("capture_method") == "chrome_visible_text":
            raise cms.SourceError("Recover the pinned Chrome documentation capture or explicitly inspect/register a new one")
        with urllib.request.urlopen(spec["url"], timeout=60) as response:
            raw = response.read(spec["bytes"] + 1)
            receipt = {"url": spec["url"], "final_url": response.url, "received_at_utc": datetime.now(timezone.utc).isoformat(),
                       "bytes": len(raw), "sha256": cms.sha256(raw)}
        if len(raw) != spec["bytes"] or cms.sha256(raw) != spec["sha256"]:
            raise cms.SourceError("Mutable public endpoint changed; inspect a new dated snapshot instead of overwriting this one: " + name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        cms.write_json(path.with_suffix(path.suffix + ".receipt.json"), receipt)
    verify_inputs(config)


def build(config, out=REPORTS):
    verify_inputs(config)
    def payload(name):
        return cms.load_json(ROOT / config["artifacts"][name]["path"])
    individual = payload("npi_individual_sample")
    pharmacies = payload("npi_pharmacy_city_query")
    identity_rows = []
    for index, provider in enumerate(individual["results"]):
        number = str(provider["number"])
        if not re.fullmatch(r"\d{10}", number):
            raise cms.SourceError("NPI identifier changed shape")
        identity_rows.append({"npi": number, "raw_number": provider["number"], "source_pointer": f"/results/{index}",
                              "registry_status_raw": provider.get("basic", {}).get("status"), "locations": locations(provider),
                              "first_address_purpose": provider.get("addresses", [{}])[0].get("address_purpose"),
                              "network_participation": None, "accepting_patients": None, "license_verified": False})
    concept = payload("rxnorm_exact_properties")["properties"]
    ndc = payload("rxnorm_ndc_properties")["ndcPropertyList"]["ndcProperty"]
    if concept["rxcui"] != "1551300" or not any(x["ndcItem"] == "00002143380" and x["rxcui"] == concept["rxcui"] for x in ndc):
        raise cms.SourceError("Inspected NDC/RxCUI mapping changed")
    formulary = ROOT / config["artifacts"]["carrier_formulary"]["path"]
    pages = subprocess.run(["pdftotext", "-layout", str(formulary), "-"], check=True, capture_output=True).stdout.decode().split("\f")
    if not all(x in pages[0] for x in ("2027", "00027047", "H5434-002, 045", "10/15/2026")):
        raise cms.SourceError("Carrier formulary year/plan/formulary/date context changed")
    line = next((line for line in pages[63].splitlines() if line.startswith("TRULICITY - dulaglutide soln auto-injector 0.75 mg/0.5ml")), None)
    if line is None or not re.search(r"\s3\s+PA, QL \(4 pens/28 days\)", line):
        raise cms.SourceError("Inspected carrier drug row changed")
    report = {"inspection_date": "2026-10-17", "artifacts": config["artifacts"],
              "vocabulary": {"version": payload("rxnorm_version"), "brand_search": drug_candidates(payload("rxnorm_brand_candidates")),
                             "exact_concept": concept, "exact_ndc_mapping": ndc, "status": "vocabulary_evidence_only; no consumer confirmation or coverage inference",
                             "nlm_attribution": config["nlm_attribution"]},
              "carrier_sample": {"plan_ids": ["H5434-002-000-2027", "H5434-045-000-2027"], "formulary_id": "00027047", "rxcui": "1551300", "ndc11": "00002143380",
                                 "pdf_page": 64, "printed_page": "48", "document_updated": "2026-10-15", "tier": "3", "prior_authorization": "Y",
                                 "carrier_quantity": {"amount": "4", "unit": "pens", "days": "28"},
                                 "quantity_comparison_status": "unresolved_unit; CMS raw 2 has no unit stated in inspected layout; no automatic conversion",
                                 "scope": "Specific product row; carrier document does not print the proxy NDC. NLM connects the exact proxy to the RxNorm concept; no whole-formulary certification."},
              "provider_identity": {"query_results": individual["result_count"], "sample": identity_rows,
                                    "document_order_discrepancy": "NPPES help says LOCATION is first; actual sample contains MAILING first. Explicit address_purpose is authoritative for parsing.",
                                    "network_evidence_status": "unavailable; no plan/location participation source captured"},
              "pharmacy_identity": {"query_city": "Naples", "query_state": "FL", "address_purpose": "LOCATION", "query_limit": 200,
                                    "returned": pharmacies["result_count"], "has_matching_reported_locations": sum(bool(locations(p)) for p in pharmacies["results"]),
                                    "scope": "Public registry city query; not all Collier County pharmacies, current store operation or clinical-network participation"},
              "medigap": {"official_sample_source": config["artifacts"]["florida_choices"]["url"],
                          "rate_status": "illustrative_public_comparison_only", "quote_receipts": [], "accepted_premium": None,
                          "search_observation": "Official county image map loaded in Chrome. Collier activation was not operable through the extension's visible locator interface; no rate result was obtained.",
                          "supplier_access": "CSG and Connecture describe APIs publicly. No inspected authenticated payload, contract, credentials, quote receipt or carrier acceptance was available; no adapter implemented."},
              "open_dependencies": config["open_dependencies"]}
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    cms.write_json(out / "observations.json", report)
    cms.write_json(out / "manifest.json", {"code_sha256": cms.file_hash(__file__), "configuration_sha256": cms.file_hash(CONFIG),
                                          "output_sha256": cms.file_hash(out / "observations.json")})
    return report


def verify(config, out=REPORTS):
    verify_inputs(config)
    out = Path(out)
    manifest = cms.load_json(out / "manifest.json")
    if manifest != {"code_sha256": cms.file_hash(__file__), "configuration_sha256": cms.file_hash(CONFIG), "output_sha256": cms.file_hash(out / "observations.json")}:
        raise cms.SourceError("Public evidence code/config/report changed")
    return cms.load_json(out / "observations.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["fetch", "build", "verify"])
    args = parser.parse_args()
    try:
        config = cms.load_json(CONFIG)
        if args.command == "fetch":
            fetch(config)
        elif args.command == "build":
            report = build(config)
            print(json.dumps({"vocabulary_status": report["vocabulary"]["brand_search"]["status"], "provider_identity": report["provider_identity"]["query_results"], "pharmacy_identity": report["pharmacy_identity"]["returned"], "quote_receipts": 0}, indent=2))
        else:
            verify(config)
            print("Verified public identity, vocabulary and source-diligence snapshots")
    except (cms.SourceError, OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print("ERROR:", error)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
