"""Florida PDP reference fields, counties and restriction supplement; research only."""
from pathlib import Path
from decimal import Decimal
from .common import DomainProjection, json_records, offering_parts, sqlite_records, load_json, make_source

BASE = 'docs/data/l04-pdp-availability-2026-10-25'


def iter_records(root):
    root = Path(root).resolve()
    yield from json_records(root, root / BASE / 'build-r4/records.json', 'L04', 'pdp_records', 'offering_id')
    yield from sqlite_records(root, root / BASE / 'build-r4/inventory.sqlite3', 'L04')
    for table in ('records',):
        yield from json_records(root, root / BASE / 'restriction-check-r3' / (table + '.json'),
                                'L04', 'restriction_' + table, 'offering_id')
    path = root / BASE / 'restriction-check-r3/gaps.json'
    yield make_source(root, path, 'L04', 'restriction_gaps', 1, 'gap_document', load_json(path), 'singleton_source_document')


def project_record(row):
    raw = row.raw
    fields = {'benefit_year': 2026, 'source_table': row.source_table}
    identifier = raw.get('offering_id')
    if identifier and ':' in identifier:
        fields.update(offering_parts(identifier))
    elif identifier:
        fields.update(source_identity=identifier, identity_grain='contract_only_not_offering')
    if row.source_table == 'pdp_records':
        fields.update(region_code=raw.get('region'), state_code=raw.get('state'),
                      source_ordinal=raw.get('ordinal'), verified_availability=False,
                      published_field_count=len(raw['fields']))
        # Each published field is a material typed observation, never silently
        # collapsed into a premium total. Original qualifiers and raw survive.
        for name, value in raw['fields'].items():
            typed = dict(value)
            if value.get('value_encoding') == 'integer_cents' and value.get('value') is not None:
                if not isinstance(value['value'], int):
                    raise ValueError('PDP money source value must be integer cents')
                typed['amount_cents'] = value['value']
                typed['amount_decimal'] = Decimal(value['value']) / Decimal(100)
            field_fields = dict(fields, field_name=name, **typed)
            yield DomainProjection(row, 'pdp_field_observation',
                                   'L04:build-r4:' + identifier + ':field:' + name, field_fields,
                                   value_state=value.get('state', 'unknown'))
        yield DomainProjection(row, 'offering', 'L04:build-r4:' + identifier,
                               dict(fields, fields=raw['fields']))
    elif row.source_table == 'counties':
        fields.update(county_fips=raw['fips'], state_code=raw['state'], county_name=raw['name'],
                      ssa_county_code=raw['ssa'], region_code=raw['region'])
        yield DomainProjection(row, 'pdp_region_county', 'L04:build-r4:county:' + raw['fips'], fields)
    else:
        fields.update(raw)
        yield DomainProjection(row, 'pdp_' + row.source_table,
                               'L04:' + row.source_table + ':' + row.source_row_key, fields,
                               value_state='quarantined' if row.source_table == 'quarantine' else 'source_observed')


def iter_projections(root):
    for row in iter_records(root):
        yield from project_record(row)
