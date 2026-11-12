"""Replay two specific 2026 Collier cases using sealed research and public observations."""
from contextlib import closing
from dataclasses import replace
from datetime import date
import json
from pathlib import Path
import sqlite3
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ADVISOR = ROOT / 'alternatives/advisor-first'
ENGINE = ADVISOR.parent / 'chat-first/cms-slice'
DATA = ROOT / 'docs/data'
sys.path[:0] = [str(p) for p in (ADVISOR, ADVISOR / 'tests', ENGINE / 'scripts', ROOT / 'cms-slice/scripts')]

from comparison_engine import build_comparison
from comparison_methods import IdentityBinding, MustHave, assess_identity_binding, evaluate_must_have
from comparison_preview import preview_for_snapshot
from guest_profiles import ProfileError
from l13_synthetic import aep, initial_cd_coverage, ma_icep, ordinary_age65_iep
from test_comparison_methods import SCOPE, SCOPE_KEY, fact, finding, profile

HUMANA, WELLCARE = '2026:H1036:217:000', '2026:H1032:198:000'
PLANS = (HUMANA, WELLCARE)
PRODUCTS = {'immediate_release': '861007', 'extended_release': '860975'}
DRUG_COVERAGE = DATA / 'l05-drug-coverage-2026-10-25/build-r3/inventory.sqlite3'
PHARMACY_NETWORK = DATA / 'l07-pharmacy-networks-2026-10-27/build-r1/inventory.sqlite3'
PROVIDERS = DATA / 'l08-provider-networks-2026-10-27/wellcare-r5/providers.sqlite3'


def rows(path, statement, args):
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        return db.execute(statement, args).fetchall()


def one(path, statement, args):
    result = rows(path, statement, args)
    assert len(result) == 1, (path, args, len(result))
    return result[0]


def eligibility():
    election = date(2026, 11, 4)
    reported_first_ab = date(2026, 11, 1)
    age_eligibility, _, part_b_iep_end = ordinary_age65_iep(date(1961, 11, 15))
    assert reported_first_ab == age_eligibility
    first_ab = reported_first_ab
    start, end = ma_icep(first_ab, part_b_iep_end)
    effective = initial_cd_coverage(first_ab, election)
    aep_start, aep_end, aep_effective = aep(2027)
    zip_entry = json.loads((ENGINE / 'apps/chat/zip-counties.json').read_text())['zips']['34102']
    assert zip_entry == [['12021', 'Collier County', 'FL']]
    assert start <= election <= end and effective == date(2026, 12, 1)
    assert aep_start <= election <= aep_end and aep_effective == date(2027, 1, 1)
    return {'state': 'initial_election_path_supported_on_fictional_inputs', 'zip': '34102',
            'county_fips': '12021', 'first_a_and_b': first_ab.isoformat(), 'election': election.isoformat(),
            'initial_election_start': start.isoformat(), 'initial_election_end': end.isoformat(),
            'initial_election_effective': effective.isoformat(), 'annual_election_effective': aep_effective.isoformat(),
            'personal_entitlement_or_enrollment_verified': False}


def doctor():
    locator, page, raw = one(PROVIDERS, """
        SELECT r.id, r.page, r.fields_json FROM r5_wellcare_records r
        JOIN r5_plan_directory_bindings b USING (document_sha256)
        WHERE b.offering_id=? AND r.publisher_provider_id=? AND r.county_raw='Collier'
          AND json_extract(r.fields_json, '$.name_raw')='Josephson, Mark MD'
          AND r.section_raw='Primary Care Providers (PCP)'
        """, (WELLCARE, '4993016'))
    assert page == 13 and json.loads(raw)['addresses'][0]['street_raw'] == '311 9th St, Ste 306'
    humana_matches = rows(PROVIDERS, """
        SELECT page FROM r4_humana_entries JOIN r3_plan_directory_bindings USING (document_sha256)
        WHERE offering_id=? AND lower(json_extract(r4_humana_entries.fields_json,'$.name_raw')) LIKE '%josephson%mark%'
        """, (HUMANA,))
    assert humana_matches == []
    return {HUMANA: {'december_status': 'unresolved_adverse_group_signal', 'exact_directory_match': None,
                     'december_access_verified': False},
            WELLCARE: {'december_status': 'dated_exact_listing_personal_access_unresolved', 'directory_record': locator,
                       'december_access_verified': False, 'page': page, 'nch_termination_effective': '2027-01-01'}}


def medicine(offering, form, public):
    formulary, ordinal, ndc, fields = one(DRUG_COVERAGE, """
        SELECT p.formulary_id,d.ordinal,d.ndc,d.modeled_json FROM plans p
        JOIN drug_rows d ON d.formulary_id=p.formulary_id
        WHERE p.offering_id=? AND d.table_name='basic' AND d.rxcui=?
        """, (offering, PRODUCTS[form]))
    native = {k: v['value'] for k, v in json.loads(fields).items()}
    part, pharmacy_row, channel = one(PHARMACY_NETWORK, """
        SELECT source_part,source_ordinal,retail_status FROM network
        WHERE offering_id=? AND pharmacy_npi=? AND PHARMACY_ZIPCODE=? AND PHARMACY_RETAIL='Y'
        """, (offering, '1841534534', '34102'))
    observation = public['plans'][offering][form]
    assert channel == public['plans'][offering]['retail_channel']
    assert observation.get('tier', native['TIER_LEVEL_VALUE']) == native['TIER_LEVEL_VALUE']
    assert observation.get('quantity_limit_amount', native['QUANTITY_LIMIT_AMOUNT']) == native['QUANTITY_LIMIT_AMOUNT']
    assert observation.get('quantity_limit_days', native['QUANTITY_LIMIT_DAYS']) == native['QUANTITY_LIMIT_DAYS']
    return {'formulary_id': formulary, 'formulary_version': native['FORMULARY_VERSION'],
            'formulary_row': ordinal, 'rxcui': PRODUCTS[form], 'ndc': ndc, 'tier': native['TIER_LEVEL_VALUE'],
            'quantity_limit': native['QUANTITY_LIMIT_YN'], 'limit_amount': native['QUANTITY_LIMIT_AMOUNT'],
            'limit_days': native['QUANTITY_LIMIT_DAYS'], 'limit_unit': None,
            'prior_authorization_flag': native['PRIOR_AUTHORIZATION_YN'], 'step_therapy_flag': native['STEP_THERAPY_YN'],
            'pharmacy_source': {'part': part, 'ordinal': pharmacy_row, 'channel': channel},
            'plan_finder': observation}


def fixture_checks():
    case = profile()
    doctor_path = 'readiness.facts.RC21.value.items[].practice'
    doctor_ref = fact(case, doctor_path, 'doctor-1')['ref']
    constraint = MustHave('fixture:keep-doctor', 'provider_access', 'beneficiary',
                          SCOPE_KEY, (dict(doctor_ref),), item_id='doctor-1')
    units = ('fixture:a', 'fixture:b')
    supports = finding(units[1], dimension='provider_access', item='doctor-1', identifier='fixture:office-match')
    reports = {}
    for label, candidate in [('hypothetical_verified_control', supports),
                             ('same_candidate_with_unresolved_access', {**supports, 'output_state': 'held'})]:
        result = evaluate_must_have(case, constraint, [candidate], unit_ids=units)
        reports[label] = result['partitions']
        assert result['automatic_personal_order'] is None and result['hidden_unit_ids'] == []
        assert 'defer_decision' in result['available_outcomes']
    assert reports['hypothetical_verified_control']['known_meets'] == [units[1]]
    assert reports['same_candidate_with_unresolved_access']['known_meets'] == []
    assert reports['same_candidate_with_unresolved_access']['unresolved'] == list(units)
    assert reports['same_candidate_with_unresolved_access']['known_conflicts'] == []

    doctor_ref['report_revision'] += 1
    stale = evaluate_must_have(case, constraint, [supports], unit_ids=units)
    assert stale['partitions']['unresolved'] == list(units)
    assert 'CONSTRAINT_REPORT_BINDING_STALE_OR_UNSCOPED' in stale['evaluations'][1]['reason_codes']

    drug_ref = fact(case, 'readiness.facts.RC22.value.items[].form', 'medicine-1')['ref']
    previous_drug = IdentityBinding('drug_product', 'fixture:rxcui', 'fixture:old-product', 'medicine-1',
                                    SCOPE, (dict(drug_ref),), ('fixture:source',))
    before = assess_identity_binding(case, [previous_drug], kind='drug_product', item_id='medicine-1', scope=SCOPE)
    drug_ref['report_revision'] += 1
    after = assess_identity_binding(case, [previous_drug], kind='drug_product', item_id='medicine-1', scope=SCOPE)
    assert before['identity_state'] == 'bound' and after['identity_state'] == 'unresolved'
    real_constraint = replace(constraint, constraint_id='keep-doctor')
    assert evaluate_must_have(case, real_constraint, [], unit_ids=PLANS)['output_state'] == 'held'
    result = build_comparison(profile(), generated_at='2026-11-04T17:07:26+00:00')
    assert result['personalized_recommendation_allowed'] is False
    assert result['authority']['recommendation']['state'] == 'held'
    wrong_year_profile = {'guide': {'fields': {'comparison.scope.county': {'value': {'fips': '12021'}}}},
                          'record': {'facts': {'RC03': {'value': {'year': '2027'}}}}}
    try:
        preview_for_snapshot({3: {}}, 3, wrong_year_profile)
    except ProfileError:
        pass
    else:
        raise AssertionError('The preview returned 2026 results for a 2027 request')
    return {**reports, 'old_site_receipt_after_correction': stale['partitions'],
            'old_drug_identity_before_correction': before['identity_state'],
            'old_drug_identity_after_correction': after['identity_state'],
            'wrong_year_preview_rejected': True,
            'advisor_recommendation_authority': result['authority']['recommendation']['state']}


def main():
    public = json.loads((HERE / 'public-observations.json').read_text())
    pilot = json.loads((HERE.parent / 'recommendation-scope-2026-11-04-r4/pilot.json').read_text())
    offers = {p['offering_id']: p for p in pilot['plans'] if p['offering_id'] in PLANS}
    assert tuple(offers) == PLANS and pilot['scope']['coverage_year'] == public['plan_finder']['year'] == 2026
    terms = {}
    for plan in offers.values():
        published, scenarios = plan['published'], plan['scenarios']
        assert published['coverage']['value']['snp'] is False
        assert published['coverage']['value']['includes_part_d'] is True
        terms[plan['offering_id']] = {
            'part_b_reduction_usd_month': published['part_b_reduction']['value']['amount'],
            'medical_in_network_limit_usd_year': published['medical_maximums']['value']['in_network']['amount'],
            'hospital_three_day_component_usd': scenarios['hospital_days']['3']['amount']['amount'],
        }
    provider = doctor()
    cases = []
    for form, must_keep in zip(PRODUCTS, (False, True)):
        drugs = {offering: medicine(offering, form, public['plan_finder']) for offering in PLANS}
        assert {row['plan_finder']['december_drug_estimate_usd'] for row in drugs.values()} == {'0.00'}
        provider_block = must_keep and not any(row['december_access_verified'] for row in provider.values())
        cases.append({'form': form, 'doctor_is_must_have': must_keep, 'medicine_by_offering': drugs,
                      'comparison_state': 'must_have_hold' if provider_block else 'tradeoffs_ready_for_review',
                      'next_action': ('resolve_exact_doctor_access_and_scope_2027_separately' if provider_block
                                      else 'confirm_initial_election_and_compare_acceptable_2026_coverage_paths'),
                      'personal_recommendation': None})
    assert [case['comparison_state'] for case in cases] == ['tradeoffs_ready_for_review', 'must_have_hold']
    assert cases[0]['medicine_by_offering'][HUMANA]['quantity_limit'] is False
    assert cases[1]['medicine_by_offering'][HUMANA]['quantity_limit'] is True
    assert all(cases[0]['medicine_by_offering'][off]['ndc'] != cases[1]['medicine_by_offering'][off]['ndc']
               for off in PLANS)
    result = {'eligibility': eligibility(), 'provider_by_offering': provider, 'shared_comparison_terms': terms,
              'comparison_terms_source': '../recommendation-scope-2026-11-04-r4/pilot.json',
              'public_observations_source': 'public-observations.json', 'cases': cases,
              'fixture_checks': fixture_checks()}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
