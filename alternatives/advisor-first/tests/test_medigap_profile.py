"""D130 fictional profile/transport checks. No network or model billing."""
import copy
import unittest
from unittest.mock import patch
import test_natural_flow as harness
import medigap_profile as pricing
from natural_state import prune_for_storage, set_target
from adaptive_flow import metadata, Q as PINNED_Q


class MedigapProfileTests(unittest.TestCase):
    setUp = harness.NaturalFlowTests.setUp
    update = staticmethod(harness.NaturalFlowTests.update)
    extraction = staticmethod(harness.NaturalFlowTests.extraction)
    for name in ('payload', 'take', 'turn', 'message', 'choice', 'task', 'stage_payloads',
                 'extracted_context', 'composed_context'):
        locals()[name] = getattr(harness.NaturalFlowTests, name)

    def seed(self, role='self'):
        self.choice('RC01', choice=role)
        self.choice('T03', zip='34101')

    def test_direct_entry_with_no_profile_starts_with_the_coverage_recipient(self):
        result = self.turn({'type': 'task', 'task': 'medigap', 'preparing': True},
                           aiConsent=False, contextPolicy=None)
        self.assertEqual(result['assessment']['nextQuestion']['id'], 'RC01')
        self.assertEqual(result['medigapProfile']['status'], 'missing')
        self.assertEqual(self.calls, [])

    def test_medigap_entry_reuses_reports_and_opens_missing_chat_buttons_without_ai(self):
        self.seed();self.choice('MG_AGE', choice='68');self.choice('MG_SEX', choice='Female')
        before = copy.deepcopy(self.g['fields'])
        result = self.turn({'type': 'task', 'task': 'medigap', 'preparing': True},
                           aiConsent=False, contextPolicy=None)
        question = result['assessment']['nextQuestion']
        self.assertEqual(question['id'], 'MG_TOBACCO')
        self.assertEqual([item[0] for item in question['choices']], ['Non-Tobacco', 'Tobacco User'])
        self.assertIn('separate tobacco and non-tobacco prices', question['why'])
        for field, item in before.items():
            self.assertEqual(self.g['fields'][field], item)
        self.assertEqual(self.calls, [])
        self.assertFalse(result['assessment']['narrative']['opener'])
        self.turn({'type': 'unknown', 'id': 'MG_TOBACCO'}, aiConsent=False)
        result = self.turn({'type': 'task', 'task': 'medigap', 'preparing': True}, aiConsent=False)
        self.assertNotEqual((result['assessment']['nextQuestion'] or {}).get('id'), 'MG_TOBACCO')
        result = self.turn({'type': 'edit', 'id': 'MG_TOBACCO'}, aiConsent=False)
        self.assertEqual(result['assessment']['nextQuestion']['id'], 'MG_TOBACCO')
        self.assertEqual(self.calls, [])

    def test_structured_profile_shared_private_and_no_model_call(self):
        self.seed()
        for key, value in [('MG_AGE', '68'), ('MG_SEX', 'Female'), ('MG_TOBACCO', 'Non-Tobacco')]:
            result = self.turn({'type': 'choice', 'id': key, 'fields': {'choice': value},
                               'source': 'plans_filter'}, aiConsent=False, contextPolicy=None)
        self.assertEqual(self.calls, [])
        self.assertEqual(result['medigapProfile']['status'], 'ready')
        self.assertEqual(result['medigapProfile']['inputs']['age'], 68)
        self.assertEqual(self.r['natural']['provenance']['guide.' + pricing.FIELDS['MG_SEX']]['method'], 'plans_filter')
        g, r = prune_for_storage(self.g, self.r)
        self.assertTrue(set(pricing.FIELDS.values()).isdisjoint(g['fields']))
        self.g['preferences']['saveSensitive'] = True
        g, r = prune_for_storage(self.g, self.r)
        self.flow.validate(g, r)
        self.assertEqual(g['fields'][pricing.FIELDS['MG_SEX']]['value'], 'Female')
        self.assertNotIn('MG_AGE', PINNED_Q)

    def test_one_message_captures_all_reports_without_second_intake(self):
        text = 'This is for me. I am 68. I am Male. I do not use tobacco. My ZIP is 34101.'
        updates = [self.update('RC01', {'choice': 'self'}, 'This is for me.'),
                   self.update('T03', {'zip': '34101'}, 'My ZIP is 34101.'),
                   self.update('MG_AGE', {'choice': '68'}, 'I am 68.'),
                   self.update('MG_SEX', {'choice': 'Male'}, 'I am Male.'),
                   self.update('MG_TOBACCO', {'choice': 'Non-Tobacco'}, 'I do not use tobacco.')]
        # Explicit quote-date age, regardless of the machine's later test date.
        with patch('medigap_profile.datetime') as clock:
            clock.now.return_value.date.return_value.isoformat.return_value = pricing.DATE
            result = self.message(text, updates)
        self.assertEqual(result['medigapProfile']['status'], 'ready')
        self.assertEqual(result['medigapProfile']['missing'], [])
        self.assertEqual(len(self.calls), 2)
        self.assertTrue(all('MG_' not in item['id'] for item in self.flow.eligible(self.owner, self.g, self.r)))

    def test_missing_only_clear_purpose_unknown_and_age_limit(self):
        self.seed();self.choice('MG_SEX', choice='Female')
        metadata(self.r)['task'] = 'medigap'
        question = self.flow.assess(self.g, self.r)['nextQuestion']
        self.assertEqual(question['id'], 'MG_AGE')
        self.assertIn('65–74', question['why'])
        self.assertEqual(question['question'], 'How old are you?')  # D138
        set_target(self.r, question)
        self.continuation = None
        self.turn({'type': 'refresh'}, aiConsent=False)
        result = self.turn({'type': 'unknown', 'id': 'MG_AGE'}, aiConsent=False)
        self.assertNotEqual(result['assessment']['nextQuestion']['id'], 'MG_AGE')
        self.assertIn('MG_AGE', result['medigapProfile']['held'])
        self.choice('MG_AGE', choice='75')
        self.assertEqual(pricing.profile(self.g)['questions'], [])
        self.assertIn('75+', pricing.profile(self.g)['message'])
        self.assertFalse(self.flow.medigap_questions(self.g, self.r))

    def test_exact_birthday_age_and_changed_birthday(self):
        self.seed()
        self.flow.put(self.g, 'situation.age65', {'month': 10, 'year': 2023}, 'user_choice')
        self.assertEqual(pricing.profile(self.g)['inputs']['age'], 68)
        self.flow.put(self.g, 'situation.age65', {'month': 11, 'year': 2023, 'first_day': False}, 'user_choice')
        self.assertIsNone(pricing.profile(self.g)['inputs']['age'])
        self.continuation = None
        self.turn({'type': 'refresh'}, aiConsent=False)
        self.choice('MG_AGE', choice='67')
        self.assertEqual(pricing.profile(self.g)['inputs']['age'], 67)
        self.flow.put(self.g, 'situation.age65', {'month': 11, 'year': 2023, 'first_day': True}, 'user_choice')
        self.assertEqual(pricing.profile(self.g)['inputs']['age'], 68)
        self.assertEqual(self.g['fields'][pricing.FIELDS['MG_AGE']]['status'], 'stale')

    def test_literal_support_helper_scope_no_smoking_or_identity_inference(self):
        cases = [('MG_SEX', 'Female', 'Her name is Alice.', 'self'),
                 ('MG_SEX', 'Female', 'I identify as a woman.', 'self'),
                 ('MG_TOBACCO', 'Non-Tobacco', 'I do not smoke.', 'self'),
                 ('MG_TOBACCO', 'Non-Tobacco', 'I quit tobacco last week.', 'self'),
                 ('MG_AGE', '68', 'I will turn 68 next month.', 'self'),
                 ('MG_AGE', '68', 'I am 68.', 'someone'),
                 ('MG_SEX', 'Female', 'My mother is Female.', 'self')]
        for key, value, quote, role in cases:
            with self.subTest(quote=quote), self.assertRaises(ValueError):
                pricing.validate_proposal(self.update(key, {'choice': value}, quote), quote, role, today=pricing.DATE)
        quote = 'My mother is Female.'
        pricing.validate_proposal(self.update('MG_SEX', {'choice': 'Female'}, quote), quote, 'someone')

    def test_d138_plain_statements_are_recorded(self):
        """Plain statements of the kind that were rejected in the November 10 live runs."""
        accepted = [('MG_AGE', '66', "I'm 66 and I'm retiring next month.", None),
                    ('MG_AGE', '66', 'I was 66', 'MG_AGE'),
                    ('MG_AGE', '66', 'I just turned 66 last week.', None),
                    ('MG_AGE', '74', "I'm 74, on Original Medicare with no supplement", None),
                    ('MG_SEX', 'Female', "I'm a woman, and I don't smoke.", None),
                    ('MG_SEX', 'Male', 'I am a 68 year old man', None),
                    ('MG_SEX', 'Female', 'woman', 'MG_SEX'),
                    ('MG_TOBACCO', 'Non-Tobacco', "I don't use tobacco.", None),
                    ('MG_TOBACCO', 'Non-Tobacco', 'No', 'MG_TOBACCO'),
                    ('MG_TOBACCO', 'Non-Tobacco', 'No, never.', 'MG_TOBACCO'),
                    ('MG_TOBACCO', 'Tobacco User', 'Yes', 'MG_TOBACCO'),
                    ('MG_TOBACCO', 'Tobacco User', 'I use tobacco.', None)]
        for key, value, quote, active in accepted:
            with self.subTest(quote=quote):
                pricing.validate_proposal(self.update(key, {'choice': value}, quote), quote, 'self',
                                          {'id': active} if active else None, today='2026-11-25')
        rejected = [('MG_AGE', '65', 'I turn 65 on December 14.'),
                    ('MG_AGE', '65', 'I will be 65 next month.'),
                    ('MG_AGE', '66', 'I was 66 when I retired.'),
                    ('MG_AGE', '66', 'I am almost 66.'),
                    ('MG_SEX', 'Female', 'My doctor is a woman.'),
                    ('MG_SEX', 'Male', 'I am not a man.'),
                    # The category is tobacco, not smoking (owner, Nov 11).
                    ('MG_TOBACCO', 'Non-Tobacco', "I'm a woman, and I don't smoke."),
                    ('MG_TOBACCO', 'Non-Tobacco', 'I do not smoke.'),
                    ('MG_TOBACCO', 'Non-Tobacco', "I've never smoked"),
                    ('MG_TOBACCO', 'Tobacco User', "I'm a smoker."),
                    ('MG_TOBACCO', 'Non-Tobacco', 'No'),
                    ('MG_TOBACCO', 'Non-Tobacco', 'I stopped smoking in May.'),
                    ('MG_TOBACCO', 'Tobacco User', 'I smoke a cigar now and then. Does that count?')]
        for key, value, quote in rejected:
            with self.subTest(quote=quote), self.assertRaises(ValueError):
                pricing.validate_proposal(self.update(key, {'choice': value}, quote), quote, 'self', today='2026-11-25')

    def test_d138_a_64_year_old_sees_age_65_prices(self):
        self.seed();self.choice('MG_SEX', choice='Female');self.choice('MG_TOBACCO', choice='Non-Tobacco')
        self.choice('MG_AGE', choice='64')
        view = pricing.profile(self.g)
        self.assertEqual((view['status'], view['inputs']['age'], view['message']), ('ready', 65, ''))
        self.assertIn('age 64', view['note'])
        self.assertEqual(next(x['value'] for x in view['details'] if x['id'] == 'MG_AGE'), 64)
        self.choice('MG_AGE', choice='63')
        self.assertEqual(pricing.profile(self.g)['status'], 'unsupported')
        self.choice('MG_AGE', choice='66')
        self.assertEqual(pricing.profile(self.g)['note'], '')

    def test_d138_turning_65_this_november_or_december_is_priced_at_65(self):
        self.seed()
        self.flow.put(self.g, 'situation.age65', {'month': 12, 'year': 2026}, 'user_choice')
        self.assertEqual(pricing.profile(self.g)['inputs']['age'], 65)
        self.flow.put(self.g, 'situation.age65', {'month': 11, 'year': 2026, 'first_day': False}, 'user_choice')
        self.assertEqual(pricing.profile(self.g)['inputs']['age'], 65)

    def test_existing_birth_month_year_is_reused_without_guessing_the_day(self):
        self.seed()
        self.flow.put(self.g, 'coverage.birth', '1958-10', 'user_choice')
        self.assertEqual(pricing.profile(self.g)['inputs']['age'], 68)
        self.flow.put(self.g, 'coverage.birth', '1958-11', 'user_choice')
        self.assertIsNone(pricing.profile(self.g)['inputs']['age'])
        self.flow.put(self.g, 'coverage.birth.firstDay', 'yes', 'user_choice')
        self.assertEqual(pricing.profile(self.g)['inputs']['age'], 68)

    def test_helper_question_asks_for_beneficiary_age(self):
        self.seed('someone')
        metadata(self.r)['task'] = 'medigap'
        question = self.flow.assess(self.g, self.r)['nextQuestion']
        self.assertEqual(question['id'], 'MG_AGE')
        self.assertIn('person receiving coverage', question['question'])
        self.assertIn('person receiving coverage', pricing.profile(self.g)['questions'][0]['question'])

    def test_explicit_correction_updates_price_profile_and_context_is_scoped(self):
        self.seed();self.choice('MG_AGE', choice='68');self.choice('MG_SEX', choice='Male')
        self.choice('MG_TOBACCO', choice='Non-Tobacco')
        result = self.message('Correction: I was 69 on November 10, 2026.', [
            self.update('MG_AGE', {'choice': '69'}, 'I was 69 on November 10, 2026.', correction=True)])
        self.assertEqual(result['medigapProfile']['inputs']['age'], 69)
        self.assertEqual(result['medigapProfile']['inputs']['gender'], 'Male')
        from natural_flow import CONTEXT_POLICY
        metadata(self.r)['task'] = 'providers'
        context = self.flow.context(self.g, self.r, CONTEXT_POLICY)
        self.assertFalse(any(x['id'].startswith('guide.medigap.') for x in context['reports']))
        metadata(self.r)['task'] = 'medigap'
        context = self.flow.context(self.g, self.r, CONTEXT_POLICY)
        self.assertEqual(sum(x['id'].startswith('guide.medigap.') for x in context['reports']), 3)
        context = self.flow.context(self.g, self.r, None)
        self.assertFalse(any(x['id'].startswith('guide.medigap.') for x in context['reports']))

    def test_new_question_only_for_requested_pricing_not_general_chat(self):
        self.seed()
        self.assertFalse(self.flow.medigap_questions(self.g, self.r))
        result = self.message('I want Medigap prices.', extraction=self.extraction(goal_quote='I want Medigap prices.'))
        self.assertEqual(result['assessment']['nextQuestion']['id'], 'MG_AGE')
        self.assertEqual(result['generated']['status'], 'complete')


if __name__ == '__main__':
    unittest.main()
