#!/usr/bin/env python3
"""Source-preserving 2026 pharmacy network inventory; no beneficiary pricing."""
import argparse
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import zipfile

from l04_acquire import write
from l07_acquire import file_hash

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l07-pharmacy-networks-2026-10-27'
PLANS = ROOT / 'docs/data/l05-drug-coverage-2026-10-25/build-r3/plans.json'
FIELDS = ['CONTRACT_ID', 'PLAN_ID', 'SEGMENT_ID', 'PHARMACY_NUMBER', 'PHARMACY_ZIPCODE',
          'PREFERRED_STATUS_RETAIL', 'PREFERRED_STATUS_MAIL', 'PHARMACY_RETAIL', 'PHARMACY_MAIL',
          'IN_AREA_FLAG'] + [f'{kind}_DISPENSING_FEE_{days}' for kind in ['BRAND', 'GENERIC', 'SELECTED'] for days in [30, 60, 90]]


def npi_from_number(value):
    return value[2:] if re.fullmatch(r'10\d{10}', value) else None


def channel(outlet, preference):
    if outlet not in ('Y', 'N') or preference not in ('Y', 'N'):
        return 'unknown_flag'
    if outlet == 'N':
        return 'not_offered' if preference == 'N' else 'inconsistent_flags'
    return 'preferred' if preference == 'Y' else 'standard'


def fees(values):
    result = []
    for value in values:
        if not value.strip() or value.strip() == '.':
            result.append(None)
        else:
            try:
                d = Decimal(value)
            except InvalidOperation as exc:
                raise ValueError('Malformed fee amount') from exc
            if not d.is_finite() or d < 0:
                raise ValueError('Unsupported fee amount')
            result.append(format(d, 'f'))
    return result


def build(out, acquisition):
    out.mkdir()
    manifest = json.loads((acquisition / 'source-manifest.json').read_text())
    if (acquisition / 'SEALED').read_text().strip() != file_hash(acquisition / 'source-manifest.json'):
        raise ValueError('Acquisition not sealed or changed')
    if manifest['year'] != 2026 or len(manifest['members']) != 6:
        raise ValueError('Wrong year or incomplete source parts')
    plans = {p['offering_id']: p for p in json.loads(PLANS.read_text())}
    if len(plans) != 71 or any(p['suppressed'] for p in plans.values()):
        raise ValueError('Unexpected plan denominator')
    con = sqlite3.connect(out / 'inventory.sqlite3')
    con.execute('PRAGMA journal_mode=OFF'); con.execute('PRAGMA synchronous=OFF')
    con.execute('PRAGMA temp_store=MEMORY')
    columns = ','.join('"' + f + '" TEXT NOT NULL' for f in FIELDS)
    con.execute('CREATE TABLE network(source_part INTEGER,source_ordinal INTEGER,offering_id TEXT NOT NULL,' + columns +
                ',pharmacy_npi TEXT,retail_status TEXT,mail_status TEXT,fees_json TEXT,raw_line BLOB NOT NULL,'
                'PRIMARY KEY(source_part,source_ordinal)) WITHOUT ROWID')
    insert = 'INSERT INTO network VALUES(' + ','.join('?' for _ in range(3 + len(FIELDS) + 5)) + ')'
    counts, flags = {}, Counter()
    by_plan = {oid: Counter() for oid in plans}
    npi_zips, invalid_numbers = defaultdict(set), Counter()
    digests = {}
    for member in sorted(manifest['members'], key=lambda x: x['part']):
        part = member['part']; path = ROOT / member['path']
        if file_hash(path) != member['sha256']:
            raise ValueError('Acquired nested ZIP changed')
        count, digest = Counter(), hashlib.sha256()
        export = out / f'network-part-{part}.psv.gz'
        with zipfile.ZipFile(path) as archive, gzip.open(export, 'wb', compresslevel=6) as selected:
            with archive.open(member['inner']['name']) as raw:
                header = raw.readline(); digest.update(header)
                if header.rstrip(b'\r\n').decode('ascii').split('|') != FIELDS:
                    raise ValueError('Unexpected native pharmacy field layout')
                selected.write(b'SOURCE_PART|SOURCE_ORDINAL|' + header)
                batch = []
                for ordinal, line in enumerate(raw, 2):
                    digest.update(line); count['national_rows'] += 1
                    if line.count(b'|') != len(FIELDS) - 1:
                        raise ValueError(f'Malformed native row {part}:{ordinal}')
                    key_cells = line.split(b'|', 3)[:3]
                    oid = '2026:' + ':'.join(x.decode('ascii') for x in key_cells)
                    if oid not in plans:
                        count['outside_scope_rows'] += 1
                        continue
                    cells = line.rstrip(b'\r\n').decode('ascii').split('|')
                    npi = npi_from_number(cells[3])
                    retail, mail = channel(cells[7], cells[5]), channel(cells[8], cells[6])
                    decoded_fees = json.dumps(fees(cells[10:]), separators=(',', ':'))
                    if npi:
                        npi_zips[npi].add(cells[4])
                    else:
                        invalid_numbers[cells[3]] += 1
                    if cells[9] not in ('0', '1'):
                        flags['unknown_service_area_flag'] += 1
                    for f, value in zip(FIELDS[5:10], cells[5:10]):
                        flags[f + '=' + value] += 1
                    flags['retail_status=' + retail] += 1; flags['mail_status=' + mail] += 1
                    batch.append((part, ordinal, oid, *cells, npi, retail, mail, decoded_fees, line))
                    selected.write(str(part).encode() + b'|' + str(ordinal).encode() + b'|' + line)
                    count['scoped_rows'] += 1
                    by_plan[oid]['rows'] += 1; by_plan[oid]['part_' + str(part)] += 1
                    by_plan[oid]['retail_' + retail] += 1; by_plan[oid]['mail_' + mail] += 1
                    if len(batch) == 10000:
                        con.executemany(insert, batch); batch.clear()
                    if count['national_rows'] % 5000000 == 0:
                        print('part', part, dict(count), flush=True)
                if batch:
                    con.executemany(insert, batch)
        con.commit()
        counts[str(part)] = dict(count)
        digests[str(part)] = {'native_sha256': digest.hexdigest(), 'native_name': member['inner']['name'],
                             'native_bytes': member['inner']['bytes'], 'archive_sha256': member['sha256']}
        print('completed part', part, dict(count), flush=True)
    print('building lookup indexes', flush=True)
    con.execute('CREATE INDEX network_plan_pharmacy ON network(offering_id,PHARMACY_NUMBER)')
    con.execute('CREATE INDEX network_pharmacy_zip ON network(pharmacy_npi,PHARMACY_ZIPCODE)')
    duplicates = con.execute('SELECT offering_id,PHARMACY_NUMBER,COUNT(*) FROM network GROUP BY offering_id,PHARMACY_NUMBER HAVING COUNT(*)>1').fetchall()
    con.commit(); con.close()
    write(out / 'plans.json', [{'offering_id': oid, 'name': p['name'], 'kind': p['kind'],
                               'suppressed': p['suppressed'], **dict(by_plan[oid])} for oid, p in sorted(plans.items())])
    write(out / 'pharmacy-keys.json', [{'npi': npi, 'source_zips': sorted(zips)} for npi, zips in sorted(npi_zips.items())])
    write(out / 'duplicates.json', [dict(zip(['offering_id', 'pharmacy_number', 'rows'], r)) for r in duplicates])
    write(out / 'invalid-pharmacy-numbers.json', dict(invalid_numbers))
    write(out / 'field-map.json', {'native_fields': FIELDS, 'fee_unit': 'USD dispensing fee, not full beneficiary payment',
          'derived_fields': ['pharmacy_npi', 'retail_status', 'mail_status', 'fees_json'],
          'NPI_derivation': 'Only documented 10 prefix plus ten digits; no inferred NPI for other forms',
          'selected_drug_fees': 'Native SELECTED fields correspond to layout SELECTED_DRUG_DISPENSING_FEE fields; preserve blank versus zero. Methodology uses brand fee if selected fee not reported.',
          'scope': 'No current-operation, drug-stock or continuous-effective-period inference'})
    coverage = {'schema': 'l07-network-coverage/1', 'year': 2026, 'target_plans': len(plans),
                'plans_with_rows': sum(bool(v['rows']) for v in by_plan.values()), 'accounting': counts,
                'native_field_observations': sum(c.get('scoped_rows', 0) for c in counts.values()) * len(FIELDS),
                'scoped_rows': sum(c.get('scoped_rows', 0) for c in counts.values()),
                'distinct_derived_npis': len(npi_zips), 'invalid_pharmacy_identifiers': dict(invalid_numbers),
                'duplicate_plan_pharmacy_keys': len(duplicates), 'flags': dict(flags),
                'identity_resolution': 'Separate identity and location build required',
                'consumer_release_enabled': False}
    write(out / 'coverage.json', coverage); write(out / 'source-members.json', digests)
    output_files = [p for p in out.iterdir() if p.is_file()]
    write(out / 'manifest.json', {'schema': 'l07-network-build/1', 'year': 2026,
          'acquisition_manifest': str((acquisition / 'source-manifest.json').relative_to(ROOT)),
          'input_sha256': {str(PLANS.relative_to(ROOT)): file_hash(PLANS),
                           str((acquisition / 'source-manifest.json').relative_to(ROOT)): file_hash(acquisition / 'source-manifest.json')},
          'code_sha256': {str(Path(__file__).resolve().relative_to(ROOT)): file_hash(Path(__file__).resolve())},
          'files_sha256': {p.name: file_hash(p) for p in output_files},
          'human_acceptance': None, 'consumer_release_enabled': False})
    print(json.dumps(coverage, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=BASE / 'build-r1')
    parser.add_argument('--acquisition', type=Path, default=BASE / 'acquisition-r1')
    args = parser.parse_args()
    build(args.out.resolve(), args.acquisition.resolve())
