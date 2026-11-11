"""Read-only full CSG database parity and all-profile retrieval verification."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import statistics
import time

from daylight_data.csg_medigap import VARIANTS
from daylight_data.csg_medigap.store import (
    connect, file_sha, read_candidate, Repository, verify_loaded,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--expected-database', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Use a new verification receipt; never overwrite evidence')
    dsn = os.environ['DAYLIGHT_CSG_DATABASE_URL']
    manifest, rates, benefits = read_candidate(args.candidate)
    factory = lambda: connect(dsn, args.expected_database, readonly=True)
    with factory() as c, c.transaction():
        c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        c.execute('SET LOCAL ROLE daylight_csg_reader')
        counts = verify_loaded(c, manifest, rates, benefits)
        total_bytes = c.execute("""SELECT sum(pg_total_relation_size(c.oid)) AS n FROM pg_class c
            JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='dl_csg_medigap' AND c.relkind='r'""").fetchone()['n']
        grants = c.execute("""SELECT
            has_table_privilege('daylight_csg_reader','dl_csg_medigap.rate','SELECT') AS private_read,
            has_table_privilege('daylight_csg_reader','dl_csg_medigap.rate','INSERT') AS private_write,
            has_table_privilege('daylight_research_reader','dl_csg_medigap.rate','SELECT') AS public_evidence_read,
            has_table_privilege('daylight_plan_research_reader','dl_csg_medigap.rate','SELECT') AS plan_type_read""").fetchone()
        assert grants == dict(private_read=True, private_write=False, public_evidence_read=False, plan_type_read=False)
    repo = Repository(factory, manifest['build_id'])
    assert repo.status()['counts'] == counts
    expected = {}
    for row in rates:
        expected.setdefault(row['source_sha256'], {})[row['id']] = row
    durations, profile_checks = [], []
    for source in manifest['sources']:
        s = source['scenario']
        request = dict(zipcode=s['zip'], age=s['age'], gender=s['gender'], tobacco=s['tobacco'],
                       effective_date=s['requested_effective_date'])
        start = time.perf_counter()
        result = repo.query(**request)
        durations.append((time.perf_counter() - start) * 1000)
        assert result['status'] == 'matched_source_observations'
        assert {r['id']: r for r in result['records']} == expected[source['sha256']]
        assert result['consumer_release'] == 'held' and result['personal_quote'] is False
        profile_checks.append(dict(request, returned_rows=result['returned_rows'], all_payloads_match=True))
    base = dict(zipcode='34101', age=65, gender='Female', tobacco='Non-Tobacco', effective_date='2026-11-10')
    full = repo.query(**base)['records']
    variant_checks = {}
    for v in VARIANTS:
        result = repo.query(**base, variant=v)
        assert result['records'] == [r for r in full if r['variant'] == v]
        variant_checks[v] = len(result['records'])
    negative = []
    for change, status in [
        ({'zipcode': '34109'}, 'needs_source_export'),
        ({'zipcode': '34110'}, 'needs_source_export'),
        ({'effective_date': '2026-11-11'}, 'needs_source_export'),
        ({'effective_date': '2027-01-01'}, 'needs_source_export'),
        ({'age': 64}, 'unsupported_pilot_age'),
        ({'age': 75}, 'unsupported_pilot_age')]:
        result = repo.query(**{**base, **change})
        assert result['status'] == status and result['records'] == []
        negative.append({'change': change, 'status': status, 'no_substitution': True})
    result = {
        'database': args.expected_database, 'schema': 'dl_csg_medigap',
        'build_id': manifest['build_id'], 'candidate_manifest_sha256': manifest['candidate_manifest_sha256'],
        'verified_counts': counts, 'all_typed_columns_and_payloads_match': True,
        'scope': manifest['scope'], 'profile_checks': profile_checks, 'variant_checks': variant_checks,
        'negative_checks': negative, 'permissions': grants, 'relation_bytes': int(total_bytes),
        'lookup_milliseconds': {'calls': len(durations), 'median': statistics.median(durations),
            'p95': sorted(durations)[int(len(durations)*.95)-1], 'max': max(durations),
            'basis': 'Serial local reads, fresh connection per exact-profile query; not a production capacity test'},
        'counts_by_zip': dict(Counter(r['scenario']['zip'] for r in rates)),
        'counts_by_variant': dict(Counter(r['variant'] for r in rates)),
        'legal_company_naics': len({r['naic'] for r in rates}),
        'carrier_variant_pairs': len({(r['naic'],r['variant']) for r in rates}),
        'review_findings': manifest['review_findings'], 'consumer_release': 'held',
        'all_market_complete': False, 'verifier_sha256': file_sha(__file__), 'passed': True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as f:
        f.write(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('profile_checks','scope','negative_checks','variant_checks')}))


if __name__ == '__main__':
    main()

