#!/usr/bin/env python3
"""Read-only local preflight: refuse a copy whose source controls have changed."""
import argparse
import getpass
import json
from pathlib import Path

from build_pilot_subset import PACKAGE, SOURCE_DB, controls, csg_hashes
from daylight_data.csg_medigap.store import connect
from daylight_data.pilot_subset.store import CSG_BUILD, PDP_BUILD, KINDS
from daylight_data.csg_medigap.store import Repository as CsgRepository
from daylight_data.plan_types.store import Repository as PlanRepository
from daylight_data.plan_types.common import digest, file_sha


def check(directory, *, full=False):
    manifest = json.loads((directory / 'manifest.json').read_text())
    binding = json.loads((directory / 'binding.json').read_text())
    if digest(manifest) != binding['snapshot_id']:
        raise ValueError('PILOT_MANIFEST_MISMATCH')
    dsn = (f'host={PACKAGE / ".state/socket"} port=55485 '
           f'dbname={SOURCE_DB} user={getpass.getuser()}')
    factory = lambda: connect(dsn, SOURCE_DB, readonly=True)
    with factory() as c:
        if digest(controls(c)) != manifest['source_controls_sha256']:
            raise ValueError('SOURCE_CONTROLS_CHANGED: reconcile STOP/review/selection history and export a new revision')
        if full and csg_hashes(c) != manifest['csg_tables']:
            raise ValueError('SOURCE_DATA_CHANGED')
    CsgRepository(factory, CSG_BUILD).status()
    pdp = PlanRepository(factory, PDP_BUILD)
    for kind in KINDS:
        response = pdp.query({'reference_year':2026, 'county_fips':'12021',
            'intended_use':'developer_source_inspection', 'kind':kind, 'page_size':100})
        if response['source_review_due'] or digest(response) != manifest['pdp_response_sha256'][kind]:
            raise ValueError('PDP_SOURCE_CHANGED_OR_EXPIRED')
    root = PACKAGE.parents[1]
    for relative, entry in manifest['catalog_files'].items():
        if file_sha(root / relative) != entry['sha256']:
            raise ValueError('CATALOG_OR_AUTHORITY_CHANGED')
    return {'source_controls_unchanged':True, 'full_CSG_column_hashes_checked':full,
            'PDP_responses_unchanged_and_current':True, 'catalog_and_authority_files_unchanged':True,
            'snapshot_id':binding['snapshot_id']}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--full',action='store_true')
    args=parser.parse_args()
    print(json.dumps(check(args.directory,full=args.full),indent=2))
