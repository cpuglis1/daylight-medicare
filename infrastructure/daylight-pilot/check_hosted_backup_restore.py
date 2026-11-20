#!/usr/bin/env python3
"""Owner-run, provider-free S3 backup/isolated PostgreSQL restore check.

Uses only a completed daily backup and new daylight_history_check_* databases.
Never restores production databases, credentials, invitations or spending state.
"""
from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess
import tarfile
import tempfile

STATE=Path('/var/lib/daylight-state')
OPERATIONS=Path('/opt/daylight-pilot/current/deployment/hosted_operations.py')


def run(args, *, data=None):
    result=subprocess.run(args,input=data,capture_output=True,timeout=120)
    if result.returncode:raise RuntimeError('Isolated restore check failed: '+Path(args[0]).name)
    return result.stdout


def pg(database,query):
    if database!='postgres' and not database.startswith('daylight_history_check_'):
        raise ValueError('Refusing a production database')
    bounded=query if query.startswith(('CREATE DATABASE ','DROP DATABASE ')) else "SET statement_timeout='20s'; SET lock_timeout='3s'; "+query
    return run(['runuser','-u','postgres','--','psql','-X','-qAt','-v','ON_ERROR_STOP=1',
        '-h',str(STATE/'pgsocket'),'-p','55485','-d',database,
        '-c',bounded]).decode().strip()


def main():
    if os.geteuid()!=0:raise ValueError('Use owner SSM administration')
    os.umask(0o077)
    spec=importlib.util.spec_from_file_location('hosted_ops',OPERATIONS)
    ops=importlib.util.module_from_spec(spec);spec.loader.exec_module(ops)
    config=ops.settings()
    day=datetime.now(timezone.utc).strftime('%Y-%m-%d')
    receipt=json.loads((STATE/'operations'/('backup-'+day+'.json')).read_text())
    if receipt['key']!='hosted-backups/daily/'+day+'.tar.gz':raise ValueError('Unexpected backup key')
    report={'backup_key':receipt['key'],'backup_sha256':receipt['sha256'],'production_changed':False,'databases':{}}
    created=[]
    with tempfile.TemporaryDirectory(dir=STATE/'operations',prefix='restore-check-') as temporary:
        temporary=Path(temporary)
        archive=temporary/'history.tar.gz'
        ops.aws(['s3api','get-object','--bucket',config['bucket'],'--key',receipt['key'],str(archive)],config)
        report['archive']=ops.verify_archive(archive,receipt['sha256'])
        try:
            with tarfile.open(archive,'r:gz') as bundle:
                for environment in ('pilot','test'):
                    database='daylight_history_check_restore_'+secrets.token_hex(5)
                    pg('postgres','CREATE DATABASE '+database+' CONNECTION LIMIT 0')
                    created.append(database)
                    pg('postgres','REVOKE ALL ON DATABASE '+database+' FROM PUBLIC; REVOKE ALL ON DATABASE '+database+' FROM daylight_app')
                    # Send the exact dump via stdin. PostgreSQL never needs to
                    # traverse the owner's private download/credential folder.
                    dump=bundle.extractfile(environment+'.dump').read()
                    run(['runuser','-u','postgres','--','pg_restore','--exit-on-error',
                         '-h',str(STATE/'pgsocket'),'-p','55485','-d',database],data=dump)
                    tables=pg(database,"SELECT count(*) FROM pg_tables WHERE schemaname='hosted_history'")
                    if tables!='3':raise ValueError('Restored history table inventory mismatch')
                    rls=pg(database,"SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='hosted_history' AND c.relname IN ('visits','turns') AND c.relrowsecurity AND c.relforcerowsecurity")
                    if rls!='2':raise ValueError('Restore lost row-level security')
                    counts=pg(database,"SELECT json_build_object('visits',(SELECT count(*) FROM hosted_history.visits),'turns',(SELECT count(*) FROM hosted_history.turns),'deletions',(SELECT count(*) FROM hosted_history.deletions))")
                    deleted=secrets.token_hex(16);expired=secrets.token_hex(16);kept=secrets.token_hex(16)
                    for visit in (deleted,expired,kept):
                        pg(database,"INSERT INTO hosted_history.visits(visit,consent_version,consent_at) VALUES ('"+visit+"','fictional-restore-check',1); INSERT INTO hosted_history.turns(visit,request_id,signature,status,submitted,metadata) VALUES ('"+visit+"','fictional-restore-turn','fictional','accepted','{}','{}')")
                    # Replay a later deletion journal exactly as recovery must do.
                    pg(database,"INSERT INTO hosted_history.deletions(visit,reason) VALUES ('"+deleted+"','participant_request'); UPDATE hosted_history.visits SET expires_at=now()-interval '1 second' WHERE visit='"+expired+"'")
                    pg(database,"""BEGIN;
                        INSERT INTO hosted_history.deletions(visit,reason)
                        SELECT visit,'retention_expired' FROM hosted_history.visits WHERE expires_at<=now()
                        ON CONFLICT(visit) DO NOTHING;
                        DELETE FROM hosted_history.turns t USING hosted_history.deletions d WHERE t.visit=d.visit;
                        UPDATE hosted_history.visits v SET deleted=true FROM hosted_history.deletions d WHERE v.visit=d.visit;
                        COMMIT;""")
                    result=pg(database,"SELECT (SELECT count(*) FROM hosted_history.turns WHERE visit IN ('"+deleted+"','"+expired+"'))::text || ',' || (SELECT count(*) FROM hosted_history.turns WHERE visit='"+kept+"')::text || ',' || (SELECT count(*) FROM hosted_history.visits WHERE visit IN ('"+deleted+"','"+expired+"') AND deleted)::text")
                    if result!='0,1,2':raise ValueError('Restore deletion/retention isolation failed')
                    report['databases'][environment]={'restored':True,'tables':3,'rls_tables':2,
                        'restored_counts':json.loads(counts),'fictional_deletion_expiry_isolation':True}
        finally:
            # Only random disposable databases created by this invocation.
            for database in created:pg('postgres','DROP DATABASE '+database)
    report['disposable_databases_removed']=True
    report['budget_restored']=False
    report['models_called']=False
    report['s3_tombstone_transport_tested']=False
    ops.private_json(STATE/'operations'/('restore-check-'+day+'.json'),report)
    print(json.dumps(report))


if __name__=='__main__':main()
