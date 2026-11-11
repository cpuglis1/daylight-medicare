"""Checksummed additive migrations for the operations database.

Same contract as daylight_data.database.migrate: each migration applies once,
in name order, inside one advisory-locked transaction; an applied migration
whose bytes later change is refused. The operations database is separate from
the research database and never receives research evidence.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
LOCK_KEY = 8572027


def migrate(connection, migrations_path: Path | None = None) -> list[str]:
    path = migrations_path or MIGRATIONS
    applied_now = []
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_KEY,))
        connection.execute("CREATE SCHEMA IF NOT EXISTS dl_ops_migrations")
        connection.execute("REVOKE ALL ON SCHEMA dl_ops_migrations FROM PUBLIC")
        connection.execute("""CREATE TABLE IF NOT EXISTS dl_ops_migrations.applied (
            name text PRIMARY KEY, sha256 text NOT NULL,
            applied_at timestamptz NOT NULL DEFAULT clock_timestamp())""")
        applied = dict(connection.execute("SELECT name, sha256 FROM dl_ops_migrations.applied").fetchall())
        available = sorted(path.glob("*.sql"))
        unknown = set(applied) - {item.name for item in available}
        if unknown:
            raise RuntimeError(f"Migration history names unavailable migrations: {sorted(unknown)}")
        for migration in available:
            content = migration.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            if migration.name in applied:
                if applied[migration.name] != digest:
                    raise RuntimeError(f"Applied migration changed: {migration.name}")
                continue
            connection.execute(content.decode())
            connection.execute("INSERT INTO dl_ops_migrations.applied(name, sha256) VALUES (%s, %s)",
                               (migration.name, digest))
            applied_now.append(migration.name)
    return applied_now
