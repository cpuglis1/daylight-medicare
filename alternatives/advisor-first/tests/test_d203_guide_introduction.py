"""D203: guide selection and conversational context, scripted/offline only."""
import unittest
import test_pending_questions as pending
import conversation_planner as planner


class GuideIntroduction(pending.PendingBase):
    def draft(self, visual='none'):
        def compose(sent):
            q = next(m for m in sent['question_candidates'] if m['id'] == 'RC04')
            return dict(reply=('The guide can help you prepare what to ask. First, let’s establish where you are now.'
                               if visual == 'signup_route' else 'Let’s establish where you are now.'),
                        question_target=q['id'], question=q['question']['question'],
                        education=dict(purpose='advance', updates=[], visual=visual))
        return compose

    def test_model_gets_actual_guide_and_can_defer_without_using_receipt(self):
        out = self.opening(mode='discuss', focus='enrollment', compose_override=self.draft())
        plan = self.composed_context()['discussion_plan']
        self.assertIn('signup_route', plan['software_cards'])
        brief = plan['guide_presentation']
        self.assertEqual(brief['route'], 'confirm_with_social_security')
        self.assertEqual(brief['guides'], ['phone'])
        self.assertIn('2–3 short', brief['rule'])
        self.assertNotIn('signup_route', [c['kind'] for c in out.get('cards', [])])
        self.assertNotIn('signup_route', planner.state(self.flow, self.owner)['cards'])
        self.assertFalse(self.flow.ux.shown(self.owner, self.flow.current_chain.get(self.owner),
                                          'signup_route:confirm_with_social_security'))

        later = self.say('Can we use that guide now?', mode='discuss', focus='enrollment',
                         targets=['RC04'], disposition='detour', compose=self.draft('signup_route'))
        self.assertIn('signup_route', [c['kind'] for c in later.get('cards', [])])

    def test_model_can_show_prepared_guide_with_intro_and_existing_question(self):
        out = self.opening(mode='discuss', focus='enrollment', compose_override=self.draft('signup_route'))
        self.assertEqual(out['generated']['status'], 'complete')
        self.assertIn('guide can help you prepare', out['reply'])
        self.assertEqual(self.asked(out), 'RC04')
        self.assertIn('signup_route', [c['kind'] for c in out.get('cards', [])])
        self.assertTrue(self.flow.ux.shown(self.owner, self.flow.current_chain.get(self.owner),
                                         'signup_route:confirm_with_social_security'))
        self.assertEqual(out['metrics']['llmCalls'], 2)
        schema = self.calls[-1]['text']['format']['schema']
        self.assertIn('signup_route', schema['properties']['education']['properties']['visual']['enum'])

    def test_unprepared_guide_cannot_be_invented(self):
        out = self.opening(mode='work', focus='enrollment', compose_override=self.draft('signup_route'))
        self.assertNotIn('signup_route', self.composed_context()['discussion_plan']['software_cards'])
        self.assertNotIn('signup_route', [c['kind'] for c in out.get('cards', [])])
        self.assertNotIn('guide_presentation', self.composed_context()['discussion_plan'])


if __name__ == '__main__':
    unittest.main()
