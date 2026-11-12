"""Export only the existing fixed controller diagnostic grammar, never log text.

Read-only inspection of the two configured advisor log paths. No request,
profile, exception message, source snippet or arbitrary log line is exported.
Events lack request identity and cannot retrospectively identify an owner turn.
"""
import collections
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / 'alternatives/advisor-first/var/logs'
EVENT = re.compile(rb'Daylight controller failure code=(unexpected_exception) '
    rb'type=([A-Za-z][A-Za-z0-9_]{0,63}) '
    rb'locations=(unavailable|[a-z_]+\.py:[0-9]+(?:,[a-z_]+\.py:[0-9]+){0,7})\r?\n?$')


def scan():
    reports = []
    for name in ('service.log', 'errors.log'):
        path = LOGS / name
        if not path.is_file() or path.is_symlink():
            reports.append({'path': str(path.relative_to(ROOT)), 'status': 'absent_or_symlink'})
            continue
        before = path.stat()
        counts = collections.Counter()
        omitted_unparsed_fixed_prefix = 0
        with path.open('rb') as stream:
            # Do not decode, print or retain broad logs. Only exact code-defined
            # scalar diagnostic fields can leave this streaming filter.
            for line in stream:
                match = EVENT.search(line)
                if match:
                    counts[tuple(part.decode('ascii') for part in match.groups())] += 1
                elif b'Daylight controller failure ' in line:
                    omitted_unparsed_fixed_prefix += 1
        after = path.stat()
        reports.append({'path': str(path.relative_to(ROOT)), 'status': 'scanned_fixed_grammar_only',
            'size_before': before.st_size, 'size_after': after.st_size,
            'same_inode_and_size_during_scan': (before.st_ino, before.st_size) == (after.st_ino, after.st_size),
            'events': [{'code': key[0], 'type': key[1], 'locations': key[2], 'count': count}
                       for key, count in sorted(counts.items())],
            'unparsed_fixed_prefix_lines_omitted': omitted_unparsed_fixed_prefix})
    return {'schema': 'daylight.valuefree-controller-event-scan.v1',
        'recorded_at': datetime.now(timezone.utc).isoformat(),
        'operator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'scope': 'Two currently configured logs, exact fixed diagnostic grammar only; no customer stores.',
        'logs': reports,
        'matching_events': sum(event['count'] for row in reports for event in row.get('events', [])),
        'original_incident_cause_established': False,
        'limits': 'No request identity or historical phase trace; absent matches cannot establish that no error occurred. No rotated logs are present. No broad log bodies are exported or copied.'}


if __name__ == '__main__':
    target = Path(__file__).with_name('VALUEFREE_RUNTIME_DIAGNOSTICS.json')
    with target.open('x') as stream:
        json.dump(scan(), stream, indent=2)
        stream.write('\n')
    print(json.dumps({'output': str(target), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}))
