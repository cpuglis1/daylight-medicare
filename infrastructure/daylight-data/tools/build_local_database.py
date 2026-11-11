"""Retain the exact fifteen-layer sizing populations in one owned local research DB.

No database is dropped. Raw records, projections and a window's checkpoint commit
together. Resume binds the database's OID/marker and frozen build manifest, then
reconciles database receipts and counts rather than trusting filesystem receipts.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
from importlib import import_module
from itertools import groupby, islice
import json
import os
from pathlib import Path
import re
import resource
import shutil
import time
import uuid

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.types.json import Jsonb

from benchmark_local_layers import bounded_batches, project_batch, relation_sizes
from daylight_data.adapters.common import adapter_code_sha256, canonical_json, digest_json, sha256_file
from daylight_data.database import connect, migrate
from daylight_data.ingestion.jobs import claim, enqueue, heartbeat, require_lease
from daylight_data.ingestion.loader import copy_batch, insert_exact, insert_projections, register_source
from daylight_data.storage import FileArchive


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("x") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def disk_guard(repository, reserve_bytes, margin=0):
    free = shutil.disk_usage(repository).free
    if free < reserve_bytes + margin:
        raise RuntimeError(f"Persistent import paused at disk reserve: free={free}, required={reserve_bytes+margin}")
    return free


def validate_target(admin_dsn, target, repository):
    info = conninfo_to_dict(admin_dsn)
    expected = (repository / "infrastructure/daylight-data/.state/socket").resolve()
    if Path(info.get("host", "")).resolve() != expected or info.get("hostaddr"):
        raise ValueError("An explicit exact project-local Unix socket is required")
    if info.get("port") != "55485" or info.get("dbname") != "daylight_data_test":
        raise ValueError("The preserved project-local admin database/port must be explicit")
    if not re.fullmatch(r"daylight_research_2026_r[1-9][0-9]{0,18}", target):
        raise ValueError("A new explicitly numbered daylight_research_2026_rN target is required")
    return info


def executable_files(repository):
    package = repository / "infrastructure/daylight-data"
    paths = list((package / "src").rglob("*.py")) + list((package / "migrations").glob("*.sql"))
    paths += [package / "requirements.lock", Path(__file__).resolve(),
              package / "tools/benchmark_local_layers.py", package / "config/source-composition.2026.json",
              package / "config/profile-contract.2026.json"]
    return {str(p.relative_to(repository)): sha256_file(p) for p in sorted(paths)}


def load_selection(repository, summary_path):
    summary = json.loads(summary_path.read_text())
    if summary["layers_measured"] != 15 or summary["new_acceptance"] or summary["source_rows"] != 17767179:
        raise ValueError("Exact reviewed fifteen-layer sizing summary is required")
    inputs = {str(summary_path.relative_to(repository)): sha256_file(summary_path)}
    selected = {}
    for layer in summary["layers"]:
        layer_id = layer["layer_id"]
        layer_path = repository / layer["layer_receipt"]
        if sha256_file(layer_path) != layer["layer_receipt_sha256"]:
            raise ValueError("Layer sizing receipt differs")
        inputs[layer["layer_receipt"]] = layer["layer_receipt_sha256"]
        items = []
        for ref in layer["unit_receipts"]:
            path = repository / ref["path"]
            if sha256_file(path) != ref["sha256"]:
                raise ValueError("Selected sizing unit receipt differs")
            unit = json.loads(path.read_text())
            binding = unit["binding"]
            if (not unit["population_complete"] or binding["layer_id"] != layer_id
                or binding["adapter_code_sha256"] != adapter_code_sha256(layer_id)):
                raise ValueError("Selected population or current layer adapter differs")
            first = binding.get("window_first_ordinal", 1)
            item = {"binding": binding, "first": first, "last": first+unit["input_rows"]-1,
                    "rows": unit["input_rows"], "projection_counts": unit["projection_counts"],
                    "stream_sha256": unit["stream_sha256"], "quarantined_rows": unit["quarantined_rows"],
                    "sizing_receipt_path": ref["path"], "sizing_receipt_sha256": ref["sha256"]}
            item["slot"] = digest_json(item)
            items.append(item)
            inputs[ref["path"]] = ref["sha256"]
        groups = defaultdict(list)
        for item in items:
            b = item["binding"]
            groups[(b["source_path"],b["source_table"])].append(item)
        for group in groups.values():
            cursor = 0
            for item in group:
                if item["first"] != cursor+1 or item["rows"] <= 0:
                    raise ValueError("Selected windows have a gap, overlap or wrong order")
                cursor = item["last"]
        if sum(i["rows"] for i in items) != layer["source_rows"]:
            raise ValueError("Selected layer source count differs")
        if sum(sum(i["projection_counts"].values()) for i in items) != layer["projection_rows"]:
            raise ValueError("Selected layer projection count differs")
        selected[layer_id] = dict(groups)
    if set(selected) != {f"L{i:02}" for i in range(1,16)}:
        raise ValueError("All fifteen exact layer selections are required")
    return summary, selected, inputs


def require_frozen(repository, manifest):
    if executable_files(repository) != manifest["executable_files"]:
        raise RuntimeError("Build executable/schema/composition changed; preserve this target and use a new revision")
    for relative, expected in {**manifest["selected_receipt_files"], **manifest.get("recovery_receipt_files", {})}.items():
        if sha256_file(repository / relative) != expected:
            raise RuntimeError("Selected sizing evidence changed during persistent build")


def load_predecessor(repository, packet, selection, inputs, sources):
    """Pin an explicit recovery revision; never silently rewrite a frozen build."""
    packet = packet.resolve()
    if not packet.is_relative_to(repository) or packet.is_symlink():
        raise ValueError("Predecessor must be an explicit local evidence packet")
    old_manifest = json.loads((packet / "BUILD_MANIFEST.json").read_text())
    old_target = json.loads((packet / "TARGET.json").read_text())
    checkpoint = json.loads((packet / "LOGICAL_CHECKPOINT.json").read_text())
    durability = json.loads((packet / "CHECKPOINT_DURABILITY.json").read_text())
    if (digest_json(old_manifest) != old_target["build_id"]
            or old_target["marker"] != "daylight-local-full/1:" + old_target["build_id"]
            or checkpoint["schema"] != "daylight-interrupted-readonly-logical-checkpoint/1"
            or checkpoint["target"] != old_target or checkpoint["passed"] is not True
            or checkpoint["consistent_exported_readonly_snapshot"] is not True
            or checkpoint["full_archive_decoded_without_execution"] is not True
            or checkpoint["database_modified"] is not False or checkpoint["service_stop_or_restart"] is not False
            or durability.get("passed") is not True
            or durability.get("logical_checkpoint_sha256") != sha256_file(packet / "LOGICAL_CHECKPOINT.json")
            or durability.get("dump_sha256") != checkpoint["sha256"]
            or old_manifest["selected_receipt_files"] != inputs or old_manifest["selected_source_files"] != sources):
        raise ValueError("Predecessor identity, source scope or read-only checkpoint differs")
    current = executable_files(repository)
    changed = {p for p in set(current) | set(old_manifest["executable_files"])
               if current.get(p) != old_manifest["executable_files"].get(p)}
    driver = "infrastructure/daylight-data/tools/build_local_database.py"
    if changed != {driver}:
        raise ValueError("This recovery permits only the explicitly reviewed driver transport change")
    dump = repository / checkpoint["path"]
    if (dump.is_symlink() or not dump.resolve().is_relative_to(repository)
            or dump.stat().st_size != checkpoint["bytes"] or sha256_file(dump) != checkpoint["sha256"]):
        raise ValueError("Preserved predecessor logical checkpoint bytes differ")
    files = {str((packet / name).relative_to(repository)): sha256_file(packet / name)
             for name in ("TARGET.json", "BUILD_MANIFEST.json", "LOGICAL_CHECKPOINT.json",
                          "LOGICAL_CHECKPOINT_TOC.txt", "CHECKPOINT_DURABILITY.json")}
    selected = {i["slot"]: i for groups in selection.values() for items in groups.values() for i in items}
    completed = {}
    for path in sorted((packet / "units").glob("*.json")):
        receipt = json.loads(path.read_text())
        item = selected.get(receipt["selected_slot"])
        if (item is None or receipt["build_id"] != old_target["build_id"]
                or receipt["binding"] != item["binding"] or receipt["source_rows"] != item["rows"]
                or receipt["projection_counts"] != item["projection_counts"]
                or receipt["stream_sha256"] != item["stream_sha256"]
                or receipt["first_ordinal"] != item["first"] or receipt["last_ordinal"] != item["last"]
                or receipt["quarantined_rows"] != item["quarantined_rows"]):
            raise ValueError("A predecessor completed window differs from the exact selection")
        relative = str(path.relative_to(repository))
        files[relative] = sha256_file(path)
        completed[item["slot"]] = {"build_id": old_target["build_id"], "job_id": receipt["job_id"],
                                   "unit_receipt_path": relative, "unit_receipt_sha256": files[relative]}
    if len(completed) != checkpoint["counts"]["complete_jobs"] or len(completed) != 122:
        raise ValueError("Predecessor completed receipt population differs")
    binding = {"packet": str(packet.relative_to(repository)), "build_id": old_target["build_id"],
               "target_sha256": files[str((packet / "TARGET.json").relative_to(repository))],
               "manifest_sha256": files[str((packet / "BUILD_MANIFEST.json").relative_to(repository))],
               "logical_checkpoint_path": str((packet / "LOGICAL_CHECKPOINT.json").relative_to(repository)),
               "logical_checkpoint_sha256": files[str((packet / "LOGICAL_CHECKPOINT.json").relative_to(repository))],
               "ownership": old_target, "historical_jobs": checkpoint["counts"]["jobs"],
               "historical_receipts": checkpoint["counts"]["receipts"],
               "interrupted_job": checkpoint["interrupted_job"],
               "interrupted_layer_id": selected[checkpoint["interrupted_job"]["payload"]["selected_slot"]]["binding"]["layer_id"],
               "interrupted_checkpoints": checkpoint["interrupted_checkpoints"],
               "preserved_dump": {"path": checkpoint["path"], "sha256": checkpoint["sha256"], "bytes": checkpoint["bytes"]},
               "transport_change": {"path": driver, "before_sha256": old_manifest["executable_files"][driver],
                                    "after_sha256": current[driver]},
               "source_adapter_derivations_changed": False, "new_acceptance": False}
    return binding, completed, files


def verify_selected_sources(repository, selection):
    sources = {}
    for groups in selection.values():
        for items in groups.values():
            for item in items:
                binding = item["binding"]
                path, digest = binding["source_path"],binding["source_sha256"]
                if path in sources and sources[path] != digest:
                    raise ValueError("Selected source path has conflicting frozen hashes")
                sources[path] = digest
    for relative,expected in sources.items():
        path = repository/relative
        if path.is_symlink() or not path.resolve().is_relative_to(repository) or sha256_file(path) != expected:
            raise ValueError("Selected original source is missing, changed or outside the approved repository: "+relative)
    return sources


def database_window_counts(connection, item):
    binding = item["binding"]
    values = (binding["derivation_id"],binding["source_table"],item["first"],item["last"])
    raw = connection.execute("""SELECT count(*) FROM dl_evidence.source_record
        WHERE derivation_id=%s AND source_table=%s AND source_row_ordinal BETWEEN %s AND %s""",values).fetchone()[0]
    projections = dict(connection.execute("""SELECT entity_type,count(*) FROM dl_evidence.observation
        WHERE derivation_id=%s AND source_table=%s AND source_row_ordinal BETWEEN %s AND %s
        GROUP BY entity_type""",values))
    return raw, projections


def check_checkpoint(checkpoint, item):
    offset = item["first"]-1
    if checkpoint is None:
        return offset
    last, retained = checkpoint[:2]
    if not offset <= last <= item["last"] or retained != last-offset:
        raise ValueError("Persisted window checkpoint is outside its exact declared population")
    return last


def unit_controls(item, build_id, manifest=None):
    controls = {"build_id":build_id,"selected_slot":item["slot"],"source_path":item["binding"]["source_path"],
            "source_table":item["binding"]["source_table"],"first_ordinal":item["first"],"last_ordinal":item["last"],
            "projection_counts":item["projection_counts"],"sizing_receipt_sha256":item["sizing_receipt_sha256"],
            "new_acceptance":False}
    producer = (manifest or {}).get("predecessor_completed_units", {}).get(item["slot"])
    if producer:
        controls["material_execution"] = producer
    return controls


def adopt_completed_unit(connection, item, manifest, args):
    """Reconcile old material under a new execution without copying evidence."""
    require_frozen(args.repository,manifest)
    disk_guard(args.repository,args.reserve_bytes)
    producer = manifest["predecessor_completed_units"][item["slot"]]
    build_id = digest_json(manifest)
    binding = item["binding"]
    require_source_access(connection, binding["layer_id"])
    prior = connection.execute("""SELECT j.state,r.input_rows,r.retained_rows,r.quarantined_rows,
        r.stream_sha256,r.controls,c.last_ordinal,c.retained_rows,c.fence,j.fence,j.payload,j.source_id,j.idempotency_key
        FROM dl_control.job j JOIN dl_control.ingest_receipt r USING(job_id)
        JOIN dl_control.checkpoint c USING(job_id) WHERE j.job_id=%s
        AND c.derivation_id=%s AND c.source_table=%s""",
        (producer["job_id"], binding["derivation_id"], binding["source_table"])).fetchall()
    expected = ("complete", item["rows"], item["rows"], item["quarantined_rows"], item["stream_sha256"],
                unit_controls(item, producer["build_id"]), item["last"], item["rows"])
    if (len(prior) != 1 or tuple(prior[0][:8]) != expected or prior[0][8] != prior[0][9]
            or prior[0][10] != unit_controls(item,producer["build_id"])
            or prior[0][11] != "sealed-local:" + binding["layer_id"]
            or prior[0][12] != digest_json(["persistent-local-full/1",producer["build_id"],item["slot"]])
            or database_window_counts(connection,item) != (item["rows"],item["projection_counts"])):
        raise ValueError("Predecessor database receipt, checkpoint or physical window differs")
    controls = unit_controls(item,build_id,manifest)
    key = digest_json(["persistent-local-full/1",build_id,item["slot"]])
    job_id = enqueue(connection,key,controls,source_id="sealed-local:"+binding["layer_id"])
    state = connection.execute("SELECT state FROM dl_control.job WHERE job_id=%s",(job_id,)).fetchone()[0]
    if state != "complete":
        lease = claim(connection,args.owner,3600,job_id=job_id)
        if lease is None:
            raise ValueError("Current adoption job has a conflicting lease or stop")
        try:
            with connection.transaction():
                require_lease(connection,lease)
                require_source_access(connection,binding["layer_id"])
                connection.execute("""INSERT INTO dl_control.checkpoint(job_id,derivation_id,source_table,
                    last_ordinal,retained_rows,fence) VALUES(%s,%s,%s,%s,%s,%s)""",
                    (job_id,binding["derivation_id"],binding["source_table"],item["last"],item["rows"],lease.fence))
                connection.execute("""INSERT INTO dl_control.ingest_receipt(job_id,input_rows,retained_rows,
                    quarantined_rows,stream_sha256,controls) VALUES(%s,%s,%s,%s,%s,%s)""",
                    (job_id,item["rows"],item["rows"],item["quarantined_rows"],item["stream_sha256"],Jsonb(controls)))
                connection.execute("UPDATE dl_control.job SET state='complete',finished_at=clock_timestamp(),lease_until=NULL WHERE job_id=%s",(job_id,))
        except BaseException:
            connection.execute("""UPDATE dl_control.job SET lease_until=clock_timestamp()-interval '1 second'
                WHERE job_id=%s AND owner_id=%s AND fence=%s AND state='running'""",
                (job_id,lease.owner_id,lease.fence))
            raise
    current = connection.execute("""SELECT r.input_rows,r.retained_rows,r.quarantined_rows,r.stream_sha256,r.controls,
        c.last_ordinal,c.retained_rows,c.fence,j.fence FROM dl_control.job j
        JOIN dl_control.ingest_receipt r USING(job_id) JOIN dl_control.checkpoint c USING(job_id)
        WHERE j.job_id=%s AND c.derivation_id=%s AND c.source_table=%s""",
        (job_id,binding["derivation_id"],binding["source_table"])).fetchall()
    if (len(current) != 1 or tuple(current[0][:7]) != (
            item["rows"],item["rows"],item["quarantined_rows"],item["stream_sha256"],controls,item["last"],item["rows"])
            or current[0][7] != current[0][8]):
        raise ValueError("Current adoption receipt/checkpoint differs")
    print(json.dumps({"adopted_slot":item["slot"],"job_id":job_id,"material_job_id":producer["job_id"],
                      "source_rows_duplicated":0}),flush=True)
    return job_id


def current_job_counts(connection, build_id):
    return connection.execute("""SELECT count(*),count(*) FILTER(WHERE state<>'complete')
        FROM dl_control.job WHERE payload->>'build_id'=%s""",(build_id,)).fetchone()


def require_source_access(connection, layer_id):
    # The existing local CLI's documented stop identity is source-scoped at the
    # selected layer: sealed-local:Lxx. Never silently ignore an unmapped STOP.
    known = {"sealed-local:"+f"L{i:02}" for i in range(1,16)}
    for source_id,state in connection.execute("SELECT source_id,state FROM dl_control.source_access_state WHERE state IN ('held','stopped')"):
        if source_id not in known:
            raise RuntimeError("Unmapped source STOP requires an exact policy mapping before this build continues")
        if source_id == "sealed-local:"+layer_id:
            raise RuntimeError("Source access is held/stopped; preserved data is not import permission")


def insert_atomic_projections(connection, projections, batch_size):
    """Keep the sealed serializer unchanged while bounding temporary stage life.

    One source batch can expand to several projection batches. ON COMMIT DROP
    would otherwise keep the first staging pair alive until the caller's outer
    raw/projection/checkpoint transaction commits. Each sealed serializer call
    receives at most one chunk, then only its own pg_temp tables are removed.
    """
    if not 1 <= batch_size <= 50000:
        raise ValueError("Invalid atomic projection chunk size")
    iterator = iter(projections)
    while chunk := list(islice(iterator, batch_size)):
        insert_projections(connection, chunk, batch_size)
        connection.execute("DROP TABLE pg_temp.projection_batch,pg_temp.offering_batch")


def run_unit(connection, module, rows, item, manifest, args, archive):
    binding, build_id = item["binding"], digest_json(manifest)
    require_frozen(args.repository, manifest)
    require_source_access(connection,binding["layer_id"])
    controls = unit_controls(item,build_id,manifest)
    job_key = digest_json(["persistent-local-full/1",build_id,item["slot"]])
    job_id = enqueue(connection,job_key,controls,source_id="sealed-local:"+binding["layer_id"])
    state = connection.execute("SELECT state FROM dl_control.job WHERE job_id=%s",(job_id,)).fetchone()[0]
    complete = state == "complete"
    lease = None if complete else claim(connection,args.owner,3600,job_id=job_id)
    if not complete and lease is None:
        raise RuntimeError("Exact build job is held/stopped or has another live owner")
    digest, projections, count, quarantine = hashlib.sha256(), Counter(), 0, 0
    started = time.monotonic()
    registered = False
    try:
        checkpoint = connection.execute("""SELECT last_ordinal,retained_rows FROM dl_control.checkpoint
            WHERE job_id=%s AND derivation_id=%s AND source_table=%s""",
            (job_id,binding["derivation_id"],binding["source_table"])).fetchone()
        cursor = check_checkpoint(checkpoint,item)
        minimum_free = disk_guard(args.repository,args.reserve_bytes,512*1024**2)
        for batch in bounded_batches(rows,args.batch_size):
            for row in batch:
                if (row.layer_id != binding["layer_id"] or row.source_path != binding["source_path"]
                    or row.source_table != binding["source_table"] or row.derivation_id != binding["derivation_id"]
                    or row.source_sha256 != binding["source_sha256"]
                    or row.adapter_code_sha256 != binding["adapter_code_sha256"]
                    or row.source_row_ordinal != item["first"]+count):
                    raise ValueError("Actual source identity/order differs from the exact selected receipt")
                count += 1
                quarantine += row.disposition.startswith("quarantined")
                digest.update(canonical_json([row.record_id,row.raw]).encode()+b"\n")
            projected = list(project_batch(module,batch))
            projections.update(p.entity_type for p in projected)
            fresh = [r for r in batch if r.source_row_ordinal > cursor]
            if fresh:
                if complete:
                    raise ValueError("Completed job has an incomplete checkpoint")
                if not registered:
                    register_source(connection,archive,args.repository,batch[0])
                    registered = True
                minimum_free = min(minimum_free,disk_guard(args.repository,args.reserve_bytes,512*1024**2))
                with connection.transaction():
                    require_lease(connection,lease)
                    require_source_access(connection,binding["layer_id"])
                    if checkpoint is None and item["first"] > 1:
                        connection.execute("""INSERT INTO dl_control.checkpoint(job_id,derivation_id,source_table,
                            last_ordinal,retained_rows,fence) VALUES(%s,%s,%s,%s,0,%s)""",
                            (job_id,binding["derivation_id"],binding["source_table"],item["first"]-1,lease.fence))
                        checkpoint = (item["first"]-1,0)
                    copy_batch(connection,lease,fresh)
                    insert_atomic_projections(connection,(p for p in projected if p.source.source_row_ordinal > cursor),args.batch_size)
                    connection.execute("""UPDATE dl_control.checkpoint SET retained_rows=last_ordinal-%s
                        WHERE job_id=%s AND derivation_id=%s AND source_table=%s""",
                        (item["first"]-1,job_id,binding["derivation_id"],binding["source_table"]))
                    require_lease(connection,lease)
                    require_source_access(connection,binding["layer_id"])
                    disk_guard(args.repository,args.reserve_bytes)
                cursor = fresh[-1].source_row_ordinal
                checkpoint = (cursor,cursor-item["first"]+1)
                heartbeat(connection,lease,3600)
            minimum_free = min(minimum_free,disk_guard(args.repository,args.reserve_bytes))
            if count % 50000 == 0:
                print(json.dumps({"progress":binding["layer_id"],"table":binding["source_table"],
                    "window_first":item["first"],"rows":count,"target_rows":item["rows"],
                    "free_gib":round(minimum_free/1024**3,2)}),flush=True)
        if (count != item["rows"] or digest.hexdigest() != item["stream_sha256"]
            or dict(projections) != item["projection_counts"] or quarantine != item["quarantined_rows"]):
            raise ValueError("Full source/projection/digest/quarantine control differs from selected sizing receipt")
        actual, actual_projections = database_window_counts(connection,item)
        if actual != count or actual_projections != dict(projections) or cursor != item["last"]:
            raise ValueError("Actual persistent source/projection/checkpoint population differs")
        receipt = connection.execute("""SELECT input_rows,retained_rows,quarantined_rows,stream_sha256,controls
            FROM dl_control.ingest_receipt WHERE job_id=%s""",(job_id,)).fetchone()
        expected_receipt = (count,count,quarantine,digest.hexdigest(),controls)
        require_frozen(args.repository,manifest)
        require_source_access(connection,binding["layer_id"])
        if complete:
            if receipt != expected_receipt:
                raise ValueError("Completed database receipt differs from exact selected controls")
        else:
            with connection.transaction():
                require_lease(connection,lease)
                connection.execute("""INSERT INTO dl_control.ingest_receipt(job_id,input_rows,retained_rows,
                    quarantined_rows,stream_sha256,controls) VALUES(%s,%s,%s,%s,%s,%s)""",
                    (job_id,count,count,quarantine,digest.hexdigest(),Jsonb(controls)))
                connection.execute("""UPDATE dl_control.job SET state='complete',finished_at=clock_timestamp(),lease_until=NULL
                    WHERE job_id=%s""",(job_id,))
        result = {"build_id":build_id,"job_id":job_id,"selected_slot":item["slot"],"binding":binding,
                  "source_rows":count,"projection_counts":dict(projections),"quarantined_rows":quarantine,
                  "first_ordinal":item["first"],"last_ordinal":item["last"],"stream_sha256":digest.hexdigest(),
                  "database_verified":True,"new_acceptance":False,"observed_at":now(),
                  "elapsed_seconds":round(time.monotonic()-started,3),"minimum_free_bytes":minimum_free,
                  "python_process_peak_rss_bytes":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  "recovered_completed_database_receipt":complete}
        if "material_execution" in controls:
            result["material_execution"] = controls["material_execution"]
        destination = args.output / "units" / (item["slot"]+".json")
        if destination.exists():
            prior = json.loads(destination.read_text())
            if prior.get("material_execution") != result.get("material_execution"):
                raise ValueError("Material execution provenance differs from the current unit receipt")
            for key in ("build_id","job_id","selected_slot","binding","source_rows","projection_counts",
                        "quarantined_rows","first_ordinal","last_ordinal","stream_sha256","database_verified","new_acceptance"):
                if prior[key] != result[key]:
                    raise ValueError("Filesystem receipt differs from the verified database receipt")
            result = prior
        else:
            atomic_json(destination,result)
        print(json.dumps({"complete":binding["layer_id"],"table":binding["source_table"],
                          "first":item["first"],"rows":count,"job_id":job_id,"reused":complete}),flush=True)
        return result
    except BaseException as error:
        if lease is not None:
            # Make only this worker's non-stopped job reclaimable. Committed data
            # stays intact; source stops and a replacement owner's fence win.
            connection.execute("""UPDATE dl_control.job SET lease_until=clock_timestamp()-interval '1 second'
                WHERE job_id=%s AND owner_id=%s AND fence=%s AND state='running'""",
                (job_id,lease.owner_id,lease.fence))
        atomic_json(args.output/"failures"/(item["slot"]+"-"+uuid.uuid4().hex[:8]+".json"),
                    {"selected_slot":item["slot"],"job_id":job_id,"error_type":type(error).__name__,
                     "error":str(error),"observed_at":now(),"partial_database_preserved":True})
        raise


def prepare_target(admin, admin_dsn, args, manifest):
    build_id = digest_json(manifest)
    predecessor = manifest.get("predecessor")
    marker = predecessor["ownership"]["marker"] if predecessor else "daylight-local-full/1:"+build_id
    target_path = args.output/"TARGET.json"
    existing = admin.execute("SELECT oid,shobj_description(oid,'pg_database') FROM pg_database WHERE datname=%s",(args.database,)).fetchone()
    if target_path.exists():
        target = json.loads(target_path.read_text())
        if (target["build_id"] != build_id or target["database"] != args.database or existing is None
            or int(existing[0]) != target["database_oid"] or existing[1] != marker):
            raise ValueError("Resume target ownership/OID/frozen build differs; no database was changed")
        if predecessor and (target.get("creation_build_id") != predecessor["build_id"]
                            or target.get("predecessor_target_sha256") != predecessor["target_sha256"]):
            raise ValueError("Resume creation/execution lineage differs")
    else:
        if predecessor:
            prior = predecessor["ownership"]
            cluster = str(admin.execute("SELECT system_identifier FROM pg_control_system()").fetchone()[0])
            if (prior["database"] != args.database or existing is None or int(existing[0]) != prior["database_oid"]
                    or existing[1] != prior["marker"] or cluster != prior["cluster_system_identifier"]):
                raise ValueError("Explicit predecessor database/OID/creation marker differs; refusing recovery adoption")
            target = {"database":args.database,"database_oid":prior["database_oid"],"build_id":build_id,
                      "cluster_system_identifier":cluster,"marker":marker,"created_at":prior["created_at"],
                      "execution_started_at":now(),
                      "creation_build_id":predecessor["build_id"],
                      "predecessor_target_sha256":predecessor["target_sha256"]}
            atomic_json(target_path,target)
        elif existing is not None:
            raise ValueError("Target already exists without this build's ownership receipt; refusing adoption")
        else:
            disk_guard(args.repository,args.reserve_bytes,1024**3)
            admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(args.database)))
            admin.execute(sql.SQL("COMMENT ON DATABASE {} IS {}").format(sql.Identifier(args.database),sql.Literal(marker)))
            admin.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(args.database)))
            admin.execute(sql.SQL("GRANT TEMPORARY ON DATABASE {} TO daylight_writer").format(sql.Identifier(args.database)))
            oid = admin.execute("SELECT oid FROM pg_database WHERE datname=%s",(args.database,)).fetchone()[0]
            target = {"database":args.database,"database_oid":int(oid),"build_id":build_id,
                      "cluster_system_identifier":manifest["cluster_system_identifier"],"marker":marker,"created_at":now()}
            atomic_json(target_path,target)
    connection = connect(make_conninfo(admin_dsn,dbname=args.database))
    if not connection.execute("SELECT pg_try_advisory_lock(%s)",(8582026,)).fetchone()[0]:
        connection.close()
        raise RuntimeError("Another persistent-build coordinator owns this target")
    migrate(connection)
    for row in manifest["inherited_source_access_states"]:
        connection.execute("""INSERT INTO dl_control.source_access_state(source_id,state,reason)
            VALUES(%s,%s,%s) ON CONFLICT DO NOTHING""",(row["source_id"],row["state"],row["reason"]))
    connection.execute("SET ROLE daylight_writer")
    archive = FileArchive(args.archive,reserve_bytes=args.reserve_bytes)
    captured = archive.put_file(args.output/"BUILD_MANIFEST.json",expected_sha256=sha256_file(args.output/"BUILD_MANIFEST.json"))
    insert_exact(connection,"dl_control.artifact",["sha256","byte_length","object_key"],
                 [captured.sha256,captured.byte_length,captured.object_key],["sha256"])
    profile = json.loads((args.repository/"infrastructure/daylight-data/config/profile-contract.2026.json").read_text())
    original = dict(profile)
    content_hash = original.pop("content_sha256")
    counts = profile["counts"]
    if (digest_json(original) != content_hash or profile["customer_rows_included"]
        or (counts["question_definitions"],counts["field_definitions"],counts["representation_gaps"]) != (41,78,14)):
        raise ValueError("Exact metadata-only 41/78/14 profile contract differs")
    insert_exact(connection,"dl_control.profile_contract",
                 ["contract_sha256","question_count","field_count","gap_count","contract_payload"],
                 [content_hash,41,78,14,Jsonb(profile)],["contract_sha256"])
    return connection,archive,target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository",required=True,type=Path)
    parser.add_argument("--summary",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--archive",required=True,type=Path)
    parser.add_argument("--database",required=True)
    parser.add_argument("--batch-size",type=int,default=1000)
    parser.add_argument("--reserve-gib",type=float,default=7)
    parser.add_argument("--predecessor-packet",type=Path)
    args = parser.parse_args()
    args.repository,args.output,args.summary = args.repository.resolve(),args.output.resolve(),args.summary.resolve()
    args.reserve_bytes = int(args.reserve_gib*1024**3)
    args.owner = "local-full-"+uuid.uuid4().hex
    if args.reserve_gib < 7 or not 1 <= args.batch_size <= 5000:
        raise ValueError("Reserve >=7GiB and batch size 1..5000 required")
    dsn = os.environ["DAYLIGHT_DATA_ADMIN_DSN"]
    validate_target(dsn,args.database,args.repository)
    summary,selection,inputs = load_selection(args.repository,args.summary)
    sources = verify_selected_sources(args.repository,selection)
    predecessor = load_predecessor(args.repository,args.predecessor_packet,selection,inputs,sources) if args.predecessor_packet else None
    args.output.mkdir(parents=True,exist_ok=True)
    for name in ("units","failures","layers"):
        (args.output/name).mkdir(exist_ok=True)
    with connect(dsn) as admin:
        settings = dict(admin.execute("SELECT name,setting FROM pg_settings WHERE name=ANY(%s)",
            (["server_version","shared_buffers","work_mem","maintenance_work_mem","max_wal_size",
              "full_page_writes","wal_compression","default_toast_compression","block_size"],)))
        inherited = [dict(zip(("source_id","state","reason"),row)) for row in admin.execute(
            "SELECT source_id,state,reason FROM dl_control.source_access_state ORDER BY source_id")]
        manifest = {"schema":"daylight-local-full-build/1","reference_year":2026,"database":args.database,
                    "cluster_system_identifier":str(admin.execute("SELECT system_identifier FROM pg_control_system()").fetchone()[0]),
                    "postgres_settings":settings,"executable_files":executable_files(args.repository),
                    "selected_receipt_files":inputs,"batch_size":args.batch_size,"batch_payload_bytes":8*1024**2,
                    "selected_source_files":sources,
                    "reserve_bytes":args.reserve_bytes,"expected_source_rows":summary["source_rows"],
                    "expected_projection_rows":summary["projection_rows"],"inherited_source_access_states":inherited,
                    "stop_identity_policy":"sealed-local:Lxx; any unmapped held/stopped identity fails closed",
                    "new_acceptance":False,"consumer_release_enabled":False}
        if predecessor:
            manifest.update(schema="daylight-local-full-build/2",predecessor=predecessor[0],
                            predecessor_completed_units=predecessor[1],recovery_receipt_files=predecessor[2])
        path = args.output/"BUILD_MANIFEST.json"
        if path.exists():
            if json.loads(path.read_text()) != manifest:
                raise ValueError("Existing frozen build manifest differs; this target is preserved")
        else:
            atomic_json(path,manifest)
        require_frozen(args.repository,manifest)
        connection,archive,target = prepare_target(admin,dsn,args,manifest)
        try:
            if predecessor:
                previous = manifest["predecessor"]["interrupted_job"]
                require_source_access(connection,manifest["predecessor"]["interrupted_layer_id"])
                old_state = connection.execute("SELECT state,owner_id,fence,payload FROM dl_control.job WHERE job_id=%s",
                    (previous["job_id"],)).fetchone()
                if old_state == ("running",previous["owner_id"],previous["fence"],previous["payload"]):
                    result = connection.execute("""UPDATE dl_control.job SET state='failed',finished_at=clock_timestamp(),lease_until=NULL
                        WHERE job_id=%s AND state='running' AND owner_id=%s AND fence=%s AND lease_until<clock_timestamp()""",
                        (previous["job_id"],previous["owner_id"],previous["fence"]))
                    if result.rowcount != 1:
                        raise ValueError("Interrupted predecessor job acquired a new lease or stop")
                elif old_state != ("failed",previous["owner_id"],previous["fence"],previous["payload"]):
                    raise ValueError("Interrupted predecessor execution changed; no historical job was replaced")
                atomic_json(args.output/"PREDECESSOR_JOB_HISTORY.json",{"job_id":previous["job_id"],
                    "before":previous,"after_state":"failed","retained_checkpoints":manifest["predecessor"]["interrupted_checkpoints"],
                    "raw_or_projection_rows_deleted":0,"source_stop_changed":False,"new_acceptance":False})
                for groups in selection.values():
                    for items in groups.values():
                        for item in items:
                            if item["slot"] in manifest["predecessor_completed_units"]:
                                adopt_completed_unit(connection,item,manifest,args)
            completed = []
            for layer_id,expected_groups in selection.items():
                module = import_module("daylight_data.adapters."+layer_id.lower())
                stream = module.iter_records(args.repository)
                seen,layer_receipts = set(),[]
                try:
                    for key,rows in groupby(stream,key=lambda r:(r.source_path,r.source_table)):
                        if key not in expected_groups or key in seen:
                            raise ValueError("Actual source table is extra, repeated or outside selected scope")
                        seen.add(key)
                        for item in expected_groups[key]:
                            layer_receipts.append(run_unit(connection,module,islice(rows,item["rows"]),item,manifest,args,archive))
                        if next(rows,None) is not None:
                            raise ValueError("Selected windows did not consume the complete source table")
                finally:
                    stream.close()
                if seen != set(expected_groups):
                    raise ValueError("Selected source tables are missing from the actual source stream")
                layer_report = {"layer_id":layer_id,"build_id":digest_json(manifest),"units":len(layer_receipts),
                                "source_rows":sum(r["source_rows"] for r in layer_receipts),
                                "projection_rows":sum(sum(r["projection_counts"].values()) for r in layer_receipts),
                                "selected_slots":[r["selected_slot"] for r in layer_receipts],
                                "simultaneously_retained":True,"new_acceptance":False,"observed_at":now()}
                atomic_json(args.output/"layers"/(layer_id+".json"),layer_report)
                completed.extend(layer_receipts)
                atomic_json(args.output/"STATUS.json",{"stage":"persistent_load_running","build_id":digest_json(manifest),
                    "database":args.database,"completed_layers":list(selection)[:list(selection).index(layer_id)+1],
                    "source_rows_retained":sum(r["source_rows"] for r in completed),"observed_at":now(),
                    "new_acceptance":False,"cloud_deployed":False})
            connection.execute("RESET ROLE")
            # Bounded operator maintenance, distinct from a consumer query timeout.
            connection.execute("SET statement_timeout='10min'")
            for table in ("source_record","observation","offering"):
                disk_guard(args.repository,args.reserve_bytes,512*1024**2)
                connection.execute(sql.SQL("ANALYZE dl_evidence.{}").format(sql.Identifier(table)))
            raw = connection.execute("SELECT count(*) FROM dl_evidence.source_record").fetchone()[0]
            projected = connection.execute("SELECT count(*) FROM dl_evidence.observation").fetchone()[0]
            if raw != summary["source_rows"] or projected != summary["projection_rows"]:
                raise ValueError("Final simultaneous database populations differ from all selected units")
            if current_job_counts(connection,digest_json(manifest)) != (363,0):
                raise ValueError("A persistent import job remains incomplete")
            require_frozen(args.repository,manifest)
            verify_selected_sources(args.repository,selection)
            result = {"schema":"daylight-local-full-load/1","build_id":digest_json(manifest),"target":target,
                      "layers_retained":15,"source_rows":raw,"projection_rows":projected,"unit_receipts":len(completed),
                      "database_bytes":connection.execute("SELECT pg_database_size(current_database())").fetchone()[0],
                      "relation_sizes":relation_sizes(connection),"minimum_free_bytes":min(r["minimum_free_bytes"] for r in completed),
                      "python_process_peak_rss_bytes":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      "observed_at":now(),"all_layers_simultaneously_retained":True,
                      "integrated_queries_verified":False,"full_domain_models_complete":False,
                      "new_acceptance":False,"consumer_release_enabled":False,"cloud_deployed":False}
            if predecessor:
                result.update(predecessor_material_units=len(manifest["predecessor_completed_units"]),
                              historical_jobs_retained=manifest["predecessor"]["historical_jobs"],
                              historical_receipts_retained=manifest["predecessor"]["historical_receipts"],
                              physical_evidence_counted_once=True,predecessor_source_digests_replayed=True)
            atomic_json(args.output/"LOAD_COMPLETE.json",result)
            atomic_json(args.output/"STATUS.json",{"stage":"persistent_load_complete_queries_pending",
                "build_id":digest_json(manifest),"database":args.database,"layers_retained":15,
                "source_rows":raw,"projection_rows":projected,"database_bytes":result["database_bytes"],
                "new_acceptance":False,"cloud_deployed":False,"observed_at":now()})
            print(json.dumps({k:result[k] for k in ("layers_retained","source_rows","projection_rows","database_bytes")}),flush=True)
        finally:
            connection.close()


if __name__ == "__main__":
    main()
