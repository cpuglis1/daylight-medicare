"""Scripted real-controller journeys; no provider calls or customer records."""
import copy
import unittest
from unittest.mock import patch

import test_curriculum_flow as support
from understanding import UnderstandingError


class UnderstandingFlowTests(unittest.TestCase):
    setUp = support.CurriculumFlowTests.setUp
    update = staticmethod(support.CurriculumFlowTests.update)
    payload = support.CurriculumFlowTests.payload
    take = support.CurriculumFlowTests.take
    turn = support.CurriculumFlowTests.turn
    message = support.CurriculumFlowTests.message
    stage_payloads = support.CurriculumFlowTests.stage_payloads
    extracted_context = support.CurriculumFlowTests.extracted_context
    composed_context = support.CurriculumFlowTests.composed_context
    extraction = staticmethod(support.CurriculumFlowTests.extraction)
    delivery = staticmethod(support.CurriculumFlowTests.delivery)
    education = staticmethod(support.CurriculumFlowTests.education)
    composition = support.CurriculumFlowTests.composition
    opening = support.CurriculumFlowTests.opening
    INSURANCE = support.CurriculumFlowTests.INSURANCE
    BENEFICIARY = support.CurriculumFlowTests.BENEFICIARY
    OPENING = support.CurriculumFlowTests.OPENING
    OVERVIEW = support.CurriculumFlowTests.OVERVIEW

    def test_cost_question_uses_shared_blocks_and_one_existing_composition_stage(self):
        out = self.message('What costs should I compare?',
            extraction=self.extraction(facts=['costs']),
            compose=self.composition(target=None,
                reply='A premium is the amount you pay each month for coverage. A plan’s premium alone is not your total cost.',
                refs=['costs'], education=self.education('teach', [self.delivery(
                    'cost_components', refs=('costs',))], 'costs')))
        self.assertEqual(out['generated']['status'], 'complete', out.get('generated'))
        guide = out['understanding']
        self.assertEqual(guide['capability'], 'costs')
        sent = self.composed_context()
        shared = next(g for g in sent['understanding_guides'] if g['capability'] == 'costs')
        self.assertEqual(guide['blocks'], shared['blocks'])
        self.assertNotIn('registry_binding', shared)
        self.assertNotIn('fictional_examples', shared)
        self.assertEqual([call['text']['format']['name'] for call in self.calls],
            ['daylight_guide_commands', 'daylight_resolved_conversation'])
        self.assertNotIn('understanding', out['guide'])
        self.assertNotIn('understanding', out['record'])
        self.assertEqual(guide['fictional_examples'][0]['receipt']['complete_total'], None)

    def test_timing_question_preserves_reported_month_without_a_personal_window(self):
        self.opening(role_known=True)
        out = self.message('How does Medicare sign-up timing work?',
            extraction=self.extraction(facts=['enrollment_intro','dates']),
            compose=self.composition(target=None,
                reply='The sign-up window and coverage start are different. Current insurance matters to timing.',
                refs=['enrollment_intro','dates'], education=self.education('teach', [self.delivery(
                    'enrollment_timing', refs=('enrollment_intro','dates'))], 'transition')))
        self.assertEqual(out['generated']['status'], 'complete', out.get('generated'))
        guide = out['understanding']
        self.assertEqual(guide['date_basis'], 'reported_only_no_personal_window_calculated')
        self.assertEqual(guide['reported_dates'][0]['label'], '65th birthday')
        self.assertIn('November', guide['reported_dates'][0]['value'])
        self.assertIsNone(guide['personal_result'])
        self.assertEqual(out['comparison']['authority']['recommendation']['state'], 'held')

    def test_free_lesson_and_its_replay_recheck_source_authority_without_generation(self):
        self.opening(role_known=True)
        payload = self.payload({'type':'read_concept', 'id':'costs'})
        before_calls = len(self.calls)
        out = self.take(payload)
        self.assertEqual(out['understanding']['capability'], 'costs')
        self.assertEqual(len(self.calls), before_calls)
        with patch.object(self.flow.understanding, 'guides', side_effect=UnderstandingError('CHANGED')):
            replay = self.flow.turn(self.owner, copy.deepcopy(payload))
        self.assertEqual(replay['understanding']['state'], 'unavailable')
        self.assertEqual(len(self.calls), before_calls)

    def test_citation_without_explicit_visual_does_not_create_a_guide(self):
        out = self.message('What costs should I compare?',
            extraction=self.extraction(facts=['costs']),
            compose=self.composition(target=None,
                reply='A plan’s premium alone is not your total cost.', refs=['costs']))
        self.assertEqual(out['generated']['status'], 'complete', out.get('generated'))
        self.assertNotIn('understanding', out)

    def test_parts_backed_original_visual_is_limited_through_the_real_controller(self):
        out = self.message('What is Original Medicare?',
            extraction=self.extraction(facts=['parts']),
            compose=self.composition(target=None,
                reply='Parts A and B together are run by the federal government.', refs=['parts'],
                education=self.education('teach', [self.delivery(
                    'original_medicare', refs=('parts',))], 'original')))
        self.assertEqual(out['generated']['status'], 'complete', out.get('generated'))
        self.assertEqual(out['advisor']['visual'], 'original')
        guide = out['understanding']
        self.assertEqual([block['id'] for block in guide['blocks']], ['original_base', 'original_access'])
        self.assertNotIn('Medigap', str(guide['blocks']))
        self.assertNotIn('Part D', str(guide['blocks']))


if __name__ == '__main__':
    unittest.main()
