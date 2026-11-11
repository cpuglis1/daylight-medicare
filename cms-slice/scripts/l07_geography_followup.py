#!/usr/bin/env python3
"""Retain Census structured-address followups for nonmatching public pharmacies."""
import argparse
import csv
import io
import json
from pathlib import Path
import re
from urllib.parse import urlencode

from l04_acquire import put, write
from l05_acquire import request
from l07_acquire import file_hash

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l07-pharmacy-networks-2026-10-27'


def collect(out, inputs, batch_manifest, reuse=None):
    if (out / 'SEALED').exists():
        raise ValueError('Followup acquisition sealed')
    out.mkdir(exist_ok=True); (out / 'raw').mkdir(exist_ok=True)
    path = out / 'source-manifest.json'
    manifest = json.loads(path.read_text()) if path.exists() else {
        'schema': 'l07-Census-followup/1', 'input_path': str(inputs.relative_to(ROOT)),
        'input_sha256': file_hash(inputs), 'batch_manifest': str(batch_manifest.relative_to(ROOT)),
        'batch_manifest_sha256': file_hash(batch_manifest), 'requests': [], 'completed_address_ids': []}
    if reuse and not manifest['requests']:
        if (reuse.parent / 'SEALED').read_text().strip() != file_hash(reuse):
            raise ValueError('Reused followup acquisition changed')
        old = json.loads(reuse.read_text())
        manifest['requests'] = old['requests']
        manifest['completed_address_ids'] = old['completed_address_ids']
        manifest['reused_manifest'] = {'path': str(reuse.relative_to(ROOT)), 'sha256': file_hash(reuse)}
        write(path, manifest)
    batches = json.loads(batch_manifest.read_text()); statuses = {}
    for batch in batches['batches']:
        for row in csv.reader(io.StringIO((ROOT / batch['output']['path']).read_text())):
            statuses[row[0]] = row[2]
    rows = [r for r in json.loads(inputs.read_text()) if statuses.get(r['address_id']) != 'Match']
    for ordinal, a in enumerate(rows, 1):
        if a['address_id'] in manifest['completed_address_ids']: continue
        street = re.split(r'\s+(?:SUITE|STE|UNIT|APT|BLDG|#)\b', a['address_1'], flags=re.I)[0]
        for variant, zipcode in [('structured_street', a['postal_code'][:5]), ('city_state_only', '')]:
            params = {'street': street, 'city': a['city'], 'state': a['state'], 'zip': zipcode,
                      'benchmark': '4', 'vintage': '4', 'format': 'json'}
            url = 'https://geocoding.geo.census.gov/geocoder/geographies/address?' + urlencode(params)
            existing = next((r for r in manifest['requests'] if r['requested_url'] == url), None)
            if existing:
                b = (ROOT / existing['path']).read_bytes(); receipt = existing
            else:
                b, receipt = request(url, out)
                receipt = {'address_id': a['address_id'], 'variant': variant, **put(out, b), **receipt}
                manifest['requests'].append(receipt); write(path, manifest)
            matches = json.loads(b).get('result', {}).get('addressMatches', [])
            if len(matches) == 1 and len(matches[0].get('geographies', {}).get('Counties', [])) == 1:
                break
        manifest['completed_address_ids'].append(a['address_id']); write(path, manifest)
        if ordinal % 50 == 0:
            print('Census followup', ordinal, '/', len(rows), flush=True)
    write(path, manifest); (out / 'SEALED').write_text(file_hash(path) + '\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, default=BASE / 'geography-followup-r1')
    p.add_argument('--inputs', type=Path, default=BASE / 'identity-build-preliminary/florida-geography-input.json')
    p.add_argument('--batch-manifest', type=Path, default=BASE / 'geography-acquisition-preliminary/source-manifest.json')
    p.add_argument('--reuse', type=Path)
    a = p.parse_args(); collect(a.out.resolve(), a.inputs.resolve(), a.batch_manifest.resolve(), a.reuse.resolve() if a.reuse else None)
