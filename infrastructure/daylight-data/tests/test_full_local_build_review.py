"""Independent persistent-build recovery checks; tiny synthetic sources only."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest

from daylight_data.adapters.common import DomainProjection, canonical_json, digest_json, make_source
from daylight_data.database import connect, migrate
from daylight_data.storage import FileArchive


@pytest.fixture
def driver(monkeypatch):
    package = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(package / "tools"))
    spec = importlib.util.spec_from_file_location("independent_full_build_review", package / "tools/build_local_database.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def isolated_database():
    dsn = os.environ.get("DAYLIGHT_DATA_TEST_DSN")
    if not dsn:
        pytest.skip("DAYLIGHT_DATA_TEST_DSN required for actual PostgreSQL recovery checks")
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    info = conninfo_to_dict(dsn)
    private_socket = Path(__file__).resolve().parents[1] / ".state/socket"
    if (not info.get("dbname", "").endswith("_test") or info.get("port") != "55485"
        or Path(info.get("host", "")).resolve() != private_socket.resolve() or info.get("hostaddr")):
        raise RuntimeError("QA requires an explicit project-local private test socket/database")
    name = "daylight_full_qa_" + uuid.uuid4().hex + "_test"
    admin = connect(dsn)
    connection = None
    try:
        admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name)))
        connection = connect(make_conninfo(dsn, dbname=name))
        migrate(connection)
        connection.execute("SET ROLE daylight_writer")
        yield connection
    finally:
        if connection is not None:
            connection.close()
        admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.close()


@pytest.fixture
def fixture_build(driver, tmp_path, monkeypatch):
    # Only executable freeze checking is bypassed for this synthetic repository.
    monkeypatch.setattr(driver, "require_frozen", lambda *args: None)
    repository = tmp_path / "repository"
    repository.mkdir()
    path = repository / "synthetic.json"
    path.write_text('[{"ordinal":1},{"ordinal":2},{"ordinal":3},{"ordinal":4}]')
    rows = [make_source(repository, path, "L01", "fixture", n, str(n), {"ordinal": n}, "fixture_ordinal")
            for n in range(1, 5)]
    output = tmp_path / "receipts"
    for name in ("units", "failures"):
        (output / name).mkdir(parents=True)
    args = SimpleNamespace(repository=repository, output=output, reserve_bytes=0,
                           batch_size=2, owner="qa-full-" + uuid.uuid4().hex)
    module = SimpleNamespace(project_record=lambda row: DomainProjection(
        row, "fixture_observation", "fixture:" + row.record_id,
        {"source_ordinal": row.source_row_ordinal, "personal_applicability_determined": False}))
    manifest = {"schema": "synthetic-full-build-review/1", "new_acceptance": False}
    archive = FileArchive(tmp_path / "archive")

    def item(selected):
        first = selected[0]
        binding = {key: getattr(first, key) for key in (
            "layer_id", "source_path", "source_table", "source_sha256", "derivation_id", "adapter_code_sha256")}
        digest = hashlib.sha256()
        for row in selected:
            digest.update(canonical_json([row.record_id, row.raw]).encode() + b"\n")
        result = {"binding": binding, "first": first.source_row_ordinal,
            "last": selected[-1].source_row_ordinal, "rows": len(selected),
            "projection_counts": {"fixture_observation": len(selected)},
            "stream_sha256": digest.hexdigest(), "quarantined_rows": 0,
            "sizing_receipt_sha256": digest_json({"synthetic": [r.source_row_ordinal for r in selected]})}
        result["slot"] = digest_json(result)
        return result
    return SimpleNamespace(driver=driver, rows=rows, args=args, module=module,
                           manifest=manifest, archive=archive, item=item)


def run(build, connection, rows=None, item=None):
    rows = build.rows if rows is None else rows
    return build.driver.run_unit(connection, build.module, iter(rows), item or build.item(rows),
                                 build.manifest, build.args, build.archive)


def job_row(connection):
    return connection.execute("SELECT job_id,state,lease_until<clock_timestamp() FROM dl_control.job ORDER BY job_id DESC LIMIT 1").fetchone()


def checkpoint(connection, item):
    return connection.execute("SELECT last_ordinal,retained_rows FROM dl_control.checkpoint WHERE derivation_id=%s AND source_table=%s ORDER BY job_id DESC LIMIT 1",
        (item["binding"]["derivation_id"], item["binding"]["source_table"])).fetchone()


def test_exact_reviewed_selection_contains_all_363_units(driver):
    repository = Path(__file__).resolve().parents[3]
    summary = repository / "docs/data/infrastructure-execution-2026-10-30-local-sizing/SUMMARY.json"
    document, selected, inputs = driver.load_selection(repository, summary)
    items = [item for groups in selected.values() for windows in groups.values() for item in windows]
    assert len(items) == 363
    assert sum(i["rows"] for i in items) == document["source_rows"] == 17767179
    assert sum(sum(i["projection_counts"].values()) for i in items) == 17823148
    assert len({i["slot"] for i in items}) == 363
    assert str(summary.relative_to(repository)) in inputs


@pytest.mark.parametrize("target", ["daylight_data_test", "postgres", "daylight_research_2026_r0", "daylight_research_2026_r1;DROP DATABASE x"])
def test_target_guard_rejects_preserved_or_unnumbered_database(driver, tmp_path, target):
    dsn = f"host={tmp_path}/infrastructure/daylight-data/.state/socket port=55485 dbname=daylight_data_test"
    with pytest.raises(ValueError):
        driver.validate_target(dsn, target, tmp_path)


@pytest.mark.parametrize("mismatch", ["unowned", "build_id", "database_oid", "marker"])
def test_existing_target_ownership_mismatch_fails_before_database_changes(driver, tmp_path, mismatch):
    manifest = {"cluster_system_identifier": "synthetic-cluster"}
    build_id = digest_json(manifest)
    target = {"build_id": build_id, "database": "daylight_research_2026_r1", "database_oid": 777}
    marker = "daylight-local-full/1:" + build_id
    if mismatch == "build_id":
        target["build_id"] = "a" * 64
    elif mismatch == "database_oid":
        target["database_oid"] = 778
    elif mismatch == "marker":
        marker = "unrelated-owner"
    if mismatch != "unowned":
        (tmp_path / "TARGET.json").write_text(json.dumps(target))
    commands = []
    class Admin:
        def execute(self, command, parameters):
            commands.append(command)
            return SimpleNamespace(fetchone=lambda: (777, marker))
    args = SimpleNamespace(output=tmp_path, database="daylight_research_2026_r1")
    with pytest.raises(ValueError, match="ownership|exists"):
        driver.prepare_target(Admin(), "", args, manifest)
    assert commands == ["SELECT oid,shobj_description(oid,'pg_database') FROM pg_database WHERE datname=%s"]


def test_actual_fresh_and_resumed_target_uses_shared_marker_private_temp_and_metadata(driver, tmp_path):
    """Provision only a fresh UUID-derived target; retain no evidence source rows."""
    dsn = os.environ.get("DAYLIGHT_DATA_TEST_DSN")
    if not dsn:
        pytest.skip("DAYLIGHT_DATA_TEST_DSN required for real provisioning checks")
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict
    info = conninfo_to_dict(dsn)
    private_socket = Path(__file__).resolve().parents[1] / ".state/socket"
    if (info.get("dbname") != "daylight_data_test" or info.get("port") != "55485"
        or Path(info.get("host", "")).resolve() != private_socket.resolve() or info.get("hostaddr")):
        raise RuntimeError("Provisioning QA requires the explicit preserved local admin socket")
    target_name = "daylight_research_2026_r" + str(10**18 + uuid.uuid4().int % 10**18)
    repository = tmp_path / "synthetic-repository"
    profile_path = repository / "infrastructure/daylight-data/config/profile-contract.2026.json"
    profile_path.parent.mkdir(parents=True)
    profile = {"contract_id": "synthetic-public-metadata-only", "coverage_year": 2026,
        "customer_rows_included": False, "counts": {"question_definitions": 41,
        "field_definitions": 78, "representation_gaps": 14},
        "question_ids": [f"Q{i:02}" for i in range(1, 42)],
        "field_ids": [f"F{i:02}" for i in range(1, 79)],
        "gap_ids": [f"G{i:02}" for i in range(1, 15)]}
    profile["content_sha256"] = digest_json(profile)
    profile_path.write_text(json.dumps(profile))
    output = tmp_path / "output"
    output.mkdir()
    args = SimpleNamespace(repository=repository, output=output, archive=tmp_path / "archive",
                           database=target_name, reserve_bytes=0)
    admin = connect(dsn)
    connections = []
    assert admin.execute("SELECT oid FROM pg_database WHERE datname=%s", (target_name,)).fetchone() is None
    manifest = {"schema": "synthetic-provisioning-review/1", "database": target_name,
        "cluster_system_identifier": str(admin.execute("SELECT system_identifier FROM pg_control_system()").fetchone()[0]),
        "inherited_source_access_states": [], "new_acceptance": False}
    (output / "BUILD_MANIFEST.json").write_text(json.dumps(manifest))
    try:
        first, archive, target = driver.prepare_target(admin, dsn, args, manifest)
        connections.append(first)
        expected_marker = "daylight-local-full/1:" + digest_json(manifest)
        assert admin.execute("SELECT oid,shobj_description(oid,'pg_database') FROM pg_database WHERE datname=%s",
            (target_name,)).fetchone() == (target["database_oid"], expected_marker)
        assert first.execute("SELECT current_user").fetchone()[0] == "daylight_writer"
        assert first.execute("SELECT has_database_privilege(current_user,current_database(),'TEMP')").fetchone()[0]
        assert not admin.execute("""SELECT coalesce(bool_or(a.grantee=0),false)
            FROM pg_database d CROSS JOIN LATERAL aclexplode(d.datacl) a WHERE d.datname=%s""", (target_name,)).fetchone()[0]
        first.execute("CREATE TEMP TABLE provisioning_check(n integer)")
        first.execute("INSERT INTO provisioning_check VALUES(1)")
        assert first.execute("SELECT sum(n) FROM provisioning_check").fetchone()[0] == 1
        assert first.execute("SELECT question_count,field_count,gap_count FROM dl_control.profile_contract").fetchall() == [(41, 78, 14)]
        assert first.execute("SELECT contract_payload->>'customer_rows_included' FROM dl_control.profile_contract").fetchone()[0] == "false"
        assert first.execute("SELECT count(*) FROM dl_evidence.source_record").fetchone()[0] == 0
        identity_before = (output / "TARGET.json").read_bytes()
        first.close()  # Release the real coordinator advisory lock before resume.
        resumed, _, same_target = driver.prepare_target(admin, dsn, args, manifest)
        connections.append(resumed)
        assert same_target == target
        assert (output / "TARGET.json").read_bytes() == identity_before
        assert resumed.execute("SELECT count(*) FROM dl_control.profile_contract").fetchone()[0] == 1
        resumed.execute("CREATE TEMP TABLE resumed_temp_check(n integer)")
        assert resumed.execute("SELECT count(*) FROM dl_evidence.observation").fetchone()[0] == 0
    finally:
        for connection in connections:
            connection.close()
        # This name was UUID-derived here and absent before provisioning; no
        # user-selected, preserved or existing numbered target is ever removed.
        admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(target_name)))
        admin.close()


@pytest.mark.parametrize("last,retained", [(2, 2), (6, 0), (4, 0), (3, 1)])
def test_checkpoint_guard_rejects_wrong_window_cursor(driver, last, retained):
    with pytest.raises(ValueError):
        driver.check_checkpoint((last, retained), {"first": 4, "last": 5})


@pytest.mark.parametrize("stage", ["copy_batch", "insert_projections"])
def test_batch_stage_failure_rolls_back_raw_projection_and_cursor(fixture_build, isolated_database, monkeypatch, stage):
    b, connection = fixture_build, isolated_database
    rows = b.rows[:2]
    item = b.item(rows)
    original = getattr(b.driver, stage)
    def failed(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("synthetic crash after atomic COPY stage")
    monkeypatch.setattr(b.driver, stage, failed)
    with pytest.raises(RuntimeError, match="synthetic crash"):
        run(b, connection, rows, item)
    assert b.driver.database_window_counts(connection, item) == (0, {})
    assert checkpoint(connection, item) is None
    assert job_row(connection)[1:] == ("running", True)
    assert connection.execute("SELECT count(*) FROM dl_control.ingest_receipt").fetchone()[0] == 0
    monkeypatch.setattr(b.driver, stage, original)
    result = run(b, connection, rows, item)
    assert result["source_rows"] == 2 and not result["new_acceptance"]


def test_two_windows_retain_actual_ordinals_and_source_identities(fixture_build, isolated_database):
    b, connection = fixture_build, isolated_database
    first, second = b.item(b.rows[:2]), b.item(b.rows[2:])
    a = run(b, connection, b.rows[:2], first)
    z = run(b, connection, b.rows[2:], second)
    assert a["job_id"] != z["job_id"]
    assert checkpoint(connection, second) == (4, 2)
    actual = connection.execute("SELECT source_row_ordinal,record_id FROM dl_evidence.source_record ORDER BY source_row_ordinal").fetchall()
    assert actual == [(row.source_row_ordinal, row.record_id) for row in b.rows]
    assert connection.execute("SELECT count(*) FROM dl_evidence.observation").fetchone()[0] == 4
    assert connection.execute("SELECT DISTINCT source_use_state FROM dl_control.source_snapshot").fetchall() == [("not_newly_reviewed",)]


def test_committed_database_receipt_recovers_without_filesystem_receipt(fixture_build, isolated_database, monkeypatch):
    b, connection = fixture_build, isolated_database
    rows = b.rows[:2]
    item = b.item(rows)
    original = b.driver.atomic_json
    def failed(path, value):
        if path.parent.name == "units":
            raise OSError("synthetic crash before filesystem receipt")
        return original(path, value)
    monkeypatch.setattr(b.driver, "atomic_json", failed)
    with pytest.raises(OSError, match="filesystem receipt"):
        run(b, connection, rows, item)
    assert job_row(connection)[1] == "complete"
    assert connection.execute("SELECT count(*) FROM dl_control.ingest_receipt").fetchone()[0] == 1
    assert not (b.args.output / "units" / (item["slot"] + ".json")).exists()
    monkeypatch.setattr(b.driver, "atomic_json", original)
    result = run(b, connection, rows, item)
    assert result["recovered_completed_database_receipt"] is True
    assert b.driver.database_window_counts(connection, item) == (2, {"fixture_observation": 2})
    assert connection.execute("SELECT count(*) FROM dl_control.ingest_receipt").fetchone()[0] == 1


def partial_build(b, connection, monkeypatch):
    b.args.batch_size = 1
    original = b.driver.insert_projections
    calls = 0
    def failed(*args, **kwargs):
        nonlocal calls
        calls += 1
        original(*args, **kwargs)
        if calls == 2:
            raise RuntimeError("synthetic second-batch failure")
    monkeypatch.setattr(b.driver, "insert_projections", failed)
    with pytest.raises(RuntimeError, match="second-batch"):
        run(b, connection)
    monkeypatch.setattr(b.driver, "insert_projections", original)


def test_partial_batch_resume_keeps_committed_prefix_and_counts_once(fixture_build, isolated_database, monkeypatch):
    b, connection = fixture_build, isolated_database
    partial_build(b, connection, monkeypatch)
    item = b.item(b.rows)
    assert checkpoint(connection, item) == (1, 1)
    assert b.driver.database_window_counts(connection, item) == (1, {"fixture_observation": 1})
    result = run(b, connection)
    assert result["source_rows"] == 4
    assert checkpoint(connection, item) == (4, 4)
    assert b.driver.database_window_counts(connection, item) == (4, {"fixture_observation": 4})


def test_wrong_persisted_cursor_fails_without_stranding_a_live_lease(fixture_build, isolated_database, monkeypatch):
    b, connection = fixture_build, isolated_database
    partial_build(b, connection, monkeypatch)
    connection.execute("UPDATE dl_control.checkpoint SET retained_rows=0")
    with pytest.raises(ValueError, match="checkpoint"):
        run(b, connection)
    assert job_row(connection)[1:] == ("running", True)
    assert b.driver.database_window_counts(connection, b.item(b.rows)) == (1, {"fixture_observation": 1})


def test_initial_reserve_pause_releases_its_owned_lease(fixture_build, isolated_database, monkeypatch):
    b, connection = fixture_build, isolated_database
    def guarded(*args, **kwargs):
        raise RuntimeError("synthetic disk reserve pause")
    monkeypatch.setattr(b.driver, "disk_guard", guarded)
    with pytest.raises(RuntimeError, match="disk reserve"):
        run(b, connection)
    assert job_row(connection)[1:] == ("running", True)
    assert b.driver.database_window_counts(connection, b.item(b.rows)) == (0, {})


def test_source_stop_blocks_completed_receipt_reuse(fixture_build, isolated_database):
    from daylight_data.ingestion.jobs import stop_source
    b, connection = fixture_build, isolated_database
    result = run(b, connection)
    receipt_path = b.args.output / "units" / (result["selected_slot"] + ".json")
    before = receipt_path.read_bytes()
    stop_source(connection, "sealed-local:L01", "synthetic source STOP")
    with pytest.raises(RuntimeError, match="held/stopped"):
        run(b, connection)
    assert receipt_path.read_bytes() == before
    assert connection.execute("SELECT count(*) FROM dl_evidence.source_record").fetchone()[0] == 4


@pytest.mark.parametrize("source_id", ["sealed-local:L01", "unmapped-underlying-source"])
def test_current_or_unknown_source_stop_blocks_new_import(fixture_build, isolated_database, source_id):
    from daylight_data.ingestion.jobs import stop_source
    b, connection = fixture_build, isolated_database
    stop_source(connection, source_id, "synthetic persisted STOP")
    with pytest.raises(RuntimeError, match="STOP|held|stopped|mapping"):
        run(b, connection)
    assert connection.execute("SELECT count(*) FROM dl_evidence.source_record").fetchone()[0] == 0
    assert connection.execute("SELECT count(*) FROM dl_control.job WHERE state='running' AND lease_until>clock_timestamp()").fetchone()[0] == 0


def test_known_other_layer_stop_does_not_unlock_or_block_current_layer(fixture_build, isolated_database):
    from daylight_data.ingestion.jobs import stop_source
    b, connection = fixture_build, isolated_database
    stop_source(connection, "sealed-local:L02", "independent layer remains stopped")
    result = run(b, connection)
    assert result["source_rows"] == 4
    assert connection.execute("SELECT state FROM dl_control.source_access_state WHERE source_id='sealed-local:L02'").fetchone()[0] == "stopped"
