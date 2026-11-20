#!/usr/bin/env python3
"""Create a deterministic private archive of the hosted fictional display rehearsal."""

import argparse
import gzip
from hashlib import file_digest, sha256
import io
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[2]
ADVISOR = Path('alternatives/advisor-first')
ENGINE = Path('alternatives/chat-first/cms-slice')
DATA = Path('infrastructure/daylight-data')
PROFILE = DATA / 'config/profile-contract.2026.json'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def verify(path, expected):
    with path.open('rb') as stream:
        if file_digest(stream, 'sha256').hexdigest() != expected:
            raise ValueError(f'Evidence hash changed: {path.name}')


def selected_files(snapshot):
    manifest = read_json(snapshot / 'manifest.json')
    if manifest['consumer_release'] != 'held':
        raise ValueError('Expected the held display subset.')
    backup = read_json(snapshot / 'compressed-backup.json')
    if backup['file'] != 'pilot.dump.gz' or not backup['full_decompression_parity']:
        raise ValueError('Expected a verified display backup.')
    files = {}
    for rel in (ADVISOR / 'web', ADVISOR / 'web-8894', ADVISOR / 'pilot-web',
                ENGINE / 'config', DATA / 'src/daylight_data'):
        for path in (ROOT / rel).rglob('*'):
            if path.is_file() and path.suffix in {'.py', '.sql', '.lock', '.json', '.html',
                                                  '.css', '.js', '.svg', '.jpg', '.woff2'}:
                files[path.relative_to(ROOT).as_posix()] = path
    for path in (ROOT / ADVISOR).iterdir():
        if path.suffix in {'.py', '.json'} and path.is_file():
            files[path.relative_to(ROOT).as_posix()] = path
    for relative in (PROFILE, ENGINE / 'apps/chat-alternative/baseline-content.json',
                     ENGINE / 'apps/chat-alternative/zip-counties.json', ENGINE / 'apps/chat/zip-counties.json',
                     Path('docs/product/plan-comparison-2026-11-01/question-decision-map.json')):
        files[relative.as_posix()] = ROOT / relative
    bound = read_json(ROOT / ADVISOR / 'engine-lock.json')
    bound.update({key: val['sha256'] for key, val in manifest['catalog_files'].items()})
    bound.update({row['path']: row['sha256'] for row in read_json(ROOT / PROFILE)['source_bindings'].values()})
    for path, expected in bound.items():
        verify(ROOT / path, expected)
        files[path] = ROOT / path
    verify(snapshot / 'pilot.dump.gz', backup['sha256'])
    for name in ('binding.json', 'manifest.json', 'compressed-backup.json', 'pilot.dump.gz'):
        files['evidence/' + name] = snapshot / name
    return files


def package(snapshot, output):
    files = selected_files(snapshot)
    inventory = {}
    with output.open('xb') as stream, gzip.GzipFile(fileobj=stream, filename='', mode='wb', mtime=0) as compressed:
        with tarfile.open(mode='w|', fileobj=compressed, format=tarfile.PAX_FORMAT) as archive:
            for relative, path in sorted(files.items()):
                if path.is_symlink():
                    raise ValueError(f'Unexpected symlink: {relative}')
                raw = path.read_bytes()
                inventory[relative] = sha256(raw).hexdigest()
                entry = tarfile.TarInfo(relative)
                entry.size, entry.mode = len(raw), 0o600
                archive.addfile(entry, io.BytesIO(raw))
            meta = json.dumps({'scope': 'fictional_display_rehearsal', 'files_sha256': inventory},
                              sort_keys=True, indent=2).encode()
            entry = tarfile.TarInfo('release-manifest.json')
            entry.size, entry.mode = len(meta), 0o600
            archive.addfile(entry, io.BytesIO(meta))
    return {'files': len(inventory), 'sha256': sha256(output.read_bytes()).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(package(args.snapshot, args.output)))
