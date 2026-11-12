"""Independent regressions for verified-byte execution and strict JSON input."""

import importlib.util
from pathlib import Path
import py_compile
import shutil
import struct
import tempfile
import unittest
from unittest.mock import patch

from daylight_data.comparison_pipeline.common import safe_json
from daylight_data.comparison_pipeline.engine import PINNED, R9, load_engine


ROOT = Path(__file__).resolve().parents[3]


class VerifiedRuleExecutionTests(unittest.TestCase):
    def test_timestamp_valid_untrusted_pyc_cannot_replace_verified_rule_source(self):
        with tempfile.TemporaryDirectory(prefix="daylight-pinned-byte-review-") as temporary:
            repository = Path(temporary)
            for relative in PINNED:
                target = repository / R9 / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / R9 / relative, target)
            source = repository / R9 / "code/l03_r9_comparison.py"
            fake = repository / "untrusted.py"
            fake.write_text(
                "def compare(*args, **kwargs):\n"
                " return {'outcome':'exact_agreement','accepted_for_reference':False,'differences':[]}\n"
            )
            cached = Path(importlib.util.cache_from_source(str(source)))
            cached.parent.mkdir(exist_ok=True)
            py_compile.compile(str(fake), cfile=str(cached), doraise=True)
            payload = bytearray(cached.read_bytes())
            # A timestamp cache is accepted by SourceFileLoader when mtime and
            # size agree, regardless of the checked SHA256 of the .py source.
            payload[4:8] = struct.pack("<I", 0)
            payload[8:12] = struct.pack("<I", int(source.stat().st_mtime))
            payload[12:16] = struct.pack("<I", source.stat().st_size)
            cached.write_bytes(payload)
            result = load_engine(repository).compare(None, None)
            self.assertEqual(result["outcome"], "insufficient_evidence")
            self.assertFalse(result["accepted_for_reference"])

    def test_changed_pinned_source_fails_instead_of_following_cached_rules(self):
        with tempfile.TemporaryDirectory(prefix="daylight-rule-drift-review-") as temporary:
            repository = Path(temporary)
            for relative in PINNED:
                target = repository / R9 / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / R9 / relative, target)
            source = repository / R9 / "code/l03_r9_comparison.py"
            source.write_bytes(source.read_bytes() + b"\n# changed rule bytes\n")
            with self.assertRaisesRegex(ValueError, "Sealed r9 rule changed"):
                load_engine(repository)

    def test_json_numeric_overflow_and_nonfinite_literals_fail_at_parse_boundary(self):
        for text in ["1e9999", "-1e9999", '{"amount": 1e9999}', "NaN", "Infinity", "-Infinity"]:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    safe_json(text)
        self.assertEqual(safe_json('{"literal":"1e9999","finite":1.25}'),
                         {"literal": "1e9999", "finite": 1.25})

    def test_duplicate_json_keys_cannot_hide_source_or_context_changes(self):
        with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
            safe_json('{"source_sha256":"old","source_sha256":"new"}')


class RunnerParserCacheTests(unittest.TestCase):
    def test_same_bytes_with_different_parse_formats_cannot_share_parsed_records(self):
        from daylight_data.comparison_pipeline import runner
        from daylight_data.comparison_pipeline.common import file_hash

        with tempfile.TemporaryDirectory(prefix="daylight-parser-format-review-") as temporary:
            repository = Path(temporary) / "repository"
            repository.mkdir()
            workspace = Path(temporary) / "workspace"
            for filename in ("records.json", "records.jsonl"):
                (repository / filename).write_text("[]")
            offering = "2026:H5652:002:000"
            config = {"schema": runner.MANIFEST_SCHEMA, "offerings": [offering], "inputs": [
                {"path": "records.json", "sha256": file_hash(repository / "records.json"),
                 "offering_id": offering}], "sources": []}
            # Isolate the parser/cache transaction boundary; inventory and rule
            # source verification have separate integration/regression tests.
            with patch.object(runner, "ensure_inventory", return_value={"record_count": 1}), \
                    patch.object(runner, "originals_for_offering", return_value=[
                        {"id": "original", "offering_id": offering, "kind": "claim"}]), \
                    patch.object(runner, "load_engine"), \
                    patch.object(runner, "rule_fingerprint", return_value="fixed-rules"):
                runner.run_batch(repository, workspace, config)
                second = {**config, "inputs": [{**config["inputs"][0], "path": "records.jsonl"}]}
                with self.assertRaisesRegex(ValueError, "non-object record"):
                    runner.run_batch(repository, workspace, second)

    def test_failure_after_publish_insert_rolls_back_run_queue_and_task_index(self):
        from daylight_data.comparison_pipeline import runner
        from daylight_data.comparison_pipeline.common import file_hash
        from daylight_data.comparison_pipeline.store import Store

        with tempfile.TemporaryDirectory(prefix="daylight-publish-rollback-review-") as temporary:
            repository = Path(temporary) / "repository"
            repository.mkdir()
            workspace = Path(temporary) / "workspace"
            (repository / "records.json").write_text("[]")
            offering = "2026:H5652:002:000"
            config = {"schema": runner.MANIFEST_SCHEMA, "offerings": [offering], "inputs": [
                {"path": "records.json", "sha256": file_hash(repository / "records.json"),
                 "offering_id": offering}], "sources": []}
            with patch.object(runner, "ensure_inventory", return_value={"record_count": 1}), \
                    patch.object(runner, "originals_for_offering", return_value=[
                        {"id": "original", "offering_id": offering, "kind": "claim"}]), \
                    patch.object(runner, "load_engine"), \
                    patch.object(runner, "rule_fingerprint", return_value="fixed-rules"):
                completed = runner.run_batch(repository, workspace, config)
                publish = Store.publish

                def fail_after_insert(store, summary, results):
                    publish(store, summary, results)
                    raise RuntimeError("simulated publication failure")

                with patch.object(Store, "publish", fail_after_insert):
                    with self.assertRaisesRegex(RuntimeError, "simulated publication failure"):
                        runner.run_batch(repository, workspace, config)
                store = Store(workspace / "comparisons.sqlite3")
                try:
                    self.assertEqual(store.latest_run(), completed["run_id"])
                    self.assertEqual(store.connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0], 1)
                    self.assertEqual(store.connection.execute(
                        "SELECT COUNT(*) FROM cache WHERE namespace='queues'").fetchone()[0], 1)
                finally:
                    store.close()

    def test_exact_mapping_replay_resolves_only_earlier_mechanical_annotations(self):
        from daylight_data.comparison_pipeline import runner
        from daylight_data.comparison_pipeline.common import canonical, digest, file_hash
        from daylight_data.comparison_pipeline.store import Store

        # Reuse the adapter suite's deliberately synthetic, fully qualified r9
        # fixture. This is no assertion about an actual published benefit.
        fixture_path = Path(__file__).with_name("test_pipeline_adapters.py")
        fixture_module = importlib.util.module_from_spec(
            importlib.util.spec_from_file_location("_mapping_review_fixtures", fixture_path))
        exec(compile(fixture_path.read_bytes(), str(fixture_path), "exec"), fixture_module.__dict__)
        component = fixture_module.record()
        offering = fixture_module.OFFERING
        with tempfile.TemporaryDirectory(prefix="daylight-mapping-replay-review-") as temporary:
            repository = Path(temporary) / "repository"
            repository.mkdir()
            workspace = Path(temporary) / "workspace"
            sources = []
            for side in ("cms", "carrier"):
                path = repository / f"{side}-source.txt"
                path.write_text(f"Synthetic {side} evidence for a mechanical mapping test only.")
                component[side]["evidence"][0]["source_sha256"] = file_hash(path)
                sources.append({"path": path.name, "sha256": file_hash(path), "role": side})
            component["carrier"]["conditions"]["qualification"]["assertion"] += " Explicit mapped fixture wording."
            component["outcome"] = "agreement_through_reviewed_mapping"
            receipt = repository / "mapping-receipt.json"
            receipt.write_bytes(canonical({"fixture": "exact synthetic pair mapping", "accepted_for_reference": False}))
            sources.append({"path": receipt.name, "sha256": file_hash(receipt), "role": "mapping_receipt"})
            registry = {"fixture-mapping": {
                "cms_sha256": digest(component["cms"]), "carrier_sha256": digest(component["carrier"]),
                "review_decision": "accepted_mapping", "reviewer": "synthetic-fixture-reviewer",
                "review_receipt_sha256": file_hash(receipt),
                "evidence": {"formal_record_id": component["id"], "formal_record_sha256": digest(component)},
            }}
            mapping_path = repository / "mapping-registry.json"
            mapping_path.write_bytes(canonical(registry))
            input_path = repository / "records.json"
            input_path.write_bytes(canonical([component]))
            config = {"schema": runner.MANIFEST_SCHEMA, "offerings": [offering], "inputs": [
                {"path": input_path.name, "sha256": file_hash(input_path), "offering_id": offering}],
                "sources": sources, "mapping_registries": [
                    {"path": mapping_path.name, "sha256": file_hash(mapping_path)}]}
            with patch.object(runner, "ensure_inventory", return_value={"record_count": 1}), \
                    patch.object(runner, "originals_for_offering", return_value=[{
                        "id": component["inventory_root_ids"][0], "offering_id": offering,
                        "kind": "claim", "original_sha256": "e" * 64}]), \
                    patch.object(runner, "load_engine", return_value=load_engine(ROOT)), \
                    patch.object(runner, "rule_fingerprint", return_value="fixed-rules"):
                runner.run_batch(repository, workspace, config)
            store = Store(workspace / "comparisons.sqlite3")
            try:
                task = store.results()[0]
                self.assertEqual(task["mechanical_results"][0]["outcome"], "agreement_through_reviewed_mapping")
                self.assertEqual(task["status"], "awaiting_source_review")
                self.assertEqual(task["review_state"], "unreviewed")
                prior_codes = {hold["code"] for hold in task["adapter_holds"]}
                self.assertIn("comparison_not_complete", prior_codes)
                self.assertIn("stored_outcome_mismatch", prior_codes)
                self.assertFalse(task["holds"])
                self.assertFalse(task["accepted_for_reference"])
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
