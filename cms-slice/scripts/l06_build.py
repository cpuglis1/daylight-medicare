#!/usr/bin/env python3
"""Build an inspectable 2026 published average-price collection, not a calculator."""
import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l06-drug-costs-2026-10-27'
L05 = ROOT / 'docs/data/l05-drug-coverage-2026-10-25/build-r3'
COLUMNS = ['CONTRACT_ID', 'PLAN_ID', 'SEGMENT_ID', 'NDC', 'DAYS_SUPPLY', 'UNIT_COST']


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        while block := source.read(4 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def read(path):
    return json.loads(path.read_text())


def member_native(member):
    """Hash all uncompressed bytes, allowing ZipFile to verify the native CRC."""
    path = ROOT / member['path']
    if sha(path) != member['sha256']:
        raise ValueError('Changed acquired member: ' + str(path))
    with zipfile.ZipFile(path) as archive:
        infos = [i for i in archive.infolist() if not i.is_dir()]
        if len(infos) != 1:
            raise ValueError('Expected one native member')
        info = infos[0]
        digest = hashlib.sha256()
        with archive.open(info) as source:
            while block := source.read(4 * 1024 * 1024):
                digest.update(block)
    return {'name': info.filename, 'bytes': info.file_size, 'sha256': digest.hexdigest()}


def build(acquisition, out):
    if out.exists():
        raise ValueError('Use a new output revision')
    out.mkdir(parents=True)
    source = read(acquisition / 'source-manifest.json')
    if (source['year'] != 2026 or (acquisition / 'SEALED').read_text().strip() !=
            sha(acquisition / 'source-manifest.json')):
        raise ValueError('Year or acquisition seal mismatch')
    members = source['members']
    plans = {p['offering_id']: p for p in read(L05 / 'plans.json')}
    if len(plans) != 71 or not all(k.startswith('2026:') for k in plans):
        raise ValueError('Changed target population')
    wanted = {tuple(k.split(':')[1:]): k for k in plans}
    wanted_bytes = {tuple(x.encode('ascii') for x in k): v for k, v in wanted.items()}
    # Verify that the quarterly companion bytes really are the already-audited
    # monthly plan/formulary snapshot before reusing any relationships.
    bridge = []
    old_monthly = read(ROOT / 'docs/data/l04-pdp-availability-2026-10-25/acquisition-r1/source-manifest.json')['sources']['monthly']
    old_drugs = read(L05 / 'source-members.json')
    for label, token in [('basic', 'basic drugs formulary'), ('excluded', 'excluded drugs formulary'), ('plan', 'plan information')]:
        member = next(m for m in members if token in m['name'].lower())
        native = member_native(member)
        if label == 'plan':
            old_member = next(m for m in old_monthly['members'] if token in m['name'].lower())
            old_native = member_native(old_member)
        else:
            old_native = old_drugs[label]['inner']
        exact = native['bytes'] == old_native['bytes'] and native['sha256'] == old_native['sha256']
        bridge.append({'table': label, 'quarterly': native, 'held_monthly': old_native, 'exact_native_bytes_agree': exact})
        if not exact:
            raise ValueError('Snapshot bridge changed; explicit reconciliation is required')
    write(out / 'snapshot-bridge.json', bridge)
    con = sqlite3.connect(out / 'inventory.sqlite3')
    con.executescript('''
        CREATE TABLE plans(offering_id TEXT PRIMARY KEY,formulary_id TEXT,payload TEXT);
        CREATE TABLE prices(source_ordinal INTEGER PRIMARY KEY,offering_id TEXT,contract_id TEXT,
            plan_id TEXT,segment_id TEXT,ndc TEXT,days_supply INTEGER,unit_cost_usd_1e4 INTEGER,
            source_unit_cost TEXT,raw_line BLOB,disposition TEXT);
        CREATE TABLE formulary_pairs(offering_id TEXT,ndc TEXT,source_ordinal INTEGER,
            PRIMARY KEY(offering_id,ndc));
    ''')
    con.executemany('INSERT INTO plans VALUES(?,?,?)', [(k, p['formulary_id'], json.dumps(p, sort_keys=True)) for k, p in sorted(plans.items())])
    old = sqlite3.connect('file:' + str(L05 / 'inventory.sqlite3') + '?mode=ro', uri=True)
    formulary_ndcs = {}
    for fid in sorted({p['formulary_id'] for p in plans.values()}):
        formulary_ndcs[fid] = old.execute("SELECT ndc,min(ordinal) FROM drug_rows WHERE table_name='basic' AND formulary_id=? GROUP BY ndc", (fid,)).fetchall()
    for oid, plan in sorted(plans.items()):
        con.executemany('INSERT INTO formulary_pairs VALUES(?,?,?)', [(oid, ndc, ordinal) for ndc, ordinal in formulary_ndcs[plan['formulary_id']]])
    old.close()
    pricing = next(m for m in members if 'pricing' in m['name'].lower())
    if sha(ROOT / pricing['path']) != pricing['sha256']:
        raise ValueError('Price ZIP hash mismatch')
    stats = Counter()
    native_digest = hashlib.sha256()
    queue = []
    with zipfile.ZipFile(ROOT / pricing['path']) as archive:
        infos = [i for i in archive.infolist() if not i.is_dir()]
        if len(infos) != 1:
            raise ValueError('Expected one price table')
        info = infos[0]
        with archive.open(info) as raw, (out / 'prices-native.psv.gz').open('wb') as compressed:
            with gzip.GzipFile(filename='', fileobj=compressed, mode='wb', mtime=0, compresslevel=1) as selected:
                header = raw.readline()
                native_digest.update(header)
                if header.rstrip(b'\r\n').decode('ascii').split('|') != COLUMNS:
                    raise ValueError('Unknown price header')
                selected.write(b'SOURCE_ORDINAL|' + header)
                for ordinal, line in enumerate(raw, 2):
                    native_digest.update(line)
                    stats['national_rows'] += 1
                    if line.count(b'|') != 5:
                        raise ValueError('Malformed national row at ' + str(ordinal))
                    parts = line.rstrip(b'\r\n').split(b'|')
                    oid = wanted_bytes.get(tuple(parts[:3]))
                    if not oid:
                        stats['outside_scope_rows'] += 1
                        continue
                    stats['scoped_rows'] += 1
                    contract, plan, segment, ndc, days, cost = [p.decode('ascii') for p in parts]
                    reasons = []
                    if not re.fullmatch(r'\d{11}', ndc):
                        reasons.append('invalid_ndc')
                    day_value = int(days) if days in ('30', '60', '90') else None
                    if day_value is None:
                        reasons.append('unsupported_days_supply')
                    price_value = None
                    try:
                        value = Decimal(cost)
                        scaled = value * 10000
                        if not value.is_finite() or value < 0 or scaled != scaled.to_integral_value() or scaled > 9223372036854775807:
                            raise InvalidOperation
                        price_value = int(scaled)
                    except (InvalidOperation, ValueError):
                        reasons.append('invalid_unit_cost')
                    disposition = ';'.join(reasons) if reasons else 'published_average'
                    stats['quarantined_rows' if reasons else 'valid_scoped_rows'] += 1
                    queue.append((ordinal, oid, contract, plan, segment, ndc, day_value,
                                  price_value, cost, line, disposition))
                    selected.write(str(ordinal).encode('ascii') + b'|' + line)
                    if len(queue) >= 5000:
                        con.executemany('INSERT INTO prices VALUES(?,?,?,?,?,?,?,?,?,?,?)', queue)
                        queue.clear()
                    if stats['national_rows'] % 5_000_000 == 0:
                        print(dict(stats), flush=True)
                if queue:
                    con.executemany('INSERT INTO prices VALUES(?,?,?,?,?,?,?,?,?,?,?)', queue)
        native = {'name': info.filename, 'bytes': info.file_size, 'sha256': native_digest.hexdigest()}
    con.executescript('CREATE INDEX price_key ON prices(offering_id,ndc,days_supply); CREATE INDEX price_ndc ON prices(ndc);')
    con.commit()
    con.execute("CREATE TEMP TABLE priced_pairs AS SELECT DISTINCT offering_id,ndc FROM prices WHERE disposition='published_average'")
    con.execute('CREATE INDEX temp.price_pair_key ON priced_pairs(offering_id,ndc)')
    plan_coverage = []
    for oid, p in sorted(plans.items()):
        counts = dict(con.execute('SELECT days_supply,count(*) FROM prices WHERE offering_id=? AND disposition=? GROUP BY days_supply', (oid, 'published_average')))
        expected = con.execute('SELECT count(*) FROM formulary_pairs WHERE offering_id=?', (oid,)).fetchone()[0]
        matched = con.execute('SELECT count(*) FROM formulary_pairs f JOIN priced_pairs p USING(offering_id,ndc) WHERE f.offering_id=?', (oid,)).fetchone()[0]
        plan_coverage.append({'offering_id': oid, 'name': p['name'], 'kind': p['kind'],
            'formulary_id': p['formulary_id'], 'published_rows': sum(counts.values()),
            'rows_by_days_supply': {str(k): v for k, v in counts.items()},
            'formulary_ndc_pairs': expected, 'formulary_ndc_pairs_with_any_price': matched,
            'formulary_ndc_pairs_without_any_price': expected - matched,
            'price_rows_present': bool(counts), 'personal_store_price_supported': False})
    missing = [{'offering_id': oid, 'ndc': ndc} for oid, ndc in con.execute('SELECT f.offering_id,f.ndc FROM formulary_pairs f LEFT JOIN priced_pairs p USING(offering_id,ndc) WHERE p.ndc IS NULL ORDER BY f.offering_id,f.ndc')]
    price_only = con.execute('SELECT count(*) FROM priced_pairs p LEFT JOIN formulary_pairs f USING(offering_id,ndc) WHERE f.ndc IS NULL').fetchone()[0]
    duplicates = con.execute('SELECT count(*) FROM (SELECT 1 FROM prices GROUP BY offering_id,ndc,days_supply HAVING count(*)>1)').fetchone()[0]
    conflicts = con.execute('SELECT count(*) FROM (SELECT 1 FROM prices GROUP BY offering_id,ndc,days_supply HAVING count(distinct source_unit_cost)>1)').fetchone()[0]
    zero = con.execute("SELECT count(*) FROM prices WHERE disposition='published_average' AND unit_cost_usd_1e4=0").fetchone()[0]
    con.close()
    coverage = {'schema': 'l06-published-price-coverage/1', 'year': 2026, 'target_plans': len(plans),
        'plans_with_price_rows': sum(r['price_rows_present'] for r in plan_coverage),
        'source_row_accounting': dict(stats), 'modeled_native_fields': COLUMNS,
        'modeled_source_field_observations': stats['scoped_rows'] * 6,
        'formulary_ndc_pairs': sum(r['formulary_ndc_pairs'] for r in plan_coverage),
        'formulary_ndc_pairs_with_any_price': sum(r['formulary_ndc_pairs_with_any_price'] for r in plan_coverage),
        'formulary_ndc_pairs_without_any_price': len(missing), 'price_only_plan_ndc_pairs': price_only,
        'duplicate_price_keys': duplicates, 'conflicting_price_keys': conflicts, 'zero_price_rows': zero,
        'native_pricing_member': native, 'average_geography': 'In-area retail across each plan service area; not Collier-store-specific',
        'snapshot': 'Q3 2026 release; first posting in September per CMS methodology, not an average of every day in the quarter',
        'missing_60_or_90_day_rows': 'Not automatically a gap; exact product/channel supply applicability is not evaluated here',
        'supplemental_excluded_rows': 'Held L05 supplemental rows remain visible separately. The basic-formulary price completeness denominator does not assert their coverage or prices.',
        'dispensing_fees': 'Native UNIT_COST retained without adding or inferring any pharmacy fee; no beneficiary fill-total calculation',
        'consumer_release_enabled': False, 'personal_calculator_implemented': False}
    write(out / 'coverage.json', coverage)
    write(out / 'plan-coverage.json', plan_coverage)
    write(out / 'missing-formulary-prices.json', missing)
    write(out / 'scope.json', {'year': 2026, 'county_fips': '12021', 'PDP_region': '11',
        'population': 'Existing 61 Collier MA-PD and 10 Florida individual PDP identities',
        'claim': 'Published average drug unit-cost source collection',
        'not_implemented': ['Personal/store-specific estimates', 'Beneficiary payment calculation', 'Annual totals', 'Ranking', 'UI', 'Source acceptance'],
        'owner_authorization': 'Yes, go out to collect for 1.', 'authorization_date': '2026-10-27'})
    inputs = [acquisition / 'source-manifest.json', L05 / 'plans.json', L05 / 'source-members.json',
              L05 / 'manifest.json', ROOT / 'docs/data/l06-drug-costs-2026-10-27/cms-quarterly-metadata-check.json']
    files = {p.name: sha(p) for p in out.iterdir() if p.is_file()}
    code = {str(p.relative_to(ROOT)): sha(p) for p in [Path(__file__).resolve(), ROOT / 'cms-slice/scripts/l06_acquire.py', ROOT / 'cms-slice/scripts/l06_validate.py']}
    write(out / 'manifest.json', {'schema': 'l06-published-average-collection/1',
        'package_id': 'L06-PUBLISHED-AVERAGE-COLLIER-FL-2026-' + out.name,
        'files_sha256': files, 'code_sha256': code,
        'input_sha256': {str(p.relative_to(ROOT)): sha(p) for p in inputs},
        'price_source': pricing, 'human_acceptance': None, 'consumer_release_enabled': False})
    print(json.dumps(coverage, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--acquisition', type=Path, default=BASE / 'acquisition-r1')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    build(args.acquisition.resolve(), args.out.resolve())
