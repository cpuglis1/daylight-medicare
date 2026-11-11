"""Additive, allowlisted public-source intake for the L11 r2 reconciliation.

Earlier evidence and collectors are immutable. No carrier or Medicare.gov
access stop is retried. A denial/challenge is retained and stops this route.
"""
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / 'docs/data/l11-medigap-rights-2026-10-28/acquisition-r2'
TARGETS = {
    'cms-2026-enrollment': 'https://www.cms.gov/files/document/cy-2026-cd-enrollment-and-disenrollment-guidance.pdf',
    'cms-2026-ma-exhibits': 'https://www.cms.gov/files/document/cy-2026-ma-appendices-and-exhibits.pdf',
    'fl-law-2016-194': 'https://laws.flrules.org/2016/194',
}
HOSTS = {'www.cms.gov', 'laws.flrules.org'}


class Redirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlparse(newurl).scheme != 'https' or urlparse(newurl).hostname not in HOSTS:
            raise ValueError('Unexpected redirect: ' + newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def acquire():
    if (DEST.parent / 'build-r2/manifest.json').exists():
        raise ValueError('r2 sealed; create a new revision')
    (DEST / 'raw').mkdir(parents=True, exist_ok=True)
    for sid, url in TARGETS.items():
        receipt = DEST / (sid + '.json')
        if receipt.exists():
            row = json.loads(receipt.read_text())
            data = (ROOT / row['path']).read_bytes()
            assert row['url'] == url and hashlib.sha256(data).hexdigest() == row['sha256']
            if row['status'] != 'retained_pdf':
                raise ValueError('Existing stop; no retry')
            continue
        for prior in DEST.glob('*.json'):
            old = json.loads(prior.read_text())
            if old.get('status') == 'access_stop' and urlparse(old['url']).hostname == urlparse(url).hostname:
                raise ValueError('Existing host stop')
        req = Request(url, headers={'User-Agent': 'DaylightPublicEvidenceResearch/1.0', 'Accept-Encoding': 'gzip'})
        try:
            response = build_opener(Redirects()).open(req, timeout=40)
        except HTTPError as error:
            response = error
        with response:
            wire = response.read(8_000_001)
            data = gzip.decompress(wire) if response.headers.get('Content-Encoding') == 'gzip' else wire
            digest = hashlib.sha256(data).hexdigest()
            row = {'source_id': sid, 'url': url, 'final_url': response.url,
                   'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
                   'http_status': response.code, 'sha256': digest, 'bytes': len(data),
                   'path': str((DEST / 'raw' / digest).relative_to(ROOT)),
                   'content_type': response.headers.get('Content-Type'),
                   'status': 'retained_pdf' if response.code == 200 and data.startswith(b'%PDF') and len(data) <= 8_000_000 else 'access_stop',
                   'retry_count': 0}
        (ROOT / row['path']).write_bytes(data)
        receipt.write_text(json.dumps(row, indent=2, sort_keys=True) + '\n')
        print(json.dumps({k: row[k] for k in ['source_id', 'status', 'bytes', 'sha256']}), flush=True)
        if row['status'] != 'retained_pdf':
            raise ValueError('Unexpected response retained; no retry')


if __name__ == '__main__':
    acquire()
