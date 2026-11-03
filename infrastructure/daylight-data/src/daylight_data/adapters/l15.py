"""Dated counseling contacts; no availability, request, delivery or handoff claims."""
from pathlib import Path

from .common import DomainProjection, load_json, make_source, sha256_file

BASE = 'docs/data/l15-local-counseling-2026-10-29/build-r1'
DIRECTORY = BASE + '/directory.json'
REFERENCE_ID = 'L15-PUBLISHED-COLLIER-2026-10-29-r1'
AS_OF_DATE = '2026-10-29'
COUNTY_FIPS = '12021'
GROUPS = ('sites', 'sources', 'statewide', 'liaison', 'online_request')
ENTITY_TYPES = {'sites': 'counseling_site', 'sources': 'counseling_source_registry_entry',
                'statewide': 'counseling_statewide_contact', 'liaison': 'counseling_liaison_contact',
                'online_request': 'counseling_online_request_route', 'directory_context': 'counseling_directory_context'}


def iter_records(root):
    root = Path(root).resolve()
    path = root / DIRECTORY
    directory = load_json(path)
    if not isinstance(directory, dict) or directory.get('site_count') != len(directory.get('sites', [])):
        raise ValueError('L15 directory shape/site control does not agree.')
    if (directory.get('reference_id'), directory.get('as_of_date'), directory.get('county_fips')) != (REFERENCE_ID, AS_OF_DATE, COUNTY_FIPS):
        raise ValueError('L15 selected reference/date/geography changed; use a new reviewed adapter revision.')
    source_hash = sha256_file(path)
    for table in GROUPS:
        value = directory[table]
        rows = value if table in {'sites', 'sources'} else [value]
        if not isinstance(rows, list):
            raise ValueError(f'L15 {table} must retain its source array/object shape.')
        for ordinal, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                raise ValueError(f'L15 {table} row must be an object.')
            yield make_source(root, path, 'L15', table, ordinal, row.get('id', table), row,
                              'json_array_position_1_based:' + table if table in {'sites', 'sources'} else 'json_object_key:' + table,
                              source_hash)
    context = {key: value for key, value in directory.items() if key not in GROUPS}
    yield make_source(root, path, 'L15', 'directory_context', 1, directory['reference_id'], context,
                      'remaining_top_level_json_members', source_hash)


def project_record(row):
    fields = dict(row.raw)
    fields['adapter_context'] = {'reference_id': REFERENCE_ID,
                                 'as_of_date': AS_OF_DATE,
                                 'county_fips': COUNTY_FIPS,
                                 'contact_does_not_establish_service_availability': True,
                                 'personal_applicability_determined': False,
                                 'submission_or_transfer_executed_by_adapter': False}
    conditions = {key: row.raw[key] for key in (
        'appointment_only', 'member_restriction', 'membership_eligibility', 'availability',
        'hours', 'appointment_route', 'administrative_contact_limit', 'purpose',
        'limit', 'limits', 'native_fields', 'status', 'security_code_required') if key in row.raw}
    return DomainProjection(row, ENTITY_TYPES[row.source_table],
                           'L15:build-r1:' + row.source_table + ':' + row.source_row_key,
                           fields, value_state='dated_published_contact_reference',
                           freshness_state='as_of_' + AS_OF_DATE, conditions=conditions)


def iter_projections(root):
    for row in iter_records(root):
        yield project_record(row)
