"""D198: offline delivery contracts; no model or network requests."""
import copy
from datetime import date
import unittest
from unittest.mock import patch

import test_conversation_planner as harness
import conversation_planner as planner
import ux_pass


class TimingCardDeliveryTests(unittest.TestCase):
    def setUp(self):
        fixture = harness.ConversationPlannerTests()
        fixture.setUp()
        self.fixture = fixture
        self.addCleanup(fixture.doCleanups)
        self.flow, self.owner, self.g, self.r = fixture.flow, fixture.owner, fixture.g, fixture.r
        self.card = {'kind': 'enrollment_timing', 'title': 'Your Medicare timing',
            'rows': [{'label': 'Sign-up window', 'value': 'fictional date range'}],
            'dates': {'iep_start': '2027-01-01'}, 'text': 'Your timing.', 'cobra': '',
            'statement_ids': ['initial_enrollment_window']}
        self.s = planner.state(self.flow, self.owner)
        self.s['focus'] = 'enrollment'
        self.s['guidance']['mode'] = 'discuss'

    def prepare(self, kind='explain', concepts=('enrollment_timing',), requested=True):
        context = {'education_context': {'requested_revisit': requested,
                   'request_kind': kind, 'revisit_concepts': list(concepts)}, 'plans_pages': {}}
        with patch('ux_flow._timing_card', return_value=copy.deepcopy(self.card)), \
             patch.object(planner, 'educational_card', return_value=None), \
             patch('enrollment_flow.cards', return_value=[]), \
             patch('enrollment_flow.context', return_value={}):
            planner.prepare(self.flow, self.owner, self.g, self.r, [], context)
        return context

    def deliver(self):
        out = {'guide': self.g, 'record': self.r, 'assessment': {},
               'generated': {'status': 'complete'}, 'reply': 'Answer to the current question.'}
        with patch.object(planner, 'attach'):
            planner.finish(self.flow, self.owner, out, 'A fictional question.', [])
        return out

    def test_validated_revisit_kind_reaches_the_composer(self):
        text = 'Could you show my enrollment timing again?'
        self.fixture.message(text, extraction=self.fixture.extraction(
            education_request={'kind': 'revisit', 'concept_ids': ['enrollment_timing'], 'quote': text},
            discussion=self.fixture.proposal(text, focus='enrollment', question_quote=text)))
        education = self.fixture.composed_context()['education_context']
        self.assertEqual(education['request_kind'], 'revisit')
        self.assertTrue(education['requested_revisit'])

    def test_first_delivery_unrelated_followups_and_transcript(self):
        self.prepare(requested=False)
        first = self.deliver()
        original = copy.deepcopy(first)
        for concepts in [('part_a',), ('enrollment_timing',)]:
            context = self.prepare(concepts=concepts)
            self.assertEqual(context['discussion_plan']['software_cards'], [])
            out = self.deliver()
            self.assertNotIn('cards', out)
            self.assertEqual(out['reply'], 'Answer to the current question.')
        self.assertEqual(first, original)

    def test_explicit_timing_redisplay_only(self):
        self.prepare(); self.deliver()
        self.assertEqual(self.prepare(kind='revisit', concepts=('part_a',))['discussion_plan']['software_cards'], [])
        self.assertEqual(self.prepare(kind='revisit')['discussion_plan']['software_cards'], ['enrollment_timing'])

    def test_changed_dates_or_assumptions_are_shown(self):
        self.prepare(); self.deliver()
        self.card['dates']['iep_start'] = '2026-12-01'
        self.assertEqual(self.prepare()['discussion_plan']['software_cards'], ['enrollment_timing'])
        self.deliver()
        self.card['footnote'] = 'Fictional corrected assumption.'
        self.assertEqual(self.prepare()['discussion_plan']['software_cards'], ['enrollment_timing'])

    def test_recovery_and_new_visit_are_isolated(self):
        self.prepare(); self.deliver()
        # A same-process reload retains this owner/chain's existing receipts.
        self.assertIs(planner.state(self.flow, self.owner), self.s)
        self.assertEqual(self.prepare()['discussion_plan']['software_cards'], [])
        self.owner = 'another-fictional-owner'
        self.s = planner.state(self.flow, self.owner)
        self.s['focus'] = 'enrollment'; self.s['guidance']['mode'] = 'discuss'
        self.assertEqual(self.prepare()['discussion_plan']['software_cards'], ['enrollment_timing'])

    def test_shortened_cobra_caveat_does_not_redeliver_same_dates(self):
        timing = ux_pass.enrollment_timing({'year': 2027, 'month': 1}, today=date(2026, 11, 19), parts='neither')
        first = ux_pass.timing_card(timing, ['cobra'])
        shortened = ux_pass.timing_card(timing, ['cobra'], ['cobra_trap'])
        self.assertNotEqual(first['text'], shortened['text'])
        self.assertEqual(planner.card_fingerprint(first), planner.card_fingerprint(shortened))
        without_cobra = ux_pass.timing_card(timing, [])
        self.assertNotEqual(planner.card_fingerprint(first), planner.card_fingerprint(without_cobra))


if __name__ == '__main__':
    unittest.main()
