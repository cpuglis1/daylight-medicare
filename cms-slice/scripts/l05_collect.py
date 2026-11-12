#!/usr/bin/env python3
"""Bounded supplemental public evidence collection for L05; no STOP bypasses."""
import argparse
import json
from pathlib import Path
import subprocess

from l04_acquire import put, write
from l05_acquire import request

ROOT = Path(__file__).resolve().parents[2]


def collect(out, entries):
    out.mkdir(parents=True, exist_ok=True)
    (out / 'raw').mkdir(exist_ok=True)
    if (out / 'SEALED').exists():
        raise ValueError('Sealed source collection; use a new revision')
    manifest_path = out / 'source-manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {'schema': 'l05-supplemental-acquisition/1', 'sources': {}}
    for item in entries:
        key = item['id']
        if key in manifest['sources']:
            if manifest['sources'][key]['requested_url'] != item['url']:
                raise ValueError('Source ID reused for a different URL')
            continue
        try:
            body, receipt = request(item['url'], out)
            source = {**item, **receipt, **put(out, body), 'status': 'captured', 'human_acceptance': None}
            if body.startswith(b'%PDF'):
                txt = out / 'raw' / (source['sha256'] + '.txt')
                subprocess.run(['pdftotext', '-layout', str(ROOT / source['path']), str(txt)], check=True, capture_output=True)
                from l04_acquire import sha
                source.update(text_path=str(txt.relative_to(ROOT)), text_sha256=sha(txt.read_bytes()))
            print(key, 'captured', len(body), flush=True)
        except Exception as exc:
            source = {**item, 'requested_url': item['url'], 'status': 'unavailable',
                      'reason': str(exc), 'http_status': getattr(exc, 'code', None)}
            print(key, 'unavailable', str(exc), flush=True)
        manifest['sources'][key] = source
        write(manifest_path, manifest)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--entries', required=True, type=Path)
    args = parser.parse_args()
    collect(args.out.resolve(), json.loads(args.entries.read_text()))
