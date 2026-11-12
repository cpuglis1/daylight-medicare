"""Source-linked conditions and comparisons for the new targeted filing intake."""
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import re

from l10_targeted_intake import ROOT, BASE, PACKET, OUT, guard, read, write

PRIOR = {'26-007296': '25-007663', '26-018953': '25-030887', '26-023593': '25-023045', '26-036521': '25-039153'}
ORIGINAL = {'26-007296': ['17-20542', '20-013251'], '26-018953': ['21-014407'],
            '26-023593': ['22-005454'], '26-036521': ['23-008889']}
KEY_FIELDS = ['Issuing Carrier', 'Form Number', 'Plan', 'Insurance Type', 'Date Range From', 'Date Range Thru',
              'Underwritten (Yes/No)', 'Rating Class', 'Sex Distinct', 'Smoker Distinct', 'Region']


def norm(text):
    return ' '.join(text.split())


def key(schedule):
    return tuple(schedule['fields'][f] for f in KEY_FIELDS)


def exact_form_mention(form, text):
    # A base F/G code must not match the corresponding high-deductible code.
    return bool(re.search(r'(?<![A-Za-z0-9])' + re.escape(form) + r'(?![A-Za-z0-9(])', text))


def ages(band):
    if band == 'Under 65':
        return ['0-64']
    if band == '80+':
        return [str(n) for n in range(80, 100)] + ['100+']
    if '-' in band:
        a, b = map(int, band.split('-'))
        return [str(n) for n in range(a, b + 1)]
    return [band]


def reconcile(out=OUT):
    out = Path(out)
    if out.resolve() == OUT.resolve():
        guard()
    if (out / 'SEALED').exists():
        raise ValueError('Use a new revision')
    docs = {d['case']: d for d in read(PACKET / 'intake.json')['documents']}
    texts = {case: read(ROOT / d['pypdf_text_path']) for case, d in docs.items()}
    schedules = read(out / 'schedules.json')
    rates = read(out / 'rate-cells.json')
    old_schedules = read(BASE / 'filing-reconciliation-r3/build-r1/schedules.json')
    conditions = []

    def fact(case, page, excerpt, values, meaning, hold=None):
        text = texts[case][page - 1]
        assert norm(excerpt) in norm(text), (case, page, excerpt)
        conditions.append({'id': f'{case}:r5-condition:{len(conditions) + 1}', 'case': case,
                           'source_page': page, 'source_pdf_sha256': docs[case]['sha256'], 'excerpt': excerpt,
                           'source_page_approved_stamp': 'APPROVED' in text, 'values': values, 'meaning': meaning,
                           'remaining_interpretation': hold, 'acceptance': 'pending', 'personal_applicability': 'not_determined',
                           'consumer_release_enabled': False})

    for case in ['25-043172', '25-043125']:
        fact(case, 3, 'Gross Monthly Premiums\nEffective January 1, 2026',
             {'published_exhibit_effective_from': '2026-01-01', 'unit': 'USD/month', 'schedule_approval_period': None},
             'Explicit date on the source monthly exhibit. Not an approval-letter interval for every annual worksheet.')
        fact(case, 4, 'Proposed Gross Monthly Premiums - Non Tobacco\nEffective January 1, 2026',
             {'published_exhibit_effective_from': '2026-01-01', 'source_status_word': 'Proposed', 'tobacco': 'non-tobacco'},
             'Retain the proposed label even though other pages carry approved schedule stamps.',
             'Final approved period and exhibit-to-approved-schedule form/amount differences remain distinct.')
        fact(case, 6, 'Proposed Gross Monthly Premiums - Tobacco\nEffective January 1, 2026',
             {'published_exhibit_effective_from': '2026-01-01', 'source_status_word': 'Proposed', 'tobacco': 'tobacco'},
             'Tobacco exhibit, with exact source status preserved.')

    fact('21-014407', 442, 'you reside with your spouse, including validly recognized civil union or domestic partner, who currently holds or is applying for a Medicare Supplement policy with American Benefit Life Insurance Company',
         {'household_route': 'spouse_civil_union_or_domestic_partner', 'co_residence_required': True,
          'other_person_ABL_policy': 'holds_or_applying'}, 'Exact first household eligibility route on approved ABLMS06751FL.')
    fact('21-014407', 442, 'you have been living with a family member for th e last twelve months who is age 50 or older and who holds or is applying for a Medicare Supplement policy with American Benefit Life Insurance Company',
         {'household_route': 'family_member', 'co_residence_months': 12, 'minimum_other_person_age': 50,
          'other_person_ABL_policy': 'holds_or_applying'}, 'Exact alternative route; it is not any unrelated co-resident.')
    fact('21-014407', 442, 'the discount will be 3.5 percent lower than the individual rates and will apply as long as these requirements are met.',
         {'household_discount_percent': '3.5', 'continuing_qualification_required': True}, 'Discount percentage and continuing condition.')
    fact('21-014407', 442, 'Upon verification of eligibility and approval of your application, you will qualify for the discount.',
         {'verification_required': True, 'application_approval_required': True}, 'A reported household answer is not company approval.')
    fact('21-014407', 505, 'Annual premium x modal factor = modal premium (round to nearest whole cent)\nModal premium x .965 = discounted premium',
         {'calculation_order': ['annual_times_mode', 'round_modal_to_cent', 'modal_times_0.965'], 'discount_multiplier': '0.965'},
         'Approved outline supplies calculation order. Source form uses bracketed variable sample amounts; those examples do not become 2026 rates.',
         'Final discount-result rounding and later form amendments remain review questions before personal billing.')
    fact('21-014407', 443, 'This one-time fee will be refunded, along with your premium, if the policy is not issued or you return it during your 30-day free look.',
         {'fee_frequency': 'one_time', 'refund_cases': ['policy_not_issued', 'returned_during_30_day_free_look']},
         'Approved application qualifies the separately shown policy fee.')
    fact('21-014407', 443, 'Draft date cannot be on the 29th, 30th or 31st of the month.',
         {'excluded_draft_days': [29, 30, 31]}, 'Source application payment constraint; not a personal payment instruction.')
    fact('22-005454', 46, 'In the past 12 months did you use any tobacco products, nicotine replacement products, electronic cigarettes or vapor cigarettes (excluding the use of 2 or fewer cigars per month)?',
         {'lookback_months': 12, 'source_cigar_exception': '2_or_fewer_per_month'},
         'AP2098FL question text is retained; no underwriting classification or eligibility is decided.')
    fact('22-005454', 46, 'An “Authorization to Draft Initial Premium” form must be completed with these selections.',
         {'initial_draft_authorization_required_where_marked': True}, 'Preserve the application asterisk and relevant selections.')
    fact('23-008889', 88, 'There will be a one-time policy fee of $25.00 added to the first premium.',
         {'fee_cents': 2500, 'fee_frequency': 'one_time', 'added_to': 'first_premium'}, 'Approved outline resolves fee placement for this form source.')
    for case, page in [('17-20542', 541), ('20-013251', 111)]:
        fact(case, page, 'Your first month’s premium payment must be included. This is necessary even if you choose our Automatic Bank Withdrawal or Auto Credit Card Charge options for future premium payments.',
             {'initial_month_payment_required': True, 'future_autopay_does_not_replace_initial_payment': True},
             'Original approved enrollment application payment requirement; original-form date is retained.')
    for case, page in [('17-20542', 546), ('20-013251', 116)]:
        fact(case, page, 'Future Payment options:', {'source_payment_section': 'future_payment_options'},
             'The full page retains Automatic Withdrawal, Coupon Book and Auto Credit Card Charge choices; no mode precision conflict is resolved by the menu.')

    prior_by_key = defaultdict(list)
    for s in schedules:
        if s['status'] == 'APPROVED' and s['case'] in PRIOR.values():
            prior_by_key[(s['case'], key(s))].append(s)
    continuity = []
    for s in old_schedules:
        if s['status'] != 'APPROVED' or s['case'] not in PRIOR:
            continue
        candidates = prior_by_key[(PRIOR[s['case']], key(s))]
        assert len(candidates) == 1, (s['id'], len(candidates))
        p = candidates[0]
        adjacent = date.fromisoformat(p['rate_effective_through']) + timedelta(days=1) == date.fromisoformat(s['rate_effective_from'])
        covers = adjacent and p['rate_effective_from'] <= '2026-01-01' and s['rate_effective_through'] >= '2026-12-31'
        continuity.append({'newer_schedule_id': s['id'], 'prior_schedule_id': p['id'], 'exact_identity_fields': KEY_FIELDS,
                           'prior_interval': [p['rate_effective_from'], p['rate_effective_through']],
                           'newer_interval': [s['rate_effective_from'], s['rate_effective_through']],
                           'intervals_adjacent': adjacent, 'published_grid_intervals_cover_2026': covers,
                           'current_sale': 'unknown', 'personal_applicability': 'not_determined', 'acceptance': 'pending'})
    assert len(continuity) == 67 and all(r['published_grid_intervals_cover_2026'] for r in continuity)

    form_bindings = []
    worksheet_pages = {(r['case'], page) for r in schedules for page in r['source_pages']}
    for newer, originals in ORIGINAL.items():
        forms = sorted({s['fields']['Form Number'] for s in old_schedules if s['case'] == newer and s['status'] == 'APPROVED'})
        for form in forms:
            evidence = []
            for case in originals:
                for i, text in enumerate(texts[case]):
                    if 'APPROVED' in text and exact_form_mention(form, text) and (case, i + 1) not in worksheet_pages:
                        evidence.append({'case': case, 'page': i + 1, 'source_pdf_sha256': docs[case]['sha256']})
            assert evidence, (newer, form)
            form_bindings.append({'newer_case': newer, 'form_raw': form, 'original_approved_text_pages': evidence,
                                  'later_amendments_checked': False, 'current_sale': 'unknown', 'acceptance': 'pending'})

    source_rows = read(BASE / 'build-r2/carrier-table-observations.json')
    rates_by_schedule = defaultdict(list)
    for r in rates:
        rates_by_schedule[r['schedule_id']].append(r)
    comparisons = []
    for i, row in enumerate(source_rows):
        case = '25-043125' if row['select'] else '25-043172'
        candidates = [s for s in schedules if s['case'] == case and s['status'] == 'APPROVED'
                      and s['fields']['Region'] == '2010 Area 2' and s['fields']['Plan'] == row['variant']]
        assert len(candidates) == 1
        s = candidates[0]
        matched = [r for r in rates_by_schedule[s['id']] if r['age_raw'] in ages(row['age_band_raw'])
                   and r['class_raw'] == ('Smoker' if row['tobacco'] == 'tobacco' else 'Non-Smoker')]
        assert len(matched) == len(ages(row['age_band_raw']))
        if row['payment_basis'] == 'regular_monthly':
            same = all(Decimal(r['annual_premium_cents']) / 12 == row['premium_cents'] for r in matched)
            state = 'same_arithmetic_monthly_amount' if same else 'different_arithmetic_monthly_amount'
        else:
            same = None
            state = 'APO_billing_precision_and_conditions_held'
        comparisons.append({'carrier_observation_index': i, 'source_id': row['source_id'], 'source_page': row['page'],
                            'source_monthly_cents': row['premium_cents'], 'schedule_id': s['id'], 'form_raw': s['fields']['Form Number'],
                            'candidate_rate_ids': [r['id'] for r in matched], 'status': state, 'same_arithmetic_amount': same,
                            'form_equivalence_accepted': False, 'approved_rate_interval_established': False,
                            'personal_quote': False, 'acceptance': 'pending'})
    counts = Counter(r['status'] for r in comparisons)
    write(out / 'conditions.json', conditions)
    write(out / 'interval-continuity.json', continuity)
    write(out / 'original-form-bindings.json', form_bindings)
    write(out / 'blue-carrier-comparisons.json', comparisons)
    summary = {'new_condition_records': len(conditions), 'exact_schedule_interval_pairs': len(continuity),
               'original_form_identifiers_with_approved_text': len(form_bindings), 'carrier_rows_compared': len(comparisons),
               'blue_comparison_status_counts': dict(counts), 'targeted_packets_acquired': 11,
               'targeted_acquisition_complete': True, 'full_l10_complete': False, 'human_acceptance': None,
               'consumer_release_enabled': False}
    write(out / 'reconciliation-summary.json', summary)
    return summary


if __name__ == '__main__':
    import json
    print(json.dumps(reconcile(), indent=2))
