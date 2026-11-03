"""Literal name discovery in the retained L08 composite directory.

This operator projection finds possible source entities. It does not identify a
person, merge aliases, choose an office or establish network participation.
Each name variant is searched separately; name tokens cannot be assembled from
different aliases. The exact actor/role/site lookup remains a separate action.
"""
import copy
import json
import re

from .binding import ResearchServingError, digest, load_local_binding
from .provider_identity import (ProviderIdentityRepository, SELECTION, TABLE_ROWS,
    CONTROLS, ACCESS, SOURCE_ACCESS_IDS, ENTITY_KEY, LOCATORS, SOURCES, _record, _locator)
from .repository import json_safe, repository_from_env

VERSION = 'l08-literal-provider-candidates-research-r1'
MAX_TEXT_CHARS = 160
MAX_TOKENS = 10
MAX_PAGE = 20
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
CONTROL_CHAR = re.compile(r'[\x00-\x1f\x7f-\x9f]')
NAME_KEYS = ('text', 'prefix', 'given', 'family', 'suffix')

# A HumanName object is one variant; a scalar organization name is another.
# Only name-bearing values are inspected: metadata such as use='official' is
# not a name token. Every supplied token must occur within the SAME variant.
SEARCH = """WITH matched AS MATERIALIZED (
 SELECT o.* FROM dl_evidence.observation o WHERE derivation_id=%s
 AND entity_type='provider_entities' AND source_table='entities'
 AND source_row_ordinal>%s AND EXISTS (
   SELECT 1 FROM jsonb_array_elements(CASE WHEN jsonb_typeof(o.fields->'name')='array'
     THEN o.fields->'name' ELSE jsonb_build_array(o.fields->'name') END) AS variants(variant)
   WHERE NOT EXISTS (
     SELECT 1 FROM unnest(%s::text[]) AS requested(pattern)
     WHERE NOT EXISTS (
       SELECT 1 FROM jsonb_path_query(CASE WHEN jsonb_typeof(variant)='object'
         THEN jsonb_build_array(variant->'text',variant->'prefix',variant->'given',variant->'family',variant->'suffix')
         ELSE variant END, '$.** ? (@.type() == "string")') AS leaves(value)
       WHERE leaves.value #>> '{}' ILIKE requested.pattern ESCAPE '!')))
 ORDER BY source_row_ordinal LIMIT %s)
 SELECT o.*,r.raw_payload,r.raw_sha256,r.record_id,r.source_row_key,r.ordinal_basis,
 d.snapshot_id,d.adapter_code_sha256,s.original_path,s.artifact_sha256,
 s.source_use_state AS snapshot_source_use_state FROM matched o
 JOIN dl_evidence.source_record r USING(derivation_id,source_table,source_row_ordinal)
 JOIN dl_control.derivation d USING(derivation_id)
 JOIN dl_control.source_snapshot s USING(snapshot_id) ORDER BY o.source_row_ordinal"""


def _query(value):
    if (not isinstance(value, str) or not value.strip() or len(value) > MAX_TEXT_CHARS
            or CONTROL_CHAR.search(value)):
        raise ResearchServingError('INVALID_LITERAL_PROVIDER_REQUEST')
    words = value.strip().split()
    omitted = []
    if len(words) > 1 and words[0].casefold().rstrip('.') in {'dr', 'doctor'}:
        omitted = words[:1]
        words = words[1:]
    if not words or len(words) > MAX_TOKENS:
        raise ResearchServingError('INVALID_LITERAL_PROVIDER_REQUEST')
    return words, omitted


def _pattern(value):
    return '%' + value.replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%'


def _strings(value):
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [text for child in value for text in _strings(child)]
    return []


def _name_groups(value):
    variants = value if isinstance(value, list) else [value]
    groups = []
    for variant in variants:
        if isinstance(variant, str):
            strings = _strings(variant)
        elif isinstance(variant, dict):
            strings = [text for key in NAME_KEYS for text in _strings(variant.get(key))]
        else:
            strings = []
        if strings:
            groups.append(strings)
    return groups


def _matches(value, tokens):
    return any(all(any(token.casefold() in text.casefold() for text in group)
                   for token in tokens) for group in _name_groups(value))


def _label(value):
    variants = value if isinstance(value, list) else [value]
    labels = []
    for variant in variants:
        if isinstance(variant, str) and variant.strip():
            labels.append(variant)
        elif isinstance(variant, dict):
            text = _strings(variant.get('text'))
            parts = text or [part for key in ('prefix', 'given', 'family', 'suffix')
                             for part in _strings(variant.get(key))]
            if parts:
                labels.append(' '.join(parts))
    return ' / '.join(labels)


def _selected_record(row, selection, table):
    record = _record(row, table)
    ordinal = row.get('source_row_ordinal')
    primary_key = 'entity_key' if table == 'entities' else 'id'
    try:
        key = json.loads(row['source_row_key'])
    except (TypeError, ValueError, KeyError):
        raise ResearchServingError('PROVIDER_DISCOVERY_LINEAGE_MISMATCH') from None
    fields = record['source_native_fields']
    if (type(ordinal) is not int or not 1 <= ordinal <= TABLE_ROWS[table]
            or row.get('ordinal_basis') != 'sqlite_primary_key_order:' + primary_key
            or row.get('derivation_id') != selection['derivation_id']
            or row.get('original_path') != selection['source_path']
            or row.get('artifact_sha256') != selection['source_sha256']
            or row.get('adapter_code_sha256') != selection['adapter_code_sha256']
            or key != [fields.get('entity_key') if table == 'entities' else fields.get('id')]):
        raise ResearchServingError('PROVIDER_DISCOVERY_LINEAGE_MISMATCH')
    return record


class ProviderCandidateRepository(ProviderIdentityRepository):
    """Name tokens retrieve candidates in source order, never a match score."""

    def search(self, name_text, *, limit=MAX_PAGE, after_ordinal=0,
               expected_snapshot_id=None, year=2026):
        tokens, omitted = _query(name_text)
        if (type(year) is not int or year != 2026 or type(limit) is not int
                or not 1 <= limit <= MAX_PAGE or type(after_ordinal) is not int
                or not 0 <= after_ordinal <= TABLE_ROWS['entities']
                or expected_snapshot_id is not None and not isinstance(expected_snapshot_id, str)
                or after_ordinal and expected_snapshot_id is None):
            raise ResearchServingError('INVALID_LITERAL_PROVIDER_REQUEST')
        selections = self.binding.selections
        if (set(selections) != set(TABLE_ROWS) or any(selection.get('layer_id') != 'L08'
                or selection.get('source_table') != table for table, selection in selections.items())):
            raise ResearchServingError('PROVIDER_IDENTITY_SELECTION_REQUIRED')
        selection = selections['entities']
        with self._read() as (connection, _base_access):
            access = connection.execute(ACCESS, (list(SOURCE_ACCESS_IDS),)).fetchall()
            result = self._envelope(json_safe(access))
            snapshot = result['binding']['snapshot_id']
            if expected_snapshot_id is not None and expected_snapshot_id != snapshot:
                raise ResearchServingError('STALE_RESEARCH_SNAPSHOT')
            controls = connection.execute(CONTROLS, ([s['derivation_id'] for s in selections.values()],)).fetchall()
            observed = {(row['derivation_id'], row['entity_type']): row['rows'] for row in controls}
            expected = {(s['derivation_id'], 'provider_' + table): TABLE_ROWS[table]
                        for table, s in selections.items()}
            if observed != expected:
                raise ResearchServingError('PROVIDER_IDENTITY_POPULATION_MISMATCH')
            rows = connection.execute(SEARCH, (selection['derivation_id'], after_ordinal,
                [_pattern(token) for token in tokens], limit + 1)).fetchall()
            ordinals = [row.get('source_row_ordinal') for row in rows]
            if (len(rows) > limit + 1 or any(type(value) is not int
                    or not after_ordinal < value <= TABLE_ROWS['entities'] for value in ordinals)
                    or ordinals != sorted(set(ordinals))):
                raise ResearchServingError('PROVIDER_DISCOVERY_QUERY_MISMATCH')
            entities = [_selected_record(row, selection, 'entities') for row in rows[:limit]]
            for entity in entities:
                fields = entity['source_native_fields']
                if (not isinstance(fields.get('entity_key'), str)
                        or not ENTITY_KEY.fullmatch(fields['entity_key'])
                        or not _matches(fields.get('name'), tokens)):
                    raise ResearchServingError('PROVIDER_DISCOVERY_QUERY_MISMATCH')
            ids = sorted({entity['source_native_fields']['observation_id'] for entity in entities
                          if isinstance(entity['source_native_fields'].get('observation_id'), str)
                          and entity['source_native_fields']['observation_id']})
            locator_rows = connection.execute(LOCATORS, (selections['observations']['derivation_id'], ids)).fetchall() if ids else []
            if (len(locator_rows) > len(ids) or len({row.get('observation_id') for row in locator_rows}) != len(locator_rows)
                    or any(row.get('observation_id') not in ids for row in locator_rows)):
                raise ResearchServingError('PROVIDER_SOURCE_LOCATOR_MISMATCH')
            locators = [_locator(row, selections['observations'], [entity for entity in entities
                if entity['source_native_fields'].get('observation_id') == row['observation_id']]) for row in locator_rows]
            by_id = {row['observation_id']: row for row in locators}
            source_ids = sorted({row['source_id'] for row in locators if isinstance(row.get('source_id'), str) and row['source_id']})
            source_rows = connection.execute(SOURCES, (selections['sources']['derivation_id'], source_ids)).fetchall() if source_ids else []
            if (len(source_rows) > len(source_ids)
                    or len({row['fields'].get('id') for row in source_rows}) != len(source_rows)
                    or any(row['fields'].get('id') not in source_ids for row in source_rows)):
                raise ResearchServingError('PROVIDER_SOURCE_LOCATOR_MISMATCH')
            sources = [_selected_record(row, selections['sources'], 'sources') for row in source_rows]
            found_sources = {source['source_native_fields']['id'] for source in sources}
            candidates = []
            for entity in entities:
                fields = entity['source_native_fields']
                locator = by_id.get(fields.get('observation_id'))
                complete = bool(locator and locator.get('pointer') and locator.get('source_id') in found_sources)
                candidate = copy.deepcopy(entity)
                candidate.update(candidate_id='L08:entity:' + digest([entity['record_ref']]),
                    kind='provider_entity',entity_key=fields['entity_key'],label=_label(fields['name']),
                    selector={'entity_key':fields['entity_key']},lookup_snapshot_id=snapshot,
                    source_observation_locator=copy.deepcopy(locator),
                    identity_detail_state='source_entity_observed' if complete else 'source_lineage_partial',
                    requires_explicit_entity_and_site_confirmation=True,
                    literal_occurrence_is_not_identity=True,automatic_profile_binding=False,
                    reported_city_resolution='not_evaluated_requires_explicit_role_site_lookup',
                    current_practice_status='dated_source_not_reverified')
                candidates.append(candidate)
            registered = sorted(row['source_id'] for row in access)
            more = len(rows) > limit
            partial = any(candidate['identity_detail_state'] == 'source_lineage_partial' for candidate in candidates)
            result.update(contract_id=VERSION,operator_only=True,
                lookup_kind='literal_provider_name_candidate_discovery',
                scope={'year':2026,'category':'retained_provider_directory_entities'},
                requested={'name_text':name_text.strip(),'literal_tokens':tokens,
                    'leading_title_omitted_for_discovery_only':omitted,'year':year,'limit':limit,'after_ordinal':after_ordinal},
                candidates=candidates,candidate_count=len(candidates),sources=sources,
                discovery_state='literal_candidates_require_confirmation' if candidates else 'not_observed_in_selected_literal_query',
                page={'has_more':more,'next_after_ordinal':ordinals[limit-1] if more else None,
                    'ordering':'source_row_ordinal','snapshot_id':snapshot},
                partial={'is_partial':bool(more or partial),'source_lineage_partial':partial,
                    'reported_city_not_filtered':True,'complete_provider_roster':False},
                source_access_registration={'state':'registered' if registered else 'unregistered',
                    'requested_source_ids':list(SOURCE_ACCESS_IDS),'registered_source_ids':registered,
                    'absence_is_permission':False,'output_authority':'held'},
                automatic_profile_binding=False,consumer_release=False,
                personal_coverage_result=False,network_status='not_evaluated',
                limitations=[
                    'Operator-only literal discovery over the retained composite directory, not a current or complete provider roster.',
                    'Each supplied token must occur in name-bearing strings of one source name variant; no fuzzy scores, reordered source results or inferred person/site equivalence.',
                    'A leading Dr/Doctor title may be omitted only for discovery and is explicitly disclosed; the reported name is not changed.',
                    'Reported city remains disambiguation context until exact actor/role/location lookup; missing actor-level cities never silently exclude a name.',
                    'Organization, practitioner, role and location identities remain distinct; NPI/name/address similarity does not merge them.',
                    'Source dates and active flags do not establish current practice, network participation, appointments or eligibility.',
                    'No-result and partial-source states remain unknown; all consumer-purpose authority stays held.',
                ])
            safe = json_safe(result)
            if len(json.dumps(safe,ensure_ascii=False).encode()) > MAX_RESPONSE_BYTES:
                raise ResearchServingError('PROVIDER_DISCOVERY_RESPONSE_LIMIT')
            return safe


def provider_candidate_repository_from_env(*, repository_root, dsn=None, timeout_ms=5000):
    base = repository_from_env(repository_root=repository_root,dsn=dsn,timeout_ms=timeout_ms)
    binding = load_local_binding(repository_root,selection=SELECTION)
    return ProviderCandidateRepository(base._connection_factory,binding,timeout_ms=timeout_ms)
