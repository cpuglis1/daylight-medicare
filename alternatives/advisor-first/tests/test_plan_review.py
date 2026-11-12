"""Offline checkpoint/authority tests using fictional profiles and scripted AI."""
import copy
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_natural_flow as support
from chat import ModelUnavailable
from guest_profiles import ProfileError
from plan_review import readiness, input_digest, TTL


class PlanReviewTests(unittest.TestCase):
    def setUp(self):
        self.guard = patch('socket.create_connection', side_effect=AssertionError('No network'))
        self.guard.start()
        self.addCleanup(self.guard.stop)
        self.case = support.NaturalFlowTests()
        self.case.setUp()

    def fill(self, omit=(), year='2026', lists=False):
        # Deliberately not questionnaire order. No learning or medical-basis quiz.
        for identifier, fields in [
            ('RC01', {'choice': 'someone'}), ('T01', {'choice': 'compare'}),
            ('T10', {'choice': 'doctors,drugs'}), ('RC03', {'year': year}),
            ('T03', {'zip': '34102'}), ('T05', {'choice': 'original,medigap,drug'}),
            ('T06', {'text': 'Dr. Synthetic at Fictional Clinic in Naples'} if lists else {'choice': 'none'}),
            ('T07', {'text': 'Example Med 5 mg; Example Med 10 mg'} if lists else {'choice': 'no'}),
            ('T09', {'choice': 'no_preference'}), ('T08', {'choice': 'local'}),
            ('RC04', {'choice': 'both'})]:
            if identifier not in omit:
                self.case.choice(identifier, **fields)

    def status(self):
        return readiness(self.case.g, self.case.r)

    def local(self, kind, **fields):
        before = len(self.case.calls)
        result = self.case.turn({'type': kind, **fields}, aiConsent=False, contextPolicy=None)
        self.assertEqual(len(self.case.calls), before)
        return result

    def review(self):
        return self.local('review_plans')['review']

    def confirm(self):
        return self.local('confirm_plan_review', token=self.review()['token'])['plansHandoff']

    def test_minimum_is_meanings_not_count_or_entire_curriculum(self):
        self.fill()
        self.assertTrue(self.status()['canReview'])
        self.assertNotIn('knowledge.general', self.case.g['fields'])
        self.assertNotIn('RC06', self.case.r['facts'])
        self.assertEqual(self.case.flow.eligible(self.case.owner, self.case.g, self.case.r), [])
        handoff = self.confirm()
        self.assertEqual(len(handoff['profile']['questions']), 41)
        self.assertEqual(handoff['scope']['county']['fips'], '12021')
        self.assertEqual(handoff['scope']['year'], 2026)
        self.assertFalse(handoff['personalRecommendationAllowed'])
        self.assertFalse(any(f['externally_verified'] for f in handoff['profile']['facts']))

    def test_each_minimum_meaning_stays_required(self):
        # RC03 (coverage year) defaults to 2026 under D108 for the pilot tool,
        # so omitting it no longer blocks the review; see the test below.
        for identifier in ['RC01', 'T03', 'T05', 'RC04', 'T06', 'T07', 'T08', 'T09', 'T10']:
            with self.subTest(identifier=identifier):
                self.case.setUp()
                self.fill(omit={identifier})
                self.assertFalse(self.status()['canReview'])
                with self.assertRaises(ProfileError):
                    self.review()

    def test_unanswered_year_defaults_to_pilot_year(self):
        self.case.setUp()
        self.fill(omit={'RC03'})
        status = self.status()
        self.assertTrue(status['canReview'])
        year = next(c for c in status['criteria'] if c['id'] == 'year')
        self.assertEqual(year['state'], 'defaulted')
        self.assertEqual(status['scope']['year'], 2026)

    def test_lists_need_retained_names_but_not_all_lookup_details(self):
        self.fill(lists=True)
        self.assertTrue(self.status()['canReview'])
        review = self.review()
        text = str(review['rows'])
        self.assertIn('5 mg', text)
        self.assertIn('10 mg', text)
        self.assertIn('Dr. Synthetic', text)
        self.assertIn('DOCTOR_CHECKS_OPEN', [h['code'] for h in review['readiness']['holds']])
        self.assertIn('MEDICINE_CHECKS_OPEN', [h['code'] for h in review['readiness']['holds']])
        self.case.g['fields'].pop('needs.providers')
        self.assertFalse(self.status()['canReview'])

    def test_unknown_optional_dimensions_remain_visible_and_unverified(self):
        self.fill(omit={'T06', 'T07', 'T09', 'T10', 'RC04'})
        for identifier in ['T06', 'T07', 'T09', 'T10', 'RC04']:
            self.case.turn({'type': 'edit', 'id': identifier}, aiConsent=False, contextPolicy=None)
            self.local('unknown', id=identifier)
        self.local('resume')
        self.assertTrue(self.status()['canReview'])
        handoff = self.confirm()
        open_labels = {x['label'] for x in handoff['holds'] if x['code'] == 'REPORT_LEFT_OPEN'}
        self.assertIn('Doctors and hospitals to keep', open_labels)
        self.assertIn('Current Medicare enrollment', open_labels)
        self.assertFalse(handoff['personalRecommendationAllowed'])

    def test_unknown_location_year_do_not_unlock_or_auto_reask(self):
        self.fill(omit={'T03', 'RC03'})
        for identifier in ['T03', 'RC03']:
            self.local('edit', id=identifier)
            self.local('defer', id=identifier)
        self.local('resume')
        self.assertFalse(self.status()['canReview'])
        self.assertNotIn('T03', [q['id'] for q in self.case.flow.eligible(self.case.owner,self.case.g,self.case.r)])
        self.assertNotIn('RC03', [q['id'] for q in self.case.flow.eligible(self.case.owner,self.case.g,self.case.r)])

    def test_requested_year_is_preserved_not_substituted_by_available_catalog(self):
        self.fill(year='2027')
        self.assertEqual(self.confirm()['scope']['year'], 2027)
        self.case.choice('T04', choice='month', month='2026-12')
        self.assertFalse(self.status()['canReview'])
        self.assertEqual(next(c for c in self.status()['missing'] if c['id'] == 'year')['state'], 'needs_clarification')

    def test_pending_clarification_holds_review(self):
        self.fill()
        self.assertFalse(readiness(self.case.g, self.case.r, pending={'update': {'id': 'T06'}})['canReview'])

    def test_current_coverage_is_not_actual_enrollment(self):
        self.fill(omit={'RC04'})
        self.assertEqual([x['question_id'] for x in self.status()['missing']], ['RC04'])

    def test_correction_invalidates_review_and_handoff(self):
        self.fill()
        review = self.review()
        self.case.choice('T10', choice='total_cost')
        with self.assertRaises(ProfileError):
            self.local('confirm_plan_review', token=review['token'])
        handoff = self.confirm()
        self.case.choice('T03', zip='33101')
        with self.assertRaises(ProfileError):
            self.local('get_plan_handoff', token=handoff['token'])

    def test_owner_chain_expiry_cancel_and_deletion_protect_receipts(self):
        self.fill()
        service = self.case.flow.plan_reviews
        review = self.review()
        chain = self.case.continuation.split('.')[0]
        for owner, current_chain in [('other', chain), (self.case.owner, 'other')]:
            with self.assertRaises(ProfileError):
                service.confirm(review['token'], owner, current_chain, self.case.g, self.case.r, self.status())
        self.local('cancel_plan_review', token=review['token'])
        with self.assertRaises(ProfileError):
            self.local('confirm_plan_review', token=review['token'])
        handoff = self.confirm()
        with patch('plan_review.time.time', return_value=time.time()+TTL+1):
            with self.assertRaises(ProfileError):
                self.local('get_plan_handoff', token=handoff['token'])
        handoff = self.confirm()
        self.case.flow.forget_owner(self.case.owner)
        self.assertEqual(service.handoffs, {})

    def test_confirmation_replay_is_idempotent_and_historical_replay_is_inert(self):
        self.fill()
        review = self.review()
        payload = self.case.payload({'type': 'confirm_plan_review', 'token': review['token']}, aiConsent=False, contextPolicy=None)
        first = self.case.take(payload)
        replay = self.case.flow.turn(self.case.owner, payload)
        self.assertEqual(first['plansHandoff']['token'], replay['plansHandoff']['token'])
        self.case.choice('T09', choice='predictable')
        self.assertNotIn('plansHandoff', self.case.flow.turn(self.case.owner, payload))

    def test_reviews_do_not_promote_report_confirmation_or_persist_receipts(self):
        self.fill()
        digest = input_digest(self.case.g, self.case.r)
        self.confirm()
        self.assertEqual(input_digest(self.case.g, self.case.r), digest)
        self.assertNotIn('plan_review', str(self.case.g)+str(self.case.r))

    def test_structured_correction_returns_to_review_without_repeating_the_field(self):
        self.fill()
        self.review()
        self.local('edit', id='T09')
        out = self.case.choice('T09', choice='predictable')
        self.assertTrue(out['planReadiness']['canReview'])
        self.assertIsNone(out['assessment']['nextQuestion'])


class FollowupContractTests(unittest.TestCase):
    def setUp(self):
        self.case = support.NaturalFlowTests()
        self.case.setUp()
        self.case.supply_fixture_followup = False
        self.case.flow.agent.composition_recovery = True

    def test_answer_only_keeps_the_answer_and_appends_the_continuation_without_a_repair_call(self):
        # Nov 9, 2026: a sound answer with no closing question is completed with the
        # educational continuation in the same composition stage; no paid repair.
        self.case.compositions.extend([
            {'reply': 'We can explore that together.', 'question_target': None, 'question': ''}])
        out = self.case.message('Help me understand Medicare.')
        self.assertEqual(out['generated']['status'], 'complete')
        self.assertTrue(out['reply'].startswith('We can explore that together.'))
        self.assertTrue(out['reply'].endswith('What would you like to understand next?'))
        self.assertEqual(out['generated']['validation_recovery']['reason'], 'missing_followup')
        self.assertEqual(out['metrics']['llmCalls'], 2)  # interpretation + one composition

    def test_empty_answer_without_a_followup_is_still_unavailable(self):
        self.case.compositions.extend([{'reply': '', 'question_target': None, 'question': ''} for _ in range(2)])
        out = self.case.message('Help me understand Medicare.')
        self.assertEqual(out['generated']['status'], 'unavailable')
        self.assertTrue(out['reply'])  # never-blank floor
        self.assertEqual(out['metrics']['llmCalls'], 3)

    def test_educational_followup_and_explicit_pause_are_supported(self):
        out = self.case.message('Help me understand Medicare.', compose={
            'question_target': None, 'question': 'Which part would you like to explore next?'})
        self.assertEqual(out['metrics']['continuation']['delivered'], 'question')
        out = self.case.message('No more questions.', compose={
            'reply': 'We can leave it here.', 'question_target': None, 'question': '',
            'agenda_update': {'current_concern': '', 'pause': True}})
        self.assertEqual(out['generated']['status'], 'complete')
        self.assertTrue(out['assessment']['intakePaused'])
