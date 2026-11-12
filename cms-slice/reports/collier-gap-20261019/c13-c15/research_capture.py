"""Small, identified, no-retry evidence fetches for the C13-C15 assessment.

This is research tooling, not the C16 Medicare.gov collector. Never fetch member data.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
UA = "DaylightMedicareEvidenceReview/0.1 (+mailto:chris@beaconfederaladvisory.com)"


def capture(key, url, max_bytes=4_000_000):
    if not key.replace('-', '').replace('_', '').isalnum():
        raise ValueError("Use a simple unique evidence key")
    if urlsplit(url).scheme != 'https':
        raise ValueError('HTTPS sources only')
    receipts, rawdir = ROOT / 'receipts', ROOT / 'raw'
    receipts.mkdir(exist_ok=True); rawdir.mkdir(exist_ok=True)
    path = receipts / (key + '.json')
    if path.exists():
        return json.loads(path.read_text())
    medicare = urlsplit(url).hostname in {'www.medicare.gov', 'medicare.gov'}
    stop = ROOT / 'medicare-stop.json'
    if medicare and stop.exists():
        raise ValueError('Medicare.gov stop condition already recorded; do not retry or evade')
    clock = ROOT / 'medicare-last-request.json'
    if medicare:
        last = json.loads(clock.read_text())['unix'] if clock.exists() else 0
        time.sleep(max(0, 5 - (time.time() - last)))
        clock.write_text(json.dumps({'unix': time.time()}))
    record = {'id': key, 'requested_url': url, 'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
              'user_agent': UA, 'max_bytes': max_bytes, 'retry_count': 0}
    request = Request(url, headers={'User-Agent': UA, 'Accept': 'application/fhir+json, application/json, text/html, text/plain, */*'})
    try:
        response = urlopen(request, timeout=25)
    except HTTPError as error:
        response = error
    except (URLError, TimeoutError) as error:
        record.update(status='transport_error', error_type=type(error).__name__)
        path.write_text(json.dumps(record, indent=2) + '\n')
        return record
    with response:
        data = response.read(max_bytes + 1)
        record.update(http_status=response.code, final_url=response.url,
                      content_type=response.headers.get('Content-Type'),
                      last_modified=response.headers.get('Last-Modified'))
    record['truncated'] = len(data) > max_bytes
    data = data[:max_bytes]
    digest = hashlib.sha256(data).hexdigest()
    (rawdir / digest).write_bytes(data)
    record.update(sha256=digest, bytes=len(data), status='captured')
    # A textual robots directive mentioning captcha is not a block page.
    body = data[:100000].decode('utf-8', errors='replace').casefold()
    blocked = record['http_status'] in {403, 429} or ('text/html' in (record['content_type'] or '') and any(x in body for x in ['verify you are human', 'captcha challenge', 'access denied', 'pardon our interruption']))
    if blocked:
        record['access_state'] = 'blocked_no_retry'
        if medicare:
            stop.write_text(json.dumps(record, indent=2) + '\n')
    path.write_text(json.dumps(record, indent=2) + '\n')
    return record


def data(key):
    spec = json.loads((ROOT / 'receipts' / (key + '.json')).read_text())
    raw = (ROOT / 'raw' / spec['sha256']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != spec['sha256']:
        raise ValueError('Saved source changed')
    return spec, raw


if __name__ == '__main__':
    result = capture(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 4_000_000)
    print(json.dumps(result))
