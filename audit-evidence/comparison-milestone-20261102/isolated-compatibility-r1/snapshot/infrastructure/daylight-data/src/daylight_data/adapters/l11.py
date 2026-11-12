"""Selected Florida Medigap rights research, retaining rule exceptions and clocks."""
import json
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

from .common import DomainProjection, load_json, make_source, sha256_file, sqlite_records

BASE = 'docs/data/l11-medigap-rights-2026-10-28/build-r2'
REFERENCE_ID = 'L11-PUBLISHED-FL-2026-research-r2'
# These substantive object sidecars are not represented in the SQLite array table.
OBJECT_SIDECARS = ('before-after.json', 'parent-reference.json', 'review-coverage.json',
                   'source-visual-QA.json', 'summary.json', 'temporal-reconciliation.json')
ENTITY_TYPES = {
    'rules.json': 'medigap_rights_rule',
    'clocks.json': 'medigap_clock_reference',
    'exhibit-24-crosswalk.json': 'medigap_exhibit_crosswalk',
    'sep-crosswalk.json': 'medigap_sep_crosswalk',
    'source-clause-ledger.json': 'medigap_source_clause',
    'creditable-category-comparisons.json': 'medigap_creditable_comparison',
    'quantity-comparisons.json': 'medigap_quantity_comparison',
    'reconciliations-r2.json': 'medigap_reconciliation',
    'review-questions.json': 'medigap_review_question',
    'issue-dispositions.json': 'medigap_issue_disposition',
    'synthetic-predicate-patterns.json': 'medigap_synthetic_predicate_pattern',
}


def iter_records(root):
    root = Path(root).resolve()
    yield from sqlite_records(root, root / BASE / 'l11-reference.sqlite', 'L11')
    for filename, table in (('sources.json', 'source_registry'), ('policy-choices.json', 'policy_choices')):
        path = root / BASE / filename
        document = load_json(path)
        if not isinstance(document, dict):
            raise ValueError(f'Expected named L11 sidecar values: {filename}')
        source_hash = sha256_file(path)
        for ordinal, (key, value) in enumerate(document.items(), 1):
            yield make_source(root, path, 'L11', table, ordinal, key,
                              {'native_key': key, 'native_value': value},
                              'json_object_member_position_1_based', source_hash)
    for filename in OBJECT_SIDECARS:
        path = root / BASE / filename
        document = load_json(path)
        if not isinstance(document, dict):
            raise ValueError(f'Expected L11 context object: {filename}')
        yield make_source(root, path, 'L11', filename, 1, filename, document,
                          'complete_json_document', sha256_file(path))


def project_record(row):
    raw = row.raw
    if row.source_table == 'records':
        dataset, local_id = raw['dataset'], raw['id']
        payload = json.loads(raw['payload'], parse_float=Decimal)
        entity_type = ENTITY_TYPES.get(dataset, 'medigap_research_context')
    elif row.source_table in {'source_registry', 'policy_choices'}:
        dataset, local_id, payload = row.source_table, raw['native_key'], raw['native_value']
        entity_type = 'medigap_source_registry_entry' if row.source_table == 'source_registry' else 'medigap_policy_choice_reference'
    else:
        dataset, local_id, payload = row.source_table, row.source_row_key, raw
        entity_type = 'medigap_temporal_context' if dataset == 'temporal-reconciliation.json' else 'medigap_research_context'
    fields = dict(payload) if isinstance(payload, Mapping) else {'native_value': payload}
    fields['adapter_context'] = {'reference_id': REFERENCE_ID, 'reference_year': 2026,
                                 'native_dataset': dataset, 'native_row_id': local_id,
                                 'rule_namespace': 'L11.medigap_rights',
                                 'personal_applicability_determined': False}
    conditions = {key: payload[key] for key in (
        'conditions', 'source_conditions', 'required_conditions', 'source_clause_ids',
        'jurisdiction', 'reference_date', 'source_effective_context', 'relationship_limit',
        'shared_requirement_rule_ids', 'conditional_policy_choice_rule_id', 'hold_ids',
        'personal_carrier_availability') if isinstance(payload, Mapping) and key in payload}
    return DomainProjection(row, entity_type, 'L11:build-r2:' + dataset + ':' + str(local_id),
                           fields, conditions=conditions)


def iter_projections(root):
    for row in iter_records(root):
        yield project_record(row)
