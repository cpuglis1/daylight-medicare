"""SELECT-only local serving audit, with exact target guards and query timings.

No service control, schema migration, source replay, restore or acceptance write.
The optional output is a new operator receipt, never a replacement build receipt.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from datetime import datetime, timezone

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / 'src'))
from daylight_data.serving import repository_from_env
from daylight_data.serving.binding import SCOPE, digest
from daylight_data.serving.repository import CATALOG, PLAN_OBSERVATIONS, QUALITY_OBSERVATIONS


def verify(repository):
    timings, ids, ordinals, pages = [], [], [], []
    after, snapshot = None, None
    while True:
        started = time.perf_counter()
        page = repository.list_plans(dict(SCOPE), after, 20, expected_snapshot_id=snapshot)
        timings.append({'query': 'list_plans', 'elapsed_ms': round((time.perf_counter() - started) * 1000, 3),
                        'rows': len(page['plans'])})
        snapshot = page['binding']['snapshot_id']
        assert page['total'] == 72 and page['status'] == 'research_only'
        assert all(x['state'] == 'held' for x in page['authority'].values())
        ids.extend(p['offering_id'] for p in page['plans'])
        ordinals.extend(p['source_ordinal'] for p in page['plans'])
        pages.append(page['page'])
        if not page['page']['has_more']:
            break
        after = page['page']['next_after_ordinal']
    assert len(ids) == len(set(ids)) == 72 and ordinals == list(range(1, 73))
    checks = []
    for offering in (ids[0], ids[-1]):
        started = time.perf_counter()
        result = repository.inspect_plan(offering, limit=5, expected_snapshot_id=snapshot)
        timings.append({'query': 'inspect_plan', 'offering_id': offering,
                        'elapsed_ms': round((time.perf_counter() - started) * 1000, 3)})
        for layer, data in result['evidence_by_layer'].items():
            assert len(data['records']) <= 5
            if layer != 'L02':
                for row in data['records']:
                    assert row['output_authority'] == 'held' and row['lineage']['raw_sha256']
                    assert 'conditions' in row and 'raw_source_payload' in row
            checks.append({'offering_id': offering, 'layer': layer,
                           'rows': len(data['records']), 'has_more': data['has_more']})
        if result['evidence_by_layer']['L03']['has_more']:
            cursor = result['evidence_by_layer']['L03']['next_after_entity_id']
            more = repository.inspect_plan(offering, layers=('L03',), limit=5,
                after_entity_id_by_layer={'L03': cursor}, expected_snapshot_id=snapshot)
            a = {r['entity_id'] for r in result['evidence_by_layer']['L03']['records']}
            b = {r['entity_id'] for r in more['evidence_by_layer']['L03']['records']}
            assert a.isdisjoint(b)
    plans = {}
    with repository._read() as (connection, _):
        d = repository.binding.selections
        for name, sql, params in [
            ('catalog', CATALOG, (d['collier']['derivation_id'], d['semantic']['derivation_id'], d['national']['derivation_id'])),
            ('semantic_detail', PLAN_OBSERVATIONS, (d['semantic']['derivation_id'],
                ['ma_semantic_claim_representation', 'ma_semantic_condition_representation'], '', ids[0], 6)),
            ('quality_context', QUALITY_OBSERVATIONS, (d['quality']['derivation_id'],
                ['quality_observation'], '', ids[0].split(':')[1], 6))]:
            plans[name] = connection.execute('EXPLAIN (FORMAT JSON) ' + sql, params).fetchone()['QUERY PLAN']
    return {'schema': 'local-research-serving-audit/1', 'passed': True,
            'observed_at': datetime.now(timezone.utc).isoformat(),
            'binding': page['binding'], 'scope': dict(SCOPE), 'plans': 72,
            'distinct_ids': len(set(ids)), 'source_ordinals_sha256': digest(ordinals),
            'offering_ids_sha256': digest(ids), 'pages': pages, 'inspection_checks': checks,
            'query_timings': timings, 'query_plans': plans, 'consumer_authority': 'held', 'new_acceptance': False,
            'source_or_database_mutated': False,
            'condition_semantics_verified': False, 'integrated_all15_consumer_service': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repository = repository_from_env(repository_root=args.repository)
    result = verify(repository)
    result['operator_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    # Exclusive creation preserves all earlier audits. Only this new receipt is written.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write('\n')
    print(json.dumps({'passed': result['passed'], 'plans': result['plans'],
                      'output_sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
                      'query_timings': result['query_timings']}))


if __name__ == '__main__':
    main()
