"""Names stay source-bound without joining independently rendered text blocks."""
import copy
import unittest

import test_natural_agent as support
from chat import ModelUnavailable


class NameGroundingBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.case = support.NaturalAgentTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.case.context['reports'] = [{
            'id': 'guide.needs.providers', 'status': 'reported',
            'value': ('Dr. Rivera at Example Clinic in Naples, and '
                      'Dr. Lee at Example Hospital in Tampa.')}]
        self.case.moves = [{'id': 'T03', 'question': {
            'id': 'T03', 'question': 'What ZIP code do you live in?'}}]

    def compose(self, reply, question='What ZIP code do you live in?', **extra):
        self.case.answer = self.case.composition(
            question_target='T03', reply=reply, question=question,
            report_refs=['guide.needs.providers'], **extra)
        return self.case.compose()

    def test_reported_doctor_pairs_do_not_require_terminal_punctuation(self):
        reply = ('I have these on the review list:\n'
                 '- Dr. Rivera at Example Clinic in Naples\n'
                 '- Dr. Lee at Example Hospital in Tampa')
        before = copy.deepcopy(self.case.context)
        for ending in ('', '.', '\n'):
            with self.subTest(ending=ending):
                out = self.compose(reply + ending)
                self.assertEqual(out['reply'], (reply + ending).strip())
                self.assertEqual(out['question'], 'What ZIP code do you live in?')
                self.assertNotIn('validation_recovery', out)
        self.assertEqual(self.case.context, before)
        self.assertEqual(len(self.case.calls), 3)  # No repair/generation retries.

    def test_boundary_rule_applies_to_any_grounded_name_and_question(self):
        for name in ('Dr. Ashley Tunkle', 'Example Clinic', 'Harbor Pharmacy',
                     'Example Med', 'BlueCross', 'Original Medicare'):
            for question in ('What ZIP code do you live in?',
                             'Which ZIP code should we use?'):
                with self.subTest(name=name, question=question):
                    self.case.context['reports'][0]['value'] = name
                    out = self.compose('On the review list: ' + name, question)
                    self.assertEqual(out['reply'], 'On the review list: ' + name)
                    self.assertEqual(out['question'], question)
                    self.assertNotIn('validation_recovery', out)

    def test_paragraph_boundary_does_not_extend_the_last_reported_name(self):
        for separator in ('\n\n', '\n \n', '\r\n\r\n'):
            with self.subTest(separator=separator):
                reply = ('On the review list: Dr. Lee at Example Hospital in Tampa'
                         + separator + 'These are details for the review.')
                self.assertEqual(self.compose(reply)['reply'], reply)

    def test_a_name_the_person_typed_earlier_in_the_visit_is_theirs(self):
        # November 13, 2026: replies naming "Bay Lantern Cardiology" or "Wellcare" a turn after the person
        # said them were rejected and fell back. Only the person's own earlier words count, never a reply.
        reply = 'Bay Lantern Cardiology is the practice to look for.'
        with self.assertRaises(ModelUnavailable):
            self.compose(reply)
        self.case.context['recent_exchanges'] = [{'user': 'Priya Talden at Bay Lantern Cardiology.', 'assistant': '', 'question': ''}]
        self.assertEqual(self.compose(reply)['reply'], reply)
        self.case.context['recent_exchanges'] = [{'user': 'ok', 'assistant': 'Bay Lantern Cardiology is listed.', 'question': ''}]
        with self.assertRaises(ModelUnavailable):
            self.compose(reply)

    def test_invented_names_in_later_paragraphs_still_fail(self):
        with self.assertRaisesRegex(ModelUnavailable, 'named entity'):
            self.compose('On the review list: Example Hospital\n\n'
                         'Dr. Avery Invented is also on the list.')

    def test_invented_or_extended_names_still_fail_at_end_of_reply(self):
        for name in ('Dr. Avery Invented', 'Dr. Rivera Smith',
                     'Example Hospital North', 'Fabricated Clinic', 'BlueCross'):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ModelUnavailable, 'named entity'):
                    self.compose('On the review list: ' + name)

    def test_question_names_are_checked_independently(self):
        self.case.moves = []
        self.case.answer = self.case.composition(
            question_target=None, reply='We can discuss the next step',
            question='Would an explanation of Fabricated Insurance help?')
        with self.assertRaisesRegex(ModelUnavailable, 'named entity'):
            self.case.compose()

    def test_boundary_does_not_break_a_multiword_identity_inside_a_block(self):
        self.case.context['reports'][0]['value'] = 'Ashley Tunkle'
        for reply in ('Dr. Ashley Tunkle Smith', 'Dr. Ashley Tunkle\nSmith'):
            with self.subTest(reply=reply):
                with self.assertRaisesRegex(ModelUnavailable, 'named entity'):
                    self.compose(reply)

    def test_reported_names_do_not_establish_verified_participation(self):
        with self.assertRaisesRegex(ModelUnavailable, 'unsupported personal finding'):
            self.compose('I verified Dr. Rivera at Example Clinic in Naples')


if __name__ == '__main__':
    unittest.main()
