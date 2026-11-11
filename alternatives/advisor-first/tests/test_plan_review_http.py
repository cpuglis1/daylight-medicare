"""Real loopback HTTP only, fixture mode and disposable database."""
import copy
import unittest
import uuid

import test_http as support


class PlanReviewHttpTests(unittest.TestCase):
    setUpClass = classmethod(support.HttpTests.setUpClass.__func__)
    tearDownClass = classmethod(support.HttpTests.tearDownClass.__func__)
    request = support.HttpTests.request
    turn = support.HttpTests.turn

    def setUp(self):
        support.HttpTests.setUp(self)
        for identifier, fields in [
            ('T01', {'choice': 'compare'}), ('RC01', {'choice': 'self'}), ('T03', {'zip': '34102'}),
            ('RC03', {'year': '2026'}), ('T05', {'choice': 'original,drug'}), ('RC04', {'choice': 'both'}),
            ('T06', {'choice': 'none'}), ('T07', {'choice': 'no'}), ('T08', {'choice': 'local'}),
            ('T09', {'choice': 'predictable'}), ('T10', {'choice': 'total_cost'})]:
            self.turn({'type': 'choice', 'id': identifier, 'fields': fields})
        self.review = self.turn({'type': 'review_plans'})['review']
        self.handoff = self.turn({'type': 'confirm_plan_review', 'token': self.review['token']})['plansHandoff']

    def test_same_origin_current_receipt_uses_server_state(self):
        code, result = self.request('/api/plans/handoff', {'token': self.handoff['token']})
        self.assertEqual(code, 200)
        self.assertEqual(result['inputDigest'], self.handoff['inputDigest'])
        self.assertEqual(result['scope']['year'], 2026)
        self.assertFalse(result['personalRecommendationAllowed'])
        self.assertEqual(self.request('/api/plans/handoff', {'token': self.handoff['token'], 'profile': {}})[0], 422)
        self.assertEqual(self.server.adaptive.agent.calls, 0)

    def test_origin_csrf_foreign_owner_and_query_boundaries(self):
        body = {'token': self.handoff['token']}
        self.assertEqual(self.request('/api/plans/handoff', body, csrf=False)[0], 403)
        self.assertEqual(self.request('/api/plans/handoff', body, origin='https://example.com')[0], 403)
        self.assertEqual(self.request('/api/plans/handoff?token=not-permitted', body)[0], 422)
        self.cookie = None
        _, self.session = self.request('/api/guest/session')
        self.assertEqual(self.request('/api/plans/handoff', body)[0], 409)

    def test_correction_revokes_receipt_without_releasing_recommendations(self):
        self.turn({'type': 'choice', 'id': 'T10', 'fields': {'choice': 'doctors'}})
        self.assertEqual(self.request('/api/plans/handoff', {'token': self.handoff['token']})[0], 409)
        code, result = self.request('/api/recommendations', {'guide': self.state['guide'], 'record': self.state['record']})
        self.assertIn(code, {409, 503})


if __name__ == '__main__':
    unittest.main()
