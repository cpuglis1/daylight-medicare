"""Private history maintenance. Invoke through the owner's MFA-protected SSM.

The runtime role cannot run this maintenance. Backups must preserve the current
deletion journal separately and reapply it BEFORE a restored DB is served.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess

import server
import psycopg
from psycopg import sql
from hosted_history import SCHEMA_SQL

EXPORTS=Path('/var/lib/daylight-state/owner-exports')
AUDIT=Path('/var/lib/daylight-state/operations/owner-review-audit.jsonl')
MAX_REVIEW_ATTEMPTS=4000
MAX_EXPORT_BYTES=64*1024*1024


def export_path(path):
    """Only a fresh JSON file in the owner's private, expiring export folder."""
    path=Path(path)
    if (not path.is_absolute() or path.parent!=EXPORTS
            or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}\.json',path.name)
            or path.exists() or path.is_symlink()):
        raise ValueError('Use a new JSON file in the private owner-exports directory.')
    info=EXPORTS.stat()
    if (EXPORTS.is_symlink() or not EXPORTS.is_dir() or info.st_uid!=os.geteuid()
            or info.st_mode & 0o077):
        raise ValueError('Owner exports require a private owner-controlled directory.')
    return path


def audit_review(database,visit,path):
    """Record a bounded metadata-only attempt before reading any chat content."""
    parent=AUDIT.parent
    if (parent.is_symlink() or not parent.is_dir() or parent.stat().st_uid!=os.geteuid()
            or parent.stat().st_mode & 0o077):
        raise ValueError('Review audit requires the private operations directory.')
    fd=os.open(AUDIT,os.O_CREAT|os.O_APPEND|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'r+',encoding='utf-8') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX)
        info=os.fstat(stream.fileno())
        if info.st_uid!=os.geteuid() or info.st_mode & 0o077 or info.st_size>4*1024*1024:
            raise ValueError('Invalid owner review audit.')
        stream.seek(0)
        if sum(1 for _ in stream)>=MAX_REVIEW_ATTEMPTS:
            raise ValueError('The bounded owner review allowance has been reached.')
        event={'action':'review_requested','time':datetime.now(timezone.utc).isoformat(),
            'database':database,'visit':visit,'filename':path.name}
        stream.write(json.dumps(event,separators=(',',':'))+'\n')
        stream.flush();os.fsync(stream.fileno())


def review_export(dsn,visit,output):
    if os.geteuid()!=0:raise ValueError('Owner review must run through root SSM administration.')
    if not re.fullmatch(r'[0-9a-f]{32}',visit):raise ValueError('Use an exact hosted visit identifier.')
    parsed=psycopg.conninfo.conninfo_to_dict(dsn)
    database=parsed.get('dbname')
    if (set(parsed)-{'host','port','dbname','user'} or
            database not in {'daylight_history_pilot','daylight_history_test'} or
            parsed.get('host')!='/var/lib/daylight-state/pgsocket' or parsed.get('port')!='55485' or
            parsed.get('user','postgres')!='postgres'):
        raise ValueError('Owner review uses the exact private PostgreSQL socket and history database.')
    output=export_path(output)
    audit_review(database,visit,output)
    # The child receives only a validated pseudonymous visit and fixed SQL. Its
    # output is captured into a new private file, never terminal or SSM output.
    query="""SELECT jsonb_build_object('visit','VISIT','turns',COALESCE(jsonb_agg(
        jsonb_build_array(request_id,status,accepted_at,finished_at,submitted,response,
                          metadata,usage,error_code) ORDER BY accepted_at,request_id),'[]'::jsonb))
        FROM hosted_history.turns t JOIN hosted_history.visits v USING(visit)
        WHERE t.visit='VISIT' AND NOT v.deleted AND v.expires_at>now();""".replace('VISIT',visit)
    fd=os.open(output,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'wb') as stream:
            # Bound child output and wall time; no prompt/history value is
            # passed as shell code or emitted by this administrative command.
            import resource
            def limits():resource.setrlimit(resource.RLIMIT_FSIZE,(MAX_EXPORT_BYTES,MAX_EXPORT_BYTES))
            result=subprocess.run(['runuser','-u','postgres','--','psql','-X','-qAt',
                '-v','ON_ERROR_STOP=1','-h',parsed['host'],'-p',parsed['port'],'-d',database,
                '-c',query],stdout=stream,stderr=subprocess.PIPE,timeout=30,preexec_fn=limits)
            if result.returncode:raise ValueError('Owner review could not be exported.')
            stream.flush();os.fsync(stream.fileno())
        if not output.stat().st_size:raise ValueError('Owner review returned no export.')
    except Exception:
        output.unlink(missing_ok=True)
        raise ValueError('Owner review failed; no export was retained.') from None


def maintain(db):
    db.execute("SELECT pg_advisory_xact_lock(hashtext('daylight-history-maintenance'))")
    db.execute('''INSERT INTO hosted_history.deletions(visit,reason)
        SELECT visit,'retention_expired' FROM hosted_history.visits WHERE expires_at<=now()
        ON CONFLICT(visit) DO NOTHING''')
    removed=db.execute('''DELETE FROM hosted_history.turns t USING hosted_history.deletions d
        WHERE t.visit=d.visit''').rowcount
    db.execute('''UPDATE hosted_history.visits v SET deleted=true
        FROM hosted_history.deletions d WHERE v.visit=d.visit''')
    return removed


def private_write(path,data):
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as stream:json.dump(data,stream,default=str)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dsn',required=True,help='Local peer-authenticated maintenance DSN, no password.')
    sub=parser.add_subparsers(dest='command',required=True)
    migrate=sub.add_parser('migrate');migrate.add_argument('--runtime-role',required=True)
    sub.add_parser('expire')
    sub.add_parser('journal-export').add_argument('output',type=Path)
    sub.add_parser('restore-journal').add_argument('input',type=Path)
    review=sub.add_parser('review');review.add_argument('visit');review.add_argument('output',type=Path)
    args=parser.parse_args()
    if args.command=='review':
        review_export(args.dsn,args.visit,args.output)
        return
    with psycopg.connect(args.dsn,connect_timeout=3) as db:
        name,=db.execute('SELECT current_database()').fetchone()
        if name not in {'daylight_history_pilot','daylight_history_test'}:
            raise ValueError('Use a dedicated hosted-history database.')
        if args.command=='migrate':
            db.execute(SCHEMA_SQL)
            role=sql.Identifier(args.runtime_role)
            db.execute(sql.SQL('REVOKE ALL ON ALL TABLES IN SCHEMA hosted_history FROM {}').format(role))
            db.execute(sql.SQL('GRANT USAGE ON SCHEMA hosted_history TO {}').format(role))
            db.execute(sql.SQL('GRANT SELECT,INSERT ON hosted_history.visits,hosted_history.turns TO {}').format(role))
            db.execute(sql.SQL('GRANT UPDATE(last_activity,expires_at) ON hosted_history.visits TO {}').format(role))
            db.execute(sql.SQL('GRANT UPDATE(finished_at,status,response,usage,error_code) ON hosted_history.turns TO {}').format(role))
            db.execute(sql.SQL('GRANT EXECUTE ON FUNCTION hosted_history.delete_visit(text) TO {}').format(role))
        elif args.command=='expire':
            print(json.dumps({'turns_removed':maintain(db)}))
        elif args.command=='journal-export':
            rows=db.execute('SELECT visit,deleted_at,reason FROM hosted_history.deletions ORDER BY visit').fetchall()
            private_write(args.output,{'schema':1,'deletions':rows})
        elif args.command=='restore-journal':
            journal=json.loads(args.input.read_text())
            if set(journal)!={'schema','deletions'} or journal['schema']!=1:raise ValueError('Use a reviewed deletion journal.')
            for visit,when,reason in journal['deletions']:
                db.execute('''INSERT INTO hosted_history.deletions VALUES (%s,%s,%s)
                    ON CONFLICT(visit) DO NOTHING''',(visit,when,reason))
            maintain(db)


if __name__=='__main__':main()
