"""Complete selected L02 source tables with separately labeled Collier projection."""
from pathlib import Path
from .common import DomainProjection, offering_parts, sqlite_records, json_records

BASE = 'docs/data/l02-ma-availability-2026-10-25/build-r5'


def iter_records(root):
    root = Path(root).resolve()
    yield from sqlite_records(root, root / BASE / 'inventory.sqlite3', 'L02')
    yield from iter_collier_offerings(root)


def iter_collier_offerings(root):
    root = Path(root).resolve()
    yield from json_records(root, root / BASE / '12021/offerings.json', 'L02', 'collier_offerings')


def project_record(row):
    raw = row.raw
    fields = {'benefit_year': 2026, 'source_table': row.source_table}
    identifier = raw.get('offering_id') or (raw.get('id') if row.source_table == 'offerings' else None)
    if identifier and ':' in identifier:
        fields.update(offering_parts(identifier))
    elif identifier:
        fields.update(source_identity=identifier, identity_grain='contract_only_not_offering')
    if row.source_table == 'offerings':
        entity_type = 'offering'
        for key in ('category', 'route', 'parent', 'legal_name', 'marketing', 'name',
                    'plan_type', 'drug', 'snp', 'snp_type', 'sanction', 'restriction_raw', 'locator'):
            fields[key] = raw.get(key)
        fields.update(inventory_state='source_observed', verified_availability=False,
                      expected_market_denominator=None, personal_applicability='not_assessed')
    elif row.source_table == 'collier_offerings':
        fields.update(raw)
        fields.update(county_fips='12021', geography_verified=False,
                      verified_availability=False, personal_applicability='not_assessed')
        entity_type = 'collier_offering_scope'
    elif row.source_table == 'areas':
        entity_type = 'offering_geography_observation'
        for key in ('contract', 'county_fips', 'state', 'county', 'grain', 'extent', 'source', 'locator'):
            fields[key] = raw.get(key)
        if fields['county_fips'] is not None and (not isinstance(fields['county_fips'], str) or len(fields['county_fips']) != 5):
            raise ValueError('County FIPS must retain a padded string')
        fields['geography_verified'] = False
    else:
        entity_type = {'ledger': 'source_row_disposition', 'quarantine': 'source_quarantine',
                       'secondary': 'secondary_identity_observation', 'differences': 'source_difference',
                       'metadata': 'source_metadata'}[row.source_table]
        fields.update(raw)
    yield DomainProjection(row, entity_type, 'L02:build-r5:' + row.source_table + ':' + row.source_row_key,
                           fields, value_state='quarantined' if row.source_table == 'quarantine' else 'source_observed',
                           conditions=raw.get('restriction_raw', []))


def iter_projections(root):
    for row in iter_records(root):
        yield from project_record(row)
