"""Utility buttons exercise current controller authority with no paid calls.

The existing scripted wire supplies deterministic conversation setup only. Every
utility under test is a free action and must leave the model call count unchanged.
"""
import copy
from pathlib import Path
import sys
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_ongoing_advisor as ongoing_tests
import test_button_backend_gates as button_support
from guest_profiles import ProfileError


class UtilityButtonGatesTests(unittest.TestCase):
    def advisor(self, paused=False):
        h = ongoing_tests.OngoingAdvisorTests()
        h.setUp()
        out = h.open_enrollment()
        if paused:
            out = h.message('Please pause the questions. I want to read for a moment.',
                extraction=h.extraction(),
                compose=h.side_answer(agenda_update={'current_concern': '', 'pause': True}))
        return h, out

    def test_concept_link_preserves_current_practical_question_without_model_call(self):
        h, before = self.advisor()
        calls = len(h.calls)
        out = h.turn({'type': 'read_concept', 'id': 'partb'}, aiConsent=False, contextPolicy=None)
        self.assertEqual(out['assessment']['nextQuestion'], before['assessment']['nextQuestion'])
        self.assertEqual(h.memory_brief()['pending_question'], 'T05')
        self.assertEqual(len(h.calls), calls)
        self.assertEqual([fact['id'] for fact in out['facts']], ['partb'])
        self.assertFalse(out['personalRecommendation'])

    def test_concept_keeps_server_generated_question_wording_instead_of_rebuilding_it(self):
        h, _ = self.advisor()
        question = 'What kind of health insurance covers you right now?'
        before = h.message('Please help me understand which insurance detail matters.',
            extraction=h.extraction(), compose=h.followup(question=question))
        calls = len(h.calls)
        out = h.turn({'type': 'read_concept', 'id': 'parts'}, aiConsent=False, contextPolicy=None)
        self.assertEqual(out['assessment']['nextQuestion']['question'], question)
        self.assertEqual(out['assessment']['nextQuestion'], before['assessment']['nextQuestion'])
        self.assertEqual(len(h.calls), calls)

    def test_concept_link_does_not_resume_a_paused_survey(self):
        h, _ = self.advisor(paused=True)
        calls = len(h.calls)
        out = h.turn({'type': 'read_concept', 'id': 'partb'}, aiConsent=False, contextPolicy=None)
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertTrue(out['assessment']['intakePaused'])
        self.assertTrue(out['assessment']['conversationOpen'])
        self.assertTrue(h.memory_brief()['paused'])
        self.assertEqual(h.memory_brief()['pending_question'], 'T05')
        self.assertEqual(len(h.calls), calls)

    def test_prepare_cancel_returns_to_paused_conversation_without_resuming_intake(self):
        h, _ = self.advisor(paused=True)
        calls = len(h.calls)
        review = h.turn({'type': 'review_preparation'}, aiConsent=False, contextPolicy=None)['review']
        out = h.turn({'type': 'discard_review', 'token': review['token']}, aiConsent=False, contextPolicy=None)
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertTrue(out['assessment']['intakePaused'])
        self.assertTrue(h.memory_brief()['paused'])
        self.assertEqual(len(h.calls), calls)

    def test_sample_return_preserves_pause_and_reported_profile(self):
        h, before = self.advisor(paused=True)
        calls = len(h.calls)
        samples = h.turn({'type': 'next', 'step': 'samples'}, aiConsent=False, contextPolicy=None)
        self.assertTrue(samples['assessment']['journey']['samplesVisible'])
        out = h.turn({'type': 'next', 'step': 'resume'}, aiConsent=False, contextPolicy=None)
        self.assertFalse(out['assessment']['journey']['samplesVisible'])
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertTrue(out['assessment']['intakePaused'])
        self.assertEqual(out['guide']['fields'], before['guide']['fields'])
        self.assertEqual(len(h.calls), calls)

    def test_preparation_requires_named_current_owner_token_and_replay_does_not_repeat_work(self):
        h, _ = self.advisor()
        calls = len(h.calls)
        reviewed = h.turn({'type': 'review_preparation'}, aiConsent=False, contextPolicy=None)
        token = reviewed['review']['token']
        bad = h.payload({'type': 'accept_review', 'token': token}, aiConsent=False, contextPolicy=None)
        with self.assertRaises(ProfileError):
            h.flow.turn(h.owner, bad)
        foreign = h.payload({'type': 'run_preparation', 'token': token}, aiConsent=False, contextPolicy=None)
        with self.assertRaises(ProfileError):
            h.flow.turn(uuid.uuid4().hex, foreign)
        payload = h.payload({'type': 'run_preparation', 'token': token}, aiConsent=False, contextPolicy=None)
        out = h.take(payload)
        replay = h.flow.turn(h.owner, payload)
        self.assertEqual(out['preparation']['id'], replay['preparation']['id'])
        self.assertEqual(out['preparation']['status'], 'prepared')
        self.assertIn('No outside party was contacted', out['preparation']['text'])
        self.assertEqual(len(h.calls), calls)

    def test_new_guest_cannot_reuse_old_continuation_but_free_refresh_rebinds_reports(self):
        h, before = self.advisor()
        calls = len(h.calls)
        old = h.payload({'type': 'read_concept', 'id': 'basics'}, aiConsent=False, contextPolicy=None)
        new_owner = uuid.uuid4().hex
        with self.assertRaises(ProfileError) as caught:
            h.flow.turn(new_owner, old)
        self.assertEqual(caught.exception.code, 409)
        refresh = {'guide': copy.deepcopy(h.g), 'record': copy.deepcopy(h.r),
                   'action': {'type': 'refresh'}, 'requestId': str(uuid.uuid4())}
        out = h.flow.turn(new_owner, refresh)
        self.assertEqual(out['guide']['fields'], before['guide']['fields'])
        self.assertNotEqual(out['continuation'], before['continuation'])
        self.assertEqual(len(h.calls), calls)
        self.assertFalse(out['personalRecommendation'])

    def test_explanation_setting_records_explicit_preference_without_survey_advance_or_model(self):
        for paused in (False, True):
            for value in ('new', 'some', 'comfortable'):
                with self.subTest(paused=paused, value=value):
                    h, before = self.advisor(paused=paused)
                    calls = len(h.calls)
                    out = h.turn({'type': 'explanation_preference', 'value': value},
                                 aiConsent=True, contextPolicy='natural-context-v3')
                    self.assertEqual(out['guide']['fields']['knowledge.general']['value'], value)
                    self.assertEqual(out['guide']['fields']['knowledge.general']['status'], 'reported')
                    self.assertEqual(out['guide']['fields']['knowledge.general']['source'], 'user_choice')
                    self.assertEqual(out['assessment']['nextQuestion'], before['assessment']['nextQuestion'])
                    self.assertEqual(out['assessment'].get('intakePaused'), before['assessment'].get('intakePaused'))
                    self.assertEqual(h.memory_brief()['pending_question'], 'T05')
                    self.assertEqual(h.memory_brief()['paused'], paused)
                    self.assertEqual(len(h.calls), calls)

    def test_explanation_setting_rejects_other_fields_values_and_fake_current_question(self):
        h, _ = self.advisor()
        for action in ({'type': 'explanation_preference', 'value': []},
                       {'type': 'explanation_preference', 'value': 'expert'},
                       {'type': 'explanation_preference', 'value': 'new', 'id': 'T05'},
                       {'type': 'explanation_preference', 'value': 'new', 'fields': {'choice': 'none'}}):
            with self.subTest(action=action), self.assertRaises(ProfileError):
                h.turn(action, aiConsent=False, contextPolicy=None)
        payload = h.payload({'type': 'read_concept', 'id': 'basics'}, aiConsent=False, contextPolicy=None)
        payload['record']['natural']['dialogue']['lastTarget'] = {'id': 'T07', 'entity': 'profile', 'fields': []}
        with self.assertRaises(ProfileError) as caught:
            h.flow.turn(h.owner, payload)
        self.assertEqual(caught.exception.code, 409)

    def test_lesson_navigation_and_settings_keep_both_pending_aggregate_targets(self):
        support = button_support.ButtonBackendGateTests()
        for action in ({'type': 'read_concept', 'id': 'drugbasics'},
                       {'type': 'next', 'step': 'samples'},
                       {'type': 'next', 'step': 'resume'},
                       {'type': 'explanation_preference', 'value': 'comfortable'}):
            with self.subTest(action=action):
                case, _, _ = support.seed_pending_pair('RC22')
                before = copy.deepcopy(case.flow.pending_for(case.owner))
                case.turn(action, aiConsent=False, contextPolicy=None)
                pending = case.flow.pending_for(case.owner)
                self.assertEqual(pending['update'], before['update'])
                self.assertEqual(pending['remaining'], before['remaining'])
                self.assertEqual(pending['revision'], [case.g['stateVersion'], case.r['stateVersion']])
                eligible = case.flow.eligible(case.owner, case.g, case.r)
                self.assertEqual(eligible[0]['question']['entity'], 'medicine-1')
                self.assertEqual(case.flow.pending_for(case.owner)['remaining'][0]['entity'], 'medicine-2')
                self.assertEqual(case.calls, [])

    def test_explanation_setting_resolves_actual_pending_familiarity_and_does_not_reask_it(self):
        h = ongoing_tests.OngoingAdvisorTests()
        h.setUp()
        text = 'I turn 65 in November and want help enrolling.'
        out = h.message(text,
            extraction=h.extraction([h.update('RC01', {'choice': 'self'}, text)],
                situations=[h.birthday(text)], goal='want help enrolling'),
            compose=h.followup(target='T02', question=h.flow.question('T02')['question']))
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T02')
        h.flow.queue_pending(h.owner, [{'id': 'T02', 'entity': 'profile', 'fields': {'choice': 'new'}}], h.g, h.r)
        calls = len(h.calls)
        out = h.turn({'type': 'explanation_preference', 'value': 'comfortable'}, aiConsent=False, contextPolicy=None)
        self.assertIsNone(h.flow.pending_for(h.owner))
        self.assertNotEqual((out['assessment']['nextQuestion'] or {}).get('id'), 'T02')
        self.assertEqual(out['guide']['fields']['knowledge.general']['value'], 'comfortable')
        self.assertEqual(out['record']['natural']['dialogue']['lastTarget']['id'], out['assessment']['nextQuestion']['id'])
        self.assertEqual(len(h.calls), calls)


if __name__ == '__main__':
    unittest.main()
