"""Separate historical observations from the unexecuted current ZIP/scenario sets."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CMS = ROOT.parents[2]


def write(name, obj):
    (ROOT / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def build():
    catalog = json.loads((CMS / "reports/work-package-2/catalog.json").read_text())
    rows = catalog["options"] + catalog["exclusions"]
    expected = {r["id"]: r for r in rows}
    old_path = CMS / "data-sources/medicare-gov-observations.json"
    old = json.loads(old_path.read_text())
    historical = {}
    for page in old["pages"]:
        for record in page["records"]:
            contract, plan, segment = record["raw_plan_id"].split("-")
            pid = "-".join([contract, plan.zfill(3), segment.zfill(3), old["benefit_year"]])
            historical[pid] = {"raw_record": record, "url": page["url"], "retrieved_at_utc": old["observed_at_utc"]}
    queries = json.loads((CMS / "data-sources/collector-queries.json").read_text())
    pending = {"assessed_at_utc": datetime.now(timezone.utc).isoformat(), "status": "blocked_origin_403", "reason": "Public app bootstrap returned HTTP 403 at 2026-10-20T14:45:02.585598+00:00; collector STOP remains active. No further Medicare.gov requests, alternate-browser attempts, retries or bypass. Current live observation sets remain absent; schemas and complete enumeration remain unvalidated.", "failure_evidence": "c16-browser-preflight-9/run.json", "new_plan_observations": 0}
    cells = [{"zip": zipcode, "plan_id": pid, "current_C17_state": "not_observed", "current_observation": None,
              "historical_reference": historical.get(pid) if zipcode == old["example_zip"] else None}
             for zipcode in queries["zip_set"] for pid in sorted(expected)]
    write("c17-coverage.json", {**pending, "target_plans": 70, "zip_set": queries["zip_set"], "target_plan_zip_cells": len(cells), "cells": cells,
                                 "historical_capture": {"path": str(old_path.relative_to(CMS)), "sha256": hashlib.sha256(old_path.read_bytes()).hexdigest(), "count": len(historical), "scope": old["scenario"], "not_new_C17_evidence": True}})
    absent = sorted(set(expected) - set(historical))
    write("c18-market-reconciliation.json", {**pending, "current_comparisons": [{"zip": zipcode, "status": "not_run", "cms_expected_ids": sorted(expected), "medicare_gov_observed_ids": None, "cms_only": None, "medicare_only": None, "unexplained_differences": None} for zipcode in queries["zip_set"]],
          "historical_34102_diagnostic": {"scope": "Original unassisted non-SNP comparison-card capture only; not a current complete-market check.", "observed_at_utc": old["observed_at_utc"], "cms_ids_matched": sorted(set(expected) & set(historical)), "medicare_only_ids": sorted(set(historical) - set(expected)),
          "cms_not_observed": [{"id": pid, "reason": "SNPs excluded from historical scenario; not evidence of market absence" if expected[pid]["category"] == "SNP" else "Unresolved historical observation gap"} for pid in absent]},
          "closure": "C18 and DQ-005 remain open. No withdrawn/sanctioned/restricted/statewide/regional explanation is manufactured from absence in an incomplete run."})
    for task, name in [("C20", "c20-drug-scenario-coverage.json"), ("C22", "c22-medigap-coverage.json")]:
        selected = [q for q in queries["queries"] if q["task"] == task]
        write(name, {**pending, "logical_query_count": len(selected), "completed_queries": 0, "observations": None,
                     "query_manifest_sha256": hashlib.sha256((CMS / "data-sources/collector-queries.json").read_bytes()).hexdigest(),
                     "additional_gate": "Exact drug strength/form, quantity units and retail/mail pharmacy identities need confirmation in the public UI; no estimates invented." if task == "C20" else "Insurer/letter/high-deductible/SELECT universe unknown until current Medicare.gov results are captured."})
    print(json.dumps({"target_plan_zip_cells": len(cells), "historical_plan_ids": len(historical), "historical_cms_not_observed": len(absent), "historical_extra_ids": len(set(historical) - set(expected)), "current_completed": 0}))


if __name__ == "__main__":
    build()
