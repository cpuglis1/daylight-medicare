"""Independent D85 security/recovery checks; fixtures only, never customer stores.

Database tests require an explicitly provided DAYLIGHT_DATA_TEST_DSN. Storage
tests use pytest's private temporary directories and never perform network I/O.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import os
from pathlib import Path
import uuid

import pytest

from daylight_data.storage import FileArchive, object_key


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_archive_reuses_identical_bytes_without_replacing_object(tmp_path):
    archive = FileArchive(tmp_path / "archive")
    payload = b"exact published source bytes\n"
    first = archive.put(io.BytesIO(payload))
    before = archive.path(first.sha256).stat()
    again = archive.put(io.BytesIO(payload), expected_sha256=sha(payload))
    after = archive.path(first.sha256).stat()
    assert first.sha256 == again.sha256 == sha(payload)
    assert first.byte_length == again.byte_length == len(payload)
    assert not first.reused and again.reused
    assert (before.st_ino, before.st_mtime_ns) == (after.st_ino, after.st_mtime_ns)
    with archive.open(first.sha256) as handle:
        assert handle.read() == payload
    assert after.st_mode & 0o777 == 0o400
    assert not list(archive.root.glob("capture-*"))


def test_archive_rejects_existing_corruption_without_overwriting(tmp_path):
    archive = FileArchive(tmp_path / "archive")
    original = b"a previously captured source"
    result = archive.put(io.BytesIO(original))
    target = archive.path(result.sha256)
    target.chmod(0o600)
    target.write_bytes(b"corruption retained for investigation")
    before = target.read_bytes()
    with pytest.raises(ValueError, match="corrupt"):
        archive.put(io.BytesIO(original))
    assert target.read_bytes() == before
    with pytest.raises(ValueError, match="corrupt"):
        archive.open(result.sha256)
    assert not list(archive.root.glob("capture-*"))


@pytest.mark.parametrize("operation", ["hash", "bound"])
def test_archive_rejected_capture_leaves_no_partial_object(tmp_path, operation):
    archive = FileArchive(tmp_path / "archive")
    kwargs = {"expected_sha256": "0" * 64} if operation == "hash" else {"max_bytes": 3}
    with pytest.raises(ValueError):
        archive.put(io.BytesIO(b"too many bytes"), **kwargs)
    assert not [p for p in archive.root.rglob("*") if p.is_file()]


@pytest.mark.parametrize("digest", ["../escape", "a" * 63, "a" * 65, "A" * 64, "z" * 64, "/" + "a" * 64])
def test_archive_content_key_never_accepts_paths_or_noncanonical_hashes(tmp_path, digest):
    archive = FileArchive(tmp_path / "archive")
    with pytest.raises(ValueError):
        object_key(digest)
    with pytest.raises(ValueError):
        archive.path(digest)


def test_archive_rejects_symlink_parent_before_any_external_write(tmp_path):
    archive = FileArchive(tmp_path / "archive")
    outside = tmp_path / "outside"
    outside.mkdir()
    (archive.root / "evidence").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        archive.put(io.BytesIO(b"must remain private"))
    assert list(outside.iterdir()) == []
    assert not list(archive.root.glob("capture-*"))


def test_archive_rejects_symlink_object_on_read(tmp_path):
    archive = FileArchive(tmp_path / "archive")
    payload = b"source bytes outside archive"
    outside = tmp_path / "outside-object"
    outside.write_bytes(payload)
    target = archive.root / object_key(sha(payload))
    target.parent.mkdir(parents=True)
    target.symlink_to(outside)
    with pytest.raises(ValueError):
        archive.open(sha(payload))


def test_archive_requires_private_existing_root(tmp_path):
    shared = tmp_path / "shared-root"
    shared.mkdir(mode=0o755)
    shared.chmod(0o755)
    with pytest.raises((ValueError, PermissionError)):
        FileArchive(shared)


def test_archive_concurrent_same_bytes_have_one_immutable_creation(tmp_path):
    archive = FileArchive(tmp_path / "archive")
    payload = b"same immutable source" * 1000
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: archive.put(io.BytesIO(payload)), range(8)))
    assert len({result.sha256 for result in results}) == 1
    assert sum(not result.reused for result in results) == 1
    assert archive.verify(sha(payload)) == len(payload)
    assert not list(archive.root.glob("capture-*"))


@pytest.mark.parametrize("relative", [
    "cms-slice/var/ten-question-profiles/guides.sqlite3",
    "cms-slice/var/guest-profiles/guides.sqlite3",
    "cms-slice/var/ai-budget/usage.sqlite3",
    "alternatives/chat-first/cms-slice/var/chat-alternative-profiles/guides.sqlite3",
])
def test_source_closure_excludes_private_store_ancestors_even_when_declared(tmp_path, relative):
    from daylight_data.adapters.closure import build_source_closure
    root = tmp_path / "synthetic-repository"
    private = root / relative
    private.parent.mkdir(parents=True)
    private.write_bytes(b"harmless synthetic private-store marker")
    manifest = root / "docs/data/synthetic/manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"database": str(private)}))
    composition = tmp_path / "composition.json"
    composition.write_text(json.dumps({"composition_digest": "synthetic-fixture",
        "layers": [{"layer_id": "L01", "seeds": [{"path": "docs/data/synthetic/manifest.json"}]}]}))
    report = build_source_closure(root, composition)
    assert relative not in {item["original_path"] for item in report["artifacts"]}
    assert any(item["original_reference"] == str(private) and item["status"] == "excluded_private_material"
               for item in report["excluded_references"])


@pytest.fixture(scope="module")
def isolated_database():
    """Create a unique disposable database only from an explicit local test DSN."""
    dsn = os.environ.get("DAYLIGHT_DATA_TEST_DSN")
    if not dsn:
        pytest.skip("DAYLIGHT_DATA_TEST_DSN is required for real PostgreSQL checks")
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    from daylight_data.database import connect, migrate

    parameters = conninfo_to_dict(dsn)
    # Prevent a typo from turning the QA fixture into a remote/production action.
    if not parameters.get("dbname", "").endswith("_test"):
        raise RuntimeError("QA requires a database explicitly named with the _test suffix")
    host = Path(parameters.get("host", ""))
    project_state = Path(__file__).resolve().parents[2] / ".state"
    if not host.is_absolute() or not host.resolve().is_relative_to(project_state.resolve()):
        raise RuntimeError("QA requires the project's isolated private socket")
    name = "daylight_qa_" + uuid.uuid4().hex + "_test"
    admin = connect(dsn)
    test_dsn = make_conninfo(dsn, dbname=name)
    try:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        connection = connect(test_dsn)
        try:
            migrate(connection)
            yield connection, test_dsn
        finally:
            connection.close()
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
    finally:
        admin.close()


def source_row(connection, tmp_path, ordinal=1, *, derivation=None, raw=None, source_use_state=None):
    from daylight_data.adapters.common import make_source
    from daylight_data.ingestion.loader import register_source

    source = tmp_path / ("synthetic-" + uuid.uuid4().hex + ".json")
    source.write_bytes(b'{"synthetic":"public fixture only"}')
    row = make_source(tmp_path, source, "L01", "synthetic", ordinal,
                      str(ordinal), raw or {"ordinal": ordinal}, "fixture_ordinal")
    if derivation is not None:
        from dataclasses import replace
        row = replace(row, derivation_id=derivation)
    archive = FileArchive(tmp_path / "archive")
    if source_use_state is not None:
        # An explicit synthetic fixture permission is seeded at immutable capture
        # creation, never by altering a real source's approval state afterward.
        with source.open("rb") as handle:
            captured = archive.put(handle)
        with connection.transaction():
            connection.execute("INSERT INTO dl_control.artifact(sha256,byte_length,object_key) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
                (captured.sha256, captured.byte_length, captured.object_key))
            connection.execute("INSERT INTO dl_control.source_snapshot(snapshot_id,layer_id,artifact_sha256,original_path,benefit_year,source_use_state) VALUES(%s,%s,%s,%s,2026,%s)",
                (row.snapshot_id, row.layer_id, row.source_sha256, row.source_path, source_use_state))
    register_source(connection, archive, tmp_path, row)
    return row


def lease_for(connection, source_id):
    from daylight_data.ingestion.jobs import enqueue, claim

    enqueue(connection, "key-" + source_id, {"fixture": source_id}, source_id)
    lease = claim(connection, "qa-owner-" + source_id, 60)
    assert lease is not None
    return lease


def finish_job(connection, lease):
    connection.execute("UPDATE dl_control.job SET state='complete' WHERE job_id=%s", (lease.job_id,))


def test_job_idempotency_rejects_a_changed_payload(isolated_database):
    from daylight_data.ingestion.jobs import enqueue
    connection, _ = isolated_database
    source = uuid.uuid4().hex
    first = enqueue(connection, "key-" + source, {"edition": 1}, source)
    assert enqueue(connection, "key-" + source, {"edition": 1}, source) == first
    with pytest.raises(ValueError, match="Idempotency"):
        enqueue(connection, "key-" + source, {"edition": 2}, source)
    connection.execute("UPDATE dl_control.job SET state='complete' WHERE job_id=%s", (first,))


def test_replaced_lease_cannot_write_rows_or_checkpoint(isolated_database, tmp_path):
    from daylight_data.database import connect
    from daylight_data.ingestion.jobs import claim, LeaseLost
    from daylight_data.ingestion.loader import copy_batch
    connection, dsn = isolated_database
    row = source_row(connection, tmp_path)
    old = lease_for(connection, uuid.uuid4().hex)
    connection.execute("UPDATE dl_control.job SET lease_until=clock_timestamp()-interval '1 second' WHERE job_id=%s", (old.job_id,))
    with connect(dsn) as other:
        replacement = claim(other, "qa-replacement", 60)
    assert replacement.job_id == old.job_id and replacement.fence > old.fence
    with pytest.raises(LeaseLost):
        copy_batch(connection, old, [row])
    assert connection.execute("SELECT count(*) FROM dl_evidence.source_record WHERE derivation_id=%s", (row.derivation_id,)).fetchone()[0] == 0
    assert connection.execute("SELECT count(*) FROM dl_control.checkpoint WHERE job_id=%s", (old.job_id,)).fetchone()[0] == 0
    copy_batch(connection, replacement, [row])
    assert connection.execute("SELECT fence FROM dl_control.checkpoint WHERE job_id=%s", (old.job_id,)).fetchone()[0] == replacement.fence
    finish_job(connection, replacement)


def test_incomplete_batch_rolls_back_rows_and_cursor_together(isolated_database, tmp_path):
    from dataclasses import replace
    from daylight_data.ingestion.loader import copy_batch
    connection, _ = isolated_database
    row = source_row(connection, tmp_path)
    lease = lease_for(connection, uuid.uuid4().hex)
    copy_batch(connection, lease, [row])
    row2 = replace(row, source_row_ordinal=2, source_row_key="2", raw={"ordinal": 2})
    row4 = replace(row, source_row_ordinal=4, source_row_key="4", raw={"ordinal": 4})
    with pytest.raises(ValueError, match="Non-contiguous"):
        copy_batch(connection, lease, [row2, row4])
    assert connection.execute("SELECT source_row_ordinal FROM dl_evidence.source_record WHERE derivation_id=%s", (row.derivation_id,)).fetchall() == [(1,)]
    assert connection.execute("SELECT last_ordinal,retained_rows FROM dl_control.checkpoint WHERE job_id=%s", (lease.job_id,)).fetchone() == (1, 1)
    copy_batch(connection, lease, [row2, replace(row4, source_row_ordinal=3, source_row_key="3", raw={"ordinal": 3})])
    assert connection.execute("SELECT last_ordinal,retained_rows FROM dl_control.checkpoint WHERE job_id=%s", (lease.job_id,)).fetchone() == (3, 3)
    finish_job(connection, lease)


def test_lease_expiring_during_copy_rolls_back_entire_batch(isolated_database, tmp_path, monkeypatch):
    from daylight_data.ingestion.jobs import require_lease, LeaseLost
    from daylight_data.ingestion import loader
    connection, _ = isolated_database
    row = source_row(connection, tmp_path)
    lease = lease_for(connection, uuid.uuid4().hex)
    calls = []

    def expire_before_final_guard(conn, current):
        calls.append(True)
        if len(calls) == 2:
            conn.execute("UPDATE dl_control.job SET lease_until=clock_timestamp()-interval '1 second' WHERE job_id=%s", (current.job_id,))
        require_lease(conn, current)

    monkeypatch.setattr(loader, "require_lease", expire_before_final_guard)
    with pytest.raises(LeaseLost):
        loader.copy_batch(connection, lease, [row])
    assert len(calls) == 2
    assert connection.execute("SELECT count(*) FROM dl_evidence.source_record WHERE derivation_id=%s", (row.derivation_id,)).fetchone()[0] == 0
    assert connection.execute("SELECT count(*) FROM dl_control.checkpoint WHERE job_id=%s", (lease.job_id,)).fetchone()[0] == 0
    finish_job(connection, lease)


def test_source_stop_survives_connection_restart_and_fences_old_owner(isolated_database):
    from daylight_data.database import connect
    from daylight_data.ingestion.jobs import claim, require_lease, stop_source, LeaseLost
    connection, dsn = isolated_database
    source = uuid.uuid4().hex
    lease = lease_for(connection, source)
    with connect(dsn) as other:
        stop_source(other, source, "Synthetic persisted source STOP")
    with connect(dsn) as restarted:
        assert restarted.execute("SELECT state FROM dl_control.source_access_state WHERE source_id=%s", (source,)).fetchone() == ("stopped",)
        assert claim(restarted, "qa-restarted-worker", 60) is None
        with pytest.raises(LeaseLost):
            with restarted.transaction():
                require_lease(restarted, lease)


def test_worker_can_persist_a_stop_through_stop_only_function(isolated_database):
    from daylight_data.ingestion.jobs import stop_source
    connection, _ = isolated_database
    source = uuid.uuid4().hex
    lease = lease_for(connection, source)
    with connection.transaction():
        connection.execute("SET LOCAL ROLE daylight_writer")
        stop_source(connection, source, "Worker-detected synthetic source STOP")
    assert connection.execute("SELECT state FROM dl_control.source_access_state WHERE source_id=%s", (source,)).fetchone() == ("stopped",)
    assert connection.execute("SELECT state,owner_id,lease_until,fence FROM dl_control.job WHERE job_id=%s", (lease.job_id,)).fetchone() == ("stopped", None, None, lease.fence + 1)


def test_writer_cannot_clear_a_persisted_stop(isolated_database):
    import psycopg
    from daylight_data.ingestion.jobs import stop_source
    connection, _ = isolated_database
    source = uuid.uuid4().hex
    stop_source(connection, source, "Synthetic persisted source STOP")
    with pytest.raises(psycopg.Error):
        with connection.transaction():
            connection.execute("SET LOCAL ROLE daylight_writer")
            connection.execute("UPDATE dl_control.source_access_state SET state='permitted' WHERE source_id=%s", (source,))
    assert connection.execute("SELECT state FROM dl_control.source_access_state WHERE source_id=%s", (source,)).fetchone() == ("stopped",)


def test_writer_cannot_remove_stop_by_renaming_source_identity(isolated_database):
    import psycopg
    from daylight_data.ingestion.jobs import stop_source
    connection, _ = isolated_database
    source = uuid.uuid4().hex
    stop_source(connection, source, "Synthetic persisted source STOP")
    with pytest.raises(psycopg.Error):
        with connection.transaction():
            connection.execute("SET LOCAL ROLE daylight_writer")
            connection.execute("UPDATE dl_control.source_access_state SET source_id=%s WHERE source_id=%s", (source + "-renamed", source))
    assert connection.execute("SELECT state FROM dl_control.source_access_state WHERE source_id=%s", (source,)).fetchone() == ("stopped",)


def test_inherited_writer_role_cannot_clear_a_persisted_stop(isolated_database):
    import psycopg
    from psycopg import sql
    from daylight_data.ingestion.jobs import stop_source
    connection, _ = isolated_database
    source, role = uuid.uuid4().hex, "daylight_qa_" + uuid.uuid4().hex
    stop_source(connection, source, "Synthetic persisted source STOP")
    connection.execute(sql.SQL("CREATE ROLE {} NOLOGIN INHERIT").format(sql.Identifier(role)))
    try:
        connection.execute(sql.SQL("GRANT daylight_writer TO {}").format(sql.Identifier(role)))
        with pytest.raises(psycopg.Error):
            with connection.transaction():
                connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
                connection.execute("UPDATE dl_control.source_access_state SET state='permitted' WHERE source_id=%s", (source,))
        assert connection.execute("SELECT state FROM dl_control.source_access_state WHERE source_id=%s", (source,)).fetchone() == ("stopped",)
    finally:
        connection.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


@pytest.mark.parametrize("permission", ["internal_research_permitted", "synthetic_fixture"])
def test_writer_cannot_mint_source_use_permission_at_capture(isolated_database, tmp_path, permission):
    import psycopg
    connection, _ = isolated_database
    row = source_row(connection, tmp_path)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with connection.transaction():
            connection.execute("SET LOCAL ROLE daylight_writer")
            connection.execute("INSERT INTO dl_control.source_snapshot(snapshot_id,layer_id,artifact_sha256,original_path,benefit_year,source_use_state) VALUES(%s,'L01',%s,'synthetic-forgery',2026,%s)",
                (uuid.uuid4().hex, row.source_sha256, permission))


@pytest.mark.parametrize("role", ["daylight_writer", "daylight_validator", "daylight_research_reader", "daylight_released_reader"])
def test_runtime_roles_cannot_forge_acceptance_or_select_release(isolated_database, role):
    import psycopg
    from psycopg import sql
    connection, _ = isolated_database
    commands = [
        "INSERT INTO dl_review.acceptance_binding(binding_id,exact_target_sha256,purpose,receipt_sha256,receipt_locator,reviewer_actor,original_authority_replay) VALUES('forged','a','consumer','b','fixture','worker','{}')",
        "INSERT INTO dl_review.release(release_id,manifest_sha256,manifest) VALUES('forged','a','{}')",
        "INSERT INTO dl_review.active_release(channel,release_id) VALUES('accepted','forged')",
    ]
    for command in commands:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with connection.transaction():
                connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
                connection.execute(command)


def test_released_role_cannot_read_internal_source_payloads(isolated_database):
    import psycopg
    connection, _ = isolated_database
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with connection.transaction():
            connection.execute("SET LOCAL ROLE daylight_released_reader")
            connection.execute("SELECT raw_payload FROM dl_evidence.source_record LIMIT 1")


def test_source_rows_remain_immutable_and_changed_replay_is_rejected(isolated_database, tmp_path):
    from dataclasses import replace
    import psycopg
    from daylight_data.ingestion.loader import copy_batch
    connection, _ = isolated_database
    row = source_row(connection, tmp_path)
    lease = lease_for(connection, uuid.uuid4().hex)
    copy_batch(connection, lease, [row])
    with pytest.raises(ValueError, match="new derivation"):
        copy_batch(connection, lease, [replace(row, raw={"ordinal": "changed parser value"})])
    with pytest.raises(psycopg.Error, match="immutable"):
        with connection.transaction():
            connection.execute("UPDATE dl_evidence.source_record SET raw_payload='{}' WHERE derivation_id=%s", (row.derivation_id,))
    assert connection.execute("SELECT raw_payload FROM dl_evidence.source_record WHERE derivation_id=%s", (row.derivation_id,)).fetchone() == ({"ordinal": 1},)
    finish_job(connection, lease)


@pytest.mark.parametrize("change", [{"layer_id": "L02"}, {"source_table": "different_parser_table"}])
def test_source_registration_rejects_immutable_metadata_collision(isolated_database, tmp_path, change):
    from dataclasses import replace
    from daylight_data.ingestion.loader import register_source
    connection, _ = isolated_database
    row = source_row(connection, tmp_path)
    with pytest.raises(ValueError, match="new derivation"):
        register_source(connection, FileArchive(tmp_path / "archive"), tmp_path, replace(row, **change))
    assert connection.execute("SELECT layer_id FROM dl_control.source_snapshot WHERE snapshot_id=%s", (row.snapshot_id,)).fetchone() == ("L01",)


def test_changed_conditions_cannot_hide_under_same_projection_and_amount(isolated_database, tmp_path):
    from dataclasses import replace
    from decimal import Decimal
    from daylight_data.adapters.common import DomainProjection
    from daylight_data.ingestion.loader import copy_batch, insert_projections
    connection, _ = isolated_database
    row = source_row(connection, tmp_path)
    lease = lease_for(connection, uuid.uuid4().hex)
    copy_batch(connection, lease, [row])
    observation = DomainProjection(row, "qa_observation", "same-amount",
        {"benefit_year": 2026, "amount": Decimal("10.1234"), "unit": "USD"},
        conditions=[{"network": "in_network", "frequency": "per_visit"}])
    insert_projections(connection, [observation])
    insert_projections(connection, [observation])
    with pytest.raises(ValueError, match="new derivation"):
        insert_projections(connection, [replace(observation, conditions=[{"network": "out_of_network", "frequency": "per_year"}])])
    assert connection.execute("SELECT amount,conditions FROM dl_evidence.observation WHERE derivation_id=%s", (row.derivation_id,)).fetchall() == [(Decimal("10.1234"), observation.conditions)]
    finish_job(connection, lease)


@pytest.fixture
def api_case(isolated_database, tmp_path):
    from dataclasses import replace
    from decimal import Decimal
    from fastapi.testclient import TestClient
    from daylight_data.adapters.common import DomainProjection
    from daylight_data.api.app import create_app
    from daylight_data.ingestion.loader import copy_batch, insert_projections
    from daylight_data.settings import Settings
    connection, dsn = isolated_database
    row = source_row(connection, tmp_path, source_use_state="synthetic_fixture")
    rows = [replace(row, source_row_ordinal=n, source_row_key=str(n), raw={"ordinal": n}) for n in range(1, 4)]
    lease = lease_for(connection, uuid.uuid4().hex)
    copy_batch(connection, lease, rows)
    insert_projections(connection, [DomainProjection(source, "qa_observation", "qa-" + str(n),
        {"benefit_year": 2026, "amount": Decimal("0.1234"), "unit": "USD", "raw_value": "1234"}) for n, source in enumerate(rows, 1)])
    finish_job(connection, lease)
    token, secret = "qa-token-" + uuid.uuid4().hex, "qa-cursor-" + uuid.uuid4().hex
    settings = Settings(dsn, tmp_path / "api-archive", token, secret)
    query = {"benefit_year": 2026, "derivation_id": row.derivation_id,
             "entity_type": "qa_observation", "page_size": 1}
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        yield client, query, {"Authorization": "Bearer " + token}, settings


def test_api_cannot_enable_internal_research_from_customer_flags(api_case):
    client, query, headers, _ = api_case
    for field, value in [("research", True), ("clientcomplete", True),
                         ("releaseoverride", "accepted"), ("profile", {"medicine": "private synthetic canary"})]:
        response = client.post("/internal/evidence/query", json={**query, field: value}, headers=headers)
        assert response.status_code == 422
    for headers in ({}, {"Authorization": "Bearer wrong-synthetic-token"}):
        assert client.post("/internal/evidence/query", json=query, headers=headers).status_code == 401


def test_api_unreviewed_source_is_held_even_for_authenticated_internal_research(api_case, isolated_database, tmp_path):
    connection, _ = isolated_database
    client, query, headers, _ = api_case
    unreviewed = tmp_path / "unreviewed"
    unreviewed.mkdir()
    row = source_row(connection, unreviewed)
    response = client.post("/internal/evidence/query", json={**query, "derivation_id": row.derivation_id}, headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "SOURCE_USE_REVIEW_REQUIRED"


def test_api_malformed_authentication_is_rejected_without_server_error(api_case):
    client, query, _, _ = api_case
    for raw in (b"Basic ignored", b"Bearer \xff", b"Bearer"):
        assert client.post("/internal/evidence/query", json=query,
            headers=[(b"authorization", raw)]).status_code == 401


def test_api_rejects_year_and_query_bound_widening(api_case):
    client, query, headers, _ = api_case
    for changes in ({"benefit_year": 2027}, {"benefit_year": "2026"},
                    {"page_size": 101}, {"page_size": True}, {"county_fips": "1202"}):
        assert client.post("/internal/evidence/query", json={**query, **changes}, headers=headers).status_code == 422
    held = client.post("/v1/offerings/query", json=query, headers=headers)
    assert held.status_code == 503
    assert "EXACT_RELEASE" in held.json()["detail"]


def test_api_pagination_binds_exact_derivation_request_and_principal(api_case):
    from fastapi.testclient import TestClient
    from daylight_data.api.app import create_app
    from daylight_data.settings import Settings
    client, query, headers, settings = api_case
    first = client.post("/internal/evidence/query", json=query, headers=headers)
    assert first.status_code == 200
    result = first.json()
    assert result["derivation_id"] == query["derivation_id"]
    assert not result["personal_recommendation_available"] and result["consumer_release"] == "held"
    assert result["observations"][0]["amount"] == "0.1234"
    cursor = result["next_cursor"]
    assert cursor
    second = client.post("/internal/evidence/query", json={**query, "cursor": cursor}, headers=headers)
    assert second.status_code == 200
    assert first.json()["observations"][0]["entity_id"] != second.json()["observations"][0]["entity_id"]
    for changes in ({"page_size": 2}, {"entity_type": "other"}, {"derivation_id": "f" * 64},
                    {"county_fips": "12021"}, {"cursor": cursor[:-1] + ("a" if cursor[-1] != "a" else "b")}):
        assert client.post("/internal/evidence/query", json={**query, "cursor": cursor, **changes}, headers=headers).status_code == 400
    other_token = "qa-other-token-" + uuid.uuid4().hex
    other_settings = Settings(settings.database_url, settings.archive_root, other_token, settings.cursor_secret)
    with TestClient(create_app(other_settings), raise_server_exceptions=False) as other:
        response = other.post("/internal/evidence/query", json={**query, "cursor": cursor},
                              headers={"Authorization": "Bearer " + other_token})
        assert response.status_code == 400
