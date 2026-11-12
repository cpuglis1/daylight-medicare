#!/usr/bin/env python3
"""Exact-NPI pharmacy identity/address joins with explicit ambiguity states."""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from l04_acquire import write
from l07_acquire import file_hash

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l07-pharmacy-networks-2026-10-27'
ADDRESS_FIELDS = ['address_1', 'address_2', 'city', 'state', 'postal_code', 'country_code', 'telephone_number']


def address_key(address):
    return tuple(re.sub(r'[^A-Z0-9]', '', str(address.get(f, '')).upper())
                 for f in ['address_1', 'address_2', 'city', 'state']) + (address.get('postal_code', '')[:5],)


def addresses(result):
    candidates = []
    for index, a in enumerate(result.get('addresses', [])):
        if a.get('address_purpose') == 'LOCATION':
            candidates.append({'origin': 'addresses', 'index': index,
                               **{f: a.get(f, '') for f in ADDRESS_FIELDS}})
    for index, a in enumerate(result.get('practiceLocations', [])):
        candidates.append({'origin': 'practiceLocations', 'index': index,
                           **{f: a.get(f, '') for f in ADDRESS_FIELDS}})
    # Retain every source location; exact normalized keys only group duplicate representations.
    groups = defaultdict(list)
    for address in candidates:
        groups[address_key(address)].append(address)
    return [group for key, group in sorted(groups.items())]


def disposition(source_zip, identity):
    if identity is None:
        return 'identity_missing', []
    if identity['registry_status'] != 'A':
        return 'identity_inactive_or_unknown', []
    if not re.fullmatch(r'\d{5}', source_zip):
        return 'network_zip_unpublished', identity['locations']
    candidates = [group for group in identity['locations'] if group[0]['postal_code'][:5] == source_zip]
    if len(candidates) == 1:
        return 'unique_zip_matched_location', candidates
    if len(candidates) > 1:
        return 'multiple_zip_matched_locations', candidates
    return ('network_registry_zip_mismatch', identity['locations']) if identity['locations'] else ('no_practice_location', [])


def build(out, acquisition, keys_file):
    out.mkdir()
    manifest_path = acquisition / 'source-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    keys = json.loads(keys_file.read_text()); wanted = {k['npi'] for k in keys}
    chosen, differing, payload_errors, requests, all_returned = {}, Counter(), [], 0, set()
    for receipt in manifest['reused'] + manifest['requests']:
        path = ROOT / receipt['path']
        if file_hash(path) != receipt['sha256']:
            raise ValueError('Registry source hash mismatch')
        payload = json.loads(path.read_text()); requests += 1
        if payload.get('Errors'):
            payload_errors.append({'url': receipt['requested_url'], 'errors': payload['Errors']})
            continue
        if payload['result_count'] != len(payload.get('results', [])):
            raise ValueError('Registry result count mismatch')
        exact = '&number=' in receipt['requested_url'] or '?number=' in receipt['requested_url']
        for ordinal, r in enumerate(payload.get('results', [])):
            npi = str(r['number']); all_returned.add(npi)
            if npi not in wanted:
                continue
            rank = (int(exact), receipt.get('retrieved_at_utc', ''))
            locs = addresses(r)
            identity = {'npi': npi, 'organization_name': r.get('basic', {}).get('organization_name'),
                        'other_names': r.get('other_names', []), 'enumeration_type': r.get('enumeration_type'),
                        'registry_status': r.get('basic', {}).get('status'),
                        'last_updated': r.get('basic', {}).get('last_updated'),
                        'enumeration_date': r.get('basic', {}).get('enumeration_date'),
                        'locations': locs,
                        'source': {'path': receipt['path'], 'sha256': receipt['sha256'], 'result_index': ordinal,
                                   'requested_url': receipt['requested_url'], 'retrieved_at_utc': receipt.get('retrieved_at_utc')}}
            if npi in chosen:
                previous = chosen[npi][1]
                if any(previous[k] != identity[k] for k in identity if k != 'source'):
                    differing[npi] += 1
            if npi not in chosen or rank >= chosen[npi][0]:
                chosen[npi] = rank, identity
    identities = {n: v[1] for n, v in chosen.items()}
    joins, geo = [], {}
    for key in keys:
        npi = key['npi']; identity = identities.get(npi)
        for source_zip in key['source_zips']:
            state, candidates = disposition(source_zip, identity)
            joins.append({'npi': npi, 'network_zip': source_zip, 'status': state,
                          'candidate_location_keys': [list(address_key(g[0])) for g in candidates]})
            for group in candidates:
                a = group[0]
                # All Florida candidate locations, including ambiguous candidates, receive geographic research.
                if a['state'] == 'FL':
                    gkey = hashlib.sha256(json.dumps(address_key(a)).encode()).hexdigest()[:20]
                    geo[gkey] = {'address_id': gkey, 'npi': npi, 'network_zip': source_zip,
                                 'identity_join_status': state, **{f: a[f] for f in ADDRESS_FIELDS}}
    with gzip.open(out / 'identities.jsonl.gz', 'wt', encoding='utf-8', compresslevel=6) as f:
        for identity in identities.values():
            f.write(json.dumps(identity, sort_keys=True) + '\n')
    write(out / 'network-location-joins.json', joins)
    write(out / 'florida-geography-input.json', list(geo.values()))
    missing = [k for k in keys if k['npi'] not in identities]
    write(out / 'missing-identities.json', missing)
    write(out / 'differing-observations.json', dict(differing))
    write(out / 'query-errors.json', payload_errors)
    coverage = {'schema': 'l07-identity-coverage/1', 'target_npis': len(wanted),
                'resolved_npis': len(identities), 'missing_npis': len(missing),
                'active_npis': sum(i['registry_status'] == 'A' for i in identities.values()),
                'NPI_network_zip_pairs': len(joins), 'location_dispositions': dict(Counter(j['status'] for j in joins)),
                'Florida_candidate_addresses': len(geo), 'source_responses_checked': requests,
                'discovery_distinct_npis': len(all_returned), 'rejected_discovery_queries': len(payload_errors),
                'different_snapshot_npis': len(differing),
                'boundary': 'Dated registry identity, not historical address, current operation, licensure or live network proof'}
    write(out / 'coverage.json', coverage)
    write(out / 'manifest.json', {'schema': 'l07-identity-build/1',
          'input_sha256': {str(manifest_path.relative_to(ROOT)): file_hash(manifest_path),
                           str(keys_file.relative_to(ROOT)): file_hash(keys_file)},
          'code_sha256': {str(Path(__file__).resolve().relative_to(ROOT)): file_hash(Path(__file__).resolve())},
          'files_sha256': {p.name: file_hash(p) for p in out.iterdir() if p.is_file()},
          'consumer_release_enabled': False, 'human_acceptance': None})
    print(json.dumps(coverage, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=BASE / 'identity-build-r1')
    parser.add_argument('--acquisition', type=Path, default=BASE / 'identity-acquisition-r1')
    parser.add_argument('--keys', type=Path, default=BASE / 'build-r1/pharmacy-keys.json')
    args = parser.parse_args()
    build(args.out.resolve(), args.acquisition.resolve(), args.keys.resolve())
