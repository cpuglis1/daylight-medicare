#!/usr/bin/env python3
"""Reproducible fictional examples and capability accounting; no model calls."""
import argparse
import json
from pathlib import Path

from understanding_scenarios import cost_example
from understanding import UnderstandingRegistry, attach_understanding
from understanding_reference import PublishedCostReference


def examples():
    registry = UnderstandingRegistry()
    output = []
    for visual, refs in [('transition', ['enrollment_intro', 'cobra_timing', 'dates']),
                         ('routes', ['routesintro', 'options', 'medigap', 'switching']),
                         ('costs', ['costs', 'medical_limit'])]:
        turn = {'guide': {'stateVersion': 1}, 'record': {'stateVersion': 1},
            'advisor': {'visual': visual, 'teachingFactIds': refs},
            'reportedRows': [{'id': 'S_AGE65', 'value': 'November (year not given)', 'status': 'reported'},
                {'id': 'RC11', 'value': {'jobEnd': 'October 2026', 'coverageEnd': 'December 2026'}, 'status': 'reported'},
                {'id': 'T04', 'label': 'Preferred coverage start', 'value': 'January 2027', 'status': 'reported'}]}
        attach_understanding(turn, registry=registry)
        output.append(turn['understanding'])
    return {'fictional_reports': True, 'guides': output,
            'scenarios': [cost_example(2), cost_example(12)]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Write reproducible inventory and fictional examples as JSON.')
    parser.add_argument('--published-cost-id', help='Inspect one exact accepted L01 reference entry; no personal inputs.')
    args = parser.parse_args()
    result = (PublishedCostReference().lookup({'year': 2026, 'ids': [args.published_cost_id]})
              if args.published_cost_id else {'inventory': UnderstandingRegistry().inventory(), 'examples': examples()})
    text = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    else:
        print(text, end='')
