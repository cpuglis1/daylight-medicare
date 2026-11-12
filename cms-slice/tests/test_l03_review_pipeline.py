"""Research pipeline safety and actual two-carrier preparation regressions."""
import copy
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import l03_review_pipeline as pipeline


def minimal_original(key, offering="2026:H1036:217:000", kind="claim"):
    return {"id": key, "offering_id": offering, "kind": kind,
            "accepted_for_reference": False, "states": ["evidence_reconciliation_pending"],
            "detail": {"source_basis": "carrier_only_blind_to_CMS_expected_amounts"},
            "context": {"network": "unknown", "variant": "base", "source_section": "chapter4"},
            "subject": "source service", "source_ids": ["source"], "observation_ids": ["observation"],
            "work_policy_id": "CLAIM"}


class PipelineGuards(unittest.TestCase):
    def test_denominator_cannot_be_replaced_by_selected_subset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            r9 = root / pipeline.R9
            r9.mkdir(parents=True)
            rows = [minimal_original("A"), minimal_original("B", "2026:H5652:002:000", "condition")]
            pipeline.write_rows(r9 / "master-inventory.jsonl.gz", rows)
            pipeline.write_json(r9 / "inventory-binding.json", {
                "inventory_digest": pipeline.digest(rows), "required_record_count": 2})
            pipeline.write_json(r9 / "offering-inventory.json", [
                {"offering_id": r["offering_id"], "required": {r["kind"]: 1}} for r in rows])
            for name in ("pilot-contract.json", "work-policies.json"):
                pipeline.write_json(r9 / name, {})
            pins = {name: pipeline.file_hash(r9 / name) for name in (
                "master-inventory.jsonl.gz", "inventory-binding.json", "offering-inventory.json",
                "pilot-contract.json", "work-policies.json")}
            pipeline.write_json(r9 / "freeze.json", {"inventory_digest": pipeline.digest(rows),
                "required_total": 2, "files_sha256": pins})
            config = {"bindings": {f"{pipeline.R9}/{name}": sha for name, sha in pins.items()}}
            selected, universe, binding = pipeline.load_inventory(root, config, [rows[0]["offering_id"]])
            self.assertEqual(list(selected), ["A"])
            self.assertEqual(len(universe), 2)
            self.assertEqual(binding["required_record_count"], 2)
            pipeline.write_rows(r9 / "master-inventory.jsonl.gz", [rows[0]])
            with self.assertRaisesRegex(ValueError, "denominator changed"):
                pipeline.load_inventory(root, config, [rows[0]["offering_id"]])

    def test_source_routing_keeps_unknowns_and_plans_separate(self):
        a = minimal_original("A")
        b = minimal_original("B", "2026:H5652:002:000")
        c = minimal_original("C")
        c["detail"] = {}
        self.assertEqual(pipeline.source_side(c), "unresolved")
        batches = pipeline.work_batches({r["id"]: r for r in (a, b, c)}, {"CLAIM": {}})
        self.assertEqual(len(batches), 3)
        self.assertTrue(all(not r["semantic_equivalence_asserted"] for r in batches))

    def candidate(self):
        return {"id": "case", "inventory_root_ids": ["A"], "cms": None,
                "carrier": {"identity": {"state": "unknown"}},
                "outcome": "insufficient_evidence", "accepted_for_reference": False}

    def replay(self, row, role="dependency_only"):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pipeline.write_json(root / "case.json", row)
            config = {"candidate_inputs": [{"path": "case.json", "engine": "r9",
                "offering_id": "2026:H1036:217:000", "link_role": role}],
                "bindings": {"case.json": pipeline.file_hash(root / "case.json"),
                             **{name: "pinned" for name in pipeline.engine_paths()}}}
            engine = type("Engine", (), {"compare": staticmethod(lambda *a, **kw: {
                "outcome": "insufficient_evidence", "accepted_for_reference": False})})
            with patch.object(pipeline, "load_engines", return_value={"r9": engine}):
                return pipeline.replay_candidates(root, config, {"A": minimal_original("A")})

    def test_dependency_links_never_complete_originals(self):
        result = self.replay(self.candidate())[0]
        self.assertEqual(result["originals_completed"], 0)
        self.assertFalse(result["interpretation_review_verified_by_pipeline"])
        with self.assertRaisesRegex(ValueError, "promote"):
            self.replay(self.candidate(), "completed_original")

    def test_wrong_plan_duplicate_and_deleted_dependencies_rejected(self):
        for deps in (["missing"], ["A", "A"], []):
            row = self.candidate()
            row["inventory_root_ids"] = deps
            with self.subTest(deps=deps), self.assertRaises(ValueError):
                self.replay(row)
        row = self.candidate()
        row["carrier"]["identity"] = {"year": 2027}
        with self.assertRaisesRegex(ValueError, "different offering"):
            self.replay(row)

    def test_acceptance_and_changed_outcomes_rejected(self):
        row = self.candidate()
        row["accepted_for_reference"] = True
        with self.assertRaisesRegex(ValueError, "acceptance"):
            self.replay(row)
        row = self.candidate()
        row["outcome"] = "exact_agreement"
        with self.assertRaisesRegex(ValueError, "outcome changed"):
            self.replay(row)

    def test_inputs_outside_repository_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "outside repository"):
                pipeline.repo_path(Path(tmp), "../outside")

    def test_source_adapter_cannot_include_alignment_or_drop_qualifiers(self):
        valid = {"adapter": "normalized_pbp_table", "fields": pipeline.CMS_ADAPTERS["normalized_pbp_table"]}
        pipeline.validate_source_adapters({"cms_exports": [valid]})
        for fields in (valid["fields"] + ["carrier_corroboration"], valid["fields"][:-1]):
            with self.subTest(fields=fields), self.assertRaisesRegex(ValueError, "source-only"):
                pipeline.validate_source_adapters({"cms_exports": [{**valid, "fields": fields}]})


class ActualTwoCarrierReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="daylight-l03-pipeline-tests-")
        cls.output = Path(cls.temp.name) / "run"
        cls.config = pipeline.ROOT / pipeline.DEFAULT_CONFIG
        cls.summary = pipeline.build(pipeline.ROOT, cls.config, cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_actual_denominator_and_missing_states_preserved(self):
        s = self.summary
        self.assertEqual(s["global_inventory"]["required"], 392570)
        self.assertEqual(s["required_originals_preserved"], 10301)
        self.assertEqual(s["selected_inventory"]["2026:H5652:002:000"]["named_missing_predicates"], 16)
        self.assertEqual(s["selected_inventory"]["2026:H1036:217:000"]["named_missing_predicates"], 1)
        self.assertEqual(s["mechanical_outcomes"], {"insufficient_evidence": 3})
        self.assertEqual(s["whole_offering_pilots_completed"], 0)
        self.assertEqual(s["newly_accepted_entries"], 0)
        self.assertFalse(s["consumer_usable"])

    def test_carrier_input_contains_no_cms_expectations(self):
        rows = [r for _, r in pipeline.json_rows(self.output / "carrier-inventory-inputs.jsonl.gz")]
        self.assertEqual({r["offering_id"] for r in rows}, set(self.summary["selected_offerings"]))
        self.assertTrue(all(r["detail"]["source_basis"] == "carrier_only_blind_to_CMS_expected_amounts" for r in rows))
        rows = [r for _, r in pipeline.json_rows(self.output / "cms-source-inputs.jsonl.gz")]
        for row in rows:
            self.assertNotIn("carrier_corroboration", row["record"])
            self.assertNotIn("EOC_source_evidence", row["record"])
            self.assertNotIn("SB_candidate_page_evidence", row["record"])

    def test_second_carrier_has_complete_main_document_page_inputs(self):
        docs = json.loads((self.output / "document-bindings.json").read_text())
        pages = [r for _, r in pipeline.json_rows(self.output / "carrier-pages.jsonl.gz")]
        self.assertEqual(len(docs), 4)
        for doc in docs:
            found = {r["record"]["pdf_page"] for r in pages if r["offering_id"] == doc["offering_id"]
                     and r["record"]["document_sha256"] == doc["document_sha256"]}
            self.assertEqual(found, set(range(1, doc["expected_pages"] + 1)))

    def test_change_detection_and_engine_invalidation(self):
        config = json.loads(self.config.read_text())
        results = json.loads((self.output / "comparison-results.json").read_text())
        records = {r["id"]: r for side in ("cms", "carrier", "unresolved")
                   for _, r in pipeline.json_rows(self.output / f"{side}-inventory-inputs.jsonl.gz")}
        delta = pipeline.change_report(self.output, records, results, config["bindings"])
        self.assertEqual(delta["comparison_jobs_to_replay"], [])
        self.assertEqual(len(delta["unchanged_mechanical_jobs"]), 3)
        changed = copy.deepcopy(results)
        changed[0]["engine_signature"] = "new-engine"
        delta = pipeline.change_report(self.output, records, changed, config["bindings"])
        self.assertEqual(delta["comparison_jobs_to_replay"], [changed[0]["id"]])
        self.assertFalse(delta["cached_acceptance_reused"])
        changed = copy.deepcopy(results)
        changed[0]["source_preparation_signature"] = "changed-source"
        delta = pipeline.change_report(self.output, records, changed, config["bindings"])
        self.assertEqual(delta["comparison_jobs_to_replay"], [changed[0]["id"]])
        records.pop(next(iter(records)))
        with self.assertRaisesRegex(ValueError, "original scope/content"):
            pipeline.change_report(self.output, records, results, config["bindings"])

    def test_no_overwrite_and_tamper_detection(self):
        with self.assertRaisesRegex(ValueError, "never overwrite"):
            pipeline.build(pipeline.ROOT, self.config, self.output)
        with tempfile.TemporaryDirectory() as tmp:
            import shutil
            target = Path(tmp) / "copy"
            shutil.copytree(self.output, target)
            pipeline.verify_output(target)
            (target / "summary.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "output changed"):
                pipeline.verify_output(target)

    def test_deterministic_compressed_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a.gz", Path(tmp) / "b.gz"
            rows = [row for _, row in pipeline.json_rows(self.output / "original-work-queue.jsonl.gz")]
            pipeline.write_rows(a, rows)
            pipeline.write_rows(b, rows)
            self.assertEqual(a.read_bytes(), b.read_bytes())


if __name__ == "__main__":
    unittest.main()
