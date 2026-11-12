#!/usr/bin/env python3
"""Seal a dated CMS restriction-check supplement to the unchanged L04 reference.

No inference of live availability, human approval or personal eligibility. Any
target non-monetary match requires explicit new interpretation instead of an
automatic 'no restriction' result.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs/data/l04-pdp-availability-2026-10-25"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def tokens(text):
    return sorted(set(re.findall(r"\b[HRS]\d{4}\b", text)))


def action_kind(label):
    if label.startswith("Civil Money Penalty ("):
        return "civil_money_penalty"
    kinds = {"Suspension of Enrollment": "enrollment_suspension", "Termination": "termination",
             "Sanction Release": "sanction_release", "Termination Retraction": "termination_retraction",
             "Corrective Action Progress": "corrective_action_progress",
             "Corrective Action Completed": "corrective_action_completed"}
    if label not in kinds:
        raise ValueError(f"Uninterpreted action: {label}")
    return kinds[label]


def build(acquisition, out):
    if out.exists():
        raise ValueError("Refusing to overwrite restriction supplement")
    reference = BASE / "build-r4"
    records, scope = read(reference / "records.json"), read(reference / "scope.json")
    target = {r["fields"]["contract_id"]["value"] for r in records}
    observations = read(BASE / "restriction-observations.json")
    if target != set(observations["target_contracts"]) or len(records) != 10:
        raise ValueError("Changed target population requires a new source review")
    sources = read(acquisition / "source-manifest.json")
    if sources["errors"] or sources["stopped_hosts"]:
        raise ValueError("Unresolved acquisition error")
    source_map = {s["url"]: s for s in sources["sources"]}
    for s in sources["sources"]:
        if s["status"] != "captured" or sha(ROOT / s["path"]) != s["sha256"]:
            raise ValueError(f"Bad source capture: {s['url']}")
        if "text_path" in s and sha(ROOT / s["text_path"]) != s["text_sha256"]:
            raise ValueError("Changed extracted source")
    rows = read(acquisition / "notices.json")
    matched = {r["pdf_url"]: r for r in observations["matched_notices"]}
    followups = {r["pdf_url"]: r for r in observations["followups_without_contract_tokens"]}
    unavailable = {r["notice_url"]: r for r in observations["unavailable_notice_dispositions"]}
    for group in ("matched_notices", "followups_without_contract_tokens", "date_and_contract_exclusion_checks"):
        for o in observations[group]:
            pages = (ROOT / source_map[o["pdf_url"]]["text_path"]).read_text().split("\f")
            page = " ".join(pages[o["page"] - 1].split())
            if " ".join(o["evidence"].split()) not in page:
                raise ValueError(f"Unsupported source observation: {o['pdf_url']}")
    ledger = []
    for row in rows:
        kind = action_kind(row["action"])
        pdfs = []
        contract_set = set()
        for url in row["downloads"]:
            s = source_map[url]
            if "text_path" not in s:
                raise ValueError("Non-PDF or unextracted notice download")
            body = (ROOT / s["text_path"]).read_text()
            direct = set(tokens(body))
            inherited = set()
            if not direct:
                if url not in followups:
                    raise ValueError(f"Notice without contract identifiers needs review: {url}")
                inherited = set(source_map[followups[url]["base_pdf_url"]]["contract_tokens"])
                if not inherited:
                    raise ValueError("Follow-up has no resolved base contract scope")
            contract_set.update(direct | inherited)
            pdfs.append({"url": url, "sha256": s["sha256"], "text_sha256": s["text_sha256"],
                         "direct_contract_tokens": sorted(direct), "inherited_contract_tokens": sorted(inherited),
                         "base_pdf_url": followups[url]["base_pdf_url"] if url in followups else None,
                         "contract_page_locators": {t: [i + 1 for i, p in enumerate(body.split("\f")) if t in tokens(p)] for t in sorted(direct)}})
        hits = sorted(contract_set & target)
        if not pdfs:
            exception = unavailable.get(row["url"])
            if kind != "civil_money_penalty" or not exception or any(row[k] != exception[k] for k in ("organization", "action")):
                raise ValueError("Missing potentially material notice")
            disposition = "unrelated_fine_page_without_download"
        elif hits:
            if kind != "civil_money_penalty":
                raise ValueError("Target restriction/release match requires a new explicit status review")
            for pdf in pdfs:
                hit = set(pdf["direct_contract_tokens"]) & target
                if hit and (pdf["url"] not in matched or hit != {matched[pdf["url"]]["contract"]}
                            or matched[pdf["url"]]["classification"] != "civil_money_penalty_only"
                            or matched[pdf["url"]]["notice_date"] != row["action_date"]):
                    raise ValueError("Unreviewed or misdated matching fine")
            disposition = "target_contract_historical_fine_only"
        else:
            disposition = "no_target_contract_match"
        ledger.append({**row, "action_kind": kind, "pdf_evidence": pdfs,
                       "scope_contract_tokens": sorted(contract_set), "target_contract_matches": hits,
                       "disposition": disposition,
                       "target_availability_restriction": False,
                       "date_basis": "Index action/effective labels retained separately; PDF operative dates control. No target restriction interval found."})
    dates = [scope["landscape_data_updated"], scope["source_cutoff_date"]]
    plans = []
    for r in records:
        f = r["fields"]
        contract = f["contract_id"]["value"]
        if f["sanctioned"]["state"] != "published" or f["sanctioned"]["value"] != "No":
            raise ValueError("Baseline sanction flag requires explicit reconciliation")
        plans.append({"offering_id": r["offering_id"], "contract_id": contract,
                      "plan_id": f["plan_id"]["value"], "segment_id": f["segment_id"]["value"],
                      "plan_name": f["plan_name"]["value"], "landscape_sanction_flag": f["sanctioned"],
                      "landscape_locator": {**r["source"], "column": "Sanctioned Plan"},
                      "checks": [{"as_of": date, "result": "no_applicable_published_restriction_found",
                                  "applicable_restriction_notices": [], "unresolved_restriction_questions": []} for date in dates],
                      "related_historical_fine_notice_urls": sorted(n["url"] for n in ledger if contract in n["target_contract_matches"]),
                      "live_enrollment_confirmed": False})
    coverage = {"offering_count": len(plans), "contract_count": len(target), "reference_dates": dates,
                "indexed_notices_checked": len(ledger), "downloaded_notice_pdfs": len({p["url"] for n in ledger for p in n["pdf_evidence"]}),
                "index_action_date_min": min(n["action_date"] for n in ledger),
                "index_action_date_max": max(n["action_date"] for n in ledger),
                "action_counts": dict(Counter(n["action_kind"] for n in ledger)),
                "target_matching_fine_notices": sum(bool(n["target_contract_matches"]) for n in ledger),
                "target_matching_nonmonetary_notices": sum(bool(n["target_contract_matches"]) and n["action_kind"] != "civil_money_penalty" for n in ledger),
                "plan_date_checks": len(plans) * len(dates), "unresolved_restriction_questions": [],
                "available_notice_download_coverage_complete": True,
                "unavailable_download_dispositions": observations["unavailable_notice_dispositions"],
                "negative_search_boundary": "Pinned official 2026 landscape sanction flags plus every notice in the CMS recent enforcement index captured October 25, 2026. Not an all-time enforcement history or live enrollment assurance.",
                "consumer_reference_accepted": False}
    gaps = {"genuine_published_reference_data_gaps": [], "restriction_date_reconciliation": "complete_with_no_applicable_restriction_found",
            "known_missing_plans": [], "missing_modeled_fields": [], "unresolved_material_conflicts": [],
            "additional_L04_source_needed_for_identified_gap": [],
            "corroboration_limits_separate_from_missing_data": ["Five carrier SBs not acquired; all corresponding CMS reference fields populated and validated.",
                "Some landscape fields have no second-source cell comparison.", "PBP provides explicit deductible amounts for only five plans; reference amounts for all ten are validated elsewhere."],
            "source_limit_without_target_availability_impact": observations["unavailable_notice_dispositions"],
            "release_acceptance_separate_from_data_gaps": "Existing actual human/source-use acceptance gates remain unchanged; no acceptance recorded by this check.",
            "outside_published_reference": ["Live enrollment confirmation", "Complete historical status ledger", "Personal eligibility/compatibility", "Drug formularies, pharmacy networks and personal drug prices", "Recommendations"]}
    out.mkdir()
    for name, value in [("records.json", plans), ("notice-ledger.json", ledger), ("coverage.json", coverage),
                        ("gaps.json", gaps), ("observations.json", observations), ("scope.json", scope)]:
        write(out / name, value)
    with (out / "plan-status.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["offering_id", "plan_name", "as_of", "landscape_sanction_flag", "restriction_check", "applicable_restriction_count"])
        for p in plans:
            for check in p["checks"]:
                writer.writerow([p["offering_id"], p["plan_name"], check["as_of"], p["landscape_sanction_flag"]["value"], check["result"], 0])
    inputs = [reference / "manifest.json", reference / "records.json", reference / "scope.json", reference / "coverage.json",
              BASE / "build-r4-validation.json", BASE / "restriction-baseline-revalidation.json", BASE / "restriction-observations.json",
              acquisition / "source-manifest.json", acquisition / "index-rows.json", acquisition / "notices.json"]
    inputs += [ROOT / s[k] for s in sources["sources"] for k in ("path", "text_path") if k in s]
    code = [ROOT / "cms-slice/scripts" / name for name in
            ["l04_restriction_acquire.py", "l04_restriction_build.py", "l04_restriction_validate.py"]]
    manifest = {"schema": "l04-restriction-supplement/1", "package_id": "L04-FL-2026-RESTRICTION-CHECK-" + out.name,
                "reference_package": str(reference.relative_to(ROOT)), "reference_manifest_sha256": sha(reference / "manifest.json"),
                "acquisition": str(acquisition.relative_to(ROOT)),
                "files": {str(p.relative_to(out)): sha(p) for p in sorted(out.iterdir())},
                "inputs": {str(p.relative_to(ROOT)): sha(p) for p in sorted(set(inputs))},
                "code": {str(p.relative_to(ROOT)): sha(p) for p in code},
                "actual_human_acceptance": None, "baseline_reference_modified": False}
    write(out / "manifest.json", manifest)
    return coverage


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acquisition", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.acquisition.resolve(), args.out.resolve()), indent=2, sort_keys=True))
