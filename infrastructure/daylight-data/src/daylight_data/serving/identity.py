"""Operator-only exact RxCUI candidates from the retained L05 dictionary.

No name search, clinical substitution, NDC conversion, offering/coverage join or
customer binding. A dictionary ID match remains an inspectable source candidate;
it establishes no current terminology status, participation, coverage or release.
"""
import copy
import json
import re

from .binding import ResearchServingError, digest, load_local_binding
from .repository import ResearchPlanRepository, STATE_KEYS, json_safe, repository_from_env


VERSION = 'l05-exact-rxcui-research-r1'
SELECTION = {'drug_identity': ('L05', 'drug_identities', '/build-r3/')}
EXPECTED_DICTIONARY_ROWS = 4547
MAX_IDS = 20
MAX_RECORDS = 100
RXCUI = re.compile(r'[1-9][0-9]{0,9}\Z')
CONCEPT_TYPES = {'SCD', 'SBD', 'GPCK', 'BPCK'}
SOURCE_ACCESS_IDS = ('sealed-local:L05', 'L05')

CONTROLS = """SELECT count(*) AS rows,min(benefit_year) AS min_year,
 max(benefit_year) AS max_year,count(offering_id) AS offering_rows
 FROM dl_evidence.observation
 WHERE derivation_id=%s AND entity_type='drug_product' AND source_table='drug_identities'"""

# observation_pkey first bounds the read to this exact 4,547-row derivation and
# entity type. The JSON equality predicate does not claim a dedicated RxCUI
# index; source_record_pkey supplies the exact raw-parent lookup. No global scan.
EXACT_RXCUI = """WITH matched AS MATERIALIZED (
 SELECT * FROM dl_evidence.observation
 WHERE derivation_id=%s AND entity_type='drug_product' AND source_table='drug_identities'
 AND fields->>'rxcui'=ANY(%s) ORDER BY source_row_ordinal LIMIT 101)
 SELECT o.*,r.raw_payload,r.raw_sha256,r.record_id,r.source_row_key,r.ordinal_basis,
 d.snapshot_id,d.adapter_code_sha256,s.original_path,s.artifact_sha256,
 s.source_use_state AS snapshot_source_use_state
 FROM matched o
 JOIN dl_evidence.source_record r USING(derivation_id,source_table,source_row_ordinal)
 JOIN dl_control.derivation d USING(derivation_id)
 JOIN dl_control.source_snapshot s USING(snapshot_id)
 ORDER BY o.source_row_ordinal"""

ACCESS = """SELECT source_id,state,reason,updated_at FROM dl_control.source_access_state
 WHERE source_id=ANY(%s) ORDER BY source_id"""


def _candidate(row):
    fields, raw = row.get('fields'), row.get('raw_payload')
    if not isinstance(fields, dict) or not isinstance(raw, dict):
        raise ResearchServingError('DRUG_IDENTITY_LINEAGE_MISMATCH')
    payload = raw.get('payload')
    try:
        payload = json.loads(payload) if isinstance(payload, str) else payload
    except (TypeError, ValueError):
        raise ResearchServingError('DRUG_IDENTITY_LINEAGE_MISMATCH') from None
    cui = fields.get('rxcui')
    if (not isinstance(payload, dict) or not isinstance(cui, str) or not RXCUI.fullmatch(cui)
            or raw.get('rxcui') != cui or payload.get('rxcui') != cui
            or row.get('raw_sha256') != digest(raw)
            or row.get('record_id') != digest([row.get('snapshot_id'), row.get('source_table'), row.get('source_row_ordinal')])
            or row.get('entity_id') != 'L05:' + row.get('record_id', '')
            or row.get('benefit_year') != 2026 or row.get('offering_id') is not None
            or fields.get('concept_type') not in CONCEPT_TYPES
            or fields.get('concept_type') != payload.get('type')
            or fields.get('coverage_inferred') is not False
            or any(fields.get(key) != payload.get(native) for key, native in
                   (('drug_name', 'name'), ('dose_form', 'dose_form'),
                    ('ingredient_strength_description', 'ingredient_strength_description'),
                    ('related_brand', 'related_brand')))):
        raise ResearchServingError('DRUG_IDENTITY_LINEAGE_MISMATCH')
    missing = [key for key in ('drug_name', 'dose_form', 'ingredient_strength_description')
               if not isinstance(fields.get(key), str) or not fields[key].strip()]
    pack = fields['concept_type'] in {'GPCK', 'BPCK'}
    reasons = (['PACK_CONCEPT_NOT_SINGLE_PRODUCT'] if pack else [])
    if missing:
        reasons.append('SOURCE_IDENTITY_DETAILS_PARTIAL')
    return {
        'candidate_id': row['entity_id'], 'namespace': 'retained_L05_RxCUI_dictionary',
        'identity': {key: copy.deepcopy(fields.get(key)) for key in
                     ('rxcui', 'drug_name', 'dose_form', 'ingredient_strength_description',
                      'related_brand', 'concept_type')},
        'identity_grain': 'pack_concept' if pack else 'drug_product_concept',
        'identity_detail_state': 'partial' if missing else 'source_details_present',
        'missing_identity_details': missing, 'reason_codes': reasons,
        'source_locator': copy.deepcopy(payload.get('source')),
        'source_history': copy.deepcopy(payload.get('history')),
        'source_native_fields': copy.deepcopy(fields), 'raw_source_payload': copy.deepcopy(raw),
        'conditions': copy.deepcopy(row['conditions']),
        'states': {key: row[key] for key in STATE_KEYS},
        'snapshot_source_use_state': row.get('snapshot_source_use_state'),
        'lineage': {key: row.get(key) for key in
                    ('derivation_id', 'snapshot_id', 'artifact_sha256', 'original_path',
                     'source_table', 'source_row_ordinal', 'source_row_key', 'ordinal_basis',
                     'raw_sha256', 'record_id', 'adapter_code_sha256')},
        'offering_grain': None, 'coverage_inferred': False,
        'automatic_profile_binding': False, 'requires_identity_confirmation': True,
        'current_terminology_status_verified': False, 'output_authority': 'held',
    }


class DrugIdentityRepository(ResearchPlanRepository):
    """Exact source candidates behind the existing ownership/read-only guard."""

    def lookup_rxcuis(self, rxcuis, *, year=2026, expected_snapshot_id=None):
        if (type(year) is not int or year != 2026 or not isinstance(rxcuis, (tuple, list))
                or not 1 <= len(rxcuis) <= MAX_IDS
                or any(not isinstance(value, str) or not RXCUI.fullmatch(value) for value in rxcuis)
                or len(set(rxcuis)) != len(rxcuis)
                or expected_snapshot_id is not None and not isinstance(expected_snapshot_id, str)):
            raise ResearchServingError('INVALID_EXACT_RXCUI_REQUEST')
        selection = self.binding.selections.get('drug_identity')
        if not selection or selection['layer_id'] != 'L05' or selection['source_table'] != 'drug_identities':
            raise ResearchServingError('DRUG_IDENTITY_SELECTION_REQUIRED')
        with self._read() as (connection, _base_access):
            own_access = connection.execute(ACCESS, (list(SOURCE_ACCESS_IDS),)).fetchall()
            by_source = {row['source_id']: json_safe(row) for row in own_access}
            result = self._envelope([by_source[key] for key in sorted(by_source)])
            if expected_snapshot_id is not None and expected_snapshot_id != result['binding']['snapshot_id']:
                raise ResearchServingError('STALE_RESEARCH_SNAPSHOT')
            controls = connection.execute(CONTROLS, (selection['derivation_id'],)).fetchone()
            if (controls['rows'] != EXPECTED_DICTIONARY_ROWS or controls['min_year'] != 2026
                    or controls['max_year'] != 2026 or controls['offering_rows'] != 0):
                raise ResearchServingError('DRUG_IDENTITY_POPULATION_MISMATCH')
            records = connection.execute(EXACT_RXCUI, (selection['derivation_id'], list(rxcuis))).fetchall()
            if len(records) > MAX_RECORDS:
                raise ResearchServingError('DRUG_IDENTITY_LOOKUP_LIMIT')
            candidates = [_candidate(row) for row in records]
            if any(candidate['identity']['rxcui'] not in rxcuis for candidate in candidates):
                raise ResearchServingError('DRUG_IDENTITY_QUERY_MISMATCH')
            matches = []
            for cui in rxcuis:
                related = [candidate for candidate in candidates if candidate['identity']['rxcui'] == cui]
                state = ('exact_id_candidate' if len(related) == 1 else
                         'ambiguous_source_identity' if related else 'not_observed_in_selected_dictionary')
                matches.append({'rxcui': cui, 'state': state,
                                'candidate_refs': [candidate['candidate_id'] for candidate in related],
                                'automatic_profile_binding': False,
                                'reason_codes': (['SOURCE_IDENTITY_AMBIGUOUS'] if len(related) > 1 else
                                                 ['SELECTED_DICTIONARY_ID_NOT_OBSERVED'] if not related else [])})
            registered = {row['source_id'] for row in own_access}
            result.update(
                contract_id=VERSION, lookup_kind='exact_rxcui_dictionary', operator_only=True,
                scope={'year': year, 'category': 'retained_drug_identity_dictionary',
                       'geography': 'no_personal_geography_or_offering_scope'},
                requested={'year': year, 'rxcuis': list(rxcuis)},
                dictionary_scope={'benefit_year': 2026, 'source_table': 'drug_identities',
                                  'selected_rows': EXPECTED_DICTIONARY_ROWS,
                                  'offering_grain': None, 'formulary_grain': None,
                                  'terminology_currentness': 'dated_retained_source_not_reverified'},
                matches=matches, candidates=candidates,
                source_access_registration={'state': 'registered' if registered else 'unregistered',
                    'requested_source_ids': list(SOURCE_ACCESS_IDS), 'registered_source_ids': sorted(registered),
                    'absence_is_permission': False, 'output_authority': 'held'},
                automatic_profile_binding=False, personal_coverage_result=False,
                consumer_release=False, clinical_substitution=False,
                gaps_preserved=['G05', 'G08', 'G09', 'G11', 'G14'],
            )
            result['limitations'] = [
                'Internal identity research only; no accepted consumer purpose or current terminology guarantee.',
                'Exact RxCUI dictionary candidates need item-specific confirmation; no customer item is bound here.',
                'No free-text name search, brand substitution, pack decomposition, dose inference or NDC conversion.',
                'A missing dictionary ID is unknown within this selection; it is not absence of coverage or a negative clinical finding.',
                'Strength/form/history retain missing and dated source states; names are not parsed to fill them.',
                'The dictionary has no offering/formulary membership, quantity, pharmacy, price or personal approval grain.',
            ]
            return json_safe(result)


def identity_repository_from_env(*, repository_root, dsn=None, timeout_ms=5000):
    """Reuse physical DB identity and immutable source/job checks; no discovery."""
    base = repository_from_env(repository_root=repository_root, dsn=dsn, timeout_ms=timeout_ms)
    binding = load_local_binding(repository_root, selection=SELECTION)
    return DrugIdentityRepository(base._connection_factory, binding, timeout_ms=timeout_ms)
