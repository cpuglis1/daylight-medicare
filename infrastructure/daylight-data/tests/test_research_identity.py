"""Bounded exact identity research; synthetic rows, no database mutations."""
from contextlib import contextmanager
import copy
import json

import pytest

from daylight_data.serving.binding import ResearchBinding, ResearchServingError, digest
from daylight_data.serving.identity import (ACCESS, CONTROLS, EXACT_RXCUI, SELECTION,
    DrugIdentityRepository, identity_repository_from_env)
from daylight_data.serving.repository import STATE_KEYS


def binding():
    return ResearchBinding('a' * 64, 'fixture_test', 'b' * 64, {'database': 'fixture_test'},
        {'drug_identity': {'layer_id': 'L05', 'source_table': 'drug_identities',
            'derivation_id': 'fixture:drug-identities', 'source_path': 'fixture:dictionary',
            'source_sha256': 'c' * 64, 'adapter_code_sha256': 'd' * 64}}, (), {}, 'e' * 64)


def record(cui='1000048', ordinal=1, *, concept='SCD', partial=False):
    source = {'kind': 'NLM_RxNorm_history' if partial else 'CMS_2026_FRF',
              'member': 'fixture:FRF.csv', 'record_ordinal': ordinal, 'sha256': 'f' * 64}
    payload = {'rxcui': cui, 'name': 'Synthetic ingredient 5 MG ORAL TABLET',
               'type': concept, 'coverage_inferred': False, 'source': source, 'raw': {'fixture': True}}
    if partial:
        payload['history'] = {'status': 'Active', 'isCurrent': 'YES', 'source': 'RXNORM'}
    else:
        payload.update(dose_form='ORAL TABLET', ingredient_strength_description='Synthetic ingredient 5 MG', related_brand='')
    raw = {'rxcui': cui, 'payload': json.dumps(payload)}
    snapshot, table = 'fixture:snapshot', 'drug_identities'
    native_id = digest([snapshot, table, ordinal])
    return {'derivation_id': 'fixture:drug-identities', 'entity_type': 'drug_product',
        'entity_id': 'L05:' + native_id, 'source_table': table, 'source_row_ordinal': ordinal,
        'offering_id': None, 'benefit_year': 2026, 'raw_payload': raw, 'raw_sha256': digest(raw),
        'record_id': native_id, 'snapshot_id': snapshot, 'source_row_key': json.dumps([cui]),
        'ordinal_basis': 'sqlite_primary_key_order:rxcui', 'original_path': 'fixture:dictionary',
        'artifact_sha256': 'c' * 64, 'adapter_code_sha256': 'd' * 64,
        'conditions': [{'fixture_native_condition': 'Retain this exact context.'}],
        'snapshot_source_use_state': 'not_newly_reviewed',
        'fields': {'benefit_year': 2026, 'source_table': table, 'rxcui': cui,
            'drug_name': payload['name'], 'dose_form': payload.get('dose_form'),
            'ingredient_strength_description': payload.get('ingredient_strength_description'),
            'related_brand': payload.get('related_brand'), 'concept_type': concept, 'coverage_inferred': False},
        **{key: 'research_only' if key == 'output_acceptance_state' else 'not_newly_reviewed' for key in STATE_KEYS}}


class Cursor:
    def __init__(self, rows): self.rows = rows
    def fetchall(self): return copy.deepcopy(self.rows)
    def fetchone(self): return copy.deepcopy(self.rows[0])


class Connection:
    def __init__(self, rows, access, controls):
        self.rows, self.access, self.controls, self.calls = rows, access, controls, []
    def execute(self, query, params):
        self.calls.append((query, copy.deepcopy(params)))
        if query == ACCESS: return Cursor(self.access)
        if query == CONTROLS: return Cursor([self.controls])
        if query == EXACT_RXCUI: return Cursor(self.rows)
        raise AssertionError('Unexpected query in bounded identity fixture')


class FixtureRepository(DrugIdentityRepository):
    def __init__(self, rows=None, access=None, controls=None):
        super().__init__(lambda: None, binding())
        self.connection = Connection([record()] if rows is None else rows, access or [], controls or
                                    {'rows': 4547, 'min_year': 2026, 'max_year': 2026, 'offering_rows': 0})
        self.reads = 0
    @contextmanager
    def _read(self):
        self.reads += 1
        yield self.connection, [{'source_id': 'L03', 'state': 'unrelated', 'reason': 'Not identity authority.'}]


def test_exact_id_returns_source_candidate_with_strength_form_lineage_and_all_purpose_holds():
    repository = FixtureRepository()
    out = repository.lookup_rxcuis(['1000048'])
    candidate = out['candidates'][0]
    assert out['status'] == 'research_only' and out['operator_only']
    assert out['matches'][0]['state'] == 'exact_id_candidate'
    assert candidate['identity']['dose_form'] == 'ORAL TABLET'
    assert candidate['identity']['ingredient_strength_description'] == 'Synthetic ingredient 5 MG'
    assert candidate['raw_source_payload'] == repository.connection.rows[0]['raw_payload']
    assert candidate['conditions'] == repository.connection.rows[0]['conditions']
    assert candidate['lineage']['raw_sha256'] == digest(candidate['raw_source_payload'])
    assert out['binding']['accepted_release_id'] is None
    assert all(purpose['state'] == 'held' for purpose in out['authority'].values())
    assert not out['consumer_release'] and not out['personal_coverage_result']
    assert not candidate['automatic_profile_binding'] and candidate['requires_identity_confirmation']
    assert candidate['offering_grain'] is None
    assert out['dictionary_scope']['formulary_grain'] is None
    assert out['scope']['category'] == 'retained_drug_identity_dictionary'
    assert 'county_fips' not in out['scope']


def test_native_source_flags_never_become_output_authority():
    row = record(); row['output_acceptance_state'] = 'source_native_accepted_reference'
    out = FixtureRepository([row]).lookup_rxcuis(['1000048'])
    assert out['candidates'][0]['states']['output_acceptance_state'] == 'source_native_accepted_reference'
    assert out['candidates'][0]['output_authority'] == 'held'
    assert all(p['state'] == 'held' for p in out['authority'].values())


def test_unknown_id_is_selection_unknown_not_coverage_failure_or_zero():
    out = FixtureRepository([]).lookup_rxcuis(['9999999999'])
    assert out['candidates'] == []
    assert out['matches'][0]['state'] == 'not_observed_in_selected_dictionary'
    assert not out['personal_coverage_result']
    assert not out['automatic_profile_binding']
    assert {'G05', 'G08', 'G09', 'G11', 'G14'} == set(out['gaps_preserved'])


def test_multiple_source_candidates_stay_ambiguous_and_all_locators_survive():
    out = FixtureRepository([record(ordinal=1), record(ordinal=2)]).lookup_rxcuis(['1000048'])
    assert out['matches'][0]['state'] == 'ambiguous_source_identity'
    assert len(out['matches'][0]['candidate_refs']) == 2
    assert len(out['candidates']) == 2
    assert [r['source_locator']['record_ordinal'] for r in out['candidates']] == [1, 2]
    assert not out['automatic_profile_binding']


@pytest.mark.parametrize('concept', ['BPCK', 'GPCK'])
def test_pack_concept_is_not_decomposed_or_treated_as_one_clinical_product(concept):
    out = FixtureRepository([record(concept=concept)]).lookup_rxcuis(['1000048'])
    row = out['candidates'][0]
    assert row['identity_grain'] == 'pack_concept'
    assert row['identity']['concept_type'] == concept
    assert 'PACK_CONCEPT_NOT_SINGLE_PRODUCT' in row['reason_codes']
    assert not out['clinical_substitution']


def test_historical_rxnorm_missing_projection_parts_are_not_parsed_from_name():
    out = FixtureRepository([record(partial=True)]).lookup_rxcuis(['1000048'])
    row = out['candidates'][0]
    assert '5 MG' in row['identity']['drug_name']
    assert row['identity']['dose_form'] is None
    assert row['identity']['ingredient_strength_description'] is None
    assert row['identity_detail_state'] == 'partial'
    assert row['source_history']['isCurrent'] == 'YES'
    assert not row['current_terminology_status_verified']


def test_access_absence_is_explicit_unregistered_and_not_inherited_from_other_layers():
    out = FixtureRepository().lookup_rxcuis(['1000048'])
    assert out['source_access_registration']['state'] == 'unregistered'
    assert out['source_access_registration']['registered_source_ids'] == []
    assert not out['source_access_registration']['absence_is_permission']
    assert out['source_access_states'] == []


def test_source_stop_is_retained_and_changes_snapshot_without_releasing_identity():
    repository = FixtureRepository()
    first = repository.lookup_rxcuis(['1000048'])
    repository.connection.access = [{'source_id': 'L05', 'state': 'source_STOP',
                                      'reason': 'fixture:exact stop', 'updated_at': '2026-11-01'}]
    out = repository.lookup_rxcuis(['1000048'])
    assert out['source_access_states'][0]['state'] == 'source_STOP'
    assert out['source_access_registration']['state'] == 'registered'
    assert all(p['state'] == 'held' for p in out['authority'].values())
    with pytest.raises(ResearchServingError, match='STALE_RESEARCH_SNAPSHOT'):
        repository.lookup_rxcuis(['1000048'], expected_snapshot_id=first['binding']['snapshot_id'])


@pytest.mark.parametrize('ids,year', [([],2026), (['name only'],2026), (['1000048;SELECT 1'],2026),
    (['001000048'],2026), ([1000048],2026), ([True],2026), (['1000048','1000048'],2026),
    (list(map(str,range(1,22))),2026), (['1000048'],2026.0), (['1000048'],True), (['1000048'],2027)])
def test_invalid_names_sql_float_year_duplicate_or_unbounded_ids_never_read(ids,year):
    repository = FixtureRepository()
    with pytest.raises(ResearchServingError, match='INVALID_EXACT_RXCUI_REQUEST'):
        repository.lookup_rxcuis(ids,year=year)
    assert repository.reads == 0 and not repository.connection.calls


@pytest.mark.parametrize('change', ['count', 'year', 'offering_grain'])
def test_population_or_grain_drift_holds_instead_of_substituting_a_source(change):
    repository = FixtureRepository()
    repository.connection.controls[{'count':'rows','year':'min_year','offering_grain':'offering_rows'}[change]] = 1
    with pytest.raises(ResearchServingError, match='DRUG_IDENTITY_POPULATION_MISMATCH'):
        repository.lookup_rxcuis(['1000048'])
    assert not any(query == EXACT_RXCUI for query,params in repository.connection.calls)


@pytest.mark.parametrize('change', ['raw_rxcui','raw_hash','record_id','entity_id','projected_strength','year','offering'])
def test_native_projection_and_hash_lineage_mismatch_is_not_a_candidate(change):
    row = record()
    if change == 'raw_rxcui': row['raw_payload']['rxcui'] = '1000001'
    elif change == 'raw_hash': row['raw_sha256'] = 'bad'
    elif change == 'record_id': row['record_id'] = 'bad'
    elif change == 'entity_id': row['entity_id'] = 'bad'
    elif change == 'projected_strength': row['fields']['ingredient_strength_description'] = 'different'
    elif change == 'year': row['benefit_year'] = 2027
    else: row['offering_id'] = '2026:H9999:001:000'
    with pytest.raises(ResearchServingError, match='DRUG_IDENTITY_LINEAGE_MISMATCH'):
        FixtureRepository([row]).lookup_rxcuis(['1000048'])


def test_batch_parameters_source_order_snapshot_and_inputs_are_stable():
    rows = [record('1000048',1), record('1000054',2)]
    repository = FixtureRepository(rows)
    before = copy.deepcopy(rows)
    ids = ['1000054','1000048']
    out = repository.lookup_rxcuis(ids)
    assert ids == ['1000054','1000048'] and rows == before
    assert [r['rxcui'] for r in out['matches']] == ids
    assert [r['identity']['rxcui'] for r in out['candidates']] == ['1000048','1000054']
    assert out == repository.lookup_rxcuis(ids)
    exact_calls = [(q,p) for q,p in repository.connection.calls if q == EXACT_RXCUI]
    assert exact_calls[0][1] == ('fixture:drug-identities',ids)
    assert all(q.lstrip().startswith(('SELECT','WITH matched AS MATERIALIZED')) for q,p in repository.connection.calls)


def test_unrequested_or_unbounded_source_response_never_becomes_candidates():
    with pytest.raises(ResearchServingError, match='DRUG_IDENTITY_QUERY_MISMATCH'):
        FixtureRepository([record('1000054')]).lookup_rxcuis(['1000048'])
    with pytest.raises(ResearchServingError, match='DRUG_IDENTITY_LOOKUP_LIMIT'):
        FixtureRepository([record(ordinal=i) for i in range(1,102)]).lookup_rxcuis(['1000048'])


def test_other_selected_layer_cannot_stand_in_for_frozen_drug_dictionary():
    repository = FixtureRepository()
    repository.binding.selections['drug_identity']['layer_id'] = 'L08'
    with pytest.raises(ResearchServingError, match='DRUG_IDENTITY_SELECTION_REQUIRED'):
        repository.lookup_rxcuis(['1000048'])
    assert repository.reads == 0


def test_factory_reuses_exact_local_guard_and_loads_own_frozen_derivation(monkeypatch):
    import daylight_data.serving.identity as module
    seen = {}
    physical_factory = lambda: None
    class Base: _connection_factory = staticmethod(physical_factory)
    def base_factory(**kwargs): seen['physical'] = kwargs; return Base()
    def load(root,**kwargs): seen['binding'] = kwargs; return binding()
    monkeypatch.setattr(module,'repository_from_env',base_factory)
    monkeypatch.setattr(module,'load_local_binding',load)
    result = identity_repository_from_env(repository_root='fixture:root',dsn='fixture:dsn')
    assert isinstance(result,DrugIdentityRepository)
    assert result._connection_factory == Base()._connection_factory
    assert seen['physical'] == {'repository_root':'fixture:root','dsn':'fixture:dsn','timeout_ms':5000}
    assert seen['binding'] == {'selection':SELECTION}
