#!/usr/bin/env python3
"""Print one saved advisor turn trace by its turn ID, for agents and Charlie (D155 Q6b).

Local runs of the advisor (:8893, viewed through :8894) save each turn as
``cms-slice/var/turn-traces/<turnId>.json`` (see
``alternatives/advisor-first/turn_trace.py``). The turn ID is the request ID
shown at the top of the :8894 side panel.

Usage:
    python3 tools/show_turn.py <turnId>            # the full JSON record
    python3 tools/show_turn.py <turnId> --summary  # facts, lookups, calls, checks, next question
    python3 tools/show_turn.py --list [N]          # the newest N turn IDs (default 20)

Env:
    DAYLIGHT_TURN_TRACES_DIR  optional override of the trace directory.

This reads local files only; it makes no network or model calls.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'alternatives/advisor-first'))
from turn_trace import TraceStore  # noqa: E402  (path set just above)


def summary(record):
    """Return a short readable view of one turn record.

    Args:
        record: a saved turn trace.
    Returns:
        Multi-line text: turn, message, facts saved, lookups, model calls,
        checks fired and next question; prompts and raw output are left to
        the full JSON view.
    """
    lines = [f"Turn {record['turnId']}  {record.get('startedAt')}  {record.get('status')}  {record.get('latencyMs')} ms",
             f"Message: {record.get('message')!r}  (action {record.get('action')})"]
    lines.append('Facts saved:' if record.get('factsSaved') else 'Facts saved: none')
    lines += [f"  {row['field']}: {row['before']!r} -> {row['after']!r}" for row in record.get('factsSaved') or []]
    lines.append('Tool calls:')
    lines += [f"  {call['tool']} ({call['stage']}) in={json.dumps(call['input'])} out={json.dumps(call['output'])}"
              for call in record.get('toolCalls') or []]
    lines.append('Model calls:')
    lines += [f"  {call['kind']} {call.get('model')} {call.get('status')} {call.get('latencyMs')} ms tokens={call.get('tokens')}"
              + (f" error={call['error']}" if call.get('error') else '')
              for call in record.get('modelCalls') or []]
    lines.append('Checks fired:' if record.get('checks') else 'Checks fired: none')
    lines += [f"  [{check['source']}] {check['message']}" for check in record.get('checks') or []]
    lines.append(f"Next question: {json.dumps(record.get('nextQuestion'))}")
    if record.get('error'):
        lines.append(f"Error: {record['error']}")
    return '\n'.join(lines)


def main(argv=None):
    """Parse arguments, read the store and print; return a process exit code."""
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('turn_id', nargs='?')
    parser.add_argument('--summary', action='store_true')
    parser.add_argument('--list', nargs='?', const=20, type=int, metavar='N')
    args = parser.parse_args(argv)
    root = Path(os.environ.get('DAYLIGHT_TURN_TRACES_DIR') or REPO / 'cms-slice/var/turn-traces')
    if not root.is_dir():
        print(f'No turn traces at {root}. Run the advisor locally first.', file=sys.stderr)
        return 1
    store = TraceStore(root)
    if args.list is not None:
        for row in store.list(limit=args.list):
            print(f"{row['turnId']}  {row['startedAt']}  {row['status']}  {(row.get('message') or row.get('action') or '')[:60]}")
        return 0
    if not args.turn_id:
        parser.error('give a turn ID or --list')
    try:
        record = store.get(args.turn_id)
    except ValueError as error:
        parser.error(str(error))
    if record is None:
        print(f'No turn {args.turn_id} in {root}.', file=sys.stderr)
        return 1
    print(summary(record) if args.summary else json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
