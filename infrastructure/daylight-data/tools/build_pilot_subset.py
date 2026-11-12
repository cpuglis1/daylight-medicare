#!/usr/bin/env python3
"""D144: create a NEW local database; never edit/drop/clean a source or target.

Run with this package's pinned venv and PYTHONPATH=src. Failures leave artifacts
for inspection. The binding is published only after full parity verification.
"""
import argparse
from datetime import datetime, timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from daylight_data.csg_medigap.store import Repository as CsgRepository, connect
from daylight_data.plan_types.store import Repository as PlanRepository
from daylight_data.plan_types.common import canonical, digest, file_sha
from daylight_data.pilot_subset.store import CSG_BUILD, PDP_BUILD, KINDS, implementation_binding, repositories

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[1]
SOURCE_DB = 'daylight_research_2026_r2'
TABLE_KEYS = {'schema_revision': 'singleton', 'build': 'build_id',
    'source': 'build_id,source_sha256', 'rate': 'build_id,id',
    'benefit': 'build_id,source_sha256,variant', 'completion': 'build_id',
    'selection_event': 'event_id', 'stop_event': 'event_id'}


def write_json(path, value):
    with path.open('x') as f:
        json.dump(value, f, indent=2, sort_keys=True, default=str)
        f.write('\n')


def csg_hashes(c):
    c.execute("SET timezone='UTC'")
    result = {}
    for table, keys in TABLE_KEYS.items():
        h = hashlib.sha256()
        query = f'COPY (SELECT to_jsonb(t)::text FROM dl_csg_medigap.{table} t ORDER BY {keys}) TO STDOUT'
        with c.cursor().copy(query) as stream:
            for block in stream:
                h.update(block)
        result[table] = {'rows': c.execute(f'SELECT count(*) AS n FROM dl_csg_medigap.{table}').fetchone()['n'],
                         'sha256': h.hexdigest()}
    return result


def controls(c):
    result = {}
    for schema, tables in {'dl_csg_medigap': ['build','completion','selection_event','stop_event'],
                          'dl_plan_types': ['build','completion','selection_event','review_event','stop_event']}.items():
        for table in tables:
            result[f'{schema}.{table}'] = c.execute(
                f'SELECT to_jsonb(t) AS value FROM {schema}.{table} t ORDER BY to_jsonb(t)::text').fetchall()
    return result


def catalog_files():
    sys.path.insert(0, str(ROOT / 'alternatives/advisor-first'))
    from plans_catalog import PlansCatalog, PATH
    from catalog_research import CatalogResearch, CATALOG_PATH, CRITICAL_BENEFITS_PATH
    from comparison_research import RESEARCH_SCOPE
    catalog = PlansCatalog().read()
    PlansCatalog().typed()
    legacy = CatalogResearch(critical_benefits_path=CRITICAL_BENEFITS_PATH)
    assert legacy.query(RESEARCH_SCOPE)['total'] == 72
    paths = {PATH, CATALOG_PATH, CRITICAL_BENEFITS_PATH}
    paths.update((PATH.parent / source['path']).resolve() for source in catalog['inputs'].values())
    paths.update(ROOT / 'cms-slice/data-sources' / name for name in (
        'plans-workspace-acceptance.json','plans-publication.json','plans-verification-findings.json'))
    return {str(p.relative_to(ROOT)): {'bytes': p.stat().st_size, 'sha256': file_sha(p)} for p in sorted(paths)}


def build(args):
    os.umask(0o077)
    if not re.fullmatch(r'daylight_pilot_[a-z0-9_]+', args.database):
        raise ValueError('Use a new daylight_pilot_* database name')
    output = args.output.resolve()
    if output.exists():
        raise ValueError('Output already exists; use a new revision. Nothing overwritten.')
    source_dsn = make_conninfo(host=str(PACKAGE / '.state/socket'), port='55485',
                             dbname=SOURCE_DB, user=getpass.getuser())
    target_dsn = make_conninfo(source_dsn, dbname=args.database)
    source_factory = lambda: connect(source_dsn, SOURCE_DB, readonly=True)
    csg = CsgRepository(source_factory, CSG_BUILD)
    pdp = PlanRepository(source_factory, PDP_BUILD)
    csg_status, pdp_status = csg.status(), pdp.status()
    with source_factory() as source:
        if source.execute('SELECT 1 FROM pg_database WHERE datname=%s', (args.database,)).fetchone():
            raise ValueError('Target database already exists; no overwrite or cleanup permitted')
        before_controls = controls(source)
        before_hashes = csg_hashes(source)
        source_bytes = source.execute('SELECT pg_database_size(current_database()) AS n').fetchone()['n']
        source_manifest = source.execute('SELECT manifest FROM dl_plan_types.active_research').fetchone()['manifest']
        source_oid = source.execute('SELECT oid FROM pg_database WHERE datname=current_database()').fetchone()['oid']
    responses = {}
    for kind, expected_count in KINDS.items():
        response = pdp.query({'reference_year': 2026, 'county_fips': '12021',
            'intended_use': 'developer_source_inspection', 'kind': kind, 'page_size': 100})
        if len(response['records']) != expected_count or response['next_after'] or response['source_review_due']:
            raise ValueError('PDP population/freshness gate failed')
        for row in response['records']:
            if digest(row['payload']) != row['payload_sha256']:
                raise ValueError('PDP source payload hash mismatch')
        responses[kind] = response
    files = catalog_files()
    output.mkdir(parents=True, mode=0o700)
    write_json(output / 'source-controls.json', before_controls)
    archive = output / 'medigap-source.dump'
    # Logical schema-only scope, including all rows, indexes, constraints, roles' ACLs,
    # immutable triggers, provenance and STOP/selection history. No --clean ever.
    subprocess.run([str(PACKAGE / '.postgres18/bin/pg_dump'),
        '--dbname', make_conninfo(source_dsn, options='-c default_transaction_read_only=on'),
        '--format=custom', '--schema=dl_csg_medigap', '--file', str(archive)], check=True)
    with psycopg.connect(source_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(sql.Identifier(args.database)))
        admin.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC').format(sql.Identifier(args.database)))
    subprocess.run([str(PACKAGE / '.postgres18/bin/pg_restore'), '--exit-on-error',
                    '--single-transaction', '--no-owner', '--dbname', target_dsn, str(archive)], check=True)
    with connect(target_dsn, args.database) as target:
        target.execute("SET timezone='UTC'")
        copied = csg_hashes(target)
        if copied != before_hashes:
            raise ValueError('Full-column Medigap copy parity failed')
        target.execute((PACKAGE / 'src/daylight_data/pilot_subset/schema.sql').read_text())
        manifest = {'schema': 'collier-display-subset/1', 'created_at': datetime.now(timezone.utc).isoformat(),
            'source_database': SOURCE_DB, 'source_database_oid': source_oid,
            'csg_build': CSG_BUILD, 'pdp_build': PDP_BUILD, 'consumer_release': 'held',
            'implementation': implementation_binding(), 'csg_tables': copied,
            'pdp_source_manifest': source_manifest, 'pdp_source_status': pdp_status,
            'pdp_response_sha256': {kind: digest(value) for kind, value in responses.items()},
            'pdp_record_counts': KINDS, 'source_controls_sha256': digest(before_controls),
            'catalog_files': files, 'scope': {'county_fips': '12021', 'year': 2026},
            'authority': ['D129 exact dated Medigap source prices', 'D134 dated published PDP display'],
            'excluded': ['full research schemas', 'operations', 'guest profiles', 'transcripts',
                         'personal drug costs', 'provider network verification', 'recommendations'],
            'stop_policy': 'Static source snapshot; reconcile original controls before use/transfer; append local STOP immediately on revocation.'}
        snapshot_id = digest(manifest)
        with target.transaction():
            for kind, response in responses.items():
                target.execute('INSERT INTO dl_pilot.pdp_response VALUES(%s,%s)', (kind, Jsonb(response)))
            target.execute('INSERT INTO dl_pilot.snapshot(snapshot_id,manifest) VALUES(%s,%s)',
                           (snapshot_id, Jsonb(manifest)))
    # Candidate binding is never the final app entry point until all parity passes.
    binding = {'schema': 'collier-display-binding/1', 'database': args.database, 'snapshot_id': snapshot_id}
    write_json(output / 'candidate-binding.json', binding)
    small_csg, small_pdp = repositories(output / 'candidate-binding.json', dsn=target_dsn)
    if small_csg.status() != csg_status:
        raise ValueError('Medigap status mismatch')
    sys.path.insert(0, str(ROOT / 'alternatives/advisor-first'))
    # These modules use the pinned engine's ProfileError; initialize import paths only.
    import server
    from medigap_pilot import prices
    from part_d_pilot import published_plans
    with source_factory() as source:
        profiles = source.execute('SELECT zip,age,gender,tobacco,requested_date FROM dl_csg_medigap.source ORDER BY zip,age,gender,tobacco').fetchall()
    checked = []
    for profile in profiles:
        request = {'zipcode': profile['zip'], 'age': profile['age'], 'gender': profile['gender'],
                   'tobacco': profile['tobacco'], 'effective_date': profile['requested_date'].isoformat()}
        original, copied = prices(csg, request), prices(small_csg, request)
        if original != copied:
            raise ValueError('Medigap app-output parity failed')
        checked.append({'profile': request, 'rows': len(copied['plans']), 'sha256': digest(copied)})
    for kind, value in responses.items():
        got = small_pdp.query({'reference_year': 2026, 'county_fips': '12021',
            'intended_use': 'developer_source_inspection', 'kind': kind, 'page_size': 100})
        if got != value:
            raise ValueError('PDP exact response parity failed')
    scope = {'zipcode': '34101', 'county_fips': '12021', 'year': 2026}
    zips = {'34101': [['12021', 'Collier County', 'FL']]}
    original, copied = published_plans(pdp, scope, zips), published_plans(small_pdp, scope, zips)
    if original != copied:
        raise ValueError('PDP full app-output parity failed')
    with source_factory() as source:
        if controls(source) != before_controls or csg_hashes(source) != before_hashes:
            raise ValueError('Source changed during export; new revision required')
    with connect(target_dsn, args.database) as target:
        target.execute('ANALYZE')
        target.execute('ALTER DATABASE ' + args.database + ' SET default_transaction_read_only=on')
        target_bytes = target.execute('SELECT pg_database_size(current_database()) AS n').fetchone()['n']
    subprocess.run([str(PACKAGE / '.postgres18/bin/pg_dump'), '--dbname', target_dsn,
        '--format=custom', '--file', str(output / 'pilot.dump')], check=True)
    subprocess.run([str(PACKAGE / '.postgres18/bin/pg_restore'), '--file', os.devnull,
                    str(output / 'pilot.dump')], check=True)
    for relative, entry in files.items():
        destination = output / 'catalog-files' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative).read_bytes())
        if file_sha(destination) != entry['sha256']:
            raise ValueError('Catalog changed during copy')
    receipt = {'schema': 'collier-subset-verification/1', 'database': args.database,
        'source_database_bytes': source_bytes, 'target_database_bytes': target_bytes,
        'reduction_percent': round(100 * (1 - target_bytes / source_bytes), 4),
        'csg_full_column_parity': before_hashes, 'csg_app_profiles': len(checked),
        'csg_app_rate_observations': sum(p['rows'] for p in checked),
        'pdp_response_counts': KINDS, 'pdp_app_sha256': digest(copied),
        'catalog_files': files, 'source_unchanged': True, 'snapshot_id': snapshot_id,
        'dump': {'bytes': (output / 'pilot.dump').stat().st_size, 'sha256': file_sha(output / 'pilot.dump'),
                 'full_archive_decode': 'passed', 'clean_CSG_restore': 'passed'},
        'csg_schema_source_dump_sha256': file_sha(archive),
        'checks': ['all CSG columns and rows equal', 'all 320 Medigap app outputs equal',
                   'all three PDP responses equal', 'ten-plan PDP app output equal',
                   'source data and authority controls unchanged', 'catalog bytes identical'],
        'not_claimed': ['source/method acceptance', 'consumer release', 'AWS deployment',
                        'off-machine recovery', 'future STOP synchronization', 'live conversation quality']}
    write_json(output / 'profile-parity.json', checked)
    write_json(output / 'manifest.json', manifest)
    write_json(output / 'verification.json', receipt)
    write_json(output / 'binding.json', binding)
    print(json.dumps({k: receipt[k] for k in ('database','source_database_bytes','target_database_bytes',
        'reduction_percent','csg_app_profiles','csg_app_rate_observations','dump')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--output', type=Path, required=True)
    build(parser.parse_args())
