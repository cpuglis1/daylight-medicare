"""Offline checks of C13-C15 receipts, scope and decisions. --seal writes evidence."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

from research_capture import ROOT, data

WORKSPACE = ROOT.parents[3]
checks = []


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    checks.append(name)


def load(name):
    return json.loads((ROOT / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def saved(key):
    return json.loads(data(key)[1])


def resources(key):
    return [e["resource"] for e in saved(key).get("entry", [])]


receipts = [json.loads(p.read_text()) for p in sorted((ROOT / "receipts").glob("*.json"))]
for r in receipts:
    if r.get("sha256"):
        raw = ROOT / "raw" / r["sha256"]
        check("receipt_integrity:" + r["id"], raw.stat().st_size == r["bytes"] and sha(raw) == r["sha256"])
    check("https_source:" + r["id"], urlsplit(r["requested_url"]).scheme == "https")
    check("complete_capture:" + r["id"], not r.get("truncated", False))
    if r["status"] == "retained_verified":
        check("retained_not_new_fetch:" + r["id"], r["retrieved_at_utc"] is None and r.get("original_source_record"))
    if r.get("http_status") in {403, 429}:
        check("blocked_without_retry:" + r["id"], r.get("access_state") == "blocked_no_retry" and r["retry_count"] == 0)

policy = load("c13-site-policy.json")
robots_bytes = data("medicare-robots")[1]
check("robots_exact_copy", (ROOT / "medicare-robots.txt").read_bytes() == robots_bytes)
text = robots_bytes.decode()
for label in ["Allow", "Disallow"]:
    actual = [v.strip() for v in re.findall(r"^" + label + r":\s*(.+)$", text, re.M)]
    check("robots_all_" + label.lower() + "_directives_retained", policy["robots"][label.lower()] == actual)

# RFC-style longest matching wildcard rule, with Allow winning a same-length tie.
# These are document boundary checks, not a collector implementation.
def robot_denied(path):
    matches = []
    for denied, patterns in [(False, policy["robots"]["allow"]), (True, policy["robots"]["disallow"])]:
        for pattern in patterns:
            terminal = pattern.endswith("$")
            bare = pattern[:-1] if terminal else pattern
            expression = "^" + re.escape(bare).replace(r"\*", ".*") + ("$" if terminal else "")
            if re.search(expression, path):
                matches.append((len(pattern.replace("*", "").replace("$", "")), not denied))
    return not max(matches)[1] if matches else False

cases = {
    "/plan-compare/": False, "/medigap-supplemental-insurance-plans/": False, "/care-compare/": False,
    "/robots.txt": False, "/privacy-policy": False, "/about-us/using-this-site": False,
    "/core/": True, "/core/a.css": False, "/core/a.css?v=1": False, "/core/a.js": False,
    "/profiles/a.svg": False, "/profiles/a.php": True, "/core/a.css.map": True,
    "/README.txt": True, "/web.config": True, "/admin/": True,
    "/comment/reply/5": True, "/filter/tips": True, "/node/add/": True,
    "/node/4": True, "/es/node/4": True, "/app-static-content/app.js": True,
    "/search/": True, "/medicare-search/": True, "/user/register/": True,
    "/user/password/": True, "/user/login/": True, "/user/logout/": True,
    "/index.php/app-static-content/app.js": True, "/index.php/user/login/": True,
}
for path, denied in cases.items():
    check("robots_boundary:" + path, robot_denied(path) == denied)
check("operational_unknown_api_denied", "Not approved" in policy["path_disposition"]["backend_api_and_other_hosts"])
check("no_collector_claim", policy["collector_implemented"] is False and policy["held"] == ["H09"])
medicare = sorted((r for r in receipts if urlsplit(r["requested_url"]).hostname == "www.medicare.gov"), key=lambda r: r["retrieved_at_utc"])
check("only_three_policy_requests", len(medicare) == 3 and {r["id"] for r in medicare} == {"medicare-robots", "medicare-privacy", "medicare-using-site"})
intervals = [(datetime.fromisoformat(b["retrieved_at_utc"]) - datetime.fromisoformat(a["retrieved_at_utc"])).total_seconds() for a, b in zip(medicare, medicare[1:])]
check("policy_requests_spaced_at_least_5_seconds", all(v >= 5 for v in intervals))

pricing = load("c14-price-source-decision.json")
inspection = load("monthly-archive-inspection.json")
check("eight_monthly_table_types_checked", len(inspection["headers"]) == 8 and not any(h["has_drug_unit_price_column"] for h in inspection["headers"]))
prescription = json.loads((WORKSPACE / "cms-slice/data-sources/prescription.json").read_text())
check("archive_inspection_matches_pin", inspection["source_sha256"] == prescription["source"]["sha256"] and inspection["source_bytes"] == prescription["source"]["bytes"])
check("no_2026_as_2027", pricing["public_sources"][1]["benefit_year_candidate"] == "2026" and "NO GO" in pricing["decision"])
check("feasibility_timebox_not_fabricated", "not three elapsed days" in pricing["timebox"]["actual"])
check("pricing_gaps_and_holds_preserved", {"DQ-007", "DQ-008"} <= set(pricing["open_issues"]) and {"H01", "H08", "H09"} <= set(pricing["holds"]))
check("no_spend_outreach_or_runtime_pricing", pricing["spend_usd"] == 0 and not pricing["new_outreach_sent"] and not pricing["runtime_price_data_added"])
for name, spec in prescription["documentation"].items():
    check("retained_document_pin:" + name, sha(WORKSPACE / "cms-slice" / spec["path"]) == spec["sha256"])

directories = load("c15-provider-api-discovery.json")
catalog_path = WORKSPACE / directories["catalog"]["path"]
check("catalog_pin", sha(catalog_path) == directories["catalog"]["sha256"])
catalog = json.loads(catalog_path.read_text())
expected = {r["id"]: r["landscape_raw"]["Parent Organization Name"] for r in catalog["options"] + catalog["exclusions"] if r["category"] != "PDP"}
actual = {r["id"]: a["parent"] for a in directories["assessments"] for r in a["target_plans"]}
check("all_59_medical_plans_exactly_assigned", expected == actual and len(actual) == 59 and sum(len(a["target_plans"]) for a in directories["assessments"]) == 59)
check("eight_parents_eighteen_contracts", len(directories["assessments"]) == 8 and len({c for a in directories["assessments"] for c in a["contracts"]}) == 18)
check("two_bounded_build_candidates", set(directories["c28_build_candidates"]) == {"Humana Inc.", "Devoted Health, Inc."})
for a in directories["assessments"]:
    for key in a["evidence"]:
        check("directory_evidence:" + key, (ROOT / "receipts" / (key + ".json")).exists())
    check("no_provider_participation_inferred:" + a["parent"], a["provider_participation_state"] == "unknown — call to confirm")
    check("endpoint_schema_pagination_mapping_recorded:" + a["parent"], all(a.get(x) for x in ["base_url", "capability_url", "capability_result", "schema", "pagination", "mapping_2027", "blocker"]))

for key in ["humana-capability", "devoted-metadata-json", "aetna-provider-metadata", "uhc-capability", "floridablue-capability"]:
    j = saved(key)
    check("valid_fhir_capability:" + key, j["resourceType"] == "CapabilityStatement" and j["fhirVersion"] == "4.0.1")
for prefix in ["humana", "devoted", "uhc", "curana"]:
    first, second = resources(prefix + "-plan-sample"), resources(prefix + "-pagination-next")
    check("distinct_next_page:" + prefix, first and second and first[0]["id"] != second[0]["id"])
for prefix, seed, network in [("humana", "H1036-217-000-2027", "humana-medical-network"), ("devoted", "H9884-016-000", "devoted-medical-network-json")]:
    r = resources(prefix + "-collier-plan")[0]
    check("exact_2027_seed:" + prefix, any(i["value"] == seed for i in r["identifier"]) and r["period"]["start"] == "2027-01-01" and r["network"])
    canonical = seed if seed.endswith("-2027") else seed + "-2027"
    check("seed_is_in_pinned_Collier_catalog:" + prefix, canonical in expected)
    organization = saved(network)
    check("network_reference_resolves:" + prefix, organization["resourceType"] == "Organization" and r["network"][0]["reference"].endswith("Organization/" + organization["id"]))
    check("referenced_organization_is_network:" + prefix, any(c.get("code") == "ntwk" for t in organization.get("type", []) for c in t.get("coding", [])))
blue = resources("floridablue-all-plans")
check("floridablue_27_observed_2026_only", len(blue) == saved("floridablue-all-plans")["total"] == 27 and all(p["period"] == {"start": "2026-01-01", "end": "2026-12-31"} for p in blue))
uhc = resources("uhc-collier-contract-identifier")[0]
check("uhc_exact_target_still_2026", uhc["period"]["start"] == "2026-01-01" and uhc["identifier"][0]["value"] == "H1045028000")
check("uhc_year_filter_limitation_retained", resources("uhc-2027-plan-sample")[0]["period"]["start"] == "2026-01-01")
curana = resources("curana-all-plans")
curana_target = [p for p in curana if "H9917" in json.dumps(p)]
check("curana_complete_bounded_plan_table", len(curana) == saved("curana-all-plans")["total"] == 72)
check("curana_contract_only_no_year_network", len(curana_target) == 5 and all(not p.get("period") and not p.get("network") and not p.get("identifier") for p in curana_target))
centene = saved("centene-directory-catalog-entry")[0]
check("centene_production_not_dev_int", centene["hostServers"][0]["hostName"] == "https://iopc-pd.api.centene.com/iopc/pd/" and data("centene-capability")[0]["http_status"] == 403)
check("aetna_access_failure_not_absence", data("aetna-plan-sample")[0]["http_status"] == 401)
check("elevance_no_invalid_capability_claim", data("freedom-capability")[0]["http_status"] == 500)

plan_text = (WORKSPACE / "COLLIER_DATA_GAP_PLAN_current.md").read_text()
for task in ["C13", "C14", "C15"]:
    check("checklist_complete:" + task, re.search(r"^- \[x\] \*\*" + task + r"\*\*.*DONE 2026-10-20", plan_text, re.M) is not None)
check("C01_still_deferred", re.search(r"^- \[ \] \*\*C01\*\*.*SKIP FOR NOW", plan_text, re.M) is not None)
check("C11_still_pending", re.search(r"^- \[ \] \*\*C11\*\*.*AWAITING CMS REPLY", plan_text, re.M) is not None)
for task in ["C16", "C20", "C26", "C27", "C28", "H01", "H09"]:
    check("later_task_or_hold_stays_open:" + task, re.search(r"^- \[ \] \*\*" + task + r"\*\*", plan_text, re.M) is not None)
check("G6_registration_correction", "without registration, so this route is free" not in plan_text and "developer app registration" in plan_text)

manifest_path = ROOT / "manifest.json"
seal = "--seal" in sys.argv
if manifest_path.exists() and not seal:
    for p in load("manifest.json")["files"]:
        file = ROOT / p["path"]
        check("manifest:" + p["path"], file.stat().st_size == p["bytes"] and sha(file) == p["sha256"])

result = {"status": "pass", "verified_at_utc": datetime.now(timezone.utc).isoformat(), "check_count": len(checks), "source_count": len(receipts), "robots_boundary_cases": len(cases), "medical_plans": len(actual), "parent_groups": 8, "exact_2027_seed_plans": 2, "build_candidates": directories["c28_build_candidates"], "medicare_policy_request_intervals_seconds": intervals, "scope": "Offline saved-source, discovery and checklist verification; no application/runtime code changed by C13-C15, so runtime suites were not rerun for this documentation batch.", "checks": checks}
if seal:
    (ROOT / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    files = [{"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size, "sha256": sha(p)} for p in sorted(ROOT.rglob("*")) if p.is_file() and p != manifest_path and "__pycache__" not in p.parts and p.name != "medicare-last-request.json"]
    manifest_path.write_text(json.dumps({"created_at_utc": result["verified_at_utc"], "files": files, "exclusions": ["manifest.json (self)", "__pycache__/", "medicare-last-request.json (transient pacing state)"]}, indent=2) + "\n")
print(json.dumps({k: v for k, v in result.items() if k != "checks"}))
