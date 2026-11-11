"""Bounded public-source collection for L10; no messages, challenges or quotes.

Only source URLs supplied explicitly are fetched. A denial is retained and stops
the run; this collector never retries or changes hosts to evade a source stop.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / 'docs/data/l10-medigap-2026-10-28/acquisition-r1'


def collect(source_id, url, kind, inputs=None):
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / 'raw').mkdir(exist_ok=True)
    receipt = DEST / (source_id + '.json')
    if receipt.exists():
        old = json.loads(receipt.read_text())
        if old['requested_url'] != url:
            raise ValueError('Immutable receipt has a different URL')
        data = (DEST / 'raw' / old['sha256']).read_bytes()
        if hashlib.sha256(data).hexdigest() != old['sha256']:
            raise ValueError('Retained bytes changed')
        return old
    req = Request(url, headers={'User-Agent': 'DaylightPublicEvidenceResearch/1.0',
                                'Accept': 'application/json, application/pdf, text/html, */*'})
    try:
        response = urlopen(req, timeout=45)
    except HTTPError as error:
        response = error
    with response:
        data = response.read(16_000_001)
        record = {'source_id': source_id, 'kind': kind, 'requested_url': url,
                  'final_url': response.url, 'http_status': response.code,
                  'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
                  'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                  'content_type': response.headers.get('Content-Type'),
                  'last_modified': response.headers.get('Last-Modified'),
                  'inputs': inputs, 'retries': 0}
    (DEST / 'raw' / record['sha256']).write_bytes(data)
    receipt.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    if record['http_status'] != 200 or len(data) > 16_000_000:
        raise ValueError(f'Source status/size changed: {source_id}; stop without retry')
    return record


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('source_id')
    p.add_argument('url')
    p.add_argument('--kind', default='public-reference')
    args = p.parse_args()
    print(json.dumps(collect(args.source_id, args.url, args.kind), indent=2))
