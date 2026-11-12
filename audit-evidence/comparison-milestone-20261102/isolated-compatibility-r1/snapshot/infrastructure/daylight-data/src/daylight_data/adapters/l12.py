"""Help-with-costs research: current and parent standards are separate source rows."""
import json
import re
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

from .common import DomainProjection, sqlite_records

BASE = 'docs/data/l12-help-with-costs-2026-10-28/build-r2'
REFERENCE_ID = 'L12-PUBLISHED-FL-2026-research-r2'
ENTITY_TYPES = {
    'rules.json': 'assistance_rule',
    'programs.json': 'assistance_program_reference',
    'automatic-routes.json': 'assistance_automatic_route',
    'application-referrals.json': 'assistance_application_referral',
    'source-clause-ledger.json': 'assistance_source_clause',
    'gaps.json': 'assistance_representation_gap',
    'parent-gaps.json': 'assistance_parent_gap',
    'review-questions-r2.json': 'assistance_review_question',
    'rule-changes-r2.json': 'assistance_rule_change',
    'work-family-coverage.json': 'assistance_work_family_context',
    'spousal-transitions-r2.json': 'assistance_spousal_transition',
    'medicaid-coverage-accounting.json': 'assistance_medicaid_coverage_accounting',
}
STANDARD_DATASETS = frozenset(('LIS-cost-sharing-2026.json', 'LIS-resources-2026.json',
    'federal-FPL-2026.json', 'federal-MSP-2026.json', 'florida-medicaid-standards.json',
    'florida-msp-lis-tables.json', 'historical-April-medicaid-standards.json',
    'historical-January-medicaid-standards.json'))


def _standard_numeric_observations(payload):
    """Type only explicit standard cells; never derive an income test or award."""
    observations = []

    def retain(pointer, value, unit, basis=None, state=None):
        if unit and isinstance(value, (str, int, Decimal)) and not isinstance(value, bool) and re.fullmatch(r'[+-]?\d+(?:\.\d+)?', str(value)):
            observations.append({'native_payload_pointer': pointer, 'source_value': value,
                                 'value_decimal': Decimal(str(value)), 'source_unit': unit,
                                 'source_basis': basis, 'source_value_state': state,
                                 'encoding': 'exact_decimal_no_unit_or_period_conversion'})

    unit, basis = payload.get('unit'), payload.get('basis')
    for key in ('value', 'individual', 'couple', 'base_limit', 'display_with_full_burial_allowance',
                'maximum_burial_exclusion', 'annual_out_of_pocket_threshold',
                'brand_copayment_maximum', 'covered_drug_cost_share_above_threshold',
                'deductible_maximum', 'generic_copayment_maximum'):
        if key in payload:
            retain('/' + key, payload[key], unit, basis, payload.get('source_status'))
    for key, value in payload.get('values', {}).items():
        retain('/values/' + key, value, unit, basis, payload.get('source_status'))
    for key, cell in payload.get('fields', {}).items():
        if isinstance(cell, Mapping):
            retain('/fields/' + key + '/value', cell.get('value'), cell.get('unit'),
                   cell.get('basis'), cell.get('source_status'))
    return observations


def iter_records(root):
    root = Path(root).resolve()
    yield from sqlite_records(root, root / BASE / 'l12-reference.sqlite', 'L12')


def project_record(row):
    raw = row.raw
    payload = json.loads(raw['payload'], parse_float=Decimal)
    dataset = raw.get('dataset', raw.get('name'))
    local_id = raw.get('id', raw.get('name'))
    fields = dict(payload) if isinstance(payload, Mapping) else {'native_value': payload}
    if row.source_table in {'datasets', 'parent_datasets'}:
        entity_type = 'assistance_dataset_envelope'
    elif dataset in STANDARD_DATASETS:
        entity_type = 'assistance_financial_standard'
    elif 'comparison' in dataset or 'reconciliation' in dataset or 'example' in dataset:
        entity_type = 'assistance_source_comparison'
    else:
        entity_type = ENTITY_TYPES.get(dataset, 'assistance_research_context')
    fields['adapter_context'] = {'reference_id': REFERENCE_ID, 'reference_year': 2026,
                                 'native_dataset': dataset, 'native_row_id': local_id,
                                 'lineage_role': 'retained_parent' if row.source_table.startswith('parent_') else 'selected_current',
                                 'rule_namespace': 'L12.assistance',
                                 'personal_applicability_determined': False}
    if row.source_table in {'records', 'parent_records'} and dataset in STANDARD_DATASETS and isinstance(payload, Mapping):
        fields['adapter_context']['standard_numeric_observations'] = _standard_numeric_observations(payload)
    conditions = {key: payload[key] for key in (
        'conditions', 'source_conditions', 'required_conditions', 'source_clause_ids',
        'jurisdiction', 'reference_year', 'effective_start', 'effective_end_exclusive',
        'period', 'period_basis', 'family_size', 'family_size_source', 'row_type',
        'interpretation_status', 'required_case_evidence', 'basis', 'unit')
        if isinstance(payload, Mapping) and key in payload}
    state = payload.get('source_status', payload.get('status', 'published_observation')) if isinstance(payload, Mapping) else 'source_observed'
    return DomainProjection(row, entity_type,
                           'L12:build-r2:' + row.source_table + ':' + dataset + ':' + str(local_id),
                           fields, value_state=state if isinstance(state, str) else 'source_observed',
                           conditions=conditions)


def iter_projections(root):
    for row in iter_records(root):
        yield project_record(row)
