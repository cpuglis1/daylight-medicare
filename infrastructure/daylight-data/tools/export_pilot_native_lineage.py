"""Exact-ID, SELECT-only source lineage export for the declared internal pilot.

No new source acquisition, schema/data mutation, acceptance or consumer release.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timezone

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / 'src'))
from daylight_data.serving.native_lineage import native_repository_from_env


def write_new(path, value):
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'w') as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.request.stat().st_size > 256 * 1024:
        raise ValueError('NATIVE_REQUEST_TOO_LARGE')
    request = json.loads(args.request.read_text())
    if request.get('offering_id') != '2026:H5652:002:000':
        raise ValueError('EXACT_DECLARED_PILOT_REQUIRED')
    repository = native_repository_from_env(repository_root=args.repository)
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    receipt = {'schema': 'pilot-native-lineage-lookup/1', 'observed_at': datetime.now(timezone.utc).isoformat(),
               'offering_id': request['offering_id'],
               'request_sha256': hashlib.sha256(args.request.read_bytes()).hexdigest(),
               'operator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'artifacts': {}, 'queries': [], 'research_only': True, 'new_acceptance': False,
               'database_or_source_mutated': False, 'semantic_verification': False}
    for kind, request_key in [('native_observations', 'observation_ids'),
                               ('native_sources', 'source_ids'), ('native_relationships', 'representation_ids'),
                               ('native_clauses', 'clause_ids')]:
        if request_key not in request:
            continue
        after, pages = 0, []
        while True:
            started = time.perf_counter()
            page = repository.lookup(kind, request[request_key], after_ordinal=after)
            receipt['queries'].append({'kind': kind, 'elapsed_ms': round((time.perf_counter()-started)*1000, 3),
                'rows': len(page['records']), 'has_more': page['has_more'],
                'sql': page['source_query'], 'parameters': page['query_parameters']})
            pages.append(page)
            if not page['has_more']: break
            if len(pages) >= 10:
                raise ValueError('NATIVE_RELATIONSHIP_EXPORT_BOUND_REACHED')
            after = page['next_after_ordinal']
        name = kind + '.json'
        receipt['artifacts'][name] = {'sha256': write_new(args.output / name, pages),
            'requested_ids': len(request[request_key]), 'records': sum(len(p['records']) for p in pages),
            'missing_ids': pages[0].get('missing_ids') if len(pages) == 1 else None}
    write_new(args.output / 'LOOKUP_RECEIPT.json', receipt)
    print(json.dumps({'artifacts': receipt['artifacts'], 'queries':
        [{k:v for k,v in q.items() if k not in {'sql','parameters'}} for q in receipt['queries']]}))


if __name__ == '__main__':
    main()
