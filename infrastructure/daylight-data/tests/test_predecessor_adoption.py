"""Real PostgreSQL predecessor-adoption checks; synthetic disposable databases only."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.types.json import Jsonb

from daylight_data.adapters.common import DomainProjection, canonical_json, digest_json, make_source, sha256_file
from daylight_data.database import connect, migrate
from daylight_data.ingestion.jobs import enqueue, stop_source
from daylight_data.storage import FileArchive


@pytest.fixture
def isolated_database():
    dsn = os.environ.get("DAYLIGHT_DATA_TEST_DSN")
    if not dsn:
        pytest.skip("DAYLIGHT_DATA_TEST_DSN required for actual PostgreSQL adoption checks")
    info = conninfo_to_dict(dsn)
    socket = Path(__file__).resolve().parents[1] / ".state/socket"
    if (not info.get("dbname", "").endswith("_test") or info.get("port") != "55485"
            or info.get("hostaddr") or info.get("service")
            or Path(info.get("host", "")).resolve() != socket.resolve()):
        raise RuntimeError("An explicit project-local private test socket/database is required")
    name = "daylight_adoption_qa_" + uuid.uuid4().hex + "_test"
    admin, connection, created = connect(dsn), None, False
    try:
        admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name)))
        created = True
        connection = connect(make_conninfo(dsn, dbname=name))
        migrate(connection)
        connection.execute("SET ROLE daylight_writer")
        yield connection
    finally:
        if connection is not None:
            connection.close()
        if created:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.close()


@pytest.fixture
def fixture_build(tmp_path, monkeypatch):
    package = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(package / "tools"))
    spec = importlib.util.spec_from_file_location("predecessor_adoption_review", package / "tools/build_local_database.py")
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    # Only executable freezing is bypassed, for this tiny synthetic repository.
    monkeypatch.setattr(driver, "require_frozen", lambda *args: None)
    repository = tmp_path / "repository"
    repository.mkdir()
    source = repository / "synthetic-public.json"
    source.write_text('{"synthetic_public_source":true}')
    module = SimpleNamespace(project_record=lambda row: DomainProjection(row, "fixture_observation",
        "fixture:" + row.record_id, {"source_ordinal": row.source_row_ordinal,
        "personal_applicability_determined": False}))
    archive = FileArchive(tmp_path / "archive")
    old = {"schema": "synthetic-adoption-review/1", "execution_revision": "old", "new_acceptance": False}

    def args(label, batch_size=2):
        output = repository / label
        for name in ("units", "failures"):
            (output / name).mkdir(parents=True, exist_ok=True)
        return SimpleNamespace(repository=repository, output=output, reserve_bytes=0,
            batch_size=batch_size, owner="qa-" + label + "-" + uuid.uuid4().hex)

    def rows(count=4):
        return [make_source(repository, source, "L01", "synthetic_public", number, str(number),
            {"ordinal": number, "synthetic": True}, "fixture_ordinal") for number in range(1, count + 1)]

    def item(selected):
        row = selected[0]
        stream = hashlib.sha256()
        for value in selected:
            stream.update(canonical_json([value.record_id, value.raw]).encode() + b"\n")
        result = {"binding": {key: getattr(row, key) for key in ("layer_id", "source_path", "source_table",
            "source_sha256", "derivation_id", "adapter_code_sha256")}, "first": row.source_row_ordinal,
            "last": selected[-1].source_row_ordinal, "rows": len(selected),
            "projection_counts": {"fixture_observation": len(selected)}, "stream_sha256": stream.hexdigest(),
            "quarantined_rows": 0, "sizing_receipt_sha256": digest_json(["synthetic-selection", len(selected)])}
        result["slot"] = digest_json(result)
        return result

    def run(connection, selected, selection, manifest, arguments):
        return driver.run_unit(connection, module, iter(selected), selection, manifest, arguments, archive)

    def seed(connection):
        selected = rows()
        selection, old_args = item(selected), args("old")
        receipt = run(connection, selected, selection, old, old_args)
        path = old_args.output / "units" / (selection["slot"] + ".json")
        producer = {"build_id": digest_json(old), "job_id": receipt["job_id"],
            "unit_receipt_path": str(path.relative_to(repository)), "unit_receipt_sha256": sha256_file(path)}
        new = {"schema": old["schema"], "execution_revision": "new", "new_acceptance": False,
               "predecessor_completed_units": {selection["slot"]: producer}}
        return SimpleNamespace(rows=selected, item=selection, old_args=old_args, old_receipt=receipt,
            producer=producer, manifest=new, args=args("new"))

    return SimpleNamespace(driver=driver, repository=repository, old_manifest=old, module=module,
                          rows=rows, item=item, args=args, run=run, seed=seed)


def evidence(connection):
    return (connection.execute("SELECT * FROM dl_evidence.source_record ORDER BY derivation_id,source_table,source_row_ordinal").fetchall(),
            connection.execute("SELECT * FROM dl_evidence.observation ORDER BY derivation_id,entity_type,entity_id").fetchall(),
            connection.execute("SELECT * FROM dl_evidence.offering ORDER BY derivation_id,offering_id").fetchall())


def administer_fixture(connection, statement, parameters=()):
    # Deliberate corruption is confined to the new UUID-owned test database.
    with connection.transaction():
        connection.execute("SET LOCAL ROLE NONE")
        connection.execute(statement, parameters)


def test_exact_completed_adoption_is_idempotent_and_does_not_duplicate_evidence(fixture_build, isolated_database):
    b, connection = fixture_build, isolated_database
    seeded = b.seed(connection)
    before = evidence(connection)
    old_control = connection.execute("SELECT * FROM dl_control.ingest_receipt WHERE job_id=%s", (seeded.producer["job_id"],)).fetchone()
    build_id = digest_json(seeded.manifest)
    controls = b.driver.unit_controls(seeded.item, build_id, seeded.manifest)
    assert controls["material_execution"] == seeded.producer and controls["new_acceptance"] is False
    job = b.driver.adopt_completed_unit(connection, seeded.item, seeded.manifest, seeded.args)
    assert job != seeded.producer["job_id"]
    assert b.driver.adopt_completed_unit(connection, seeded.item, seeded.manifest, seeded.args) == job
    assert evidence(connection) == before
    assert connection.execute("SELECT * FROM dl_control.ingest_receipt WHERE job_id=%s", (seeded.producer["job_id"],)).fetchone() == old_control
    assert connection.execute("SELECT controls FROM dl_control.ingest_receipt WHERE job_id=%s", (job,)).fetchone() == (controls,)
    assert connection.execute("SELECT last_ordinal,retained_rows FROM dl_control.checkpoint WHERE job_id=%s", (job,)).fetchone() == (4, 4)
    # The normal source replay verifies the adopted current job without writing material again.
    result = b.run(connection, seeded.rows, seeded.item, seeded.manifest, seeded.args)
    assert result["job_id"] == job and result["recovered_completed_database_receipt"] is True
    assert evidence(connection) == before
    assert b.driver.current_job_counts(connection, build_id) == (1, 0)
    assert connection.execute("SELECT count(*) FROM dl_control.ingest_receipt").fetchone() == (2,)
    with connection.transaction():
        connection.execute("SET LOCAL ROLE daylight_released_reader")
        assert connection.execute("SELECT count(*) FROM dl_released.offerings").fetchone() == (0,)
    assert connection.execute("SELECT DISTINCT output_acceptance_state FROM dl_evidence.observation").fetchall() == [("research_only",)]
    assert connection.execute("SELECT DISTINCT source_use_state FROM dl_control.source_snapshot").fetchall() == [("not_newly_reviewed",)]


@pytest.mark.parametrize("change", ["receipt_controls", "receipt_count", "receipt_digest", "payload", "key",
    "source_id", "cursor", "fence", "state", "physical_count"])
def test_changed_predecessor_controls_and_physical_population_are_rejected(fixture_build, isolated_database, change):
    b, connection = fixture_build, isolated_database
    seeded = b.seed(connection)
    job = seeded.producer["job_id"]
    mutations = {
        "receipt_controls": ("UPDATE dl_control.ingest_receipt SET controls=%s WHERE job_id=%s", (Jsonb({"changed": True}), job)),
        "receipt_count": ("UPDATE dl_control.ingest_receipt SET input_rows=5,retained_rows=5 WHERE job_id=%s", (job,)),
        "receipt_digest": ("UPDATE dl_control.ingest_receipt SET stream_sha256=%s WHERE job_id=%s", ("0" * 64, job)),
        "payload": ("UPDATE dl_control.job SET payload=%s WHERE job_id=%s", (Jsonb({"changed": True}), job)),
        "key": ("UPDATE dl_control.job SET idempotency_key='changed-synthetic-key' WHERE job_id=%s", (job,)),
        "source_id": ("UPDATE dl_control.job SET source_id='sealed-local:L02' WHERE job_id=%s", (job,)),
        "cursor": ("UPDATE dl_control.checkpoint SET last_ordinal=3,retained_rows=3 WHERE job_id=%s", (job,)),
        "fence": ("UPDATE dl_control.checkpoint SET fence=fence+1 WHERE job_id=%s", (job,)),
        "state": ("UPDATE dl_control.job SET state='failed' WHERE job_id=%s", (job,)),
    }
    if change == "physical_count":
        extra = DomainProjection(seeded.rows[0], "fixture_observation", "synthetic-extra-identity", {"synthetic": True})
        with connection.transaction():
            b.driver.insert_atomic_projections(connection, [extra], 2)
    else:
        administer_fixture(connection, *mutations[change])
    before = evidence(connection)
    with pytest.raises(ValueError, match="Predecessor"):
        b.driver.adopt_completed_unit(connection, seeded.item, seeded.manifest, seeded.args)
    assert evidence(connection) == before
    assert b.driver.current_job_counts(connection, digest_json(seeded.manifest)) == (0, 0)


@pytest.mark.parametrize("source_id,state", [("sealed-local:L01", "held"), ("sealed-local:L01", "stopped"),
    ("unmapped-source", "stopped")])
def test_held_or_stopped_source_cannot_be_adopted(fixture_build, isolated_database, source_id, state):
    b, connection = fixture_build, isolated_database
    seeded = b.seed(connection)
    if state == "stopped":
        stop_source(connection, source_id, "Synthetic fixture STOP")
    else:
        administer_fixture(connection, "INSERT INTO dl_control.source_access_state(source_id,state,reason) VALUES(%s,%s,%s)",
                           (source_id, state, "Synthetic fixture hold"))
    before = evidence(connection)
    with pytest.raises(RuntimeError, match="STOP|held|stopped"):
        b.driver.adopt_completed_unit(connection, seeded.item, seeded.manifest, seeded.args)
    assert evidence(connection) == before
    assert b.driver.current_job_counts(connection, digest_json(seeded.manifest)) == (0, 0)


def test_current_job_counts_exclude_historical_failed_and_complete_jobs(fixture_build, isolated_database):
    b, connection = fixture_build, isolated_database
    seeded = b.seed(connection)
    build_id = digest_json(seeded.manifest)
    b.driver.adopt_completed_unit(connection, seeded.item, seeded.manifest, seeded.args)
    historical = enqueue(connection, "historical-failed", {"build_id": digest_json(b.old_manifest)}, "synthetic")
    connection.execute("UPDATE dl_control.job SET state='failed' WHERE job_id=%s", (historical,))
    assert connection.execute("SELECT count(*) FROM dl_control.job").fetchone() == (3,)
    assert b.driver.current_job_counts(connection, build_id) == (1, 0)
    enqueue(connection, "new-pending", {"build_id": build_id}, "synthetic")
    assert b.driver.current_job_counts(connection, build_id) == (2, 1)


@pytest.mark.parametrize("change", ["receipt_controls", "cursor", "fence"])
def test_idempotent_adoption_rechecks_current_receipt_and_checkpoint(fixture_build, isolated_database, change):
    b, connection = fixture_build, isolated_database
    seeded = b.seed(connection)
    job = b.driver.adopt_completed_unit(connection, seeded.item, seeded.manifest, seeded.args)
    mutations = {
        "receipt_controls": ("UPDATE dl_control.ingest_receipt SET controls=%s WHERE job_id=%s", (Jsonb({"changed": True}), job)),
        "cursor": ("UPDATE dl_control.checkpoint SET last_ordinal=3,retained_rows=3 WHERE job_id=%s", (job,)),
        "fence": ("UPDATE dl_control.checkpoint SET fence=fence+1 WHERE job_id=%s", (job,)),
    }
    administer_fixture(connection, *mutations[change])
    before = evidence(connection)
    with pytest.raises(ValueError, match="Current adoption"):
        b.driver.adopt_completed_unit(connection, seeded.item, seeded.manifest, seeded.args)
    assert evidence(connection) == before
    assert connection.execute("SELECT count(*) FROM dl_control.job").fetchone() == (2,)


def test_transactional_adoption_failure_expires_owned_lease_and_can_retry(fixture_build, isolated_database, monkeypatch):
    b, connection = fixture_build, isolated_database
    seeded = b.seed(connection)
    before = evidence(connection)
    original = b.driver.require_lease
    def fail_inside_transaction(*args):
        original(*args)
        raise RuntimeError("Synthetic adoption transaction failure")
    monkeypatch.setattr(b.driver, "require_lease", fail_inside_transaction)
    with pytest.raises(RuntimeError, match="adoption transaction"):
        b.driver.adopt_completed_unit(connection, seeded.item, seeded.manifest, seeded.args)
    current = connection.execute("SELECT job_id,state,lease_until<clock_timestamp() FROM dl_control.job WHERE payload->>'build_id'=%s",
                                 (digest_json(seeded.manifest),)).fetchone()
    assert current[1:] == ("running", True)
    assert connection.execute("SELECT count(*) FROM dl_control.checkpoint WHERE job_id=%s", (current[0],)).fetchone() == (0,)
    assert connection.execute("SELECT count(*) FROM dl_control.ingest_receipt WHERE job_id=%s", (current[0],)).fetchone() == (0,)
    assert evidence(connection) == before
    assert connection.execute("SELECT state FROM dl_control.job WHERE job_id=%s", (seeded.producer["job_id"],)).fetchone() == ("complete",)
    monkeypatch.setattr(b.driver, "require_lease", original)
    assert b.driver.adopt_completed_unit(connection, seeded.item, seeded.manifest, seeded.args) == current[0]
    assert evidence(connection) == before


def test_partial_old_thousand_row_prefix_survives_new_build_completion(fixture_build, isolated_database, monkeypatch):
    b, connection = fixture_build, isolated_database
    rows = b.rows(1003)
    item, old_args = b.item(rows), b.args("old-partial", batch_size=1000)
    original, calls = b.driver.insert_atomic_projections, 0
    def failed_second_chunk(*args, **kwargs):
        nonlocal calls
        calls += 1
        original(*args, **kwargs)
        if calls == 2:
            raise RuntimeError("Synthetic old second-batch failure")
    monkeypatch.setattr(b.driver, "insert_atomic_projections", failed_second_chunk)
    with pytest.raises(RuntimeError, match="old second-batch"):
        b.run(connection, rows, item, b.old_manifest, old_args)
    monkeypatch.setattr(b.driver, "insert_atomic_projections", original)
    old_job = connection.execute("SELECT job_id FROM dl_control.job").fetchone()[0]
    connection.execute("UPDATE dl_control.job SET state='failed' WHERE job_id=%s", (old_job,))
    old_checkpoint = connection.execute("SELECT * FROM dl_control.checkpoint WHERE job_id=%s", (old_job,)).fetchone()
    assert old_checkpoint[3:5] == (1000, 1000)
    prefix = evidence(connection)
    assert len(prefix[0]) == len(prefix[1]) == 1000
    assert connection.execute("SELECT count(*) FROM dl_control.ingest_receipt WHERE job_id=%s", (old_job,)).fetchone() == (0,)
    manifest = {"schema": b.old_manifest["schema"], "execution_revision": "new-partial-replay",
                "new_acceptance": False, "predecessor_completed_units": {}}
    result = b.run(connection, rows, item, manifest, b.args("new-partial", batch_size=1000))
    assert result["job_id"] != old_job and result["source_rows"] == 1003
    assert connection.execute("SELECT * FROM dl_control.checkpoint WHERE job_id=%s", (old_job,)).fetchone() == old_checkpoint
    assert connection.execute("SELECT state FROM dl_control.job WHERE job_id=%s", (old_job,)).fetchone() == ("failed",)
    assert connection.execute("SELECT count(*) FROM dl_control.ingest_receipt WHERE job_id=%s", (old_job,)).fetchone() == (0,)
    after = evidence(connection)
    assert len(after[0]) == len(after[1]) == 1003
    assert after[0][:1000] == prefix[0]
    assert all(row in after[1] for row in prefix[1])
    assert b.driver.current_job_counts(connection, digest_json(manifest)) == (1, 0)


@pytest.fixture
def recovery_attachment(fixture_build, isolated_database, tmp_path):
    driver, existing = fixture_build.driver, isolated_database
    # This admin session is confined to the same UUID database created above.
    admin = connect(existing.info.dsn)
    database = existing.info.dbname
    old_build_id = digest_json({"synthetic": "predecessor-creation"})
    marker = "daylight-local-full/1:" + old_build_id
    admin.execute(sql.SQL("COMMENT ON DATABASE {} IS {}").format(sql.Identifier(database), sql.Literal(marker)))
    oid = int(admin.execute("SELECT oid FROM pg_database WHERE datname=%s", (database,)).fetchone()[0])
    cluster = str(admin.execute("SELECT system_identifier FROM pg_control_system()").fetchone()[0])
    target = {"database": database, "database_oid": oid, "build_id": old_build_id,
              "marker": marker, "cluster_system_identifier": cluster,
              "created_at": "2026-10-30T00:00:00+00:00"}
    prior_target = tmp_path / "prior-TARGET.json"
    prior_target.write_text(canonical_json(target))
    predecessor = {"ownership": target, "build_id": old_build_id, "target_sha256": sha256_file(prior_target)}
    manifest = {"schema": "synthetic-recovery-attachment/2", "cluster_system_identifier": cluster,
                "inherited_source_access_states": [], "predecessor": predecessor}
    output = tmp_path / "new-packet"
    output.mkdir()
    (output / "BUILD_MANIFEST.json").write_text(canonical_json(manifest))
    repository = Path(__file__).resolve().parents[3]
    args = SimpleNamespace(database=database, repository=repository, output=output,
                           archive=tmp_path / "attachment-archive", reserve_bytes=0)
    try:
        yield SimpleNamespace(driver=driver, admin=admin, dsn=existing.info.dsn,
            args=args, manifest=manifest, predecessor=target, prior_target=prior_target)
    finally:
        admin.close()


def attachment_state(attachment):
    connection = attachment.admin
    return {
        "database": connection.execute("SELECT oid,shobj_description(oid,'pg_database') FROM pg_database WHERE datname=%s",
                                       (attachment.args.database,)).fetchone(),
        "migrations": connection.execute("SELECT * FROM dl_migrations.applied ORDER BY name").fetchall(),
        "counts": connection.execute("""SELECT
            (SELECT count(*) FROM dl_evidence.source_record),
            (SELECT count(*) FROM dl_evidence.observation),
            (SELECT count(*) FROM dl_control.profile_contract),
            (SELECT count(*) FROM dl_control.artifact),
            (SELECT count(*) FROM dl_control.job)""").fetchone(),
    }


def test_prepare_target_attaches_same_owned_database_and_resumes_new_lineage(recovery_attachment):
    a = recovery_attachment
    before = attachment_state(a)
    connection, archive, target = a.driver.prepare_target(a.admin, a.dsn, a.args, a.manifest)
    try:
        assert target["database"] == a.predecessor["database"]
        assert target["database_oid"] == a.predecessor["database_oid"]
        assert target["marker"] == a.predecessor["marker"]
        assert target["cluster_system_identifier"] == a.predecessor["cluster_system_identifier"]
        assert target["creation_build_id"] == a.predecessor["build_id"]
        assert target["predecessor_target_sha256"] == sha256_file(a.prior_target)
        assert target["build_id"] == digest_json(a.manifest) != target["creation_build_id"]
        assert json.loads((a.args.output / "TARGET.json").read_text()) == target
        assert connection.info.dbname == a.args.database
        assert connection.execute("""SELECT question_count,field_count,gap_count,
            contract_payload->'customer_rows_included' FROM dl_control.profile_contract""").fetchall() == [(41, 78, 14, False)]
        assert connection.execute("SELECT count(*) FROM dl_evidence.source_record").fetchone() == (0,)
        assert connection.execute("SELECT count(*) FROM dl_evidence.observation").fetchone() == (0,)
    finally:
        connection.close()
    after = attachment_state(a)
    assert after["database"] == before["database"]
    assert after["migrations"] == before["migrations"]
    connection, _, resumed = a.driver.prepare_target(a.admin, a.dsn, a.args, a.manifest)
    try:
        assert resumed == target
        assert attachment_state(a) == after
    finally:
        connection.close()


@pytest.mark.parametrize("key", ["database_oid", "marker", "cluster_system_identifier"])
def test_prepare_target_rejects_wrong_predecessor_identity_before_attachment_writes(recovery_attachment, key):
    a = recovery_attachment
    before = attachment_state(a)
    ownership = a.manifest["predecessor"]["ownership"]
    ownership[key] = ownership[key] + 1 if key == "database_oid" else "wrong-synthetic-identity"
    with pytest.raises(ValueError, match="predecessor database/OID/creation marker"):
        a.driver.prepare_target(a.admin, a.dsn, a.args, a.manifest)
    assert not (a.args.output / "TARGET.json").exists()
    assert not a.args.archive.exists()
    assert attachment_state(a) == before


@pytest.mark.parametrize("key", ["creation_build_id", "predecessor_target_sha256"])
def test_prepare_target_resume_rejects_tampered_recovery_linkage(recovery_attachment, key):
    a = recovery_attachment
    connection, _, target = a.driver.prepare_target(a.admin, a.dsn, a.args, a.manifest)
    connection.close()
    before = attachment_state(a)
    target[key] = "0" * 64
    (a.args.output / "TARGET.json").write_text(canonical_json(target))
    with pytest.raises(ValueError, match="creation/execution lineage"):
        a.driver.prepare_target(a.admin, a.dsn, a.args, a.manifest)
    assert attachment_state(a) == before
    assert json.loads((a.args.output / "TARGET.json").read_text())[key] == "0" * 64
