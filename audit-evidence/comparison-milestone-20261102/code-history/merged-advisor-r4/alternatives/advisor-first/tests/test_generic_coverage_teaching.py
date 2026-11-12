"""Generic sourced teaching must not be mistaken for reported insurance.

Use the real composition validator and injected Responses transport. No paid
calls, source-release changes, or new authority to assert personal coverage.
"""
import copy
import unittest

import test_natural_agent as support
from chat import ModelUnavailable


class GenericCoverageTeachingTests(unittest.TestCase):
    setUp = support.NaturalAgentTests.setUp
    composition = support.NaturalAgentTests.composition
    compose = support.NaturalAgentTests.compose

    def prepare(self, reply, *, coverage_report=False, evidence=True):
        self.moves = [{'id': 'T05', 'question': {'id': 'T05',
                      'question': 'What health insurance do you have now?'}}]
        self.context['evidence'] = [copy.deepcopy(self.agent.facts[identifier])
                                    for identifier in ('routesintro', 'options')] if evidence else []
        refs = ['guide.situation.age65']
        if coverage_report:
            self.context['reports'].append({'id': 'guide.coverage.current',
                                           'value': ['employer'], 'status': 'reported'})
            refs.append('guide.coverage.current')
        self.answer = self.composition(question_target='T05', reply=reply,
            question='What health insurance do you have now?', report_refs=refs,
            evidence_refs=['routesintro', 'options'] if evidence else [])

    def test_exact_live_overview_keeps_sourced_generic_drug_coverage_explanation(self):
        # Observed live regression: the last clause was matched as personal
        # because earlier sentences contained You/your, despite no current
        # insurance report or statement being present.
        reply = ('You’ll usually compare two main Medicare paths: Original Medicare, '
                 'which is Part A and Part B through the federal program, or a Medicare '
                 'Advantage plan, which is a private plan that provides your Medicare '
                 'coverage. With Original Medicare, you can add a separate drug plan '
                 'and may be able to add Medigap; with Medicare Advantage, drug coverage '
                 'is often included.')
        self.prepare(reply)
        out = self.compose()
        self.assertEqual(out['reply'], reply)
        self.assertEqual(out['question_target'], 'T05')
        self.assertNotIn('guide.coverage.current', out['report_refs'])
        self.assertEqual(len(self.calls), 1)
        self.assertIs(self.calls[0]['store'], False)
        self.assertEqual(self.calls[0]['tools'], [])

    def test_nonpossessive_qualified_categories_do_not_inherit_unrelated_personal_scope(self):
        for reply in (
            'You can compare the paths. Drug coverage is usually included with Medicare Advantage.',
            'You can learn one piece at a time; prescription drug coverage is often included.',
            'You can compare the paths, drug coverage is generally included with Medicare Advantage.',
            'You can compare the paths. Drug coverage is included in most plans.',
            'You can compare the paths. Prescription coverage is offered with many plans.',
            'You can compare the paths. Drug coverage is made available in some Medicare Advantage plans.',
            'You have coverage options. Drug coverage is included in most plans.',
        ):
            with self.subTest(reply=reply):
                self.prepare(reply)
                self.assertEqual(self.compose()['reply'], reply)

    def test_live_overview_with_generality_after_predicate_is_not_personal_insurance(self):
        reply = ('You’ll usually choose between two main Medicare paths: Original Medicare, '
                 'which is Parts A and B from the federal program, or a Medicare Advantage '
                 'plan, which provides Parts A and B through a private plan. With Original '
                 'Medicare, you can add a separate drug plan and may be able to buy Medigap; '
                 'with Medicare Advantage, drug coverage is included in most plans, and you '
                 'still pay the Part B premium either way.')
        self.prepare(reply)
        self.assertEqual(self.compose()['reply'], reply)
        self.assertNotIn('guide.coverage.current', self.answer['report_refs'])

    def test_actual_and_implied_personal_insurance_claims_still_need_coverage_report(self):
        for reply in (
            'Your insurance is through a former job.',
            'You are currently covered through a former job.',
            'Your drug coverage is often included with Medicare Advantage.',
            'You are retired. Coverage is through a former employer.',
            'Your insurance, which comes from a former job, is still active.',
            'You have insurance through a current job.',
            'Your coverage comes from a current job.',
            'Her coverage is through a former job.',
            'His health plan is through a current job.',
            'Their coverage will continue through a current job.',
            'Your drug coverage is included in most plans.',
            'His prescription coverage is offered with many plans.',
            'You have drug coverage in most plans.',
        ):
            with self.subTest(reply=reply):
                self.prepare(reply)
                with self.assertRaisesRegex(ModelUnavailable,
                        'A personal insurance statement needs its resolved coverage report'):
                    self.compose()

    def test_actual_insurance_statement_can_still_use_its_existing_resolved_report(self):
        reply = 'Your insurance is through a current job.'
        self.prepare(reply, coverage_report=True)
        self.assertEqual(self.compose()['reply'], reply)

    def test_generic_category_exception_does_not_remove_reviewed_evidence_requirement(self):
        self.prepare('You can compare the paths. Drug coverage is often included with Medicare Advantage.',
                     evidence=False)
        with self.assertRaisesRegex(ModelUnavailable, 'needs reviewed evidence'):
            self.compose()


if __name__ == '__main__':
    unittest.main()
