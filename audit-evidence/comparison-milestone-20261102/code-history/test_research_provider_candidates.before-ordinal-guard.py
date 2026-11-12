"""Bounded source-name discovery; explicit entity and site selection stays separate."""
from contextlib import contextmanager
import copy
import json

import pytest

from daylight_data.serving.binding import ResearchServingError
from daylight_data.serving.provider_candidates import (ProviderCandidateRepository, SEARCH,
    _query, _pattern, _name_groups)
from daylight_data.serving.provider_identity import LOCATORS, SOURCES
from test_research_provider_identity import FixtureRepository, Connection, Cursor, row


def named(name, ordinal=1, kind='Practitioner'):
    return row('entities',{'entity_key':'fixture.invalid/'+kind+'/name-'+str(ordinal),
        'type':kind,'observation_id':'fixture:entity:'+str(ordinal),
        'npi_json':json.dumps(['1000000001']),'name_json':json.dumps(name),
        'status_json':'{"active":true}','period_json':'null'},ordinal)


class DiscoveryConnection(Connection):
    def __init__(self,entities):
        super().__init__(entities,[],[],[])
        self.results=copy.deepcopy(entities)
        self.locator_edit=None;self.source_edit=None
    def execute(self,query,params):
        if query==SEARCH:
            self.calls.append((query,copy.deepcopy(params)))
            return Cursor([record for record in self.results if record['source_row_ordinal']>params[1]][:params[3]])
        cursor=super().execute(query,params)
        if query==LOCATORS and self.locator_edit:
            for record in cursor.rows:self.locator_edit(record)
        if query==SOURCES and self.source_edit:
            for record in cursor.rows:self.source_edit(record)
        return cursor


class FixtureDiscovery(ProviderCandidateRepository):
    def __init__(self,entities=None):
        seed=FixtureRepository()
        super().__init__(lambda:None,seed.binding)
        self.connection=DiscoveryConnection(entities or [named([{'given':['Maria'],'family':'Lopez'}])])
        self.reads=0
    @contextmanager
    def _read(self):
        self.reads+=1
        yield self.connection,[]


def test_structured_name_keeps_raw_parent_site_unknown_source_order_and_every_hold():
    repo=FixtureDiscovery();out=repo.search('Maria Lopez')
    assert out['candidate_count']==1 and out['operator_only']
    candidate=out['candidates'][0]
    assert candidate['label']=='Maria Lopez'
    assert candidate['source_native_fields']['name']==[{'given':['Maria'],'family':'Lopez'}]
    assert candidate['selector']=={'entity_key':candidate['entity_key']}
    assert candidate['source_observation_locator']['raw_parent_verified']
    assert candidate['source_observation_locator']['primary_record_refs']==[candidate['record_ref']]
    assert 'raw_payload' not in candidate['source_observation_locator']
    assert candidate['reported_city_resolution']=='not_evaluated_requires_explicit_role_site_lookup'
    assert candidate['literal_occurrence_is_not_identity']
    assert candidate['requires_explicit_entity_and_site_confirmation']
    assert not out['consumer_release'] and not out['automatic_profile_binding']
    assert all(authority['state']=='held' for authority in out['authority'].values())
    assert out['source_access_registration']['state']=='unregistered'
    assert out['source_access_registration']['absence_is_permission'] is False


def test_doctor_title_is_explicit_query_only_not_report_or_source_rewrite():
    out=FixtureDiscovery().search('Dr. Maria Lopez')
    assert out['requested']['name_text']=='Dr. Maria Lopez'
    assert out['requested']['literal_tokens']==['Maria','Lopez']
    assert out['requested']['leading_title_omitted_for_discovery_only']==['Dr.']
    assert out['candidates'][0]['label']=='Maria Lopez'


def test_organization_and_practitioner_with_shared_name_are_distinct_unranked_candidates():
    repo=FixtureDiscovery([named('Synthetic Health',1,'Organization'),named('Synthetic Health',2)])
    out=repo.search('Synthetic Health')
    assert len({candidate['candidate_id'] for candidate in out['candidates']})==2
    assert [candidate['source_native_fields']['type'] for candidate in out['candidates']]==['Organization','Practitioner']


def test_tokens_cannot_be_spliced_between_two_source_name_aliases():
    repo=FixtureDiscovery([named([{'given':['Maria'],'family':'Stone'}, {'given':['Helen'],'family':'Lopez'}])])
    with pytest.raises(ResearchServingError,match='PROVIDER_DISCOVERY_QUERY_MISMATCH'):
        repo.search('Maria Lopez')


def test_metadata_use_is_not_a_name_match():
    repo=FixtureDiscovery([named([{'use':'official','given':['Maria'],'family':'Lopez'}])])
    with pytest.raises(ResearchServingError,match='PROVIDER_DISCOVERY_QUERY_MISMATCH'):
        repo.search('official')
    assert _name_groups([{'use':'official','given':['Maria'],'family':'Lopez'}])==[['Maria','Lopez']]


@pytest.mark.parametrize('text', ['%', '_', '!', "O'Neil", 'Maria; SELECT', 'MÜLLER'])
def test_literal_sql_data_is_bound_not_interpolated(text):
    repo=FixtureDiscovery([named(text)])
    repo.search(text)
    query,params=next((q,p) for q,p in repo.connection.calls if q==SEARCH)
    assert params[2]==[_pattern(token) for token in _query(text)[0]]
    assert query==SEARCH and "ESCAPE '!'" in query
    if len(text)>1:assert text not in query


def test_pagination_pins_snapshot_and_never_silently_treats_first_page_as_complete():
    repo=FixtureDiscovery([named('Maria Lopez',i) for i in range(1,5)])
    first=repo.search('Maria Lopez',limit=2)
    assert first['page']['has_more'] and first['page']['next_after_ordinal']==2
    assert first['partial']['is_partial']
    second=repo.search('Maria Lopez',limit=2,after_ordinal=2,
        expected_snapshot_id=first['binding']['snapshot_id'])
    assert not second['page']['has_more']
    assert set(candidate['candidate_id'] for candidate in first['candidates']).isdisjoint(
        candidate['candidate_id'] for candidate in second['candidates'])


@pytest.mark.parametrize('kwargs',[{'year':2027},{'year':True},{'limit':0},{'limit':21},
    {'limit':True},{'after_ordinal':-1},{'after_ordinal':80310},{'after_ordinal':1},
    {'expected_snapshot_id':True}])
def test_invalid_request_has_no_source_reads(kwargs):
    repo=FixtureDiscovery()
    with pytest.raises(ResearchServingError):repo.search('Maria Lopez',**kwargs)
    assert repo.reads==0


@pytest.mark.parametrize('text',[None,{},'', '  ', 'a'*161,'Maria\nLopez','Maria\x00Lopez','a '*11])
def test_invalid_text_has_no_source_reads(text):
    repo=FixtureDiscovery()
    with pytest.raises(ResearchServingError):repo.search(text)
    assert repo.reads==0


def test_stale_snapshot_stops_before_candidate_query():
    repo=FixtureDiscovery()
    with pytest.raises(ResearchServingError,match='STALE_RESEARCH_SNAPSHOT'):
        repo.search('Maria Lopez',expected_snapshot_id='old')
    assert not any(query==SEARCH for query,_ in repo.connection.calls)


def test_unknown_does_not_become_absence_of_provider_or_network():
    repo=FixtureDiscovery();repo.connection.results=[]
    out=repo.search('No fixture name')
    assert out['discovery_state']=='not_observed_in_selected_literal_query'
    assert out['candidates']==[] and out['network_status']=='not_evaluated'


@pytest.mark.parametrize('field,value',[('raw_sha256','bad'),('derivation_id','foreign'),
    ('original_path','foreign'),('artifact_sha256','f'*64),('adapter_code_sha256','f'*64),
    ('source_row_key','["foreign"]'),('entity_id','foreign')])
def test_foreign_or_tampered_retained_entity_rejects(field,value):
    repo=FixtureDiscovery();repo.connection.results[0][field]=value
    with pytest.raises(ResearchServingError):repo.search('Maria Lopez')


@pytest.mark.parametrize('field,value',[('pointer','foreign'),('entity_key','foreign'),
    ('resource_type','Organization'),('raw_sha256','not-a-source-hash'),('original_path','foreign')])
def test_native_locator_drift_rejects(field,value):
    repo=FixtureDiscovery();repo.connection.locator_edit=lambda item:item.__setitem__(field,value)
    with pytest.raises(ResearchServingError,match='PROVIDER_SOURCE_LOCATOR_MISMATCH'):
        repo.search('Maria Lopez')


def test_missing_native_observation_remains_partial_not_invented():
    repo=FixtureDiscovery();repo.connection.omit_observations={'fixture:entity:1'}
    out=repo.search('Maria Lopez')
    assert out['partial']['source_lineage_partial']
    assert out['candidates'][0]['identity_detail_state']=='source_lineage_partial'
    assert out['candidates'][0]['source_observation_locator'] is None


def test_missing_source_record_remains_partial_not_permission():
    repo=FixtureDiscovery();repo.connection.omit_sources=True
    out=repo.search('Maria Lopez')
    assert out['partial']['source_lineage_partial'] and not out['consumer_release']


def test_population_loss_rejects():
    repo=FixtureDiscovery();repo.connection.controls[0]['rows']-=1
    with pytest.raises(ResearchServingError,match='PROVIDER_IDENTITY_POPULATION_MISMATCH'):
        repo.search('Maria Lopez')


def test_query_cannot_return_other_name_or_duplicate_ordinals():
    repo=FixtureDiscovery([named('Helen Stone')])
    with pytest.raises(ResearchServingError,match='PROVIDER_DISCOVERY_QUERY_MISMATCH'):
        repo.search('Maria Lopez')
    repo=FixtureDiscovery();repo.connection.results*=2
    with pytest.raises(ResearchServingError,match='PROVIDER_DISCOVERY_QUERY_MISMATCH'):
        repo.search('Maria Lopez')
