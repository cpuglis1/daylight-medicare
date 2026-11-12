"""Compare canonical alternative source; explicitly apply source-only updates if requested."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

SOURCE = Path(__file__).resolve().parents[1]
CANONICAL = Path('/Users/cep4u/daylight/alternatives/chat-first')
TARGET = Path('/Users/cep4u/daylight-chat-alternative-runtime')
SERVICE = 'gui/501/com.daylight.chat-alternative.8891'
PARTS = ('apps', 'scripts', 'config')
SUFFIXES = {'.py', '.js', '.css', '.html', '.json', '.svg', '.woff', '.woff2', '.ttf', '.jpg', '.jpeg', '.png', '.webp', '.txt'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_files(root):
    files = {}
    for part in PARTS:
        directory = root / 'cms-slice' / part
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError(f'Expected a real source directory: {directory}')
        for path in sorted(directory.rglob('*')):
            relative = path.relative_to(root)
            if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root):
                raise ValueError(f'Symlink is not a deployable input: {relative}')
            if '__pycache__' in path.parts or path.name == '.DS_Store' or path.suffix == '.pyc':
                continue
            if not path.is_file():
                continue
            if path.suffix not in SUFFIXES or path.name.startswith('.'):
                raise ValueError(f'Unreviewed source file type: {relative}')
            files[relative] = path
    return files


def service_identity():
    state = subprocess.check_output(['launchctl', 'print', SERVICE], text=True)
    expected = (
        f'path = {TARGET}/runtime/com.daylight.chat-alternative.8891.plist',
        f'working directory = {TARGET}',
        str(TARGET / 'cms-slice/scripts/chat_server.py'),
        'state = running',
    )
    if not all(item in state for item in expected):
        raise ValueError('Alternative launchd identity does not match; no update performed.')
    match = re.search(r'^\s*pid = (\d+)\s*$', state, re.MULTILINE)
    if not match:
        raise ValueError('Alternative launchd PID is missing; no update performed.')
    listener = subprocess.check_output(
        ['lsof', '-nP', '-t', '-iTCP:8891', '-sTCP:LISTEN'], text=True
    ).split()
    if set(listener) != {match[1]}:
        raise ValueError('Port 8891 is not owned solely by the expected job; no update performed.')
    return int(match[1])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='Compare only (the default).')
    mode.add_argument('--apply', action='store_true', help='Copy changed source files, preserving before-images.')
    parser.add_argument('--restart', action='store_true', help='With --apply, restart only the verified alternative if source changed.')
    args = parser.parse_args(argv)
    if args.restart and not args.apply:
        parser.error('--restart requires --apply')
    if SOURCE != CANONICAL or TARGET.is_symlink() or not TARGET.is_dir():
        raise ValueError('Use the canonical source and the existing real alternative runtime.')
    files = source_files(SOURCE)
    runtime_files = source_files(TARGET)
    changed = [name for name, path in files.items() if name not in runtime_files or digest(path) != digest(runtime_files[name])]
    extra = sorted(str(name) for name in runtime_files.keys() - files.keys())
    summary = {'source': str(SOURCE), 'runtime': str(TARGET), 'sourceFiles': len(files), 'changed': [str(name) for name in changed], 'runtimeOnlyPreserved': extra}
    if not args.apply or not changed:
        summary['action'] = 'check only' if not args.apply else 'already synchronized; no restart'
        print(json.dumps(summary, indent=2))
        return 1 if changed else 0
    pid = service_identity()
    backup = SOURCE / 'runtime/backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup.mkdir(parents=True, exist_ok=False)
    manifest = {'source': str(SOURCE), 'target': str(TARGET), 'service': SERVICE, 'pidBefore': pid, 'files': {}}
    for name in changed:
        old = TARGET / name
        saved = backup / name
        manifest['files'][str(name)] = {'before': digest(old) if old.is_file() else None, 'after': digest(files[name])}
        if old.is_file():
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old, saved)
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    # Recheck identity before the first write. No storage/launch/env files are in this list.
    if service_identity() != pid:
        raise ValueError('Service changed during preparation; no update performed.')
    for name in changed:
        destination = TARGET / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(files[name], destination)
        if digest(destination) != manifest['files'][str(name)]['after']:
            raise ValueError(f'Copy verification failed; before-images are in {backup}')
    if args.restart:
        if service_identity() != pid:
            raise ValueError(f'Service changed; source copied but restart withheld. Backup: {backup}')
        subprocess.run(['launchctl', 'kickstart', '-k', SERVICE], check=True)
    summary.update(action='source updated', backup=str(backup), restartRequested=args.restart)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
