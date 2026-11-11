"""Explicit public CMS acquisition for the L04 published PDP reference.

The large monthly ZIP is read using ordinary HTTP byte ranges. Retained ZIP
headers/compressed member bytes and CRCs bind the selected complete members;
no whole-archive SHA is claimed. No Plan Finder or stopped carrier is requested.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import struct
import urllib.request
from urllib.error import HTTPError
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l04-pdp-availability-2026-10-25'
MONTHLY = 'https://data.cms.gov/sites/default/files/2026-09/903ba816-d276-4c17-9b5a-0224bbd4e949/2026_20260916.zip'
SOURCES = {
    'area-september': ('L04-S01', 'https://www.cms.gov/files/zip/pdp-contract-service-area-state-county-september-2026.zip', '2026-09'),
    'area-october': ('L04-S02', 'https://www.cms.gov/files/zip/pdp-contract-service-area-state-county-october-2026.zip', '2026-10'),
    'layout': ('P26-S13-LAYOUT', 'https://data.cms.gov/sites/default/files/2025-10/0564eb37-402d-4110-bd98-2d5399dc30e7/PUFRecordLayout-2026.pdf', '2026 layout'),
    'methodology': ('P26-S13-METHOD', 'https://data.cms.gov/sites/default/files/2025-10/8f1d8b42-bfd1-4f9c-b86d-b92af0c6f3d5/Methodology-PUF-2026.pdf', '2026 methodology'),
    'florida-blue-sb': ('P26-N01-S5904-001-002-SB-2026', 'https://files.guidewell.com/m/27ae5145263a2356/original/medicare-forms-2026-sb-fbm2540.pdf', '2026 SB; carrier page dated 2025-08-22'),
    'florida-blue-premier-page': ('P26-N01-S5904-001-PAGE-2026', 'https://www.floridablue.com/medicare/forms/s5904-bluemedicare-premier-rx', 'observed carrier document index; contains multiple years'),
    'florida-blue-complete-page': ('P26-N01-S5904-002-PAGE-2026', 'https://www.floridablue.com/medicare/forms/s5904-bluemedicare-complete-rx', 'observed carrier document index; contains multiple years'),
    'humana-basic-sb': ('P26-N01-S5884-105-SB-2026', 'https://assets.humana.com/is/content/humana/S5884105000SB26pdf', '2026 SB; verify payload'),
    'humana-premier-sb': ('P26-N01-S5884-157-SB-2026', 'https://assets.humana.com/is/content/humana/S5884157000SB26pdf', '2026 SB; verify payload'),
    'humana-value-sb': ('P26-N01-S5884-190-SB-2026', 'https://assets.humana.com/is/content/humana/S5884190000SB26pdf', '2026 SB; verify payload'),
    'enforcement': ('L04-S03', 'https://www.cms.gov/medicare/audits-compliance/part-c-d/part-c-and-part-d-enforcement-actions', 'observed page; not full status history'),
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def put(out, raw):
    digest = sha(raw)
    path = out / 'raw' / digest
    if path.exists() and path.read_bytes() != raw:
        raise ValueError('Hash-addressed evidence collision')
    if not path.exists():
        path.write_bytes(raw)
    return {'sha256': digest, 'bytes': len(raw), 'path': str(path.relative_to(ROOT))}


def request(url, byte_range=None, modified=None):
    headers = {'User-Agent': 'Daylight published Medicare reference research'}
    if byte_range:
        headers['Range'] = byte_range
    if modified:
        headers['If-Unmodified-Since'] = modified
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=45) as response:
        if byte_range and response.status != 206:
            raise ValueError('CMS range request not supported; no implicit large download')
        raw = response.read(60_000_001)
        if len(raw) > 60_000_000:
            raise ValueError('Bounded source response exceeded limit')
        return raw, {'requested_url': url, 'final_url': response.url,
                     'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
                     'http_status': response.status,
                     'headers': {k.lower(): v for k, v in response.headers.items()
                                 if k.lower() in {'content-type', 'content-length', 'last-modified', 'etag', 'content-range'}}}


def monthly(out):
    tail, receipt = request(MONTHLY, 'bytes=-65557')
    total = int(receipt['headers']['content-range'].split('/')[-1])
    at = tail.rfind(b'PK\x05\x06')
    if at < 0:
        raise ValueError('ZIP end-of-central-directory not found')
    _, disk, start_disk, entries, all_entries, cd_bytes, cd_offset, comment = struct.unpack_from('<4s4H2IH', tail, at)
    if disk or start_disk or entries != all_entries or cd_offset == 0xffffffff:
        raise ValueError('Unsupported multipart/ZIP64 index')
    modified = receipt['headers'].get('last-modified')
    cd, cd_receipt = request(MONTHLY, f'bytes={cd_offset}-{cd_offset + cd_bytes - 1}', modified)
    if len(cd) != cd_bytes or int(cd_receipt['headers']['content-range'].split('/')[-1]) != total:
        raise ValueError('Monthly archive changed during capture')
    # A small valid ZIP containing the original central directory allows the
    # standard library to inspect names/sizes/offsets without fetching 2.3 GB.
    index = cd + struct.pack('<4s4H2IH', b'PK\x05\x06', 0, 0, entries, entries, cd_bytes, 0, 0)
    with zipfile.ZipFile(io.BytesIO(index)) as archive:
        infos = archive.infolist()
    result = {'id': 'P26-S13', 'benefit_year': '2026', 'source_period': '2026-09',
              'archive_url': MONTHLY, 'archive_bytes': total, 'whole_archive_sha256': None,
              'capture_method': 'HTTP byte ranges; complete selected ZIP members only',
              'index': {'tail': put(out, tail), 'central_directory': put(out, cd),
                        'synthetic_index': put(out, index), 'receipt': receipt, 'central_directory_receipt': cd_receipt},
              'archive_members': [{'name': i.filename, 'bytes': i.file_size,
                                   'compressed_bytes': i.compress_size, 'crc32': f'{i.CRC:08x}',
                                   'header_offset': i.header_offset} for i in infos], 'members': []}
    for info in infos:
        label = info.filename.lower()
        if not any(x in label for x in ['plan information', 'plan_information', 'geographic locator', 'geographic_locator']):
            continue
        header, hr = request(MONTHLY, f'bytes={info.header_offset}-{info.header_offset + 29}', modified)
        values = struct.unpack('<4s5H3I2H', header)
        if values[0] != b'PK\x03\x04' or values[2] & 1:
            raise ValueError('Invalid/encrypted member')
        name_len, extra_len = values[-2:]
        end = info.header_offset + 30 + name_len + extra_len + info.compress_size - 1
        block, br = request(MONTHLY, f'bytes={info.header_offset}-{end}', modified)
        start = 30 + name_len + extra_len
        compressed = block[start:]
        raw = zlib.decompress(compressed, -15) if info.compress_type == 8 else compressed
        if (info.compress_type not in (0, 8) or len(raw) != info.file_size
                or zlib.crc32(raw) != info.CRC
                or block[30:30 + name_len].decode('utf-8') != info.filename):
            raise ValueError('Member CRC/size/name verification failed')
        result['members'].append({'name': info.filename, **put(out, raw),
                                  'compressed_block': put(out, block), 'receipt': br,
                                  'local_header': put(out, header), 'header_receipt': hr,
                                  'crc32': f'{info.CRC:08x}'})
    if not result['members']:
        raise ValueError('No plan/geography members selected; inspect index')
    return result


def acquire(out, names):
    out = Path(out).resolve()
    (out / 'raw').mkdir(parents=True, exist_ok=True)
    path = out / 'source-manifest.json'
    manifest = json.loads(path.read_text()) if path.exists() else {
        'schema': 'l04-acquisition/1', 'benefit_year': '2026', 'sources': {},
        'inherited_access': json.loads((ROOT / 'docs/data/l02-ma-availability-2026-10-25/source-access-state.json').read_text()),
        'use_review': 'Research capture; no human permitted-use or consumer acceptance asserted'}
    for name in names:
        if name in manifest['sources']:
            print(name, 'cached', flush=True)
            continue
        try:
            if name == 'monthly':
                source = monthly(out)
            else:
                sid, url, period = SOURCES[name]
                raw, receipt = request(url)
                source = {'id': sid, 'benefit_year': '2026', 'source_period': period,
                          **put(out, raw), **receipt}
                if raw.startswith(b'PK'):
                    with zipfile.ZipFile(io.BytesIO(raw)) as z:
                        source['members'] = [{'name': i.filename, 'bytes': i.file_size,
                                              'sha256': sha(z.read(i))} for i in z.infolist()]
            source['status'] = 'captured'
        except (HTTPError, ValueError) as error:
            source = {'id': SOURCES.get(name, ('P26-S13',))[0], 'status': 'unavailable',
                      'reason': str(error), 'http_status': getattr(error, 'code', None),
                      'stop': getattr(error, 'code', None) in (401, 403, 429)}
        manifest['sources'][name] = source
        write(path, manifest)
        print(name, source['status'], source.get('bytes', ''), flush=True)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=BASE / 'acquisition-r1')
    parser.add_argument('--only', nargs='+', choices=[*SOURCES, 'monthly'], default=['area-september', 'area-october', 'layout', 'methodology', 'enforcement', 'monthly'])
    args = parser.parse_args()
    acquire(args.out, args.only)
