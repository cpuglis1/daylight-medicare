"""Cold-recovery safety mechanics only: all service/clone actions are mocked.

No PostgreSQL connection, stop/start, APFS clone or real cluster mutation occurs.
"""
import errno
import importlib.util
import json
from pathlib import Path
import shlex
import tempfile
from types import SimpleNamespace

import pytest

SPEC = importlib.util.spec_from_file_location("cold_recovery_review", Path(__file__).resolve().parents[1] / "tools/rehearse_local_recovery.py")
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)


@pytest.fixture(autouse=True)
def prohibit_live_actions(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Live service/database action is forbidden in recovery tests")
    monkeypatch.setattr(recovery.psycopg, "connect", forbidden)
    monkeypatch.setattr(recovery.subprocess, "run", forbidden)
    monkeypatch.setattr(recovery.ctypes, "CDLL", forbidden)


def settings(root):
    data = root / "infrastructure/daylight-data/.state/pgdata"
    return {"data_directory": str(data), "config_file": str(data / "postgresql.conf"),
        "hba_file": str(data / "pg_hba.conf"), "ident_file": str(data / "pg_ident.conf"),
        "external_pid_file": "", "port": "55485", "unix_socket_directories": str(data.parent / "socket"),
        "listen_addresses": "", "archive_mode": "off", "ssl": "off",
        **{key: "" for key in recovery.CALLBACKS}}


@pytest.mark.parametrize("condition", ["clients", "prepared", "slots", "unowned_database"])
def test_preflight_rejects_other_activity_and_unowned_databases(tmp_path, condition):
    databases = ["daylight_data_test", recovery.TARGET]
    if condition == "unowned_database":
        databases.append("unrelated_customer_store")
    with pytest.raises(ValueError):
        recovery.validate_preflight(settings(tmp_path), int(condition == "clients"),
            int(condition == "prepared"), int(condition == "slots"), databases, tmp_path)


@pytest.mark.parametrize("key", ["data_directory", "config_file", "hba_file", "ident_file", "external_pid_file",
    "archive_command", "archive_library", "restore_command", "archive_cleanup_command", "recovery_end_command",
    "primary_conninfo", "primary_slot_name", "shared_preload_libraries", "ssl_passphrase_command"])
def test_preflight_rejects_external_paths_and_callbacks(tmp_path, key):
    configuration = settings(tmp_path)
    configuration[key] = "unhandled-value"
    with pytest.raises(ValueError):
        recovery.validate_preflight(configuration, 0, 0, 0, ["daylight_data_test", recovery.TARGET], tmp_path)


def test_whole_cluster_inventory_rejects_external_symlink_and_config_include(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "pg_tblspc").mkdir()
    (data / "pg_tblspc/external").symlink_to(tmp_path / "outside")
    with pytest.raises(ValueError, match="symlink"):
        recovery.regular_inventory(data)
    (data / "pg_tblspc/external").unlink()
    config = data / "postgresql.conf"
    config.write_text("# include 'historical-comment'\ninclude_dir = 'extra'\n")
    with pytest.raises(ValueError, match="includes"):
        recovery.regular_inventory(data)


@pytest.mark.parametrize("name", ["standby.signal", "recovery.signal", "backup_label"])
def test_inventory_rejects_unhandled_recovery_state(tmp_path, name):
    (tmp_path / name).touch()
    with pytest.raises(ValueError, match="Recovery"):
        recovery.regular_inventory(tmp_path)


@pytest.mark.parametrize("directory", ["pg_replslot", "pg_twophase"])
def test_cold_inventory_rechecks_slot_and_prepared_transaction_files(tmp_path, directory):
    target = tmp_path / directory
    target.mkdir()
    (target / "unexpected-state").write_bytes(b"synthetic state")
    with pytest.raises(ValueError, match="prepared-transaction"):
        recovery.regular_inventory(tmp_path)


def test_kernel_clone_failure_has_no_fallback_or_destination(tmp_path, monkeypatch):
    source, target = tmp_path / "source", tmp_path / "destination"
    source.write_bytes(b"synthetic source only")
    class FailedClone:
        def __call__(self, *args):
            return -1
    monkeypatch.setattr(recovery.ctypes, "CDLL", lambda *args, **kwargs: SimpleNamespace(clonefile=FailedClone()))
    monkeypatch.setattr(recovery.ctypes, "get_errno", lambda: errno.ENOTSUP)
    with pytest.raises(OSError, match="no copy fallback"):
        recovery.kernel_clone(source, target)
    assert not target.exists()


def test_capture_hashes_independent_mock_files_and_preserves_empty_directories(tmp_path, monkeypatch):
    source, target = tmp_path / "source", tmp_path / "clone"
    source.mkdir()
    (source / "base").mkdir()
    (source / "pg_tblspc").mkdir()
    (source / "base/published").write_bytes(b"small public fixture")
    # This is a synthetic in-memory-behavior stand-in, never a kernel clone.
    monkeypatch.setattr(recovery, "kernel_clone", lambda a, b: b.write_bytes(a.read_bytes()))
    captured = []
    recovery.capture_cluster(source, target, tmp_path, captured, reserve=0, headroom=0)
    assert (target / "pg_tblspc").is_dir()
    assert captured[0]["source_inode"] != captured[0]["clone_inode"]
    (source / "base/published").write_bytes(b"later change to the fake primary")
    recovery.verify_capture(target, captured, tmp_path, reserve=0)
    (target / "base/published").write_bytes(b"mock corruption")
    with pytest.raises(RuntimeError, match="cold source hash"):
        recovery.verify_capture(target, captured, tmp_path, reserve=0)


def test_capture_refuses_live_pid_before_mock_clone(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "postmaster.pid").write_text("synthetic-pid")
    calls = []
    monkeypatch.setattr(recovery, "kernel_clone", lambda *args: calls.append(args))
    with pytest.raises(RuntimeError, match="PID"):
        recovery.capture_cluster(source, tmp_path / "copy", tmp_path, [], reserve=0, headroom=0)
    assert not calls


def test_capture_reserve_failure_does_not_fall_back_to_copy(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "source-file").write_bytes(b"fixture")
    monkeypatch.setattr(recovery.shutil, "disk_usage", lambda p: SimpleNamespace(free=recovery.RESERVE))
    with pytest.raises(RuntimeError, match="headroom"):
        recovery.capture_cluster(source, tmp_path / "clone", tmp_path, [])


@pytest.mark.parametrize("failure", ["stop", "capture", "none"])
def test_cold_capture_always_restores_original_before_any_clone_readback(tmp_path, monkeypatch, failure):
    actions = []
    class Control:
        def smart_stop(self, data):
            actions.append("smart-stop")
            if failure == "stop":
                raise RuntimeError("shutdown pending")
        def ensure_original(self, data, options):
            actions.append("original-state-checked-and-restored")
            return "restarted"
    def capture(*args, **kwargs):
        actions.append("capture")
        if failure == "capture":
            raise RuntimeError("clone unsupported")
        return 100
    monkeypatch.setattr(recovery, "capture_cluster", capture)
    control = Control()
    if failure == "none":
        result = recovery.cold_capture(control, tmp_path, tmp_path / "copy", tmp_path, [], "owned-options")
        assert result["capture_complete"]
    else:
        with pytest.raises(RuntimeError):
            recovery.cold_capture(control, tmp_path, tmp_path / "copy", tmp_path, [], "owned-options")
    assert actions[-1] == "original-state-checked-and-restored"
    assert control.recovery_status["original_restart"] == "restarted"


def test_shutdown_timeout_never_blindly_starts_a_second_primary(tmp_path, monkeypatch):
    control = recovery.ServiceControl(tmp_path, tmp_path, timeout=0)
    monkeypatch.setattr(control, "status", lambda data: 0)
    starts = []
    monkeypatch.setattr(control, "start", lambda *args: starts.append(args))
    assert control.ensure_original(tmp_path, "options") == "running_or_shutdown_pending_no_second_start"
    assert not starts


def test_original_start_occurs_only_after_actual_server_stop(tmp_path, monkeypatch):
    control = recovery.ServiceControl(tmp_path, tmp_path)
    statuses = iter([0, 3])
    monkeypatch.setattr(control, "status", lambda data: next(statuses))
    monkeypatch.setattr(recovery.time, "sleep", lambda value: None)
    starts = []
    monkeypatch.setattr(control, "start", lambda *args: starts.append(args))
    assert control.ensure_original(tmp_path, "safe-options") == "restarted"
    assert starts == [(tmp_path, "safe-options", "original-restart")]


def test_clone_options_bind_all_paths_and_disable_external_activity(tmp_path):
    data, socket = tmp_path / "data", tmp_path / "private-socket"
    tokens = shlex.split(recovery.server_options(data, socket, 55486, clone=True))
    values = dict(value.split("=", 1) for option, value in zip(tokens[::2], tokens[1::2]) if option == "-c")
    assert values["data_directory"] == str(data)
    for name, filename in [("config_file", "postgresql.conf"), ("hba_file", "pg_hba.conf"), ("ident_file", "pg_ident.conf")]:
        assert values[name] == str(data / filename)
    assert values["unix_socket_directories"] == str(socket)
    assert values["port"] == "55486" and values["listen_addresses"] == ""
    assert values["default_transaction_read_only"] == "on" and values["autovacuum"] == "off"
    assert all(values[k] == "" for k in recovery.CALLBACKS)
    assert values["external_pid_file"] == "" and values["log_directory"] == str(data / "log")


def test_unverified_clone_pid_never_authorizes_stop(tmp_path):
    data, socket = tmp_path / "copy", tmp_path / "socket"
    data.mkdir()
    (data / "postmaster.pid").write_text("123\n/original/primary\n0\n55485\n/original/socket\n")
    with pytest.raises(ValueError, match="Refusing to stop"):
        recovery.stop_clone(SimpleNamespace(), data, socket)


def identity(data, socket):
    return {"database": recovery.TARGET, "database_oid": 10, "marker": "owned",
        "cluster_system_identifier": "system", "data_directory": str(data), "socket": str(socket),
        "port": "55486", "listen_addresses": "", "transaction_read_only": "on",
        "unix_socket": True, "in_recovery": False}


@pytest.mark.parametrize("key,value", [("data_directory", "/original"), ("port", "55485"),
    ("transaction_read_only", "off"), ("database_oid", 11), ("listen_addresses", "localhost")])
def test_actual_clone_identity_must_match_before_research_queries(tmp_path, key, value):
    row = identity(tmp_path / "data", tmp_path / "socket")
    target = {k: row[k] for k in ("database", "database_oid", "marker", "cluster_system_identifier")}
    row[key] = value
    with pytest.raises(ValueError):
        recovery.assert_instance(row, target, tmp_path / "data", tmp_path / "socket", 55486)


def test_report_and_dangling_symlink_cannot_be_overwritten(tmp_path):
    report = tmp_path / "report.json"
    report.write_text("earlier sealed receipt")
    with pytest.raises(FileExistsError):
        recovery.exclusive_json(report, {"passed": True})
    assert report.read_text() == "earlier sealed receipt"
    report.unlink()
    report.symlink_to(tmp_path / "missing")
    with pytest.raises(FileExistsError):
        recovery.exclusive_json(report, {})


def test_reserve_monitor_cancels_only_its_supplied_read_only_session(tmp_path, monkeypatch):
    free = iter([recovery.RESERVE + 100 * 1024**2, recovery.RESERVE + 1, recovery.RESERVE])
    monkeypatch.setattr(recovery.shutil, "disk_usage", lambda p: SimpleNamespace(free=next(free)))
    cancellations = []
    monitor = recovery.FreeSpaceMonitor(tmp_path, recovery.RESERVE, lambda: cancellations.append("owned-session"))
    monitor.sample()
    monitor.sample()
    assert cancellations == ["owned-session"]
    assert monitor.breached.is_set()


def test_operator_cannot_run_without_explicit_operator_execution_flag(tmp_path):
    with pytest.raises(ValueError, match="explicit operator invocation"):
        recovery.main(["--repository", str(tmp_path), "--output", str(tmp_path / "report.json")])


def test_completed_query_verification_is_required_before_live_connection(tmp_path, monkeypatch):
    packet = tmp_path / recovery.PACKET
    packet.mkdir(parents=True)
    target = {"database": recovery.TARGET, "database_oid": 1, "marker": "owned", "cluster_system_identifier": "cluster"}
    contract = {"target": target, "build_id": "build"}
    verifier = SimpleNamespace(load_contract=lambda *args: contract, read_json=lambda p: json.loads(p.read_text()))
    monkeypatch.setattr(recovery, "verifier_module", lambda root: verifier)
    (packet / "QUERY_VERIFICATION.json").write_text(json.dumps({"passed": False}))
    with pytest.raises(ValueError, match="passing query verification"):
        recovery.load_prerequisites(tmp_path)


def test_coordinator_excludes_a_second_operator_without_database_activity(tmp_path):
    tmp_path.chmod(0o700)
    with recovery.coordinator(tmp_path):
        with pytest.raises(RuntimeError, match="coordinator"):
            with recovery.coordinator(tmp_path):
                pytest.fail("Second operator must not own the primary")


@pytest.mark.parametrize("journal_failure", [False, True])
def test_private_run_identity_is_written_before_any_service_change(monkeypatch, journal_failure):
    # A deliberately short synthetic root also exercises the macOS socket bound.
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="q-") as name:
        root = Path(name).resolve()
        state = root / "infrastructure/daylight-data/.state"
        state.mkdir(parents=True, mode=0o700)
        packet = root / recovery.PACKET
        packet.mkdir(parents=True)
        target = {"database": recovery.TARGET, "database_oid": 1, "marker": "fixture",
                  "cluster_system_identifier": "fixture-cluster"}
        contract = {"target": target, "build_id": "fixture-build"}
        before = {"identity": target, "other_clients": 0, "prepared_transactions": 0,
                  "replication_slots": 0}
        monkeypatch.setenv("DAYLIGHT_DATA_DATABASE_URL", "synthetic-only")
        monkeypatch.setattr(recovery, "load_prerequisites", lambda repository: (None, contract, {}))
        monkeypatch.setattr(recovery, "source_dsn", lambda value, repository: "synthetic-only")
        monkeypatch.setattr(recovery, "preflight", lambda *args: before)
        monkeypatch.setattr(recovery, "ServiceControl", lambda *args: SimpleNamespace(actions=[]))
        monkeypatch.setattr(recovery, "primary_health", lambda *args: {"healthy": True})
        monkeypatch.setattr(recovery.shutil, "disk_usage", lambda path: SimpleNamespace(free=20 * 1024**3))
        calls = []

        def check_journal_before_capture(control, *args, **kwargs):
            journals = list((state / "recovery-rehearsals").glob("*/RUN_START.json"))
            assert len(journals) == 1
            journal = json.loads(journals[0].read_text())
            assert journals[0].stat().st_mode & 0o077 == 0
            assert journal["target"] == target and journal["preflight_identity"] == target
            assert journal["original_data_directory"] == str(state / "pgdata")
            assert journal["clone_port"] == 55486 and journal["service_change_started"] is False
            assert journal["operator_code_sha256"] == recovery.sha(Path(recovery.__file__))
            calls.append("journal-checked-before-mocked-capture")
            raise RuntimeError("Synthetic capture failure; no service action")

        monkeypatch.setattr(recovery, "cold_capture", check_journal_before_capture)
        if journal_failure:
            original_writer = recovery.exclusive_json
            def failed_journal(path, value):
                if path.name == "RUN_START.json":
                    raise OSError("Synthetic journal failure")
                return original_writer(path, value)
            monkeypatch.setattr(recovery, "exclusive_json", failed_journal)
        args = SimpleNamespace(execute_cold_rehearsal=True, reserve_gib=7, startup_headroom_gib=2,
                               repository=root, output=packet / "RECOVERY.json")
        if journal_failure:
            with pytest.raises(OSError, match="journal failure"):
                recovery.rehearse(args)
            assert not calls
        else:
            assert recovery.rehearse(args) == 1
            report = json.loads(args.output.read_text())
            assert calls == ["journal-checked-before-mocked-capture"]
            assert report["original_final_health"]["healthy"]
            assert report["service_actions"] == []
            assert len(report["run_start_journal_sha256"]) == 64
