"""Enrollment research. RC rule IDs belong to L13, never the profile namespace."""
import json
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

from .common import DomainProjection, sqlite_records

BASE = 'docs/data/l13-enrollment-2026-10-28/build-r1'
REFERENCE_ID = 'L13-PUBLISHED-COLLIER-2026-research-r1'
ENTITY_TYPES = {
    'rules.json': 'enrollment_rule',
    'clocks.json': 'enrollment_clock_reference',
    'annual-windows.json': 'enrollment_annual_window',
    'regulatory-SEP-inventory.json': 'enrollment_regulatory_sep',
    'AB-exceptional-SEP-inventory.json': 'enrollment_ab_exceptional_sep',
    'CMS-SEP-comparisons.json': 'enrollment_cms_sep_comparison',
    'source-clause-ledger.json': 'enrollment_source_clause',
    'quantities.json': 'enrollment_quantity_reference',
    'gaps.json': 'enrollment_research_gap',
    'layer-boundaries.json': 'enrollment_layer_boundary',
    'reconciliations.json': 'enrollment_reconciliation',
    'additional-regulatory-context.json': 'enrollment_regulatory_context',
}


def iter_records(root):
    root = Path(root).resolve()
    yield from sqlite_records(root, root / BASE / 'l13-reference.sqlite', 'L13')


def project_record(row):
    raw = row.raw
    payload = json.loads(raw['payload'], parse_float=Decimal)
    dataset = raw.get('dataset', raw.get('name'))
    local_id = raw.get('id', raw.get('name'))
    fields = dict(payload) if isinstance(payload, Mapping) else {'native_value': payload}
    entity_type = 'enrollment_dataset_envelope' if row.source_table == 'datasets' else ENTITY_TYPES.get(dataset, 'enrollment_research_context')
    fields['adapter_context'] = {'reference_id': REFERENCE_ID, 'reference_year': 2026,
                                 'native_dataset': dataset, 'native_row_id': local_id,
                                 'rule_namespace': 'L13.enrollment',
                                 'profile_question_binding_inferred': False,
                                 'personal_applicability_determined': False}
    conditions = {key: payload[key] for key in (
        'conditions', 'source_conditions', 'required_conditions', 'parent_conditions',
        'source_native_conditions', 'source_clause_ids', 'required_case_evidence',
        'jurisdiction', 'applicability', 'temporal_status', 'prior_CMS_approval',
        'timing_sentences', 'temporal_scope', 'effective_start', 'effective_end_exclusive')
        if isinstance(payload, Mapping) and key in payload}
    return DomainProjection(row, entity_type,
                           'L13:build-r1:' + row.source_table + ':' + dataset + ':' + str(local_id),
                           fields, conditions=conditions)


def iter_projections(root):
    for row in iter_records(root):
        yield project_record(row)
