"""Contract-grain Star observations with exact decimal and measurement context."""
from decimal import Decimal
import json
from pathlib import Path
from .common import DomainProjection, sqlite_records

BASE = 'docs/data/l09-star-ratings-2026-10-28/build-r4'


def iter_records(root):
    root = Path(root).resolve()
    yield from sqlite_records(root, root / BASE / 'inventory.sqlite3', 'L09')


def project_record(row):
    raw = row.raw
    payload = json.loads(raw['payload'], parse_float=Decimal) if 'payload' in raw else dict(raw)
    fields = dict(payload)
    if row.source_table == 'observations':
        fields.update(contract_id=raw['contract'], rating_year=payload['rating_year'],
                      rating_kind=raw['kind'], rating_code=raw['code'],
                      value_decimal=Decimal(raw['value_decimal']) if raw['value_decimal'] is not None else None,
                      unit=raw['unit'], value_encoding='exact_decimal_string', value_state=raw['state'],
                      grain='contract_rating_kind_measure_and_year')
        entity_type, local_id = 'quality_observation', raw['id']
    elif row.source_table == 'offerings':
        fields.update(offering_id=raw['offering_id'], contract_id=raw['contract'], rating_type=raw['rating_type'])
        entity_type, local_id = 'offering_quality_binding', raw['offering_id']
    elif row.source_table == 'definitions':
        fields.update(measure_code=raw['code'])
        entity_type, local_id = 'quality_measure_definition', raw['code']
    elif row.source_table == 'contracts':
        fields.update(contract_id=raw['contract'])
        entity_type, local_id = 'quality_contract', raw['contract']
    else:
        entity_type, local_id = 'quality_source_context', row.source_row_key
    yield DomainProjection(row, entity_type, 'L09:build-r4:' + entity_type + ':' + local_id,
                           fields, value_state=fields.get('value_state', 'source_observed'),
                           conditions={'measurement_period_raw': payload.get('measurement_period_raw'),
                                       'measurement_period_basis': payload.get('measurement_period_basis'),
                                       'source_revision_label': payload.get('source_revision_label')})


def iter_projections(root):
    for row in iter_records(root):
        yield from project_record(row)
