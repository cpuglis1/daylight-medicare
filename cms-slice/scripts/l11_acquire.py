"""Retain explicitly named public L11 evidence; never retry a denial.

This does not collect personal records or accept website terms. Medicare.gov and
carrier routes with existing stops are excluded; held bytes are reused instead.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import gzip
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / 'docs/data/l11-medigap-rights-2026-10-28/acquisition-r1'
ALLOWED = {'uscode.house.gov', 'www.flsenate.gov', 'flrules.org',
           'www.flrules.org', 'www.cms.gov', 'myfloridacfo.com',
           'www.myfloridacfo.com', 'www.ecfr.gov', 'www.govinfo.gov', 'www.archives.gov'}


class PublicRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlparse(newurl).scheme != 'https' or urlparse(newurl).hostname not in ALLOWED:
            raise ValueError('Unexpected redirect; review before accessing ' + newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def collect(source_id, url, kind):
    if urlparse(url).scheme != 'https' or urlparse(url).hostname not in ALLOWED:
        raise ValueError('Source outside explicitly permitted public legal/guidance hosts')
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / 'raw').mkdir(exist_ok=True)
    receipt_path = DEST / (source_id + '.json')
    if (DEST.parent / 'build-r1' / 'manifest.json').exists() and not receipt_path.exists():
        raise ValueError('L11 r1 is sealed; add evidence only in a new acquisition/build revision')
    if receipt_path.exists():
        record = json.loads(receipt_path.read_text())
        if record['requested_url'] != url:
            raise ValueError('Existing receipt URL differs; use a new revision')
        raw = DEST / 'raw' / record['sha256']
        if hashlib.sha256(raw.read_bytes()).hexdigest() != record['sha256']:
            raise ValueError('Retained bytes changed')
        if record['http_status'] != 200 or b'challenge-platform' in raw.read_bytes():
            raise ValueError('Existing failed source receipt; do not retry')
        return record
    # A denial from the same host in this acquisition revision stops further
    # automated collection from that host until separately reviewed.
    for p in DEST.glob('*.json'):
        old = json.loads(p.read_text())
        if isinstance(old, dict) and 'requested_url' in old and 'sha256' in old:
            blocked = old.get('http_status') in (401, 403, 429)
            blocked |= b'challenge-platform' in (DEST / 'raw' / old['sha256']).read_bytes()
            if blocked and urlparse(old['requested_url']).hostname == urlparse(url).hostname:
                raise ValueError('Host has an existing access stop: ' + urlparse(url).hostname)
    req = Request(url, headers={'User-Agent': 'DaylightPublicEvidenceResearch/1.0',
                               'Accept': 'text/html, application/pdf, application/msword, application/xml, */*',
                               'Accept-Encoding': 'gzip'})
    try:
        response = build_opener(PublicRedirects()).open(req, timeout=40)
    except HTTPError as error:
        response = error
    with response:
        wire = response.read(8_000_001)
        data = gzip.decompress(wire) if response.headers.get('Content-Encoding') == 'gzip' else wire
        record = {'source_id': source_id, 'kind': kind, 'requested_url': url,
                  'final_url': response.url, 'http_status': response.code,
                  'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
                  'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                  'content_type': response.headers.get('Content-Type'),
                  'last_modified': response.headers.get('Last-Modified'),
                  'content_encoding': response.headers.get('Content-Encoding'),
                  'wire_sha256': hashlib.sha256(wire).hexdigest(),
                  'wire_bytes': len(wire),
                  'retries': 0}
    (DEST / 'raw' / record['sha256']).write_bytes(data)
    if record['wire_sha256'] != record['sha256']:
        (DEST / 'raw' / record['wire_sha256']).write_bytes(wire)
    receipt_path.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    if record['http_status'] != 200 or len(data) > 8_000_000 or b'challenge-platform' in data:
        raise ValueError('Source status/size requires review; no automatic retry: ' + source_id)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source_id', nargs='?')
    parser.add_argument('url', nargs='?')
    parser.add_argument('--targets', type=Path)
    parser.add_argument('--kind', default='official-legal-reference')
    args = parser.parse_args()
    if args.targets:
        for entry in json.loads(args.targets.read_text()):
            record = collect(entry['source_id'], entry['url'], entry.get('kind', args.kind))
            print(json.dumps({k: record[k] for k in ('source_id', 'http_status', 'bytes', 'sha256')}), flush=True)
    else:
        if not args.source_id or not args.url:
            parser.error('Supply source_id and url, or --targets')
        print(json.dumps(collect(args.source_id, args.url, args.kind), indent=2))
