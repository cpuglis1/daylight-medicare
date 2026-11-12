#!/usr/bin/env python3
"""An exact second-carrier sample: positive ST, a QL brand, and absent-brand uncertainty."""

from collections import Counter
import json
import re
import subprocess
from urllib.parse import urlencode

import cms_slice as cms
from drug_validation import replay_rows
from evidence_store import PublicSources, VisibleHTML, html_text
import prescription as rx

OUT = cms.ROOT / "reports/devoted-drug-validation.json"
SOURCE_IDS = ("devoted-016-documents", "devoted-2027-formulary-excmod", "devoted-2027-st-index", "devoted-2027-st-cor")


def build(sources=None, out=OUT):
    sources = sources or PublicSources()
    config = cms.load_json(rx.CONFIG)
    report = rx.verify(config)
    plan_id, formulary_id = "H9884-016-000-2027", "00027129"
    join = next(j for j in report["joins"] if j["id"] == plan_id)
    if join["selected_plan"]["raw"]["FORMULARY_ID"] != formulary_id:
        raise cms.SourceError("Devoted plan/formulary identity changed")
    specs, documents = {}, {}
    for source_id in SOURCE_IDS:
        spec, raw = sources.read(source_id)
        specs[source_id] = spec
        if raw.startswith(b"%PDF"):
            documents[source_id] = subprocess.run(["pdftotext", "-layout", str(sources.raw/spec["sha256"]), "-"], check=True, capture_output=True).stdout.decode().split("\f")
        else:
            documents[source_id] = html_text(raw)
    page = documents["devoted-016-documents"]
    parser = VisibleHTML()
    parser.feed(sources.read("devoted-016-documents")[1].decode())
    if not all(s in page for s in ("DEVOTED CHOICE GIVEBACK 016 FL (PPO)", "Collier", "2027 Drug List")) or specs["devoted-2027-formulary-excmod"]["requested_url"] not in parser.links:
        raise cms.SourceError("Exact plan document linkage changed")
    pages = documents["devoted-2027-formulary-excmod"]
    if "2027 Formulary" not in pages[0] or "Approved Formulary ID 00027129" not in pages[0] or "DEVOTED CHOICE GIVEBACK 016 FL" not in pages[1]:
        raise cms.SourceError("Second carrier formulary scope changed")
    st_index = documents["devoted-2027-st-index"]
    if not all(s in st_index for s in ("2027 Part D Step Therapy Criteria", "All other Florida plans")) or not all(s in documents["devoted-2027-st-cor"][0] for s in ("Step Therapy Criteria", "GOUT", "FEBUXOSTAT", "Updated 10/15/2026")):
        raise cms.SourceError("Published ST criteria context changed")
    expected = [
        ("834235", "febuxostat", "febuxostat 40 MG Oral Tablet", 13, r"febuxostat TABS 40mg, 80mg\s+4\s+ST", {"TIER_LEVEL_VALUE":"4", "PRIOR_AUTHORIZATION_YN":"N", "STEP_THERAPY_YN":"Y", "QUANTITY_LIMIT_YN":"N"}),
        ("834241", "febuxostat", "febuxostat 80 MG Oral Tablet", 13, r"febuxostat TABS 40mg, 80mg\s+4\s+ST", {"TIER_LEVEL_VALUE":"4", "PRIOR_AUTHORIZATION_YN":"N", "STEP_THERAPY_YN":"Y", "QUANTITY_LIMIT_YN":"N"}),
        ("1364447", "eliquis", "apixaban 5 MG Oral Tablet [Eliquis]", 65, r"ELIQUIS TABS 5mg\s+3\s+QL \(74 tabs / 30 days\)", {"TIER_LEVEL_VALUE":"3", "PRIOR_AUTHORIZATION_YN":"N", "STEP_THERAPY_YN":"N", "QUANTITY_LIMIT_YN":"Y", "QUANTITY_LIMIT_DAYS":"30"})]
    all_rows = [{"evidence":e, "raw":r} for e,r in rx.captured_rows(rx.CACHE/"formulary.psv.gz") if r["FORMULARY_ID"] == formulary_id and r["CONTRACT_YEAR"] == "2027"]
    cases, checked_rows, counts = [], [], Counter()
    vocabularies = {}
    for code, query, name, number, pattern, fields in expected:
        url = "https://rxnav.nlm.nih.gov/REST/drugs.json?"+urlencode({"name":query})
        spec, payload = sources.json("rxnorm-"+cms.sha256(url.encode())[:16])
        vocabularies[query] = (spec, payload)
        if not any(x["rxcui"] == code and x["name"] == name for g in payload["drugGroup"]["conceptGroup"] for x in g.get("conceptProperties") or []):
            raise cms.SourceError("Exact second-carrier vocabulary concept changed")
        matched_lines = [line.strip() for line in pages[number-1].splitlines() if re.fullmatch(pattern+r"\s*",line)]
        rows = [r for r in all_rows if r["raw"]["RXCUI"] == code]
        if len(matched_lines) != 1 or len(rows) != 1:
            raise cms.SourceError("Exact carrier sample row absent/ambiguous")
        checks = {key:"agrees" if rows[0]["raw"][key] == value else "conflict" for key,value in fields.items()}
        counts.update(checks.values())
        checked_rows += rows
        cases.append({"rxcui":code, "vocabulary_name":name, "vocabulary_evidence":PublicSources.evidence(spec), "pdf_page":number,
                      "carrier_raw_line":matched_lines[0], "cms_row":rows[0], "checks":checks,
                      "quantity_unit_status":"not_applicable_no_QL_marker" if fields["QUANTITY_LIMIT_YN"] == "N" else "CMS_unit_unresolved_no_conversion",
                      "personal_approval":None})
    absent_code = "834239"
    spec, payload = vocabularies["febuxostat"]
    if not any(x["rxcui"] == absent_code and x["name"] == "febuxostat 40 MG Oral Tablet [Uloric]" for g in payload["drugGroup"]["conceptGroup"] for x in g.get("conceptProperties") or []):
        raise cms.SourceError("Absent-brand vocabulary identity changed")
    if any(r["raw"]["RXCUI"] == absent_code for r in all_rows):
        raise cms.SourceError("Previously absent brand now listed; review this changed case")
    result = {"plan_id":plan_id, "formulary_id":formulary_id, "product_cases":3, "positive_step_therapy_products":2,
              "check_status_counts":dict(counts), "cases":cases, "source_replay":replay_rows(config,checked_rows),
              "absent_brand_case":{"rxcui":absent_code, "vocabulary_name":"febuxostat 40 MG Oral Tablet [Uloric]", "basic_formulary_match":False,
                                   "related_generic_rxcui":"834235", "vocabulary_evidence":PublicSources.evidence(spec),
                                   "status":"absence_not_noncoverage; generic presence_does_not_confirm_brand", "personal_coverage":None},
              "sources":{sid:PublicSources.evidence(spec) for sid,spec in specs.items()},
              "manual_mapping":"Exact plan document page links the approved formulary. The separately inspected 2027 ST index assigns this plan under All other Florida plans; PDF criteria p1 has FEBUXOSTAT. No clinical criteria are evaluated for a person.",
              "visual_review":"Formulary PDF pages 2,13,65 and ST criteria page1 rendered and inspected; qualified review pending",
              "domain_signoff":"pending", "code_sha256":cms.file_hash(__file__), "prescription_manifest_sha256":cms.file_hash(rx.REPORTS/"manifest.json")}
    cms.write_json(out,result)
    if counts["conflict"]:
        raise cms.SourceError("Second-carrier restriction conflict; preserve and investigate")
    return result


if __name__ == "__main__":
    try:
        r=build()
        print(json.dumps({k:r[k] for k in ("product_cases","positive_step_therapy_products","check_status_counts","source_replay")},indent=2))
    except (cms.SourceError,OSError,ValueError,KeyError,subprocess.CalledProcessError) as error:
        raise SystemExit("Second-carrier validation unavailable: "+str(error))
