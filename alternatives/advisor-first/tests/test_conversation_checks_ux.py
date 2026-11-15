"""D157 (CV-16 to CV-19, CV-21, CV-22): the doctor and medicine checks never loop.

The controller is exercised with a stub directory, so these run without the
local database. The real directory search is the data layer's (see the handoff
spec for what it must return for the PP16 names).
"""
from pathlib import Path
import sys
import types
import unittest

ROOT_SRC = Path(__file__).resolve().parents[3] / 'infrastructure' / 'daylight-data' / 'src'
if str(ROOT_SRC) not in sys.path:
    sys.path.insert(0, str(ROOT_SRC))  # the local data package (needs psycopg)

import test_natural_flow as harness

try:
    import daylight_data.serving.binding  # noqa: F401
except Exception:   # the local data package needs a database driver
    package = types.ModuleType('daylight_data')
    serving = types.ModuleType('daylight_data.serving')
    binding = types.ModuleType('daylight_data.serving.binding')

    class ResearchServingError(Exception):
        pass
    binding.ResearchServingError = ResearchServingError
    sys.modules.setdefault('daylight_data', package)
    sys.modules.setdefault('daylight_data.serving', serving)
    sys.modules['daylight_data.serving.binding'] = binding

from conversation_checks import ConversationChecks


def candidate(identifier, label, city='Naples'):
    return {'candidate_id': identifier, 'kind': 'clinician', 'label': label, 'site_count': 1,
            'source_npis': [identifier], 'office_previews': [{'street': '1 Main St', 'city': city, 'state': 'FL', 'postal': '34102'}]}


class Directory:
    """Returns what the test says the directory holds for each query."""
    def __init__(self, answers):
        self.answers, self.queries = answers, []

    def search(self, **query):
        self.queries.append(query)
        rows = self.answers(query)
        return {'candidates': rows, 'next_offset': None}

    def sites(self, **_):
        return {'sites': [], 'next_offset': None}


class ChecksNeverLoop(unittest.TestCase):
    for name in ('payload', 'take', 'turn', 'message', 'choice', 'task'):
        locals()[name] = getattr(harness.NaturalFlowTests, name)
    update = staticmethod(harness.NaturalFlowTests.update)
    extraction = staticmethod(harness.NaturalFlowTests.extraction)

    def setUp(self):
        harness.NaturalFlowTests.setUp(self)
        self.choice('RC01', choice='self')
        self.choice('T03', zip='34102')
        self.choice('RC03', year='2026')

    def checks(self, answers, drugs=None):
        self.directory = Directory(answers)
        self.subject = ConversationChecks(self.flow, self.directory, drugs, lambda: [])
        return self.subject

    def view(self):
        return self.subject.reconcile(self.owner, self.g, self.r)

    def answer(self, value):
        question = self.subject.visits[self.owner]['question']
        self.subject.answer(self.owner, self.g, self.r, question['token'], value)
        return self.view()

    def test_a_name_with_a_city_is_searched_by_name_and_never_asked_for_the_city(self):
        self.choice('T06', text='Ashley Tunkle in Naples')
        self.checks(lambda query: [])
        view = self.view()
        first = self.directory.queries[0]
        self.assertEqual((first['name'], first['location']), ('Ashley Tunkle', 'Naples'))
        question = view['question']
        self.assertEqual(question['field'], 'doctor_location')
        self.assertEqual(question['question'], 'What is the name of Ashley Tunkle’s practice or office?')   # CV-18
        self.assertNotIn('in Naples in', question['question'])
        self.assertNotIn('Which of these', question['question'])            # CV-16: no empty list
        self.assertFalse(question['choices'])
        self.assertIn('all_retained', [query['region'] for query in self.directory.queries])   # CV-17: widened first

    def test_no_match_after_the_practice_name_is_left_open_with_one_line_and_not_asked_again(self):
        self.choice('T06', text='Ashley Tunkle in Naples')
        self.checks(lambda query: [])
        self.view()
        view = self.answer('Millennium Physician Group')
        self.assertIsNone(view['question'])                                # no loop
        notes = [item for item in view['results'] if item['kind'] == 'note']
        self.assertEqual(len(notes), 1)                                    # CV-19
        self.assertIn('plan networks aren’t checked for this doctor', notes[0]['details'][0])
        self.assertIn('Each plan will show that', notes[0]['details'][0])
        again = self.view()
        self.assertIsNone(again['question'])
        self.assertFalse(again['results'])                                 # said once

    def test_a_practice_name_finds_the_listing_the_name_alone_missed(self):
        self.choice('T06', text='Ashley Tunkle in Naples')
        hit = candidate('1285603670', 'Ashley Langford Tunkle, MD')
        self.checks(lambda query: [hit] if query.get('practice') == 'Millennium Physician Group' else [])
        self.view()
        view = self.answer('Millennium Physician Group')
        self.assertEqual(view['question']['field'], 'doctor')
        self.assertEqual(view['question']['question'], 'Which of these is Ashley Tunkle?')
        self.assertEqual(view['question']['choices'][0]['value'], '1285603670')

    def test_a_list_the_person_passed_over_is_never_shown_again(self):
        self.choice('T06', text='Henry Biggs')
        rows = [candidate('a', 'Richard Biggs, DO'), candidate('b', 'Harold Biggs, MD')]
        self.checks(lambda query: list(rows))
        view = self.view()
        if view['question']['field'] == 'doctor_location':
            view = self.answer('Naples')
        self.assertEqual(view['question']['field'], 'doctor')
        shown = [row['value'] for row in view['question']['choices'] if not row['value'].startswith('__')]
        self.assertEqual(shown, ['a', 'b'])
        view = self.answer('__all__')                                       # "Look outside this area"
        later = [row['value'] for row in (view['question'] or {}).get('choices', []) if not row['value'].startswith('__')]
        self.assertFalse(set(later) & {'a', 'b'})                           # CV-16, CV-17
        self.assertNotEqual((view['question'] or {}).get('question'), 'Which of these is Henry Biggs?')

    def test_leaving_a_doctor_open_says_once_what_that_means(self):
        self.choice('T06', text='Ashley Tunkle in Naples')
        self.checks(lambda query: [])
        self.view()
        view = self.answer('__later__')
        notes = [item for item in view['results'] if item['kind'] == 'note']
        self.assertEqual(len(notes), 1)
        self.assertIn('Left open: plan networks aren’t checked for Ashley Tunkle', notes[0]['details'][0])
        self.assertFalse(self.view()['results'])

    def test_the_person_is_never_asked_to_pick_a_drug_plan(self):
        self.choice('T07', text='Ozempic; metoprolol')

        class Drugs:
            foundation = None
        subject = self.checks(lambda query: [], drugs=None)
        subject.prescriptions = object()                                    # a drug service is present
        view = self.view()
        self.assertIsNone(view['question'])                                 # CV-21
        notes = [item for item in view['results'] if item['kind'] == 'note']
        self.assertEqual(len(notes), 1)                                     # CV-22: one clear "not checked yet"
        self.assertIn('aren’t checked against each plan’s drug list yet', notes[0]['details'][0])
        again = [item for item in self.view()['results'] if item['kind'] == 'note']
        self.assertEqual(len(again), 1)                                     # one line that stays; never two

    # --- found in the live run on :8895, November 12, 2026 ------------------------
    def test_one_doctor_is_one_answer_for_someone_on_the_original_medicare_path(self):
        import datetime
        import ux_flow
        ux_flow.TODAY = datetime.date(2026, 11, 12)
        self.addCleanup(setattr, ux_flow, 'TODAY', None)
        self.choice('T10', choice='total_cost,bills')
        self.choice('T09', choice='predictable')                            # leans Original Medicare with Medigap
        self.choice('T06', text='Ashley Tunkle in Naples')
        hit = candidate('1285603670', 'Ashley Langford Tunkle, MD')

        class Office(Directory):
            def sites(self, **_):
                return {'sites': [{'site_id': 's1', 'address': {'street': '800 Goodlette Rd', 'city': 'Naples',
                                                                 'state': 'FL', 'postal': '34102'}}], 'next_offset': None}

            def selection(self, **chosen):
                self.chosen = chosen
                return chosen

            def evidence(self, selection):
                return {'state': 'dated_listing', 'assignment': [], 'opt_out': [], 'enrollment': [
                    {'published_state': 'published_approved_billing_enrollment_in_extract', 'published_on': '2026-10-01'}]}
        self.directory = Office(lambda query: [hit])
        self.subject = ConversationChecks(self.flow, self.directory, None, lambda: [])
        view = self.view()
        self.assertEqual(view['question']['field'], 'doctor')               # which doctor: the one real question
        view = self.answer('1285603670')
        self.assertIsNone(view['question'])                                 # no office, coverage or date question
        result = next(item for item in view['results'] if item['kind'] == 'doctor')
        self.assertEqual((result['plan'], result['date']), ('Original Medicare', '2026-11-12'))
        self.assertEqual(self.directory.chosen['route'], 'original_medicare')
        text = ' '.join(result['details'])
        self.assertIn('Medicare lists this doctor as enrolled to bill Medicare', text)
        self.assertIn('The office can tell you', text)
        for phrase in ('Opt-out', 'Assignment at this office', 'Appointment availability', 'enrollment record:'):
            self.assertNotIn(phrase, text)
        # "Change coverage" still asks, and is not answered by the default.
        self.subject.edit(self.owner, self.g, self.r, result['key'], 'plan')
        self.assertEqual(self.view()['question']['field'], 'doctor_plan')

    def test_no_second_medicines_note_from_the_checks_when_no_drug_service_is_attached(self):
        # The conversation says it once (ux_flow.finish); the checks stay quiet.
        self.choice('T07', text='Ozempic; metoprolol')
        self.checks(lambda query: [], drugs=None)
        self.assertFalse([item for item in self.view()['results'] if item['kind'] == 'note'])

    def test_code_written_check_wording_uses_plain_words(self):
        import conversation_checks
        source = open(conversation_checks.__file__, encoding='utf-8').read()
        for phrase in ('checking participation', 'the local check', 'the exact office',
                       'Which drug plan would you like to look at'):
            self.assertNotIn(phrase, source)                                # CV-20, CV-21


if __name__ == '__main__':
    unittest.main()
