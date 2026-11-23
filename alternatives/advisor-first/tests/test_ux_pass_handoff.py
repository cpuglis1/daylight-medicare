"""D157 handoff contracts for the backend and data layer (owner: Codex).

Each test states what the conversation and Plans pages need from a layer the
front-end agent does not edit. They are expected to FAIL until that work is
done; they are listed in ``known-failures.json`` with the handoff ID. Spec:
``audit-evidence/ux-pass-pp16-20261112/HANDOFF.md``.

Fictional inputs. The two doctor names are real Collier clinicians from the
November 12, 2026 test conversation, kept so the directory miss can be replayed.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import recommendation_engine as engine


def inputs(**changes):
    value = {'version': engine.INPUTS_VERSION,
             'scope': {'zipcode': '34102', 'county_fips': '12021', 'year': 2026},
             'medigap': {'status': 'ready', 'zipcode': '34102', 'age': 65, 'reported_age': 65,
                         'gender': 'Male', 'tobacco': 'Non-Tobacco'},
             'part_d_status': 'ready', 'doctors': 'list', 'medicines': 'yes', 'travel': [],
             'cost_preference': 'predictable', 'priorities': ['total_cost', 'bills'],
             'current_coverage': ['cobra'], 'medicaid': None}
    value.update(changes)
    return value


class H1DoctorDirectory(unittest.TestCase):
    """CV-16. The directory must find the two PP16 doctors from the words typed."""

    @classmethod
    def setUpClass(cls):
        try:
            from demo_server import REPO
            from daylight_data.serving.part_d_local import local_candidate
            from daylight_data.serving.pilot_doctors import PilotDoctors
            cls.doctors = PilotDoctors(local_candidate(REPO).foundation)
        except Exception as error:   # needs the local foundation database
            raise unittest.SkipTest('Local doctor foundation unavailable: %s' % type(error).__name__)

    def npis(self, **query):
        found = self.doctors.search(year=2026, **query)
        return [npi for row in found['candidates'][:5] for npi in row.get('source_npis', [])]

    def test_ashley_tunkle_in_naples_is_found(self):
        # Medicare's clinician file lists her as LANGFORD TUNKLE, ASHLEY (Millennium
        # Physician Group, 800 Goodlette Rd, Naples); other directories as
        # "Tunkle, Ashley", "Tunkle, Ashley Langford" and "Ashley E Tunkle".
        for query in ({'name': 'Ashley Tunkle', 'location': 'Naples'}, {'name': 'Ashley Tunkle'},
                      {'name': 'Ashley Tunkle', 'practice': 'Millennium Physician Group'}):
            with self.subTest(query=query):
                self.assertIn('1285603670', self.npis(**query))

    def test_dr_henry_biggs_is_found_with_or_without_the_title(self):
        for query in ({'name': 'Dr. Henry Biggs'}, {'name': 'Henry Biggs', 'specialty': 'orthopedic'},
                      {'name': 'Henry Biggs', 'practice': 'Joint Replacement Institute'}):
            with self.subTest(query=query):
                self.assertIn('1558326538', self.npis(**query))

    def test_search_reports_what_it_covered(self):
        found = self.doctors.search(name='Ashley Tunkle', location='Naples', year=2026)
        # So the conversation can say plainly which clinician types and area were searched.
        for key in ('clinician_types_searched', 'radius_or_area_searched'):
            self.assertIn(key, found)


class H2MedicinesAcrossEveryPlan(unittest.TestCase):
    """CV-21, CV-22, CV-23. Check reported medicines against every plan's drug
    list (the ten Part D plans and every Medicare Advantage plan with drug
    coverage) without the person choosing a plan."""

    def test_a_formulary_matrix_exists(self):
        from part_d_visit import PrescriptionVisit
        self.assertTrue(hasattr(PrescriptionVisit, 'formulary_matrix'),
                        'PrescriptionVisit.formulary_matrix(owner, entry) -> {plans: {offering_id: {medicines: '
                        '[{name, rxcui, state: covered|not_listed|needs_detail, tier, prior_authorization, '
                        'quantity_limit, step_therapy, evidence_date}]}}, needs: [{medicine, field}]}')

    def test_prior_authorization_flags_reach_the_conversation(self):
        from part_d_visit import PrescriptionVisit
        row = getattr(PrescriptionVisit, 'FORMULARY_FIELDS', ())
        for field in ('prior_authorization', 'quantity_limit', 'step_therapy'):
            self.assertIn(field, row)


class H3MedigapLettersByFirstEligibility(unittest.TestCase):
    """PG-02. Plans C, F and high-deductible F are for people eligible for
    Medicare before January 1, 2020. The method reads age as a proxy; it should
    read the reported first-eligibility date when there is one, and the price
    endpoint should mark the plans so the participant build can group them."""

    def test_the_engine_reads_the_first_eligibility_date(self):
        value = inputs()
        value['medigap']['first_eligible'] = '2026-11'       # from the reported 65th-birthday month
        value['medigap']['age'] = value['medigap']['reported_age'] = 73   # old enough for the age proxy to pass
        result = {'status': 'matched_source_prices', 'plans': [
            {'id': 'f', 'variant': 'F', 'monthly_cents': 20000, 'company': 'Fictional', 'select_observed': None},
            {'id': 'g', 'variant': 'G', 'monthly_cents': 15000, 'company': 'Fictional', 'select_observed': None}]}
        out = engine.evaluate_medigap(value, result)
        checks = {check['id']: check for check in out['plans']['f']['checks']}
        eligibility = next(check for check in out['plans']['f']['checks'] if check['kind'] == 'eligibility')
        self.assertEqual(eligibility['state'], 'not_met', checks)

    def test_the_price_endpoint_marks_letters_the_person_cannot_buy(self):
        import medigap_pilot
        self.assertTrue(hasattr(medigap_pilot, 'set_aside'),
                        'medigap_pilot.set_aside(plan, first_eligible) -> None or {reason}; prices() adds it to '
                        'each plan so the participant build groups Plans C, F and HDF without the evaluation sorting.')


class H4OnlyCheckedInputsAreListed(unittest.TestCase):
    """PG-04. "What it used" must list only inputs that were actually checked,
    per tab; unchecked ones are marked so the pop-up can say "Not checked"."""

    def test_each_preference_says_whether_it_was_checked(self):
        prefs = engine.checked_preferences(inputs(), {})
        self.assertTrue(prefs)
        for item in prefs:
            self.assertIn('checked', item, item)

    def test_medigap_does_not_report_medicines_or_unmatched_doctors_as_used(self):
        out = engine.evaluate(inputs(), ma_plans=[], medigap_result={'status': 'matched_source_prices', 'plans': []},
                              part_d_result={'status': 'published_plans', 'plans': []})
        used = {item['id']: item for item in out['medigap'].get('preferences', out.get('preferences', []))}
        self.assertFalse(used['medicines']['checked'])                   # Medigap does not cover drugs
        self.assertFalse(used.get('doctors', {}).get('checked', True))     # no doctor was matched


class H5PathAmounts(unittest.TestCase):
    """X-03. One read for the two-path card: listed amounts for both paths, so
    the chat card is filled by software and never by the model."""

    def test_a_path_amounts_read_exists(self):
        import recommendation_http
        self.assertTrue(hasattr(recommendation_http, 'path_amounts'),
                        'path_amounts(profile) -> {original: {part_b_premium, medigap: {letter, low_cents, high_cents, '
                        'count, dated}, part_d: {low_cents, high_cents, count}}, advantage: {premium: {low_cents, '
                        'high_cents}, in_network_limit: {low_cents, high_cents}, count}}; available on the '
                        'participant build with listed amounts and no ranking.')


class H6PlainWordsInBackendMessages(unittest.TestCase):
    """PG-07 and the owner's November 12 direction: no pilot wording to participants."""

    def test_price_endpoints_do_not_say_pilot(self):
        for name in ('medigap_pilot.py', 'part_d_pilot.py'):
            source = (Path(__file__).resolve().parents[1] / name).read_text(encoding='utf-8')
            messages = [line for line in source.splitlines() if "'message'" in line or 'message = ' in line or "pricing" in line.casefold()]
            for line in messages:
                self.assertNotIn('pilot', line.split('#')[0].casefold().replace('unsupported_pilot', ''), line.strip())


if __name__ == '__main__':
    unittest.main()
