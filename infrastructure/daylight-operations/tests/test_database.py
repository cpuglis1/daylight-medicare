"""Migration-runner rules, using a fake connection (no PostgreSQL needed).

The SQL itself is exercised against a real server by tests/run_sql_tests.sh.
"""
from contextlib import contextmanager

import pytest

from daylight_operations.database import MIGRATIONS, migrate


class FakeConnection:
    def __init__(self, applied=None):
        self.applied = dict(applied or {})
        self.statements = []

    @contextmanager
    def transaction(self):
        yield

    def execute(self, sql, params=None):
        self.statements.append(sql)
        if sql.startswith("SELECT name, sha256"):
            rows = list(self.applied.items())
            return type("Cursor", (), {"fetchall": lambda self_: rows})()
        if sql.startswith("INSERT INTO dl_ops_migrations.applied"):
            self.applied[params[0]] = params[1]
        return None


def test_applies_each_migration_once_in_order(tmp_path):
    (tmp_path / "002_b.sql").write_text("SELECT 2;")
    (tmp_path / "001_a.sql").write_text("SELECT 1;")
    connection = FakeConnection()
    assert migrate(connection, tmp_path) == ["001_a.sql", "002_b.sql"]
    assert migrate(connection, tmp_path) == []


def test_refuses_a_changed_applied_migration(tmp_path):
    migration = tmp_path / "001_a.sql"
    migration.write_text("SELECT 1;")
    connection = FakeConnection()
    migrate(connection, tmp_path)
    migration.write_text("SELECT 'edited';")
    with pytest.raises(RuntimeError, match="changed"):
        migrate(connection, tmp_path)


def test_refuses_history_naming_missing_migrations(tmp_path):
    (tmp_path / "001_a.sql").write_text("SELECT 1;")
    with pytest.raises(RuntimeError, match="unavailable"):
        migrate(FakeConnection({"000_gone.sql": "x" * 64}), tmp_path)


def test_packaged_migrations_are_found():
    assert (MIGRATIONS / "001_operations.sql").is_file()
