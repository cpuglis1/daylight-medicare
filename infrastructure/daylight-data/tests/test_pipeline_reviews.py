"""Source-reading reuse is exact meaning reuse, never a mechanical waiver."""
from copy import deepcopy
from decimal import Decimal
import unittest
from unittest.mock import patch

from daylight_data.comparison_pipeline import reviews
from daylight_data.comparison_pipeline.common import digest


def task():
    def component(identifier):
        return {"id": identifier, "inventory_root_ids": ["original-one", "original-two"],
            "cms": {"identity": {"year": 2026, "contract": "H1045", "plan": "048", "segment": "002"},
                    "context": {"network": "in_network"}, "cost": {"amount": "10.00"},
                    "evidence": [{"source_sha256": "a" * 64, "member": "official.json", "pointer": "/field"}]},
            "carrier": {"identity": {"year": 2026, "contract": "H1045", "plan": "048", "segment": "002"},
                "conditions": {"qualification": {"state": "asserted", "assertion": "Only under full antecedent",
                                                "obligation_ids": ["original-one"], "evidence_ids": ["proof-one"]}},
                "exceptions": [{"if": "exact alternative", "then": "separate source branch"}],
                "shared_budgets": [{"id": "pool", "members": ["A", "B"]}],
                "evidence": [{"source_sha256": "b" * 64, "pdf_page": 12,
                              "parent": "Entire governing paragraph", "child_ids": ["child-one", "child-two"]}]},
            "outcome": "insufficient_evidence", "interpretation_review_receipt": "old-proof-not-migrated",
            "accepted_for_reference": False, "full_custom_component_metadata": {"all": ["clauses", "retained"]}}
    return {"schema": "daylight/comparison-task/1", "task_id": "stable-task", "offering_id": "2026:H1045:048:002",
        "source_record_id": "stable-record", "original_ids": ["original-one", "original-two"],
        "original_bindings": [{"id": "original-one", "sha256": "1" * 64},
                              {"id": "original-two", "sha256": "2" * 64}],
        "components": [component("component-B"), component("component-A")],
        "source_artifacts": [{"role": "untrusted_source", "raw_record": {
            "full_parent": "All governing paragraphs", "children": [{"id": "child-one", "role": "required"}],
            "provenance": {"source": "original bytes", "interpretation": "Full conditional reading"}}}],
        "source_dependencies": [{"path": "sources/original.zip", "sha256": "a" * 64,
            "role": "official_native", "member": "original/official.json", "member_bytes": 123,
            "archive_sha256": "c" * 64}, {"path": "sources/eoc.pdf", "sha256": "b" * 64, "role": "carrier"}],
        "interpretation": {"meaning": "Full exact reading", "Boolean": {"AND": ["A", {"OR": ["B", "C"]}]}},
        "parent_child_scope": {"required": ["child-one", "child-two"], "closed": False},
        "provenance": {"source": {"all_custom_source_metadata": "retained"}},
        "adapter_id": "sealed-r9-component-bundle", "adapter_version": "adapter/old",
        "adapter_dependencies": {"implementation": {"sha256": "old-code"}},
        "input_fingerprint": "exact-source-record-hash", "task_input_sha256": "old-technical-task-hash",
        "decimal_encoding": [{"path": "/raw/source_number", "value": "0.1234567890123456789"}],
        "decimal_encoding_path_basis": "raw_record RFC6901 pointers",
        "rule_fingerprint": "old-rules", "mapping_fingerprint": "old-mapping",
        "holds": [{"code": "unknown_source_scope", "category": "semantics"}],
        "research_only": True, "accepted_for_reference": False, "consumer_usable": False}


def receipt(value, version=2, decision="source_reviewed"):
    result = {"schema": reviews.REVIEW_SCHEMA_V2 if version == 2 else reviews.REVIEW_SCHEMA_V1,
        "task_id": value["task_id"], "component_ids": sorted(c["id"] for c in value["components"]),
        "reviewer": "independent-source-reader", "review_id": "explicit-new-receipt",
        "decision": decision, "accepted_for_reference": False, "consumer_usable": False}
    if version == 2:
        result["source_meaning_sha256"] = reviews.source_meaning_fingerprint(value)
    else:
        result.update(task_input_sha256=value["task_input_sha256"], rule_fingerprint=value["rule_fingerprint"],
                      mapping_fingerprint=value["mapping_fingerprint"],
                      source_dependencies_sha256=digest(value["source_dependencies"]))
    return result


class SourceReviewTests(unittest.TestCase):
    def setUp(self):
        self.task = task()
        self.bindings = [{"path": "explicit-receipts.jsonl", "sha256": "d" * 64, "role": "source_review"}]

    def assess(self, value=None, receipts=None):
        return reviews.assess_source_review(self.task if value is None else value,
            [receipt(self.task)] if receipts is None else receipts, self.bindings)

    def test_v2_identical_reading_survives_technical_changes_but_mechanics_must_replay(self):
        original = receipt(self.task)
        changed = deepcopy(self.task)
        changed.update(adapter_version="adapter/new", adapter_dependencies={"implementation": {"sha256": "new-code"}},
            task_input_sha256="new-task-hash", rule_fingerprint="new-cli-store-and-engine-code",
            mapping_fingerprint="new-mapping-method", comparison_checks=[{"outcome": "fresh mechanical result"}],
            holds=[{"code": "unresolved_source_still_blocks"}], adapter_holds=[{"code": "new-technical-diagnostic"}],
            input_artifact={"path": "new/container.jsonl.gz", "sha256": "new-container"})
        self.assertEqual(self.assess(changed, [original]), ("source_reviewed", digest(original), []))
        before = digest({"input": self.task["task_input_sha256"], "rules": self.task["rule_fingerprint"],
                         "mapping": self.task["mapping_fingerprint"]})
        after = digest({"input": changed["task_input_sha256"], "rules": changed["rule_fingerprint"],
                        "mapping": changed["mapping_fingerprint"]})
        self.assertNotEqual(before, after)
        self.assertEqual(changed["holds"], [{"code": "unresolved_source_still_blocks"}])
        self.assertFalse(changed["accepted_for_reference"])

    def test_fingerprint_is_idempotent_on_completed_results_and_does_not_mutate(self):
        value = deepcopy(self.task)
        expected = reviews.source_meaning_fingerprint(value)
        value.update(source_meaning_sha256=expected, review_state="source_reviewed", review_fingerprint="review-hash",
            review_binding={"technical": "binding"}, review_bindings=["binding"], status="comparison_held",
            evaluation_key="technical-key", mechanical_results=[{"outcome": "insufficient_evidence"}],
            cache_hit=True, cache_metrics={"reused": 1}, timings={"seconds": 0.1}, run_id="new-run")
        before = deepcopy(value)
        self.assertEqual(reviews.source_meaning_fingerprint(value), expected)
        self.assess(value)
        self.assertEqual(value, before)

    def test_prefilled_meaning_hash_cannot_hide_changed_conditions(self):
        current = receipt(self.task)
        changed = deepcopy(self.task)
        changed["source_meaning_sha256"] = current["source_meaning_sha256"]
        changed["components"][0]["carrier"]["conditions"]["qualification"]["assertion"] += " New material qualifier."
        self.assertNotEqual(reviews.source_meaning_fingerprint(changed), changed["source_meaning_sha256"])
        self.assertEqual(self.assess(changed, [current])[0], "unreviewed")

    def test_every_condition_scope_proof_identity_original_and_source_change_stales_v2(self):
        changes = {
            "offering": lambda t: t.update(offering_id="2026:H1045:048:003"),
            "condition": lambda t: t["components"][0]["carrier"]["conditions"]["qualification"].update(assertion="Different antecedent"),
            "condition_child": lambda t: t["components"][0]["carrier"]["conditions"]["qualification"]["obligation_ids"].append("another-child"),
            "condition_proof": lambda t: t["components"][0]["carrier"]["conditions"]["qualification"]["evidence_ids"].append("another-proof"),
            "identity": lambda t: t["components"][0]["carrier"]["identity"].update(segment="003"),
            "context": lambda t: t["components"][0]["cms"]["context"].update(network="out_of_network"),
            "exception": lambda t: t["components"][0]["carrier"]["exceptions"][0].update(then="Different exception branch"),
            "shared_budget": lambda t: t["components"][0]["carrier"]["shared_budgets"][0]["members"].append("C"),
            "evidence_parent": lambda t: t["components"][0]["carrier"]["evidence"][0].update(parent="Different whole parent"),
            "evidence_source": lambda t: t["components"][0]["carrier"]["evidence"][0].update(source_sha256="f" * 64),
            "component_top_metadata": lambda t: t["components"][0].update(interpretation_review_receipt="different exact proof"),
            "component_order": lambda t: t["components"].reverse(),
            "component_omission": lambda t: t["components"].pop(),
            "source_artifact_parent": lambda t: t["source_artifacts"][0]["raw_record"].update(full_parent="Different parent"),
            "source_artifact_child": lambda t: t["source_artifacts"][0]["raw_record"]["children"][0].update(role="optional"),
            "source_artifact_omission": lambda t: t["source_artifacts"].clear(),
            "source_member": lambda t: t["source_dependencies"][0].update(member="different/member.json"),
            "source_archive": lambda t: t["source_dependencies"][0].update(archive_sha256="e" * 64),
            "source_length": lambda t: t["source_dependencies"][0].update(member_bytes=124),
            "source_bytes": lambda t: t["source_dependencies"][1].update(sha256="e" * 64),
            "source_actual_path": lambda t: t["source_dependencies"][1].update(path="other/exact-proof.pdf"),
            "source_dependency_omission": lambda t: t["source_dependencies"].pop(),
            "source_dependency_order": lambda t: t["source_dependencies"].reverse(),
            "original_hash": lambda t: t["original_bindings"][0].update(sha256="e" * 64),
            "original_id": lambda t: t["original_bindings"][0].update(id="different-original"),
            "original_omission": lambda t: t["original_bindings"].pop(),
            "original_role_scope": lambda t: t["original_ids"].pop(),
            "interpretation": lambda t: t["interpretation"]["Boolean"].update(AND=["A", "B", "C"]),
            "parent_child_scope": lambda t: t["parent_child_scope"]["required"].pop(),
            "provenance": lambda t: t["provenance"]["source"].update(all_custom_source_metadata="changed"),
            "adapter_family": lambda t: t.update(adapter_id="different-source-family"),
            "input_fingerprint": lambda t: t.update(input_fingerprint="different-source-input"),
            "source_record_id": lambda t: t.update(source_record_id="different-source-record"),
            "decimal_encoding": lambda t: t["decimal_encoding"][0].update(value="0.1234567890123456788"),
        }
        current = receipt(self.task)
        for name, mutate in changes.items():
            with self.subTest(change=name):
                changed = deepcopy(self.task); mutate(changed)
                self.assertNotEqual(reviews.source_meaning_fingerprint(changed), current["source_meaning_sha256"])
                state, review_hash, holds = self.assess(changed, [current])
                self.assertEqual(state, "unreviewed")
                self.assertEqual(review_hash, digest(current))
                self.assertEqual(holds[0]["code"], "stale_source_review")

    def test_new_unknown_top_metadata_and_nested_technical_names_are_preserved(self):
        expected = reviews.source_meaning_fingerprint(self.task)
        for mutate in (
                lambda t: t.update(new_semantic_field={"eligibility": "new qualifier"}),
                lambda t: t.update(adapter_input_scope="unknown semantic metadata"),
                lambda t: t["components"][0].update(rule_fingerprint="component proof metadata"),
                lambda t: t["source_artifacts"][0]["raw_record"].update(input_artifact={"path": "actual parent source"})):
            changed = deepcopy(self.task); mutate(changed)
            self.assertNotEqual(reviews.source_meaning_fingerprint(changed), expected)

    def test_semantic_schema_or_family_contract_change_invalidates_receipt(self):
        current = receipt(self.task)
        for key, replacement in (("schema_sha256", "f" * 64), ("condition_family_ids", ["different-contract-family"]),
                                 ("complete_meaning_contract_id", "new-semantic-contract")):
            changed = deepcopy(reviews.SEMANTIC_CONTRACT); changed[key] = replacement
            with self.subTest(key=key), patch.object(reviews, "SEMANTIC_CONTRACT", changed):
                self.assertEqual(self.assess(receipts=[current])[0], "unreviewed")
        self.assertEqual(self.assess(receipts=[current])[0], "source_reviewed")

    def test_source_artifact_only_and_quarantined_raw_are_fully_hashed(self):
        value = deepcopy(self.task); value["components"] = []
        value["raw_record"] = {"whole_unknown_source": {"amount": Decimal("0.12345678901234567890123456789")}}
        current = receipt(value)
        self.assertEqual(self.assess(value, [current])[0], "source_reviewed")
        value["raw_record"]["whole_unknown_source"]["amount"] += Decimal("0.00000000000000000001")
        self.assertEqual(self.assess(value, [current])[0], "unreviewed")

    def test_v1_stays_exact_and_stales_on_any_legacy_binding_change(self):
        current = receipt(self.task, version=1)
        self.assertEqual(self.assess(receipts=[current]), ("source_reviewed", digest(current), []))
        for key in ("task_input_sha256", "rule_fingerprint", "mapping_fingerprint"):
            changed = deepcopy(self.task); changed[key] += "-new"
            with self.subTest(key=key):
                self.assertEqual(self.assess(changed, [current])[0], "unreviewed")
        changed = deepcopy(self.task); changed["source_dependencies"][0]["member"] = "new-member"
        self.assertEqual(self.assess(changed, [current])[0], "unreviewed")
        current["component_ids"].reverse()
        self.assertEqual(self.assess(receipts=[current])[0], "unreviewed")

    def test_held_receipts_keep_held_state_without_mutating_existing_holds(self):
        for version in (1, 2):
            current = receipt(self.task, version=version, decision="held")
            before = deepcopy(self.task)
            self.assertEqual(self.assess(receipts=[current]), ("held", digest(current), []))
            self.assertEqual(self.task, before)
            self.assertTrue(self.task["holds"])

    def test_no_receipt_no_historical_autoimport_and_unrelated_receipt_ignored(self):
        self.assertEqual(self.assess(receipts=[]), ("unreviewed", digest([]), []))
        unrelated = receipt(self.task); unrelated["task_id"] = "another-task"
        self.assertEqual(self.assess(receipts=[unrelated]), ("unreviewed", digest([]), []))

    def test_duplicate_current_receipts_including_v1_plus_v2_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate current source review"):
            self.assess(receipts=[receipt(self.task, 1), receipt(self.task, 2)])

    def test_malformed_current_receipt_types_are_rejected(self):
        for field, value in (("reviewer", ["reader"]), ("review_id", True), ("decision", ["source_reviewed"]),
                             ("component_ids", "component-A"), ("source_meaning_sha256", None),
                             ("accepted_for_reference", 0), ("consumer_usable", 0)):
            current = receipt(self.task); current[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.assess(receipts=[current])
        for receipts in (None, {}, [None], [{"task_id": []}]):
            with self.subTest(receipts=receipts), self.assertRaises(ValueError):
                reviews.assess_source_review(self.task, receipts, self.bindings)

    def test_missing_stale_or_inapplicable_receipt_values_never_grant_acceptance(self):
        for field, value in (("source_meaning_sha256", "old-meaning"), ("component_ids", []),
                             ("schema", "unknown-schema"), ("decision", "accepted_mapping"),
                             ("accepted_for_reference", True), ("consumer_usable", True),
                             ("reviewer", ""), ("review_id", "")):
            current = receipt(self.task); current[field] = value
            with self.subTest(field=field):
                self.assertEqual(self.assess(receipts=[current])[0], "unreviewed")
        current = receipt(self.task); del current["accepted_for_reference"]
        self.assertEqual(self.assess(receipts=[current])[0], "unreviewed")

    def test_stale_diagnostic_preserves_full_receipt_proofs_without_aliasing(self):
        current = receipt(self.task); current["source_meaning_sha256"] = "old"
        _, _, holds = self.assess(receipts=[current])
        self.assertEqual(holds, [{"code": "stale_source_review", "category": "review",
                                  "path": "/review_state", "source_dependencies": self.bindings}])
        holds[0]["source_dependencies"][0]["path"] = "changed local result"
        self.assertEqual(self.bindings[0]["path"], "explicit-receipts.jsonl")

    def test_key_order_is_canonical_but_numeric_and_boolean_meanings_differ(self):
        reverse = dict(reversed(list(self.task.items())))
        self.assertEqual(reviews.source_meaning_fingerprint(reverse), reviews.source_meaning_fingerprint(self.task))
        a = deepcopy(self.task); b = deepcopy(self.task)
        a["custom_source_flag"] = False; b["custom_source_flag"] = 0
        self.assertNotEqual(reviews.source_meaning_fingerprint(a), reviews.source_meaning_fingerprint(b))

    def test_malformed_task_trees_and_missing_binding_structures_fail_closed(self):
        for mutate in (lambda t: t.pop("original_bindings"), lambda t: t.update(source_dependencies=None),
                       lambda t: t.update(components=["not an object"]), lambda t: t.update(offering_id=None),
                       lambda t: t.update(custom_source=float("nan")), lambda t: t.update(custom_source={1: "coercion"})):
            changed = deepcopy(self.task); mutate(changed)
            with self.assertRaises(ValueError):
                reviews.source_meaning_fingerprint(changed)


if __name__ == "__main__":
    unittest.main()
