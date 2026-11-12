#!/usr/bin/env python3
"""Normalize saved Florida CHOICES annual illustrative comparison rows offline."""
import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path

import cms_slice as cms


def normalize(row, capture, index):
    required = {"ratE_ID", "agE_CD", "seX_CD", "zipcodE_DS", "companY_NM", "plaN_CD", "ratE_AM"}
    if not required <= set(row) or row["zipcodE_DS"] != capture["inputs"]["zipCode"]:
        raise cms.SourceError("CHOICES row schema/geography changed")
    if row["agE_CD"] != capture["inputs"]["age"] or row["seX_CD"] not in {capture["inputs"]["gender"], "n"}:
        raise cms.SourceError("CHOICES age/sex filter not reflected in source rows")
    # No monthly conversion, fee inclusion assumption or extrapolation to an effective year.
    amount = row["ratE_AM"]
    cents = None if amount is None else Decimal(str(amount)) * 100
    if cents is not None and (not cents.is_finite() or cents < 0 or cents != cents.to_integral_value()):
        raise cms.SourceError("CHOICES amount is not an exact nonnegative annual-cent value")
    letter = row["plaN_CD"]
    if letter not in {"A", "B", "C", "D", "F", "G", "K", "L", "M", "N", "F*", "G*"}:
        raise cms.SourceError("Unreviewed CHOICES letter/variant")
    return {"source_rate_id": str(row["ratE_ID"]), "insurer_legal_name_raw": row["companY_NM"], "naic": None,
            "letter": letter.rstrip("*"), "high_deductible": letter.endswith("*"), "insurance_type_id_raw": row.get("inS_TYPE_ID"),
            "product_group_raw": row.get("grouP_CD"), "policy_form": None, "rating_area_raw": row["zipcodE_DS"],
            "sale_status": "not_independently_verified", "rate_type": "illustrative_public_comparison", "annual_premium_cents": None if cents is None else int(cents),
            "unit": "USD/year", "amount_state": "unavailable" if cents is None else "value", "actual_rate_effective_date": None,
            "requested_effective_date": capture["inputs"]["effectiveDate"], "effective_year_verification": "unknown_not_in_returned_schema",
            "age_raw": row["agE_CD"], "sex_raw": row["seX_CD"], "tobacco_query_raw": capture["inputs"]["smoker"],
            "rating_class_raw": row.get("ratinG_CLASS_NM"), "household_discount": "not_available_in_public_search_inputs_or_returned_schema",
            "policy_fee_amount_raw": row.get("policY_FEE_AM"), "policy_fee_assessed_code_raw": row.get("policY_FEE_ASSESSED_CD"),
            "fee_inclusion_in_premium": "unverified", "guaranteed_issue_indicator_raw": row.get("guaranteeD_ISSUE_CD"),
            "guaranteed_issue_entitlement": "not_determined", "underwriting_assumptions_raw": row.get("eligibilitY_DS"),
            "marketing_method_raw": row.get("marketinG_METHOD_CD"), "insurer_phone_raw": row.get("companY_PHONE_DS"),
            "insurer_website_raw": row.get("companY_WEBSITE_DS"),
            "evidence": {"url": capture["url"], "retrieved_at_utc": capture["retrieved_at_utc"], "sha256": capture["sha256"], "json_pointer": "/rates/" + str(index), "synthetic_scenario": capture["id"]}}


def build(source_index, out):
    source_index, out = Path(source_index), Path(out)
    source = cms.load_json(source_index)
    records = []
    for capture in source["captures"]:
        raw = source_index.parent / "raw" / capture["sha256"]
        if raw.stat().st_size != capture["bytes"] or cms.file_hash(raw) != capture["sha256"]:
            raise cms.SourceError("CHOICES source bytes changed")
        payload = json.loads(raw.read_text(), parse_float=str)
        if set(payload) != {"rates", "rateDisplays"}:
            raise cms.SourceError("CHOICES source shape changed")
        records.extend(normalize(r, capture, i) for i, r in enumerate(payload["rates"]))
    result = {"status": "partial_dataset_source_gaps_open", "rate_count": len(records), "scenario_count": len(source["captures"]),
              "insurer_count": len({r["insurer_legal_name_raw"] for r in records}), "rate_type_counts": dict(Counter(r["rate_type"] for r in records)),
              "geography": "Synthetic 34102 comparison scenarios after selecting Collier; not all Florida or every Collier ZIP.",
              "source_index_sha256": cms.file_hash(source_index), "records": records,
              "gaps": ["OIR public-records response pending", "NAIC/form identifiers and actual rate effective dates absent from returned schema", "IRFS underlying documents not yet obtained; its public request flow requires email and a challenge", "Household discount scenarios cannot be set in current public CHOICES form", "Source GI indicator is not a personal guaranteed-issue determination", "No independent second-source rate replay per insurer", "Medicare.gov C22 product universe pending; DQ-011 remains open"],
              "release_use": "Research dataset only. Every amount is an illustrative annual comparison; no real quote, acceptance, 2027 filed-rate claim or personal cost total."}
    cms.write_json(out, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-index", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.source_index, args.out)
    print(json.dumps({k: result[k] for k in ["status", "rate_count", "scenario_count", "insurer_count"]}))
