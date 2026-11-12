"""Transactional local work cache; PostgreSQL and accepted references are untouched.

All cached blobs carry a content digest. Run publication and its task index use
one transaction, so a failed run cannot replace the last completed snapshot.
"""
from __future__ import annotations

import gzip
import sqlite3
from pathlib import Path

from .common import canonical, digest, safe_json


class Store:
    def __init__(self, database: Path):
        database.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(database, timeout=30)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.executescript("""
          CREATE TABLE IF NOT EXISTS pipeline_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS cache (
            namespace TEXT NOT NULL, key TEXT NOT NULL, payload BLOB NOT NULL,
            sha256 TEXT NOT NULL, PRIMARY KEY(namespace,key));
          CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, config_sha256 TEXT NOT NULL,
            summary BLOB NOT NULL, summary_sha256 TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS run_tasks (
            run_id TEXT NOT NULL REFERENCES runs(run_id), task_id TEXT NOT NULL,
            offering_id TEXT NOT NULL, status TEXT NOT NULL, evaluation_key TEXT NOT NULL,
            result BLOB NOT NULL, result_sha256 TEXT NOT NULL,
            PRIMARY KEY(run_id, task_id));
          CREATE INDEX IF NOT EXISTS tasks_by_offering ON run_tasks(run_id,offering_id,status);
        """)
        version = self.connection.execute("SELECT value FROM pipeline_meta WHERE key='schema'").fetchone()
        if version and version[0] != "1":
            self.connection.close()
            raise ValueError("Unsupported comparison cache schema")
        self.connection.execute("INSERT OR IGNORE INTO pipeline_meta VALUES ('schema','1')")
        self.connection.commit()

    def close(self):
        self.connection.close()

    @staticmethod
    def packed(value):
        return gzip.compress(canonical(value), mtime=0), digest(value)

    @staticmethod
    def unpacked(blob, expected, *, exact_decimals=False):
        try:
            result = safe_json(gzip.decompress(blob), exact_decimals=exact_decimals)
        except Exception as exc:
            raise ValueError("Corrupt comparison cache payload") from exc
        if digest(result) != expected:
            raise ValueError("Comparison cache digest mismatch")
        return result

    def get(self, namespace, key):
        row = self.connection.execute(
            "SELECT payload,sha256 FROM cache WHERE namespace=? AND key=?", (namespace, key)).fetchone()
        return None if row is None else self.unpacked(*row, exact_decimals=namespace == "artifacts")

    def put(self, namespace, key, value):
        blob, sha = self.packed(value)
        self.connection.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?,?)", (namespace, key, blob, sha))

    def latest_run(self):
        row = self.connection.execute("SELECT run_id FROM runs ORDER BY rowid DESC LIMIT 1").fetchone()
        return row[0] if row else None

    def summary(self, run_id=None):
        run_id = run_id or self.latest_run()
        row = self.connection.execute("SELECT summary,summary_sha256 FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise ValueError("Unknown completed comparison run")
        return self.unpacked(*row)

    def results(self, run_id=None, *, offering_id=None, status=None, limit=None):
        run_id = run_id or self.latest_run()
        # Checking the run also distinguishes an empty completed run from an unknown one.
        self.summary(run_id)
        query, values = "SELECT result,result_sha256 FROM run_tasks WHERE run_id=?", [run_id]
        for field, value in (("offering_id", offering_id), ("status", status)):
            if value is not None:
                query += f" AND {field}=?"
                values.append(value)
        query += " ORDER BY task_id"
        if limit is not None:
            if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
                raise ValueError("Result limit must be a positive integer")
            query += " LIMIT ?"
            values.append(limit)
        return [self.unpacked(*row) for row in self.connection.execute(query, values)]

    def publish(self, summary, results):
        blob, sha = self.packed(summary)
        self.connection.execute("INSERT INTO runs VALUES (?,?,?,?,?)", (
            summary["run_id"], summary["created_at"], summary["config_sha256"], blob, sha))
        for result in results:
            blob, sha = self.packed(result)
            self.connection.execute("INSERT INTO run_tasks VALUES (?,?,?,?,?,?,?)", (
                summary["run_id"], result["task_id"], result["offering_id"],
                result["status"], result["evaluation_key"], blob, sha))
