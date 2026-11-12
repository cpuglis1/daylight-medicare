#!/usr/bin/env python3
"""Independent complete reread of all six original 2026 network parts."""
import argparse
from collections import Counter
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l07-pharmacy-networks-2026-10-27'
EXPECTED = ['CONTRACT_ID', 'PLAN_ID', 'SEGMENT_ID', 'PHARMACY_NUMBER', 'PHARMACY_ZIPCODE',
            'PREFERRED_STATUS_RETAIL', 'PREFERRED_STATUS_MAIL', 'PHARMACY_RETAIL', 'PHARMACY_MAIL', 'IN_AREA_FLAG',
            'BRAND_DISPENSING_FEE_30', 'BRAND_DISPENSING_FEE_60', 'BRAND_DISPENSING_FEE_90',
            'GENERIC_DISPENSING_FEE_30', 'GENERIC_DISPENSING_FEE_60', 'GENERIC_DISPENSING_FEE_90',
            'SELECTED_DISPENSING_FEE_30', 'SELECTED_DISPENSING_FEE_60', 'SELECTED_DISPENSING_FEE_90']


def digest_file(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for b in iter(lambda: stream.read(1048576), b''):
            h.update(b)
    return h.hexdigest()


def expected_derivations(cells):
    value = cells[3]
    npi = value[2:] if len(value) == 12 and value[:2] == '10' and value.isascii() and value.isdigit() else None
    states = []
    for outlet, preferred in [(cells[7], cells[5]), (cells[8], cells[6])]:
        if outlet == 'Y' and preferred == 'Y': states.append('preferred')
        elif outlet == 'Y' and preferred == 'N': states.append('standard')
        elif outlet == 'N' and preferred == 'N': states.append('not_offered')
        elif outlet == 'N' and preferred == 'Y': states.append('inconsistent_flags')
        else: states.append('unknown_flag')
    amounts = []
    for raw in cells[10:]:
        if raw.strip() in ('', '.'):
            amounts.append(None)
        else:
            amount = Decimal(raw)
            if not amount.is_finite() or amount < 0:
                raise ValueError('Invalid source fee')
            amounts.append(format(amount, 'f'))
    return npi, *states, amounts


def assert_record(record, part, ordinal, oid, cells, line):
    if record is None or tuple(record[:3]) != (part, ordinal, oid):
        raise ValueError('Missing/reassigned network source row')
    if tuple(record[3:22]) != tuple(cells) or record[26] != line:
        raise ValueError('Native field or raw-line mismatch')
    npi, retail, mail, amounts = expected_derivations(cells)
    if tuple(record[22:25]) != (npi, retail, mail) or json.loads(record[25]) != amounts:
        raise ValueError('Derived field mismatch')


def validate(package, output):
    manifest = json.loads((package / 'manifest.json').read_text())
    checks = {}
    for key, values in [('input_sha256', manifest['input_sha256']), ('code_sha256', manifest['code_sha256'])]:
        for path, sha in values.items():
            checks[key + ':' + path] = digest_file(ROOT / path) == sha
    for name, sha in manifest['files_sha256'].items():
        checks['file_sha256:' + name] = digest_file(package / name) == sha
    if not all(checks.values()):
        raise ValueError('A bound input/code/output changed')
    acq = json.loads((ROOT / manifest['acquisition_manifest']).read_text())
    checks['all_six_original_parts'] = sorted(m['part'] for m in acq['members']) == list(range(1, 7))
    checks['source_year_2026'] = acq['year'] == manifest['year'] == 2026
    if not all(checks.values()):
        raise ValueError('Wrong source year or omitted part')
    plans_path = next(ROOT / p for p in manifest['input_sha256'] if p.endswith('/plans.json'))
    plans = json.loads(plans_path.read_text())
    prefixes = {(':'.join(p['offering_id'].split(':')[1:]) + ':').replace(':', '|').encode(): p['offering_id'] for p in plans}
    counts, plan_counts, source_hashes = {}, Counter(), {}
    sources = json.loads((package / 'source-members.json').read_text())
    con = sqlite3.connect('file:' + str(package / 'inventory.sqlite3') + '?mode=ro', uri=True)
    for member in sorted(acq['members'], key=lambda m: m['part']):
        part = member['part']; path = ROOT / member['path']
        if digest_file(path) != member['sha256']:
            raise ValueError('Original ZIP changed')
        # Validate retained HTTP range hashes and complete nonoverlapping coverage.
        next_at = member['start']
        for block in member['compressed_ranges']:
            if block['start'] != next_at or digest_file(ROOT / block['path']) != block['sha256']:
                raise ValueError('Missing, shifted or altered retained HTTP range')
            next_at = block['end'] + 1
        if next_at != member['end']:
            raise ValueError('Incomplete retained member ranges')
        rows = con.execute('SELECT * FROM network WHERE source_part=? ORDER BY source_ordinal', (part,))
        count, h, size = Counter(), hashlib.sha256(), 0
        with zipfile.ZipFile(path) as z, gzip.open(package / f'network-part-{part}.psv.gz', 'rb') as exported:
            with z.open(member['inner']['name']) as stream:
                header = stream.readline(); h.update(header); size += len(header)
                if header.rstrip(b'\r\n').decode().split('|') != EXPECTED:
                    raise ValueError('Unexpected original header')
                if exported.readline() != b'SOURCE_PART|SOURCE_ORDINAL|' + header:
                    raise ValueError('Export header mismatch')
                for ordinal, line in enumerate(stream, 2):
                    h.update(line); size += len(line); count['national_rows'] += 1
                    if line.count(b'|') != 18:
                        raise ValueError('Malformed source row')
                    oid = prefixes.get(line[:14])
                    if oid is None:
                        count['outside_scope_rows'] += 1
                    else:
                        cells = line.rstrip(b'\r\n').decode('ascii').split('|')
                        assert_record(rows.fetchone(), part, ordinal, oid, cells, line)
                        if exported.readline() != f'{part}|{ordinal}|'.encode() + line:
                            raise ValueError('Exported source field mismatch')
                        count['scoped_rows'] += 1; plan_counts[oid] += 1
                    if count['national_rows'] % 20000000 == 0:
                        print('audit part', part, dict(count), flush=True)
                if rows.fetchone() is not None or exported.read(1):
                    raise ValueError('Invented extra database/export row')
        if size != member['inner']['bytes'] or h.hexdigest() != sources[str(part)]['native_sha256']:
            raise ValueError('Native byte count/hash mismatch')
        counts[str(part)] = dict(count); source_hashes[str(part)] = h.hexdigest()
        print('audit completed part', part, dict(count), flush=True)
    coverage = json.loads((package / 'coverage.json').read_text())
    checks['row_accounting_recomputed'] = counts == coverage['accounting']
    checks['all_71_plans_have_source_rows'] = len(plan_counts) == 71 == len(plans)
    checks['all_19_native_fields_and_13_derived_values_checked'] = True
    checks['database_and_native_exports_match_every_scoped_source_row'] = True
    total = sum(c.get('scoped_rows', 0) for c in counts.values())
    checks['native_field_observation_count'] = total * 19 == coverage['native_field_observations']
    con.close()
    result = {'schema': 'l07-independent-network-validation/1', 'passed': all(checks.values()),
              'checks': checks, 'manifest_sha256': digest_file(package / 'manifest.json'),
              'scoped_rows_checked': total, 'native_field_observations_checked': total * 19,
              'derived_value_observations_checked': total * 13, 'accounting': counts,
              'native_sha256': source_hashes, 'unexplained_field_mismatches': 0,
              'limits': 'Published network fidelity; pharmacy identity/address and geography have separate audits; no live participation or personal price claim'}
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: result[k] for k in ['passed', 'scoped_rows_checked', 'native_field_observations_checked']}, indent=2))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, default=BASE / 'build-r1')
    parser.add_argument('--out', type=Path, default=BASE / 'build-r1-validation.json')
    args = parser.parse_args()
    validate(args.package.resolve(), args.out.resolve())
