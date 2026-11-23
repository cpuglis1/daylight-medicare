"""Questions are worded for the person being helped when the visit is for someone else.

Covers fix 3 of the rebalance plan: the approved question wording addresses the
reader as "you", so a helper signing up a parent was asked about their own
coverage. These tests check that (1) code's fallback wording names the person
being helped once subject.role is 'someone', (2) the same questions keep the
approved "you" wording for a self visit, (3) the composer's own helper wording
("When does your mom need coverage to begin?") is no longer swapped back to the
stock text by the keyword check, and (4) the composer is told to word questions
for the person being helped. All data is fictional.
"""
import unittest

import test_natural_flow as flow_harness
from natural_agent import COMPOSE_INSTRUCTIONS, NaturalAgent


class HelperQuestionWordingTests(unittest.TestCase):
    def case(self, role):
        """Return a flow harness with the visit's subject set to `role`."""
        case = flow_harness.NaturalFlowTests()
        case.setUp()
        case.choice('T01', choice='compare')
        case.choice('RC01', choice=role)
        return case

    def candidate_text(self, case, identifier):
        """Return the wording of one eligible question offered to the composer."""
        moves = case.flow.eligible(case.owner, case.g, case.r)
        return next(m['question']['question'] for m in moves if m['id'] == identifier)

    def test_helper_visit_offers_questions_about_the_person_being_helped(self):
        """With subject.role 'someone', T04 and T05 name the person being helped, not 'you'."""
        case = self.case('someone')
        for identifier in ('T04', 'T05'):
            with self.subTest(identifier=identifier):
                text = self.candidate_text(case, identifier)
                self.assertIn('the person you are helping', text)
                self.assertNotRegex(text, r'\bdo you\b')

    def test_self_visit_keeps_the_approved_wording(self):
        """A self visit is still asked the approved 'you' wording."""
        case = self.case('self')
        self.assertEqual(self.candidate_text(case, 'T05'), case.flow.question('T05')['question'])
        self.assertIn('you have', self.candidate_text(case, 'T05'))

    def test_helper_wording_keeps_the_question_meaning(self):
        """Only the wording changes: id, choices and fields match the approved question."""
        case = self.case('someone')
        approved = case.flow.question('T05')
        worded = case.flow.contextual_question(case.g, case.r, approved)
        self.assertNotEqual(worded['question'], approved['question'])
        for key in ('id', 'choices', 'fields', 'multi', 'signature'):
            self.assertEqual(worded.get(key), approved.get(key))
        # The caller's question is not mutated.
        self.assertEqual(approved['question'], case.flow.question('T05')['question'])

    def test_composer_helper_wording_for_start_is_not_swapped_back(self):
        """'When does your mom need coverage to begin?' passes the T04 meaning check."""
        move = {'id': 'T04', 'question': {'id': 'T04', 'question': 'When do you need Medicare coverage to start?',
                                          'fields': [], 'choices': []}}
        self.assertTrue(NaturalAgent._valid_question('When does your mom need Medicare coverage to begin?', move))
        # The check still rejects a question that drops the start meaning.
        self.assertFalse(NaturalAgent._valid_question('Does your mom need Medicare?', move))

    def test_composer_is_told_to_word_questions_for_the_person_being_helped(self):
        """The compose instructions tie helper wording to the subject.role report."""
        self.assertIn('guide.subject.role report is someone', COMPOSE_INSTRUCTIONS)
        self.assertIn('your mom', COMPOSE_INSTRUCTIONS)


if __name__ == '__main__':
    unittest.main()
