#!/usr/bin/env python3
"""Read-only selected-source/local PostgreSQL sizing; never import or copy evidence.

Inventory scope is the explicit composition's component directories plus seed
files. It is intentionally not a recursive dependency-closure audit. SQLite rows
and sampled values stay in memory; the report contains only counts and sizes.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import resource
import sqlite3
import sys
import time
from typing import Any


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def forbidden(path: Path, root: Path) -> bool:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return True
    parts = relative.parts
    if any(part in {".git", ".aws", ".ssh", ".codex", "credentials", "secrets"}
           or part.startswith(".env") for part in parts):
        return True
    return any(parts[n:n + 2] == ("cms-slice", "var") for n in range(len(parts) - 1))


def regular_files(path: Path, root: Path):
    if path.is_symlink() or forbidden(path, root):
        return
    if path.is_file():
        yield path
    elif path.is_dir():
        for current, directories, files in os.walk(path, followlinks=False):
            base = Path(current)
            directories[:] = sorted(name for name in directories
                                    if not (base / name).is_symlink()
                                    and not forbidden(base / name, root))
            for name in sorted(files):
                item = base / name
                if item.is_file() and not item.is_symlink() and not forbidden(item, root):
                    yield item


def disk_snapshot(path: Path) -> dict[str, int]:
    info = os.statvfs(path)
    return {"total_bytes": info.f_blocks * info.f_frsize,
            "available_bytes": info.f_bavail * info.f_frsize,
            "free_bytes_including_reserved": info.f_bfree * info.f_frsize}


def metadata_tree_size(path: Path) -> dict[str, Any]:
    """Metadata-only size walk, deduplicating hard links; never open file contents."""
    result = {"exists": path.exists(), "files": 0, "logical_bytes": 0,
              "allocated_bytes_from_stat": 0, "errors": 0}
    seen = set()
    if not path.exists():
        return result
    for current, directories, files in os.walk(path, followlinks=False):
        directories[:] = [name for name in directories if not (Path(current) / name).is_symlink()]
        for name in files:
            item = Path(current) / name
            try:
                if item.is_symlink():
                    continue
                info = item.stat()
                marker = info.st_dev, info.st_ino
                if marker in seen:
                    continue
                seen.add(marker)
                result["files"] += 1
                result["logical_bytes"] += info.st_size
                result["allocated_bytes_from_stat"] += info.st_blocks * 512
            except OSError:
                result["errors"] += 1
    return result


def encoded_size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False, default=lambda item: {"binary_byte_length": len(item)}
        if isinstance(item, bytes) else str(item)).encode())


def distribution(values: list[int]) -> dict[str, Any]:
    if not values:
        return {"sample_rows": 0}
    values = sorted(values)
    return {"sample_rows": len(values), "minimum_bytes": values[0],
            "p50_bytes": values[(len(values) - 1) // 2],
            "p95_bytes": values[min(len(values) - 1, int(len(values) * .95))],
            "maximum_bytes": values[-1], "mean_bytes": round(sum(values) / len(values), 2)}


def sqlite_inventory(path: Path, sample_rows: int = 16) -> dict[str, Any]:
    before = path.stat()
    result: dict[str, Any] = {"bytes": before.st_size, "tables": [], "indexes": []}
    # mode=ro guarantees missing paths cannot be created. Sources are sealed;
    # immutable=1 avoids journals or locks. The audit never instantiates app stores.
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("PRAGMA cache_size=-8192")
        result["page_size"] = db.execute("PRAGMA page_size").fetchone()[0]
        result["page_count"] = db.execute("PRAGMA page_count").fetchone()[0]
        result["freelist_pages"] = db.execute("PRAGMA freelist_count").fetchone()[0]
        objects = db.execute("SELECT name,type,tbl_name,sql FROM sqlite_master WHERE type IN ('table','index') AND name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
        stats = {}
        try:
            stats = {row[0]: {"btree_pages": row[1], "btree_bytes": row[2],
                              "payload_bytes": row[3], "unused_bytes": row[4]}
                     for row in db.execute("SELECT name,count(*),sum(pgsize),sum(payload),sum(unused) FROM dbstat GROUP BY name")}
            result["dbstat_available"] = True
        except sqlite3.OperationalError:
            result["dbstat_available"] = False
        for name, kind, table, sql_text in objects:
            if kind == "index":
                result["indexes"].append({"name": name, "table": table, **stats.get(name, {})})
                continue
            quoted = '"' + name.replace('"', '""') + '"'
            columns = db.execute("PRAGMA table_info(" + quoted + ")").fetchall()
            count = db.execute("SELECT count(*) FROM " + quoted).fetchone()[0]
            item = {"name": name, "rows": count, **stats.get(name, {}),
                    "column_count": len(columns),
                    "declared_blob_columns": sum("BLOB" in (col[2] or "").upper() for col in columns),
                    "virtual_table": bool(sql_text and "CREATE VIRTUAL TABLE" in sql_text.upper())}
            sizes, blob_rows = [], 0
            observed = set()
            try:
                low, high = db.execute("SELECT min(rowid),max(rowid) FROM " + quoted).fetchone()
                if count and low is not None:
                    for n in range(sample_rows):
                        target = low + (high - low) * n // max(1, sample_rows - 1)
                        row = db.execute("SELECT rowid,* FROM " + quoted + " WHERE rowid>=? ORDER BY rowid LIMIT 1", (target,)).fetchone()
                        if row and row[0] not in observed:
                            observed.add(row[0])
                            values = dict(zip([column[1] for column in columns], row[1:]))
                            sizes.append(encoded_size(values))
                            blob_rows += any(isinstance(value, bytes) for value in row[1:])
                item["sample_basis"] = f"up_to_{sample_rows}_evenly_spaced_persisted_rowid_seeks_not_random"
            except sqlite3.OperationalError:
                # WITHOUT ROWID sources are explicit prefix samples, never
                # mislabeled representative or extrapolated as uniform density.
                for row in db.execute("SELECT * FROM " + quoted + " LIMIT ?", (sample_rows,)):
                    sizes.append(encoded_size(dict(zip([column[1] for column in columns], row))))
                    blob_rows += any(isinstance(value, bytes) for value in row)
                item["sample_basis"] = "bounded_prefix_without_rowid"
            item["serialized_row_size_sample"] = distribution(sizes)
            item["sample_rows_with_binary_values"] = blob_rows
            item["sample_encoding_caveat"] = "JSON byte length only; binary values represented by length, not a lossless transport or PostgreSQL storage forecast"
            result["tables"].append(item)
    after = path.stat()
    result["size_and_mtime_unchanged"] = (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    result["rows_all_user_tables_including_virtual_shadow_context"] = sum(item["rows"] for item in result["tables"])
    return result


def jsonl_inventory(path: Path) -> dict[str, Any]:
    opener = gzip.open if path.name.endswith(".gz") else open
    count = size = longest = 0
    with opener(path, "rb") as handle:
        for line in handle:
            size += len(line)
            longest = max(longest, len(line))
            if line.strip():
                count += 1
    return {"records_nonempty_lines": count, "uncompressed_bytes": size,
            "maximum_line_bytes": longest, "mean_line_bytes": round(size / count, 2) if count else None,
            "meaning": "Streamed line/byte accounting; no semantic interpretation or approval"}


def inventory(root: Path, composition_path: Path, sample_rows: int = 16, progress=False):
    started = time.monotonic()
    auditor_hash = file_digest(Path(__file__).resolve())
    composition = json.loads(composition_path.read_text())
    files: dict[str, dict[str, Any]] = {}
    layers = []
    for layer in composition["layers"]:
        selected = set()
        for source in [item["path"] for item in layer["components"]] + [item["path"] for item in layer["seeds"]]:
            for path in regular_files(root / source, root):
                relative = path.relative_to(root).as_posix()
                selected.add(relative)
                if relative not in files:
                    info = path.stat()
                    files[relative] = {"path": relative, "bytes": info.st_size,
                        "allocated_bytes_from_stat": info.st_blocks * 512, "layers": []}
                if layer["layer_id"] not in files[relative]["layers"]:
                    files[relative]["layers"].append(layer["layer_id"])
        layers.append({"layer_id": layer["layer_id"], "revision": layer["revision"],
            "component_paths": [item["path"] for item in layer["components"]],
            "selected_component_plus_seed_files": len(selected),
            "selected_component_plus_seed_bytes": sum(files[path]["bytes"] for path in selected),
            "sqlite_files": [path for path in sorted(selected) if Path(path).suffix in {".sqlite", ".sqlite3", ".db"}],
            "consumer_release_enabled": False})
    sqlite_files, jsonl_files = [], []
    for relative, item in sorted(files.items(), key=lambda pair: -pair[1]["bytes"]):
        path = root / relative
        if path.suffix in {".sqlite", ".sqlite3", ".db"}:
            if progress:
                print("Sizing SQLite " + relative, file=sys.stderr, flush=True)
            sqlite_files.append({**item, **sqlite_inventory(path, sample_rows)})
        elif path.name.endswith((".jsonl", ".jsonl.gz")):
            if progress:
                print("Counting JSONL " + relative, file=sys.stderr, flush=True)
            jsonl_files.append({**item, **jsonl_inventory(path)})
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if file_digest(Path(__file__).resolve()) != auditor_hash:
        raise RuntimeError("Sizing auditor changed during the run")
    return {"schema": "daylight-local-source-sizing/1", "captured_at_utc": now(),
        "auditor_code_sha256": auditor_hash,
        "composition_path": composition_path.relative_to(root).as_posix(),
        "composition_file_sha256": file_digest(composition_path),
        "composition_digest": composition["composition_digest"], "reference_year": 2026,
        "scope": "Selected component directories plus seed files only; not dependency closure, archive creation, import or accepted evidence",
        "layers": layers, "sqlite_files": sqlite_files, "jsonl_files": jsonl_files,
        "all_selected_file_metadata": sorted(files.values(), key=lambda item: (-item["bytes"], item["path"])),
        "unique_selected_paths": len(files), "unique_selected_path_bytes": sum(item["bytes"] for item in files.values()),
        "disk": disk_snapshot(root), "elapsed_seconds": round(time.monotonic() - started, 3),
        "auditor_peak_rss_bytes": rss if sys.platform == "darwin" else rss * 1024,
        "consumer_release_enabled": False, "personal_recommendations_enabled": False,
        "limitations": ["Source file bytes, SQLite btree sizes and sampled JSON lengths do not predict PostgreSQL TOAST/index/WAL exactly.",
            "Table counts cover materialized .sqlite/.sqlite3/.db files only; compressed SQLite parents are sized as files but never expanded by this audit. JSON arrays are sized, not counted. JSONL mirrors are separately line-counted and cannot be added as unique records.",
            "Selected directories can contain technical context/FTS mirrors/parent files; their row totals are not unique benefit/provider counts.",
            "Sample widths use rowid strata or bounded prefixes, not a probability sample or a safe universal multiplier.",
            "APFS stat allocation may count shared clone extents more than once; filesystem free-space deltas remain authoritative."]}


def postgres_snapshot(root: Path, dsn_env: str, population_counts: bool = False):
    import psycopg
    from psycopg.conninfo import conninfo_to_dict
    dsn = os.environ[dsn_env]
    settings = conninfo_to_dict(dsn)
    host = Path(settings.get("host", ""))
    if not host.is_absolute() or not host.resolve().is_relative_to(root / "infrastructure/daylight-data/.state"):
        raise ValueError("Sizing is restricted to the project's local private socket")
    with psycopg.connect(dsn, autocommit=False, connect_timeout=5) as db:
        db.execute("SET TRANSACTION READ ONLY")
        db.execute("SET LOCAL statement_timeout='60s'")
        db.execute("SET LOCAL lock_timeout='2s'")
        database, version, size, lsn = db.execute("SELECT current_database(),current_setting('server_version'),pg_database_size(current_database()),pg_current_wal_lsn()::text").fetchone()
        tables = []
        for row in db.execute("""SELECT n.nspname,c.relname,c.reltuples::bigint,
            pg_relation_size(c.oid),pg_table_size(c.oid),pg_indexes_size(c.oid),
            CASE WHEN c.reltoastrelid=0 THEN 0 ELSE pg_total_relation_size(c.reltoastrelid) END,
            pg_total_relation_size(c.oid)
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE c.relkind IN ('r','m','p') AND n.nspname LIKE 'dl_%'
            ORDER BY pg_total_relation_size(c.oid) DESC"""):
            schema, name, rows, main, table, indexes, toast, total = row
            tables.append({"schema": schema, "table": name, "planner_estimated_rows": rows,
                "main_heap_bytes": main, "heap_and_auxiliary_forks_excluding_toast_bytes": table - toast,
                "toast_including_its_indexes_bytes": toast, "own_indexes_bytes": indexes,
                "total_bytes": total, "accounting_balances": table - toast + toast + indexes == total})
        schemas = defaultdict(Counter)
        for item in tables:
            for key in ("heap_and_auxiliary_forks_excluding_toast_bytes", "toast_including_its_indexes_bytes", "own_indexes_bytes", "total_bytes"):
                schemas[item["schema"]][key] += item[key]
        indexes = [{"schema": row[0], "table": row[1], "index": row[2], "bytes": row[3]}
            for row in db.execute("SELECT schemaname,relname,indexrelname,pg_relation_size(indexrelid) FROM pg_stat_user_indexes ORDER BY pg_relation_size(indexrelid) DESC")]
        wal_stats = dict(zip(["wal_records", "wal_fpi", "wal_bytes", "stats_reset"],
            db.execute("SELECT wal_records,wal_fpi,wal_bytes::text,stats_reset::text FROM pg_stat_wal").fetchone()))
        wal_files = db.execute("SELECT count(*),coalesce(sum(size),0) FROM pg_ls_waldir()").fetchone()
        temp = db.execute("SELECT temp_files,temp_bytes,stats_reset::text FROM pg_stat_database WHERE datname=current_database()").fetchone()
        parameters = {key: db.execute("SELECT current_setting(%s)", (key,)).fetchone()[0]
                      for key in ["block_size", "wal_segment_size", "min_wal_size", "max_wal_size", "checkpoint_timeout", "full_page_writes", "wal_compression", "default_toast_compression", "work_mem", "maintenance_work_mem", "log_statement", "logging_collector"]}
        populations = None
        if population_counts:
            populations = {"source_rows_by_layer": [{"layer": row[0], "source_rows": row[1], "distinct_derivations": row[2]}
                for row in db.execute("""SELECT s.layer_id,count(*),count(DISTINCT r.derivation_id)
                    FROM dl_evidence.source_record r JOIN dl_control.derivation d USING(derivation_id)
                    JOIN dl_control.source_snapshot s USING(snapshot_id) GROUP BY s.layer_id ORDER BY s.layer_id""")],
                "ingest_receipts": [{"job_id": row[0], "input_rows": row[1], "retained_rows": row[2]}
                    for row in db.execute("SELECT job_id,input_rows,retained_rows FROM dl_control.ingest_receipt ORDER BY job_id")]}
    package = root / "infrastructure/daylight-data"
    return {"schema": "daylight-local-postgres-sizing/1", "captured_at_utc": now(),
        "database": database, "postgres_version": version, "read_only_snapshot": True,
        "database_bytes": size, "wal_lsn": lsn, "tables": tables,
        "schema_sizes": {key: dict(value) for key, value in schemas.items()}, "indexes": indexes,
        "wal_generated_cluster_stats": wal_stats, "wal_retained_files": {"files": wal_files[0], "bytes": int(wal_files[1])},
        "database_temp_statistics": {"files": temp[0], "bytes": temp[1], "stats_reset": temp[2]},
        "parameters": parameters, "disk": disk_snapshot(root), "exact_population_counts_optional": populations,
        "local_tree_metadata": {name: metadata_tree_size(package / name) for name in [".state", ".state/pgdata", ".state/pgdata/pg_wal", ".state/archive"]},
        "limitations": ["pg_database_size excludes cluster WAL and external object archive/logs.",
            "WAL counters/LSN are cluster-wide; concurrent writers prevent per-import attribution.",
            "Planner row counts are estimates; exact import controls/receipts remain required.",
            "stat allocated bytes do not resolve APFS shared clone extent ownership."]}


def compare(before: dict, after: dict):
    if before["database"] != after["database"]:
        raise ValueError("Cannot compare different databases as one import interval")
    def lsn(value):
        high, low = value.split("/")
        return int(high, 16) * 2**32 + int(low, 16)
    previous = {(item["schema"], item["table"]): item for item in before["tables"]}
    tables = []
    for item in after["tables"]:
        old = previous.get((item["schema"], item["table"]), {})
        tables.append({"schema": item["schema"], "table": item["table"], **{
            key + "_delta": item[key] - old.get(key, 0)
            for key in ["heap_and_auxiliary_forks_excluding_toast_bytes", "toast_including_its_indexes_bytes", "own_indexes_bytes", "total_bytes"]}})
    unchanged_stats_epoch = before["wal_generated_cluster_stats"]["stats_reset"] == after["wal_generated_cluster_stats"]["stats_reset"]
    return {"schema": "daylight-local-sizing-interval/1", "database": after["database"],
        "before_utc": before["captured_at_utc"], "after_utc": after["captured_at_utc"],
        "database_bytes_delta": after["database_bytes"] - before["database_bytes"],
        "filesystem_available_bytes_consumed": before["disk"]["available_bytes"] - after["disk"]["available_bytes"],
        "wal_generated_lsn_bytes_cluster_wide": lsn(after["wal_lsn"]) - lsn(before["wal_lsn"]),
        "wal_generated_counter_bytes_cluster_wide": int(after["wal_generated_cluster_stats"]["wal_bytes"]) - int(before["wal_generated_cluster_stats"]["wal_bytes"]) if unchanged_stats_epoch else None,
        "wal_retained_bytes_delta": after["wal_retained_files"]["bytes"] - before["wal_retained_files"]["bytes"],
        "table_deltas": sorted(tables, key=lambda item: -item["total_bytes_delta"]),
        "caveat": "An interval is attributable to one import only with other cluster/filesystem writers controlled; it is not a peak-disk or peak-RSS measurement."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ["inventory", "postgres"]:
        item = commands.add_parser(command)
        item.add_argument("--repository-root", type=Path, required=True)
        item.add_argument("--output", type=Path, required=True)
        if command == "inventory":
            item.add_argument("--composition", type=Path)
            item.add_argument("--sample-rows", type=int, default=16, choices=range(1, 65))
            item.add_argument("--progress", action="store_true")
        else:
            item.add_argument("--dsn-env", default="DAYLIGHT_DATA_SIZING_DSN")
            item.add_argument("--population-counts", action="store_true")
    item = commands.add_parser("compare")
    item.add_argument("--before", type=Path, required=True)
    item.add_argument("--after", type=Path, required=True)
    item.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "inventory":
        root = args.repository_root.resolve()
        result = inventory(root, args.composition or root / "infrastructure/daylight-data/config/source-composition.2026.json", args.sample_rows, args.progress)
    elif args.command == "postgres":
        result = postgres_snapshot(args.repository_root.resolve(), args.dsn_env, args.population_counts)
    else:
        result = compare(json.loads(args.before.read_text()), json.loads(args.after.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(json.dumps({"output": str(args.output), "schema": result["schema"]}))


if __name__ == "__main__":
    main()
