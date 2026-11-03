"""Measure full source-table populations in disposable PostgreSQL fixture DBs.

Only newly created random daylight_sizing_*_test databases are dropped. Existing
research/app databases and sealed inputs are never changed. Receipts are sizing
evidence, not durable all-layer integration, acceptance or consumer release.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
from importlib import import_module
from itertools import chain, groupby, islice
import json
import os
from pathlib import Path
import resource
import shutil
import time
import uuid

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.types.json import Jsonb

from daylight_data.adapters.common import canonical_json, digest_json
from daylight_data.database import connect, migrate
from daylight_data.ingestion.jobs import claim, enqueue, heartbeat, require_lease
from daylight_data.ingestion.loader import copy_batch, insert_projections, register_source
from daylight_data.storage import FileArchive


def disk_guard(root, reserve):
    free = shutil.disk_usage(root).free
    if free < reserve:
        raise RuntimeError(f"Local sizing stopped at disk reserve: free_bytes={free}, reserve_bytes={reserve}")
    return free


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("x") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def relation_sizes(connection):
    return [{"schema": row[0], "table": row[1], "heap_bytes": row[2],
             "index_bytes": row[3], "total_bytes_including_toast": row[4]}
            for row in connection.execute("""SELECT schemaname,relname,
                pg_relation_size(relid),pg_indexes_size(relid),pg_total_relation_size(relid)
                FROM pg_statio_user_tables ORDER BY schemaname,relname""")]


def project_batch(module, batch):
    for row in batch:
        result = module.project_record(row)
        if hasattr(result, "source"):
            yield result
        else:
            yield from result


def bounded_batches(rows, max_rows, max_payload_bytes=8 * 1024**2):
    batch, size = [], 0
    for row in rows:
        width = len(canonical_json(row.raw).encode())
        if width > 32 * 1024**2:
            raise ValueError("Individual sizing row exceeds explicit 32MiB memory bound")
        if batch and (len(batch) >= max_rows or size + width > max_payload_bytes):
            yield batch
            batch, size = [], 0
        batch.append(row)
        size += width
    if batch:
        yield batch


def ordinal_windows(rows, window_rows):
    """Disjoint windows preserve original ordinals and are fully consumed in order."""
    while True:
        first = next(rows, None)
        if first is None:
            return
        window = chain([first], islice(rows, window_rows - 1))
        yield first, window
        if next(window, None) is not None:
            raise ValueError("Sizing window was not completely consumed")


def file_manifest(repository):
    package = repository / "infrastructure/daylight-data"
    paths = list((package / "src").rglob("*.py")) + list((package / "migrations").glob("*.sql"))
    paths += [Path(__file__).resolve(), package / "requirements.lock"]
    return {str(path.relative_to(repository)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(paths)}


def require_frozen_code(args):
    if file_manifest(args.repository) != args.startup_files:
        raise RuntimeError("Executable/schema files changed during sizing; freeze code and restart")


def measure_unit(admin, admin_dsn, module, rows, first, args, archive):
    if not getattr(args, "contract_hash", None):
        raise ValueError("A frozen code/schema/settings sizing contract is required")
    binding = {"layer_id": first.layer_id, "source_path": first.source_path,
               "source_sha256": first.source_sha256, "source_table": first.source_table,
               "derivation_id": first.derivation_id, "adapter_code_sha256": first.adapter_code_sha256,
               "sizing_contract_sha256": args.contract_hash,
               "window_first_ordinal": first.source_row_ordinal,
               "window_row_limit": args.window_rows}
    require_frozen_code(args)
    key = digest_json(binding)
    destination = args.output / "units" / (key + ".json")
    if destination.exists():
        previous = json.loads(destination.read_text())
        if previous.get("binding") != binding or not previous.get("population_complete"):
            raise ValueError("Existing sizing receipt has incompatible or incomplete binding")
        digest, count = hashlib.sha256(), 0
        for row in rows:
            count += 1
            digest.update(canonical_json([row.record_id, row.raw]).encode() + b"\n")
        if count != previous["input_rows"] or digest.hexdigest() != previous["stream_sha256"]:
            raise ValueError("Previously measured unit differs from source stream")
        require_frozen_code(args)
        return previous
    database_name = "daylight_sizing_" + uuid.uuid4().hex + "_test"
    initial_free = disk_guard(args.repository, args.reserve_bytes + 128 * 1024**2)
    admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(database_name)))
    dsn = make_conninfo(admin_dsn, dbname=database_name)
    connection = None
    started = time.monotonic()
    state = {"binding": binding, "database": database_name, "population_complete": False,
             "input_rows": 0, "disposable_database_only": True}
    try:
        connection = connect(dsn)
        migrate(connection)
        baseline = connection.execute("SELECT pg_database_size(current_database())").fetchone()[0]
        baseline_sizes = relation_sizes(connection)
        baseline_evidence = sum(row["total_bytes_including_toast"] for row in baseline_sizes if row["schema"] == "dl_evidence")
        connection.execute("SET ROLE daylight_writer")
        job_id = enqueue(connection, key, binding, source_id="sealed-local:" + first.layer_id)
        lease = claim(connection, "local-sizing", lease_seconds=3600, job_id=job_id)
        if lease is None:
            raise RuntimeError("Unable to obtain local sizing lease")
        register_source(connection, archive, args.repository, first)
        disk_guard(args.repository, args.reserve_bytes)
        offset = first.source_row_ordinal - 1
        if offset:
            # Cursor position is the beginning of this declared source window.
            # No prefix rows are claimed retained in this disposable database.
            connection.execute("""INSERT INTO dl_control.checkpoint(job_id,derivation_id,source_table,
                last_ordinal,retained_rows,fence) VALUES(%s,%s,%s,%s,0,%s)""",
                (job_id,first.derivation_id,first.source_table,offset,lease.fence))
        digest, projections, count, minimum_free, quarantined = hashlib.sha256(), Counter(), 0, initial_free, 0
        for batch in bounded_batches(rows, args.batch_size):
            minimum_free = min(minimum_free, disk_guard(args.repository, args.reserve_bytes + 512 * 1024**2))
            with connection.transaction():
                copy_batch(connection, lease, batch)
                if offset:
                    # Commit the source cursor and the truthful window row count
                    # together; never claim that the omitted prefix is stored.
                    connection.execute("UPDATE dl_control.checkpoint SET retained_rows=last_ordinal-%s WHERE job_id=%s", (offset,job_id))
            minimum_free = min(minimum_free, disk_guard(args.repository, args.reserve_bytes))
            projected = insert_projections(connection, project_batch(module, batch), args.batch_size)
            minimum_free = min(minimum_free, disk_guard(args.repository, args.reserve_bytes))
            projections.update(projected)
            count += len(batch)
            state["complete_batch_rows"] = count
            for row in batch:
                quarantined += row.disposition.startswith("quarantined")
                digest.update(canonical_json([row.record_id, row.raw]).encode() + b"\n")
            heartbeat(connection, lease, lease_seconds=3600)
            if count % (args.batch_size * 50) == 0:
                print(json.dumps({"progress": binding, "rows": count,
                                  "free_gib": round(shutil.disk_usage(args.repository).free / 1024**3, 2)}), flush=True)
        with connection.transaction():
            require_lease(connection, lease)
            actual = connection.execute("SELECT count(*) FROM dl_evidence.source_record").fetchone()[0]
            projected_actual = connection.execute("SELECT count(*) FROM dl_evidence.observation").fetchone()[0]
            if count != actual or sum(projections.values()) != projected_actual:
                raise ValueError("Sizing source/projection population differs from stored rows")
            connection.execute("""INSERT INTO dl_control.ingest_receipt(job_id,input_rows,retained_rows,
                quarantined_rows,stream_sha256,controls) VALUES(%s,%s,%s,%s,%s,%s)""",
                (job_id, count, actual, quarantined, digest.hexdigest(), Jsonb({first.source_table: count})))
            connection.execute("UPDATE dl_control.job SET state='complete',finished_at=clock_timestamp(),lease_until=NULL WHERE job_id=%s", (job_id,))
        connection.execute("RESET ROLE")
        connection.execute("ANALYZE dl_evidence.source_record")
        connection.execute("ANALYZE dl_evidence.observation")
        sizes = relation_sizes(connection)
        evidence_bytes = sum(row["total_bytes_including_toast"] for row in sizes if row["schema"] == "dl_evidence")
        require_frozen_code(args)
        state.update(population_complete=True, input_rows=count, retained_rows=actual,
                     window_first_ordinal=first.source_row_ordinal,
                     window_last_ordinal=first.source_row_ordinal+count-1,
                     quarantined_rows=quarantined,
                     projection_counts=dict(projections), stream_sha256=digest.hexdigest(),
                     schema_baseline_database_bytes=baseline,
                     baseline_relation_sizes=baseline_sizes,
                     empty_evidence_baseline_bytes=baseline_evidence,
                     net_evidence_relation_bytes=evidence_bytes-baseline_evidence,
                     database_bytes=connection.execute("SELECT pg_database_size(current_database())").fetchone()[0],
                     evidence_relation_bytes=evidence_bytes, relation_sizes=sizes,
                     elapsed_seconds=round(time.monotonic() - started, 3),
                     process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                     minimum_observed_free_bytes=minimum_free,
                     observed_at=datetime.now(timezone.utc).isoformat(),
                     new_acceptance=False, consumer_release_enabled=False,
                     limitation="Measured isolated contiguous source windows; summed net relation bytes estimate consolidated storage and exclude consolidated index layout changes, future models, WAL, workspace and backup retention")
        atomic_json(destination, state)
        print(json.dumps({"measured": binding, "rows": count, "evidence_bytes": evidence_bytes}), flush=True)
        return state
    except BaseException as error:
        state.update(error_type=type(error).__name__, error=str(error),
                     observed_at=datetime.now(timezone.utc).isoformat())
        failure = args.output / "failures" / (key + "-" + uuid.uuid4().hex[:8] + ".json")
        atomic_json(failure, state)
        raise
    finally:
        if connection is not None:
            connection.close()
        # The identifier was created in this function and is never caller supplied.
        admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database_name)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layers", nargs="+", required=True)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--reserve-gib", type=float, default=7)
    parser.add_argument("--window-rows", type=int, default=250000)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 5000 or args.reserve_gib < 7 or not 1 <= args.window_rows <= 250000:
        parser.error("Batch limit 1..5000 and disk reserve >=7GiB required")
    args.repository = args.repository.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    for directory in ("units", "failures"):
        (args.output / directory).mkdir(exist_ok=True)
    args.reserve_bytes = int(args.reserve_gib * 1024**3)
    args.startup_files = file_manifest(args.repository)
    dsn = os.environ["DAYLIGHT_DATA_TEST_DSN"]
    info = conninfo_to_dict(dsn)
    if not info.get("dbname", "").endswith("_test") or not info.get("host", "").startswith(str(args.repository / "infrastructure/daylight-data/.state/socket")):
        raise ValueError("Explicit project-local *_test PostgreSQL target required")
    archive = FileArchive(args.archive, reserve_bytes=args.reserve_bytes)
    with psycopg.connect(dsn, autocommit=True) as admin:
        settings = dict(admin.execute("SELECT name,setting FROM pg_settings WHERE name = ANY(%s)",
            (["server_version", "shared_buffers", "work_mem", "maintenance_work_mem", "wal_level",
              "full_page_writes", "wal_compression", "wal_segment_size", "block_size", "max_wal_size",
              "default_toast_compression"],)))
        contract = {"schema": "daylight-local-sizing-contract/4", "files": args.startup_files,
                    "postgres_settings": settings, "batch_rows": args.batch_size,
                    "batch_payload_bytes": 8 * 1024**2, "reserve_bytes": args.reserve_bytes,
                    "window_rows": args.window_rows}
        args.contract_hash = digest_json(contract)
        contract_path = args.output / ("run-contract-" + args.contract_hash + ".json")
        if not contract_path.exists():
            atomic_json(contract_path, contract)
        for layer in args.layers:
            if layer not in {f"L{i:02}" for i in range(1, 16)}:
                raise ValueError("Unsupported layer")
            module = import_module("daylight_data.adapters." + layer.lower())
            receipts = []
            table_controls = []
            stream = module.iter_records(args.repository)
            try:
                for unit, rows in groupby(stream, key=lambda row: (row.source_path, row.source_table)):
                    table_digest, table_count = hashlib.sha256(), [0]
                    def tracked_rows():
                        for row in rows:
                            table_count[0] += 1
                            if row.source_row_ordinal != table_count[0]:
                                raise ValueError("Source table has a gap, duplicate or reordered ordinal")
                            table_digest.update(canonical_json([row.record_id,row.raw]).encode() + b"\n")
                            yield row
                    windows = []
                    for first, window in ordinal_windows(tracked_rows(), args.window_rows):
                        result = measure_unit(admin, dsn, module, window, first, args, archive)
                        receipts.append(result)
                        windows.append({"first": result["window_first_ordinal"],
                                        "last": result["window_last_ordinal"],
                                        "rows": result["input_rows"]})
                    previous = 0
                    for window in windows:
                        if window["first"] != previous+1 or window["last"]-window["first"]+1 != window["rows"]:
                            raise ValueError("Source windows overlap or have an unexplained gap")
                        previous = window["last"]
                    if previous != table_count[0]:
                        raise ValueError("Source window coverage differs from full source stream")
                    table_controls.append({"source_path":unit[0], "source_table":unit[1],
                        "source_rows":table_count[0], "ordered_full_stream_sha256":table_digest.hexdigest(),
                        "windows":windows, "unexplained_loss":0})
            finally:
                stream.close()
            summary = {"layer_id": layer, "sizing_populations_complete": True,
                       "unit_count": len(receipts), "source_rows": sum(r["input_rows"] for r in receipts),
                       "measured_evidence_relation_bytes": sum(r["evidence_relation_bytes"] for r in receipts),
                       "net_evidence_relation_bytes": sum(r["net_evidence_relation_bytes"] for r in receipts),
                       "sizing_contract_sha256": args.contract_hash,
                       "units": [r["binding"] for r in receipts], "new_acceptance": False,
                       "source_table_population_controls":table_controls,
                       "full_typed_integration_complete": False,
                       "observed_at": datetime.now(timezone.utc).isoformat()}
            if hasattr(module, "sizing_dispositions"):
                summary["non_domain_source_table_dispositions"] = module.sizing_dispositions(args.repository)
            if layer == "L03":
                native = module.sizing_controls(args.repository)
                transported = {(c["source_path"],c["source_table"]):c["source_rows"] for c in table_controls}
                for source in native:
                    for table,count in source["native_table_counts"].items():
                        if transported.get((source["source_path"],table),0) != count:
                            raise ValueError("Frozen L03 native table differs from full transported population")
                semantic = next(source["semantic_inventory_controls"] for source in native if "semantic_inventory_controls" in source)
                if semantic["canonical_kind_counts"] != {"claim":143505,"condition":249065}:
                    raise ValueError("Frozen L03 r9 semantic denominator differs from required143505/249065 controls")
                if (semantic["semantic_kind_counts"] != {"claim":143679,"condition":249065}
                    or semantic["semantic_representation_rows"] != 392744
                    or semantic["canonical_mapping_rows"] != 392744
                    or semantic["canonical_identity_rows"] != 392570
                    or semantic["source_identity_alias_rows"] != 174
                    or semantic["work_obligation_rows"] != 230
                    or semantic["missing_canonical_mappings"] != 0):
                    raise ValueError("Frozen L03 r9 representations, aliases or follow-up accounting differs")
                projected = Counter()
                for window in receipts:
                    if window["binding"]["source_table"] == "semantic_unit" and "/semantic-inventory-r9/" in window["binding"]["source_path"]:
                        projected.update(window["projection_counts"])
                if dict(projected) != {"ma_semantic_claim_representation":143679,"ma_semantic_condition_representation":249065}:
                    raise ValueError("Frozen L03 r9 semantic representation projection counts differ")
                summary["native_inventory_controls"] = native
                summary["semantic_inventory_controls"] = semantic
                summary["frozen_r9_obligations"] = semantic["canonical_kind_counts"]
            require_frozen_code(args)
            target = args.output / (layer + ".json")
            if target.exists():
                target = args.output / (layer + "-" + uuid.uuid4().hex[:8] + ".json")
            atomic_json(target, summary)
            print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
