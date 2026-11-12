#!/usr/bin/env python3
"""Explicit core-benefit dictionary/matrix for 70 records; no inferred benefit codes."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import zipfile

import cms_slice as cms

OUT = cms.ROOT / "reports/collier-gap-20261020/c16-c23"


def definitions():
    numeric = [
        ("part_c_premium", "Part C Premium", "USD/month", "Published Part C component; not all Medicare costs."),
        ("part_d_basic_premium", "Part D Basic Premium", "USD/month", "Published basic component; negative source credits retained."),
        ("part_d_supplemental_premium", "Part D Supplemental Premium", "USD/month", "Published supplemental component."),
        ("part_d_total_premium", "Part D Total Premium", "USD/month", "Published Part D total; retain separate subsidy/beneficiary fields."),
        ("consolidated_premium", "Monthly Consolidated Premium (Part C + D)", "USD/month", "Part C plus Part D where applicable, not total Medicare cost."),
        ("part_d_lips", "Part D LIPS (CMS Pays)", "USD/month", "Published subsidy field, not an eligibility determination."),
        ("low_income_beneficiary_premium", "Part D Low Income Beneficiary Premium Amount", "USD/month", "Published assistance-basis field, never an unconditional personal quote."),
        ("annual_part_d_deductible", "Annual Part D Deductible Amount", "USD/benefit-year", "Plan-level deductible; tier/drug exceptions require confirmation."),
        ("in_network_medical_moop", "In-Network Maximum Out-of-Pocket (MOOP) Amount", "USD/benefit-year", "Published medical limit; not premiums/Part D. Regional PPO semantics require review."),
    ]
    result = [{"id": key, "label": column, "landscape_column": column, "unit": unit, "meaning": meaning,
               "interpretation_source": "data-sources/field-mapping.json; pinned landscape README (source ZIP landscape-readme.txt)", "requires_conditions": True}
              for key, column, unit, meaning in numeric]
    complex_fields = [
        ("part_b_reduction", "Part B premium reduction", "standardBid/standardBidDetails", "USD/month; separate from plan premium and eligibility-dependent adjustments"),
        ("medical_deductible", "Medical deductible", "planLevelCostSharing", "USD/year and network/service applicability"),
        ("out_of_network_moop", "Out-of-network medical spending limit", "planLevelCostSharing", "USD/year; preserve network and Regional PPO qualifications"),
        ("combined_moop", "Combined medical spending limit", "planLevelCostSharing", "USD/year; never infer by summing in/out limits"),
        ("primary_care", "Primary care cost sharing", "benefitDetails/benefitDetailsInfo", "copay/coinsurance/range, unit, network, site and deductible conditions"),
        ("specialist", "Specialist cost sharing", "benefitDetails/benefitDetailsInfo", "copay/coinsurance/range, network/site and authorization/referral conditions"),
        ("inpatient", "Inpatient hospital cost sharing", "benefitDetails/benefitDetailsInfo", "per day/stay, day bands, benefit period, network and authorization"),
        ("emergency", "Emergency care cost sharing", "benefitDetails/benefitDetailsInfo", "per encounter, admission waiver and travel/network scope"),
        ("skilled_nursing", "Skilled nursing facility cost sharing", "benefitDetails/benefitDetailsInfo", "per day/day bands, qualifying stay, benefit period, authorization"),
        ("referrals", "Referral rules", "priorAuthorizationAndReferral/priorReferral", "service-specific scope; never decode a bare code as a yes/no rule"),
        ("prior_authorization", "Prior authorization", "priorAuthorizationAndReferral/priorAuthorization", "service-specific rules, exceptions and effective year"),
        ("dental", "Dental benefit and limits", "benefitDetails/benefitDetailsInfo", "preventive/comprehensive, annual limit, covered services, network and frequency"),
        ("vision", "Vision benefit and limits", "benefitDetails/benefitDetailsInfo", "exam/eyewear allowance, frequency, network and exclusions"),
        ("hearing", "Hearing benefit and limits", "benefitDetails/benefitDetailsInfo", "exam/devices, per ear/pair, copay/allowance, frequency and network"),
        ("travel", "Travel/out-of-area rules", "visitorTravel/visitorTravelDetails", "urgent/emergency/routine travel coverage, duration and geographic scope"),
    ]
    for key, label, section, meaning in complex_fields:
        result.append({"id": key, "label": label, "pbp_candidate_section": "/pbp/0/" + section,
                       "unit": "structured_conditioned_benefit", "meaning": meaning,
                       "interpretation_source": "Exact-year/plan Summary of Benefits or EOC passage required; raw PBP candidate sections are not a decoded field mapping.",
                       "requires_conditions": True, "ranking_allowed": False})
    return result


def build(out=OUT):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    catalog_path = cms.ROOT / "reports/work-package-2/catalog.json"
    quality_path = cms.ROOT / "reports/demo-quality.json"
    source_zip = cms.ROOT / "reports/work-package-1/market-12021-2027-sources.zip"
    catalog, quality = cms.load_json(catalog_path), cms.load_json(quality_path)
    corroboration = {(r["plan_id"], r["field"]): r for r in quality["matrix"]}
    dictionary = definitions()
    records = []
    with zipfile.ZipFile(source_zip) as archive:
        for record in sorted(catalog["options"] + catalog["exclusions"], key=lambda r: r["id"]):
            member = "pbp/" + record["id"] + ".json"
            raw_pbp = archive.read(member)
            document = json.loads(raw_pbp)
            cells = {}
            for field in dictionary:
                key = field["id"]
                if "landscape_column" in field:
                    column = field["landscape_column"]
                    evidence = {**record["source"], "column": column}
                    value = cms.money(record["landscape_raw"].get(column, cms.ABSENT), evidence, allow_negative=key == "part_d_basic_premium")
                    check = corroboration.get((record["id"], key))
                    cells[key] = {"source_cell": value, "unit": field["unit"],
                                  "verification_state": "historical_selected_field_corroboration" if check and check.get("medicare_gov", {}).get("status") == "agrees" else "captured_source_only",
                                  "medicare_gov": check.get("medicare_gov") if check else {"status": "not_observed_for_this_field"},
                                  "carrier": check.get("corroboration") if check else {"status": "not_independently_checked"},
                                  "domain_review": "pending", "new_C17_observation": False}
                    if record["id"] in {"H1889-026-000-2027", "H5594-017-000-2027"} and key in {"part_d_total_premium", "consolidated_premium"}:
                        cells[key]["verification_state"] = "unresolved_premium_basis_conflict"
                        cells[key]["ranking_allowed"] = False
                        cells[key]["explanation"] = "C21 retains $7.30 landscape total, $7.30 listed CMS-paid subsidy, $0 low-income beneficiary field and $0 monthly PUF PREMIUM separately. PUF basis unresolved."
                    if record["plan_type"] == "Regional PPO" and key == "in_network_medical_moop":
                        cells[key]["qualification"] = "Regional PPO deductible/limit and service-area meaning not independently reviewed; not substituted from PBP bands."
                else:
                    pointer = field["pbp_candidate_section"]
                    candidate = cms.pointer(document, pointer)
                    not_applicable = record["category"] == "PDP"
                    cells[key] = {"source_cell": {"state": "not_applicable_plan_category" if not_applicable else "uninterpreted_pending_document_review", "value": None},
                                  "verification_state": "not_applicable_standalone_PDP" if not_applicable else "not_independently_reviewed",
                                  "candidate_section_exists": candidate is not cms.ABSENT,
                                  "candidate_section_evidence": {"artifact": "pbp", "member": member, "member_sha256": cms.sha256(raw_pbp), "json_pointer": pointer},
                                  "qualification": "Candidate section location is navigation evidence only, not proof of a field value. Exact 2027 SB/EOC passage and interpretation remain required.",
                                  "ranking_allowed": False, "domain_review": "pending"}
                    summary = quality.get("medicare_gov_plan_summaries", {}).get(record["id"], {})
                    summary_key = {"primary_care": "primary_care_raw", "specialist": "specialist_raw"}.get(key)
                    if summary_key and summary.get(summary_key) is not None:
                        cells[key]["source_cell"] = {"state": "historical_card_summary", "raw": summary[summary_key],
                                                     "evidence": {k: summary.get(k) for k in ["url", "observed_at_utc", "qualification"]}}
                        cells[key]["verification_state"] = "historical_card_observation_conditions_unreviewed"
                        cells[key]["qualification"] = summary["qualification"]
            records.append({"id": record["id"], "name": record["name"], "category": record["category"], "plan_type": record["plan_type"],
                            "eligibility_state": "restricted_unconfirmed" if record["category"] == "SNP" else "not_assessed",
                            "fields": cells})
    states = Counter(c["verification_state"] for r in records for c in r["fields"].values())
    report = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "benefit_year": "2027", "county_fips": "12021",
              "plan_count": len(records), "field_count": len(dictionary), "cell_count": sum(len(r["fields"]) for r in records),
              "verification_counts": dict(states), "plans": records,
              "scope": "C19 dictionary/matrix completion, not completion of the G1 independent-review gate. Existing 38-plan selected-field observations and 16 carrier samples are retained with their original scope/dates; no extension of DQ-005/006 closure is claimed. Unknown/coded benefits cannot drive ranking.",
              "input_sha256": {"catalog": cms.file_hash(catalog_path), "quality": cms.file_hash(quality_path), "source_zip": cms.file_hash(source_zip)}}
    cms.write_json(out / "c19-field-dictionary.json", {"version": 1, "definitions": dictionary, "null_policy": "Zero, absent, blank, not applicable, unavailable, uninterpreted and conflicting remain distinct; never infer eligibility or noncoverage from a missing value."})
    cms.write_json(out / "c19-core-benefit-matrix.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    result = build(parser.parse_args().out)
    print(json.dumps({k: result[k] for k in ["plan_count", "field_count", "cell_count", "verification_counts"]}))
