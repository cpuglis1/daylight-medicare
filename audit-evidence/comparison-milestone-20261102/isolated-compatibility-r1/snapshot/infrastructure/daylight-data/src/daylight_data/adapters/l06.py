"""Published 2026 L06 source-preserving research adapter; no acceptance implied."""
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


LAYER_ID = 'L06'
BASE = 'docs/data/l06-drug-costs-2026-10-27'
CONTROL_HASHES = {'build-r1/manifest.json': 'cff044edf598201f6e20a042fa6b20fbf3627c163a43317e70786204852df327', 'build-cost-r1/manifest.json': '98a9c4310f368265c98b075783f297f38756230edfb561c8374979f4bbb40493'}
SOURCE_SPECS = ({'relative_path': 'build-r1/inventory.sqlite3', 'format': 'sqlite', 'table': None, 'control': 'build-r1/manifest.json'}, {'relative_path': 'build-cost-r1/inventory.sqlite3', 'format': 'sqlite', 'table': None, 'control': 'build-cost-r1/manifest.json'}, {'relative_path': 'build-r1/coverage.json', 'format': 'json', 'table': 'price_coverage', 'control': 'build-r1/manifest.json'}, {'relative_path': 'build-r1/missing-formulary-prices.json', 'format': 'json', 'table': 'missing_formulary_prices', 'control': 'build-r1/manifest.json'}, {'relative_path': 'build-r1/plan-coverage.json', 'format': 'json', 'table': 'price_plan_coverage', 'control': 'build-r1/manifest.json'}, {'relative_path': 'build-r1/scope.json', 'format': 'json', 'table': 'price_scope', 'control': 'build-r1/manifest.json'}, {'relative_path': 'build-r1/snapshot-bridge.json', 'format': 'json', 'table': 'snapshot_bridge', 'control': 'build-r1/manifest.json'}, {'relative_path': 'build-cost-r1/PBP-named-amount-comparisons.json', 'format': 'json', 'table': 'pbp_amount_comparisons', 'control': 'build-cost-r1/manifest.json'}, {'relative_path': 'build-cost-r1/insulin-blank-channel-dispositions.json', 'format': 'json', 'table': 'insulin_blank_channel_dispositions', 'control': 'build-cost-r1/manifest.json'}, {'relative_path': 'build-cost-r1/plan-coverage.json', 'format': 'json', 'table': 'schedule_plan_coverage', 'control': 'build-cost-r1/manifest.json'}, {'relative_path': 'build-cost-r1/field-map.json', 'format': 'json', 'table': 'schedule_field_map', 'control': 'build-cost-r1/manifest.json'}, {'relative_path': 'build-cost-r1/scope.json', 'format': 'json', 'table': 'schedule_scope', 'control': 'build-cost-r1/manifest.json'}, {'relative_path': 'build-cost-r1/coverage.json', 'format': 'json', 'table': 'schedule_coverage', 'control': 'build-cost-r1/manifest.json'}, {'relative_path': 'build-cost-r1/source-members.json', 'format': 'json', 'table': 'schedule_source_members', 'control': 'build-cost-r1/manifest.json'})


CHANNELS = (('PREF', 'preferred_retail'), ('NONPREF', 'standard_retail'),
            ('MAIL_PREF', 'preferred_mail'), ('MAIL_NONPREF', 'standard_mail'))


def _value(modeled, key):
    return modeled.get(key, {}).get('value')


def project_record(row):
    raw, table = row.raw, row.source_table
    component = Path(row.source_path).parent.name
    fields = {'benefit_year': 2026, 'source_table': table, 'source_component': component}
    _offering(fields, raw.get('offering_id'))
    state = 'source_observed'
    if table == 'prices':
        amount = raw.get('unit_cost_usd_1e4')
        if amount is not None and not isinstance(amount, int):
            raise ValueError('Native price must retain integer 1e-4 USD encoding')
        fields.update(ndc=raw.get('ndc'), days_supply=raw.get('days_supply'),
                      amount_usd_1e4=amount, amount_decimal=Decimal(amount) / Decimal(10000) if amount is not None else None,
                      amount_encoding='integer_USD_1e4', source_unit_cost=raw.get('source_unit_cost'),
                      source_ordinal=raw['source_ordinal'], contract_id=raw.get('contract_id'),
                      plan_id=raw.get('plan_id'), segment_id=raw.get('segment_id'),
                      price_kind='published_in_area_retail_average', physical_unit=None,
                      physical_unit_state='source_UNIT_COST_unit_not_asserted', pharmacy_specific=False,
                      personal_price=False, dispensing_fee_addition_performed=False)
        state, entity = raw['disposition'], 'drug_price_observation'
    elif table == 'formulary_pairs':
        fields.update(ndc=raw['ndc'], source_ordinal=raw['source_ordinal'],
                      meaning='source_formulary_pair_not_a_personal_coverage_or_price_conclusion')
        entity = 'offering_formulary_product_pair'
    elif table == 'plans':
        payload = _payload(raw)
        fields.update(formulary_id=raw.get('formulary_id') or payload.get('formulary_id'),
                      formulary_version=payload.get('formulary_version'), plan_name=payload.get('name'),
                      suppressed=payload.get('suppressed'), product_kind=payload.get('kind'))
        entity = 'drug_cost_plan_context'
    elif table == 'schedules':
        modeled, native = _payload(raw, 'modeled_json'), _payload(raw, 'raw_json')
        family = raw['table_name']
        fields.update(schedule_family=family, source_ordinal=raw['source_ordinal'],
                      tier=_value(modeled, 'TIER'), tier_state=modeled.get('TIER', {}).get('source_state'),
                      days_supply=_value(modeled, 'DAYS_SUPPLY'), days_supply_raw=native.get('DAYS_SUPPLY'),
                      phase_code=_value(modeled, 'COVERAGE_LEVEL'),
                      phase=modeled.get('COVERAGE_LEVEL', {}).get('meaning'),
                      deductible_applies=_value(modeled, 'DED_APPLIES_YN'),
                      specialty_tier=_value(modeled, 'TIER_SPECIALTY_YN'))
        yield DomainProjection(row, 'drug_cost_schedule', f'L06:{row.record_id}:schedule', fields,
                               conditions={'native_field_states': {key: val.get('source_state') for key, val in modeled.items()},
                                           'personal_calculation_performed': False})
        for suffix, channel in CHANNELS:
            channel_fields = dict(fields, channel=channel, personal_calculation_performed=False)
            if family == 'beneficiary':
                kind = modeled.get('COST_TYPE_' + suffix, {})
                amount = modeled.get('COST_AMT_' + suffix, {})
                minimum = modeled.get('COST_MIN_AMT_' + suffix, {})
                maximum = modeled.get('COST_MAX_AMT_' + suffix, {})
                channel_fields.update(cost_type_code=kind.get('value'), cost_type=kind.get('meaning'),
                                      amount_decimal=_number(amount.get('value')), unit=amount.get('unit'),
                                      channel_state=kind.get('meaning') or kind.get('source_state'),
                                      amount_state=amount.get('source_state'), amount_meaning=amount.get('meaning'),
                                      native_amount_decimal=_number(amount.get('native_numeric_value')),
                                      minimum_decimal=_number(minimum.get('value')), maximum_decimal=_number(maximum.get('value')),
                                      bound_unit=minimum.get('unit'), bound_meaning=minimum.get('meaning'))
                channel_state = channel_fields['channel_state'] or 'unknown'
            elif family == 'insulin':
                native_suffix = suffix.lower()
                copay = modeled.get('copay_amt_' + native_suffix + '_insln', {})
                coin = modeled.get('coin_amt_' + native_suffix + '_insln', {})
                channel_fields.update(copay_decimal=_number(copay.get('value')), copay_unit=copay.get('unit'),
                                      coinsurance_decimal=_number(coin.get('value')), coinsurance_unit=coin.get('unit'),
                                      copay_state=copay.get('source_state'), coinsurance_state=coin.get('source_state'),
                                      channel_state='source_blank' if copay.get('source_state') == 'source_blank' and coin.get('source_state') == 'source_blank' else 'published_insulin_schedule',
                                      disposition_binding='see_exact_source_ordinal_channel_disposition_observation')
                channel_state = channel_fields['channel_state']
            else:
                raise ValueError(f'Unknown selected schedule family: {family}')
            yield DomainProjection(row, 'drug_cost_channel_schedule', f'L06:{row.record_id}:channel:{channel}',
                                   channel_fields, value_state=channel_state,
                                   conditions={'bounds_not_applied_in_calculator': True,
                                               'unknown_or_blank_is_not_zero': True})
        return
    elif table == 'insulin_blank_channel_dispositions':
        fields.update(channel=raw.get('channel'), source_ordinal=raw.get('source_ordinal'),
                      matched_beneficiary_channel_types=raw.get('matched_beneficiary_channel_types'))
        state, entity = raw['status'], 'drug_cost_channel_disposition'
    elif table == 'pbp_amount_comparisons':
        fields.update(schedule_family=raw.get('table'), source_ordinal=raw.get('source_ordinal'),
                      source_field=raw.get('source_field'), source_value_decimal=_number(raw.get('source_value')),
                      PBP_member=raw.get('PBP_member'), PBP_field=raw.get('PBP_field'),
                      PBP_pointer=raw.get('PBP_pointer_within_rx'), PBP_raw=raw.get('PBP_raw'),
                      PBP_numeric_basis=raw.get('PBP_numeric_basis'), days_supply_raw=raw.get('days_supply_raw'),
                      tier_raw=raw.get('tier_raw'))
        state, entity = raw['status'], 'drug_cost_named_source_comparison'
    elif table == 'snapshot_bridge':
        fields.update(source_drug_table=raw.get('table'), held_monthly=raw.get('held_monthly'),
                      quarterly=raw.get('quarterly'), exact_native_bytes_agree=raw.get('exact_native_bytes_agree'))
        entity = 'drug_cost_snapshot_bridge'
    elif table in ('price_plan_coverage', 'schedule_plan_coverage'):
        fields.update({key: val for key, val in raw.items() if key != 'offering_id'})
        entity = 'drug_cost_plan_source_accounting'
    elif table == 'missing_formulary_prices':
        fields.update(raw)
        entity, state = 'drug_price_gap', 'missing_published_price_in_snapshot'
    else:
        fields.update(control_key=raw.get('key'), control_value=raw.get('value'))
        entity = 'drug_cost_source_control'
    yield DomainProjection(row, entity, f'L06:{row.record_id}', fields, value_state=state)
