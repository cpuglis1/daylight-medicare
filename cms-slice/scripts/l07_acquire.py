#!/usr/bin/env python3
"""Collect six pinned 2026 CMS network members with resumable retained ranges."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import zipfile
import zlib

from l04_acquire import put, write
from l05_acquire import request

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l07-pharmacy-networks-2026-10-27'
L04 = ROOT / 'docs/data/l04-pdp-availability-2026-10-25/acquisition-r1/source-manifest.json'
CHUNK = 16 * 1024 * 1024


def file_hash(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def acquire(out):
    if (out / 'SEALED').exists():
        raise ValueError('Acquisition sealed; use a new revision')
    out.mkdir(exist_ok=True)
    (out / 'raw').mkdir(exist_ok=True)
    old = json.loads(L04.read_text())['sources']['monthly']
    for key in ['tail', 'central_directory', 'synthetic_index']:
        item = old['index'][key]
        if file_hash(ROOT / item['path']) != item['sha256']:
            raise ValueError('Pinned CMS index changed')
    tail, receipt = request(old['archive_url'], out, 'bytes=-65557')
    if (hashlib.sha256(tail).hexdigest() != old['index']['tail']['sha256'] or
            int(receipt['headers']['content-range'].split('/')[-1]) != old['archive_bytes']):
        raise ValueError('CMS monthly archive differs from held snapshot')
    modified = receipt['headers'].get('last-modified')
    with zipfile.ZipFile(ROOT / old['index']['synthetic_index']['path']) as archive:
        parts = [i for i in archive.infolist() if 'pharmacy networks' in i.filename.lower()]
    if len(parts) != 6:
        raise ValueError('Expected exactly six pharmacy network members')
    manifest_path = out / 'source-manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {
        'schema': 'l07-network-acquisition/1', 'year': 2026,
        'archive_url': old['archive_url'], 'archive_bytes': old['archive_bytes'],
        'whole_parent_archive_sha256': None, 'index': old['index'],
        'tail_recheck': {**put(out, tail), **receipt},
        'input_manifest_sha256': file_hash(L04), 'members': [],
        'scope': 'Published September 2026 network snapshot, all six parts',
        'inherited_stops': ['medicare.gov', 'uhc.com', 'wellcare.com'],
        'human_acceptance': None}
    write(manifest_path, manifest)
    for part, info in enumerate(parts, 1):
        if any(x['name'] == info.filename for x in manifest['members']):
            continue
        checkpoint = out / f'part-{part}-checkpoint.json'
        if checkpoint.exists():
            c = json.loads(checkpoint.read_text())
        else:
            offset = info.header_offset
            header, hr = request(old['archive_url'], out, f'bytes={offset}-{offset + 29}', modified)
            v = struct.unpack('<4s5H3I2H', header)
            if v[0] != b'PK\x03\x04' or v[2] & 1 or v[3] != info.compress_type:
                raise ValueError('Invalid ZIP local header')
            n, e = v[-2:]
            names, nr = request(old['archive_url'], out, f'bytes={offset + 30}-{offset + 29 + n + e}', modified)
            if names[:n].decode() != info.filename:
                raise ValueError('ZIP member name mismatch')
            start = offset + 30 + n + e
            c = {'name': info.filename, 'part': part, 'start': start, 'end': start + info.compress_size,
                 'bytes': info.file_size, 'compressed_bytes': info.compress_size, 'compression': info.compress_type,
                 'crc32': f'{info.CRC:08x}', 'local_header': {**put(out, header), **hr},
                 'name_extra': {**put(out, names), **nr}, 'compressed_ranges': []}
            write(checkpoint, c)
        next_at = c['start']
        for previous in c['compressed_ranges']:
            if previous['start'] != next_at or file_hash(ROOT / previous['path']) != previous['sha256']:
                raise ValueError('Invalid retained range checkpoint')
            next_at = previous['end'] + 1
        for a in range(next_at, c['end'], CHUNK):
            b = min(a + CHUNK, c['end'])
            body, r = request(old['archive_url'], out, f'bytes={a}-{b - 1}', modified)
            if len(body) != b - a or r['headers'].get('content-range') != f'bytes {a}-{b - 1}/{old["archive_bytes"]}':
                raise ValueError('Shifted or truncated HTTP range')
            c['compressed_ranges'].append({'start': a, 'end': b - 1, **put(out, body), **r})
            write(checkpoint, c)
            print(f'part {part}/6: {b - c["start"]}/{c["compressed_bytes"]} bytes', flush=True)
        partial = out / 'raw' / f'part-{part}.assembling'
        crc, size = 0, 0
        decompressor = zlib.decompressobj(-15) if info.compress_type == 8 else None
        if info.compress_type not in (0, 8):
            raise ValueError('Unsupported ZIP compression')
        with partial.open('wb') as target:
            for item in c['compressed_ranges']:
                body = (ROOT / item['path']).read_bytes()
                body = decompressor.decompress(body) if decompressor else body
                target.write(body); crc = zlib.crc32(body, crc); size += len(body)
            if decompressor:
                body = decompressor.flush()
                target.write(body); crc = zlib.crc32(body, crc); size += len(body)
                if not decompressor.eof or decompressor.unused_data:
                    raise ValueError('Invalid compressed stream completion')
        if size != info.file_size or crc != info.CRC:
            raise ValueError('ZIP member size/CRC mismatch')
        digest = file_hash(partial)
        destination = out / 'raw' / digest
        partial.rename(destination)
        with zipfile.ZipFile(destination) as nested:
            inners = [{'name': i.filename, 'bytes': i.file_size, 'compressed_bytes': i.compress_size,
                       'crc32': f'{i.CRC:08x}'} for i in nested.infolist() if not i.is_dir()]
        if len(inners) != 1:
            raise ValueError('Expected exactly one native file per network part')
        manifest['members'].append({**c, 'path': str(destination.relative_to(ROOT)),
                                    'sha256': digest, 'inner': inners[0]})
        write(manifest_path, manifest)
        print(f'part {part} retained: {inners[0]}', flush=True)
    manifest['completed_at_utc'] = datetime.now(timezone.utc).isoformat()
    write(manifest_path, manifest)
    (out / 'SEALED').write_text(file_hash(manifest_path) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=BASE / 'acquisition-r1')
    acquire(parser.parse_args().out.resolve())
