"""Full compact-database finalization, logical backup, clean restore and parity.

Only newly owned recovery targets are created. No source/candidate is dropped.
The external evidence archive remains at its original preserved paths.
"""
import argparse
from dataclasses import replace
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
sys.path.insert(0,str(Path(__file__).parent))
from compact_range import raw_hash as packed_raw_hash
from compact_process import environment, reserve_watch

SPEC=importlib.util.spec_from_file_location('compact_r2',Path(__file__).with_name('compact_database_r2.py'))
c=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(c)
RESTORED='daylight_compact_restore_2026_r2_test'


def count_rows(db):
    return db.execute('''SELECT (SELECT count(*) FROM dl_compact.source_record) AS raw_rows,
      (SELECT count(*) FROM dl_compact.observation) AS projection_rows,
      (SELECT count(*) FROM dl_compact.offering) AS offerings''').fetchone()


def analyze_compact(database):
    with c.connect(database) as db:
        for name in ('source_set','symbol','evidence_state','source_record','source_page','observation','offering'):
            db.execute(sql.SQL('ANALYZE {}').format(sql.Identifier('dl_compact',name)))


def finalize():
    manifest=json.loads((c.RUN/'compact-target.json').read_text())
    with c.connect(c.SOURCE,True) as source,c.connect(c.TARGET) as target:
        c.assert_target(target,manifest)
        if count_rows(target)['raw_rows']!=17767179 or count_rows(target)['projection_rows']!=17823148:
            raise ValueError('Full frozen source population must be loaded')
        with source.transaction(),target.transaction(),c.monitor(target):
            source.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            query=sql.SQL('SELECT * FROM dl_evidence.offering ORDER BY derivation_id,offering_id')
            expected_hash,_=c.binary_hash(source,query)
            if not count_rows(target)['offerings']:
                c.binary_copy(source,target,query,'dl_compact.stage_offering')
                target.execute('''INSERT INTO dl_compact.offering
                  SELECT s.source_set_id,o.offering_id,o.benefit_year,o.contract_id,o.plan_id,o.segment_id,
                    o.plan_name,o.category,o.source_row_ordinal,o.output_acceptance_state
                  FROM dl_compact.stage_offering o JOIN dl_compact.source_set s USING(derivation_id,source_table)''')
                target.execute('TRUNCATE dl_compact.stage_offering')
            if c.binary_hash(target,query)[0]!=expected_hash:raise ValueError('Offering parity differs')
            for table in c.CONTROL:
                if metadata_hash(source,table)!=metadata_hash(target,table):raise ValueError('Control metadata differs: '+table)
            source_sequence=source.execute('SELECT last_value,is_called FROM dl_control.job_job_id_seq').fetchone()
            target.execute("SELECT setval('dl_control.job_job_id_seq',%s,%s)",(source_sequence['last_value'],source_sequence['is_called']))
        for table in ('source_record','source_page','observation','offering'):
            target.execute(sql.SQL('ANALYZE {}').format(sql.Identifier('dl_compact',table)))
        counts=count_rows(target)
        if counts!={'raw_rows':17767179,'projection_rows':17823148,'offerings':5972}:raise ValueError('Full physical counts differ')
        checkpoints=target.execute('SELECT * FROM dl_compact.load_checkpoint ORDER BY source_set_id,first_ordinal').fetchall()
        if sum(x['raw_rows'] for x in checkpoints)!=17767179 or sum(x['projection_rows'] for x in checkpoints)!=17823148:
            raise ValueError('Checkpoint accounting differs')
        result={'schema':'daylight-compact-full-load/2','passed':True,'at':c.now(),'target':c.TARGET,
          'counts':counts,'checkpoints':len(checkpoints),'checkpoint_sha256':hashlib.sha256(json.dumps(checkpoints,sort_keys=True,default=str).encode()).hexdigest(),
          'database_bytes':target.execute('SELECT pg_database_size(current_database()) AS n').fetchone()['n'],
          'free_bytes':c.guard(),'manifest_sha256':c.hashfile(c.RUN/'compact-target.json'),
          'new_acceptance':False,'source_values_changed':False}
        c.fresh_json(c.RUN/'complete.json',result);print(json.dumps(result),flush=True)


def metadata_hash(db,table):
    ordering=db.execute('''SELECT string_agg(quote_ident(a.attname),',' ORDER BY k.ordinality) AS columns
        FROM pg_index i CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY k(attnum,ordinality)
        JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.attnum
        WHERE i.indrelid=%s::regclass AND i.indisprimary''',(table,)).fetchone()['columns']
    if not ordering:raise ValueError('Metadata table must have a primary key')
    query=sql.SQL('SELECT * FROM {} ORDER BY {}').format(c.table_identifier(table),sql.SQL(ordering))
    return c.binary_hash(db,query)[0]


def backup():
    complete=json.loads((c.RUN/'complete.json').read_text())
    if not complete['passed']:raise ValueError('Completed compact load required')
    archive=c.RUN/'compact-full.dump.gz';errors=c.RUN/'compact-dump.stderr'
    if archive.exists():raise ValueError('Existing backup never overwritten')
    env={k:os.environ[k] for k in ('PATH','TMPDIR') if k in os.environ}
    env['PGOPTIONS']='-c default_transaction_read_only=on'
    started=time.monotonic();minimum=c.guard();digest=hashlib.sha256()
    with archive.open('xb') as out,errors.open('xb') as err:
        archive.chmod(0o600)
        process=subprocess.Popen([str(c.PACKAGE/'.postgres18/bin/pg_dump'),'--format=custom','--compress=none',
            '--no-password','--lock-wait-timeout=10s','--dbname='+c.dsn(c.TARGET,True)],stdout=subprocess.PIPE,stderr=err,env=env)
        try:
            with gzip.GzipFile(fileobj=out,mode='wb',filename='',mtime=0,compresslevel=3) as gz:
                while block:=process.stdout.read(1024**2):
                    minimum=min(minimum,c.guard(256*1024**2));gz.write(block)
            if process.wait()!=0:raise RuntimeError('Compact pg_dump failed; private stderr retained')
            out.flush();os.fsync(out.fileno())
        finally:
            if process.poll() is None:process.terminate();process.wait(timeout=10)
            process.stdout.close()
    # Full gzip CRC and native custom-archive decoding are checked before restore.
    with (c.RUN/'compact-decode.stderr').open('xb') as err:
        decoder=subprocess.Popen([str(c.PACKAGE/'.postgres18/bin/pg_restore'),'--file=-'],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=err)
        try:
            with gzip.open(archive,'rb') as incoming:
                while block:=incoming.read(1024**2):decoder.stdin.write(block)
            decoder.stdin.close()
            if decoder.wait()!=0:raise RuntimeError('Compact backup decode failed')
        finally:
            if decoder.poll() is None:decoder.terminate();decoder.wait(timeout=10)
    receipt={'passed':True,'archive':str(archive),'sha256':c.hashfile(archive),'bytes':archive.stat().st_size,
      'native_decode_and_gzip_crc_verified':True,'clean_restore_executed':False,'off_machine_copy':False,
      'minimum_free_bytes':minimum,'seconds':time.monotonic()-started,
      'external_evidence_archive_included':False,'complete_sha256':c.hashfile(c.RUN/'complete.json')}
    c.fresh_json(c.RUN/'backup.json',receipt);print(json.dumps(receipt),flush=True)


def restore():
    receipt=json.loads((c.RUN/'backup.json').read_text());archive=Path(receipt['archive'])
    if c.hashfile(archive)!=receipt['sha256']:raise ValueError('Backup hash differs')
    complete=json.loads((c.RUN/'complete.json').read_text())
    c.guard(complete['database_bytes']+2*1024**3)
    marker='daylight-d94-recovery:'+receipt['sha256']
    with c.connect('postgres') as admin:
        if admin.execute('SELECT 1 FROM pg_database WHERE datname=%s',(RESTORED,)).fetchone():raise ValueError('Existing restore target preserved')
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(RESTORED)))
        admin.execute(sql.SQL('COMMENT ON DATABASE {} IS {}').format(sql.Identifier(RESTORED),sql.Literal(marker)))
    c.fresh_json(c.RUN/'restore-target.json',{'database':RESTORED,'marker':marker,'backup_sha256':receipt['sha256'],'at':c.now()})
    started=time.monotonic();minimum=c.guard()
    with (c.RUN/'restore.stderr').open('xb') as err:
        label='daylight-d94-clean-restore'
        process=subprocess.Popen([str(c.PACKAGE/'.postgres18/bin/pg_restore'),'--exit-on-error','--no-owner','--dbname='+c.dsn(RESTORED)],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=err,env=environment(label))
        try:
            with reserve_watch(c,process,RESTORED,label):
                with gzip.open(archive,'rb') as incoming:
                    while block:=incoming.read(1024**2):
                        minimum=min(minimum,c.guard(256*1024**2));process.stdin.write(block)
                process.stdin.close()
                if process.wait()!=0:raise RuntimeError('Clean compact restore failed; owned target retained')
        finally:
            if process.poll() is None:process.terminate();process.wait(timeout=10)
    analyze_compact(RESTORED)
    c.fresh_json(c.RUN/'restore-loaded.json',{'passed':True,'database':RESTORED,'minimum_free_bytes':minimum,
        'seconds':time.monotonic()-started,'backup_sha256':receipt['sha256']})
    print(json.dumps({'restore_loaded':True,'seconds':time.monotonic()-started}),flush=True)


def verify_restore():
    receipt=json.loads((c.RUN/'restore-loaded.json').read_text())
    if receipt['passed'] is not True:raise ValueError('Actual clean restore required')
    started=time.monotonic();checked=0;metadata={};source_metadata={}
    with c.connect(c.TARGET,True) as original,c.connect(RESTORED,True) as recovered:
        complete=json.loads((c.RUN/'complete.json').read_text())
        if complete['counts']!=count_rows(recovered):raise ValueError('Restored population differs')
        for table in c.CONTROL+['dl_migrations.applied','dl_compact.source_set','dl_compact.symbol','dl_compact.evidence_state','dl_compact.migration','dl_compact.load_checkpoint']:
            metadata[table]=metadata_hash(recovered,table)
            if metadata_hash(original,table)!=metadata[table]:raise ValueError('Restored metadata differs: '+table)
        for sequence in ('dl_control.job_job_id_seq','dl_compact.symbol_symbol_id_seq'):
            query=sql.SQL('SELECT last_value,is_called FROM {}').format(c.table_identifier(sequence))
            if original.execute(query).fetchone()!=recovered.execute(query).fetchone():raise ValueError('Restored sequence differs: '+sequence)
        ranges=original.execute('''SELECT c.*,s.derivation_id,s.source_table FROM dl_compact.load_checkpoint c
            JOIN dl_compact.source_set s USING(source_set_id) ORDER BY source_set_id,first_ordinal''').fetchall()
        with (c.RUN/'restore-parity.jsonl').open('x') as log:
            for row in ranges:
                params=(row['derivation_id'],row['source_table'],row['first_ordinal'],row['last_ordinal'])
                for query,key in ((c.RAW_QUERY,'raw_binary_sha256'),(c.OBS_QUERY,'projection_binary_sha256')):
                    observed=packed_raw_hash(recovered,params) if key=='raw_binary_sha256' else c.binary_hash(recovered,query,params)
                    if observed[0]!=row[key]:raise ValueError('Restored logical-column hash differs')
                checked+=1
                log.write(json.dumps({'set':row['source_set_id'],'first':row['first_ordinal'],'last':row['last_ordinal'],'passed':True})+'\n');log.flush()
                if checked%25==0:print(json.dumps({'restored_chunks_verified':checked,'total':len(ranges)}),flush=True)
        offering=sql.SQL('SELECT * FROM dl_evidence.offering ORDER BY derivation_id,offering_id')
        with c.connect(c.SOURCE,True) as source:
            c.source_contract(source)
            for table in c.CONTROL+['dl_migrations.applied']:
                source_metadata[table]=metadata_hash(source,table)
                if table in c.CONTROL and source_metadata[table]!=metadata[table]:raise ValueError('Live frozen metadata changed: '+table)
            # The independently initialized compact DB records its own schema
            # execution timestamps. Compare migration code identity separately;
            # staging leaves the original history, including its times, intact.
            migrations=sql.SQL('SELECT name,sha256 FROM dl_migrations.applied ORDER BY name')
            if c.binary_hash(source,migrations)!=c.binary_hash(recovered,migrations):raise ValueError('Migration code differs')
            if c.binary_hash(source,offering)!=c.binary_hash(recovered,offering):raise ValueError('Restored offerings differ')
        offering_hash=c.binary_hash(recovered,offering)[0]
        with recovered.transaction():
            recovered.execute('SET LOCAL ROLE daylight_released_reader')
            if recovered.execute('SELECT count(*) AS n FROM dl_released.offerings').fetchone()['n']!=0:raise ValueError('Consumer hold lost')
        counts=count_rows(recovered)
    # Exercise real retained research queries using an explicit test-only physical
    # binding; this does not change any live configuration or purpose authority.
    sys.path.insert(0,str(c.PACKAGE/'src'))
    from daylight_data.serving.binding import load_local_binding
    from daylight_data.serving.repository import ResearchPlanRepository
    spec=importlib.util.spec_from_file_location('serving_audit',Path(__file__).with_name('verify_research_serving.py'))
    audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
    binding=replace(load_local_binding(c.ROOT),database=RESTORED)
    repository=ResearchPlanRepository(lambda:c.connect(RESTORED,True),binding,timeout_ms=30000)
    audit_result=audit.verify(repository);c.fresh_json(c.RUN/'restored-serving-audit.json',audit_result)
    result={'schema':'daylight-compact-clean-recovery/2','passed':True,'database':RESTORED,'counts':counts,
       'every_logical_column_rehashed':True,'verified_chunks':checked,'full_integrated_restore':True,
       'serving_plans':audit_result['plans'],'consumer_authority':'held','new_acceptance':False,
       'off_machine_recovery':False,'seconds':time.monotonic()-started,
       'metadata_sha256':metadata,
       'source_metadata_sha256':source_metadata,
       'offering_binary_sha256':offering_hash,
       'backup_sha256':receipt['backup_sha256'],'at':c.now()}
    c.fresh_json(c.RUN/'recovery-verified.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('finalize','backup','restore','verify_restore'))
    args=p.parse_args();globals()[args.action]()
