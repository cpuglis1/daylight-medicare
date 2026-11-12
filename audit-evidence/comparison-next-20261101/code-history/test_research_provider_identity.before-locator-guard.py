"""Exact actor/role/site source candidates; no customer or database writes."""
from contextlib import contextmanager
import copy
import json

import pytest

from daylight_data.adapters.common import SourceRecord
from daylight_data.adapters.l08 import project_record
from daylight_data.serving.binding import ResearchBinding, ResearchServingError, digest
from daylight_data.serving.repository import json_safe
from daylight_data.serving.provider_identity import (ACCESS, CONTROLS, ENTITY_NPI, ENTITY_EXACT,
    ROLES, LOCATIONS, LOCATORS, SOURCES, CONFLICTS, TABLE_ROWS, SELECTION,
    ProviderIdentityRepository, provider_repository_from_env)

NPI = '1000000001'
ACTOR = 'fixture.invalid/Practitioner/one'
LOCATION = 'fixture.invalid/Location/one'


def row(table, raw, ordinal):
    raw = copy.deepcopy(raw)
    source = SourceRecord('L08', 'docs/data/l08-provider-networks-2026-10-27/wellcare-r5/providers.sqlite3',
        table, ordinal, json.dumps([raw.get('entity_key', raw.get('id'))]), 'c'*64,
        'fixture:snapshot', 'fixture:'+table, raw, 'sqlite_primary_key_order', adapter_code_sha256='d'*64)
    projected = project_record(source)
    return {'derivation_id':source.derivation_id, 'entity_type':projected.entity_type,
        'entity_id':projected.entity_id, 'source_table':table,'source_row_ordinal':ordinal,
        'fields':json_safe(projected.fields), 'conditions':json_safe(projected.conditions),
        'raw_payload':raw, 'raw_sha256':digest(raw), 'record_id':source.record_id,
        'snapshot_id':source.snapshot_id,'source_row_key':source.source_row_key,'ordinal_basis':source.ordinal_basis,
        'original_path':source.source_path,'artifact_sha256':source.source_sha256,'adapter_code_sha256':'d'*64,
        'value_state':projected.value_state, 'evidence_state':projected.evidence_state,
        'semantic_review_state':projected.semantic_review_state,'source_use_state':projected.source_use_state,
        'freshness_state':projected.freshness_state,'output_acceptance_state':'research_only',
        'snapshot_source_use_state':'not_newly_reviewed'}


def actor(key=ACTOR, *, npi=NPI, kind='Practitioner', ordinal=1):
    return row('entities',{'entity_key':key,'type':kind,'observation_id':'fixture:entity:'+str(ordinal),
        'npi_json':json.dumps([npi] if npi else []),'name_json':json.dumps([{'text':'Synthetic source actor'}]),
        'status_json':json.dumps({'active':True}),
        'period_json':json.dumps({'start':'2025-01-01','end':'2025-12-31'})},ordinal)


def role(key='fixture.invalid/PractitionerRole/one', *, provider=ACTOR, organization=None,
         locations=(LOCATION,), ordinal=1):
    return row('roles',{'entity_key':key,'observation_id':'fixture:role:'+str(ordinal),
        'provider_key':provider,'organization_key':organization,'locations_json':json.dumps(list(locations)),
        'networks_json':json.dumps(['fixture.invalid/Organization/source-network']),
        'specialty_json':json.dumps(['Synthetic source specialty']),
        'period_json':json.dumps({'start':'0001-01-01','end':'9999-12-31'}),
        'qualifiers_json':json.dumps({'active':True,'source_qualification':'Keep this exact context.'})},ordinal)


def location(key=LOCATION, ordinal=1):
    return row('locations',{'entity_key':key,'observation_id':'fixture:location:'+str(ordinal),
        'name_json':json.dumps('Synthetic office'),
        'address_json':json.dumps({'line':['1 Synthetic Lane'],'city':'Synthetic city','state':'FL'}),
        'telecom_json':json.dumps([{'system':'phone','value':'fixture:phone'}]),
        'position_json':'null'},ordinal)


def conflict(npi='1999999999'):
    return row('source_conflicts',{'id':'fixture:conflict','kind':'published_identifier_conflict',
        'fields_json':json.dumps({'directory_npi':npi,'directory_street':'Synthetic site A',
                                 'registry_practice_address':'Synthetic site B','disposition':'Retain both facts; hold identity.'})},1)


def source():
    return row('sources',{'id':'fixture:source','url':'https://fixture.invalid/source',
        'sha256':'f'*64,'path':'fixture:original-artifact','retrieved':'2026-10-27T00:00:00Z'},1)


class Cursor:
    def __init__(self,rows): self.rows=copy.deepcopy(rows)
    def fetchall(self): return copy.deepcopy(self.rows)


class Connection:
    def __init__(self,entities,roles,locations,conflicts):
        self.entities,self.roles,self.locations,self.conflicts=entities,roles,locations,conflicts
        self.access=[];self.calls=[];self.omit_observations=set();self.omit_sources=False
        self.controls=[{'derivation_id':'fixture:'+table,'entity_type':'provider_'+table,'rows':count}
                       for table,count in TABLE_ROWS.items()]
    def execute(self,query,params):
        self.calls.append((query,copy.deepcopy(params)))
        if query==ACCESS:return Cursor(self.access)
        if query==CONTROLS:return Cursor(self.controls)
        if query in (ENTITY_NPI,ENTITY_EXACT):
            selected=[r for r in self.entities if r['source_row_ordinal']>params[2] and
                      (params[1] in r['fields']['npi'] if query==ENTITY_NPI else r['fields']['entity_key']==params[1])]
            return Cursor(sorted(selected,key=lambda r:r['source_row_ordinal'])[:21])
        if query==ROLES:
            selected=[r for r in self.roles if r['source_row_ordinal']>params[3] and
                      (r['fields']['provider_key'] in params[1] or r['fields']['entity_key'] in params[2])]
            return Cursor(sorted(selected,key=lambda r:r['source_row_ordinal'])[:51])
        if query==LOCATIONS:return Cursor([r for r in self.locations if r['fields']['entity_key'] in params[1]][:101])
        if query==CONFLICTS:return Cursor(self.conflicts)
        if query==LOCATORS:
            out=[]
            for i,identifier in enumerate(params[1],1):
                if identifier in self.omit_observations:continue
                native_id=digest(['fixture:snapshot','observations',i])
                out.append({'observation_id':identifier,'entity_id':'L08:'+native_id,'record_id':native_id,
                    'snapshot_id':'fixture:snapshot','source_row_ordinal':i,'source_table':'observations',
                    'derivation_id':'fixture:observations','source_id':'fixture:source','pointer':'/fixture/'+str(i),
                    'raw_sha256':'e'*64,'original_path':'fixture:dictionary','artifact_sha256':'c'*64,
                    'adapter_code_sha256':'d'*64,'entity_key':'fixture:entity-key','resource_type':'Fixture'})
            return Cursor(out)
        if query==SOURCES:return Cursor([] if self.omit_sources else [source()])
        raise AssertionError('Unexpected provider identity query')


class FixtureRepository(ProviderIdentityRepository):
    def __init__(self,entities=None,roles=None,locations=None,conflicts=None):
        binding=ResearchBinding('a'*64,'fixture_test','b'*64,{'database':'fixture_test'},
            {table:{'layer_id':'L08','source_table':table,'derivation_id':'fixture:'+table,
                    'source_path':'fixture:composite','source_sha256':'c'*64,'adapter_code_sha256':'d'*64}
             for table in TABLE_ROWS},(),{},'e'*64)
        super().__init__(lambda:None,binding)
        self.connection=Connection([actor()] if entities is None else entities,
            [role()] if roles is None else roles,[location()] if locations is None else locations,
            [conflict()] if conflicts is None else conflicts)
        self.reads=0
    @contextmanager
    def _read(self):
        self.reads+=1
        yield self.connection,[]


def test_exact_npi_role_site_keeps_native_periods_qualifiers_and_all_holds():
    repository=FixtureRepository();out=repository.lookup(npi=NPI)
    assert out['identity_state']=='site_identity_candidate'
    site=out['site_candidates'][0]
    assert site['relation_basis']=='explicit_role_provider_key_and_location_reference'
    assert site['source_periods']['entity']['end']=='2025-12-31'
    assert site['source_periods']['role']['start']=='0001-01-01'
    assert site['current_practice_status']=='dated_source_not_reverified'
    assert out['role_observations'][0]['source_native_fields']['qualifiers']['active'] is True
    assert out['role_observations'][0]['conditions']['provider_period']['end']=='9999-12-31'
    assert site['network_status']==site['participation_status']==site['appointment_availability']=='not_evaluated'
    assert not out['automatic_profile_binding'] and not out['consumer_release']
    assert all(p['state']=='held' for p in out['authority'].values())
    assert out['binding']['accepted_release_id'] is None
    assert out['federal_hospital_identity']==out['cms_participation']=='separate_not_queried'


def test_one_actor_two_roles_and_sites_are_explicit_disambiguation_not_first_site():
    other='fixture.invalid/Location/two'
    out=FixtureRepository(roles=[role(),role('fixture.invalid/PractitionerRole/two',locations=(other,),ordinal=2)],
                          locations=[location(),location(other,2)]).lookup(npi=NPI)
    assert out['identity_state']=='site_disambiguation_required'
    assert len(out['site_candidates'])==2
    assert len({r['candidate_id'] for r in out['site_candidates']})==2
    assert [r['location_key'] for r in out['site_candidates']]==[LOCATION,other]


def test_same_npi_distinct_actors_shared_site_and_identical_address_are_not_merged():
    other='fixture.invalid/Practitioner/two'
    out=FixtureRepository(entities=[actor(),actor(other,ordinal=2)],
        roles=[role(),role('fixture.invalid/PractitionerRole/two',provider=other,ordinal=2)]).lookup(npi=NPI)
    assert len(out['entity_candidates'])==2 and len(out['site_candidates'])==2
    assert len({r['candidate_id'] for r in out['site_candidates']})==2
    assert len({r['location_ref'] for r in out['site_candidates']})==1
    assert out['identity_state']=='site_disambiguation_required'


def test_npi_on_role_with_missing_actor_preserves_role_identity_without_inventing_person():
    key='fixture.invalid/PractitionerRole/one'
    out=FixtureRepository(entities=[actor(key,kind='PractitionerRole')],
        roles=[role(key,provider='fixture.invalid/Practitioner/unretained')]).lookup(npi=NPI)
    site=out['site_candidates'][0]
    assert site['entity_type']=='PractitionerRole'
    assert site['relation_basis']=='exact_role_entity_key_and_location_reference'
    assert site['actor_resolution_state']=='role_identity_actor_reference_not_separately_resolved'
    assert site['role_actor_key']=='fixture.invalid/Practitioner/unretained'
    assert len(out['entity_candidates'])==1
    assert out['partial']['unresolved_role_actor_keys']==['fixture.invalid/Practitioner/unretained']
    assert out['identity_state']=='partial_identity_candidates'


def test_role_without_native_actor_reference_stays_partial_without_fabricated_actor():
    key='fixture.invalid/PractitionerRole/one'
    out=FixtureRepository(entities=[actor(key,kind='PractitionerRole')],
        roles=[role(key,provider=None)]).lookup(entity_key=key)
    assert out['partial']['unresolved_role_actor_keys']==[None]
    assert out['site_candidates'][0]['role_actor_key'] is None
    assert out['identity_state']=='partial_identity_candidates'
    assert len(out['entity_candidates'])==1


def test_organization_affiliation_alone_does_not_supply_all_member_provider_sites():
    group='fixture.invalid/Organization/group'
    out=FixtureRepository(entities=[actor(group,kind='Organization')],
        roles=[role(provider=ACTOR,organization=group)]).lookup(npi=NPI)
    assert out['role_observations']==[] and out['site_candidates']==[]
    assert out['identity_state']=='site_identity_unresolved'


def test_exact_location_key_is_location_identity_not_a_clinician():
    out=FixtureRepository(entities=[actor(LOCATION,kind='Location')],roles=[]).lookup(entity_key=LOCATION)
    site=out['site_candidates'][0]
    assert site['relation_basis']=='exact_location_entity_key'
    assert site['actor_resolution_state']=='location_entity_only'
    assert site['role_ref'] is None and site['entity_type']=='Location'


def test_missing_locations_and_observation_sources_stay_partial_not_negative_network():
    repository=FixtureRepository(locations=[])
    out=repository.lookup(npi=NPI)
    assert out['identity_state']=='partial_identity_candidates'
    assert out['partial']['missing_location_keys']==[LOCATION]
    assert out['network_status']=='not_evaluated'
    repository=FixtureRepository();repository.connection.omit_observations={'fixture:role:1'}
    assert repository.lookup(npi=NPI)['partial']['missing_observation_ids']==['fixture:role:1']
    repository=FixtureRepository();repository.connection.omit_sources=True
    assert repository.lookup(npi=NPI)['partial']['missing_source_ids']==['fixture:source']


def test_published_identifier_conflict_retains_both_addresses_and_no_resolution():
    out=FixtureRepository(conflicts=[conflict(NPI)]).lookup(npi=NPI)
    assert out['identity_state']=='source_identity_conflict'
    detail=out['source_conflicts'][0]['source_native_fields']['fields']
    assert detail['directory_street']=='Synthetic site A'
    assert detail['registry_practice_address']=='Synthetic site B'
    assert out['site_candidates'][0]['identity_state']=='source_identity_conflict_requires_review'
    assert out['site_candidates'][0]['source_identity_conflict_refs']
    assert not out['automatic_profile_binding']


def test_missing_exact_id_is_unknown_in_partial_directory_not_absent_practice():
    out=FixtureRepository().lookup(npi='9999999999')
    assert out['identity_state']=='not_observed_in_selected_directory'
    assert not out['site_candidates']
    assert out['current_practice_status']=='dated_source_not_reverified'


@pytest.mark.parametrize('lookup_input',[{}, {'npi':NPI,'entity_key':ACTOR}, {'npi':1000000001},
    {'npi':'name only'}, {'npi':"1';SELECT 1"}, {'entity_key':'name with spaces'},
    {'npi':NPI,'year':2027}, {'npi':NPI,'year':2026.0}, {'npi':NPI,'after_entity_ordinal':True},
    {'npi':NPI,'after_role_ordinal':1}, {'npi':NPI,'after_entity_ordinal':90000}])
def test_invalid_or_unbound_pagination_requests_never_read(lookup_input):
    repository=FixtureRepository()
    with pytest.raises(ResearchServingError,match='INVALID_EXACT_PROVIDER_REQUEST'):repository.lookup(**lookup_input)
    assert repository.reads==0 and repository.connection.calls==[]


def test_npi_many_entity_pages_are_partial_and_require_the_same_snapshot():
    entities=[actor('fixture.invalid/Practitioner/'+str(i),ordinal=i) for i in range(1,23)]
    repository=FixtureRepository(entities=entities,roles=[])
    first=repository.lookup(npi=NPI)
    assert len(first['entity_candidates'])==20 and first['page']['entities_have_more']
    assert first['partial']['is_partial'] and first['page']['next_entity_ordinal']==20
    second=repository.lookup(npi=NPI,after_entity_ordinal=20,expected_snapshot_id=first['binding']['snapshot_id'])
    assert len(second['entity_candidates'])==2 and not second['page']['entities_have_more']
    assert first['binding']==second['binding']


def test_many_roles_and_locations_do_not_claim_complete_site_resolution():
    roles=[role('fixture.invalid/PractitionerRole/'+str(i),ordinal=i) for i in range(1,53)]
    out=FixtureRepository(roles=roles).lookup(npi=NPI)
    assert len(out['role_observations'])==50 and out['page']['roles_have_more']
    keys=tuple('fixture.invalid/Location/'+str(i) for i in range(1,105))
    out=FixtureRepository(roles=[role(locations=keys)],locations=[]).lookup(npi=NPI)
    assert out['partial']['unfetched_location_keys']==list(keys[100:])
    assert out['partial']['is_partial']


def test_site_candidate_cross_product_is_bounded_and_preserves_incomplete_state():
    keys=tuple('fixture.invalid/Location/'+str(i) for i in range(1,7))
    roles=[role('fixture.invalid/PractitionerRole/'+str(i),locations=keys,ordinal=i) for i in range(1,41)]
    out=FixtureRepository(roles=roles,locations=[location(key,i) for i,key in enumerate(keys,1)]).lookup(npi=NPI)
    assert len(out['site_candidates'])==200
    assert out['page']['site_candidates_have_more'] and out['partial']['is_partial']
    assert out['identity_state']=='partial_identity_candidates'
    assert len({r['candidate_id'] for r in out['site_candidates']})==200


def test_response_cap_fails_explicitly_instead_of_silently_trimming_source_evidence(monkeypatch):
    import daylight_data.serving.provider_identity as module
    monkeypatch.setattr(module,'MAX_RESPONSE_BYTES',100)
    with pytest.raises(ResearchServingError,match='PROVIDER_IDENTITY_RESPONSE_LIMIT'):
        FixtureRepository().lookup(npi=NPI)


def test_source_stop_or_changed_binding_rejects_old_snapshot_and_never_grants_authority():
    repository=FixtureRepository();first=repository.lookup(npi=NPI)
    assert first['source_access_registration']['state']=='unregistered'
    repository.connection.access=[{'source_id':'L08','state':'source_STOP','reason':'Synthetic stop'}]
    out=repository.lookup(npi=NPI)
    assert out['source_access_states'][0]['state']=='source_STOP'
    assert all(p['state']=='held' for p in out['authority'].values())
    with pytest.raises(ResearchServingError,match='STALE_RESEARCH_SNAPSHOT'):
        repository.lookup(npi=NPI,expected_snapshot_id=first['binding']['snapshot_id'])


@pytest.mark.parametrize('change',['population','raw_hash','native_name','entity_id'])
def test_source_or_projection_drift_is_not_a_candidate(change):
    repository=FixtureRepository()
    if change=='population':repository.connection.controls[0]['rows']=1
    elif change=='raw_hash':repository.connection.entities[0]['raw_sha256']='bad'
    elif change=='native_name':repository.connection.entities[0]['fields']['name']='different'
    else:repository.connection.entities[0]['entity_id']='bad'
    with pytest.raises(ResearchServingError,match='PROVIDER_IDENTITY_(?:POPULATION|LINEAGE)_MISMATCH'):
        repository.lookup(npi=NPI)


def test_candidate_identity_and_result_are_deterministic_without_mutating_source_rows():
    repository=FixtureRepository();before=copy.deepcopy(repository.connection.entities)
    first=repository.lookup(npi=NPI);second=repository.lookup(npi=NPI)
    assert first==second and repository.connection.entities==before
    entity=first['entity_candidates'][0]
    assert entity['candidate_id'].startswith('L08:entity:') and entity['kind']=='provider_entity'
    assert entity['lookup_snapshot_id']==first['binding']['snapshot_id']
    site=first['site_candidates'][0]
    assert site['candidate_id'].startswith('L08:site:')
    assert site['lookup_snapshot_id']==first['binding']['snapshot_id']
    assert first['sources'][0]['source_native_fields']['sha256']=='f'*64
    assert all(q.lstrip().startswith(('SELECT','WITH matched AS MATERIALIZED')) for q,p in repository.connection.calls)


def test_factory_reuses_existing_physical_guard_and_own_frozen_selection(monkeypatch):
    import daylight_data.serving.provider_identity as module
    seen={};connection=lambda:None
    class Base: _connection_factory=staticmethod(connection)
    def base(**kw):seen['base']=kw;return Base()
    def binding(root,**kw):seen['selection']=kw;return FixtureRepository().binding
    monkeypatch.setattr(module,'repository_from_env',base);monkeypatch.setattr(module,'load_local_binding',binding)
    repo=provider_repository_from_env(repository_root='fixture:root',dsn='fixture:dsn')
    assert isinstance(repo,ProviderIdentityRepository) and repo._connection_factory is connection
    assert seen['base']=={'repository_root':'fixture:root','dsn':'fixture:dsn','timeout_ms':5000}
    assert seen['selection']=={'selection':SELECTION}
