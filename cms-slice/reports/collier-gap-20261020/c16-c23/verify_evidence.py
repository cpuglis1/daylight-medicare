"""Offline evidence/receipt checks. --seal writes verification and manifest."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
CMS = ROOT.parents[2]
checks = []


def read(name):
    return json.loads((ROOT / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(name, value):
    if not value:
        raise AssertionError(name)
    checks.append(name)


events = [json.loads(line) for line in (ROOT / "c16-cycle-evidence/events.jsonl").read_text().splitlines()]
requests = [e for e in events if e["kind"] == "request"]
denials = [e for e in events if e.get("http_status") == 403]
check("actual_origin_403_saved", len(denials) == 1 and denials[0]["url"].endswith("/ldflags"))
denial = denials[0]
check("no_request_after_403", not any(e["at_utc"] > denial["at_utc"] for e in requests))
check("active_persistent_source_stop", "403" in read("c16-active-stop.json")["reason"] and "403" in json.loads((CMS / "var/medicare-collector/STOP").read_text())["reason"])
spacings = [(datetime.fromisoformat(b["at_utc"]) - datetime.fromisoformat(a["at_utc"])).total_seconds() for a, b in zip(requests, requests[1:])]
check("all_recorded_dispatches_at_least_five_seconds_apart", min(spacings) >= 5)
check("request_cap_observed", len(requests) < 2000)
for p in (ROOT / "c16-cycle-evidence/receipts").glob("*.json"):
    r = json.loads(p.read_text()); raw = ROOT / "c16-cycle-evidence/raw" / r["sha256"]
    check("collector_receipt:" + p.name, raw.stat().st_size == r["bytes"] and sha(raw) == r["sha256"])
    check("no_retry:" + p.name, r["retries"] == 0)

for task, count in [("c17", 36), ("c20", 1220), ("c22", 48)]:
    r = read(task + "-dry-run.json")
    check("zero_network_dry_run:" + task, r["network_requests"] == 0 and r["logical_query_count"] == count and r["ready"] is False)
for filename in ["c17-coverage.json", "c18-market-reconciliation.json", "c20-drug-scenario-coverage.json", "c22-medigap-coverage.json"]:
    r = read(filename)
    check("no_fake_completion:" + filename, r["status"] == "blocked_origin_403" and r["new_plan_observations"] == 0)
check("all_target_zip_cells_accounted", len(read("c17-coverage.json")["cells"]) == 280)
check("no_current_market_absence_claim", all(r["medicare_gov_observed_ids"] is None and r["unexplained_differences"] is None for r in read("c18-market-reconciliation.json")["current_comparisons"]))

matrix = read("c19-core-benefit-matrix.json")
definitions = read("c19-field-dictionary.json")["definitions"]
check("all_70_plans_and_1680_field_states", len(matrix["plans"]) == 70 and len(definitions) == 24 and sum(len(r["fields"]) for r in matrix["plans"]) == 1680)
check("all_matrix_input_hashes_match", matrix["input_sha256"] == {"catalog": sha(CMS / "reports/work-package-2/catalog.json"), "quality": sha(CMS / "reports/demo-quality.json"), "source_zip": sha(CMS / "reports/work-package-1/market-12021-2027-sources.zip")})
for row in matrix["plans"]:
    check("every_field_has_a_state:" + row["id"], all(c["verification_state"] for c in row["fields"].values()))
    check("uninterpreted_inpatient_not_zero_or_ranked:" + row["id"], row["fields"]["inpatient"]["source_cell"]["value"] is None and row["fields"]["inpatient"]["ranking_allowed"] is False)
for row in read("c21-premium-basis-display.json")["records"]:
    check("both_premium_bases_visible:" + row["id"], [o["value"]["value_cents"] for o in row["premium_basis"]["observations"]] == [730, 730, 0, 0] and row["premium_source_conflict"])

choices = read("choices-source-index.json")
for capture in choices["captures"]:
    raw = ROOT / "raw" / capture["sha256"]
    check("choices_receipt:" + capture["id"], sha(raw) == capture["sha256"] and raw.stat().st_size == capture["bytes"])
    check("choices_success:" + capture["id"], capture["http_status"] == 200)
dataset = read("c23-florida-medigap.json")
check("all_partial_rate_rows_retained", len(dataset["records"]) == dataset["rate_count"] == 3876 and dataset["scenario_count"] == 17 and dataset["insurer_count"] == 34)
check("illustrative_annual_only_no_effective_date_invention", all(r["rate_type"] == "illustrative_public_comparison" and r["unit"] == "USD/year" and r["actual_rate_effective_date"] is None and r["guaranteed_issue_entitlement"] == "not_determined" for r in dataset["records"]))
check("single_irfs_naic_crosswalk_only", dataset["insurers_with_naic_verified_from_irfs"] == 1 and dataset["insurers_missing_naic"] == 33)
ack = read("c23-oir-acknowledgment.json")
check("official_oir_case_not_a_data_delivery", ack["official_tracking_number"] == "26-045612" and ack["attachments_with_dataset"] == 0 and not ack["fees_authorized"])
check("full_application_suite_passed", "Ran 191 tests" in (ROOT / "tests-final.log").read_text() and (ROOT / "tests-final.log").read_text().rstrip().endswith("OK"))
check("frozen_premium_replay_passed", read("extracted-premium-basis.json")["status"] == "pass")
selection = read("selection-receipt.json")
check("original_review_deadline_retained", selection["review_after_utc"] == "2026-10-21T01:33:00.069116+00:00")
check("selected_test_release_matches_receipt", json.loads((CMS / "releases/current.json").read_text())["release_id"] == selection["release_id"])

seal = "--seal" in sys.argv
if (ROOT / "manifest.json").exists() and not seal:
    for r in read("manifest.json")["files"]:
        check("manifest:" + r["path"], sha(ROOT / r["path"]) == r["sha256"])
result = {"status": "pass", "verified_at_utc": datetime.now(timezone.utc).isoformat(), "check_count": len(checks), "application_tests": 191,
          "collector_dispatches": len(requests), "minimum_recorded_dispatch_interval_seconds": min(spacings), "origin_403_at_utc": denial["at_utc"], "post_denial_requests": 0,
          "current_plan_observations": 0, "core_benefit_cells": 1680, "illustrative_annual_rate_rows": 3876, "insurers": 34, "oir_tracking_number": "26-045612", "checks": checks}
if seal:
    (ROOT / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    files = [{"path": str(p.relative_to(ROOT)), "sha256": sha(p), "bytes": p.stat().st_size} for p in sorted(ROOT.rglob("*")) if p.is_file() and p.name != "manifest.json" and "__pycache__" not in p.parts]
    (ROOT / "manifest.json").write_text(json.dumps({"created_at_utc": result["verified_at_utc"], "files": files, "exclusions": ["manifest.json (self)", "__pycache__/"]}, indent=2) + "\n")
print(json.dumps({k: v for k, v in result.items() if k != "checks"}))
