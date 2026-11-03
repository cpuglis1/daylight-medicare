"""Restricted/other coverage research: base paths and additive claims stay distinct."""
import json
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

from .common import DomainProjection, sqlite_records

BASE = 'docs/data/l14-other-coverage-2026-10-29'
COMPONENTS = (('build-r1', 'selected_base'), ('gap-resolution-r2/build-r2', 'selected_additive_component'))
ENTITY_TYPES = {
    'paths': 'other_coverage_path',
    'rules': 'other_coverage_rule',
    'claims': 'other_coverage_additive_claim',
    'records': 'other_coverage_source_record',
    'evidence': 'other_coverage_source_clause',
    'gaps': 'other_coverage_research_gap',
    'reconciliations': 'other_coverage_reconciliation',
    'negative-search': 'other_coverage_negative_search_field',
    'restricted-documents': 'other_coverage_restricted_document',
    'Fenyx-documents': 'other_coverage_fenyx_document',
    'Fenyx-comparisons': 'other_coverage_fenyx_comparison',
    'HCPP-profiles': 'other_coverage_hcpp_profile',
    'state-observations': 'other_coverage_state_observation',
    'state-observation': 'other_coverage_state_observation_field',
    'source-registry': 'other_coverage_source_registry_entry',
    'new-source-registry': 'other_coverage_additive_source_registry_entry',
    'source-accounting': 'other_coverage_source_accounting',
    'source-anomalies': 'other_coverage_source_anomaly_field',
    'federal-register-amendments': 'other_coverage_regulatory_amendment',
    'federal-register-searches': 'other_coverage_regulatory_search',
    'public-PDF-inventories': 'other_coverage_document_inventory',
}


def iter_records(root):
    root = Path(root).resolve()
    for component, _role in COMPONENTS:
        yield from sqlite_records(root, root / BASE / component / 'reference.sqlite', 'L14')


def project_record(row):
    raw = row.raw
    payload = json.loads(raw['payload'], parse_float=Decimal)
    component = row.source_path[len(BASE) + 1:].rsplit('/', 1)[0]
    role = dict(COMPONENTS)[component]
    fields = dict(payload) if isinstance(payload, Mapping) else {'native_value': payload}
    fields['adapter_context'] = {'reference_year': 2026, 'component': component,
                                 'component_role': role, 'native_row_id': raw['id'],
                                 'rule_namespace': 'L14.other_coverage',
                                 'personal_applicability_determined': False,
                                 'contact_or_observation_is_live_availability': False}
    conditions = {key: payload[key] for key in (
        'conditions', 'source_conditions', 'all_source_conditions', 'source_clause_ids',
        'required_case_evidence', 'jurisdiction', 'temporal_scope', 'source_edition',
        'effective_on', 'publication_date', 'dates', 'current_opening', 'personal_eligibility',
        'employer_group_only', 'unrestricted_public_enrollment', 'PDP_interaction',
        'unified_plan_join', 'unified_design_join', 'unified_plan_deductible',
        'unified_plan_deposit', 'live_capacity', 'reported_open_slots', 'interpretation')
        if isinstance(payload, Mapping) and key in payload}
    state = payload.get('status', 'source_observed') if isinstance(payload, Mapping) else 'source_native_context_field'
    return DomainProjection(row, ENTITY_TYPES.get(row.source_table, 'other_coverage_context_field'),
                           'L14:' + component + ':' + row.source_table + ':' + raw['id'],
                           fields, value_state=state if isinstance(state, str) else 'source_observed',
                           conditions=conditions)


def iter_projections(root):
    for row in iter_records(root):
        yield project_record(row)
