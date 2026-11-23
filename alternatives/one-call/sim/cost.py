"""What each visit on the one-call variant cost, summed from its content-free turn trace.

    cd alternatives/one-call
    python3 -m sim.cost                  # the live server's trace (var/one-call-turn-trace.jsonl)
    python3 -m sim.cost path/to/trace.jsonl

The trace holds codes, counts, token numbers, dollars and seconds for each typed
turn. It holds nothing a person or the model wrote, and neither does this report.
Dollars are the amounts the budget ledger settled for the turn's requests; a
request the ledger could not settle is counted under ``unresolved``.
"""
import json
from pathlib import Path
import sys

DEFAULT = Path(__file__).resolve().parents[1] / 'var' / 'one-call-turn-trace.jsonl'
NUMBERS = ('requests', 'input_tokens', 'cached_tokens', 'output_tokens', 'settled_nano_usd', 'unresolved_attempts')


def read(path):
    """The trace's lines as dicts. A line that is not one JSON object is skipped and counted."""
    rows, skipped = [], 0
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            row = None
        if isinstance(row, dict) and isinstance(row.get('visit'), str):
            rows.append(row)
        else:
            skipped += 1
    return rows, skipped


def _number(value):
    return value if type(value) in (int, float) else 0


def summarise(rows):
    """One total per visit, in the order visits first appear, and one grand total."""
    visits = {}
    for row in rows:
        total = visits.setdefault(row['visit'], {
            'visit': row['visit'], 'first': row.get('at'), 'last': row.get('at'), 'turns': 0, 'fallbacks': 0,
            'fallback_reasons': {}, 'retries': 0, 'tool_calls': 0, 'seconds': 0.0, **{key: 0 for key in NUMBERS}})
        total['turns'] += 1
        total['last'] = row.get('at') or total['last']
        total['seconds'] += _number(row.get('seconds'))
        total['retries'] += 1 if row.get('retry') else 0
        total['tool_calls'] += len(row.get('tools') or [])
        if row.get('fallback'):
            total['fallbacks'] += 1
            reason = row.get('fallback_reason') if isinstance(row.get('fallback_reason'), str) else 'unknown'
            total['fallback_reasons'][reason] = total['fallback_reasons'].get(reason, 0) + 1
        for key in NUMBERS:
            total[key] += _number(row.get(key))
    listed = list(visits.values())
    for total in listed:
        total['usd'] = round(total['settled_nano_usd'] / 1e9, 6)
        total['seconds'] = round(total['seconds'], 2)
    overall = {key: sum(total[key] for total in listed) for key in (*NUMBERS, 'turns', 'fallbacks', 'retries', 'tool_calls')}
    overall['usd'] = round(overall['settled_nano_usd'] / 1e9, 6)
    overall['visits'] = len(listed)
    return listed, overall


def report(listed, overall, skipped=0):
    lines = ['%-12s  %5s  %8s  %10s  %10s  %8s  %9s  %9s  %s' % (
        'visit', 'turns', 'requests', 'input', 'cached', 'output', 'dollars', 'fallbacks', 'fallback reasons')]
    for total in listed:
        reasons = ', '.join('%s x%d' % item for item in sorted(total['fallback_reasons'].items())) or '-'
        lines.append('%-12s  %5d  %8d  %10d  %10d  %8d  %9.4f  %9d  %s' % (
            total['visit'], total['turns'], total['requests'], total['input_tokens'], total['cached_tokens'],
            total['output_tokens'], total['usd'], total['fallbacks'], reasons))
    lines.append('%-12s  %5d  %8d  %10d  %10d  %8d  %9.4f  %9d' % (
        'all (%d)' % overall['visits'], overall['turns'], overall['requests'], overall['input_tokens'],
        overall['cached_tokens'], overall['output_tokens'], overall['usd'], overall['fallbacks']))
    if overall['unresolved_attempts']:
        lines.append('Requests the ledger could not settle (not in the dollars above): %d' % overall['unresolved_attempts'])
    if skipped:
        lines.append('Lines skipped because they were not trace lines: %d' % skipped)
    return '\n'.join(lines)


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) > 1 or arguments and arguments[0] in ('-h', '--help'):
        print(__doc__.strip())
        return 0 if arguments and arguments[0] in ('-h', '--help') else 2
    path = Path(arguments[0]) if arguments else DEFAULT
    if not path.is_file():
        print('No turn trace at %s. The live 8897 server writes one line per typed turn.' % path)
        return 1
    rows, skipped = read(path)
    print(report(*summarise(rows), skipped))
    return 0


if __name__ == '__main__':
    sys.exit(main())
