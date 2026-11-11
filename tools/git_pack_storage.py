#!/usr/bin/env python3
"""Coalesce stale temporary pack prefixes without pruning any Git object/file.

Uses only a fixed census of tmp_pack_* files. Exact full-file hashes, an actual
restore from an independent compressed bundle, no open handles, and stable file
identities are mandatory. All names, lengths and bytes survive unchanged.
"""
import argparse
import collections
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import uuid

import storage_maintenance as m


def prefix_hashes(path, lengths):
    h = hashlib.sha256(); previous = 0; result = {}
    with path.open('rb') as source:
        for length in sorted(set(lengths)):
            remaining = length-previous
            while remaining:
                block = source.read(min(remaining, 1024**2))
                if not block:
                    raise ValueError('Truncated canonical pack')
                h.update(block); remaining -= len(block)
            result[length] = h.hexdigest(); previous = length
    return result


def plan(root, run):
    census = json.loads((run/'git-garbage-census.json').read_text())
    groups = collections.defaultdict(list)
    for row in census['files']:
        if not re.fullmatch(r'\.git/objects/pack/tmp_pack_[A-Za-z0-9]+', row['path']) or row['bytes'] < 1024**2:
            continue
        p = m.regular(root, row['path']); value, before = m.stable_hash(p)
        if before.st_size != row['bytes'] or before.st_mtime_ns != row['mtime_ns'] or before.st_nlink != 1:
            raise ValueError('Temporary pack changed since census')
        with p.open('rb') as source:
            head = hashlib.sha256(source.read(1024**2)).hexdigest()
        groups[head].append(dict(row, sha256=value, mode=before.st_mode & 0o777))
    result = []
    for rows in groups.values():
        if len(rows) < 2:
            continue
        rows.sort(key=lambda x: (-x['bytes'], x['path']))
        canonical = rows[0]
        prefixes = prefix_hashes(root/canonical['path'], [r['bytes'] for r in rows])
        matches = [r for r in rows if prefixes[r['bytes']] == r['sha256']]
        if len(matches) > 1:
            result.append({'canonical': canonical, 'occurrences': matches})
    m.write_json(run/'git-prefix-plan.json', {'groups': result, 'no_pruning': True,
        'redundant_prefix_bytes': sum(r['bytes'] for g in result for r in g['occurrences'][1:])})
    print(json.dumps({'prefix_groups': len(result), 'candidate_bytes': sum(r['bytes'] for g in result for r in g['occurrences'][1:])}), flush=True)


def recover(root, run):
    groups = json.loads((run/'git-prefix-plan.json').read_text())['groups']
    archive = run/'git-pack-recovery.tar.gz'
    with archive.open('xb') as output:
        os.chmod(archive, 0o600)
        with gzip.GzipFile(fileobj=output, mode='wb', filename='', mtime=0, compresslevel=1) as gz:
            with tarfile.open(fileobj=gz, mode='w|') as tar:
                for group in groups:
                    row = group['canonical']; p = m.regular(root, row['path'])
                    if m.digest(p) != row['sha256']:
                        raise ValueError('Canonical changed')
                    m.guard(root, row['bytes'] + 64*1024**2)
                    info = tarfile.TarInfo(row['sha256']); info.size=row['bytes']; info.mode=0o600
                    with p.open('rb') as source:
                        tar.addfile(info, source)
        output.flush(); os.fsync(output.fileno())
    expected = {g['canonical']['sha256']: g for g in groups}
    restored = []
    with tempfile.TemporaryDirectory(prefix='git-restore-', dir=run) as directory:
        with tarfile.open(archive, 'r|gz') as tar:
            for member in tar:
                if not member.isfile() or member.name not in expected:
                    raise ValueError('Unexpected recovery member')
                group = expected[member.name]
                if member.size != group['canonical']['bytes']:
                    raise ValueError('Recovery size differs')
                p = Path(directory)/member.name
                m.guard(root, member.size + 64*1024**2)
                with tar.extractfile(member) as source, p.open('xb') as out:
                    shutil.copyfileobj(source, out, 1024**2); out.flush(); os.fsync(out.fileno())
                recovered = prefix_hashes(p, [row['bytes'] for row in group['occurrences']])
                for row in group['occurrences']:
                    if recovered[row['bytes']] != row['sha256']:
                        raise ValueError('Recovered prefix differs')
                    restored.append(row['path'])
                p.unlink()
    if len(restored) != sum(len(g['occurrences']) for g in groups):
        raise ValueError('Recovery membership differs')
    m.write_json(run/'git-pack-recovery.json', {'passed': True, 'archive_sha256': m.digest(archive),
        'archive_bytes': archive.stat().st_size, 'plan_sha256': m.digest(run/'git-prefix-plan.json'),
        'restored_original_files': restored, 'all_original_bytes_verified': True,
        'full_repository_restore': False})
    print(json.dumps({'git_file_recovery_passed': True, 'files': len(restored), 'archive_bytes': archive.stat().st_size}), flush=True)


def ensure_closed(paths):
    result = subprocess.run(['/usr/sbin/lsof', '-nP', '-t', '--', *map(str, paths)], capture_output=True, text=True)
    # 1 with no output means no open handles. Any warning/error fails closed.
    if result.returncode != 1 or result.stdout.strip() or result.stderr.strip():
        raise RuntimeError('Cannot establish that temporary packs have no open handles')


def apply(root, run):
    receipt = json.loads((run/'git-pack-recovery.json').read_text())
    if (receipt.get('passed') is not True or receipt['plan_sha256'] != m.digest(run/'git-prefix-plan.json')
            or receipt['archive_sha256'] != m.digest(run/'git-pack-recovery.tar.gz')):
        raise ValueError('Exact successful recovery required')
    groups = json.loads((run/'git-prefix-plan.json').read_text())['groups']
    paths = [root/row['path'] for g in groups for row in g['occurrences']]
    ensure_closed(paths)
    start = m.guard(root); replaced = []
    journal = run/('git-coalesce-'+uuid.uuid4().hex[:8]+'.jsonl')
    with journal.open('x') as log:
        for group in groups:
            canonical = m.regular(root, group['canonical']['path'])
            if m.digest(canonical) != group['canonical']['sha256']:
                raise ValueError('Canonical pack changed')
            for row in group['occurrences'][1:]:
                p = m.regular(root, row['path']); value, before = m.stable_hash(p)
                if (value != row['sha256'] or before.st_size != row['bytes']
                        or before.st_mtime_ns != row['mtime_ns'] or before.st_nlink != 1
                        or getattr(before, 'st_flags', 0)):
                    raise ValueError('Temporary pack changed')
                m.guard(root, 64*1024**2)
                with tempfile.TemporaryDirectory(prefix='cow-pack-', dir=run) as directory:
                    clone = Path(directory)/'pack'
                    m.kernel_clone(canonical, clone)
                    clone.chmod(0o600)  # Only the private clone; Git packs are read-only.
                    with clone.open('r+b') as out:
                        out.truncate(row['bytes']); out.flush(); os.fsync(out.fileno())
                    m.copy_metadata(p, clone)
                    if m.digest(clone) != value or clone.stat().st_ino == before.st_ino:
                        raise ValueError('Independent clone hash differs')
                    ensure_closed([p, canonical])
                    if m.identity(p.stat()) != m.identity(before):
                        raise RuntimeError('Temporary pack changed before replacement')
                    event = {'path': row['path'], 'sha256': value, 'bytes': row['bytes'], 'status': 'prepared'}
                    log.write(json.dumps(event)+'\n'); log.flush(); os.fsync(log.fileno())
                    os.replace(clone, p)
                    directory_fd = os.open(p.parent, os.O_RDONLY)
                    try:
                        os.fsync(directory_fd)
                    finally:
                        os.close(directory_fd)
                    if m.digest(p) != value or p.stat().st_mtime_ns != row['mtime_ns']:
                        raise ValueError('Replacement verification failed')
                    event['status'] = 'verified'; replaced.append(event)
                    log.write(json.dumps(event)+'\n'); log.flush(); os.fsync(log.fileno())
    m.write_json(run/'git-coalesce-summary.json', {'verified_replacements': len(replaced),
        'observed_volume_free_delta': shutil.disk_usage(root).free-start,
        'all_original_paths_retained': True, 'all_original_bytes_retained': True,
        'journal': journal.name,
        'refs_index_and_normal_git_objects_modified': False, 'git_pruning_executed': False})
    print(json.dumps({'verified_git_prefix_replacements': len(replaced),
        'observed_volume_free_delta': shutil.disk_usage(root).free-start}), flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('plan', 'recover', 'apply'))
    p.add_argument('--root', required=True, type=Path); p.add_argument('--run', required=True, type=Path)
    args=p.parse_args(); root=args.root.resolve(); run=args.run.resolve()
    if not run.is_relative_to(root/'infrastructure/daylight-data/.state/maintenance'):
        raise ValueError('Private maintenance directory required')
    globals()[args.action](root, run)


if __name__ == '__main__':
    main()
