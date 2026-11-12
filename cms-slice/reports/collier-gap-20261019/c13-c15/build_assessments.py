"""Build dated assessment artifacts from saved primary-source responses; no network."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from research_capture import ROOT, data

WORKSPACE = ROOT.parents[3]
CMS = WORKSPACE / "cms-slice"


def write(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resource(key):
    return json.loads(data(key)[1])


def plan(key):
    return resource(key)["entry"][0]["resource"]


def brief_plan(key):
    p = plan(key)
    return {"evidence": key, **{k: p.get(k) for k in
            ["resourceType", "id", "identifier", "name", "period", "network"]}}


now = datetime.now(timezone.utc).isoformat()

# The existing PDFs retain their original provenance, rather than pretending to fetch again.
prescription = json.loads((CMS / "data-sources/prescription.json").read_text())
for filename, spec in prescription["documentation"].items():
    source = CMS / spec["path"]
    assert digest(source) == spec["sha256"]
    shutil.copyfile(source, ROOT / "raw" / spec["sha256"])
    key = "retained-cms-" + filename.removesuffix(".pdf")
    write("receipts/" + key + ".json", {
        "id": key, "requested_url": spec["url"], "status": "retained_verified",
        "original_source_record": "cms-slice/data-sources/prescription.json#/documentation/" + filename,
        "verified_at_utc": now, "retrieved_at_utc": None,
        "qualification": "Previously captured primary PDF; no fresh retrieval date asserted.",
        "sha256": spec["sha256"], "bytes": spec["bytes"], "content_type": "application/pdf",
    })
    subprocess.run(["pdftotext", "-layout", str(source), str(ROOT / filename.replace(".pdf", ".txt"))], check=True)

# C13: retain exact robots directives and distinguish them from the narrower collector policy.
robots_receipt, robots_bytes = data("medicare-robots")
robots = robots_bytes.decode()
(ROOT / "medicare-robots.txt").write_bytes(robots_bytes)
allow = re.findall(r"^Allow:\s*(.+)$", robots, re.M)
deny = re.findall(r"^Disallow:\s*(.+)$", robots, re.M)
allow = [x.strip() for x in allow]
deny = [x.strip() for x in deny]
policy = {
    "task": "C13", "status": "complete", "assessed_at_utc": now,
    "decision": "Allow bounded synthetic public-page observations subject to robots and G9; unknown backend paths require separate engineering review in C16.",
    "legal_approval": {"state": "owner_reported_approved_C12", "evidence": "../c09-c12/c12-legal-decision.json"},
    "robots": {"evidence": "medicare-robots", "host_scope": "www.medicare.gov",
               "user_agent_group": "*", "sha256": robots_receipt["sha256"],
               "retrieved_at_utc": robots_receipt["retrieved_at_utc"],
               "review_due_at_utc": (datetime.fromisoformat(robots_receipt["retrieved_at_utc"]) + timedelta(hours=24)).isoformat(),
               "allow": allow, "disallow": deny},
    "reviewed_public_entry_paths": ["/plan-compare/", "/medigap-supplemental-insurance-plans/", "/care-compare/"],
    "reviewed_policy_paths": ["/robots.txt", "/privacy-policy", "/about-us/using-this-site"],
    "path_disposition": {
        "reviewed_entries": "Not disallowed by saved robots; eligible for bounded synthetic observation under G9.",
        "core_profiles": "Only the explicit CSS/JS/image exceptions override those directory denials. Other assets remain denied.",
        "app_static_content": "Denied, including the /index.php/ variant. C16 must not load it merely because a page depends on it.",
        "account_login_member": "Excluded from collector scope even if a particular route is not named in robots.",
        "backend_api_and_other_hosts": "Not approved by this review. Review actual paths, host-specific robots/policies and response shape before adding to C16's bounded manifest.",
        "entry_subroutes": "Not automatically approved by approval of an entry URL; enumerate and review in C16.",
    },
    "policy_findings": [
        {"evidence": "medicare-privacy", "finding": "Privacy, security, cookies and account-data practices; no affirmative blanket grant for automated reuse found in this saved page."},
        {"evidence": "medicare-using-site", "finding": "Accessibility, linking and security-reporting information; no blanket automated collection grant found in this saved page."},
        {"evidence": "cms-linking-policy", "finding": "External links do not confer CMS endorsement; linked sites retain their own policies."},
    ],
    "interpretation": "Robots non-denial is a crawl boundary, not a legal license or a claim about third-party rights. C12 approval remains recorded; no new legal sign-off requested.",
    "guardrails_for_C16": {
        "minimum_interval_seconds": 5, "maximum_requests_per_run": 2000,
        "rate_scope": "All outgoing collector requests, including browser subresources; block denied/unreviewed requests before navigation.",
        "schedule": "Off-peak Eastern, preferably overnight", "inputs": "Fixed synthetic C17/C20/C22/C27 sets only",
        "user_agent": "Descriptive application name and owner contact", "cache": "No identical query in a refresh cycle",
        "stop_on": ["403", "429", "CAPTCHA", "block page", "unexpected schema/page shape", "newly disallowed path"],
        "forbidden": ["real beneficiary inputs (H09)", "logged-in pages", "login or CAPTCHA bypass", "IP rotation or proxies to evade restrictions"],
        "receipts": ["synthetic inputs", "URL", "UTC retrieval time", "raw response or page snapshot", "SHA-256", "parser version"],
        "preflight": "Refresh robots/policy review before use if 24-hour review window expires; do not renew other source/release deadlines.",
        "dry_run_and_kill_switch": "Required by C16, not implemented in this assessment",
    },
    "execution": "Only robots/privacy/using-this-site pages were requested here; three identified Medicare.gov GETs spaced at least five seconds. No Plan Finder scenario, member or provider data query was run on Medicare.gov.",
    "held": ["H09"], "collector_implemented": False,
}
write("c13-site-policy.json", policy)

# C14: close the bounded source decision, without claiming three calendar days elapsed.
discovery = json.loads((ROOT / "cms-release-discovery.json").read_text())
monthly = json.loads((ROOT / "monthly-archive-inspection.json").read_text())
pricing = {
    "task": "C14", "status": "complete_assessment_no_go", "assessed_at_utc": now,
    "timebox": {"planned": "Three-day feasibility effort", "actual": "Expedited point-in-time assessment on October 19–20, 2026 Eastern; not three elapsed days of monitoring or supplier replies.",
                "completion_basis": "Catalog discovery, retained archive/header inspection, official pricing-grain documentation and public commercial offering review support a present no-go decision. Future availability is not predicted."},
    "decision": "NO GO for a personal 2027 drug-cost calculator; no adequate authorized 2027 negotiated price feed has been obtained.",
    "public_sources": [
        {"source": "CMS monthly 2027 PUF", "evidence": ["cms-public-catalog-c14", "retained-cms-methodology-2027", "retained-cms-layout-2027"],
         "distribution": discovery["monthly"], "archive_inspection": "monthly-archive-inspection.json",
         "archive_sha256": monthly["source_sha256"], "archive_bytes": monthly["source_bytes"],
         "result": "Full retained archive hash verified; eight distinct table headers re-read; six pharmacy partitions share the pinned layout. No per-drug negotiated unit-price table. Tier copays/coinsurance and dispensing fees do not supply that missing price."},
        {"source": "CMS quarterly pricing PUF", "evidence": ["cms-public-catalog-c14", "retained-cms-quarterly-methodology-2026", "retained-cms-quarterly-layout-2026"],
         "distribution": discovery["quarterly"], "benefit_year_candidate": "2026",
         "result": "Latest selected current catalog distribution is SPUF_2026_20261007.zip, not a 2027 feed. Retained official methodology describes plan-level average monthly unit costs; layout defines plan/segment/NDC/days-supply average in-area retail unit cost, without pharmacy ID in the pricing table. Unsuitable for a store-specific quote even if an appropriate future-year average file appears.",
         "scope": "Fresh catalog selection plus verified retained documentation; quarterly raw ZIP was not newly downloaded or scanned in C14."},
        {"source": "CMS/MPF external access inquiry", "evidence": "../c09-c12/c11-send-receipt.json", "result": "C11 reply/access grant remains pending; no licensed feed assumed."},
        {"source": "Medicare.gov fixed synthetic observations", "evidence": "c13-site-policy.json", "result": "Future C20 dated examples only; no observation run in this assessment and no personal query service authorized (H09)."},
    ],
    "commercial_sources": [
        {"name": "ConnectureDRX", "evidence": ["connecture-pricing-api", "connecture-plancompare"],
         "published_claim": "Medicare comparison APIs, dosage-specific pricing and monthly out-of-pocket estimates across benefit phases.",
         "verified_access": False, "adequate_for_calculator": False,
         "missing": ["executed license/redisplay and retention rights", "2027 Collier plan coverage", "pharmacy-specific data grain", "sample payload and validation cases", "price and refresh SLA"]},
        {"name": "SunFire", "evidence": ["sunfire-home", "sunfire-quoting"],
         "published_claim": "MAPD/PDP quoting/enrollment platform and existing/custom APIs; public pages do not verify a standalone 2027 negotiated drug-price data license.",
         "verified_access": False, "adequate_for_calculator": False,
         "missing": ["drug-price API availability and scope", "2027 Collier coverage", "sample/schema/grain", "reuse license, pricing and cadence"]},
        {"name": "CSG Market Advisor", "evidence": "../c09-c12/c10-csg-decision.json",
         "result": "Prior optional subscription decision deferred. A quoted tool subscription is not evidence of a licensed 2027 raw drug-price feed.", "adequate_for_calculator": False},
    ],
    "minimum_source_acceptance": [
        "Authorized contract or official access grant with display, caching, retention and derivative-calculation rights for this use.",
        "Benefit year 2027 and exact CMS contract/plan/segment identity; coverage or explicit unavailable states for all 61 drug-bearing Collier records.",
        "Exact drug identifier and strength/form, quantity/unit, days supply, pharmacy identifier or explicitly labeled average grain, retail/mail and preferred status.",
        "Negotiated unit/total price definition, dispensing-fee inclusion, effective/as-of dates, refresh cadence and correction policy.",
        "Plan cost-sharing rules and benefit-phase calculation inputs validated against dated fixed synthetic worked cases; no substitution of 2026 values.",
        "Source and calculation version receipts, error/missing-data behavior and independent reconciliation before H01 can be approved.",
    ],
    "next_trigger": "Reassess when C11 returns an authorized 2027 route, CMS publishes a 2027 pricing distribution, or an approved commercial evaluation produces a license and representative sample. Supplier outreach/purchase/account creation was not performed in C14.",
    "R1_behavior": "Retain 61-plan coverage/tier/restriction and pharmacy evidence; link Plan Finder for personal estimates. Future C20 observations are dated synthetic examples.",
    "holds": ["H01", "H08", "H09"], "open_issues": ["DQ-007", "DQ-008"],
    "date_ambiguity": prescription["date_discrepancy"], "spend_usd": 0,
    "new_outreach_sent": False, "runtime_price_data_added": False,
}
write("c14-price-source-decision.json", pricing)

# C15: retain every target identity and a bounded, provider-independent discovery result.
catalog_path = CMS / "reports/work-package-2/catalog.json"
catalog = json.loads(catalog_path.read_text())
groups = defaultdict(list)
for record in catalog["options"] + catalog["exclusions"]:
    if record["category"] != "PDP":
        groups[record["landscape_raw"]["Parent Organization Name"]].append({"id": record["id"], "name": record["name"], "contract": record["identity"]["contract"]})

assessments = [
    {"parent": "Centene Corporation", "brands": ["Wellcare"],
     "primary_docs": ["centene-partners", "centene-documentation", "centene-api-catalog", "centene-directory-catalog-entry", "centene-directory-openapi-link"],
     "base_url": "https://iopc-pd.api.centene.com/iopc/pd/", "capability_evidence": "centene-capability", "capability_result": "HTTP 403; stop without retry or bypass.",
     "schema": "centene-openapi.json: public OpenAPI 3.0.1, FHIR 4.0.1 resources, including InsurancePlan, OrganizationAffiliation, PractitionerRole and Location. Catalog says authentication None and separately identifies the production server. OpenAPI servers entry is dev-int; it was not treated as production.",
     "pagination": "OpenAPI InsurancePlan and PractitionerRole searches document _next/_page parameters; no live page verified because production metadata was blocked.",
     "mapping_2027": "Unverified; no production InsurancePlan rows obtained.", "c28_disposition": "defer", "blocker": "Production 403 despite public catalog; obtain functioning published route or app access without bypass.",
     "evidence": ["centene-capability", "centene-directory-catalog-entry", "centene-directory-openapi-link"]},
    {"parent": "Guidewell Mutual Holding Corporation", "brands": ["Florida Blue", "Florida Blue Medicare"],
     "primary_docs": ["floridablue-directory-doc", "floridablue-product"],
     "base_url": "https://apigw.bcbsfl.com/interop/interop-developer-portal/emr/api/v1/fhir/",
     "capability_url": "https://apigw.bcbsfl.com/interop/interop-developer-portal/cms/iop/v1/pd/R4/metadata",
     "capability_evidence": "floridablue-capability", "capability_result": "HTTP 200 FHIR 4.0.1, but broad generic clinical metadata does not establish access to those clinical resources. No internal metadata/OAuth URLs were followed.",
     "schema": "floridablue-openapi.json: embedded primary Swagger 2 directory schema, 15 path templates covering seven resource families plus root, security empty. Product-code InsurancePlan records are not an exact CMS plan crosswalk.",
     "pagination": "Bounded _count=50 request returned all 27 InsurancePlans (total 27), no next link.",
     "mapping_2027": "All 27 returned InsurancePlan periods are 2026-01-01 to 2026-12-31; no 2027 mapping established in this bounded table.",
     "c28_disposition": "defer", "blocker": "Need published 2027 rows and exact CMS contract/plan/segment to medical-network crosswalk.",
     "evidence": ["floridablue-capability", "floridablue-all-plans", "floridablue-directory-doc"]},
    {"parent": "Humana Inc.", "brands": ["Humana"], "primary_docs": ["humana-developers"],
     "base_url": "https://fhir.humana.com/api/", "capability_evidence": "humana-capability", "capability_result": "HTTP 200 CapabilityStatement, FHIR 4.0.1.",
     "schema": "InsurancePlan has exact CMS-style identifier, period and network references. PractitionerRole search supports practitioner, organization, location, specialty, active and date. Resolve network types explicitly; returned plan also references dental/LTC and older-named pharmacy networks.",
     "pagination": "Server next link with _continuationToken followed once; second one-row page succeeded and differs from the first.",
     "mapping_2027": "Exact H1036-217-000-2027 record, period begins 2027-01-01, five network references. FL Medicare HMO Organization reference resolves HTTP 200. Representative discovery only; remaining 16 plan mappings not yet validated.",
     "mapped_seed": brief_plan("humana-collier-plan"), "c28_disposition": "eligible_for_bounded_adapter_build", "blocker": "C28 must map every supported plan and validate exact provider/location/plan cases before user participation answers.",
     "evidence": ["humana-capability", "humana-plan-sample", "humana-pagination-next", "humana-collier-plan", "humana-medical-network"]},
    {"parent": "UnitedHealth Group, Inc.", "brands": ["UnitedHealthcare", "AARP", "CarePlus is not assumed"],
     "primary_docs": ["https://www.uhc.com/legal/interoperability-apis/patient-access-api"],
     "base_url": "https://flex.optum.com/fhirpublic/R4/", "capability_evidence": "uhc-capability", "capability_result": "HTTP 200 CapabilityStatement, FHIR 4.0.1; public provider directory base, distinct from member/patient APIs.",
     "schema": "InsurancePlan identifier is compact contract/PBP/segment without hyphens or year (e.g. H1045028000); metadata advertises period and identifier search. PractitionerRole and OrganizationAffiliation include network parameters.",
     "pagination": "Server next link (_getpages/_getpagesoffset) followed once successfully; distinct second record.",
     "mapping_2027": "Exact compact H1045028000 returns one record dated 2026, not 2027. A period=ge2027-01-01 sample still returned a 2026 record: do not trust that filter or use total 1395 as proof of 2027 coverage. An initial hyphenated/year-suffixed identifier returned zero and is retained as a negative probe, not absence evidence.",
     "observed_plan": brief_plan("uhc-collier-contract-identifier"), "c28_disposition": "defer", "blocker": "Need actual 2027 period and exact medical-network mapping; validate filtering.",
     "evidence": ["uhc-capability", "uhc-plan-sample", "uhc-pagination-next", "uhc-2027-plan-sample", "uhc-collier-plan", "uhc-collier-contract-identifier", "uhc-directory-guide"]},
    {"parent": "CVS Health Corporation", "brands": ["Aetna"], "primary_docs": ["aetna-developers", "aetna-provider-token-guide"],
     "base_url": "https://apif1.aetna.com/fhir/v1/providerdirectory/", "capability_evidence": "aetna-provider-metadata", "capability_result": "HTTP 200 CapabilityStatement, FHIR 4.0.1.",
     "schema": "Practitioner, PractitionerRole, Organization, OrganizationAffiliation, InsurancePlan and Location. InsurancePlan advertises address-state; role search has specialty/location and page/_count.",
     "pagination": "page/_count documented in metadata; data pagination not exercised because InsurancePlan request returned 401.",
     "mapping_2027": "Unverified; official public non-PII token guide requires developer app credentials. No account/client was provisioned.",
     "c28_disposition": "defer", "blocker": "Obtain app registration/access under applicable developer terms, then verify 2027 mappings. CMS permits developer registration; this is not evidence of plan or provider absence.",
     "evidence": ["aetna-provider-metadata", "aetna-provider-token-guide", "aetna-plan-sample"]},
    {"parent": "Elevance Health, Inc.", "brands": ["Freedom Health", "Optimum HealthCare"],
     "primary_docs": ["freedom-interoperability", "optimum-interoperability", "freedom-developer-portal"],
     "base_url": "https://api.aaneelconnect.com/cms/r4/providerdirectory/", "capability_url": "https://api.aaneelconnect.com/cms/r4/Metadata", "capability_evidence": "freedom-capability",
     "capability_result": "HTTP 500 without payer-id. Public portal documents a required payer-id selection; the payerCode query GUID was not guessed to be the header value.",
     "schema": "Primary AaNeel portal script advertises FHIR R4 directory resources and public/no-member-auth access; no valid live CapabilityStatement captured. Public UI bundle config points at a sandbox configuration service; no sandbox settings were promoted to production.",
     "tenant_links": {"Freedom": "https://developers.aaneelconnect.com/?payerCode=58353272-7878-4bd2-a001-9521770858b6", "Optimum": "https://developers.aaneelconnect.com/?payerCode=5d1757ff-cbd5-4679-b07c-f337267567fe"},
     "pagination": "Not verified; no usable live tenant-scoped response.", "mapping_2027": "Unverified for both H5427 Freedom and H5594 Optimum; separate published payer tenants.",
     "c28_disposition": "defer", "blocker": "Resolve documented production payer-id configuration and valid metadata/plan responses for both tenants.",
     "evidence": ["freedom-capability", "freedom-portal-js", "freedom-interoperability", "optimum-interoperability"]},
    {"parent": "Devoted Health, Inc.", "brands": ["Devoted"], "primary_docs": ["devoted-developers"],
     "base_url": "https://fhir.devoted.com/fhir/", "capability_evidence": "devoted-metadata-json", "capability_result": "HTTP 200 CapabilityStatement, FHIR 4.0.1, requested with standard _format=json because the first metadata response was an HTML representation.",
     "schema": "InsurancePlan identifier/period/network; OrganizationAffiliation supports network/location/participating-organization; PractitionerRole supports practitioner/location/organization. Directory has no member login in these probes.",
     "pagination": "Server _getpages/_getpagesoffset next link followed once; distinct one-row page succeeded.",
     "mapping_2027": "Exact H9884-016-000 plus period 2027-01-01 to 2027-12-31, FL PPO network Organization resolves HTTP 200 as JSON using _format=json (first representation was HTML). This is the sole pinned Devoted Collier plan.",
     "mapped_seed": brief_plan("devoted-collier-plan"), "c28_disposition": "eligible_for_bounded_adapter_build", "blocker": "C28 must still validate provider/location/plan cases and network joins before user participation answers.",
     "evidence": ["devoted-metadata-json", "devoted-plan-sample", "devoted-pagination-next", "devoted-collier-plan", "devoted-medical-network", "devoted-medical-network-json"]},
    {"parent": "Curana Health Holdings, LLC", "brands": ["Align Senior Care Florida"],
     "primary_docs": ["curana-interoperability", "curana-current-api-guide", "curana-usage-policy"],
     "base_url": "https://fhir.curanahealth.com/v1/api/", "capability_evidence": "curana-capability", "capability_result": "Metadata candidate returned HTTP 404; a working CapabilityStatement was not found in the primary guide. Do not treat illustrative example URLs as endpoints.",
     "schema": "Current primary guide, pages 35–41: InsurancePlan, Location, Organization, Practitioner and PractitionerRole; offset/limit pagination. Actual InsurancePlan embeds contract-only identifiers in plan[].identifier and has no period/network on the observed H9917 rows.",
     "pagination": "Documented offset=0&limit=1 then returned next offset=1&limit=1 both succeeded; distinct records. Bounded limit=100 returned all 72 plans.",
     "mapping_2027": "Five returned InsurancePlan records reference H9917 only; none has benefit-year period, exact PBP/segment or network reference. Cannot map the two pinned 2027 H9917 plans from these records.",
     "c28_disposition": "defer", "blocker": "Need current capability/schema confirmation and exact 2027 plan/segment-to-medical-network mapping.",
     "evidence": ["curana-capability", "curana-plan-sample", "curana-pagination-next", "curana-all-plans", "curana-current-api-guide"]},
]
for item in assessments:
    item["target_plans"] = sorted(groups.pop(item["parent"]), key=lambda p: p["id"])
    item["target_plan_count"] = len(item["target_plans"])
    item["contracts"] = sorted(set(p["contract"] for p in item["target_plans"]))
    item.setdefault("capability_url", data(item["capability_evidence"])[0]["requested_url"])
    item["provider_participation_state"] = "unknown — call to confirm"
assert not groups
# Remove any untested brand assumption from the UHC discovery bucket.
assessments[3]["brands"] = ["UnitedHealthcare", "AARP"]
directories = {
    "task": "C15", "status": "complete_discovery", "assessed_at_utc": now,
    "catalog": {"path": "cms-slice/reports/work-package-2/catalog.json", "sha256": digest(catalog_path), "medical_plans": 59, "parent_groups": 8, "contracts": 18},
    "cms_registration_correction": {"evidence": "cms-directory-api-faq", "finding": "Public directory data must not require user/member authentication or authorization. CMS explicitly allows developer/app registration/API keys; the plan's earlier 'without registration' statement was too broad. No claim of zero implementation, licensing or vendor cost follows from the public API rule."},
    "method": "Primary documentation and bounded unauthenticated GETs for metadata, InsurancePlan and two network Organizations; one next-page check per available paginated service. No member resources, real beneficiary inputs, sign-up, credentials, production adapter or mass provider crawl.",
    "scope": "Eight parents are discovery buckets. Two have representative exact 2027 plan/network evidence and may start bounded C28 adapter work; neither is an approved provider participation service. Six defer until listed blockers resolve. Negative probes never imply nonparticipation or lack of eligibility.",
    "c28_build_candidates": ["Humana Inc.", "Devoted Health, Inc."], "exact_2027_seed_plan_count": 2,
    "runtime_provider_answers_added": False, "assessments": assessments,
    "next_validation": "C28: prove exact plan/segment/year and medical network (not dental/pharmacy), stable pagination/filtering, NPI+location+role joins, confidence states and as-of receipt; validate >=15 exact provider/location/plan cases across covered insurers as required by G6. C26 hospital table and C27 independent cross-check remain open.",
}
write("c15-provider-api-discovery.json", directories)

sources = []
for path in sorted((ROOT / "receipts").glob("*.json")):
    receipt = json.loads(path.read_text())
    sources.append({k: receipt.get(k) for k in ["id", "requested_url", "final_url", "http_status", "status", "retrieved_at_utc", "verified_at_utc", "sha256", "bytes", "truncated", "access_state"]})
write("sources.json", {"created_at_utc": now, "source_count": len(sources), "sources": sources})

rows = []
for a in assessments:
    rows.append(f"| {a['parent']} | {a['target_plan_count']} | {', '.join(a['contracts'])} | {a['capability_result']} | {a['mapping_2027']} | {'Build candidate; validation required' if a['c28_disposition'].startswith('eligible') else 'Defer; unknown — call to confirm'} |")
(ROOT / "c15-provider-api-discovery.md").write_text("""# C15 — provider directory API discovery

Completed October 20, 2026. All eight parent groups and all 59 pinned MA records are assigned in the [machine-readable ledger](c15-provider-api-discovery.json), with exact target IDs, production endpoints, capability URLs, schema, pagination, source receipts and blockers.

Two parent groups support a bounded C28 adapter build based on representative exact 2027 plan-to-network records. This proves no physician or hospital participation. The runtime stays **unknown — call to confirm** until C28's exact provider/location/plan validation and confidence handling pass. Humana's other 16 plan mappings remain untested; Devoted has one pinned Collier plan.

| Parent | Plans | Contracts | Capability result | 2027 mapping evidence | C28 disposition |
| --- | ---: | --- | --- | --- | --- |
""" + "\n".join(rows) + """

The current [CMS Provider Directory API FAQ](https://www.cms.gov/initiatives/burden-reduction/overview/interoperability/frequently-asked-questions/provider-directory-api) allows developer app registration/API keys while excluding member/user authentication for these public directories. G6 is corrected accordingly. Aetna's 401 is an access prerequisite, not evidence of a directory violation or provider absence.

The Centene catalog identifies a production server separately from its OpenAPI dev-int example. Only the production metadata URL was probed, and its 403 was not retried. Elevance's Freedom and Optimum links identify different payer tenants; a public payerCode was not guessed to be a required payer-id. Florida Blue's overbroad metadata is not a grant to clinical APIs. Curana's current guide mixes illustrative example URLs with an actual public host; only that actual host was queried. Stale links, wrong-year results and unsuccessful probes are retained.

Follow-up belongs to C28: resolve blockers, verify each supported plan's medical network, inspect provider/location relationships and source dates, and validate at least 15 exact cases across supported insurers. C26/C27 remain open. No new vendor outreach, accounts, contracts or member access occurred.
""")

(ROOT / "c13-site-policy.md").write_text("""# C13 — Medicare.gov policy review

Completed October 20, 2026. Exact [robots.txt](medicare-robots.txt), raw privacy/using-this-site pages and the CMS linking policy are preserved with URL, UTC time and SHA-256 in [sources.json](sources.json). [The policy decision](c13-site-policy.json) records every Allow/Disallow directive and the C16 boundaries. C12 remains complete on the owner's reported legal approval.

The saved robots file does not deny `/plan-compare/`, `/medigap-supplemental-insurance-plans/` or `/care-compare/`; all three are linked in the saved Medicare.gov navigation. These entry URLs are eligible for bounded synthetic public-page observations under G9. This does not automatically approve subroutes, API/back-end requests or other hosts. C16 must enumerate and review its actual request manifest before collection.

Robots denies `/core/` and `/profiles/` except specified CSS/JS/image patterns, and denies admin, comment/reply, filter/tips, node, Spanish node, app-static-content, search, medicare-search and user register/password/login/logout paths, plus the listed `/index.php/` equivalents. `/README.txt` and `/web.config` are denied. The exact list, including wildcard/end-marker exceptions, is retained in the JSON. `/app-static-content/` must stay blocked even if a public app depends on it. No account/member/login route is in scope.

Privacy and using-this-site explain privacy/security, accessibility, external links and reporting security issues. They do not supply a blanket automated reuse permission in the captured text. Non-denial by robots is not a legal license. This review implements the existing approved G9 boundary and does not reopen C12.

C16 retains: fixed synthetic sets, off-peak Eastern, at least five seconds between all outgoing requests, at most 2,000 requests/run, identified User-Agent, query cache, complete observation receipts, dry-run/kill switch, and stop on 403/429/CAPTCHA/block/schema change. Browser subresources must also obey the request policy. No proxies/IP rotation/login bypass and no real-user queries (H09). If required app traffic falls outside reviewed paths, stop and review that engineering dependency rather than silently allowing it. Refresh the robots/policy review after its 24-hour window; existing release freshness deadlines do not change.

Only three Medicare.gov policy GETs were made in this research, at least five seconds apart. No collector or Plan Finder scenarios were run. C16 remains open.
""")

(ROOT / "c14-price-source-decision.md").write_text("""# C14 — 2027 drug-price source feasibility

**Decision: NO GO for a personal calculator.** No adequate authorized 2027 negotiated price feed was obtained. [The decision record](c14-price-source-decision.json) states evidence, limits, acceptance criteria and reopening triggers. H01/H08/H09 remain held; DQ-007 and DQ-008 remain open.

The planned three-day feasibility effort was completed as an expedited point-in-time assessment on October 19–20 Eastern. This is not a claim of three elapsed days, multi-day availability monitoring or vendor responses. The current evidence supports a decision now; it does not predict future publication or commercial availability.

| Route | Verified finding | Decision |
| --- | --- | --- |
| CMS monthly 2027 | Fresh catalog selects `2027_20261008.zip`; full retained 2,290,695,063-byte archive hash verified and eight table-type headers re-read. Formulary, tier cost sharing and dispensing fees lack a complete per-drug unit-price table. | Useful coverage/network evidence; insufficient pricing. |
| CMS quarterly pricing | Latest catalog candidate remains `SPUF_2026_20261007.zip`. Official retained methodology/layout describe plan-level average monthly retail unit costs by plan/segment/NDC/days supply; pricing table lacks pharmacy ID. Quarterly ZIP not newly downloaded. | Wrong benefit year; average grain also cannot support store-specific quotes. |
| CMS external access | C11 inquiry sent; reply/access grant pending. | No authorized feed assumed. |
| ConnectureDRX | Primary API page advertises dosage pricing and monthly OOP estimates. No 2027 Collier payload, signed license, refresh SLA or quote obtained. | Commercial lead, not an available verified feed. |
| SunFire | Primary pages advertise MAPD/PDP quoting and existing/custom APIs. Standalone negotiated drug-price API scope and rights not established. | Commercial lead requiring validation. |
| CSG | C10 subscription purchase deferred; tool marketing/subscription does not establish raw price-feed rights. | No purchase or adequate feed. |
| Medicare.gov observations | Potential future C20 fixed synthetic reference cases under C13/G9. | Dated examples, not a personal calculator or real-user query service. |

See [fresh release discovery](cms-release-discovery.json), [archive inspection](monthly-archive-inspection.json) and the linked source URLs/receipts in the decision JSON. Retained official PDFs are hash-verified, with their original provenance distinguished from new HTTP captures. The inner `20261031` tokens are not claimed as publication or retrieval dates; DQ-008's naming/date ambiguity remains explicit.

To reopen: obtain an authorized 2027 source with exact plan/year/NDC/quantity/days/pharmacy or clearly labeled average grain, price/dispensing-fee definitions, effective dates and refresh terms; validate worked synthetic cases and missing-data behavior, then obtain the existing H01 approval. Never substitute 2026 prices. Until then R1 shows all 61 plans' coverage/pharmacy evidence and links Plan Finder for personal estimates. No money, accounts, new vendor outreach or runtime prices were added.
""")

(ROOT / "README.md").write_text("""# C13–C15 completion evidence

Completed October 20, 2026, following the owner's instruction to finish C13–C15. This batch contains research decisions and source captures; the selected application release and its review deadline are unchanged.

- **C13:** [Medicare.gov policy review](c13-site-policy.md), [machine-readable boundary](c13-site-policy.json), [exact robots.txt](medicare-robots.txt). C12 approval retained; C16 must enforce actual request-path review and existing G9 controls.
- **C14:** [Pricing feasibility decision](c14-price-source-decision.md), [decision JSON](c14-price-source-decision.json). Expedited assessment complete; **no adequate authorized 2027 feed**, so the personal calculator remains held.
- **C15:** [Eight-parent discovery matrix](c15-provider-api-discovery.md), [59-plan ledger](c15-provider-api-discovery.json). Humana and Devoted are candidates for bounded C28 work based on two exact 2027 plan/network seeds. Six groups defer; provider participation remains unknown.

[Source inventory](sources.json) indexes primary URLs and receipts in `receipts/`; raw bodies are stored by SHA-256 in `raw/`. Failed/stale/blocked results remain evidence with their real status. The assessment builders and verifier are local research tooling and make no runtime changes. Run `python3 verify_assessments.py` from this directory for saved-evidence integrity and boundary checks; see [verification](verification.json) and [manifest](manifest.json).

C01 stays deferred for owner testing. C11 still awaits a CMS reply; no new reply claim is made here. H01/H08/H09 and the remaining build/release tasks stay open. DQ history is preserved. No beneficiary data, vendor purchase, developer registration, new external messages or production directory adapter was involved.
""")

print(json.dumps({"status": "built", "sources": len(sources), "parents": len(assessments), "medical_plans": sum(len(a["target_plans"]) for a in assessments), "build_candidates": directories["c28_build_candidates"]}))
