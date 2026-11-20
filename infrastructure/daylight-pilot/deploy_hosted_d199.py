#!/usr/bin/env python3
"""D199: deploy the :8895 wiring to the hosted invited demo, test site first.

build (local):   reconstruct the exact deployed release, select the current workspace
                 inputs, and write a delta bundle, a plan and a CloudShell transfer zip.
apply (host):    as root, stage the immutable release, migrate the history block table,
                 restore the doctor/drug database once, then switch ONE environment
                 (test, then pilot) with drain, readiness checks and automatic rollback.
rollback (host): put one environment back on its previous unit and configuration.
renew-pricing:   write the root-managed weekly price review and restart both services.

No provider call, credential read, quota/ledger change, invitation change or DNS change.
The invitation links stay the same. Doctor/drug checks run on one environment at a time
(about 1.4 GB of memory each on the 4 GB host).
"""
import argparse
import copy
import datetime as dt
import fcntl
import gzip
import hashlib
import http.client
import json
import os
from pathlib import Path
import pwd
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import zipfile

DEPLOYED = 'c7cec20f91e8a92e6164463d293362f83464c453fcdd460ed5b00c742063feeb'
BASELINE = '63ab51328bf138f0e2425c8e218cee8828263594e3ed866d391a5d1a7575736b'
SCOPE = 'fictional_invited_hosted_demo'
HOST_ROOT = Path('/opt/daylight-pilot')
STATE = Path('/var/lib/daylight-state')
SOCKET = STATE / 'pgsocket'
CONFIG = Path('/etc/daylight-pilot/runtime')
UNITS = Path('/etc/systemd/system')
PRICING = Path('/etc/daylight-pilot/pricing-review.json')
PYTHON = '/opt/daylight-runtime/venv-3.14.7/bin/python'
APP = 'daylight-app'
FOUNDATION_DB = 'daylight_pilot_foundation_2026_r1'
CONTROLS_DB = 'daylight_source_controls_2026'
PORTS = {'pilot': (19093, 'daylightmedicare.com'), 'test': (19094, 'test.daylightmedicare.com')}
ENVIRONMENT_LINES = ('Environment=DAYLIGHT_TOKEN_PREFLIGHT=local_bound',
                     'Environment=DAYLIGHT_REVEAL_WPS=20',
                     f'Environment=DAYLIGHT_PRICING_REVIEW={PRICING}')
# Must equal hosted_history.BLOCKS_SQL; the build step checks it.
BLOCKS_SQL = """
CREATE TABLE IF NOT EXISTS hosted_history.turn_blocks (
    visit text NOT NULL, request_id text NOT NULL, blocks jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (visit, request_id),
    FOREIGN KEY (visit, request_id) REFERENCES hosted_history.turns(visit, request_id) ON DELETE CASCADE
);
ALTER TABLE hosted_history.turn_blocks ENABLE ROW LEVEL SECURITY;
ALTER TABLE hosted_history.turn_blocks FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS block_isolation ON hosted_history.turn_blocks;
CREATE POLICY block_isolation ON hosted_history.turn_blocks
    USING (visit = current_setting('daylight.visit', true))
    WITH CHECK (visit = current_setting('daylight.visit', true));
REVOKE ALL ON hosted_history.turn_blocks FROM PUBLIC;
"""
BLOCKS_GRANT = 'GRANT SELECT, INSERT, UPDATE(blocks, updated_at) ON hosted_history.turn_blocks TO daylight_app'
CONTROLS_SQL = """
CREATE SCHEMA dl_control;
CREATE TABLE dl_control.source_access_state (
    source_id text PRIMARY KEY, state text NOT NULL CHECK (state IN ('permitted','stopped','held')),
    reason text NOT NULL, updated_at timestamptz NOT NULL DEFAULT clock_timestamp());
REVOKE ALL ON SCHEMA dl_control FROM PUBLIC;
GRANT USAGE ON SCHEMA dl_control TO daylight_app;
GRANT SELECT ON dl_control.source_access_state TO daylight_app;
"""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(manifest):
    return json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()


# ---------------------------------------------------------------- local build

def deployed_manifest(directory):
    """The exact files of the live release, from the reviewed baseline and D198 patch."""
    with zipfile.ZipFile(directory / 'hosted-baseline-63ab51328bf1.zip') as archive:
        raw = archive.read('release-manifest.json')
        if sha(raw) != BASELINE:
            raise ValueError('Baseline manifest differs from the deployed baseline')
        base = json.loads(raw)
        contents = {name: archive.read(name) for name in base['files_sha256']}
    patch = json.loads((directory / 'timing-card-patch.json').read_text())
    if patch['base_release'] != BASELINE:
        raise ValueError('Timing patch ancestry differs')
    live = copy.deepcopy(base); live['base_release'] = BASELINE
    for name, item in patch['files'].items():
        live['files_sha256'][name] = item['after']
    if sha(canonical(live)) != DEPLOYED:
        raise ValueError('Reconstructed manifest is not the live release')
    return live


def selected(root):
    sys.path.insert(0, str(root / 'infrastructure/daylight-pilot'))
    from package_display_rehearsal import selected_files
    files = selected_files(root / 'infrastructure/daylight-data/.state/pilot-subset/2026-11-12-r1')
    directory = root / 'infrastructure/daylight-pilot'
    for name in ('install_hosted_runtime.py', 'hosted_operations.py', 'install_hosted_proxy.py',
                 'hosted_egress_guard.py', 'deploy_hosted_d199.py'):
        files['deployment/' + name] = directory / name
    knowledge = root / 'docs/data/pilot-knowledge-2026-11-12-r2'
    for path in knowledge.rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts:
            files[path.relative_to(root).as_posix()] = path
    binding_path = root / 'infrastructure/daylight-data/.state/pilot-foundation-2026-r2-hosted/binding.json'
    binding = json.loads(binding_path.read_text())
    files['evidence/foundation-binding.json'] = binding_path
    return files, binding


def foundation_files(root, binding):
    """Source files the doctor/drug readers open at runtime, at their bound relative paths."""
    names = set(binding['controls'])
    names.add(binding['datasets']['federal_provider_rows']['artifact'])
    names.add('docs/data/l08-provider-networks-2026-10-27/build-r1/hospital-identity-aliases.json')
    for folder in ('docs/data/part-d-national-2026/candidate-r1',
                   'docs/data/l07-pharmacy-networks-2026-10-27/identity-acquisition-r1/raw'):
        names.update(p.relative_to(root).as_posix() for p in (root / folder).iterdir() if p.is_file())
    if any((root / name).is_symlink() for name in names):
        raise ValueError('Foundation files must be regular files')
    return sorted(names)


def file_sha(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def data_archive(root, binding, dump, output_dir):
    import tarfile
    names = foundation_files(root, binding)
    hashes = {name: file_sha(root / name) for name in names}
    hashes_dump = file_sha(dump)
    key = sha(canonical({'files': hashes, 'dump': hashes_dump}))[:12]
    archive = output_dir / f'd199-data-{key}.tar.gz'
    if not archive.exists():
        with open(archive, 'xb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', mtime=0, compresslevel=6) as stream, \
                tarfile.open(fileobj=stream, mode='w|', format=tarfile.PAX_FORMAT) as tar:
            members = [('foundation.dump.gz', dump)] + [('files/' + name, root / name) for name in names]
            for member, path in members:
                info = tarfile.TarInfo(member); info.size = path.stat().st_size; info.mode = 0o600
                with open(path, 'rb') as source:
                    tar.addfile(info, source)
    return archive, hashes, hashes_dump


def build(root, output_dir):
    directory = root / 'infrastructure/daylight-pilot'
    sys.path.insert(0, str(root / 'alternatives/advisor-first'))
    import server  # noqa: F401  (sets the pinned engine import path)
    from hosted_history import BLOCKS_SQL as SOURCE_BLOCKS, BLOCKS_GRANT_SQL
    if SOURCE_BLOCKS != BLOCKS_SQL or BLOCKS_GRANT_SQL.format('daylight_app') != BLOCKS_GRANT:
        raise ValueError('Deployment migration differs from hosted_history')
    live = deployed_manifest(directory)
    files, binding = selected(root)
    if any(path.is_symlink() for path in files.values()):
        raise ValueError('Release inputs must be regular files')
    contents = {name: path.read_bytes() for name, path in files.items()}
    manifest = {'scope': SCOPE, 'base_release': DEPLOYED,
                'files_sha256': {name: sha(data) for name, data in contents.items()}}
    raw = canonical(manifest); release = sha(raw)
    changed = {name: data for name, data in contents.items()
               if live['files_sha256'].get(name) != manifest['files_sha256'][name]}
    missing = sorted(set(live['files_sha256']) - set(manifest['files_sha256']))
    bundle = output_dir / f'hosted-d199-{release[:12]}.zip'
    if not bundle.exists():
        with zipfile.ZipFile(bundle, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted({'release-manifest.json': raw, **changed}.items()):
                entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED; entry.external_attr = 0o100600 << 16
                archive.writestr(entry, data)
    with zipfile.ZipFile(bundle) as archive:
        if archive.read('release-manifest.json') != raw or set(archive.namelist()) != {'release-manifest.json', *changed}:
            raise ValueError('Existing bundle differs; never overwrite')
    dump = root / 'infrastructure/daylight-data/.state/pilot-foundation-2026-r1/foundation.dump.gz'
    parity = json.loads((dump.parent / 'parity.json').read_text())
    data, data_hashes, dump_sha = data_archive(root, binding, dump, output_dir)
    plan = {'schema': 'daylight-d199-plan/v1', 'release': release, 'base_release': DEPLOYED,
            'bundle': bundle.name, 'bundle_sha256': sha(bundle.read_bytes()),
            'data_archive': data.name, 'data_archive_sha256': file_sha(data),
            'foundation_dump_sha256': dump_sha, 'foundation_files': data_hashes,
            'foundation_package_binding_id': binding['package_binding_id'],
            'foundation_binding_id': binding['binding_id'],
            'foundation_rows': {name: value['rows'] for name, value in parity['datasets'].items()},
            'changed_files': sorted(changed), 'files_not_carried_forward': missing,
            'tool_sha256': sha((directory / 'deploy_hosted_d199.py').read_bytes())}
    (output_dir / 'd199-plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    transfer = output_dir / 'd199-transfer.zip'
    if transfer.exists():
        transfer.unlink()  # derived convenience archive; every member is hash-bound by the plan
    with zipfile.ZipFile(transfer, 'x', compression=zipfile.ZIP_STORED) as archive:
        for path in (bundle, output_dir / 'd199-plan.json', directory / 'deploy_hosted_d199.py',
                     directory / 'cloudshell_d199.py'):
            archive.write(path, path.name)
    return {**{k: plan[k] for k in ('release', 'bundle', 'bundle_sha256', 'data_archive', 'data_archive_sha256')},
            'data_bytes': data.stat().st_size,
            'changed_files': len(changed), 'files': len(manifest['files_sha256']),
            'files_not_carried_forward': missing, 'transfer': str(transfer),
            'transfer_bytes': transfer.stat().st_size}


# ---------------------------------------------------------------- host apply

def run(*args, input=None, timeout=900):
    result = subprocess.run(args, input=input, capture_output=True, text=True, timeout=timeout,
                            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    if result.returncode:
        raise RuntimeError(f'Command failed: {Path(args[0]).name} {args[1] if len(args) > 1 else ""}'
                           f' :: {result.stderr.strip()[-400:]}')
    return result.stdout.strip()


def psql(query, database='postgres'):
    return run('runuser', '-u', 'postgres', '--', 'psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1',
               '-h', str(SOCKET), '-p', '55485', '-d', database, '-c', query)


def psql_script(script, database):
    return run('runuser', '-u', 'postgres', '--', 'psql', '-X', '-q', '-v', 'ON_ERROR_STOP=1',
               '-h', str(SOCKET), '-p', '55485', '-d', database, input=script)


def verify_tree(directory, release):
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('Immutable release directory required')
    raw = (directory / 'release-manifest.json').read_bytes()
    if sha(raw) != release:
        raise ValueError('Release manifest hash differs')
    value = json.loads(raw)
    for name, digest in value['files_sha256'].items():
        path = directory / name
        if (Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink()
                or not path.resolve().is_relative_to(directory.resolve()) or sha(path.read_bytes()) != digest):
            raise ValueError('Installed release file differs: ' + name)
    return value


def read_plan(folder, expected):
    raw = (folder / 'd199-plan.json').read_bytes()
    if sha(raw) != expected:
        raise ValueError('Plan hash differs')
    plan = json.loads(raw)
    if plan['schema'] != 'daylight-d199-plan/v1' or plan['base_release'] != DEPLOYED:
        raise ValueError('Unexpected plan')
    if sha((folder / plan['bundle']).read_bytes()) != plan['bundle_sha256']:
        raise ValueError('Bundle hash differs')
    if sha(Path(__file__).read_bytes()) != plan['tool_sha256']:
        raise ValueError('This tool differs from the planned tool')
    return plan


def stage(folder, plan):
    before = HOST_ROOT / 'releases' / DEPLOYED
    verify_tree(before, DEPLOYED)
    after = HOST_ROOT / 'releases' / plan['release']
    if after.exists():
        verify_tree(after, plan['release'])
        return after
    with zipfile.ZipFile(folder / plan['bundle']) as archive, \
            tempfile.TemporaryDirectory(prefix='.d199-', dir=HOST_ROOT / 'releases') as temporary:
        raw = archive.read('release-manifest.json')
        if sha(raw) != plan['release']:
            raise ValueError('Bundle manifest is not the planned release')
        manifest = json.loads(raw)
        temporary = Path(temporary)
        for name, digest in manifest['files_sha256'].items():
            target = temporary / name
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if name in archive.namelist():
                target.write_bytes(archive.read(name))
            else:
                source = before / name
                if source.is_symlink() or sha(source.read_bytes()) != digest:
                    raise ValueError('Unchanged file is not in the live release: ' + name)
                shutil.copyfile(source, target)
        (temporary / 'release-manifest.json').write_bytes(raw)
        verify_tree(temporary, plan['release'])
        group = pwd.getpwnam(APP).pw_gid
        for path in [temporary, *temporary.rglob('*')]:
            if path.is_symlink():
                raise ValueError('No release symlinks permitted')
            os.chown(path, 0, group); path.chmod(0o750 if path.is_dir() else 0o640)
        temporary.rename(after)
    return after


def migrate_history():
    for environment in ('pilot', 'test'):
        database = 'daylight_history_' + environment
        psql_script(BLOCKS_SQL + BLOCKS_GRANT + ';\n', database)
        if psql("SELECT count(*) FROM pg_tables WHERE schemaname='hosted_history' AND tablename='turn_blocks'",
                database) != '1':
            raise ValueError('Block table migration did not apply')


def install_foundation_files(folder, plan):
    """Extract the verified doctor/drug source files once to the state volume (read-only to the app)."""
    import tarfile
    base = STATE / 'foundation'
    base.mkdir(mode=0o750, exist_ok=True)
    os.chown(base, 0, pwd.getpwnam(APP).pw_gid)
    base.chmod(0o750)  # The root installer's 077 umask otherwise removes group traversal.
    root = base / plan['foundation_binding_id'][:12]
    def verify(directory):
        for name, digest in plan['foundation_files'].items():
            path = directory / name
            if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()) or file_sha(path) != digest:
                raise ValueError('Doctor/drug source file differs: ' + name)
    if root.exists():
        verify(root)
        return root, None
    archive = folder / plan['data_archive']
    if file_sha(archive) != plan['data_archive_sha256']:
        raise ValueError('Data archive hash differs')
    if shutil.disk_usage(STATE).free < 8 * 1024**3:
        raise ValueError('Not enough free state-volume space for the doctor/drug data')
    temporary = Path(tempfile.mkdtemp(prefix='.d199-data-', dir=base))
    dump = STATE / 'restore' / 'foundation.dump.gz'
    (STATE / 'restore').mkdir(mode=0o700, exist_ok=True)
    try:
        with tarfile.open(archive, 'r:gz') as tar:
            for member in tar:
                name = member.name
                if not member.isfile() or Path(name).is_absolute() or '..' in Path(name).parts:
                    raise ValueError('Unexpected data archive member')
                if name == 'foundation.dump.gz':
                    target = dump
                elif name.startswith('files/') and name[6:] in plan['foundation_files']:
                    target = temporary / name[6:]
                else:
                    raise ValueError('Unplanned data archive member: ' + name)
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
                with tar.extractfile(member) as source, open(target, 'xb') as out:
                    shutil.copyfileobj(source, out, 16 * 1024**2)
        if file_sha(dump) != plan['foundation_dump_sha256']:
            raise ValueError('Doctor/drug dump hash differs')
        verify(temporary)
        group = pwd.getpwnam(APP).pw_gid
        for path in [temporary, *temporary.rglob('*')]:
            os.chown(path, 0, group); path.chmod(0o750 if path.is_dir() else 0o640)
        temporary.rename(root)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        dump.unlink(missing_ok=True)
        raise
    return root, dump


def restore_foundation(folder, plan):
    root, dump = install_foundation_files(folder, plan)
    if psql(f"SELECT 1 FROM pg_database WHERE datname='{FOUNDATION_DB}'"):
        verify_foundation(plan)
        if dump is not None:
            dump.unlink(missing_ok=True)
    else:
        if dump is None:
            raise ValueError('The doctor/drug database is absent; rerun with a fresh data folder')
        restore = STATE / 'restore'
        postgres = pwd.getpwnam('postgres')
        os.chown(restore, postgres.pw_uid, postgres.pw_gid)
        raw = restore / 'foundation.dump'
        with gzip.open(dump) as source, raw.open('xb') as target:
            shutil.copyfileobj(source, target, 16 * 1024**2)
        dump.unlink()
        os.chown(raw, postgres.pw_uid, postgres.pw_gid)
        try:
            psql(f'CREATE DATABASE {FOUNDATION_DB}')
            run('runuser', '-u', 'postgres', '--', 'pg_restore', '--exit-on-error', '--single-transaction',
                '--no-owner', '--no-acl', '-h', str(SOCKET), '-p', '55485', '-d', FOUNDATION_DB, str(raw),
                timeout=3600)
        except Exception:
            psql(f'DROP DATABASE IF EXISTS {FOUNDATION_DB}')
            raise
        finally:
            raw.unlink(missing_ok=True)
        psql(f'REVOKE ALL ON DATABASE {FOUNDATION_DB} FROM PUBLIC; '
             f'GRANT CONNECT ON DATABASE {FOUNDATION_DB} TO daylight_app')
        psql('GRANT USAGE ON SCHEMA dl_pilot_foundation TO daylight_app; '
             'GRANT SELECT ON ALL TABLES IN SCHEMA dl_pilot_foundation TO daylight_app', FOUNDATION_DB)
        psql(f'ALTER DATABASE {FOUNDATION_DB} SET default_transaction_read_only=on')
        verify_foundation(plan)
    if not psql(f"SELECT 1 FROM pg_database WHERE datname='{CONTROLS_DB}'"):
        psql(f'CREATE DATABASE {CONTROLS_DB}')
        psql(f'REVOKE ALL ON DATABASE {CONTROLS_DB} FROM PUBLIC; '
             f'GRANT CONNECT ON DATABASE {CONTROLS_DB} TO daylight_app')
        psql_script(CONTROLS_SQL, CONTROLS_DB)
    states = psql("SELECT count(*) FROM dl_control.source_access_state WHERE state<>'permitted'", CONTROLS_DB)
    return root, {'foundation_verified': True, 'foundation_root': str(root), 'non_permitted_sources': int(states)}


def verify_foundation(plan):
    stamp = psql('SELECT binding_id FROM dl_pilot_foundation.binding', FOUNDATION_DB)
    if stamp != plan['foundation_package_binding_id']:
        raise ValueError('Doctor/drug database stamp differs')
    for name, rows in plan['foundation_rows'].items():
        count = psql(f'SELECT count(*) FROM dl_pilot_foundation."{name}"', FOUNDATION_DB)
        if int(count) != rows:
            raise ValueError(f'Doctor/drug dataset row count differs: {name}')


def install_pricing(after):
    source = after / 'alternatives/advisor-first/pricing-review.json'
    value = json.loads(source.read_text())
    if PRICING.exists():
        current = json.loads(PRICING.read_text())
        if current['valid_until'] >= value['valid_until']:
            return current
    write_private(PRICING, json.dumps(value, indent=2) + '\n', 0o640, pwd.getpwnam(APP).pw_gid)
    return value


def write_private(path, value, mode, group):
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            os.fchmod(stream.fileno(), mode); os.fchown(stream.fileno(), 0, group)
            stream.write(value); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def unit_text(old, release_dir, *, checks=False):
    """Point one service at the new release with the :8895 runtime settings."""
    lines = old.splitlines()
    starts = [line for line in lines if line.startswith('ExecStart=')]
    if len(starts) != 1 or '/hosted_server.py --config ' not in starts[0] \
            or lines.count('Environment=DAYLIGHT_MODEL_ENVIRONMENT=hosted-demo') != 1:
        raise ValueError('Unexpected service unit')
    current = next(line for line in lines if line.startswith('WorkingDirectory=')).split('=', 1)[1]
    if not current.startswith(str(HOST_ROOT / 'releases') + '/'):
        raise ValueError('Unexpected working directory')
    out = []
    for line in lines:
        if line.startswith(('Environment=DAYLIGHT_TOKEN_PREFLIGHT=', 'Environment=DAYLIGHT_REVEAL_WPS=',
                            'Environment=DAYLIGHT_PRICING_REVIEW=', 'MemoryMax=')):
            continue
        if line.startswith('Environment=DAYLIGHT_BLOCK_RELEASE='):
            line = 'Environment=DAYLIGHT_BLOCK_RELEASE=on'
        out.append(line.replace(current, str(release_dir)))
        if line == 'Environment=DAYLIGHT_MODEL_ENVIRONMENT=hosted-demo':
            out.extend(ENVIRONMENT_LINES)
            out.append('MemoryMax=2G' if checks else 'MemoryMax=900M')
    if 'Environment=DAYLIGHT_BLOCK_RELEASE=on' not in out:
        out.insert(out.index('Environment=DAYLIGHT_MODEL_ENVIRONMENT=hosted-demo') + 1,
                   'Environment=DAYLIGHT_BLOCK_RELEASE=on')
    return '\n'.join(out) + '\n', Path(current)


def config_text(raw, release_dir, checks, foundation_root=None):
    value = json.loads(raw)
    value['release'] = release_dir.name
    value['binding'] = str(release_dir / 'evidence/binding.json')
    for key in ('foundation_binding', 'foundation_root', 'foundation_dsn', 'controls_dsn'):
        value.pop(key, None)
    if checks:
        if foundation_root is None:
            raise ValueError('Doctor/drug checks need their verified data folder')
        value['foundation_binding'] = str(release_dir / 'evidence/foundation-binding.json')
        value['foundation_root'] = str(foundation_root)
        value['foundation_dsn'] = f'host={SOCKET} port=55485 dbname={FOUNDATION_DB} user=daylight_app'
        value['controls_dsn'] = f'host={SOCKET} port=55485 dbname={CONTROLS_DB} user=daylight_app'
    return json.dumps(value, indent=2) + '\n'


def drained(environments):
    with sqlite3.connect((STATE / 'budget/model-usage.sqlite3').as_uri() + '?mode=ro', uri=True, timeout=3) as db:
        if db.execute("SELECT count(*) FROM ai_charges WHERE status='reserved'").fetchone()[0]:
            return False
    return all(psql("SELECT count(*) FROM hosted_history.turns WHERE status='accepted'",
                    'daylight_history_' + name) == '0' for name in environments)


def chat_flags(environments, values=None):
    previous = {}
    for name in environments:
        path = (STATE / 'cohorts' / name / 'access.sqlite3').as_uri()
        with sqlite3.connect(path + ('?mode=ro' if values is None else '?mode=rw'), uri=True, timeout=3) as db:
            previous[name] = dict(db.execute("SELECT name,enabled FROM flags WHERE name IN ('all_chat','guest_chat')"))
            if values is not None:
                for flag, enabled in values[name].items():
                    db.execute('UPDATE flags SET enabled=? WHERE name=?', (enabled, flag))
    return previous


def ready(environment, release, seconds=300):
    port, host = PORTS[environment]
    deadline = time.monotonic() + seconds
    while True:
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
        try:
            connection.request('GET', '/pilot/join', headers={'Host': host, 'Connection': 'close'})
            response = connection.getresponse()
            if response.status == 200 and response.getheader('X-Daylight-Release') == release:
                response.read(65536)
                return
        except (OSError, http.client.HTTPException):
            pass
        finally:
            connection.close()
        if time.monotonic() >= deadline:
            raise RuntimeError(f'{environment} failed readiness on {release[:12]}')
        time.sleep(1)


def memory_available():
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemAvailable:'):
            return int(line.split()[1]) * 1024
    return 0


def switch(changes, environments, releases):
    """Drain, rewrite, restart and verify; restore everything on any failure."""
    services = ['daylight-' + name + '.service' for name in environments]
    old_flags = chat_flags(environments)
    for attempt in (0, 1):
        deadline = time.monotonic() + 60
        while not drained(environments):
            if time.monotonic() >= deadline:
                if attempt:
                    chat_flags(environments, old_flags)
                raise ValueError('An unfinished turn prevents a safe restart; nothing changed')
            time.sleep(0.5)
        if not attempt:
            chat_flags(environments, {name: {'all_chat': 0, 'guest_chat': 0} for name in environments})
    stopped = False
    try:
        run('systemctl', 'stop', *services); stopped = True
        for path, (old, new) in changes.items():
            if path.read_text() != old:
                raise ValueError('Configuration changed during preparation')
            stat = path.stat()
            write_private(path, new, stat.st_mode & 0o777, stat.st_gid)
        run('systemd-analyze', 'verify', *(str(UNITS / name) for name in services))
        run('systemctl', 'daemon-reload'); run('systemctl', 'start', *services)
        for name in environments:
            ready(name, releases[name])
    except Exception:
        if stopped:
            run('systemctl', 'stop', *services)
            for path, (old, _) in changes.items():
                stat = path.stat(); write_private(path, old, stat.st_mode & 0o777, stat.st_gid)
            run('systemctl', 'daemon-reload'); run('systemctl', 'start', *services)
        chat_flags(environments, old_flags)
        raise
    chat_flags(environments, old_flags)


def apply(folder, plan_sha, environment):
    plan = read_plan(folder, plan_sha)
    if environment == 'test' and 'foundation_binding' in json.loads((CONFIG / 'pilot.json').read_text()):
        raise ValueError('Doctor/drug checks are active on pilot; refuse a second large index on this host')
    after = stage(folder, plan)
    migrate_history()
    foundation_root, data = restore_foundation(folder, plan)
    pricing = install_pricing(after)
    changes, releases, previous = {}, {}, {}
    # Doctor/drug checks live on the environment being switched; pilot promotion removes them from test.
    affected = ['test'] if environment == 'test' else ['pilot', 'test']
    for name in affected:
        unit, config = UNITS / f'daylight-{name}.service', CONFIG / f'{name}.json'
        old_unit, old_config = unit.read_text(), config.read_text()
        target = after if (name == environment or json.loads(old_config)['release'] == after.name) else None
        if target is None:
            target = Path(json.loads(old_config)['binding']).parents[1]
        new_unit, current = unit_text(old_unit, target, checks=name == environment)
        changes[unit] = (old_unit, new_unit)
        changes[config] = (old_config, config_text(old_config, target, checks=name == environment,
                                                   foundation_root=foundation_root))
        releases[name] = target.name; previous[name] = current.name
        if name != environment and target != after:
            # Leave the other environment's code and settings exactly as they were.
            del changes[unit]; del changes[config]
    if memory_available() < 1800 * 1024**2 and not any(
            'foundation_binding' in json.loads(old) for path, (old, _) in changes.items() if path.suffix == '.json'):
        raise ValueError('Too little free memory for the doctor/drug index; nothing changed')
    backup = STATE / 'operations' / f'd199-{environment}-{int(time.time())}'
    backup.mkdir(mode=0o700, parents=True)
    for path, (old, _) in changes.items():
        (backup / path.name).write_text(old)
    switch(changes, [name for name in affected if UNITS / f'daylight-{name}.service' in changes], releases)
    if environment == 'pilot':
        link = HOST_ROOT / 'current.d199'
        link.unlink(missing_ok=True); link.symlink_to(after); os.replace(link, HOST_ROOT / 'current')
    report = {'environment': environment, 'release': after.name, 'previous': previous,
              'backup': str(backup), 'pricing_valid_until': pricing['valid_until'], **data,
              'checks_environment': environment, 'provider_calls': 0, 'invitations_changed': False}
    (STATE / 'operations' / f'd199-{environment}-{after.name[:12]}.json').write_text(json.dumps(report))
    return report


def rollback(environment):
    backups = sorted((STATE / 'operations').glob(f'd199-{environment}-*/'))
    if not backups:
        raise ValueError('No D199 backup for this environment')
    backup = backups[-1]
    changes = {}
    for saved in backup.iterdir():
        live = (UNITS if saved.suffix == '.service' else CONFIG) / saved.name
        changes[live] = (live.read_text(), saved.read_text())
    environments = sorted({p.stem.removeprefix('daylight-') for p in changes})
    releases = {name: json.loads(changes[CONFIG / f'{name}.json'][1])['release'] for name in environments}
    switch(changes, environments, releases)
    if environment == 'pilot':
        link = HOST_ROOT / 'current.d199'
        link.unlink(missing_ok=True); link.symlink_to(HOST_ROOT / 'releases' / releases['pilot'])
        os.replace(link, HOST_ROOT / 'current')
    return {'rolled_back': environment, 'restored_from': str(backup), 'releases': releases}


def renew_pricing(verified_at, valid_until):
    checked = dt.datetime.strptime(verified_at, '%Y-%m-%dT%H:%M:%SZ')
    until = dt.datetime.strptime(valid_until, '%Y-%m-%dT%H:%M:%SZ')
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    if not checked <= now < until or until - checked > dt.timedelta(days=7):
        raise ValueError('A price review lasts at most 7 days from its verification')
    environments = ['pilot', 'test']
    old = PRICING.read_text() if PRICING.exists() else None
    write_private(PRICING, json.dumps({'verified_at': verified_at, 'valid_until': valid_until}, indent=2) + '\n',
                  0o640, pwd.getpwnam(APP).pw_gid)
    releases = {name: json.loads((CONFIG / f'{name}.json').read_text())['release'] for name in environments}
    unit_paths = {UNITS / f'daylight-{name}.service' for name in environments}
    try:
        switch({path: (path.read_text(), path.read_text()) for path in unit_paths}, environments, releases)
    except Exception:
        if old is not None:
            write_private(PRICING, old, 0o640, pwd.getpwnam(APP).pw_gid)
        raise
    return {'pricing_review': {'verified_at': verified_at, 'valid_until': valid_until}, 'restarted': environments}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('build'); p.add_argument('--output', type=Path, required=True)
    p = commands.add_parser('apply'); p.add_argument('folder', type=Path); p.add_argument('plan_sha256')
    p.add_argument('--environment', choices=('test', 'pilot'), required=True)
    p = commands.add_parser('rollback'); p.add_argument('--environment', choices=('test', 'pilot'), required=True)
    p = commands.add_parser('renew-pricing'); p.add_argument('verified_at'); p.add_argument('valid_until')
    args = parser.parse_args()
    if args.command == 'build':
        report = build(Path(__file__).resolve().parents[2], args.output)
    else:
        if os.geteuid() != 0:
            raise ValueError('Root-only deployment')
        (STATE / 'operations').mkdir(mode=0o700, exist_ok=True)
        with (STATE / 'operations/d199.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if args.command == 'apply':
                report = apply(args.folder, args.plan_sha256, args.environment)
            elif args.command == 'rollback':
                report = rollback(args.environment)
            else:
                report = renew_pricing(args.verified_at, args.valid_until)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
