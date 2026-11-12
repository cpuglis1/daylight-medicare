"""Published 2026 L05 source-preserving research adapter; no acceptance implied."""
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


LAYER_ID = 'L05'
BASE = 'docs/data/l05-drug-coverage-2026-10-25'
CONTROL_HASHES = {'build-r3/manifest.json': '0c69fd3f698893fe6a25ba3532b1db39a1b9f7fa1c6bc899222d0481aab04364', 'condition-assessment-r1/manifest.json': '64a520ebfa05f794cd019dec7580c99ae2224214f85241a419ad5825c04743c3', 'closeout-r1/build-r5/manifest.json': '6b6e796ef5b98ef1f8b38d152ac836afbe279d2f348066071ec315b5aa12a87d'}
SOURCE_SPECS = ({'relative_path': 'build-r3/inventory.sqlite3', 'format': 'sqlite', 'table': None, 'control': 'build-r3/manifest.json'}, {'relative_path': 'build-r3/coverage.json', 'format': 'json', 'table': 'base_coverage', 'control': 'build-r3/manifest.json'}, {'relative_path': 'build-r3/field-map.json', 'format': 'json', 'table': 'base_field_map', 'control': 'build-r3/manifest.json'}, {'relative_path': 'build-r3/source-members.json', 'format': 'json', 'table': 'base_source_members', 'control': 'build-r3/manifest.json'}, {'relative_path': 'build-r3/source-row-accounting.json', 'format': 'json', 'table': 'base_source_accounting', 'control': 'build-r3/manifest.json'}, {'relative_path': 'condition-assessment-r1/condition-contexts.csv.gz', 'format': 'csv_gzip', 'table': 'condition_contexts', 'control': 'condition-assessment-r1/manifest.json'}, {'relative_path': 'condition-assessment-r1/documents.json', 'format': 'json', 'table': 'condition_documents', 'control': 'condition-assessment-r1/manifest.json'}, {'relative_path': 'condition-assessment-r1/plan-condition-matrix.json', 'format': 'json', 'table': 'condition_plan_matrix', 'control': 'condition-assessment-r1/manifest.json'}, {'relative_path': 'condition-assessment-r1/assessment.json', 'format': 'json', 'table': 'condition_assessment', 'control': 'condition-assessment-r1/manifest.json'}, {'relative_path': 'closeout-r1/build-r5/condition-reference-links.jsonl.gz', 'format': 'jsonl_gzip', 'table': 'condition_reference_links', 'control': 'closeout-r1/build-r5/manifest.json'}, {'relative_path': 'closeout-r1/build-r5/criteria-comparisons.jsonl.gz', 'format': 'jsonl_gzip', 'table': 'criteria_comparisons', 'control': 'closeout-r1/build-r5/manifest.json'}, {'relative_path': 'closeout-r1/build-r5/criteria-sections.jsonl.gz', 'format': 'jsonl_gzip', 'table': 'criteria_sections', 'control': 'closeout-r1/build-r5/manifest.json'}, {'relative_path': 'closeout-r1/build-r5/documents.json', 'format': 'json', 'table': 'criteria_documents', 'control': 'closeout-r1/build-r5/manifest.json'}, {'relative_path': 'closeout-r1/build-r5/plans.json', 'format': 'json', 'table': 'closeout_plans', 'control': 'closeout-r1/build-r5/manifest.json'}, {'relative_path': 'closeout-r1/build-r5/quantity-code-mapping.json', 'format': 'json', 'table': 'quantity_code_mapping', 'control': 'closeout-r1/build-r5/manifest.json'}, {'relative_path': 'closeout-r1/build-r5/quantity-query-evidence.json', 'format': 'json', 'table': 'quantity_query_evidence', 'control': 'closeout-r1/build-r5/manifest.json'}, {'relative_path': 'closeout-r1/build-r5/quantity-statements.json', 'format': 'json', 'table': 'quantity_statements', 'control': 'closeout-r1/build-r5/manifest.json'}, {'relative_path': 'closeout-r1/build-r5/quantity-units.jsonl.gz', 'format': 'jsonl_gzip', 'table': 'quantity_units', 'control': 'closeout-r1/build-r5/manifest.json'}, {'relative_path': 'closeout-r1/build-r5/coverage.json', 'format': 'json', 'table': 'closeout_coverage', 'control': 'closeout-r1/build-r5/manifest.json'})


def _modeled(modeled, key):
    return modeled.get(key, {}).get('value')


def project_record(row):
    raw = row.raw
    table = row.source_table
    fields = {'benefit_year': 2026, 'source_table': table,
              'source_component': str(Path(row.source_path).parent).split(BASE + '/')[-1]}
    identifier = raw.get('offering_id')
    _offering(fields, identifier)
    conditions = []
    state = 'source_observed'
    suffix = ''
    if table == 'plans':
        payload = _payload(raw)
        fields.update(formulary_id=raw.get('formulary_id'), formulary_version=payload.get('formulary_version'),
                      plan_name=payload.get('name'), product_kind=payload.get('kind'),
                      suppressed=payload.get('suppressed'), basic_rows=payload.get('basic_rows'),
                      supplemental_source_grain=payload.get('supplemental_source_grain'))
        entity = 'offering_formulary'
    elif table == 'drug_identities':
        payload = _payload(raw)
        fields.update(rxcui=raw['rxcui'], drug_name=payload.get('name'), dose_form=payload.get('dose_form'),
                      ingredient_strength_description=payload.get('ingredient_strength_description'),
                      related_brand=payload.get('related_brand'), concept_type=payload.get('type'),
                      coverage_inferred=False)
        entity = 'drug_product'
    elif table == 'drug_rows':
        source = _payload(raw, 'raw_json')
        modeled = _payload(raw, 'modeled_json')
        basic = raw['table_name'] == 'basic'
        fields.update(source_drug_table=raw['table_name'], native_source_ordinal=raw['ordinal'],
                      formulary_id=raw.get('formulary_id'), formulary_version=source.get('FORMULARY_VERSION'),
                      rxcui=raw.get('rxcui'), ndc=raw.get('ndc'), contract_id=raw.get('contract_id'),
                      plan_id=raw.get('plan_id'), supplemental_identity_grain=None if basic else 'contract_plan_without_segment',
                      tier=_modeled(modeled, 'TIER_LEVEL_VALUE' if basic else 'TIER'),
                      prior_authorization=_modeled(modeled, 'PRIOR_AUTHORIZATION_YN' if basic else 'PRIOR_AUTH_YN'),
                      step_therapy=_modeled(modeled, 'STEP_THERAPY_YN'),
                      quantity_limit=_modeled(modeled, 'QUANTITY_LIMIT_YN'),
                      quantity_amount_decimal=_number(_modeled(modeled, 'QUANTITY_LIMIT_AMOUNT')),
                      quantity_days=_modeled(modeled, 'QUANTITY_LIMIT_DAYS'),
                      selected_drug=_modeled(modeled, 'SELECTED_DRUG_YN'),
                      physical_quantity_unit=None, physical_unit_state='not_supplied_by_CMS_source',
                      modeled_field_states={key: val.get('state') for key, val in modeled.items()})
        entity = 'formulary_drug_observation' if basic else 'supplemental_drug_observation'
        conditions = {'prior_authorization': fields['prior_authorization'], 'step_therapy': fields['step_therapy'],
                      'quantity_limit': fields['quantity_limit'], 'complete_criteria_not_inferred': True}
    elif table == 'condition_gaps':
        fields.update(source_drug_table=raw['table_name'], native_source_ordinal=raw['ordinal'],
                      missing_fact=raw['missing_fact'], source_needed=raw['source_needed'])
        entity, state = 'drug_condition_gap', 'missing_CMS_condition_detail'
    elif table == 'benefit_context':
        payload = _payload(raw)
        fields.update(member=payload.get('member'), source_pointer=payload.get('pointer'),
                      rx_context=payload.get('rx'), interpretation=payload.get('interpretation'))
        entity = 'drug_benefit_context'
    elif table == 'condition_contexts':
        fields.update(source_drug_table=raw['table'], native_source_ordinal=int(raw['source_row']),
                      rxcui=raw.get('rxcui'), formulary_id=raw.get('formulary_id'),
                      contract_id=raw.get('contract_id') or None, plan_id=raw.get('plan_id') or None,
                      missing_fact=raw['missing_CMS_detail'], resolution_state=raw['resolution_state'],
                      affected_offering_ids=json.loads(raw['affected_offering_ids']),
                      candidate_document_ids=json.loads(raw['candidate_document_ids']),
                      source_needed=raw.get('additional_source_needed'))
        entity, state = 'drug_condition_source_assessment', raw['resolution_state']
    elif table == 'condition_reference_links':
        fields.update(source_drug_table=raw['table'], native_source_ordinal=raw['source_row'],
                      formulary_id=raw.get('formulary_id'), rxcui=raw.get('rxcui'),
                      missing_fact=raw.get('fact'), condition_kind=raw.get('kind'))
        links = raw.get('plan_links') or [None]
        for index, link in enumerate(links, 1):
            linked = dict(fields)
            if link is not None:
                _offering(linked, link.get('offering_id'))
                linked.update(source_state=link.get('source_state'), locator_state=link.get('locator_state'),
                              current_document_ids=link.get('current_full_document_ids', []),
                              earlier_document_ids=link.get('earlier_full_document_ids', []),
                              named_section_locator_candidates=link.get('named_section_locator_candidates', []),
                              questionnaire_ids=link.get('matching_questionnaire_ids', []),
                              September_continuity_asserted=link.get('September_continuity_asserted'),
                              personal_approval=False)
            yield DomainProjection(row, 'drug_condition_reference', f'L05:{row.record_id}:plan-link:{index}', linked,
                                   value_state=linked.get('source_state') or 'unbound_source_context',
                                   source_use_state='source_access_STOP' if 'STOP' in str(linked.get('source_state')) else 'existing_source_policy_applies',
                                   conditions={'locator_state': linked.get('locator_state'), 'no_snapshot_backdating': True})
        return
    elif table == 'quantity_units':
        fields.update(source_drug_table=raw['table'], native_source_ordinal=raw['source_row'],
                      formulary_id=raw.get('formulary_id'), rxcui=raw.get('rxcui'),
                      quantity_amount_decimal=_number(raw.get('quantity_amount_raw')),
                      quantity_days_decimal=_number(raw.get('quantity_days_raw')), physical_quantity_unit=raw.get('unit'),
                      unit_evidence=raw.get('evidence', []), other_dated_limits=raw.get('other_dated_carrier_limits', []),
                      unresolved_reason=raw.get('unresolved_reason'), validity=raw.get('validity'))
        entity, state = 'drug_quantity_unit_observation', raw['state']
    elif table == 'criteria_sections':
        fields.update(section_id=raw['section_id'], document_id=raw['document_id'], title=raw.get('title'),
                      printed_product_scope=raw.get('printed_product_scope'), criteria_text=raw['full_text'],
                      pdf_page_start=raw.get('pdf_page_start'), pdf_page_end=raw.get('pdf_page_end'),
                      text_sha256=raw.get('text_sha256'), source_product_binding='source_printed_scope_only')
        entity = 'drug_policy_section'
    elif table == 'criteria_comparisons':
        fields.update(current_document_id=raw.get('current_document_id'), archived_document_id=raw.get('archived_document_id'),
                      normalized_title=raw.get('normalized_title'), before_section_ids=raw.get('before_section_ids'),
                      after_section_ids=raw.get('after_section_ids'),
                      September_continuity_inferred=raw.get('September_continuity_inferred'))
        entity, state = 'drug_policy_comparison', raw['comparison_state']
    elif table in ('criteria_documents', 'condition_documents'):
        fields.update(document_id=raw.get('id') or raw.get('source_id'), document_kind=raw.get('kind') or raw.get('content_kind'),
                      family=raw.get('family'), formulary_id=raw.get('formulary_id'),
                      formulary_version=raw.get('formulary_version'), full_criteria=raw.get('full_criteria'),
                      declared_date=raw.get('declared_date') or raw.get('document_effective_or_updated_date'),
                      applicability_state=raw.get('applicability_state'), page_count=raw.get('page_count'),
                      full_text_path=raw.get('full_text_path'), full_text_sha256=raw.get('full_text_sha256'))
        entity = 'drug_policy_document'
    elif table in ('closeout_plans', 'condition_plan_matrix'):
        fields.update(formulary_id=raw.get('formulary_id'), formulary_version=raw.get('formulary_version'),
                      plan_name=raw.get('name'), condition_source_state=raw.get('condition_source_state'),
                      criteria_state=raw.get('criteria_state'), current_dated_criteria=raw.get('current_dated_criteria'),
                      earlier_dated_criteria=raw.get('earlier_dated_criteria'),
                      candidate_document_ids=raw.get('candidate_document_ids'), clinical_approval=False,
                      CMS_snapshot_backdating_assumed=False)
        entity, state = 'offering_condition_source_state', raw.get('condition_source_state') or 'unaccepted_snapshot_condition_binding'
    elif table == 'quantity_statements':
        fields.update(statement_id=raw.get('statement_id'), source_document_id=raw.get('source_id'),
                      product_label=raw.get('product_label'), formulary_ids=raw.get('formulary_ids'),
                      quantity_amount_decimal=_number(raw.get('amount')), quantity_days=raw.get('days'),
                      physical_quantity_unit=raw.get('unit'), physical_unit_raw=raw.get('unit_raw'),
                      limit_text=raw.get('limit_text'), pdf_page=raw.get('pdf_page'), tier=raw.get('tier'))
        entity = 'drug_quantity_statement'
    elif table in ('quantity_code_mapping', 'quantity_query_evidence'):
        fields.update(local_evidence_id=raw.get('key'), evidence=raw.get('value'))
        entity = 'drug_product_alias_evidence'
    else:
        fields.update(control_key=raw.get('key'), control_value=raw.get('value'))
        entity = 'drug_coverage_source_control'
    yield DomainProjection(row, entity, f'L05:{row.record_id}{suffix}', fields, value_state=state,
                           source_use_state='source_access_STOP' if 'STOP' in str(state) else 'existing_source_policy_applies',
                           conditions=conditions)
