"""Offline state/authority checks. Scripted prose is not a quality evaluation."""
import copy
import calendar
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import test_natural_flow as support
from advisor_memory import CONTEXT_POLICY, VisitMemory
from natural_agent import NaturalAgent
from natural_state import prune_for_storage
from contextual_capture import classify_situation
from turn_contract import question_binding, continuation


class TurnContractTests(unittest.TestCase):
    def setUp(self):
        self.network = patch('socket.create_connection', side_effect=AssertionError('Network forbidden'))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.case = support.NaturalFlowTests()
        self.case.setUp()
        self.case.choice('RC01', choice='self')

    @staticmethod
    def proposal(text, **extra):
        return {'kind': 'age65', 'subject': 'beneficiary', 'scope': 'intended',
                'quote': text, 'uncertain': False, 'correction': False,
                'month': 3, 'year': 2027, 'status': '', 'when': '',
                'first_day': None, 'first_day_quote': '', **extra}

    def request_birthday(self):
        self.case.choice('T05', choice='cobra')
        self.case.message('Help me understand the timing.', compose={
            'question_target': 'S_AGE65',
            'question': 'What month and year will you turn 65, and does your birthday fall on the first of that month?'})

    def report(self, text, proposal, **compose):
        return self.case.message(text, extraction=self.case.extraction(situation_proposals=[proposal]),
            compose={'question_target': None, 'question': '', 'reply': 'We can use that for the review.', **compose})

    def outcomes(self):
        return self.case.composed_context()['working_assessment']['current_turn']['capture_outcomes']

    def test_contextual_compound_answer_is_committed_before_composition(self):
        self.request_birthday()
        text = 'March 2027, and no'
        before = len(self.case.calls)
        self.report(text, self.proposal(text, first_day=False, first_day_quote='no'))
        self.assertEqual(self.case.flow.value(self.case.g, 'situation.age65'),
                         {'month': 3, 'year': 2027, 'first_day': False})
        self.assertEqual(self.outcomes()[0]['status'], 'accepted')
        context = self.case.composed_context()
        self.assertIn({'month': 3, 'year': 2027, 'first_day': False},
                      [item['value'] for item in context['reports']])
        self.assertEqual(context['working_assessment']['current_turn']['answer_context']['id'], 'S_AGE65')
        self.assertEqual(len(self.case.calls) - before, 2)
        self.assertNotIn('I turn 65', json.dumps(context['working_assessment']))

    def test_binding_is_displayed_question_not_scheduler_choice(self):
        text = 'Ask about my coverage.'
        self.case.message(text, compose={'question_target': 'T05',
            'question': 'Which health insurance do you currently have?'})
        shown = self.case.flow.current_presentation(self.case.owner, self.case.continuation)['nextQuestion']
        self.case.message('COBRA', [self.case.update('T05', {'choice': 'cobra'}, 'COBRA')],
                          compose={'question_target': None, 'question': ''})
        extracted = self.case.extracted_context()
        self.assertEqual(extracted['activeQuestion']['question'], shown['question'])
        self.assertEqual(extracted['answer_context']['question'], shown['question'])
        self.assertEqual(self.case.flow.value(self.case.g, 'coverage.current'), ['cobra'])
        self.assertEqual(self.outcomes()[0]['status'], 'accepted')

    def test_unrelated_question_cannot_supply_birthday_meaning(self):
        text = 'March 2027, and no'
        proposal = self.proposal(text, first_day=False, first_day_quote='no')
        for target in ('T04', 'T05', 'RC04'):
            with self.subTest(target=target):
                binding = question_binding(self.case.flow.question(target), 'self')
                self.assertFalse(NaturalAgent._valid_situation_proposal(proposal, text, 'self', binding))
        self.report(text, proposal)
        self.assertIsNone(self.case.flow.value(self.case.g, 'situation.age65'))
        self.assertEqual(self.outcomes()[0]['status'], 'unsupported')

    def test_context_never_supplies_missing_values_or_first_day(self):
        binding = question_binding(self.case.flow.question('S_AGE65'), 'self', ['month', 'year', 'first_day'])
        for text, proposal in [
                ('March', self.proposal('March', year=2027)),
                ('April 2027', self.proposal('April 2027')),
                ('March 2027', self.proposal('March 2027', first_day=False)),
                ('March 2027', self.proposal('March 2027', first_day=False, first_day_quote='no'))]:
            with self.subTest(text=text, proposal=proposal):
                self.assertFalse(NaturalAgent._valid_situation_proposal(proposal, text, 'self', binding))
        self.assertTrue(NaturalAgent._valid_situation_proposal(self.proposal('March', year=None), 'March', 'self', binding))

    def test_uncertainty_conflict_correction_and_wrong_person_keep_guards(self):
        self.request_birthday()
        text = 'Maybe March 2027, and no'
        self.report(text, self.proposal(text, uncertain=True, first_day=False, first_day_quote='no'))
        self.assertIsNone(self.case.flow.value(self.case.g, 'situation.age65'))
        self.assertEqual(self.outcomes()[0]['status'], 'needs_clarification')
        text = 'March 2027, and no'
        self.report(text, self.proposal(text, first_day=False, first_day_quote='no'))
        self.assertEqual(self.case.flow.value(self.case.g, 'situation.age65')['month'], 3)
        text = 'I turn 65 in April 2027.'
        self.report(text, self.proposal(text, month=4))
        self.assertEqual(self.outcomes()[0]['status'], 'conflicting')
        self.assertFalse(any(r['id'] == 'guide.situation.age65' for r in self.case.composed_context()['reports']))
        text = 'Actually, I turn 65 in April 2027.'
        self.report(text, self.proposal(text, month=4, correction=True))
        self.assertEqual(self.case.flow.value(self.case.g, 'situation.age65'), {'month': 4, 'year': 2027})
        binding = question_binding(self.case.flow.question('S_AGE65'), 'someone', ['month', 'year', 'first_day'])
        text = 'I turn 65 in March 2027.'
        self.assertFalse(NaturalAgent._valid_situation_proposal(self.proposal(text), text, 'someone', binding))
        text = 'If I turn 65 in March 2027?'
        self.assertFalse(NaturalAgent._valid_situation_proposal(self.proposal(text), text, 'self', binding))

    def test_contextual_classification_uses_real_quote_for_uncertainty(self):
        binding = question_binding(self.case.flow.question('S_AGE65'), 'self', ['month', 'year'])
        value = {'month': 3, 'year': 2027}
        self.assertEqual(classify_situation('Maybe March 2027', 'age65', value, answer_context=binding)['reason'], 'tentative')
        self.assertEqual(classify_situation('March 2027', 'age65', value)['decision'], 'reject')
        self.assertEqual(classify_situation('March 2027', 'age65', value, answer_context=binding)['decision'], 'accept')
        for number in range(1, 13):
            with self.subTest(month=number):
                quote = calendar.month_name[number] + ' 2027, and no'
                self.assertEqual(classify_situation(quote, 'age65', {'month': number, 'year': 2027},
                                 answer_context=binding)['decision'], 'accept')

    def test_reports_outlive_history_without_expanding_saved_transcript(self):
        self.request_birthday()
        text = 'March 2027, and no'
        self.report(text, self.proposal(text, first_day=False, first_day_quote='no'))
        for _ in range(7):
            self.case.message('Tell me more.', compose={'question_target': None, 'question': '', 'reply': 'We can continue.'})
        context = self.case.composed_context()
        # D155 Q11: the whole visit chat is sent, so the quote is still in the
        # exchanges; the report must also be carried as a report, and the saved
        # transcript must not grow a working assessment (checked below).
        self.assertIn(text, json.dumps(context['recent_exchanges']))
        self.assertEqual(self.case.flow.value(self.case.g, 'situation.age65')['first_day'], False)
        self.assertIn('guide.situation.age65', [item['id'] for item in context['reports'] + context['known']])
        self.assertNotIn('S_AGE65', [c['id'] for c in self.case.flow.eligible(self.case.owner, self.case.g, self.case.r)])
        _, stored = prune_for_storage(copy.deepcopy(self.case.g), copy.deepcopy(self.case.r))
        self.assertNotIn('working_assessment', json.dumps(stored))
        self.assertNotIn(text, json.dumps(stored))

    def test_reaffirmed_report_has_already_known_outcome(self):
        self.case.choice('T08', choice='local')
        self.case.message('I only want local care.', [self.case.update('T08', {'choice': 'local'}, 'I only want local care.')],
                          compose={'question_target': None, 'question': ''})
        self.assertEqual(self.outcomes()[0]['status'], 'already_known')

    def test_model_can_continue_learning_or_offer_a_next_step_without_a_script(self):
        for question, progress, move in [('What part feels unclear?', 'open', 'clarify'),
                                         ('Would you like to explore anything else?', 'useful_stopping_point', 'next_step')]:
            with self.subTest(question=question):
                out = self.case.message('Help me understand my options.', compose={
                    'reply': 'We can take this at your pace.', 'question_target': None, 'question': question,
                    'conversation_assessment': {'goal_progress': progress, 'next_move': move}})
                record = out['metrics']['continuation']
                self.assertEqual(record['assessment']['goal_progress'], progress)
                # November 8, 2026: without a learning signal from extraction, a
                # null-target question is replaced by the open approved meaning.
                self.assertTrue(record['validation_changed_continuation'])
                self.assertNotIn(question, out['reply'])
                self.assertIsNotNone(out['assessment']['nextQuestion'])

    def test_removed_personal_question_is_not_intentional_completion(self):
        out = self.case.message('Please continue.', compose={
            'reply': 'We can continue.', 'question_target': None, 'question': 'What ZIP code do you live in?',
            'conversation_assessment': {'goal_progress': 'open', 'next_move': 'ask'}})
        # An exact approved wording may recover its target. Use a noncanonical
        # personal question to exercise removal rather than exact-ID recovery.
        out = self.case.message('Please continue.', compose={
            'reply': 'We can continue.', 'question_target': None, 'question': 'Could you tell me your ZIP code?',
            'conversation_assessment': {'goal_progress': 'open', 'next_move': 'ask'}})
        # November 8, 2026: the non-canonical personal question is replaced by
        # the approved meaning's wording rather than withheld.
        self.assertEqual(out['metrics']['continuation']['delivered'], 'question')
        self.assertTrue(out['metrics']['continuation']['validation_changed_continuation'])
        self.case.message('Where were we?', compose={'question_target': None, 'question': ''})
        previous = self.case.composed_context()['working_assessment']['goal']['previous_continuation']
        self.assertTrue(previous['validation_changed_continuation'])
        self.assertEqual(previous['assessment']['goal_progress'], 'open')  # kept: the question was delivered (Nov 8, 2026)

    def test_advisory_assessment_never_grants_plan_or_learning_authority(self):
        out = self.case.message('Thanks.', compose={'question_target': None, 'question': '',
            'conversation_assessment': {'goal_progress': 'useful_stopping_point', 'next_move': 'finish'},
            'task_work': {'check_ids': ['provider_participation'], 'blocking_concepts': [], 'next_step': 'review'}})
        self.assertEqual(out['education']['covered'], [])
        self.assertFalse(out['task_work']['task_resolved'])
        self.assertEqual(out['task_work']['completed_external_actions'], [])
        self.assertEqual(out['task_work']['checks'][0]['verification_state'], 'not_verified')
        self.assertEqual(self.case.composed_context()['working_assessment']['understanding']['assessment_is_tentative'], True)

    def test_malformed_optional_assessment_keeps_valid_answer_without_completion_credit(self):
        out = self.case.message('Thanks.', compose={'question_target': None, 'question': '',
            'reply': 'We can continue when you want.',
            'conversation_assessment': {'goal_progress': 'verified', 'next_move': 'enroll'}})
        self.assertTrue(out['reply'].startswith('We can continue when you want.'))
        self.assertIsNotNone(out['assessment']['nextQuestion'])  # Nov 8, 2026: approved question, not appended prose
        self.assertIsNone(out['metrics']['continuation']['assessment'])

    def test_pause_and_failed_composition_are_not_reported_as_successful_continuation(self):
        out = self.case.message('No more questions.', compose={
            'question_target': 'T05', 'question': 'What health insurance do you have now?'})
        self.assertEqual(out['metrics']['continuation']['assessment']['goal_progress'], 'paused')
        self.assertEqual(out['metrics']['continuation']['delivered'], 'answer_only')
        self.assertFalse(out['metrics']['continuation']['validation_changed_continuation'])
        out = self.case.message('Continue please.', compose=TimeoutError('offline failure'))
        self.assertEqual(out['metrics']['continuation']['delivered'], 'withheld')
        self.assertIsNone(out['metrics']['continuation']['assessment'])

    def test_reaffirmed_situation_remains_grounded_outside_previous_topic(self):
        self.request_birthday()
        text = 'March 2027, and no'
        self.report(text, self.proposal(text, first_day=False, first_day_quote='no'))
        text = 'I turn 65 in March 2027.'
        self.report(text, self.proposal(text))
        self.assertEqual(self.outcomes()[0]['status'], 'already_known')
        report = next(item for item in self.case.composed_context()['reports'] if item['id'] == 'guide.situation.age65')
        self.assertEqual(report['value'], {'month': 3, 'year': 2027, 'first_day': False})

    def test_continuation_memory_is_owner_visit_permission_and_ttl_scoped(self):
        now = [0]
        memory = VisitMemory(clock=lambda: now[0])
        record = continuation({'question': '', 'question_target': None}, {'question': '', 'question_target': None},
                              {'goal_progress': 'open', 'next_move': 'explain'})
        memory.remember('one', 'visit', CONTEXT_POLICY, 'x', 'y', '', continuation=record)
        self.assertEqual(memory.brief('one', 'visit', CONTEXT_POLICY)['continuation'], record)
        self.assertEqual(memory.brief('two', 'visit', CONTEXT_POLICY), {})
        self.assertEqual(memory.brief('one', 'other', CONTEXT_POLICY), {})
        now[0] = 3601
        self.assertEqual(memory.brief('one', 'visit', CONTEXT_POLICY), {})
        memory.remember('one', 'visit', CONTEXT_POLICY, 'x', 'y', '', continuation=record)
        self.assertEqual(memory.brief('one', 'visit', 'natural-context-v1'), {})


if __name__ == '__main__':
    unittest.main()
