"""Additive source conditions, census and review ledger for owner filing PDFs.

This is a finite transcription packet, not a personal premium calculator or an
assertion that the statewide/Collier market denominator has been established.
"""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l10-medigap-2026-10-28'
PACKET = BASE / 'filing-reconciliation-r3'
OUT = PACKET / 'build-r1'
REGIONS = {'26-007296': 'Area 2', '26-018953': '1',
           '26-023593': '320 to 322 327 to 329 335 to 339 341 to 349', '26-036521': 'Area 1'}


def read(p):
    return json.loads(Path(p).read_text())


def write(p, v):
    Path(p).write_text(json.dumps(v, indent=2, sort_keys=True, ensure_ascii=False) + '\n')


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def norm(t):
    return ' '.join(t.split())


def enrich(out=OUT):
    out = Path(out)
    if (out / 'SEALED').exists():
        raise ValueError('Sealed filing revision; use a new output directory')
    docs = read(PACKET / 'intake.json')['documents']
    schedules = read(out / 'schedules.json')
    rates = read(out / 'rate-cells.json')
    facts = []

    def fact(case, page, excerpt, values, meaning, hold=None):
        doc = next(d for d in docs if Path(d['retained_path']).name.startswith(case))
        text = read(PACKET / 'text' / (Path(doc['retained_path']).stem + '-pypdf.json'))[page-1]
        assert norm(excerpt) in norm(text), (case, page, excerpt)
        facts.append({'id': f'{case}:condition:{len(facts)+1}', 'case': case, 'source_page': page,
                      'source_pdf_sha256': doc['sha256'], 'excerpt': excerpt, 'values': values,
                      'meaning': meaning, 'interpretation_hold': hold, 'acceptance': 'pending',
                      'personal_applicability': 'not_determined', 'consumer_release_enabled': False})

    fact('26-007296', 40, 'Collier 10100 2', {'county': 'Collier', 'source_county_code': '10100', 'region': 'Area 2'},
         'Exact county assignment in Exhibit 5; the published Area 2 schedule already includes its area basis.')
    fact('26-007296', 40, '2 0.950', {'region': 'Area 2', 'area_factor': '0.950'},
         'Do not apply the area factor again to a region-specific annual worksheet amount.')
    fact('26-007296', 5, 'The only premium payment mode available is monthly (1/12 of the annual rates shown in Exhibit 4).',
         {'monthly_basis_memo': '1/12'}, 'Worksheet monthly factor is separately retained as 0.0833.',
         'Exact billing/rounding interpretation between 1/12 and 0.0833 is unresolved; no calculator.')
    fact('26-007296', 4, 'For clarification, an open enrollee or guarantee issue enrollee who is a tobacco user will be assigned to the standard class.',
         {'source_class_condition': 'tobacco user in open enrollment or guaranteed issue -> standard'},
         'Source statement only. No determination of an individual enrollment right or underwriting result.')
    fact('26-018953', 183, 'A 3.5% household discount is available based upon the response to the application question.',
         {'household_discount_percent': '3.5', 'condition': 'response to the application question'},
         'Application question/qualifying answer and discount ordering are not established by this sentence.',
         'Do not apply household discount without the exact eligibility and calculation basis.')
    fact('26-018953', 183, 'There is a one-time $25 application fee.',
         {'application_fee_cents': 2500, 'frequency': 'one_time'}, 'Separate fee; not automatically included in annual grid premium.')
    fact('26-018953', 183, '1 320-321, 323-327, 338-339, 341-342, 344, 347 1.09',
         {'zip_prefixes_for_Collier_test_cases': ['341'], 'region': '1', 'area_factor': '1.09'},
         'All 25 retained OIR Collier ZIP test cases start with 341. This is a rating-area join, not a county sale conclusion.')
    fact('26-018953', 181, 'ABLMS21A-FL, ABLMS21F-FL, ABLMS21G-FL, ABLMS21N-FL',
         {'memo_form_prefix': 'ABLMS21', 'worksheet_and_approval_prefix': 'ABLMSP21'},
         'Memo omits P present in the approved schedules and approval heading.',
         'Form-string discrepancy retained; no automatic form equivalence or personal applicability.')
    fact('26-018953', 181, 'The rate increase will apply to both inforce and new business policies.',
         {'source_business_basis': ['inforce', 'new_business']},
         'Filing intent for these forms; approval alone does not establish current sale or individual acceptance.')
    fact('26-023593', 3, '320-322, 328-329, 335-339, 341-349 1.07',
         {'zip_prefixes_for_Collier_test_cases': ['341'], 'region': REGIONS['26-023593'], 'area_factor': '1.07'},
         'Collier test ZIP prefix 341 agrees. Worksheet additionally lists 327; do not resolve that other-prefix discrepancy by inference.',
         '327 appears in worksheet but not this memo row; Collier 341 join is unaffected.')
    fact('26-023593', 3, 'Premiums vary by the policyholder’s issue age, gender, zip code and tobacco use.',
         {'rating_dimensions': ['issue_age', 'gender', 'zip_code', 'tobacco_use']},
         'Source class labels are retained; an exact grid match does not determine eligibility.')
    fact('26-036521', 3, '$25 one-time policy fee collected from the applicant',
         {'policy_fee_cents': 2500, 'frequency': 'one_time'}, 'Separate fee, corroborated by approved worksheet at-issue fee field.')
    fact('26-036521', 5, '1 1.00 320-321, 323-329, 335, 337-339, 341-342, 344, 347',
         {'zip_prefixes_for_Collier_test_cases': ['341'], 'region': 'Area 1', 'area_factor': '1.00'},
         'Rating-area assignment only; not proof that a particular person can buy the policy.')
    fact('26-036521', 5, 'Monthly 0.08333', {'monthly_basis_memo': '0.08333'},
         'Approved worksheet separately records 0.0833.',
         'Source precision differs; exact monthly billing is held.')
    fact('26-036521', 7, 'Premium = Round(Round(Rate *Area, 2) * Mode, 2)',
         {'rounding_formula_raw': 'Premium = Round(Round(Rate *Area, 2) * Mode, 2)'},
         'Rounding order retained. Native workbook, tie-rounding semantics and modal precision need resolution before a calculator.')

    # Explicit annual instruction appears in each packet, outside overprinted grids.
    for doc in docs:
        case = Path(doc['retained_path']).name[:9]
        pages = read(PACKET / 'text' / (Path(doc['retained_path']).stem + '-pypdf.json'))
        pi = next(i for i, text in enumerate(pages) if 'All Rates are ANNUAL.' in norm(text))
        fact(case, pi+1, 'All Rates are ANNUAL.', {'unit': 'USD/year'},
             'Source collection unit. No automatic conversion to a monthly billing premium.')
    write(out / 'conditions.json', facts)

    sparse = read(PACKET / 'sparse-page-review.json')
    page_inventory = read(out / 'page-inventory.json')
    sparse_map = {(p['case'], p['page']): p for p in sparse}
    interrogatories = {('26-007296', 82), ('26-018953', 38), ('26-023593', 36)}
    blank_pages = {('26-007296', p) for p in list(range(20,25))+list(range(35,40))}
    blank_pages |= {('26-023593', p) for p in [45,48,115,118,129]}
    for p in page_inventory:
        key = (p['case'], p['page'])
        if key not in sparse_map:
            continue
        if key in interrogatories:
            role = 'retained_image_interrogatory_no_rate_table'
        elif key in blank_pages:
            role = 'visually_blank_page'
        elif key == ('26-036521', 16):
            role = 'sparse_supporting_percentage_not_a_premium'
        else:
            role = 'visually_empty_worksheet_grid_with_footer'
        p['role'] = role
        p['sparse_visual_review'] = '150dpi render/contact-sheet inspection plus OCR; no new premium inferred'
        p['render_sha256'] = sparse_map[key]['render_sha256']
    write(out / 'page-inventory.json', page_inventory)

    # Every source schedule participates in the exact form/type/issue-block census.
    products = defaultdict(list)
    for s in schedules:
        f = s['fields']
        key = (f['Issuing Carrier'], f['Form Number'], f['Plan'], f['Insurance Type'],
               s['policy_issue_range_from'], s['policy_issue_range_through'])
        products[key].append(s)
    census = []
    for key, ss in sorted(products.items()):
        company, form, plan, kind, issue_from, issue_to = key
        approved = [s for s in ss if s['status'] == 'APPROVED']
        census.append({'company': company, 'form_raw': form, 'plan_raw': plan, 'insurance_type_raw': kind,
                       'policy_issue_from_raw': issue_from, 'policy_issue_through_raw': issue_to,
                       'schedule_ids': [s['id'] for s in ss], 'approved_schedule_ids': [s['id'] for s in approved],
                       'regions_raw': sorted({s['fields']['Region'] for s in ss}),
                       'source_statuses': sorted({s['status'] for s in ss}),
                       'collier_grid_period_sourced': any(s['case'] in REGIONS and s['fields']['Region'] == REGIONS[s['case']] for s in approved),
                       'current_sale': 'unknown', 'group_membership_applicability': 'not_determined',
                       'select_network_applicability': 'not_determined' if 'Select' in kind else 'not_a_SELECT_source_label',
                       'full_2026_continuity': 'not_established', 'acceptance': 'pending'})
    write(out / 'filed-product-census.json', census)

    # Map the entire retained lead catalog; historical names are never promoted to
    # current products. The queue's extent is the parent catalog, not the market.
    catalog = read(BASE / 'build-r2/insurer-catalog.json')
    details = read(BASE / 'build-r2/filing-details.json')
    cases_by_name = defaultdict(list)
    for detail in details:
        n = detail['source_native']
        for co in n['Companies']:
            if n['FilingType'] in ['Rates', 'Both'] and n['FinalAction'] == 'APPROVED':
                cases_by_name[co['CoNm']].append({'case': n['FileLogNumber'], 'product_raw': n['ProdNm'],
                                                 'filing_type': n['FilingType'], 'state': 'metadata_lead_only',
                                                 'source_id': detail['source_id']})
    names = {s['fields']['Issuing Carrier'] for s in schedules}
    queue = []
    for co in catalog:
        name = co['company_name_raw']
        queue.append({'company_raw': name, 'naic_exact_name_association': co['exact_name_unique_naic'],
                      'in_CHOICES_samples': co['choices_observation_count'] > 0,
                      'filed_in_2026': co['filed_2026'],
                      'owner_packet_obtained': name in names,
                      'approved_2026_filed_rate_case_leads': cases_by_name[name],
                      'state': 'partial_packet_plus_required_scope_evidence' if name in names else 'required_source_and_classification',
                      'closure_evidence': ['2026-effective forms and business state', 'applicable Collier/SELECT/group conditions',
                                           'approved tables, manuals and interval continuity', 'exact R15/source-use/acceptance decisions']})
    write(out / 'company-source-queue.json', queue)

    collier_sids = {s['id'] for s in schedules if s['status'] == 'APPROVED' and s['case'] in REGIONS and s['fields']['Region'] == REGIONS[s['case']]}
    before_after = {
        'scope': 'Six supplied filing PDFs only; parent r2 remains unchanged',
        'before': {'owner_filing_pdfs': 0, 'filed_schedule_cells_reproduced': 0, 'letter_sourced_rate_periods': 0},
        'after': {'owner_filing_pdfs': len(docs), 'pages': sum(d['pages'] for d in docs),
                  'schedules_all_statuses': len(schedules), 'annual_cells_all_statuses': len(rates),
                  'annual_cells_approved': sum(r['source_status'] == 'APPROVED' for r in rates),
                  'approved_Collier_annual_cells_with_sourced_period': sum(r['schedule_id'] in collier_sids for r in rates),
                  'letter_sourced_rate_periods': len(read(out/'approval-letters.json')),
                  'condition_records': len(facts), 'source_form_issue_type_groups': len(census),
                  'company_leads_accounted': len(queue)},
        'same_annual_CHOICES_grid_amounts': read(out/'comparison-summary.json')['status_counts'],
        'consumer_release_enabled': False, 'human_acceptance': None, 'full_l10_complete': False}
    write(out / 'before-after.json', before_after)
    gaps = [
        {'id': 'F01', 'state': 'required_incomplete_census', 'scope': 'Complete 2026 Collier product/form/sale-state denominator',
         'remaining': '188 historical company leads are all retained but do not prove 2026 continuation, sale or county applicability. The 34 CHOICES names are a sample extent.',
         'next_action': 'Reconcile applicable official statewide collection and permitted dated carrier product evidence, retaining closed/unknown/group/SELECT options.', 'work_owner': 'AI source collection/reconciliation; source owner only for inaccessible records'},
        {'id': 'F02', 'state': 'required_missing_packets', 'scope': '29 CHOICES companies plus other applicable census products',
         'remaining': 'No applicable filed rate PDF packet in this intake. Exact company queue and approved-2026 filing leads are retained; no-history-in-2026 is not no product.',
         'next_action': 'Use the pending OIR collection first; classify prior-effective filings and permitted carrier manuals. Do not ask owner to retype values.', 'work_owner': 'AI; OIR delivery or owner-mediated challenge where required'},
        {'id': 'F03', 'state': 'required_period_continuity', 'scope': 'January 1, 2026 to each supplied approval start',
         'remaining': 'Four approval periods start August, September or November. Replaced proposal grids do not establish the earlier legally effective rates.',
         'next_action': 'Acquire actual prior approval/table/manual and any intervening amendments or termination evidence.', 'work_owner': 'AI and source owner'},
        {'id': 'F04', 'state': 'required_source_period_and_SELECT_relationship', 'scope': 'Florida Blue standard and SELECT',
         'remaining': 'Public approved schedules lack a proven premium effective period; related restricted actuarial-memo titles explicitly say 2027. Policy-issue ranges and OIR action dates are not substitutes for 2026 applicability. Legacy forms and SELECT conditions stay distinct.',
         'next_action': 'Obtain permitted approval/effective-date evidence or authoritative written clarification and exact form/area/network joins.', 'work_owner': 'Source owner evidence, then AI comparison'},
        {'id': 'F05', 'state': 'required_rating_reconstruction_and_interpretation', 'scope': 'Whole rating models, fees, discounts, modes and rounding',
         'remaining': 'Annual cells reproduced; exact monthly billed premiums, household qualification/order, mode precision differences, ABL form discrepancy and current-sale/underwriting applicability remain unresolved.',
         'next_action': 'Collect missing application/manual/workbook bases; validate full calculation boundaries before specialist R15 review.', 'work_owner': 'AI mechanical work; qualified reviewer resolves actual ambiguity'},
        {'id': 'F06', 'state': 'required_review_and_release_decisions', 'scope': 'Exact new revision',
         'remaining': 'No human acceptance, source-use decision or consumer activation for these observations; technical audit cannot supply them.',
         'next_action': 'Review the exact sealed packet and resolve the preceding evidence gaps. Personal quotes/recommendations require their separate gates.', 'work_owner': 'Exact-scope source/domain/owner reviewers'}]
    write(out / 'gaps.json', gaps)
    return before_after


if __name__ == '__main__':
    print(json.dumps(enrich(), indent=2))
