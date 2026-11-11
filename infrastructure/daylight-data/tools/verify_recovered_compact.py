"""Read-only recovery verification without any original/working database.

Use a trusted retained recovery receipt and a freshly restored compact database.
The receipt seals metadata and the original per-chunk hashes inside the archive.
This command grants no source permission and changes no serving binding.
"""
import argparse
import json
from pathlib import Path
import time

from psycopg import sql

import compact_recovery as r

c=r.c


def verify(database,expected):
    if not expected.get('passed') or not expected.get('full_integrated_restore') or not expected.get('every_logical_column_rehashed'):
        raise ValueError('Trusted complete recovery receipt required')
    started=time.monotonic();checked=0
    with c.connect(database,True) as db:
        if r.count_rows(db)!=expected['counts']:raise ValueError('Recovered population differs')
        for table,fingerprint in expected['metadata_sha256'].items():
            if r.metadata_hash(db,table)!=fingerprint:raise ValueError('Recovered metadata differs: '+table)
        if db.execute('SELECT count(*) AS n FROM pg_constraint WHERE NOT convalidated').fetchone()['n']:
            raise ValueError('Unvalidated recovered constraints')
        if db.execute('SELECT count(*) AS n FROM pg_index WHERE NOT indisvalid OR NOT indisready').fetchone()['n']:
            raise ValueError('Invalid recovered indexes')
        ranges=db.execute('''SELECT c.*,s.derivation_id,s.source_table FROM dl_compact.load_checkpoint c
            JOIN dl_compact.source_set s USING(source_set_id) ORDER BY source_set_id,first_ordinal''').fetchall()
        for row in ranges:
            params=(row['derivation_id'],row['source_table'],row['first_ordinal'],row['last_ordinal'])
            if (r.packed_raw_hash(db,params)[0]!=row['raw_binary_sha256']
                or c.binary_hash(db,c.OBS_QUERY,params)[0]!=row['projection_binary_sha256']):
                raise ValueError('Recovered logical column differs from original hash')
            checked+=1
            if checked%25==0:print(json.dumps({'verified_chunks':checked,'total':len(ranges)}),flush=True)
        if checked!=expected['verified_chunks']:raise ValueError('Recovered checkpoint coverage differs')
        offering=sql.SQL('SELECT * FROM dl_evidence.offering ORDER BY derivation_id,offering_id')
        if c.binary_hash(db,offering)[0]!=expected['offering_binary_sha256']:raise ValueError('Recovered offerings differ')
        with db.transaction():
            db.execute('SET LOCAL ROLE daylight_released_reader')
            if db.execute('SELECT count(*) AS n FROM dl_released.offerings').fetchone()['n']!=0:raise ValueError('Consumer hold lost')
    return {'passed':True,'database':database,'counts':expected['counts'],'verified_chunks':checked,
        'every_logical_column_matches_original_hashes':True,'original_database_required':False,
        'consumer_authority':'held','new_acceptance':False,'seconds':time.monotonic()-started,'at':c.now()}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database',required=True);p.add_argument('--receipt',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    args=p.parse_args()
    if args.output.exists():raise ValueError('Existing verification output preserved')
    result=verify(args.database,json.loads(args.receipt.read_text()));result['receipt_sha256']=c.hashfile(args.receipt)
    c.fresh_json(args.output,result);print(json.dumps(result),flush=True)
