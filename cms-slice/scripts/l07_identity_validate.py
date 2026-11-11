#!/usr/bin/env python3
"""Independent source-pointer and address-join audit of every modeled identity."""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l07-pharmacy-networks-2026-10-27'
AF = ['address_1', 'address_2', 'city', 'state', 'postal_code', 'country_code', 'telephone_number']


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''): h.update(b)
    return h.hexdigest()


def canonical(a):
    return [re.sub('[^A-Z0-9]', '', str(a.get(k, '')).upper()) for k in ['address_1', 'address_2', 'city', 'state']] + [a.get('postal_code', '')[:5]]


def check(package, output):
    manifest = json.loads((package / 'manifest.json').read_text()); checks = {}
    for group in ['input_sha256', 'code_sha256']:
        for p, h in manifest[group].items(): checks[group + ':' + p] = sha(ROOT / p) == h
    for p, h in manifest['files_sha256'].items(): checks['output:' + p] = sha(package / p) == h
    if not all(checks.values()): raise ValueError('Identity package changed')
    acquisition_path = next(ROOT / p for p in manifest['input_sha256'] if p.endswith('source-manifest.json'))
    acquisition = json.loads(acquisition_path.read_text())
    receipt_index = defaultdict(list)
    for receipt in acquisition['reused'] + acquisition['requests']:
        receipt_index[receipt['path']].append(receipt)
    by_source, identities = defaultdict(list), {}
    with gzip.open(package / 'identities.jsonl.gz', 'rt') as f:
        for line in f:
            identity = json.loads(line); identities[identity['npi']] = identity
            by_source[identity['source']['path']].append(identity)
    modeled = 0
    for source, group in by_source.items():
        raw_path = ROOT / source
        if sha(raw_path) != group[0]['source']['sha256']: raise ValueError('NPPES payload changed')
        payload = json.loads(raw_path.read_text())
        for item in group:
            if not any(r['sha256'] == item['source']['sha256'] and
                       r['requested_url'] == item['source']['requested_url'] and
                       r.get('retrieved_at_utc') == item['source']['retrieved_at_utc']
                       for r in receipt_index[source]):
                raise ValueError('Identity source URL/date differs from retained receipt')
            native = payload['results'][item['source']['result_index']]
            expected = {'npi': str(native['number']), 'organization_name': native.get('basic', {}).get('organization_name'),
                        'other_names': native.get('other_names', []), 'enumeration_type': native.get('enumeration_type'),
                        'registry_status': native.get('basic', {}).get('status'),
                        'last_updated': native.get('basic', {}).get('last_updated'),
                        'enumeration_date': native.get('basic', {}).get('enumeration_date')}
            for k, v in expected.items():
                if item[k] != v: raise ValueError('Identity field differs from exact source result: ' + k)
                modeled += 1
            observed = []
            for group_locations in item['locations']:
                if not group_locations: raise ValueError('Empty location group')
                for address in group_locations:
                    pointer = native[address['origin']][address['index']]
                    if address['origin'] == 'addresses' and pointer.get('address_purpose') != 'LOCATION':
                        raise ValueError('Mailing address substituted for practice location')
                    for k in AF:
                        if address[k] != pointer.get(k, ''): raise ValueError('Address/phone source mismatch')
                        modeled += 1
                    if canonical(address) != canonical(group_locations[0]): raise ValueError('Different locations collapsed')
                    observed.append((address['origin'], address['index']))
            expected_pointers = [('addresses', i) for i, a in enumerate(native.get('addresses', [])) if a.get('address_purpose') == 'LOCATION']
            expected_pointers += [('practiceLocations', i) for i in range(len(native.get('practiceLocations', [])))]
            if sorted(observed) != sorted(expected_pointers): raise ValueError('Source practice address omitted or duplicated')
    joins = json.loads((package / 'network-location-joins.json').read_text())
    keys_path = next(ROOT / p for p in manifest['input_sha256'] if p.endswith('pharmacy-keys.json'))
    keys = json.loads(keys_path.read_text()); denominator = {(k['npi'], z) for k in keys for z in k['source_zips']}
    if {(r['npi'], r['network_zip']) for r in joins} != denominator or len(joins) != len(denominator):
        raise ValueError('Network identity/location denominator changed')
    for row in joins:
        item = identities.get(row['npi']); candidates = []
        if item is None: state = 'identity_missing'
        elif item['registry_status'] != 'A': state = 'identity_inactive_or_unknown'
        elif not re.fullmatch(r'\d{5}', row['network_zip']):
            state = 'network_zip_unpublished'; candidates = item['locations']
        else:
            matches = [g for g in item['locations'] if g[0]['postal_code'][:5] == row['network_zip']]
            if len(matches) == 1: state = 'unique_zip_matched_location'; candidates = matches
            elif len(matches) > 1: state = 'multiple_zip_matched_locations'; candidates = matches
            elif item['locations']: state = 'network_registry_zip_mismatch'; candidates = item['locations']
            else: state = 'no_practice_location'
        if row['status'] != state or row['candidate_location_keys'] != [canonical(g[0]) for g in candidates]:
            raise ValueError('Unsupported identity/location resolution')
    missing = json.loads((package / 'missing-identities.json').read_text())
    checks['missing_identity_list_exact'] = {k['npi'] for k in missing} == {k['npi'] for k in keys} - set(identities)
    checks['all_identity_address_and_phone_fields_match'] = True
    checks['all_66248_network_NPI_zip_pairs_accounted'] = len(joins) == 66248
    checks['no_mailing_or_different_location_substitution'] = True
    geography_expected = {}
    join_index = {(r['npi'], r['network_zip']): r for r in joins}
    for key in keys:
        npi = key['npi']; item = identities.get(npi)
        if item is None: continue
        for zipcode in key['source_zips']:
            row = join_index[npi, zipcode]
            for group in item['locations']:
                address = group[0]
                if canonical(address) not in row['candidate_location_keys'] or address['state'] != 'FL': continue
                address_id = hashlib.sha256(json.dumps(canonical(address)).encode()).hexdigest()[:20]
                geography_expected[address_id] = {'address_id': address_id, 'npi': npi, 'network_zip': zipcode,
                    'identity_join_status': row['status'], **{f: address[f] for f in AF}}
    supplied_geography = json.loads((package / 'florida-geography-input.json').read_text())
    checks['all_Florida_geography_inputs_reconstructed'] = {r['address_id']: r for r in supplied_geography} == geography_expected
    exact_receipts = {r['requested_url'].split('&number=')[-1]: r for r in acquisition['requests'] if '&number=' in r['requested_url']}
    checks['every_missing_identity_has_exact_zero_result'] = all(
        k['npi'] in exact_receipts and json.loads((ROOT / exact_receipts[k['npi']]['path']).read_text()).get('result_count') == 0
        for k in missing)
    checks['all_source_URLs_and_observation_dates_reconciled'] = True
    result = {'schema': 'l07-independent-identity-validation/1', 'passed': all(checks.values()),
              'checks': checks, 'resolved_npis_checked': len(identities), 'network_NPI_zip_pairs_checked': len(joins),
              'modeled_source_field_observations_checked': modeled, 'unexplained_field_mismatches': 0,
              'location_states': dict(Counter(r['status'] for r in joins)),
              'manifest_sha256': sha(package / 'manifest.json'),
              'limits': 'Exact selected registry observations and deterministic joins; missing identities and ambiguous/historical locations remain explicit'}
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n'); print(json.dumps(result, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--package', type=Path, default=BASE / 'identity-build-r1')
    p.add_argument('--out', type=Path, default=BASE / 'identity-build-r1-validation.json'); args = p.parse_args()
    check(args.package.resolve(), args.out.resolve())
