"""Meaningful regression cases for exact-context research work planning."""

from copy import deepcopy
import json
import unittest

from daylight_data.comparison_pipeline.planning import build_work_queue, compare_snapshots


def result(task="task-A", originals=None):
    return {
        "task_id": task, "offering_id": "2026:H5652:002:000",
        "original_ids": originals or ["original-A"],
        "components": [{
            "role": "complete_schedule", "source_sha256": "source-one",
            "provenance": {"locator": "/pbp/0/schedule", "proof": "proof-one"},
            "context": {"year": 2026, "network": "in_network", "variant": "base",
                        "conditions": {"requires_referral": False},
                        "parent_context": {"id": "parent-one", "children": ["child-one"]}},
            "rule": {"amount": "44", "period": "month"},
        }],
        "adapter_id": "native-pbp", "adapter_version": "1",
        "input_fingerprint": "full-input-one", "holds": [],
        "mechanical_results": [{"outcome": "exact_agreement", "differences": []}],
        "evaluation_key": "evaluation-one", "review_state": "unreviewed",
    }


class PlanningTests(unittest.TestCase):
    def test_exact_duplicate_review_work_retains_every_task_and_original(self):
        a = result("task-A", ["original-A", "condition-A"])
        b = result("task-B", ["original-B"])
        b["evaluation_key"] = "evaluation-two"
        a["task_input_sha256"] = "lineage-input-A"
        b["task_input_sha256"] = "lineage-input-B"
        queue = build_work_queue([b, a])
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["task_ids"], ["task-A", "task-B"])
        self.assertEqual(queue[0]["original_ids"], ["condition-A", "original-A", "original-B"])
        self.assertEqual(queue[0]["evaluation_keys"], ["evaluation-one", "evaluation-two"])
        self.assertEqual(queue[0]["metrics"]["replay_reuse_opportunities"], 1)
        self.assertEqual(queue[0]["task_bindings"][1]["original_ids"], ["original-B"])

    def test_same_price_different_complete_context_never_groups(self):
        base = result()
        edits = [
            ("offering_id", "2027:H5652:002:000"),
            ("network", "out_of_network"), ("variant", "optional"),
            ("year", 2027), ("conditions", {"requires_referral": True}),
            ("parent_context", {"id": "other", "children": ["child-two"]}),
            ("source_sha256", "source-two"),
            ("role", "amount_fragment"), ("proof", "proof-two"),
        ]
        for key, value in edits:
            with self.subTest(key=key):
                changed = result("task-B", ["original-B"])
                if key == "offering_id":
                    changed[key] = value
                elif key in {"source_sha256", "role"}:
                    changed["components"][0][key] = value
                elif key == "proof":
                    changed["components"][0]["provenance"][key] = value
                else:
                    changed["components"][0]["context"][key] = value
                self.assertEqual(len(build_work_queue([base, changed])), 2)

    def test_source_and_graph_edits_invalidate_equal_numeric_price(self):
        old, new = result(), result()
        new["components"][0]["source_sha256"] = "source-two"
        new["components"][0]["context"]["parent_context"]["children"].append("new-child")
        delta = compare_snapshots([old], [new])
        change = delta["changed"][0]
        self.assertEqual(change["impacted_original_ids"], ["original-A"])
        self.assertIn("SOURCE_BINDING_CHANGED", change["invalidation_reason_codes"])
        self.assertIn("CONTEXT_OR_DEPENDENCY_CHANGED", change["invalidation_reason_codes"])
        self.assertIn("/components/0/source_sha256", {item["path"] for item in change["changes"]})
        self.assertFalse(change["mechanical_replay_opportunity"])
        self.assertEqual(new["components"][0]["rule"]["amount"], "44")

    def test_rule_adapter_and_review_binding_changes_are_explicit(self):
        for field, value, expected in [
            ("adapter_version", "2", "ADAPTER_CHANGED"),
            ("review_binding", {"receipt_sha256": "new"}, "REVIEW_BINDING_CHANGED"),
            ("review_state", "source_reviewed", "REVIEW_BINDING_CHANGED"),
            ("input_fingerprint", "new-input", "INPUT_FINGERPRINT_CHANGED"),
        ]:
            with self.subTest(field=field):
                new = result()
                new[field] = value
                delta = compare_snapshots([result()], [new])
                self.assertIn(expected, delta["changed"][0]["invalidation_reason_codes"])
                self.assertFalse(delta["accepted_for_reference"])
        new = result()
        new["components"][0]["rule"]["period"] = "year"
        delta = compare_snapshots([result()], [new])
        self.assertIn("RULE_OR_MEANING_CHANGED", delta["changed"][0]["invalidation_reason_codes"])

    def test_added_removed_and_relinked_tasks_preserve_inventory_obligations(self):
        old = [result("removed", ["retained-inventory"]), result("kept", ["old-link"])]
        new = [result("added", ["new-link"]), result("kept", ["replacement-link"])]
        delta = compare_snapshots(old, new)
        self.assertEqual(delta["removed"][0]["original_ids"], ["retained-inventory"])
        self.assertFalse(delta["removed"][0]["inventory_deletion_permitted"])
        self.assertEqual(delta["changed"][0]["impacted_original_ids"], ["old-link", "replacement-link"])
        self.assertEqual(delta["impacted_original_ids"],
                         ["new-link", "old-link", "replacement-link", "retained-inventory"])
        self.assertFalse(delta["source_inventory_mutated"])

    def test_schema_adapter_source_incomplete_conflict_and_review_are_distinct(self):
        task = result()
        task["holds"] = [
            {"code": "schema_error", "path": "/components/0/rule"},
            {"code": "adapter_missing", "path": "/adapter_id"},
            {"code": "source_unavailable", "path": "/components/0/source_sha256",
             "source_dependencies": [{"document_id": "missing-document"}]},
            {"code": "unknown_selector", "path": "/components/0/context/conditions"},
        ]
        task["mechanical_results"] = [{"outcome": "conflict", "differences": [
            {"path": "/carrier/cost/amount", "cms": "40", "carrier": "44"}]}]
        queue = build_work_queue([task])
        self.assertEqual([q["category"] for q in queue],
                         ["schema", "adapter", "source", "incomplete_context", "actual_conflict", "review_needed"])
        conflict = next(q for q in queue if q["category"] == "actual_conflict")
        self.assertEqual(conflict["paths"], ["/carrier/cost/amount"])
        self.assertTrue(conflict["source_dependencies"])
        source = next(q for q in queue if q["category"] == "source")
        self.assertEqual(source["reported_source_dependencies"], [[{"document_id": "missing-document"}]])

    def test_unrecognized_outcome_or_success_with_differences_is_not_conflict_evidence(self):
        for outcome in ["insufficient_evidence", "invented_future_outcome", "exact_agreement"]:
            task = result()
            task["mechanical_results"] = [{"outcome": outcome, "differences": ["/carrier/context/network"]}]
            queue = build_work_queue([task])
            self.assertIn("incomplete_context", {q["category"] for q in queue})
            self.assertNotIn("actual_conflict", {q["category"] for q in queue})

    def test_acceptance_is_never_inherited_even_from_unchanged_reviewed_input(self):
        task = result()
        task.update(review_state="source_reviewed", accepted_for_reference=True, release_approved=True)
        self.assertEqual(build_work_queue([task]), [])
        delta = compare_snapshots([task], [task])
        self.assertFalse(delta["accepted_for_reference"])
        self.assertFalse(delta["acceptance_inherited"])
        self.assertFalse(delta["unchanged"][0]["accepted_for_reference"])
        self.assertTrue(delta["unchanged"][0]["review_requires_exact_current_binding"])
        changed = deepcopy(task)
        changed["components"][0]["source_sha256"] = "new"
        changed["review_state"] = "unreviewed"
        queue = build_work_queue([changed])
        self.assertEqual(queue[0]["category"], "review_needed")
        self.assertFalse(queue[0]["accepted_for_reference"])

    def test_review_state_does_not_suppress_source_holds(self):
        task = result()
        task["review_state"] = "source_reviewed"
        task["holds"] = [{"code": "missing_source", "path": "/components/0/source_sha256"}]
        self.assertEqual([q["category"] for q in build_work_queue([task])], ["source"])

    def test_group_and_delta_determinism_input_immutability_and_json_output(self):
        a, b = result("A"), result("B", ["B-original"])
        original = deepcopy([a, b])
        forward = build_work_queue([a, b])
        self.assertEqual(forward, build_work_queue([b, a]))
        self.assertEqual([a, b], original)
        self.assertEqual(compare_snapshots([a, b], [a, b]), compare_snapshots([b, a], [b, a]))
        json.dumps(forward, allow_nan=False)

    def test_missing_source_context_cannot_create_duplicate_replay_group(self):
        a, b = result("A"), result("B", ["B-original"])
        for task in (a, b):
            task["components"] = [{"amount": "44"}]
        self.assertEqual(len(build_work_queue([a, b])), 2)
        self.assertEqual(compare_snapshots([], [a, b])["metrics"]["exact_duplicate_replay_opportunities"], 0)

    def test_commercial_metadata_cannot_affect_priority_signature_or_delta(self):
        a, b = result(), result()
        b["commercial_metadata"] = {"commission": "100000", "rank": 1}
        self.assertEqual(build_work_queue([a]), build_work_queue([b]))
        self.assertEqual(compare_snapshots([a], [b])["metrics"]["changed_task_count"], 0)

    def test_source_component_fields_are_never_stripped_by_metadata_name(self):
        a, b = result("A"), result("B", ["B-original"])
        b["components"][0]["provenance"]["commercial"] = {"source_note": "literal source context"}
        queue = build_work_queue([a, b])
        self.assertEqual(len(queue), 2)
        self.assertEqual({item["priority"] for item in queue}, {60})
        same_task = deepcopy(b)
        same_task["task_id"] = "A"
        delta = compare_snapshots([a], [same_task])
        self.assertIn("SOURCE_BINDING_CHANGED", delta["changed"][0]["invalidation_reason_codes"])

    def test_duplicate_task_id_and_nonfinite_input_reject_instead_of_losing_scope(self):
        with self.assertRaisesRegex(ValueError, "duplicate task_id"):
            build_work_queue([result(), result()])
        bad = result()
        bad["components"][0]["rule"]["amount"] = float("nan")
        with self.assertRaises(ValueError):
            compare_snapshots([], [bad])

    def test_json_pointer_escaping_and_null_versus_missing_are_preserved(self):
        a, b = result(), result()
        a["components"][0]["source/field~name"] = None
        delta = compare_snapshots([a], [b])
        change = delta["changed"][0]["changes"][0]
        self.assertEqual(change["path"], "/components/0/source~1field~0name")
        self.assertEqual(change["change"], "removed")
        self.assertIsNone(change["previous"])
        self.assertNotIn("current", change)

    def test_root_normalized_dependency_rule_mapping_and_review_fields(self):
        old = result()
        old.update(source_dependencies=[{"path": "document.pdf", "sha256": "one", "role": "carrier"}],
                   rule_fingerprint="rule-one", mapping_fingerprint="map-one",
                   review_fingerprint="review-one", task_input_sha256="task-input-one")
        edits = [
            ("source_dependencies", [{"path": "document.pdf", "sha256": "two", "role": "carrier"}], "SOURCE_BINDING_CHANGED"),
            ("rule_fingerprint", "rule-two", "RULE_OR_MEANING_CHANGED"),
            ("mapping_fingerprint", "map-two", "MAPPING_BINDING_CHANGED"),
            ("review_fingerprint", "review-two", "REVIEW_BINDING_CHANGED"),
            ("task_input_sha256", "task-input-two", "TASK_INPUT_BINDING_CHANGED"),
        ]
        for field, value, reason in edits:
            with self.subTest(field=field):
                new = deepcopy(old)
                new[field] = value
                delta = compare_snapshots([old], [new])
                self.assertIn(reason, delta["changed"][0]["invalidation_reason_codes"])
                dependencies = build_work_queue([new])[0]["source_dependencies"]
                self.assertIn("/source_dependencies", {dependency["path"] for dependency in dependencies})

    def test_malformed_hold_pointer_retains_concrete_fallback(self):
        task = result()
        task["holds"] = [{"code": "missing_source", "path": None}]
        source = next(item for item in build_work_queue([task]) if item["category"] == "source")
        self.assertEqual(source["paths"], ["/holds/0"])

    def test_actual_r9_dimension_differences_point_to_both_source_inputs(self):
        task = result()
        task["components"][0].update(id="record-one", cms={"context": {"network": "IN"}},
                                    carrier={"context": {"network": "OUT"}})
        task["mechanical_results"] = [{"component_id": "record-one", "outcome": "conflict",
                                       "differences": ["context"]}]
        conflict = next(item for item in build_work_queue([task]) if item["category"] == "actual_conflict")
        self.assertEqual(conflict["paths"], ["/components/0/carrier/context", "/components/0/cms/context"])

    def test_reviewed_mapping_differences_are_not_reinvented_as_unresolved(self):
        task = result()
        task["mechanical_results"] = [{"outcome": "agreement_through_reviewed_mapping",
                                       "differences": ["cost"]}]
        queue = build_work_queue([task])
        self.assertEqual([item["category"] for item in queue], ["review_needed"])
        self.assertFalse(queue[0]["accepted_for_reference"])

    def test_different_basis_retains_specific_alignment_work(self):
        task = result()
        task["mechanical_results"] = [{"outcome": "different_basis", "differences": ["context"]}]
        work = next(item for item in build_work_queue([task]) if item["category"] == "incomplete_context")
        self.assertEqual(work["reason_codes"], ["MECHANICAL_BASIS_ALIGNMENT_REQUIRED"])

    def test_runner_source_review_and_normalization_categories_keep_their_roles(self):
        task = result()
        task["holds"] = [{"code": "unbound_source_bytes", "category": "source_dependency", "path": "/components"},
                         {"code": "adapter_rejected", "category": "normalization", "path": "/"},
                         {"code": "stale_source_review", "category": "review", "path": "/review_state"}]
        task["review_state"] = "held"
        queue = build_work_queue([task])
        self.assertEqual([item["category"] for item in queue], ["adapter", "source", "review_needed"])
        review = queue[-1]
        self.assertIn("SOURCE_REVIEW_HELD", review["reason_codes"])
        self.assertNotIn("INVALID_REVIEW_STATE", review["reason_codes"])

    def test_runner_explicit_conflict_hold_is_not_misclassified_as_unknown_context(self):
        task = result()
        task["holds"] = [{"code": "comparison_outcome", "category": "semantics", "outcome": "conflict",
                          "path": "/components/0", "differences": ["cost"]}]
        task["mechanical_results"] = [{"outcome": "conflict", "differences": ["cost"]}]
        categories = {item["category"] for item in build_work_queue([task])}
        self.assertEqual(categories, {"actual_conflict", "review_needed"})

    def test_bulk_container_edit_changes_only_materially_changed_record(self):
        old_a, old_b = result("A"), result("B", ["original-B"])
        for task in (old_a, old_b):
            task["input_artifact"] = {"path": "bulk.jsonl.gz", "sha256": "old-container",
                                      "record_sha256": "exact-record-" + task["task_id"]}
        new_a, new_b = deepcopy(old_a), deepcopy(old_b)
        for task in (new_a, new_b):
            task["input_artifact"]["sha256"] = "new-container"
        new_a["components"][0]["context"]["conditions"]["requires_referral"] = True
        new_a["input_artifact"]["record_sha256"] = "changed-record-A"
        new_a["evaluation_key"] = "new-evaluation-A"
        delta = compare_snapshots([old_a, old_b], [new_a, new_b])
        self.assertEqual([item["task_id"] for item in delta["changed"]], ["A"])
        self.assertEqual([item["task_id"] for item in delta["unchanged"]], ["B"])
        self.assertEqual(delta["metrics"]["container_rebinding_count"], 2)
        self.assertEqual(delta["metrics"]["informational_container_rebinding_count"], 1)
        self.assertEqual(delta["impacted_original_ids"], ["original-A"])
        info = next(item for item in delta["container_rebindings"] if item["task_id"] == "B")
        self.assertTrue(info["informational_only"])
        self.assertEqual(info["previous_artifact"]["sha256"], "old-container")
        self.assertTrue(delta["unchanged"][0]["mechanical_replay_opportunity"])

    def test_container_exclusion_requires_all_exact_record_evaluation_and_proof_bindings(self):
        old = result()
        old["input_artifact"] = {"path": "before.json", "sha256": "old", "record_sha256": "same-record"}
        for field in ("record_sha256", "evaluation_key", "source_dependencies", "raw_record", "component", "missing_proof"):
            with self.subTest(field=field):
                new = deepcopy(old)
                new["input_artifact"].update(path="after.json", sha256="new")
                if field == "record_sha256":
                    new["input_artifact"][field] = "new-record"
                elif field == "evaluation_key":
                    new[field] = "new-evaluation"
                elif field == "source_dependencies":
                    new[field] = [{"path": "source.pdf", "sha256": "new-source"}]
                elif field == "raw_record":
                    new[field] = {"literal": "changed"}
                elif field == "component":
                    new["components"][0]["context"]["conditions"] = {"requires_referral": True}
                else:
                    del old["input_artifact"]["record_sha256"]
                    del new["input_artifact"]["record_sha256"]
                delta = compare_snapshots([old], [new])
                self.assertEqual(delta["metrics"]["changed_task_count"], 1)
                self.assertFalse(delta["container_rebindings"][0]["informational_only"])
                self.assertIn("/input_artifact/sha256", {change["path"] for change in delta["changed"][0]["changes"]})

    def test_boolean_integer_context_change_is_not_a_replay_opportunity(self):
        old, new = result(), result()
        new["components"][0]["context"]["conditions"]["requires_referral"] = 0
        delta = compare_snapshots([old], [new])
        self.assertEqual(delta["metrics"]["changed_task_count"], 1)
        self.assertFalse(delta["changed"][0]["mechanical_replay_opportunity"])


if __name__ == "__main__":
    unittest.main()
