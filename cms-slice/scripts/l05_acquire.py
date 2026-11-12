#!/usr/bin/env python3
"""Acquire the three missing 2026 formulary members, reusing L04 ZIP evidence.

Ordinary public HTTPS/range requests only. Stops persist, redirects are checked,
and no whole-parent ZIP hash is claimed for selected-member acquisition.
"""
import argparse
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import re
import struct
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler
import zipfile
import zlib

from l04_acquire import put, sha, write

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l05-drug-coverage-2026-10-25'
L04 = ROOT / 'docs/data/l04-pdp-availability-2026-10-25/acquisition-r1/source-manifest.json'
STOP_HOSTS = {'uhc.com', 'wellcare.com', 'medicare.gov'}


def request(url, out, byte_range=None, modified=None):
    stops = out / 'stopped-hosts.json'
    blocked = STOP_HOSTS | set(json.loads(stops.read_text()) if stops.exists() else [])

    def guard(target):
        host = urlparse(target).hostname or ''
        if urlparse(target).scheme != 'https' or any(host == x or host.endswith('.' + x) for x in blocked):
            raise ValueError('Source access STOP or non-HTTPS URL: ' + target)

    class Redirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            guard(newurl)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    guard(url)
    headers = {'User-Agent': 'Daylight published Medicare reference research'}
    if byte_range:
        headers['Range'] = byte_range
    if modified:
        headers['If-Unmodified-Since'] = modified
    try:
        with build_opener(Redirect).open(Request(url, headers=headers), timeout=45) as response:
            guard(response.url)
            if byte_range and response.status != 206:
                raise ValueError('Range not supported; no implicit large download')
            body = response.read(30_000_001)
            if len(body) > 30_000_000:
                raise ValueError('Public source exceeds 30 MB response limit')
            return body, {'requested_url': url, 'final_url': response.url, 'http_status': response.status,
                          'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
                          'headers': {k.lower(): v for k, v in response.headers.items() if k.lower() in
                                      {'content-type', 'content-length', 'content-range', 'etag', 'last-modified'}}}
    except HTTPError as exc:
        if exc.code in (401, 403, 429):
            blocked.add(urlparse(url).hostname)
            write(stops, sorted(blocked))
        raise


def acquire(out):
    out.mkdir()  # Immutable acquisition revision.
    (out / 'raw').mkdir()
    old = json.loads(L04.read_text())['sources']['monthly']
    manifest = {'schema': 'l05-acquisition/1', 'year': 2026, 'sources': {},
                'reused_l04_manifest_sha256': sha(L04.read_bytes()),
                'inherited_stops': sorted(STOP_HOSTS), 'human_acceptance': None}
    try:
        for name in ['tail', 'central_directory', 'synthetic_index']:
            r = old['index'][name]
            if sha((ROOT / r['path']).read_bytes()) != r['sha256']:
                raise ValueError('Changed pinned L04 archive index')
        tail, receipt = request(old['archive_url'], out, 'bytes=-65557')
        if (sha(tail) != old['index']['tail']['sha256'] or
                int(receipt['headers']['content-range'].split('/')[-1]) != old['archive_bytes']):
            raise ValueError('CMS archive differs from pinned L04 source')
        modified = receipt['headers'].get('last-modified')
        source = {'id': 'P26-S13', 'year': 2026, 'archive_url': old['archive_url'],
                  'archive_bytes': old['archive_bytes'], 'whole_archive_sha256': None,
                  'reused_index': old['index'], 'tail_recheck': {**put(out, tail), **receipt}, 'members': []}
        with zipfile.ZipFile(ROOT / old['index']['synthetic_index']['path']) as archive:
            infos = [i for i in archive.infolist() if any(t in i.filename.lower() for t in
                     ['basic drugs formulary', 'excluded drugs formulary', 'indication based coverage formulary'])]
        if len(infos) != 3:
            raise ValueError('Expected exactly three drug archives')
        for info in infos:
            header, hr = request(old['archive_url'], out, f'bytes={info.header_offset}-{info.header_offset + 29}', modified)
            values = struct.unpack('<4s5H3I2H', header)
            if values[0] != b'PK\x03\x04' or values[2] & 1:
                raise ValueError('Invalid/encrypted ZIP member')
            name_len, extra_len = values[-2:]
            start = 30 + name_len + extra_len
            end = info.header_offset + start + info.compress_size - 1
            block, br = request(old['archive_url'], out, f'bytes={info.header_offset}-{end}', modified)
            if len(block) != start + info.compress_size:
                raise ValueError('Truncated member range')
            body = zlib.decompress(block[start:], -15) if info.compress_type == 8 else block[start:]
            if (info.compress_type not in (0, 8) or len(body) != info.file_size or zlib.crc32(body) != info.CRC
                    or block[30:30 + name_len].decode('utf-8') != info.filename):
                raise ValueError('Member name/size/CRC mismatch')
            record = {'name': info.filename, **put(out, body), 'crc32': f'{info.CRC:08x}',
                      'local_header': {**put(out, header), **hr}, 'compressed_block': {**put(out, block), **br}}
            with zipfile.ZipFile(io.BytesIO(body)) as nested:
                record['inner_members'] = [{'name': i.filename, 'bytes': i.file_size, 'sha256': sha(nested.read(i))}
                                           for i in nested.infolist()]
            source['members'].append(record)
            manifest['sources']['drug_tables'] = source
            write(out / 'source-manifest.json', manifest)
            print('captured', info.filename, len(body), flush=True)
        # The official 2026 reference file supplies drug names without per-drug API requests.
        url = 'https://www.cms.gov/medicare/coverage/prescription-drug-coverage/formulary-guidance'
        body, receipt = request(url, out)
        manifest['sources']['formulary_guidance'] = {**put(out, body), **receipt}
        links = re.findall(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', body.decode('utf-8'), re.S)
        candidates = [urljoin(url, href) for href, title in links
                      if re.search(r'2026\s+September\s+Formulary Reference', re.sub('<[^>]+>', ' ', title), re.I)]
        if len(candidates) != 1:
            raise ValueError('2026 September reference-file link missing or ambiguous')
        body, receipt = request(candidates[0], out)
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            members = [{'name': i.filename, 'bytes': i.file_size, 'sha256': sha(archive.read(i))} for i in archive.infolist()]
        manifest['sources']['drug_identity_reference'] = {**put(out, body), **receipt, 'members': members,
                                                         'scope': 'CMS CY2026 September Formulary Reference File'}
    except Exception as exc:
        manifest['error'] = {'type': type(exc).__name__, 'message': str(exc), 'http_status': getattr(exc, 'code', None)}
        raise
    finally:
        write(out / 'source-manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    acquire(args.out.resolve())
