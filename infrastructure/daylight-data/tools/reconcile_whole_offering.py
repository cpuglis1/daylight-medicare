#!/usr/bin/env python3
"""Additive, offline H5652-002 interpretation/reconciliation review producer.

Frozen r11 is input only. Native source decoding, producer interpretation,
cross-source comparison, independent review and acceptance are separate fields.
No source acquisition, database access, model call or application import.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import xml.etree.ElementTree as ET

VERSION = 'l03-whole-offering-reconciliation/1'
OFFERING = '2026:H5652:002:000'
R11 = Path('docs/data/l03-ma-benefits-2026-11-01-whole-offering-r11/source-preparation')
R12 = Path('docs/data/l03-ma-benefits-2026-11-02-whole-offering-r12')
MANIFEST_SHA = '1e686ef4eb6688616a28573ea898088dd597caa9f7f7a19b9dfdb99e656e8cd5'
CANONICAL_SHA = '872c969620487f130b62ba77fbe760440fdcfa163176056f1e891dcb691c3080'
CMS_SHA = 'e40e423ec93ffecbd482ecc3c707ba53654bf522ac2d58cea720799f0080d52f'
EXPECTED = {'claim': 1778, 'condition': 2897}
HOLDS = ['published_display', 'personal_comparison', 'ranking', 'recommendation', 'quote', 'enrollment']
EOC_SHA = '7602dc081bd6d615dac7f43d3739234668e5701c5464cc89d061ac1f46ae75ba'
SB_SHA = '4da5fb8e022fde082317606d85f22bec561315c7fbf197d3b06944e9d960439d'


class ReconciliationError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def load(path):
    with path.open(encoding='utf-8') as stream:
        return json.load(stream)


def write_new(path, value, *, jsonl=False, compressed=False):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    raw = (''.join(canonical(row) + '\n' for row in value) if jsonl else canonical(value) + '\n').encode()
    if compressed:
        raw = gzip.compress(raw, compresslevel=6, mtime=0)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def json_pointer(document, pointer):
    if pointer == '':
        return document
    if not isinstance(pointer, str) or not pointer.startswith('/'):
        raise ReconciliationError('Invalid exact source JSON pointer')
    current = document
    for key in pointer[1:].split('/'):
        key = key.replace('~1', '/').replace('~0', '~')
        current = current[int(key)] if isinstance(current, list) else current[key]
    return current


def checked_inputs(repository):
    base = repository / R11
    manifest_path = base / 'SOURCE_PREPARATION_MANIFEST.json'
    if file_sha(manifest_path) != MANIFEST_SHA:
        raise ReconciliationError('Frozen r11 manifest changed')
    manifest = load(manifest_path)
    for relative, binding in manifest['files'].items():
        path = base / relative
        if path.resolve().is_relative_to(base.resolve()) is False:
            raise ReconciliationError('Input escapes exact frozen packet')
        if path.stat().st_size != binding['bytes'] or file_sha(path) != binding['sha256']:
            raise ReconciliationError('Frozen r11 member changed: ' + relative)
    capture = base / 'generated-r2'
    if file_sha(capture / 'offering-canonical.jsonl.gz') != CANONICAL_SHA:
        raise ReconciliationError('Selected canonical bytes changed')
    with gzip.open(capture / 'offering-canonical.jsonl.gz', 'rt') as stream:
        rows = [json.loads(line) for line in stream]
    if Counter(row['kind'] for row in rows) != Counter(EXPECTED):
        raise ReconciliationError('Offering denominator changed')
    if len({row['id'] for row in rows}) != 4675 or any(
        row['offering_id'] != OFFERING or row['accepted_for_reference'] is not False for row in rows
    ):
        raise ReconciliationError('Offering identity/acceptance changed')
    if Counter(state for row in rows for state in row['states']) != Counter({
        'evidence_reconciliation_pending': 4659, 'required_evidence_missing': 16
    }):
        raise ReconciliationError('Frozen missing/pending state changed')
    cms = load(capture / 'CMS-native-member.json')
    if file_sha(capture / 'CMS-native-member.json') != CMS_SHA:
        raise ReconciliationError('CMS member changed')
    native = {}
    receipt = load(capture / 'NATIVE_LOOKUP_RECEIPT.json')
    for batch in receipt['batches']:
        path = capture / batch['path']
        if file_sha(path) != batch['sha256']:
            raise ReconciliationError('Native batch changed')
        with gzip.open(path, 'rt') as stream:
            envelope = json.load(stream)
        kind = batch['kind']
        target = native.setdefault(kind, {})
        for record in envelope['records']:
            raw = record['raw_payload']
            if digest(raw) != record['raw_sha256']:
                raise ReconciliationError('Native raw-payload digest changed')
            key = tuple(raw.get(k, '') for k in ('parent_id', 'child_id', 'relation', 'source_id')) if kind == 'native_relationships' else raw.get('id', raw.get('source_id'))
            if key in target and target[key]['raw_payload'] != raw:
                raise ReconciliationError('Conflicting native repeated key')
            target[key] = record
    expected_native = {'native_observations': 6577, 'native_sources': 2806,
                       'native_clauses': 2141, 'native_relationships': 2476}
    if {key: len(value) for key, value in native.items()} != expected_native:
        raise ReconciliationError('Full native source population changed')
    with gzip.open(capture / 'carrier-pages.jsonl.gz', 'rt') as stream:
        pages = [json.loads(line) for line in stream]
    return rows, native, cms, pages, {'path': str(R11 / 'SOURCE_PREPARATION_MANIFEST.json'),
                                     'sha256': MANIFEST_SHA, 'members_verified': len(manifest['files'])}


def parse_payload(record):
    raw = record['raw_payload']
    return raw, json.loads(raw['payload']) if isinstance(raw.get('payload'), str) else raw.get('payload', {})


def scalar_state(value):
    if value is None:
        return {'state': 'source_null', 'value': None, 'negative_or_zero_inferred': False}
    if value == '':
        return {'state': 'source_blank', 'value': '', 'negative_or_zero_inferred': False}
    return {'state': 'source_present', 'value': value, 'negative_or_zero_inferred': False}


def interpret_observation(record, clauses, cms):
    """Decode source-local meaning; never transfer an enum between formats."""
    raw, payload = parse_payload(record)
    result = {'id': raw['id'], 'layer': raw['layer'], 'source_id': raw['source_id'],
              'representation_id': raw['unit_id'], 'raw_payload_sha256': record['raw_sha256'],
              'source_record_ordinal': record['source_row_ordinal'],
              'complete_native_payload': payload, 'independent_interpretation_review': None}
    layer = raw['layer']
    if layer == 'cms_json':
        pointer = payload['locator']['pointer']
        actual = json_pointer(cms, pointer)
        if actual != payload['raw']:
            raise ReconciliationError('CMS pointer/raw mismatch at ' + pointer)
        result['source_meaning'] = {'kind': payload['source_role'], 'native_json_path': pointer,
            'native_value': scalar_state(actual),
            'interpretation': 'The exact named native selection, component or ordered schedule, with enclosing controls. No flat-table enum mapping is applied.',
            'format_mapping_review_required': True}
    elif layer == 'cms_table':
        normalized = payload['normalized']
        state = normalized['state']
        if state == 'unresolved_code':
            meaning = 'The published question has this raw code; its source code meaning remains unresolved.'
        else:
            meaning = 'Source-local answer to the exact official CMS question; scope remains the original table/category/package/group and field.'
        result['source_meaning'] = {'kind': 'official_question_answer',
            'question': payload['dictionary_question'], 'field': payload['locator']['field'],
            'raw_answer': payload['raw'], 'normalized_answer': normalized,
            'interpretation': meaning, 'applies_to_native_json': False,
            'unknown_code_is_negative': False}
    elif layer == 'carrier_clause':
        clause_id = payload['clause_id']
        clause_raw, clause = parse_payload(clauses[clause_id])
        if hashlib.sha256(clause['quote'].encode()).hexdigest() != payload['quote_sha256']:
            raise ReconciliationError('Carrier clause quotation mismatch')
        result['source_meaning'] = {'kind': 'carrier_proposition', 'clause_id': clause_id,
            'quote': clause['quote'], 'logical_parent': clause['parent_sentence'],
            'relation': clause['relation'], 'source_column': clause['source_column'],
            'condition_families': clause.get('condition_families', []),
            'list_intro': clause.get('list_intro'),
            'source_fragments': clause['source_fragments'],
            'parent_source_fragments': clause['parent_source_fragments'],
            'interpretation': 'The proposition is interpreted only within its exact logical parent, list antecedent, printed column and service context. Extraction is not independent printed-source verification.'}
    elif layer == 'carrier_list_intro':
        result['source_meaning'] = {'kind': 'inherited_carrier_list_condition',
            'quote': payload['quote'], 'member_clause_id': payload['member_clause_id'],
            'intro_clause_ids': payload['intro_clause_ids'], 'source_fragments': payload['source_fragments'],
            'interpretation': 'This list antecedent qualifies the member proposition; it is not a separate unconditional benefit.'}
    elif layer == 'cms_named_amount':
        pointer = payload['source'].get('pointer')
        if pointer:
            actual = json_pointer(cms, pointer)
            if actual != payload['raw']:
                raise ReconciliationError('Named amount pointer mismatch')
        result['source_meaning'] = {'kind': 'published_named_amount',
            'field': payload['field'], 'value': payload['value'], 'unit': payload['unit'],
            'network': payload['network'], 'period': payload['period'],
            'qualifications': payload['qualifications'], 'native_json_path': pointer,
            'source_value_state': payload['value_state'], 'raw_value': payload['raw'],
            'locator': payload['source'],
            'original_json_pointer_replayed': bool(pointer),
            'interpretation': 'Named amount and enclosing activation/category/accounting rules are inseparable.'}
    elif layer == 'cms_json_narrative':
        original = json_pointer(cms, payload['locator']['pointer'])
        start, end = payload['source_character_range']
        if original[start:end] != payload['quote']:
            raise ReconciliationError('CMS narrative quote mismatch')
        result['source_meaning'] = {'kind': 'CMS_narrative_condition', 'quote': payload['quote'],
            'native_json_path': payload['locator']['pointer'], 'complete_original_value': original,
            'interpretation': 'Preserve each procedure, distinct lookback/reset and full enclosing rider context; no uniform category frequency is inferred.'}
    elif layer == 'named_source_requirement':
        result['source_meaning'] = {'kind': 'required_missing_evidence',
            'closure_evidence': payload.get('closure_evidence'), 'next_action': payload.get('next_action'),
            'interpretation': 'This is a retained requirement, not supporting evidence. The required-missing state stays open.'}
    else:
        raise ReconciliationError('Unknown source layer: ' + str(layer))
    return result


def source_service_contexts(row, observations, cms):
    service_ids = row['context'].get('service_ids', [])
    result = {}
    def add(pointer, variant, origin):
        service = json_pointer(cms, pointer)
        key = (variant, service['categoryCode'], service['categoryTypeId'], pointer)
        context = result.setdefault(key, {'variant': variant, 'category_code': service['categoryCode'],
            'category_type_id': service['categoryTypeId'], 'pointer': pointer,
            'object_sha256': digest(service), 'binding_origins': [],
            'scope_verified_from_native_observation': False,
            'scope_does_not_override_original_table_package_controls': True})
        context['binding_origins'].append(origin)
        if origin.startswith('native_json_observation:'):
            context['scope_verified_from_native_observation'] = True
    for service_id in service_ids:
        if service_id.startswith(OFFERING + ':benefitDetails:'):
            add('/pbp/0/benefitDetails/benefitDetailsInfo/' + service_id.rsplit(':', 1)[1], 'base', 'inherited_canonical_service_ids')
    for oid in row['observation_ids']:
        _, payload = parse_payload(observations[oid])
        pointer = payload.get('locator', {}).get('pointer') or payload.get('source', {}).get('pointer')
        if pointer and '/benefitPackages/' in pointer:
            root = pointer.split('/benefitPackages/')[0]
            index = pointer.split('/benefitPackages/')[1].split('/')[0]
            rider = json_pointer(cms, root)
            add(root + '/benefitPackages/' + index, 'optional_rider:' + rider['optSupPkgId'], 'native_json_observation:' + oid)
        elif pointer and '/benefitDetailsInfo/' in pointer:
            root, suffix = pointer.split('/benefitDetailsInfo/', 1)
            add(root + '/benefitDetailsInfo/' + suffix.split('/')[0], 'base', 'native_json_observation:' + oid)
    return [result[key] for key in sorted(result)]


def record_pages(row, interpretations):
    result = set()
    for oid in row['observation_ids']:
        meaning = interpretations[oid]['source_meaning']
        for fragment in meaning.get('source_fragments', []):
            loc = fragment['locator']
            result.add((loc['kind'], loc['pdf_page']))
    return sorted(result)


def ocr_lines(words):
    """Reproduce retained r7 layout lines while retaining their original boxes."""
    grouped = defaultdict(list)
    for ordinal, word in enumerate(words):
        grouped[(word['block_num'], word['par_num'], word['line_num'])].append((ordinal, word))
    recognized = [{'y': statistics.median(w['top'] + w['height'] / 2 for _, w in values),
                   'words': values} for values in grouped.values()]
    lines = []
    for group in sorted(recognized, key=lambda value: value['y']):
        near = [value for value in lines if abs(value['y'] - group['y']) < 8]
        if near:
            min(near, key=lambda value: abs(value['y'] - group['y']))['words'].extend(group['words'])
        else:
            lines.append(group)
    result = []
    for number, group in enumerate(sorted(lines, key=lambda value: value['y']), 1):
        text, projected = '', []
        for ordinal, word in sorted(group['words'], key=lambda value: value[1]['left']):
            text += ' ' * max(1, round(word['left'] / 9.0) - len(text))
            start = len(text)
            text += word['text']
            projected.append({'word_ordinal': ordinal, 'start': start, 'end': len(text),
                              'left': word['left'], 'top': word['top'], 'width': word['width'],
                              'height': word['height'], 'text': word['text'], 'confidence': word['conf']})
        result.append({'line': number, 'y_150dpi': group['y'], 'text': text, 'words': projected})
    return result


def proposed_glyph_decode(text, *, bold=False, symbol=False):
    """Diagnostic only: retain the original; do not claim repaired printed truth."""
    if symbol:
        return None
    substitutions = {'_': 'a', '?': 'A'}
    if bold:
        substitutions['Y'] = 'a'
    return ''.join(substitutions.get(char, chr(ord(char) + 1) if 33 <= ord(char) <= 125 else char)
                   for char in text)


def capture_layout(repository, output):
    """Read original PDF font/coordinates and retained OCR, without expected CMS."""
    checked_inputs(repository)
    source = repository / 'docs/data/l03-ma-benefits-2026-10-25/source-reconciliation-r7/new-source-pages.jsonl.gz'
    retained = {}
    with gzip.open(source, 'rt') as stream:
        for line in stream:
            row = json.loads(line)
            if row['document_sha256'] not in {SB_SHA, EOC_SHA}:
                continue
            lines = ocr_lines(row['ocr_words'])
            if '\n'.join(item['text'] for item in lines) != row['layout_text']:
                raise ReconciliationError('Original OCR line reconstruction mismatch')
            retained[(row['document_sha256'], row['pdf_page'])] = {
                'document_sha256': row['document_sha256'], 'physical_page': row['pdf_page'],
                'layout_text_sha256': row['layout_text_sha256'], 'lines': lines}
    if len(retained) != 206:
        raise ReconciliationError('Original OCR page census mismatch')
    pdf = repository / 'docs/data/l03-ma-benefits-2026-10-25/source-reconciliation-r7/acquisition/raw' / EOC_SHA
    if file_sha(pdf) != EOC_SHA:
        raise ReconciliationError('Original EOC PDF changed')
    command = ['/opt/homebrew/bin/pdftohtml', '-xml', '-hidden', '-i', '-stdout', str(pdf)]
    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=120)
    if len(process.stdout) > 16 * 1024 * 1024:
        raise ReconciliationError('Unexpected PDF font-coordinate output size')
    root = ET.fromstring(process.stdout)
    bindings = {'original-pdf-font-coordinate-xml.json.gz': write_new(
        output / 'original-pdf-font-coordinate-xml.json.gz',
        {'xml': process.stdout.decode('utf-8')}, compressed=True)}
    fonts, pages, headings = {}, [], []
    for page in root.findall('page'):
        number = int(page.attrib['number'])
        for font in page.findall('fontspec'):
            fonts[font.attrib['id']] = dict(font.attrib)
        spans = []
        for ordinal, element in enumerate(page.findall('text')):
            raw = ''.join(element.itertext())
            font = fonts[element.attrib['font']]
            bold = element.find('b') is not None
            symbol = 'Symbol' in font['family'] or 'S32' in font['family']
            proposed = proposed_glyph_decode(raw, bold=bold, symbol=symbol)
            span = {'span_ordinal': ordinal, **{key: int(element.attrib[key]) for key in ('top', 'left', 'width', 'height')},
                'font': font, 'bold': bold, 'raw_native_text': raw,
                'glyph_decode_proposal': proposed, 'printed_semantics_verified': False,
                'unresolved_symbol_font': symbol}
            spans.append(span)
        candidate_headings = [span for span in spans if span['bold'] and span['left'] < 420 and
                              240 <= span['top'] < 1040]
        # Bold text is a structural candidate, not automatic service identity.
        # Every page/box remains available for exact original pixel review.
        page_headings = []
        for span in sorted(candidate_headings, key=lambda value: (value['top'], value['left'])):
            if page_headings and span['top'] - page_headings[-1]['bottom'] <= 10:
                page_headings[-1]['native_span_ordinals'].append(span['span_ordinal'])
                page_headings[-1]['proposed_text'] += ' ' + (span['glyph_decode_proposal'] or span['raw_native_text'])
                page_headings[-1]['bottom'] = span['top'] + span['height']
            else:
                page_headings.append({'physical_page': number, 'top': span['top'],
                    'bottom': span['top'] + span['height'], 'left': span['left'],
                    'native_span_ordinals': [span['span_ordinal']],
                    'proposed_text': span['glyph_decode_proposal'] or span['raw_native_text'],
                    'role': 'unreviewed_bold_source_structure', 'service_identity_inferred': False})
        headings.extend(page_headings)
        pages.append({'document_sha256': EOC_SHA, 'physical_page': number,
            'native_coordinate_width': int(page.attrib['width']), 'native_coordinate_height': int(page.attrib['height']),
            'source_spans': spans, 'bold_structure_candidates': page_headings,
            'retained_ocr': retained[(EOC_SHA, number)],
            'decoding_status': 'proposed_font_substitution_only; original pixels control'})
    if len(pages) != 193:
        raise ReconciliationError('Original font-coordinate EOC page count changed')
    bindings['font-aware-pages.jsonl.gz'] = write_new(output / 'font-aware-pages.jsonl.gz', pages, jsonl=True, compressed=True)
    bindings['bold-structure-candidates.json'] = write_new(output / 'bold-structure-candidates.json', headings)
    receipt = {'schema': VERSION + '/original-font-layout', 'original_pdf_sha256': EOC_SHA,
        'pages': len(pages), 'retained_OCR_pages_verified': len(retained), 'bold_candidates': len(headings),
        'bindings': bindings, 'command': command, 'operator_sha256': file_sha(Path(__file__)),
        'native_xml_sha256': hashlib.sha256(process.stdout).hexdigest(),
        'substitution_is_verified_semantics': False, 'CMS_values_used_to_decode': False,
        'producer_prior_CMS_exposure_disclosed': True, 'new_acceptance': False}
    write_new(output / 'LAYOUT_CAPTURE_RECEIPT.json', receipt)
    return receipt


def fragment_words(fragment, page):
    """Return exact retained OCR words touched by a pinned old character span."""
    locator = fragment['locator']
    lines = page['retained_ocr']['lines']
    first, last, number = locator['line_start'], locator['line_end'], fragment['printed_line']
    if not first <= number <= last <= len(lines):
        raise ReconciliationError('Fragment printed-line range changed')
    passage = '\n'.join(line['text'] for line in lines[first - 1:last])
    if hashlib.sha256(passage.encode()).hexdigest() != locator['passage_sha256']:
        raise ReconciliationError('Fragment passage does not equal exact retained source')
    prefix = sum(len(line['text']) + 1 for line in lines[first - 1:number - 1])
    start, end = fragment['start'] - prefix, fragment['end'] - prefix
    line = lines[number - 1]
    if not 0 <= start < end <= len(line['text']):
        raise ReconciliationError('Fragment escaped its declared printed line')
    selected = [word for word in line['words'] if word['start'] < end and word['end'] > start]
    return selected, line


def census_medical_layout(repository, layout, boundary_path, output):
    """Audit all old clauses; produce corrected row/column source-cell candidates.

    Source cells are parents for later atomic interpretation, not assertions of
    verified benefits. New candidate identity and counts are separate from r9.
    """
    rows, native, _, source_pages, input_binding = checked_inputs(repository)
    layout_receipt = load(layout / 'LAYOUT_CAPTURE_RECEIPT.json')
    binding = layout_receipt['bindings']['font-aware-pages.jsonl.gz']
    if file_sha(layout / 'font-aware-pages.jsonl.gz') != binding['sha256']:
        raise ReconciliationError('New layout input changed')
    with gzip.open(layout / 'font-aware-pages.jsonl.gz', 'rt') as stream:
        pages = {row['physical_page']: row for row in map(json.loads, stream)}
    boundaries = load(boundary_path)['rows']
    scopes = sorted(boundaries, key=lambda value: (value['physical_page'], value['native_top']))
    if len(scopes) != 67 or len({row['source_scope_key'] for row in scopes}) != 67:
        raise ReconciliationError('Explicit medical source-row boundary count changed')
    def scope_at(page, y):
        prior = [row for row in scopes if (row['physical_page'], row['native_top'] - 4) <= (page, y)]
        return prior[-1] if prior else None
    cells, word_to_cell = {}, {}
    merged_scope_evidence = defaultdict(list)
    for number in range(44, 113):
        for span in pages[number]['source_spans']:
            if 425 <= span['left'] < 640 and span['left'] + span['width'] > 645 and 245 <= span['top'] < 1045:
                scope = scope_at(number, span['top'] + span['height'] / 2)
                if scope:
                    merged_scope_evidence[scope['source_scope_key']].append({
                        'physical_page': number, 'span_ordinal': span['span_ordinal'],
                        'left': span['left'], 'top': span['top'], 'width': span['width'],
                        'height': span['height'], 'raw_native_text': span['raw_native_text']})
    for number in range(44, 113):
        page = pages[number]
        for line in page['retained_ocr']['lines']:
            y = line['y_150dpi'] * 0.72
            if not 247 <= y < 1045:
                continue
            scope = scope_at(number, y)
            if scope is None:
                continue
            for word in line['words']:
                x = word['left'] * 0.72
                spanning = bool(merged_scope_evidence[scope['source_scope_key']])
                column = ('service_column' if x < 426 else 'merged_cost_columns' if spanning else
                          'cost_in_network' if x < 640 else 'cost_out_of_network')
                key = (scope['source_scope_key'], column)
                candidate_id = 'R12-SOURCE-CELL-' + digest(key)[:24]
                cell = cells.setdefault(key, {'id': candidate_id, 'source_scope': scope,
                    'source_column': column, 'source_words': [], 'source_role': 'corrected_row_column_parent_candidate',
                    'merged_column_native_span_evidence': merged_scope_evidence[scope['source_scope_key']],
                    'atomic_proposition': False, 'printed_meaning_review_complete': False,
                    'accepted_for_reference': False, 'original_to_candidate_mapping_is_acceptance': False})
                cell['source_words'].append({'physical_page': number, 'printed_line': line['line'],
                    **word, 'document_sha256': EOC_SHA})
                word_to_cell[(number, word['word_ordinal'])] = candidate_id
    for cell in cells.values():
        cell['source_text_candidate'] = ' '.join(word['text'] for word in cell['source_words'])
        cell['source_word_count'] = len(cell['source_words'])
        cell['full_source_word_binding_sha256'] = digest(cell['source_words'])
    observation_clauses = {}
    for oid, value in native['native_observations'].items():
        raw, payload = parse_payload(value)
        if raw['layer'] == 'carrier_clause':
            observation_clauses[oid] = payload['clause_id']
    canonical_by_clause = defaultdict(set)
    for row in rows:
        for oid in row['observation_ids']:
            if oid in observation_clauses:
                canonical_by_clause[observation_clauses[oid]].add(row['id'])
    clauses, links = [], []
    for cid, record in sorted(native['native_clauses'].items()):
        _, clause = parse_payload(record)
        scopes_seen, cells_seen, word_refs, source_pages_seen = set(), set(), [], set()
        unmapped = []
        for ordinal, fragment in enumerate(clause['source_fragments']):
            loc = fragment['locator']
            number = loc['pdf_page']
            source_pages_seen.add((loc['kind'], number))
            if loc['document_sha256'] != EOC_SHA or not 44 <= number <= 112:
                unmapped.append({'fragment_ordinal': ordinal, 'reason': 'outside_medical_chart_2D_census'})
                continue
            words, line = fragment_words(fragment, pages[number])
            fragment_cells = set()
            for word in words:
                cell_id = word_to_cell.get((number, word['word_ordinal']))
                if cell_id:
                    fragment_cells.add(cell_id)
                    word_refs.append({'fragment_ordinal': ordinal, 'physical_page': number,
                                      'word_ordinal': word['word_ordinal'], 'candidate_cell_id': cell_id})
            cells_seen.update(fragment_cells)
            for cell_id in fragment_cells:
                scopes_seen.add(next(cell['source_scope']['source_scope_key'] for cell in cells.values() if cell['id'] == cell_id))
            if not fragment_cells:
                unmapped.append({'fragment_ordinal': ordinal, 'reason': 'header_footer_or_outside_cell_area'})
        flags = []
        if len(scopes_seen) > 1:
            flags.append('multiple_distinct_printed_service_rows_in_old_clause')
        if any(cell['id'] in cells_seen and cell['source_column'] == 'merged_cost_columns' for cell in cells.values()) and clause['source_column'].startswith('cost_column'):
            flags.append('old_separate_network_column_touches_printed_merged_cost_cell')
        item = {'old_clause_id': cid, 'old_native_payload_sha256': record['raw_sha256'],
            'old_quote': clause['quote'], 'old_logical_parent': clause['parent_sentence'],
            'old_source_column': clause['source_column'],
            'original_canonical_ids': sorted(canonical_by_clause[cid]),
            'original_source_pages': [{'document_kind': k, 'physical_page': p} for k, p in sorted(source_pages_seen)],
            'original_source_fragments': clause['source_fragments'],
            'printed_row_scope_candidates': sorted(scopes_seen), 'source_cell_candidates': sorted(cells_seen),
            'layout_flags': flags, 'unmapped_fragments': unmapped,
            'census_state': 'layout_risk_identified_requires_atomic_repair' if flags else
                            'medical_2D_layout_scanned_no_multirow_flag' if cells_seen else
                            'outside_medical_2D_census_requires_separate_source_review',
            'semantic_reconciliation_complete': False, 'accepted_for_reference': False}
        clauses.append(item)
        if cells_seen:
            links.append({'old_clause_id': cid, 'old_canonical_ids': sorted(canonical_by_clause[cid]),
                          'candidate_cell_ids': sorted(cells_seen), 'exact_original_word_links': word_refs,
                          'new_cell_is_an_atomic_obligation': False})
    flags = Counter(flag for row in clauses for flag in row['layout_flags'])
    flagged = [row for row in clauses if row['layout_flags']]
    result_bindings = {}
    for name, values in [('complete-clause-layout-census.jsonl.gz', clauses),
                         ('corrected-medical-source-cells.jsonl.gz', sorted(cells.values(), key=lambda value: value['id'])),
                         ('original-to-corrected-source-cells.jsonl.gz', links)]:
        result_bindings[name] = write_new(output / name, values, jsonl=True, compressed=True)
    receipt = {'schema': VERSION + '/medical-layout-census', 'input_binding': input_binding,
        'boundary_binding': {'path': str(boundary_path), 'sha256': file_sha(boundary_path)},
        'layout_binding': {'path': str(layout), 'receipt_sha256': file_sha(layout / 'LAYOUT_CAPTURE_RECEIPT.json')},
        'all_native_clauses_accounted': len(clauses), 'census_states': dict(Counter(row['census_state'] for row in clauses)),
        'layout_flags': dict(flags), 'flagged_old_clauses': len(flagged),
        'affected_original_canonical_ids': len({cid for row in flagged for cid in row['original_canonical_ids']}),
        'original_required_claims_conditions': EXPECTED, 'original_required_total': 4675,
        'original_ids_or_denominator_changed': False, 'required_missing_predicates': 16,
        'new_source_parent_cells': len(cells), 'new_atomic_obligations_proposed': 0,
        'new_required_obligations_adopted': 0,
        'source_parents_are_not_atomic_obligations': True,
        'all_offering_defects_repaired': False, 'whole_offering_reconciliation_complete': False,
        'new_accepted': 0, 'bindings': result_bindings, 'operator_sha256': file_sha(Path(__file__))}
    write_new(output / 'LAYOUT_DEFECT_CENSUS_RECEIPT.json', receipt)
    return receipt


def validate_atomic_source_proposal(spec, cells):
    if spec['kind'] not in {'claim', 'condition'} or not spec['statement'].strip():
        raise ReconciliationError('Atomic repair must name its claim/condition')
    if spec.get('independent_review') is not None or spec.get('accepted_for_reference') is not False:
        raise ReconciliationError('Producer cannot invent interpretation review or acceptance')
    if not spec.get('source_cell_ids') or not spec.get('exact_source_anchors'):
        raise ReconciliationError('Atomic repair needs exact source parents and textual anchors')
    selected = [cells[identifier] for identifier in spec['source_cell_ids']]
    for cell in selected:
        if digest(cell['source_words']) != cell['full_source_word_binding_sha256']:
            raise ReconciliationError('Atomic source word binding changed')
    for anchor in spec['exact_source_anchors']:
        if not isinstance(anchor, str) or not anchor.strip() or not any(
                anchor in cell['source_text_candidate'] for cell in selected):
            raise ReconciliationError('Repair source anchor not present: ' + spec['key'] + ': ' + str(anchor))
    return selected


def materialize_atomic_repairs(repository, census_path, spec_path, output):
    """Bind manually interpreted new propositions to exact corrected source cells.

    Candidate units are additive. No old ID is retired or quietly made an alias;
    the review packet records proposed correspondence separately.
    """
    original_rows, _, _, _, input_binding = checked_inputs(repository)
    receipt = load(census_path / 'LAYOUT_DEFECT_CENSUS_RECEIPT.json')
    for name, binding in receipt['bindings'].items():
        if file_sha(census_path / name) != binding['sha256']:
            raise ReconciliationError('Layout census input changed')
    def read_rows(name):
        with gzip.open(census_path / name, 'rt') as stream:
            return list(map(json.loads, stream))
    cells = {row['id']: row for row in read_rows('corrected-medical-source-cells.jsonl.gz')}
    census = read_rows('complete-clause-layout-census.jsonl.gz')
    manual = load(spec_path)
    if manual['offering_id'] != OFFERING or manual['accepted_for_reference'] is not False:
        raise ReconciliationError('Atomic repair identity/acceptance mismatch')
    if manual['source_parent_sha256'] != receipt['bindings']['corrected-medical-source-cells.jsonl.gz']['sha256']:
        raise ReconciliationError('Manual interpretation source-parent binding mismatch')
    specs = manual['units']
    keys = [row['key'] for row in specs]
    if len(keys) != len(set(keys)):
        raise ReconciliationError('Duplicate atomic repair key')
    result, by_key = [], {}
    for spec in specs:
        selected = validate_atomic_source_proposal(spec, cells)
        evidence = []
        for cell in selected:
            evidence.append({'source_cell_id': cell['id'],
                'source_word_binding_sha256': cell['full_source_word_binding_sha256'],
                'source_column': cell['source_column'], 'source_scope': cell['source_scope'],
                'exact_source_word_count': cell['source_word_count'],
                'physical_pages': sorted({word['physical_page'] for word in cell['source_words']}),
                'original_pdf_sha256': EOC_SHA})
        material = {'kind': spec['kind'], 'statement': spec['statement'],
                    'structured_meaning': spec['structured_meaning'], 'evidence': evidence}
        identifier = 'R12-PROPOSED-' + digest(material)[:28]
        row = {'id': identifier, 'key': spec['key'], 'offering_id': OFFERING, **material,
            'exact_source_anchors': spec.get('exact_source_anchors', []),
            'condition_keys': spec.get('condition_keys', []),
            'comparison_questions': spec['comparison_questions'],
            'atomicity_state': 'producer_proposed_complete_assertion_or_material_predicate',
            'independent_atomicity_review': None, 'independent_interpretation_review': None,
            'complete_meaning_reconciliation_complete': False,
            'accepted_for_reference': False, 'consumer_purposes': {purpose: 'held' for purpose in HOLDS}}
        result.append(row); by_key[spec['key']] = row
    if len({row['id'] for row in result}) != len(result):
        raise ReconciliationError('Duplicate semantic repair proposal; use one unit with explicit aliases')
    for row in result:
        row['condition_ids'] = []
        for key in row['condition_keys']:
            if key not in by_key or by_key[key]['kind'] != 'condition':
                raise ReconciliationError('Repair condition key missing or not condition')
            row['condition_ids'].append(by_key[key]['id'])
    by_cell = defaultdict(list)
    for row in result:
        for evidence in row['evidence']:
            by_cell[evidence['source_cell_id']].append(row['id'])
    affected, mappings = set(), []
    for clause in census:
        if not clause['layout_flags']:
            continue
        affected.update(clause['original_canonical_ids'])
        mappings.append({'original_clause_id': clause['old_clause_id'],
            'original_canonical_ids': clause['original_canonical_ids'],
            'original_quote': clause['old_quote'], 'layout_findings': clause['layout_flags'],
            'source_part_correspondence': [{'source_cell_id': cell_id,
                'new_proposed_unit_ids': sorted(by_cell[cell_id]),
                'correspondence_state': 'exact_source_parent_bound; semantic replacement requires independent review'}
                for cell_id in clause['source_cell_candidates']],
            'old_id_retired': False, 'new_mapping_accepted': False})
    uncovered = sorted({cell_id for row in mappings for item in row['source_part_correspondence']
                        if not item['new_proposed_unit_ids'] for cell_id in [item['source_cell_id']]})
    old_kinds = Counter(row['kind'] for row in original_rows if row['id'] in affected)
    proposed_kinds = Counter(row['kind'] for row in result)
    bindings = {'proposed-atomic-units.jsonl.gz': write_new(output / 'proposed-atomic-units.jsonl.gz', result, jsonl=True, compressed=True),
        'old-to-proposed-unit-correspondence.json': write_new(output / 'old-to-proposed-unit-correspondence.json', mappings)}
    summary = {'schema': VERSION + '/atomic-repair-proposal', 'input_binding': input_binding,
        'census_receipt_sha256': file_sha(census_path / 'LAYOUT_DEFECT_CENSUS_RECEIPT.json'),
        'manual_spec_sha256': file_sha(spec_path), 'operator_sha256': file_sha(Path(__file__)),
        'before': {'original_required': EXPECTED, 'original_total': 4675, 'required_missing': 16,
                   'layout_flagged_clauses': len(mappings), 'layout_affected_required_ids': dict(old_kinds)},
        'after': {'original_ids_preserved': 4675, 'original_ids_retired': 0,
                  'new_atomic_candidates': dict(proposed_kinds), 'new_atomic_candidate_total': len(result),
                  'unreviewed_additive_union_count': 4675 + len(result),
                  'new_required_obligations_adopted': 0, 'required_missing_unchanged': 16},
        'uncovered_flagged_source_parent_ids': uncovered,
        'every_flagged_source_parent_has_a_specific_proposal': not uncovered,
        'all_source_defects_repaired_and_reviewed': False,
        'correspondence_is_semantic_equivalence': False,
        'whole_offering_reconciliation_complete': False, 'new_accepted': 0,
        'bindings': bindings}
    write_new(output / 'ATOMIC_REPAIR_RECEIPT.json', summary)
    return summary


def propose_table_control(observation, rules):
    """Keep dictionary-format meanings and source-type repairs explicit.

    The manual rules identify question/component scope. They do not turn an
    equal scalar, screen illustration or code-position into semantic agreement.
    """
    if observation['layer'] != 'cms_table':
        raise ReconciliationError('Clinical table review requires original table observation')
    payload = observation['complete_native_payload']
    field = payload['locator']['field']
    question = payload['dictionary_question']
    normalized = payload['normalized']
    matched = [rule for rule in rules if any(re.fullmatch(pattern, field)
                                           for pattern in rule['exact_field_patterns'])]
    for rule in matched:
        if rule['independent_review'] is not None or rule['accepted_for_reference'] is not False:
            raise ReconciliationError('Manual control cannot invent review or acceptance')
    unit_proposal = None
    if normalized['state'] == 'typed_numeric':
        if re.fullmatch(r'(?:Begin|End) Day Interval \d+', question):
            unit_proposal = {'original_unit': normalized.get('unit'), 'proposed_unit': 'day_index',
                'basis': 'exact official table question names a day endpoint, not a monetary amount',
                'raw_value': payload['raw'], 'new_value': normalized['value'],
                'numeric_value_changed': False, 'independent_review': None}
        elif question == 'Number of Routine Foot Care visits':
            unit_proposal = {'original_unit': normalized.get('unit'), 'proposed_unit': 'visit_count',
                'basis': 'exact official table question names a number of visits',
                'raw_value': payload['raw'], 'new_value': normalized['value'],
                'numeric_value_changed': False, 'independent_review': None}
    return {'observation_id': observation['id'], 'field': field, 'question': question,
        'locator': payload['locator'], 'raw_value': payload['raw'],
        'original_normalized_answer': normalized, 'source_type_correction': unit_proposal,
        'manual_rule_ids': [rule['id'] for rule in matched],
        'manual_comparisons': [{key: rule[key] for key in
            ('id', 'producer_comparison', 'outcome_basis', 'material_holds', 'comparison_scope',
             'carrier_physical_pages') if key in rule}
            for rule in matched],
        'comparison_work_remaining': [] if matched else [
            'Exact question/subtype answer is retained; complete carrier mapping has not been authored for this field.'],
        'native_JSON_code_mapping_applied': False, 'complete_meaning_agreement': False,
        'independent_review': None, 'accepted_for_reference': False}


def combine_full_width_source_parent(cells, scope_key):
    """Rejoin exact words in an explicitly reviewed full-width paragraph.

    This operation is source-parent geometry repair, never atomic meaning or
    permission. It cannot be applied to ordinary table rows without a separate
    manually specified scope; that would mix service and price columns.
    """
    if scope_key != 'EOC-044-0250' or len(cells) != 3:
        raise ReconciliationError('Only the reviewed full-width chart instruction is allowed')
    words = {}
    for cell in cells:
        if cell['source_scope']['source_scope_key'] != scope_key:
            raise ReconciliationError('Full-width source scope mismatch')
        if digest(cell['source_words']) != cell['full_source_word_binding_sha256']:
            raise ReconciliationError('Full-width source word binding changed')
        for word in cell['source_words']:
            key = (word['physical_page'], word['word_ordinal'])
            if key in words:
                raise ReconciliationError('Duplicate source word in full-width union')
            words[key] = word
    ordered = sorted(words.values(), key=lambda w: (w['physical_page'], w['printed_line'], w['start']))
    text = ' '.join(word['text'] for word in ordered)
    return {'id': 'R12-FULL-WIDTH-PARENT-' + digest(ordered)[:24],
        'offering_id': OFFERING, 'original_pdf_sha256': EOC_SHA,
        'source_scope': cells[0]['source_scope'], 'source_column': 'full_width_paragraph',
        'source_words': ordered, 'full_source_word_binding_sha256': digest(ordered),
        'source_text_candidate': text, 'source_word_count': len(ordered),
        'original_geometry_parent_ids': sorted(cell['id'] for cell in cells),
        'geometry_explanation': 'Printed instruction spans the complete chart width above the first medical service row. '
                                'The three earlier x-coordinate strips are historical geometry outputs; '
                                'they are not independent semantic service/cost cells here.',
        'word_union_has_no_additions_deletions_duplicates': len(ordered) == sum(len(c['source_words']) for c in cells),
        'atomic_proposition': False, 'printed_meaning_review_complete': False,
        'accepted_for_reference': False}


def prepare_sb_source_repairs(repository, spec_path, output):
    """Bind hand-authored SB meanings to exact independently selected words.

    The original extraction remains historical. Split bullet lists and monetary
    rows use explicit page/line/x regions reviewed against original pixels;
    ordinary reading-order concatenation is never accepted as a service identity.
    """
    checked_inputs(repository)
    packet = repository / R12
    expected_pages = {}
    with gzip.open(repository / R11 / 'generated-r2/carrier-pages.jsonl.gz', 'rt') as stream:
        for row in map(json.loads, stream):
            if row['document_sha256'] == SB_SHA:
                expected_pages[row['pdf_page']] = row
    pages = {}
    retained_path = repository / 'docs/data/l03-ma-benefits-2026-10-25/source-reconciliation-r7/new-source-pages.jsonl.gz'
    with gzip.open(retained_path, 'rt') as stream:
        for row in map(json.loads, stream):
            if row['document_sha256'] != SB_SHA:
                continue
            expected = expected_pages[row['pdf_page']]
            legacy_digest = hashlib.sha256(json.dumps(row['ocr_words'], sort_keys=True,
                separators=(',', ':'), allow_nan=False).encode()).hexdigest()
            if legacy_digest != expected['ocr_words_sha256'] or row['layout_text_sha256'] != expected['layout_text_sha256']:
                raise ReconciliationError('Original SB words/geometry changed from frozen r11 binding')
            lines = ocr_lines(row['ocr_words'])
            if '\n'.join(line['text'] for line in lines) != row['layout_text']:
                raise ReconciliationError('Original SB line reconstruction changed')
            pages[row['pdf_page']] = {'retained_ocr': {'lines': lines}}
    manual = load(spec_path)
    if manual['offering_id'] != OFFERING or manual['original_SB_sha256'] != SB_SHA:
        raise ReconciliationError('SB manual source identity mismatch')
    units, by_key = [], {}
    for spec in manual['units']:
        if spec['key'] in by_key or spec['kind'] not in {'claim', 'condition', 'source_context'}:
            raise ReconciliationError('Duplicate/invalid SB proposed source unit')
        if spec['accepted_for_reference'] is not False or spec['independent_review'] is not None:
            raise ReconciliationError('SB proposal cannot invent acceptance or independent review')
        words = {}
        for region in spec['regions']:
            for line in pages[region['page']]['retained_ocr']['lines']:
                if region['line_start'] <= line['line'] <= region['line_end']:
                    for word in line['words']:
                        if region['x_min'] <= word['left'] < region['x_max']:
                            words[(region['page'], word['word_ordinal'])] = {
                                **word, 'physical_page': region['page'], 'printed_line': line['line'],
                                'document_sha256': SB_SHA}
        if not words:
            raise ReconciliationError('SB proposal has no selected source words')
        ordered = sorted(words.values(), key=lambda w: (w['physical_page'], w['printed_line'], w['start']))
        material = {'kind': spec['kind'], 'statement': spec['statement'],
                    'structured_meaning': spec['structured_meaning'],
                    'source_word_binding_sha256': digest(ordered)}
        unit = {'id': 'R12-SB-PROPOSED-' + digest(material)[:28], 'key': spec['key'],
            'offering_id': OFFERING, **material, 'source_regions': spec['regions'],
            'exact_source_words': ordered, 'exact_source_text_in_region_reading_order': ' '.join(w['text'] for w in ordered),
            'condition_keys': spec['condition_keys'], 'context_keys': spec.get('context_keys', []),
            'semantic_obligation_candidate': spec['kind'] in {'claim', 'condition'},
            'independent_review': None, 'accepted_for_reference': False,
            'atomicity_review_required': True, 'complete_meaning_reconciliation_complete': False,
            'consumer_purposes': {purpose: 'held' for purpose in HOLDS}}
        units.append(unit); by_key[spec['key']] = unit
    for unit in units:
        unit['condition_ids'] = []
        for key in unit['condition_keys']:
            if key not in by_key or by_key[key]['kind'] != 'condition':
                raise ReconciliationError('SB condition dependency missing or not a condition')
            unit['condition_ids'].append(by_key[key]['id'])
        unit['context_ids'] = [by_key[key]['id'] for key in unit['context_keys']]
    by_word = defaultdict(set)
    for unit in units:
        for word in unit['exact_source_words']:
            by_word[(word['physical_page'], word['word_ordinal'])].add(unit['id'])
    with gzip.open(packet / 'layout-defect-census-r2/complete-clause-layout-census.jsonl.gz', 'rt') as stream:
        clauses = list(map(json.loads, stream))
    mappings = []
    for clause in clauses:
        fragments = [f for f in clause['original_source_fragments'] if f['locator']['document_sha256'] == SB_SHA]
        if not fragments:
            continue
        selected_words, matches, unbound = set(), defaultdict(set), set()
        for fragment in fragments:
            page_number = fragment['locator']['pdf_page']
            selected, _ = fragment_words(fragment, pages[page_number])
            for word in selected:
                key = (page_number, word['word_ordinal']); selected_words.add(key)
                if key not in by_word:
                    unbound.add(key)
                for identifier in by_word[key]:
                    matches[identifier].add(key)
        mappings.append({'original_clause_id': clause['old_clause_id'],
            'original_canonical_ids': clause['original_canonical_ids'], 'original_quote': clause['old_quote'],
            'original_source_fragments': fragments,
            'proposed_source_unit_correspondences': [{'proposed_unit_id': key,
                'exact_shared_source_word_count': len(value),
                'source_word_keys': sorted(value), 'semantic_equivalence_asserted': False}
                for key, value in sorted(matches.items())],
            'original_quote_word_count': len(selected_words), 'unbound_original_word_keys': sorted(unbound),
            'all_original_words_have_manual_parent_or_context': not unbound,
            'candidate_multi_scope_correspondence_requires_review': len(matches) > 1,
            'old_required_id_retired': False, 'independent_review': None,
            'complete_meaning_reconciliation_complete': False})
    bindings = {
        'proposed-SB-source-units.jsonl.gz': write_new(output / 'proposed-SB-source-units.jsonl.gz', units, jsonl=True, compressed=True),
        'old-SB-clause-to-proposed-units.jsonl.gz': write_new(output / 'old-SB-clause-to-proposed-units.jsonl.gz', mappings, jsonl=True, compressed=True)}
    receipt = {'schema': VERSION + '/SB-source-repair', 'operator_sha256': file_sha(Path(__file__)),
        'manual_spec_sha256': file_sha(spec_path), 'original_SB_sha256': SB_SHA,
        'original_SB_OCR_pages_exactly_verified_against_r11': len(pages),
        'proposed_units': len(units), 'kinds': dict(Counter(r['kind'] for r in units)),
        'old_SB_clauses_all_scoped_census': len(mappings),
        'old_SB_clauses_with_manual_source_correspondences': sum(bool(r['proposed_source_unit_correspondences']) for r in mappings),
        'old_SB_clauses_wholly_within_manual_source_regions': sum(r['all_original_words_have_manual_parent_or_context'] for r in mappings),
        'old_SB_clauses_with_multiple_candidate_meaning_units': sum(r['candidate_multi_scope_correspondence_requires_review'] for r in mappings),
        'before_original_required': 4675, 'after_original_required_unchanged': 4675,
        'new_proposed_SB_candidates': sum(r['semantic_obligation_candidate'] for r in units),
        'source_context_parents_not_additional_semantic_obligations': sum(not r['semantic_obligation_candidate'] for r in units),
        'new_required_adopted': 0,
        'required_missing_unchanged': 16, 'original_quotes_preserved': True,
        'all_meaning_reconciled': False, 'independent_review_complete': False,
        'new_acceptance': False, 'bindings': bindings}
    write_new(output / 'SB_SOURCE_REPAIR_RECEIPT.json', receipt)
    return receipt


def exact_pos_group(cms, group_id):
    """Resolve a literal UUID to its own source group, without amount matching."""
    prefix = '/pbp/0/costShareGroups/pointOfServiceGroups/pointOfServiceGroupsDetails/posGroupsData'
    groups = json_pointer(cms, prefix)
    matches = [(index, group) for index, group in enumerate(groups) if group['groupId'] == group_id]
    if len(matches) != 1:
        raise ReconciliationError('Exact native POS UUID is missing or duplicated')
    index, group = matches[0]
    return {'source_pointer': prefix + '/' + str(index), 'group_id': group_id,
        'complete_native_group': group, 'native_group_sha256': digest(group),
        'proposed_reference_role': 'point_of_service_cost_sharing_group_reference',
        'shared_dollar_allowance_inferred': False, 'ordinary_unrestricted_OON_inferred': False,
        'all_original_controls_and_blank_values_retained': True,
        'independent_full_meaning_review': None, 'accepted_for_reference': False}


def interpret_native_control(observation, cms, field_rules, table_by_field):
    """Return component-specific producer proposals, never a permission flag."""
    if observation['layer'] != 'cms_json':
        raise ReconciliationError('Native control review requires exact JSON observation')
    payload = observation['complete_native_payload']
    pointer, raw = payload['locator']['pointer'], payload['raw']
    if json_pointer(cms, pointer) != raw:
        raise ReconciliationError('Native review exact pointer/raw mismatch')
    match = re.match(r'^/pbp/0/benefitDetails/benefitDetailsInfo/(\d+)/benefitDetails/', pointer)
    if not match:
        raise ReconciliationError('Native clinical control outside exact service scope')
    service_index = int(match[1])
    service = cms['pbp'][0]['benefitDetails']['benefitDetailsInfo'][service_index]
    field = pointer.rsplit('/', 1)[1]
    if field not in field_rules:
        raise ReconciliationError('Unauthored native field: ' + field)
    rule = field_rules[field]
    parent_pointer = pointer.rsplit('/', 1)[0]
    parent = json_pointer(cms, parent_pointer)
    proposed = {'kind': rule['kind'], 'source_interpretation': rule['source_interpretation'],
                'raw_preserved': raw, 'independent_review': None}
    holds = []
    if rule['kind'] in {'currency_literal', 'percentage_literal', 'day_endpoint_literal', 'count_literal'}:
        if isinstance(raw, bool) or not isinstance(raw, (int, str)) or raw == '':
            raise ReconciliationError('Nonliteral native quantity must remain unknown')
        number = Decimal(str(raw))
        if rule['kind'] in {'day_endpoint_literal', 'count_literal'} and number != number.to_integral():
            raise ReconciliationError('Fractional native day/count value')
        proposed.update(value=str(raw), unit=rule['unit'], source_precision_preserved=True)
    elif rule['kind'] == 'named_binary_control':
        proposed['proposed_label'] = rule['proposed_codes'].get(str(raw))
        proposed['official_native_enum_dictionary_supplied'] = False
        if proposed['proposed_label'] is None:
            holds.append('UNMAPPED_EXACT_NATIVE_CONTROL_CODE')
    elif rule['kind'] == 'literal_checkbox':
        if type(raw) is not bool:
            raise ReconciliationError('Nonboolean native checkbox')
        proposed['value'] = raw
    elif rule['kind'] == 'exact_group_reference':
        if not isinstance(raw, str) or not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', raw):
            raise ReconciliationError('Native group reference is not exact UUID')
        proposed['group_id'] = raw
        proposed['exact_source_group'] = exact_pos_group(cms, raw)
        holds.append('SOURCE_ROLE_CORRECTION_SHARED_BUDGET_TO_POS_GROUP_PROPOSED')
    elif rule['kind'] == 'component_cost_mode':
        aggregate = 'CopayMultiServiceLocationComponent/CopayMutliServiceCopay/' in pointer
        proposed['aggregate_presence_question'] = aggregate
        proposed['proposed_mode'] = ({'1': 'copayment_present', '2': 'copayment_not_selected'}.get(str(raw))
                                    if aggregate else rule['proposed_modes'].get(str(raw)))
        proposed['all_named_amount_siblings'] = {key: value for key, value in parent.items()
            if key != field and ('Amount' in key or key.endswith('Amt'))}
        if proposed['proposed_mode'] is None:
            holds.append('UNMAPPED_COMPONENT_COST_MODE')
        if not aggregate:
            amounts = proposed['all_named_amount_siblings']
            if str(raw) == '1' and not any(value not in ('', None) for key, value in amounts.items()
                                        if 'Min' not in key and 'Max' not in key):
                holds.append('SELECTED_SCALAR_MODE_HAS_NO_RETAINED_SCALAR')
            if str(raw) == '3' and not (any('Min' in key and value not in ('', None) for key, value in amounts.items())
                                      and any('Max' in key and value not in ('', None) for key, value in amounts.items())):
                holds.append('SELECTED_RANGE_MODE_HAS_MISSING_ENDPOINT')
        proposed['official_native_enum_dictionary_supplied'] = False
    elif rule['kind'] == 'insulin_monthly_cap':
        if service['categoryCode'] != '15-1' or '/CoinsuranceComponent/' not in pointer:
            raise ReconciliationError('Monthly cap proposal outside exact insulin component')
        proposed.update(value=str(Decimal(str(raw))), unit=rule['unit'],
            source_native_name_preserved=field, question_basis='PBP11–15 instrument physical195; flat monthlycap; EOCPartBinsulin')
        holds.append('CONTEXT_SPECIFIC_FIELD_NAME_TO_MONTHLY_QUESTION_MAPPING_PROPOSED')
    elif rule['kind'] == 'ambulance_two_question_component':
        if service['categoryCode'] != '10a' or not any('/' + name + '/' in pointer for name in
                ['CoinAdmissionWaivedHospitalComponent', 'CopayAdmissionWaivedHospitalComponent']):
            raise ReconciliationError('Ambulance field-role proposal outside exact component')
        proposed['question_role'] = ('financial_component_present' if field == 'admissionWaivedYesNo'
                                     else 'financial_component_waived_on_hospital_admission')
        proposed['proposed_label'] = {'1': 'Yes', '2': 'No'}.get(str(raw))
        proposed['source_native_name_preserved'] = field
        holds.append('MISLEADING_NATIVE_FIELD_ROLE_CORRECTION_PROPOSED')
    elif rule['kind'] == 'category_specific_question':
        specific = {'11a': ('preferred_DME_vendors_or_manufacturers', 'pbp_b11a_dme_pref_vend_man_yn'),
                    '11c': ('diabetic_supplies_manufacturer_restriction', 'pbp_b11c_dme_limit_manufact_yn'),
                    '15-1': ('insulin_cost_share_counts_to_plan_level_deductible', 'mrx_b_ira_deduct_yn')}
        if service['categoryCode'] not in specific:
            raise ReconciliationError('Generic question has no authored category-specific meaning')
        proposed['question_role'], proposed['exact_flat_field_candidate'] = specific[service['categoryCode']]
        proposed['proposed_label'] = {'1': 'Yes', '2': 'No'}.get(str(raw))
        holds.append('CONTEXT_SPECIFIC_GENERIC_QUESTION_MAPPING_PROPOSED')
    elif rule['kind'] == 'contextual_period_code':
        contextual = {'bdBenefitUnlimitedPeriodicity': {'3': 'Every year (routinefootcare only)'},
                      'bdCopayObservationServicePeriodicity': {'1': 'Per day (observation only)'},
                      'bdMedInpatientHospitalAcuteBenefitPeriod': {'1': 'Original Medicare (SNF)',
                                                                 '3': 'Per admission or stay (acute/psychiatric costcontrol)'}}
        proposed['proposed_contextual_label'] = contextual[field].get(str(raw))
        holds.append('CONTEXT_SPECIFIC_PERIOD_AND_COVERED_DAY_MAPPING_PROPOSED')
    else:
        raise ReconciliationError('Unhandled authored native rule kind')
    flat_fields = []
    if 'flat_category_suffix_candidate' in rule and service['categoryTypeId'] == 1:
        category = service['categoryCode']
        prefix = 'mrx_b' if category == '15' else 'mrx_b_ira' if category == '15-1' else 'pbp_b' + category
        flat_fields.append(prefix + '_' + rule['flat_category_suffix_candidate'])
    if proposed.get('exact_flat_field_candidate'):
        flat_fields.append(proposed['exact_flat_field_candidate'])
    pairs = []
    for candidate in flat_fields:
        for original in table_by_field.get(candidate, []):
            flat = original['complete_native_payload']
            same_raw = raw == flat['raw']
            pairs.append({'observation_id': original['id'], 'field': candidate,
                'question': flat['dictionary_question'], 'raw': flat['raw'],
                'normalized_answer': flat['normalized'], 'locator': flat['locator'],
                'literal_codes_equal': same_raw,
                'semantic_equivalence_asserted': False})
            if not same_raw:
                holds.append('PAIRED_NATIVE_FLAT_CODES_DIFFER_REQUIRES_SOURCE_SCOPE_REVIEW')
    return {'observation_id': observation['id'], 'source_pointer': pointer,
        'source_field': field, 'source_raw': raw, 'original_source_role': payload['source_role'],
        'native_service_context': {'index': service_index, 'categoryCode': service['categoryCode'],
                                   'categoryTypeId': service['categoryTypeId']},
        'complete_native_parent_component': parent, 'native_parent_sha256': digest(parent),
        'producer_proposed_typed_meaning': proposed, 'same_category_flat_question_candidates': pairs,
        'specific_mapping_holds': sorted(set(holds)), 'official_native_enum_dictionary_supplied': False,
        'independent_interpretation_review': None, 'complete_meaning_reconciliation_complete': False,
        'accepted_for_reference': False, 'consumer_purposes': {purpose: 'held' for purpose in HOLDS}}


def build_native_review(repository, output):
    _, _, cms, _, frozen_binding = checked_inputs(repository)
    packet = repository / R12
    work = load(packet / 'UNRESOLVED_WORKLIST_R2.json')['groups']['clinical_medical_source_adapters']['records']
    selected = {q['observation_id'] for row in work for q in row['source_observations']}
    with gzip.open(packet / 'case-comparisons-r2/source-interpretations.jsonl.gz', 'rt') as stream:
        all_observations = list(map(json.loads, stream))
    table_by_field = defaultdict(list)
    for row in all_observations:
        if row['layer'] == 'cms_table':
            table_by_field[row['complete_native_payload']['locator']['field']].append(row)
    spec_path = packet / 'clinical-native-format-spec-r1.json'
    manual = load(spec_path)
    if manual['offering_id'] != OFFERING or manual['source_release_accepted'] is not False:
        raise ReconciliationError('Native manual source identity/release mismatch')
    records = [interpret_native_control(row, cms, manual['fields'], table_by_field)
               for row in all_observations if row['layer'] == 'cms_json' and row['id'] in selected]
    if len(records) != 392 or len({r['source_field'] for r in records}) != 58:
        raise ReconciliationError('Exact selected native clinical population changed')
    binding = write_new(output / 'clinical-native-format-reviews.jsonl.gz', records, jsonl=True, compressed=True)
    receipt = {'schema': VERSION + '/clinical-native-format-review', 'frozen_input_binding': frozen_binding,
        'manual_spec_sha256': file_sha(spec_path), 'operator_sha256': file_sha(Path(__file__)),
        'native_observations': len(records), 'distinct_native_leaf_fields': 58,
        'typed_source_kinds': dict(Counter(r['producer_proposed_typed_meaning']['kind'] for r in records)),
        'mapping_hold_counts': dict(Counter(code for row in records for code in row['specific_mapping_holds'])),
        'same_category_flat_question_pairs': sum(len(r['same_category_flat_question_candidates']) for r in records),
        'paired_literal_code_differences': sum(not p['literal_codes_equal'] for r in records
                                              for p in r['same_category_flat_question_candidates']),
        'exact_POS_group_reference_joins': sum('exact_source_group' in r['producer_proposed_typed_meaning'] for r in records),
        'distinct_exact_POS_group_UUIDs': len({r['producer_proposed_typed_meaning']['group_id'] for r in records
                                               if 'group_id' in r['producer_proposed_typed_meaning']}),
        'before_original_required': 4675, 'after_original_required_unchanged': 4675,
        'required_missing_unchanged': 16, 'new_required_adopted': 0,
        'all_source_semantics_reconciled': False, 'new_acceptance': False,
        'bindings': {'clinical-native-format-reviews.jsonl.gz': binding}}
    write_new(output / 'NATIVE_FORMAT_REVIEW_RECEIPT.json', receipt)
    return receipt


def clinical_review_legacy_r1(repository, output):
    """Build exact-ID clinical review, preserving its still-unresolved work.

    Manual printed readings, layout repair proposals and control comparisons
    remain separate artifacts. A source-parent correspondence is never treated
    as a reviewed semantic replacement for an old required obligation.
    """
    _, _, _, _, frozen_binding = checked_inputs(repository)
    packet = repository / R12
    def rows(name):
        with gzip.open(packet / name, 'rt') as stream:
            return list(map(json.loads, stream))
    old = {r['canonical_id']: r for r in rows('case-comparisons-r2/per-id-reconciliation.jsonl.gz')}
    observations = {r['id']: r for r in rows('case-comparisons-r2/source-interpretations.jsonl.gz')}
    census = {r['old_clause_id']: r for r in rows('layout-defect-census-r2/complete-clause-layout-census.jsonl.gz')}
    cells = {r['id']: r for r in rows('layout-defect-census-r2/corrected-medical-source-cells.jsonl.gz')}
    readings = load(packet / 'clinical-source-readings-r1.json')
    pixels = load(packet / 'clinical-pixel-inspection-r1.json')
    if pixels['medical_source_readings_sha256'] != file_sha(packet / 'clinical-source-readings-r1.json'):
        raise ReconciliationError('Manual source readings changed after pixel receipt')
    pixel_pages = {}
    for binding in pixels['inspected_medical_source_pages']:
        if file_sha(repository / binding['path']) != binding['sha256']:
            raise ReconciliationError('Inspected original-page render changed')
        pixel_pages[binding['physical_page']] = binding
    reading_by_cell = {}
    for reading in readings['readings']:
        if (reading['offering_id'] != OFFERING or reading['accepted_for_reference'] is not False
                or reading['all_material_conditions_independently_reviewed'] is not False):
            raise ReconciliationError('Clinical reading has invented identity/review/acceptance')
        if not set(reading['physical_pages']).issubset(pixel_pages):
            raise ReconciliationError('Clinical reading lacks original-page pixel inspection')
        for bound in reading['source_cells']:
            cell = cells[bound['id']]
            if (cell['full_source_word_binding_sha256'] != bound['source_words_sha256']
                    or cell['source_text_candidate'] != bound['full_exact_text']):
                raise ReconciliationError('Manual reading changed its exact source parent')
            reading_by_cell[bound['id']] = reading
    rules = load(packet / 'clinical-control-comparison-r1.json')['rules']
    worklist = load(packet / 'UNRESOLVED_WORKLIST_R2.json')
    original_ids = {r['canonical_id'] for r in worklist['groups']['clinical_medical_source_adapters']['records']}
    handoff_file = packet / 'post-freeze-carrier-dental-review/clinical-neighbor-handoff.json'
    handoff = load(handoff_file)
    neighbor_ids = {r['canonical_id'] for r in handoff}
    if (len(original_ids) != 2090 or len(neighbor_ids) != 51
            or len(original_ids & neighbor_ids) != 16 or len(neighbor_ids - original_ids) != 35):
        raise ReconciliationError('Clinical ownership/handoff exact population changed')
    selected_ids = sorted(original_ids | neighbor_ids)
    controls, control_by_obs = [], {}
    for identifier in sorted({q for c in selected_ids for q in old[c]['source_native_observation_ids']}):
        observation = observations[identifier]
        if observation['layer'] == 'cms_table':
            control = propose_table_control(observation, rules)
            controls.append(control); control_by_obs[identifier] = control
    repairs = rows('medical-atomic-repairs-r1/proposed-atomic-units.jsonl.gz')
    proposed_by_cell = defaultdict(list)
    for repair in repairs:
        for bound in repair['evidence']:
            proposed_by_cell[bound['source_cell_id']].append(repair['id'])
    result = []
    for identifier in selected_ids:
        record = old[identifier]
        source_details, reading_ids, repair_ids, issue_codes = [], set(), set(), set()
        clauses, flags = [], []
        for obs_id in record['source_native_observation_ids']:
            observation = observations[obs_id]
            layer = observation['layer']
            payload = observation['complete_native_payload']
            detail = {'observation_id': obs_id, 'layer': layer,
                'raw_payload_sha256': observation['raw_payload_sha256'],
                'source_native_meaning': observation['source_meaning']}
            if layer == 'carrier_clause':
                clause_id = payload['clause_id']
                clause = census[clause_id]
                clauses.append(clause_id); flags.extend(clause['layout_flags'])
                detail['exact_old_quote'] = clause['old_quote']
                detail['original_fragments_and_context'] = payload
                detail['source_parent_correspondence'] = []
                for cell_id in clause['source_cell_candidates']:
                    reading = reading_by_cell.get(cell_id)
                    reading_id = reading['id'] if reading else None
                    if reading_id:
                        reading_ids.add(reading_id)
                    repair_ids.update(proposed_by_cell[cell_id])
                    detail['source_parent_correspondence'].append({'source_cell_id': cell_id,
                        'manual_reading_id': reading_id,
                        'proposed_repair_unit_ids': sorted(proposed_by_cell[cell_id]),
                        'semantic_equivalence_asserted': False})
                if clause['layout_flags']:
                    issue_codes.add('ORIGINAL_QUOTE_LAYOUT_REPAIR_REQUIRED')
                if not detail['source_parent_correspondence']:
                    issue_codes.add('SOURCE_OUTSIDE_CURRENT_MEDICAL_2D_REPAIR')
            elif layer == 'cms_table':
                control = control_by_obs[obs_id]
                detail['manual_control_comparison'] = control
                if control['source_type_correction']:
                    issue_codes.add('ORIGINAL_NUMERIC_UNIT_CORRECTION_PROPOSED')
                if control['comparison_work_remaining']:
                    issue_codes.add('EXACT_TABLE_FIELD_MAPPING_NOT_YET_AUTHORED')
            elif layer == 'cms_json':
                detail['native_format_hold'] = 'No unreviewed flat-table enum or UI-screen-order conversion is applied.'
                issue_codes.add('NATIVE_FORMAT_MAPPING_REVIEW_REQUIRED')
            source_details.append(detail)
        if not reading_ids and any(q['layer'].startswith('carrier') for q in source_details):
            issue_codes.add('SB_OR_GLOBAL_SOURCE_READING_REQUIRED')
        if flags and not repair_ids:
            issue_codes.add('NO_CURRENT_CLINICAL_REPAIR_UNIT_FOR_FLAGGED_QUOTE')
        result.append({'schema': VERSION + '/clinical-exact-id-review',
            'canonical_id': identifier, 'kind': record['kind'], 'offering_id': OFFERING,
            'original_required_state': record['original_states'],
            'original_canonical_sha256': record['canonical_sha256'],
            'original_predicate': record['predicate'], 'original_subject': record['subject'],
            'original_material_context': record['material_source_context'],
            'original_linked_canonical_ids': record['linked_canonical_ids'],
            'complete_source_proposition_sibling_ids': record['complete_source_proposition_sibling_ids'],
            'source_scoped_relationships': record['source_scoped_relationships'],
            'original_source_pages': record['source_pages'],
            'source_assessments': source_details,
            'manual_printed_reading_ids': sorted(reading_ids),
            'specific_proposed_repair_unit_ids': sorted(repair_ids),
            'issue_codes': sorted(issue_codes), 'layout_flags': sorted(set(flags)),
            'ownership': 'clinical_neighbor_transferred_for_additive_review' if identifier in neighbor_ids - original_ids
                         else 'original_clinical_worklist',
            'producer_proposed_review_state': 'specific_source_reading_and_repair_bound' if reading_ids
                                              else 'specific_native_source_controls_retained_or_unmapped',
            'comparison_outcome': 'insufficient_evidence',
            'complete_meaning_reconciliation_complete': False,
            'independent_review': None, 'new_acceptance': False,
            'accepted_for_reference': False,
            'consumer_purposes': {purpose: 'held' for purpose in HOLDS}})
    bindings = {
        'clinical-per-id-review.jsonl.gz': write_new(output / 'clinical-per-id-review.jsonl.gz', result, jsonl=True, compressed=True),
        'clinical-native-table-comparisons.jsonl.gz': write_new(output / 'clinical-native-table-comparisons.jsonl.gz', controls, jsonl=True, compressed=True)}
    summary = {'schema': VERSION + '/clinical-review-receipt', 'frozen_input_binding': frozen_binding,
        'original_required_offering': EXPECTED, 'original_required_count_unchanged': 4675,
        'original_missing_count_unchanged': 16, 'original_clinical_worklist_ids': len(original_ids),
        'dental_clinical_neighbor_handoff_unique_ids': len(neighbor_ids),
        'dental_clinical_neighbors_already_in_clinical_worklist': len(original_ids & neighbor_ids),
        'dental_clinical_neighbors_transferred': len(neighbor_ids - original_ids),
        'exact_unique_reviewed_ids': len(result), 'kinds': dict(Counter(r['kind'] for r in result)),
        'manual_source_reading_count': len(readings['readings']),
        'manual_material_conditions_count': sum(len(r['material_conditions']) for r in readings['readings']),
        'original_pdf_pages_in_pixel_receipt': len(pixel_pages),
        'unique_table_observations': len(controls),
        'table_observations_with_manual_comparisons': sum(bool(r['manual_rule_ids']) for r in controls),
        'table_observations_with_source_unit_repairs': sum(bool(r['source_type_correction']) for r in controls),
        'issue_counts': dict(Counter(code for r in result for code in r['issue_codes'])),
        'ids_with_source_parent_reading': sum(bool(r['manual_printed_reading_ids']) for r in result),
        'all_ids_full_meaning_reconciled': False, 'independent_review_complete': False,
        'whole_offering_pilot_complete': False, 'new_accepted': 0,
        'manual_and_ownership_inputs': {str(path.relative_to(packet)): file_sha(path) for path in [
            packet / 'UNRESOLVED_WORKLIST_R2.json', handoff_file,
            packet / 'clinical-source-readings-r1.json', packet / 'clinical-pixel-inspection-r1.json',
            packet / 'clinical-control-comparison-r1.json']},
        'operator_sha256': file_sha(Path(__file__)), 'bindings': bindings}
    write_new(output / 'CLINICAL_REVIEW_RECEIPT.json', summary)
    return summary




def prepare_repeated_footer_readings(repository, output):
    """Recover complete QMB/Medicaid footer parents without merging cost cells."""
    checked_inputs(repository)
    packet = repository / R12
    source_path = repository / 'docs/data/l03-ma-benefits-2026-10-25/source-reconciliation-r7/new-source-pages.jsonl.gz'
    parents = []
    with gzip.open(source_path, 'rt') as stream:
        for page in map(json.loads, stream):
            if page['document_sha256'] != EOC_SHA or not 44 <= page['pdf_page'] <= 112:
                continue
            lines = ocr_lines(page['ocr_words'])
            starts = [i for i, line in enumerate(lines) if 'Qualified' in line['text'] and '(QMB)' in line['text']]
            if len(starts) != 1:
                raise ReconciliationError('Repeated footer needs exact unique QMB paragraph start')
            selected = lines[starts[0]:starts[0] + 3]
            text = ' '.join(word['text'] for line in selected for word in line['words'])
            if not text.endswith('Original Medicare.') or 'may be less' not in text:
                raise ReconciliationError('Incomplete repeated footer source paragraph')
            words = [{**w, 'physical_page': page['pdf_page'], 'printed_line': line['line'], 'document_sha256': EOC_SHA}
                     for line in selected for w in line['words']]
            parents.append({'id': 'R12-COMPLETE-FOOTER-' + digest(words)[:28],
                'physical_page': page['pdf_page'], 'original_pdf_sha256': EOC_SHA,
                'complete_full_width_paragraph_text': text, 'exact_source_words': words,
                'source_word_binding_sha256': digest(words), 'source_parent_not_atomic_obligation': True})
    if len(parents) != 69:
        raise ReconciliationError('Exact 69 chart footer parent population changed')
    # The source readings are hand-authored and deliberately retain modal "may".
    meanings = [
        {'id': 'R12-FOOTER-MAY-REDUCE', 'kind': 'claim',
         'statement': 'For services covered under Original Medicare, deductible, coinsurance and/or copayment may be less when either the QMB or full-Medicaid condition applies. The footer does not establish an individual waiver or exact reduced price.',
         'applicability': {'any_of': ['R12-FOOTER-QMB', 'R12-FOOTER-MEDICAID'],
                           'service_scope': 'services covered under Original Medicare', 'modal': 'may'},
         'reduced_price_or_zero_inferred': False},
        {'id': 'R12-FOOTER-QMB', 'kind': 'condition', 'statement': 'The member is a Qualified Medicare Beneficiary (QMB).',
         'relation_to_claim': 'alternative_qualifying_population', 'reported_status_is_verified': False},
        {'id': 'R12-FOOTER-MEDICAID', 'kind': 'condition', 'statement': 'The member has full Medicaid benefits.',
         'relation_to_claim': 'alternative_qualifying_population', 'reported_status_is_verified': False}]
    old_quotes = {'If you are a Qualified Medicare Beneficiary (QMB)',
        'have full Medicaid benefits then your deductible, coinsurance and/or copayment may be less for services that are covered under Original Medicare.'}
    by_page = {p['physical_page']: p for p in parents}
    with gzip.open(packet / 'layout-defect-census-r2/complete-clause-layout-census.jsonl.gz', 'rt') as stream:
        clauses = [r for r in map(json.loads, stream) if r['old_quote'] in old_quotes]
    mappings = []
    for clause in clauses:
        fragments = clause['original_source_fragments']
        pages = sorted({f['locator']['pdf_page'] for f in fragments if f['locator']['document_sha256'] == EOC_SHA})
        if not pages or not set(pages).issubset(by_page):
            raise ReconciliationError('Repeated footer clause points outside exact retained chart parents')
        mappings.append({'original_clause_id': clause['old_clause_id'], 'original_quote': clause['old_quote'],
            'original_canonical_ids': clause['original_canonical_ids'], 'original_source_fragments': fragments,
            'complete_footer_parent_ids': [by_page[p]['id'] for p in pages],
            'proposed_meaning_ids': ['R12-FOOTER-QMB'] if clause['old_quote'].startswith('If you') else
                                    ['R12-FOOTER-MAY-REDUCE', 'R12-FOOTER-MEDICAID'],
            'individual_waiver_inferred': False, 'old_ID_quote_and_denominator_unchanged': True})
    if len(mappings) != 138:
        raise ReconciliationError('Exact retained truncated footer clause population changed')
    bindings = {
        'complete-footer-source-parents.jsonl.gz': write_new(output / 'complete-footer-source-parents.jsonl.gz', parents, jsonl=True, compressed=True),
        'old-footer-clause-correspondence.jsonl.gz': write_new(output / 'old-footer-clause-correspondence.jsonl.gz', mappings, jsonl=True, compressed=True),
        'proposed-footer-meaning-units.json': write_new(output / 'proposed-footer-meaning-units.json', meanings)}
    receipt = {'schema': VERSION + '/repeated-footer-source-repair/1', 'offering_id': OFFERING,
        'original_pdf_sha256': EOC_SHA, 'original_chart_pages': 69, 'retained_old_truncated_clauses': 138,
        'complete_full_width_source_parents': len(parents), 'proposed_meaning_units': len(meanings),
        'proposed_meaning_kinds': dict(Counter(m['kind'] for m in meanings)),
        'source_scoped_meaning_representations_if_each_page_retained': len(parents) * len(meanings),
        'canonical_novelty_or_deduplication_decided': False,
        'semantic_equivalence_or_ID_retirement_applied': False, 'original_required_unchanged': 4675,
        'required_missing_unchanged': 16, 'new_required_adopted': 0,
        'independent_review': None, 'new_acceptance': False, 'operator_sha256': file_sha(Path(__file__)), 'bindings': bindings}
    write_new(output / 'FOOTER_REPAIR_RECEIPT.json', receipt)
    return receipt


def global_source_readings(record, readings):
    """Bind named full-width contexts by both retained section and source page.

    A heading incorrectly inherited from the preceding oxygen section is an
    explicit exception; it cannot become an oxygen coverage proposition.
    """
    if record['canonical_id'] == 'CANONICAL-abc4bb27415965a163b0791c7d19':
        return []
    section = record['material_source_context'].get('source_section', '')
    pages = {p['physical_page'] for p in record['source_pages'] if p['document_kind'] == 'EOC'}
    return [reading for reading in readings
            if any(section.startswith(prefix) for prefix in reading['source_section_prefixes'])
            and pages & set(reading['physical_pages'])]


def clinical_review(repository, output):
    """Freeze source-specific producer proposals and exact unresolved semantics.

    Original canonical obligations and their graph remain unchanged. Geometry,
    atomic source candidates, specific component comparisons, missing evidence,
    independent interpretation review and release are separate dimensions.
    """
    _, _, _, _, frozen_binding = checked_inputs(repository)
    packet = repository / R12
    inputs = []
    def read(name):
        path = packet / name; inputs.append(path)
        return load(path)
    def rows(name):
        path = packet / name; inputs.append(path)
        with gzip.open(path, 'rt') as stream:
            return list(map(json.loads, stream))
    old = {r['canonical_id']: r for r in rows('case-comparisons-r2/per-id-reconciliation.jsonl.gz')}
    observations = {r['id']: r for r in rows('case-comparisons-r2/source-interpretations.jsonl.gz')}
    census = {r['old_clause_id']: r for r in rows('layout-defect-census-r2/complete-clause-layout-census.jsonl.gz')}
    cells = {r['id']: r for r in rows('layout-defect-census-r2/corrected-medical-source-cells.jsonl.gz')}
    fullwidth = read('full-width-source-parent-correction-r1/complete-full-width-parent.json')
    old_fullwidth = fullwidth['original_geometry_parent_ids']
    replay = combine_full_width_source_parent([cells[key] for key in old_fullwidth], 'EOC-044-0250')
    if canonical(replay) != canonical(fullwidth):
        raise ReconciliationError('Reviewed full-width source parent failed exact replay')
    cells[fullwidth['id']] = fullwidth
    cell_alias = {key: fullwidth['id'] for key in old_fullwidth}
    readings = read('clinical-source-readings-r2.json')
    pixels = read('clinical-pixel-inspection-r2.json')
    if pixels['medical_source_readings_sha256'] != file_sha(packet / 'clinical-source-readings-r2.json'):
        raise ReconciliationError('Manual source readings changed after pixel receipt')
    pixel_pages = {}
    for binding in pixels['inspected_medical_source_pages']:
        if file_sha(repository / binding['path']) != binding['sha256']:
            raise ReconciliationError('Inspected original-page render changed')
        pixel_pages[binding['physical_page']] = binding
    by_cell = defaultdict(list)
    for reading in readings['readings']:
        if (reading['offering_id'] != OFFERING or reading['accepted_for_reference'] is not False
                or reading['all_material_conditions_independently_reviewed'] is not False):
            raise ReconciliationError('Clinical reading has invented identity/review/acceptance')
        if not set(reading['physical_pages']).issubset(pixel_pages):
            raise ReconciliationError('Clinical reading lacks original-page pixel inspection')
        for bound in reading['source_cells']:
            cell = cells[bound['id']]
            if (cell['full_source_word_binding_sha256'] != bound['source_words_sha256']
                    or cell['source_text_candidate'] != bound['full_exact_text']):
                raise ReconciliationError('Manual reading changed exact source parent')
            by_cell[bound['id']].append(reading)
    global_notes = read('clinical-global-source-readings-r1.json')
    for reading in global_notes['readings']:
        for page in reading['source_parent_pages']:
            render = packet / 'printed-source-review/eoc' / f"page-{page['physical_page']:03d}.png"
            if file_sha(render) != page['original_page_render_sha256']:
                raise ReconciliationError('Global context original pixel binding changed')
    rules = read('clinical-control-comparison-r3.json')['rules']
    worklist = read('UNRESOLVED_WORKLIST_R2.json')
    original_ids = {r['canonical_id'] for r in worklist['groups']['clinical_medical_source_adapters']['records']}
    handoff = read('post-freeze-carrier-dental-review/clinical-neighbor-handoff.json')
    neighbor_ids = {r['canonical_id'] for r in handoff}
    missing_ids = {r['canonical_id'] for r in worklist['groups']['clinical_required_missing_health_education_definition']['records']}
    if (len(original_ids), len(neighbor_ids), len(original_ids & neighbor_ids), len(missing_ids)) != (2090, 51, 16, 1):
        raise ReconciliationError('Exact clinical/neighbor/missing population changed')
    selected_ids = sorted(original_ids | neighbor_ids | missing_ids)
    sb_units = {r['id']: r for r in rows('sb-source-repairs-r2/proposed-SB-source-units.jsonl.gz')}
    sb_map = {r['original_clause_id']: r for r in rows('sb-source-repairs-r2/old-SB-clause-to-proposed-units.jsonl.gz')}
    native = {r['observation_id']: r for r in rows('clinical-native-format-review-r2/clinical-native-format-reviews.jsonl.gz')}
    footer_map = {r['original_clause_id']: r for r in rows('repeated-footer-source-repairs-r1/old-footer-clause-correspondence.jsonl.gz')}
    footer_parents = {r['id']: r for r in rows('repeated-footer-source-repairs-r1/complete-footer-source-parents.jsonl.gz')}
    footer_meanings = {r['id']: r for r in read('repeated-footer-source-repairs-r1/proposed-footer-meaning-units.json')}
    dental_by_old = defaultdict(list)
    for unit in rows('post-freeze-carrier-dental-review/proposed-atomic-source-units.jsonl.gz'):
        for identifier in unit['old_canonical_ids']:
            dental_by_old[identifier].append(unit)
    sb_pixels = read('SB_PIXEL_INSPECTION_R1.json')
    for page in sb_pixels['inspected_pages']:
        if file_sha(repository / page['path']) != page['sha256']:
            raise ReconciliationError('SB original pixel binding changed')
    if file_sha(repository / sb_pixels['original_pdf_path']) != SB_SHA:
        raise ReconciliationError('Original SB bytes changed')
    read('OFFICIAL_CLINICAL_QUESTION_REVIEW_R1.json')
    repairs = rows('medical-atomic-repairs-r1/proposed-atomic-units.jsonl.gz')
    proposed_by_cell = defaultdict(list)
    for repair in repairs:
        for bound in repair['evidence']:
            proposed_by_cell[bound['source_cell_id']].append(repair['id'])
    controls = {}
    for identifier in sorted({q for c in selected_ids for q in old[c]['source_native_observation_ids']}):
        observation = observations[identifier]
        if observation['layer'] == 'cms_table':
            controls[identifier] = propose_table_control(observation, rules)
    if len(controls) != 365 or any(not c['manual_rule_ids'] for c in controls.values()):
        raise ReconciliationError('Specific clinical table question comparison missing')
    result = []
    for identifier in selected_ids:
        record = old[identifier]
        details, reading_ids, repair_ids, sb_ids, global_ids = [], set(), set(), set(), set()
        footer_ids, dental_ids = set(), set()
        issue_codes, questions, proposed_roles = set(), [], []
        matching_global = global_source_readings(record, global_notes['readings'])
        for reading in matching_global:
            global_ids.add(reading['id'])
        if identifier == 'CANONICAL-abc4bb27415965a163b0791c7d19':
            proposed_roles.extend(global_notes['exact_source_context_corrections'])
            issue_codes.add('INHERITED_OXYGEN_CONTEXT_CORRECTED_TO_CHAPTER_HEADING_PROPOSED')
        predicate = record['predicate']
        if predicate.startswith('shared_allowance: you pay these amounts until you reach the out- of-pocket maximum.'):
            proposed_roles.append({'before_predicate': predicate,
                'proposed_predicate_role': 'MOOP_cost_sharing_stopping_condition',
                'shared_dollar_allowance_inferred': False, 'independent_review': None})
            issue_codes.add('MOOP_STOPPING_PREDICATE_MISLABELED_SHARED_ALLOWANCE')
        for obs_id in record['source_native_observation_ids']:
            observation = observations[obs_id]; layer = observation['layer']; payload = observation['complete_native_payload']
            detail = {'observation_id': obs_id, 'layer': layer, 'raw_payload_sha256': observation['raw_payload_sha256'],
                'complete_retained_native_payload': payload, 'source_native_meaning': observation['source_meaning']}
            if layer == 'carrier_clause':
                clause_id = payload['clause_id']; clause = census[clause_id]
                detail.update(exact_old_quote=clause['old_quote'], original_fragments=clause['original_source_fragments'],
                              layout_flags=clause['layout_flags'], printed_source_readings=[])
                for historical_cell_id in clause['source_cell_candidates']:
                    cell_id = cell_alias.get(historical_cell_id, historical_cell_id)
                    for reading in by_cell.get(cell_id, []):
                        reading_ids.add(reading['id'])
                        detail['printed_source_readings'].append({'historical_source_cell_id': historical_cell_id,
                            'current_source_parent_id': cell_id, 'manual_reading_id': reading['id'],
                            'financial_reading': reading['financial_reading'], 'material_conditions': reading['material_conditions'],
                            'interpretation_questions': reading['interpretation_questions'],
                            'semantic_equivalence_asserted': False})
                    repair_ids.update(proposed_by_cell[historical_cell_id])
                if clause_id in sb_map:
                    mapping = sb_map[clause_id]
                    detail['SB_exact_word_correspondence'] = mapping
                    units = [sb_units[q['proposed_unit_id']] for q in mapping['proposed_source_unit_correspondences']]
                    sb_ids.update(u['id'] for u in units)
                    detail['SB_proposed_meanings'] = [{key: unit[key] for key in ['id', 'key', 'kind', 'statement',
                        'structured_meaning', 'condition_ids', 'context_ids', 'semantic_obligation_candidate']} for unit in units]
                    if mapping['unbound_original_word_keys']:
                        issue_codes.add('SB_ORIGINAL_WORDS_OUTSIDE_AUTHORED_MEANING_SCOPE')
                if clause_id in footer_map:
                    mapping = footer_map[clause_id]
                    footer_ids.update(mapping['proposed_meaning_ids'])
                    detail['complete_footer_parent_correspondence'] = mapping
                    detail['full_width_footer_source_parents'] = [footer_parents[key] for key in mapping['complete_footer_parent_ids']]
                    detail['footer_proposed_meanings'] = [footer_meanings[key] for key in mapping['proposed_meaning_ids']]
                    issue_codes.add('TRUNCATED_FOOTER_REJOIN_AND_ALTERNATIVE_POPULATION_SCOPE_PROPOSED')
                if identifier in dental_by_old:
                    units = dental_by_old[identifier]
                    dental_ids.update(unit['id'] for unit in units)
                    detail['separate_frozen_dental_source_proposals'] = [{key: unit[key] for key in
                        ['id', 'source_statement', 'source_locator', 'structured_reading', 'required_context_proposed_child_ids']}
                        for unit in units]
                    detail['dental_parent_scope_correspondence_is_not_old_predicate_equivalence'] = True
                if matching_global:
                    detail['named_global_source_contexts'] = [{key: r[key] for key in
                        ['id', 'physical_pages', 'producer_source_readings', 'unresolved_questions']} for r in matching_global]
                if clause['layout_flags']:
                    issue_codes.add('HISTORICAL_MIXED_LAYOUT_QUOTE_REQUIRES_CHILD_REPLACEMENT_REVIEW')
                if not detail['printed_source_readings'] and clause_id not in sb_map and clause_id not in footer_map and identifier not in dental_by_old and not matching_global and not proposed_roles:
                    issue_codes.add('EXACT_CARRIER_CLAUSE_MEANING_NOT_AUTHORED')
                    questions.append({'clause_id': clause_id, 'work': 'Interpret the retained exact quote and original printed source in its named service/context; this clause has no authored medical/SB/global meaning yet.',
                                      'original_quote': clause['old_quote']})
            elif layer == 'cms_table':
                detail['specific_table_question_comparison'] = controls[obs_id]
                if controls[obs_id]['source_type_correction']:
                    issue_codes.add('ORIGINAL_NUMERIC_UNIT_CORRECTION_PROPOSED')
                for comp in controls[obs_id]['manual_comparisons']:
                    questions.extend({'observation_id': obs_id, 'rule_id': comp['id'], 'work': q} for q in comp['material_holds'])
            elif layer == 'cms_json':
                if obs_id not in native:
                    raise ReconciliationError('Exact selected clinical native observation has no authored interpretation')
                detail['component_specific_native_proposal'] = native[obs_id]
                issue_codes.update(native[obs_id]['specific_mapping_holds'])
                questions.extend({'observation_id': obs_id, 'source_pointer': native[obs_id]['source_pointer'],
                                  'work': hold} for hold in native[obs_id]['specific_mapping_holds'])
            details.append(detail)
        if record['required_evidence_missing']:
            issue_codes.add('REQUIRED_HEALTH_EDUCATION_DEFINITION_NOT_AVAILABLE')
            questions.append({'work': record['unresolved_disposition']['specific_required_work'],
                'genuine_source_gap': True, 'falls_definition_does_not_close_this_requirement': True})
        result.append({'schema': VERSION + '/clinical-exact-id-review-r2',
            'canonical_id': identifier, 'kind': record['kind'], 'offering_id': OFFERING,
            'original_required_state': record['original_states'], 'required_evidence_missing': record['required_evidence_missing'],
            'original_canonical_sha256': record['canonical_sha256'], 'original_predicate': predicate,
            'original_subject': record['subject'], 'original_material_context': record['material_source_context'],
            'original_linked_canonical_ids': record['linked_canonical_ids'],
            'complete_source_proposition_sibling_ids': record['complete_source_proposition_sibling_ids'],
            'source_scoped_relationships': record['source_scoped_relationships'], 'original_source_pages': record['source_pages'],
            'source_assessments': details, 'manual_chart_reading_ids': sorted(reading_ids),
            'SB_source_unit_ids': sorted(sb_ids), 'global_context_reading_ids': sorted(global_ids),
            'specific_proposed_repair_unit_ids': sorted(repair_ids), 'specific_source_role_corrections': proposed_roles,
            'footer_proposed_meaning_ids': sorted(footer_ids), 'separate_dental_source_proposal_ids': sorted(dental_ids),
            'issue_codes': sorted(issue_codes), 'specific_unresolved_meaning_questions': questions,
            'ownership': 'required_missing_health_education' if identifier in missing_ids else
                         'clinical_neighbor_transferred' if identifier in neighbor_ids - original_ids else 'original_clinical_worklist',
            'comparison_outcome': 'insufficient_evidence',
            'producer_source_readings_and_component_proposals_available': bool(reading_ids or sb_ids or global_ids or footer_ids or dental_ids or proposed_roles or any(d['layer'].startswith('cms_') for d in details)),
            'old_to_proposed_source_word_overlap_is_semantic_equivalence': False,
            'complete_meaning_reconciliation_complete': False, 'independent_review': None,
            'new_acceptance': False, 'accepted_for_reference': False,
            'consumer_purposes': {purpose: 'held' for purpose in HOLDS}})
    bindings = {
        'clinical-per-id-review.jsonl.gz': write_new(output / 'clinical-per-id-review.jsonl.gz', result, jsonl=True, compressed=True),
        'clinical-native-table-comparisons.jsonl.gz': write_new(output / 'clinical-native-table-comparisons.jsonl.gz', list(controls.values()), jsonl=True, compressed=True)}
    summary = {'schema': VERSION + '/clinical-review-receipt-r3', 'frozen_input_binding': frozen_binding,
        'original_required_offering': EXPECTED, 'original_required_count_unchanged': 4675, 'original_missing_count_unchanged': 16,
        'original_clinical_ids': len(original_ids), 'handoff_ids': len(neighbor_ids), 'handoff_overlap': len(original_ids & neighbor_ids),
        'handoff_new_clinical_ids': len(neighbor_ids - original_ids), 'clinical_missing_health_education_ids': len(missing_ids),
        'exact_unique_reviewed_ids': len(result), 'kinds': dict(Counter(r['kind'] for r in result)),
        'manual_chart_readings': len(readings['readings']), 'manual_chart_named_conditions': sum(len(r['material_conditions']) for r in readings['readings']),
        'manual_global_contexts': len(global_notes['readings']), 'manual_global_named_predicates': sum(len(r['producer_source_readings']) for r in global_notes['readings']),
        'ids_with_chart_reading': sum(bool(r['manual_chart_reading_ids']) for r in result),
        'ids_with_SB_reading': sum(bool(r['SB_source_unit_ids']) for r in result),
        'ids_with_global_reading': sum(bool(r['global_context_reading_ids']) for r in result),
        'ids_with_footer_meaning': sum(bool(r['footer_proposed_meaning_ids']) for r in result),
        'ids_with_separate_dental_source_proposals': sum(bool(r['separate_dental_source_proposal_ids']) for r in result),
        'ids_with_source_or_component_proposals': sum(r['producer_source_readings_and_component_proposals_available'] for r in result),
        'specific_table_observations': len(controls), 'table_observations_with_manual_comparisons': sum(bool(r['manual_rule_ids']) for r in controls.values()),
        'table_unit_corrections': sum(bool(r['source_type_correction']) for r in controls.values()),
        'native_component_observations': len(native),
        'issue_counts_by_original_canonical_ID': dict(Counter(code for r in result for code in r['issue_codes'])),
        'original_ids_retired': 0, 'new_required_adopted': 0, 'new_accepted': 0,
        'all_ids_full_meaning_reconciled': False, 'independent_review_complete': False, 'whole_offering_pilot_complete': False,
        'accounting_and_source_parent_correspondence_are_not_semantic_completion': True,
        'manual_and_ownership_inputs': {str(path.relative_to(packet)): file_sha(path) for path in dict.fromkeys(inputs)},
        'operator_sha256': file_sha(Path(__file__)), 'bindings': bindings}
    write_new(output / 'CLINICAL_REVIEW_RECEIPT.json', summary)
    return summary


def assert_review_release(record):
    """A proposed review record cannot counterfeit an independent review/release."""
    if record.get('accepted_for_reference') is not False or record.get('new_acceptance') is not False:
        raise ReconciliationError('Acceptance cannot be asserted by the producer')
    if record.get('independent_review') is not None:
        raise ReconciliationError('Independent review must be supplied by an external bound receipt')
    if record['required_evidence_missing'] and record['comparison_outcome'] != 'insufficient_evidence':
        raise ReconciliationError('Missing required evidence cannot be reconciled by decoding metadata')
    if record['comparison_outcome'] in {'exact_agreement', 'agreement_through_reviewed_mapping'}:
        raise ReconciliationError('Producer proposals cannot establish full-meaning agreement')


def check_component(cms, check):
    if check.get('level') != 'component_only' or check.get('complete_meaning_agreement') is not False:
        raise ReconciliationError('A component witness cannot claim complete meaning')
    pointer = check['pointer']
    value = json_pointer(cms, pointer)
    if isinstance(value, (dict, list)):
        raise ReconciliationError('Component witness must specify an exact scalar')
    expected = check['expected_source_component']
    if not isinstance(value, str) or not isinstance(expected, str) or value == '' or expected == '':
        raise ReconciliationError('A blank/non-string source scalar is not an amount agreement')
    # Exact decimals are used solely for the named numeric component. Source
    # enums/terminal values remain raw and never become infinity/eligibility.
    try:
        equal = Decimal(value) == Decimal(expected)
    except InvalidOperation:
        equal = value == expected
    component_path = pointer.rsplit('/', 1)[0]
    return {**check, 'actual_native_value': value, 'exact_component_equal': equal,
            'enclosing_native_component': json_pointer(cms, component_path),
            'enclosing_native_component_sha256': digest(json_pointer(cms, component_path)),
            'full_meaning_outcome': 'insufficient_evidence',
            'reviewed_factual_mapping': None, 'accepted_for_reference': False}


def case_matches(case, record):
    family = record['subject'].removeprefix('Published service family: ')
    if record['subject'].startswith('Published service family: ') and family in case['carrier_families']:
        return True
    tags = {f"{context['variant']}:{context['category_code']}:{context['category_type_id']}"
            for context in record['native_service_contexts']}
    for tag in case['service_categories']:
        if tag == 'optional_rider:*' and any(item.startswith('optional_rider:') for item in tags):
            return True
        if tag in tags:
            return True
    return record['canonical_id'] in case.get('canonical_ids', [])


def apply_cases(records, cases, cms):
    if len({case['id'] for case in cases}) != len(cases):
        raise ReconciliationError('Duplicate interpretation case ID')
    results = []
    for case in cases:
        if case['full_meaning_outcome'] != 'insufficient_evidence' or case['accepted_for_reference'] is not False or case['independent_review'] is not None:
            raise ReconciliationError('Producer interpretation cannot assert independent review/acceptance')
        selected = [row for row in records if case_matches(case, row)]
        if not selected:
            raise ReconciliationError('Interpretation case has no exact canonical binding: ' + case['id'])
        checked = [check_component(cms, item) for item in case['component_checks']]
        result = {**case, 'canonical_ids': sorted(row['canonical_id'] for row in selected),
            'canonical_counts': dict(Counter(row['kind'] for row in selected)),
            'component_results': checked,
            'case_binding_is_complete_interpretation': False,
            'all_conditions_individually_reviewed': False}
        results.append(result)
        for record in selected:
            record['producer_interpretation_cases'].append(case['id'])
            questions = record['unresolved_disposition'].setdefault('case_specific_questions', [])
            questions.extend({'case_id': case['id'], 'question': question} for question in case['unresolved_questions'])
    for row in records:
        if not row['producer_interpretation_cases']:
            row['unresolved_disposition']['internal_work_remaining'] = 'No substantive producer interpretation case has yet been bound to this exact canonical ID. Source decoding/retention alone does not close it.'
        else:
            row['unresolved_disposition']['internal_work_remaining'] = 'Review this exact predicate and its complete native observations/linked conditions against the cited producer case; case membership alone is not reconciliation.'
    return results


def build(repository, case_path=None):
    rows, native, cms, pages, binding = checked_inputs(repository)
    obs = native['native_observations']
    interpretations = {oid: interpret_observation(value, native['native_clauses'], cms)
                       for oid, value in sorted(obs.items())}
    representations = {rep: row['id'] for row in rows for rep in row['representation_ids']}
    edges = list(value['raw_payload'] for value in native['native_relationships'].values())
    by_representation = defaultdict(list)
    for edge in edges:
        for endpoint in {edge['parent_id'], edge['child_id']}:
            if endpoint not in representations:
                raise ReconciliationError('Relationship endpoint outside exact offering')
            by_representation[endpoint].append(edge)
    propositions = defaultdict(list)
    for row in rows:
        scope = row['context'].get('complete_source_proposition_scope')
        if scope:
            propositions[scope].append(row['id'])
    records = []
    for row in rows:
        missing = 'required_evidence_missing' in row['states']
        linked_edges = {canonical(edge): edge for rep in row['representation_ids'] for edge in by_representation[rep]}
        linked_ids = sorted({representations[endpoint] for edge in linked_edges.values()
                             for endpoint in (edge['parent_id'], edge['child_id'])} - {row['id']})
        scope = row['context'].get('complete_source_proposition_scope')
        record = {'canonical_id': row['id'], 'canonical_sha256': digest(row), 'kind': row['kind'],
            'offering_id': OFFERING, 'subject': row['subject'], 'predicate': row['predicate'],
            'original_states': row['states'], 'required_evidence_missing': missing,
            'source_native_observation_ids': row['observation_ids'],
            'source_ids': row['source_ids'], 'representation_ids': row['representation_ids'],
            'source_pages': [{'document_kind': k, 'physical_page': p} for k, p in record_pages(row, interpretations)],
            'native_service_contexts': source_service_contexts(row, obs, cms),
            'complete_source_proposition_sibling_ids': sorted(set(propositions.get(scope, [])) - {row['id']}),
            'linked_canonical_ids': linked_ids,
            'source_scoped_relationships': sorted(linked_edges.values(), key=canonical),
            'material_source_context': row['context'], 'canonical_detail': row['detail'],
            'comparison_outcome': 'insufficient_evidence',
            'producer_interpretation_cases': [],
            'unresolved_disposition': {'specific_required_work': row['detail'].get('closure_evidence') if missing else None,
                'source_decoding_available': not missing,
                'complete_meaning_reconciliation_complete': False},
            'independent_review': None, 'new_acceptance': False, 'accepted_for_reference': False}
        assert_review_release(record)
        records.append(record)
    case_results = []
    if case_path:
        spec = load(case_path)
        if spec['offering_id'] != OFFERING:
            raise ReconciliationError('Interpretation case offering mismatch')
        case_results = apply_cases(records, spec['cases'], cms)
    source_decodes = Counter(item['source_meaning']['kind'] for item in interpretations.values())
    summary = {'schema': VERSION, 'offering_id': OFFERING, 'input_binding': binding,
        'required': EXPECTED, 'required_total': len(records), 'required_missing': sum(r['required_evidence_missing'] for r in records),
        'source_decodes': dict(source_decodes), 'native_source_counts': {key: len(value) for key, value in native.items()},
        'per_id_records': len(records), 'all_original_states_preserved': True,
        'substantive_producer_cases': len(case_results),
        'ids_with_substantive_case_context': sum(bool(row['producer_interpretation_cases']) for row in records),
        'ids_without_substantive_case_context': sum(not row['producer_interpretation_cases'] for row in records),
        'component_witnesses': sum(len(case['component_results']) for case in case_results),
        'component_equal': sum(item['exact_component_equal'] for case in case_results for item in case['component_results']),
        'case_membership_is_reconciliation': False,
        'producer_interpretations_complete': False, 'independent_review_complete': False,
        'whole_offering_reconciliation_complete': False, 'whole_offering_pilot_complete': False,
        'new_fully_supported': 0, 'new_awaiting_review': 0, 'new_accepted': 0,
        'consumer_purposes': {purpose: 'held' for purpose in HOLDS},
        'database_access': False, 'source_acquisition': False, 'paid_ai_calls': 0}
    return records, list(interpretations.values()), case_results, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cases', type=Path)
    parser.add_argument('--capture-layout', action='store_true')
    parser.add_argument('--census-medical-layout', type=Path)
    parser.add_argument('--row-boundaries', type=Path)
    parser.add_argument('--atomic-spec', type=Path)
    parser.add_argument('--layout-census', type=Path)
    parser.add_argument('--clinical-review', action='store_true')
    parser.add_argument('--sb-source-spec', type=Path)
    parser.add_argument('--native-format-review', action='store_true')
    parser.add_argument('--repeated-footer-review', action='store_true')
    args = parser.parse_args()
    if args.repeated_footer_review:
        print(canonical(prepare_repeated_footer_readings(args.repository.resolve(), args.output)))
        return
    if args.native_format_review:
        print(canonical(build_native_review(args.repository.resolve(), args.output)))
        return
    if args.sb_source_spec:
        print(canonical(prepare_sb_source_repairs(args.repository.resolve(), args.sb_source_spec, args.output)))
        return
    if args.clinical_review:
        print(canonical(clinical_review(args.repository.resolve(), args.output)))
        return
    if args.capture_layout:
        print(canonical(capture_layout(args.repository.resolve(), args.output)))
        return
    if args.census_medical_layout:
        if not args.row_boundaries:
            parser.error('--census-medical-layout requires --row-boundaries')
        print(canonical(census_medical_layout(args.repository.resolve(), args.census_medical_layout,
                                              args.row_boundaries, args.output)))
        return
    if args.atomic_spec:
        if not args.layout_census:
            parser.error('--atomic-spec requires --layout-census')
        print(canonical(materialize_atomic_repairs(args.repository.resolve(), args.layout_census,
                                                   args.atomic_spec, args.output)))
        return
    records, interpretations, cases, summary = build(args.repository.resolve(), args.cases)
    bindings = {}
    for name, values in [('per-id-reconciliation.jsonl.gz', records), ('source-interpretations.jsonl.gz', interpretations)]:
        bindings[name] = write_new(args.output / name, values, jsonl=True, compressed=True)
    if cases:
        bindings['producer-case-comparisons.json'] = write_new(args.output / 'producer-case-comparisons.json', cases)
        summary['case_specification'] = {'path': str(args.cases), 'sha256': file_sha(args.cases)}
    summary['outputs'] = bindings
    summary['operator_sha256'] = file_sha(Path(__file__))
    write_new(args.output / 'RECONCILIATION_RECEIPT.json', summary)
    print(canonical(summary))


if __name__ == '__main__':
    main()
