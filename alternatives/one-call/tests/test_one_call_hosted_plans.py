"""Run against the retained hosted release plus the D222 patch; no real accounts."""
import functools
import importlib.util
import json
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _one_call_support as support
sys.path.insert(0, str(support.ADVISOR / 'tests'))
from test_one_call_plans_context import view
from types import SimpleNamespace

HOSTED = importlib.util.find_spec('hosted_server') is not None
if HOSTED:
    import test_hosted_history as base
    from hosted_server import build_hosted
    from chat import ResponsesClient


@unittest.skipUnless(HOSTED, 'Hosted adapter is in the retained release, not GitHub dev')
class HostedPlans(unittest.TestCase):
    if HOSTED:
        setUp, app, join = base.HostedTests.setUp, base.HostedTests.app, base.HostedTests.join

    def test_both_invitation_policies_compare_through_authenticated_http(self):
        for policy, tier in [('owner', 'default'), ('accelerator', 'ultrafast')]:
            with self.subTest(policy=policy):
                history = base.MemoryHistory()
                with patch.object(base, 'build_hosted', functools.partial(build_hosted, one_call=True, demo_policy=policy)):
                    app = self.app(history)
                script = support.Script()
                text = 'Cedar Example HMO has a $17.00 monthly premium; Willow Example HMO has a $29.00 monthly premium. Published terms are shown for review; Part B premiums are separate.'
                script.add([support.message(support.reply({'text': text, 'fact_ids': ['fictional-a:premium', 'fictional-b:premium']}))])
                def transport(payload):
                    result = script(payload)
                    result.update(model='gpt-6.1-sol', service_tier=tier)
                    return result
                flow = app.adaptive
                agent = flow.agent
                agent.client = ResponsesClient(key='fictional-offline', model='gpt-6.1-sol', transport=transport)
                agent.client.service_tier = tier
                agent.enabled = True
                agent.count_tokens = lambda *_: 300
                flow.fixture = False
                flow.model_agents = {'gpt-6.1-sol': agent}
                flow.reconciler.enabled = False
                app.hosted_budget.clock = self.budget.clock
                catalog = view()
                flow.plans_service = SimpleNamespace(for_handoff=lambda *_: catalog, projection=lambda: (catalog, None),
                    decision_evidence_digest=lambda _: catalog['decision_evidence_digest'])
                cookies, csrf = self.join(app)
                _, raw, _ = base.request(app, '/api/conversation/initial', cookies=cookies)
                initial = json.loads(raw)
                payload = {k: initial[k] for k in ('guide', 'record', 'continuation') if k in initial}
                payload.update(requestId='fictional-plans-' + policy, aiConsent=True, contextPolicy=support.CONTEXT_POLICY,
                    action={'type': 'message', 'message': 'Tell me the key difference between these two plans.'},
                    plansContextPolicy='plans-context-v1', plansContext={
                        'version': 'plans-context-v1', 'reviewToken': None, 'viewDigest': catalog['view_digest'],
                        'visibleIds': ['fictional-a', 'fictional-b'], 'comparedIds': ['fictional-a', 'fictional-b'],
                        'selectedId': None, 'field': None, 'mode': 'compare', 'navigation': 'advantage'})
                with patch.object(socket.socket, 'connect', side_effect=AssertionError('No network')):
                    code, raw, _ = base.request(app, '/api/conversation/turn', payload, cookies, csrf)
                self.assertEqual(code, 200, raw)
                self.assertEqual(json.loads(raw)['reply'], text)
                self.assertEqual(len(script.sent), 1)
                self.assertEqual(script.sent[0]['service_tier'], tier)
                self.assertEqual(script.sent[0]['reasoning']['effort'], 'low')
                self.assertTrue(any(row['status'] == 'response_ready' for row in history.rows.values()))
                self.assertNotEqual(base.request(app, '/api/conversation/turn', payload)[0], 200)
                self.assertIs(agent.budget, app.hosted_budget)


if __name__ == '__main__': unittest.main()
