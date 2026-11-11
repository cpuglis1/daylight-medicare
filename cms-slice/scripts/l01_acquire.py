#!/usr/bin/env python3
"""Fixed official-source L01 acquisition. No Medicare.gov requests or STOP reset.

Snapshots are content-addressed and never overwritten. Refresh creates receipts;
it cannot extend acceptance. A denied host is not retried in the same run.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'docs/data/l01-national-2026/r1'
HOSTS = {'www.cms.gov', 'www.ssa.gov', 'secure.ssa.gov', 'www.govinfo.gov', 'ffic.myflfamilies.com', 'www.federalregister.gov'}
VERSION = 'l01-acquire/1'


def require_research_revision(package, registry=None):
    """Never overwrite inputs/outputs of a revision already submitted/accepted.

    A revoked receipt also preserves its historical revision. New evidence must
    use a new revision workspace and a new review, rather than mutate history.
    """
    registry=Path(registry) if registry is not None else ROOT/'cms-slice/data-sources/l01-acceptance.json'
    manifest=Path(package)/'manifest.json'
    if not manifest.exists() or not registry.exists():return
    current=json.loads(manifest.read_text());review=json.loads(registry.read_text())
    if review.get('package_id')!=current.get('package_id'):return
    records=[review.get('package_review',{})]+list(review.get('claims',{}).values())
    if any(r.get('decision')=='accepted' or (r.get('receipt') and r.get('reviewed_at_utc')) for r in records):
        raise ValueError('Reviewed revision is frozen; retain it and create a new year/revision workspace')


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n')


class OfficialRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme != 'https' or urlsplit(newurl).hostname not in HOSTS:
            raise ValueError('Unreviewed redirect; no request made')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def acquire(package=PACKAGE, source_ids=None):
    require_research_revision(package)
    sources = json.loads((package / 'source-inventory.json').read_text())['sources']
    stamp = datetime.now(timezone.utc).isoformat()
    run = package / 'acquisitions' / stamp.replace(':', '')
    denied = set()
    for prior in package.glob('acquisitions/*/*.json'):
        previous = json.loads(prior.read_text())
        if any(reason in previous.get('reason','') for reason in ['HTTP Error 401', 'HTTP Error 403', 'HTTP Error 429', 'Access challenge']):
            denied.add(urlsplit(previous['url']).hostname)
    opener = build_opener(OfficialRedirect)
    for source in sources:
        if source_ids and source['id'] not in source_ids:
            continue
        host = urlsplit(source['url']).hostname
        receipt = {**source, 'retrieved_at_utc': stamp, 'transformation_version': VERSION,
                   'access_record': 'Public official route; research retention; no login, paid access, or automated denial retry. No blanket third-party reuse license inferred.',
                   'status': 'unavailable'}
        if host == 'www.medicare.gov':
            receipt['reason'] = 'Existing Medicare.gov STOP preserved; no request made.'
        elif host not in HOSTS or host in denied:
            receipt['reason'] = 'Unreviewed or denied host; no request made.'
        else:
            try:
                with opener.open(Request(source['url'], headers={'User-Agent': 'Daylight-L01-Research/1 (official public evidence; no beneficiary data)'}), timeout=35) as response:
                    raw = response.read(20000001)
                    if len(raw) > 20000000:
                        raise ValueError('Artifact exceeds acquisition size bound')
                    if b'captcha' in raw[:20000].lower() or b'access denied' in raw[:10000].lower():
                        denied.add(host)
                        raise ValueError('Access challenge; host stopped')
                    sha = hashlib.sha256(raw).hexdigest()
                    artifact = package / 'raw' / sha
                    artifact.parent.mkdir(parents=True, exist_ok=True)
                    if artifact.exists():
                        assert artifact.read_bytes() == raw
                    else:
                        with artifact.open('xb') as f:
                            f.write(raw)
                    media = response.headers.get_content_type()
                    receipt.update(status='acquired', sha256=sha, byte_count=len(raw), final_url=response.url,
                                   media_type=media, artifact=str(artifact.relative_to(package)),
                                   http_last_modified=response.headers.get('Last-Modified'))
                    textfile = package / 'extracted' / (sha + '.txt')
                    textfile.parent.mkdir(parents=True, exist_ok=True)
                    if not textfile.exists():
                        if media == 'application/pdf' or raw.startswith(b'%PDF'):
                            subprocess.run(['pdftotext', '-layout', str(artifact), str(textfile)], check=True)
                        else:
                            textfile.write_text(raw.decode('utf-8', errors='replace'))
                    receipt['extracted_artifact'] = str(textfile.relative_to(package))
                    receipt['extractor'] = 'pdftotext -layout (version recorded in validation)' if raw.startswith(b'%PDF') else 'UTF-8 HTML source, replacement decoding'
            except (HTTPError, URLError, ValueError, OSError, subprocess.CalledProcessError) as error:
                receipt['reason'] = str(error)
                if isinstance(error, HTTPError) and error.code in {401, 403, 429}:
                    denied.add(host)
        dump(run / (source['id'] + '.json'), receipt)
        print(source['id'], receipt['status'], receipt.get('byte_count', receipt.get('reason')), flush=True)
    return run


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', action='append')
    p.add_argument('--package', type=Path, default=PACKAGE)
    a = p.parse_args()
    print(acquire(a.package, a.source))
