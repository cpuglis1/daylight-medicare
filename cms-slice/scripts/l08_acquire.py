#!/usr/bin/env python3
"""Additive, cached acquisition of public L08 evidence; never access patient resources."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import threading
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l08-provider-networks-2026-10-27'
OUT = BASE / 'acquisition-r1'
LOCK = threading.Lock()
INHERITED = {'uhc.com', 'wellcare.com', 'medicare.gov', 'iopc-pd.api.centene.com'}


def digest(b):
    return hashlib.sha256(b).hexdigest()


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def acquire(url, label=None):
    """One ordinary HTTPS GET with checked redirects, content hash and durable failure."""
    OUT.mkdir(exist_ok=True)
    (OUT / 'raw').mkdir(exist_ok=True)
    (OUT / 'receipts').mkdir(exist_ok=True)
    if (OUT / 'SEALED').exists():
        raise ValueError('Sealed acquisition')
    rid = digest(url.encode())
    receipt_path = OUT / 'receipts' / (rid + '.json')
    if receipt_path.exists():
        return json.loads(receipt_path.read_text())
    stops = OUT / 'stopped-hosts.json'

    def guard(target):
        with LOCK:
            blocked = INHERITED | set(json.loads(stops.read_text()) if stops.exists() else [])
        host = urlparse(target).hostname or ''
        if urlparse(target).scheme != 'https' or any(host == x or host.endswith('.' + x) for x in blocked):
            raise ValueError('Persisted source access STOP or non-HTTPS: ' + target)

    class Redirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            guard(newurl)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    record = {'id': rid, 'requested_url': url, 'label': label,
              'retrieved_at_utc': datetime.now(timezone.utc).isoformat(), 'attempts': 1}
    temp = OUT / 'raw' / (rid + '.download')
    try:
        guard(url)
        with build_opener(Redirect).open(Request(url, headers={
                'User-Agent': 'Daylight public Medicare directory reference research',
                'Accept': '*/*'}), timeout=60) as response:
            guard(response.url)
            record.update(http_status=response.status, final_url=response.url,
                          headers={k.lower(): v for k,v in response.headers.items() if k.lower() in {
                              'content-type','content-length','etag','last-modified','content-range'}})
            h, size = hashlib.sha256(), 0
            with temp.open('wb') as output:
                while True:
                    chunk = response.read(1024*1024)
                    if not chunk: break
                    h.update(chunk); size += len(chunk); output.write(chunk)
                    if size > 2_000_000_000:
                        raise ValueError('Source exceeds 2GB bound')
            raw = OUT / 'raw' / h.hexdigest()
            temp.replace(raw)
            record.update(sha256=h.hexdigest(), bytes=size, path=str(raw.relative_to(ROOT)))
    except Exception as exc:
        record.update(error_type=type(exc).__name__, error=str(exc), http_status=getattr(exc,'code',record.get('http_status')))
        if isinstance(exc, HTTPError):
            body = exc.read()
            raw = OUT / 'raw' / digest(body)
            raw.write_bytes(body)
            record.update(sha256=digest(body), bytes=len(body), path=str(raw.relative_to(ROOT)))
            if exc.code in (401,403,429):
                with LOCK:
                    existing = set(json.loads(stops.read_text()) if stops.exists() else [])
                    existing.add(urlparse(url).hostname)
                    write(stops, sorted(existing))
        if temp.exists(): temp.unlink()
    write(receipt_path, record)
    return record


def body(record):
    if record.get('error'): raise ValueError(record['error'])
    return (ROOT / record['path']).read_bytes()


def fetch_many(jobs, workers=4):
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda x: acquire(x['url'], x.get('label')), jobs))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url'); p.add_argument('--label'); p.add_argument('--jobs',type=Path)
    args=p.parse_args()
    if args.jobs:
        for r in fetch_many(json.loads(args.jobs.read_text())):
            print(json.dumps(r), flush=True)
    else: print(json.dumps(acquire(args.url,args.label)))
