#!/usr/bin/env python3
"""Non-destructive, copy-first restore of the cleanup's original documents."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    ledger = json.loads((HERE / 'migration-ledger.json').read_text())
    marker = ROOT / 'archive/local-checkpoints/cleanup-2026-10-21/rollback-completed.json'
    if marker.exists():
        raise SystemExit('Rollback already completed; inspect the saved receipt before another action')
    head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if head != ledger['baseline_head']:
        raise SystemExit('HEAD changed since cleanup; use the ledger/before-images for a reviewed manual copy-first restore')
    for item in ledger['operations']:
        backup = ROOT / item['before_image']
        if not backup.is_file() or digest(backup) != item['original_sha256']:
            raise SystemExit('Before-image missing or changed: ' + item['before_image'])
        for key in ('original_path','before_image','new_path'):
            value = item.get(key)
            if value and (not (ROOT / value).resolve().is_relative_to(ROOT) or Path(value).is_absolute()):
                raise SystemExit('Unsafe ledger path: ' + value)
    plan = [{'restore': item['original_path'], 'from': item['before_image']} for item in ledger['operations']]
    print(json.dumps({'mode':'apply' if args.apply else 'dry-run', 'restores':plan,
                      'policy':'Copy current cleanup files first; retain new documentation and archived copies; no removals or Git changes.'},indent=2))
    if not args.apply:
        return
    marker.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    saved = ROOT / ('archive/local-checkpoints/rollback-' + stamp)
    saved.mkdir(parents=True, exist_ok=False)
    paths = set(ledger['cleanup_authored_paths'])
    paths.update(item['original_path'] for item in ledger['operations'])
    # Include all subsequently recorded screenshots and reports authored for this review.
    paths.update(str(p.relative_to(ROOT)) for p in HERE.rglob('*') if p.is_file())
    preserved = []
    for name in sorted(paths):
        current = ROOT / name
        if current.is_file():
            if not current.resolve().is_relative_to(ROOT) or current.is_symlink():
                raise SystemExit('Refusing symlink or outside path: ' + name)
            destination = saved / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(current, destination)
            if digest(destination) != digest(current):
                raise SystemExit('Current-version preservation failed: ' + name)
            preserved.append(name)
    restored = []
    # All current versions are copied before the first original document is restored.
    for item in ledger['operations']:
        destination = ROOT / item['original_path']
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / item['before_image'], destination)
        if digest(destination) != item['original_sha256']:
            raise SystemExit('Restore verification failed: ' + item['original_path'])
        restored.append(item['original_path'])
    receipt = {'saved_current_versions':str(saved.relative_to(ROOT)), 'preserved_paths':preserved,'restored_paths':restored,
               'completed_utc':datetime.now(timezone.utc).isoformat(),'new_and_archived_files_retained':True}
    (saved / 'rollback-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    marker.write_text(json.dumps(receipt,indent=2)+'\n')
    print('Original documents restored; current/new versions retained at ' + str(saved))

if __name__ == '__main__':
    main()
