#!/usr/bin/env python3
"""Read-only freshness check and whole-record annual/revision diff. Never approve."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from l01 import PACKAGE, Acceptance, load, verify


def compare(baseline, candidate):
    changes = []
    for filename in ['facts.json', 'bands.json', 'rules.json', 'inventory.json', 'sources.json']:
        def keyed(path):
            value = load(Path(path) / filename)
            if isinstance(value, dict):
                value = value['obligations']
            return {row['id']: row for row in value}
        old, new = keyed(baseline), keyed(candidate)
        for id in sorted(set(old) | set(new)):
            if old.get(id) != new.get(id):
                changes.append({'file': filename, 'id': id, 'before': old.get(id), 'after': new.get(id),
                                'action': 're-review changed claim and all dependent outputs; prior decision retained'})
    return {'baseline': str(baseline), 'candidate': str(candidate), 'changes': changes,
            'acceptance_carried_forward': False, 'automatic_release': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['check', 'compare'])
    p.add_argument('--baseline', type=Path, default=PACKAGE)
    p.add_argument('--candidate', type=Path)
    a = p.parse_args()
    if a.action == 'compare':
        if a.candidate is None:
            p.error('--candidate is required')
        result = compare(a.baseline, a.candidate)
    else:
        try:
            m = verify(a.baseline, datetime.now(timezone.utc))
            result = {'technical_integrity': 'passed', 'source_review_after_utc': m['source_review_after_utc'], 'acceptance': Acceptance(a.baseline).status()}
        except (OSError, ValueError, KeyError, TypeError):
            result = {'technical_integrity': 'held', 'historical_evidence_retained': True, 'acceptance_extended': False}
    print(json.dumps(result, indent=2))
