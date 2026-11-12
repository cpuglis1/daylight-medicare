"""Check old sources/customer rows/AI charges without printing private values."""
from pathlib import Path
import collections
from datetime import date,timedelta
import hashlib
import json
import sqlite3

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
source=json.loads((HERE/'protected-source-before.json').read_text())
changed=[r['path'] for r in source if not (ROOT/r['path']).is_file() or hashlib.sha256((ROOT/r['path']).read_bytes()).hexdigest()!=r['sha256']]
stores=[];charges=[]
for before in json.loads((HERE/'stores-before.json').read_text()):
    path=Path(before['path']);db=sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True)
    missing={};counts={};operational=[]
    for table,hashes in before['tables'].items():
        safe=table.replace('"','""');rows=db.execute('SELECT * FROM "'+safe+'"').fetchall()
        after=collections.Counter(hashlib.sha256(repr(row).encode()).hexdigest() for row in rows)
        lost=collections.Counter(hashes)-after
        # The existing budget guard advances its latest UTC day; it must not
        # reset or rewrite charges. Prove this is exactly that allowed change.
        if table=='ai_meta' and lost:
            clock=db.execute("SELECT key,value FROM ai_meta WHERE key='latest_day'").fetchone()
            if clock:
                current=date.fromisoformat(clock[1])
                for n in range(32):
                    earlier=(current-timedelta(days=n)).isoformat()
                    digest=hashlib.sha256(repr(('latest_day',earlier)).encode()).hexdigest()
                    if lost[digest]:
                        lost.subtract({digest:1});lost=+lost
                        operational.append({'table':'ai_meta','key':'latest_day','before':earlier,'after':clock[1]})
                        break
        if lost:missing[table]=sum(lost.values())
        counts[table]={'before':len(hashes),'after':len(rows)}
        if table=='ai_charges':
            cols=[r[1] for r in db.execute('PRAGMA table_info(ai_charges)')]
            for row in rows:
                if hashlib.sha256(repr(row).encode()).hexdigest() not in set(hashes):
                    value=dict(zip(cols,row));charges.append({k:value.get(k) for k in ['day','status','charged','input_tokens','output_tokens']})
    db.close()
    stores.append({'path':str(path),'inode_preserved':path.stat().st_ino==before['inode'],
        'missing_or_changed_old_rows':missing,'counts':counts,'allowed_operational_changes':operational})
result={'protected_source_files':len(source),'changed_protected_source_files':changed,'stores':stores,
    'new_ai_charges':charges,'new_ai_estimated_usd':sum(x['charged'] or 0 for x in charges)/1_000_000_000}
(HERE/'preservation.json').write_text(json.dumps(result,indent=2)+'\n')
assert not changed and all(s['inode_preserved'] and not s['missing_or_changed_old_rows'] for s in stores)
assert all(c['status']=='settled' for c in charges)
print(f"{len(source)} protected source files unchanged; old customer rows and AI charges preserved; {len(charges)} settled new charges, estimated ${result['new_ai_estimated_usd']:.6f}.")
