"""Deterministic research work planning; these functions grant no acceptance.

Grouping here shares *review work*, never inventory identity. Every task and
original linkage survives, and the full component payload is part of the work
signature. An equal price is therefore insufficient for either grouping or
reusing a comparison. The evaluator, not this module, supplies hold/outcome
facts; unknown outcomes are conservatively treated as incomplete work.
"""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any


_PRIORITY = {
    "schema": 10,
    "adapter": 20,
    "source": 30,
    "incomplete_context": 40,
    "actual_conflict": 50,
    "review_needed": 60,
}
_ACCEPTANCE_FIELDS = {"accepted_for_reference", "accepted_for_release", "release_approved"}
# These are not planning inputs. In particular, they cannot affect priority,
# grouping, invalidation, or replay opportunities.
_COMMERCIAL_FIELDS = {
    "commercial", "commercial_metadata", "commission", "commissions",
    "payout", "payouts", "conversion_target", "commercial_rank",
}
_SOURCE_KEYS = {
    "source", "sources", "source_id", "source_ids", "source_sha256",
    "source_hash", "source_fingerprint", "source_dependencies", "source_path",
    "document_sha256", "document_id", "document_hash", "locator", "locators",
    "provenance", "source_proof", "source_proofs", "evidence", "evidence_id",
    "evidence_ids", "parent_id", "parent_ids", "parent_context", "source_graph",
    "dependency_graph", "graph_fingerprint", "context_fingerprint",
}
_SUCCESS = {
    "exact_agreement", "agreement_through_reviewed_mapping",
    "supported_carrier_statement", "documented_inapplicability",
    "agreement", "match", "supported",
}
_CONFLICT = {"conflict", "known_conflict", "source_conflict", "actual_conflict"}
_SCHEMA_CODES = {"schema", "schema_error", "invalid_schema", "schema_validation_failed"}
_ADAPTER_CODES = {
    "adapter", "adapter_error", "missing_adapter", "unsupported_adapter",
    "adapter_missing", "adapter_failure", "adapter_unavailable",
}
_SOURCE_CODES = {
    "source", "missing_source", "source_missing", "source_unavailable",
    "source_not_found", "required_source_missing", "source_access_blocked",
}
_R9_DIMENSIONS = {
    "identity", "service", "context", "cost", "unit", "boundaries",
    "conditions", "exceptions", "variant", "shared_budgets",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _scope_payload(value: Any) -> Any:
    """Preserve every nested source/component field, regardless of its name."""
    return deepcopy(value)


def _comparable_result(result: dict) -> dict:
    # Only the result envelope's non-planning metadata is excluded. Fields in
    # source payloads cannot be removed merely for sharing one of these names.
    return {key: deepcopy(value) for key, value in result.items()
            if key not in _ACCEPTANCE_FIELDS | _COMMERCIAL_FIELDS}


def _index(results: list[dict]) -> dict[str, dict]:
    if not isinstance(results, list):
        raise ValueError("results must be a list of normalized task results")
    indexed = {}
    for result in results:
        if not isinstance(result, dict) or not isinstance(result.get("task_id"), str) or not result["task_id"]:
            raise ValueError("each result requires a nonempty string task_id")
        identifier = result["task_id"]
        if identifier in indexed:
            raise ValueError(f"duplicate task_id would lose task accounting: {identifier}")
        originals = result.get("original_ids", [])
        if not isinstance(originals, list) or any(not isinstance(x, str) or not x for x in originals):
            raise ValueError(f"original_ids must be a list of nonempty strings: {identifier}")
        # Validate JSON determinism before performing any grouping.
        _canonical(result)
        indexed[identifier] = deepcopy(result)
    return indexed


def _pointer(path: str, key: Any) -> str:
    return path + "/" + str(key).replace("~", "~0").replace("/", "~1")


def _dependencies(value: Any, path: str = "/components") -> list[dict]:
    found = []
    if isinstance(value, dict):
        for key in sorted(value):
            child = _pointer(path, key)
            item = value[key]
            if key in _SOURCE_KEYS and item not in (None, "", [], {}):
                found.append({"path": child, "value": _scope_payload(item)})
            found.extend(_dependencies(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_dependencies(item, _pointer(path, index)))
    return found


def _paths(item: Any, fallback: str) -> list[str]:
    if isinstance(item, str):
        return [item] if item.startswith("/") else [fallback]
    if not isinstance(item, dict):
        return [fallback]
    values = item.get("paths", item.get("path", item.get("json_path", [])))
    values = [values] if isinstance(values, str) else values
    if not isinstance(values, list):
        return [fallback]
    # Only actual JSON pointers are emitted. The hold/result itself remains a
    # concrete location when an upstream adapter supplied prose instead.
    return sorted({x for x in values if isinstance(x, str) and x.startswith("/")}) or [fallback]


def _hold_category(hold: Any) -> str:
    if not isinstance(hold, dict):
        return "incomplete_context"
    if hold.get("code") == "comparison_outcome" and hold.get("outcome") in _CONFLICT:
        return "actual_conflict"
    category = hold.get("category")
    category = {"source_dependency": "source", "normalization": "adapter",
                "review": "review_needed", "semantics": "incomplete_context",
                "scope": "incomplete_context"}.get(category, category)
    if category in _PRIORITY:
        return category
    code = str(hold.get("code", hold.get("reason_code", ""))).lower()
    if code in _SCHEMA_CODES or code.startswith("schema_"):
        return "schema"
    if code in _ADAPTER_CODES or code.startswith("adapter_"):
        return "adapter"
    if code in _SOURCE_CODES:
        return "source"
    if code in _CONFLICT:
        return "actual_conflict"
    return "incomplete_context"


def _replay_payload(result: dict) -> dict:
    # Task/original IDs are linkages, not evidence equivalence. No field inside
    # components is stripped: source roles, conditions and parent graphs matter.
    return {key: _scope_payload(value) for key, value in result.items()
            if key not in {"task_id", "original_ids", "holds", "mechanical_results",
                           "evaluation_key", "review_state", "review_binding",
                           "review_bindings", "review_fingerprint", "cache_hit"}
            | _ACCEPTANCE_FIELDS | _COMMERCIAL_FIELDS}


def _binding(result: dict) -> dict:
    return {
        "task_id": result["task_id"],
        "offering_id": result.get("offering_id"),
        "original_ids": sorted(set(result.get("original_ids", []))),
        "evaluation_key": result.get("evaluation_key"),
        "input_fingerprint": result.get("input_fingerprint"),
        "task_input_sha256": result.get("task_input_sha256"),
        "rule_fingerprint": result.get("rule_fingerprint"),
        "mapping_fingerprint": result.get("mapping_fingerprint"),
        "review_fingerprint": result.get("review_fingerprint"),
        "adapter_id": result.get("adapter_id"),
        "adapter_version": result.get("adapter_version"),
        "review_state": result.get("review_state", "unreviewed"),
        "accepted_for_reference": False,
    }


def _result_dependencies(result: dict) -> list[dict]:
    """Retain root-normalized source dependencies as well as component proofs."""
    dependencies = _dependencies(result.get("components", []))
    supplied = result.get("source_dependencies", [])
    if supplied not in (None, [], {}):
        dependencies.append({"path": "/source_dependencies", "value": _scope_payload(supplied)})
    return dependencies


def _difference_paths(result: dict, comparison: dict, difference: Any, fallback: str) -> list[str]:
    """Locate sealed-r9 dimension names in the actual supplied component."""
    if isinstance(difference, str) and difference in _R9_DIMENSIONS:
        components = result.get("components", [])
        component_id = comparison.get("component_id")
        if component_id is not None and isinstance(components, list):
            paths = []
            for index, component in enumerate(components):
                if isinstance(component, dict) and component.get("id", component.get("component_id")) == component_id:
                    for side in ("cms", "carrier"):
                        if isinstance(component.get(side), dict) and difference in component[side]:
                            paths.append(f"/components/{index}/{side}/{difference}")
            if paths:
                return paths
    return _paths(difference, fallback)


def build_work_queue(results: list[dict]) -> list[dict]:
    """Return stable exception/review groups with all task/original linkages.

    Structured holds may supply category, code/reason_code, JSON-pointer path(s)
    and source_dependencies. Missing/unknown evidence stays incomplete; the
    planner neither decodes source selectors nor judges semantic equivalence.
    """
    indexed = _index(results)
    groups: dict[str, dict] = {}
    for task_id, result in sorted(indexed.items()):
        issues: dict[str, list[dict]] = {}

        def add(category: str, code: str, path: str | list[str], dependency: Any = None) -> None:
            issues.setdefault(category, []).append({
                "code": code,
                "paths": [path] if isinstance(path, str) else path,
                "source_dependencies": _scope_payload(dependency) if dependency else [],
            })

        for required in ("offering_id", "adapter_id", "adapter_version", "input_fingerprint"):
            if not result.get(required):
                add("adapter" if required.startswith("adapter_") else "incomplete_context",
                    "MISSING_" + required.upper(), "/" + required)
        if not result.get("original_ids"):
            add("incomplete_context", "MISSING_ORIGINAL_LINKAGE", "/original_ids")
        if not isinstance(result.get("components"), list) or not result["components"]:
            add("incomplete_context", "MISSING_COMPONENT_CONTEXT", "/components")

        holds = result.get("holds", [])
        if not isinstance(holds, list):
            add("schema", "INVALID_HOLDS_SHAPE", "/holds")
            holds = []
        for index, hold in enumerate(holds):
            fallback = f"/holds/{index}"
            code = (str(hold.get("code", hold.get("reason_code", "INCOMPLETE_CONTEXT")))
                    if isinstance(hold, dict) else "UNSTRUCTURED_HOLD")
            add(_hold_category(hold), code, _paths(hold, fallback),
                hold.get("source_dependencies") if isinstance(hold, dict) else None)

        mechanical = result.get("mechanical_results", [])
        if not isinstance(mechanical, list):
            add("schema", "INVALID_MECHANICAL_RESULTS_SHAPE", "/mechanical_results")
            mechanical = []
        if not mechanical:
            add("incomplete_context", "NO_MECHANICAL_RESULT", "/mechanical_results")
        for index, comparison in enumerate(mechanical):
            fallback = f"/mechanical_results/{index}"
            if not isinstance(comparison, dict):
                add("schema", "INVALID_MECHANICAL_RESULT", fallback)
                continue
            outcome = str(comparison.get("outcome", "")).lower()
            differences = comparison.get("differences", [])
            paths = []
            if isinstance(differences, list):
                for position, difference in enumerate(differences):
                    paths.extend(_difference_paths(result, comparison, difference,
                                                   f"{fallback}/differences/{position}"))
            else:
                add("schema", "INVALID_DIFFERENCES_SHAPE", fallback + "/differences")
            paths = sorted(set(paths)) or [fallback + "/outcome"]
            if outcome in _CONFLICT:
                add("actual_conflict", "EXPLICIT_MECHANICAL_CONFLICT", paths)
            elif outcome in _SCHEMA_CODES:
                add("schema", "MECHANICAL_SCHEMA_FAILURE", paths)
            elif outcome in _ADAPTER_CODES:
                add("adapter", "MECHANICAL_ADAPTER_FAILURE", paths)
            elif outcome in _SOURCE_CODES:
                add("source", "MECHANICAL_SOURCE_DEPENDENCY", paths)
            elif outcome == "different_basis":
                add("incomplete_context", "MECHANICAL_BASIS_ALIGNMENT_REQUIRED", paths)
            elif outcome not in _SUCCESS:
                add("incomplete_context", "INCOMPLETE_OR_UNKNOWN_MECHANICAL_OUTCOME", paths)
            elif differences and outcome != "agreement_through_reviewed_mapping":
                # A claimed success plus differences is not a new conflict fact.
                add("incomplete_context", "SUCCESS_WITH_UNRESOLVED_DIFFERENCES", paths)

        state = result.get("review_state", "unreviewed")
        if state not in {"unreviewed", "source_reviewed", "held"}:
            add("schema", "INVALID_REVIEW_STATE", "/review_state")
        if state != "source_reviewed":
            add("review_needed", "SOURCE_REVIEW_HELD" if state == "held" else "EXACT_SOURCE_REVIEW_REQUIRED", "/review_state")

        dependencies = _result_dependencies(result)
        for category, reasons in issues.items():
            reasons.sort(key=_canonical)
            work = {
                # This hash includes task/original lineage in the evaluator.
                # All actual component/source/role fields and the conservative
                # adapter input fingerprint stay bound; linkages stay below.
                "payload": {k: v for k, v in _replay_payload(result).items()
                            if k != "task_input_sha256"},
                "category": category, "issues": reasons,
                "review_binding": _scope_payload({k: v for k, v in result.items() if k.startswith("review_")}),
            }
            # Equal missing context cannot establish reusable source work.
            if not dependencies or not result.get("input_fingerprint"):
                work["ungroupable_task_id"] = task_id
            signature = _digest(work)
            group = groups.setdefault(signature, {
                "queue_id": "work-" + signature,
                "review_work_signature": signature,
                "category": category,
                "priority": _PRIORITY[category],
                "priority_reason_code": "RESEARCH_" + category.upper(),
                "reason_codes": sorted({reason["code"] for reason in reasons}),
                "paths": sorted({path for reason in reasons for path in reason["paths"]}),
                "source_dependencies": dependencies,
                "reported_source_dependencies": [reason["source_dependencies"] for reason in reasons
                                                 if reason["source_dependencies"]],
                "task_bindings": [],
                "grouping_role": "identical_review_work_only_not_inventory_aliasing",
                "source_inventory_mutated": False,
                "accepted_for_reference": False,
            })
            group["task_bindings"].append(_binding(result))

    queue = []
    for group in groups.values():
        group["task_bindings"].sort(key=lambda item: item["task_id"])
        bindings = group["task_bindings"]
        group.update(
            task_ids=[item["task_id"] for item in bindings],
            offering_ids=sorted({item["offering_id"] for item in bindings if item["offering_id"] is not None}),
            original_ids=sorted({original for item in bindings for original in item["original_ids"]}),
            evaluation_keys=sorted({item["evaluation_key"] for item in bindings if item["evaluation_key"] is not None}),
            metrics={"review_work_group_count": 1, "task_count": len(bindings),
                     "linked_original_count": len({original for item in bindings for original in item["original_ids"]}),
                     "replay_reuse_opportunities": max(0, len(bindings) - 1)},
        )
        queue.append(group)
    return sorted(queue, key=lambda item: (item["priority"], item["queue_id"]))


def _changes(previous: Any, current: Any, path: str = "") -> list[dict]:
    if type(previous) is not type(current):
        return [{"path": path, "change": "replaced", "previous": previous, "current": current}]
    if isinstance(previous, dict):
        changes = []
        for key in sorted(previous.keys() | current.keys()):
            pointer = _pointer(path, key)
            if key not in previous:
                changes.append({"path": pointer, "change": "added", "current": current[key]})
            elif key not in current:
                changes.append({"path": pointer, "change": "removed", "previous": previous[key]})
            else:
                changes.extend(_changes(previous[key], current[key], pointer))
        return changes
    if isinstance(previous, list):
        changes = []
        for index in range(max(len(previous), len(current))):
            pointer = _pointer(path, index)
            if index >= len(previous):
                changes.append({"path": pointer, "change": "added", "current": current[index]})
            elif index >= len(current):
                changes.append({"path": pointer, "change": "removed", "previous": previous[index]})
            else:
                changes.extend(_changes(previous[index], current[index], pointer))
        return changes
    return [] if previous == current else [
        {"path": path, "change": "replaced", "previous": previous, "current": current}]


def _invalidation_reasons(changes: list[dict]) -> list[str]:
    reasons = set()
    for change in changes:
        path = change["path"].lower()
        if path.startswith("/adapter_"):
            reasons.add("ADAPTER_CHANGED")
        if path.startswith("/offering_id"):
            reasons.add("OFFERING_SCOPE_CHANGED")
        if path.startswith("/original_ids"):
            reasons.add("ORIGINAL_LINKAGE_CHANGED")
        if path.startswith("/input_fingerprint"):
            reasons.add("INPUT_FINGERPRINT_CHANGED")
        if path.startswith("/task_input_sha256"):
            reasons.add("TASK_INPUT_BINDING_CHANGED")
        if path.startswith("/mapping_fingerprint"):
            reasons.add("MAPPING_BINDING_CHANGED")
        if path.startswith("/review_"):
            reasons.add("REVIEW_BINDING_CHANGED")
        if path.startswith("/evaluation_key"):
            reasons.add("EVALUATION_BINDING_CHANGED")
        if any(token in path for token in ("source", "provenance", "locator", "proof", "evidence", "document")):
            reasons.add("SOURCE_BINDING_CHANGED")
        if any(token in path for token in ("context", "condition", "parent", "graph", "role", "network", "variant", "year", "population", "setting")):
            reasons.add("CONTEXT_OR_DEPENDENCY_CHANGED")
        if any(token in path for token in ("rule", "selector", "predicate", "meaning", "frequency", "amount", "cost")):
            reasons.add("RULE_OR_MEANING_CHANGED")
        if path.startswith("/components"):
            reasons.add("COMPONENT_INPUT_CHANGED")
        if path.startswith(("/holds", "/mechanical_results")):
            reasons.add("MECHANICAL_RESULT_OR_HOLD_CHANGED")
    return sorted(reasons or {"TASK_PAYLOAD_CHANGED"})


def _without_container_locator(result: dict) -> dict:
    """Omit only the enclosing transport's path/hash, keeping the record proof."""
    result = dict(result)
    artifact = result.get("input_artifact")
    if isinstance(artifact, dict):
        result["input_artifact"] = {key: value for key, value in artifact.items()
                                    if key not in {"path", "sha256"}}
    return result


def _container_rebinding(previous: dict, current: dict) -> tuple[dict | None, bool]:
    old, new = previous.get("input_artifact"), current.get("input_artifact")
    old_locator = {key: old[key] for key in ("path", "sha256") if isinstance(old, dict) and key in old}
    new_locator = {key: new[key] for key in ("path", "sha256") if isinstance(new, dict) and key in new}
    if _canonical(old_locator) == _canonical(new_locator):
        return None, False
    # A container's edit is informational only when BOTH the record and actual
    # evaluation fingerprints are present/unchanged, and literally every other
    # task/component/source/context/proof field is unchanged. Never strip a
    # source dependency, raw record or the record's own fingerprint.
    same_proofs = (
        isinstance(old, dict) and isinstance(new, dict)
        and isinstance(old.get("record_sha256"), str) and bool(old["record_sha256"])
        and old.get("record_sha256") == new.get("record_sha256")
        and isinstance(previous.get("evaluation_key"), str) and bool(previous["evaluation_key"])
        and previous.get("evaluation_key") == current.get("evaluation_key")
    )
    informational = same_proofs and (
        _canonical(_without_container_locator(_comparable_result(previous)))
        == _canonical(_without_container_locator(_comparable_result(current))))
    rebinding = dict(
        _binding(current), previous_artifact=deepcopy(old), current_artifact=deepcopy(new),
        previous_artifact_present="input_artifact" in previous,
        current_artifact_present="input_artifact" in current,
        informational_only=bool(informational),
        reason_code="CONTAINER_REBOUND_WITH_IDENTICAL_RECORD_AND_EVALUATION" if informational
        else "CONTAINER_REBOUND_REQUIRES_MATERIAL_TASK_REVIEW",
    )
    return rebinding, bool(informational)


def compare_snapshots(previous: list[dict], current: list[dict]) -> dict:
    """Describe task changes and replay opportunities without deleting inventory.

    Removed tasks remain explicit retention obligations. Review/acceptance is
    never copied to a new evaluation: even unchanged-source replay is a proposed
    mechanical optimization, not independent review or reference approval.
    """
    before, after = _index(previous), _index(current)
    added = [_binding(after[key]) for key in sorted(after.keys() - before.keys())]
    removed = [dict(_binding(before[key]), reason_code="TASK_REMOVED_RETAIN_SOURCE_INVENTORY",
                    inventory_deletion_permitted=False) for key in sorted(before.keys() - after.keys())]
    changed, unchanged, container_rebindings = [], [], []
    replay_count = 0
    for key in sorted(before.keys() & after.keys()):
        old, new = before[key], after[key]
        rebinding, informational = _container_rebinding(old, new)
        if rebinding is not None:
            container_rebindings.append(rebinding)
        comparable_old, comparable_new = _comparable_result(old), _comparable_result(new)
        replay_old, replay_new = _replay_payload(old), _replay_payload(new)
        if informational:
            comparable_old, comparable_new = (_without_container_locator(comparable_old),
                                               _without_container_locator(comparable_new))
            replay_old, replay_new = _without_container_locator(replay_old), _without_container_locator(replay_new)
        differences = _changes(comparable_old, comparable_new)
        replay = _canonical(replay_old) == _canonical(replay_new)
        # Empty evidence is not a useful replay opportunity.
        replay = (replay and bool(new.get("components")) and bool(new.get("input_fingerprint"))
                  and bool(_result_dependencies(new)))
        replay_count += int(replay)
        binding = _binding(new)
        if differences:
            changed.append(dict(
                binding, previous_original_ids=sorted(set(old.get("original_ids", []))),
                impacted_original_ids=sorted(set(old.get("original_ids", [])) | set(new.get("original_ids", []))),
                changes=differences, invalidation_reason_codes=_invalidation_reasons(differences),
                mechanical_replay_opportunity=replay, review_requires_exact_current_binding=True,
                source_dependencies=_result_dependencies(new),
                previous_source_dependencies=_result_dependencies(old),
            ))
        else:
            unchanged.append(dict(binding, mechanical_replay_opportunity=replay,
                                  review_requires_exact_current_binding=True))
    impacted = sorted({original for entry in added + removed + changed
                       for original in entry.get("impacted_original_ids", entry["original_ids"])})
    queue = build_work_queue(current)
    replay_groups: dict[str, int] = {}
    for result in after.values():
        if result.get("components") and result.get("input_fingerprint") and _result_dependencies(result):
            fingerprint = _digest(_replay_payload(result))
            replay_groups[fingerprint] = replay_groups.get(fingerprint, 0) + 1
    return {
        "added": added, "removed": removed, "changed": changed, "unchanged": unchanged,
        "container_rebindings": container_rebindings,
        "impacted_original_ids": impacted,
        "metrics": {
            "previous_task_count": len(before), "current_task_count": len(after),
            "added_task_count": len(added), "removed_task_count": len(removed),
            "changed_task_count": len(changed), "unchanged_task_count": len(unchanged),
            "container_rebinding_count": len(container_rebindings),
            "informational_container_rebinding_count": sum(item["informational_only"] for item in container_rebindings),
            "impacted_original_count": len(impacted),
            "review_work_group_count": len(queue),
            "queued_task_count": len({task for item in queue for task in item["task_ids"]}),
            "mechanical_replay_opportunities": replay_count,
            "exact_duplicate_replay_opportunities": sum(count - 1 for count in replay_groups.values()),
        },
        "metric_scope": "task_linkages_and_review_work_not_verified_benefit_counts",
        "source_inventory_mutated": False, "inventory_deletion_permitted": False,
        "acceptance_inherited": False, "accepted_for_reference": False,
    }
