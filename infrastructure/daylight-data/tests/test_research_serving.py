"""Research query boundaries and projections; fictional rows, no DB mutation."""
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
import copy
import json

import pytest

from daylight_data.serving import ResearchBinding, ResearchPlanRepository, ResearchServingError
from daylight_data.serving.binding import SCOPE, load_local_binding
from daylight_data.serving.repository import STATE_KEYS, json_safe, validate_local_dsn, validate_local_connection
from daylight_data.serving.native_lineage import NativeLineageRepository


def binding():
    return ResearchBinding('a' * 64, 'fixture_test', 'b' * 64,
        {'database': 'fixture_test', 'database_oid': 123, 'marker': 'fixture:marker',
         'cluster_system_identifier': '456'},
        {key: {'derivation_id': key, 'layer_id': 'L02', 'source_path': 'fixture:path',
               'source_sha256': 'c' * 64, 'adapter_code_sha256': 'd' * 64}
         for key in ['collier', 'national', 'semantic', 'quality', 'quality_binding']},
        (), {}, 'e' * 64)


def catalog():
    rows = []
    for ordinal in range(1, 73):
        identifier = f'2026:H9999:{ordinal:03d}:000'
        rows.append({'native_id': identifier, 'raw_native_id': identifier, 'national_id': identifier,
            'source_ordinal': ordinal, 'source_row_ordinal': ordinal,
            'contract_id': 'H9999', 'plan_id': f'{ordinal:03d}', 'segment_id': '000',
            'category': 'MA', 'national_name': 'Fictional source name', 'r9_identity_present': True,
            'national_derivation_id': 'national', 'national_source_table': 'offerings',
            'national_source_ordinal': ordinal, 'fields': {'id': identifier, 'name': 'Fictional source name',
                'snp': 'source restricted', 'verified_availability': False},
            'conditions': 'Fictional raw restriction remains verbatim.',
            **{key: 'source_observed' for key in STATE_KEYS},
            'derivation_id': 'collier', 'snapshot_id': 'fixture:snapshot',
            'artifact_sha256': 'c' * 64, 'source_table': 'collier_offerings',
            'original_path': 'fixture:source', 'raw_sha256': 'f' * 64,
            'record_id': 'fixture:row:' + str(ordinal), 'source_row_key': identifier,
            'ordinal_basis': 'source array', 'adapter_code_sha256': 'd' * 64})
    return rows


class Cursor:
    def __init__(self, rows): self.rows = rows
    def fetchall(self): return copy.deepcopy(self.rows)
    def fetchone(self): return copy.deepcopy(self.rows[0])


class FakeConnection:
    def __init__(self, rows=None): self.rows = rows or []; self.calls = []
    def execute(self, query, params=None): self.calls.append((query, params)); return Cursor(self.rows)


class FixtureRepository(ResearchPlanRepository):
    def __init__(self, rows=None):
        super().__init__(lambda: None, binding())
        self.rows = catalog() if rows is None else rows
        self.connection = FakeConnection()
    @contextmanager
    def _read(self): yield self.connection, []
    def _catalog(self, connection):
        fake = FakeConnection(self.rows)
        return super()._catalog(fake)


def test_exact_scope_wrong_year_geography_category_or_extra_personal_keys_never_query():
    repository = FixtureRepository()
    for scope in [{}, {**SCOPE, 'year': 2027}, {**SCOPE, 'county_fips': '12071'},
                  {**SCOPE, 'year': 2026.0}, {**SCOPE, 'category': 'pdp'}, {**SCOPE, 'income': 100}]:
        with pytest.raises(ResearchServingError, match='UNSUPPORTED_RESEARCH_SCOPE'):
            repository.list_plans(scope)
    assert not repository.connection.calls


def test_pagination_preserves_72_exact_source_order_and_holds():
    repository = FixtureRepository()
    ids, ordinals, after = [], [], None
    while True:
        result = repository.list_plans(dict(SCOPE), after, limit=20)
        assert result['status'] == 'research_only'
        assert all(purpose['state'] == 'held' for purpose in result['authority'].values())
        assert result['binding']['accepted_release_id'] is None
        ids += [p['offering_id'] for p in result['plans']]
        ordinals += [p['source_ordinal'] for p in result['plans']]
        if not result['page']['has_more']: break
        after = result['page']['next_after_ordinal']
    assert len(set(ids)) == len(ids) == 72 and ordinals == list(range(1, 73))
    assert result['plans'][-1]['restrictions'] == 'Fictional raw restriction remains verbatim.'
    assert result['plans'][-1]['verified_availability'] is False


@pytest.mark.parametrize('change', ['duplicate', 'null', 'native_drift', 'national_missing', 'r9_missing'])
def test_bridge_failures_are_not_silent_filtering(change):
    rows = catalog()
    if change == 'duplicate': rows[1]['native_id'] = rows[0]['native_id']
    elif change == 'null': rows[1]['native_id'] = None
    elif change == 'native_drift': rows[1]['raw_native_id'] = 'different'
    elif change == 'national_missing': rows[1]['national_id'] = None
    else: rows[1]['r9_identity_present'] = False
    with pytest.raises(ResearchServingError, match='EXACT_72_IDENTITY_BRIDGE_MISMATCH'):
        FixtureRepository(rows).list_plans(dict(SCOPE))


def test_empty_or_wrong_cursor_and_stale_binding_fail_closed():
    repository = FixtureRepository()
    for after in [-1, True, '2', 73]:
        with pytest.raises(ResearchServingError, match='INVALID_SOURCE_ORDINAL_CURSOR'):
            repository.list_plans(dict(SCOPE), after)
    with pytest.raises(ResearchServingError, match='STALE_RESEARCH_SNAPSHOT'):
        repository.list_plans(dict(SCOPE), expected_snapshot_id='old')
    with pytest.raises(ResearchServingError, match='OFFERING_OUTSIDE_SELECTED_SCOPE'):
        repository.inspect_plan('2026:H1111:001:000')
    with pytest.raises(ResearchServingError, match='UNSUPPORTED_RESEARCH_LAYER'):
        repository.inspect_plan('2026:H9999:001:000', layers=['L10'])


def test_binding_and_source_ordinals_are_repeatable_not_time_dependent():
    repository = FixtureRepository()
    assert repository.list_plans(dict(SCOPE)) == repository.list_plans(dict(SCOPE))
    a = repository.list_plans(dict(SCOPE))
    repository.binding.control_hashes['fixture:new-control'] = 'new'
    b = repository.list_plans(dict(SCOPE))
    assert a['binding']['snapshot_id'] != b['binding']['snapshot_id']


def test_observation_preserves_decimal_native_context_states_and_qualified_conditions():
    row = {**catalog()[0], 'entity_id': 'fixture:claim', 'entity_type': 'fixture:condition',
        'offering_id': '2026:H9999:001:000', 'county_fips': '12021', 'benefit_year': 2026,
        'amount': Decimal('0.10000000000000000001'), 'amount_unit': 'USD', 'amount_basis': 'source',
        'amount_period': 'source period', 'raw_value': 'source literal',
        'conditions': {'context': {'operator': 'except', 'text': 'Fictional full caveat.'}},
        'raw_payload': {'context': 'source JSON string remains exact'}, 'source_use_state': 'source_STOP'}
    projected = json_safe(ResearchPlanRepository._observation(row, 'L03'))
    assert projected['amount'] == '0.10000000000000000001'
    assert projected['conditions'] == row['conditions']
    assert projected['raw_source_payload'] == row['raw_payload']
    assert projected['states']['source_use_state'] == 'source_STOP'
    assert projected['output_authority'] == 'held'


def test_local_dsn_guard_rejects_aliases_ports_other_databases_and_hostaddr():
    b = binding(); root = Path('/fixture')
    base = 'host=/fixture/infrastructure/daylight-data/.state/socket port=55485 dbname=fixture_test user=fixture'
    validate_local_dsn(base, root, b)
    for bad in [base.replace('55485', '5432'), base.replace('fixture_test', 'other'),
                base + ' hostaddr=127.0.0.1', base.replace('/fixture/infrastructure/daylight-data/.state/socket', 'localhost')]:
        with pytest.raises(ResearchServingError, match='EXACT_LOCAL_RESEARCH_TARGET_REQUIRED'):
            validate_local_dsn(bad, root, b)


def test_actual_target_guard_uses_shared_database_comment_before_reading_sources():
    b = binding()
    class Connection(FakeConnection):
        @contextmanager
        def transaction(self): yield
    c = Connection([{**b.target, 'port': '55485', 'unix_socket': True}])
    validate_local_connection(c, b.target)
    assert c.calls[0][0] == 'SET TRANSACTION READ ONLY'
    assert "shobj_description" in c.calls[1][0]
    c.rows[0]['database_oid'] += 1
    with pytest.raises(ResearchServingError, match='ACTUAL_LOCAL_RESEARCH_TARGET_MISMATCH'):
        validate_local_connection(c, b.target)


def test_native_lookup_is_operator_only_exact_id_type_and_100_bound():
    repo = NativeLineageRepository(lambda: None, binding())
    for ids in [[], ['OBS-x'] * 2, ['OBS-x'] * 101, ['SRC-x'], ['OBS-x; SELECT 1']]:
        with pytest.raises(ResearchServingError): repo.lookup('native_observations', ids)
    with pytest.raises(ResearchServingError): repo.lookup('arbitrary_table', ['OBS-x'])


def test_declared_source_amount_and_clause_namespaces_have_fixed_table_queries():
    class NativeFixture(NativeLineageRepository):
        @contextmanager
        def _read(self): yield FakeConnection(), []
    b = binding()
    b.selections.update(native_sources={'derivation_id': 'fixture:source', 'source_table': 'source_disposition'},
                        native_clauses={'derivation_id': 'fixture:clause', 'source_table': 'clause'})
    repo = NativeFixture(lambda: None, b)
    for kind, identifier, table in [('native_sources', 'SOURCE_AMOUNT-fixture', 'source_disposition'),
                                     ('native_clauses', 'CLAUSE-fixture', 'clause')]:
        result = repo.lookup(kind, [identifier])
        assert result['records'] == [] and result['missing_ids'] == [identifier]
        assert result['query_parameters'][1] == table
        assert result['operator_only'] is True


def test_incomplete_or_unreviewed_build_controls_are_rejected(tmp_path):
    directory = tmp_path / 'packet'; directory.mkdir()
    for name in ['BUILD_MANIFEST', 'TARGET', 'LOAD_COMPLETE']:
        (directory / (name + '.json')).write_text(json.dumps({}))
    with pytest.raises(ResearchServingError, match='COMPLETED_BUILD_BINDING_MISMATCH'):
        load_local_binding(tmp_path, 'packet')
