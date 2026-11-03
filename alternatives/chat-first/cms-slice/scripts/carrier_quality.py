"""Bounded carrier corroboration and an explicit field-quality matrix for all 38 demo records."""

import argparse
from collections import Counter
from decimal import Decimal
from pathlib import Path
import re
import subprocess

import cms_slice as cms
from evidence_store import PublicSources
import research

OUT = cms.ROOT / "reports/demo-quality.json"
MANIFEST = OUT.with_name("demo-quality-manifest.json")
GOV_OBSERVATIONS = cms.ROOT / "data-sources/medicare-gov-observations.json"
AMOUNT = r"\$[\d,]+(?:\.\d{2})?"


def cents(value):
    return int(Decimal(value.replace("$", "").replace(",", "")) * 100)


def humana_values(pages, category):
    matches = [(i, p) for i, p in enumerate(pages) if "Monthly plan premium" in p and "Monthly Premium, Deductible" in p]
    if len(matches) != 1:
        raise cms.SourceError("Humana cost-table context changed")
    i, page = matches[0]
    premium = re.search(r"Monthly plan premium\s+(" + AMOUNT + ")", page)
    if not premium:
        raise cms.SourceError("Humana premium anchor changed")
    values = {"part_d_total_premium" if category == "PDP" else "part_c_premium" if category == "MA" else "consolidated_premium":
              {"cents": cents(premium[1]), "raw": premium[1], "pdf_page": i+1}}
    if category != "PDP":
        moop = re.search(r"Medical Maximum out-of-pocket\s+(" + AMOUNT + r")\s+in-network", page)
        if not moop:
            raise cms.SourceError("Humana in-network MOOP anchor changed")
        values["in_network_medical_moop"] = {"cents": cents(moop[1]), "raw": moop[1], "pdf_page": i+1}
    if category != "MA":
        section = re.search(r"Pharmacy \(Part D\) deductible(.*?)(?:Medical Maximum|Prescription Drug Benefits)", page, re.S)
        amounts = re.findall(AMOUNT, section[1]) if section else []
        if not amounts:
            raise cms.SourceError("Humana tier-qualified deductible anchor changed")
        values["annual_part_d_deductible"] = {"cents": max(cents(x) for x in amounts), "raw": amounts,
                                              "pdf_page": i+1, "qualification": " ".join(section[1].split())}
    return values


def devoted_values(pages):
    page = pages[3]
    patterns = {"consolidated_premium": r"Monthly Premium\s+(" + AMOUNT + ")",
                "annual_part_d_deductible": r"Pharmacy \(Part D\)\s+(" + AMOUNT + r") for Tiers 3-5",
                "in_network_medical_moop": r"Maximum Out-of-\s+(" + AMOUNT + ")"}
    result = {}
    for field, pattern in patterns.items():
        match = re.search(pattern, page)
        if not match:
            raise cms.SourceError("Devoted table anchor changed: " + field)
        result[field] = {"cents": cents(match[1]), "raw": match[1], "pdf_page": 4}
    result["annual_part_d_deductible"]["qualification"] = "Tiers 3–5; $0 deductible if receiving Extra Help; not medicine-specific"
    return result


def build(sources=None):
    sources = sources or PublicSources()
    model = research.ReadModel()
    catalog = model.catalog("2027", "12021")
    prior = cms.load_json(research.REPORTS / "validation.json")
    gov = cms.load_json(GOV_OBSERVATIONS)
    if (gov["benefit_year"], gov["county_fips"]) != ("2027", "12021") or gov["scenario"]["special_needs_included"] is not False:
        raise cms.SourceError("Medicare.gov observation scope/year differs from the declared comparison")
    gov_rows = {}
    for page in gov["pages"]:
        for observed in page["records"]:
            match = re.fullmatch(r"([HRS]\d{4})-(\d{3})-(\d{1,3})", observed["raw_plan_id"])
            if not match:
                raise cms.SourceError("Uninspected Medicare.gov plan identity")
            key = "-".join((match[1], match[2], match[3].zfill(3), "2027"))
            if key in gov_rows:
                raise cms.SourceError("Duplicated Medicare.gov plan observation")
            gov_rows[key] = {**observed, "url": page["url"], "plan_type": page["plan_type"]}
    non_snp = {r["id"] for r in catalog["options"] + catalog["exclusions"] if r["category"] != "SNP"}
    if set(gov_rows) != non_snp:
        raise cms.SourceError("Official UI/archive non-SNP population differs; preserve and investigate before release")
    observations = {}
    documents = []
    for sample in prior["samples"]:
        ident = sample["identity"]
        pid = f"{ident['contract']}-{ident['plan']}-{ident['segment_join']}-{ident['year']}"
        observations[pid] = {check["field"]: {"status": check["status"], "source": check["carrier"], "qualification": "Only this monetary fact was corroborated"} for check in sample["money_checks"]}
    for row in catalog["options"]:
        if row["landscape_raw"]["Parent Organization Name"] == "Humana Inc.":
            ident = row["identity"]
            sid = "humana-" + ident["contract"] + ident["plan"] + ident["segment_join"] + "-sb"
        elif row["id"] == "H9884-016-000-2027":
            sid = "devoted-016-sb"
        else:
            continue
        spec, raw = sources.read(sid)
        if not raw.startswith(b"%PDF"):
            raise cms.SourceError("Carrier artifact is not a PDF")
        pages = subprocess.run(["pdftotext", "-layout", str(sources.raw / spec["sha256"]), "-"], check=True, capture_output=True).stdout.decode().split("\f")
        context = " ".join("\n".join(pages[:4]).split())
        pid_short = row["identity"]["contract"] + "-" + row["identity"]["plan"]
        full_identity = row["identity"]["contract"] + row["identity"]["plan"] + row["identity"]["segment_join"]
        if not (pid_short in context or full_identity in context) or not all(token in context for token in ("2027", "Summary of Benefits", "Collier" if row["category"] != "PDP" else "Florida")):
            raise cms.SourceError("Carrier year/plan/geography context rejected: " + row["id"])
        values = humana_values(pages, row["category"]) if sid.startswith("humana") else devoted_values(pages)
        observations[row["id"]] = {field: {"status": "agrees" if value["cents"] == row["facts"][field]["value_cents"] else "conflict",
                                             "source": {**PublicSources.evidence(spec), **value},
                                             "qualification": value.get("qualification", "Specific field; no full-plan or personal suitability certification")}
                                    for field, value in values.items()}
        documents.append({"plan_id": row["id"], "source_id": sid, "sha256": spec["sha256"], "identity_year_geography": "source_context_checked", "benefit_pages": sorted({v["pdf_page"] for v in values.values()})})
    matrix = []
    for row in catalog["options"]:
        for field in [row["plan_premium"]["field"], "annual_part_d_deductible", "in_network_medical_moop"]:
            cell = row["facts"][field]
            check = observations.get(row["id"], {}).get(field)
            official = gov_rows[row["id"]]
            official_raw = official[{"annual_part_d_deductible": "drug_deductible_raw", "in_network_medical_moop": "in_network_moop_raw"}.get(field, "published_premium_raw")]
            if official_raw is None:
                gov_status = "not_applicable_agrees" if cell["state"] == "not_applicable" and (row["category"] == "PDP" if field == "in_network_medical_moop" else official["no_part_d_text_observed"]) else "unresolved_missing_observation"
                official_cents = None
            else:
                official_amount = official_raw.removesuffix(" In-network")
                if not re.fullmatch(AMOUNT, official_amount):
                    raise cms.SourceError("Uninspected Medicare.gov amount encoding")
                official_cents = cents(official_amount)
                gov_status = "agrees" if official_cents == cell["value_cents"] else "conflict"
            matrix.append({"plan_id": row["id"], "parent_organization": row["landscape_raw"]["Parent Organization Name"],
                           "field": field, "cms_value_cents": cell["value_cents"], "cms_state": cell["state"], "cms_source": cell["evidence"],
                           "corroboration": check if check else {"status": "not_independently_checked" if cell["state"] == "value" else "source_not_applicable_or_unavailable", "qualification": "No carrier agreement inherited from another record"},
                           "medicare_gov": {"status": gov_status, "raw": official_raw, "value_cents": official_cents, "url": official["url"],
                                            "observed_at_utc": gov["observed_at_utc"], "capture_method": gov["capture_method"],
                                            "qualification": "Published selected field in an unassisted public example; not a personal price, carrier certification, or domain sign-off"},
                           "qualified_domain_signoff": "pending"})
    counts = Counter(x["corroboration"]["status"] for x in matrix)
    gov_counts = Counter(x["medicare_gov"]["status"] for x in matrix)
    result = {"scope": "All 38 comparison records; narrow monetary corroboration, not independent certification of every field",
              "catalog_sha256": cms.file_hash(research.REPORTS / "catalog.json"), "code_sha256": cms.file_hash(__file__),
              "carrier_records_checked": len(observations), "carrier_parent_organizations_checked": len({r["landscape_raw"]["Parent Organization Name"] for r in catalog["options"] if r["id"] in observations}),
              "field_status_counts": dict(counts), "documents": documents, "matrix": matrix,
              "medicare_gov_observations_sha256": cms.file_hash(GOV_OBSERVATIONS), "medicare_gov_field_status_counts": dict(gov_counts),
              "medicare_gov_plan_summaries": {pid: {"primary_care_raw": observed.get("primary_care_raw"), "specialist_raw": observed.get("specialist_raw"),
                                                    "url": observed["url"], "observed_at_utc": gov["observed_at_utc"],
                                                    "qualification": observed.get("medical_summary_scope", "Standalone PDP has no medical office-visit benefit")}
                                                for pid, observed in gov_rows.items() if pid in {r["id"] for r in catalog["options"]}},
              "medicare_gov_population": {"observed_non_snp_records": len(gov_rows), "matching_archive_non_snp_records": len(non_snp),
                                          "supported_records_checked": len(catalog["options"]), "regional_ppo_records_outside_scope": 5},
              "five_regional_ppos": "Remain excluded pending reviewed field/geography semantics; not hidden or classified as personally ineligible",
              "qualified_domain_signoff": "pending"}
    cms.write_json(OUT, result)
    cms.write_json(MANIFEST, {"quality_sha256": cms.file_hash(OUT), "code_sha256": cms.file_hash(__file__),
                              "catalog_sha256": cms.file_hash(research.REPORTS / "catalog.json"),
                              "validation_sha256": cms.file_hash(research.REPORTS / "validation.json"),
                              "medicare_gov_observations_sha256": cms.file_hash(GOV_OBSERVATIONS),
                              "carrier_sources": {doc["source_id"]: doc["sha256"] for doc in documents}})
    if counts["conflict"] or gov_counts["conflict"] or gov_counts["unresolved_missing_observation"]:
        raise cms.SourceError("New carrier conflict found; preserve report and stop affected claims")
    return result


def verify(path=OUT, manifest_path=MANIFEST, sources=None):
    sources = sources or PublicSources()
    manifest = cms.load_json(manifest_path)
    checks = {"quality_sha256": path, "code_sha256": Path(__file__), "catalog_sha256": research.REPORTS / "catalog.json",
              "validation_sha256": research.REPORTS / "validation.json", "medicare_gov_observations_sha256": GOV_OBSERVATIONS}
    for key, candidate in checks.items():
        if cms.file_hash(candidate) != manifest[key]:
            raise cms.SourceError("Quality evidence changed: " + key)
    for source_id, digest in manifest["carrier_sources"].items():
        spec, _ = sources.read(source_id)
        if spec["sha256"] != digest:
            raise cms.SourceError("Carrier source differs from quality review")
    result = cms.load_json(path)
    if result["field_status_counts"].get("conflict") or result["medicare_gov_field_status_counts"].get("conflict") or result["medicare_gov_field_status_counts"].get("unresolved_missing_observation"):
        raise cms.SourceError("Unresolved critical quality conflict")
    return result


if __name__ == "__main__":
    try:
        r = build()
        print({k: r[k] for k in ("carrier_records_checked", "carrier_parent_organizations_checked", "field_status_counts", "medicare_gov_field_status_counts", "medicare_gov_population")})
    except (cms.SourceError, OSError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit("Quality build failed: " + str(error))
