"""Decision relevance is guidance, never a new questionnaire or authority."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from decision_guidance import guidance
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_natural_flow as flow_support
from natural_flow import CONTEXT_POLICY, LEGACY_CONTEXT_POLICY, PREVIOUS_CONTEXT_POLICY


def candidate(identifier, priority=1, required=False):
    return {'id': identifier, 'question': {'id': identifier},
            'priority': priority, 'required': required}


class DecisionGuidanceTests(unittest.TestCase):
    def test_comparison_marks_relevance_without_enforcing_intake_sequence(self):
        moves = [candidate('RC11'), candidate('T04'), candidate('T10'),
                 candidate('T07'), candidate('T06'), candidate('T03')]
        for removed in ('T03', 'T06', 'T07'):
            ranked, brief = guidance(moves, task='compare', age65=True,
                concerns=[{'topic':'timing','status':'open','subject':'beneficiary'}])
            self.assertEqual([item['id'] for item in ranked], [item['id'] for item in moves])
            self.assertTrue(brief['relevance_is_advisory'])
            self.assertEqual(brief['practical_focus'], 'timing')
            self.assertCountEqual([item['id'] for item in ranked], [item['id'] for item in moves])
            moves = [item for item in moves if item['id'] != removed]

    def test_comparison_confusion_can_be_answered_without_forcing_intake(self):
        ranked, brief = guidance([candidate('T03'), candidate('T04')], task='compare',
            age65=True, education_request={'kind':'clarify','concept_ids':['enrollment_timing']})
        self.assertEqual(brief['focus'], 'timing')
        self.assertEqual(brief['question_policy'], 'clarify_current_confusion')
        self.assertTrue(brief['return_point_is_optional'])
        self.assertEqual(ranked[0]['id'], 'T03')

    def test_timing_marks_dependencies_without_prescribing_next_question(self):
        moves = [candidate('T03'), candidate('T04'), candidate('RC09'), candidate('T10')]
        ranked, brief = guidance(moves, task='timing')
        self.assertEqual([item['id'] for item in ranked], ['T03', 'T04', 'RC09', 'T10'])
        self.assertEqual(brief['focus'], 'timing')
        self.assertIn('RC09', [item['question_id'] for item in brief['obstacles']])
        self.assertTrue(brief['return_point_is_optional'])
        self.assertEqual(brief['personal_research'], 'held')

    def test_all_approved_candidates_survive_without_mutating_source_state(self):
        moves = [candidate('T03'), candidate('T04'), candidate('RC09')]
        before = copy.deepcopy(moves)
        ranked, _ = guidance(moves, task='timing')
        self.assertEqual(moves, before)
        self.assertCountEqual([item['id'] for item in ranked], [item['id'] for item in moves])
        ranked[0]['question']['id'] = 'changed'
        self.assertEqual(moves, before)

    def test_current_explicit_concern_changes_relevance_without_claiming_a_result(self):
        moves = [candidate('T03'), candidate('T06'), candidate('T04')]
        ranked, brief = guidance(moves, task='timing', age65=True,
            concerns=[{'topic': 'doctors', 'status': 'open', 'subject': 'beneficiary'}])
        self.assertEqual(next(item for item in ranked if item['id'] == 'T06')['decision_relevance'],
                         'current_decision')
        self.assertEqual(brief['focus'], 'doctors')
        self.assertIn('exact provider check', brief['objective'])
        self.assertEqual(brief['personal_research'], 'held')

    def test_unknown_start_is_a_decision_obstacle_not_a_missing_preference_to_force(self):
        ranked, brief = guidance([candidate('RC04')], task='timing',
                                 dispositions={'T04': 'unknown'})
        self.assertEqual([item['id'] for item in ranked], ['RC04'])
        self.assertEqual(brief['obstacles'], [{'question_id': 'T04', 'state': 'unknown',
            'help': 'Help explain the decision; do not demand a preferred month.'}])

    def test_deferred_remains_distinct_from_unknown(self):
        _, brief = guidance([candidate('RC04')], task='timing', dispositions={'T04': 'deferred'})
        self.assertEqual(brief['obstacles'][0]['state'], 'deferred')
        self.assertIn('unless the person reopens', brief['obstacles'][0]['help'])

    def test_educational_detour_can_answer_without_demanding_return(self):
        ranked, brief = guidance([candidate('T04'), candidate('T07')], task='timing',
            pending_question='T04', education_request={'kind': 'explain', 'concept_ids': ['part_b']})
        self.assertEqual(brief['question_policy'], 'answer_first_return_when_useful')
        self.assertEqual(brief['focus'], 'learning')
        self.assertEqual(brief['practical_focus'], 'timing')
        self.assertEqual(ranked[0]['id'], 'T04')
        self.assertEqual(ranked[0]['decision_relevance'], 'current_decision')

    def test_learner_or_unspecified_concern_cannot_reframe_beneficiary_questions(self):
        moves = [candidate('T06'), candidate('RC09'), candidate('T04')]
        for subject in ('learner', 'unclear', None):
            with self.subTest(subject=subject):
                ranked, brief = guidance(moves, task='timing', concerns=[{
                    'topic': 'doctors', 'status': 'open', 'subject': subject}])
                self.assertEqual(brief['focus'], 'timing')
                self.assertEqual(brief['practical_focus'], 'timing')
                self.assertEqual(next(item for item in ranked if item['id'] == 'RC09')
                                 ['decision_relevance'], 'current_decision')
                self.assertEqual(next(item for item in ranked if item['id'] == 'T06')
                                 ['decision_relevance'], 'available_if_useful')
                provider = next(item for item in ranked if item['id'] == 'T06')
                self.assertEqual(provider['decision_relevance'], 'available_if_useful')
                self.assertCountEqual([item['id'] for item in ranked], ['T06', 'RC09', 'T04'])

    def test_learning_request_changes_explanation_without_reordering_practical_work(self):
        moves = [candidate('T06'), candidate('RC09'), candidate('T04'), candidate('T02')]
        original, _ = guidance(moves, task='timing', dispositions={'T04': 'unknown'})
        for kind, concept, focus in (('explain', 'provider_checks', 'doctors'),
                                     ('clarify', 'part_b', 'learning'),
                                     ('revisit', 'cost_components', 'total_cost')):
            with self.subTest(kind=kind, concept=concept):
                ranked, brief = guidance(moves, task='timing', dispositions={'T04': 'unknown'},
                    education_request={'kind': kind, 'concept_ids': [concept]})
                self.assertEqual(ranked, original)
                self.assertEqual(brief['focus'], focus)
                self.assertEqual(brief['practical_focus'], 'timing')
                self.assertEqual(brief['obstacles'][0]['question_id'], 'T04')
                self.assertEqual(brief['obstacles'][0]['state'], 'unknown')
                self.assertTrue(brief['return_point_is_optional'])

    def test_current_confusion_and_required_report_conflict_remain_separate(self):
        ranked, brief = guidance([candidate('T04'), candidate('T05', required=True)],
            education_request={'kind': 'clarify', 'concept_ids': ['coverage_paths']})
        self.assertEqual(ranked[0]['id'], 'T05')
        self.assertEqual(brief['question_policy'], 'clarify_current_confusion')
        self.assertEqual(brief['obstacles'][0]['state'], 'conflicting')

    def test_helper_identity_precedes_personal_question_choices(self):
        ranked, _ = guidance([candidate('T06'), candidate('RC01')],
                            concerns=[{'topic': 'doctors', 'status': 'open', 'subject': 'beneficiary'}])
        self.assertEqual(ranked[0]['id'], 'RC01')

    def test_closed_and_unsupported_concerns_do_not_drive_the_decision(self):
        _, brief = guidance([], task='timing', concerns=[
            {'topic': 'doctors', 'status': 'deferred', 'subject': 'beneficiary'},
            {'topic': 'commercial', 'status': 'open', 'subject': 'beneficiary'}])
        self.assertEqual(brief['focus'], 'timing')
        self.assertEqual(brief['obstacles'], [])


class DecisionPermissionIntegrationTests(unittest.TestCase):
    """Inspect actual injected request payloads, without inheriting other tests."""

    @staticmethod
    def extraction(concerns=()):
        return {'updates': [], 'requests': [], 'fact_ids': [],
                'agenda': {'concerns': list(concerns), 'priorityReason': {}},
                'situation_proposals': [], 'goal_quote': '',
                'education_request': {'kind': 'none', 'concept_ids': [], 'quote': ''}}

    @staticmethod
    def answer():
        return {'question_target': None, 'question': '',
                'reply': 'We can stay with the concern you want to discuss.',
                'agenda_update': {'current_concern': 'keeping a doctor', 'pause': False}}

    def case_with_v3_concern(self):
        case = flow_support.NaturalFlowTests()
        case.setUp()
        case.turn({'type': 'task', 'task': 'timing', 'preparing': True},
                  aiConsent=False, contextPolicy=None)
        case.turn({'type': 'choice', 'id': 'RC01', 'fields': {'choice': 'self'}},
                  aiConsent=False, contextPolicy=None)
        # The report state remains identical across the following messages.
        # Changing only a concern must not reorder older-policy request payloads.
        original_order = [item['id'] for item in case.flow.eligible(case.owner, case.g, case.r)]
        self.assertIn('T06', original_order)
        self.assertNotEqual(original_order[0], 'T06')
        message = 'Keeping my doctor matters to me.'
        out = case.message(message, extraction=self.extraction([{
            'topic': 'doctors', 'subject': 'beneficiary', 'scope': 'current',
            'status': 'open', 'quote': message}]), compose=self.answer())
        self.assertEqual(out['generated']['status'], 'complete')
        sent = case.stage_payloads('daylight_resolved_conversation')[-1]
        self.assertEqual(sent['resolved_context']['advisor_brief']['decision']['focus'], 'doctors')
        self.assertEqual(next(item for item in sent['question_candidates'] if item['id'] == 'T06')
                         ['decision_relevance'], 'current_decision')
        self.assertEqual([item['id'] for item in case.flow.eligible(case.owner, case.g, case.r)],
                         original_order, 'Eligibility itself must remain policy-neutral.')
        return case, original_order

    def test_older_policies_do_not_receive_v3_decision_tags_brief_or_concern_order(self):
        for policy in (LEGACY_CONTEXT_POLICY, PREVIOUS_CONTEXT_POLICY):
            with self.subTest(policy=policy):
                case, original_order = self.case_with_v3_concern()
                out = case.message('Please continue.', extraction=self.extraction(),
                                   compose=self.answer(), contextPolicy=policy)
                self.assertEqual(out['generated']['status'], 'complete')
                sent = case.stage_payloads('daylight_resolved_conversation')[-1]
                self.assertEqual([item['id'] for item in sent['question_candidates']], original_order)
                self.assertTrue(all('decision_relevance' not in item
                                    for item in sent['question_candidates']))
                for context in (case.extracted_context(), sent['resolved_context']):
                    self.assertNotIn('advisor_brief', context)
                    self.assertNotIn('recent_exchanges', context)
                chain = case.flow.current_chain[case.owner]
                self.assertEqual(case.flow.memory.brief(case.owner, chain, CONTEXT_POLICY), {})

    def test_current_v3_keeps_concern_guidance_without_removing_alternative_candidates(self):
        case, original_order = self.case_with_v3_concern()
        out = case.message('Please continue.', extraction=self.extraction(),
                           compose=self.answer(), contextPolicy=CONTEXT_POLICY)
        self.assertEqual(out['generated']['status'], 'complete')
        sent = case.stage_payloads('daylight_resolved_conversation')[-1]
        self.assertEqual(next(item for item in sent['question_candidates'] if item['id'] == 'T06')
                         ['decision_relevance'], 'current_decision')
        self.assertCountEqual([item['id'] for item in sent['question_candidates']], original_order)
        brief = sent['resolved_context']['advisor_brief']['decision']
        self.assertEqual(brief['focus'], 'doctors')
        self.assertTrue(brief['relevance_is_advisory'])
        self.assertTrue(brief['return_point_is_optional'])
        # November 8, 2026: an answer-only draft gains the approved return
        # point (the pending T04 timing question) rather than ending without one.
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T04')

    def test_route_revisit_retains_sources_for_open_provider_concern(self):
        case, _ = self.case_with_v3_concern()
        message = 'Can you bring this back to my two options?'
        extraction = self.extraction()
        extraction['education_request'] = {
            'kind': 'revisit', 'concept_ids': ['coverage_paths'], 'quote': message}
        out = case.message(message, extraction=extraction, compose=self.answer())
        self.assertEqual(out['generated']['status'], 'complete')
        context = case.stage_payloads('daylight_resolved_conversation')[-1]['resolved_context']
        evidence = {item['id']: item for item in context['evidence']}
        self.assertTrue({'routesintro', 'options', 'original', 'advantage', 'checks'} <= set(evidence))
        self.assertLessEqual(len(evidence), 8)  # six sources plus up to two rule statements (Nov 8, 2026)
        for identifier in ('original', 'advantage'):
            self.assertEqual(evidence[identifier], case.flow.facts[identifier])
        self.assertEqual(context['advisor_brief']['decision']['focus'], 'coverage_paths')
        self.assertEqual(context['advisor_brief']['decision']['practical_focus'], 'doctors')

    def test_old_permission_does_not_carry_provider_decision_sources_forward(self):
        case, _ = self.case_with_v3_concern()
        out = case.message('Please continue.', extraction=self.extraction(),
                           compose=self.answer(), contextPolicy=PREVIOUS_CONTEXT_POLICY)
        self.assertEqual(out['generated']['status'], 'complete')
        context = case.stage_payloads('daylight_resolved_conversation')[-1]['resolved_context']
        self.assertNotIn('advisor_brief', context)
        self.assertFalse({'original', 'advantage'} & {item['id'] for item in context['evidence']})

    def test_helpers_own_doctor_concern_and_learning_stay_separate_from_beneficiary_priority(self):
        case = flow_support.NaturalFlowTests()
        case.setUp()
        case.turn({'type': 'task', 'task': 'timing', 'preparing': True},
                  aiConsent=False, contextPolicy=None)
        case.turn({'type': 'choice', 'id': 'RC01', 'fields': {'choice': 'someone'}},
                  aiConsent=False, contextPolicy=None)
        message = 'I worry about keeping my own doctors.'
        out = case.message(message, extraction=self.extraction([{
            'topic': 'doctors', 'subject': 'learner', 'scope': 'current',
            'status': 'open', 'quote': message}]), compose=self.answer())
        self.assertEqual(out['generated']['status'], 'complete')
        self.assertTrue(any(item['topic'] == 'doctors' and item['subject'] == 'learner'
                            for item in case.r['natural']['agenda']['concerns']))
        sent = case.stage_payloads('daylight_resolved_conversation')[-1]
        self.assertEqual(sent['resolved_context']['advisor_brief']['decision']['focus'], 'timing')
        self.assertNotEqual(sent['question_candidates'][0]['id'], 'T06')
        provider = next(item for item in sent['question_candidates'] if item['id'] == 'T06')
        self.assertEqual(provider['decision_relevance'], 'available_if_useful')
        before_candidates = copy.deepcopy(sent['question_candidates'])

        # An explicit learning request is still welcome. It changes what to
        # explain, without inventing a beneficiary priority or changing intake.
        message = 'Could you explain how provider checks work?'
        extraction = self.extraction()
        extraction['education_request'] = {
            'kind': 'explain', 'concept_ids': ['provider_checks'], 'quote': message}
        out = case.message(message, extraction=extraction, compose=self.answer())
        self.assertEqual(out['generated']['status'], 'complete')
        sent = case.stage_payloads('daylight_resolved_conversation')[-1]
        decision = sent['resolved_context']['advisor_brief']['decision']
        self.assertEqual(decision['focus'], 'doctors')
        self.assertEqual(decision['practical_focus'], 'timing')
        self.assertEqual(decision['question_policy'], 'answer_first_return_when_useful')
        self.assertEqual(sent['question_candidates'], before_candidates)
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertNotIn('needs.priorities', case.g['fields'])
        self.assertNotIn('needs.providers', case.g['fields'])


if __name__ == '__main__':
    unittest.main()
