"""Incremental batch invariants exercised with real strict r9 component shapes."""
import copy
import gzip
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from daylight_data.comparison_pipeline.common import canonical, digest, file_hash, safe_json
from daylight_data.comparison_pipeline import runner
from daylight_data.comparison_pipeline.store import Store

ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = ROOT / "docs/data/l03-plan-completion-2026-11-03-r1/clinical/complete-original-continuation-r1/typed-boundary-and-entailment-r8/ALL391_EFFECTIVE_ACTUAL_R9_COMPARISONS_R8.jsonl.gz"
OFFERING = "2026:H5652:002:000"


class IncrementalRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(EXAMPLE, "rt") as stream:
            cls.example = safe_json(next(stream))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        sealed = self.repo / runner.load_engine.__globals__["R9"]
        sealed.parent.mkdir(parents=True)
        sealed.symlink_to(ROOT / runner.load_engine.__globals__["R9"], target_is_directory=True)
        self.workspace = Path(self.temp.name) / "work"
        self.rows = [copy.deepcopy(self.example), copy.deepcopy(self.example)]
        self.rows[1]["id"] += "-SECOND"
        self.path = self.repo / "input.json"
        roots = [{"id": key, "offering_id": OFFERING, "kind": "condition",
                  "original_sha256": "e" * 64, "observation_ids": []} for key in self.example["inventory_root_ids"]]
        roots.append({"id": "CANONICAL-not-yet-authored", "offering_id": OFFERING, "kind": "claim",
                      "original_sha256": "f" * 64, "observation_ids": []})
        self.inventory_patch = patch.object(runner, "ensure_inventory", return_value={
            "mode": "cache_hit", "record_count": 392570, "offering_count": 72})
        self.scope_patch = patch.object(runner, "originals_for_offering", return_value=roots)
        self.inventory_patch.start()
        self.scope_patch.start()
        self.addCleanup(self.inventory_patch.stop)
        self.addCleanup(self.scope_patch.stop)

    def config(self, *, extra=None):
        self.path.write_bytes(canonical(self.rows))
        value = {"schema": runner.MANIFEST_SCHEMA, "offerings": [OFFERING],
                 "inputs": [{"path": "input.json", "sha256": file_hash(self.path), "offering_id": OFFERING}]}
        value.update(extra or {})
        return value

    def run_batch(self, config=None):
        return runner.run_batch(self.repo, self.workspace, config or self.config())

    def results(self, run_id=None):
        store = Store(self.workspace / "comparisons.sqlite3")
        try:
            return store.results(run_id)
        finally:
            store.close()

    def test_cold_warm_and_single_condition_delta(self):
        first = self.run_batch()
        self.assertEqual(first["cache_metrics"]["tasks_evaluated"], 2)
        warm = self.run_batch()
        self.assertEqual(warm["cache_metrics"]["task_evaluations_reused"], 2)
        self.assertEqual(warm["cache_metrics"].get("tasks_evaluated", 0), 0)
        self.rows[1]["carrier"]["context"]["setting"] += " Source-local qualification changed."
        delta = self.run_batch()
        self.assertEqual(delta["cache_metrics"]["tasks_evaluated"], 1)
        self.assertEqual(delta["cache_metrics"]["task_evaluations_reused"], 1)
        scope = delta["offerings"][OFFERING]
        self.assertEqual(scope["originals_with_candidate_inputs"], 1)
        self.assertEqual(scope["originals_without_candidate_inputs"], 1)
        self.assertEqual(scope["whole_originals_completed_by_pipeline"], 0)
        self.assertFalse(delta["consumer_usable"])

    def test_source_change_invalidates_unchanged_record(self):
        source = self.repo / "source-context.json"
        source.write_text('{"condition":"first"}')
        config = self.config(extra={"sources": [{"path": source.name, "sha256": file_hash(source)}]})
        config["inputs"][0]["dependency_paths"] = [source.name]
        self.run_batch(config)
        source.write_text('{"condition":"changed"}')
        with self.assertRaisesRegex(ValueError, "byte binding changed"):
            self.run_batch(config)
        config["sources"][0]["sha256"] = file_hash(source)
        result = self.run_batch(config)
        self.assertEqual(result["cache_metrics"]["tasks_evaluated"], 2)

    def test_rule_change_invalidates_even_with_identical_amounts(self):
        self.run_batch()
        with patch.object(runner, "rule_fingerprint", return_value="new-reviewed-rule-version"):
            result = self.run_batch()
        self.assertEqual(result["cache_metrics"]["tasks_evaluated"], 2)

    def test_all_components_survive_bundle_and_one_bad_component_blocks(self):
        # Two component records, including all source conditions, are one task.
        self.rows = [{"artifact_type": "r9_component_bundle", "id": "complete-bundle",
                      "offering_id": OFFERING, "original_ids": self.example["inventory_root_ids"],
                      "components": self.rows}]
        self.run_batch()
        result = self.results()[0]
        self.assertEqual(len(result["components"]), 2)
        self.assertEqual(len(result["mechanical_results"]), 2)
        self.assertEqual(result["status"], "comparison_held")
        self.assertFalse(result["accepted_for_reference"])

    def test_foreign_original_cannot_be_imported_or_hide_last_run(self):
        first = self.run_batch()
        self.rows[0]["inventory_root_ids"] = ["CANONICAL-wrong-offering"]
        with self.assertRaisesRegex(ValueError, "original dependency"):
            self.run_batch()
        store = Store(self.workspace / "comparisons.sqlite3")
        try:
            self.assertEqual(store.latest_run(), first["run_id"])
            self.assertEqual(len(store.results()), 2)
        finally:
            store.close()

    def test_schema_error_is_quarantined_with_raw_context(self):
        self.rows[0]["carrier"]["made_up_hidden_exception"] = "retained in quarantine"
        self.run_batch()
        row = next(r for r in self.results() if r["source_record_id"] == self.rows[0]["id"])
        self.assertEqual(row["status"], "quarantined")
        self.assertEqual(row["raw_record"]["carrier"]["made_up_hidden_exception"], "retained in quarantine")
        self.assertEqual(row["mechanical_results"], [])

    def test_quarantine_and_repair_keep_same_task_identity(self):
        clean = copy.deepcopy(self.rows)
        self.rows[0]["carrier"]["unrecognized_field"] = "source text"
        self.run_batch()
        rejected = next(r for r in self.results() if r["source_record_id"] == self.rows[0]["id"])
        self.rows = clean
        self.run_batch()
        repaired = next(r for r in self.results() if r["source_record_id"] == self.rows[0]["id"])
        self.assertEqual(rejected["task_id"], repaired["task_id"])
        self.assertNotEqual(rejected["evaluation_key"], repaired["evaluation_key"])

    def test_source_decimal_transport_is_exact_on_cold_and_warm_runs(self):
        original = self.example["inventory_root_ids"]
        raw = ('[{"artifact_type":"native_literal","id":"native-number",'
               '"offering_id":"' + OFFERING + '","original_ids":' + json.dumps(original) + ','
               '"payload":{"raw_amount":0.1234567890123456789012345},"pointer":"/raw_amount"}]')
        self.path.write_text(raw)
        config = {"schema": runner.MANIFEST_SCHEMA, "offerings": [OFFERING], "inputs": [
            {"path": self.path.name, "sha256": file_hash(self.path), "offering_id": OFFERING}]}
        self.run_batch(config)
        cold = self.results()[0]
        self.run_batch(config)
        warm = self.results()[0]
        self.assertEqual(cold["source_artifacts"][0]["literal_value"], "0.1234567890123456789012345")
        self.assertEqual(cold["source_artifacts"], warm["source_artifacts"])
        self.assertEqual(cold["evaluation_key"], warm["evaluation_key"])
        self.assertEqual(cold["mechanical_results"], [])
        self.assertEqual(cold["status"], "comparison_held")

    def test_invalid_bundle_keeps_all_literal_original_dependencies(self):
        components = copy.deepcopy(self.rows)
        components[1]["carrier"]["unrecognized_field"] = "full source retained"
        self.rows = [{"artifact_type": "r9_component_bundle", "id": "bad-bundle", "components": components}]
        self.run_batch()
        task = self.results()[0]
        self.assertEqual(task["status"], "quarantined")
        self.assertEqual(task["original_ids"], self.example["inventory_root_ids"])
        self.assertEqual(len(task["raw_record"]["components"]), 2)

    def test_exact_receipt_changes_do_not_inherit_source_review(self):
        self.run_batch()
        row = self.results()[0]
        receipt = {"schema": runner.REVIEW_SCHEMA, "task_id": row["task_id"],
                   "task_input_sha256": row["task_input_sha256"], "rule_fingerprint": row["rule_fingerprint"],
                   "mapping_fingerprint": row["mapping_fingerprint"],
                   "source_dependencies_sha256": digest(row["source_dependencies"]),
                   "component_ids": sorted(c["id"] for c in row["components"]),
                   "decision": "source_reviewed", "reviewer": "independent-test-reviewer", "review_id": "test-receipt",
                   "accepted_for_reference": False, "consumer_usable": False}
        path = self.repo / "review.json"
        path.write_bytes(canonical(receipt))
        config = self.config(extra={"source_reviews": [{"path": path.name, "sha256": file_hash(path)}]})
        reviewed = self.run_batch(config)
        self.assertEqual(reviewed["cache_metrics"]["tasks_evaluated"], 1)
        self.assertEqual(self.results()[0]["review_state"], "source_reviewed")
        self.rows[0]["carrier"]["conditions"]["qualification"]["assertion"] += " Changed condition."
        config = self.config(extra={"source_reviews": config["source_reviews"]})
        self.run_batch(config)
        changed = self.results()[0]
        self.assertEqual(changed["review_state"], "unreviewed")
        self.assertTrue(any(h["code"] == "stale_source_review" for h in changed["holds"]))
        self.assertFalse(changed["consumer_usable"])

    def test_cache_corruption_fails_closed_and_keeps_last_snapshot(self):
        first = self.run_batch()
        db = sqlite3.connect(self.workspace / "comparisons.sqlite3")
        db.execute("UPDATE cache SET payload=? WHERE namespace='evaluations'", (b"corrupt",))
        db.commit()
        db.close()
        with self.assertRaisesRegex(ValueError, "Corrupt comparison cache"):
            self.run_batch()
        self.assertEqual(len(self.results(first["run_id"])), 2)

    def test_v2_exact_source_reading_survives_technical_change_but_not_condition_change(self):
        self.run_batch()
        task = next(r for r in self.results() if r["source_record_id"] == self.rows[0]["id"])
        receipt = {"schema": "daylight-source-review-receipt/2", "task_id": task["task_id"],
                   "source_meaning_sha256": task["source_meaning_sha256"],
                   "component_ids": sorted(c["id"] for c in task["components"]),
                   "decision": "source_reviewed", "review_id": "exact-source-reading-test",
                   "reviewer": "independent-test-reviewer", "accepted_for_reference": False, "consumer_usable": False}
        path = self.repo / "v2-review.json"
        path.write_bytes(canonical(receipt))
        config = self.config(extra={"source_reviews": [{"path": path.name, "sha256": file_hash(path)}]})
        self.run_batch(config)
        with patch.object(runner, "rule_fingerprint", return_value="different-technical-code-version"):
            result = self.run_batch(config)
        unchanged = next(r for r in self.results() if r["task_id"] == task["task_id"])
        self.assertEqual(unchanged["source_meaning_sha256"], task["source_meaning_sha256"])
        self.assertEqual(unchanged["review_state"], "source_reviewed")
        self.assertEqual(result["cache_metrics"]["tasks_evaluated"], 2)
        self.assertEqual(unchanged["status"], "comparison_held")  # Source/mechanical holds remain.
        self.assertFalse(unchanged["accepted_for_reference"])
        self.assertFalse(unchanged["consumer_usable"])
        self.rows[0]["carrier"]["conditions"]["qualification"]["assertion"] += " New source qualification."
        config = self.config(extra={"source_reviews": config["source_reviews"]})
        self.run_batch(config)
        changed = next(r for r in self.results() if r["task_id"] == task["task_id"])
        self.assertEqual(changed["review_state"], "unreviewed")
        self.assertNotEqual(changed["source_meaning_sha256"], task["source_meaning_sha256"])
        self.assertTrue(any(h["code"] == "stale_source_review" for h in changed["holds"]))

    def test_duplicate_ids_abort_transaction(self):
        first = self.run_batch()
        self.rows[1]["id"] = self.rows[0]["id"]
        with self.assertRaisesRegex(ValueError, "Duplicate batch task"):
            self.run_batch()
        self.assertEqual(len(self.results(first["run_id"])), 2)

    def test_duplicate_keys_and_exponent_overflow_are_not_json_inputs(self):
        for value in ('{"amount":"0","amount":"100"}', '{"amount":1e9999}', '{"amount":NaN}'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                safe_json(value)


if __name__ == "__main__":
    unittest.main()
