"""Published 2026 L07 source-preserving research adapter; no acceptance implied."""
from __future__ import annotations

import base64
from contextlib import closing
from dataclasses import replace
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
from urllib.parse import quote

from .common import DomainProjection, canonical_json, make_source, offering_parts, sha256_file, sqlite_records

JSON_ITEM_LIMIT = 16 * 1024 * 1024


def _json_items(path):
    """Stream one array element/object entry at a time, with a bounded item buffer."""
    decoder = json.JSONDecoder(parse_float=Decimal)
    with Path(path).open(encoding='utf-8-sig') as handle:
        buffer, position, ended = '', 0, False

        def refill():
            nonlocal buffer, position, ended
            buffer = buffer[position:]
            position = 0
            chunk = handle.read(65536)
            buffer += chunk
            ended = not chunk
            if len(buffer.encode('utf-8')) > JSON_ITEM_LIMIT:
                raise ValueError('Structured source item exceeds the explicit 16 MiB adapter bound')

        def whitespace():
            nonlocal position
            while True:
                while position < len(buffer) and buffer[position].isspace():
                    position += 1
                if position < len(buffer) or ended:
                    return
                refill()

        def token(expected=None):
            nonlocal position
            whitespace()
            if position >= len(buffer):
                raise ValueError('Truncated structured source')
            result = buffer[position]
            if expected is not None and result != expected:
                raise ValueError(f'Expected JSON delimiter {expected!r}, got {result!r}')
            position += 1
            return result

        def value():
            nonlocal position
            whitespace()
            while True:
                try:
                    result, end = decoder.raw_decode(buffer, position)
                    if end == len(buffer) and not ended:
                        refill()
                        continue
                    position = end
                    return result
                except json.JSONDecodeError:
                    if ended:
                        raise
                    refill()

        opening = token()
        if opening not in '[{':
            raise ValueError('Selected JSON table must be an array or object')
        closing_token = ']' if opening == '[' else '}'
        ordinal = 0
        while True:
            whitespace()
            if position < len(buffer) and buffer[position] == closing_token:
                token(closing_token)
                break
            if ordinal:
                token(',')
            if opening == '{':
                key = value()
                if not isinstance(key, str):
                    raise ValueError('JSON object key must be text')
                token(':')
                row = {'key': key, 'value': value()}
            else:
                row = value()
                key = ordinal + 1
                if not isinstance(row, dict):
                    row = {'value': row}
            ordinal += 1
            yield ordinal, key, row
        whitespace()
        if position != len(buffer):
            raise ValueError('Trailing content after selected JSON table')


def _controls(root):
    result = {}
    for name, expected in CONTROL_HASHES.items():
        path = root / BASE / name
        if sha256_file(path) != expected:
            raise ValueError(f'Selected source control hash changed: {path}')
        with path.open(encoding='utf-8') as handle:
            result[name] = json.load(handle)
    return result


def selected_sources():
    """Data artifacts chosen at their native grain; SQLite mirrors are not duplicated."""
    return tuple(dict(spec, path=BASE + '/' + spec['relative_path']) for spec in SOURCE_SPECS)


def _expected(spec, controls):
    manifest = controls[spec['control']]
    mapping = manifest.get('files', manifest.get('files_sha256', manifest.get('sha256', {})))
    name = spec['relative_path']
    control_parent = Path(spec['control']).parent
    local = Path(name).relative_to(control_parent).as_posix() if Path(name).is_relative_to(control_parent) else name
    expected = mapping.get(local, mapping.get(BASE + '/' + name))
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError(f'Selected artifact has no exact hash in its control: {name}')
    return expected


def _binary_payload(raw):
    """A reversible byte envelope, avoiding UTF-8 decoding or silent BLOB loss."""
    return {key: ({'encoding': 'base64', 'data': base64.b64encode(bytes(value)).decode('ascii'),
                   'byte_length': len(value), 'sha256': hashlib.sha256(value).hexdigest()}
                  if isinstance(value, (bytes, bytearray, memoryview)) else value)
            for key, value in raw.items()}


def iter_records(root):
    root = Path(root).resolve()
    controls = _controls(root)
    for spec in SOURCE_SPECS:
        path = root / BASE / spec['relative_path']
        expected = _expected(spec, controls)
        if spec['format'] == 'sqlite':
            for row in sqlite_records(root, path, LAYER_ID):
                if row.source_sha256 != expected:
                    raise ValueError(f'Selected SQLite source hash changed: {path}')
                yield replace(row, raw=_binary_payload(row.raw))
            continue
        actual = sha256_file(path)
        if actual != expected:
            raise ValueError(f'Selected source hash changed: {path}')
        if spec['format'] == 'jsonl_gzip':
            def values():
                with gzip.open(path, 'rt', encoding='utf-8') as handle:
                    for ordinal, line in enumerate(iter(lambda: handle.readline(JSON_ITEM_LIMIT + 1), ''), 1):
                        if len(line.encode('utf-8')) > JSON_ITEM_LIMIT:
                            raise ValueError('JSONL source item exceeds explicit adapter bound')
                        row = json.loads(line, parse_float=Decimal)
                        if not isinstance(row, dict):
                            raise ValueError('Expected JSONL object')
                        yield ordinal, row.get('id', ordinal), row
            basis = 'jsonl_line_ordinal_1_based'
        elif spec['format'] == 'csv_gzip':
            def values():
                import csv
                with gzip.open(path, 'rt', encoding='utf-8-sig', newline='') as handle:
                    for ordinal, row in enumerate(csv.DictReader(handle), 1):
                        yield ordinal, ordinal, dict(row)
            basis = 'csv_data_record_ordinal_1_based'
        else:
            def values():
                yield from _json_items(path)
            basis = 'json_array_or_object_entry_ordinal_1_based'
        for ordinal, key, raw in values():
            yield make_source(root, path, LAYER_ID, spec['table'], ordinal,
                              raw.get('id', key), raw, basis, actual)


def inventory(root):
    """Read counts/sizes without creating a database, archive or materialized table."""
    root = Path(root).resolve()
    controls = _controls(root)
    sources = []
    for spec in SOURCE_SPECS:
        path = root / BASE / spec['relative_path']
        counts = {}
        if spec['format'] == 'sqlite':
            uri = 'file:' + quote(str(path.resolve()), safe='/') + '?mode=ro&immutable=1'
            with closing(sqlite3.connect(uri, uri=True)) as database:
                for name, in database.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
                    escaped = '"' + name.replace('"', '""') + '"'
                    counts[name] = database.execute('SELECT COUNT(*) FROM ' + escaped).fetchone()[0]
        elif spec['format'] == 'jsonl_gzip':
            with gzip.open(path, 'rt', encoding='utf-8') as handle:
                counts[spec['table']] = sum(1 for _ in handle)
        elif spec['format'] == 'csv_gzip':
            import csv
            with gzip.open(path, 'rt', encoding='utf-8-sig', newline='') as handle:
                counts[spec['table']] = sum(1 for _ in csv.DictReader(handle))
        else:
            counts[spec['table']] = sum(1 for _ in _json_items(path))
        sources.append({'path': spec['relative_path'], 'bytes': path.stat().st_size,
                        'expected_sha256': _expected(spec, controls), 'tables': counts})
    return {'layer_id': LAYER_ID, 'selected_source_bytes': sum(row['bytes'] for row in sources),
            'source_rows': sum(sum(row['tables'].values()) for row in sources), 'sources': sources,
            'controls_verified': True, 'source_byte_hashes_verified': False,
            'meaning': 'Read-only source sizing; no database import, archive copy or acceptance.'}


def _payload(raw, name='payload'):
    value = raw.get(name)
    return json.loads(value, parse_float=Decimal) if isinstance(value, str) else (value or {})


def _number(value):
    return None if value is None or str(value).strip() in ('', '.') else Decimal(str(value))


def _offering(fields, identifier):
    if identifier and isinstance(identifier, str) and ':' in identifier:
        fields.update(offering_parts(identifier))


def iter_projections(root):
    for row in iter_records(root):
        yield from project_record(row)


LAYER_ID = 'L07'
BASE = 'docs/data/l07-pharmacy-networks-2026-10-27'
CONTROL_HASHES = {'build-r1/manifest.json': '1cb8ee7374ad08e98a4803cb1b6b07aae7a3accaccad2df80aa7c37dac40675c', 'identity-build-r1/manifest.json': '359fffc6b859c3d451f471fd53e8d27c0cf9d678396f4796ba9fb50ac0d579fd', 'location-build-r4/manifest.json': 'e86c3c5993532ddb295c7db3dfad25b4e947e4624e564c89c1c2fd28fee0b571', 'closeout-r1/manifest.json': 'e901c3ed2a0d19bdaea59e7d24beb2de482a43d387e4ac5f9a37941fe784422a'}
SOURCE_SPECS = ({'relative_path': 'build-r1/inventory.sqlite3', 'format': 'sqlite', 'table': None, 'control': 'build-r1/manifest.json'}, {'relative_path': 'location-build-r4/inventory.sqlite3', 'format': 'sqlite', 'table': None, 'control': 'location-build-r4/manifest.json'}, {'relative_path': 'build-r1/plans.json', 'format': 'json', 'table': 'network_plans', 'control': 'build-r1/manifest.json'}, {'relative_path': 'build-r1/pharmacy-keys.json', 'format': 'json', 'table': 'pharmacy_keys', 'control': 'build-r1/manifest.json'}, {'relative_path': 'build-r1/invalid-pharmacy-numbers.json', 'format': 'json', 'table': 'invalid_pharmacy_numbers', 'control': 'build-r1/manifest.json'}, {'relative_path': 'build-r1/duplicates.json', 'format': 'json', 'table': 'network_duplicates', 'control': 'build-r1/manifest.json'}, {'relative_path': 'build-r1/field-map.json', 'format': 'json', 'table': 'network_field_map', 'control': 'build-r1/manifest.json'}, {'relative_path': 'build-r1/source-members.json', 'format': 'json', 'table': 'network_source_members', 'control': 'build-r1/manifest.json'}, {'relative_path': 'build-r1/coverage.json', 'format': 'json', 'table': 'network_coverage', 'control': 'build-r1/manifest.json'}, {'relative_path': 'identity-build-r1/identities.jsonl.gz', 'format': 'jsonl_gzip', 'table': 'identities', 'control': 'identity-build-r1/manifest.json'}, {'relative_path': 'identity-build-r1/missing-identities.json', 'format': 'json', 'table': 'missing_identities', 'control': 'identity-build-r1/manifest.json'}, {'relative_path': 'identity-build-r1/differing-observations.json', 'format': 'json', 'table': 'differing_identity_observations', 'control': 'identity-build-r1/manifest.json'}, {'relative_path': 'identity-build-r1/network-location-joins.json', 'format': 'json', 'table': 'identity_location_joins', 'control': 'identity-build-r1/manifest.json'}, {'relative_path': 'identity-build-r1/query-errors.json', 'format': 'json', 'table': 'identity_query_errors', 'control': 'identity-build-r1/manifest.json'}, {'relative_path': 'identity-build-r1/florida-geography-input.json', 'format': 'json', 'table': 'florida_geography_input', 'control': 'identity-build-r1/manifest.json'}, {'relative_path': 'identity-build-r1/coverage.json', 'format': 'json', 'table': 'identity_coverage', 'control': 'identity-build-r1/manifest.json'}, {'relative_path': 'location-build-r4/exceptions.json', 'format': 'json', 'table': 'location_exceptions', 'control': 'location-build-r4/manifest.json'}, {'relative_path': 'location-build-r4/Collier-pharmacies.json', 'format': 'json', 'table': 'collier_pharmacies', 'control': 'location-build-r4/manifest.json'}, {'relative_path': 'location-build-r4/plan-location-coverage.json', 'format': 'json', 'table': 'plan_location_coverage', 'control': 'location-build-r4/manifest.json'}, {'relative_path': 'location-build-r4/coverage.json', 'format': 'json', 'table': 'location_coverage', 'control': 'location-build-r4/manifest.json'}, {'relative_path': 'closeout-r1/changes.json', 'format': 'json', 'table': 'closeout_changes', 'control': 'closeout-r1/manifest.json'}, {'relative_path': 'closeout-r1/decisions.json', 'format': 'json', 'table': 'closeout_decisions', 'control': 'closeout-r1/manifest.json'}, {'relative_path': 'closeout-r1/directory-observations.json', 'format': 'json', 'table': 'directory_observations', 'control': 'closeout-r1/manifest.json'}, {'relative_path': 'closeout-r1/field-comparisons.json', 'format': 'json', 'table': 'directory_field_comparisons', 'control': 'closeout-r1/manifest.json'}, {'relative_path': 'closeout-r1/held-directory-cases.json', 'format': 'json', 'table': 'held_directory_cases', 'control': 'closeout-r1/manifest.json'}, {'relative_path': 'closeout-r1/nearby-priority-cases.json', 'format': 'json', 'table': 'nearby_priority_cases', 'control': 'closeout-r1/manifest.json'}, {'relative_path': 'closeout-r1/remaining-gap-cases.json', 'format': 'json', 'table': 'remaining_gap_cases', 'control': 'closeout-r1/manifest.json'}, {'relative_path': 'closeout-r1/HealthPark-identity-distinction.json', 'format': 'json', 'table': 'healthpark_identity_distinction', 'control': 'closeout-r1/manifest.json'}, {'relative_path': 'closeout-r1/directory-accounting.json', 'format': 'json', 'table': 'directory_accounting', 'control': 'closeout-r1/manifest.json'}, {'relative_path': 'closeout-r1/gaps.json', 'format': 'json', 'table': 'closeout_gaps', 'control': 'closeout-r1/manifest.json'}, {'relative_path': 'closeout-r1/sources.json', 'format': 'json', 'table': 'closeout_sources', 'control': 'closeout-r1/manifest.json'})


FEE_COLUMNS = tuple(f'{product}_DISPENSING_FEE_{days}' for product in ('BRAND', 'GENERIC', 'SELECTED') for days in (30, 60, 90))


def _addresses(candidates):
    """Keep every source candidate; never pick a location from an ambiguous set."""
    result = []
    for candidate in candidates:
        address = candidate.get('registry_address') or candidate.get('address') or {}
        geography = candidate.get('geography') or {}
        result.append({'address_id': candidate.get('address_id'), 'address_1': address.get('address_1'),
                       'address_2': address.get('address_2'), 'city': address.get('city'),
                       'state': address.get('state'), 'postal_code': address.get('postal_code'),
                       'telephone_number': address.get('telephone_number'),
                       'county_fips': geography.get('county_fips'), 'geography_basis': geography.get('basis'),
                       'source_state': candidate.get('source_state')})
    return result


def project_record(row):
    raw, table = row.raw, row.source_table
    fields = {'benefit_year': 2026, 'source_table': table, 'source_component': Path(row.source_path).parent.name}
    _offering(fields, raw.get('offering_id'))
    state = 'source_observed'
    if table == 'network':
        fields.update(npi=raw.get('pharmacy_npi'), pharmacy_number_raw=raw.get('PHARMACY_NUMBER'),
                      network_zip=raw.get('PHARMACY_ZIPCODE'), retail_status=raw.get('retail_status'),
                      mail_status=raw.get('mail_status'), in_area_flag_raw=raw.get('IN_AREA_FLAG'),
                      retail_offered_flag_raw=raw.get('PHARMACY_RETAIL'), mail_offered_flag_raw=raw.get('PHARMACY_MAIL'),
                      preferred_retail_flag_raw=raw.get('PREFERRED_STATUS_RETAIL'),
                      preferred_mail_flag_raw=raw.get('PREFERRED_STATUS_MAIL'),
                      dispensing_fee_usd={key: _number(raw.get(key)) for key in FEE_COLUMNS},
                      dispensing_fee_missing_fields=[key for key in FEE_COLUMNS if _number(raw.get(key)) is None],
                      fee_basis='USD_dispensing_fee_not_full_beneficiary_payment',
                      selected_fee_substitution_performed=False,
                      source_part=raw['source_part'], source_ordinal=raw['source_ordinal'],
                      current_operation_verified=False, pharmacy_specific_drug_price=False)
        entity = 'pharmacy_network_observation'
    elif table in ('locations', 'location_exceptions', 'nearby_priority_cases'):
        payload = _payload(raw, 'record_json') if table == 'locations' else raw
        fields.update(npi=raw.get('npi') or payload.get('npi'), network_zip=raw.get('network_zip') or payload.get('network_zip'),
                      identity_status=raw.get('identity_status') or payload.get('status'),
                      scope_group=raw.get('scope_group') or payload.get('scope_group'),
                      county_fips=raw.get('county_fips') or payload.get('county_fips'),
                      candidate_addresses=_addresses(payload.get('candidate_locations', [])),
                      candidate_location_keys=payload.get('candidate_location_keys', []),
                      county_evidence_level=payload.get('county_evidence_level'),
                      selected_address_id=payload.get('selected_address_id'),
                      identity_source=payload.get('identity_source'),
                      exact_snapshot_address_continuity_established=payload.get('exact_CMS_snapshot_address_continuity_established', False))
        entity = 'pharmacy_location_observation'
        state = fields['identity_status'] or 'location_unresolved'
    elif table == 'identities':
        fields.update(npi=raw.get('npi'), organization_name=raw.get('organization_name'),
                      enumeration_type=raw.get('enumeration_type'), registry_status=raw.get('registry_status'),
                      enumeration_date=raw.get('enumeration_date'), last_updated=raw.get('last_updated'),
                      registry_locations=raw.get('locations'), other_names=raw.get('other_names'),
                      source_locator=raw.get('source'), current_operation_verified=False)
        entity = 'pharmacy_registry_identity'
    elif table == 'identity_location_joins':
        fields.update(npi=raw.get('npi'), network_zip=raw.get('network_zip'),
                      candidate_location_keys=raw.get('candidate_location_keys'))
        entity, state = 'pharmacy_identity_location_binding', raw.get('status', 'unknown')
    elif table in ('pharmacy_keys', 'missing_identities', 'invalid_pharmacy_numbers'):
        fields.update(raw)
        entity = 'pharmacy_source_identity_key' if table == 'pharmacy_keys' else 'pharmacy_identity_gap'
        state = 'source_key_observed' if table == 'pharmacy_keys' else 'source_identity_unresolved'
    elif table == 'network_plans':
        fields.update(formulary_id=raw.get('formulary_id'), formulary_version=raw.get('formulary_version'),
                      plan_name=raw.get('name'), product_kind=raw.get('kind'))
        entity = 'pharmacy_network_plan_context'
    elif table == 'directory_observations':
        fields.update(npi=raw.get('npi'), street=raw.get('street'), city=raw.get('city'),
                      state=raw.get('state'), postal_code=raw.get('postal_code'), telephone_number=raw.get('phone'),
                      county_fips=raw.get('county_fips'), document_plan=raw.get('document_plan'),
                      directory_updated_date=raw.get('directory_updated_date'), pdf_page=raw.get('page'),
                      source_use=raw.get('use'), exact_snapshot_address_continuity_established=False)
        entity = 'pharmacy_directory_location_observation'
    elif table in ('closeout_changes', 'closeout_decisions', 'directory_field_comparisons', 'held_directory_cases'):
        fields.update(npi=raw.get('npi'), network_zip=raw.get('network_zip'), county_fips=raw.get('county_fips'),
                      change_kind=raw.get('kind'), county_evidence_level=raw.get('county_evidence_level'),
                      selected_address_id=raw.get('selected_address_id'), directory_updated_date=raw.get('directory_updated_date'),
                      directory_observation_index=raw.get('directory_observation_index', raw.get('observation_index')),
                      source_ZIP_preserved=raw.get('CMS_ZIP_preserved') or raw.get('native_CMS_ZIP'),
                      registry_ZIP_preserved=raw.get('registry_ZIP_preserved'),
                      reason=raw.get('reason'), comparison=raw.get('comparison'),
                      before_scope=raw.get('before_scope'), after_scope=raw.get('after_scope'))
        entity = 'pharmacy_location_reconciliation'
        state = 'held' if table == 'held_directory_cases' else 'source_native_reconciliation'
    elif table == 'remaining_gap_cases':
        fields.update(npi=raw.get('npi'), network_zip=raw.get('network_zip'),
                      identity_join_status=raw.get('identity_join_status'), scope_group=raw.get('scope_group'),
                      affected_source_rows=raw.get('affected_source_rows'),
                      candidate_addresses=_addresses(raw.get('candidate_locations', [])),
                      additional_directory_observation_indices=raw.get('additional_directory_observation_indices'))
        entity, state = 'pharmacy_location_gap', 'unresolved_source_location'
    elif table == 'collier_pharmacies':
        fields.update(npi=raw.get('npi'), network_zip=raw.get('network_zip'),
                      county_fips=raw.get('county_fips'), address=raw.get('address'),
                      geography_evidence=raw.get('geography_evidence'), registry_identity_state=raw.get('registry_identity_state'))
        entity = 'pharmacy_county_location_observation'
    elif table == 'plan_location_coverage':
        fields.update(scope_group=raw.get('scope_group'), network_rows=raw.get('network_rows'))
        entity = 'pharmacy_plan_location_accounting'
    else:
        fields.update(control_key=raw.get('key'), control_value=raw.get('value'))
        entity = 'pharmacy_network_source_control'
    yield DomainProjection(row, entity, f'L07:{row.record_id}', fields, value_state=state,
                           conditions={'personal_network_or_operation_not_inferred': True})
