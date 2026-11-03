"""Read-only verifier guards and exact-window controls; no live DB connection."""
from copy import deepcopy
import ast
from datetime import datetime, timezone
import gzip
import importlib.util
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from psycopg.conninfo import conninfo_to_dict

TOOL = Path(__file__).resolve().parents[1] / "tools/verify_local_database.py"
SPEC = importlib.util.spec_from_file_location("verify_local_database", TOOL)
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


def unit(first=1, rows=10, table="source", layer="L01"):
    raw = {"binding": {"layer_id": layer, "source_path": "published/source.sqlite3",
                       "source_table": table, "source_sha256": "a" * 64,
                       "adapter_code_sha256": "b" * 64, "derivation_id": table + "-derivation",
                       "window_first_ordinal": first},
           "input_rows": rows, "projection_counts": {"published_example": rows},
           "stream_sha256": "c" * 64, "quarantined_rows": 0,
           "population_complete": True, "new_acceptance": False, "consumer_release_enabled": False}
    return verifier.normalize_unit(raw, {"path": f"receipt-{layer}-{table}-{first}.json", "sha256": "d" * 64}, layer)


def receipt(item, build_id="build"):
    return {"job_id": 1, "idempotency_key": verifier.digest(["persistent-local-full/1", build_id, item["slot"]]),
            "source_id": "sealed-local:" + item["binding"]["layer_id"], "state": "complete",
            "lease_until": None, "finished_at": datetime.now(timezone.utc), "fence": 3,
            "payload": verifier.controls(item, build_id), "controls": verifier.controls(item, build_id),
            "input_rows": item["rows"], "retained_rows": item["rows"], "quarantined_rows": 0,
            "stream_sha256": item["stream_sha256"], "derivation_id": item["binding"]["derivation_id"],
            "source_table": item["binding"]["source_table"], "last_ordinal": item["last"],
            "checkpoint_retained_rows": item["rows"], "checkpoint_fence": 3}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return verifier.sha256(path)


def fixture_contract(root):
    packet, summary_path = root / "packet", root / "summary.json"
    profile = {"customer_rows_included": False, "counts": {"question_definitions": 41,
               "field_definitions": 78, "representation_gaps": 14}}
    profile["content_sha256"] = verifier.digest(profile)
    code_hashes = {verifier.PROFILE: write_json(root / verifier.PROFILE, profile)}
    driver = root / verifier.BUILDER
    driver.parent.mkdir(parents=True, exist_ok=True)
    driver.write_text("original transport fixture\n")
    code_hashes[verifier.BUILDER] = verifier.sha256(driver)
    units, layers, pins, sources = [], [], {}, {}
    for n in range(1, 16):
        layer = f"L{n:02}"
        item = unit(rows=1, layer=layer)
        item["binding"]["source_path"] = f"published/{layer}.sqlite3"
        ref = {"path": item["sizing_receipt_path"], "sha256": ""}
        raw = {"binding": item["binding"], "input_rows": 1,
               "projection_counts": item["projection_counts"], "stream_sha256": item["stream_sha256"],
               "quarantined_rows": 0, "population_complete": True, "new_acceptance": False,
               "consumer_release_enabled": False}
        ref["sha256"] = write_json(root / ref["path"], raw)
        pins[ref["path"]] = ref["sha256"]
        layer_path = f"layers/{layer}.json"
        layer_hash = write_json(root / layer_path, {"layer_id": layer})
        pins[layer_path] = layer_hash
        layers.append({"layer_id": layer, "source_rows": 1, "projection_rows": 1,
                       "layer_receipt": layer_path, "layer_receipt_sha256": layer_hash, "unit_receipts": [ref]})
        sources[item["binding"]["source_path"]] = item["binding"]["source_sha256"]
    summary = {"layers_measured": 15, "source_rows": 15, "projection_rows": 15,
               "new_acceptance": False, "layers": layers}
    pins["summary.json"] = write_json(summary_path, summary)
    manifest = {"schema": "daylight-local-full-build/1", "reference_year": 2026,
                "database": verifier.DATABASE, "new_acceptance": False, "consumer_release_enabled": False,
                "expected_source_rows": 15, "expected_projection_rows": 15, "reserve_bytes": 7 * 1024**3,
                "cluster_system_identifier": "fixture", "executable_files": code_hashes,
                "selected_receipt_files": pins, "selected_source_files": sources}
    target = {"database": verifier.DATABASE, "database_oid": 1234, "build_id": verifier.digest(manifest),
              "cluster_system_identifier": "fixture", "marker": "daylight-local-full/1:" + verifier.digest(manifest),
              "created_at": "2026-10-30T00:00:00+00:00"}
    complete = {"schema": "daylight-local-full-load/1", "build_id": verifier.digest(manifest), "target": target,
                "layers_retained": 15, "source_rows": 15, "projection_rows": 15, "unit_receipts": 15,
                "all_layers_simultaneously_retained": True, "new_acceptance": False,
                "consumer_release_enabled": False, "cloud_deployed": False}
    for name, value in [("BUILD_MANIFEST", manifest), ("TARGET", target), ("LOAD_COMPLETE", complete)]:
        write_json(packet / (name + ".json"), value)
    return packet, summary_path


def fs_receipt(item, build_id, job_id, producer=None):
    value = {"build_id": build_id, "selected_slot": item["slot"], "binding": item["binding"],
             "source_rows": item["rows"], "projection_counts": item["projection_counts"],
             "quarantined_rows": item["quarantined_rows"], "first_ordinal": item["first"],
             "last_ordinal": item["last"], "stream_sha256": item["stream_sha256"],
             "database_verified": True, "new_acceptance": False, "job_id": job_id}
    if producer is not None:
        value["material_execution"] = producer
    return value


def fixture_recovery(root):
    old_packet, summary_path = fixture_contract(root)
    old = verifier.load_contract(root, old_packet, summary_path)
    old_target, old_manifest, old_id = old["target"], old["manifest"], old["build_id"]
    pins = {}
    for name in ("TARGET.json", "BUILD_MANIFEST.json"):
        path = old_packet / name
        pins[str(path.relative_to(root))] = verifier.sha256(path)
    producers = {}
    for job_id, item in enumerate(old["units"][:verifier.ADOPTED_UNITS], 1):
        path = old_packet / "units" / (item["slot"] + ".json")
        h = write_json(path, fs_receipt(item, old_id, job_id))
        relative = str(path.relative_to(root))
        pins[relative] = h
        producers[item["slot"]] = {"build_id": old_id, "job_id": job_id,
                                  "unit_receipt_path": relative, "unit_receipt_sha256": h}
    interrupted = old["units"][verifier.ADOPTED_UNITS]
    job = {"job_id": verifier.INTERRUPTED_JOB, "state": "running", "lease_expired": True,
           "payload": verifier.controls(interrupted, old_id)}
    cursors = [{"job_id": verifier.INTERRUPTED_JOB, "derivation_id": interrupted["binding"]["derivation_id"],
                "source_table": interrupted["binding"]["source_table"], "last_ordinal": verifier.INTERRUPTED_PREFIX_ROWS,
                "retained_rows": verifier.INTERRUPTED_PREFIX_ROWS, "fence": 1}]
    dump = root / "state/checkpoint.dump.gz"
    dump.parent.mkdir()
    dump.write_bytes(gzip.compress(b"PGDMP synthetic fixture only"))
    toc = old_packet / "LOGICAL_CHECKPOINT_TOC.txt"
    toc.write_text("synthetic public TOC\n")
    pins[str(toc.relative_to(root))] = verifier.sha256(toc)
    checkpoint = {"schema": "daylight-interrupted-readonly-logical-checkpoint/1", "passed": True,
                  "target": old_target, "ownership": {k: old_target[k] for k in
                    ("database", "database_oid", "marker", "cluster_system_identifier")},
                  "predecessor_manifest_sha256": pins[str((old_packet / "BUILD_MANIFEST.json").relative_to(root))],
                  "counts": {"jobs": verifier.HISTORICAL_JOBS, "complete_jobs": verifier.ADOPTED_UNITS,
                             "receipts": verifier.ADOPTED_UNITS, "acceptance_bindings": 0, "releases": 0},
                  "interrupted_job": job, "interrupted_checkpoints": cursors,
                  "path": str(dump.relative_to(root)), "bytes": dump.stat().st_size, "sha256": verifier.sha256(dump),
                  "toc_sha256": verifier.sha256(toc), "consistent_exported_readonly_snapshot": True,
                  "full_archive_decoded_without_execution": True, "outer_gzip_crc_verified": True,
                  "service_stop_or_restart": False, "database_modified": False, "database_renamed": False,
                  "clean_restore_executed": False, "physical_checkpoint": False, "off_machine_copy_created": False,
                  "full_load_complete": False, "new_acceptance": False}
    checkpoint_path = old_packet / "LOGICAL_CHECKPOINT.json"
    pins[str(checkpoint_path.relative_to(root))] = write_json(checkpoint_path, checkpoint)
    durability = {"passed": True, "logical_checkpoint_sha256": verifier.sha256(checkpoint_path),
                  "dump_sha256": checkpoint["sha256"]}
    durability_path = old_packet / "CHECKPOINT_DURABILITY.json"
    pins[str(durability_path.relative_to(root))] = write_json(durability_path, durability)
    driver = root / verifier.BUILDER
    driver.write_text("new driver-only transport fixture\n")
    manifest = deepcopy(old_manifest)
    manifest["schema"] = "daylight-local-full-build/2"
    manifest["executable_files"][verifier.BUILDER] = verifier.sha256(driver)
    manifest["predecessor"] = {"packet": str(old_packet.relative_to(root)), "build_id": old_id,
        "target_sha256": pins[str((old_packet / "TARGET.json").relative_to(root))],
        "manifest_sha256": pins[str((old_packet / "BUILD_MANIFEST.json").relative_to(root))],
        "logical_checkpoint_path": str(checkpoint_path.relative_to(root)),
        "logical_checkpoint_sha256": verifier.sha256(checkpoint_path), "ownership": old_target,
        "historical_jobs": verifier.HISTORICAL_JOBS, "historical_receipts": verifier.ADOPTED_UNITS,
        "interrupted_job": job, "interrupted_checkpoints": cursors,
        "interrupted_layer_id": interrupted["binding"]["layer_id"],
        "preserved_dump": {k: checkpoint[k] for k in ("path", "sha256", "bytes")},
        "transport_change": {"path": verifier.BUILDER, "before_sha256": old_manifest["executable_files"][verifier.BUILDER],
                             "after_sha256": verifier.sha256(driver)},
        "source_adapter_derivations_changed": False, "new_acceptance": False}
    manifest["recovery_receipt_files"], manifest["predecessor_completed_units"] = pins, producers
    packet = root / "recovery-packet"
    target = dict(old_target, build_id=verifier.digest(manifest), creation_build_id=old_id,
                  predecessor_target_sha256=manifest["predecessor"]["target_sha256"],
                  execution_started_at="2026-10-30T01:00:00+00:00")
    complete = dict(old["complete"], build_id=target["build_id"], target=target,
                    predecessor_material_units=verifier.ADOPTED_UNITS, historical_jobs_retained=verifier.HISTORICAL_JOBS,
                    historical_receipts_retained=verifier.ADOPTED_UNITS, physical_evidence_counted_once=True,
                    predecessor_source_digests_replayed=True)
    for name, value in [("BUILD_MANIFEST", manifest), ("TARGET", target), ("LOAD_COMPLETE", complete)]:
        write_json(packet / (name + ".json"), value)
    return packet, summary_path


def rebind_execution_manifest(packet, manifest):
    target = json.loads((packet / "TARGET.json").read_text())
    target["build_id"] = verifier.digest(manifest)
    complete = json.loads((packet / "LOAD_COMPLETE.json").read_text())
    complete.update(build_id=target["build_id"], target=target)
    for name, value in [("BUILD_MANIFEST", manifest), ("TARGET", target), ("LOAD_COMPLETE", complete)]:
        write_json(packet / (name + ".json"), value)


class LocalConnectionGuards(unittest.TestCase):
    def test_exact_private_socket_target_and_read_only_startup(self):
        root = Path("/fixture/daylight")
        socket = str(root / "infrastructure/daylight-data/.state/socket")
        for db in ("daylight_data_test", verifier.DATABASE):
            info = conninfo_to_dict(verifier.target_dsn(
                f"host={socket} port=55485 dbname={db} options='-c default_transaction_read_only=off'", root))
            self.assertEqual(info["dbname"], verifier.DATABASE)
            self.assertIn("default_transaction_read_only=on", info["options"])
            self.assertNotIn("read_only=off", info["options"])

    def test_tcp_alias_service_hostaddr_ambient_and_other_database_are_rejected(self):
        root = Path("/fixture/daylight")
        socket = str(root / "infrastructure/daylight-data/.state/socket")
        cases = ["dbname=daylight_data_test", "host=localhost port=55485 dbname=daylight_data_test",
                 f"host={socket} hostaddr=127.0.0.1 port=55485 dbname=daylight_data_test",
                 f"host={socket} port=5432 dbname=daylight_data_test",
                 f"host={socket} port=55485 dbname=customer_profiles",
                 f"host={socket} port=55485 dbname=daylight_research_2026_r1",
                 f"host={socket},localhost port=55485 dbname=daylight_data_test",
                 f"host={socket} port=55485 dbname=daylight_data_test service=other"]
        for dsn in cases:
            with self.subTest(dsn=dsn), self.assertRaises(ValueError):
                verifier.target_dsn(dsn, root)


class ExactWindowControls(unittest.TestCase):
    def test_second_window_checkpoint_counts_its_window_not_absolute_ordinal(self):
        item = unit(first=250001, rows=100)
        row = receipt(item)
        self.assertTrue(verifier.receipt_matches(row, item, "build"))
        row["checkpoint_retained_rows"] = row["last_ordinal"]
        self.assertFalse(verifier.receipt_matches(row, item, "build"))

    def test_stale_fence_wrong_receipt_or_unfinished_job_cannot_pass(self):
        item = unit()
        for field, value in [("checkpoint_fence", 2), ("state", "running"), ("stream_sha256", "wrong"),
                             ("source_table", "another_table"), ("retained_rows", 9),
                             ("finished_at", None), ("controls", {"new_acceptance": True})]:
            row = receipt(item)
            row[field] = value
            with self.subTest(field=field):
                self.assertFalse(verifier.receipt_matches(row, item, "build"))

    def test_windows_must_be_contiguous_with_one_source_and_derivation(self):
        first, second = unit(rows=10), unit(first=11, rows=5)
        verifier.check_windows([first, second])
        for broken in (unit(first=10), unit(first=12)):
            with self.assertRaises(ValueError):
                verifier.check_windows([first, broken])
        wrong = deepcopy(second)
        wrong["binding"]["derivation_id"] = "changed-parser"
        with self.assertRaises(ValueError):
            verifier.check_windows([first, wrong])

    def test_same_table_name_in_distinct_source_files_is_not_one_population(self):
        first, second = unit(rows=10), unit(rows=5)
        second["binding"]["source_path"] = "another/source.sqlite3"
        second["slot"] = "another-slot"
        self.assertEqual(len(verifier.check_windows([first, second])), 2)


class FrozenControlFiles(unittest.TestCase):
    def test_complete_control_validation_without_reading_original_sources(self):
        with tempfile.TemporaryDirectory() as temporary, patch.multiple(verifier, RAW_ROWS=15, PROJECTION_ROWS=15, UNIT_COUNT=15):
            root = Path(temporary)
            packet, summary = fixture_contract(root)
            # These selected artifact paths deliberately do not exist. The
            # verifier reconciles their frozen identities, never replays bytes.
            result = verifier.load_contract(root, packet, summary)
            self.assertEqual(len(result["units"]), 15)
            self.assertFalse((root / "published").exists())

    def test_missing_load_complete_never_connects(self):
        with tempfile.TemporaryDirectory() as temporary, patch.multiple(verifier, RAW_ROWS=15, PROJECTION_ROWS=15, UNIT_COUNT=15):
            root = Path(temporary)
            packet, summary = fixture_contract(root)
            (packet / "LOAD_COMPLETE.json").unlink()
            with patch.object(verifier.psycopg, "connect") as connect, self.assertRaises(FileNotFoundError):
                verifier.verify(root, packet, summary, "never-used")
            connect.assert_not_called()

    def test_changed_receipt_bytes_are_rejected_before_database_use(self):
        with tempfile.TemporaryDirectory() as temporary, patch.multiple(verifier, RAW_ROWS=15, PROJECTION_ROWS=15, UNIT_COUNT=15):
            root = Path(temporary)
            packet, summary = fixture_contract(root)
            (root / "receipt-L01-source-1.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "changed"):
                verifier.load_contract(root, packet, summary)

    def test_different_target_ownership_or_incomplete_scope_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary, patch.multiple(verifier, RAW_ROWS=15, PROJECTION_ROWS=15, UNIT_COUNT=15):
            root = Path(temporary)
            packet, summary = fixture_contract(root)
            target = json.loads((packet / "TARGET.json").read_text())
            target["marker"] = "someone-elses-database"
            write_json(packet / "TARGET.json", target)
            with self.assertRaisesRegex(ValueError, "ownership"):
                verifier.load_contract(root, packet, summary)

    def test_existing_report_and_source_receipt_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "TARGET.json"
            destination.write_text("protected")
            with self.assertRaises(ValueError):
                verifier.write_report(destination, {"passed": False})
            self.assertEqual(destination.read_text(), "protected")


class RecoveryExecutionProvenance(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        constants = patch.multiple(verifier, RAW_ROWS=15, PROJECTION_ROWS=15, UNIT_COUNT=15,
                                   ADOPTED_UNITS=2, HISTORICAL_JOBS=3, INTERRUPTED_JOB=3, INTERRUPTED_PREFIX_ROWS=1)
        constants.start()
        self.addCleanup(constants.stop)
        self.packet, self.summary = fixture_recovery(self.root)

    def test_additive_execution_preserves_creation_marker_and_exact_producers(self):
        result = verifier.load_contract(self.root, self.packet, self.summary)
        self.assertEqual(result["target"]["marker"], "daylight-local-full/1:" + result["target"]["creation_build_id"])
        self.assertNotEqual(result["target"]["creation_build_id"], result["build_id"])
        self.assertEqual(len(result["recovery"]["producers"]), 2)
        self.assertEqual(result["target"]["database_oid"], result["recovery"]["target"]["database_oid"])

    def test_adopted_database_controls_must_name_original_material_execution(self):
        item = unit()
        producer = {"build_id": "prior", "job_id": 7, "unit_receipt_path": "prior-unit.json", "unit_receipt_sha256": "e" * 64}
        row = receipt(item)
        row["payload"] = row["controls"] = verifier.controls(item, "build", producer)
        self.assertTrue(verifier.receipt_matches(row, item, "build", producer))
        self.assertFalse(verifier.receipt_matches(row, item, "build"))
        row["controls"] = verifier.controls(item, "build")
        self.assertFalse(verifier.receipt_matches(row, item, "build", producer))
        fresh = fs_receipt(item, "build", 8, producer)
        self.assertTrue(verifier.filesystem_unit_matches(fresh, item, "build", 8, producer))
        fresh.pop("material_execution")
        self.assertFalse(verifier.filesystem_unit_matches(fresh, item, "build", 8, producer))

    def test_missing_or_duplicate_producer_cannot_be_adopted(self):
        original = json.loads((self.packet / "BUILD_MANIFEST.json").read_text())
        for mutation in ("missing", "duplicate_job", "interrupted_job"):
            changed = deepcopy(original)
            producers = changed["predecessor_completed_units"]
            slots = list(producers)
            if mutation == "missing":
                producers.pop(slots[0])
            elif mutation == "duplicate_job":
                producers[slots[1]]["job_id"] = producers[slots[0]]["job_id"]
            else:
                producers[slots[0]]["job_id"] = verifier.INTERRUPTED_JOB
            rebind_execution_manifest(self.packet, changed)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                verifier.load_contract(self.root, self.packet, self.summary)

    def test_changed_checkpoint_archive_bytes_fail_even_with_unchanged_receipt(self):
        manifest = json.loads((self.packet / "BUILD_MANIFEST.json").read_text())
        dump = self.root / manifest["predecessor"]["preserved_dump"]["path"]
        dump.write_bytes(b"different archive bytes")
        with self.assertRaisesRegex(ValueError, "archive bytes"):
            verifier.load_contract(self.root, self.packet, self.summary)

    def test_source_derivation_change_and_missing_durability_pin_are_rejected(self):
        original = json.loads((self.packet / "BUILD_MANIFEST.json").read_text())
        for mutation in ("derivation", "durability_pin"):
            changed = deepcopy(original)
            if mutation == "derivation":
                changed["predecessor"]["source_adapter_derivations_changed"] = True
            else:
                changed["recovery_receipt_files"].pop("packet/CHECKPOINT_DURABILITY.json")
            rebind_execution_manifest(self.packet, changed)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                verifier.load_contract(self.root, self.packet, self.summary)

    def test_new_completion_cannot_claim_unreplayed_or_double_counted_material(self):
        complete = json.loads((self.packet / "LOAD_COMPLETE.json").read_text())
        for field in ("physical_evidence_counted_once", "predecessor_source_digests_replayed"):
            changed = dict(complete, **{field: False})
            write_json(self.packet / "LOAD_COMPLETE.json", changed)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "complete persistent"):
                verifier.load_contract(self.root, self.packet, self.summary)

    def test_database_receipts_require_current_job_and_receipt_build_filters(self):
        self.assertIn("j.payload->>'build_id'=%s AND r.controls->>'build_id'=%s", verifier.RECEIPTS_SQL)
        self.assertIn("WHERE j.payload->>'build_id'=%s", verifier.EXECUTION_COUNTS_SQL)
        self.assertIn("wrong_receipt_builds", verifier.EXECUTION_COUNTS_SQL)


class QueryContract(unittest.TestCase):
    def test_real_frozen_collier_projection_keeps_72_native_ids_in_fields_id(self):
        from daylight_data.adapters import l02
        root = TOOL.parents[3]
        source = root / l02.BASE / "12021/offerings.json"
        raw_rows = json.loads(source.read_text())
        projected = [next(l02.project_record(SimpleNamespace(raw=row, source_table="collier_offerings",
                     source_row_key=row["id"], record_id="published-fixture-" + str(i))))
                     for i, row in enumerate(raw_rows)]
        self.assertEqual(len(raw_rows), 72)
        self.assertEqual(len({p.fields["id"] for p in projected}), 72)
        self.assertEqual({p.fields["id"] for p in projected}, {row["id"] for row in raw_rows})
        self.assertTrue(all("offering_id" not in row and "offering_id" not in p.fields
                            for row, p in zip(raw_rows, projected)))
        for p in projected:
            self.assertRegex(p.fields["id"], r"^2026:[A-Z][0-9]{4}:[0-9]{3}:[0-9]{3}$")
        self.assertIn("o.fields->>'id' AS offering_id", verifier.COLLIER_SQL)
        self.assertIn("r.raw_payload->>'id' AS native_id", verifier.COLLIER_SQL)
        self.assertIn("source_projection_id_mismatches", verifier.COLLIER_SQL)
        self.assertIn("duplicate_or_null_ids", verifier.COLLIER_SQL)
        self.assertIn("source_row_ordinal)", verifier.COLLIER_SQL)

    def test_storage_measurement_is_before_reader_role_and_records_actual_role(self):
        tree = ast.parse(inspect.getsource(verifier.verify))
        size_calls = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Call)
                      and isinstance(n.func, ast.Name) and n.func.id == "measure_owned_database_size"]
        reader_switches = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Call)
                           and isinstance(n.func, ast.Attribute) and n.func.attr == "execute"
                           and n.args and isinstance(n.args[0], ast.Constant)
                           and n.args[0].value == "SET LOCAL ROLE daylight_research_reader"]
        self.assertEqual(len(size_calls), 1)
        self.assertEqual(len(reader_switches), 1)
        self.assertLess(size_calls[0], reader_switches[0])
        class Recorder:
            def query(self, name, statement):
                self.statement = statement
                return [{"bytes": 58013032975, "effective_role": "local_owner", "transaction_read_only": "on"}]
            def proof(self, name, passed, *args):
                self.passed = passed
        measurement = Recorder()
        rows = verifier.measure_owned_database_size(measurement, {"effective_role": "local_owner"})
        self.assertTrue(measurement.passed)
        self.assertEqual(rows[0]["effective_role"], "local_owner")
        self.assertIn("current_user AS effective_role", measurement.statement)
        verifier.measure_owned_database_size(measurement, {"effective_role": "daylight_research_reader"})
        self.assertFalse(measurement.passed)

    def test_hospital_source_unknown_requires_material_state_and_both_holds(self):
        row = {"source_state": "unknown_no_exact_campus_plan_evidence",
               "value_state": "unknown_no_exact_campus_plan_evidence",
               "personal_network_status_determined": False,
               "source_use_state": "existing_source_policy_applies",
               "output_acceptance_state": "research_only"}
        self.assertTrue(verifier.unknown_inspection_matches([row]))
        for field in ("value_state", "source_use_state", "output_acceptance_state"):
            changed = dict(row)
            changed.pop(field)
            with self.subTest(missing=field):
                self.assertFalse(verifier.unknown_inspection_matches([changed]))
        for field, value in [("value_state", "known_in_network"), ("source_use_state", "redisplay_allowed"),
                             ("output_acceptance_state", "accepted"), ("personal_network_status_determined", True)]:
            changed = dict(row, **{field: value})
            with self.subTest(changed=field):
                self.assertFalse(verifier.unknown_inspection_matches([changed]))

    def test_bounded_context_inspection_rejects_changed_context_with_holds_intact(self):
        rows = [{"semantic_review_state": "not_newly_reviewed", "output_acceptance_state": "research_only",
                 "native_context": '{"limit": 12, "period": "year"}',
                 "projected_context": '{"limit": 12, "period": "year"}'} for _ in range(5)]
        self.assertTrue(verifier.context_inspection_matches(rows))
        changed = deepcopy(rows)
        changed[0]["projected_context"] = '{"limit": 24, "period": "year"}'
        self.assertFalse(verifier.context_inspection_matches(changed))
        # Even equivalent JSON text must retain its exact native characters.
        changed[0]["projected_context"] = '{"limit":12,"period":"year"}'
        self.assertFalse(verifier.context_inspection_matches(changed))
        changed[0]["native_context"], changed[0]["projected_context"] = {"limit": 1}, {"limit": True}
        self.assertFalse(verifier.context_inspection_matches(changed))
        self.assertEqual(changed[0]["semantic_review_state"], "not_newly_reviewed")
        self.assertEqual(changed[0]["output_acceptance_state"], "research_only")
        self.assertIn("r.raw_payload->'context' AS native_context", verifier.CONDITIONS_SQL)
        self.assertIn("p.fields->'source_columns'->'context' AS projected_context", verifier.CONDITIONS_SQL)

    def test_measurement_rejects_non_select_and_stacked_statements(self):
        measurement = verifier.Measurements(None)
        for statement in ["DELETE FROM anything", "SELECT 1; SELECT 2", "ANALYZE dl_evidence.observation"]:
            with self.subTest(statement=statement), self.assertRaises(ValueError):
                measurement.query("invalid", statement)

    def test_canonical_grain_and_cross_table_snapshot_are_explicit(self):
        self.assertIn("count(DISTINCT c.canonical_id)", verifier.R9_SQL)
        self.assertIn("c.snapshot_id=u.snapshot_id", verifier.R9_SQL)
        self.assertIn("u FULL JOIN c", verifier.R9_SQL)
        self.assertNotIn("c.derivation_id=u.derivation_id", verifier.R9_SQL)
        self.assertIn("source_row_ordinal BETWEEN %s AND %s", verifier.RAW_WINDOW_SQL)
        self.assertIn("source_row_ordinal BETWEEN %s AND %s", verifier.PROJECTION_WINDOW_SQL)

    def test_public_lookup_ids_are_bound_parameters_not_personal_input(self):
        self.assertIn("o.offering_id=%s AND o.fields->>'npi'=%s", verifier.PHARMACY_SQL)
        self.assertIn("o.fields->'npi' ? %s", verifier.PROVIDER_SQL)
        self.assertIn("r.raw_sha256", verifier.PROVIDER_SQL)
        self.assertIn("r.raw_sha256", verifier.PHARMACY_SQL)


if __name__ == "__main__":
    unittest.main()
