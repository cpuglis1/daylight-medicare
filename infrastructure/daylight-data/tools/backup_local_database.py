"""Create and fully decode a private local custom-format backup of the completed r2 DB.

This does not execute a clean database restore or create an off-machine backup.
Only an owned newly created partial dump is removed on failure; no database is changed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

from psycopg.conninfo import conninfo_to_dict, make_conninfo
from daylight_data.adapters.common import digest_json, sha256_file
from daylight_data.database import connect

TARGET = "daylight_research_2026_r2"


def fsync_parent(path):
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def exclusive_text(path, value):
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise ValueError("A regular output parent is required")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    fsync_parent(path)


def exclusive_json(path, value):
    exclusive_text(path, json.dumps(value, indent=2, default=str) + "\n")


class GuardedWriter:
    """Hash and guard bytes actually written after compression, including trailer."""
    def __init__(self, destination, repository, reserve_bytes):
        self.destination, self.repository, self.reserve_bytes = destination, repository, reserve_bytes
        self.digest, self.count = hashlib.sha256(), 0
        self.minimum_free_bytes = shutil.disk_usage(repository).free

    def write(self, block):
        free = shutil.disk_usage(self.repository).free
        self.minimum_free_bytes = min(self.minimum_free_bytes, free)
        if free < self.reserve_bytes + len(block) + 64 * 1024**2:
            raise RuntimeError("Compressed backup stopped at local disk reserve; the database is unchanged")
        written = self.destination.write(block)
        if written != len(block):
            raise OSError("A compressed backup write was incomplete")
        self.digest.update(block)
        self.count += written
        return written

    def flush(self):
        return self.destination.flush()


def guarded_gzip_stream(source, raw_destination, repository, reserve_bytes, compresslevel=6,
                        block_size=1024*1024):
    """Bounded Python gzip around pg_dump --compress=none; no plaintext disk file."""
    if not 1 <= compresslevel <= 9 or not 1 <= block_size <= 8 * 1024**2:
        raise ValueError("Bounded gzip compression level/read size required")
    writer = GuardedWriter(raw_destination, repository, reserve_bytes)
    with gzip.GzipFile(fileobj=writer, mode="wb", filename="", mtime=0, compresslevel=compresslevel) as compressed:
        for block in iter(lambda: source.read(block_size), b""):
            compressed.write(block)
    return writer.count, writer.digest.hexdigest(), writer.minimum_free_bytes


def gzip_archive_toc(archive, restore, toc_path):
    """pg_restore --list reads only a <=8 MiB decompressed private prefix."""
    fd, name = tempfile.mkstemp(prefix=".toc-prefix-", dir=archive.parent)
    prefix = Path(name)
    try:
        with os.fdopen(fd, "wb") as output, gzip.open(archive, "rb") as source:
            output.write(source.read(8 * 1024**2))
            output.flush()
            os.fsync(output.fileno())
        listed = subprocess.run([str(restore), "--list", str(prefix)], check=True, capture_output=True, text=True)
        exclusive_text(toc_path, listed.stdout)
    finally:
        prefix.unlink(missing_ok=True)


def decode_gzip_archive(archive, restore, stderr_path):
    """Verify full gzip CRC and custom archive decode; SQL goes only to /dev/null."""
    process = None
    try:
        with stderr_path.open("ab") as errors:
            process = subprocess.Popen([str(restore), "--file=-"], stdin=subprocess.PIPE,
                                       stdout=subprocess.DEVNULL, stderr=errors)
            with gzip.open(archive, "rb") as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    process.stdin.write(block)
            process.stdin.close()
            if process.wait():
                raise RuntimeError("Full custom archive decoding failed; private stderr retained")
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def load_completed_contract(root, packet):
    path = Path(__file__).with_name("verify_local_database.py")
    spec = importlib.util.spec_from_file_location("backup_completed_verifier", path)
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    return verifier.load_contract(root, packet, root / verifier.SUMMARY)


def require_current_execution_complete(db, build_id):
    row = db.execute("""SELECT count(*) AS jobs,count(*) FILTER(WHERE j.state='complete') AS complete_jobs,
        count(r.job_id) AS receipts,
        count(*) FILTER(WHERE r.job_id IS NOT NULL AND r.controls->>'build_id' IS DISTINCT FROM %s) AS wrong_receipt_builds,
        (SELECT count(*) FROM dl_control.checkpoint c JOIN dl_control.job k USING(job_id)
         WHERE k.payload->>'build_id'=%s) AS checkpoints
        FROM dl_control.job j LEFT JOIN dl_control.ingest_receipt r USING(job_id)
        WHERE j.payload->>'build_id'=%s""", (build_id, build_id, build_id)).fetchone()
    if tuple(row) != (363, 363, 363, 0, 363):
        raise ValueError("Exact current-build 363 complete jobs/receipts/checkpoints are required for backup")


def require_fresh_receipts(packet):
    for name in ("BACKUP.json", "BACKUP_TOC.txt"):
        path = packet / name
        if path.exists() or path.is_symlink():
            raise FileExistsError("A prior backup receipt or TOC is preserved: " + name)


def guarded_copy(source, destination, repository, reserve_bytes, block_size=1024*1024):
    digest, count = hashlib.sha256(), 0
    minimum = shutil.disk_usage(repository).free
    while True:
        block = source.read(block_size)
        if not block:
            break
        free = shutil.disk_usage(repository).free
        minimum = min(minimum,free)
        if free < reserve_bytes + len(block) + 64*1024**2:
            raise RuntimeError("Backup stopped at local disk reserve; the database is unchanged")
        destination.write(block)
        digest.update(block)
        count += len(block)
    return count,digest.hexdigest(),minimum


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository",required=True,type=Path)
    parser.add_argument("--packet",required=True,type=Path)
    parser.add_argument("--reserve-gib",type=float,default=7)
    args = parser.parse_args()
    root,packet = args.repository.resolve(),args.packet.resolve()
    require_fresh_receipts(packet)
    if args.reserve_gib < 7:
        raise ValueError("The local 7GiB reserve cannot be lowered")
    reserve = int(args.reserve_gib*1024**3)
    info = conninfo_to_dict(os.environ["DAYLIGHT_DATA_DATABASE_URL"])
    if (info.get("dbname") != TARGET or info.get("hostaddr") or info.get("service")
        or info.get("port") != "55485"
        or Path(info.get("host","")).resolve() != (root/"infrastructure/daylight-data/.state/socket").resolve()):
        raise ValueError("Backup requires the exact completed project-local r2 database")
    contract = load_completed_contract(root, packet)
    target, build_id = contract["target"], contract["build_id"]
    dsn = make_conninfo(host=info["host"],port=info["port"],dbname=TARGET,user=info.get("user",os.environ.get("USER","")),
                       options="-c default_transaction_read_only=on")
    with connect(dsn) as db:
        db.execute("SET default_transaction_read_only=on")
        row = db.execute("SELECT oid,shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()").fetchone()
        if int(row[0]) != target["database_oid"] or row[1] != target["marker"]:
            raise ValueError("Backup target ownership differs")
        cluster = str(db.execute("SELECT system_identifier FROM pg_control_system()").fetchone()[0])
        if cluster != target["cluster_system_identifier"]:
            raise ValueError("Backup cluster identity differs")
        require_current_execution_complete(db, build_id)
    package = root/"infrastructure/daylight-data"
    backup_root = package/".state/backups"
    directory = backup_root/TARGET
    for path in (package/".state",backup_root,directory):
        if path.is_symlink():
            raise ValueError("Backup directory ancestors cannot be symlinks")
        path.mkdir(exist_ok=True,mode=0o700)
        if path.stat().st_mode & 0o077:
            raise ValueError("Backup directories must remain private")
    key = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+uuid.uuid4().hex[:8]
    partial,final = directory/(key+".partial"),directory/(key+".dump.gz")
    stderr_path = directory/(key+".stderr")
    dump,restore = package/".postgres18/bin/pg_dump",package/".postgres18/bin/pg_restore"
    environment = dict(os.environ)
    for name in ("PGHOSTADDR","PGSERVICE","PGSERVICEFILE","PGDATABASE","PGOPTIONS"):
        environment.pop(name,None)
    environment["PGOPTIONS"] = "-c default_transaction_read_only=on"
    environment["PGAPPNAME"] = "daylight-local-readonly-backup"
    process = None
    published = False
    try:
        fd = os.open(partial,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"wb") as output,stderr_path.open("xb") as errors:
            stderr_path.chmod(0o600)
            process = subprocess.Popen([str(dump),"--format=custom","--compress=none","--no-password",
                "--lock-wait-timeout=10s","--dbname="+dsn],stdout=subprocess.PIPE,stderr=errors,env=environment)
            count,digest,minimum = guarded_gzip_stream(process.stdout,output,root,reserve,compresslevel=6)
            process.stdout.close()
            code = process.wait()
            if code:
                raise RuntimeError("pg_dump failed; inspect the private stderr file")
            output.flush()
            os.fsync(output.fileno())
        os.link(partial,final)
        partial.unlink()
        final.chmod(0o400)
        fsync_parent(final)
        published = True
        if sha256_file(final) != digest or final.stat().st_size != count:
            raise RuntimeError("Completed backup bytes differ from streamed hash")
        gzip_archive_toc(final, restore, packet/"BACKUP_TOC.txt")
        decode_gzip_archive(final, restore, stderr_path)
        result = {"schema":"daylight-local-custom-backup/1","observed_at":datetime.now(timezone.utc).isoformat(),
                  "database":TARGET,"database_oid":target["database_oid"],"build_id":build_id,
                  "path":str(final.relative_to(root)),"bytes":count,"sha256":digest,
                  "minimum_free_bytes":minimum,"format":"PostgreSQL custom (native compression none) / outer Python gzip:6",
                  "toc_file":"BACKUP_TOC.txt","toc_sha256":sha256_file(packet/"BACKUP_TOC.txt"),
                  "full_archive_decoded_to_sql_without_execution":True,"clean_database_restore_executed":False,
                  "outer_gzip_crc_verified":True,"current_execution_complete_jobs":363,
                  "cluster_global_roles_included":False,"external_evidence_archive_included":False,
                  "off_machine_copy_created":False,"contains_customer_profiles":False,
                  "database_modified":False,"new_acceptance":False}
        exclusive_json(packet/"BACKUP.json", result)
        print(json.dumps({k:result[k] for k in ("path","bytes","sha256","full_archive_decoded_to_sql_without_execution")}))
    except BaseException:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill();process.wait()
        # This path was created exclusively by this invocation. Completed
        # published bytes remain available for diagnosis if readback fails.
        if not published:
            partial.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    main()
