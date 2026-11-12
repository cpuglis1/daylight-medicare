"""Paired language controls over real contracts and fictional in-memory reports.

No generation, source lookup, profile database or server startup is used. These
tests establish bounded guard behavior, not general model quality or entailment.
"""
import copy
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import server  # Register pinned imports only.
from chat import ModelUnavailable, ResponsesClient
from conversation_claims import explicit_defer_request
from natural_flow import CONTEXT_POLICY, NaturalConversation


class ConversationClaimTests(unittest.TestCase):
    def setUp(self):
        def forbidden(*args, **kwargs):
            self.fail('This validator test cannot make a model call.')
        self.flow = NaturalConversation(None, None,
            json.loads((HERE / 'web/guide-contract.json').read_text()),
            json.loads((HERE / 'web/teaching-facts.json').read_text()),
            json.loads((HERE / 'web/readiness-content.json').read_text()),
            ResponsesClient(key='fictional-unused', model='gpt-5.4', transport=forbidden),
            True, None, fixture=False)
        self.g, self.r = self.flow.initial()
        self.flow.capture(self.g, self.r, {'id':'RC01', 'entity':'profile', 'fields':{'choice':'self'}})
        self.context = self.flow.context(self.g, self.r, CONTEXT_POLICY, self.flow.question('T05'))
        self.context['evidence'] = [copy.deepcopy(self.flow.facts['basics'])]
        self.moves = self.flow.eligible('fictional-validation', self.g, self.r)

    def answer(self, **updates):
        return {'question_target':None, 'reply':'', 'question':'', 'report_refs':[],
                'evidence_refs':[], 'agenda_update':{'current_concern':'','pause':False},
                'education':{'purpose':'advance','updates':[],'visual':'none'},
                'education_followups':[], **updates}

    def validate(self, **updates):
        return self.flow.agent.validate_composition(self.answer(**updates), self.context, self.moves)

    def coverage(self, values):
        self.flow.capture(self.g, self.r, {'id':'T05', 'entity':'profile', 'fields':{'choice':','.join(values)}})
        self.context = self.flow.context(self.g, self.r, CONTEXT_POLICY, self.flow.question('T07'))
        self.context['evidence'] = [copy.deepcopy(self.flow.facts['basics'])]
        self.moves = self.flow.eligible('fictional-validation', self.g, self.r)

    def test_personal_current_coverage_must_match_the_referenced_value(self):
        self.coverage(['none'])
        for reply in ['You currently have insurance through your employer.',
                      'Your current coverage is through your employer.',
                      'You have employer coverage.', 'You currently have insurance.']:
            with self.subTest(reply=reply), self.assertRaisesRegex(ModelUnavailable, 'conflicts'):
                self.validate(reply=reply, report_refs=['guide.coverage.current'])

    def test_supported_coverage_paraphrases_and_none_remain_available(self):
        for values, replies in [(['employer'], ['You currently have insurance through your employer.',
                                               'Your current coverage is through your employer.']),
                                (['none'], ['You currently have no health insurance.'])]:
            with self.subTest(values=values):
                self.setUp()
                self.coverage(values)
                for reply in replies:
                    self.assertEqual(self.validate(reply=reply, report_refs=['guide.coverage.current'])['reply'], reply)

    def test_typed_none_does_not_prevent_discussing_possible_coverage(self):
        self.coverage(['none'])
        reply = 'We can discuss employer coverage as a possible category to understand.'
        self.assertEqual(self.validate(reply=reply)['reply'], reply)

    def test_unrelated_citation_cannot_support_provider_access(self):
        with self.assertRaisesRegex(ModelUnavailable, 'provider-access'):
            self.validate(reply='Medicare Advantage covers every doctor.', evidence_refs=['basics'])

    def test_relevant_citation_still_cannot_authorize_universal_advantage_access(self):
        self.context['evidence'] = [copy.deepcopy(self.flow.facts['advantage'])]
        for reply in ['Medicare Advantage covers every doctor.',
                      'Medicare Advantage is not free and covers every doctor.',
                      "Medicare Advantage doesn't have a free premium but covers every doctor."]:
            with self.subTest(reply=reply), self.assertRaisesRegex(ModelUnavailable, 'provider-access'):
                self.validate(reply=reply, evidence_refs=['advantage'])

    def test_negation_of_the_actual_provider_access_proposition_is_preserved(self):
        self.context['evidence'] = [copy.deepcopy(self.flow.facts['advantage'])]
        for reply in ['Medicare Advantage does not cover every doctor.',
                      "Medicare Advantage doesn't cover every doctor.",
                      'Medicare Advantage cannot let you see every doctor.']:
            with self.subTest(reply=reply):
                self.assertEqual(self.validate(reply=reply, evidence_refs=['advantage'])['reply'], reply)

    def test_scoped_provider_teaching_retains_dynamic_wording(self):
        self.context['evidence'] = [copy.deepcopy(self.flow.facts['advantage']), copy.deepcopy(self.flow.facts['original'])]
        for reply, refs in [
            ('With Medicare Advantage, access to doctors varies by plan.', ['advantage']),
            ('Original Medicare lets you see any doctor who accepts Medicare.', ['original']),
            ('Unlike Medicare Advantage, Original Medicare lets you use any doctor who accepts Medicare.', ['original', 'advantage'])]:
            with self.subTest(reply=reply):
                self.assertEqual(self.validate(reply=reply, evidence_refs=refs)['reply'], reply)

    def test_original_provider_access_requires_its_qualifier(self):
        self.context['evidence'] = [copy.deepcopy(self.flow.facts['original'])]
        with self.assertRaisesRegex(ModelUnavailable, 'provider-access'):
            self.validate(reply='Original Medicare lets you see any doctor.', evidence_refs=['original'])

    def test_application_topic_is_not_a_personal_application_status(self):
        for reply in ['You can leave the application question for later.',
                      'We can return to your application questions when useful.',
                      'If you have applied, that is a separate detail to establish.']:
            with self.subTest(reply=reply):
                self.assertEqual(self.validate(reply=reply)['reply'], reply)

    def test_asserted_application_status_still_requires_resolved_progress(self):
        for reply in ["You haven't applied yet.", 'You have already applied.', 'Your application is pending.']:
            with self.subTest(reply=reply), self.assertRaisesRegex(ModelUnavailable, 'progress report'):
                self.validate(reply=reply)
        self.context['reports'].append({'id':'readiness.RC04.profile.choice','status':'reported','value':'pending'})
        reply = 'Your application is pending.'
        self.assertEqual(self.validate(reply=reply, report_refs=['readiness.RC04.profile.choice'])['reply'], reply)

    def test_modal_may_accepts_new_verbs_without_a_verb_whitelist(self):
        for reply in ['We may revisit this after you have had time to think.',
                      'Your priorities may evolve as we talk.',
                      'That may simplify the next step.', 'May we revisit this later?']:
            with self.subTest(reply=reply):
                self.assertEqual(self.validate(reply=reply)['reply'], reply)

    def test_calendar_may_still_requires_a_source(self):
        for reply in ['Your May start date is a separate question.', 'We can return in May.', 'May 2027.']:
            with self.subTest(reply=reply), self.assertRaisesRegex(ModelUnavailable, 'date or amount'):
                self.validate(reply=reply)

    def test_prescription_target_cannot_ask_current_insurance(self):
        for question in ['What kind of coverage do you have?', 'Which drug coverage do you have?']:
            with self.subTest(question=question):
                out = self.validate(reply='We can use the next detail to focus the discussion.',
                    question_target='T07', question=question)
                self.assertEqual(out['question'], self.flow.question('T07')['question'])
                self.assertEqual(out['reply'], 'We can use the next detail to focus the discussion.')

    def test_prescription_question_paraphrases_remain_dynamic(self):
        for question in ['Which medicines would you like us to include?',
                         'What medications belong on your list?',
                         'Which prescriptions should we include in a coverage check?']:
            with self.subTest(question=question):
                self.assertEqual(self.validate(question_target='T07', question=question)['question'], question)

    def test_unrelated_double_question_recovers_only_the_canonical_question(self):
        for question in ['What coverage do you have now? Which prescriptions do you take?',
                         'What coverage do you have now and which prescriptions do you take?']:
            with self.subTest(question=question):
                out = self.validate(reply='We can take this a detail at a time.', question_target='T05', question=question)
                self.assertEqual(out['question'], self.flow.question('T05')['question'])
                self.assertEqual(out['reply'], 'We can take this a detail at a time.')

    def test_approved_coupled_fields_are_not_split_or_rejected(self):
        question = self.flow.question('RC11', ['jobEnd', 'coverageEnd'])
        self.moves = [{'id':'RC11','question':question}]
        generated = 'When did your job end? When did the health insurance end?'
        self.assertEqual(self.validate(question_target='RC11', question=generated)['question'], generated)

    def test_null_target_cannot_smuggle_a_personal_followup(self):
        reply = 'We can stay with this explanation.'
        for question in ['Which medicines do you take regularly?',
                         'Which doctors would you like to keep?',
                         'Have you already enrolled in Medicare Part B?']:
            with self.subTest(question=question):
                out = self.validate(reply=reply, question=question)
                self.assertIsNone(out['question_target'])
                self.assertEqual(out['question'], '')
                self.assertEqual(out['reply'], reply)

    def test_null_target_educational_invitation_remains_available(self):
        question = 'Would you like to explore how drug coverage works?'
        self.assertEqual(self.validate(question=question)['question'], question)

    def test_pause_omits_selected_practical_question_and_preserves_reply(self):
        reply = 'We can pause here.'
        out = self.validate(reply=reply, question_target='T05',
            question='What health insurance do you have now?',
            agenda_update={'current_concern':'','pause':True})
        self.assertEqual(out['reply'], reply)
        self.assertIsNone(out['question_target'])
        self.assertEqual(out['question'], '')

    def test_explicit_leave_for_later_defer_has_positive_and_scope_controls(self):
        for quote in ['Please leave the start-month question for later.',
                      'Let us come back to the coverage start later.']:
            with self.subTest(quote=quote):
                self.flow.agent._validate_fields({'id':'T04', 'scope':'intended', 'quote':quote,
                    'fields':[{'key':'choice','value':'deferred'}]})
        for quote in ["Don't leave that for later.", 'If I leave this for later, what happens?',
                      'My mother used to leave this for later.']:
            with self.subTest(quote=quote):
                self.assertFalse(explicit_defer_request(quote))

    def test_aspect_metadata_is_scoped_to_concept_and_actual_evidence(self):
        self.context['evidence'] = [copy.deepcopy(self.flow.facts['routesintro']), copy.deepcopy(self.flow.facts['options'])]
        update = {'concept_id':'coverage_paths', 'depth':'explored', 'reason':'deepen',
                  'evidence_refs':['options'], 'aspect_ids':['additional_coverage']}
        args = {'reply':'We can examine the added coverage pieces.', 'evidence_refs':['options'],
                'education':{'purpose':'teach','updates':[update],'visual':'none'}}
        self.assertEqual(self.validate(**args)['education']['updates'], [update])
        for change in [{'aspect_ids':['invented']}, {'evidence_refs':['routesintro']}]:
            with self.subTest(change=change):
                candidate = copy.deepcopy(args)
                candidate['evidence_refs'] = ['options','routesintro']
                candidate['education']['updates'][0].update(change)
                out = self.validate(**candidate)
                self.assertEqual(out['education']['updates'], [])
                self.assertEqual(out['reply'], args['reply'])


if __name__ == '__main__':
    unittest.main()
