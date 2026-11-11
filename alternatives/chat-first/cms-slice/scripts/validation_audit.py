#!/usr/bin/env python3
"""Replay the validation work and prepare an unsigned, exact-release review packet.

Offline only. This command cannot accept claims or authorize a consumer release.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess

import cms_slice as cms
from consumer_acceptance import digest, requirements

OUT = cms.ROOT / "reports/collier-gap-20261020/validation"
PRIOR = cms.ROOT / "reports/collier-gap-20261020/c16-c23"


def financial(out):
    catalog = cms.load_json(cms.ROOT / "reports/work-package-2/catalog.json")
    by_id = {r["id"]: r for r in catalog["options"] + catalog["exclusions"]}
    manual = cms.load_json(out / "manual-financial-transcription.json")["values"]
    docs = {r["plan_id"]: r for r in cms.load_json(out / "humana-documents.json") if not r.get("error")}
    optimum = {r["document"]: r for r in cms.load_json(out / "optimum-documents.json") if not r.get("error")}
    manual.update({"H5594-016-000-2027": [0, 10500, 50000], "H5594-017-000-2027": [0, 10500, 50000],
                   "H5594-030-000-2027": [0, 0, 500000], "H5594-031-000-2027": [0, 0, 500000]})
    results = []
    for pid, values in sorted(manual.items()):
        row = by_id[pid]
        is_optimum = pid.startswith("H5594")
        doc = optimum["OPT27SB" + pid.split("-")[1]] if is_optimum else docs[pid]
        raw_path = cms.ROOT.parent / doc["raw_path"]
        if cms.file_hash(raw_path) != doc["spec"]["sha256"]:
            raise cms.SourceError("Carrier source changed: " + pid)
        pages = subprocess.run(["pdftotext", "-layout", str(raw_path), "-"], check=True, capture_output=True).stdout.decode().split("\f")
        context = " ".join(" ".join(pages[:4]).split())
        compact = pid.replace("-", "")[:-4]
        if (not (compact in context or (pid[:5] + "-" + pid[6:9]) in context or (pid[:5] + "_" + pid[6:9]) in context)
                or "2027" not in context or not ("Collier" in context or "Florida" in context)):
            raise cms.SourceError("Plan/year/geography context not found: " + pid)
        cost_pages = [i+1 for i, p in enumerate(pages) if ("How much is my premium" in p if is_optimum else "Monthly Premium, Deductible" in p and "Monthly plan premium" in p)]
        if len(cost_pages) != 1:
            raise cms.SourceError("Ambiguous cost page: " + pid)
        columns = ["Part C Premium" if row["category"] == "MA" else "Monthly Consolidated Premium (Part C + D)",
                   "Annual Part D Deductible Amount", "In-Network Maximum Out-of-Pocket (MOOP) Amount"]
        conditions = ["Published monthly plan premium, separate from other Medicare obligations; eligibility and assistance apply.",
                      "Annual Part D amount before applicable tier/insulin exceptions or Extra Help; not a medicine-specific cost.",
                      "Annual in-network covered medical spending limit; premiums and Part D costs are separate; Medicaid assistance can change member payments."]
        for index, (column, observed) in enumerate(zip(columns, values)):
            source = cms.money(row["landscape_raw"].get(column, cms.ABSENT), {**row["source"], "column": column})
            page = cost_pages[0] if index != 2 or not is_optimum else next(i+1 for i,p in enumerate(pages) if "per year from doctors" in " ".join(p.split()))
            if observed is None:
                state = "cms_not_applicable_carrier_negative_not_established"
            elif pid == "H5594-017-000-2027" and index == 0:
                state = "unresolved_basis_difference"
            elif source["state"] != "value" or source["value_cents"] != observed:
                state = "conflict"
            else:
                state = "numeric_agreement_conditions_retained"
            entry = {"plan_id": pid, "field": ["monthly_premium", "drug_deductible", "medical_limit"][index],
                     "carrier_value_cents": observed, "cms": source, "comparison_state": state,
                     "unit": "USD cents per month" if index == 0 else "USD cents per benefit year",
                     "conditions": conditions[index], "carrier_evidence": {**doc["spec"], "pdf_page": page},
                     "technical_review": "Codex; rendered page and source text inspected 2026-10-20",
                     "domain_acceptance": "pending", "consumer_use_allowed": False}
            if index == 1:
                page_text = pages[cost_pages[0]-1]
                entry["extra_help_changes_deductible"] = "Extra Help" in page_text
                entry["tier_qualification_on_page"] = bool(re.search(r"Tier\s+\d", page_text))
                entry["insulin_exception_on_page"] = "Insulin" in page_text
            if pid.startswith("R5826"):
                entry["regional_ppo_condition"] = "The combined medical deductible has listed exclusions including in-network services; do not apply it as a universal in-network deductible. Combined MOOP is separate. Full EOC/domain interpretation pending."
            if state == "unresolved_basis_difference":
                entry["disposition"] = "Exact 2027 SB and LIS table support zero for the eligible/assisted population. CMS landscape total is 730 cents, subsidy is 730 cents and low-income beneficiary field is zero; monthly PUF is zero. PUF layout says monthly premium amount without defining subsidy basis. No unqualified gross/beneficiary substitution; DQ-004 remains open."
            results.append(entry)
    report = {"plans": len(manual), "cells": len(results), "states": dict(Counter(r["comparison_state"] for r in results)),
              "new_carrier_document_checks": results, "consumer_accepted_cells": 0,
              "scope": "Additional selected financial fields for 14 previously unsampled SNP/Regional PPO records; not a complete SB/EOC or all-70-plan review."}
    if report["states"].get("conflict"):
        raise cms.SourceError("New financial conflict; inspect before continuing")
    cms.write_json(out / "financial-audit.json", report)
    return report


def drug_cases(out):
    from demo_tools import DemoTools
    from evidence_store import PublicSources
    tools = DemoTools(research_mode=True)
    sources = PublicSources(out / "sources.json", out / "raw")
    cases, joins = [], []
    expected = {"1551300": {"TIER_LEVEL_VALUE": "2", "QUANTITY_LIMIT_YN": "Y", "QUANTITY_LIMIT_AMOUNT": "2",
                            "QUANTITY_LIMIT_DAYS": "28", "PRIOR_AUTHORIZATION_YN": "Y", "STEP_THERAPY_YN": "N"},
                "834235": {"TIER_LEVEL_VALUE": "3", "QUANTITY_LIMIT_YN": "N", "PRIOR_AUTHORIZATION_YN": "N", "STEP_THERAPY_YN": "Y"}}
    versions = {"00027024": "9", "00027025": "10"}
    for form, version in versions.items():
        sid = "optimum-O27FORM" + form[-3:]
        spec, _ = sources.read(sid)
        pages = subprocess.run(["pdftotext", "-layout", str(sources.raw / spec["sha256"]), "-"], capture_output=True, check=True).stdout.decode().split("\f")
        if not re.search(r"ID\s*" + str(int(form)) + r",?\s*Version\s+" + version, pages[0]) or "2027" not in pages[0]:
            raise cms.SourceError("Formulary identity/year/version changed")
        for code, checks in expected.items():
            rows = tools.forms_rx[(form, code)]
            if len(rows) != 1 or any(rows[0]["raw"][k] != v for k,v in checks.items()):
                raise cms.SourceError("New selected formulary discrepancy: " + form + "/" + code)
            token = "TRULICITY SUBCUTANEOUS" if code == "1551300" else "febuxostat oral tablet"
            page = next(i+1 for i,p in enumerate(pages) if token in p)
            cases.append({"formulary_id": form, "rxcui": code, "product": "Trulicity 0.75 mg/0.5 mL auto-injector" if code == "1551300" else "febuxostat 40 mg oral tablet",
                          "carrier_evidence": {**spec, "pdf_page": page}, "carrier_version": version,
                          "cms_source": rows[0], "cms_version": rows[0]["raw"]["FORMULARY_VERSION"],
                          "source_versions_match": rows[0]["raw"]["FORMULARY_VERSION"] == version,
                          "selected_field_agreements": checks, "domain_acceptance": "pending", "consumer_use_allowed": False,
                          "quantity_unit": None, "quantity_unit_disposition": "Trulicity raw quantity 2 per 28 days is retained; the table/PUF does not establish a common explicit physical unit. No pens/mL conversion is inferred." if code == "1551300" else "No quantity-limit amount asserted for this selected row",
                          "other_carrier_flags": ["NM"] if code == "1551300" else [],
                          "scope": "Selected row symbols only. Carrier publication is one version newer than pinned CMS; no whole-formulary acceptance or coverage authorization."})
    for pid in ("H5594-016-000-2027", "H5594-017-000-2027", "H5594-030-000-2027", "H5594-031-000-2027"):
        row = tools.joins[pid]["selected_plan"]
        form = row["raw"]["FORMULARY_ID"]
        if form != ("00027024" if "-030-" in pid else "00027025"):
            raise cms.SourceError("Optimum plan/formulary mapping changed")
        joins.append({"plan_id": pid, "formulary_id": form, "source_plan_row": row["source_row"],
                      "carrier_plan_mapping": "Plan number and name listed on exact 2027 formulary cover and the plan's Important Documents modal",
                      "products": sorted(expected), "domain_acceptance": "pending"})
    report = {"unique_product_formulary_cases": len(cases), "plan_product_joins": len(joins)*len(expected),
              "selected_field_agreements": sum(len(c["selected_field_agreements"]) for c in cases),
              "version_differences": len(cases), "consumer_accepted_cases": 0, "cases": cases, "joins": joins,
              "worked_drug_cost_estimates": 0, "pricing_source": "unavailable; H01 remains held"}
    cms.write_json(out / "optimum-drug-cases.json", report)
    return report


def build(out=OUT):
    out = Path(out)
    money = financial(out)
    additional_drugs = drug_cases(out)
    catalog = cms.load_json(cms.ROOT / "reports/work-package-2/catalog.json")
    matrix = cms.load_json(PRIOR / "c19-core-benefit-matrix.json")
    inventory = requirements(catalog, matrix)
    cms.write_json(out / "required-claims.json", inventory)
    source = cms.load_json(out / "sources.json")["sources"]
    receipts = cms.load_json(out / "optimum-document-receipts.json")
    market = []
    expected = {r["id"] for r in catalog["options"] + catalog["exclusions"] if r["identity"]["contract"] == "H5594"}
    for receipt in receipts:
        if "observed_plan_keys" not in receipt:
            continue
        observed = {"H5594-" + key[-3:] + "-000-2027" for key in receipt["observed_plan_keys"]}
        # The carrier's internal keys are mapped by the captured exact 2027 SB covers.
        market.append({"zip": receipt["zip"], "county": "Collier", "year": "2027", "expected_cms_ids": sorted(expected),
                       "carrier_ids": sorted(observed), "cms_only": sorted(expected-observed), "carrier_only": sorted(observed-expected),
                       "evidence": receipt, "acceptance": "pending", "scope": "Optimum carrier only; no Medicare.gov observation or full-market certification"})
    cms.write_json(out / "carrier-market-check.json", {"plans": len(expected), "zip_checks": len(market), "rows": market,
                   "full_70_plan_four_zip_validation": "blocked; Medicare.gov STOP remains active",
                   "uhc_enrollment_lead": {"plan_id": "H1889-026-000-2027", "url": "https://www.uhc.com/communityplan/florida/plans/medicare/2027/dual-complete-hmo-pos-snp",
                       "finding": "Previously retrieved official page lists Collier but says closed to new enrollment starting January 1, 2027. Exact 2027 EOC interpretation supports assisted zero premium. Local origin retrieval returned 403; no origin bytes/hash saved. Treat as a material reconciliation lead, not accepted availability.",
                       "raw_pdf_sha256": None, "acceptance": "pending"}})
    medical = [r for r in catalog["options"]+catalog["exclusions"] if r["category"] != "PDP"]
    provider_rows = [{"hospital_system": hospital, "plan_id": row["id"], "year": "2027", "provider_identity": None,
                      "service_location": None, "medical_network": None, "participation": "unknown", "accepted": False,
                      "next_evidence": "Exact facility/location and insurer medical-network evidence for this year and plan; broad system/carrier lists do not establish this cell"}
                     for hospital in ("NCH", "Physicians Regional") for row in sorted(medical, key=lambda r:r["id"])]
    cms.write_json(out / "hospital-validation-queue.json", {"cells": len(provider_rows), "confirmed": 0, "rows": provider_rows,
                   "source_receipts": {k:v for k,v in source.items() if k.startswith(("nch", "physicians"))},
                   "material_source_issues": ["Dated NCH 2027 notice ends Wellcare participation; generic contracted-payer list still includes Wellcare without an effective year", "NCH hospital Humana HMO/PPO listing differs from its medical group's PPO-only listing", "Physicians Regional Medical Group's general page does not establish hospital or exact-plan participation"],
                   "scope": "Queue only; medical-group notices are distinct from hospitals, and no NPI/network match is fabricated"})
    pharmacy = cms.load_json(out / "pharmacy-join-audit.json")
    drugs = [cms.load_json(cms.ROOT / "reports" / name) for name in ("drug-validation.json", "devoted-drug-validation.json")]
    medigap = cms.load_json(PRIOR / "c23-florida-medigap.json")
    summary = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "consumer_accepted_claims": 0,
               "required_claims": len(inventory["claims"]), "required_core_cells": matrix["cell_count"],
               "additional_selected_financial_review": {k:money[k] for k in ("plans", "cells", "states")},
               "carrier_availability_checks": {"plans": len(expected), "zip_count": len(market), "scope": "one carrier"},
               "pharmacy_join_replay": {k:pharmacy[k] for k in ("plans_checked", "rows_checked")},
               "historical_carrier_drug_cases": sum(d["product_cases"] for d in drugs),
               "historical_carrier_drug_checks": sum(sum(d["check_status_counts"].values()) for d in drugs),
               "additional_drug_checks": {k:additional_drugs[k] for k in ("unique_product_formulary_cases", "plan_product_joins", "selected_field_agreements", "version_differences", "consumer_accepted_cases")},
               "clinical_participation_confirmed": 0, "hospital_cells_pending": len(provider_rows),
               "medigap": {"oir_case": "26-045612", "response": "acknowledgment only", "captured_rates": 3876, "accepted_rates": 0,
                           "effective_dates": "unverified", "filing_reproductions": 0},
               "external_dependencies": ["Authorized access resolution for stopped Medicare.gov observations", "Responsive OIR records and rate-table access", "Named Medicare subject-matter reviewer"],
               "remaining_independent_work": ["Exact SB/EOC review for every displayed core field across all 70 records; selected financial checks are partial", "Broader independent insurer drug/pharmacy and clinical participation checks", "Resolve premium PUF basis with adequate primary evidence", "Reconcile Medigap forms, dates and rates when responsive evidence arrives"],
               "input_sha256": {"matrix": cms.file_hash(PRIOR / "c19-core-benefit-matrix.json"), "sources": cms.file_hash(out / "sources.json"),
                                "manual_transcription": cms.file_hash(out / "manual-financial-transcription.json"), "pharmacy": cms.file_hash(out / "pharmacy-join-audit.json")}}
    cms.write_json(out / "validation-status.json", summary)
    return summary


def packet(release, out=OUT):
    import demo_release
    path = demo_release.resolve(release)
    manifest = demo_release.verify(path)
    inventory = cms.load_json(path / "validation-requirements.json")
    template = {"version": 1, "status": "pending", "release_id": manifest["release_id"], "manifest_sha256": cms.file_hash(path / "manifest.json"),
                "reviewer": None, "reviewed_at_utc": None, "review_after_utc": None, "review_receipt": None,
                "claims": {r["id"]: {"status": "pending", "claim_sha256": digest(r), "conditions_reviewed": False,
                                      "reconciliation_receipt": None, "reviewer": None, "reviewed_at_utc": None,
                                      "review_after_utc": None, "review_receipt": None} for r in inventory["claims"]}, "approved_outputs": {}}
    cms.write_json(out / "reviewer-template.json", template)
    cms.write_json(out / "candidate-binding.json", {"release_id": manifest["release_id"], "manifest_sha256": cms.file_hash(path / "manifest.json"),
                   "requirements_sha256": cms.file_hash(path / "validation-requirements.json"), "required_claims": len(inventory["claims"]),
                   "review_after_utc_not_extended": manifest["source_receipt"]["data_review_after_utc"], "consumer_ready": False,
                   "domain_signoff": "pending", "template_sha256": cms.file_hash(out / "reviewer-template.json")})
    return manifest["release_id"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--release", help="Bind a prepared review packet to this exact immutable candidate")
    args = parser.parse_args()
    print(packet(args.release, args.out) if args.release else build(args.out))
