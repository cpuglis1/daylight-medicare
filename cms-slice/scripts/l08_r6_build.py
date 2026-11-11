"""Normalize dated CMS records with complete source retention and explicit Florida selection."""
import collections
import csv
import gzip
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

from l08_r6_common import BASE, HOME, OWNER, PARENT, REFERENCE_DATE, ROOT, assert_open, csv_encoding, filehash, packed, write
from l08_r6_reference import assignment_state, enrollment_state, optout_state


def rows(path, encoding):
    with Path(path).open(encoding=encoding, newline='') as stream:
        r = csv.DictReader(stream)
        for ix, value in enumerate(r, 2):
            if None in value or any(v is None for v in value.values()):
                raise ValueError('Malformed source row: ' + str(path) + ':' + str(ix))
            yield ix, value


def retain_owner():
    inventory = []
    parent = BASE / 'owner-originals'
    parent.mkdir(exist_ok=True)
    manifest = json.loads((OWNER / 'manifest.json').read_text())
    specs = {r['filename']: (d, r) for d in manifest for r in d['resources']}
    for path in sorted(OWNER.iterdir()):
        if not path.is_file():
            raise ValueError('Unexpected input directory')
        dest = parent / (path.name + '.gz')
        if not dest.exists():
            with path.open('rb') as src, gzip.open(dest, 'wb', compresslevel=6) as out:
                shutil.copyfileobj(src, out, 1024 * 1024)
        h = hashlib.sha256()
        with gzip.open(dest, 'rb') as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                h.update(chunk)
        if h.hexdigest() != filehash(path):
            raise ValueError('Retained owner bytes mismatch')
        item = {'owner_path': str(path), 'retained_path': str(dest),
                'sha256_original_bytes': h.hexdigest(), 'bytes': path.stat().st_size}
        if path.name in specs:
            d, r = specs[path.name]
            if path.stat().st_size != r['filesize']:
                raise ValueError('Owner manifest size mismatch')
            item.update(publisher_manifest=d, modeled=d['dataset_id'] != 'n0yb-util')
        inventory.append(item)
    write(BASE / 'owner-intake.json', inventory)
    return inventory


def main():
    assert_open()
    BASE.mkdir(exist_ok=True)
    write(BASE / 'parent-pin.json', {'reference': json.loads((HOME / 'CURRENT_REFERENCE.json').read_text()),
          'manifest_sha256': filehash(PARENT / 'manifest.json'),
          'database_sha256': filehash(PARENT / 'providers.sqlite3'),
          'parent_database_is_read_only_and_not_cloned': True})
    if json.loads((HOME / 'CURRENT_REFERENCE.json').read_text())['reference_id'] != 'L08-PUBLISHED-COLLIER-2026-research-r5':
        raise ValueError('Unexpected parent; reconcile before build')
    inventory = retain_owner()
    sources = json.loads((BASE / 'sources.json').read_text())
    paths = {k: Path(v['path']) for k, v in sources.items() if v['resource']['downloadURL'].endswith('.csv')}
    paths['clinicians'] = next(OWNER.glob('*DAC_NationalDownloadableFile.csv'))
    paths['affiliations'] = next(OWNER.glob('*Facility_Affiliation.csv'))
    encodings = {k: csv_encoding(p) for k, p in paths.items()}
    fl_npis, fl_clinical_ids, fl_pacs = set(), set(), set()
    for _, r in rows(paths['clinicians'], encodings['clinicians']):
        if r['State'] == 'FL':
            fl_npis.add(r['NPI']); fl_clinical_ids.add(r['Ind_enrl_ID']); fl_pacs.add(r['Ind_PAC_ID'])
    seed = set(fl_clinical_ids)
    for _, r in rows(paths['practice_locations'], encodings['practice_locations']):
        if r['STATE_CD'] == 'FL':
            seed.add(r['ENRLMT_ID'])
    for _, r in rows(paths['additional_npis'], encodings['additional_npis']):
        if r['NPI'] in fl_npis:
            seed.add(r['ENRLMT_ID'])
    for _, r in rows(paths['enrollment'], encodings['enrollment']):
        if r['STATE_CD'] == 'FL' or r['NPI'] in fl_npis:
            seed.add(r['ENRLMT_ID'])
    # Exactly one hop from the frozen Florida seed, not recursive expansion through
    # shared national billing groups. Both source endpoints of selected edges remain.
    selected_ids = set(seed)
    for _, r in rows(paths['reassignment'], encodings['reassignment']):
        a, b = r['REASGN_BNFT_ENRLMT_ID'], r['RCV_BNFT_ENRLMT_ID']
        if a in seed or b in seed:
            selected_ids.update((a, b))
    write(BASE / 'selection.json', {'state': 'FL', 'base_enrollment_ids': sorted(seed),
           'selected_enrollment_ids': sorted(selected_ids), 'Florida_clinician_NPIs': sorted(fl_npis),
           'Florida_clinician_PACs': sorted(fl_pacs),
           'policy': 'All FL clinician listings; enrollment STATE_CD=FL or clinician-NPI/ID match or FL practice city/state/ZIP or additional-NPI match, plus one-hop reassignment endpoints. All related selected enrollment rows, locations, secondary specialties and additional NPIs; affiliations matching FL clinician NPI/PAC. National opt-out records. No county inferred from ZIP or city.'})
    dbpath = BASE / 'original-medicare.sqlite3'
    if dbpath.exists():
        dbpath.unlink()
    db = sqlite3.connect(dbpath)
    db.execute('PRAGMA journal_mode=OFF')
    db.execute('PRAGMA temp_store=MEMORY')
    db.executescript('''
        CREATE TABLE sources(id TEXT PRIMARY KEY, fields_json TEXT NOT NULL);
        CREATE TABLE observations(source_id TEXT,source_row INTEGER,npi TEXT,enrollment_id TEXT,
            state_raw TEXT,city_raw TEXT,postal_raw TEXT,fields_json TEXT NOT NULL,
            PRIMARY KEY(source_id,source_row));
        CREATE TABLE assignments(source_row INTEGER PRIMARY KEY,npi TEXT,enrollment_id TEXT,
            individual_raw TEXT,individual_state TEXT,group_raw TEXT,group_state TEXT);
        CREATE TABLE enrollment_status(source_row INTEGER PRIMARY KEY,enrollment_id TEXT,npi TEXT,
            provider_type_raw TEXT,state TEXT);
        CREATE TABLE optout_periods(source_row INTEGER PRIMARY KEY,npi TEXT,start_raw TEXT,end_raw TEXT,state TEXT);
        CREATE TABLE reassignments(source_row INTEGER PRIMARY KEY,reassigning_id TEXT,receiving_id TEXT);
        CREATE TABLE metadata(key TEXT PRIMARY KEY,value_json TEXT);
    ''')
    statistics = {}
    for kind, path in paths.items():
        n, kept, fields = 0, 0, 0
        source_counts = collections.Counter()
        selected_counts = collections.Counter()
        headers = None
        print('Normalize ' + kind, flush=True)
        for ix, r in rows(path, encodings[kind]):
            n += 1
            if headers is None:
                headers = list(r)
            eid = r.get('ENRLMT_ID', r.get('Ind_enrl_ID', ''))
            npi = r.get('NPI', '')
            state = r.get('STATE_CD', r.get('State', r.get('State Code', '')))
            city = r.get('CITY_NAME', r.get('City/Town', r.get('City Name', '')))
            postal = r.get('ZIP_CD', r.get('ZIP Code', r.get('Zip Code', '')))
            source_counts[state] += 1
            if kind == 'clinicians':
                keep = state == 'FL'
            elif kind == 'affiliations':
                keep = npi in fl_npis or r['Ind_PAC_ID'] in fl_pacs
            elif kind == 'reassignment':
                keep = r['REASGN_BNFT_ENRLMT_ID'] in seed or r['RCV_BNFT_ENRLMT_ID'] in seed
            elif kind == 'optout':
                keep = True
            else:
                keep = eid in selected_ids
            if not keep:
                continue
            kept += 1; fields += len(r); selected_counts[state] += 1
            db.execute('INSERT INTO observations VALUES(?,?,?,?,?,?,?,?)',
                       (kind, ix, npi, eid, state, city, postal, packed(r)))
            if kind == 'clinicians':
                db.execute('INSERT INTO assignments VALUES(?,?,?,?,?,?,?)',
                           (ix,npi,eid,r['ind_assgn'],assignment_state(r['ind_assgn']),
                            r['grp_assgn'],assignment_state(r['grp_assgn'])))
            elif kind == 'enrollment':
                db.execute('INSERT INTO enrollment_status VALUES(?,?,?,?,?)',
                           (ix,eid,npi,r['PROVIDER_TYPE_CD'],enrollment_state(r['PROVIDER_TYPE_CD'])))
            elif kind == 'optout':
                db.execute('INSERT INTO optout_periods VALUES(?,?,?,?,?)',
                           (ix,npi,r['Optout Effective Date'],r['Optout End Date'],
                            optout_state(r['Optout Effective Date'],r['Optout End Date'])))
            elif kind == 'reassignment':
                db.execute('INSERT INTO reassignments VALUES(?,?,?)',
                           (ix,r['REASGN_BNFT_ENRLMT_ID'],r['RCV_BNFT_ENRLMT_ID']))
        item = {'path': str(path), 'sha256': filehash(path), 'encoding': encodings[kind],
                'national_source_rows': n, 'selected_rows': kept, 'selected_literal_fields': fields,
                'headers': headers, 'national_state_row_counts': dict(source_counts),
                'selected_state_row_counts': dict(selected_counts)}
        statistics[kind] = item
        db.execute('INSERT INTO sources VALUES(?,?)', (kind,packed(item)))
        db.commit()
    db.executescript('''
        CREATE INDEX observation_npi ON observations(npi);
        CREATE INDEX observation_enrollment ON observations(enrollment_id);
        CREATE INDEX observation_city ON observations(city_raw,state_raw);
        CREATE INDEX enrollment_id ON enrollment_status(enrollment_id);
        CREATE INDEX enrollment_npi ON enrollment_status(npi);
        CREATE INDEX optout_npi ON optout_periods(npi);
        CREATE INDEX reassigning_id ON reassignments(reassigning_id);
        CREATE INDEX receiving_id ON reassignments(receiving_id);
    ''')
    for key, value in {'reference_date': REFERENCE_DATE, 'data_acceptance_inferred': False,
                       'consumer_release_enabled': False, 'county_assignment': 'unknown_not_inferred_from_city_or_ZIP',
                       'MA_participation_established': False}.items():
        db.execute('INSERT INTO metadata VALUES(?,?)',(key,packed(value)))
    db.commit()
    db.close()
    write(BASE / 'normalization.json', statistics)
    print(json.dumps({k: v['selected_rows'] for k, v in statistics.items()}), flush=True)


if __name__ == '__main__':
    main()
