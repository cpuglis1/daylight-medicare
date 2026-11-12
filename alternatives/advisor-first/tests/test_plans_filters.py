"""D97: Plans-page filters submit free structured answers labelled plans_filter.

Deterministic harness only; no paid calls.
"""
import unittest

import test_http as support  # noqa: F401  (shared path setup)
from test_comparison_chat import CurrentChatHarness
from guest_profiles import ProfileError

REPORTS = [('T01', {'choice': 'compare'}), ('RC01', {'choice': 'self'}), ('T03', {'zip': '34102'}),
    ('RC03', {'year': '2026'}), ('T05', {'choice': 'original,drug'}), ('RC04', {'choice': 'both'}),
    ('T06', {'text': 'Dr. Canary Example'}), ('T07', {'text': 'Examplezine 10 mg'}), ('T08', {'choice': 'local'}),
    ('T09', {'choice': 'predictable'}), ('T10', {'choice': 'total_cost'})]


class PlansFilterAnswers(unittest.TestCase):
    def setUp(self):
        self.h = CurrentChatHarness()

    def filter(self, identifier, **fields):
        return self.h.turn({'type': 'choice', 'id': identifier, 'fields': fields, 'source': 'plans_filter'},
                           aiConsent=False, contextPolicy=None)

    def test_filter_answer_is_a_free_report_labelled_plans_filter(self):
        self.h.choice('T01', choice='compare')
        before = len(self.h.calls)
        self.filter('T06', text='Dr. Canary Example')
        self.assertEqual(len(self.h.calls), before)
        self.assertEqual(self.h.g['fields']['needs.providers']['value'], 'Dr. Canary Example')
        provenance = self.h.r['natural']['provenance']
        self.assertEqual(provenance['guide.needs.providers']['method'], 'plans_filter')
        self.assertEqual(provenance['guide.needs.providers']['status'], 'user_reported')

    def test_filter_answers_alone_reach_the_plan_review_checkpoint(self):
        for identifier, fields in REPORTS:
            out = self.filter(identifier, **fields)
        self.assertTrue(out['planReadiness']['canReview'], out['planReadiness']['missing'])
        review = self.h.turn({'type': 'review_plans'}, aiConsent=False)['review']
        self.assertTrue(review['token'])

    def test_conversation_sees_the_filter_label(self):
        self.h.choice('T01', choice='compare')
        self.filter('T03', zip='34102')
        self.h.message('What should I look at next?')
        reports = {r['id']: r for r in self.h.composed_context()['reports']}
        self.assertEqual(reports['guide.comparison.scope.zip']['provenance']['method'], 'plans_filter')

    def test_label_is_refused_outside_its_narrow_shape(self):
        self.h.choice('T01', choice='compare')
        before = len(self.h.calls)
        bad = [({'type': 'choice', 'id': 'T06', 'fields': {'text': 'Dr. A'}, 'source': 'conversation'}, {}),
               ({'type': 'choice', 'id': 'RC22', 'fields': {'name': 'x'}, 'source': 'plans_filter'}, {}),
               ({'type': 'message', 'message': 'hi', 'source': 'plans_filter'}, {}),
               ({'type': 'choice', 'id': 'T06', 'fields': {'text': 'Dr. A'}, 'source': 'plans_filter'}, {'aiConsent': True})]
        for action, extra in bad:
            with self.assertRaises(ProfileError):
                self.h.take(self.h.payload(action, **({'aiConsent': False, 'contextPolicy': None} | extra)))
        self.assertEqual(len(self.h.calls), before)


if __name__ == '__main__':
    unittest.main()
