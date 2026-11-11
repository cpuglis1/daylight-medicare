import argparse
import json
import os
from pathlib import Path

from . import PlanTypeError
from .common import canonical, read_json
from .prepare import prepare, verify_bundle
from .store import Repository, connect, install, load, select_research


def main():
    parser=argparse.ArgumentParser(description='Versioned Collier plan-type source research; consumer display held')
    commands=parser.add_subparsers(dest='command',required=True)
    build=commands.add_parser('prepare')
    build.add_argument('--repository',required=True,type=Path)
    build.add_argument('--selection',required=True,type=Path)
    build.add_argument('--output',required=True,type=Path)
    verify=commands.add_parser('verify-bundle')
    verify.add_argument('--bundle',required=True,type=Path)
    for name in ('install','load','select-research','inspect','status','stop','review','diff'):
        sub=commands.add_parser(name)
        sub.add_argument('--expected-database',required=True)
        if name in ('load',):sub.add_argument('--bundle',required=True,type=Path)
        if name in ('select-research','inspect','status','stop'):sub.add_argument('--build-id',required=True)
        if name in ('select-research','stop'):sub.add_argument('--reason',required=True)
        if name=='stop':sub.add_argument('--source-id')
        if name=='inspect':sub.add_argument('--request',required=True,type=Path)
        if name=='review':
            sub.add_argument('--receipt',required=True,type=Path)
            sub.add_argument('--original',required=True,type=Path)
            sub.add_argument('--trusted-reviewers',required=True,type=Path)
        if name=='diff':
            sub.add_argument('--before',required=True)
            sub.add_argument('--after',required=True)
    args=parser.parse_args()
    if args.command=='prepare':
        result=prepare(args.repository,args.selection,args.output)
        print(canonical({'build_id':result['build_id'],'counts':result['counts'],'consumer_release':'held'}));return
    if args.command=='verify-bundle':
        manifest=verify_bundle(args.bundle)
        from .prepare import stream_items
        total=sum(sum(1 for _ in stream_items(args.bundle,s)) for s in manifest['sources'])
        print(canonical({'build_id':manifest['build_id'],'verified_items':total,'consumer_release':'held'}));return
    dsn=os.environ['DAYLIGHT_PLAN_TYPES_DATABASE_URL']
    from psycopg.conninfo import conninfo_to_dict
    info=conninfo_to_dict(dsn)
    if (info.get('dbname')!=args.expected_database or info.get('service') or info.get('hostaddr')
            or (not info.get('host','').startswith('/') and info.get('sslmode')!='verify-full')):
        raise PlanTypeError('EXPLICIT_DATABASE_TARGET_REQUIRED')
    with connect(dsn,readonly=args.command in {'inspect','status','diff'}) as connection:
        actual=connection.execute('SELECT current_database() AS database').fetchone()['database']
        if actual!=args.expected_database:raise PlanTypeError('DATABASE_TARGET_MISMATCH')
        if args.command=='install':
            install(connection);result={'schema':'installed_or_exact','consumer_release':'held'}
        elif args.command=='load':result=load(connection,args.bundle)
        elif args.command=='select-research':
            select_research(connection,args.build_id,args.reason);result={'selected_research':args.build_id,'consumer_release':'held'}
        elif args.command=='inspect':
            result=Repository(lambda:connect(dsn,readonly=True),args.build_id).query(read_json(args.request))
        elif args.command=='status':
            result=Repository(lambda:connect(dsn,readonly=True),args.build_id).status()
        elif args.command=='stop':
            if args.source_id and not connection.execute('SELECT 1 FROM dl_plan_types.source WHERE build_id=%s AND source_id=%s',(args.build_id,args.source_id)).fetchone():
                raise PlanTypeError('SOURCE_OUTSIDE_STOP_BUILD')
            connection.execute('INSERT INTO dl_plan_types.stop_event(build_id,source_id,reason) VALUES(%s,%s,%s)',(args.build_id,args.source_id,args.reason))
            result={'stopped':args.build_id}
        elif args.command=='review':
            from .authority import record_review
            record_review(connection,args.receipt,args.original,args.trusted_reviewers)
            result={'review_recorded':True,'consumer_release':'held'}
        else:
            found=connection.execute('SELECT count(*) AS n FROM dl_plan_types.completion WHERE build_id=ANY(%s)',([args.before,args.after],)).fetchone()['n']
            if found!=len({args.before,args.after}):raise PlanTypeError('COMPLETED_DIFF_BUILDS_REQUIRED')
            rows=connection.execute('''SELECT coalesce(a.kind,b.kind) AS kind,coalesce(a.entity_key,b.entity_key) AS entity_key,
              CASE WHEN a.item_id IS NULL THEN 'added' WHEN b.item_id IS NULL THEN 'removed'
                   WHEN a.payload_sha256<>b.payload_sha256 THEN 'changed' ELSE 'unchanged' END AS disposition
              FROM (SELECT i.*,s.source_path FROM dl_plan_types.item i JOIN dl_plan_types.source s USING(build_id,source_id) WHERE build_id=%s) a
              FULL JOIN (SELECT i.*,s.source_path FROM dl_plan_types.item i JOIN dl_plan_types.source s USING(build_id,source_id) WHERE build_id=%s) b
                ON a.kind=b.kind AND a.source_path=b.source_path AND a.entity_key=b.entity_key AND a.source_pointer=b.source_pointer
              WHERE a.payload_sha256 IS DISTINCT FROM b.payload_sha256
              ORDER BY kind,entity_key LIMIT 1001''',(args.before,args.after)).fetchall()
            result={'before':args.before,'after':args.after,'changes':rows[:1000],'truncated':len(rows)>1000,'consumer_release':'held'}
    print(canonical(result))


if __name__=='__main__':
    main()
