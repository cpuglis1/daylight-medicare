"""Real PostgreSQL staging/rollback regressions, using UUID disposable databases.

Only synthetic public fixtures are loaded. The explicit local test DSN is used
to create/drop this test's own database; existing research databases are untouched.
"""
from dataclasses import replace
from decimal import Decimal
import importlib.util
import os
from pathlib import Path
import uuid

import pytest
from psycopg import errors, sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from daylight_data.adapters.common import DomainProjection, make_source, offering_parts
from daylight_data.database import connect, migrate
from daylight_data.ingestion.jobs import claim, enqueue
from daylight_data.ingestion.loader import copy_batch, insert_projections as sealed_insert_projections, register_source
from daylight_data.storage import FileArchive


@pytest.fixture
def atomic_insert(monkeypatch):
    package = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(package / "tools"))
    spec = importlib.util.spec_from_file_location("projection_staging_driver_review", package / "tools/build_local_database.py")
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    return driver.insert_atomic_projections


@pytest.fixture
def isolated_database():
    dsn = os.environ.get("DAYLIGHT_DATA_TEST_DSN")
    if not dsn:
        pytest.skip("DAYLIGHT_DATA_TEST_DSN required for actual PostgreSQL staging checks")
    info = conninfo_to_dict(dsn)
    private_socket = Path(__file__).resolve().parents[1] / ".state/socket"
    if (not info.get("dbname", "").endswith("_test") or info.get("port") != "55485"
            or info.get("hostaddr") or info.get("service")
            or Path(info.get("host", "")).resolve() != private_socket.resolve()):
        raise RuntimeError("An explicit project-local private test socket/database is required")
    name = "daylight_projection_qa_" + uuid.uuid4().hex + "_test"
    admin = connect(dsn)
    connection, created = None, False
    try:
        admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name)))
        created = True
        admin.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(name)))
        admin.execute(sql.SQL("GRANT CONNECT,TEMPORARY ON DATABASE {} TO daylight_writer").format(sql.Identifier(name)))
        connection = connect(make_conninfo(dsn, dbname=name))
        migrate(connection)
        # Permanent same-name fixtures prove cleanup addresses only pg_temp.
        connection.execute("CREATE TABLE public.projection_batch (sentinel text)")
        connection.execute("CREATE TABLE public.offering_batch (sentinel text)")
        connection.execute("SET ROLE daylight_writer")
        yield connection
    finally:
        if connection is not None:
            connection.close()
        if created:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.close()


@pytest.fixture
def source_and_lease(isolated_database, tmp_path):
    connection = isolated_database
    source = tmp_path / "synthetic-public.json"
    source.write_text('{"synthetic_public_expansion":true}')
    row = make_source(tmp_path, source, "L05", "synthetic_expansion", 1, "public-row",
                      {"synthetic_public_expansion": True}, "fixture_ordinal")
    register_source(connection, FileArchive(tmp_path / "archive"), tmp_path, row)
    job = enqueue(connection, "projection-staging-" + uuid.uuid4().hex,
                  {"synthetic": True}, "synthetic-public-fixture")
    lease = claim(connection, "projection-staging-qa", 300, job_id=job)
    assert lease is not None
    return connection, row, lease


def expanded(row, count):
    result = []
    for index in range(count):
        if index % 1000 == 0:
            identifier = f"2026:H0001:{index // 1000 + 1:03d}:000"
            result.append(DomainProjection(row, "offering", identifier,
                {**offering_parts(identifier), "plan_name": f"Synthetic {index}", "category": "fixture"}))
        else:
            result.append(DomainProjection(row, "synthetic_expanded_benefit", f"public:{index}",
                {"benefit_year": 2026, "county_fips": "12021", "amount_decimal": Decimal("10.1250"),
                 "unit": "USD", "basis": "fixture", "period": "per_visit", "raw_value": "10.1250",
                 "source_index": index, "personal_applicability_determined": False},
                conditions=[{"network": "source_fixture", "frequency": "per_visit", "index": index}]))
    return result


def staging_absent(connection):
    assert connection.execute("SELECT to_regclass('pg_temp.projection_batch'),to_regclass('pg_temp.offering_batch')").fetchone() == (None, None)
    assert connection.execute("SELECT to_regclass('public.projection_batch') IS NOT NULL,to_regclass('public.offering_batch') IS NOT NULL").fetchone() == (True, True)


def evidence(connection):
    return {
        "raw": connection.execute("SELECT * FROM dl_evidence.source_record ORDER BY derivation_id,source_table,source_row_ordinal").fetchall(),
        "observations": connection.execute("SELECT * FROM dl_evidence.observation ORDER BY derivation_id,entity_type,entity_id").fetchall(),
        "offerings": connection.execute("SELECT * FROM dl_evidence.offering ORDER BY derivation_id,offering_id").fetchall(),
        "checkpoint": connection.execute("SELECT * FROM dl_control.checkpoint ORDER BY job_id,derivation_id,source_table").fetchall(),
    }


@pytest.mark.parametrize("count", [1000, 1001, 2505])
def test_expanded_raw_batch_spans_copy_chunks_in_one_outer_transaction(source_and_lease, atomic_insert, count):
    connection, row, lease = source_and_lease
    projections = expanded(row, count)
    with connection.transaction():
        copy_batch(connection, lease, [row])
        atomic_insert(connection, projections, batch_size=1000)
        actual = dict(connection.execute("SELECT entity_type,count(*) FROM dl_evidence.observation GROUP BY entity_type"))
        assert sum(actual.values()) == count
        assert actual["offering"] == (count - 1) // 1000 + 1
        staging_absent(connection)
        assert connection.execute("SELECT count(*) FROM dl_evidence.observation").fetchone() == (count,)
        assert connection.execute("SELECT last_ordinal,retained_rows FROM dl_control.checkpoint").fetchone() == (1, 1)
    assert connection.execute("SELECT DISTINCT output_acceptance_state FROM dl_evidence.observation").fetchall() == [("research_only",)]
    with connection.transaction():
        connection.execute("SET LOCAL ROLE daylight_released_reader")
        assert connection.execute("SELECT count(*) FROM dl_released.offerings").fetchone() == (0,)


def test_exact_replay_multiple_times_before_and_after_outer_commit(source_and_lease, atomic_insert):
    connection, row, lease = source_and_lease
    projections = expanded(row, 2505)
    with connection.transaction():
        copy_batch(connection, lease, [row])
        atomic_insert(connection, projections, batch_size=1000)
        original = evidence(connection)
        atomic_insert(connection, projections, batch_size=1000)
        assert evidence(connection) == original
        staging_absent(connection)
    with connection.transaction():
        copy_batch(connection, lease, [row])
        atomic_insert(connection, projections, batch_size=1000)
        assert evidence(connection) == original
        staging_absent(connection)


def test_offering_rows_survive_multiple_chunks_with_exact_source_lineage(source_and_lease, atomic_insert):
    connection, row, lease = source_and_lease
    with connection.transaction():
        copy_batch(connection, lease, [row])
        atomic_insert(connection, expanded(row, 2505), batch_size=1000)
        rows = connection.execute("""SELECT offering_id,plan_name,source_table,source_row_ordinal,output_acceptance_state
            FROM dl_evidence.offering ORDER BY offering_id""").fetchall()
        assert rows == [(f"2026:H0001:{index + 1:03d}:000", f"Synthetic {index * 1000}", row.source_table, 1, "research_only")
                        for index in range(3)]
        assert connection.execute("SELECT count(*) FROM dl_evidence.observation WHERE entity_type='offering'").fetchone() == (3,)
        staging_absent(connection)


@pytest.mark.parametrize("failure", ["constraint", "changed_immutable_identity"])
def test_second_chunk_failure_rolls_back_raw_projections_offerings_and_checkpoint(source_and_lease, atomic_insert, failure):
    connection, row, lease = source_and_lease
    valid = expanded(row, 2505)
    broken = list(valid)
    if failure == "constraint":
        # The second chunk's observation INSERT fails after the first chunk was inserted.
        broken[1001] = replace(valid[1001], fields={**valid[1001].fields, "county_fips": "invalid"})
        expected_error = errors.CheckViolation
    else:
        # The second chunk tries to change the offering inserted by the first chunk.
        broken[1000] = replace(valid[0], fields={**valid[0].fields, "plan_name": "Changed fixture"})
        expected_error = ValueError
    with pytest.raises(expected_error):
        with connection.transaction():
            copy_batch(connection, lease, [row])
            atomic_insert(connection, broken, batch_size=1000)
    assert evidence(connection) == {"raw": [], "observations": [], "offerings": [], "checkpoint": []}
    staging_absent(connection)
    # Recovery can retry the exact same raw ordinal after the entire failed outer transaction.
    with connection.transaction():
        copy_batch(connection, lease, [row])
        atomic_insert(connection, valid, batch_size=1000)
        assert connection.execute("SELECT count(*) FROM dl_evidence.observation").fetchone() == (2505,)
        assert connection.execute("SELECT last_ordinal,retained_rows FROM dl_control.checkpoint").fetchone() == (1, 1)
        staging_absent(connection)


def test_sealed_serializer_is_unchanged_and_driver_owns_chunk_lifetime(source_and_lease):
    connection, row, lease = source_and_lease
    # This expected failure documents the sealed helper's transaction lifetime;
    # the new driver owns the staging cleanup without changing serializer bytes.
    with pytest.raises(errors.DuplicateTable):
        with connection.transaction():
            copy_batch(connection, lease, [row])
            sealed_insert_projections(connection, expanded(row, 1001), batch_size=1000)
    assert evidence(connection) == {"raw": [], "observations": [], "offerings": [], "checkpoint": []}
    staging_absent(connection)
