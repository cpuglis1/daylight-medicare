"""Full native restore within the local reserve, retiring recovered scratch data.

The original research DB is never changed. A complete archived table must match
every candidate column before its redundant candidate storage can be released.
The final recovery database contains all tables, indexes, constraints and views.
"""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import time

from psycopg import sql

import compact_recovery as r
from compact_process import environment, reserve_watch

c=r.c
BIG=('observation','source_record','source_page')


def table_hash(db,table):
    # Sort only fixed-width SHA256 values, preserving duplicate multiplicity.
    # record_send includes every column's type, nullness and binary value.
    query=sql.SQL('SELECT sha256(record_send(t)) FROM {} t ORDER BY 1').format(c.table_identifier(table))
    with c.monitor(db):
        digest,size=c.binary_hash(db,query)
    if (size-21)%38:raise ValueError('Unexpected single bytea-column binary COPY framing')
    return {'sha256':digest,'rows':(size-21)//38,'binary_bytes':size}


def restore_part(archive,name,args):
    label='daylight-d94-bounded-'+name
    started=time.monotonic();minimum=c.guard()
    with (c.RUN/('bounded-'+name+'.stderr')).open('xb') as err:
        proc=subprocess.Popen([str(c.PACKAGE/'.postgres18/bin/pg_restore'),'--exit-on-error','--no-owner',
            '--dbname='+c.dsn(r.RESTORED),*args],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,
            stderr=err,env=environment(label))
        try:
            with reserve_watch(c,proc,r.RESTORED,label):
                with gzip.open(archive,'rb') as incoming:
                    while block:=incoming.read(1024**2):
                        minimum=min(minimum,c.guard(256*1024**2))
                        try:proc.stdin.write(block)
                        except BrokenPipeError:break  # A section can finish before the archive ends.
                try:proc.stdin.close()
                except BrokenPipeError:pass
                if proc.wait()!=0:raise RuntimeError('Bounded restore failed: '+name)
        finally:
            if proc.poll() is None:proc.terminate();proc.wait(timeout=10)
    result={'part':name,'passed':True,'seconds':time.monotonic()-started,'minimum_free_bytes':minimum}
    c.fresh_json(c.RUN/('bounded-'+name+'.json'),result);print(json.dumps(result),flush=True)


def make_toc(archive):
    prefix=c.RUN/'bounded-toc-prefix.tmp'
    try:
        with gzip.open(archive,'rb') as incoming,prefix.open('xb') as out:out.write(incoming.read(8*1024**2))
        listing=subprocess.run([str(c.PACKAGE/'.postgres18/bin/pg_restore'),'--list',str(prefix)],check=True,capture_output=True,text=True).stdout
        (c.RUN/'bounded-toc.txt').write_text(listing)
    finally:prefix.unlink(missing_ok=True)
    if any('BLOB' in line and not line.startswith(';') for line in listing.splitlines()):raise ValueError('Unexpected large objects need explicit restore accounting')
    selected=[];excluded=[]
    for line in listing.splitlines():
        if any(' TABLE DATA dl_compact '+name+' ' in line for name in BIG):excluded.append(line)
        else:selected.append(line)
    if len(excluded)!=len(BIG):raise ValueError('Exact three large-table archive inventory required')
    path=c.RUN/'bounded-small-data.list';path.write_text('\n'.join(selected)+'\n');return path


def verify_tables(original,recovered,names):
    result={}
    for name in names:
        table='dl_compact.'+name
        expected=table_hash(original,table);actual=table_hash(recovered,table)
        if expected!=actual:raise ValueError('Recovered complete table differs: '+table)
        result[name]=expected
        c.fresh_json(c.RUN/('bounded-verified-'+name+'.json'),{'table':table,'passed':True,**expected})
        print(json.dumps({'table':table,'all_columns_recovered':True,'rows':expected['rows']}),flush=True)
    return result


def retire_temporary_tables(original,names,proof,manifest,first=False):
    for name in names:
        if not proof.get(name):raise ValueError('Full matching table recovery proof required')
    marker=manifest['marker']+':verified-scratch-retirement'
    with original.transaction():
        # Invalidate the old loader's ownership marker before any retirement.
        # It cannot resume against this intentionally emptied working copy.
        if first:original.execute(sql.SQL('COMMENT ON DATABASE {} IS {}').format(sql.Identifier(c.TARGET),sql.Literal(marker)))
        original.execute(sql.SQL('TRUNCATE {}').format(sql.SQL(',').join(c.table_identifier('dl_compact.'+name) for name in names)))
    result={'passed':True,'temporary_tables':names,'proof':proof,'marker':marker,
        'original_research_database_untouched':True,'at':c.now()}
    c.fresh_json(c.RUN/('bounded-retired-'+names[0]+'.json'),result)
    print(json.dumps({'verified_temporary_storage_released':names,'free_bytes':c.guard()}),flush=True)


def restore():
    backup=json.loads((c.RUN/'backup.json').read_text());archive=Path(backup['archive'])
    if not backup.get('native_decode_and_gzip_crc_verified') or c.hashfile(archive)!=backup['sha256']:
        raise ValueError('Complete verified archive required')
    manifest=json.loads((c.RUN/'compact-target.json').read_text())
    started=time.monotonic();marker='daylight-d94-recovery:'+backup['sha256']
    with c.connect(c.SOURCE,True) as source:c.source_contract(source)
    with c.connect(c.TARGET) as original:c.assert_target(original,manifest)
    # Largest data heap plus bounded digest-sort/workspace; full indexes are
    # built after their redundant candidate tables have been verified/freed.
    with c.connect(c.TARGET,True) as original:
        largest=original.execute("SELECT pg_table_size('dl_compact.observation') AS n").fetchone()['n']
    c.guard(largest+2*1024**3)
    with c.connect('postgres') as admin:
        if admin.execute('SELECT 1 FROM pg_database WHERE datname=%s',(r.RESTORED,)).fetchone():raise ValueError('Existing recovery target preserved')
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(r.RESTORED)))
        admin.execute(sql.SQL('COMMENT ON DATABASE {} IS {}').format(sql.Identifier(r.RESTORED),sql.Literal(marker)))
    c.fresh_json(c.RUN/'restore-target.json',{'database':r.RESTORED,'marker':marker,'backup_sha256':backup['sha256'],'at':c.now(),'strategy':'whole-table-verified-scratch-retirement'})
    toc=make_toc(archive)
    restore_part(archive,'pre-data',['--section=pre-data'])
    restore_part(archive,'small-data',['--section=data','--use-list='+str(toc)])
    restore_part(archive,'observation',['--data-only','--schema=dl_compact','--table=observation'])
    with c.connect(c.TARGET) as original,c.connect(r.RESTORED,True) as recovered:
        original.execute("SET statement_timeout='1800s'");recovered.execute("SET statement_timeout='1800s'")
        proof=verify_tables(original,recovered,['observation'])
        retire_temporary_tables(original,['observation'],proof,manifest,True)
    for name in ('source_record','source_page'):
        restore_part(archive,name,['--data-only','--schema=dl_compact','--table='+name])
    with c.connect(c.TARGET) as original,c.connect(r.RESTORED,True) as recovered:
        original.execute("SET statement_timeout='1800s'");recovered.execute("SET statement_timeout='1800s'")
        proof=verify_tables(original,recovered,['source_record','source_page','offering'])
        # PostgreSQL requires empty FK dependents in the same TRUNCATE command.
        # Each complete table has already been recovered and verified above.
        proof['observation']=json.loads((c.RUN/'bounded-verified-observation.json').read_text())
        retire_temporary_tables(original,['source_record','source_page','offering','observation'],proof,manifest)
    restore_part(archive,'post-data',['--section=post-data'])
    r.analyze_compact(r.RESTORED)
    with c.connect(r.RESTORED,True) as recovered:
        invalid=recovered.execute("SELECT count(*) AS n FROM pg_index WHERE NOT indisvalid OR NOT indisready").fetchone()['n']
        pending=recovered.execute("SELECT count(*) AS n FROM pg_constraint WHERE NOT convalidated").fetchone()['n']
        if invalid or pending:raise ValueError('Restored constraints/indexes incomplete')
    result={'passed':True,'database':r.RESTORED,'seconds':time.monotonic()-started,
        'backup_sha256':backup['sha256'],'strategy':'whole-table-verified-scratch-retirement',
        'all_post_data_restored':True,'original_research_database_untouched':True}
    c.fresh_json(c.RUN/'restore-loaded.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':restore()
