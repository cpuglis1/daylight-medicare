"""Checksummed additive migrations and explicit, bounded database sessions."""
from contextlib import contextmanager
import hashlib
from pathlib import Path
import psycopg


def connect(dsn: str):
    connection = psycopg.connect(dsn, autocommit=True, connect_timeout=5)
    if connection.info.server_version // 10000 not in {17, 18}:
        connection.close()
        raise RuntimeError("D85 requires tested PostgreSQL 18 or 17; no silent fallback")
    connection.execute("SET statement_timeout = '30s'")
    connection.execute("SET lock_timeout = '3s'")
    connection.execute("SET idle_in_transaction_session_timeout = '30s'")
    return connection


def migrate(connection, migrations_path: Path | None = None):
    path = migrations_path or Path(__file__).resolve().parents[2] / "migrations"
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(8572026)")
        connection.execute("CREATE SCHEMA IF NOT EXISTS dl_migrations")
        connection.execute("REVOKE ALL ON SCHEMA dl_migrations FROM PUBLIC")
        connection.execute("""CREATE TABLE IF NOT EXISTS dl_migrations.applied (
            name text PRIMARY KEY, sha256 text NOT NULL,
            applied_at timestamptz NOT NULL DEFAULT clock_timestamp())""")
        applied = dict(connection.execute("SELECT name,sha256 FROM dl_migrations.applied"))
        for migration in sorted(path.glob("*.sql")):
            content = migration.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            if migration.name in applied:
                if applied[migration.name] != digest:
                    raise RuntimeError(f"Applied migration changed: {migration.name}")
                continue
            connection.execute(content.decode())
            connection.execute("INSERT INTO dl_migrations.applied(name,sha256) VALUES(%s,%s)",
                               (migration.name, digest))
        unknown = set(applied) - {item.name for item in path.glob("*.sql")}
        if unknown:
            raise RuntimeError("Migration history contains unavailable migrations")


@contextmanager
def read_transaction(connection, timeout_ms: int = 1500):
    if not 1 <= timeout_ms <= 30000:
        raise ValueError("Unbounded query timeout")
    with connection.transaction():
        connection.execute("SET TRANSACTION READ ONLY")
        connection.execute("SELECT set_config('statement_timeout',%s,true)", (str(timeout_ms),))
        yield connection
