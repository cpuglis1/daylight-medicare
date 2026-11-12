#!/usr/bin/env python3
"""Additive, local-only indexed MVP snapshot; no runtime/release promotion.

Round-trips every input JSON value, stores content-addressed compressed objects,
and exposes exact plan/field/hold/family/question indexes. Historical family
coverage is labeled by its source revision rather than silently refreshed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import zlib

BASE = 'docs/product/recommendation-scope-2026-11-04-'
SOURCES = {
    'native': BASE+'r5/catalog.json',
    'families': BASE+'r9/offering-gaps.json',
    'medical': BASE+'r10/critical-benefits.json',
    'display': BASE+'r13/display-candidate.json',
    'questions': BASE+'r1/question-capability-map.json',
    'profile': 'infrastructure/daylight-data/config/profile-contract.2026.json',
}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def put(db, value):
    raw = canonical(value)
    key = sha(raw)
    db.execute('INSERT OR IGNORE INTO object VALUES(?,?)', (key, zlib.compress(raw, 9)))
    return key


def get(db, key):
    raw = zlib.decompress(db.execute('SELECT payload FROM object WHERE sha256=?', (key,)).fetchone()[0])
    if sha(raw) != key:
        raise ValueError('Snapshot object hash mismatch')
    return json.loads(raw)


def initialize(db):
    db.executescript('''
    PRAGMA foreign_keys=ON;
    CREATE TABLE object(sha256 TEXT PRIMARY KEY,payload BLOB NOT NULL) WITHOUT ROWID;
    CREATE TABLE artifact(name TEXT PRIMARY KEY,path TEXT NOT NULL,source_sha256 TEXT NOT NULL,
      metadata_object TEXT NOT NULL REFERENCES object,collection TEXT,kind TEXT) WITHOUT ROWID;
    CREATE TABLE member(artifact TEXT REFERENCES artifact,ordinal INTEGER,item_key TEXT,
      object TEXT REFERENCES object,PRIMARY KEY(artifact,ordinal)) WITHOUT ROWID;
    CREATE TABLE offering(offering_id TEXT PRIMARY KEY,year INTEGER CHECK(year=2026),
      name TEXT NOT NULL,plan_type TEXT NOT NULL,record_object TEXT REFERENCES object) WITHOUT ROWID;
    CREATE TABLE benefit(offering_id TEXT REFERENCES offering,field TEXT,state TEXT NOT NULL,
      object TEXT REFERENCES object,PRIMARY KEY(offering_id,field)) WITHOUT ROWID;
    CREATE TABLE scenario(offering_id TEXT REFERENCES offering,scenario TEXT,state TEXT NOT NULL,
      decimal_amount TEXT,unit TEXT,object TEXT REFERENCES object,
      PRIMARY KEY(offering_id,scenario)) WITHOUT ROWID;
    CREATE TABLE family(offering_id TEXT REFERENCES offering,family TEXT,
      source_revision TEXT NOT NULL,object TEXT REFERENCES object,
      PRIMARY KEY(offering_id,family)) WITHOUT ROWID;
    CREATE TABLE medical_service(offering_id TEXT REFERENCES offering,service TEXT,
      object TEXT REFERENCES object,PRIMARY KEY(offering_id,service)) WITHOUT ROWID;
    CREATE TABLE question(question_id TEXT PRIMARY KEY,object TEXT REFERENCES object) WITHOUT ROWID;
    CREATE TABLE operating_boundary(key TEXT PRIMARY KEY,value TEXT NOT NULL) WITHOUT ROWID;
    ''')
    db.executemany('INSERT INTO operating_boundary VALUES(?,?)', [
        ('mode', 'offline_shadow_unactivated'), ('new_acceptance', 'false'),
        ('customer_records', 'none'), ('consumer_authority', 'original_exact_purpose_required'),
        ('family_revision', 'r9_historical_gap_matrix'),
        ('full_research_replacement', 'false')])


def load_inputs(db, root):
    values = {}
    for name, relative in SOURCES.items():
        raw = (root/relative).read_bytes()
        value = json.loads(raw)
        values[name] = value
        collection = 'plans' if name in ('native', 'medical', 'display') else 'offerings' if name == 'families' else None
        children = value.get(collection) if collection else None
        kind = 'dict' if isinstance(children, dict) else 'list' if children is not None else None
        metadata = {k: v for k, v in value.items() if k != collection}
        db.execute('INSERT INTO artifact VALUES(?,?,?,?,?,?)',
                   (name, relative, sha(raw), put(db, metadata), collection, kind))
        if children is not None:
            for ordinal, (key, child) in enumerate(children.items() if kind == 'dict' else enumerate(children)):
                db.execute('INSERT INTO member VALUES(?,?,?,?)', (name, ordinal, str(key), put(db, child)))
    return values


def reconstruct(db, name):
    row = db.execute('SELECT metadata_object,collection,kind FROM artifact WHERE name=?', (name,)).fetchone()
    value = get(db, row[0])
    if row[1]:
        children = [(key, get(db, obj)) for key, obj in db.execute(
            'SELECT item_key,object FROM member WHERE artifact=? ORDER BY ordinal', (name,))]
        value[row[1]] = dict(children) if row[2] == 'dict' else [v for _, v in children]
    return value


def build(root, destination):
    if destination.exists():
        raise FileExistsError('An existing snapshot is never overwritten')
    destination.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(destination)
    try:
        initialize(db)
        values = load_inputs(db, root)
        for row in values['display']['plans']:
            plan = row['display_candidate']; oid = plan['offering_id']
            if not oid.startswith('2026:'):
                raise ValueError('Wrong year')
            db.execute('INSERT INTO offering VALUES(?,?,?,?,?)', (oid, 2026, plan['name'], plan['type'], put(db, row)))
            for field, cell in plan['benefits'].items():
                db.execute('INSERT INTO benefit VALUES(?,?,?,?)', (oid, field, cell['state'], put(db, cell)))
            for name, cell in plan['cost_examples'].items():
                amount = cell.get('amount') or {}
                if cell['state'] == 'held' and amount:
                    raise ValueError('Held scenario contains amount')
                db.execute('INSERT INTO scenario VALUES(?,?,?,?,?,?)',
                    (oid, name, cell['state'], amount.get('amount'), amount.get('unit'), put(db, cell)))
        for row in values['families']['offerings']:
            for name, value in row['families'].items():
                db.execute('INSERT INTO family VALUES(?,?,?,?)', (row['offering_id'], name, 'r9', put(db, value)))
        for oid, row in values['medical']['plans'].items():
            for name, value in row['medical_services'].items():
                db.execute('INSERT INTO medical_service VALUES(?,?,?)', (oid, name, put(db, value)))
        for question in values['questions']['questions']:
            db.execute('INSERT INTO question VALUES(?,?)', (question['question_id'], put(db, question)))
        db.commit()
        result = verify(db, root)
        db.execute('PRAGMA query_only=ON')
        return result
    finally:
        db.close()
        destination.chmod(0o400)


def verify(db, root):
    if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)] or db.execute('PRAGMA foreign_key_check').fetchall():
        raise ValueError('Snapshot integrity failed')
    for name, relative in SOURCES.items():
        raw = (root/relative).read_bytes()
        if sha(raw) != db.execute('SELECT source_sha256 FROM artifact WHERE name=?', (name,)).fetchone()[0]:
            raise ValueError('Original source changed')
        if canonical(reconstruct(db, name)) != canonical(json.loads(raw)):
            raise ValueError('Source reconstruction differs: '+name)
    counts = {t: db.execute('SELECT count(*) FROM '+t).fetchone()[0]
              for t in ('offering', 'benefit', 'scenario', 'family', 'medical_service', 'question')}
    expected = {'offering': 72, 'benefit': 720, 'scenario': 288, 'family': 1008,
                'medical_service': 1440, 'question': 41}
    if counts != expected:
        raise ValueError('MVP feature counts differ: '+str(counts))
    # Reconstruct each query index independently from the retained inputs. A
    # complete JSON round-trip alone would not detect a corrupted query column.
    display = json.loads((root/SOURCES['display']).read_bytes())
    expected_rows = {'offering': [], 'benefit': [], 'scenario': [], 'family': [],
                     'medical_service': [], 'question': []}
    for row in display['plans']:
        plan = row['display_candidate']; oid = plan['offering_id']
        expected_rows['offering'].append((oid, 2026, plan['name'], plan['type'], sha(canonical(row))))
        for field, cell in plan['benefits'].items():
            expected_rows['benefit'].append((oid, field, cell['state'], sha(canonical(cell))))
        for name, cell in plan['cost_examples'].items():
            amount = cell.get('amount') or {}
            expected_rows['scenario'].append((oid, name, cell['state'], amount.get('amount'),
                                               amount.get('unit'), sha(canonical(cell))))
    families = json.loads((root/SOURCES['families']).read_bytes())
    for row in families['offerings']:
        for name, value in row['families'].items():
            expected_rows['family'].append((row['offering_id'], name, 'r9', sha(canonical(value))))
    medical = json.loads((root/SOURCES['medical']).read_bytes())
    for oid, row in medical['plans'].items():
        for name, value in row['medical_services'].items():
            expected_rows['medical_service'].append((oid, name, sha(canonical(value))))
    questions = json.loads((root/SOURCES['questions']).read_bytes())
    expected_rows['question'] = [(q['question_id'], sha(canonical(q))) for q in questions['questions']]
    for table, rows in expected_rows.items():
        actual = db.execute('SELECT * FROM '+table).fetchall()
        if sorted(actual) != sorted(rows):
            raise ValueError('Query index differs: '+table)
    held = db.execute("SELECT count(*) FROM benefit WHERE state='held'").fetchone()[0]
    scenarios = db.execute("SELECT count(*) FROM scenario WHERE state='held'").fetchone()[0]
    if held != 141 or scenarios != 88:
        raise ValueError('Material hold counts differ')
    return {'passed': True, 'counts': counts, 'published_holds': held, 'scenario_holds': scenarios,
            'total_material_holds': held+scenarios, 'complete_input_json_roundtrips': len(SOURCES),
            'active_app_changed': False, 'new_acceptance': False, 'consumer_release_enabled': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--destination', required=True, type=Path)
    args = p.parse_args()
    print(json.dumps(build(args.root.resolve(), args.destination), indent=2))


if __name__ == '__main__':
    main()
