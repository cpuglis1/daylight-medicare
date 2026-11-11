"""Verify the exact owned fifteen-layer local research database using SELECT only.

Requires LOAD_COMPLETE.json before connecting. No sources are replayed, no archive
is copied, and no database object, acceptance, release or application is changed.
Run with DAYLIGHT_DATA_DATABASE_URL pointing at the private project Unix socket.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row


DATABASE = "daylight_research_2026_r2"
RAW_ROWS = 17_767_179
PROJECTION_ROWS = 17_823_148
UNIT_COUNT = 363
ADAPTER_VERSION = "d85-adapters-r1"
R9 = "docs/data/l03-ma-benefits-2026-10-25/semantic-inventory-r9/inventory.sqlite3.gz"
SUMMARY = "docs/data/infrastructure-execution-2026-10-30-local-sizing/SUMMARY.json"
PACKET = "docs/data/infrastructure-execution-2026-10-30-local-full-db/build-r3"
PROFILE = "infrastructure/daylight-data/config/profile-contract.2026.json"
ADOPTED_UNITS = 122
HISTORICAL_JOBS = 123
INTERRUPTED_JOB = 123
INTERRUPTED_PREFIX_ROWS = 1000
BUILDER = "infrastructure/daylight-data/tools/build_local_database.py"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def sha256(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def relative_file(repository, relative):
    repository = repository.resolve()
    path = repository / relative
    if path.is_symlink() or not path.resolve().is_relative_to(repository) or not path.is_file():
        raise ValueError("A pinned file is absent, a symlink or outside the repository")
    return path


def read_json(path):
    if path.stat().st_size > 32 * 1024**2:
        raise ValueError("Control JSON exceeds the explicit 32 MiB bound")
    return json.loads(path.read_text())


def target_dsn(dsn, repository):
    """Never follow ambient PGHOST, host lists, TCP aliases, services or hostaddr."""
    info = conninfo_to_dict(dsn)
    expected = str((repository / "infrastructure/daylight-data/.state/socket").resolve())
    if (info.get("host") != expected or info.get("hostaddr") or info.get("service")
            or info.get("port") != "55485"
            or info.get("dbname") not in {"daylight_data_test", DATABASE}):
        raise ValueError("An explicit exact project Unix socket, port and approved database are required")
    # These startup settings protect even the first catalog statement. User
    # options cannot override the verifier's transaction/read-only settings.
    return make_conninfo(dsn, dbname=DATABASE, connect_timeout="5",
                         options="-c default_transaction_read_only=on -c statement_timeout=120000 "
                                 "-c lock_timeout=3000 -c idle_in_transaction_session_timeout=180000")


def normalize_unit(unit, reference, layer_id):
    binding = unit["binding"]
    first, rows = binding.get("window_first_ordinal", 1), unit["input_rows"]
    if (unit.get("population_complete") is not True or binding["layer_id"] != layer_id
            or type(first) is not int or type(rows) is not int or rows <= 0 or first <= 0
            or unit.get("new_acceptance") is not False
            or unit.get("consumer_release_enabled") is not False):
        raise ValueError("An exact complete research-only sizing population is required")
    item = {"binding": binding, "first": first, "last": first + rows - 1,
            "rows": rows, "projection_counts": unit["projection_counts"],
            "stream_sha256": unit["stream_sha256"], "quarantined_rows": unit["quarantined_rows"],
            "sizing_receipt_path": reference["path"], "sizing_receipt_sha256": reference["sha256"]}
    if any(type(n) is not int or n < 0 for n in item["projection_counts"].values()):
        raise ValueError("Projection controls must be exact nonnegative integers")
    item["slot"] = digest(item)
    return item


def check_windows(units):
    groups = defaultdict(list)
    for item in units:
        b = item["binding"]
        groups[(b["layer_id"], b["source_path"], b["source_table"])].append(item)
    for group in groups.values():
        cursor = 0
        identities = set()
        for item in group:
            if item["first"] != cursor + 1:
                raise ValueError("Selected windows have a gap, overlap or wrong order")
            cursor = item["last"]
            b = item["binding"]
            identities.add((b["source_sha256"], b["derivation_id"], b["adapter_code_sha256"]))
        if len(identities) != 1:
            raise ValueError("A selected table changes derivation or source within its windows")
    if len({item["slot"] for item in units}) != len(units):
        raise ValueError("Repeated selected window")
    return groups


def validate_recovery(repository, manifest, target, units):
    """Bind an additive execution to its unchanged creation identity and producers."""
    if manifest["schema"] == "daylight-local-full-build/1":
        if (target.get("marker") != "daylight-local-full/1:" + target["build_id"]
                or manifest.get("predecessor") or manifest.get("predecessor_completed_units")):
            raise ValueError("Legacy ownership creation marker or predecessor scope differs")
        return None
    predecessor = manifest["predecessor"]
    if set(predecessor) != {"packet", "build_id", "target_sha256", "manifest_sha256",
                            "logical_checkpoint_path", "logical_checkpoint_sha256", "ownership",
                            "historical_jobs", "historical_receipts", "interrupted_job", "interrupted_layer_id",
                            "interrupted_checkpoints", "preserved_dump", "transport_change",
                            "source_adapter_derivations_changed", "new_acceptance"}:
        raise ValueError("Exact predecessor binding fields are required")
    pins = manifest["recovery_receipt_files"]
    old_target_path = str(Path(predecessor["packet"]) / "TARGET.json")
    old_manifest_path = str(Path(predecessor["packet"]) / "BUILD_MANIFEST.json")
    checkpoint_path = predecessor["logical_checkpoint_path"]
    toc_path = str(Path(checkpoint_path).with_name("LOGICAL_CHECKPOINT_TOC.txt"))
    durability_path = str(Path(predecessor["packet"]) / "CHECKPOINT_DURABILITY.json")
    required_pins = {old_target_path: predecessor["target_sha256"],
                     old_manifest_path: predecessor["manifest_sha256"],
                     checkpoint_path: predecessor["logical_checkpoint_sha256"]}
    producer_files = {str(Path(predecessor["packet"]) / "units" / (slot + ".json"))
                      for slot in manifest["predecessor_completed_units"]}
    if set(pins) != set(required_pins) | {toc_path, durability_path} | producer_files:
        raise ValueError("Recovery pins must contain only exact predecessor controls and selected unit receipts")
    if (any(pins.get(path) != expected for path, expected in required_pins.items())
            or toc_path not in pins or durability_path not in pins):
        raise ValueError("Predecessor target, manifest, logical checkpoint, TOC and durability receipt must be pinned")
    for relative, expected in pins.items():
        if sha256(relative_file(repository, relative)) != expected:
            raise ValueError("Pinned recovery receipt changed")
    old_target = read_json(relative_file(repository, old_target_path))
    old_manifest = read_json(relative_file(repository, old_manifest_path))
    old_id = predecessor["build_id"]
    if (old_manifest.get("schema") != "daylight-local-full-build/1" or digest(old_manifest) != old_id
            or old_target.get("build_id") != old_id or old_target.get("database") != DATABASE
            or old_target.get("marker") != "daylight-local-full/1:" + old_id
            or old_id == target["build_id"]):
        raise ValueError("Exact legacy predecessor creation chain is required")
    if (target.get("creation_build_id") != old_id or target.get("predecessor_target_sha256") != predecessor["target_sha256"]
            or predecessor["ownership"] != old_target or target.get("created_at") != old_target.get("created_at")
            or not isinstance(target.get("execution_started_at"), str)
            or any(target.get(k) != old_target.get(k) for k in
                   ("database", "database_oid", "marker", "cluster_system_identifier"))):
        raise ValueError("Recovery must preserve the original database/OID/cluster/creation marker")
    for key in ("reference_year", "database", "selected_receipt_files", "selected_source_files",
                "expected_source_rows", "expected_projection_rows", "inherited_source_access_states", "postgres_settings"):
        if manifest.get(key) != old_manifest.get(key):
            raise ValueError("Recovery changed frozen data scope, source policy or settings")
    current_code = {k: v for k, v in manifest["executable_files"].items() if k != BUILDER}
    prior_code = {k: v for k, v in old_manifest["executable_files"].items() if k != BUILDER}
    if current_code != prior_code:
        raise ValueError("Only the execution driver may change in this recovery revision")
    if (predecessor["transport_change"] != {"path": BUILDER,
            "before_sha256": old_manifest["executable_files"][BUILDER],
            "after_sha256": manifest["executable_files"][BUILDER]}
            or predecessor["source_adapter_derivations_changed"] is not False
            or predecessor["new_acceptance"] is not False):
        raise ValueError("Exact driver-only transport revision and unchanged derivations are required")
    checkpoint = read_json(relative_file(repository, checkpoint_path))
    expected_checkpoint = {"schema": "daylight-interrupted-readonly-logical-checkpoint/1", "passed": True,
                           "target": old_target, "predecessor_manifest_sha256": predecessor["manifest_sha256"],
                           "consistent_exported_readonly_snapshot": True, "full_archive_decoded_without_execution": True,
                           "outer_gzip_crc_verified": True,
                           "service_stop_or_restart": False, "database_modified": False, "database_renamed": False,
                           "clean_restore_executed": False, "physical_checkpoint": False, "off_machine_copy_created": False,
                           "full_load_complete": False, "new_acceptance": False}
    if (any(checkpoint.get(k) != value for k, value in expected_checkpoint.items())
            or checkpoint.get("toc_sha256") != pins[toc_path]
            or any(checkpoint.get("ownership", {}).get(k) != old_target[k] for k in
                   ("database", "database_oid", "marker", "cluster_system_identifier"))):
        raise ValueError("Logical checkpoint identity, read-only scope or archive decoding proof differs")
    durability = read_json(relative_file(repository, durability_path))
    if (durability.get("passed") is not True or durability.get("logical_checkpoint_sha256") != predecessor["logical_checkpoint_sha256"]
            or durability.get("dump_sha256") != checkpoint["sha256"]):
        raise ValueError("Logical checkpoint durability receipt differs")
    counts = checkpoint["counts"]
    if any(counts.get(k) != n for k, n in {"jobs": HISTORICAL_JOBS, "complete_jobs": ADOPTED_UNITS,
           "receipts": ADOPTED_UNITS, "acceptance_bindings": 0, "releases": 0}.items()):
        raise ValueError("Historical checkpoint population differs")
    if (predecessor["historical_jobs"] != counts["jobs"] or predecessor["historical_receipts"] != counts["receipts"]
            or predecessor["preserved_dump"] != {k: checkpoint[k] for k in ("path", "sha256", "bytes")}):
        raise ValueError("Predecessor execution/archive summary differs from the checkpoint")
    interrupted, cursors = checkpoint["interrupted_job"], checkpoint["interrupted_checkpoints"]
    if (interrupted.get("job_id") != INTERRUPTED_JOB or interrupted.get("state") != "running"
            or interrupted.get("lease_expired") is not True or interrupted["payload"].get("build_id") != old_id
            or len(cursors) != 1 or cursors[0].get("job_id") != INTERRUPTED_JOB
            or cursors[0].get("last_ordinal") != INTERRUPTED_PREFIX_ROWS
            or cursors[0].get("retained_rows") != INTERRUPTED_PREFIX_ROWS):
        raise ValueError("Captured interrupted execution/prefix differs")
    if predecessor["interrupted_job"] != interrupted or predecessor["interrupted_checkpoints"] != cursors:
        raise ValueError("Predecessor interrupted history differs from the captured checkpoint")
    dump_path = relative_file(repository, checkpoint["path"])
    if dump_path.stat().st_size != checkpoint["bytes"] or sha256(dump_path) != checkpoint["sha256"]:
        raise ValueError("Logical checkpoint archive bytes differ")
    selected = {item["slot"]: item for item in units}
    producers = manifest["predecessor_completed_units"]
    if len(producers) != ADOPTED_UNITS or not set(producers) <= set(selected):
        raise ValueError("Exact adopted predecessor population is required")
    job_ids = set()
    for slot, producer in producers.items():
        if (set(producer) != {"build_id", "job_id", "unit_receipt_path", "unit_receipt_sha256"}
                or producer["build_id"] != old_id or type(producer["job_id"]) is not int
                or producer["job_id"] <= 0 or producer["job_id"] == INTERRUPTED_JOB
                or producer["job_id"] in job_ids
                or producer["unit_receipt_path"] != str(Path(predecessor["packet"]) / "units" / (slot + ".json"))
                or pins.get(producer["unit_receipt_path"]) != producer["unit_receipt_sha256"]):
            raise ValueError("Adopted unit lacks one exact pinned predecessor producer")
        job_ids.add(producer["job_id"])
        original = read_json(relative_file(repository, producer["unit_receipt_path"]))
        item = selected[slot]
        if not filesystem_unit_matches(original, item, old_id, producer["job_id"]):
            raise ValueError("Original material execution receipt differs from selected unit")
    if interrupted["payload"].get("selected_slot") in producers:
        raise ValueError("An incomplete predecessor unit cannot be adopted")
    interrupted_item = selected.get(interrupted["payload"].get("selected_slot"))
    if (interrupted_item is None or predecessor["interrupted_layer_id"] != interrupted_item["binding"]["layer_id"]
            or interrupted["payload"] != controls(interrupted_item, old_id)
            or cursors[0]["derivation_id"] != interrupted_item["binding"]["derivation_id"]
            or cursors[0]["source_table"] != interrupted_item["binding"]["source_table"]):
        raise ValueError("Interrupted checkpoint must bind its exact unadopted selected source unit")
    return {"binding": predecessor, "target": old_target, "manifest": old_manifest,
            "checkpoint": checkpoint, "producers": producers}


def filesystem_unit_matches(receipt, item, build_id, job_id=None, producer=None):
    expected = {"build_id": build_id, "selected_slot": item["slot"], "binding": item["binding"],
                "source_rows": item["rows"], "projection_counts": item["projection_counts"],
                "quarantined_rows": item["quarantined_rows"], "first_ordinal": item["first"],
                "last_ordinal": item["last"], "stream_sha256": item["stream_sha256"],
                "database_verified": True, "new_acceptance": False}
    return (all(receipt.get(k) == value for k, value in expected.items())
            and type(receipt.get("job_id")) is int and receipt["job_id"] > 0
            and (job_id is None or receipt["job_id"] == job_id)
            and ((producer is None and "material_execution" not in receipt)
                 or (producer is not None and receipt.get("material_execution") == producer)))


def load_contract(repository, packet, summary_path):
    repository, packet, summary_path = repository.resolve(), packet.resolve(), summary_path.resolve()
    manifest = read_json(packet / "BUILD_MANIFEST.json")
    target = read_json(packet / "TARGET.json")
    complete = read_json(packet / "LOAD_COMPLETE.json")
    build_id = digest(manifest)
    if (manifest.get("schema") not in {"daylight-local-full-build/1", "daylight-local-full-build/2"} or manifest.get("database") != DATABASE
            or manifest.get("reference_year") != 2026 or manifest.get("new_acceptance") is not False
            or manifest.get("consumer_release_enabled") is not False
            or manifest.get("expected_source_rows") != RAW_ROWS
            or manifest.get("expected_projection_rows") != PROJECTION_ROWS
            or manifest.get("reserve_bytes", 0) < 7 * 1024**3):
        raise ValueError("Frozen build scope differs from the exact local research target")
    if (target.get("database") != DATABASE or target.get("build_id") != build_id
            or target.get("marker") != "daylight-local-full/1:" + target.get("creation_build_id", build_id)
            or target.get("cluster_system_identifier") != manifest["cluster_system_identifier"]
            or type(target.get("database_oid")) is not int):
        raise ValueError("Target ownership receipt differs from the frozen manifest")
    expected_complete = {"schema": "daylight-local-full-load/1", "build_id": build_id,
                         "target": target, "layers_retained": 15, "source_rows": RAW_ROWS,
                         "projection_rows": PROJECTION_ROWS, "unit_receipts": UNIT_COUNT,
                         "all_layers_simultaneously_retained": True, "new_acceptance": False,
                         "consumer_release_enabled": False, "cloud_deployed": False}
    if manifest["schema"] == "daylight-local-full-build/2":
        expected_complete.update(predecessor_material_units=ADOPTED_UNITS, historical_jobs_retained=HISTORICAL_JOBS,
                                 historical_receipts_retained=ADOPTED_UNITS, physical_evidence_counted_once=True,
                                 predecessor_source_digests_replayed=True)
    if any(complete.get(k) != v for k, v in expected_complete.items()):
        raise ValueError("A matching complete persistent load receipt is required before verification")
    # Hash only small frozen implementation/control files. Deliberately do not
    # replay or rehash the many gigabytes of selected original source artifacts.
    pinned = manifest["selected_receipt_files"]
    for relative, expected in {**manifest["executable_files"], **pinned}.items():
        if sha256(relative_file(repository, relative)) != expected:
            raise ValueError("Frozen implementation or selected sizing receipt changed")
    if pinned.get(str(summary_path.relative_to(repository))) != sha256(summary_path):
        raise ValueError("Sizing summary is not pinned by this build")
    summary = read_json(summary_path)
    if (summary.get("layers_measured"), summary.get("source_rows"), summary.get("projection_rows"),
            summary.get("new_acceptance")) != (15, RAW_ROWS, PROJECTION_ROWS, False):
        raise ValueError("Exact fifteen-layer sizing summary is required")
    units, input_files, layers = [], {str(summary_path.relative_to(repository)): sha256(summary_path)}, set()
    for layer in summary["layers"]:
        layer_id = layer["layer_id"]
        if layer_id in layers:
            raise ValueError("Repeated layer selection")
        layers.add(layer_id)
        input_files[layer["layer_receipt"]] = layer["layer_receipt_sha256"]
        selected = []
        for ref in layer["unit_receipts"]:
            input_files[ref["path"]] = ref["sha256"]
            selected.append(normalize_unit(read_json(relative_file(repository, ref["path"])), ref, layer_id))
        if (sum(x["rows"] for x in selected), sum(sum(x["projection_counts"].values()) for x in selected)) != (
                layer["source_rows"], layer["projection_rows"]):
            raise ValueError("Layer controls differ from its selected units")
        units.extend(selected)
    if (layers != {f"L{i:02}" for i in range(1, 16)} or len(units) != UNIT_COUNT
            or input_files != pinned or sum(x["rows"] for x in units) != RAW_ROWS
            or sum(sum(x["projection_counts"].values()) for x in units) != PROJECTION_ROWS):
        raise ValueError("Full exact selected population or input pin set differs")
    check_windows(units)
    sources = {}
    for item in units:
        b = item["binding"]
        if b["source_path"] in sources and sources[b["source_path"]] != b["source_sha256"]:
            raise ValueError("One selected source path has conflicting byte hashes")
        sources[b["source_path"]] = b["source_sha256"]
    if sources != manifest["selected_source_files"]:
        raise ValueError("Selected source identities differ from build manifest")
    profile = read_json(relative_file(repository, PROFILE))
    unsigned = dict(profile)
    if unsigned.pop("content_sha256") != digest(unsigned) or profile["customer_rows_included"] is not False:
        raise ValueError("Profile metadata content hash or customer boundary differs")
    if PROFILE not in manifest["executable_files"]:
        raise ValueError("Profile metadata must be frozen in the build")
    recovery = validate_recovery(repository, manifest, target, units)
    return {"manifest": manifest, "target": target, "complete": complete, "build_id": build_id,
            "summary": summary, "units": units, "profile": profile, "recovery": recovery, "packet": packet}


def controls(item, build_id, producer=None):
    result = {"build_id": build_id, "selected_slot": item["slot"],
            "source_path": item["binding"]["source_path"], "source_table": item["binding"]["source_table"],
            "first_ordinal": item["first"], "last_ordinal": item["last"],
            "projection_counts": item["projection_counts"],
            "sizing_receipt_sha256": item["sizing_receipt_sha256"], "new_acceptance": False}
    if producer is not None:
        result["material_execution"] = producer
    return result


def receipt_matches(row, item, build_id, producer=None):
    b = item["binding"]
    expected = controls(item, build_id, producer)
    return (row["idempotency_key"] == digest(["persistent-local-full/1", build_id, item["slot"]])
            and row["source_id"] == "sealed-local:" + b["layer_id"] and row["state"] == "complete"
            and row["lease_until"] is None and row["finished_at"] is not None
            and row["payload"] == expected and row["controls"] == expected
            and row["input_rows"] == row["retained_rows"] == item["rows"]
            and row["quarantined_rows"] == item["quarantined_rows"]
            and row["stream_sha256"] == item["stream_sha256"]
            and row["derivation_id"] == b["derivation_id"] and row["source_table"] == b["source_table"]
            and row["last_ordinal"] == item["last"] and row["checkpoint_retained_rows"] == item["rows"]
            and row["checkpoint_fence"] == row["fence"])


class Measurements:
    def __init__(self, connection, effective_role=None):
        self.connection = connection
        self.effective_role = effective_role
        self.queries, self.proofs = [], []

    def query(self, name, statement, parameters=(), max_rows=1000):
        if not statement.lstrip().upper().startswith(("SELECT", "WITH")) or ";" in statement:
            raise ValueError("Verifier statements must be single fixed SELECT/WITH queries")
        entry = {"id": name, "sql": statement, "parameters": parameters,
                 "row_limit": max_rows, "statement_timeout_ms": 120000,
                 "effective_role": self.effective_role}
        started = time.monotonic()
        try:
            # SAVEPOINT permits a timed-out diagnostic to be recorded without
            # abandoning the consistent outer READ ONLY snapshot.
            with self.connection.transaction():
                entry["plan"] = self.connection.execute("EXPLAIN (FORMAT JSON, SETTINGS TRUE) " + statement,
                                                        parameters).fetchone()["QUERY PLAN"]
                execution_started = time.monotonic()
                with self.connection.execute(statement, parameters) as cursor:
                    rows = cursor.fetchmany(max_rows + 1)
                    if len(rows) > max_rows:
                        raise ValueError("Diagnostic result exceeds its declared metadata/public-row bound")
                entry.update(rows=rows, execution_seconds=round(time.monotonic() - execution_started, 6),
                             returned_rows=len(rows), success=True)
        except Exception as error:
            # No DSN, SQL exception detail, credentials or arbitrary payload is
            # emitted on a connection/permission/operator failure.
            entry.update(success=False, error_type=type(error).__name__, sqlstate=getattr(error, "sqlstate", None))
            rows = None
        entry["total_seconds"] = round(time.monotonic() - started, 6)
        self.queries.append(entry)
        print(json.dumps({"query": name, "success": entry["success"], "seconds": entry["total_seconds"]}), flush=True)
        return rows

    def proof(self, name, passed, observed, expected, query_ids=(), limitation=None):
        self.proofs.append({"name": name, "passed": bool(passed), "observed": observed,
                            "expected": expected, "query_ids": list(query_ids), "limitation": limitation})


RECEIPTS_SQL = """SELECT j.job_id,j.idempotency_key,j.source_id,j.state,j.payload,j.fence,j.lease_until,j.finished_at,
    r.input_rows,r.retained_rows,r.quarantined_rows,r.stream_sha256,r.controls,
    c.derivation_id,c.source_table,c.last_ordinal,c.retained_rows AS checkpoint_retained_rows,c.fence AS checkpoint_fence
    FROM dl_control.job j LEFT JOIN dl_control.ingest_receipt r USING(job_id)
    LEFT JOIN dl_control.checkpoint c USING(job_id)
    WHERE j.payload->>'build_id'=%s AND r.controls->>'build_id'=%s
    ORDER BY j.job_id,c.derivation_id,c.source_table"""
EXECUTION_COUNTS_SQL = """SELECT count(*) AS jobs,count(*) FILTER(WHERE j.state='complete') AS complete_jobs,
    count(*) FILTER(WHERE j.state='failed') AS failed_jobs,
    count(*) FILTER(WHERE j.state NOT IN ('complete','failed')) AS other_jobs,count(r.job_id) AS receipts,
    count(*) FILTER(WHERE r.job_id IS NOT NULL AND r.controls->>'build_id' IS DISTINCT FROM %s) AS wrong_receipt_builds,
    (SELECT count(*) FROM dl_control.checkpoint c JOIN dl_control.job k USING(job_id)
     WHERE k.payload->>'build_id'=%s) AS checkpoints
    FROM dl_control.job j LEFT JOIN dl_control.ingest_receipt r USING(job_id) WHERE j.payload->>'build_id'=%s"""
RAW_WINDOW_SQL = """SELECT count(*) AS rows,min(source_row_ordinal) AS first,max(source_row_ordinal) AS last,
    count(*) FILTER(WHERE disposition LIKE 'quarantined%%') AS quarantined_rows
    FROM dl_evidence.source_record WHERE derivation_id=%s AND source_table=%s
    AND source_row_ordinal BETWEEN %s AND %s"""
PROJECTION_WINDOW_SQL = """SELECT entity_type,count(*) AS rows FROM dl_evidence.observation
    WHERE derivation_id=%s AND source_table=%s AND source_row_ordinal BETWEEN %s AND %s
    GROUP BY entity_type ORDER BY entity_type"""


def verify_units(m, contract):
    units, build_id = contract["units"], contract["build_id"]
    recovery = contract.get("recovery")
    producers = recovery["producers"] if recovery else {}
    cohorts = m.query("all_execution_cohorts", """SELECT j.payload->>'build_id' AS build_id,count(*) AS jobs,
        count(r.job_id) AS receipts,count(*) FILTER(WHERE j.state='complete') AS complete_jobs,
        count(*) FILTER(WHERE j.state='failed') AS failed_jobs
        FROM dl_control.job j LEFT JOIN dl_control.ingest_receipt r USING(job_id)
        GROUP BY j.payload->>'build_id' ORDER BY build_id""", max_rows=3)
    expected_cohorts = [{"build_id": build_id, "jobs": UNIT_COUNT, "receipts": UNIT_COUNT,
                         "complete_jobs": UNIT_COUNT, "failed_jobs": 0}]
    if recovery:
        expected_cohorts.append({"build_id": recovery["binding"]["build_id"], "jobs": HISTORICAL_JOBS,
                                 "receipts": ADOPTED_UNITS, "complete_jobs": ADOPTED_UNITS, "failed_jobs": 1})
    expected_cohorts.sort(key=lambda x: x["build_id"])
    m.proof("exact current and explicitly retained historical execution cohorts", cohorts == expected_cohorts,
            cohorts, expected_cohorts, ["all_execution_cohorts"],
            "Execution counts are separate from physical evidence counts; historical/adoption receipt row totals are never added.")
    counts = m.query("current_execution_counts", EXECUTION_COUNTS_SQL, (build_id, build_id, build_id))
    expected_counts = [{"jobs": UNIT_COUNT, "complete_jobs": UNIT_COUNT, "failed_jobs": 0, "other_jobs": 0,
                        "receipts": UNIT_COUNT, "wrong_receipt_builds": 0, "checkpoints": UNIT_COUNT}]
    m.proof("current execution has exactly 363 complete jobs, receipts and checkpoints", counts == expected_counts,
            counts, expected_counts, ["current_execution_counts"], "Historical executions are accounted separately, never added to physical rows.")
    rows = m.query("database_receipts_checkpoints", RECEIPTS_SQL, (build_id, build_id), max_rows=UNIT_COUNT + 1)
    by_slot = defaultdict(list)
    for row in rows or []:
        by_slot[(row.get("controls") or {}).get("selected_slot")].append(row)
    bad = []
    for item in units:
        candidates = by_slot.get(item["slot"], [])
        if len(candidates) != 1 or not receipt_matches(candidates[0], item, build_id, producers.get(item["slot"])):
            bad.append(item["slot"])
    m.proof("363 exact database jobs, receipts and truthful window checkpoints",
            rows is not None and len(rows) == UNIT_COUNT and not bad and set(by_slot) == {i["slot"] for i in units},
            {"joined_rows": len(rows) if rows is not None else None, "mismatched_slots": bad},
            {"rows": UNIT_COUNT, "mismatched_slots": []}, ["database_receipts_checkpoints"])
    for item in units:
        b = item["binding"]
        values = (b["derivation_id"], b["source_table"], item["first"], item["last"])
        label = b["layer_id"] + ":" + item["slot"]
        raw = m.query("raw:" + label, RAW_WINDOW_SQL, values)
        projected = m.query("projection:" + label, PROJECTION_WINDOW_SQL, values)
        raw_expected = {"rows": item["rows"], "first": item["first"], "last": item["last"],
                        "quarantined_rows": item["quarantined_rows"]}
        actual_types = {r["entity_type"]: r["rows"] for r in projected} if projected is not None else None
        m.proof("selected window " + label, raw == [raw_expected] and actual_types == item["projection_counts"],
                {"binding": b, "raw": raw, "projection_counts": actual_types},
                {"raw": raw_expected, "projection_counts": item["projection_counts"]},
                ["raw:" + label, "projection:" + label])
        fs_path = contract["packet"] / "units" / (item["slot"] + ".json")
        try:
            fs_path = relative_file(contract["packet"], "units/" + item["slot"] + ".json")
            fs_receipt = read_json(fs_path)
            candidate = by_slot.get(item["slot"], [])
            fs_matches = len(candidate) == 1 and filesystem_unit_matches(fs_receipt, item, build_id,
                candidate[0]["job_id"], producers.get(item["slot"]))
            fs_observed = {"path": str(fs_path.relative_to(contract["packet"])), "sha256": sha256(fs_path),
                           "job_id": fs_receipt.get("job_id"), "material_execution": fs_receipt.get("material_execution")}
        except (OSError, ValueError, KeyError) as error:
            fs_matches, fs_observed = False, {"error_type": type(error).__name__}
        m.proof("current filesystem receipt " + label, fs_matches, fs_observed,
                "exact current database job/selected controls and explicit predecessor producer when adopted")
    if recovery:
        verify_predecessor_execution(m, contract)


def verify_predecessor_execution(m, contract):
    recovery, units = contract["recovery"], {i["slot"]: i for i in contract["units"]}
    old_id, producers = recovery["binding"]["build_id"], recovery["producers"]
    counts = m.query("historical_execution_counts", EXECUTION_COUNTS_SQL, (old_id, old_id, old_id))
    expected = [{"jobs": HISTORICAL_JOBS, "complete_jobs": ADOPTED_UNITS, "failed_jobs": 1, "other_jobs": 0,
                 "receipts": ADOPTED_UNITS, "wrong_receipt_builds": 0, "checkpoints": HISTORICAL_JOBS}]
    m.proof("predecessor history retains 123 jobs, 122 receipts and one failed prefix execution", counts == expected,
            counts, expected, ["historical_execution_counts"], "Historical receipt row totals are not added to current physical populations.")
    rows = m.query("predecessor_material_receipts_checkpoints", RECEIPTS_SQL, (old_id, old_id), max_rows=ADOPTED_UNITS + 1)
    by_job = defaultdict(list)
    for row in rows or []:
        by_job[row["job_id"]].append(row)
    bad = []
    for slot, producer in producers.items():
        candidates = by_job.get(producer["job_id"], [])
        if len(candidates) != 1 or not receipt_matches(candidates[0], units[slot], old_id):
            bad.append(slot)
    m.proof("122 adopted producers independently match original canonical database receipts/checkpoints",
            rows is not None and len(rows) == ADOPTED_UNITS and not bad
            and set(by_job) == {p["job_id"] for p in producers.values()},
            {"rows": len(rows) if rows is not None else None, "mismatched_slots": bad},
            {"rows": ADOPTED_UNITS, "mismatched_slots": []}, ["predecessor_material_receipts_checkpoints"])
    failed = m.query("historical_interrupted_prefix", """SELECT j.job_id,j.state,j.payload,j.lease_until,j.finished_at,
        c.derivation_id,c.source_table,c.last_ordinal,c.retained_rows,c.fence,
        (SELECT count(*) FROM dl_evidence.source_record r WHERE r.derivation_id=c.derivation_id
         AND r.source_table=c.source_table AND r.source_row_ordinal BETWEEN 1 AND c.last_ordinal) AS preserved_prefix_rows
        FROM dl_control.job j LEFT JOIN dl_control.checkpoint c USING(job_id)
        WHERE j.job_id=%s AND j.payload->>'build_id'=%s""", (INTERRUPTED_JOB, old_id), max_rows=2)
    captured = recovery["checkpoint"]["interrupted_checkpoints"][0]
    captured_job = recovery["checkpoint"]["interrupted_job"]
    valid = failed is not None and len(failed) == 1
    if valid:
        row = failed[0]
        valid = (row["state"] == "failed" and row["lease_until"] is None and row["finished_at"] is not None
                 and row["payload"] == captured_job["payload"]
                 and all(row[k] == captured[k] for k in ("derivation_id", "source_table", "last_ordinal", "retained_rows", "fence"))
                 and row["preserved_prefix_rows"] == INTERRUPTED_PREFIX_ROWS)
    m.proof("failed predecessor retains its captured 1000-row checkpoint and source prefix", valid, failed,
            "captured prefix unchanged; expired running job explicitly retired to failed without adoption",
            ["historical_interrupted_prefix"])


def derivation(units, layer_id, source_table, path_contains=None):
    found = {i["binding"]["derivation_id"] for i in units if i["binding"]["layer_id"] == layer_id
             and i["binding"]["source_table"] == source_table
             and (path_contains is None or path_contains in i["binding"]["source_path"])}
    if len(found) != 1:
        raise ValueError("Domain query has an ambiguous or missing selected table")
    return found.pop()


def verify_metadata(m, contract):
    units = contract["units"]
    metadata = m.query("source_derivation_bindings", """SELECT d.derivation_id,d.snapshot_id,d.adapter_version,
        d.configuration_hash,d.adapter_code_sha256,s.layer_id,s.original_path,s.artifact_sha256,s.benefit_year,
        s.source_use_state,a.byte_length FROM dl_control.derivation d
        JOIN dl_control.source_snapshot s USING(snapshot_id) JOIN dl_control.artifact a ON a.sha256=s.artifact_sha256
        ORDER BY d.derivation_id""")
    expected = {}
    for item in units:
        b = item["binding"]
        expected[b["derivation_id"]] = {"snapshot_id": digest({"layer": b["layer_id"], "path": b["source_path"],
                                                               "sha256": b["source_sha256"]}),
            "adapter_version": ADAPTER_VERSION,
            "configuration_hash": digest(["2026-source-preserving", b["source_table"], b["adapter_code_sha256"]]),
            "adapter_code_sha256": b["adapter_code_sha256"], "layer_id": b["layer_id"],
            "original_path": b["source_path"], "artifact_sha256": b["source_sha256"], "benefit_year": 2026,
            "source_use_state": "not_newly_reviewed"}
    bad = [r["derivation_id"] for r in metadata or [] if r["derivation_id"] not in expected or
           any(r[k] != v for k, v in expected[r["derivation_id"]].items())]
    m.proof("exact source snapshots and code-bound table derivations",
            metadata is not None and len(metadata) == len(expected) and not bad,
            {"derivations": len(metadata) if metadata is not None else None, "mismatches": bad},
            {"derivations": len(expected), "mismatches": []}, ["source_derivation_bindings"])
    snapshots = m.query("snapshot_count", "SELECT count(*) AS rows FROM dl_control.source_snapshot")
    m.proof("no extra source snapshots", snapshots == [{"rows": len({r["snapshot_id"] for r in expected.values()})}],
            snapshots, len({r["snapshot_id"] for r in expected.values()}), ["snapshot_count"])
    source_states = m.query("source_access_holds", "SELECT source_id,state,reason FROM dl_control.source_access_state ORDER BY source_id")
    inherited = sorted(contract["manifest"]["inherited_source_access_states"], key=lambda x: x["source_id"])
    m.proof("inherited source access states remain exact", source_states == inherited, source_states, inherited,
            ["source_access_holds"])
    profile = m.query("profile_metadata_only", """SELECT contract_sha256,question_count,field_count,gap_count,
        contract_payload=%s::jsonb AS exact_payload,
        contract_payload->'customer_rows_included'='false'::jsonb AS no_customer_rows
        FROM dl_control.profile_contract ORDER BY contract_sha256""", (json.dumps(contract["profile"]),))
    p_expected = [{"contract_sha256": contract["profile"]["content_sha256"], "question_count": 41,
                   "field_count": 78, "gap_count": 14, "exact_payload": True, "no_customer_rows": True}]
    m.proof("one exact metadata-only profile contract 41/78/14", profile == p_expected, profile, p_expected,
            ["profile_metadata_only"])


COLLIER_SQL = """WITH c AS MATERIALIZED (
    SELECT o.fields->>'id' AS offering_id,r.raw_payload->>'id' AS native_id,
    o.offering_id AS material_offering_id FROM dl_evidence.observation o
    JOIN dl_evidence.source_record r USING(derivation_id,source_table,source_row_ordinal)
    WHERE o.derivation_id=%s AND o.entity_type='collier_offering_scope' AND o.source_table='collier_offerings'),
    s AS MATERIALIZED (SELECT DISTINCT offering_id FROM dl_evidence.observation WHERE derivation_id=%s)
    SELECT count(*) AS collier_rows,count(DISTINCT c.offering_id) AS collier_distinct,
    count(*)-count(DISTINCT c.offering_id) AS duplicate_or_null_ids,
    count(*) FILTER(WHERE c.offering_id IS NULL OR c.offering_id !~ '^2026:[A-Z][0-9]{4}:[0-9]{3}:[0-9]{3}$') AS invalid_ids,
    count(*) FILTER(WHERE c.offering_id IS DISTINCT FROM c.native_id) AS source_projection_id_mismatches,
    count(*) FILTER(WHERE c.material_offering_id IS NOT NULL) AS material_offering_id_rows,
    count(*) FILTER(WHERE c.material_offering_id IS NOT NULL AND c.material_offering_id IS DISTINCT FROM c.offering_id) AS conflicting_material_ids,
    (SELECT count(*) FROM dl_evidence.offering WHERE derivation_id=%s) AS national_offerings,
    (SELECT count(*) FROM s) AS r9_offerings,
    count(*) FILTER(WHERE n.offering_id IS NULL) AS missing_national,
    count(*) FILTER(WHERE s.offering_id IS NULL) AS missing_r9
    FROM c LEFT JOIN dl_evidence.offering n ON n.offering_id=c.offering_id AND n.derivation_id=%s
    LEFT JOIN s ON s.offering_id=c.offering_id"""
R9_SQL = """WITH u AS MATERIALIZED (
    SELECT d.snapshot_id,r.raw_payload->>'id' AS unit_id,r.raw_payload->>'kind' AS kind
    FROM dl_evidence.source_record r JOIN dl_control.derivation d USING(derivation_id) WHERE r.derivation_id=%s),
    c AS MATERIALIZED (SELECT d.snapshot_id,r.raw_payload->>'unit_id' AS unit_id,
    r.raw_payload->>'canonical_id' AS canonical_id FROM dl_evidence.source_record r
    JOIN dl_control.derivation d USING(derivation_id) WHERE r.derivation_id=%s)
    SELECT coalesce(u.kind,'orphan_mapping') AS kind,count(*) AS representations,
    count(DISTINCT c.canonical_id) AS canonical_identities,
    count(*) FILTER(WHERE c.unit_id IS NULL) AS missing_mapping,
    count(*) FILTER(WHERE u.unit_id IS NULL) AS orphan_mapping
    FROM u FULL JOIN c ON c.snapshot_id=u.snapshot_id AND c.unit_id=u.unit_id
    GROUP BY u.kind ORDER BY kind"""
CONDITIONS_SQL = """WITH sample AS MATERIALIZED (
    SELECT * FROM dl_evidence.observation WHERE derivation_id=%s
    AND entity_type='ma_semantic_condition_representation' ORDER BY entity_id LIMIT 5)
    SELECT p.offering_id,p.fields->>'semantic_unit_id' AS semantic_unit_id,
    p.fields->'source_columns'->>'subject' AS subject,p.fields->'source_columns'->>'predicate' AS predicate,
    p.conditions,p.value_state,p.semantic_review_state,p.output_acceptance_state,
    s.original_path,s.artifact_sha256,d.snapshot_id,p.source_table,p.source_row_ordinal,r.raw_sha256,
    r.raw_payload->'context' AS native_context,
    p.fields->'source_columns'->'context' AS projected_context
    FROM sample p JOIN dl_evidence.source_record r USING(derivation_id,source_table,source_row_ordinal)
    JOIN dl_control.derivation d USING(derivation_id) JOIN dl_control.source_snapshot s USING(snapshot_id)
    ORDER BY p.entity_id"""
PDP_SQL = """WITH counties AS MATERIALIZED (
    SELECT county_fips,fields->>'region_code' AS region FROM dl_evidence.observation
    WHERE derivation_id=%s AND entity_type='pdp_region_county'),
    plans AS MATERIALIZED (SELECT offering_id,fields->>'region_code' AS region FROM dl_evidence.observation
    WHERE derivation_id=%s AND entity_type='offering')
    SELECT count(DISTINCT c.county_fips) AS florida_counties,
    count(*) FILTER(WHERE c.county_fips NOT LIKE '12%%') AS non_florida_relationships,
    count(*) AS published_region_plan_relationships,count(DISTINCT p.offering_id) AS pdp_offerings,
    count(*) FILTER(WHERE p.offering_id IS NULL) AS unmatched_counties
    FROM counties c LEFT JOIN plans p USING(region)"""
PHARMACY_SQL = """SELECT o.offering_id,o.fields->>'npi' AS npi,o.fields->>'network_zip' AS source_zip,
    o.fields->>'retail_status' AS retail_status,o.fields->>'mail_status' AS mail_status,
    o.fields->'dispensing_fee_usd' AS source_dispensing_fees,o.fields->>'fee_basis' AS fee_basis,
    o.fields->'current_operation_verified' AS current_operation_verified,
    o.conditions,o.value_state,o.source_use_state,o.output_acceptance_state,
    s.original_path,s.artifact_sha256,o.source_table,o.source_row_ordinal,r.raw_sha256
    FROM dl_evidence.observation o JOIN dl_evidence.source_record r USING(derivation_id,source_table,source_row_ordinal)
    JOIN dl_control.derivation d USING(derivation_id) JOIN dl_control.source_snapshot s USING(snapshot_id)
    WHERE o.derivation_id=%s AND o.entity_type='pharmacy_network_observation'
    AND o.offering_id=%s AND o.fields->>'npi'=%s ORDER BY o.entity_id LIMIT 10"""
PROVIDER_SQL = """SELECT o.entity_type,o.fields->>'entity_key' AS source_entity_key,o.fields->'npi' AS source_npis,
    o.fields->'personal_network_status_determined' AS personal_network_status_determined,
    o.fields->'identity_is_not_network_verification' AS identity_is_not_network_verification,
    o.value_state,o.source_use_state,o.output_acceptance_state,s.original_path,s.artifact_sha256,
    o.source_table,o.source_row_ordinal,r.raw_sha256
    FROM dl_evidence.observation o JOIN dl_evidence.source_record r USING(derivation_id,source_table,source_row_ordinal)
    JOIN dl_control.derivation d USING(derivation_id) JOIN dl_control.source_snapshot s USING(snapshot_id)
    WHERE o.derivation_id=%s AND o.fields->'npi' ? %s ORDER BY o.entity_id LIMIT 10"""


def context_inspection_matches(rows):
    """Bounded exact context preservation, never semantic condition validation.

    Both SQL columns use JSONB ->, retaining a native SQLite context string as
    text and a structured JSON context as JSON. Canonical encoding compares JSON
    types consistently while preserving every character inside source strings.
    """
    return rows is not None and len(rows) == 5 and all(
        row["semantic_review_state"] == "not_newly_reviewed"
        and row["output_acceptance_state"] == "research_only"
        and row["native_context"] is not None
        and canonical(row["native_context"]) == canonical(row["projected_context"])
        for row in rows)


def unknown_inspection_matches(rows):
    """One exact source unknown must keep its material state and research gates."""
    if rows is None or len(rows) != 1:
        return False
    row = rows[0]
    return (row.get("source_state") == "unknown_no_exact_campus_plan_evidence"
            and row.get("value_state") == row.get("source_state")
            and row.get("personal_network_status_determined") is False
            and row.get("source_use_state") == "existing_source_policy_applies"
            and row.get("output_acceptance_state") == "research_only")


def verify_domains(m, contract):
    units = contract["units"]
    d = lambda layer, table, path=None: derivation(units, layer, table, path)
    semantic, mapping = d("L03", "semantic_unit", R9), d("L03", "canonical_unit", R9)
    collier = m.query("collier_national_r9_bridge", COLLIER_SQL,
                      (d("L02", "collier_offerings"), semantic, d("L02", "offerings"), d("L02", "offerings")))
    expected = [{"collier_rows": 72, "collier_distinct": 72, "duplicate_or_null_ids": 0, "invalid_ids": 0,
                 "source_projection_id_mismatches": 0, "material_offering_id_rows": 0, "conflicting_material_ids": 0,
                 "national_offerings": 5962, "r9_offerings": 72, "missing_national": 0, "missing_r9": 0}]
    m.proof("72 distinct Collier offerings bridge national L02 and frozen r9", collier == expected,
            collier, expected, ["collier_national_r9_bridge"],
            "Frozen Collier scope IDs are fields.id, matched exactly to raw.id; all 72 scope material offering_id columns remain unpopulated. Published identity joins do not verify personal availability.")
    canonical_rows = m.query("r9_canonical_semantic_counts", R9_SQL, (semantic, mapping))
    expected = [{"kind": "claim", "representations": 143679, "canonical_identities": 143505,
                 "missing_mapping": 0, "orphan_mapping": 0},
                {"kind": "condition", "representations": 249065, "canonical_identities": 249065,
                 "missing_mapping": 0, "orphan_mapping": 0}]
    m.proof("r9 canonical claims and predicates preserve representations and aliases", canonical_rows == expected,
            canonical_rows, expected, ["r9_canonical_semantic_counts"],
            "392,570 canonical obligations are evidence/comparison obligations, not verified benefits.")
    required = {table: d("L03", table, R9) for table in ("semantic_unit", "canonical_unit", "source_identity_alias", "work_obligation")}
    snapshots = m.query("r9_common_source_snapshot", """SELECT count(*) AS table_derivations,
        count(DISTINCT snapshot_id) AS common_snapshot_count FROM dl_control.derivation WHERE derivation_id=ANY(%s)""",
        (list(required.values()),))
    expected = [{"table_derivations": 4, "common_snapshot_count": 1}]
    m.proof("r9 cross-table joins use one source snapshot across table-specific derivations", snapshots == expected,
            snapshots, expected, ["r9_common_source_snapshot"])
    populations = m.query("r9_mappings_aliases_followups", """SELECT source_table,count(*) AS rows
        FROM dl_evidence.source_record WHERE derivation_id=ANY(%s) GROUP BY source_table ORDER BY source_table""",
        (list(required.values()),))
    expected = [{"source_table": table, "rows": count} for table, count in sorted({"semantic_unit": 392744,
                "canonical_unit": 392744, "source_identity_alias": 174, "work_obligation": 230}.items())]
    m.proof("r9 392744 representations/mappings, 174 aliases and 230 followups", populations == expected,
            populations, expected, ["r9_mappings_aliases_followups"])
    inspected = m.query("bounded_context_preservation_inspection", CONDITIONS_SQL, (semantic,), max_rows=5)
    m.proof("bounded context preservation inspection retains exact native/projected context and held review",
            context_inspection_matches(inspected),
            {"public_rows": len(inspected) if inspected is not None else None}, {"public_rows": 5},
            ["bounded_context_preservation_inspection"],
            "Five illustrative rows compared exactly; no semantic condition validation. Exhaustive population accounting is separate.")
    pdp = m.query("florida_pdp_county_region_join", PDP_SQL, (d("L04", "counties"), d("L04", "pdp_records")))
    expected = [{"florida_counties": 67, "non_florida_relationships": 0,
                 "published_region_plan_relationships": 670, "pdp_offerings": 10, "unmatched_counties": 0}]
    m.proof("67 Florida PDP counties join ten source-region offerings", pdp == expected, pdp, expected,
            ["florida_pdp_county_region_join"], "Region relationships remain published reference observations.")
    quarantine = m.query("l02_quarantine_preserved", """SELECT r.source_row_ordinal,r.disposition,
        o.value_state,o.entity_type,o.output_acceptance_state FROM dl_evidence.source_record r
        JOIN dl_evidence.observation o USING(derivation_id,source_table,source_row_ordinal)
        WHERE r.derivation_id=%s ORDER BY r.source_row_ordinal""", (d("L02", "quarantine"),), max_rows=3)
    m.proof("all three L02 source quarantine rows remain quarantined", quarantine is not None and len(quarantine) == 3
            and all(r["disposition"].startswith("quarantined") and r["value_state"] == "quarantined"
                    and r["entity_type"] == "source_quarantine" for r in quarantine),
            quarantine, "3 retained source_quarantine observations, not silently discarded", ["l02_quarantine_preserved"])
    pharmacy = m.query("published_plan_pharmacy_lookup", PHARMACY_SQL,
                       (d("L07", "network", "/build-r1/"), "2026:H0710:010:000", "1003001934"), max_rows=10)
    m.proof("bounded published plan/pharmacy lookup keeps operation unverified and research output held", pharmacy is not None and len(pharmacy) > 0
            and all(r["current_operation_verified"] is False and r["output_acceptance_state"] == "research_only" for r in pharmacy),
            {"public_rows": len(pharmacy) if pharmacy is not None else None}, "at least one published-source row",
            ["published_plan_pharmacy_lookup"], "Published identifiers only; no personal pharmacy, network verification or drug-price claim.")
    provider = m.query("illustrative_public_npi_lookup", PROVIDER_SQL,
                       (d("L08", "entities", "/wellcare-r5/"), "1922013515"), max_rows=10)
    m.proof("illustrative NPI identity never asserts personal network participation", provider is not None and len(provider) > 0
            and all(r["personal_network_status_determined"] is False and r["identity_is_not_network_verification"] is True
                    for r in provider), {"public_rows": len(provider) if provider is not None else None},
            "at least one identity row with personal determination false", ["illustrative_public_npi_lookup"])
    unknown = m.query("provider_exact_unknown_example", """SELECT offering_id,fields->>'hospital_id' AS hospital_id,
        fields->>'state' AS source_state,fields->'personal_network_status_determined' AS personal_network_status_determined,
        value_state,source_use_state,output_acceptance_state FROM dl_evidence.observation
        WHERE derivation_id=%s AND offering_id=%s AND fields->>'hospital_id'=%s ORDER BY entity_id LIMIT 5""",
        (d("L08", "hospital_plan_matrix", "/wellcare-r5/"), "2026:H0710:010:000", "AHCA:514411"), max_rows=5)
    m.proof("source-native hospital/plan unknown retains exact material state and research gates",
            unknown_inspection_matches(unknown), unknown,
            "value_state equals unknown_no_exact_campus_plan_evidence; source policy applies; research_only; no personal determination",
            ["provider_exact_unknown_example"])
    provider_derivations = sorted({i["binding"]["derivation_id"] for i in units if i["binding"]["layer_id"] == "L08"})
    provider_guard = m.query("all_provider_personal_network_guards", """SELECT count(*) AS rows,
        count(*) FILTER(WHERE fields->'personal_network_status_determined' IS DISTINCT FROM 'false'::jsonb) AS invalid_personal_guard,
        count(*) FILTER(WHERE fields->'identity_is_not_network_verification' IS DISTINCT FROM 'true'::jsonb) AS invalid_identity_guard,
        count(*) FILTER(WHERE value_state LIKE 'unknown%%') AS source_unknown_rows
        FROM dl_evidence.observation WHERE derivation_id=ANY(%s)""", (provider_derivations,))
    m.proof("all provider records keep personal network determination false", provider_guard is not None
            and provider_guard[0]["rows"] == 4169528 and provider_guard[0]["invalid_personal_guard"] == 0
            and provider_guard[0]["invalid_identity_guard"] == 0 and provider_guard[0]["source_unknown_rows"] > 0,
            provider_guard, "4,169,528 retained observations; all guards exact; source unknowns remain", ["all_provider_personal_network_guards"])
    source_stops = m.query("native_drug_source_stops", """WITH native AS MATERIALIZED (
        SELECT r.derivation_id,'L05:'||r.record_id||':plan-link:'||x.ordinality AS entity_id
        FROM dl_evidence.source_record r CROSS JOIN LATERAL
        jsonb_array_elements(CASE WHEN jsonb_typeof(r.raw_payload->'plan_links')='array'
        THEN r.raw_payload->'plan_links' ELSE '[]'::jsonb END) WITH ORDINALITY AS x(link,ordinality)
        WHERE r.derivation_id=%s AND x.link->>'source_state' LIKE '%%STOP%%')
        SELECT count(*) AS native_stop_links,count(*) FILTER(WHERE o.entity_id IS NULL) AS missing_projection,
        count(*) FILTER(WHERE o.source_use_state IS DISTINCT FROM 'source_access_STOP') AS lost_source_stop,
        count(*) FILTER(WHERE o.fields->'personal_approval' IS DISTINCT FROM 'false'::jsonb) AS invalid_personal_approval
        FROM native n LEFT JOIN dl_evidence.observation o ON o.derivation_id=n.derivation_id
        AND o.entity_type='drug_condition_reference' AND o.entity_id=n.entity_id""",
        (d("L05", "condition_reference_links"),))
    m.proof("native drug condition source STOPs survive exact plan-link projections", source_stops is not None
            and source_stops[0]["native_stop_links"] > 0 and source_stops[0]["missing_projection"] == 0
            and source_stops[0]["lost_source_stop"] == 0 and source_stops[0]["invalid_personal_approval"] == 0,
            source_stops, "all native STOP links retained with source_access_STOP and personal_approval false",
            ["native_drug_source_stops"])


def verify_boundaries(m):
    states = m.query("observation_review_use_output_states", """SELECT evidence_state,semantic_review_state,
        source_use_state,freshness_state,output_acceptance_state,count(*) AS rows
        FROM dl_evidence.observation GROUP BY 1,2,3,4,5 ORDER BY 1,2,3,4,5""")
    allowed = {"research_only", "exact_existing_receipt_gate_required"}
    m.proof("all observation output/review gates remain held", states is not None and sum(r["rows"] for r in states) == PROJECTION_ROWS
            and all(r["output_acceptance_state"] in allowed and r["semantic_review_state"] == "not_newly_reviewed" for r in states),
            states, "all projections research-only or exact-existing-receipt-gated; no new semantic review",
            ["observation_review_use_output_states"])
    offerings = m.query("offering_output_states", "SELECT output_acceptance_state,count(*) AS rows FROM dl_evidence.offering GROUP BY 1 ORDER BY 1")
    m.proof("offering material rows remain research-only", offerings == [{"output_acceptance_state": "research_only", "rows": 5972}],
            offerings, [{"output_acceptance_state": "research_only", "rows": 5972}], ["offering_output_states"])
    release = m.query("empty_acceptance_release_active", """SELECT
        (SELECT count(*) FROM dl_review.acceptance_binding) AS acceptance_bindings,
        (SELECT count(*) FROM dl_review.release) AS releases,
        (SELECT count(*) FROM dl_review.active_release) AS active_releases""")
    expected = [{"acceptance_bindings": 0, "releases": 0, "active_releases": 0}]
    m.proof("no acceptance binding, release or active consumer release", release == expected, release, expected,
            ["empty_acceptance_release_active"])
    privileges = m.query("research_role_boundary", """SELECT current_user AS effective_role,
        current_setting('transaction_read_only') AS transaction_read_only,
        has_table_privilege(current_user,'dl_evidence.source_record','INSERT,UPDATE,DELETE,TRUNCATE') AS can_mutate_raw,
        has_table_privilege(current_user,'dl_review.acceptance_binding','INSERT,UPDATE,DELETE') AS can_accept,
        has_table_privilege(current_user,'dl_review.release','INSERT,UPDATE,DELETE') AS can_release""")
    expected = [{"effective_role": "daylight_research_reader", "transaction_read_only": "on",
                 "can_mutate_raw": False, "can_accept": False, "can_release": False}]
    m.proof("read-only research credential has no mutation or release authority", privileges == expected,
            privileges, expected, ["research_role_boundary"])


def json_default(value):
    if isinstance(value, (datetime, Decimal)):
        return str(value)
    raise TypeError(type(value).__name__)


def write_report(path, value):
    # Never overwrite any load/build/source receipt, including on a failed run.
    if path.exists():
        raise ValueError("Verification output already exists; select a fresh report path")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("x") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, default=json_default)
        handle.write("\n")
    # Exclusive destination creation prevents replacing a concurrently created
    # evidence receipt. The temporary file is always just this generated report.
    try:
        os.link(temporary, path)
    finally:
        temporary.unlink()


def measure_owned_database_size(m, ownership):
    """Size is an administrative catalog measurement, never a research-role grant."""
    rows = m.query("actual_retained_database_size", """SELECT pg_database_size(current_database()) AS bytes,
        current_user AS effective_role,current_setting('transaction_read_only') AS transaction_read_only""")
    valid = (rows is not None and len(rows) == 1 and rows[0]["bytes"] > 0
             and rows[0]["effective_role"] == ownership["effective_role"]
             and rows[0]["transaction_read_only"] == "on")
    m.proof("database storage measured by the owned read-only catalog operator", valid, rows,
            "positive database bytes under the verified ownership role in READ ONLY", ["actual_retained_database_size"])
    return rows


def verify(repository, packet, summary_path, dsn):
    contract = load_contract(repository, packet, summary_path)
    safe_dsn = target_dsn(dsn, repository)
    with psycopg.connect(safe_dsn, autocommit=True, row_factory=dict_row) as connection:
        with connection.transaction():
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            m = Measurements(connection, effective_role=connection.info.user)
            ownership_rows = m.query("actual_database_ownership", """SELECT current_database() AS database,d.oid AS database_oid,
                shobj_description(d.oid,'pg_database') AS marker,
                (SELECT system_identifier::text FROM pg_control_system()) AS cluster_system_identifier,
                current_setting('transaction_read_only') AS transaction_read_only,
                current_user AS effective_role,
                current_setting('port') AS port,inet_server_addr() IS NULL AS unix_socket
                FROM pg_database d WHERE d.datname=current_database()""", max_rows=1)
            ownership = ownership_rows[0] if ownership_rows else None
            target = contract["target"]
            if (ownership is None or any(ownership[k] != target[k] for k in (
                    "database", "database_oid", "marker", "cluster_system_identifier"))
                    or ownership["transaction_read_only"] != "on" or ownership["port"] != "55485"
                    or ownership["unix_socket"] is not True):
                raise ValueError("Actual target database ownership, cluster or local connection differs")
            migrations = m.query("actual_applied_migrations", "SELECT name,sha256 FROM dl_migrations.applied ORDER BY name")
            expected_migrations = {Path(k).name: v for k, v in contract["manifest"]["executable_files"].items()
                                   if "/migrations/" in k}
            if migrations is None or {r["name"]: r["sha256"] for r in migrations} != expected_migrations:
                raise ValueError("Actual additive migration history differs from frozen build")
            m.effective_role = ownership["effective_role"]
            database_size = measure_owned_database_size(m, ownership)
            connection.execute("SET LOCAL ROLE daylight_research_reader")
            m.effective_role = "daylight_research_reader"
            settings = m.query("frozen_postgresql_settings", "SELECT name,setting FROM pg_settings WHERE name=ANY(%s) ORDER BY name",
                               (sorted(contract["manifest"]["postgres_settings"]),))
            actual_settings = {r["name"]: r["setting"] for r in settings} if settings is not None else None
            m.proof("PostgreSQL settings remain bound to the persistent build",
                    actual_settings == contract["manifest"]["postgres_settings"], actual_settings,
                    contract["manifest"]["postgres_settings"], ["frozen_postgresql_settings"])
            totals = m.query("simultaneously_retained_populations", """SELECT
                (SELECT count(*) FROM dl_evidence.source_record) AS source_rows,
                (SELECT count(*) FROM dl_evidence.observation) AS projection_rows,
                (SELECT count(DISTINCT layer_id) FROM dl_control.source_snapshot) AS layers""")
            expected = [{"source_rows": RAW_ROWS, "projection_rows": PROJECTION_ROWS, "layers": 15}]
            m.proof("all fifteen selected populations are simultaneously retained", totals == expected,
                    totals, expected, ["simultaneously_retained_populations"])
            verify_metadata(m, contract)
            verify_units(m, contract)
            verify_domains(m, contract)
            verify_boundaries(m)
            sizes = m.query("actual_retained_relation_sizes", """SELECT n.nspname AS schema,c.relname AS relation,
                pg_relation_size(c.oid) AS heap_bytes,pg_indexes_size(c.oid) AS index_bytes,
                pg_total_relation_size(c.oid) AS total_bytes_including_toast
                FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname IN ('dl_control','dl_evidence','dl_review') AND c.relkind='r'
                ORDER BY n.nspname,c.relname""")
            connection.execute("SET LOCAL ROLE daylight_released_reader")
            m.effective_role = "daylight_released_reader"
            consumer = m.query("empty_consumer_released_view", """SELECT current_user AS effective_role,
                current_setting('transaction_read_only') AS transaction_read_only,
                (SELECT count(*) FROM dl_released.offerings) AS released_offerings""")
            expected = [{"effective_role": "daylight_released_reader", "transaction_read_only": "on", "released_offerings": 0}]
            m.proof("consumer role sees zero released offerings", consumer == expected, consumer, expected,
                    ["empty_consumer_released_view"])
            passed = all(p["passed"] for p in m.proofs) and all(q["success"] for q in m.queries)
            return {"schema": "daylight-local-full-verification/1", "database": DATABASE,
                    "build_id": contract["build_id"], "ownership": ownership, "migrations": migrations,
                    "creation_build_id": contract["target"].get("creation_build_id", contract["build_id"]),
                    "predecessor_material_units": len(contract["recovery"]["producers"]) if contract["recovery"] else 0,
                    "historical_jobs_retained": HISTORICAL_JOBS if contract["recovery"] else 0,
                    "historical_receipts_retained": ADOPTED_UNITS if contract["recovery"] else 0,
                    "physical_evidence_counted_once": True,
                    "verified_at": datetime.now(timezone.utc).isoformat(), "passed": passed,
                    "integrated_queries_verified": passed,
                    "proof_matrix": m.proofs, "query_measurements": m.queries,
                    "selected_units": UNIT_COUNT, "expected_source_rows": RAW_ROWS,
                    "expected_projection_rows": PROJECTION_ROWS, "relation_sizes": sizes, "database_size": database_size,
                    "query_execution": "one consistent REPEATABLE READ READ ONLY snapshot; fixed SELECTs; research/released read roles",
                    "plan_measurement": "EXPLAIN FORMAT JSON estimates plus independently timed actual SELECT; no ANALYZE replay",
                    "selected_source_files_replayed": False, "raw_payload_stream_rehashed": False,
                    "customer_rows_read": 0, "new_acceptance": False, "consumer_release_enabled": False,
                    "full_domain_models_complete": False, "cloud_deployed": False,
                    "limitations": ["Population/lineage/query verification is not semantic/source acceptance or personal applicability.",
                                    "Raw source stream digests are reconciled to exact sizing/database receipts; original sources are not replayed.",
                                    "Existing frozen obligations, aliases, unknowns and source-use/output holds remain research evidence."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repository = args.repository.resolve()
    packet = (args.packet or repository / PACKET).resolve()
    summary = (args.summary or repository / SUMMARY).resolve()
    if not packet.is_relative_to(repository) or not summary.is_relative_to(repository):
        raise ValueError("Controls must be inside the authorized repository")
    if args.output.exists():
        raise ValueError("Verification output already exists; choose a fresh path")
    try:
        result = verify(repository, packet, summary, os.environ["DAYLIGHT_DATA_DATABASE_URL"])
    except Exception as error:
        result = {"schema": "daylight-local-full-verification/1", "database": DATABASE, "passed": False,
                  "error_type": type(error).__name__, "sqlstate": getattr(error, "sqlstate", None),
                  "no_database_mutations": True, "new_acceptance": False, "consumer_release_enabled": False}
    write_report(args.output.resolve(), result)
    print(json.dumps({"passed": result["passed"], "report": str(args.output.resolve())}), flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
