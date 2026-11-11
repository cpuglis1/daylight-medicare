"""Rehash every file referenced by the frozen original research snapshots."""
import json
from pathlib import Path
import time

import compact_database_r2 as c


if __name__=='__main__':
    started=time.monotonic();checked=[]
    with c.connect(c.SOURCE,True) as db:
        c.source_contract(db)
        rows=db.execute('''SELECT DISTINCT s.original_path,s.artifact_sha256,a.byte_length AS size_bytes
            FROM dl_control.source_snapshot s JOIN dl_control.artifact a
            ON a.sha256=s.artifact_sha256 ORDER BY s.original_path''').fetchall()
    for row in rows:
        path=Path(row['original_path'])
        if not path.is_absolute():path=c.ROOT/path
        if not path.is_file() or path.stat().st_size!=row['size_bytes'] or c.hashfile(path)!=row['artifact_sha256']:
            raise ValueError('Retained original artifact differs: '+row['original_path'])
        checked.append(row)
    result={'passed':True,'files':len(checked),'bytes':sum(x['size_bytes'] for x in checked),
        'all_retained_artifact_bytes_match_frozen_controls':True,'checked':checked,
        'seconds':time.monotonic()-started,'at':c.now()}
    c.fresh_json(c.RUN/'retained-artifact-parity.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='checked'}),flush=True)
