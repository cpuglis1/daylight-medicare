"""Independent all-row/all-field source parity, selection accounting and parent preservation."""
import collections
import csv
import gzip
import hashlib
import json
import sqlite3
from pathlib import Path

from l08_r6_common import BASE, PARENT, ROOT, filehash, write


def main():
    errors, checks, counts = [], [], collections.Counter()
    def check(ok, label):
        checks.append({'check': label, 'passed': bool(ok)})
        if not ok:
            errors.append(label)

    stats = json.loads((BASE / 'normalization.json').read_text())
    selection = json.loads((BASE / 'selection.json').read_text())
    selected_ids = set(selection['selected_enrollment_ids'])
    seed = set(selection['base_enrollment_ids'])
    fl_npis = set(selection['Florida_clinician_NPIs'])
    fl_pacs = set(selection['Florida_clinician_PACs'])
    db = sqlite3.connect('file:' + str(BASE / 'original-medicare.sqlite3') + '?mode=ro', uri=True)
    check(db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'SQLite integrity')
    reconstructed_npis, reconstructed_clinical_ids, reconstructed_pacs = set(), set(), set()
    reconstructed_seed, reconstructed_edges = set(), set()
    # Recover independent seed membership before comparing every selected row.
    for kind in ['clinicians', 'practice_locations', 'additional_npis', 'enrollment']:
        item = stats[kind]
        with open(item['path'], encoding=item['encoding'], newline='') as f:
            for r in csv.DictReader(f):
                if kind == 'clinicians' and r['State'] == 'FL':
                    reconstructed_npis.add(r['NPI']); reconstructed_clinical_ids.add(r['Ind_enrl_ID'])
                    reconstructed_pacs.add(r['Ind_PAC_ID'])
                    reconstructed_seed.add(r['Ind_enrl_ID'])
                elif kind == 'practice_locations' and r['STATE_CD'] == 'FL':
                    reconstructed_seed.add(r['ENRLMT_ID'])
                elif kind == 'additional_npis' and r['NPI'] in reconstructed_npis:
                    reconstructed_seed.add(r['ENRLMT_ID'])
                elif kind == 'enrollment' and (r['STATE_CD'] == 'FL' or r['NPI'] in reconstructed_npis):
                    reconstructed_seed.add(r['ENRLMT_ID'])
    item = stats['reassignment']
    with open(item['path'], encoding=item['encoding'], newline='') as f:
        for r in csv.DictReader(f):
            a, b = r['REASGN_BNFT_ENRLMT_ID'], r['RCV_BNFT_ENRLMT_ID']
            if a in reconstructed_seed or b in reconstructed_seed:
                reconstructed_edges.update((a, b))
    check(seed == reconstructed_seed, 'Independent Florida seed accounting')
    check(selected_ids == reconstructed_seed | reconstructed_edges, 'Exactly one-hop enrollment expansion')
    check(fl_npis == reconstructed_npis and fl_pacs == reconstructed_pacs, 'Exact Florida identity sets')
    reconstructed_all = reconstructed_seed | reconstructed_edges
    for kind, item in stats.items():
        print('Validate '+kind,flush=True)
        check(filehash(Path(item['path'])) == item['sha256'], kind + ': input hash')
        record_stream = iter(db.execute('SELECT source_row,npi,enrollment_id,state_raw,city_raw,postal_raw,fields_json '
                                       'FROM observations WHERE source_id=? ORDER BY source_row', (kind,)))
        observed = next(record_stream, None)
        n = kept = 0
        with open(item['path'], encoding=item['encoding'], newline='') as f:
            reader = csv.DictReader(f)
            check(reader.fieldnames == item['headers'], kind + ': exact headers')
            for ix, r in enumerate(reader, 2):
                n += 1
                if None in r or any(v is None for v in r.values()):
                    errors.append(kind + ': malformed row ' + str(ix)); continue
                eid = r.get('ENRLMT_ID', r.get('Ind_enrl_ID', ''))
                npi = r.get('NPI', '')
                state = r.get('STATE_CD', r.get('State', r.get('State Code', '')))
                city = r.get('CITY_NAME', r.get('City/Town', r.get('City Name', '')))
                postal = r.get('ZIP_CD', r.get('ZIP Code', r.get('Zip Code', '')))
                if kind == 'clinicians':
                    keep = state == 'FL'
                elif kind == 'affiliations':
                    keep = npi in reconstructed_npis or r['Ind_PAC_ID'] in reconstructed_pacs
                elif kind == 'optout':
                    keep = True
                elif kind == 'reassignment':
                    keep = r['REASGN_BNFT_ENRLMT_ID'] in reconstructed_seed or r['RCV_BNFT_ENRLMT_ID'] in reconstructed_seed
                else:
                    keep = eid in reconstructed_all
                if not keep:
                    continue
                kept += 1
                if not observed or observed[:6] != (ix,npi,eid,state,city,postal) or json.loads(observed[6]) != r:
                    errors.append(kind + ': source field/row mismatch ' + str(ix))
                counts['literal_source_fields_compared'] += len(r)
                counts['source_rows_compared'] += 1
                if kind == 'clinicians':
                    a = db.execute('SELECT npi,enrollment_id,individual_raw,individual_state,group_raw,group_state FROM assignments WHERE source_row=?', (ix,)).fetchone()
                    mapping = {'Y':'published_accepts_assignment','M':'published_may_accept_assignment','':'unknown_not_published'}
                    exp = (npi,eid,r['ind_assgn'], mapping.get(r['ind_assgn'],'unknown_unrecognized_source_code'),
                           r['grp_assgn'], mapping.get(r['grp_assgn'],'unknown_unrecognized_source_code'))
                    if a != exp:
                        errors.append('Assignment interpretation mismatch ' + str(ix))
                    counts['assignment_fields_compared'] += 6
                observed = next(record_stream, None)
        check(observed is None, kind + ': no unsupported database rows')
        check(n == item['national_source_rows'] and kept == item['selected_rows'], kind + ': complete selection/count parity')
        counts['national_source_rows_accounted'] += n
    # All normalized states are independently recalculated from preserved source data.
    from datetime import date
    reference = date(2026,10,28)
    for table,kind in [('assignments','clinicians'),('enrollment_status','enrollment'),
                       ('optout_periods','optout'),('reassignments','reassignment')]:
        check(db.execute('SELECT count(*) FROM '+table).fetchone()[0]==stats[kind]['selected_rows'], table+': every derived row accounted')
    for row,npi,start,end,state,fields in db.execute("SELECT p.source_row,p.npi,p.start_raw,p.end_raw,p.state,o.fields_json "
        "FROM optout_periods p JOIN observations o ON o.source_id='optout' AND o.source_row=p.source_row"):
        f=json.loads(fields)
        if (npi,start,end)!=(f['NPI'],f['Optout Effective Date'],f['Optout End Date']):
            errors.append('Opt-out identity/date source mismatch '+str(row))
        try:
            a, b = date.fromisoformat(start), date.fromisoformat(end)
            exp = ('held_reversed_source_interval' if a>b else
                   'source_interval_boundary_review' if reference in (a,b) else
                   'published_optout_interval_contains_reference_date' if a<reference<b else
                   'published_interval_does_not_contain_reference_date')
        except (TypeError, ValueError):
            exp = 'unknown_invalid_or_missing_source_date'
        if state != exp:
            errors.append('Opt-out interval mismatch ' + str(row))
        counts['optout_periods_compared'] += 1
    for r in db.execute("SELECT e.source_row,e.provider_type_raw,e.state,o.fields_json,e.npi,e.enrollment_id FROM enrollment_status e "
                        "JOIN observations o ON o.source_id='enrollment' AND o.source_row=e.source_row"):
        f = json.loads(r[3]); prefix = f['PROVIDER_TYPE_CD'].split('-')[0]
        exp = ('published_ordering_referring_only_enrollment' if prefix=='33' else
               'published_approved_billing_enrollment_in_extract' if prefix in {'00','12','14','30','53'} else
               'published_enrollment_unclassified_type')
        if r[1] != f['PROVIDER_TYPE_CD'] or r[2] != exp or (r[4],r[5])!=(f['NPI'],f['ENRLMT_ID']):
            errors.append('Enrollment interpretation mismatch ' + str(r[0]))
        counts['enrollment_statuses_compared'] += 1
    for r in db.execute("SELECT r.source_row,r.reassigning_id,r.receiving_id,o.fields_json FROM reassignments r "
                        "JOIN observations o ON o.source_id='reassignment' AND o.source_row=r.source_row"):
        f = json.loads(r[3])
        if (r[1],r[2]) != (f['REASGN_BNFT_ENRLMT_ID'],f['RCV_BNFT_ENRLMT_ID']):
            errors.append('Reassignment mismatch ' + str(r[0]))
        counts['reassignment_edges_compared'] += 1
    for key in ['enrollment','optout']:
        a = json.loads((BASE / (key+'-api-accounting.json')).read_text())
        check(a['terminal_empty_page'] and a['whole_population_all_field_multiset_comparison_passed'], key + ': API/CSV complete literal comparison')
        counts['API_pages_accounted'] += len(a['pages'])
        # Recreate the comparison independently from the actual retained page bodies.
        expected = collections.Counter()
        item = stats[key]
        with open(item['path'], encoding=item['encoding'], newline='') as f:
            for r in csv.DictReader(f):
                if key=='optout' or r['STATE_CD']=='FL':
                    expected[json.dumps(r,sort_keys=True,ensure_ascii=False)] += 1
        actual = collections.Counter()
        offset=0
        for page in a['pages']:
            raw=BASE/'acquisition/raw'/page['sha256']
            data=json.loads(raw.read_bytes())
            check(page['offset']==offset and page['rows']==len(data), key+': page accounting '+str(offset))
            for r in data:
                actual[json.dumps(r,sort_keys=True,ensure_ascii=False)] += 1
                counts['API_literal_fields_independently_compared'] += len(r)
            offset+=len(data)
        check(expected==actual, key+': independent complete API/CSV field multiset')
        check(a['pages'][-1]['rows']==0 and offset==a['rows'], key+': exact terminal/row accounting')
        del expected,actual
    for entry in json.loads((BASE/'owner-intake.json').read_text()):
        h=hashlib.sha256()
        with gzip.open(entry['retained_path'],'rb') as f:
            for chunk in iter(lambda:f.read(1024*1024), b''):h.update(chunk)
        check(h.hexdigest()==entry['sha256_original_bytes'], 'Retained owner bytes: '+Path(entry['owner_path']).name)
        counts['retained_owner_files_compared']+=1
    for p in (BASE/'acquisition/receipts').glob('*.json'):
        r=json.loads(p.read_text())
        check(not r.get('error'), 'Acquisition succeeded: '+r['url'])
        if r.get('raw_relative_path'):
            check(filehash(BASE/'acquisition'/r['raw_relative_path'])==r['sha256'], 'Response content hash: '+p.name)
            counts['API_or_download_receipts_compared']+=1
    pin=json.loads((BASE/'parent-pin.json').read_text())
    check(filehash(PARENT/'providers.sqlite3')==pin['database_sha256'], 'Parent database unchanged')
    check(filehash(PARENT/'manifest.json')==pin['manifest_sha256'], 'Parent manifest unchanged')
    parent_manifest=json.loads((PARENT/'manifest.json').read_text())
    print('Rehash sealed parent files',flush=True)
    for rel, m in parent_manifest['files'].items():
        p=ROOT/rel
        if not p.exists() or p.stat().st_size!=m['bytes'] or filehash(p)!=m['sha256']:
            errors.append('Parent sealed file changed: '+rel)
        counts['sealed_parent_files_rehashed']+=1
    check(db.execute("SELECT value_json FROM metadata WHERE key='consumer_release_enabled'").fetchone()[0]=='false', 'Consumer release remains disabled')
    db.close()
    write(BASE/'validation.json', {'passed': not errors,'checks': checks,'counts':dict(counts),
          'errors':errors, 'scope':'Every selected literal field and source row; independently reconstructed selection, normalized states, API/CSV population comparison, complete retained source bytes and sealed parent hashes. Not a census or personal participation acceptance.'})
    print(json.dumps({'passed':not errors,'counts':dict(counts),'errors':errors[:10]}),flush=True)
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
