"""Explicit local CSG backend operations; no automatic acquisition or app activation."""
import argparse
import json
import os
from pathlib import Path

from .store import connect, install, load, read_candidate, Repository, select_research, verify_loaded


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['install', 'load', 'verify', 'select-research', 'status', 'query'])
    p.add_argument('--expected-database', required=True)
    p.add_argument('--candidate')
    p.add_argument('--build-id')
    p.add_argument('--request', help='Local JSON request, never a participant profile in a URL')
    p.add_argument('--reason')
    a = p.parse_args()
    dsn = os.environ['DAYLIGHT_CSG_DATABASE_URL']
    readonly = a.command in ('status', 'query', 'verify')
    if a.command in ('status', 'query'):
        repo = Repository(lambda: connect(dsn, a.expected_database, readonly=True), a.build_id)
        result = repo.status() if a.command == 'status' else repo.query(**json.loads(Path(a.request).read_text()))
    else:
        with connect(dsn, a.expected_database, readonly=readonly) as c:
            if a.command == 'install':
                install(c); result = {'schema': 'dl_csg_medigap', 'consumer_release': 'held'}
            elif a.command == 'load':
                result = load(c, a.candidate)
            elif a.command == 'select-research':
                select_research(c, a.build_id, a.reason); result = {'selected_research': a.build_id, 'consumer_release': 'held'}
            else:
                m, rates, benefits = read_candidate(a.candidate)
                with c.transaction():
                    c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                    c.execute('SET LOCAL ROLE daylight_csg_reader')
                    result = {'build_id': m['build_id'], 'verified_counts': verify_loaded(c, m, rates, benefits)}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
