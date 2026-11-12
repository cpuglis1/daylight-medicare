"""Preserve legacy record-ID equality inspection on the compact source view.

Run on the staged original database before cutover. The expression matches the
view's public text ID; full concurrent rebuild proves index recovery.
"""
import importlib.util
import json
from pathlib import Path
import time

SPEC=importlib.util.spec_from_file_location('compact_r2',Path(__file__).with_name('compact_database_r2.py'))
c=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(c)


def info(db):
    return db.execute('''SELECT c.oid,pg_get_indexdef(c.oid) AS definition,pg_relation_size(c.oid) AS bytes,
        i.indisvalid,i.indisready FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        JOIN pg_index i ON i.indexrelid=c.oid WHERE n.nspname='dl_compact' AND c.relname='compact_source_identity' ''').fetchone()


if __name__=='__main__':
    with c.connect(c.SOURCE) as db:
        c.source_contract(db);db.execute("SET lock_timeout='30s'");db.execute("SET statement_timeout='30min'")
        if not db.execute("SELECT 1 FROM pg_namespace WHERE nspname='dl_compact_check'").fetchone():raise ValueError('Staged compact schema required')
        if info(db):raise ValueError('Existing identity index preserved')
        started=time.monotonic()
        with c.monitor(db):db.execute("CREATE INDEX CONCURRENTLY compact_source_identity ON dl_compact.source_record USING hash ((encode(record_hash,'hex')))")
        before=info(db)
        with c.monitor(db):db.execute('REINDEX INDEX CONCURRENTLY dl_compact.compact_source_identity')
        after=info(db)
        if not after['indisvalid'] or not after['indisready'] or after['definition']!=before['definition'] or after['oid']==before['oid']:
            raise ValueError('Compact source-identity recovery failed')
        db.execute('ANALYZE dl_compact.source_record')
        key=json.loads((c.RUN/'record-identity-plan-before.json').read_text())['record_id']
        old_query="SELECT * FROM dl_evidence.source_record WHERE record_id=%s ORDER BY derivation_id,source_table,source_row_ordinal"
        new_query=old_query.replace('dl_evidence.','dl_compact_check.')
        from psycopg import sql
        if c.binary_hash(db,sql.SQL(old_query),(key,))!=c.binary_hash(db,sql.SQL(new_query),(key,)):
            raise ValueError('Legacy/compact record-ID lookup differs')
        plan=db.execute('EXPLAIN (FORMAT JSON) '+new_query,(key,)).fetchone()['QUERY PLAN']
        if 'compact_source_identity' not in json.dumps(plan):raise ValueError('Identity expression index not used')
        result={'passed':True,'created':before,'recovered':after,'exact_record_id_binary_parity':True,
                'query_plan':plan,'seconds':time.monotonic()-started,'source_values_changed':False,
                'recovery_ddl':"CREATE INDEX compact_source_identity ON dl_compact.source_record USING hash ((encode(record_hash,'hex')))",
                'operator_sha256':c.hashfile(Path(__file__))}
        c.fresh_json(c.RUN/'compact-identity-index-recovery.json',result)
        print(json.dumps({'passed':True,'index_bytes':after['bytes'],'seconds':result['seconds']}),flush=True)
