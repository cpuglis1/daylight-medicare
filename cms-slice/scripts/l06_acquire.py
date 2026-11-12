#!/usr/bin/env python3
"""Capture selected complete members of the published 2026 quarterly CMS ZIP.

Ordinary HTTPS ranges only; no Plan Finder access or whole-parent ZIP hash.
Supports a ZIP64 parent index and streams large members with retained ranges.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import struct
import zipfile
import zlib

from l04_acquire import put, write
from l05_acquire import request

ROOT = Path(__file__).resolve().parents[2]
URL = 'https://data.cms.gov/sites/default/files/2026-10/062e9434-ed9d-4e83-abbd-4d64eb375949/SPUF_2026_20261007.zip'
CHUNK = 16 * 1024 * 1024


def index(out):
    tail, receipt = request(URL, out, 'bytes=-65557')
    total = int(receipt['headers']['content-range'].split('/')[-1])
    modified = receipt['headers'].get('last-modified')
    at = tail.rfind(b'PK\x05\x06')
    if at < 0:
        raise ValueError('Missing ZIP end record')
    _, disk, start_disk, entries, count, size, offset, comment = struct.unpack_from('<4s4H2IH', tail, at)
    if disk or start_disk or entries != count:
        raise ValueError('Multipart archive is unsupported')
    evidence = {'tail': {**put(out, tail), **receipt}}
    if offset == 0xffffffff or size == 0xffffffff or count == 0xffff:
        signature, zip64_disk, zip64_offset, disks = struct.unpack_from('<4sIQI', tail, at - 20)
        if signature != b'PK\x06\x07' or zip64_disk or disks != 1:
            raise ValueError('Invalid ZIP64 locator')
        raw, r = request(URL, out, f'bytes={zip64_offset}-{zip64_offset + 55}', modified)
        v = struct.unpack('<4sQ2H2I4Q', raw)
        if v[0] != b'PK\x06\x06' or v[4] or v[5] or v[6] != v[7]:
            raise ValueError('Invalid ZIP64 end record')
        count, size, offset = v[7], v[8], v[9]
        evidence['zip64_end'] = {**put(out, raw), **r}
    if count >= 0xffff or size >= 0xffffffff:
        raise ValueError('Unusually large central directory requires inspection')
    raw, r = request(URL, out, f'bytes={offset}-{offset + size - 1}', modified)
    if len(raw) != size or int(r['headers']['content-range'].split('/')[-1]) != total:
        raise ValueError('Central directory size/parent mismatch')
    synthetic = raw + struct.pack('<4s4H2IH', b'PK\x05\x06', 0, 0, count, count, size, 0, 0)
    evidence['central_directory'] = {**put(out, raw), **r}
    evidence['synthetic_index'] = put(out, synthetic)
    with zipfile.ZipFile(io.BytesIO(synthetic)) as archive:
        members = [{'name': i.filename, 'bytes': i.file_size, 'compressed_bytes': i.compress_size,
                    'crc32': f'{i.CRC:08x}', 'header_offset': i.header_offset,
                    'compression': i.compress_type} for i in archive.infolist()]
    return {'schema': 'l06-quarterly-acquisition/1', 'year': 2026, 'source_id': 'P26-S19',
            'archive_url': URL, 'archive_bytes': total, 'whole_archive_sha256': None,
            'capture_method': 'Retained HTTP ranges and complete selected ZIP members',
            'last_modified': modified, 'index': evidence, 'archive_members': members,
            'members': [], 'human_acceptance': None,
            'scope': 'Published plan-level in-area retail average unit costs; no named-pharmacy or beneficiary estimate',
            'inherited_stops': ['medicare.gov', 'uhc.com', 'wellcare.com']}


def capture(out, manifest, info):
    modified = manifest['last_modified']
    offset = info['header_offset']
    raw, receipt = request(URL, out, f'bytes={offset}-{offset + 29}', modified)
    v = struct.unpack('<4s5H3I2H', raw)
    if v[0] != b'PK\x03\x04' or v[2] & 1 or v[3] != info['compression']:
        raise ValueError('Invalid/encrypted/inconsistent ZIP local header')
    name_size, extra_size = v[-2:]
    names, nr = request(URL, out, f'bytes={offset + 30}-{offset + 29 + name_size + extra_size}', modified)
    if names[:name_size].decode('utf-8') != info['name']:
        raise ValueError('Member filename mismatch')
    start = offset + 30 + name_size + extra_size
    end = start + info['compressed_bytes']
    partial = out / 'raw' / (hashlib.sha256(info['name'].encode()).hexdigest() + '.partial')
    if partial.exists():
        raise ValueError('Partial capture exists; inspect before retrying')
    digest, crc, size = hashlib.sha256(), 0, 0
    decompressor = zlib.decompressobj(-15) if info['compression'] == 8 else None
    if info['compression'] not in (0, 8):
        raise ValueError('Unsupported compression')
    chunks = []
    with partial.open('xb') as target:
        for a in range(start, end, CHUNK):
            b = min(a + CHUNK, end)
            block, r = request(URL, out, f'bytes={a}-{b - 1}', modified)
            if (len(block) != b - a or r['headers'].get('content-range') !=
                    f'bytes {a}-{b - 1}/{manifest["archive_bytes"]}'):
                raise ValueError('Truncated or shifted source range')
            chunks.append({'start': a, 'end': b - 1, **put(out, block), **r})
            payload = decompressor.decompress(block) if decompressor else block
            target.write(payload)
            digest.update(payload)
            crc = zlib.crc32(payload, crc)
            size += len(payload)
            print(f'{info["name"]}: {b - start}/{end - start} compressed bytes', flush=True)
        if decompressor:
            payload = decompressor.flush()
            if not decompressor.eof or decompressor.unused_data:
                raise ValueError('Incomplete or trailing compressed member')
            target.write(payload)
            digest.update(payload)
            crc = zlib.crc32(payload, crc)
            size += len(payload)
    if size != info['bytes'] or f'{crc:08x}' != info['crc32']:
        raise ValueError('Member length/CRC mismatch')
    destination = out / 'raw' / digest.hexdigest()
    if destination.exists():
        if destination.stat().st_size != size or hashlib.sha256(destination.read_bytes()).hexdigest() != digest.hexdigest():
            raise ValueError('Content-addressed destination mismatch')
        partial.unlink()
    else:
        partial.rename(destination)
    with zipfile.ZipFile(destination) as nested:
        inners = [{'name': i.filename, 'bytes': i.file_size, 'compressed_bytes': i.compress_size,
                   'crc32': f'{i.CRC:08x}'} for i in nested.infolist()]
    return {**info, 'path': str(destination.relative_to(ROOT)), 'sha256': digest.hexdigest(),
            'local_header': {**put(out, raw), **receipt},
            'name_extra': {**put(out, names), **nr}, 'compressed_ranges': chunks,
            'inner_members': inners}


def acquire(out, collect=False):
    out.mkdir(parents=True, exist_ok=True)
    (out / 'raw').mkdir(exist_ok=True)
    manifest_path = out / 'source-manifest.json'
    if (out / 'SEALED').exists():
        raise ValueError('Sealed acquisition; use a new revision')
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else index(out)
    write(manifest_path, manifest)
    if not collect:
        print(json.dumps({'archive_bytes': manifest['archive_bytes'], 'members': manifest['archive_members']}, indent=2))
        return
    # Companion snapshots establish precise plan/formulary linkage and any
    # differences from the already-held September monthly files.
    selected = [m for m in manifest['archive_members'] if any(s in m['name'].lower() for s in
                ['pricing', 'plan information', 'basic drugs formulary', 'excluded drugs formulary'])]
    if not any('pricing' in m['name'].lower() for m in selected):
        raise ValueError('Pricing member missing; inspect index')
    for info in selected:
        if any(m['name'] == info['name'] for m in manifest['members']):
            continue
        manifest['members'].append(capture(out, manifest, info))
        write(manifest_path, manifest)
    manifest['completed_at_utc'] = datetime.now(timezone.utc).isoformat()
    write(manifest_path, manifest)
    (out / 'SEALED').write_text(hashlib.sha256(manifest_path.read_bytes()).hexdigest() + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--collect', action='store_true')
    args = parser.parse_args()
    acquire(args.out.resolve(), args.collect)
