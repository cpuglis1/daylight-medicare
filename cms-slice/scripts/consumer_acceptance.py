"""Fail-closed consumer admission, separate from technical/source verification.

Research tools can inspect raw captures offline. Consumer entry points always
require a named domain review bound to immutable data AND runtime code. No CLI,
HTTP parameter or environment variable can disable this gate.
"""

from datetime import datetime, timezone
from functools import wraps
import json
from pathlib import Path

import cms_slice as cms

REGISTRY = cms.ROOT / "data-sources/consumer-acceptance.json"
NOTICE = "Data validation is incomplete. Plan facts, costs and coverage results are unavailable until the required review is complete."
WORKSTREAMS = {"availability", "benefits", "medigap", "drugs_pharmacies", "providers", "rules_programs"}


class AcceptanceRequired(cms.SourceError):
    pass


def digest(value):
    return cms.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode())


def utc(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Acceptance dates must include timezone")
    return parsed.astimezone(timezone.utc)


class ConsumerAcceptance:
    def __init__(self, release=None, registry=REGISTRY, now=None):
        self.release = Path(release).resolve() if release is not None else None
        self.registry = Path(registry)
        self.now = now or (lambda: datetime.now(timezone.utc))

    def _review(self, record, deadline):
        reviewer = record["reviewer"]
        if (record["status"] != "accepted" or not reviewer["name"].strip()
                or reviewer["role"] != "medicare_subject_matter_reviewer"
                or not record["review_receipt"].strip()
                or not utc(record["reviewed_at_utc"]) <= self.now() < utc(record["review_after_utc"]) <= deadline):
            raise AcceptanceRequired(NOTICE)

    def checked(self):
        """Reload on every operation: revocation/expiry takes effect immediately."""
        try:
            if self.release is None:
                raise AcceptanceRequired(NOTICE)
            registry = cms.load_json(self.registry)
            if registry.get("status") != "accepted":
                raise AcceptanceRequired(NOTICE)
            import demo_release
            manifest = demo_release.verify(self.release)
            requirements = cms.load_json(self.release / "validation-requirements.json")
            deadline = utc(manifest["source_receipt"]["data_review_after_utc"])
            if (registry["version"] != 1 or registry["release_id"] != manifest["release_id"]
                    or registry["manifest_sha256"] != cms.file_hash(self.release / "manifest.json")
                    or requirements["version"] != 1
                    or "validation-requirements.json" not in manifest["files_sha256"]
                    or set(requirements["required_workstreams"]) != WORKSTREAMS
                    or not requirements["claims"]):
                raise AcceptanceRequired(NOTICE)
            self._review(registry, deadline)
            claims = registry["claims"]
            if not isinstance(claims, dict):
                raise AcceptanceRequired(NOTICE)
            for claim in requirements["claims"]:
                acceptance = claims[claim["id"]]
                self._review(acceptance, min(deadline, utc(registry["review_after_utc"])))
                if (acceptance["claim_sha256"] != digest(claim)
                        or acceptance["conditions_reviewed"] is not True
                        or not acceptance["reconciliation_receipt"].strip()):
                    raise AcceptanceRequired(NOTICE)
            if not isinstance(registry["approved_outputs"], dict):
                raise AcceptanceRequired(NOTICE)
            return registry, deadline
        except (OSError, ValueError, KeyError, TypeError, AttributeError, cms.SourceError) as error:
            raise AcceptanceRequired(NOTICE) from error

    def require_release(self):
        self.checked()

    def require_output(self, value):
        """Every returned fact and structured plan must have its exact acceptance.

        A full-record receipt does not replace individual field requirements.
        It also prevents unreviewed conditions/notes leaking around field checks.
        Raw evidence exports stay in research reports, outside consumer APIs.
        """
        registry, deadline = self.checked()
        def approve(kind, payload):
            key = kind + ":" + digest(payload)
            review = registry["approved_outputs"].get(key, {})
            try:
                self._review(review, min(deadline, utc(registry["review_after_utc"])))
            except (ValueError, KeyError, TypeError, AttributeError) as error:
                raise AcceptanceRequired(NOTICE) from error
        def walk(item):
            if isinstance(item, dict):
                if "text" in item and "id" in item and "evidence" in item:
                    approve("fact", item)
                if "metrics" in item and "id" in item:
                    approve("plan", item)
                    for field, cell in item["metrics"].items():
                        approve("field", {"plan_id": item["id"], "field": field, "cell": cell})
                for key in ("results", "resources", "candidates", "coordination_flags", "premium_basis"):
                    if key in item:
                        approve("structured:" + key, item[key])
                for child in item.values():
                    walk(child)
            elif isinstance(item, list):
                for child in item:
                    walk(child)
        walk(value)
        return value

    def status(self):
        try:
            self.require_release()
            return {"consumer_ready": True, "validation_status": "accepted"}
        except AcceptanceRequired:
            return {"consumer_ready": False, "validation_status": "pending", "validation_notice": NOTICE}


def research_or_accepted(method):
    """Explicit Python-only research mode is never honored by the HTTP gate."""
    @wraps(method)
    def guarded(self, *args, **kwargs):
        tools = getattr(self, "tools", getattr(getattr(self, "chat", None), "tools", self))
        if getattr(tools, "research_mode", False):
            return method(self, *args, **kwargs)
        gate = getattr(tools, "consumer_acceptance", None) or ConsumerAcceptance()
        gate.require_release()
        return gate.require_output(method(self, *args, **kwargs))
    return guarded


def requirements(snapshot, matrix):
    """A complete required inventory; none of these entries is an acceptance."""
    claims = []
    for row in sorted(snapshot["options"] + snapshot["exclusions"], key=lambda r: r["id"]):
        for zipcode in ("34102", "34109", "34145", "34142"):
            claims.append({"id": "availability:" + row["id"] + ":" + zipcode,
                           "workstream": "availability", "plan_id": row["id"],
                           "year": "2027", "county_fips": "12021", "zip": zipcode,
                           "required_evidence": "Current source observation, exact identity and enrollment restrictions; both-direction reconciliation"})
    for row in matrix["plans"]:
        for field, cell in row["fields"].items():
            claims.append({"id": "benefit:" + row["id"] + ":" + field,
                           "workstream": "benefits", "plan_id": row["id"], "year": "2027", "county_fips": "12021",
                           "field": field, "research_cell": cell,
                           "required_evidence": "Exact 2027 SB/EOC page, units, period, exceptions, conditions and independent reconciliation; explicit not-applicable states also reviewed"})
        claims.append({"id": "stars:" + row["id"], "workstream": "benefits", "plan_id": row["id"],
                       "year": "2027", "required_evidence": "Correct contract, rating year, measure and numeric or official nonnumeric state"})
    for workstream in sorted(WORKSTREAMS):
        claims.append({"id": "workstream:" + workstream, "workstream": workstream,
                       "required_evidence": "Completed workstream reconciliation and scoped cases; exact source/transformation hashes and refresh deadlines"})
    return {"version": 1, "required_workstreams": sorted(WORKSTREAMS), "claims": claims,
            "scope": "Required R1 acceptance inventory, not accepted facts. Missing required claims block the entire consumer release."}
