#!/usr/bin/env python3
"""D186-D187 bounded private backups, retention and durable deletion.

Root-only operations on the existing host. No model calls or AWS provisioning.
Deletion markers precede removal; restore must replay every surviving marker.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import struct
import subprocess
import tarfile
import tempfile
import time

STATE=Path('/var/lib/daylight-state')
CONFIG=Path('/etc/daylight-pilot/operations.json')
ENVIRONMENTS=('pilot','test')
MAX_BACKUP=128*1024*1024
MAX_DAILY_MARKER_ATTEMPTS=64
MAX_MARKERS=4096
PREFIX='hosted-backups/'
SOCKET=Path('/run/daylight-delete/socket')


def run(args, *, data=None, timeout=120):
    result=subprocess.run(args,input=data,capture_output=True,timeout=timeout)
    if result.returncode:
        raise RuntimeError('Private operation failed: '+Path(args[0]).name)
    return result.stdout


def settings():
    value=json.loads(CONFIG.read_text())
    if set(value)!={'bucket','kms_key','region','app_uid','app_gid'} or value['region']!='us-east-1':
        raise ValueError('Use exact reviewed backup settings')
    return value


def aws(arguments,config):
    return run(['aws','--region',config['region'],'--no-cli-pager','--cli-connect-timeout','5',
                '--cli-read-timeout','20',*arguments],timeout=35)


def put_once(file,key,config):
    if not key.startswith(PREFIX) or '..' in key:
        raise ValueError('Unexpected backup key')
    aws(['s3api','put-object','--bucket',config['bucket'],'--key',key,'--body',str(file),
         '--server-side-encryption','aws:kms','--ssekms-key-id',config['kms_key'],
         '--bucket-key-enabled','--if-none-match','*'],config)


def private_json(path,value):
    """Atomic durable root-only receipt, including before external requests."""
    temporary=path.with_suffix(path.suffix+'.tmp')
    with temporary.open('w') as stream:
        json.dump(value,stream,separators=(',',':'));stream.flush();os.fsync(stream.fileno())
    temporary.chmod(0o600);temporary.replace(path)
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


@contextmanager
def deletion_lock():
    directory=STATE/'operations';directory.mkdir(mode=0o700,exist_ok=True)
    with (directory/'deletion.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        yield


def marker_attempt():
    """Persist a global retry ceiling, so restarts cannot reset request costs."""
    path=STATE/'operations/marker-attempts.json'
    today=datetime.now(timezone.utc).strftime('%Y-%m-%d')
    value=json.loads(path.read_text()) if path.exists() else {'day':today,'count':0}
    if value['day']!=today:value={'day':today,'count':0}
    if value['count']>=MAX_DAILY_MARKER_ATTEMPTS:
        raise RuntimeError('Private deletion service reached its daily retry allowance')
    value['count']+=1;private_json(path,value)


def pg(query,environment):
    if environment not in ENVIRONMENTS:raise ValueError('Unknown environment')
    return run(['runuser','-u','postgres','--','psql','-X','-qAt','-v','ON_ERROR_STOP=1',
                '-h',str(STATE/'pgsocket'),'-p','55485','-d','daylight_history_'+environment,
                '-c',"SET statement_timeout='10s'; SET lock_timeout='3s'; "+query])


def valid_visit(visit):
    return isinstance(visit,str) and re.fullmatch('[0-9a-f]{32}',visit) is not None


@contextmanager
def sqlite_database(path, *, mode='rw'):
    path=Path(path)
    if path.is_symlink():raise ValueError('Unexpected SQLite-store symlink')
    db=sqlite3.connect(path.as_uri()+'?mode='+mode,uri=True,timeout=3)
    try:
        db.execute('PRAGMA trusted_schema=OFF')
        with db:yield db
    finally:db.close()


def access(environment):
    if environment not in ENVIRONMENTS:raise ValueError('Unknown environment')
    path=STATE/'cohorts'/environment/'access.sqlite3'
    return sqlite_database(path)


def delete_visit(environment,visit,config):
    with deletion_lock():return _delete_visit(environment,visit,config)


def _delete_visit(environment,visit,config):
    if not valid_visit(visit):raise ValueError('Invalid visit')
    with access(environment) as db:
        if not db.execute('SELECT 1 FROM invites WHERE id=?',(visit,)).fetchone():
            raise ValueError('Unknown visit')
    receipts=STATE/'operations/deletions'/environment
    receipts.mkdir(parents=True,exist_ok=True,mode=0o700)
    receipt=receipts/(visit+'.json')
    pending=receipts/(visit+'.pending')
    if not receipt.exists():
        marker_attempt()
        if pending.exists():
            marker=json.loads(pending.read_text())
        else:
            if sum(1 for pattern in ('*/*.json','*/*.pending')
                   for _ in (STATE/'operations/deletions').glob(pattern))>=MAX_MARKERS:
                raise RuntimeError('Deletion journal reached its bounded capacity')
            marker={'schema':1,'environment':environment,'visit':visit,
                    'deleted_at':datetime.now(timezone.utc).isoformat(),'reason':'participant_request'}
            # Recovery sees the intent even if the process dies just after PUT.
            private_json(pending,marker)
        raw=json.dumps(marker,separators=(',',':')).encode()
        # A lost PUT acknowledgement is safe: retrieve and validate the existing
        # immutable marker. Never overwrite it or restart its retention clock.
        with tempfile.NamedTemporaryFile(dir=receipts) as stream:
            stream.write(raw);stream.flush()
            key=PREFIX+'deletions/'+environment+'/'+visit+'.json'
            try:put_once(Path(stream.name),key,config)
            except RuntimeError:
                aws(['s3api','get-object','--bucket',config['bucket'],'--key',key,stream.name],config)
                raw=Path(stream.name).read_bytes()
                old=json.loads(raw)
                if old.get('environment')!=environment or old.get('visit')!=visit or old.get('schema')!=1:
                    raise ValueError('Unexpected deletion marker')
        private_json(receipt,json.loads(raw))
        pending.unlink(missing_ok=True)
    # Revoke before SQL removal: a database outage cannot leave a deleted visit
    # accessible. Hourly maintenance retries durable local receipts.
    with access(environment) as db:
        db.execute('UPDATE invites SET revoked=1 WHERE id=?',(visit,))
    pg("BEGIN; SELECT set_config('daylight.visit','"+visit+"',true); "
       "SELECT hosted_history.delete_visit('"+visit+"'); COMMIT;",environment)
    # Owner exports are deliberately private JSON files with a visit field.
    for path in (STATE/'owner-exports').glob('*.json'):
        if path.is_file() and not path.is_symlink():
            try:matches=json.loads(path.read_text()).get('visit')==visit
            except (ValueError,AttributeError):matches=False
            if matches:path.unlink()
    return {'deleted':True}


def expire():
    for environment in ENVIRONMENTS:
        pg("""BEGIN;
        SELECT pg_advisory_xact_lock(hashtext('daylight-history-maintenance'));
        INSERT INTO hosted_history.deletions(visit,reason)
        SELECT visit,'retention_expired' FROM hosted_history.visits WHERE expires_at<=now()
        ON CONFLICT(visit) DO NOTHING;
        DELETE FROM hosted_history.turns t USING hosted_history.deletions d WHERE t.visit=d.visit;
        UPDATE hosted_history.visits v SET deleted=true FROM hosted_history.deletions d WHERE v.visit=d.visit;
        COMMIT;""",environment)
    exports=STATE/'owner-exports'
    if exports.is_dir():
        for path in exports.iterdir():
            if path.is_file() and not path.is_symlink() and path.stat().st_mtime<time.time()-86400:
                path.unlink()


def retry_deletions(config, *, locked=False):
    for environment in ENVIRONMENTS:
        directory=STATE/'operations/deletions'/environment
        visits={p.stem for pattern in ('*.json','*.pending') for p in directory.glob(pattern)}
        for visit in sorted(visits):
            if valid_visit(visit):
                (_delete_visit if locked else delete_visit)(environment,visit,config)


def backup(config):
    directory=STATE/'operations';directory.mkdir(exist_ok=True,mode=0o700)
    with (directory/'backup.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        day=datetime.now(timezone.utc).strftime('%Y-%m-%d')
        receipt=directory/('backup-'+day+'.json')
        if receipt.exists():return {'already_completed':True}
        created_at=datetime.now(timezone.utc).isoformat()
        # A backup whose S3 acknowledgement was lost is recovered, not replaced.
        key=PREFIX+'daily/'+day+'.tar.gz'
        intent=directory/('backup-'+day+'.pending')
        if intent.exists():
            info=json.loads(intent.read_text())
            remote=json.loads(aws(['s3api','head-object','--bucket',config['bucket'],'--key',key],config))
            if remote.get('Metadata',{}).get('sha256')!=info['sha256'] or remote['ContentLength']!=info['bytes']:
                raise RuntimeError('Daily backup acknowledgement needs owner review')
            private_json(receipt,info);intent.unlink();return info
        with deletion_lock():
            retry_deletions(config,locked=True)
            expire()
        for environment in ENVIRONMENTS:
            size=int(pg('SELECT pg_database_size(current_database())',environment).strip())
            if size>1024*1024*1024:raise RuntimeError('History database exceeds backup bound')
        if shutil.disk_usage(directory).free<3*1024*1024*1024:
            raise RuntimeError('Insufficient bounded backup workspace')
        with tempfile.TemporaryDirectory(dir=directory,prefix='backup-') as temp:
            temp=Path(temp)
            for environment in ENVIRONMENTS:
                output=temp/(environment+'.dump')
                with output.open('wb') as stream:
                    result=subprocess.run(['runuser','-u','postgres','--','pg_dump','-Fc',
                        '-h',str(STATE/'pgsocket'),'-p','55485','-d','daylight_history_'+environment],
                        stdout=stream,stderr=subprocess.PIPE,timeout=120)
                    if result.returncode:raise RuntimeError('History backup failed')
                source=STATE/'cohorts'/environment
                with sqlite_database(source/'access.sqlite3',mode='ro') as src, sqlite_database(temp/(environment+'-access.sqlite3'),mode='rwc') as dst:
                    src.backup(dst)
                keyfd=os.open(source/'signing.key',os.O_RDONLY|os.O_NOFOLLOW)
                with os.fdopen(keyfd,'rb') as signing:
                    signing_value=signing.read(33)
                    if len(signing_value)!=32:raise RuntimeError('Unexpected invitation signing key')
                (temp/(environment+'-signing.key')).write_bytes(signing_value)
            with sqlite_database(STATE/'budget/model-usage.sqlite3',mode='ro') as src,sqlite_database(temp/'model-usage.sqlite3',mode='rwc') as dst:
                src.backup(dst)
            manifest={'schema':1,'created_at':created_at,
                'release':Path('/opt/daylight-pilot/current').resolve().name,
                'budget_restore':'blocked_until_provider_reconciliation',
                'restore_requires':'latest_s3_deletions_then_expire_before_any_service_start'}
            (temp/'manifest.json').write_text(json.dumps(manifest))
            archive=temp/'history.tar.gz'
            files=list(temp.iterdir())
            with tarfile.open(archive,'w:gz') as bundle:
                for file in files:bundle.add(file,arcname=file.name,recursive=False)
            if archive.stat().st_size>MAX_BACKUP:raise RuntimeError('Backup exceeds approved daily storage bound')
            info={'key':key,'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
            private_json(intent,info)
            aws(['s3api','put-object','--bucket',config['bucket'],'--key',key,'--body',str(archive),
                 '--server-side-encryption','aws:kms','--ssekms-key-id',config['kms_key'],
                 '--bucket-key-enabled','--if-none-match','*','--metadata','sha256='+info['sha256']],config)
            private_json(receipt,info);intent.unlink()
            return info


def serve(config):
    SOCKET.parent.mkdir(mode=0o750,exist_ok=True)
    os.chown(SOCKET.parent,0,config['app_gid'])
    if SOCKET.exists():SOCKET.unlink()
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as listener:
        listener.bind(str(SOCKET));SOCKET.chmod(0o660);os.chown(SOCKET,0,config['app_gid'])
        listener.listen(4)
        while True:
            connection,_=listener.accept()
            with connection:
                connection.settimeout(4)
                try:
                    _,uid,_=struct.unpack('3i',connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                    if uid!=config['app_uid']:raise ValueError('Unauthorized peer')
                    data=b''
                    while not data.endswith(b'\n') and len(data)<=512:
                        part=connection.recv(513-len(data))
                        if not part:break
                        data+=part
                    request=json.loads(data)
                    if len(data)>512 or set(request)!={'environment','visit'}:raise ValueError('Invalid deletion request')
                    result=delete_visit(request['environment'],request['visit'],config)
                except Exception:result={'deleted':False}
                try:connection.sendall(json.dumps(result).encode()+b'\n')
                except OSError:pass
                time.sleep(1)  # Serial processing bounds external calls.


def verify_archive(path,expected_sha256):
    """Validate a private recovery candidate. This NEVER restores or starts chat.

    Recovery must separately fetch/replay current S3 deletion markers and run
    expiry. Budget restoration remains blocked pending provider reconciliation.
    """
    if path.is_symlink() or path.stat().st_size>MAX_BACKUP:
        raise ValueError('Use a bounded regular backup archive')
    if not re.fullmatch('[0-9a-f]{64}',expected_sha256) or hashlib.sha256(path.read_bytes()).hexdigest()!=expected_sha256:
        raise ValueError('Backup digest mismatch')
    required={'pilot.dump','test.dump','pilot-access.sqlite3','test-access.sqlite3',
              'pilot-signing.key','test-signing.key','model-usage.sqlite3','manifest.json'}
    with tarfile.open(path,'r:gz') as archive:
        members=archive.getmembers()
        if ({m.name for m in members}!=required or len(members)!=len(required)
                or any(not m.isfile() for m in members)
                or sum(m.size for m in members)>768*1024*1024):
            raise ValueError('Unexpected backup inventory')
        raw=archive.extractfile('manifest.json').read(4097)
        if len(raw)>4096:raise ValueError('Oversized backup manifest')
        manifest=json.loads(raw)
        created=datetime.fromisoformat(manifest['created_at'])
        if created.tzinfo is None:raise ValueError('Backup timestamp lacks timezone')
        age=(datetime.now(timezone.utc)-created).total_seconds()
        if not 0<=age<29*86400:
            raise ValueError('Backup is outside the safe deletion-journal recovery window')
        if (manifest.get('schema')!=1 or manifest.get('budget_restore')!='blocked_until_provider_reconciliation'
                or manifest.get('restore_requires')!='latest_s3_deletions_then_expire_before_any_service_start'):
            raise ValueError('Unexpected recovery contract')
        with tempfile.TemporaryDirectory(prefix='daylight-restore-check-') as temp:
            for name in required-{'manifest.json'}:
                member=archive.getmember(name)
                target=Path(temp)/name
                with archive.extractfile(member) as source,target.open('wb') as destination:
                    shutil.copyfileobj(source,destination)
                target.chmod(0o600)
                if name.endswith('.sqlite3'):
                    with sqlite_database(target,mode='ro') as db:
                        if db.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:
                            raise ValueError('Backup SQLite integrity failed')
                elif name.endswith('.dump'):
                    run(['pg_restore','--list',str(target)])
                elif target.stat().st_size!=32:
                    raise ValueError('Unexpected signing-key size')
    return {'archive_integrity_verified':True,'service_resume_permitted':False,
            'remaining':['restore into isolated database','replay current S3 deletion markers',
                         'apply expiry','reconcile provider budget before enabling chat']}


def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('backup','maintain','deletion-service','verify-archive'))
    parser.add_argument('--archive',type=Path)
    parser.add_argument('--sha256')
    args=parser.parse_args()
    if os.geteuid()!=0:raise ValueError('Owner maintenance only')
    if args.command=='verify-archive':
        if args.archive is None or args.sha256 is None:parser.error('Supply --archive and --sha256')
        print(json.dumps(verify_archive(args.archive,args.sha256)));return
    config=settings()
    if args.command=='deletion-service':serve(config)
    elif args.command=='backup':print(json.dumps(backup(config)))
    else:expire();retry_deletions(config);print('{"maintenance_completed":true}')

if __name__=='__main__':main()
