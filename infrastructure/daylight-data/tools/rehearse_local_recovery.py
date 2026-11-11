"""Optional, explicit same-host cold APFS whole-cluster recovery rehearsal.

No database is dropped and no primary file is removed or replaced. This operator
requires an explicit operator invocation: importing it or running tests never
controls a service. A successful result proves a local physical copy can start and answer
the bounded research checks, not a logical dump restore or off-machine recovery.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
from datetime import datetime, timezone
import errno
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import stat
import subprocess
import threading
import time
import uuid

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row

TARGET = "daylight_research_2026_r2"
PACKET = "docs/data/infrastructure-execution-2026-10-30-local-full-db/build-r3"
SUMMARY = "docs/data/infrastructure-execution-2026-10-30-local-sizing/SUMMARY.json"
PROFILE_COUNT = (41, 78, 14)
CLONE_PORT = 55486
RESERVE = 7 * 1024**3
HEADROOM = 2 * 1024**3
CALLBACKS = ("archive_command", "archive_library", "restore_command", "archive_cleanup_command", "recovery_end_command",
             "primary_conninfo", "primary_slot_name", "ssl_passphrase_command",
             "shared_preload_libraries", "session_preload_libraries", "local_preload_libraries")
SETTING_NAMES = ("data_directory", "config_file", "hba_file", "ident_file", "external_pid_file", "port",
                 "unix_socket_directories", "listen_addresses", "archive_mode", "ssl", "default_transaction_read_only") + CALLBACKS


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    value = hashlib.sha256()
    before = path.stat()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise RuntimeError("A captured file changed while hashing")
    return value.hexdigest()


def fresh(path):
    if path.exists() or path.is_symlink():
        raise FileExistsError("Rehearsal evidence/destination already exists")


def exclusive_json(path, value):
    fresh(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def private_directory(path, *, create=False):
    if path.is_symlink():
        raise ValueError("Private rehearsal directories cannot be symlinks")
    if create:
        path.mkdir(mode=0o700)
    if not path.is_dir() or path.stat().st_mode & 0o077:
        raise ValueError("Rehearsal directory must be private")


def disk_guard(repository, reserve=RESERVE, headroom=0):
    available = shutil.disk_usage(repository).free
    if available < reserve + headroom:
        raise RuntimeError("Cold rehearsal stopped at the reserved disk/headroom boundary")
    return available


@contextmanager
def coordinator(state):
    """One operator for this primary, without adding a client that blocks stop."""
    private_directory(state)
    path = state / "cold-rehearsal.lock"
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode) or os.fstat(fd).st_mode & 0o077:
            raise ValueError("Private regular coordinator lock required")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("Another cold-rehearsal coordinator owns this primary") from error
        yield
    finally:
        os.close(fd)


def verifier_module(repository):
    path = repository / "infrastructure/daylight-data/tools/verify_local_database.py"
    spec = importlib.util.spec_from_file_location("cold_rehearsal_verifier", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_prerequisites(repository):
    verifier = verifier_module(repository)
    packet = repository / PACKET
    contract = verifier.load_contract(repository, packet, repository / SUMMARY)
    verification_path = packet / "QUERY_VERIFICATION.json"
    if verification_path.is_symlink():
        raise ValueError("Query verification cannot be a symlink")
    verification = verifier.read_json(verification_path)
    expected = {"schema": "daylight-local-full-verification/1", "database": TARGET,
                "build_id": contract["build_id"], "passed": True, "selected_units": 363,
                "expected_source_rows": 17767179, "expected_projection_rows": 17823148,
                "new_acceptance": False, "consumer_release_enabled": False,
                "full_domain_models_complete": False, "cloud_deployed": False}
    if any(verification.get(k) != v for k, v in expected.items()):
        raise ValueError("Exact completed r2 and passing query verification are required")
    if not verification.get("proof_matrix") or not verification.get("query_measurements"):
        raise ValueError("Query verification must contain executed proofs and measurements")
    if not all(p.get("passed") is True for p in verification["proof_matrix"]) or not all(
            q.get("success") is True for q in verification["query_measurements"]):
        raise ValueError("An incomplete query proof cannot authorize a rehearsal")
    target = contract["target"]
    if any(verification["ownership"].get(k) != target[k] for k in (
            "database", "database_oid", "marker", "cluster_system_identifier")):
        raise ValueError("Passing query report has a different target identity")
    return verifier, contract, {"query_verification_sha256": sha(verification_path),
                                "verifier_sha256": sha(repository / "infrastructure/daylight-data/tools/verify_local_database.py")}


def source_dsn(value, repository):
    info = conninfo_to_dict(value)
    socket = str(repository / "infrastructure/daylight-data/.state/socket")
    if (info.get("host") != socket or info.get("port") != "55485" or info.get("dbname") != TARGET
            or info.get("hostaddr") or info.get("service")):
        raise ValueError("Exact original private r2 endpoint required")
    return make_conninfo(value, options="-c default_transaction_read_only=on -c statement_timeout=120000 "
                         "-c lock_timeout=3000", connect_timeout="5")


INSTANCE_SQL = """SELECT current_database() AS database,d.oid AS database_oid,
    shobj_description(d.oid,'pg_database') AS marker,
    (SELECT system_identifier::text FROM pg_control_system()) AS cluster_system_identifier,
    current_setting('data_directory') AS data_directory,current_setting('port') AS port,
    current_setting('unix_socket_directories') AS socket,current_setting('listen_addresses') AS listen_addresses,
    current_setting('transaction_read_only') AS transaction_read_only,
    inet_server_addr() IS NULL AS unix_socket,pg_is_in_recovery() AS in_recovery
    FROM pg_database d WHERE d.datname=current_database()"""


def assert_instance(row, target, data, socket, port):
    if row is None or any(row[k] != target[k] for k in (
            "database", "database_oid", "marker", "cluster_system_identifier")):
        raise ValueError("Actual server target/cluster ownership differs")
    if (row["data_directory"] != str(data) or row["socket"] != str(socket) or row["port"] != str(port)
            or row["listen_addresses"] != "" or row["transaction_read_only"] != "on"
            or row["unix_socket"] is not True or row["in_recovery"] is not False):
        raise ValueError("Actual server data path/private endpoint/read-only state differs")


def regular_inventory(data):
    if data.is_symlink() or not data.is_dir():
        raise ValueError("An owned regular cluster directory is required")
    files = []
    for parent, directories, names in os.walk(data, followlinks=False):
        for name in directories + names:
            path = Path(parent) / name
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise ValueError("Unhandled cluster symlink/external/special path")
            if stat.S_ISREG(mode):
                files.append(path)
    if any((data / name).exists() for name in ("standby.signal", "recovery.signal", "backup_label")):
        raise ValueError("Recovery/standby/unfinished backup state is not supported")
    for name in ("pg_replslot", "pg_twophase"):
        directory = data / name
        if directory.exists() and any(directory.iterdir()):
            raise ValueError("Replication-slot or prepared-transaction files prevent capture")
    for name in ("postgresql.conf", "postgresql.auto.conf", "pg_hba.conf", "pg_ident.conf"):
        path = data / name
        if path.exists():
            for line in path.read_text().splitlines():
                statement = line.strip().lower()
                if statement and not statement.startswith("#") and statement.split("=", 1)[0].strip().split()[0] in {
                        "include", "include_if_exists", "include_dir"}:
                    raise ValueError("Configuration includes require an explicit external-path policy")
    return sorted(files)


def validate_preflight(settings, other_clients, prepared, slots, databases, repository):
    data = repository / "infrastructure/daylight-data/.state/pgdata"
    socket = repository / "infrastructure/daylight-data/.state/socket"
    expected = {"data_directory": str(data), "config_file": str(data / "postgresql.conf"),
                "hba_file": str(data / "pg_hba.conf"), "ident_file": str(data / "pg_ident.conf"),
                "external_pid_file": "", "port": "55485", "unix_socket_directories": str(socket),
                "listen_addresses": "", "archive_mode": "off", "ssl": "off"}
    if any(settings.get(k) != v for k, v in expected.items()) or any(settings.get(k) for k in CALLBACKS):
        raise ValueError("External configuration, callbacks, replication or endpoint is not supported")
    if other_clients or prepared or slots:
        raise ValueError("Other clients, prepared transactions or replication slots prevent a cold rehearsal")
    allowed = {"postgres", "template0", "template1", "daylight_data_test", "daylight_research_2026_r1", TARGET}
    if set(databases) - allowed or TARGET not in databases or "daylight_data_test" not in databases:
        raise ValueError("Cluster contains an unhandled database outside the owned project scope")


def preflight(dsn, repository, target):
    with psycopg.connect(dsn, autocommit=True, row_factory=dict_row) as connection:
        with connection.transaction():
            connection.execute("SET TRANSACTION READ ONLY")
            identity = connection.execute(INSTANCE_SQL).fetchone()
            assert_instance(identity, target, repository / "infrastructure/daylight-data/.state/pgdata",
                            repository / "infrastructure/daylight-data/.state/socket", 55485)
            settings = {r["name"]: r["setting"] for r in connection.execute(
                "SELECT name,setting FROM pg_settings WHERE name=ANY(%s)", (list(SETTING_NAMES),))}
            other = connection.execute("""SELECT count(*) AS n FROM pg_stat_activity
                WHERE pid<>pg_backend_pid() AND backend_type IN ('client backend','walsender','walreceiver')""").fetchone()["n"]
            prepared = connection.execute("SELECT count(*) AS n FROM pg_prepared_xacts").fetchone()["n"]
            slots = connection.execute("SELECT count(*) AS n FROM pg_replication_slots").fetchone()["n"]
            databases = [r["datname"] for r in connection.execute("SELECT datname FROM pg_database ORDER BY datname")]
            validate_preflight(settings, other, prepared, slots, databases, repository)
    regular_inventory(repository / "infrastructure/daylight-data/.state/pgdata")
    return {"identity": identity, "settings": settings, "databases": databases,
            "other_clients": other, "prepared_transactions": prepared, "replication_slots": slots}


def clean_environment():
    environment = {k: v for k, v in os.environ.items() if not k.startswith("PG")}
    environment["LC_ALL"] = "C"
    return environment


class ServiceControl:
    def __init__(self, repository, run, timeout=60):
        self.bin = repository / "infrastructure/daylight-data/.postgres18/bin"
        self.run = run
        self.timeout = timeout
        self.actions = []

    def command(self, label, arguments, *, timeout=None):
        result = subprocess.run([str(a) for a in arguments], capture_output=True, text=True,
                                env=clean_environment(), timeout=timeout or self.timeout + 10)
        descriptor = os.open(self.run / (label + ".log"), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(descriptor, "a") as handle:
            handle.write(result.stdout + result.stderr)
        self.actions.append({"operation": label, "returncode": result.returncode, "observed_at": now()})
        return result

    def status(self, data):
        result = self.command("status", [self.bin / "pg_ctl", "status", "-D", data])
        if result.returncode not in (0, 3):
            raise RuntimeError("Server status is unknown; refusing service control")
        return result.returncode

    def smart_stop(self, data):
        result = self.command("original-smart-stop", [self.bin / "pg_ctl", "stop", "-D", data,
            "-m", "smart", "-w", "-t", str(self.timeout)])
        if result.returncode or self.status(data) != 3:
            raise RuntimeError("Smart shutdown did not finish; it may still be continuing in the background")
        state = self.command("cold-control", [self.bin / "pg_controldata", "-D", data])
        if state.returncode or not any(line.split(":", 1)[-1].strip() == "shut down"
                for line in state.stdout.splitlines() if line.startswith("Database cluster state:")):
            raise RuntimeError("A cleanly shut down whole cluster is required")

    def start(self, data, options, label):
        result = self.command(label, [self.bin / "pg_ctl", "start", "-D", data,
            "-l", self.run / (label + "-server.log"), "-o", options, "-w", "-t", str(self.timeout)])
        if result.returncode:
            raise RuntimeError("Server startup did not complete; inspect private rehearsal logs")

    def ensure_original(self, data, options):
        # A timed-out smart shutdown can remain in progress. Wait for its actual
        # state; never call start while an original server is still running.
        deadline = time.monotonic() + self.timeout
        while self.status(data) == 0:
            if time.monotonic() >= deadline:
                return "running_or_shutdown_pending_no_second_start"
            time.sleep(0.25)
        self.start(data, options, "original-restart")
        return "restarted"


def server_options(data, socket, port, *, clone):
    settings = {"data_directory": str(data), "config_file": str(data / "postgresql.conf"),
        "hba_file": str(data / "pg_hba.conf"), "ident_file": str(data / "pg_ident.conf"),
        "external_pid_file": "", "unix_socket_directories": str(socket), "unix_socket_permissions": "0700",
        "listen_addresses": "", "port": str(port)}
    if clone:
        settings.update(default_transaction_read_only="on", autovacuum="off", archive_mode="off",
            archive_command="", archive_library="", restore_command="", archive_cleanup_command="", recovery_end_command="",
            primary_conninfo="", primary_slot_name="", ssl="off", ssl_passphrase_command="",
            shared_preload_libraries="", session_preload_libraries="", local_preload_libraries="",
            logging_collector="off", log_destination="stderr", log_directory=str(data / "log"))
    return " ".join("-c " + shlex.quote(key + "=" + value) for key, value in settings.items())


def kernel_clone(source, destination):
    fresh(destination)
    library = ctypes.CDLL(None, use_errno=True)
    try:
        clonefile = library.clonefile
    except AttributeError as error:
        raise RuntimeError("Kernel clonefile unavailable; full-copy fallback is forbidden") from error
    clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
    clonefile.restype = ctypes.c_int
    if clonefile(os.fsencode(source), os.fsencode(destination), 0) != 0:
        raise OSError(ctypes.get_errno() or errno.EIO, "Kernel clonefile failed; no copy fallback is permitted")


def capture_cluster(source, destination, repository, captured, *, reserve=RESERVE, headroom=HEADROOM):
    if (source / "postmaster.pid").exists():
        raise RuntimeError("Primary PID file still exists; refusing a live per-file copy")
    fresh(destination)
    private_directory(destination, create=True)
    minimum = disk_guard(repository, reserve, headroom)
    for path in regular_inventory(source):
        if (source / "postmaster.pid").exists():
            raise RuntimeError("Original server restarted during cold capture")
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        before = path.stat()
        source_hash = sha(path)
        minimum = min(minimum, disk_guard(repository, reserve, headroom))
        kernel_clone(path, target)
        after = path.stat()
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise RuntimeError("Original file changed during cold clone capture")
        cloned = target.lstat()
        if (not stat.S_ISREG(cloned.st_mode) or cloned.st_dev != before.st_dev
                or cloned.st_ino == before.st_ino or cloned.st_size != before.st_size):
            raise RuntimeError("Clone must have independent regular-file identity and exact size on the same filesystem")
        target.chmod(0o600)
        captured.append({"path": str(relative), "bytes": before.st_size, "source_sha256": source_hash,
                         "source_inode": before.st_ino, "clone_inode": cloned.st_ino})
    # Empty directories matter (for example pg_tblspc/archive_status).
    for parent, directories, _ in os.walk(source, followlinks=False):
        for name in directories:
            (destination / (Path(parent) / name).relative_to(source)).mkdir(parents=True, exist_ok=True, mode=0o700)
    if (source / "postmaster.pid").exists():
        raise RuntimeError("Original server restarted during cold capture")
    if {str(p.relative_to(source)) for p in regular_inventory(source)} != {r["path"] for r in captured}:
        raise RuntimeError("Whole-cluster file inventory changed during capture")
    return minimum


def cold_capture(control, source, destination, repository, captured, original_options, **guards):
    result = {"original_restart": "not_requested", "capture_complete": False}
    control.recovery_status = result
    try:
        control.smart_stop(source)
        result["minimum_free_bytes"] = capture_cluster(source, destination, repository, captured, **guards)
        result["capture_complete"] = True
        return result
    finally:
        # Also runs after a smart-stop timeout or a failed hash/clone syscall.
        result["original_restart"] = control.ensure_original(source, original_options)


def verify_capture(destination, captured, repository, reserve=RESERVE):
    if {str(p.relative_to(destination)) for p in regular_inventory(destination)} != {r["path"] for r in captured}:
        raise RuntimeError("Captured whole-cluster file inventory differs")
    for item in captured:
        disk_guard(repository, reserve)
        path = destination / item["path"]
        if path.is_symlink() or sha(path) != item["source_sha256"] or path.stat().st_size != item["bytes"]:
            raise RuntimeError("Captured clone bytes differ from the cold source hash")


def owned_clone_pid(data, socket):
    pidfile = data / "postmaster.pid"
    if not pidfile.exists():
        return None
    if pidfile.is_symlink():
        raise ValueError("Clone PID file cannot be a symlink")
    lines = pidfile.read_text().splitlines()
    if (len(lines) < 5 or lines[1] != str(data) or lines[3] != str(CLONE_PORT)
            or lines[4] != str(socket) or not lines[0].isdigit()):
        raise ValueError("Refusing to stop a process without exact owned clone data/socket/port identity")
    return int(lines[0])


def stop_clone(control, data, socket):
    pid = owned_clone_pid(data, socket)
    if pid is None:
        return "not_running"
    result = control.command("clone-smart-stop", [control.bin / "pg_ctl", "stop", "-D", data,
        "-m", "smart", "-w", "-t", str(control.timeout)])
    if result.returncode or control.status(data) != 3:
        raise RuntimeError("Verified clone shutdown is pending; preserved private files require operator attention")
    return "stopped"


class FreeSpaceMonitor:
    def __init__(self, repository, reserve, cancel):
        self.repository, self.reserve, self.cancel = repository, reserve, cancel
        self.minimum = shutil.disk_usage(repository).free
        self.breached = threading.Event()
        self.finished = threading.Event()

    def sample(self):
        free = shutil.disk_usage(self.repository).free
        self.minimum = min(self.minimum, free)
        if free < self.reserve + 64 * 1024**2 and not self.breached.is_set():
            self.breached.set()
            try:
                self.cancel()
            except Exception as error:
                self.cancel_error_type = type(error).__name__

    def __enter__(self):
        def watch():
            while not self.finished.wait(0.25):
                self.sample()
        self.thread = threading.Thread(target=watch, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.finished.set()
        self.thread.join(timeout=2)


def verify_clone(verifier, contract, dsn, data, socket, repository, reserve):
    with psycopg.connect(dsn, autocommit=True, row_factory=dict_row) as connection:
        with connection.transaction():
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            identity = connection.execute(INSTANCE_SQL).fetchone()
            assert_instance(identity, contract["target"], data, socket, CLONE_PORT)
            migrations = connection.execute("SELECT name,sha256 FROM dl_migrations.applied ORDER BY name").fetchall()
            expected = {Path(k).name: v for k, v in contract["manifest"]["executable_files"].items() if "/migrations/" in k}
            if {r["name"]: r["sha256"] for r in migrations} != expected:
                raise ValueError("Restored migration history differs")
            connection.execute("SET LOCAL ROLE daylight_research_reader")
            with FreeSpaceMonitor(repository, reserve, connection.cancel) as monitor:
                class GuardedMeasurements(verifier.Measurements):
                    def query(self, *args, **kwargs):
                        if monitor.breached.is_set():
                            raise RuntimeError("Reserve monitor canceled restored-copy verification")
                        disk_guard(repository, reserve)
                        answer = super().query(*args, **kwargs)
                        disk_guard(repository, reserve)
                        return answer
                m = GuardedMeasurements(connection)
                rows = m.query("restored_all_layer_counts", """SELECT
                    (SELECT count(*) FROM dl_evidence.source_record) AS raw_rows,
                    (SELECT count(*) FROM dl_evidence.observation) AS projection_rows,
                    (SELECT count(DISTINCT layer_id) FROM dl_control.source_snapshot) AS layers""")
                expected_rows = [{"raw_rows": 17767179, "projection_rows": 17823148, "layers": 15}]
                m.proof("all fifteen populations restored together", rows == expected_rows, rows, expected_rows)
                verifier.verify_metadata(m, contract)
                verifier.verify_units(m, contract)
                verifier.verify_domains(m, contract)
                verifier.verify_boundaries(m)
                connection.execute("SET LOCAL ROLE daylight_released_reader")
                released = m.query("restored_consumer_hold", "SELECT count(*) AS rows FROM dl_released.offerings")
                m.proof("consumer release remains empty", released == [{"rows": 0}], released, [{"rows": 0}])
                passed = (not monitor.breached.is_set() and all(p["passed"] for p in m.proofs)
                          and all(q["success"] for q in m.queries))
                return {"passed": passed, "identity": identity, "proof_matrix": m.proofs,
                        "query_measurements": m.queries, "minimum_free_bytes": monitor.minimum,
                        "raw_payload_stream_rehashed": False}


def primary_health(dsn, repository, target):
    with psycopg.connect(dsn, autocommit=True, row_factory=dict_row) as connection:
        with connection.transaction():
            connection.execute("SET TRANSACTION READ ONLY")
            identity = connection.execute(INSTANCE_SQL).fetchone()
            assert_instance(identity, target, repository / "infrastructure/daylight-data/.state/pgdata",
                            repository / "infrastructure/daylight-data/.state/socket", 55485)
            connection.execute("SET LOCAL ROLE daylight_research_reader")
            counts = connection.execute("""SELECT
                (SELECT count(*) FROM dl_evidence.source_record) AS raw_rows,
                (SELECT count(*) FROM dl_evidence.observation) AS projection_rows""").fetchone()
            if counts != {"raw_rows": 17767179, "projection_rows": 17823148}:
                raise ValueError("Original full database population changed")
    old = make_conninfo(dsn, dbname="daylight_data_test")
    with psycopg.connect(old, autocommit=True, row_factory=dict_row) as connection:
        with connection.transaction():
            connection.execute("SET TRANSACTION READ ONLY")
            connection.execute("SET LOCAL ROLE daylight_research_reader")
            main = connection.execute("""SELECT count(*) AS source_rows,
                (SELECT count(*) FROM dl_control.ingest_receipt) AS receipts FROM dl_evidence.source_record""").fetchone()
            if main != {"source_rows": 1960454, "receipts": 8}:
                raise ValueError("Preserved original database population changed")
    return {"healthy": True, "identity": identity, "full_database_counts": counts, "preserved_main_counts": main}


def rehearse(args):
    if not args.execute_cold_rehearsal:
        raise ValueError("An explicit operator invocation with --execute-cold-rehearsal is required")
    if args.reserve_gib < 7 or args.startup_headroom_gib < 1:
        raise ValueError("Reserve >=7 GiB and startup headroom >=1 GiB are mandatory")
    repository = args.repository.resolve()
    output = args.output.absolute()
    fresh(output)
    if (not output.parent.is_dir() or not output.parent.resolve().is_relative_to(repository / PACKET)):
        raise ValueError("An existing report parent inside the exact r2 packet is required")
    reserve, headroom = int(args.reserve_gib * 1024**3), int(args.startup_headroom_gib * 1024**3)
    verifier, contract, prerequisites = load_prerequisites(repository)
    dsn = source_dsn(os.environ["DAYLIGHT_DATA_DATABASE_URL"], repository)
    before = preflight(dsn, repository, contract["target"])
    state = repository / "infrastructure/daylight-data/.state"
    private_directory(state)
    parent = state / "recovery-rehearsals"
    if not parent.exists():
        private_directory(parent, create=True)
    private_directory(parent)
    run = parent / uuid.uuid4().hex
    private_directory(run, create=True)
    socket = state / "recovery-socket-55486"
    fresh(socket)
    if len(str(socket / ".s.PGSQL.55486").encode()) > 100:
        raise ValueError("Private clone Unix socket path exceeds the conservative platform bound")
    private_directory(socket, create=True)
    data, clone = state / "pgdata", run / "data"
    start_free = disk_guard(repository, reserve, headroom)
    control = ServiceControl(repository, run)
    captured = []
    result = {"schema": "daylight-local-cold-physical-recovery/1", "database": TARGET,
              "build_id": contract["build_id"], "observed_at": now(), "passed": False,
              "scope": "same-host APFS cold whole-cluster physical recovery rehearsal",
              "new_acceptance": False, "consumer_release_enabled": False, "cloud_deployed": False,
              "logical_dump_restored": False, "off_machine_copy_created": False,
              "copy_method": "kernel clonefile only; independent inodes; no full-copy fallback",
              "prerequisites": prerequisites, "original_preflight": before,
              "private_run_directory": str(run), "clone_data_directory": str(clone),
              "clone_socket": str(socket), "clone_port": CLONE_PORT,
              "start_free_bytes": start_free, "reserve_bytes": reserve, "startup_headroom_bytes": headroom,
              "limitations": ["Same-disk COW blocks share a device failure domain; this is not an off-machine backup.",
                              "Clone startup/read queries may allocate COW control/WAL/hint-bit blocks.",
                              "Physical startup/query proofs do not prove logical dump restoration or PITR.",
                              "Row transport and recovered holds do not establish domain or release acceptance.",
                              "In-process cleanup cannot guarantee restart after machine power loss or SIGKILL."]}
    journal = {"schema": "daylight-cold-rehearsal-run-start/1", "observed_at": now(),
               "operator_pid": os.getpid(), "operator_code_sha256": sha(Path(__file__).resolve()),
               "build_id": contract["build_id"], "target": contract["target"],
               "run_directory": str(run), "report_path": str(output),
               "original_data_directory": str(data), "original_socket": str(state / "socket"), "original_port": 55485,
               "clone_data_directory": str(clone), "clone_socket": str(socket), "clone_port": CLONE_PORT,
               "preflight_identity": before["identity"], "other_clients": before["other_clients"],
               "prepared_transactions": before["prepared_transactions"], "replication_slots": before["replication_slots"],
               "reserve_bytes": reserve, "startup_headroom_bytes": headroom, "start_free_bytes": start_free,
               "service_change_started": False, "new_acceptance": False}
    # Private/fsynced identity evidence exists before the first service command,
    # including if an interruption prevents a final report from being written.
    exclusive_json(run / "RUN_START.json", journal)
    result["run_start_journal_sha256"] = sha(run / "RUN_START.json")
    clone_attempted = False
    try:
        result["cold_capture"] = cold_capture(control, data, clone, repository, captured,
            server_options(data, state / "socket", 55485, clone=False), reserve=reserve, headroom=headroom)
        # Original restart happens inside cold_capture's finally, before any
        # clone readback/startup or lengthy verification.
        result["original_health_after_capture"] = primary_health(dsn, repository, contract["target"])
        verify_capture(clone, captured, repository, reserve)
        result["capture_hashes_verified"] = True
        disk_guard(repository, reserve, headroom)
        clone_attempted = True
        control.start(clone, server_options(clone, socket, CLONE_PORT, clone=True), "clone-start")
        clone_dsn = make_conninfo(dsn, host=str(socket), port=str(CLONE_PORT), dbname=TARGET)
        result["restored_queries"] = verify_clone(verifier, contract, clone_dsn, clone, socket, repository, reserve)
        result["passed"] = result["restored_queries"]["passed"]
    except BaseException as error:
        result["error_type"] = type(error).__name__
        result["sqlstate"] = getattr(error, "sqlstate", None)
    finally:
        result["original_restart_status"] = getattr(control, "recovery_status", {})
        result["captured_regular_files"] = len(captured)
        result["captured_logical_bytes"] = sum(f["bytes"] for f in captured)
        # Service cleanup precedes evidence I/O: a report filesystem error must
        # never bypass shutdown of this independently verified clone.
        if clone_attempted:
            try:
                result["clone_final_state"] = stop_clone(control, clone, socket)
            except BaseException as error:
                result["clone_final_state"] = "unresolved_verified_copy_shutdown"
                result["clone_shutdown_error_type"] = type(error).__name__
                result["passed"] = False
        try:
            result["original_final_health"] = primary_health(dsn, repository, contract["target"])
        except BaseException as error:
            result["original_final_health"] = {"healthy": False, "error_type": type(error).__name__}
            result["passed"] = False
        result["end_free_bytes"] = shutil.disk_usage(repository).free
        result["free_space_delta_bytes"] = start_free - result["end_free_bytes"]
        result["minimum_observed_free_bytes"] = min(start_free, result["end_free_bytes"],
            result.get("cold_capture", {}).get("minimum_free_bytes", start_free),
            result.get("restored_queries", {}).get("minimum_free_bytes", start_free))
        if result["end_free_bytes"] < reserve:
            result["passed"] = False
        result["service_actions"] = control.actions
        try:
            exclusive_json(run / "CAPTURE.json", {"files": captured, "whole_capture_complete": result.get("capture_hashes_verified", False)})
            result["capture_manifest_sha256"] = sha(run / "CAPTURE.json")
        except BaseException as error:
            result["capture_manifest_error_type"] = type(error).__name__
            result["passed"] = False
        exclusive_json(output, result)
    print(json.dumps({"passed": result["passed"], "report": str(output)}), flush=True)
    return 0 if result["passed"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--execute-cold-rehearsal", action="store_true")
    parser.add_argument("--reserve-gib", type=float, default=7)
    parser.add_argument("--startup-headroom-gib", type=float, default=2)
    args = parser.parse_args(argv)
    if not args.execute_cold_rehearsal:
        raise ValueError("An explicit operator invocation with --execute-cold-rehearsal is required")
    with coordinator(args.repository.resolve() / "infrastructure/daylight-data/.state"):
        return rehearse(args)


if __name__ == "__main__":
    raise SystemExit(main())
