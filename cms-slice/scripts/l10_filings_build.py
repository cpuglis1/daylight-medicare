"""Additive intake of owner-delivered OIR filing packets; preserves r2.

Published rate cells and filing fields are research observations. A stamped
schedule's policy-issue date range is never used as its rate-effective date.
"""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

import pdfplumber

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l10-medigap-2026-10-28'
PACKET = BASE / 'filing-reconciliation-r3'
AGES = ['0-64'] + [str(n) for n in range(65, 100)] + ['100+']
LABELS = ['Filing Company', 'Website', 'Toll Free Number', 'Date Range From', 'Date Range Thru',
          'Issuing Carrier', 'Insurance Type', 'Plan Type', 'Plan', 'Form Number', 'Eligibility:',
          'Underwritten (Yes/No)', 'Rating Class', 'Sex Distinct', 'Smoker Distinct', 'Marketing Method',
          'Age Basis', 'Policy Fee Assessed', 'Fee Amount', 'Modal Factors/Annual',
          'Modal Factors/Semi-Annual', 'Modal Factors/Quarterly', 'Modal Factors/Semi-Monthly',
          'Modal Factors/Monthly', 'Modal Factors/EFT/Monthly', 'Modal Factors/Other', 'Other Description', 'Region']
LETTERS = {'26-007296': {'page': 158, 'effective_from': '2026-08-01', 'effective_through': '2027-07-31', 'approved_change_percent': '11.5', 'form_heading': 'FLMESNM10A ET AL.'},
           '26-018953': {'page': 241, 'effective_from': '2026-09-01', 'effective_through': '2027-08-31', 'approved_change_percent': '12.0', 'form_heading': 'ABLMSP21A-FL ET AL.'},
           '26-023593': {'page': 130, 'effective_from': '2026-08-01', 'effective_through': '2027-07-31', 'approved_change_percent': '12.0', 'form_heading': 'WNIC2096AFL ET AL.'},
           '26-036521': {'page': 180, 'effective_from': '2026-11-01', 'effective_through': '2027-10-31', 'approved_change_percent': '11.0', 'form_heading': 'MTM20-50021 ET AL.'}}


def digest(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()


def load(path): return json.loads(Path(path).read_text())


def dump(path, data): Path(path).write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + '\n')


def clean(page):
    # Body worksheet is Arial; the overlapping OIR stamp is Helvetica. Keep
    # source body glyphs without changing or rewriting the original PDF.
    return page.filter(lambda obj: obj.get('object_type') != 'char' or 'Arial' in obj['fontname'])


def cents(text):
    if not re.fullmatch(r'\$[\d,]+\.\d{2}', text): raise ValueError('Unsupported rate cell ' + repr(text))
    return int(Decimal(text.replace('$', '').replace(',', '')) * 100)


def build(out):
    out = Path(out)
    if out.exists(): raise ValueError('Use a new immutable output directory')
    out.mkdir(parents=True)
    intake = load(PACKET / 'intake.json'); schedules = []; rates = []; pages_out = []; approvals = []; exceptions = []
    for item in intake['documents']:
        path = ROOT / item['retained_path']; case = path.name[:9]
        if digest(path) != item['sha256']: raise ValueError('Changed source PDF')
        text_pages = (ROOT / item['poppler_text_path']).read_text().split('\f')[:item['pages']]
        if case in LETTERS:
            approval = {**LETTERS[case], 'case': case, 'source_pdf_sha256': item['sha256'],
                        'source_excerpt': text_pages[LETTERS[case]['page'] - 1], 'acceptance': 'pending'}
            approvals.append(approval)
        with pdfplumber.open(path) as document:
            starts = [i for i, text in enumerate(text_pages) if 'Filing Company' in text]
            schedule_pages = set()
            for index, pi in enumerate(starts):
                labels_table = clean(document.pages[pi]).extract_tables()[0]
                labels = [r[0] for r in labels_table[:28]]
                if labels != LABELS: raise ValueError(f'Worksheet labels changed: {case} p{pi+1}: {labels}')
                status = 'APPROVED' if 'APPROVED' in text_pages[pi][:400] else 'REPLACED' if 'REPLACED' in text_pages[pi][:400] else 'unknown'
                vp = clean(document.pages[pi + 1]); table = vp.extract_tables()[0]
                if len(table) != 39 or len(table[0]) < 3: raise ValueError(f'Worksheet shape changed {case} {pi+2}')
                if [r[1] for r in table[2:]] != AGES: raise ValueError('Worksheet ages changed')
                fields = {label: table[i][0] or None for i, label in enumerate(LABELS)}
                sid = f'{case}:p{pi+1}'
                used_pages = [pi+1, pi+2]
                columns = []
                # First values page includes the left field values, age column,
                # and one or more rate columns. A continuation has rates only.
                for ci in range(2, len(table[0])):
                    columns.append({'page': pi+2, 'column': ci, 'class_raw': table[0][ci], 'sex_raw': table[1][ci],
                                    'values': [row[ci] for row in table[2:]]})
                next_start = starts[index+1] if index+1 < len(starts) else len(document.pages)
                if pi+2 < next_start:
                    candidate = clean(document.pages[pi+2]).extract_tables()
                    if candidate and len(candidate[0]) == 39 and all(re.fullmatch(r'\$[\d,]+\.\d{2}', str(c or '')) for row in candidate[0][2:] for c in row):
                        continuation = candidate[0]; used_pages.append(pi+3)
                        for ci in range(len(continuation[0])):
                            columns.append({'page': pi+3, 'column': ci, 'class_raw': continuation[0][ci], 'sex_raw': continuation[1][ci],
                                            'values': [row[ci] for row in continuation[2:]]})
                if status == 'unknown': exceptions.append({'case': case, 'page': pi+1, 'reason': 'Unknown schedule status'})
                actual_period = LETTERS.get(case) if status == 'APPROVED' else None
                record = {'id': sid, 'case': case, 'status': status, 'source_pages': used_pages,
                          'source_pdf_sha256': item['sha256'], 'fields': fields,
                          'policy_issue_range_from': fields['Date Range From'], 'policy_issue_range_through': fields['Date Range Thru'],
                          'rate_effective_from': actual_period['effective_from'] if actual_period else None,
                          'rate_effective_through': actual_period['effective_through'] if actual_period else None,
                          'rate_effective_basis': 'filing_approval_letter' if actual_period else 'unresolved_or_superseded',
                          'date_range_is_not_rate_effective_date': True, 'source_columns': [{k:v for k,v in c.items() if k!='values'} for c in columns],
                          'annual_premium_unit_basis': 'OIR_annual_rate_collection_and_source_modal_fields',
                          'personal_quote': False, 'current_sale_status': 'not_established_by_approval', 'acceptance': 'pending'}
                schedules.append(record); schedule_pages.update(used_pages)
                for ci, column in enumerate(columns):
                    for ri, (age, value) in enumerate(zip(AGES, column['values'])):
                        amount = cents(value)
                        rates.append({'id': f'{sid}:c{ci}:r{ri}', 'schedule_id': sid, 'case': case,
                                      'source_pdf_sha256': item['sha256'], 'source_page': column['page'], 'source_column': column['column'],
                                      'age_raw': age, 'class_raw': column['class_raw'], 'sex_raw': column['sex_raw'],
                                      'amount_raw': value, 'annual_premium_cents': amount, 'unit': 'USD/year',
                                      'source_status': status, 'zero_meaning': 'unresolved_not_a_free_offer' if amount == 0 else None,
                                      'personal_quote': False, 'rate_effective_from': record['rate_effective_from'],
                                      'rate_effective_through': record['rate_effective_through']})
            for i, text in enumerate(text_pages):
                if i+1 in schedule_pages: role = 'rate_collection_schedule'
                elif i+1 == LETTERS.get(case, {}).get('page'): role = 'approval_letter'
                elif 'commission' in text.lower(): role = 'contains_commercial_or_expense_context_excluded_from_decision_retrieval'
                elif len(text.strip()) < 40: role = 'image_or_sparse_page_requires_visual_classification'
                elif 'Exhibit' in text: role = 'retained_supporting_exhibit_not_a_consumer_rate'
                else: role = 'retained_correspondence_or_supporting_text'
                pages_out.append({'case': case, 'page': i+1, 'role': role, 'source_pdf_sha256': item['sha256'],
                                  'poppler_text_chars': len(text.strip()), 'text_sha256': hashlib.sha256(text.encode()).hexdigest(),
                                  'consumer_retrieval_enabled': False})
    dump(out / 'schedules.json', schedules); dump(out / 'rate-cells.json', rates)
    dump(out / 'approval-letters.json', approvals); dump(out / 'page-inventory.json', pages_out)
    dump(out / 'exceptions.json', exceptions)
    coverage = {'schema': 'l10-owner-filings-coverage/1', 'owner_pdfs': len(intake['documents']), 'pages': len(pages_out),
                'schedules': len(schedules), 'schedule_status_counts': dict(Counter(x['status'] for x in schedules)),
                'annual_rate_cells': len(rates), 'rate_cells_by_status': dict(Counter(x['source_status'] for x in rates)),
                'approval_letters_with_actual_effective_period': len(approvals),
                'blue_approval_period_unresolved': True, 'full_l10_complete': False, 'human_acceptance': None,
                'consumer_release_enabled': False}
    dump(out / 'coverage.json', coverage)
    return coverage


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    print(json.dumps(build(a.out),indent=2))
