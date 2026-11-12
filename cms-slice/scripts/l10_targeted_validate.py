"""Independent pypdf-position/Poppler audit of the targeted filing revision."""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
import re

from pypdf import PdfReader
import pdfplumber

from l10_filings_validate import glyphs, lines
from l10_targeted_intake import ROOT, BASE, PACKET, OUT, read, write, sha

LABELS = ['Filing Company', 'Website', 'Toll Free Number', 'Date Range From', 'Date Range Thru', 'Issuing Carrier',
          'Insurance Type', 'Plan Type', 'Plan', 'Form Number', 'Eligibility:', 'Underwritten (Yes/No)', 'Rating Class',
          'Sex Distinct', 'Smoker Distinct', 'Marketing Method', 'Age Basis', 'Policy Fee Assessed', 'Fee Amount',
          'Modal Factors/Annual', 'Modal Factors/Semi-Annual', 'Modal Factors/Quarterly', 'Modal Factors/Semi-Monthly',
          'Modal Factors/Monthly', 'Modal Factors/EFT/Monthly', 'Modal Factors/Other', 'Other Description', 'Region']


def norm(text):
    return ' '.join(text.split())


def compact(text):
    return re.sub(r'\s+', '', text)


def native_money_rows(records):
    grouped = {}
    for x, y, text in sorted(records, key=lambda r: -r[1]):
        anchor = next((a for a in grouped if abs(a - y) < 3.5), y)
        grouped.setdefault(anchor, []).append((x, text))
    money = {}
    for y, chunks in grouped.items():
        chunks.sort()
        for i, (x, text) in enumerate(chunks):
            if '$' not in text:
                continue
            end = next((j for j in range(i + 1, len(chunks)) if '$' in chunks[j][1]), len(chunks))
            match = re.match(r'\$[\d,]+\.\d{2}', compact(''.join(t for _, t in chunks[i:end])))
            if match:
                money.setdefault(y, []).append((x, match[0]))
    return money


def native_age_anchor(records):
    explicit = [x for x, y, text in records if text.strip() == 'Age']
    if explicit:
        return explicit[0]
    rows = {}
    for x, y, text in sorted(records, key=lambda r: -r[1]):
        anchor = next((a for a in rows if abs(a - y) < 3.5), y)
        rows.setdefault(anchor, []).append((x, text))
    for y in sorted(rows, reverse=True):
        characters = [(char, x) for x, text in sorted(rows[y]) for char in text]
        joined = ''.join(char for char, _ in characters)
        index = joined.find('Age')
        if index >= 0:
            return characters[index][1]
    raise AssertionError('No native Age header')


def validate(out=OUT):
    out = Path(out)
    intake = read(PACKET / 'intake.json')
    schedules = read(out / 'schedules.json'); rates = read(out / 'rate-cells.json')
    assert not read(out / 'worksheet-holds.json')
    by_page = defaultdict(list)
    for row in rates:
        by_page[(row['case'], row['source_page'])].append(row)
    fields_checked = money_checked = headers_checked = candidates_checked = 0
    documents = {d['case']: d for d in intake['documents']}
    layouts = {}
    for case, doc in documents.items():
        source = ROOT / doc['retained_path']
        assert sha(source) == sha(ROOT / doc['owner_path']) == doc['sha256']
        assert sha(ROOT / doc['pypdf_text_path']) == doc['pypdf_text_sha256']
        assert sha(ROOT / doc['poppler_text_path']) == doc['poppler_text_sha256']
        pdf = PdfReader(source); native = read(ROOT / doc['pypdf_text_path'])
        layout = (ROOT / doc['poppler_text_path']).read_text().split('\f')[:doc['pages']]; layouts[case] = layout
        assert len(pdf.pages) == len(native) == len(layout) == doc['pages']
        assert 'Filing Number: ' + case in pdf.pages[0].extract_text()
        expected_candidates = {i + 1 for i, text in enumerate(native) if 'Filing Company' in text}
        expected_headers = {p for p in expected_candidates if all(compact(label) in compact(native[p - 1]) for label in LABELS)}
        actual = [s for s in schedules if s['case'] == case]
        nonworksheets = [r for r in read(out / 'nonworksheet-candidates.json') if r['case'] == case]
        assert {s['source_pages'][0] for s in actual} == expected_headers
        assert {r['source_page'] for r in nonworksheets} == expected_candidates - expected_headers
        candidates_checked += len(expected_candidates)
        for schedule in actual:
            hp = schedule['source_pages'][0]; text = native[hp - 1]
            assert schedule['source_pdf_sha256'] == doc['sha256']
            assert schedule['status'] == ('APPROVED' if 'APPROVED' in text else 'REPLACED')
            legacy = schedule['layout'] == 'legacy_fields_on_header'
            values_page = pdf.pages[hp]
            gs = glyphs(values_page)
            age_x = native_age_anchor(gs)
            if legacy:
                raw = '\n'.join(norm(line) for line in pdf.pages[hp - 1].extract_text().splitlines())
                anchors = [re.search(r'^' + re.escape(label) + (r'(?! Type\b)' if label == 'Plan' else '') + r'(?=\s|$|[0-9])\s*', raw, re.M) for label in LABELS]
                assert all(anchors), (case, hp, 'native legacy field labels')
                for i, label in enumerate(LABELS):
                    segment = raw[anchors[i].end():anchors[i + 1].start()] if i < len(LABELS) - 1 else raw[anchors[i].end():].splitlines()[0]
                    assert (norm(segment) or None) == (norm(schedule['fields'][label]) if schedule['fields'][label] else None), (case, hp, label, segment, schedule['fields'][label])
                    fields_checked += 1
            else:
                anchors = {t: y for y, t in lines(glyphs(pdf.pages[hp - 1])) if t in LABELS}
                assert set(anchors) == set(LABELS)
                for label in LABELS:
                    value = norm(''.join(t for x, y, t in sorted(gs) if x < age_x - 20 and abs(y - anchors[label]) < 6)) or None
                    assert compact(value or '') == compact(schedule['fields'][label] or ''), (case, hp, label, value, schedule['fields'][label])
                    fields_checked += 1
            for page in schedule['source_pages'][1:]:
                page_glyphs = gs if page == hp + 1 else glyphs(pdf.pages[page - 1])
                money = native_money_rows(page_glyphs)
                assert len(money) == 37, (case, page, 'money rows', len(money))
                columns = [c for c in schedule['source_columns'] if c['page'] == page]
                assert all(len(v) == len(columns) for v in money.values())
                top = max(money)
                hs = lines([(x, y, t) for x, y, t in page_glyphs if y > top + 6 and (page != hp + 1 or x > age_x + 20)])
                assert len(hs) == 2 and compact(hs[0][1]) == compact(' '.join(c['class_raw'] for c in columns)) and compact(hs[1][1]) == compact(' '.join(c['sex_raw'] for c in columns)), (case, page, hs)
                headers_checked += len(columns) * 2
                ages = ['0-64'] + [str(n) for n in range(65, 100)] + ['100+']
                for (_, values), age in zip(sorted(money.items(), reverse=True), ages):
                    for column, (_, amount) in zip(columns, sorted(values)):
                        matched = [r for r in by_page[(case, page)] if r['source_column'] == column['column'] and r['age_raw'] == age]
                        assert len(matched) == 1
                        row = matched[0]
                        assert row['amount_raw'] == amount and row['annual_premium_cents'] == int(Decimal(amount.replace('$', '').replace(',', '')) * 100)
                        assert row['schedule_id'] == schedule['id'] and row['class_raw'] == column['class_raw'] and row['sex_raw'] == column['sex_raw']
                        assert row['source_status'] == schedule['status'] and row['unit'] == 'USD/year' and row['personal_quote'] is False
                        assert row['zero_meaning'] == ('unresolved_not_a_free_offer' if row['annual_premium_cents'] == 0 else None)
                        money_checked += 1
            assert schedule['policy_issue_dates_are_not_rate_periods'] is True
            assert schedule['current_sale'] == 'unknown' and schedule['acceptance'] == 'pending'
        inventory = [p for p in read(out / 'page-inventory.json') if p['case'] == case]
        assert {p['page'] for p in inventory} == set(range(1, doc['pages'] + 1))
    assert money_checked == len(rates) == 40700 and fields_checked == len(schedules) * 28
    approvals = read(out / 'approval-letters.json')
    for r in approvals:
        raw = layouts[r['case']][r['source_page'] - 1]
        match = re.search(r'rate change of\s+([\d.]+)%,?\s+effective\s+(\d+/\d+/\d+)\s+through\s+(\d+/\d+/\d+),?\s+are\s+APPROVED', raw, re.S | re.I)
        assert match and match[1] == r['approved_change_percent']
        assert [datetime.strptime(match[i], '%m/%d/%Y').date().isoformat() for i in [2, 3]] == [r['effective_from'], r['effective_through']]
    period_map = {r['case']: r for r in approvals}
    for s in schedules:
        expected = period_map.get(s['case']) if s['status'] == 'APPROVED' else None
        assert [s['rate_effective_from'], s['rate_effective_through']] == ([expected['effective_from'], expected['effective_through']] if expected else [None, None])
    condition_methods = Counter()
    for fact in read(out / 'conditions.json'):
        matched = compact(fact['excerpt']) in compact(layouts[fact['case']][fact['source_page'] - 1])
        method = 'Poppler_layout'
        if not matched:
            # OIR's Helvetica-Bold stamp overprints some application body lines.
            # Read body glyph geometry independently; never edit the original PDF.
            with pdfplumber.open(ROOT / documents[fact['case']]['retained_path']) as pdf:
                page = pdf.pages[fact['source_page'] - 1].filter(lambda obj: obj.get('object_type') != 'char' or not obj['fontname'].endswith('Helvetica-Bold'))
                body = page.extract_text() or ''
                if compact(fact['excerpt']) not in compact(body) and fact['case'] == '22-005454' and fact['source_page'] == 46:
                    # The response boxes at x477+ interrupt the wrapped question.
                    # Its complete question column ends before x444.
                    body = page.crop((0, 0, 470, page.height)).extract_text() or ''
            matched = compact(fact['excerpt']) in compact(body)
            method = 'pdfplumber_body_geometry_excluding_OIR_stamp'
        assert matched, fact['id']
        condition_methods[method] += 1
        assert fact['source_pdf_sha256'] == documents[fact['case']]['sha256'] and fact['acceptance'] == 'pending'
    old = {s['id']: s for s in read(BASE / 'filing-reconciliation-r3/build-r1/schedules.json')}
    new = {s['id']: s for s in schedules}
    for pair in read(out / 'interval-continuity.json'):
        a, b = new[pair['prior_schedule_id']], old[pair['newer_schedule_id']]
        assert all(a['fields'][f] == b['fields'][f] for f in pair['exact_identity_fields'])
        assert date.fromisoformat(a['rate_effective_through']) + timedelta(days=1) == date.fromisoformat(b['rate_effective_from'])
        assert pair['prior_interval'] == [a['rate_effective_from'], a['rate_effective_through']]
        assert pair['newer_interval'] == [b['rate_effective_from'], b['rate_effective_through']]
        assert a['rate_effective_from'] <= '2026-01-01' and b['rate_effective_through'] >= '2026-12-31'
        assert pair['published_grid_intervals_cover_2026'] is True and pair['current_sale'] == 'unknown'
    parent = read(BASE / 'build-r2/carrier-table-observations.json'); by_id = {r['id']: r for r in rates}
    comparisons = read(out / 'blue-carrier-comparisons.json')
    assert len(comparisons) == len(parent) == 680
    for r in comparisons:
        p = parent[r['carrier_observation_index']];s = new[r['schedule_id']]
        assert s['fields']['Plan'] == p['variant'] and s['fields']['Region'] == '2010 Area 2' and s['status'] == 'APPROVED'
        assert s['case'] == ('25-043125' if p['select'] else '25-043172')
        values = [by_id[i] for i in r['candidate_rate_ids']]
        if p['payment_basis'] == 'regular_monthly':
            assert all(Decimal(v['annual_premium_cents']) / 12 == p['premium_cents'] for v in values)
            assert r['status'] == 'same_arithmetic_monthly_amount'
        else:
            assert r['status'] == 'APO_billing_precision_and_conditions_held' and r['same_arithmetic_amount'] is None
        assert r['form_equivalence_accepted'] is False and r['approved_rate_interval_established'] is False
    bindings = read(out / 'original-form-bindings.json')
    binding_methods = Counter()
    for r in bindings:
        for e in r['original_approved_text_pages']:
            t = layouts[e['case']][e['page'] - 1]
            code_pattern = r'(?<![A-Za-z0-9])' + re.escape(r['form_raw']) + r'(?![A-Za-z0-9(])'
            matched = bool(re.search(code_pattern, t)) and 'APPROVED' in compact(t)
            method = 'Poppler_layout'
            if not matched:
                with pdfplumber.open(ROOT / documents[e['case']]['retained_path']) as pdf:
                    page = pdf.pages[e['page'] - 1]
                    body = page.filter(lambda obj: obj.get('object_type') != 'char' or not obj['fontname'].endswith('Helvetica-Bold')).extract_text() or ''
                    stamp = page.filter(lambda obj: obj.get('object_type') != 'char' or obj['fontname'].endswith('Helvetica-Bold')).extract_text() or ''
                matched = bool(re.search(code_pattern, body)) and 'APPROVED' in compact(stamp)
                method = 'pdfplumber_body_and_separate_stamp_geometry'
            assert matched, (r['form_raw'], e['case'], e['page'])
            binding_methods[method] += 1
        assert r['later_amendments_checked'] is False and r['acceptance'] == 'pending'
    protected = read(PACKET / 'preservation-before.json')
    assert all(sha(ROOT / p) == wanted for p, wanted in protected.items())
    return {'schema': 'l10-targeted-independent-audit/1', 'passed': True, 'source_pdfs': len(documents), 'pages_accounted': intake['total_pages'],
            'worksheet_candidates_accounted': candidates_checked, 'schedules_checked': len(schedules), 'field_values_checked': fields_checked,
            'annual_source_cells_checked': money_checked, 'column_headers_checked': headers_checked, 'approval_periods_checked': len(approvals),
            'condition_records_checked': len(read(out / 'conditions.json')), 'condition_source_methods': dict(condition_methods),
            'continuity_pairs_checked': len(read(out / 'interval-continuity.json')),
            'blue_comparisons_checked': len(comparisons), 'original_form_identifiers_checked': len(bindings),
            'original_form_page_source_methods': dict(binding_methods),
            'protected_files_unchanged': len(protected), 'unexplained_source_value_mismatches': 0,
            'human_acceptance': None, 'consumer_release_enabled': False, 'full_l10_complete': False}


if __name__ == '__main__':
    import json
    result = validate()
    if not (OUT / 'SEALED').exists():
        write(PACKET / 'validation.json', result)
    print(json.dumps(result, indent=2))
