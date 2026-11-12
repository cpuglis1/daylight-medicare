"""Exact source-reading receipts, separate from technical mechanical replay.

V1 retains its task-input/rule/mapping bindings. V2 binds the complete source
meaning and a fixed semantic contract, so technical engine changes can replay
mechanics without pretending an unchanged reading is new research. Neither
version approves equivalence mappings, complete originals, reference acceptance
or consumer release. The runner must retain all source/mechanical/unknown holds.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import math

from .common import digest

REVIEW_SCHEMA_V1 = "daylight-source-review-receipt/1"
REVIEW_SCHEMA_V2 = "daylight-source-review-receipt/2"

# These are semantic IDs from the sealed comparison schema and complete-meaning
# family contract, not a digest of the CLI, store or comparator implementation.
SEMANTIC_CONTRACT = {
    "schema_id": "urn:daylight:l03:comparison:1",
    "schema_sha256": "37e66820165e819baf6113955c54e727615e440ad655ac8fbea1ef519740140d",
    "complete_meaning_contract_id": "l03-comparison/1",
    "source_scope_guard_contract_id": "l03-meaning-comparison-r9/1",
    "condition_family_ids": [
        "authorization", "referral", "network_and_setting", "deductible",
        "frequency_and_quantity", "covered_days", "shared_allowance",
        "qualification", "exclusion", "waiver_and_replacement",
    ],
}

# ONLY top-level runtime/transport fields are omitted. Do not recursively use
# this list: components and source artifacts include their complete original
# metadata, stored outcomes, evidence, interpretation, parents and child scope.
# Unrecognized future task metadata is included, failing closed on additions.
_TECHNICAL_FIELDS = frozenset({
    "schema", "adapter_version", "adapter_dependencies", "adapter_holds",
    "task_input_sha256", "rule_fingerprint", "mapping_fingerprint",
    "source_meaning_sha256", "comparison_checks", "holds",
    "review_state", "review_fingerprint", "review_binding", "review_bindings",
    "mechanical_results", "evaluation_key", "status", "input_artifact",
    "cache_hit", "cache_metrics", "timings", "run_id",
})


def _json_tree(value, path="/", active=None):
    """Reject type-coercing/nonfinite Python values before canonical hashing."""
    active = set() if active is None else active
    kind = type(value)
    if value is None or kind in (str, int, bool):
        return
    if kind is float and math.isfinite(value):
        return
    if kind is Decimal and value.is_finite():
        return
    if kind not in (dict, list):
        raise ValueError(f"Review binding must be finite JSON at {path}")
    if id(value) in active:
        raise ValueError(f"Cyclic review binding at {path}")
    active.add(id(value))
    try:
        if kind is dict:
            for key, child in value.items():
                if type(key) is not str:
                    raise ValueError(f"Review binding keys must be strings at {path}")
                _json_tree(child, path + key + "/", active)
        else:
            for index, child in enumerate(value):
                _json_tree(child, path + str(index) + "/", active)
    finally:
        active.remove(id(value))


def _component_ids(task):
    components = task.get("components")
    if type(components) is not list or any(type(c) is not dict or
            type(c.get("id")) is not str or not c["id"].strip() for c in components):
        raise ValueError("Task components require exact nonempty component IDs")
    # Duplicate occurrences are retained. Their source/mechanical holds are not
    # waived by a source-reading receipt, and omission must change the binding.
    return sorted(c["id"] for c in components)


def source_meaning_fingerprint(task: dict) -> str:
    """Hash full source meaning; no nested field or custom metadata is dropped.

    Exact original bindings, component order, source artifacts, complete source
    dependencies (including archive/member proofs) and all unknown top-level
    metadata are included. This function does not resolve or approve any value.
    Calling it on a completed runtime result gives the same hash as before its
    technical evaluation/review fields were attached.
    """
    if type(task) is not dict or type(task.get("offering_id")) is not str or not task["offering_id"].strip():
        raise ValueError("Source review requires an exact offering identity")
    if type(task.get("task_id")) is not str or not task["task_id"].strip():
        raise ValueError("Source review requires an exact task identity")
    _component_ids(task)
    bindings = task.get("original_bindings")
    if type(bindings) is not list or any(type(b) is not dict or
            type(b.get("id")) is not str or not b["id"].strip() or
            type(b.get("sha256")) is not str or not b["sha256"].strip() for b in bindings):
        raise ValueError("Source review requires every exact original ID/hash binding")
    if type(task.get("source_dependencies")) is not list:
        raise ValueError("Source review requires explicit actual source dependencies")
    if "source_artifacts" in task and type(task["source_artifacts"]) is not list:
        raise ValueError("Task source_artifacts must be a complete list")
    payload = {key: value for key, value in task.items() if key not in _TECHNICAL_FIELDS}
    meaning = {"schema": "daylight-source-meaning/1", "semantic_contract": SEMANTIC_CONTRACT, "task": payload}
    _json_tree(meaning)
    return digest(meaning)


def _receipt_types(receipt):
    _json_tree(receipt)
    string_fields = {"schema", "task_id", "task_input_sha256", "rule_fingerprint", "mapping_fingerprint",
                     "source_dependencies_sha256", "source_meaning_sha256", "reviewer", "review_id", "decision"}
    for key in string_fields & receipt.keys():
        if type(receipt[key]) is not str:
            raise ValueError(f"Malformed current source review field: {key}")
    if "component_ids" in receipt and (type(receipt["component_ids"]) is not list or
            any(type(i) is not str or not i.strip() for i in receipt["component_ids"])):
        raise ValueError("Malformed current source review component_ids")
    for key in ("accepted_for_reference", "consumer_usable"):
        if key in receipt and type(receipt[key]) is not bool:
            raise ValueError(f"Malformed current source review field: {key}")


def assess_source_review(task: dict, receipts: list[dict], receipt_bindings: list[dict]) -> tuple[str, str, list[dict]]:
    """Return current reading state/hash/holds; never remove other task holds.

    The caller byte-verifies receipt files. ``receipt_bindings`` retain those
    complete pins in stale-review diagnostics. Historical proofs are not scanned
    or migrated: only explicitly supplied current receipts can match this task.
    """
    if type(task) is not dict or type(task.get("task_id")) is not str or not task["task_id"].strip():
        raise ValueError("Source review requires an exact task identity")
    if type(receipts) is not list or any(type(r) is not dict for r in receipts):
        raise ValueError("Source reviews must be a list of receipt objects")
    if type(receipt_bindings) is not list or any(type(b) is not dict for b in receipt_bindings):
        raise ValueError("Source review receipt bindings must be a list of objects")
    _json_tree(receipt_bindings)
    for receipt in receipts:
        if "task_id" in receipt and type(receipt["task_id"]) is not str:
            raise ValueError("Malformed source review task_id")
    selected = [r for r in receipts if r.get("task_id") == task["task_id"]]
    if len(selected) > 1:
        raise ValueError("Duplicate current source review for task")
    if not selected:
        return "unreviewed", digest([]), []
    receipt = selected[0]
    _receipt_types(receipt)
    required = {"task_id": task["task_id"], "component_ids": _component_ids(task),
                "accepted_for_reference": False, "consumer_usable": False}
    schema = receipt.get("schema")
    if schema == REVIEW_SCHEMA_V1:
        try:
            required.update(schema=REVIEW_SCHEMA_V1, task_input_sha256=task["task_input_sha256"],
                rule_fingerprint=task["rule_fingerprint"], mapping_fingerprint=task["mapping_fingerprint"],
                source_dependencies_sha256=digest(task["source_dependencies"]))
        except KeyError as exc:
            raise ValueError(f"V1 source review task binding is missing: {exc.args[0]}") from exc
    elif schema == REVIEW_SCHEMA_V2:
        required.update(schema=REVIEW_SCHEMA_V2, source_meaning_sha256=source_meaning_fingerprint(task))
    valid = schema in (REVIEW_SCHEMA_V1, REVIEW_SCHEMA_V2)
    valid = valid and all(receipt.get(key) == value for key, value in required.items())
    valid = valid and bool(receipt.get("reviewer")) and bool(receipt.get("review_id"))
    valid = valid and receipt.get("decision") in {"source_reviewed", "held"}
    review_hash = digest(receipt)
    if not valid:
        return "unreviewed", review_hash, [{"code": "stale_source_review", "category": "review",
            "path": "/review_state", "source_dependencies": deepcopy(receipt_bindings)}]
    return receipt["decision"], review_hash, []
