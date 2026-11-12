"""Exact provider/entity and explicit-site candidates from dated L08 research.

The wellcare-r5 file is a composite directory reference. Its FHIR entities,
roles and locations are not federal hospital/participation records, and neither
an NPI nor a role/location link establishes network or appointment availability.
No name similarity, address merging, new source acquisition or profile binding.
"""
import copy
import json
import re
from decimal import Decimal

from .binding import ResearchServingError, digest, load_local_binding
from .repository import ResearchPlanRepository, STATE_KEYS, json_safe, repository_from_env


VERSION = 'l08-exact-provider-site-research-r1'
TABLE_ROWS = {'entities': 80309, 'roles': 72223, 'locations': 6025,
              'observations': 82055, 'sources': 1231, 'source_conflicts': 1}
SELECTION = {table: ('L08', table, '/wellcare-r5/') for table in TABLE_ROWS}
NPI = re.compile(r'[0-9]{10}\Z')
ENTITY_KEY = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:/?%+=~@-]{0,511}\Z')
MAX_ENTITIES, MAX_ROLES, MAX_LOCATIONS, MAX_SITES = 20, 50, 100, 200
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
SOURCE_ACCESS_IDS = ('sealed-local:L08', 'L08')
ACTOR_TYPES = {'Practitioner', 'Organization', 'PractitionerRole', 'OrganizationAffiliation'}

CONTROLS = """SELECT derivation_id,entity_type,count(*) AS rows FROM dl_evidence.observation
 WHERE derivation_id=ANY(%s) GROUP BY derivation_id,entity_type"""
ACCESS = """SELECT source_id,state,reason,updated_at FROM dl_control.source_access_state
 WHERE source_id=ANY(%s) ORDER BY source_id"""

SELECT = """WITH matched AS MATERIALIZED (
 SELECT * FROM dl_evidence.observation WHERE derivation_id=%s AND entity_type='{entity_type}'
 AND {predicate} ORDER BY source_row_ordinal LIMIT {limit})
 SELECT o.*,r.raw_payload,r.raw_sha256,r.record_id,r.source_row_key,r.ordinal_basis,
 d.snapshot_id,d.adapter_code_sha256,s.original_path,s.artifact_sha256,
 s.source_use_state AS snapshot_source_use_state FROM matched o
 JOIN dl_evidence.source_record r USING(derivation_id,source_table,source_row_ordinal)
 JOIN dl_control.derivation d USING(derivation_id)
 JOIN dl_control.source_snapshot s USING(snapshot_id) ORDER BY o.source_row_ordinal"""
ENTITY_NPI = SELECT.format(entity_type='provider_entities',
    predicate="fields->'npi' ? %s AND source_row_ordinal>%s", limit=MAX_ENTITIES + 1)
ENTITY_EXACT = SELECT.format(entity_type='provider_entities',
    predicate="fields->>'entity_key'=%s AND source_row_ordinal>%s", limit=MAX_ENTITIES + 1)
ROLES = SELECT.format(entity_type='provider_roles',
    predicate="(fields->>'provider_key'=ANY(%s) OR fields->>'entity_key'=ANY(%s)) AND source_row_ordinal>%s",
    limit=MAX_ROLES + 1)
LOCATIONS = SELECT.format(entity_type='provider_locations',
    predicate="fields->>'entity_key'=ANY(%s)", limit=MAX_LOCATIONS + 1)
CONFLICTS = SELECT.format(entity_type='provider_source_conflicts', predicate='true', limit=2)
SOURCES = SELECT.format(entity_type='provider_sources', predicate="fields->>'id'=ANY(%s)", limit=201)

# Native FHIR observation locators are separate evidence from normalized entity
# rows. Retain their exact raw-parent identity without returning every unrelated
# clinical/network field from the original resource a second time.
LOCATORS = """WITH matched AS MATERIALIZED (
 SELECT * FROM dl_evidence.observation WHERE derivation_id=%s AND entity_type='provider_observations'
 AND fields->>'id'=ANY(%s) ORDER BY source_row_ordinal LIMIT 201)
 SELECT o.entity_id,o.source_table,o.source_row_ordinal,o.derivation_id,
 o.fields->>'id' AS observation_id,o.fields->>'source_id' AS source_id,
 o.fields->>'pointer' AS pointer,o.fields->>'entity_key' AS entity_key,
 o.fields->>'type' AS resource_type,r.record_id,r.raw_sha256,d.snapshot_id,
 s.original_path,s.artifact_sha256,d.adapter_code_sha256 FROM matched o
 JOIN dl_evidence.source_record r USING(derivation_id,source_table,source_row_ordinal)
 JOIN dl_control.derivation d USING(derivation_id)
 JOIN dl_control.source_snapshot s USING(snapshot_id) ORDER BY o.source_row_ordinal"""


def _lineage(row):
    return {key: row.get(key) for key in ('derivation_id', 'snapshot_id', 'artifact_sha256',
        'original_path', 'source_table', 'source_row_ordinal', 'source_row_key', 'ordinal_basis',
        'raw_sha256', 'record_id', 'adapter_code_sha256')}


def _record(row, table):
    raw, fields = row.get('raw_payload'), row.get('fields')
    if (not isinstance(raw, dict) or not isinstance(fields, dict)
            or row.get('source_table') != table or row.get('entity_type') != 'provider_' + table
            or row.get('raw_sha256') != digest(raw)
            or row.get('record_id') != digest([row.get('snapshot_id'), table, row.get('source_row_ordinal')])
            or row.get('entity_id') != 'L08:' + row.get('record_id', '')
            or fields.get('reference_component') != 'wellcare-r5'
            or fields.get('identity_is_not_network_verification') is not True
            or fields.get('personal_network_status_determined') is not False):
        raise ResearchServingError('PROVIDER_IDENTITY_LINEAGE_MISMATCH')
    for key, value in raw.items():
        target = key
        if key.endswith('_json') and isinstance(value, str):
            target = 'provider_period' if key == 'period_json' else key[:-5]
            try:
                value = json_safe(json.loads(value, parse_float=Decimal))
            except (TypeError, ValueError):
                raise ResearchServingError('PROVIDER_IDENTITY_LINEAGE_MISMATCH') from None
        if target not in fields or fields[target] != value:
            raise ResearchServingError('PROVIDER_IDENTITY_LINEAGE_MISMATCH')
    return {'record_ref': row['entity_id'], 'source_table': table,
            'source_native_fields': copy.deepcopy(fields), 'raw_source_payload': copy.deepcopy(raw),
            'conditions': copy.deepcopy(row['conditions']), 'states': {key: row[key] for key in STATE_KEYS},
            'lineage': _lineage(row), 'snapshot_source_use_state': row.get('snapshot_source_use_state'),
            'output_authority': 'held', 'source_native_flags_are_not_authority': True}


def _strings(value, *, keys=False):
    if (not isinstance(value, list) or any(not isinstance(key, str) for key in value)
            or keys and any(not ENTITY_KEY.fullmatch(key) for key in value)):
        raise ResearchServingError('PROVIDER_IDENTITY_REFERENCE_INVALID')
    return value


def _unique(values):
    return list(dict.fromkeys(values))


def _site(entity, role, location, snapshot_id):
    ef, lf = entity['source_native_fields'], location['source_native_fields']
    rf = role['source_native_fields'] if role else {}
    basis = ('exact_location_entity_key' if role is None else
             'explicit_role_provider_key_and_location_reference' if rf.get('provider_key') == ef['entity_key']
             else 'exact_role_entity_key_and_location_reference')
    return {
        'candidate_id': 'L08:site:' + digest([entity['record_ref'], role['record_ref'] if role else None,
                                             location['record_ref']]),
        'kind': 'provider_site', 'namespace': 'retained_L08_composite_directory_site',
        'lookup_snapshot_id': snapshot_id, 'source_component': 'wellcare-r5_composite_reference',
        'entity_ref': entity['record_ref'], 'entity_key': ef['entity_key'], 'entity_type': ef['type'],
        'source_npis': copy.deepcopy(ef.get('npi', [])),
        'source_name': copy.deepcopy(ef.get('name')),
        'role_ref': role['record_ref'] if role else None,
        'role_key': rf.get('entity_key'), 'role_actor_key': rf.get('provider_key'),
        'source_organization_reference': rf.get('organization_key'),
        'location_ref': location['record_ref'], 'location_key': lf['entity_key'],
        'source_location': {key: copy.deepcopy(lf.get(key)) for key in ('name', 'address', 'telecom', 'position')},
        'relation_basis': basis,
        'actor_resolution_state': ('location_entity_only' if role is None else
                                   'explicit_source_actor_entity' if rf.get('provider_key') == ef['entity_key']
                                   else 'role_identity_actor_reference_not_separately_resolved'),
        'source_periods': {'entity': copy.deepcopy(ef.get('provider_period')),
                           'role': copy.deepcopy(rf.get('provider_period'))},
        'identity_state': 'requires_explicit_site_disambiguation',
        'automatic_profile_binding': False, 'network_status': 'not_evaluated',
        'participation_status': 'not_evaluated', 'appointment_availability': 'not_evaluated',
        'current_practice_status': 'dated_source_not_reverified', 'output_authority': 'held',
    }


class ProviderIdentityRepository(ResearchPlanRepository):
    """Bounded exact selector then explicit source actor/role/location edges."""

    def lookup(self, *, npi=None, entity_key=None, year=2026, expected_snapshot_id=None,
               after_entity_ordinal=0, after_role_ordinal=0):
        if (type(year) is not int or year != 2026 or (npi is None) == (entity_key is None)
                or npi is not None and (not isinstance(npi, str) or not NPI.fullmatch(npi))
                or entity_key is not None and (not isinstance(entity_key, str) or not ENTITY_KEY.fullmatch(entity_key))
                or any(type(value) is not int or value < 0 for value in (after_entity_ordinal, after_role_ordinal))
                or after_entity_ordinal > TABLE_ROWS['entities'] or after_role_ordinal > TABLE_ROWS['roles']
                or expected_snapshot_id is not None and not isinstance(expected_snapshot_id, str)
                or (after_entity_ordinal or after_role_ordinal) and expected_snapshot_id is None):
            raise ResearchServingError('INVALID_EXACT_PROVIDER_REQUEST')
        selections = self.binding.selections
        if (set(selections) != set(TABLE_ROWS) or any(s.get('layer_id') != 'L08'
                or s.get('source_table') != table for table, s in selections.items())):
            raise ResearchServingError('PROVIDER_IDENTITY_SELECTION_REQUIRED')
        with self._read() as (connection, _base_access):
            access = connection.execute(ACCESS, (list(SOURCE_ACCESS_IDS),)).fetchall()
            result = self._envelope(json_safe(access))
            snapshot_id = result['binding']['snapshot_id']
            if expected_snapshot_id is not None and expected_snapshot_id != snapshot_id:
                raise ResearchServingError('STALE_RESEARCH_SNAPSHOT')
            controls = connection.execute(CONTROLS, ([s['derivation_id'] for s in selections.values()],)).fetchall()
            observed = {(row['derivation_id'], row['entity_type']): row['rows'] for row in controls}
            expected = {(s['derivation_id'], 'provider_' + table): TABLE_ROWS[table] for table, s in selections.items()}
            if observed != expected:
                raise ResearchServingError('PROVIDER_IDENTITY_POPULATION_MISMATCH')

            selector_query, selector = (ENTITY_NPI, npi) if npi is not None else (ENTITY_EXACT, entity_key)
            rows = connection.execute(selector_query,
                (selections['entities']['derivation_id'], selector, after_entity_ordinal)).fetchall()
            more_entities = len(rows) > MAX_ENTITIES
            entities = [_record(row, 'entities') for row in rows[:MAX_ENTITIES]]
            for entity in entities:
                f = entity['source_native_fields']
                _strings(f.get('npi'))
                if (not isinstance(f.get('entity_key'), str) or not ENTITY_KEY.fullmatch(f['entity_key'])
                        or not isinstance(f.get('type'), str) or
                        (npi is not None and npi not in f['npi']) or
                        (entity_key is not None and f['entity_key'] != entity_key)):
                    raise ResearchServingError('PROVIDER_IDENTITY_QUERY_MISMATCH')
                entity.update(candidate_id='L08:entity:' + digest([entity['record_ref']]),
                    kind='provider_entity', namespace='retained_L08_composite_directory_entity',
                    lookup_snapshot_id=snapshot_id, automatic_profile_binding=False,
                    current_practice_status='dated_source_not_reverified')
            keys = [entity['source_native_fields']['entity_key'] for entity in entities
                    if entity['source_native_fields']['type'] in ACTOR_TYPES]
            role_rows = connection.execute(ROLES,
                (selections['roles']['derivation_id'], keys, keys, after_role_ordinal)).fetchall() if keys else []
            more_roles = len(role_rows) > MAX_ROLES
            roles = [_record(row, 'roles') for row in role_rows[:MAX_ROLES]]
            for role in roles:
                f = role['source_native_fields']
                _strings(f.get('locations'), keys=True)
                if f.get('provider_key') not in keys and f.get('entity_key') not in keys:
                    raise ResearchServingError('PROVIDER_ROLE_QUERY_MISMATCH')
            location_keys = _unique([e['source_native_fields']['entity_key'] for e in entities
                                     if e['source_native_fields']['type'] == 'Location']
                                    + [key for role in roles for key in role['source_native_fields']['locations']])
            queried_location_keys = location_keys[:MAX_LOCATIONS]
            location_rows = connection.execute(LOCATIONS,
                (selections['locations']['derivation_id'], queried_location_keys)).fetchall() if queried_location_keys else []
            if len(location_rows) > MAX_LOCATIONS:
                raise ResearchServingError('PROVIDER_LOCATION_QUERY_LIMIT')
            locations = [_record(row, 'locations') for row in location_rows]
            location_map = {}
            for location in locations:
                key = location['source_native_fields'].get('entity_key')
                if key not in queried_location_keys or key in location_map:
                    raise ResearchServingError('PROVIDER_LOCATION_QUERY_MISMATCH')
                location_map[key] = location

            all_records = entities + roles + locations
            observation_ids = _unique([r['source_native_fields'].get('observation_id') for r in all_records
                                       if isinstance(r['source_native_fields'].get('observation_id'), str)])
            locators = connection.execute(LOCATORS,
                (selections['observations']['derivation_id'], observation_ids)).fetchall() if observation_ids else []
            if len(locators) > 200 or any(r['observation_id'] not in observation_ids for r in locators):
                raise ResearchServingError('PROVIDER_SOURCE_LOCATOR_MISMATCH')
            for locator in locators:
                if (locator['record_id'] != digest([locator['snapshot_id'], 'observations', locator['source_row_ordinal']])
                        or locator['entity_id'] != 'L08:' + locator['record_id']):
                    raise ResearchServingError('PROVIDER_SOURCE_LOCATOR_MISMATCH')
            source_ids = _unique([r['source_id'] for r in locators if isinstance(r.get('source_id'), str)])
            source_rows = connection.execute(SOURCES,
                (selections['sources']['derivation_id'], source_ids)).fetchall() if source_ids else []
            if len(source_rows) > 200:
                raise ResearchServingError('PROVIDER_SOURCE_LOCATOR_LIMIT')
            sources = [_record(row, 'sources') for row in source_rows]
            if any(r['source_native_fields'].get('id') not in source_ids for r in sources):
                raise ResearchServingError('PROVIDER_SOURCE_LOCATOR_MISMATCH')
            conflict_rows = connection.execute(CONFLICTS, (selections['source_conflicts']['derivation_id'],)).fetchall()
            if len(conflict_rows) != TABLE_ROWS['source_conflicts']:
                raise ResearchServingError('PROVIDER_IDENTITY_POPULATION_MISMATCH')
            relevant_npis = set([npi] if npi is not None else []) | {
                value for entity in entities for value in entity['source_native_fields']['npi']}
            conflicts = []
            for row in conflict_rows:
                record = _record(row, 'source_conflicts')
                detail = record['source_native_fields'].get('fields', {})
                if any(detail.get(key) in relevant_npis for key in ('directory_npi', 'registry_npi', 'npi')):
                    conflicts.append(record)

            sites = []
            for entity in entities:
                ef = entity['source_native_fields']
                if ef['type'] == 'Location' and ef['entity_key'] in location_map:
                    sites.append(_site(entity, None, location_map[ef['entity_key']], snapshot_id))
                for role in roles:
                    rf = role['source_native_fields']
                    if ef['entity_key'] in {rf.get('provider_key'), rf.get('entity_key')}:
                        for key in rf['locations']:
                            if key in location_map:
                                sites.append(_site(entity, role, location_map[key], snapshot_id))
            more_sites = len(sites) > MAX_SITES
            sites = sites[:MAX_SITES]
            for site in sites:
                site['source_identity_conflict_refs'] = [record['record_ref'] for record in conflicts
                    if any(record['source_native_fields']['fields'].get(key) in site['source_npis']
                           for key in ('directory_npi', 'registry_npi', 'npi'))]
                if site['source_identity_conflict_refs']:
                    site['identity_state'] = 'source_identity_conflict_requires_review'
            missing_locations = [key for key in queried_location_keys if key not in location_map]
            unfetched_locations = location_keys[MAX_LOCATIONS:]
            missing_observations = sorted(set(observation_ids) - {r['observation_id'] for r in locators})
            missing_sources = sorted(set(source_ids) - {r['source_native_fields']['id'] for r in sources})
            records_without_observation = [r['record_ref'] for r in all_records
                if not isinstance(r['source_native_fields'].get('observation_id'), str)
                or not r['source_native_fields']['observation_id']]
            locators_without_source = [r['entity_id'] for r in locators
                if not isinstance(r.get('source_id'), str) or not r['source_id']]
            entity_keys = {entity['source_native_fields']['entity_key'] for entity in entities}
            unresolved_actors = _unique([role['source_native_fields'].get('provider_key') for role in roles
                if role['source_native_fields'].get('provider_key') not in entity_keys])
            partial = bool(more_entities or more_roles or more_sites or missing_locations or unfetched_locations
                           or missing_observations or missing_sources or records_without_observation
                           or locators_without_source or unresolved_actors)
            state = ('source_identity_conflict' if conflicts else
                     'not_observed_in_selected_directory' if not entities else
                     'partial_identity_candidates' if partial else
                     'site_disambiguation_required' if len(sites) > 1 or len(entities) > 1 else
                     'site_identity_candidate' if sites else 'site_identity_unresolved')
            result.update(
                contract_id=VERSION, operator_only=True,
                scope={'year': year, 'category': 'composite_directory_identity',
                       'source_component': 'wellcare-r5', 'personal_geography_or_plan_scope': None},
                requested={'npi': npi, 'entity_key': entity_key, 'year': year,
                           'after_entity_ordinal': after_entity_ordinal, 'after_role_ordinal': after_role_ordinal},
                identity_state=state, source_population=dict(TABLE_ROWS),
                entity_candidates=entities, role_observations=roles, location_observations=locations,
                site_candidates=sites, source_observation_locators=json_safe(locators),
                sources=sources, source_conflicts=conflicts,
                page={'entities_have_more': more_entities, 'roles_have_more': more_roles,
                      'site_candidates_have_more': more_sites,
                      'next_entity_ordinal': rows[MAX_ENTITIES - 1]['source_row_ordinal'] if more_entities else None,
                      'next_role_ordinal': role_rows[MAX_ROLES - 1]['source_row_ordinal'] if more_roles else None,
                      'ordering': 'source_row_ordinal_then_source_location_reference', 'snapshot_id': snapshot_id},
                partial={'is_partial': partial, 'missing_location_keys': missing_locations,
                         'unfetched_location_keys': unfetched_locations,
                         'missing_observation_ids': missing_observations, 'missing_source_ids': missing_sources,
                         'records_without_observation_id': records_without_observation,
                         'locators_without_source_id': locators_without_source,
                         'unresolved_role_actor_keys': unresolved_actors},
                source_access_registration={'state': 'registered' if access else 'unregistered',
                    'requested_source_ids': list(SOURCE_ACCESS_IDS), 'absence_is_permission': False,
                    'output_authority': 'held'},
                federal_hospital_identity='separate_not_queried', cms_participation='separate_not_queried',
                automatic_profile_binding=False, consumer_release=False,
                network_status='not_evaluated', participation_status='not_evaluated',
                appointment_availability='not_evaluated', eligibility='not_evaluated',
                current_practice_status='dated_source_not_reverified',
                gaps_preserved=['G05', 'G06', 'G12', 'G14'])
            result['limitations'] = [
                'Composite normalized directory snapshot, not a complete provider roster or current registry verification.',
                'NPI-bearing practitioners, organizations, roles and locations remain distinct source entities.',
                'Only explicit role provider/location references form site candidates; organization membership is not a substitute.',
                'Names or matching addresses do not merge entities/sites; shared sites and multiple roles remain separate.',
                'A source active flag or period does not establish current practice, participation, network access or appointments.',
                'Missing, truncated or conflicting source references are unresolved, never a negative coverage finding.',
                'Federal hospital IDs, Original Medicare assignments/enrollment/optout, and medical-plan network findings need separate methods and sources.',
                'Every site candidate still requires explicit item/person/time disambiguation; customer confirmation grants no consumer source authority.',
            ]
            safe = json_safe(result)
            if len(json.dumps(safe, ensure_ascii=False).encode()) > MAX_RESPONSE_BYTES:
                raise ResearchServingError('PROVIDER_IDENTITY_RESPONSE_LIMIT')
            return safe


def provider_repository_from_env(*, repository_root, dsn=None, timeout_ms=5000):
    base = repository_from_env(repository_root=repository_root, dsn=dsn, timeout_ms=timeout_ms)
    binding = load_local_binding(repository_root, selection=SELECTION)
    return ProviderIdentityRepository(base._connection_factory, binding, timeout_ms=timeout_ms)
