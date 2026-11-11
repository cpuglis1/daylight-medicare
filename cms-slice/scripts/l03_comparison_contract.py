"""L03 structured comparison contract, r8. No lookup/release integration.

This checks stored meaning, not whether a human correctly read a PDF. Evidence
interpretation and acceptance are separate, externally recorded decisions.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import json

SCHEMA = "l03-comparison/1"
DIMENSIONS = (
    "identity", "service", "context", "cost", "unit", "boundaries",
    "conditions", "exceptions", "variant", "shared_budgets",
)
CONDITION_FAMILIES = (
    "authorization", "referral", "network_and_setting", "deductible",
    "frequency_and_quantity", "covered_days", "shared_allowance",
    "qualification", "exclusion", "waiver_and_replacement",
)
OUTCOMES = (
    "exact_agreement", "agreement_through_reviewed_mapping", "different_basis",
    "supported_carrier_statement", "conflict", "insufficient_evidence",
    "documented_inapplicability",
)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def unknown(value):
    if value is None or value == "":
        return True
    if isinstance(value, str) and value.strip().lower() in {
            "unknown", "unresolved", "missing", "not_stated", "not_resolved", "pending"}:
        return True
    if isinstance(value, dict):
        return value.get("state") in {"unknown", "unresolved", "missing"} or any(
            unknown(v) for v in value.values())
    if isinstance(value, list):
        return any(unknown(v) for v in value)
    return False


def canonical(value, key=""):
    """Decimal equivalence only for explicitly named decimal fields.

    Array order is material (day bands/condition schedules); strings are not
    case-folded and periods/networks are never guessed or converted.
    """
    if isinstance(value, dict):
        return {k: canonical(v, k) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [canonical(v) for v in value]
    if key in {"amount", "minimum", "maximum", "percentage"} and value is not None:
        try:
            number = Decimal(str(value))
            if not number.is_finite():
                raise ValueError("Non-finite decimal")
            return str(number.normalize())
        except InvalidOperation as exc:
            raise ValueError("Invalid decimal") from exc
    return value


def evidence_ready(observation, side):
    evidence = observation.get("evidence", [])
    if not evidence:
        return False
    if not isinstance(evidence, list):
        return False
    for item in evidence:
        if not isinstance(item, dict):
            return False
        common = ["source_sha256", "interpretation_review_id"]
        locators = ["member", "pointer"] if side == "cms" else [
            "pdf_page", "passage_sha256", "location", "headers", "footnotes"]
        if any(k not in item or unknown(item[k]) for k in common + locators):
            return False
        if item.get("side") != side:
            return False
        if not isinstance(item["source_sha256"], str) or len(item["source_sha256"]) != 64:
            return False
        if side == "carrier" and (not isinstance(item["pdf_page"], int) or
                item["pdf_page"] < 1 or not isinstance(item["headers"], list) or
                not isinstance(item["footnotes"], list)):
            return False
    return True


def observation_ready(observation, side):
    if not isinstance(observation, dict) or not evidence_ready(observation, side):
        return False
    if any(k not in observation or unknown(observation[k]) for k in DIMENSIONS):
        return False
    structures = {
        "identity": ("year", "contract", "plan", "segment", "geography", "geographic_variant"),
        "service": ("category", "subtype"),
        "context": ("network", "setting", "population", "assistance_basis"),
        "cost": ("kind", "amount", "range_basis"),
        "unit": ("currency_or_percentage", "denominator", "period"),
        "boundaries": ("day_bands", "quantity", "frequency", "reset"),
        "variant": ("kind", "identifier", "enrollment_basis", "effective_period"),
    }
    for key, fields in structures.items():
        value = observation[key]
        if not isinstance(value, dict) or not all(k in value for k in fields):
            return False
    identity = observation["identity"]
    if (not isinstance(identity["year"], int) or isinstance(identity["year"], bool) or
            not all(isinstance(identity[k], str) for k in ("contract", "plan", "segment"))):
        return False
    if observation["cost"]["kind"] not in {
        "premium", "copayment", "coinsurance", "deductible", "allowance",
        "spending_limit", "plan_payment_limit", "premium_reduction", "nonmonetary"
    }:
        return False
    amount = observation["cost"]["amount"]
    if isinstance(amount, (dict,list)):
        if (observation["cost"]["kind"] != "nonmonetary" or not isinstance(amount,dict) or
                amount.get("state") != "documented_inapplicable" or not amount.get("evidence_id")):
            return False
    if not isinstance(observation["exceptions"], list) or not isinstance(observation["shared_budgets"], list):
        return False
    conditions = observation["conditions"]
    if not isinstance(conditions, dict) or set(conditions) != set(CONDITION_FAMILIES):
        return False
    for family, item in conditions.items():
        if not isinstance(item, dict) or item.get("state") not in {
            "asserted", "explicit_absence", "documented_inapplicable"
        } or not all(item.get(k) for k in ("assertion", "obligation_ids", "evidence_ids", "interpretation_review_id")):
            return False
    bands = observation["boundaries"]["day_bands"]
    if not isinstance(bands, list):
        return False
    previous_end = None
    for band in bands:
        if not isinstance(band, dict) or not all(k in band for k in ("begin", "end", "amount", "unit")):
            return False
        begin, end = band["begin"], band["end"]
        if (isinstance(begin, bool) or isinstance(end, bool) or
                not isinstance(begin, int) or not isinstance(end, int) or begin > end or
                (previous_end is not None and begin <= previous_end)):
            return False
        previous_end = end
    budgets = observation["shared_budgets"]
    if any(not isinstance(x, dict) or not x.get("id") for x in budgets):
        return False
    if len({x["id"] for x in budgets}) != len(budgets):
        return False
    try:
        canonical(observation)
    except ValueError:
        return False
    return True


def comparison_value(observation, dimension):
    if dimension == "conditions":
        return {family: {"state": item["state"], "assertion": item["assertion"]}
                for family, item in observation[dimension].items()}
    return canonical(observation[dimension])


def compare(cms, carrier, *, mapping=None, mapping_registry=None, expected_identity=None):
    """Fail closed on incomplete observations. Does not accept/release claims.

    Reviewed mappings must bind the complete pair of observation fingerprints.
    An arbitrary mapping identifier cannot excuse a disagreement.
    """
    result = {"schema": SCHEMA, "outcome": "insufficient_evidence",
              "differences": [], "accepted_for_reference": False}
    if not observation_ready(carrier, "carrier"):
        return result
    if carrier["identity"]["year"] != 2026 or (
            expected_identity is not None and carrier["identity"] != expected_identity):
        result.update(outcome="conflict", differences=["identity"])
        return result
    if carrier.get("inapplicability") is not None:
        control = carrier["inapplicability"]
        if control.get("explicit_source_control") and control.get("review_id"):
            result["outcome"] = "documented_inapplicability"
        return result
    if cms is None:
        result["outcome"] = "supported_carrier_statement"
        return result
    if not observation_ready(cms, "cms"):
        return result
    try:
        result["differences"] = [k for k in DIMENSIONS
                                 if comparison_value(cms,k) != comparison_value(carrier,k)]
    except ValueError:
        return result
    if not result["differences"]:
        result["outcome"] = "exact_agreement"
    elif "context" in result["differences"] and not any(
            k in result["differences"] for k in ("identity", "service", "unit", "variant")):
        a, b = cms["context"].copy(), carrier["context"].copy()
        basis_a, basis_b = a.pop("assistance_basis", None), b.pop("assistance_basis", None)
        result["outcome"] = "different_basis" if (
            basis_a is not None and basis_b is not None and basis_a != basis_b and a == b
        ) else "conflict"
    else:
        result["outcome"] = "conflict"
    if mapping is not None:
        approved = (mapping_registry or {}).get(mapping)
        if "identity" not in result["differences"] and approved and approved.get("review_decision") == "accepted_mapping" and (
            approved.get("cms_sha256") == fingerprint(cms) and
            approved.get("carrier_sha256") == fingerprint(carrier) and
            approved.get("reviewer") and approved.get("evidence") and
            approved.get("review_receipt_sha256")
        ):
            result.update(outcome="agreement_through_reviewed_mapping", mapping_id=mapping)
    return result


def check_inventory_transition(before, after, change=None):
    """Never silently remove/reclassify a root obligation or its evidence.

    A new revision can propose a scope change, but only a bound review receipt
    permits retiring a required root. Child claims never replace root IDs.
    """
    old = {x["id"]: x for x in before}
    new = {x["id"]: x for x in after}
    if len(old) != len(before) or len(new) != len(after):
        raise ValueError("Duplicate inventory identifier")
    changes = []
    for key, row in old.items():
        other = new.get(key)
        if other is None or any(row.get(k) != other.get(k) for k in (
                "required", "kind", "source_ids", "parent_id", "offering_id")):
            changes.append(key)
    if changes:
        approved = change or {}
        if not (approved.get("review_receipt_sha256") and
                approved.get("before_sha256") == fingerprint(before) and
                approved.get("after_sha256") == fingerprint(after) and
                set(approved.get("affected_ids", [])) == set(changes)):
            raise ValueError("Unreviewed denominator/evidence change: " + ", ".join(changes[:5]))
    return {"retained_roots": len(old.keys() & new.keys()),
            "added_roots": len(new.keys() - old.keys()), "reviewed_changes": changes}
