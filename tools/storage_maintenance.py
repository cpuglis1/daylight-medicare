#!/usr/bin/env python3
"""Preserve source bytes, verify recovery, and coalesce exact copies with APFS COW.

Never edits PostgreSQL, Git objects, guest stores, source content, or live app code.
All original paths survive. A restored recovery bundle is mandatory before coalescing.
"""
from __future__ import annotations

import argparse
import collections
import ctypes
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tarfile
import tempfile

RESERVE = 7 * 1024**3
SOURCE_ROOTS = ('docs', 'plans', 'cms-slice', 'alternatives', 'audit-evidence',
                'archive', 'medicare-project-2026-10-17-v1.2', 'tools', '.github')
EXCLUDE_DIRS = {'var', '__pycache__', 'node_modules', '.venv', '.git', '.pytest_cache'}
COALESCE_ROOTS = ('docs/data/', 'plans/', 'cms-slice/data-sources/raw/',
                  'infrastructure/daylight-data/.state/archive/evidence/')


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024**2), b''):
            h.update(b)
    return h.hexdigest()


def write_json(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())


def guard(root, extra=0):
    free = shutil.disk_usage(root).free
    if free < RESERVE + extra:
        raise RuntimeError('Required 7 GiB reserve would be breached')
    return free


def identity(s):
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def regular(root, relative):
    p = root / relative
    if not p.is_relative_to(root) or '..' in Path(relative).parts:
        raise ValueError('Path escapes repository')
    for ancestor in (p, *p.parents):
        if ancestor == root:
            break
        if ancestor.is_symlink():
            raise ValueError('Symlink path is excluded')
    if not stat.S_ISREG(p.lstat().st_mode):
        raise ValueError('Regular file required')
    return p


def stable_hash(path):
    before = path.stat()
    value = digest(path)
    if identity(before) != identity(path.stat()):
        raise RuntimeError('File changed while hashing: ' + str(path))
    return value, before


def source_paths(root):
    roots = [root / n for n in SOURCE_ROOTS]
    roots += [p for p in root.iterdir() if p.is_file() and p.suffix in ('.md', '.json')]
    roots += [root / 'infrastructure/daylight-data/src',
              root / 'infrastructure/daylight-data/migrations',
              root / 'infrastructure/daylight-data/config',
              root / 'infrastructure/daylight-data/tools',
              root / 'infrastructure/daylight-data/tests',
              root / 'infrastructure/daylight-data/.state/archive/evidence']
    seen = set()
    for base in roots:
        if base.is_file():
            candidates = [base]
        else:
            candidates = []
            for d, dirs, files in os.walk(base, followlinks=False):
                dirs[:] = sorted(x for x in dirs if x not in EXCLUDE_DIRS and not (Path(d)/x).is_symlink())
                candidates.extend(Path(d)/x for x in sorted(files))
        for p in candidates:
            if p.is_symlink() or p.name.startswith('.env') or p.name == '.DS_Store' or p.suffix == '.pyc':
                continue
            rel = p.relative_to(root).as_posix()
            if rel not in seen and stat.S_ISREG(p.lstat().st_mode):
                seen.add(rel)
                yield rel, p


def census(root):
    totals = collections.Counter()
    allocated = collections.Counter()
    files = 0
    for d, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = [n for n in dirs if not (Path(d)/n).is_symlink()]
        for n in names:
            p = Path(d)/n
            try:
                s = p.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISREG(s.st_mode):
                key = p.relative_to(root).parts[0]
                totals[key] += s.st_size
                allocated[key] += s.st_blocks * 512
                files += 1
    return {'observed_at': now(), 'files': files, 'logical_bytes': dict(totals),
            'allocated_bytes_nonunique': dict(allocated), 'volume_free_bytes': shutil.disk_usage(root).free,
            'note': 'st_blocks does not identify shared APFS extents; volume deltas include concurrent activity.'}


def inventory(root, run):
    write_json(run/'baseline.json', census(root))
    rows = []
    for i, (relative, p) in enumerate(source_paths(root), 1):
        value, s = stable_hash(p)
        rows.append({'path': relative, 'sha256': value, 'bytes': s.st_size,
                     'mode': stat.S_IMODE(s.st_mode), 'mtime_ns': s.st_mtime_ns,
                     'inode': s.st_ino, 'links': s.st_nlink})
        if i % 10000 == 0:
            print(json.dumps({'hashed_files': i}), flush=True)
    write_json(run/'source-inventory.json', {'schema': 1, 'observed_at': now(), 'files': rows})
    groups = collections.defaultdict(list)
    for row in rows:
        if row['bytes'] >= 1024**2 and row['path'].startswith(COALESCE_ROOTS):
            groups[row['sha256']].append(row)
    duplicates = [{'sha256': h, 'bytes': r[0]['bytes'], 'occurrences': r}
                  for h, r in groups.items() if len(r) > 1]
    duplicates.sort(key=lambda x: (-x['bytes'], x['sha256']))
    write_json(run/'duplicates.json', {'schema': 1, 'groups': duplicates,
               'redundant_logical_bytes': sum(x['bytes']*(len(x['occurrences'])-1) for x in duplicates)})
    print(json.dumps({'source_files': len(rows), 'duplicate_groups': len(duplicates),
                      'duplicate_logical_bytes': sum(x['bytes']*(len(x['occurrences'])-1) for x in duplicates)}), flush=True)


def read_groups(run):
    return json.loads((run/'duplicates.json').read_text())['groups']


def recover(root, run):
    groups = read_groups(run)
    target = run/'source-recovery.tar.gz'
    with target.open('xb') as output:
        os.chmod(target, 0o600)
        with gzip.GzipFile(fileobj=output, mode='wb', filename='', mtime=0, compresslevel=3) as gz:
            with tarfile.open(fileobj=gz, mode='w|') as tar:
                for g in groups:
                    p = regular(root, g['occurrences'][0]['path'])
                    h, before = stable_hash(p)
                    if h != g['sha256']:
                        raise ValueError('Source differs from inventory')
                    info = tarfile.TarInfo(g['sha256'])
                    info.size, info.mode, info.mtime = before.st_size, 0o600, 0
                    with p.open('rb') as source:
                        # Check reserve on every read, including large incompressible files.
                        class Guarded:
                            def read(self, n=-1):
                                guard(root, 64*1024**2)
                                return source.read(n)
                        tar.addfile(info, Guarded())
                    if identity(before) != identity(p.stat()):
                        raise RuntimeError('Recovery source changed')
        output.flush()
        os.fsync(output.fileno())
    expected = {g['sha256']: g['bytes'] for g in groups}
    restored = []
    with tempfile.TemporaryDirectory(prefix='restore-', dir=run) as temp:
        with tarfile.open(target, 'r|gz') as tar:
            for member in tar:
                if not member.isfile() or member.name not in expected or member.size != expected[member.name]:
                    raise ValueError('Unexpected recovery member')
                p = Path(temp)/member.name
                guard(root, member.size + 64*1024**2)
                with tar.extractfile(member) as source, p.open('xb') as out:
                    shutil.copyfileobj(source, out, 1024**2)
                    out.flush()
                    os.fsync(out.fileno())
                if digest(p) != member.name:
                    raise ValueError('Restored source hash differs')
                restored.append(member.name)
                p.unlink()  # Only the freshly restored scratch copy.
    if len(restored) != len(expected) or set(restored) != set(expected):
        raise ValueError('Recovery membership differs')
    write_json(run/'recovery.json', {'schema': 1, 'passed': True, 'verified_at': now(),
        'archive_sha256': digest(target), 'archive_bytes': target.stat().st_size,
        'inventory_sha256': digest(run/'source-inventory.json'),
        'duplicates_sha256': digest(run/'duplicates.json'), 'restored_objects': restored,
        'all_duplicate_candidate_bytes_restored_and_hashed': True,
        'postgresql_full_restore': False, 'off_machine_recovery': False})
    print(json.dumps({'recovery_passed': True, 'restored_objects': len(restored),
                      'archive_bytes': target.stat().st_size}), flush=True)


def kernel_clone(source, destination):
    lib = ctypes.CDLL(None, use_errno=True)
    call = lib.clonefile
    call.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
    call.restype = ctypes.c_int
    if call(os.fsencode(source), os.fsencode(destination), 0):
        raise OSError(ctypes.get_errno(), 'APFS clone failed; no hardlink/copy fallback')


def copy_metadata(source, destination):
    # macOS copyfile.h: ACL | STAT | XATTR, with no data-copy flag.
    lib = ctypes.CDLL(None, use_errno=True)
    call = lib.copyfile
    call.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_uint32]
    call.restype = ctypes.c_int
    if call(os.fsencode(source), os.fsencode(destination), None, 7 | (1 << 18) | (1 << 19)):
        raise OSError(ctypes.get_errno(), 'Native metadata preservation failed')


def coalesce(root, run):
    receipt = json.loads((run/'recovery.json').read_text())
    if (receipt.get('passed') is not True or not receipt.get('all_duplicate_candidate_bytes_restored_and_hashed')
        or receipt['archive_sha256'] != digest(run/'source-recovery.tar.gz')
        or receipt['duplicates_sha256'] != digest(run/'duplicates.json')
        or receipt['inventory_sha256'] != digest(run/'source-inventory.json')):
        raise ValueError('Exact successful recovery receipt required')
    start = guard(root)
    journal = run/'coalesce.jsonl'
    count = 0
    with journal.open('x') as log:
        os.chmod(journal, 0o600)
        for g in read_groups(run):
            canonical = regular(root, g['occurrences'][0]['path'])
            if digest(canonical) != g['sha256']:
                raise ValueError('Canonical source changed')
            for row in g['occurrences'][1:]:
                target = regular(root, row['path'])
                value, before = stable_hash(target)
                if value != g['sha256'] or before.st_size != row['bytes'] or before.st_mtime_ns != row['mtime_ns']:
                    raise ValueError('Duplicate changed since inventory')
                # Preserve special metadata and independently writable inodes.
                if before.st_nlink != 1 or getattr(before, 'st_flags', 0):
                    log.write(json.dumps({'path': row['path'], 'status': 'skipped_links_or_flags'})+'\n')
                    log.flush()
                    continue
                with tempfile.TemporaryDirectory(prefix='.daylight-cow-', dir=target.parent) as temp:
                    replacement = Path(temp)/'replacement'
                    free_before = guard(root, 64*1024**2)
                    kernel_clone(canonical, replacement)
                    copy_metadata(target, replacement)
                    if replacement.stat().st_ino == before.st_ino or digest(replacement) != value:
                        raise ValueError('Clone independence/hash check failed')
                    if identity(target.stat()) != identity(before):
                        raise RuntimeError('Target changed before replacement')
                    event = {'path': row['path'], 'canonical': str(canonical.relative_to(root)),
                             'sha256': value, 'bytes': before.st_size, 'old_inode': before.st_ino,
                             'new_inode': replacement.stat().st_ino, 'status': 'prepared', 'at': now()}
                    log.write(json.dumps(event)+'\n'); log.flush(); os.fsync(log.fileno())
                    os.replace(replacement, target)
                    fd = os.open(target.parent, os.O_RDONLY)
                    try:
                        os.fsync(fd)
                    finally:
                        os.close(fd)
                    if digest(target) != value or stat.S_IMODE(target.stat().st_mode) != row['mode']:
                        raise RuntimeError('Post-replacement verification failed')
                    count += 1
                    event.update(status='verified', volume_free_delta=shutil.disk_usage(root).free-free_before)
                    log.write(json.dumps(event)+'\n'); log.flush(); os.fsync(log.fileno())
    write_json(run/'coalesce-summary.json', {'schema': 1, 'verified_replacements': count,
        'started_free_bytes': start, 'finished_free_bytes': shutil.disk_usage(root).free,
        'all_original_paths_retained': True, 'source_contents_changed': False,
        'postgresql_changed': False, 'git_objects_changed': False})
    print(json.dumps({'verified_replacements': count, 'observed_volume_free_delta': shutil.disk_usage(root).free-start}), flush=True)


def verify(root, run):
    rows = json.loads((run/'source-inventory.json').read_text())['files']
    changed = []
    for row in rows:
        p = regular(root, row['path'])
        h, _ = stable_hash(p)
        if h != row['sha256']:
            changed.append(row['path'])
    write_json(run/'source-parity.json', {'schema': 1, 'verified_at': now(),
        'checked_files': len(rows), 'changed_paths': changed, 'passed': not changed})
    write_json(run/'after.json', census(root))
    print(json.dumps({'checked_files': len(rows), 'changed_files': len(changed), 'passed': not changed}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('inventory', 'recover', 'coalesce', 'verify'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    root, run = args.root.resolve(), args.run.absolute()
    parent = root/'infrastructure/daylight-data/.state/maintenance'
    if not run.is_relative_to(parent) or run.is_symlink():
        raise ValueError('Run directory must be within the private maintenance area')
    run.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(run, 0o700)
    import fcntl
    with (run/'LOCK').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        globals()[args.action](root, run)


if __name__ == '__main__':
    main()
