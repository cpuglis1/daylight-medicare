"""Literal dictionary discovery for operator-reviewed identity candidates only.

Text occurrence is not clinical equivalence, strength equivalence, coverage or
identity confirmation. Source names, packs, missing details and dates survive.
No synonyms, fuzzy scores, brand expansion, unit conversion or customer binding.
"""
import json
import re

from .binding import ResearchServingError, digest, load_local_binding
from .identity import (ACCESS, SELECTION, EXPECTED_DICTIONARY_ROWS, DrugIdentityRepository,
                       _candidate)
from .repository import json_safe, repository_from_env


VERSION = 'l05-literal-drug-candidates-research-r1'
MAX_TEXT_CHARS = 160
MAX_PAGE = 20
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
CONTROL_CHAR = re.compile(r'[\x00-\x1f\x7f-\x9f]')
SOURCE_ACCESS_IDS = ('sealed-local:L05', 'L05')
EXPECTED_CONTROLS = {'rows': EXPECTED_DICTIONARY_ROWS, 'min_year': 2026, 'max_year': 2026,
                     'offering_rows': 0, 'missing_name': 0, 'missing_strength': 28,
                     'missing_form': 28, 'pack_rows': 285}

CONTROLS = """SELECT count(*) AS rows,min(benefit_year) AS min_year,
 max(benefit_year) AS max_year,count(offering_id) AS offering_rows,
 count(*) FILTER(WHERE NULLIF(btrim(fields->>'drug_name'),'') IS NULL) AS missing_name,
 count(*) FILTER(WHERE NULLIF(btrim(fields->>'ingredient_strength_description'),'') IS NULL) AS missing_strength,
 count(*) FILTER(WHERE NULLIF(btrim(fields->>'dose_form'),'') IS NULL) AS missing_form,
 count(*) FILTER(WHERE fields->>'concept_type' IN ('GPCK','BPCK')) AS pack_rows
 FROM dl_evidence.observation WHERE derivation_id=%s AND entity_type='drug_product'
 AND source_table='drug_identities'"""

# The existing source-lineage index bounds this to 4,547 records. Optional text
# filters retain name-matched records whose source strength/form is absent. The
# fixed ! escape makes percent/underscore/exclamation literal user characters.
SEARCH = """WITH matched AS MATERIALIZED (
 SELECT * FROM dl_evidence.observation WHERE derivation_id=%s
 AND entity_type='drug_product' AND source_table='drug_identities'
 AND source_row_ordinal>%s AND fields->>'drug_name' ILIKE %s ESCAPE '!'
 AND (%s::text IS NULL OR NULLIF(btrim(fields->>'ingredient_strength_description'),'') IS NULL
      OR fields->>'ingredient_strength_description' ILIKE %s ESCAPE '!')
 AND (%s::text IS NULL OR NULLIF(btrim(fields->>'dose_form'),'') IS NULL
      OR fields->>'dose_form' ILIKE %s ESCAPE '!')
 ORDER BY source_row_ordinal LIMIT %s)
 SELECT o.*,r.raw_payload,r.raw_sha256,r.record_id,r.source_row_key,r.ordinal_basis,
 d.snapshot_id,d.adapter_code_sha256,s.original_path,s.artifact_sha256,
 s.source_use_state AS snapshot_source_use_state,
 o.fields->>'drug_name' ILIKE %s ESCAPE '!' AS name_literal_observed,
 CASE WHEN NULLIF(btrim(o.fields->>'ingredient_strength_description'),'') IS NULL THEN NULL
      ELSE o.fields->>'ingredient_strength_description' ILIKE %s ESCAPE '!' END AS strength_literal_observed,
 CASE WHEN NULLIF(btrim(o.fields->>'dose_form'),'') IS NULL THEN NULL
      ELSE o.fields->>'dose_form' ILIKE %s ESCAPE '!' END AS form_literal_observed
 FROM matched o JOIN dl_evidence.source_record r USING(derivation_id,source_table,source_row_ordinal)
 JOIN dl_control.derivation d USING(derivation_id)
 JOIN dl_control.source_snapshot s USING(snapshot_id) ORDER BY o.source_row_ordinal"""


def _text(value, *, optional=False):
    if optional and value is None:
        return None
    if (not isinstance(value, str) or not value.strip() or len(value) > MAX_TEXT_CHARS
            or CONTROL_CHAR.search(value)):
        raise ResearchServingError('INVALID_LITERAL_DRUG_REQUEST')
    return value.strip()


def _pattern(text):
    if text is None:
        return None
    return '%' + text.replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%'


def _field_state(row, candidate, text, field, observed_key):
    if text is None:
        return 'not_requested'
    value = candidate['identity'][field]
    if not isinstance(value, str) or not value.strip():
        if row.get(observed_key) is not None:
            raise ResearchServingError('DRUG_CANDIDATE_QUERY_MISMATCH')
        return 'source_detail_unknown'
    if row.get(observed_key) is not True:
        raise ResearchServingError('DRUG_CANDIDATE_QUERY_MISMATCH')
    return 'literal_substring_observed'


class DrugCandidateRepository(DrugIdentityRepository):
    """Discover dated dictionary rows; exact RxCUI choice is a separate action."""

    def search(self, name_text, *, strength_text=None, form_text=None, limit=MAX_PAGE,
               after_ordinal=0, expected_snapshot_id=None, year=2026):
        name = _text(name_text)
        strength, form = _text(strength_text, optional=True), _text(form_text, optional=True)
        if (type(year) is not int or year != 2026 or type(limit) is not int or not 1 <= limit <= MAX_PAGE
                or type(after_ordinal) is not int or not 0 <= after_ordinal <= EXPECTED_DICTIONARY_ROWS
                or expected_snapshot_id is not None and not isinstance(expected_snapshot_id, str)
                or after_ordinal and expected_snapshot_id is None):
            raise ResearchServingError('INVALID_LITERAL_DRUG_REQUEST')
        selected = self.binding.selections
        if (set(selected) != {'drug_identity'} or selected['drug_identity'].get('layer_id') != 'L05'
                or selected['drug_identity'].get('source_table') != 'drug_identities'):
            raise ResearchServingError('DRUG_IDENTITY_SELECTION_REQUIRED')
        selection = selected['drug_identity']
        name_pattern, strength_pattern, form_pattern = map(_pattern, (name, strength, form))
        with self._read() as (connection, _base_access):
            access = connection.execute(ACCESS, (list(SOURCE_ACCESS_IDS),)).fetchall()
            result = self._envelope(json_safe(access))
            snapshot_id = result['binding']['snapshot_id']
            if expected_snapshot_id is not None and expected_snapshot_id != snapshot_id:
                raise ResearchServingError('STALE_RESEARCH_SNAPSHOT')
            controls = connection.execute(CONTROLS, (selection['derivation_id'],)).fetchone()
            if controls != EXPECTED_CONTROLS:
                raise ResearchServingError('DRUG_CANDIDATE_POPULATION_MISMATCH')
            rows = connection.execute(SEARCH, (selection['derivation_id'], after_ordinal, name_pattern,
                strength_pattern, strength_pattern, form_pattern, form_pattern, limit + 1,
                name_pattern, strength_pattern, form_pattern)).fetchall()
            if len(rows) > limit + 1:
                raise ResearchServingError('DRUG_CANDIDATE_LOOKUP_LIMIT')
            ordinals = [row.get('source_row_ordinal') for row in rows]
            if (any(type(ordinal) is not int or not after_ordinal < ordinal <= EXPECTED_DICTIONARY_ROWS
                    for ordinal in ordinals) or ordinals != sorted(set(ordinals))):
                raise ResearchServingError('DRUG_CANDIDATE_QUERY_MISMATCH')
            candidates = []
            for row in rows[:limit]:
                candidate = _candidate(row)
                if row.get('name_literal_observed') is not True:
                    raise ResearchServingError('DRUG_CANDIDATE_QUERY_MISMATCH')
                lexical = {'name': 'literal_substring_observed',
                    'strength': _field_state(row, candidate, strength, 'ingredient_strength_description',
                                             'strength_literal_observed'),
                    'form': _field_state(row, candidate, form, 'dose_form', 'form_literal_observed')}
                candidate.update(discovery_basis='case_insensitive_literal_substrings',
                    lexical_states=lexical, lookup_snapshot_id=snapshot_id,
                    lexical_occurrence_is_not_identity_or_dose_equivalence=True,
                    discovery_state='requires_explicit_identity_confirmation')
                candidates.append(candidate)
            more = len(rows) > limit
            partial_details = any(candidate['missing_identity_details'] for candidate in candidates)
            request = {'name_text': name, 'strength_text': strength, 'form_text': form,
                       'year': year, 'limit': limit, 'after_ordinal': after_ordinal}
            reasons = (['MORE_LITERAL_CANDIDATES_REMAIN'] if more else [])
            if partial_details:
                reasons.append('RETURNED_SOURCE_IDENTITY_DETAILS_PARTIAL')
            registered = sorted(row['source_id'] for row in access)
            result.update(contract_id=VERSION, lookup_kind='literal_dictionary_candidate_discovery',
                operator_only=True, scope={'year': year, 'category': 'retained_drug_identity_dictionary',
                    'geography': 'no_personal_geography_or_offering_scope'},
                requested=request, query_id=digest({'contract_id': VERSION, 'snapshot_id': snapshot_id,
                                                  'requested': request}),
                discovery_state=('literal_candidates_require_confirmation' if candidates
                                 else 'not_observed_in_selected_literal_query'),
                candidates=candidates, candidate_count=len(candidates),
                page={'has_more': more, 'next_after_ordinal': ordinals[limit - 1] if more else None,
                      'ordering': 'source_row_ordinal', 'snapshot_id': snapshot_id},
                partial={'is_partial': bool(more or partial_details), 'reason_codes': reasons,
                    'source_dictionary_missing_details': {'name': controls['missing_name'],
                        'strength': controls['missing_strength'], 'form': controls['missing_form']},
                    'source_dictionary_is_complete_terminology': False,
                    'optional_filters_retain_name_candidates_with_missing_source_details': True},
                dictionary_scope={'benefit_year': 2026, 'source_table': 'drug_identities',
                    'selected_rows': EXPECTED_DICTIONARY_ROWS, 'pack_rows': controls['pack_rows'],
                    'offering_grain': None, 'formulary_grain': None,
                    'terminology_currentness': 'dated_retained_source_not_reverified'},
                source_access_registration={'state': 'registered' if registered else 'unregistered',
                    'requested_source_ids': list(SOURCE_ACCESS_IDS), 'registered_source_ids': registered,
                    'absence_is_permission': False, 'output_authority': 'held'},
                automatic_profile_binding=False, consumer_release=False, personal_coverage_result=False,
                clinical_substitution=False, clinical_or_dose_equivalence=False,
                gaps_preserved=['G05', 'G08', 'G09', 'G11', 'G14'])
            result['limitations'] = [
                'Operator-only discovery over the retained 4,547-row dictionary, not a complete or current terminology service.',
                'Case-insensitive literal substrings retrieve candidates; one result or a strength-text occurrence is not identity or dose equivalence.',
                'Only outer query whitespace is removed; no typo correction, synonym/brand expansion, ingredient inference or unit conversion.',
                'Source strength/form omissions remain unknown even when the name contains apparent details; packs are not decomposed.',
                'Optional strength/form filters retain name candidates whose corresponding source attribute is missing, explicitly unresolved.',
                'A missing literal result is unknown within this selection; it is not absence of coverage, a clinical finding or a suggested substitute.',
                'Exact RxCUI selection and item/report-specific confirmation are separate actions; no customer item is bound here.',
                'The dictionary has no offering/formulary membership, quantity, pharmacy, price or personal approval grain.',
                'Source access, evidence/method acceptance and consumer-purpose release remain held independently of discovery.',
            ]
            safe = json_safe(result)
            if len(json.dumps(safe, ensure_ascii=False).encode()) > MAX_RESPONSE_BYTES:
                raise ResearchServingError('DRUG_CANDIDATE_RESPONSE_LIMIT')
            return safe


def candidate_repository_from_env(*, repository_root, dsn=None, timeout_ms=5000):
    """Reuse the immutable physical-target, source, job and reader-role checks."""
    base = repository_from_env(repository_root=repository_root, dsn=dsn, timeout_ms=timeout_ms)
    binding = load_local_binding(repository_root, selection=SELECTION)
    return DrugCandidateRepository(base._connection_factory, binding, timeout_ms=timeout_ms)
