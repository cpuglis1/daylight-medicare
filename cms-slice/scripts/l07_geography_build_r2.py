#!/usr/bin/env python3
"""Compose native networks with dated identity and county-location evidence."""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3

from l04_acquire import write
from l07_acquire import file_hash
from l07_identity_build import address_key

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l07-pharmacy-networks-2026-10-27'
COUNTIES = {'12021': 'Collier', '12071': 'Lee', '12051': 'Hendry', '12087': 'Monroe'}


def collect_evidence(base):
    batch = json.loads((base / 'geography-acquisition-r1/source-manifest.json').read_text())
    evidence = {}
    for part in batch['batches']:
        receipt = part['output']
        if file_hash(ROOT / receipt['path']) != receipt['sha256']: raise ValueError('Census output changed')
        for ordinal, row in enumerate(csv.reader(io.StringIO((ROOT / receipt['path']).read_text())), 1):
            item = {'address_id': row[0], 'status': row[2], 'source': {**receipt, 'record_ordinal': ordinal},
                    'basis': 'Census batch address-range geography'}
            if row[2] == 'Match' and len(row) == 12:
                item.update(county_fips=row[8] + row[9], coordinates=row[5], match_type=row[3], matched_address=row[4])
            evidence[row[0]] = item
    followup = json.loads((base / 'geography-followup-r2/source-manifest.json').read_text())
    for receipt in followup['requests']:
        if file_hash(ROOT / receipt['path']) != receipt['sha256']: raise ValueError('Census followup changed')
        matches = json.loads((ROOT / receipt['path']).read_text()).get('result', {}).get('addressMatches', [])
        if len(matches) == 1 and len(matches[0].get('geographies', {}).get('Counties', [])) == 1:
            county = matches[0]['geographies']['Counties'][0]
            evidence[receipt['address_id']] = {'address_id': receipt['address_id'], 'status': 'Match',
                'county_fips': county['STATE'] + county['COUNTY'], 'county_name': county['NAME'],
                'coordinates': matches[0].get('coordinates'), 'matched_address': matches[0]['matchedAddress'],
                'source': receipt, 'basis': 'Census structured-address geography; suite retained in identity source'}
    for decision in json.loads((base / 'geography-county-r2/decisions.json').read_text()):
        if evidence.get(decision['address_id'], {}).get('status') != 'Match':
            evidence[decision['address_id']] = {'address_id': decision['address_id'], 'status': 'Match',
                'county_fips': decision['county_fips'], 'county_name': decision['county_name'],
                'source': decision['source'], 'feature_indexes': decision['feature_indexes'],
                'route_evidence': decision['route_evidence'], 'basis': decision['basis']}
    return evidence


def build(out):
    out.mkdir()
    identities = {}
    with gzip.open(BASE / 'identity-build-r1/identities.jsonl.gz', 'rt') as f:
        for line in f:
            row = json.loads(line); identities[row['npi']] = row
    joins = json.loads((BASE / 'identity-build-r1/network-location-joins.json').read_text())
    geo_inputs = {r['address_id']: r for r in json.loads((BASE / 'identity-build-r1/florida-geography-input.json').read_text())}
    evidence = collect_evidence(BASE)
    records, exceptions, individual_names = [], [], []
    for npi, item in identities.items():
        if item['enumeration_type'] == 'NPI-1':
            native = json.loads((ROOT / item['source']['path']).read_text())['results'][item['source']['result_index']]
            names = {f: native.get('basic', {}).get(f) for f in ['first_name', 'middle_name', 'last_name', 'name_prefix', 'name_suffix']}
            individual_names.append({'npi': npi, 'individual_name': names, 'source': item['source']})
    for join in joins:
        item = identities.get(join['npi']); candidates = []
        if item:
            for group in item['locations']:
                address = group[0]
                if list(address_key(address)) not in join['candidate_location_keys']: continue
                address_id = hashlib.sha256(json.dumps(address_key(address)).encode()).hexdigest()[:20]
                geography = evidence.get(address_id) if address['state'] == 'FL' else None
                candidates.append({'address_id': address_id, 'registry_address': address,
                                   'geography': geography,
                                   'source_state': 'Florida' if address['state'] == 'FL' else 'outside_Florida_as_registered'})
        category, county = 'identity_or_location_unresolved', None
        if join['status'] == 'unique_zip_matched_location' and len(candidates) == 1:
            candidate = candidates[0]; geography = candidate['geography']
            if candidate['registry_address']['state'] != 'FL':
                category = 'outside_Florida_as_registered'
            elif geography and geography['status'] == 'Match' and geography.get('county_fips', '').startswith('12'):
                county = geography['county_fips']; category = COUNTIES.get(county, 'other_Florida_county')
            else:
                category = 'Florida_county_unresolved'
        record = {**join, 'scope_group': category, 'county_fips': county, 'candidate_locations': candidates,
                  'identity_source': item['source'] if item else None}
        records.append(record)
        if category in ['identity_or_location_unresolved', 'Florida_county_unresolved']:
            exceptions.append(record)
    with gzip.open(out / 'locations.jsonl.gz', 'wt', encoding='utf-8') as f:
        for r in records: f.write(json.dumps(r, sort_keys=True) + '\n')
    write(out / 'individual-registry-names.json', individual_names)
    write(out / 'exceptions.json', exceptions)
    write(out / 'geography-evidence.json', evidence)
    unresolved_geo = [a for key, a in geo_inputs.items() if evidence.get(key, {}).get('status') != 'Match']
    write(out / 'unresolved-Florida-geography.json', unresolved_geo)
    con = sqlite3.connect(out / 'inventory.sqlite3')
    con.execute('CREATE TABLE locations(npi TEXT,network_zip TEXT,identity_status TEXT,scope_group TEXT,county_fips TEXT,record_json TEXT,PRIMARY KEY(npi,network_zip))')
    con.executemany('INSERT INTO locations VALUES(?,?,?,?,?,?)', [(r['npi'], r['network_zip'], r['status'], r['scope_group'], r['county_fips'], json.dumps(r, sort_keys=True)) for r in records])
    con.execute("ATTACH DATABASE ? AS native", ('file:' + str(BASE / 'build-r1/inventory.sqlite3') + '?mode=ro',))
    coverage_by_plan = con.execute('SELECT n.offering_id,l.scope_group,COUNT(*) FROM native.network n LEFT JOIN locations l ON n.pharmacy_npi=l.npi AND n.PHARMACY_ZIPCODE=l.network_zip GROUP BY n.offering_id,l.scope_group').fetchall()
    write(out / 'plan-location-coverage.json', [dict(zip(['offering_id', 'scope_group', 'network_rows'], r)) for r in coverage_by_plan])
    con.commit(); con.close()
    local = [r for r in records if r['scope_group'] == 'Collier']
    write(out / 'Collier-pharmacies.json', [{'npi': r['npi'], 'network_zip': r['network_zip'],
        'organization_name': identities[r['npi']]['organization_name'], 'county_fips': r['county_fips'],
        'address': r['candidate_locations'][0]['registry_address'],
        'geography_evidence': r['candidate_locations'][0]['geography'], 'identity_source': r['identity_source']} for r in local])
    coverage = {'schema': 'l07-location-coverage/1', 'network_NPI_zip_pairs': len(records),
                'scope_groups': dict(Counter(r['scope_group'] for r in records)),
                'identity_join_states': dict(Counter(r['status'] for r in records)),
                'Florida_candidate_addresses': len(geo_inputs), 'Florida_candidate_addresses_geographically_supported': len(geo_inputs) - len(unresolved_geo),
                'unresolved_Florida_candidate_geography': len(unresolved_geo), 'individual_registry_name_records': len(individual_names),
                'ZIP341_unresolved_identity_or_county': sum(r['network_zip'].startswith('341') and r['scope_group'] in ['identity_or_location_unresolved', 'Florida_county_unresolved'] for r in records),
                'consumer_release_enabled': False, 'historical_address_and_live_operation_confirmed': False}
    write(out / 'coverage.json', coverage)
    inputs = [BASE / 'build-r1/manifest.json', BASE / 'identity-build-r1/manifest.json',
              BASE / 'geography-acquisition-r1/source-manifest.json', BASE / 'geography-followup-r2/source-manifest.json',
              BASE / 'geography-county-r2/decisions.json', BASE / 'geography-county-r2/route41-evidence.json']
    write(out / 'manifest.json', {'schema': 'l07-composite-location-build/1',
          'input_sha256': {str(p.relative_to(ROOT)): file_hash(p) for p in inputs},
          'code_sha256': {str(Path(__file__).resolve().relative_to(ROOT)): file_hash(Path(__file__).resolve())},
          'files_sha256': {p.name: file_hash(p) for p in out.iterdir() if p.is_file()},
          'consumer_release_enabled': False, 'human_acceptance': None})
    print(json.dumps(coverage, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--out', type=Path, default=BASE / 'location-build-r2')
    build(p.parse_args().out.resolve())
