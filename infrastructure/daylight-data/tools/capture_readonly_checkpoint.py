"""Read-only logical checkpoint of the exact interrupted r2 execution.

No service stop/start, database rename, SQL restore or database mutation occurs.
The dump and checkpoint counts share one exported REPEATABLE READ snapshot.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import uuid

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row

from backup_local_database import (guarded_gzip_stream, gzip_archive_toc, decode_gzip_archive,
                                   exclusive_json, fsync_parent)
from daylight_data.adapters.common import digest_json, sha256_file


def main():
    root = Path(__file__).resolve().parents[3]
    package = root / "infrastructure/daylight-data"
    packet = root / "docs/data/infrastructure-execution-2026-10-30-local-full-db/build-r2"
    output = packet / "LOGICAL_CHECKPOINT.json"
    operator_hashes = {"operator_sha256": sha256_file(Path(__file__)),
                       "shared_backup_operator_sha256": sha256_file(Path(__file__).with_name("backup_local_database.py"))}
    for prior in (output, packet / "LOGICAL_CHECKPOINT_TOC.txt"):
        if prior.exists() or prior.is_symlink():
            raise FileExistsError("The prior logical checkpoint evidence is preserved")
    target = json.loads((packet / "TARGET.json").read_text())
    manifest = json.loads((packet / "BUILD_MANIFEST.json").read_text())
    if (target["build_id"] != "3eb6a72ca32becaf2fc6841d6fa6bd42083968658fa026f675de527fcd2d99a9"
            or digest_json(manifest) != target["build_id"]):
        raise ValueError("Exact interrupted execution controls required")
    info = conninfo_to_dict(os.environ["DAYLIGHT_DATA_DATABASE_URL"])
    if (info.get("host") != str(package / ".state/socket") or info.get("port") != "55485"
            or info.get("dbname") != "daylight_research_2026_r2" or info.get("hostaddr") or info.get("service")):
        raise ValueError("Exact original private endpoint required")
    dsn = make_conninfo(host=info["host"], port=info["port"], dbname=info["dbname"], user=info["user"],
                       options="-c default_transaction_read_only=on -c statement_timeout=120000")
    directory = package / ".state/checkpoints"
    if directory.is_symlink():
        raise ValueError("Checkpoint directory cannot be a symlink")
    directory.mkdir(exist_ok=True, mode=0o700)
    if directory.stat().st_mode & 0o077:
        raise ValueError("Private checkpoint directory required")
    key = "interrupted-r2-" + uuid.uuid4().hex
    partial, final = directory / (key + ".partial"), directory / (key + ".dump.gz")
    errors = directory / (key + ".stderr")
    environment = {k: v for k, v in os.environ.items() if not k.startswith("PG")}
    environment["PGOPTIONS"] = "-c default_transaction_read_only=on"
    environment["PGAPPNAME"] = "daylight-readonly-interrupted-checkpoint"
    process = None
    published = False
    try:
        with psycopg.connect(dsn, autocommit=True, row_factory=dict_row) as db:
            with db.transaction():
                db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                db.execute("SET LOCAL idle_in_transaction_session_timeout='45min'")
                identity = db.execute("""SELECT current_database() AS database,oid AS database_oid,
                    shobj_description(oid,'pg_database') AS marker,
                    (SELECT system_identifier::text FROM pg_control_system()) AS cluster_system_identifier
                    FROM pg_database WHERE datname=current_database()""").fetchone()
                if any(identity[k] != target[k] for k in identity):
                    raise ValueError("Actual checkpoint ownership differs")
                counts = db.execute("""SELECT
                    (SELECT count(*) FROM dl_evidence.source_record) AS source_rows,
                    (SELECT count(*) FROM dl_evidence.observation) AS projection_rows,
                    (SELECT count(*) FROM dl_control.job) AS jobs,
                    (SELECT count(*) FROM dl_control.job WHERE state='complete') AS complete_jobs,
                    (SELECT count(*) FROM dl_control.ingest_receipt) AS receipts,
                    (SELECT count(*) FROM dl_review.acceptance_binding) AS acceptance_bindings,
                    (SELECT count(*) FROM dl_review.release) AS releases""").fetchone()
                job = db.execute("""SELECT job_id,state,owner_id,fence,payload,
                    lease_until<clock_timestamp() AS lease_expired FROM dl_control.job WHERE job_id=123""").fetchone()
                cursors = db.execute("SELECT * FROM dl_control.checkpoint WHERE job_id=123").fetchall()
                if (counts["jobs"], counts["complete_jobs"], counts["receipts"], counts["acceptance_bindings"], counts["releases"]) != (123,122,122,0,0):
                    raise ValueError("Original interrupted population differs")
                if (job["state"] != "running" or job["lease_expired"] is not True
                        or job["payload"]["build_id"] != target["build_id"]
                        or len(cursors) != 1 or cursors[0]["last_ordinal"] != 1000 or cursors[0]["retained_rows"] != 1000):
                    raise ValueError("Original interrupted committed prefix differs")
                snapshot = db.execute("SELECT pg_export_snapshot() AS snapshot").fetchone()["snapshot"]
                fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as file, errors.open("xb") as stderr:
                    errors.chmod(0o600)
                    process = subprocess.Popen([str(package / ".postgres18/bin/pg_dump"), "--format=custom",
                        "--compress=none", "--no-password", "--lock-wait-timeout=10s", "--snapshot=" + snapshot,
                        "--dbname=" + dsn], stdout=subprocess.PIPE, stderr=stderr, env=environment)
                    size, digest, minimum = guarded_gzip_stream(process.stdout, file, root, 7 * 1024**3, compresslevel=1)
                    process.stdout.close()
                    if process.wait():
                        raise RuntimeError("Read-only checkpoint pg_dump failed; private stderr retained")
                    file.flush(); os.fsync(file.fileno())
        os.link(partial, final); partial.unlink(); final.chmod(0o400); fsync_parent(final); published = True
        if sha256_file(final) != digest or final.stat().st_size != size:
            raise ValueError("Checkpoint byte hash differs")
        restore = str(package / ".postgres18/bin/pg_restore")
        gzip_archive_toc(final, restore, packet / "LOGICAL_CHECKPOINT_TOC.txt")
        decode_gzip_archive(final, restore, errors)
        if operator_hashes != {"operator_sha256": sha256_file(Path(__file__)),
                "shared_backup_operator_sha256": sha256_file(Path(__file__).with_name("backup_local_database.py"))}:
            raise ValueError("Checkpoint operator/helper changed during capture; published archive is preserved")
        result = {"schema": "daylight-interrupted-readonly-logical-checkpoint/1", "passed": True,
                  "observed_at": datetime.now(timezone.utc).isoformat(), "target": target, "ownership": identity,
                  "predecessor_manifest_sha256": sha256_file(packet / "BUILD_MANIFEST.json"),
                  **operator_hashes, "counts": counts,
                  "interrupted_job": job, "interrupted_checkpoints": cursors,
                  "path": str(final.relative_to(root)), "bytes": size, "sha256": digest,
                  "minimum_free_bytes": minimum, "format": "PostgreSQL custom (native compression none) / outer Python gzip:1",
                  "outer_gzip_crc_verified": True,
                  "consistent_exported_readonly_snapshot": True, "full_archive_decoded_without_execution": True,
                  "toc_sha256": sha256_file(packet / "LOGICAL_CHECKPOINT_TOC.txt"),
                  "service_stop_or_restart": False, "database_modified": False,
                  "database_renamed": False, "clean_restore_executed": False,
                  "physical_checkpoint": False, "off_machine_copy_created": False,
                  "cluster_global_roles_included": False, "external_evidence_archive_included": False,
                  "full_load_complete": False, "new_acceptance": False}
        exclusive_json(output, result)
        print(json.dumps({"passed": True, "bytes": size, "sha256": digest}), flush=True)
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill(); process.wait()
        if not published:
            partial.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
