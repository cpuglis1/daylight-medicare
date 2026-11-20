#!/usr/bin/env python3
"""Restore the held display snapshot into a new, socket-only private database."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess

VOLUME_SERIAL = 'vol04a5e06e77ec054ac'
STATE = Path('/var/lib/daylight-state')
RELEASE = Path('/opt/daylight-pilot/releases/aaa19850dd02ccd61b25f633e170bc8f01d0321cbe26e5b1715874e2cfe3ec42')
DB = 'daylight_pilot_collier_2026_r1'
DATA = STATE / 'postgresql'
SOCKET = STATE / 'pgsocket'


def run(*args, input=None, ok=(0,)):
    r = subprocess.run(args, input=input, capture_output=True)
    if r.returncode not in ok:
        raise RuntimeError('Command failed: ' + ' '.join(args[:2]))
    return r.stdout


def postgres(*args, **kwargs):
    return run('runuser', '-u', 'postgres', '--', *args, **kwargs)


def sql(query, database='postgres'):
    return postgres('psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-h', str(SOCKET),
                    '-p', '55485', '-d', database, '-c', query).decode().strip()


def main():
    os.umask(0o077)
    assert os.geteuid() == 0
    uid, gid = pwd.getpwnam('postgres').pw_uid, pwd.getpwnam('postgres').pw_gid
    devices = json.loads(run('lsblk', '-Jb', '-o', 'PATH,SERIAL,SIZE,FSTYPE,MOUNTPOINTS'))['blockdevices']
    selected = [d for d in devices if d.get('serial') == VOLUME_SERIAL]
    if len(selected) != 1:
        raise ValueError('Expected the exact state volume.')
    device = selected[0]
    if int(device['size']) != 30 * 1024**3 or device.get('children'):
        raise ValueError('Unexpected volume layout.')
    if not device['fstype']:
        signatures = json.loads(run('wipefs', '--no-act', '--json', device['path']))['signatures']
        if signatures or any(device.get('mountpoints') or []):
            raise ValueError('Never format a volume with signatures or mounts.')
        run('mkfs.xfs', '-L', 'daylight', device['path'])
    elif device['fstype'] != 'xfs' or run('blkid', '-s', 'LABEL', '-o', 'value', device['path']).strip() != b'daylight':
        raise ValueError('Existing volume is not this deployment state disk.')
    STATE.mkdir(mode=0o711, exist_ok=True)
    if STATE.is_symlink():
        raise ValueError('Refusing symlink mountpoint.')
    uuid = run('blkid', '-s', 'UUID', '-o', 'value', device['path']).decode().strip()
    entry = f'UUID={uuid} {STATE} xfs defaults,nodev,nosuid,noexec 0 2'
    fstab = Path('/etc/fstab')
    entries = [line for line in fstab.read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')]
    matches = [line for line in entries if len(line.split()) > 1 and line.split()[1] == str(STATE)]
    if matches and matches != [entry]:
        raise ValueError('Mount configuration changed.')
    if not matches:
        with fstab.open('a') as out:
            out.write('\n' + entry + '\n')
    if subprocess.run(['mountpoint', '-q', str(STATE)]).returncode:
        if list(STATE.iterdir()):
            raise ValueError('Never mount over existing files.')
        run('mount', str(STATE))
    assert run('findmnt', '-n', '-o', 'UUID', '--target', str(STATE)).decode().strip() == uuid
    STATE.chmod(0o711)
    for p in (DATA, SOCKET):
        p.mkdir(exist_ok=True, mode=0o700)
        os.chown(p, uid, gid)
        p.chmod(0o700)
    if not (DATA / 'PG_VERSION').exists():
        if list(DATA.iterdir()):
            raise ValueError('Never initialize over existing database files.')
        postgres('initdb', '-D', str(DATA), '--encoding=UTF8', '--locale=C.UTF-8',
                 '--auth-local=peer', '--auth-host=reject')
        with (DATA / 'postgresql.conf').open('a') as f:
            f.write("\nlisten_addresses = ''\nmax_connections = 20\nshared_buffers = '64MB'\nlogging_collector = off\nlog_statement = 'none'\nlog_min_error_statement = 'panic'\n")
    elif (DATA / 'PG_VERSION').read_text().strip() != '18':
        raise ValueError('Unexpected database major version.')
    binary = shutil.which('postgres')
    if not binary:
        raise ValueError('Missing PostgreSQL executable.')
    unit = f'''[Unit]
Description=Daylight private display database
RequiresMountsFor={STATE}
After=local-fs.target
[Service]
User=postgres
Group=postgres
ExecStart={binary} -D {DATA} -h "" -k {SOCKET} -p 55485
Restart=on-failure
UMask=0077
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
ReadWritePaths={DATA} {SOCKET}
MemoryMax=768M
LimitNOFILE=4096
StandardOutput=null
StandardError=journal
[Install]
WantedBy=multi-user.target
'''
    path = Path('/etc/systemd/system/daylight-postgres.service')
    if path.exists() and path.read_text() != unit:
        raise ValueError('Existing service differs; review before changing.')
    path.write_text(unit)
    run('systemctl', 'daemon-reload')
    run('systemctl', 'enable', '--now', 'daylight-postgres.service')
    # pg_isready is a bounded, local readiness check, with no model/provider I/O.
    import time
    for attempt in range(30):
        if subprocess.run(['runuser', '-u', 'postgres', '--', 'pg_isready', '-q', '-h', str(SOCKET), '-p', '55485']).returncode == 0:
            break
        time.sleep(1)
    else:
        raise RuntimeError('Private database did not become ready.')
    if sql(f"SELECT 1 FROM pg_database WHERE datname='{DB}'"):
        raise ValueError('Database already exists; never overwrite or restore over it.')
    for role in ('daylight_csg_reader', 'daylight_csg_loader', 'daylight_plan_research_reader'):
        if not sql(f"SELECT 1 FROM pg_roles WHERE rolname='{role}'"):
            sql(f'CREATE ROLE {role} NOLOGIN')
    sql(f'CREATE DATABASE {DB}')
    restore = STATE / 'restore'
    restore.mkdir(exist_ok=True, mode=0o700)
    os.chown(restore, uid, gid)
    dump = restore / 'pilot.dump'
    expected = json.loads((RELEASE / 'evidence/compressed-backup.json').read_text())
    raw = gzip.decompress((RELEASE / 'evidence/pilot.dump.gz').read_bytes())
    if hashlib.sha256(raw).hexdigest() != expected['decoded_sha256']:
        raise ValueError('Decoded backup hash differs.')
    with dump.open('xb') as out:
        out.write(raw)
    os.chown(dump, uid, gid)
    postgres('pg_restore', '--exit-on-error', '--single-transaction', '--no-owner',
             '-h', str(SOCKET), '-p', '55485', '-d', DB, str(dump))
    sql(f'ALTER DATABASE {DB} SET default_transaction_read_only=on')
    receipt = {'database': DB, 'snapshot_id': sql('SELECT snapshot_id FROM dl_pilot.snapshot', DB),
               'csg_rates': int(sql('SELECT count(*) FROM dl_csg_medigap.rate', DB)),
               'pdp_responses': int(sql('SELECT count(*) FROM dl_pilot.pdp_response', DB)),
               'listen_addresses': sql('SHOW listen_addresses', DB), 'volume_uuid': uuid,
               'read_only': sql('SHOW default_transaction_read_only', DB),
               'source_reconciliation': 'pending local source check', 'app_active': False}
    (STATE / 'restore-receipt.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
