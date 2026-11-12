"""D94 derived-index replacement, with a full rebuild recovery before retirement.

Only three named non-unique secondary indexes are eligible. Source tables,
primary/FK constraints, data, permissions and authority are never modified.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import time

from psycopg import sql

SPEC=importlib.util.spec_from_file_location('compact_r2',Path(__file__).with_name('compact_database_r2.py'))
c=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(c)
RUN=c.PACKAGE/'.state/maintenance/20261105-index-r1'
INDEXES={
 'observation_query':('d94_offering_lookup', 'CREATE INDEX CONCURRENTLY d94_offering_lookup ON dl_evidence.observation (derivation_id,entity_type,offering_id) WHERE offering_id IS NOT NULL'),
 'observation_source_lineage':('d94_source_lineage','CREATE INDEX CONCURRENTLY d94_source_lineage ON dl_evidence.observation (derivation_id,source_row_ordinal)'),
 'source_record_identity':('d94_record_identity','CREATE INDEX CONCURRENTLY d94_record_identity ON dl_evidence.source_record USING hash(record_id)'),
}


def index_info(db,name):
    return db.execute('''SELECT c.oid,c.relname,pg_get_indexdef(c.oid) AS definition,
      pg_relation_size(c.oid) AS bytes,i.indisvalid,i.indisready,i.indisunique,i.indisprimary,
      EXISTS(SELECT 1 FROM pg_constraint WHERE conindid=c.oid) AS constraint_backed
      FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_index i ON i.indexrelid=c.oid
      WHERE n.nspname='dl_evidence' AND c.relname=%s''',(name,)).fetchone()


def prepare():
    RUN.mkdir(parents=True,exist_ok=True,mode=0o700)
    with c.connect(c.SOURCE) as db:
        c.source_contract(db)
        db.execute("SET statement_timeout='30min'")
        originals={name:index_info(db,name) for name in INDEXES}
        if any(not v or v['indisunique'] or v['constraint_backed'] or v['indisprimary'] for v in originals.values()):
            raise ValueError('Only exact non-unique, non-constraint secondary indexes may be replaced')
        c.fresh_json(RUN/'original-indexes.json',originals)
        for old,(name,command) in INDEXES.items():
            if index_info(db,name):raise ValueError('Existing replacement requires explicit resume/review')
            started=time.monotonic()
            with c.monitor(db):db.execute(command)
            before=index_info(db,name)
            if not before or not before['indisvalid'] or not before['indisready']:raise ValueError('Replacement index invalid')
            # Actual full-source rebuild rehearses recovery while the old index
            # is still present. A failed rebuild cannot remove the old path.
            with c.monitor(db):db.execute(sql.SQL('REINDEX INDEX CONCURRENTLY {}').format(sql.Identifier('dl_evidence',name)))
            recovered=index_info(db,name)
            if (not recovered['indisvalid'] or not recovered['indisready'] or before['oid']==recovered['oid']
                    or before['definition']!=recovered['definition']):raise ValueError('Full index recovery differs')
            c.fresh_json(RUN/(name+'-recovery.json'),{'passed':True,'old_index':old,'created':before,'recovered':recovered,
                'source_rows_modified':False,'seconds':time.monotonic()-started})
            print(json.dumps({'index':name,'recovery_passed':True,'bytes':recovered['bytes'],'seconds':round(time.monotonic()-started,2)}),flush=True)
        c.fresh_json(RUN/'replacement-indexes-ready.json',{'passed':True,'source':c.source_contract(db),
            'operator_sha256':c.hashfile(Path(__file__)),'replacement_recovery_receipts':{
                old:c.hashfile(RUN/(name+'-recovery.json')) for old,(name,_) in INDEXES.items()},'new_acceptance':False})


def retire():
    gate=json.loads((RUN/'replacement-indexes-ready.json').read_text())
    if not gate['passed'] or gate['operator_sha256']!=c.hashfile(Path(__file__)):raise ValueError('Exact recovery gate required')
    originals=json.loads((RUN/'original-indexes.json').read_text())
    with c.connect(c.SOURCE) as db:
        if c.source_contract(db)!=gate['source']:raise ValueError('Source identity or compact code changed')
        db.execute("SET statement_timeout='30min'")
        for old,(name,_) in INDEXES.items():
            receipt=RUN/(name+'-recovery.json')
            if c.hashfile(receipt)!=gate['replacement_recovery_receipts'][old]:raise ValueError('Recovery receipt changed')
            current=index_info(db,old);ready=index_info(db,name)
            if (current!=originals[old] or not ready or not ready['indisvalid'] or not ready['indisready']
                    or current['constraint_backed'] or current['indisunique']):raise ValueError('Index changed since recovery')
            c.fresh_json(RUN/(old+'-retirement-start.json'),{'original':current,'replacement':ready,'at':c.now()})
            with c.monitor(db):db.execute(sql.SQL('DROP INDEX CONCURRENTLY {}').format(sql.Identifier('dl_evidence',old)))
            if index_info(db,old) is not None:raise ValueError('Retirement incomplete')
            print(json.dumps({'retired':old,'old_bytes':current['bytes'],'replacement_bytes':ready['bytes']}),flush=True)
        after={name:index_info(db,name) for name,_ in INDEXES.values()}
        c.fresh_json(RUN/'retirement-complete.json',{'passed':True,'originals':originals,'replacements':after,
            'net_relation_bytes_saved':sum(x['bytes'] for x in originals.values())-sum(x['bytes'] for x in after.values()),
            'source_rows_modified':False,'constraints_modified':False,'permissions_modified':False,
            'full_database_restore_claimed':False,'at':c.now()})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare','retire'))
    args=p.parse_args();globals()[args.action]()
