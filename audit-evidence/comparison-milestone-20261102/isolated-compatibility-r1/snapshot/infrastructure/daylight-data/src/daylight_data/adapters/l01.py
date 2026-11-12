"""D76 exact published cost reference; no personal applicability or calculator."""
from pathlib import Path
from decimal import Decimal
from .common import DomainProjection, json_records

BASE = 'docs/data/l01-national-2026/published-reference-r1'


def iter_records(root):
    root = Path(root).resolve()
    for table in ('costs', 'bands', 'notes'):
        yield from json_records(root, root / BASE / (table + '.json'), 'L01', table)


def project_record(row):
    raw = row.raw
    fields = {'reference_id': 'L01-PUBLISHED-US-2026-r1', 'local_id': raw['id'],
              'benefit_year': 2026, 'personal_applicability_determined': False}
    if row.source_table == 'costs':
        for key in ('label', 'kind', 'unit', 'currency', 'period', 'cost_basis',
                    'coverage_context', 'effective_from', 'effective_until',
                    'qualification_ids', 'observation_ids', 'conflict_ids'):
            fields[key] = raw.get(key)
        fields['source_value'] = raw.get('value')
        if raw.get('kind') == 'money':
            if not isinstance(raw.get('value'), int):
                raise ValueError('Published cost money must retain integer cents')
            fields.update(amount_cents=raw['value'], amount_decimal=Decimal(raw['value']) / Decimal(100),
                          amount_encoding='USD_integer_cents')
        elif raw.get('kind') == 'rate':
            rate = raw['value']
            fields.update(rate_numerator=rate['numerator'], rate_denominator=rate['denominator'],
                          value_decimal=Decimal(rate['numerator']) / Decimal(rate['denominator']),
                          value_encoding='exact_fraction')
        elif raw.get('kind') == 'quantity':
            fields['quantity_decimal'] = Decimal(str(raw['value']))
        elif raw.get('kind') == 'prescription_cap':
            fields.update(maximum_cents=raw['value']['maximum_cents'],
                          schedule=raw['value']['schedule'],
                          approximate_rate=raw['value']['approximate_rate'])
        entity_type = 'federal_cost_reference'
    elif row.source_table == 'bands':
        for key in ('coverage_context', 'filing_status', 'lower_cents', 'upper_cents',
                    'lower_inclusive', 'upper_inclusive', 'base_cents', 'adjustment_cents',
                    'published_total_cents', 'currency', 'period', 'income_unit',
                    'effective_from', 'effective_until', 'tax_return_basis',
                    'qualification_ids', 'observation_ids', 'conflict_ids'):
            fields[key] = raw.get(key)
        fields['amount_encoding'] = 'USD_integer_cents'
        entity_type = 'federal_income_band_reference'
    else:
        fields.update(raw)
        entity_type = 'federal_reference_qualification'
    # The adapter preserves source acceptance scope, but only the existing gate
    # can establish current receipt validity for a requested output.
    yield DomainProjection(row, entity_type, 'L01:L01-PUBLISHED-US-2026-r1:' + row.source_table + ':' + raw['id'],
                           fields, output_acceptance_state='exact_existing_receipt_gate_required',
                           conditions=raw.get('conditions', raw.get('qualification_ids', [])))


def iter_projections(root):
    for row in iter_records(root):
        yield from project_record(row)
