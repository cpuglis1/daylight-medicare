"""Native concurrent primary-index recovery/repacking; never changes key meaning."""
import importlib.util
import json
from pathlib import Path
import time
from psycopg import sql

SPEC=importlib.util.spec_from_file_location('index_r1',Path(__file__).with_name('redesign_research_indexes.py'))
m=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(m)
c=m.c

if __name__=='__main__':
    with c.connect(c.SOURCE) as db:
        c.source_contract(db);db.execute("SET statement_timeout='30min'")
        for name in ('source_record_pkey','observation_pkey'):
            before=m.index_info(db,name)
            if not before or not before['indisprimary'] or not before['indisunique'] or not before['constraint_backed']:
                raise ValueError('Exact original primary index required')
            c.fresh_json(m.RUN/(name+'-repack-start.json'),before)
            start=time.monotonic()
            # PostgreSQL validates the replacement before its own atomic swap
            # and old-index retirement. Foreign-key/key semantics are unchanged.
            with c.monitor(db):db.execute(sql.SQL('REINDEX INDEX CONCURRENTLY {}').format(sql.Identifier('dl_evidence',name)))
            after=m.index_info(db,name)
            if (not after['indisvalid'] or not after['indisready'] or not after['indisprimary']
                or not after['indisunique'] or before['definition']!=after['definition']):
                raise ValueError('Primary-index recovery validation differs')
            result={'passed':True,'before':before,'after':after,'net_relation_bytes_saved':before['bytes']-after['bytes'],
                    'seconds':time.monotonic()-start,'source_values_changed':False,'key_definition_changed':False}
            c.fresh_json(m.RUN/(name+'-repack-complete.json'),result)
            print(json.dumps({'index':name,'saved':result['net_relation_bytes_saved'],'seconds':result['seconds']}),flush=True)
