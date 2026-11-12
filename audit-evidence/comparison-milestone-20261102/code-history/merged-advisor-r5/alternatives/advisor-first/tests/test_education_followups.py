"""Optional teaching questions remain bounded drafts, not a new advisor stage."""
import copy
import unittest

import test_natural_agent as support


class EducationFollowupTests(unittest.TestCase):
    setUp = support.NaturalAgentTests.setUp
    composition = support.NaturalAgentTests.composition
    compose = support.NaturalAgentTests.compose

    def teaching(self, followups):
        self.moves = [{'id': 'T05', 'question': {'id': 'T05',
            'question': 'What health insurance do you have now?'}}]
        self.context['evidence'] = [copy.deepcopy(self.agent.facts['routesintro'])]
        self.answer = self.composition(question_target='T05',
            reply='Original Medicare and Medicare Advantage are two coverage paths with different rules and costs.',
            question='What health insurance do you have now?', evidence_refs=['routesintro'],
            education_followups=followups)

    def test_current_teaching_can_offer_optional_drafts_without_replacing_question(self):
        prompts = ['How does prescription coverage work with each path?',
                   'How would I compare the costs?']
        self.teaching(prompts)
        out = self.compose()
        self.assertEqual(out['education_followups'], prompts)
        self.assertEqual(out['question_target'], 'T05')
        self.assertEqual(out['question'], self.answer['question'])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0]['reasoning'], {'effort': 'none'})
        spec = self.calls[0]['text']['format']['schema']['properties']['education_followups']
        self.assertEqual(spec['maxItems'], 2)
        self.assertEqual(spec['items']['maxLength'], 120)

    def test_old_scripted_output_defaults_to_no_prompts(self):
        self.answer = self.composition()
        self.assertEqual(self.compose()['education_followups'], [])

    def test_missing_teaching_pause_and_required_clarification_suppress_prompts(self):
        for condition in ('no_evidence', 'no_reply', 'pause', 'required'):
            with self.subTest(condition=condition):
                self.teaching(['How do the two paths differ?'])
                if condition == 'no_evidence':
                    self.answer.update(reply='We can continue from here.', evidence_refs=[])
                elif condition == 'no_reply':
                    self.answer['reply'] = ''
                elif condition == 'pause':
                    self.answer['agenda_update']['pause'] = True
                else:
                    self.moves[0]['required'] = True
                self.assertEqual(self.compose()['education_followups'], [])

    def test_malformed_optional_drafts_do_not_block_a_valid_reply(self):
        for prompts in ('question', [1], [''], ['  '], ['a' * 121],
                        ['one', 'two', 'three'], ['one\ntwo']):
            with self.subTest(prompts=prompts):
                self.teaching(prompts)
                before = len(self.calls)
                out = self.compose()
                self.assertEqual(out['education_followups'], [])
                self.assertEqual(out['reply'], self.answer['reply'])
                self.assertEqual(out['question_target'], 'T05')
                self.assertEqual(len(self.calls)-before, 1)

    def test_duplicates_and_exact_previously_answered_question_are_removed(self):
        self.teaching(['How do costs differ?', '  how do costs differ? '])
        self.assertEqual(self.compose()['education_followups'], ['How do costs differ?'])
        self.teaching(['How do costs differ?'])
        self.context['recent_exchanges'] = [{'user': 'How do costs differ?',
            'assistant': 'A prior reviewed explanation.', 'question': ''}]
        self.assertEqual(self.compose()['education_followups'], [])

    def test_optional_drafts_share_literal_and_action_guards(self):
        for prompt in ('Can I pay $999 for this?', 'Will you enroll me because you can enroll now?'):
            with self.subTest(prompt=prompt):
                self.teaching([prompt])
                before = len(self.calls)
                out = self.compose()
                self.assertEqual(out['education_followups'], [])
                self.assertEqual(out['reply'], self.answer['reply'])
                self.assertEqual(out['question_target'], 'T05')
                self.assertEqual(len(self.calls)-before, 1)

    def test_one_bad_supplement_does_not_remove_a_safe_alternative(self):
        self.teaching(['Can I pay $999 for this?', 'How do costs differ?'])
        out = self.compose()
        self.assertEqual(out['education_followups'], ['How do costs differ?'])
        self.assertEqual(out['reply'], self.answer['reply'])


if __name__ == '__main__':
    unittest.main()
