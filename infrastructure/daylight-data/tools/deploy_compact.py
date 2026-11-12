"""Recover-first deployment preserving the original database identity/read API.

The old tables remain available for atomic rollback until all live checks pass.
Only a verified redundant working copy or legacy table can be retired.
"""
import argparse
import gzip
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import time

from psycopg import sql
from psycopg.types.json import Jsonb
sys.path.insert(0,str(Path(__file__).parent))
from compact_range import raw_hash as packed_raw_hash
from compact_process import environment, reserve_watch

SPEC=importlib.util.spec_from_file_location('recovery',Path(__file__).with_name('compact_recovery.py'))
r=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(r)
c=r.c
LEGACY='dl_legacy_d94'
CHECK='dl_compact_check'


def gate():
    result=json.loads((c.RUN/'recovery-verified.json').read_text())
    backup=json.loads((c.RUN/'backup.json').read_text())
    if (not result.get('passed') or result.get('full_integrated_restore') is not True
        or result.get('every_logical_column_rehashed') is not True
        or result['backup_sha256']!=backup['sha256']
        or c.hashfile(Path(backup['archive']))!=backup['sha256']):raise ValueError('Exact full recovery proof required')
    return result,backup


def views(schema):
    source=(c.PACKAGE/'redesign/r2/schema.sql').read_text()
    matches=re.findall(r'CREATE VIEW dl_evidence\.(source_record|observation|offering) AS\n(.*?);',source,re.S)
    if len(matches)!=3:raise ValueError('Compatibility view inventory differs')
    overlay=(c.PACKAGE/'redesign/r3/read_views.sql').read_text()
    overrides=dict(re.findall(r'CREATE OR REPLACE VIEW dl_evidence\.(source_record) AS\n(.*?);',overlay,re.S))
    if set(overrides)!={'source_record'}:raise ValueError('Read adapter inventory differs')
    matches=[(name,overrides.get(name,body)) for name,body in matches]
    return [sql.SQL('CREATE VIEW {}.{} AS '+body).format(sql.Identifier(schema),sql.Identifier(name)) for name,body in matches]


def cleanup_working():
    recovered,backup=gate()
    manifest=json.loads((c.RUN/'compact-target.json').read_text())
    restored=json.loads((c.RUN/'restore-target.json').read_text())
    candidate_marker=manifest['marker']
    if (c.RUN/'bounded-retired-observation.json').exists():
        candidate_marker=json.loads((c.RUN/'bounded-retired-observation.json').read_text())['marker']
    with c.connect(c.SOURCE,True) as source:
        c.source_contract(source)
        # Keep the complete original dataset active while retiring these tested
        # duplicates. The verified archive remains, with its hash checked above.
        if source.execute("SELECT relkind FROM pg_class WHERE oid='dl_evidence.source_record'::regclass").fetchone()['relkind']!='r':
            raise ValueError('Original active source table must still be intact')
    results=[]
    with c.connect('postgres') as admin:
        for name,marker in ((c.TARGET,candidate_marker),(r.RESTORED,restored['marker'])):
            info=admin.execute("SELECT oid,shobj_description(oid,'pg_database') AS marker,pg_database_size(oid) AS bytes FROM pg_database WHERE datname=%s",(name,)).fetchone()
            if not info or info['marker']!=marker:raise ValueError('Exact owned duplicate database required')
            clients=admin.execute("SELECT count(*) AS n FROM pg_stat_activity WHERE datname=%s AND backend_type='client backend'",(name,)).fetchone()['n']
            if clients:raise ValueError('Working copy still has clients; no forced drop')
            c.fresh_json(c.RUN/(name+'-retirement-start.json'),{'database':name,**info,'recovery_sha256':c.hashfile(c.RUN/'recovery-verified.json')})
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
            results.append({'database':name,'bytes':info['bytes'],'verified_duplicate_retired':True})
    c.fresh_json(c.RUN/'working-copies-retired.json',{'passed':True,'retired':results,'original_source_retained':True,'backup_sha256':backup['sha256']})
    print(json.dumps(results),flush=True)


def stage_selection(archive,destination):
    # pg_restore's namespace filter can omit the SCHEMA creation entry (whose
    # archive namespace is '-'). Select its exact TOC entries including ACLs.
    prefix=destination.with_suffix('.prefix')
    try:
        with gzip.open(archive,'rb') as incoming,prefix.open('xb') as out:out.write(incoming.read(8*1024**2))
        listing=subprocess.run([str(c.PACKAGE/'.postgres18/bin/pg_restore'),'--list',str(prefix)],capture_output=True,text=True,check=True).stdout
    finally:prefix.unlink(missing_ok=True)
    selected=[line for line in listing.splitlines() if not line.startswith(';') and ' dl_compact ' in line]
    if sum(' SCHEMA - dl_compact ' in line for line in selected)!=1:raise ValueError('Exact compact schema creation required')
    for name in ('source_record','source_page','observation','offering'):
        if sum(' TABLE DATA dl_compact '+name+' ' in line for line in selected)!=1:raise ValueError('Exact compact table archive data required')
    with destination.open('x') as out:out.write('\n'.join(selected)+'\n')
    destination.chmod(0o600)
    return destination


def stage():
    recovered,backup=gate();archive=Path(backup['archive'])
    with c.connect(c.SOURCE) as source:
        c.source_contract(source)
        if source.execute("SELECT 1 FROM pg_namespace WHERE nspname='dl_compact'").fetchone():raise ValueError('Existing compact schema preserved')
    complete=json.loads((c.RUN/'complete.json').read_text())
    c.guard(complete['database_bytes']+2*1024**3)
    selection=stage_selection(archive,c.RUN/'stage-selected.list')
    started=time.monotonic();minimum=c.guard()
    with (c.RUN/'stage-restore.stderr').open('xb') as err:
        # An error rolls back the complete new schema; existing evidence tables
        # and control schemas are outside this restore selection.
        label='daylight-d94-stage-restore'
        process=subprocess.Popen([str(c.PACKAGE/'.postgres18/bin/pg_restore'),'--single-transaction',
            '--exit-on-error','--no-owner','--use-list='+str(selection),'--dbname='+c.dsn(c.SOURCE)],
            stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=err,env=environment(label))
        try:
            with reserve_watch(c,process,c.SOURCE,label):
                with gzip.open(archive,'rb') as incoming:
                    while block:=incoming.read(1024**2):
                        minimum=min(minimum,c.guard(256*1024**2))
                        try:process.stdin.write(block)
                        except BrokenPipeError:break
                try:process.stdin.close()
                except BrokenPipeError:pass
                if process.wait()!=0:raise RuntimeError('Stage restore failed; original tables remain active')
        finally:
            if process.poll() is None:process.terminate();process.wait(timeout=10)
    with c.connect(c.SOURCE) as source,source.transaction():
        source.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(CHECK)))
        source.execute(sql.SQL('REVOKE ALL ON SCHEMA {} FROM PUBLIC').format(sql.Identifier(CHECK)))
        for definition in views(CHECK):source.execute(definition)
    r.analyze_compact(c.SOURCE)
    c.fresh_json(c.RUN/'stage-loaded.json',{'passed':True,'backup_sha256':backup['sha256'],
        'minimum_free_bytes':minimum,'seconds':time.monotonic()-started,'original_evidence_tables_active':True})
    print(json.dumps({'stage_loaded':True,'seconds':time.monotonic()-started}),flush=True)


def check_query(query,db):
    return sql.SQL(query.as_string(db).replace('dl_evidence.',CHECK+'.'))


def column_contract(db,schema,table):
    return db.execute('''SELECT attnum,attname,format_type(atttypid,atttypmod) AS type,attcollation
        FROM pg_attribute WHERE attrelid=%s::regclass AND attnum>0 AND NOT attisdropped ORDER BY attnum''',
        (schema+'.'+table,)).fetchall()


def verify_stage():
    recovery,_=gate();started=time.monotonic();checked=0
    with c.connect(c.SOURCE,True) as db:
        c.source_contract(db)
        for table in c.CONTROL+['dl_migrations.applied']:
            if r.metadata_hash(db,table)!=recovery['source_metadata_sha256'][table]:raise ValueError('Frozen controls changed after recovery')
        original_counts=db.execute('''SELECT (SELECT count(*) FROM dl_evidence.source_record) AS raw_rows,
            (SELECT count(*) FROM dl_evidence.observation) AS projection_rows,
            (SELECT count(*) FROM dl_evidence.offering) AS offerings''').fetchone()
        if original_counts!=recovery['counts']:raise ValueError('Frozen original population changed')
        for table in ('source_record','observation','offering'):
            if column_contract(db,'dl_evidence',table)!=column_contract(db,CHECK,table):
                raise ValueError('Logical column name/type/order/collation differs: '+table)
        ranges=db.execute('''SELECT c.*,s.derivation_id,s.source_table FROM dl_compact.load_checkpoint c
            JOIN dl_compact.source_set s USING(source_set_id) ORDER BY source_set_id,first_ordinal''').fetchall()
        if sum(x['raw_rows'] for x in ranges)!=17767179 or sum(x['projection_rows'] for x in ranges)!=17823148:
            raise ValueError('Staged checkpoint scope differs')
        with (c.RUN/'stage-parity.jsonl').open('x') as log:
            for row in ranges:
                params=(row['derivation_id'],row['source_table'],row['first_ordinal'],row['last_ordinal'])
                for query,key in ((c.RAW_QUERY,'raw_binary_sha256'),(c.OBS_QUERY,'projection_binary_sha256')):
                    # Original hashes were sealed by the source copy and matched
                    # in a full clean restore. Verify this new staged copy, with
                    # frozen live controls/counts checked above.
                    staged=packed_raw_hash(db,params) if key=='raw_binary_sha256' else c.binary_hash(db,check_query(query,db),params)
                    if staged[0]!=row[key]:raise ValueError('Staged logical column differs from original hash')
                checked+=1;log.write(json.dumps({'set':row['source_set_id'],'first':row['first_ordinal'],'passed':True})+'\n');log.flush()
                if checked%25==0:print(json.dumps({'stage_chunks_verified':checked,'total':len(ranges)}),flush=True)
        query=sql.SQL('SELECT * FROM dl_evidence.offering ORDER BY derivation_id,offering_id')
        if c.binary_hash(db,query)!=c.binary_hash(db,check_query(query,db)):raise ValueError('Staged offerings differ')
        count=db.execute('SELECT (SELECT count(*) FROM dl_compact.source_record) AS raw_rows,(SELECT count(*) FROM dl_compact.observation) AS projection_rows,(SELECT count(*) FROM dl_compact.offering) AS offerings').fetchone()
    c.fresh_json(c.RUN/'stage-verified.json',{'passed':True,'column_names_types_order_and_collations_equal':True,'every_staged_logical_column_matches_original_hashes':True,'frozen_live_controls_and_population_unchanged':True,
        'read_adapter_sha256':c.hashfile(c.PACKAGE/'redesign/r3/read_views.sql'),'operator_sha256':c.hashfile(Path(__file__)),
        'verified_chunks':checked,'counts':count,'seconds':time.monotonic()-started,'at':c.now()})


def cutover():
    gate();stage=json.loads((c.RUN/'stage-verified.json').read_text())
    if not stage.get('passed') or not stage.get('every_staged_logical_column_matches_original_hashes') or not stage.get('frozen_live_controls_and_population_unchanged'):
        raise ValueError('Complete staged parity required')
    if stage['read_adapter_sha256']!=c.hashfile(c.PACKAGE/'redesign/r3/read_views.sql') or stage['operator_sha256']!=c.hashfile(Path(__file__)):
        raise ValueError('Staged read adapter/operator changed')
    started=time.monotonic()
    with c.connect(c.SOURCE) as db,db.transaction():
        c.source_contract(db)
        db.execute('LOCK TABLE dl_evidence.source_record,dl_evidence.observation,dl_evidence.offering IN ACCESS EXCLUSIVE MODE NOWAIT')
        if db.execute('SELECT count(*) AS n FROM dl_review.active_release').fetchone()['n']:raise ValueError('Active consumer release requires separate migration review')
        db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(LEGACY)))
        db.execute(sql.SQL('REVOKE ALL ON SCHEMA {} FROM PUBLIC').format(sql.Identifier(LEGACY)))
        for name in ('offering','observation','source_record'):
            db.execute(sql.SQL('ALTER TABLE {} SET SCHEMA {}').format(sql.Identifier('dl_evidence',name),sql.Identifier(LEGACY)))
        for definition in views('dl_evidence'):db.execute(definition)
        db.execute('GRANT SELECT ON dl_evidence.source_record,dl_evidence.observation,dl_evidence.offering TO daylight_writer,daylight_validator,daylight_reviewer,daylight_research_reader')
        db.execute('''CREATE OR REPLACE VIEW dl_released.offerings WITH(security_barrier=true) AS
            SELECT offering_id,benefit_year,contract_id,plan_id,segment_id,plan_name,category FROM dl_evidence.offering WHERE false''')
        db.execute('CREATE TABLE dl_compact.cutover_receipt(singleton boolean PRIMARY KEY CHECK(singleton),receipt jsonb NOT NULL)')
        db.execute('INSERT INTO dl_compact.cutover_receipt VALUES(true,%s)',(Jsonb({'source_database_identity_retained':True,
            'recovery_sha256':c.hashfile(c.RUN/'recovery-verified.json'),'stage_sha256':c.hashfile(c.RUN/'stage-verified.json'),
            'operator_sha256':c.hashfile(Path(__file__)),'new_acceptance':False,'at':c.now()}),))
        db.execute('CREATE TRIGGER cutover_receipt_immutable BEFORE UPDATE OR DELETE ON dl_compact.cutover_receipt FOR EACH ROW EXECUTE FUNCTION dl_control.reject_mutation()')
    c.fresh_json(c.RUN/'cutover.json',{'passed':True,'seconds':time.monotonic()-started,'database':c.SOURCE,
        'original_tables_retained_for_rollback':True,'database_identity_and_source_control_unchanged':True,
        'new_acceptance':False,'at':c.now()})
    print(json.dumps({'cutover':True,'seconds':time.monotonic()-started}),flush=True)


def rollback():
    with c.connect(c.SOURCE) as db,db.transaction():
        for name in ('source_record','observation','offering'):
            if not db.execute('SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relname=%s',(LEGACY,name)).fetchone():raise ValueError('Rollback originals unavailable')
        db.execute('DROP VIEW dl_released.offerings')
        for name in ('offering','observation','source_record'):
            db.execute(sql.SQL('DROP VIEW {}').format(sql.Identifier('dl_evidence',name)))
        for name in ('source_record','observation','offering'):
            db.execute(sql.SQL('ALTER TABLE {} SET SCHEMA dl_evidence').format(sql.Identifier(LEGACY,name)))
        db.execute('''CREATE VIEW dl_released.offerings WITH(security_barrier=true) AS
            SELECT offering_id,benefit_year,contract_id,plan_id,segment_id,plan_name,category FROM dl_evidence.offering WHERE false''')
        db.execute('GRANT SELECT ON dl_released.offerings TO daylight_released_reader')
    c.fresh_json(c.RUN/'rollback.json',{'passed':True,'original_read_path_restored':True,'at':c.now()})


def retire_legacy():
    gate()
    live=json.loads((c.RUN/'live-serving-audit.json').read_text())
    cut=json.loads((c.RUN/'cutover.json').read_text())
    checks=json.loads((c.RUN/'live-final-checks.json').read_text())
    if (not cut.get('passed') or not live.get('passed') or live.get('plans')!=72
        or not checks.get('passed') or checks.get('counts')!={'raw_rows':17767179,'projection_rows':17823148,'offerings':5972}):
        raise ValueError('Live feature/count/permission validation required before legacy retirement')
    with c.connect(c.SOURCE) as db:
        c.source_contract(db)
        rows=db.execute('''SELECT c.relname,pg_total_relation_size(c.oid) AS bytes FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname=%s AND c.relkind='r' ORDER BY c.relname''',(LEGACY,)).fetchall()
        if {x['relname'] for x in rows}!={'source_record','observation','offering'}:raise ValueError('Exact redundant legacy table inventory required')
        before=db.execute('SELECT pg_database_size(current_database()) AS n').fetchone()['n']
        c.fresh_json(c.RUN/'legacy-retirement-start.json',{'legacy':rows,'database_bytes':before,
            'recovery_sha256':c.hashfile(c.RUN/'recovery-verified.json'),'live_checks_sha256':c.hashfile(c.RUN/'live-final-checks.json')})
        with db.transaction():
            db.execute(sql.SQL('DROP TABLE {},{},{}').format(sql.Identifier(LEGACY,'offering'),sql.Identifier(LEGACY,'observation'),sql.Identifier(LEGACY,'source_record')))
            db.execute(sql.SQL('DROP SCHEMA {}').format(sql.Identifier(LEGACY)))
        after=db.execute('SELECT pg_database_size(current_database()) AS n').fetchone()['n']
        result={'passed':True,'retired_redundant_legacy_tables':rows,'database_before':before,'database_after':after,
            'database_relation_bytes_reclaimed':before-after,'all_source_logical_rows_retained':True,
            'original_source_files_and_backups_retained':True,'at':c.now()}
        c.fresh_json(c.RUN/'legacy-retired.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('cleanup_working','stage','verify_stage','cutover','rollback','retire_legacy'))
    args=p.parse_args();globals()[args.action]()
