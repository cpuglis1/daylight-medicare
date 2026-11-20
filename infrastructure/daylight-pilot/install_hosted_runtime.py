#!/usr/bin/env python3
"""Stage a content-addressed release; apply private runtime only after scoped approval.

Never changes SG, CloudFront, DNS, prices, API credentials or source rows.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import shutil
import subprocess
import tempfile
import zipfile

ROOT=Path('/opt/daylight-pilot')
STATE=Path('/var/lib/daylight-state')
SOCKET=STATE/'pgsocket'
PYTHON='/opt/daylight-runtime/venv-3.14.7/bin/python'
APP='daylight-app'
DISPLAY='daylight_pilot_collier_2026_r1'

def run(*args,input=None):
    r=subprocess.run(args,input=input,capture_output=True,text=True,
                     env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    if r.returncode:
        fd,path=tempfile.mkstemp(prefix='hosted-install-error-',suffix='.txt',dir=STATE)
        with os.fdopen(fd,'w') as log:log.write(r.stderr)
        raise RuntimeError('Private installation command failed: '+args[0]+' (private details: '+path+')')
    return r.stdout.strip()

def sql(query,database='postgres'):
    return run('runuser','-u','postgres','--','psql','-X','-qAt','-v','ON_ERROR_STOP=1',
               '-h',str(SOCKET),'-p','55485','-d',database,'-c',query)

def valid_path(name):
    if not isinstance(name,str) or '\\' in name or '\x00' in name:return False
    path=PurePosixPath(name)
    return bool(name) and name!='.' and not path.is_absolute() and '..' not in path.parts and str(path)==name

def digest_value(value):
    return isinstance(value,str) and len(value)==64 and all(c in '0123456789abcdef' for c in value)

def verified_manifest(raw):
    manifest=json.loads(raw)
    if (set(manifest)!={'scope','base_release','files_sha256'} or
            manifest['scope']!='fictional_invited_hosted_demo' or not digest_value(manifest['base_release']) or
            not isinstance(manifest['files_sha256'],dict) or not 1<=len(manifest['files_sha256'])<=2000):
        raise ValueError('Invalid hosted release manifest')
    for name,digest in manifest['files_sha256'].items():
        if not valid_path(name) or name=='release-manifest.json' or not digest_value(digest):
            raise ValueError('Invalid hosted release file')
    required={'deployment/install_hosted_runtime.py','deployment/hosted_operations.py',
              'deployment/hosted_egress_guard.py',
              'alternatives/advisor-first/hosted_server.py','evidence/binding.json'}
    if not required<=manifest['files_sha256'].keys():raise ValueError('Incomplete hosted release')
    return manifest

def stage(archive,expected):
    if not digest_value(expected) or hashlib.sha256(archive.read_bytes()).hexdigest()!=expected:
        raise ValueError('Archive hash mismatch')
    with zipfile.ZipFile(archive) as z:
        if (len(z.namelist())!=len(set(z.namelist())) or len(z.namelist())>2001 or
                sum(info.file_size for info in z.infolist())>128*1024*1024):
            raise ValueError('Invalid release archive inventory')
        raw=z.read('release-manifest.json');manifest=verified_manifest(raw)
        release=hashlib.sha256(raw).hexdigest()
        base=ROOT/'releases'/manifest['base_release']
        if base.is_symlink() or not base.is_dir():raise ValueError('Verified base release is absent')
        target=ROOT/'releases'/release
        allowed=set(manifest['files_sha256'])|{'release-manifest.json'}
        if not set(z.namelist())<=allowed:raise ValueError('Unexpected archive entry')
        data_files={}
        for name,digest in manifest['files_sha256'].items():
            source=base/name
            if source.is_symlink() or not source.resolve().is_relative_to(base.resolve()):
                raise ValueError('Base release path escapes its directory')
            data=z.read(name) if name in z.namelist() else source.read_bytes()
            if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('Release hash mismatch: '+name)
            data_files[name]=data
        if target.exists() or target.is_symlink():
            if target.is_symlink() or (target/'release-manifest.json').read_bytes()!=raw:
                raise ValueError('Existing staged release does not match')
            for name,digest in manifest['files_sha256'].items():
                path=target/name
                if path.is_symlink() or not path.resolve().is_relative_to(target.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                    raise ValueError('Existing staged file does not match')
            return release
        with tempfile.TemporaryDirectory(prefix='.stage-',dir=ROOT/'releases') as temporary:
            temporary=Path(temporary)
            for name,data in data_files.items():
                dest=temporary/name;dest.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                dest.write_bytes(data);dest.chmod(0o600)
            (temporary/'release-manifest.json').write_bytes(raw)
            (temporary/'release-manifest.json').chmod(0o600)
            temporary.rename(target)
        return release

def write(path,value,mode=0o600):
    path=Path(path);path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    if path.exists() and path.read_text()!=value:
        backup=path.with_name(path.name+'.before-hosted')
        if backup.exists():raise ValueError('Existing configuration changed: '+str(path))
        shutil.copy2(path,backup)
    path.write_text(value);path.chmod(mode)

def apply(release):
    if not digest_value(release):raise ValueError('Use an exact release digest')
    target=ROOT/'releases'/release
    raw=(target/'release-manifest.json').read_bytes();assert hashlib.sha256(raw).hexdigest()==release
    manifest=verified_manifest(raw)
    for name,digest in manifest['files_sha256'].items():
        assert hashlib.sha256((target/name).read_bytes()).hexdigest()==digest
    # This operation is intentionally first-install only. Upgrades need a drained
    # service and a separate atomic pointer switch, never state reinitialization.
    current=ROOT/'current'
    assert not current.exists() and not current.is_symlink(),'Use the upgrade/rollback procedure'
    for name in ('pilot','test'):
        assert not sql("SELECT 1 FROM pg_database WHERE datname='daylight_history_"+name+"'"),'History DB exists; never overwrite'
        assert not (STATE/'cohorts'/name).exists(),'Existing cohort must not be reinitialized'
    assert not (STATE/'budget').exists(),'Existing ledger must not be reinitialized'
    assert not (STATE/'egress/allowance.json').exists(),'Existing egress allowance must not be reset'
    assert shutil.which('aws'),'The installed AWS CLI is required for private operations'
    assert Path('/usr/sbin/nft').is_file(),'The installed kernel egress guard is required'
    # Resolve import/schema failures before making a user, DB or persistent ledger.
    appdir=target/'alternatives/advisor-first'
    schema_code="import sys;sys.path.insert(0,"+repr(str(appdir))+");import server;from hosted_history import SCHEMA_SQL;print(SCHEMA_SQL)"
    schema=run(PYTHON,'-c',schema_code)
    try:pwd.getpwnam(APP)
    except KeyError:run('useradd','--system','--home-dir','/nonexistent','--shell','/sbin/nologin',APP)
    user=pwd.getpwnam(APP)
    ROOT.chmod(0o711);(ROOT/'releases').chmod(0o711)
    for path in [target,*target.rglob('*')]:
        assert not path.is_symlink()
        os.chown(path,0,user.pw_gid);path.chmod(0o750 if path.is_dir() else 0o640)
    # Only the already-installed public Python runtime is made executable/readable.
    # No release, credential or private state directory is made public.
    runtime=Path('/opt/daylight-runtime')
    for path in [runtime,*runtime.rglob('*')]:
        if path.is_symlink():continue
        path.chmod((path.stat().st_mode&0o777)|0o555 if path.is_dir() else (path.stat().st_mode&0o777)|0o444)
    os.chown(SOCKET,pwd.getpwnam('postgres').pw_uid,user.pw_gid);SOCKET.chmod(0o710)
    # Keep PostgreSQL on its existing private socket. Only the application UID
    # receives traversal; peer authentication still decides database access.
    if not sql("SELECT 1 FROM pg_roles WHERE rolname='daylight_app'"):
        sql('CREATE ROLE daylight_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS')
    if sql("SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls FROM pg_roles WHERE rolname='daylight_app'")!='f':
        raise ValueError('Existing application role has unexpected privileges')
    sql('GRANT daylight_csg_reader,daylight_plan_research_reader TO daylight_app')
    # Existing local peer rule requires a reviewed OS-name mapping for the hyphen.
    ident=STATE/'postgresql/pg_ident.conf'
    mapping='daylight_app daylight-app daylight_app\n'
    if mapping not in ident.read_text():
        with ident.open('a') as f:f.write('\n'+mapping)
    hba=STATE/'postgresql/pg_hba.conf'
    rule='local all daylight_app peer map=daylight_app\n'
    if rule not in hba.read_text():write(hba,rule+hba.read_text())
    sql('SELECT pg_reload_conf()')
    cohort=STATE/'cohorts';cohort.mkdir(mode=0o700);os.chown(cohort,user.pw_uid,user.pw_gid)
    ledger_dir=STATE/'budget';ledger_dir.mkdir(mode=0o700);os.chown(ledger_dir,user.pw_uid,user.pw_gid)
    ledger=ledger_dir/'model-usage.sqlite3'
    configdir=Path('/etc/daylight-pilot/runtime');configdir.mkdir(parents=True,mode=0o750)
    configdir.parent.chmod(0o711)  # TLS remains in its separate root-only directory.
    configdir.chmod(0o750)  # mkdir is affected by the installer's private umask.
    os.chown(configdir,0,user.pw_gid)
    # Root installs the already-validated schema through postgres peer auth.
    import time
    ends=int(time.time())+30*86400
    for name,port,origin in [('pilot',19093,'https://daylightmedicare.com'),('test',19094,'https://test.daylightmedicare.com')]:
        database='daylight_history_'+name
        assert not sql("SELECT 1 FROM pg_database WHERE datname='"+database+"'"),'History DB exists; never overwrite'
        sql('CREATE DATABASE '+database)
        sql('REVOKE ALL ON DATABASE '+database+' FROM PUBLIC; GRANT CONNECT ON DATABASE '+database+' TO daylight_app')
        run('runuser','-u','postgres','--','psql','-X','-q','-v','ON_ERROR_STOP=1',
            '-h',str(SOCKET),'-p','55485','-d',database,input=schema)
        sql('''GRANT USAGE ON SCHEMA hosted_history TO daylight_app;
            GRANT SELECT,INSERT ON hosted_history.visits,hosted_history.turns TO daylight_app;
            GRANT UPDATE(last_activity,expires_at) ON hosted_history.visits TO daylight_app;
            GRANT UPDATE(finished_at,status,response,usage,error_code) ON hosted_history.turns TO daylight_app;
            GRANT EXECUTE ON FUNCTION hosted_history.delete_visit(text) TO daylight_app''',database)
        run('runuser','-u',APP,'--',PYTHON,str(appdir/'pilot_admin.py'),str(cohort/name),
            '--ledger',str(ledger),'initialize',str(ends))
        config={'port':port,'state':str(cohort/name),'origin':origin,'ledger':str(ledger),
            'environment':name,
            'history_dsn':f'host={SOCKET} port=55485 dbname={database} user=daylight_app',
            'display_dsn':f'host={SOCKET} port=55485 dbname={DISPLAY} user=daylight_app',
            'binding':str(target/'evidence/binding.json'),'release':release,
            'key_file':f'/run/credentials/daylight-{name}.service/openai'}
        p=configdir/(name+'.json');write(p,json.dumps(config,indent=2)+'\n',0o640);os.chown(p,0,user.pw_gid)
        unit=f'''[Unit]
Description=Daylight {name} private hosted application (AI paused)
After=daylight-postgres.service daylight-delete.service
Requires=daylight-postgres.service daylight-delete.service
RequiresMountsFor={STATE}
[Service]
User={APP}
Group={APP}
WorkingDirectory={target}
Environment=DAYLIGHT_MODEL_ENVIRONMENT=hosted-demo
Environment=DAYLIGHT_BLOCK_RELEASE=off
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart={PYTHON} {appdir}/hosted_server.py --config {p} --paused
Restart=on-failure
RestartSec=5
UMask=0077
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
ProtectProc=invisible
RestrictSUIDSGID=yes
LockPersonality=yes
ReadWritePaths={cohort/name} {ledger_dir}
InaccessiblePaths={cohort/('test' if name=='pilot' else 'pilot')}
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
IPAddressDeny=169.254.169.254
IPAddressDeny=fd00:ec2::254
MemoryMax=900M
TasksMax=64
LimitNOFILE=1024
StandardOutput=null
StandardError=journal
LogRateLimitIntervalSec=60
LogRateLimitBurst=20
[Install]
WantedBy=multi-user.target
'''
        write('/etc/systemd/system/daylight-'+name+'.service',unit,0o644)
    current.symlink_to(target)
    operations={'bucket':'daylight-pilot-foundation-backupbucket-zmzwmrv5ebp3',
        'kms_key':'arn:aws:kms:us-east-1:020055445580:key/532f547a-784f-4a61-876a-d692e3b675ac',
        'region':'us-east-1','app_uid':user.pw_uid,'app_gid':user.pw_gid}
    write('/etc/daylight-pilot/operations.json',json.dumps(operations)+'\n')
    install_operations(target)
    run('systemd-analyze','verify','/etc/systemd/system/daylight-pilot.service',
        '/etc/systemd/system/daylight-test.service','/etc/systemd/system/daylight-delete.service',
        '/etc/systemd/system/daylight-maintain.service','/etc/systemd/system/daylight-backup.service')
    # The parent deployment first verifies the quota behavior in an isolated
    # network namespace. Initialize itself also uses nft --check, then durably
    # debits the one-time allowance before granting any application traffic.
    egress=str(target/'deployment/hosted_egress_guard.py')
    run('/usr/bin/python3',egress,'initialize')
    run('/usr/bin/python3',egress,'install-unit')
    run('systemctl','daemon-reload')
    run('systemctl','enable','--now','daylight-delete.service','daylight-pilot.service','daylight-test.service',
        'daylight-maintain.timer','daylight-backup.timer')
    run('systemctl','is-active','daylight-delete.service','daylight-pilot.service','daylight-test.service')
    print(json.dumps({'release':release,'services_installed':True,'ai_paused':True,'public_access_changed':False}))


def install_operations(target):
    for name,command in [('delete','deletion-service'),('maintain','maintain'),('backup','backup')]:
        kind='simple' if name=='delete' else 'oneshot'
        runtime='RuntimeDirectory=daylight-delete\nRuntimeDirectoryMode=0750\n' if name=='delete' else ''
        restart='Restart=on-failure\nRestartSec=10\n' if name=='delete' else ''
        unit=f'''[Unit]
Description=Daylight private {name}
After=daylight-postgres.service network-online.target
Requires=daylight-postgres.service
RequiresMountsFor={STATE}
[Service]
Type={kind}
{restart}TimeoutStartSec=300
ExecStart={PYTHON} {target}/deployment/hosted_operations.py {command}
UMask=0077
Environment=AWS_MAX_ATTEMPTS=1
Environment=PYTHONDONTWRITEBYTECODE=1
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
ReadWritePaths={STATE}/operations {STATE}/cohorts {STATE}/budget {STATE}/owner-exports
{runtime}MemoryMax=384M
TasksMax=32
StandardOutput=null
StandardError=journal
LogRateLimitIntervalSec=60
LogRateLimitBurst=10
[Install]
WantedBy=multi-user.target
'''
        write('/etc/systemd/system/daylight-'+name+'.service',unit,0o644)
    for path in ('operations','owner-exports'):
        (STATE/path).mkdir(mode=0o700,exist_ok=True)
    for name,calendar in [('maintain','hourly'),('backup','*-*-* 05:15:00 UTC')]:
        write('/etc/systemd/system/daylight-'+name+'.timer',f'''[Unit]
Description=Daylight {name} schedule
[Timer]
OnCalendar={calendar}
Persistent=true
RandomizedDelaySec=60
[Install]
WantedBy=timers.target
''',0o644)

def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('stage');p.add_argument('archive',type=Path);p.add_argument('sha256')
    p=sub.add_parser('apply');p.add_argument('release');p.add_argument('--approved-runtime-access',action='store_true',required=True)
    args=parser.parse_args();assert os.geteuid()==0
    if args.command=='stage':print(json.dumps({'staged_release':stage(args.archive,args.sha256)}))
    else:apply(args.release)

if __name__=='__main__':main()
