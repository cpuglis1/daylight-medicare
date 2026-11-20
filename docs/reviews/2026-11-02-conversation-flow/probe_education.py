"""Read-only curriculum probes with fictional visit state and no network."""
import json
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'alternatives/advisor-first'))


def denied(*args, **kwargs):
    raise AssertionError('Network forbidden in this review')


socket.create_connection = denied
socket.socket.connect = denied
from education import empty_record, plan_update


def proposal(concept, depth, reason, evidence, visual='none', purpose='teach'):
    return {'purpose': purpose, 'updates': [{'concept_id': concept,
            'depth': depth, 'reason': reason, 'evidence_refs': [evidence]}],
            'visual': visual}


record = empty_record()
depth_results = []
for index, (depth, reason) in enumerate([
        ('introduced', 'new'), ('explored', 'deepen'), ('explored', 'deepen')]):
    result = plan_update(record, proposal('provider_checks', depth, reason, 'checks'),
                         ['checks'], event_id=f'review:{index}')
    record = result['record']
    depth_results.append({'depth': depth, 'reason': reason,
                          'accepted_updates': len(result['accepted_updates']),
                          'issues': result['issues'],
                          'record': record['concepts']['provider_checks']})

first = plan_update(empty_record(),
                    proposal('coverage_paths', 'introduced', 'new', 'routesintro', 'routes'),
                    ['routesintro'], event_id='review:intro')
clarify = plan_update(first['record'],
                     proposal('coverage_paths', 'explored', 'clarify', 'routesintro',
                              'routes', 'clarify'),
                     ['routesintro'], requested_revisit=True,
                     revisit_concepts=['coverage_paths'], event_id='review:clarify')

print(json.dumps({'scope': 'Deterministic metadata probes; not model or UI observations',
                  'paid_model_calls': 0, 'depth_sequence': depth_results,
                  'current_clarification': {
                      'accepted_updates': len(clarify['accepted_updates']),
                      'issues': clarify['issues'], 'visual': clarify['visual']}}, indent=2))
