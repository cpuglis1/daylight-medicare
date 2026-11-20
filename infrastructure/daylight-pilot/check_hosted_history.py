#!/usr/bin/env python3
"""Run only fictional PostgreSQL tests on the existing private host.

No display database modification, API credential, ingress, or paid probe.
The isolated database is retained for inspection; no participant data is used.
"""
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys
import zipfile

DATABASE='daylight_history_check_20261119'
SOCKET='/var/lib/daylight-state/pgsocket'
PYTHON='/opt/daylight-runtime/venv-3.14.7/bin/python'

def run(*args):
    return subprocess.run(args,check=True,text=True,capture_output=True).stdout

def main():
    archive=Path(sys.argv[1]);expected=sys.argv[2]
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected
    target=Path('/var/lib/daylight-state/history-check')/expected
    assert not target.exists(), 'Use a fresh, inspected test bundle.'
    target.mkdir(mode=0o700,parents=True)
    owner=pwd.getpwnam('postgres')
    with zipfile.ZipFile(archive) as z:
        manifest=json.loads(z.read('manifest.json'))
        assert set(z.namelist())==set(manifest)|{'manifest.json'}
        for name,digest in manifest.items():
            assert '/' not in name and name.endswith('.py')
            data=z.read(name);assert hashlib.sha256(data).hexdigest()==digest
            path=target/name;path.write_bytes(data);path.chmod(0o600);os.chown(path,owner.pw_uid,owner.pw_gid)
    os.chown(target,owner.pw_uid,owner.pw_gid)
    target.parent.chmod(0o711)
    # The installed app runtime is root-only. Copy only public package files
    # into this isolated test directory; don't relax app/release permissions.
    deps=target/'dependencies';deps.mkdir(mode=0o700)
    library=Path('/opt/daylight-runtime/venv-3.14.7/lib/python3.14/site-packages')
    for name in ('psycopg','psycopg_binary'):
        if (library/name).exists():shutil.copytree(library/name,deps/name)
    for path in [deps,*deps.rglob('*')]:
        os.chown(path,owner.pw_uid,owner.pw_gid)
        path.chmod(0o700 if path.is_dir() else 0o600)
    psql=['runuser','-u','postgres','--','psql','-X','-qAt','-h',SOCKET,'-p','55485','-d','postgres','-v','ON_ERROR_STOP=1']
    exists=run(*psql,'-c',f"SELECT count(*) FROM pg_database WHERE datname='{DATABASE}'").strip()
    if exists=='0':run(*psql,'-c',f'CREATE DATABASE {DATABASE}')
    dsn=f'host={SOCKET} port=55485 dbname={DATABASE} user=postgres'
    command=['runuser','-u','postgres','--','env',f'DAYLIGHT_HISTORY_TEST_DSN={dsn}',
        f'PYTHONPATH={target}:{deps}','/usr/bin/python3.14','-m','unittest','test_hosted_history_postgres','-v']
    result=subprocess.run(command,capture_output=True,text=True)
    receipt={'bundle_sha256':expected,'database':DATABASE,'exit_code':result.returncode,
             'stdout':result.stdout,'stderr':result.stderr,'paid_model_calls':0,'public_access':False}
    Path('/var/lib/daylight-state/history-check-result.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt))
    raise SystemExit(result.returncode)

if __name__=='__main__':main()
