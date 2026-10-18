"""Compact factual tools over verified evidence; no suitability ranking or price engine."""

from collections import defaultdict
from datetime import datetime, timezone
import json
import re
import threading

import cms_slice as cms
import prescription as rx
import research
from identity_lookup import IdentityLookup
from knowledge import Knowledge

TOOL_CODE_SHA256 = cms.file_hash(__file__)
REVIEW_INPUTS = ("reports/work-package-1/run-manifest.json", "reports/work-package-2/read-manifest.json",
                 "reports/work-package-3/manifest.json", "reports/source-diligence/manifest.json",
                 "reports/demo-quality-manifest.json", "reports/drug-validation-manifest.json",
                 "reports/devoted-drug-validation.json")


def dollars(cents):
    return f"${cents / 100:,.2f}"


class DemoTools:
    def __init__(self, model=None, prescription_model=None, knowledge=None, identities=None, release=None):
        if release is not None:
            from demo_release import load
            frozen = load(release)
            model, prescription_model, knowledge, identities = (frozen[k] for k in ("model", "prescription_model", "knowledge", "identities"))
        self.model = model or research.ReadModel()
        self.rx = prescription_model or research.PrescriptionModel()
        self.knowledge = knowledge or Knowledge()
        self.identities = identities or IdentityLookup()
        if release is not None:
            self.quality = frozen["quality"]
            self.data_review = frozen["data_review"]
        else:
            import carrier_quality
            self.quality = carrier_quality.verify()
            self.data_review = cms.load_json(cms.ROOT / "data-sources/demo-review.json")
            if set(self.data_review["basis_sha256"]) != set(REVIEW_INPUTS) or any(cms.file_hash(cms.ROOT / p) != h for p, h in self.data_review["basis_sha256"].items()):
                raise cms.SourceError("Demo review checkpoint differs from current evidence; review the changed release")
        checked = datetime.fromisoformat(self.data_review["engineering_checked_at_utc"])
        due = datetime.fromisoformat(self.data_review["review_after_utc"])
        if due <= checked:
            raise cms.SourceError("Demo source-review dates are invalid")
        self.snapshot = self.model.catalog("2027", "12021")
        self.cache = getattr(self.rx, "cache", rx.CACHE)
        self.by_id = {r["id"]: r for r in self.snapshot["options"] + self.snapshot["exclusions"]}
        self.joins = {r["id"]: r for r in self.rx.report["joins"]}
        self.forms_rx = defaultdict(list)
        # Immutable in-memory source rows are read only after PrescriptionModel verifies all captures.
        for evidence, row in rx.captured_rows(self.cache / "formulary.psv.gz"):
            item = {"evidence": evidence, "raw": row}
            self.forms_rx[(row["FORMULARY_ID"], row["RXCUI"])].append(item)
        if cms.file_hash(self.cache / "formulary.psv.gz") != self.rx.manifest["cache_sha256"]["formulary.psv.gz"]:
            raise cms.SourceError("Formulary capture changed while building the immutable query index")
        self.pharmacy_matches = {}
        self.lock = threading.RLock()
        self.version = "naples-demo-" + cms.sha256(json.dumps({
            "catalog": cms.sha256(json.dumps(self.snapshot, sort_keys=True).encode()),
            "rx_manifest": cms.sha256(json.dumps(self.rx.manifest, sort_keys=True).encode()), "knowledge": self.knowledge.version,
            "quality": cms.sha256(json.dumps(self.quality, sort_keys=True).encode()),
            "data_review": self.data_review,
            "tool_code": TOOL_CODE_SHA256}, sort_keys=True).encode())[:20]

    def fact(self, fid, text, evidence=None, **extra):
        return {"id": fid, "text": text, "evidence": evidence or [], **extra}

    def review_evidence(self):
        return {k: self.data_review[k] for k in ("engineering_checked_at_utc", "review_after_utc")} | {
            "freshness": "review_overdue" if datetime.now(timezone.utc) > datetime.fromisoformat(self.data_review["review_after_utc"]) else "within_review_window",
            "review_scope": "Engineering checkpoint of pinned inputs and limited corroboration; source publication date and qualified domain sign-off are separate"}

    def cms_evidence(self, cell):
        return {"id": "cms-" + cell["archive_sha256"][:12] + "-" + str(cell["record_ordinal"]),
                "url": self.snapshot["sources"][cell["artifact"]]["url"], **cell, **self.review_evidence()}

    def market_options(self, year="2027", county_fips="12021", category=None):
        self.model.catalog(year, county_fips)
        if category not in {None, "MA", "MA-PD", "PDP"}:
            raise cms.SourceError("Category must be MA, MA-PD, PDP or unset; no eligibility inference")
        rows = [r for r in self.snapshot["options"] if category is None or r["category"] == category]
        facts = [self.fact("market-scope", "The captured 2027 Collier source has 70 records. The supported comparison scope has 38: 20 MA-PD, 7 MA-only, and 11 standalone PDP. It excludes 27 SNP and 5 Regional PPO records; exclusions do not establish personal ineligibility.",
                           [{"id": "cms-market-scope", "url": self.snapshot["sources"]["landscape"]["url"], "sha256": self.snapshot["sources"]["landscape"]["sha256"], "benefit_year": "2027", "county_fips": "12021", **self.review_evidence()}])]
        for row in rows:
            premium = row["plan_premium"]["fact"]
            amount = dollars(premium["value_cents"]) if premium["state"] == "value" else premium["state"]
            facts.append(self.fact("plan-" + row["id"], f"{row['id']}: {row['name']} ({row['category']}, {row['plan_type']}); published plan premium {amount} per month. Other Medicare obligations and personal adjustments are separate.",
                                   [self.cms_evidence(premium["evidence"])], plan_id=row["id"]))
        return {"facts": facts, "full_option_ids": [r["id"] for r in rows], "order": "source identity; not suitability", "snapshot_id": self.version,
                "excluded_ids": [r["id"] for r in self.snapshot["exclusions"]], "preserve_all_facts": True}

    def plan_details(self, plan_id):
        if plan_id not in self.by_id:
            raise cms.SourceError("Plan outside the pinned Collier 2027 release")
        row = self.by_id[plan_id]
        if not row["comparison_available"]:
            return {"facts": [self.fact("excluded-" + plan_id, f"{plan_id} is in the captured source but outside the supported comparison scope: {', '.join(row['exclusion_reasons'])}. This is a scope limit, not personal ineligibility.", [self.cms_evidence(row["source"])], plan_id=plan_id)], "snapshot_id": self.version}
        facts = []
        for field in [row["plan_premium"]["field"], "annual_part_d_deductible", "in_network_medical_moop"]:
            cell = row["facts"][field]
            value = dollars(cell["value_cents"]) if cell["state"] == "value" else cell["state"].replace("_", " ")
            note = {"annual_part_d_deductible": "Drug/tier applicability still needs checking.",
                    "in_network_medical_moop": "This medical limit does not include premiums or Part D costs."}.get(field, "Other Medicare obligations and personal adjustments are separate.")
            facts.append(self.fact(f"{plan_id}-{field}", f"{row['name']} ({plan_id}): {research.LABELS[field]} is {value}. {note}", [self.cms_evidence(cell["evidence"])], plan_id=plan_id))
        facts.extend(f for f in self.knowledge.facts.values() if f.get("plan_id") == plan_id)
        official = self.quality.get("medicare_gov_plan_summaries", {}).get(plan_id)
        if official and official.get("primary_care_raw") is not None and official.get("specialist_raw") is not None:
            facts.append(self.fact(plan_id+"-official-office-summary",
                                   f"The Medicare.gov comparison card for {row['name']} ({plan_id}) lists primary doctor visits as {official['primary_care_raw']} and specialist visits as {official['specialist_raw']}. This is a published summary; deductible, referral, service-setting and full Evidence of Coverage conditions still need checking.",
                                   [{"id": "medicaregov-"+plan_id, "url": official["url"], "retrieved_at_utc": official["observed_at_utc"],
                                     "sha256": self.quality["medicare_gov_observations_sha256"], **self.review_evidence()}], plan_id=plan_id))
        return {"facts": facts, "snapshot_id": self.version, "category": row["category"], "personal_fit_assessed": False}

    def medicine_candidates(self, name):
        result = self.identities.medicines(name)
        facts = [self.fact("drug-candidates-" + cms.sha256(name.casefold().encode())[:12],
                           f"The public vocabulary found {result['candidate_count']} strength/form/product candidates for {result['query']}. " +
                           (f"Showing {len(result['candidates'])}; refine the medicine name if your exact product is missing. " if result['truncated'] else "") +
                           "No product, quantity or days supply has been confirmed for you.", [result["evidence"]])]
        return {**result, "facts": facts}

    def plan_candidates(self, name):
        if not isinstance(name, str) or not 2 <= len(name.strip()) <= 100:
            raise cms.SourceError("Specify a short published plan or carrier name")
        tokens = re.findall(r"[a-z0-9]+", name.casefold())
        candidates = []
        for row in self.by_id.values():
            haystack = (row["name"] + " " + row["landscape_raw"]["Organization Marketing Name"]).casefold()
            if tokens and all(t in haystack for t in tokens):
                candidates.append({"plan_id": row["id"], "name": row["name"], "category": row["category"],
                                   "comparison_available": row["comparison_available"], "exclusion_reasons": row["exclusion_reasons"]})
        candidates.sort(key=lambda p: p["plan_id"])
        return {"status": "choose_exact_plan" if candidates else "no_matching_name_in_captured_market", "query": name,
                "candidates": candidates, "confirmed_plan_id": None,
                "facts": [self.fact("plan-name-"+cms.sha256(name.casefold().encode())[:12],
                                    f"The captured market has {len(candidates)} plan-name matches for {name}. Choose the exact plan ID and year; similar names can have different benefits or comparison scope.",
                                    [{"id": "cms-plan-identities", "url": self.snapshot["sources"]["landscape"]["url"], "sha256": self.snapshot["sources"]["landscape"]["sha256"], **self.review_evidence()}])]}

    def pharmacy_candidates(self, name, city="Naples"):
        result = self.identities.pharmacies(name, city)
        return {**result, "facts": [self.fact("pharmacy-candidates-" + cms.sha256((name+city).encode())[:12],
                f"The public registry search found {len(result['candidates'])} matching reported locations for {name} in {city}. Confirm the exact address; registry identity does not establish current operation or plan participation.", [result["evidence"]])]}

    def _pharmacy(self, plan_id, npi):
        key = (plan_id, npi)
        with self.lock:
            if key in self.pharmacy_matches:
                return self.pharmacy_matches[key]
            name = plan_id + "-pharmacy.psv.gz"
            digest = self.rx.manifest["cache_sha256"].get(name)
            if digest is None or cms.file_hash(self.cache / name) != digest:
                raise cms.SourceError("Pharmacy capture missing or changed; do not infer network status")
            number = rx.pharmacy_number(npi)
            rows = [{"evidence": e, "raw": r} for e, r in rx.captured_rows(self.cache / name) if r["PHARMACY_NUMBER"] == number]
            if cms.file_hash(self.cache / name) != digest:
                raise cms.SourceError("Pharmacy capture changed during lookup")
            self.pharmacy_matches[key] = rows
            return rows

    def drug_evidence(self, rxcui, plan_ids=None, pharmacy_npi=None):
        if not isinstance(rxcui, str) or not re.fullmatch(r"[1-9]\d{0,7}", rxcui):
            raise cms.SourceError("Specify an exact RxCUI from a confirmed product choice or explicit code query")
        if pharmacy_npi is not None:
            rx.pharmacy_number(pharmacy_npi)
        if plan_ids is None:
            plan_ids = [r["id"] for r in self.snapshot["options"]]
        if not isinstance(plan_ids, list) or not 1 <= len(plan_ids) <= 38 or any(not isinstance(p, str) for p in plan_ids) or len(set(plan_ids)) != len(plan_ids):
            raise cms.SourceError("Choose one to 38 distinct supported plans")
        if any(p not in self.by_id or not self.by_id[p]["comparison_available"] for p in plan_ids):
            raise cms.SourceError("Prescription comparison contains an unsupported/excluded plan")
        facts, results = [], []
        for plan_id in [r["id"] for r in self.snapshot["options"] if r["id"] in plan_ids]:
            join = self.joins[plan_id]
            if not join["selected_plan"]:
                results.append({"plan_id": plan_id, "status": join["status"], "products": []})
                facts.append(self.fact("rx-"+plan_id+"-"+rxcui, f"{plan_id} has no Part D coverage in this source; it does not inherit another plan's drug benefits.", [self.cms_evidence(self.by_id[plan_id]["source"])], plan_id=plan_id))
                continue
            raw_plan = join["selected_plan"]["raw"]
            if raw_plan["PLAN_SUPPRESSED_YN"] != "N":
                raise cms.SourceError("Plan prescription data suppressed or unknown")
            products = self.forms_rx.get((raw_plan["FORMULARY_ID"], rxcui), [])
            summary = []
            for item in products:
                row = item["raw"]
                summary.append({"ndc11": row["NDC"], "tier": row["TIER_LEVEL_VALUE"], "prior_authorization": row["PRIOR_AUTHORIZATION_YN"],
                                "step_therapy": row["STEP_THERAPY_YN"], "quantity_limit": row["QUANTITY_LIMIT_YN"],
                                "raw_quantity": row["QUANTITY_LIMIT_AMOUNT"], "quantity_days": row["QUANTITY_LIMIT_DAYS"], "quantity_unit": None,
                                "evidence": {"source_archive_sha256": self.rx.config["source"]["sha256"], **item["evidence"]}})
            evidence = [{"id": "rx-" + plan_id + "-" + rxcui, "url": self.rx.config["source"]["url"], "sha256": self.rx.config["source"]["sha256"], "formulary_id": raw_plan["FORMULARY_ID"], "rows": [p["evidence"] for p in summary], **self.review_evidence()}]
            if summary:
                flag = lambda value: {"Y": "indicated", "N": "not indicated"}.get(value, "unresolved")
                conditions = sorted({f"tier {p['tier']}, prior authorization {flag(p['prior_authorization'])}, step therapy {flag(p['step_therapy'])}, quantity limit {flag(p['quantity_limit'])}" for p in summary})
                text = f"{plan_id}: RxCUI {rxcui} is listed in the captured basic formulary with " + "; ".join(conditions) + ". Approval, prescribed quantity and personal price remain unconfirmed."
            else:
                text = f"{plan_id}: RxCUI {rxcui} was not found in the captured basic formulary. This alone does not establish noncoverage; supplemental, indication-specific and exception evidence may be needed."
            pharmacy = {"status": "not_requested"}
            if pharmacy_npi:
                rows = self._pharmacy(plan_id, pharmacy_npi)
                pharmacy = {"status": "listed_in_pinned_network" if rows else "not_listed_in_pinned_network", "npi": pharmacy_npi,
                            "rows": [{"preferred_retail": r["raw"]["PREFERRED_STATUS_RETAIL"], "retail": r["raw"]["PHARMACY_RETAIL"], "evidence": r["evidence"]} for r in rows]}
                text += f" Pharmacy NPI {pharmacy_npi} is {'listed' if rows else 'not listed'} in this pinned network; current store participation still needs confirmation."
            facts.append(self.fact("rx-"+plan_id+"-"+rxcui, text, evidence, plan_id=plan_id))
            results.append({"plan_id": plan_id, "status": "listed_with_source_conditions" if summary else "missing_basic_evidence_not_noncoverage", "products": summary, "pharmacy": pharmacy})
        return {"facts": facts, "results": results, "rxcui": rxcui, "snapshot_id": self.version,
                "pricing": "unavailable_for_2027", "personal_medicine_confirmed": False,
                "order": "source identity; not suitability or cost", "preserve_all_facts": True}

    def provider_evidence(self, name, plan_id=None):
        if plan_id is not None and plan_id not in self.by_id:
            raise cms.SourceError("Provider query plan is outside the supported release")
        return self.knowledge.provider(name, plan_id)

    def drug_list_evidence(self, rxcuis, plan_ids=None, pharmacy_npi=None):
        if (not isinstance(rxcuis, list) or not 1 <= len(rxcuis) <= 15 or
                any(not isinstance(code, str) or not re.fullmatch(r"[1-9]\d{0,7}", code) for code in rxcuis) or len(set(rxcuis)) != len(rxcuis)):
            raise cms.SourceError("Specify one to 15 distinct exact RxCUI product codes; no medicine is inferred")
        codes = sorted(rxcuis, key=int)
        batches = [self.drug_evidence(code, plan_ids, pharmacy_npi) for code in codes]
        ids = [r["plan_id"] for r in batches[0]["results"]]
        by_plan = {pid: [] for pid in ids}
        facts = []
        for code, batch in zip(codes, batches):
            if [r["plan_id"] for r in batch["results"]] != ids:
                raise cms.SourceError("Medicine batch membership changed during comparison")
            facts.extend(batch["facts"])
            for result in batch["results"]:
                by_plan[result["plan_id"]].append({"rxcui": code, **result})
        return {"facts": sorted(facts, key=lambda f: f.get("plan_id", f["id"])),
                "results": [{"plan_id": pid, "medicines": by_plan[pid]} for pid in ids],
                "rxcuis": codes, "full_option_ids": ids, "snapshot_id": self.version, "pricing": "unavailable_for_2027",
                "personal_medicine_list_confirmed": False, "preserve_all_facts": True,
                "order": "Plan source identity, then numeric vocabulary code; no suitability, drug substitution or cost ranking"}

    def education(self, topic):
        return self.knowledge.topic(topic)

    def call(self, name, arguments):
        allowed = {"market_options", "plan_details", "plan_candidates", "medicine_candidates", "pharmacy_candidates", "drug_evidence", "drug_list_evidence", "provider_evidence", "education"}
        if name not in allowed or not isinstance(arguments, dict):
            raise cms.SourceError("Unsupported factual tool")
        try:
            return getattr(self, name)(**arguments)
        except TypeError as error:
            raise cms.SourceError("Tool arguments do not match the supported schema") from error
