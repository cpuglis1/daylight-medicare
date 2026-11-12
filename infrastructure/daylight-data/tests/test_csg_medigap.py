"""Fictional CSG checks in a uniquely created local test database."""
import hashlib
from itertools import product
import json
import os
from pathlib import Path
import uuid
from unittest.mock import patch

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest

from daylight_data.csg_medigap import CsgError, SCOPE, VARIANTS
from daylight_data.csg_medigap.store import (
    connect, file_sha, install, load, read_candidate, Repository, select_research, verify_loaded,
)


@pytest.fixture
def candidate(tmp_path):
    raw = tmp_path / 'raw'; raw.mkdir()
    out = tmp_path / 'candidate'; out.mkdir()
    sources, rates, benefits = [], [], []
    for zipcode, age, gender, tobacco in product(SCOPE['zips'], SCOPE['ages'], SCOPE['genders'], SCOPE['tobacco']):
        name = f'{zipcode}-{age}-{gender}-{tobacco}.xlsx'
        p = raw / name; p.write_text(f'Fictional retained source {tmp_path.name} {name}')
        sha = file_sha(p)
        scenario = {'zip': zipcode, 'age': age, 'gender': gender, 'tobacco': tobacco,
                    'requested_effective_date': SCOPE['requested_effective_date'], 'fictional': True}
        sources.append({'filename': name, 'sha256': sha, 'scenario': scenario,
                        'rate_counts': {v: 2 if v == 'G' else 0 for v in VARIANTS}})
        for i in range(2):
            pointer = f'Plan G Rates!A{11+i}:Q{11+i}'
            rates.append({'id': hashlib.sha256(f'{sha}:{pointer}'.encode()).hexdigest(),
                'source_sha256': sha, 'source_locator': pointer, 'scenario': scenario, 'variant': 'G',
                'naic': '00001', 'monthly_cents': age * 100 + i, 'annual_cents': None if i else 70001,
                'monthly_with_discounts_cents': None, 'annual_with_discounts_cents': None,
                'source_effective_date': '2026-01-01', 'rating_class_raw': f'Fictional class {i}',
                'rating_type_raw': 'Issue Age', 'select_observed': True if i else None,
                'personal_quote': False, 'consumer_release': 'held', 'holds': ['FICTIONAL_HOLD'],
                'county_fips': '12021', 'raw': {'County': 'COLLIER',
                    'AM Best Rating': 'Stable' if i else 'A', 'AM Best Outlook': 'A-' if i else 'Stable'}})
        for v in VARIANTS:
            benefits.append({'source_sha256': sha, 'variant': v, 'sheet': f'Plan {v} Details',
                             'cells': {'A1': {'value': 'Fictional benefit'}}, 'consumer_release': 'held'})
    (out / 'rates.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rates))
    (out / 'benefit-observations.json').write_text(json.dumps(benefits))
    (out / 'research.sqlite3').write_text('Fictional transport; PostgreSQL reads verified JSON streams')
    manifest = {'schema': 'csg-medigap-private-candidate/1', 'consumer_release': 'held',
                'sources': sources, 'source_count': 320, 'rate_rows': 640, 'benefit_sheets': 3840,
                'holds': ['FICTIONAL_HOLD'], 'code_sha256': '0' * 64,
                'files': {p.name: file_sha(p) for p in out.iterdir()}}
    (out / 'manifest.json').write_text(json.dumps(manifest))
    return out


def test_complete_scope_and_all_source_fields_are_accounted(candidate):
    m, rates, benefits = read_candidate(candidate)
    assert m['counts'] == {'sources': 320, 'rates': 640, 'benefits': 3840}
    assert m['review_findings']['rating_outlook_label_anomaly_rows'] == 320
    assert m['review_findings']['annual_amount_unknown_rows'] == 320
    assert {r['rating_class_raw'] for r in rates} == {'Fictional class 0', 'Fictional class 1'}
    assert all(b['consumer_release'] == 'held' for b in benefits)


def test_modified_source_or_stream_fails_before_loading(candidate):
    source = next((candidate.parent / 'raw').iterdir()); source.write_text('changed')
    with pytest.raises(CsgError, match='SOURCE_HASH'): read_candidate(candidate)
    (candidate / 'rates.jsonl').write_text('{}\n')
    with pytest.raises(CsgError, match='CANDIDATE_HASH'): read_candidate(candidate)


def test_missing_profile_and_changed_row_authority_fail(candidate):
    p = candidate / 'manifest.json'; m = json.loads(p.read_text())
    m['sources'][0]['scenario']['age'] = 75; p.write_text(json.dumps(m))
    with pytest.raises(CsgError, match='PROFILE_COVERAGE'): read_candidate(candidate)
    m['sources'][0]['scenario']['age'] = 65
    rates = [json.loads(l) for l in (candidate / 'rates.jsonl').read_text().splitlines()]
    rates[0]['personal_quote'] = True
    (candidate / 'rates.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rates))
    m['files']['rates.jsonl'] = file_sha(candidate / 'rates.jsonl'); p.write_text(json.dumps(m))
    with pytest.raises(CsgError, match='AUTHORITY'): read_candidate(candidate)


@pytest.fixture(scope='module')
def database():
    dsn = os.environ.get('DAYLIGHT_DATA_TEST_DSN')
    if not dsn: pytest.skip('Explicit local _test DSN required')
    info = conninfo_to_dict(dsn)
    if not info.get('dbname', '').endswith('_test') or not info.get('host', '').startswith('/'):
        raise RuntimeError('Only an explicit local test target may create the disposable fixture DB')
    name = 'daylight_csg_' + uuid.uuid4().hex + '_test'
    with connect(dsn, info['dbname']) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        target = make_conninfo(dsn, dbname=name)
        try:
            with connect(target, name) as c: install(c)
            yield target, name
        finally:
            admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))


@pytest.fixture
def loaded(database, candidate):
    dsn, name = database
    with connect(dsn, name) as c:
        result = load(c, candidate)
        select_research(c, result['build_id'], 'Fictional test selection')
    repo = Repository(lambda: connect(dsn, name, readonly=True), result['build_id'])
    return repo, result


BASE = dict(zipcode='34101', age=65, gender='Female', tobacco='Non-Tobacco', effective_date='2026-11-10')


def test_postgres_full_parity_idempotency_and_exact_profiles(database, candidate, loaded):
    repo, first = loaded
    dsn, name = database
    with connect(dsn, name) as c:
        assert load(c, candidate)['reused'] is True
        m, rates, benefits = read_candidate(candidate)
        assert verify_loaded(c, m, rates, benefits) == first['counts']
    result = repo.query(**BASE)
    assert result['returned_rows'] == 2
    assert sorted(r['monthly_cents'] for r in result['records']) == [6500, 6501]
    assert {r['annual_cents'] for r in result['records']} == {70001, None}
    assert any(r['select_observed'] is True for r in result['records'])
    assert len(result['field_issues']) == 1
    assert result['consumer_release'] == 'held' and result['personal_quote'] is False
    assert not result['all_market_complete']
    for age in (65, 74):
        assert repo.query(zipcode='34108', age=age, gender='Male', tobacco='Tobacco User',
                          effective_date='2026-11-10')['returned_rows'] == 2


def test_no_fallback_or_scope_expansion(loaded):
    repo = loaded[0]
    for change in ({'zipcode': '34109'}, {'effective_date': '2026-11-11'}, {'effective_date': '2027-01-01'}):
        r = repo.query(**{**BASE, **change})
        assert r['status'] == 'needs_source_export' and r['records'] == []
    for age in (64, 75, 100):
        r = repo.query(**{**BASE, 'age': age})
        assert r['status'] == 'unsupported_pilot_age' and r['eligibility'] == 'not_determined'
    assert repo.query(**BASE, variant='A')['status'] == 'no_rows_in_source_export'
    for change in ({'age': True}, {'gender': 'unknown'}, {'tobacco': None}):
        with pytest.raises(CsgError): repo.query(**{**BASE, **change})
    with pytest.raises(TypeError): repo.query(**BASE, consumer_release=True)


def test_reader_permissions_sealing_and_atomic_failure(database, candidate, loaded):
    dsn, name = database; build = loaded[1]['build_id']
    with connect(dsn, name) as c:
        with c.transaction():
            c.execute('SET LOCAL ROLE daylight_csg_reader')
            with pytest.raises(psycopg.errors.InsufficientPrivilege), c.transaction():
                c.execute('DELETE FROM dl_csg_medigap.rate WHERE build_id=%s', (build,))
        with pytest.raises(psycopg.errors.RaiseException, match='immutable'), c.transaction():
            c.execute('UPDATE dl_csg_medigap.rate SET monthly_cents=1 WHERE build_id=%s', (build,))
        with pytest.raises(psycopg.errors.RaiseException, match='complete'), c.transaction():
            c.execute('INSERT INTO dl_csg_medigap.rate SELECT * FROM dl_csg_medigap.rate WHERE build_id=%s LIMIT 1', (build,))
        before = c.execute('SELECT count(*) AS n FROM dl_csg_medigap.build').fetchone()['n']
        p = candidate / 'manifest.json'; m = json.loads(p.read_text()); m['code_sha256'] = '1' * 64; p.write_text(json.dumps(m))
        with patch('daylight_data.csg_medigap.store.verify_loaded', side_effect=CsgError('Injected verification failure')):
            with pytest.raises(CsgError, match='Injected'): load(c, candidate)
        assert c.execute('SELECT count(*) AS n FROM dl_csg_medigap.build').fetchone()['n'] == before


def test_source_stop_propagates_and_stale_build_fails(database, candidate, loaded):
    dsn, name = database; repo, first = loaded
    source = read_candidate(candidate)[0]['sources'][0]['sha256']
    p = candidate / 'manifest.json'; m = json.loads(p.read_text()); m['code_sha256'] = '2' * 64; p.write_text(json.dumps(m))
    with connect(dsn, name) as c:
        second = load(c, candidate)
        select_research(c, second['build_id'], 'Fictional second revision')
        with pytest.raises(CsgError, match='STALE'): repo.status()
        c.execute('INSERT INTO dl_csg_medigap.stop_event(build_id,source_sha256,reason) VALUES(%s,%s,%s)',
                  (first['build_id'], source, 'Fictional source stop'))
        current = Repository(lambda: connect(dsn, name, readonly=True), second['build_id'])
        with pytest.raises(CsgError, match='SOURCE_STOP'): current.status()
        with pytest.raises(CsgError, match='SOURCE_STOP'): select_research(c, second['build_id'], 'Must fail')

