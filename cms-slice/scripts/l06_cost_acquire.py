#!/usr/bin/env python3
"""Collect the two 2026 cost schedules using previously pinned CMS ZIP indexes."""
import argparse
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import struct
import zipfile
import zlib

from l04_acquire import put, sha, write
from l05_acquire import request

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l06-drug-costs-2026-10-27'
MONTHLY_MANIFEST = ROOT / 'docs/data/l04-pdp-availability-2026-10-25/acquisition-r1/source-manifest.json'
QUARTERLY_MANIFEST = BASE / 'acquisition-r1/source-manifest.json'


def acquire(out):
    if out.exists():
        raise ValueError('Use a new immutable acquisition directory')
    (out / 'raw').mkdir(parents=True)
    monthly_sources = json.loads(MONTHLY_MANIFEST.read_text())['sources']
    monthly = monthly_sources['monthly']
    quarterly = json.loads(QUARTERLY_MANIFEST.read_text())
    manifest = {'schema': 'l06-cost-schedule-acquisition/1', 'year': 2026,
                'date_local': '2026-10-27', 'source_id': 'P26-S14', 'members': [],
                'input_manifests': {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in [MONTHLY_MANIFEST, QUARTERLY_MANIFEST]},
                'definitions': {k: monthly_sources[k] for k in ['layout', 'methodology']},
                'whole_parent_archive_sha256': None,
                'scope': 'Published beneficiary and insulin schedules for the existing 71 plans; no pharmacy-specific prices or calculator',
                'human_acceptance': None}
    write(out / 'source-manifest.json', manifest)
    for label, source in [('monthly', monthly), ('quarterly', quarterly)]:
        if str(source.get('year', source.get('benefit_year'))) != '2026':
            raise ValueError('Wrong source year')
        index = source['index']['synthetic_index']
        if sha((ROOT / index['path']).read_bytes()) != index['sha256']:
            raise ValueError('Changed pinned ZIP index')
        url = source['archive_url']
        tail, receipt = request(url, out, 'bytes=-65557')
        expected_tail = source['index']['tail']['sha256']
        if sha(tail) != expected_tail or int(receipt['headers']['content-range'].split('/')[-1]) != source['archive_bytes']:
            raise ValueError('Parent archive differs from pinned snapshot')
        modified = receipt['headers'].get('last-modified')
        manifest[label + '_tail_recheck'] = {**put(out, tail), **receipt}
        with zipfile.ZipFile(ROOT / index['path']) as z:
            infos = [i for i in z.infolist() if 'beneficiary cost file' in i.filename.lower()]
        if len(infos) != 2:
            raise ValueError('Expected beneficiary and insulin nested members')
        for info in infos:
            header, hr = request(url, out, f'bytes={info.header_offset}-{info.header_offset + 29}', modified)
            values = struct.unpack('<4s5H3I2H', header)
            if values[0] != b'PK\x03\x04' or values[2] & 1:
                raise ValueError('Invalid/encrypted source ZIP member')
            name_len, extra_len = values[-2:]
            start = 30 + name_len + extra_len
            end = info.header_offset + start + info.compress_size - 1
            block, br = request(url, out, f'bytes={info.header_offset}-{end}', modified)
            if len(block) != start + info.compress_size or br['headers'].get('content-range') != f'bytes {info.header_offset}-{end}/{source["archive_bytes"]}':
                raise ValueError('Truncated or shifted source range')
            if block[30:30 + name_len].decode('utf-8') != info.filename:
                raise ValueError('Wrong member name')
            body = zlib.decompress(block[start:], -15) if info.compress_type == 8 else block[start:]
            if info.compress_type not in (0, 8) or len(body) != info.file_size or zlib.crc32(body) != info.CRC:
                raise ValueError('Member compression/length/CRC mismatch')
            with zipfile.ZipFile(io.BytesIO(body)) as nested:
                native = [{'name': i.filename, 'bytes': i.file_size, 'sha256': sha(nested.read(i)),
                           'crc32': f'{i.CRC:08x}'} for i in nested.infolist() if not i.is_dir()]
            if len(native) != 1:
                raise ValueError('Expected one native schedule per nested archive')
            record = {'source': label, 'table': 'insulin' if 'insulin' in info.filename.lower() else 'beneficiary',
                      'name': info.filename, **put(out, body), 'inner': native[0],
                      'crc32': f'{info.CRC:08x}', 'local_header': {**put(out, header), **hr},
                      'compressed_block': {**put(out, block), **br}, 'reused_index': index}
            manifest['members'].append(record)
            write(out / 'source-manifest.json', manifest)
            print(label, record['table'], native[0]['bytes'], native[0]['sha256'], flush=True)
    for kind in ['beneficiary', 'insulin']:
        copies = [m['inner'] for m in manifest['members'] if m['table'] == kind]
        if copies[0]['sha256'] != copies[1]['sha256']:
            raise ValueError('Monthly/quarterly schedule difference needs explicit reconciliation')
    manifest['monthly_quarterly_native_bytes_agree'] = True
    manifest['completed_at_utc'] = datetime.now(timezone.utc).isoformat()
    write(out / 'source-manifest.json', manifest)
    (out / 'SEALED').write_text(sha((out / 'source-manifest.json').read_bytes()) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=BASE / 'acquisition-cost-r1')
    args = parser.parse_args()
    acquire(args.out.resolve())
