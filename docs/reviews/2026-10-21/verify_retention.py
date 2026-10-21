#!/usr/bin/env python3
"""Verify original project bytes without removing or modifying any input."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent

def digest(path, kind):
    if kind == 'symlink':
        return hashlib.sha256(os.readlink(path).encode()).hexdigest() if path.is_symlink() else None
    if not path.is_file() or path.is_symlink():
        return None
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def verify():
    ledger = json.loads((HERE / 'migration-ledger.json').read_text())
    original = json.loads((ROOT / ledger['original_manifest']).read_text())
    operations = {item['original_path']: item for item in ledger['operations']}
    counts, retained, failures = Counter(), [], []
    for item in original['files']:
        name, expected, kind = item['path'], item.get('sha256'), item['type']
        current = ROOT / name
        if kind == 'special':
            failures.append({'path': name, 'reason': 'Special input needs manual inspection'})
            continue
        if digest(current, kind) == expected:
            counts['unchanged_at_original_path'] += 1
            continue
        operation = operations.get(name)
        if operation:
            locations = [operation.get('new_path'), operation['before_image']]
            location = next((path for path in locations if path and digest(ROOT / path, kind) == expected), None)
            if location:
                counts['retained_move' if operation['action'] == 'move' else 'retained_before_edit'] += 1
                retained.append({'original_path': name, 'verified_original_bytes_at': location,
                                 'current_path': operation.get('new_path', name), 'sha256': expected})
                continue
        failures.append({'path': name, 'reason': 'No original hash match at original/recorded retained location'})
    missing_dirs = [name for name in original['directories'] if not (ROOT / name).is_dir()]
    result = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'original_files': len(original['files']),
              'original_logical_bytes': sum(item['size'] for item in original['files']),
              'original_manifest_sha256': digest(ROOT / ledger['original_manifest'], 'file'),
              'counts': dict(counts), 'retained_original_versions': retained, 'failures': failures,
              'original_directories_missing': missing_dirs,
              'all_original_content_retained': not failures and not missing_dirs,
              'scope': 'Project files including ignored caches/symlinks; .git internals excluded and Git state separately captured.'}
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, help='Optional new report; existing differing report is refused')
    args = parser.parse_args()
    result = verify()
    body = json.dumps(result, indent=2) + '\n'
    if args.out:
        if args.out.exists():
            raise SystemExit('Report exists; choose a new output path to preserve prior evidence')
        args.out.write_text(body)
    print(json.dumps({key: result[key] for key in ('original_files','counts','failures','original_directories_missing','all_original_content_retained')}, indent=2))
    raise SystemExit(0 if result['all_original_content_retained'] else 1)
