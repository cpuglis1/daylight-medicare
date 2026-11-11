#!/usr/bin/env python3
"""Independently reconstruct the L04 restriction check from original CMS bytes.

Uses no builder/acquirer parser. Re-extracts all PDF contracts with pdftotext
-raw, independently parses the HTML table/download blocks, and checks the
complete ten-plan population against the unchanged, revalidated baseline.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime
import hashlib
from html import unescape
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs/data/l04-pdp-availability-2026-10-25"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def plain(html):
    return " ".join(unescape(re.sub(r"<[^>]*>", " ", html)).split())


def contracts(text):
    return {a + b for a, b in re.findall(r"\b([HRS])\s*(\d{4})\b", text)}


def validate(package, output=None):
    checks, failures = Counter(), []

    def check(ok, kind, context=None):
        checks[kind] += 1
        if not ok:
            failures.append({"check": kind, "context": context})

    manifest = read(package / "manifest.json")
    for group, base in [("files", package), ("inputs", ROOT), ("code", ROOT)]:
        for name, digest in manifest[group].items():
            p = base / name
            check(p.is_file() and sha(p) == digest, "bound_" + group + "_hash", name)
    reference = ROOT / manifest["reference_package"]
    original_manifest = read(reference / "manifest.json")
    for name, digest in original_manifest["files_sha256"].items():
        check(sha(reference / name) == digest, "baseline_package_file_unchanged", name)
    check(manifest["reference_manifest_sha256"] == sha(reference / "manifest.json"), "exact_reference_binding")
    baseline_audit = read(BASE / "restriction-baseline-revalidation.json")
    check(baseline_audit["manifest_sha256"] == manifest["reference_manifest_sha256"]
          and baseline_audit["failed"] == 0 and baseline_audit["primary_field_observations_checked"] == 310,
          "baseline_raw_audit_passed")
    acquisition = ROOT / manifest["acquisition"]
    capture = read(acquisition / "source-manifest.json")
    source = {s["url"]: s for s in capture["sources"]}
    check(not capture["errors"] and not capture["stopped_hosts"], "no_unresolved_capture_error")
    index_url = capture["index_url"]
    index_html = (ROOT / source[index_url]["path"]).read_text()
    table = re.search(r'<table\b[^>]*id="dynamic_list_items_table"[^>]*>(.*?)</table>', index_html, re.S)[1]
    expected_rows = []
    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table, re.S):
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row_html, re.S)
        if not cells:
            continue
        check(len(cells) == 5, "index_five_columns")
        cells_without_labels = [re.sub(r"<label\b[^>]*>.*?</label>", "", c, flags=re.S) for c in cells]
        values = [plain(c) for c in cells_without_labels]
        href = re.search(r'<a\b[^>]*href="([^"]+)"', cells[0])[1]
        expected_rows.append(dict(zip(["action_date", "organization", "action", "basis", "effective_date"], values),
                                  url=urljoin(index_url, unescape(href))))
    check(read(acquisition / "index-rows.json") == expected_rows, "independent_index_reconstruction")
    check(len({r["url"] for r in expected_rows}) == len(expected_rows) > 0, "index_not_empty_or_duplicated")
    check(read(package / "scope.json") == read(reference / "scope.json"), "reference_scope_unchanged")
    scope = read(reference / "scope.json")
    as_of_dates = [scope["landscape_data_updated"], scope["source_cutoff_date"]]
    base_records = read(reference / "records.json")
    base_by_id = {r["offering_id"]: r for r in base_records}
    target = {r["fields"]["contract_id"]["value"] for r in base_records}
    check(len(base_records) == len(base_by_id) == 10 and len(target) == 5, "complete_baseline_population")
    observations = read(package / "observations.json")
    check(observations == read(BASE / "restriction-observations.json"), "observations_bound_to_reviewed_input")
    matched_observations = {o["pdf_url"]: o for o in observations["matched_notices"]}
    followups = {o["pdf_url"]: o for o in observations["followups_without_contract_tokens"]}
    unavailable = {o["notice_url"]: o for o in observations["unavailable_notice_dispositions"]}
    pdfs, fulltext = {}, {}
    for url, s in source.items():
        check(s["status"] == "captured" and sha(ROOT / s["path"]) == s["sha256"], "source_bytes_verified", url)
        if "text_path" not in s:
            continue
        result = subprocess.run(["pdftotext", "-raw", str(ROOT / s["path"]), "-"], check=True, capture_output=True)
        text = result.stdout.decode("utf-8")
        fulltext[url] = text
        pdfs[url] = contracts(text)
        layout = (ROOT / s["text_path"]).read_text()
        check(sha(ROOT / s["text_path"]) == s["text_sha256"], "extraction_hash", url)
        check(pdfs[url] == set(s["contract_tokens"]) == contracts(layout), "dual_extraction_exact_contract_sets", url)
        check(len(text.strip()) > 500 and text.count("\f") == s["pages"], "all_pdf_pages_extracted", url)
    for group in ("matched_notices", "followups_without_contract_tokens", "date_and_contract_exclusion_checks"):
        for o in observations[group]:
            layout_page = (ROOT / source[o["pdf_url"]]["text_path"]).read_text().split("\f")[o["page"] - 1]
            check(" ".join(o["evidence"].split()) in " ".join(layout_page.split()), "page_specific_observation", o["pdf_url"])
    ledger = read(package / "notice-ledger.json")
    check([{k: n[k] for k in ["action_date", "organization", "action", "basis", "effective_date", "url"]} for n in ledger] == expected_rows,
          "every_index_notice_dispositioned_without_omissions")
    check(len({n["url"] for n in ledger}) == len(ledger), "no_duplicate_ledger_notice")
    ledger_by_url = {n["url"]: n for n in ledger}
    relevant_fines, nonmonetary_hits, all_downloads = [], [], set()
    fine_by_contract = {c: [] for c in target}
    for row in expected_rows:
        n = ledger_by_url.get(row["url"])
        if n is None:
            continue
        page = (ROOT / source[row["url"]]["path"]).read_text()
        block = re.search(r'<div\b[^>]*class="[^"]*field--name-field-downloads\b[^>]*>(.*?)</div>', page, re.S)
        downloads = sorted({urljoin(row["url"], unescape(h)) for h in re.findall(r'<a\b[^>]*href="([^"]+)"', block[1])}) if block else []
        check(sorted(n["downloads"]) == downloads, "notice_downloads_independent_of_navigation", row["url"])
        check(sorted(p["url"] for p in n["pdf_evidence"]) == downloads, "every_linked_notice_pdf_checked", row["url"])
        all_downloads.update(downloads)
        scope_contracts = set()
        for url in downloads:
            s, direct = source[url], pdfs[url]
            inherited = set()
            if not direct:
                follow = followups.get(url)
                check(follow is not None, "identifierless_notice_explicitly_resolved", url)
                if follow:
                    inherited = pdfs[follow["base_pdf_url"]]
                    check(bool(inherited) and "Elevance" in fulltext[url], "followup_base_entity_and_contract_scope", url)
            scope_contracts |= direct | inherited
            p = next((p for p in n["pdf_evidence"] if p["url"] == url), {})
            check(p.get("direct_contract_tokens") == sorted(direct) and p.get("inherited_contract_tokens") == sorted(inherited)
                  and p.get("sha256") == s["sha256"] and p.get("text_sha256") == s["text_sha256"], "ledger_pdf_scope_and_hash", url)
            layout_pages = (ROOT / s["text_path"]).read_text().split("\f")
            check(p.get("contract_page_locators") == {t: [i + 1 for i, page_text in enumerate(layout_pages) if t in contracts(page_text)] for t in sorted(direct)},
                  "every_contract_has_exact_page_locator", url)
        hits = scope_contracts & target
        check(n["scope_contract_tokens"] == sorted(scope_contracts) and n["target_contract_matches"] == sorted(hits), "exact_target_match", row["url"])
        monetary = row["action"].startswith("Civil Money Penalty (")
        expected_kind = "civil_money_penalty" if monetary else {
            "Suspension of Enrollment": "enrollment_suspension", "Termination": "termination",
            "Sanction Release": "sanction_release", "Termination Retraction": "termination_retraction",
            "Corrective Action Progress": "corrective_action_progress",
            "Corrective Action Completed": "corrective_action_completed"
        }.get(row["action"])
        check(expected_kind is not None and n["action_kind"] == expected_kind, "action_classification_matches_source", row["url"])
        if not downloads:
            e = unavailable.get(row["url"])
            entities = {r["fields"][k]["value"].casefold() for r in base_records for k in ("contract_name", "parent_organization")}
            check(monetary and e is not None and e["organization"] == row["organization"] and e["action"] == row["action"]
                  and row["organization"].casefold() not in entities, "missing_download_nonmaterial_to_target_availability", row["url"])
            disposition = "unrelated_fine_page_without_download"
        elif hits:
            if not monetary:
                nonmonetary_hits.append(row["url"])
            check(monetary, "no_target_nonmonetary_notice", row["url"])
            relevant_fines.append(row["url"])
            for url in downloads:
                direct_hits = pdfs[url] & target
                if not direct_hits:
                    continue
                o = matched_observations.get(url)
                check(o is not None and direct_hits == {o["contract"]} and o["classification"] == "civil_money_penalty_only", "matching_notice_explicitly_interpreted", url)
                first_page = fulltext[url].split("\f")[0]
                date_strings = re.findall(r"\b[A-Z][a-z]+ \d{1,2}, \d{4}\b", first_page)
                date = datetime.strptime(date_strings[0], "%B %d, %Y").date().isoformat() if date_strings else None
                check(o is not None and date == row["action_date"] == o["notice_date"], "matched_notice_date_from_pdf", url)
                check("Notice of Imposition of Civil Money Penalty" in " ".join(first_page.split()), "penalty_subject_is_not_enrollment_suspension", url)
                check(set(re.findall(r"\$[\d,]+", row["action"])) <= set(re.findall(r"\$[\d,]+", first_page)), "fine_amount_matches_index", url)
            for c in hits:
                fine_by_contract[c].append(row["url"])
            disposition = "target_contract_historical_fine_only"
        else:
            disposition = "no_target_contract_match"
        check(n["disposition"] == disposition and n["target_availability_restriction"] is False, "notice_disposition_accurate", row["url"])
        check(row["action_date"] <= scope["source_cutoff_date"], "notice_within_evidence_cutoff", row["url"])
    check(set(pdfs) == all_downloads, "no_download_missing_or_mistaken_navigation_pdf")
    check(set(matched_observations) == {u for u, cs in pdfs.items() if cs & target}, "all_target_pdf_matches_reviewed")
    plans = read(package / "records.json")
    check(len(plans) == len({p["offering_id"] for p in plans}) == 10 and {p["offering_id"] for p in plans} == set(base_by_id), "all_ten_exact_plan_ids_checked")
    csv_expected = []
    for p in plans:
        r = base_by_id.get(p["offering_id"])
        if r is None:
            continue
        f = r["fields"]
        for key in ["contract_id", "plan_id", "segment_id", "plan_name"]:
            check(p[key] == f[key]["value"], "plan_identity_from_baseline", p["offering_id"])
        check(p["landscape_sanction_flag"] == f["sanctioned"] and f["sanctioned"]["value"] == "No" and f["sanctioned"]["state"] == "published", "baseline_sanction_observation_preserved", p["offering_id"])
        check(p["landscape_locator"] == {**r["source"], "column": "Sanctioned Plan"}, "baseline_raw_locator", p["offering_id"])
        check(p["checks"] == [{"as_of": d, "result": "no_applicable_published_restriction_found", "applicable_restriction_notices": [], "unresolved_restriction_questions": []} for d in as_of_dates]
              and not nonmonetary_hits, "both_reference_dates_reconciled", p["offering_id"])
        check(p["related_historical_fine_notice_urls"] == sorted(fine_by_contract[p["contract_id"]]) and p["live_enrollment_confirmed"] is False, "fine_and_live_availability_kept_distinct", p["offering_id"])
        for d in as_of_dates:
            csv_expected.append([p["offering_id"], p["plan_name"], d, "No", "no_applicable_published_restriction_found", "0"])
    with (package / "plan-status.csv").open(newline="") as stream:
        flat = list(csv.reader(stream))
    check(flat[1:] == csv_expected, "all_twenty_exported_plan_date_rows")
    coverage = read(package / "coverage.json")
    expected_counts = {"offering_count": 10, "contract_count": 5, "reference_dates": as_of_dates,
                       "indexed_notices_checked": len(expected_rows), "downloaded_notice_pdfs": len(all_downloads),
                       "target_matching_fine_notices": len(relevant_fines), "target_matching_nonmonetary_notices": len(nonmonetary_hits),
                       "plan_date_checks": 20, "unresolved_restriction_questions": []}
    for k, v in expected_counts.items():
        check(coverage[k] == v, "coverage_summary_matches_raw_evidence", k)
    check(coverage["action_counts"] == dict(Counter(n["action_kind"] for n in ledger)), "all_action_counts_accounted")
    check(coverage["index_action_date_min"] == min(r["action_date"] for r in expected_rows)
          and coverage["index_action_date_max"] == max(r["action_date"] for r in expected_rows), "published_search_date_bounds")
    gaps = read(package / "gaps.json")
    for k in ["genuine_published_reference_data_gaps", "known_missing_plans", "missing_modeled_fields", "unresolved_material_conflicts", "additional_L04_source_needed_for_identified_gap"]:
        check(gaps[k] == [] and not nonmonetary_hits and baseline_audit["failed"] == 0, "gap_claim_supported", k)
    check(manifest["actual_human_acceptance"] is None and manifest["baseline_reference_modified"] is False and coverage["consumer_reference_accepted"] is False, "no_acceptance_or_live_capability_inferred")
    before = read(BASE / "restriction-preservation-before.json")
    check(all((ROOT / name).is_file() and sha(ROOT / name) == digest for name, digest in before["files"].items()), "all_preexisting_bound_files_preserved")
    check((ROOT / "cms-slice/data-sources/l04-published-reference-review.json").exists() == before["review_registry_existed"], "review_registry_state_preserved")
    result = {"schema": "l04-restriction-validation/1", "manifest_sha256": sha(package / "manifest.json"),
              "passed": not failures, "failed": len(failures), "failures": failures, "checks": dict(checks),
              **expected_counts, "independent_pdf_extractions": len(pdfs), "genuine_L04_data_gaps_identified": [] if not failures else None,
              "negative_search_boundary": coverage["negative_search_boundary"], "independent_human_acceptance": False}
    if output:
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = validate(args.package.resolve(), args.out)
    print(json.dumps({k: result[k] for k in ["passed", "failed", "offering_count", "plan_date_checks", "indexed_notices_checked", "independent_pdf_extractions", "target_matching_fine_notices", "target_matching_nonmonetary_notices"]}, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
