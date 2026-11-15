"""D138 conversation-to-panels contracts. Scripted transport, no network or model billing."""
import unittest
import test_natural_flow as harness
import medigap_profile as pricing
from adaptive_flow import metadata
from natural_flow import CONTEXT_POLICY, NaturalConversation
from natural_agent import false_unavailability


class D138Tests(unittest.TestCase):
    setUp = harness.NaturalFlowTests.setUp
    update = staticmethod(harness.NaturalFlowTests.update)
    extraction = staticmethod(harness.NaturalFlowTests.extraction)
    for name in ('payload', 'take', 'turn', 'message', 'choice', 'task', 'stage_payloads',
                 'extracted_context', 'composed_context'):
        locals()[name] = getattr(harness.NaturalFlowTests, name)

    def ready(self):
        self.choice('RC01', choice='self'); self.choice('T03', zip='34102')
        self.choice('MG_AGE', choice='66'); self.choice('MG_SEX', choice='Female')
        self.choice('MG_TOBACCO', choice='Non-Tobacco')

    def test_the_model_is_told_what_the_tabs_can_show_without_a_task(self):
        self.choice('RC01', choice='self'); self.choice('T03', zip='34102')
        self.assertEqual(metadata(self.r)['task'], '')
        pages = self.flow.context(self.g, self.r, CONTEXT_POLICY)['plans_pages']
        self.assertEqual(pages['medigap']['status'], 'missing')
        self.assertEqual(pages['medigap']['still_needed'],
                         ['age', 'sex (Female or Male)', 'tobacco use'])   # D157: plain words
        self.assertEqual(pages['part_d']['status'], 'ready')
        self.ready()
        pages = self.flow.context(self.g, self.r, CONTEXT_POLICY)['plans_pages']
        self.assertEqual((pages['medigap']['status'], pages['medigap']['still_needed']), ('ready', []))
        # D129 holds: status only, never a rate, plan or count.
        self.assertEqual(set(pages['medigap']), {'tab', 'shows', 'status', 'message', 'note', 'still_needed'})
        self.assertNotIn('plans_pages', self.flow.context(self.g, self.r, None))

    def test_a_reply_cannot_deny_what_a_ready_tab_shows(self):
        both = {'medigap': {'status': 'ready'}, 'part_d': {'status': 'ready'}}
        medigap_only = {'medigap': {'status': 'ready'}, 'part_d': {'status': 'unsupported'}}
        observed = ['I don’t have supplement prices available here to show you, so I can’t give you a reliable dollar comparison.',
                    'I don’t have current local plan listings or published prices available in this conversation.',
                    'I don’t have published Medigap premiums or Part D plan details available here yet.',
                    'I don’t have a current Plan G premium quote for ZIP code 34108.']
        for reply in observed:
            with self.subTest(reply=reply):
                self.assertTrue(false_unavailability(reply, both))
        allowed = [('I can’t state the amounts here, but the Medicare Supplement (Medigap) tab now lists premiums for your details.', both),
                   ('I can’t give a guaranteed personal quote.', both),
                   ('I don’t have supported 2027 plan prices here.', medigap_only),
                   ('I don’t have published Medigap premiums or Part D plan details available here yet.', medigap_only),
                   ('I don’t have supplement prices available here.', {'medigap': {'status': 'missing'}, 'part_d': {'status': 'missing'}}),
                   ('Medigap helps pay your share of costs under Original Medicare.', both)]
        for reply, pages in allowed:
            with self.subTest(reply=reply):
                self.assertFalse(false_unavailability(reply, pages))

    def test_naming_the_product_opens_its_route(self):
        named = NaturalConversation.named_plan_task
        for text in ['Can you show me what the supplement plans cost?', 'How much is Plan G?',
                     'I think I want a Medigap supplement.', 'Original Medicare with a supplement and a drug plan']:
            self.assertEqual(named(text), 'medigap', text)
        for text in ['I need a drug plan.', 'Which Part D plans can I get and what do they cost?']:
            self.assertEqual(named(text), 'drug_pricing', text)
        # "Plan B" and "Plan D" are common slips for Parts B and D.
        for text in ['I want an Advantage plan.', 'I have Plan A and Plan B.', 'What is Medicare?', '']:
            self.assertIsNone(named(text), text)

    def test_a_price_question_without_the_word_medigap_starts_the_pricing_questions(self):
        self.choice('RC01', choice='self'); self.choice('T03', zip='34102')
        text = 'Can you show me what the supplement plans cost?'
        result = self.message(text, extraction=self.extraction(mode='answer', fact_ids=['basics']))
        self.assertEqual(metadata(self.r)['task'], 'medigap')
        self.assertEqual(result['assessment']['nextQuestion']['id'], 'MG_AGE')

    def test_a_drug_plan_request_sets_the_part_d_route_and_medigap_details_finish_first(self):
        self.choice('RC01', choice='self'); self.choice('T03', zip='34103')
        self.message('Which Part D plans can I get and what do they cost?',
                     extraction=self.extraction(mode='answer', fact_ids=['basics']))
        self.assertEqual(metadata(self.r)['task'], 'drug_pricing')
        self.message('How much is Plan G?', extraction=self.extraction(mode='answer', fact_ids=[]))
        self.assertEqual(metadata(self.r)['task'], 'medigap')
        self.message('And I need a drug plan too, what do those cost?',
                     extraction=self.extraction(mode='answer', fact_ids=[]))
        self.assertEqual(metadata(self.r)['task'], 'medigap')  # age, sex and tobacco are still open


    def test_a_bare_zip_or_age_is_recorded_without_ai_while_replies_are_paused(self):
        from unittest.mock import patch
        self.choice('RC01', choice='self')
        self.turn({'type': 'task', 'task': 'medigap', 'preparing': True}, aiConsent=False, contextPolicy=None)
        self.assertEqual(self.flow.assess(self.g, self.r)['nextQuestion']['id'], 'T03')
        with patch.object(type(self.flow), 'ai_paused', return_value=True):
            result = self.message('34102')
            self.assertEqual(self.flow.value(self.g, 'comparison.scope.zip'), '34102')
            self.assertEqual(result['assessment']['nextQuestion']['id'], 'MG_AGE')
            result = self.message('66')
            self.assertEqual(result['medigapProfile']['inputs']['age'], 66)
            self.assertEqual(result['assessment']['nextQuestion']['id'], 'MG_SEX')
        self.assertEqual(self.calls, [])  # no model call was made


    def test_cms_checklist_names_match_the_operations_scorer(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'infrastructure/daylight-operations/src'))
        from daylight_operations.checklist import CHECKLIST_ITEMS, coverage_score
        import cms_checklist
        self.assertEqual(cms_checklist.ITEM_IDS, tuple(CHECKLIST_ITEMS))
        receipt = cms_checklist.receipt(self.flow.facts, None)
        score = coverage_score(receipt['items'])
        self.assertEqual((score['covered'], score['total'], score['unknown_items']), (0, 12, []))

    def test_cms_checklist_content_gaps_are_named_not_hidden(self):
        """A conversation cannot cover a topic it has no reviewed statement for."""
        import cms_checklist
        audit = cms_checklist.content_audit(self.flow.facts)
        # The six gaps found on November 11 were closed the same day by the
        # owner-accepted statements in pilot-rules-r3-cms-checklist.json.
        self.assertEqual(audit['gaps'], [])
        without = {key: fact for key, fact in self.flow.facts.items() if not key.startswith('cms_')}
        self.assertEqual(cms_checklist.content_audit(without)['gaps'],
                         ['coverage_outside_us', 'effect_on_current_coverage', 'plan_year_changes_and_eoc',
                          'how_to_file_complaints', 'special_needs_plan_requirements', 'right_to_cancel'])

    def test_cms_checklist_counts_only_delivered_reviewed_teaching(self):
        import cms_checklist
        record = {'concepts': {
            'cost_components': {'depth': 'introduced', 'evidence_refs': ['costs']},
            'medicare_advantage': {'depth': 'explored', 'evidence_refs': ['advantage']},
            'prescription_coverage': {'depth': 'needs_clarification', 'evidence_refs': ['drugbasics']}}}
        receipt = cms_checklist.receipt(self.flow.facts, record)
        self.assertTrue(receipt['items']['premiums_including_part_b']['covered'])
        self.assertTrue(receipt['items']['cost_sharing']['covered'])
        self.assertFalse(receipt['items']['formulary_coverage']['covered'])  # not delivered
        self.assertFalse(receipt['items']['how_to_file_complaints']['covered'])  # not delivered
        self.assertEqual((receipt['covered'], receipt['complete'], receipt['enrollment_authorization']), (2, False, False))

    def test_every_v3_turn_carries_the_checklist_account(self):
        result = self.message('What is Medicare?', extraction=self.extraction(mode='answer', fact_ids=['basics']))
        self.assertEqual(result['cmsChecklist']['total'], 12)
        self.assertNotIn('cmsChecklist', self.choice('RC01', choice='self'))


    def test_review_rows_do_not_contradict_a_part_a_only_report(self):
        self.choice('T05', choice='original')
        rows = {row['id']: row['value'] for row in self.flow.rows(self.g, self.r)}
        self.assertIn('Parts A and B', rows['T05'])
        self.r.setdefault('facts', {})['RC04'] = {'value': {'choice': 'a_only'}, 'revision': 1}
        rows = {row['id']: row['value'] for row in self.flow.rows(self.g, self.r)}
        self.assertEqual(rows['T05'], 'Medicare')


    def test_before_you_enroll_shows_all_twelve_topics_and_records_the_time(self):
        import cms_checklist
        step = cms_checklist.before_enroll(self.flow.facts)
        self.assertEqual([item['id'] for item in step['items']], list(cms_checklist.ITEM_IDS))
        self.assertTrue(step['complete'])
        self.assertTrue(all(item['statements'] and item['complete'] for item in step['items']))
        self.assertEqual(self.calls, [])
        opened = self.turn({'type': 'before_enroll_open'}, aiConsent=False, contextPolicy=None)['beforeEnroll']
        self.assertEqual(len(opened['items']), 12)
        self.assertRegex(opened['shown_at'], r'^2\d{3}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$')
        self.assertIsNone(opened['acknowledged_at'])
        done = self.turn({'type': 'before_enroll_ack'}, aiConsent=False, contextPolicy=None)['beforeEnroll']
        self.assertEqual(done['shown_at'], opened['shown_at'])
        self.assertIsNotNone(done['acknowledged_at'])
        self.assertEqual(done['digest'], opened['digest'])
        self.assertEqual(self.calls, [])  # no model call
        self.assertEqual(self.flow.rows(self.g, self.r), [])  # no profile change

    def test_before_you_enroll_cannot_be_acknowledged_with_a_topic_missing(self):
        import cms_checklist
        without = {key: fact for key, fact in self.flow.facts.items() if key != 'cms_complaints'}
        step = cms_checklist.before_enroll(without)
        self.assertFalse(step['complete'])
        self.assertEqual([item['id'] for item in step['items'] if not item['complete']], ['how_to_file_complaints'])


    def test_a_reply_that_names_the_ready_tab_is_grounded(self):
        """Found in the November 11 live rerun: the reply named the tab as told and was rejected."""
        self.ready()
        self.turn({'type': 'task', 'task': 'medigap', 'preparing': True}, aiConsent=False, contextPolicy=None)
        reply = ('The Medicare Supplement (Medigap) tab on the Plans page now lists premiums for your details. '
                 'The pilot list covers ages 65–74 in ZIPs 34101–34108, and the Part D drug plans tab has the 2026 plans for Collier County.')
        self.compositions.append({'reply': reply})
        result = self.message('Can you show me what the supplement plans cost?',
                              extraction=self.extraction(mode='answer', fact_ids=[]))
        self.assertEqual(result['generated']['status'], 'complete', result['generated'])
        self.assertIn('Medicare Supplement (Medigap) tab', result['reply'])


if __name__ == '__main__':
    unittest.main()
