#!/usr/bin/env python3
"""Retain public NPPES pharmacy identity responses, reusing captured lookups."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import string
from urllib.parse import urlencode

from l04_acquire import put, write
from l05_acquire import request
from l07_acquire import file_hash

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l07-pharmacy-networks-2026-10-27'
STATES = 'AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY AS GU MP PR VI FM MH PW AA AE AP'.split()


def acquire(out, exact_keys=None, postal_keys=None):
    if (out / 'SEALED').exists():
        raise ValueError('Identity acquisition sealed; use a new revision')
    out.mkdir(exist_ok=True); (out / 'raw').mkdir(exist_ok=True)
    path = out / 'source-manifest.json'
    manifest = json.loads(path.read_text()) if path.exists() else {
        'schema': 'l07-NPPES-acquisition/1', 'observed_year': 2026,
        'source': 'Official NPPES v2.1 registry; identity does not prove operation/participation',
        'requests': [], 'reused': [], 'completed_searches': [], 'truncated_searches': [],
        'scope': 'Public pharmacy identity and location evidence; exact NPI matching is performed separately'}
    if not manifest['reused']:
        registry_path = ROOT / 'cms-slice/data-sources/demo-sources.json'
        registry = json.loads(registry_path.read_text())['sources']
        for source_id, r in registry.items():
            if 'npiregistry' in r.get('requested_url', '') and 'Pharmacy' in r.get('requested_url', ''):
                raw = ROOT / 'cms-slice/data-sources/raw/demo' / r['sha256']
                if file_hash(raw) != r['sha256']:
                    raise ValueError('Held NPPES source changed')
                manifest['reused'].append({**r, 'path': str(raw.relative_to(ROOT)), 'source_id': source_id})
        probe = out / 'api-probe.json'
        if probe.exists():
            manifest['requests'].append(json.loads(probe.read_text()))
        write(path, manifest)
    cached = {r['requested_url']: r for r in manifest['requests']}

    def fetch(params):
        url = 'https://npiregistry.cms.hhs.gov/api/?' + urlencode(params)
        if url in cached:
            r = cached[url]
            if file_hash(ROOT / r['path']) != r['sha256']:
                raise ValueError('Cached NPPES response changed')
            body = (ROOT / r['path']).read_bytes()
        else:
            body, receipt = request(url, out)
            r = {**put(out, body), **receipt}
            manifest['requests'].append(r); cached[url] = r
            write(path, manifest)
        payload = json.loads(body)
        if payload.get('Errors'):
            raise ValueError('NPPES rejected query: ' + json.dumps(payload['Errors']))
        if payload.get('result_count') != len(payload.get('results', [])):
            raise ValueError('NPPES count mismatch')
        return payload

    def search(state, prefix=''):
        key = state + ':' + prefix
        if key in manifest['completed_searches']:
            return
        full = True
        for skip in range(0, 1200, 200):
            params = {'version': '2.1', 'enumeration_type': 'NPI-2', 'taxonomy_description': 'Pharmacy',
                      'address_purpose': 'LOCATION', 'state': state, 'limit': 200, 'skip': skip}
            if prefix:
                params['organization_name'] = prefix + '*'
            result = fetch(params)
            if result['result_count'] < 200:
                full = False
                break
        if full:
            if key not in manifest['truncated_searches']:
                manifest['truncated_searches'].append(key)
            write(path, manifest)
            if len(prefix) < 8:
                for char in string.ascii_uppercase + string.digits:
                    search(state, prefix + char)
        manifest['completed_searches'].append(key)
        write(path, manifest)
        if not prefix:
            print('NPPES state', state, 'queries', len(manifest['requests']), 'split', full, flush=True)

    def postal_search(prefix):
        key = 'postal:' + prefix
        if key in manifest['completed_searches']:
            return
        full = True
        for skip in range(0, 1200, 200):
            result = fetch({'version': '2.1', 'enumeration_type': 'NPI-2', 'taxonomy_description': 'Pharmacy',
                            'address_purpose': 'LOCATION', 'postal_code': prefix + ('*' if len(prefix) < 5 else ''),
                            'limit': 200, 'skip': skip})
            if result['result_count'] < 200:
                full = False
                break
        if full:
            if key not in manifest['truncated_searches']:
                manifest['truncated_searches'].append(key)
            write(path, manifest)
            if len(prefix) < 5:
                for char in string.digits:
                    postal_search(prefix + char)
        manifest['completed_searches'].append(key)
        write(path, manifest)
        if len(prefix) == 3:
            print('NPPES postal', prefix, 'queries', len(manifest['requests']), flush=True)

    if postal_keys is not None:
        keys = json.loads(postal_keys.read_text())
        prefixes = sorted({z[:3] for k in keys for z in k['source_zips'] if len(z) == 5 and z.isdigit()})
        for prefix in prefixes:
            postal_search(prefix)
        manifest['postal_discovery_completed_at_utc'] = datetime.now(timezone.utc).isoformat()
        manifest['postal_target_key_sha256'] = file_hash(postal_keys)
        write(path, manifest)
    elif exact_keys is None:
        for state in STATES:
            search(state)
        manifest['state_discovery_completed_at_utc'] = datetime.now(timezone.utc).isoformat()
        write(path, manifest)
    else:
        keys = json.loads(exact_keys.read_text())
        seen = set()
        for r in manifest['requests'] + manifest['reused']:
            for result in json.loads((ROOT / r['path']).read_text()).get('results', []):
                seen.add(str(result['number']))
        pending = sorted({p['npi'] for p in keys} - seen)
        print('exact NPI followups', len(pending), flush=True)
        for ordinal, npi in enumerate(pending, 1):
            fetch({'version': '2.1', 'number': npi})
            if ordinal % 100 == 0:
                print('exact NPI', ordinal, '/', len(pending), flush=True)
        manifest['exact_target_key_file'] = str(exact_keys.relative_to(ROOT))
        manifest['exact_target_key_sha256'] = file_hash(exact_keys)
        manifest['exact_followups_completed_at_utc'] = datetime.now(timezone.utc).isoformat()
        write(path, manifest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=BASE / 'identity-acquisition-r1')
    parser.add_argument('--exact-keys', type=Path)
    parser.add_argument('--postal-keys', type=Path)
    args = parser.parse_args()
    acquire(args.out.resolve(), args.exact_keys.resolve() if args.exact_keys else None,
            args.postal_keys.resolve() if args.postal_keys else None)
