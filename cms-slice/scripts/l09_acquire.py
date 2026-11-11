"""Capture immutable public CMS L09 methodology; reuse the inspected rating archive."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l09-star-ratings-2026-10-28'
SOURCES = {
    'performance_index': 'https://www.cms.gov/medicare/health-drug-plans/part-c-d-performance-data',
    'technical_notes': 'https://www.cms.gov/files/document/2026-star-ratings-technical-notes.pdf',
    'fact_sheet': 'https://www.cms.gov/files/document/2026-star-ratings-fact-sheet.pdf',
    'cai_supplement': 'https://www.cms.gov/files/document/2026-categorical-adjustment-index-measure-supplement.pdf',
    'recalculated_cai_context': 'https://www.cms.gov/files/document/recalculated-2026-categorical-adjustment-index-values-2027-quality-bonus-payment-ratings.pdf',
    'correction_context': 'https://www.cms.gov/newsroom/fact-sheets/2027-medicare-advantage-part-d-star-ratings',
}
ARCHIVE_SHA = 'a72f4f4965239e12b3b264c843a71ea6bbd9c655547be5b1f95b3b0df4d1cde7'


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + '\n')


class CMSRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        require_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def require_url(url):
    p = urlsplit(url)
    if p.scheme != 'https' or p.hostname != 'www.cms.gov' or p.port not in (None, 443) or p.username:
        raise ValueError('Only the observed public www.cms.gov source origin is permitted')


def acquire(out):
    if out.exists():
        raise ValueError('Use a new acquisition revision; existing captures cannot be overwritten')
    out.mkdir(parents=True)
    raw = out / 'raw'
    raw.mkdir()
    planning = BASE / 'planning-r1'
    archive = planning / '2026-star-ratings-data-tables.zip'
    if sha(archive) != ARCHIVE_SHA:
        raise ValueError('The inspected 2026 archive changed')
    shutil.copy2(archive, raw / ARCHIVE_SHA)
    receipt = json.loads((planning / 'receipt.json').read_text())
    sources = {'ratings': {**receipt, 'path': str((raw / ARCHIVE_SHA).relative_to(ROOT)),
                           'reuse': str(archive.relative_to(ROOT)), 'benefit_year': 2026,
                           'use': 'published ratings source; source-use/release review pending'}}
    opener = build_opener(CMSRedirects())
    for source_id, url in SOURCES.items():
        require_url(url)
        try:
            with opener.open(Request(url, headers={'User-Agent': 'DaylightResearch/1.0'}), timeout=40) as response:
                require_url(response.url)
                data = response.read(15_000_001)
                if len(data) > 15_000_000:
                    raise ValueError('Source exceeded the inspected 15 MB bound')
                digest = hashlib.sha256(data).hexdigest()
                (raw / digest).write_bytes(data)
                sources[source_id] = {'requested_url': url, 'final_url': response.url,
                    'path': str((raw / digest).relative_to(ROOT)), 'sha256': digest,
                    'bytes': len(data), 'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
                    'last_modified': response.headers.get('Last-Modified'),
                    'content_type': response.headers.get('Content-Type'),
                    'use': 'methodology/context only; no personal or consumer approval'}
                if source_id in {'technical_notes', 'fact_sheet', 'cai_supplement', 'recalculated_cai_context'} and not data.startswith(b'%PDF-'):
                    raise ValueError('Expected a complete PDF: ' + source_id)
        except HTTPError as error:
            write(out / 'STOP.json', {'source_id': source_id, 'url': url, 'status': error.code,
                                      'action': 'No automatic retry or alternate origin; acquisition incomplete'})
            raise
        print(source_id, sources[source_id]['bytes'], flush=True)
    manifest = {'schema': 'l09-acquisition/1', 'year': 2026, 'sources': sources,
        'consumer_release_enabled': False, 'human_acceptance': None,
        'source_review_after_utc': '2026-11-27T00:00:00+00:00'}
    write(out / 'source-manifest.json', manifest)
    (out / 'SEALED').write_text(sha(out / 'source-manifest.json') + '\n')
    print('Acquisition sealed:', out, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    acquire(parser.parse_args().out.resolve())
