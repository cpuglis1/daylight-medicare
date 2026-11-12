#!/usr/bin/env python3
"""Re-read all native price rows and independently compare the scoped outputs."""
import argparse
from collections import Counter
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def digest_file(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        while block := f.read(4 * 1024 * 1024):
            h.update(block)
    return h.hexdigest()


def compare_source_row(ordinal, raw, stored):
    """Compare source strings and reverse the scaled amount without builder helpers."""
    if stored is None:
        raise ValueError(f'Source price row missing from inventory: {ordinal}')
    values = raw.rstrip(b'\r\n').decode('ascii').split('|')
    contract, plan, segment, ndc, days, cost = values
    if stored[0] != ordinal or stored[1] != '2026:' + ':'.join(values[:3]):
        raise ValueError(f'Price ordinal/identity differs: {ordinal}')
    if tuple(stored[2:6]) != (contract, plan, segment, ndc) or stored[8] != cost or stored[9] != raw:
        raise ValueError(f'Native price field differs: {ordinal}')
    if stored[10] == 'published_average':
        if str(stored[6]) != days or stored[6] not in (30, 60, 90):
            raise ValueError(f'Days-supply differs: {ordinal}')
        if Decimal(stored[7]) / Decimal(10000) != Decimal(cost):
            raise ValueError(f'Modeled price differs: {ordinal}')
        if len(ndc) != 11 or not ndc.isdigit() or Decimal(cost) < 0:
            raise ValueError(f'Invalid published drug/price: {ordinal}')


def validate(package, output):
    manifest = json.loads((package / 'manifest.json').read_text())
    coverage = json.loads((package / 'coverage.json').read_text())
    checks = {}
    for key in ['files_sha256', 'code_sha256', 'input_sha256']:
        for name, expected in manifest[key].items():
            path = package / name if key == 'files_sha256' else ROOT / name
            checks[key + ':' + name] = digest_file(path) == expected
    if not all(checks.values()):
        raise ValueError('Bound input/code/artifact hash mismatch')
    target_file = ROOT / 'docs/data/l05-drug-coverage-2026-10-25/build-r3/plans.json'
    targets = {p['offering_id']: p for p in json.loads(target_file.read_text())}
    target_keys = {tuple(p.split(':')[1:]) for p in targets}
    con = sqlite3.connect('file:' + str(package / 'inventory.sqlite3') + '?mode=ro', uri=True)
    source = manifest['price_source']
    checks['price_zip_hash'] = digest_file(ROOT / source['path']) == source['sha256']
    if not checks['price_zip_hash']:
        raise ValueError('Price source changed')
    stored_rows = iter(con.execute('SELECT * FROM prices ORDER BY source_ordinal'))
    next_stored = next(stored_rows, None)
    counts = Counter()
    per_plan = Counter()
    source_digest = hashlib.sha256()
    with zipfile.ZipFile(ROOT / source['path']) as archive:
        members = [m for m in archive.infolist() if not m.is_dir()]
        if len(members) != 1:
            raise ValueError('Ambiguous price source')
        with archive.open(members[0]) as native, gzip.open(package / 'prices-native.psv.gz', 'rb') as flat:
            header = native.readline()
            source_digest.update(header)
            if header.rstrip(b'\r\n') != b'CONTRACT_ID|PLAN_ID|SEGMENT_ID|NDC|DAYS_SUPPLY|UNIT_COST':
                raise ValueError('Unexpected source fields')
            if flat.readline() != b'SOURCE_ORDINAL|' + header:
                raise ValueError('Flat source header differs')
            for ordinal, raw in enumerate(native, 2):
                source_digest.update(raw)
                counts['national_rows'] += 1
                cells = raw.rstrip(b'\r\n').split(b'|')
                if len(cells) != 6:
                    raise ValueError('Malformed native row')
                key = tuple(v.decode('ascii') for v in cells[:3])
                if key not in target_keys:
                    counts['outside_scope_rows'] += 1
                    continue
                counts['scoped_rows'] += 1
                compare_source_row(ordinal, raw, next_stored)
                if flat.readline() != str(ordinal).encode() + b'|' + raw:
                    raise ValueError('Flat output differs from native row ' + str(ordinal))
                counts['quarantined_rows' if next_stored[10] != 'published_average' else 'valid_scoped_rows'] += 1
                per_plan[next_stored[1]] += 1
                next_stored = next(stored_rows, None)
            if flat.read(1) or next_stored is not None:
                raise ValueError('Extra flat/database rows not in source')
    checks['native_price_member_hash'] = source_digest.hexdigest() == coverage['native_pricing_member']['sha256']
    checks['all_source_rows_accounted'] = counts['national_rows'] == counts['outside_scope_rows'] + counts['scoped_rows']
    checks['source_counts_agree'] = dict(counts) == coverage['source_row_accounting']
    checks['six_modeled_fields_per_scoped_row'] = counts['scoped_rows'] * 6 == coverage['modeled_source_field_observations']
    checks['database_target_set_equals_existing_71'] = {r[0] for r in con.execute('SELECT offering_id FROM plans')} == set(targets)
    rows = json.loads((package / 'plan-coverage.json').read_text())
    checks['per_plan_price_counts_agree'] = all(per_plan[r['offering_id']] == r['published_rows'] for r in rows)
    checks['all_71_target_plans_accounted_in_coverage'] = len(rows) == 71 and {r['offering_id'] for r in rows} == set(targets)
    old = sqlite3.connect('file:' + str(ROOT / 'docs/data/l05-drug-coverage-2026-10-25/build-r3/inventory.sqlite3') + '?mode=ro', uri=True)
    expected = set()
    for oid, p in targets.items():
        expected.update((oid, r[0]) for r in old.execute("SELECT DISTINCT ndc FROM drug_rows WHERE table_name='basic' AND formulary_id=?", (p['formulary_id'],)))
    actual = set(con.execute('SELECT offering_id,ndc FROM formulary_pairs'))
    priced = set(con.execute("SELECT DISTINCT offering_id,ndc FROM prices WHERE disposition='published_average'"))
    missing = set((r['offering_id'], r['ndc']) for r in json.loads((package / 'missing-formulary-prices.json').read_text()))
    checks['basic_formulary_denominator_independently_reconstructed'] = expected == actual
    checks['missing_price_list_exact'] = missing == expected - priced
    checks['matched_formulary_price_count'] = len(expected & priced) == coverage['formulary_ndc_pairs_with_any_price']
    checks['price_only_pair_count'] = len(priced - expected) == coverage['price_only_plan_ndc_pairs']
    checks['no_personal_estimate_release'] = not manifest['consumer_release_enabled'] and not coverage['personal_calculator_implemented']
    old.close()
    con.close()
    result = {'schema': 'l06-independent-source-audit/1', 'passed': all(checks.values()),
        'package_manifest_sha256': digest_file(package / 'manifest.json'), 'checks': checks,
        'native_price_rows_read': counts['national_rows'], 'scoped_rows_checked': counts['scoped_rows'],
        'native_and_modeled_fields_checked': counts['scoped_rows'] * 6,
        'unexplained_field_mismatches': 0,
        'limits': 'Source-copy, modeled-field and declared population/join validation only. No named-pharmacy price, beneficiary calculation, personal applicability or human data acceptance.'}
    if output.exists():
        raise ValueError('Refusing to overwrite validation receipt')
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'checks'}, indent=2), flush=True)
    if not result['passed']:
        raise ValueError('Source audit failed: ' + str([k for k, v in checks.items() if not v]))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    validate(args.package.resolve(), args.out.resolve())
