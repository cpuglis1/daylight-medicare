"""D94 lossless, bounded physical copy into an explicitly owned compact DB.

The source is always READ ONLY. Binary COPY round-trips every logical column.
No source database/index is dropped. Resume is bound to source, schema and code.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import threading
import time

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT/'infrastructure/daylight-data'
SOURCE = 'daylight_research_2026_r2'
TARGET = 'daylight_compact_2026_r1'
RUN = PACKAGE/'.state/maintenance/20261105-db-r1'
PACKET = ROOT/'docs/data/infrastructure-execution-2026-10-30-local-full-db/build-r3'
RESERVE = 7*1024**3
CONTROL = ['dl_control.artifact','dl_control.source_snapshot','dl_control.derivation',
 'dl_control.source_access_state','dl_control.job','dl_control.checkpoint',
 'dl_control.ingest_receipt','dl_control.profile_contract',
 'dl_review.acceptance_binding','dl_review.release','dl_review.active_release']
STATE = ('value_state','evidence_state','semantic_review_state','source_use_state',
         'freshness_state','output_acceptance_state')


def hashfile(p):
    h=hashlib.sha256()
    with p.open('rb') as source:
        for block in iter(lambda:source.read(1024**2),b''):h.update(block)
    return h.hexdigest()


def now():return datetime.now(timezone.utc).isoformat()


def fresh_json(p,value):
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:
        json.dump(value,f,indent=2,default=str);f.write('\n');f.flush();os.fsync(f.fileno())


def dsn(database,readonly=False):
    return psycopg.conninfo.make_conninfo(host=str(PACKAGE/'.state/socket'),port='55485',
        dbname=database,user='cep4u',**({'options':'-c default_transaction_read_only=on'} if readonly else {}))


def connect(database,readonly=False):
    db=psycopg.connect(dsn(database,readonly),autocommit=True,row_factory=dict_row)
    db.execute("SET lock_timeout='3s'")
    db.execute("SET statement_timeout='180s'")
    return db


def guard(extra=0):
    free=shutil.disk_usage(ROOT).free
    if free<RESERVE+extra:raise RuntimeError('7 GiB reserve reached; committed chunks preserved')
    return free


@contextmanager
def monitor(db):
    finished=threading.Event();failed=[]
    def watch():
        while not finished.wait(.25):
            if shutil.disk_usage(ROOT).free<RESERVE+256*1024**2:
                failed.append(True);db.cancel();return
    thread=threading.Thread(target=watch,daemon=True);thread.start()
    try:
        guard(256*1024**2);yield
        if failed:raise RuntimeError('Reserve monitor canceled compact operation')
    finally:finished.set();thread.join(timeout=2)


def table_identifier(name):return sql.SQL('.').join(map(sql.Identifier,name.split('.')))


def binary_copy(source,target,query,destination,parameters=()):
    h=hashlib.sha256();total=0
    with source.cursor().copy(sql.SQL('COPY ({}) TO STDOUT (FORMAT BINARY)').format(query),parameters) as incoming:
        with target.cursor().copy(sql.SQL('COPY {} FROM STDIN (FORMAT BINARY)').format(table_identifier(destination))) as outgoing:
            for block in incoming:
                guard(256*1024**2);h.update(block);total+=len(block);outgoing.write(block)
    return h.hexdigest(),total


def binary_hash(db,query,parameters=()):
    h=hashlib.sha256();total=0
    with db.cursor().copy(sql.SQL('COPY ({}) TO STDOUT (FORMAT BINARY)').format(query),parameters) as incoming:
        for block in incoming:h.update(block);total+=len(block)
    return h.hexdigest(),total


def source_contract(source):
    complete=json.loads((PACKET/'LOAD_COMPLETE.json').read_text())
    old=json.loads((PACKET/'TARGET.json').read_text())
    actual=source.execute("SELECT d.oid,shobj_description(d.oid,'pg_database') AS marker,(SELECT system_identifier::text FROM pg_control_system()) AS cluster FROM pg_database d WHERE datname=current_database()").fetchone()
    if (source.info.dbname!=SOURCE or actual['oid']!=old['database_oid'] or actual['marker']!=old['marker'] or actual['cluster']!=old['cluster_system_identifier']):
        raise ValueError('Original database identity differs')
    if complete['source_rows']!=17767179 or complete['projection_rows']!=17823148:raise ValueError('Original source scope differs')
    return {'source':old,'complete_sha256':hashfile(PACKET/'LOAD_COMPLETE.json'),
            'schema_sha256':hashfile(PACKAGE/'redesign/r1/schema.sql'),
            'operator_sha256':hashfile(Path(__file__)), 'new_acceptance':False}


def units():
    values=[]
    for p in sorted((PACKET/'units').glob('*.json')):
        row=json.loads(p.read_text());b=row['binding']
        values.append({'derivation_id':b['derivation_id'],'source_table':b['source_table'],
                      'first':row['first_ordinal'],'last':row['last_ordinal'],
                      'raw_rows':row['source_rows'],'projection_rows':sum(row['projection_counts'].values()),
                      'layer':b['layer_id'],'slot':row['selected_slot']})
    if len(values)!=363 or sum(x['raw_rows'] for x in values)!=17767179 or sum(x['projection_rows'] for x in values)!=17823148:
        raise ValueError('Frozen unit accounting differs')
    return sorted(values,key=lambda x:(x['derivation_id'],x['first']))


def assert_target(db,manifest):
    row=db.execute("SELECT shobj_description(oid,'pg_database') AS marker FROM pg_database WHERE datname=current_database()").fetchone()
    if db.info.dbname!=TARGET or row['marker']!=manifest['marker']:raise ValueError('Compact target ownership differs')
    stored=db.execute('SELECT manifest FROM dl_compact.migration WHERE singleton').fetchone()
    if not stored or stored['manifest']!=manifest:raise ValueError('Compact manifest differs')
    expected=source_contract_source_only()
    if any(manifest[k]!=expected[k] for k in ('schema_sha256','operator_sha256','complete_sha256','source')):
        raise ValueError('Code/source changed; new revision required')


def source_contract_source_only():
    with connect(SOURCE,True) as source:return source_contract(source)


def initialize(toast):
    guard(2*1024**3)
    with connect(SOURCE,True) as source:
        contract=source_contract(source)
        manifest={**contract,'schema':'daylight-compact-physical-copy/1','target':TARGET,
                  'toast_tuple_target':toast,'created_at':now()}
        manifest['marker']='daylight-d94-compact:'+hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
        with connect('postgres') as admin:
            if admin.execute('SELECT 1 FROM pg_database WHERE datname=%s',(TARGET,)).fetchone():raise ValueError('Existing target is never initialized/replaced')
            admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(TARGET)))
            admin.execute(sql.SQL('COMMENT ON DATABASE {} IS {}').format(sql.Identifier(TARGET),sql.Literal(manifest['marker'])))
        with connect(TARGET) as target:
            # Original migrations are unchanged; this is a separately recorded physical revision.
            import sys
            sys.path.insert(0,str(PACKAGE/'src'))
            from daylight_data.database import migrate
            migrate(target)
            with target.transaction():
                for name in CONTROL:
                    if name=='dl_review.active_release' and source.execute('SELECT count(*) AS n FROM dl_review.active_release').fetchone()['n']:
                        raise ValueError('Active release needs explicit migration review')
                    binary_copy(source,target,sql.SQL('SELECT * FROM {}').format(table_identifier(name)),name)
                target.execute((PACKAGE/'redesign/r1/schema.sql').read_text().replace('toast_tuple_target=512',f'toast_tuple_target={toast}'))
                sets=sorted({(v['derivation_id'],v['source_table']) for v in units()})
                if len(sets)!=315:raise ValueError('Source-set count differs')
                with target.cursor().copy('COPY dl_compact.source_set FROM STDIN') as copy:
                    for number,(derivation,table) in enumerate(sets,1):copy.write_row((number,derivation,table))
                target.execute('INSERT INTO dl_compact.migration(singleton,manifest) VALUES(true,%s)',(psycopg.types.json.Jsonb(manifest),))
                target.execute('ANALYZE dl_compact.source_set')
        fresh_json(RUN/'compact-target.json',manifest)
    print(json.dumps({'initialized':TARGET,'toast_tuple_target':toast}),flush=True)


def ranges(derived,table,first,last):
    return (derived,table,first,last)


RAW_QUERY=sql.SQL('SELECT * FROM dl_evidence.source_record WHERE derivation_id=%s AND source_table=%s AND source_row_ordinal BETWEEN %s AND %s ORDER BY source_row_ordinal')
OBS_QUERY=sql.SQL('SELECT * FROM dl_evidence.observation WHERE derivation_id=%s AND source_table=%s AND source_row_ordinal BETWEEN %s AND %s ORDER BY source_row_ordinal,entity_type,entity_id')


def load_chunk(source,target,source_set,first,last):
    params=(source_set['derivation_id'],source_set['source_table'],first,last)
    with target.transaction(),monitor(target),source.transaction():
        source.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        target.execute('TRUNCATE dl_compact.stage_source,dl_compact.stage_observation')
        raw_hash,raw_bytes=binary_copy(source,target,RAW_QUERY,'dl_compact.stage_source',params)
        obs_hash,obs_bytes=binary_copy(source,target,OBS_QUERY,'dl_compact.stage_observation',params)
        raw_count=target.execute('SELECT count(*) AS n FROM dl_compact.stage_source').fetchone()['n']
        obs_count=target.execute('SELECT count(*) AS n FROM dl_compact.stage_observation').fetchone()['n']
        target.execute('''INSERT INTO dl_compact.symbol(value)
            SELECT value FROM (
              SELECT ordinal_basis AS value FROM dl_compact.stage_source UNION SELECT disposition FROM dl_compact.stage_source
              UNION SELECT entity_type FROM dl_compact.stage_observation UNION SELECT amount_unit FROM dl_compact.stage_observation
              UNION SELECT amount_basis FROM dl_compact.stage_observation UNION SELECT amount_period FROM dl_compact.stage_observation
            ) symbols_to_add WHERE value IS NOT NULL
              AND NOT EXISTS(SELECT 1 FROM dl_compact.symbol existing WHERE existing.value=symbols_to_add.value)
            ORDER BY value ON CONFLICT(value) DO NOTHING''')
        target.execute('''INSERT INTO dl_compact.evidence_state(value_state,evidence_state,semantic_review_state,source_use_state,freshness_state,output_acceptance_state)
            SELECT DISTINCT value_state,evidence_state,semantic_review_state,source_use_state,freshness_state,output_acceptance_state
            FROM dl_compact.stage_observation ON CONFLICT DO NOTHING''')
        target.execute('''INSERT INTO dl_compact.source_record
            SELECT %s,r.source_row_ordinal,decode(r.record_id,'hex'),r.source_row_key,b.symbol_id,
                   decode(r.raw_sha256,'hex'),r.raw_payload,d.symbol_id
            FROM dl_compact.stage_source r JOIN dl_compact.symbol b ON b.value=r.ordinal_basis
            JOIN dl_compact.symbol d ON d.value=r.disposition''',(source_set['source_set_id'],))
        target.execute('''INSERT INTO dl_compact.observation
            SELECT %s,o.source_row_ordinal,t.symbol_id,o.entity_id,o.offering_id,o.county_fips,o.benefit_year,
                   o.amount,u.symbol_id,b.symbol_id,p.symbol_id,o.raw_value,s.state_id,o.conditions,o.fields
            FROM dl_compact.stage_observation o
            JOIN dl_compact.symbol t ON t.value=o.entity_type
            JOIN dl_compact.evidence_state s USING(value_state,evidence_state,semantic_review_state,source_use_state,freshness_state,output_acceptance_state)
            LEFT JOIN dl_compact.symbol u ON u.value=o.amount_unit
            LEFT JOIN dl_compact.symbol b ON b.value=o.amount_basis
            LEFT JOIN dl_compact.symbol p ON p.value=o.amount_period''',(source_set['source_set_id'],))
        if binary_hash(target,RAW_QUERY,params)[0]!=raw_hash or binary_hash(target,OBS_QUERY,params)[0]!=obs_hash:
            raise ValueError('Lossless binary logical-column parity failed; whole chunk rolled back')
        target.execute('INSERT INTO dl_compact.load_checkpoint(source_set_id,first_ordinal,last_ordinal,raw_rows,projection_rows,raw_binary_sha256,projection_binary_sha256) VALUES(%s,%s,%s,%s,%s,%s,%s)',
            (source_set['source_set_id'],first,last,raw_count,obs_count,raw_hash,obs_hash))
        target.execute('TRUNCATE dl_compact.stage_source,dl_compact.stage_observation')
    return {'raw_rows':raw_count,'projection_rows':obs_count,'raw_copy_bytes':raw_bytes,'projection_copy_bytes':obs_bytes}


def chunks_for_units(batch,pilot):
    result=[]
    for unit in units():
        if pilot:
            # One bounded first chunk for every source grain, covering all 15 layers.
            if any(v['derivation_id']==unit['derivation_id'] for v in result):continue
            last=min(unit['last'],unit['first']+pilot-1)
        else:last=unit['last']
        for first in range(unit['first'],last+1,batch):
            result.append({**unit,'first':first,'last':min(last,first+batch-1)})
    return result


def load(batch,pilot):
    manifest=json.loads((RUN/'compact-target.json').read_text())
    with connect(SOURCE,True) as source,connect(TARGET) as target:
        assert_target(target,manifest)
        sets={r['derivation_id']:r for r in target.execute('SELECT * FROM dl_compact.source_set').fetchall()}
        completed={(r['source_set_id'],r['first_ordinal'],r['last_ordinal']) for r in target.execute('SELECT * FROM dl_compact.load_checkpoint').fetchall()}
        # Pilot range boundaries become durable checkpoints. Full loading starts
        # after those exact prefixes rather than copying them a second time.
        for unit in chunks_for_units(batch,pilot):
            source_set=sets[unit['derivation_id']]
            existing=target.execute('SELECT first_ordinal,last_ordinal FROM dl_compact.load_checkpoint WHERE source_set_id=%s AND first_ordinal<=%s AND last_ordinal>=%s ORDER BY first_ordinal',
                (source_set['source_set_id'],unit['last'],unit['first'])).fetchall()
            gaps=[(unit['first'],unit['last'])]
            for old in existing:
                gaps=[part for a,b in gaps for part in ((a,min(b,old['first_ordinal']-1)),(max(a,old['last_ordinal']+1),b)) if part[0]<=part[1]]
            for first,last in gaps:
                start=time.monotonic();result=load_chunk(source,target,source_set,first,last)
                with (RUN/'load-journal.jsonl').open('a') as f:
                    json.dump({'at':now(),'source_set':source_set['source_set_id'],'layer':unit['layer'],'first':first,'last':last,**result,'seconds':time.monotonic()-start,'free_bytes':guard()},f);f.write('\n');f.flush();os.fsync(f.fileno())
                print(json.dumps({'set':source_set['source_set_id'],'layer':unit['layer'],**result,'seconds':round(time.monotonic()-start,3)}),flush=True)
        target.execute('ANALYZE dl_compact.source_record');target.execute('ANALYZE dl_compact.observation')
        counts=target.execute('SELECT sum(raw_rows) AS raw_rows,sum(projection_rows) AS projection_rows FROM dl_compact.load_checkpoint').fetchone()
        size=target.execute('SELECT pg_database_size(current_database()) AS bytes').fetchone()['bytes']
        report={'at':now(),'pilot':bool(pilot),'counts':counts,'database_bytes':size,'free_bytes':guard(),'new_acceptance':False}
        filename=('pilot-'+str(pilot) if pilot else 'full-load')+'.json';fresh_json(RUN/filename,report)
        print(json.dumps(report,default=str),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('init','load'))
    parser.add_argument('--toast',type=int,default=512,choices=(256,384,512,768))
    parser.add_argument('--batch',type=int,default=20000)
    parser.add_argument('--pilot',type=int,default=0)
    args=parser.parse_args()
    if not 100<=args.batch<=50000 or not 0<=args.pilot<=5000:raise ValueError('Explicit bounded batch/pilot required')
    RUN.mkdir(parents=True,exist_ok=True,mode=0o700)
    import fcntl
    with (RUN/'LOCK').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.action=='init':initialize(args.toast)
        else:load(args.batch,args.pilot)


if __name__=='__main__':main()
