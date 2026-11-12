"""Reconstruct the eleven new packets without changing the sealed r3 parser."""
from collections import Counter
from datetime import datetime
import hashlib
from pathlib import Path
import re

import pdfplumber

from l10_filings_build import AGES, LABELS, clean, cents
from l10_targeted_intake import ROOT, BASE, PACKET, OUT, guard, read, write, sha

PERIOD = re.compile(r'rate change of\s+([\d.]+)%,?\s+effective\s+(\d+/\d+/\d+)\s+through\s+(\d+/\d+/\d+),?\s+are\s+APPROVED', re.S | re.I)
MONEY = re.compile(r'\$[\d,]+\.\d{2}')


def norm(text):
    return ' '.join(text.split())


def approval_periods(documents):
    records = []
    for doc in documents:
        for i, text in enumerate(read(ROOT / doc['pypdf_text_path'])):
            match = PERIOD.search(text)
            if match:
                records.append({'case': doc['case'], 'source_page': i + 1, 'source_pdf_sha256': doc['sha256'],
                                'excerpt': norm(match[0]), 'approved_change_percent': match[1],
                                'effective_from': datetime.strptime(match[2], '%m/%d/%Y').date().isoformat(),
                                'effective_through': datetime.strptime(match[3], '%m/%d/%Y').date().isoformat(),
                                'acceptance': 'pending'})
    assert {r['case'] for r in records} == {'25-007663', '25-030887', '25-023045', '25-039153'}
    assert len(records) == 4
    return records


def build(out=OUT):
    out = Path(out)
    if out.resolve() == OUT.resolve():
        guard()
    if (out / 'SEALED').exists():
        raise ValueError('Use a new revision')
    out.mkdir(parents=True, exist_ok=True)
    documents = read(PACKET / 'intake.json')['documents']
    approvals = approval_periods(documents)
    periods = {r['case']: r for r in approvals}
    schedules, rates, page_records, holds, nonworksheets = [], [], [], [], []
    for doc in documents:
        assert sha(ROOT / doc['retained_path']) == doc['sha256']
        texts = read(ROOT / doc['pypdf_text_path'])
        candidates = doc['worksheet_header_candidate_pages']
        starts = []
        for hp in candidates:
            compact = re.sub(r'\s+', '', texts[hp - 1])
            if all(re.sub(r'\s+', '', label) in compact for label in LABELS):
                starts.append(hp)
            else:
                nonworksheets.append({'case': doc['case'], 'source_page': hp, 'source_pdf_sha256': doc['sha256'],
                                      'disposition': 'correspondence_mentions_a_worksheet_label_without_the_28_field_header'})
        used = set()
        with pdfplumber.open(ROOT / doc['retained_path']) as pdf:
            for index, hp in enumerate(starts):
                pi = hp - 1
                try:
                    ht = clean(pdf.pages[pi]).extract_tables()[0]
                    legacy = len(ht[0]) > 1 and bool(ht[0][1])
                    if legacy:
                        compact = re.sub(r'\s+', '', texts[pi])
                        assert all(re.sub(r'\s+', '', label) in compact for label in LABELS)
                        fields = {label: ht[i][1] or None for i, label in enumerate(LABELS)}
                    else:
                        assert [r[0] for r in ht[:28]] == LABELS
                    table = clean(pdf.pages[pi + 1]).extract_tables()[0]
                    age_col = 0 if legacy else 1
                    assert len(table) == 39 and [r[age_col] for r in table[2:]] == AGES
                    if not legacy:
                        fields = {label: table[i][0] or None for i, label in enumerate(LABELS)}
                    columns = [{'page': hp + 1, 'column': ci, 'class_raw': table[0][ci], 'sex_raw': table[1][ci],
                                'values': [r[ci] for r in table[2:]]} for ci in range(age_col + 1, len(table[0]))]
                    source_pages = [hp, hp + 1]
                    next_start = starts[index + 1] if index + 1 < len(starts) else len(texts) + 1
                    if hp + 2 < next_start:
                        candidate = clean(pdf.pages[pi + 2]).extract_tables()
                        if candidate and len(candidate[0]) == 39 and all(MONEY.fullmatch(str(c or '')) for row in candidate[0][2:] for c in row):
                            source_pages.append(hp + 2)
                            for ci in range(len(candidate[0][0])):
                                columns.append({'page': hp + 2, 'column': ci, 'class_raw': candidate[0][0][ci],
                                                'sex_raw': candidate[0][1][ci], 'values': [r[ci] for r in candidate[0][2:]]})
                    assert fields['Filing Company'] and all(c['class_raw'] and c['sex_raw'] for c in columns)
                    assert columns and all(MONEY.fullmatch(str(v or '')) for c in columns for v in c['values'])
                    status = 'APPROVED' if 'APPROVED' in texts[pi] else 'REPLACED' if 'REPLACED' in texts[pi] else 'unknown'
                    assert status != 'unknown'
                    period = periods.get(doc['case']) if status == 'APPROVED' else None
                    sid = f"{doc['case']}:p{hp}"
                    schedule = {'id': sid, 'case': doc['case'], 'status': status, 'source_pages': source_pages,
                                'source_pdf_sha256': doc['sha256'], 'fields': fields,
                                'layout': 'legacy_fields_on_header' if legacy else 'split_label_and_value_pages',
                                'source_columns': [{k: v for k, v in c.items() if k != 'values'} for c in columns],
                                'policy_issue_range_from': fields['Date Range From'], 'policy_issue_range_through': fields['Date Range Thru'],
                                'policy_issue_dates_are_not_rate_periods': True,
                                'rate_effective_from': period['effective_from'] if period else None,
                                'rate_effective_through': period['effective_through'] if period else None,
                                'rate_effective_basis': 'filing_approval_letter' if period else 'not_established_for_this_schedule',
                                'personal_quote': False, 'current_sale': 'unknown', 'acceptance': 'pending'}
                    schedules.append(schedule)
                    used.update(source_pages)
                    for ci, column in enumerate(columns):
                        for ri, (age, amount) in enumerate(zip(AGES, column['values'])):
                            rates.append({'id': f'{sid}:c{ci}:r{ri}', 'schedule_id': sid, 'case': doc['case'],
                                          'source_page': column['page'], 'source_column': column['column'],
                                          'source_pdf_sha256': doc['sha256'], 'source_status': status,
                                          'age_raw': age, 'class_raw': column['class_raw'], 'sex_raw': column['sex_raw'],
                                          'amount_raw': amount, 'annual_premium_cents': cents(amount), 'unit': 'USD/year',
                                          'zero_meaning': 'unresolved_not_a_free_offer' if cents(amount) == 0 else None,
                                          'rate_effective_from': schedule['rate_effective_from'], 'rate_effective_through': schedule['rate_effective_through'],
                                          'personal_quote': False, 'acceptance': 'pending'})
                except (AssertionError, IndexError, KeyError, TypeError, ValueError) as error:
                    holds.append({'case': doc['case'], 'source_header_page': hp, 'reason': str(error) or type(error).__name__,
                                  'source_pdf_sha256': doc['sha256'], 'state': 'unresolved_internal_extraction'})
                finally:
                    for page in pdf.pages[pi:min(pi + 3, len(pdf.pages))]:
                        page.close()
        for i, text in enumerate(texts):
            role = 'source_rate_worksheet' if i + 1 in used else 'sparse_page_requires_review' if len(text.strip()) < 80 else 'retained_source_text_requires_scoped_interpretation'
            page_records.append({'case': doc['case'], 'page': i + 1, 'role': role, 'source_pdf_sha256': doc['sha256'],
                                 'text_sha256': hashlib.sha256(text.encode()).hexdigest(), 'text_characters': len(text.strip()),
                                 'consumer_retrieval_enabled': False})
        print({'built': doc['case'], 'schedules': sum(s['case'] == doc['case'] for s in schedules),
               'holds': sum(h['case'] == doc['case'] for h in holds)}, flush=True)
    for name, rows in [('schedules.json', schedules), ('rate-cells.json', rates), ('approval-letters.json', approvals),
                       ('page-inventory.json', page_records), ('worksheet-holds.json', holds), ('nonworksheet-candidates.json', nonworksheets)]:
        write(out / name, rows)
    coverage = {'source_packets': len(documents), 'pages': len(page_records),
                'worksheet_header_candidates': sum(len(d['worksheet_header_candidate_pages']) for d in documents),
                'nonworksheet_candidates': len(nonworksheets), 'worksheet_headers': len(schedules) + len(holds),
                'schedules': len(schedules), 'schedule_status_counts': dict(Counter(s['status'] for s in schedules)),
                'annual_source_cells': len(rates), 'annual_cell_status_counts': dict(Counter(r['source_status'] for r in rates)),
                'approval_letter_periods': len(approvals), 'unresolved_worksheet_extractions': len(holds),
                'human_acceptance': None, 'consumer_release_enabled': False, 'full_l10_complete': False}
    write(out / 'coverage.json', coverage)
    return coverage


if __name__ == '__main__':
    import json
    print(json.dumps(build(), indent=2))
