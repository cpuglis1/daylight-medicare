"""Append-only CSG PostgreSQL import and exact-profile research access (D128)."""
from collections import Counter
from contextlib import contextmanager
from datetime import date
import hashlib
from importlib.metadata import version
from itertools import product
import json
from pathlib import Path
import platform
import re

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from . import CsgError, SCOPE, VARIANTS

SCHEMA = Path(__file__).with_name('schema.sql')
MONEY = ('monthly_cents', 'annual_cents', 'monthly_with_discounts_cents', 'annual_with_discounts_cents')
RATE_COLUMNS = ('id', 'source_sha256', 'variant', 'naic', *MONEY, 'source_effective_date',
                'rating_class', 'rating_type', 'select_observed', 'payload_sha256', 'payload')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_sha(path):
    with Path(path).open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def code_binding():
    return {p.name: file_sha(p) for p in sorted(Path(__file__).parent.iterdir())
            if p.suffix in ('.py', '.sql')}


def runtime_binding():
    return {'python': platform.python_version(), 'psycopg': version('psycopg')}


def profile_key(s):
    return (s['zip'], s['age'], s['gender'], s['tobacco'], s['requested_effective_date'])


def rating_label_issue(r):
    return (r['raw'].get('AM Best Rating') in {'Stable', 'Negative', 'Positive'}
            or r['raw'].get('AM Best Outlook') in {'A++', 'A+', 'A', 'A-', 'B++', 'B+'})


def read_candidate(candidate):
    """Verify immutable transport and all profile/row identities before a DB write."""
    candidate = Path(candidate).resolve()
    original = json.loads((candidate / 'manifest.json').read_text())
    if original.get('schema') != 'csg-medigap-private-candidate/1' or original.get('consumer_release') != 'held':
        raise CsgError('UNSUPPORTED_CANDIDATE')
    expected_files = {'rates.jsonl', 'benefit-observations.json', 'research.sqlite3'}
    if set(original.get('files', {})) != expected_files:
        raise CsgError('INCOMPLETE_CANDIDATE')
    for name, sha in original['files'].items():
        if file_sha(candidate / name) != sha:
            raise CsgError('CANDIDATE_HASH_MISMATCH')
    sources = original['sources']
    if original['source_count'] != 320 or len(sources) != 320:
        raise CsgError('EXACT_320_PROFILE_SCOPE_REQUIRED')
    expected_profiles = set(product(SCOPE['zips'], SCOPE['ages'], SCOPE['genders'], SCOPE['tobacco'],
                                    [SCOPE['requested_effective_date']]))
    if {profile_key(s['scenario']) for s in sources} != expected_profiles:
        raise CsgError('PROFILE_COVERAGE_MISMATCH')
    by_hash = {}
    for s in sources:
        name = s['filename']
        if Path(name).name != name or s['scenario'].get('fictional') is not True:
            raise CsgError('INVALID_SOURCE_SCOPE')
        if set(s['rate_counts']) != set(VARIANTS) or s['sha256'] in by_hash:
            raise CsgError('INVALID_SOURCE_VARIANTS_OR_DUPLICATE')
        if file_sha(candidate.parent / 'raw' / name) != s['sha256']:
            raise CsgError('SOURCE_HASH_MISMATCH')
        by_hash[s['sha256']] = s
    rates = [json.loads(line) for line in (candidate / 'rates.jsonl').read_text().splitlines()]
    counts, ids = Counter(), set()
    for r in rates:
        source = by_hash.get(r['source_sha256'])
        if (source is None or r['scenario'] != source['scenario'] or r['variant'] not in VARIANTS
                or r['id'] in ids or r['personal_quote'] is not False or r['consumer_release'] != 'held'
                or r['holds'] != original['holds'] or r['county_fips'] != '12021'
                or 'COLLIER' not in r['raw']['County'].split(';')):
            raise CsgError('RATE_SCOPE_OR_AUTHORITY_MISMATCH')
        if r['id'] != hashlib.sha256(f"{r['source_sha256']}:{r['source_locator']}".encode()).hexdigest():
            raise CsgError('RATE_LOCATOR_MISMATCH')
        for key in MONEY:
            if r[key] is not None and (type(r[key]) is not int or r[key] < 0):
                raise CsgError('INVALID_INTEGER_MONEY')
        if not re.fullmatch(r'\d{5}', r['naic']):
            raise CsgError('INVALID_NAIC')
        ids.add(r['id']); counts[(r['source_sha256'], r['variant'])] += 1
    if len(rates) != original['rate_rows']:
        raise CsgError('RATE_COUNT_MISMATCH')
    for s in sources:
        if any(counts[(s['sha256'], v)] != n for v, n in s['rate_counts'].items()):
            raise CsgError('SOURCE_VARIANT_COUNT_MISMATCH')
    benefits = json.loads((candidate / 'benefit-observations.json').read_text())
    if (len(benefits) != 3840 or len(benefits) != original['benefit_sheets']
            or {(b['source_sha256'], b['variant']) for b in benefits} != set(product(by_hash, VARIANTS))
            or any(b['consumer_release'] != 'held' or b['sheet'] != f"Plan {b['variant']} Details" for b in benefits)):
        raise CsgError('BENEFIT_COVERAGE_MISMATCH')
    manifest = {'schema': 'csg-postgres-build/1', 'scope': SCOPE,
                'candidate_manifest_sha256': file_sha(candidate / 'manifest.json'),
                'candidate_files': original['files'], 'importer_sha256': original['code_sha256'],
                'sources': sources, 'holds': original['holds'], 'code': code_binding(),
                'runtime': runtime_binding(), 'source_policy': 'private_owner_authorized_CSG_exports_D123_D128',
                'review_findings': {
                    'rating_outlook_label_anomaly_rows': sum(rating_label_issue(r) for r in rates),
                    'rating_fields_use': 'Raw source labels only; anomalous rating/outlook fields require review before quality comparisons',
                    'annual_amount_unknown_rows': sum(r['annual_cents'] is None for r in rates),
                    'annual_differs_from_12_monthly_rows': sum(r['annual_cents'] is not None and r['monthly_cents'] is not None
                                                             and r['annual_cents'] != r['monthly_cents'] * 12 for r in rates),
                    'class_discount_fee_select_eligibility': 'not_determined',
                },
                'counts': {'sources': len(sources), 'rates': len(rates), 'benefits': len(benefits)},
                'consumer_release': 'held', 'all_market_complete': False}
    manifest['build_id'] = digest(manifest)
    return manifest, rates, benefits


def connect(dsn, expected_database, *, readonly=False):
    connection = psycopg.connect(dsn, autocommit=True, row_factory=dict_row, connect_timeout=5,
        options='-c statement_timeout=30000 -c lock_timeout=1000 -c idle_in_transaction_session_timeout=60000'
                + (' -c default_transaction_read_only=on' if readonly else ''))
    if connection.info.dbname != expected_database:
        connection.close()
        raise CsgError('DATABASE_IDENTITY_MISMATCH')
    return connection


def install(connection):
    with connection.transaction():
        connection.execute('SELECT pg_advisory_xact_lock(128202601)')
        exists = connection.execute("SELECT to_regnamespace('dl_csg_medigap') AS n").fetchone()['n']
        if exists:
            row = connection.execute('SELECT sha256 FROM dl_csg_medigap.schema_revision WHERE singleton').fetchone()
            if not row or row['sha256'] != file_sha(SCHEMA):
                raise CsgError('SCHEMA_REVISION_MISMATCH')
        else:
            connection.execute(SCHEMA.read_text())
            connection.execute('INSERT INTO dl_csg_medigap.schema_revision(sha256) VALUES(%s)', (file_sha(SCHEMA),))


def rate_values(r):
    return (r['id'], r['source_sha256'], r['variant'], r['naic'], *(r[k] for k in MONEY),
            date.fromisoformat(r['source_effective_date']), r['rating_class_raw'], r['rating_type_raw'],
            r['select_observed'], digest(r), Jsonb(r, dumps=canonical))


def verify_loaded(connection, manifest, rates, benefits):
    """Compare every DB payload and typed value, not just row counts."""
    build = manifest['build_id']
    row = connection.execute('SELECT manifest FROM dl_csg_medigap.build WHERE build_id=%s', (build,)).fetchone()
    if not row or row['manifest'] != manifest:
        raise CsgError('STORED_BUILD_MISMATCH')
    sources = connection.execute('SELECT * FROM dl_csg_medigap.source WHERE build_id=%s', (build,)).fetchall()
    expected_sources = {s['sha256']: s for s in manifest['sources']}
    if len(sources) != len(expected_sources):
        raise CsgError('STORED_SOURCE_COUNT_MISMATCH')
    for s in sources:
        wanted = expected_sources[s['source_sha256']]
        if s['metadata'] != wanted or s['filename'] != wanted['filename'] or (
                s['zip'], s['age'], s['gender'], s['tobacco'], s['requested_date'].isoformat()) != profile_key(wanted['scenario']):
            raise CsgError('STORED_SOURCE_MISMATCH')
    actual = connection.execute('SELECT * FROM dl_csg_medigap.rate WHERE build_id=%s ORDER BY id', (build,)).fetchall()
    if len(actual) != len(rates):
        raise CsgError('STORED_RATE_COUNT_MISMATCH')
    for got, wanted in zip(actual, sorted(rates, key=lambda r: r['id'])):
        expected = rate_values(wanted)
        if got['payload'] != wanted or any(got[k] != v for k, v in zip(RATE_COLUMNS[:-1], expected[:-1])):
            raise CsgError('STORED_RATE_MISMATCH')
    actual_b = connection.execute('SELECT * FROM dl_csg_medigap.benefit WHERE build_id=%s ORDER BY source_sha256,variant', (build,)).fetchall()
    if len(actual_b) != len(benefits):
        raise CsgError('STORED_BENEFIT_COUNT_MISMATCH')
    for got, wanted in zip(actual_b, sorted(benefits, key=lambda b: (b['source_sha256'], b['variant']))):
        if got['payload'] != wanted or got['payload_sha256'] != digest(wanted):
            raise CsgError('STORED_BENEFIT_MISMATCH')
    return dict(manifest['counts'])


def stopped(connection, build):
    return connection.execute('''SELECT 1 FROM dl_csg_medigap.stop_event e WHERE e.build_id=%s
        OR e.source_sha256 IN (SELECT source_sha256 FROM dl_csg_medigap.source WHERE build_id=%s) LIMIT 1''',
        (build, build)).fetchone() is not None


def load(connection, candidate):
    manifest, rates, benefits = read_candidate(candidate)
    build = manifest['build_id']
    with connection.transaction():
        connection.execute('SELECT pg_advisory_xact_lock(128202602)')
        connection.execute('SET LOCAL ROLE daylight_csg_loader')
        existing = connection.execute('SELECT 1 FROM dl_csg_medigap.completion WHERE build_id=%s', (build,)).fetchone()
        if existing:
            verify_loaded(connection, manifest, rates, benefits)
            return {'build_id': build, 'counts': manifest['counts'], 'reused': True, 'consumer_release': 'held'}
        connection.execute('INSERT INTO dl_csg_medigap.build(build_id,manifest) VALUES(%s,%s)', (build, Jsonb(manifest)))
        with connection.cursor().copy('COPY dl_csg_medigap.source FROM STDIN') as copy:
            for s in manifest['sources']:
                copy.write_row((build, s['sha256'], s['filename'], *profile_key(s['scenario'])[:-1],
                                date.fromisoformat(s['scenario']['requested_effective_date']), Jsonb(s, dumps=canonical)))
        with connection.cursor().copy('COPY dl_csg_medigap.rate(build_id,' + ','.join(RATE_COLUMNS) + ') FROM STDIN') as copy:
            for r in rates:
                copy.write_row((build, *rate_values(r)))
        with connection.cursor().copy('COPY dl_csg_medigap.benefit FROM STDIN') as copy:
            for b in benefits:
                copy.write_row((build, b['source_sha256'], b['variant'], digest(b), Jsonb(b, dumps=canonical)))
        verify_loaded(connection, manifest, rates, benefits)
        connection.execute('INSERT INTO dl_csg_medigap.completion(build_id,counts) VALUES(%s,%s)', (build, Jsonb(manifest['counts'])))
    return {'build_id': build, 'counts': manifest['counts'], 'reused': False, 'consumer_release': 'held'}


def select_research(connection, build, reason):
    if not isinstance(reason, str) or not reason.strip():
        raise CsgError('REASON_REQUIRED')
    with connection.transaction():
        connection.execute('SELECT pg_advisory_xact_lock(128202602)')
        connection.execute('SET LOCAL ROLE daylight_csg_loader')
        if stopped(connection, build):
            raise CsgError('SOURCE_STOP')
        connection.execute('INSERT INTO dl_csg_medigap.selection_event(build_id,reason) VALUES(%s,%s)', (build, reason))


class Repository:
    """Private read-only backend access, with no consumer-release switch."""
    def __init__(self, factory, expected_build):
        if not callable(factory) or not re.fullmatch(r'[a-f0-9]{64}', expected_build or ''):
            raise CsgError('INVALID_REPOSITORY_CONFIGURATION')
        self.factory, self.expected = factory, expected_build

    @contextmanager
    def read(self):
        with self.factory() as c, c.transaction():
            c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            c.execute('SET LOCAL ROLE daylight_csg_reader')
            c.execute("SET LOCAL statement_timeout='5000ms'")
            row = c.execute('SELECT build_id,manifest FROM dl_csg_medigap.active_research').fetchone()
            if not row or row['build_id'] != self.expected:
                raise CsgError('STALE_OR_UNSELECTED_BUILD')
            m = row['manifest']
            if digest({k: v for k, v in m.items() if k != 'build_id'}) != self.expected or m['scope'] != SCOPE:
                raise CsgError('BUILD_BINDING_MISMATCH')
            if m['code'] != code_binding() or m['runtime'] != runtime_binding():
                raise CsgError('RUNTIME_BINDING_MISMATCH')
            if stopped(c, self.expected):
                raise CsgError('SOURCE_STOP')
            yield c, m

    def status(self):
        with self.read() as (_, m):
            return {'build_id': self.expected, 'scope': m['scope'], 'counts': m['counts'],
                    'consumer_release': 'held', 'all_market_complete': False, 'holds': m['holds']}

    def query(self, *, zipcode, age, gender, tobacco, effective_date, variant=None):
        if (not isinstance(zipcode, str) or not re.fullmatch(r'\d{5}', zipcode)
                or type(age) is not int or not 0 <= age <= 120 or gender not in SCOPE['genders']
                or tobacco not in SCOPE['tobacco'] or not isinstance(effective_date, str)
                or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', effective_date)
                or (variant is not None and variant not in VARIANTS)):
            raise CsgError('EXPLICIT_QUOTE_INPUTS_REQUIRED')
        date.fromisoformat(effective_date)
        with self.read() as (c, m):
            result = {'build_id': self.expected, 'consumer_release': 'held', 'personal_quote': False,
                'eligibility': 'not_determined', 'all_market_complete': False, 'holds': m['holds'],
                'profile': {'zip': zipcode, 'age': age, 'gender': gender, 'tobacco': tobacco,
                            'requested_effective_date': effective_date}, 'records': []}
            if age not in SCOPE['ages']:
                result.update(status='unsupported_pilot_age', reason=(
                    'Medigap pricing for ages 75+ is not supported in this pilot.' if age >= 75 else
                    'Medigap pricing in this pilot supports ages 65–74; under-65 pricing is not supported.'))
                return result
            s = c.execute('''SELECT source_sha256,metadata FROM dl_csg_medigap.source
                WHERE build_id=%s AND zip=%s AND age=%s AND gender=%s AND tobacco=%s AND requested_date=%s''',
                (self.expected, zipcode, age, gender, tobacco, effective_date)).fetchone()
            if not s:
                result.update(status='needs_source_export', reason='This exact profile/date is not in the selected build; plan availability is not determined.')
                return result
            sql = 'SELECT payload,payload_sha256 FROM dl_csg_medigap.rate WHERE build_id=%s AND source_sha256=%s'
            args = [self.expected, s['source_sha256']]
            if variant:
                sql += ' AND variant=%s'; args.append(variant)
            rows = c.execute(sql + ' ORDER BY variant,naic,id LIMIT 1001', args).fetchall()
            if len(rows) > 1000:
                raise CsgError('SOURCE_PROFILE_BOUND_EXCEEDED')
            for r in rows:
                if digest(r['payload']) != r['payload_sha256'] or profile_key(r['payload']['scenario']) != profile_key(result['profile']):
                    raise CsgError('STORED_PAYLOAD_MISMATCH')
            result.update(status='matched_source_observations' if rows else 'no_rows_in_source_export',
                          source_sha256=s['source_sha256'], records=[r['payload'] for r in rows], returned_rows=len(rows),
                          field_issues=[{'record_id': r['payload']['id'],
                              'fields': ['AM Best Rating', 'AM Best Outlook'],
                              'state': 'source_labels_require_review'} for r in rows if rating_label_issue(r['payload'])])
            return result
