"""Decision records (I06) and the commercial-context guard (I02).

``build_decision_record`` produces the row stored in ``dl_ops.decision_record``.
It refuses any document carrying a commercial key, using the same rule as the
database's ``dl_ops.has_commercial_key`` check, so a leak fails before the insert.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Any, Iterable

from .checklist import CHECKLIST_ITEMS

COMMERCIAL_KEY = re.compile(
    r"(^|_)(commissions?|payouts?|compensation|referral_fees?|carrier_contracts?|"
    r"carrier_appointments?|lifetime_value|revenue)($|_)", re.IGNORECASE)
PURPOSES = frozenset({"published_term_comparison", "personal_recommendation", "coverage_path_comparison"})
STATES = frozenset({"held", "available", "no_supported_terms"})


class CommercialContextError(ValueError):
    """A commercial field reached the decision side."""


def canonical_sha256(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def commercial_keys(value: Any, path: str = "$") -> list[str]:
    """Paths of every object key, at any depth, that names commercial economics."""
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            here = f"{path}.{key}"
            if isinstance(key, str) and COMMERCIAL_KEY.search(key):
                found.append(here)
            found.extend(commercial_keys(item, here))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found.extend(commercial_keys(item, f"{path}[{index}]"))
    return found


def assert_no_commercial_context(**documents: Any) -> None:
    leaks = [p for name, doc in documents.items() for p in commercial_keys(doc, name)]
    if leaks:
        raise CommercialContextError("Commercial fields cannot enter a decision: " + ", ".join(leaks))


def checklist_receipt(covered: dict[str, dict]) -> dict:
    """Normalize pre-enrollment checklist coverage; unknown item names are refused."""
    unknown = set(covered) - set(CHECKLIST_ITEMS)
    if unknown:
        raise ValueError(f"Unknown checklist items: {sorted(unknown)}")
    return {item: covered.get(item, {"covered": False}) for item in CHECKLIST_ITEMS}


def build_decision_record(*, purpose: str, state: str, inputs: dict, evidence_versions: dict,
                          method_version: str, policy_version: str, candidate_ids: Iterable[str],
                          ordered_ids: Iterable[str] = (), tie_groups: list | None = None,
                          excluded: list | None = None, reason_codes: Iterable[str] = (),
                          holds: list | None = None, model_versions: dict | None = None,
                          checklist_coverage: dict | None = None, visit_ref: str | None = None,
                          decision_id: str | None = None) -> dict:
    if purpose not in PURPOSES:
        raise ValueError(f"Unknown decision purpose {purpose!r}")
    if state not in STATES:
        raise ValueError(f"Unknown decision state {state!r}")
    candidates = list(candidate_ids)
    ordered = list(ordered_ids)
    if not set(ordered) <= set(candidates):
        raise ValueError("Ordered IDs must come from the candidate set")
    record = {
        "decision_id": decision_id or str(uuid.uuid4()),
        "visit_ref": visit_ref,
        "purpose": purpose,
        "state": state,
        "inputs": inputs,
        "inputs_sha256": canonical_sha256(inputs),
        "evidence_versions": evidence_versions,
        "method_version": method_version,
        "policy_version": policy_version,
        "model_versions": model_versions or {},
        "candidate_ids": candidates,
        "ordered_ids": ordered,
        "tie_groups": tie_groups or [],
        "excluded": excluded or [],
        "reason_codes": list(reason_codes),
        "holds": holds or [],
        "checklist_coverage": checklist_receipt(checklist_coverage) if checklist_coverage is not None else {},
    }
    assert_no_commercial_context(**{k: record[k] for k in (
        "inputs", "evidence_versions", "model_versions", "tie_groups", "excluded", "holds", "checklist_coverage")})
    return record


def substantive_result(record: dict) -> dict:
    """The parts of a decision that must not change when only economics change (I01)."""
    return {k: record[k] for k in ("state", "candidate_ids", "ordered_ids", "tie_groups",
                                   "excluded", "reason_codes", "holds")}
