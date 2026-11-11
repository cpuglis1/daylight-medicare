#!/usr/bin/env python3
"""Geocode public Florida pharmacy practice addresses using Census batches."""
import argparse
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid

from l04_acquire import put, write
from l05_acquire import request
from l07_acquire import file_hash

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l07-pharmacy-networks-2026-10-27'
URL = 'https://geocoding.geo.census.gov/geocoder/geographies/addressbatch'


def collect(out, inputs, reuse=None):
    if (out / 'SEALED').exists():
        raise ValueError('Geography acquisition is sealed')
    out.mkdir(exist_ok=True); (out / 'raw').mkdir(exist_ok=True)
    rows = json.loads(inputs.read_text())
    source = {'schema': 'l07-Census-geography-acquisition/1', 'input_path': str(inputs.relative_to(ROOT)),
              'input_sha256': file_hash(inputs), 'benchmark': '4', 'vintage': '4', 'metadata': [], 'batches': [],
              'limits': 'Public pharmacy addresses only. Interpolated address geography does not prove business operation or network participation.'}
    known_ids = set()
    if reuse:
        if (reuse.parent / 'SEALED').read_text().strip() != file_hash(reuse):
            raise ValueError('Reused Census acquisition changed')
        prior = json.loads(reuse.read_text())
        source['reused_manifest'] = {'path': str(reuse.relative_to(ROOT)), 'sha256': file_hash(reuse)}
        for batch in prior['batches']:
            if file_hash(ROOT / batch['output']['path']) != batch['output']['sha256']:
                raise ValueError('Reused Census output changed')
            known_ids.update(r[0] for r in csv.reader(io.StringIO((ROOT / batch['output']['path']).read_text())))
            source['batches'].append({**batch, 'reused': True})
    rows = [r for r in rows if r['address_id'] not in known_ids]
    for url in ['https://geocoding.geo.census.gov/geocoder/benchmarks',
                'https://geocoding.geo.census.gov/geocoder/vintages?benchmark=4']:
        body, receipt = request(url, out)
        source['metadata'].append({**put(out, body), **receipt})
    for offset in range(0, len(rows), 9000):
        group = rows[offset:offset + 9000]
        text = io.StringIO(newline=''); writer = csv.writer(text, lineterminator='\n')
        for a in group:
            writer.writerow([a['address_id'], ' '.join(x for x in [a['address_1'], a['address_2']] if x),
                             a['city'], a['state'], a['postal_code'][:5]])
        native = text.getvalue().encode(); input_receipt = put(out, native)
        boundary = 'DaylightPublicPharmacy' + uuid.uuid4().hex
        body = bytearray()
        for name, value in [('benchmark', '4'), ('vintage', '4')]:
            body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        body.extend(f'--{boundary}\r\nContent-Disposition: form-data; name="addressFile"; filename="public-pharmacies.csv"\r\nContent-Type: text/csv\r\n\r\n'.encode())
        body.extend(native); body.extend(f'\r\n--{boundary}--\r\n'.encode())
        req = Request(URL, data=bytes(body), headers={'User-Agent': 'Daylight published pharmacy reference research',
                      'Content-Type': 'multipart/form-data; boundary=' + boundary})
        try:
            with urlopen(req, timeout=300) as response:
                if response.url != URL:
                    raise ValueError('Unexpected Census batch redirect')
                result = response.read(30_000_001)
                if len(result) > 30_000_000:
                    raise ValueError('Unexpected Census response size')
                receipt = {'requested_url': URL, 'final_url': response.url, 'http_status': response.status,
                           'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
                           'headers': {k.lower(): v for k, v in response.headers.items() if k.lower() in
                                       {'content-type', 'content-length', 'last-modified', 'etag'}}}
        except HTTPError as exc:
            if exc.code in (401, 403, 429):
                write(out / 'stopped-hosts.json', ['geocoding.geo.census.gov'])
            raise
        parsed = list(csv.reader(io.StringIO(result.decode('utf-8-sig'))))
        if len(parsed) != len(group) or {r[0] for r in parsed} != {r['address_id'] for r in group}:
            put(out, result)
            raise ValueError('Census response omitted/duplicated submitted addresses')
        source['batches'].append({'rows': len(group), 'input': input_receipt, 'output': {**put(out, result), **receipt}})
        write(out / 'source-manifest.json', source)
        print('Census batch', offset, 'rows', len(group), 'statuses', sorted({r[2] for r in parsed}), flush=True)
    write(out / 'source-manifest.json', source)
    (out / 'SEALED').write_text(file_hash(out / 'source-manifest.json') + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=BASE / 'geography-acquisition-r1')
    parser.add_argument('--inputs', type=Path, default=BASE / 'identity-build-r1/florida-geography-input.json')
    parser.add_argument('--reuse', type=Path)
    args = parser.parse_args()
    collect(args.out.resolve(), args.inputs.resolve(), args.reuse.resolve() if args.reuse else None)
