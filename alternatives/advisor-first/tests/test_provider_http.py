"""Provider capture through real HTTP, fake Responses, and a disposable ledger.

This exercises the service/budget/serialization boundary omitted by direct
controller fixtures. It uses no API network access or existing customer records.
"""
import copy
from datetime import datetime
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import uuid

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import server as advisor_server  # Registers pinned engine imports; no live build.
from advisor_budget import AdvisorDailyBudget
from chat import ResponsesClient
from natural_flow import CONTEXT_POLICY


class ProviderHttpTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='daylight-provider-http-')
        self.addCleanup(self.temporary.cleanup)
        temporary = Path(self.temporary.name)
        self.calls, self.counted, self.extractions, self.targets = [], [], [], []
        self.service = advisor_server.make_server(
            0, database=temporary/'profiles.sqlite3', budget_database=temporary/'budget.sqlite3',
            web=HERE/'web',
            client=ResponsesClient(key='synthetic', model='gpt-5.4', transport=self.transport),
            enable_live=True, live_limit=None, count_tokens=self.count_tokens,
            cookie_namespace='daylight_test_provider_http',
            ui_config={'mockAI': False, 'advisorFirst': True, 'variant': 'D86'},
            conversation_class=advisor_server.ChatConversation,
            profile_gate_class=advisor_server.ProfileReadiness,
            adaptive_class=advisor_server.NaturalConversation)
        budget = AdvisorDailyBudget.adopt(self.service.budget, policy_path=HERE/'budget-policy.json')
        # Fake transport + disposable ledger: anchor this fixture to its reviewed
        # pricing date. Never extend production pricing approval to keep CI green.
        verified_at = datetime.fromisoformat(budget.rates['verified_at']).timestamp()
        budget.clock = lambda: verified_at
        self.assertEqual(Path(self.service.budget.path).resolve(), (temporary/'budget.sqlite3').resolve())
        self.thread = threading.Thread(target=self.service.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_service)
        self.cookie = None
        status, self.session = self.request('/api/guest/session')
        self.assertEqual(status, 200)
        status, self.state = self.request('/api/conversation/initial')
        self.assertEqual(status, 200)

    def close_service(self):
        self.service.shutdown()
        self.service.server_close()
        self.thread.join()

    def count_tokens(self, _client, payload):
        self.counted.append(payload['text']['format']['name'])
        return 1000

    def transport(self, payload):
        self.calls.append(copy.deepcopy(payload))
        name = payload['text']['format']['name']
        if name == 'daylight_guide_commands':
            self.assertTrue(self.extractions, 'Unexpected interpretation call')
            value = self.extractions.pop(0)
            value.setdefault('education_request', {'kind': 'none', 'concept_ids': [], 'quote': ''})
        elif name == 'daylight_resolved_conversation':
            self.assertTrue(self.targets, 'Unexpected advisor call')
            target = self.targets.pop(0)
            sent = json.loads(payload['input'][0]['content'])
            candidate = next((item for item in sent['question_candidates'] if item['id'] == target), None)
            self.assertIsNotNone(candidate, 'The scripted advisor target must be service-approved')
            value = {'question_target': target,
                'reply': 'We can work through the next useful detail together.',
                'question': candidate['question']['question'],
                'report_refs': [], 'evidence_refs': [],
                'education': {'purpose': 'advance', 'updates': [], 'visual': 'none'},
                'agenda_update': {'current_concern': 'coverage options', 'pause': False}}
        else:
            self.fail('Unexpected model contract: ' + name)
        return {'status': 'completed', 'model': 'gpt-5.4', 'service_tier': 'default',
            'usage': {'input_tokens': 300, 'output_tokens': 70, 'total_tokens': 370,
                      'input_tokens_details': {'cached_tokens': 0}},
            'output': [{'content': [{'type': 'output_text', 'text': json.dumps(value)}]}]}

    def request(self, path, payload=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.service.server_port, timeout=10)
        headers = {'Origin': f'http://127.0.0.1:{self.service.server_port}'}
        if self.cookie:
            headers['Cookie'] = self.cookie
        if payload is not None:
            headers.update({'Content-Type': 'application/json', 'X-Daylight-CSRF': self.session['csrf']})
        connection.request('POST' if payload is not None else 'GET', path,
                           json.dumps(payload) if payload is not None else None, headers)
        result = connection.getresponse()
        cookie = result.getheader('Set-Cookie')
        if cookie:
            self.cookie = cookie.split(';')[0]
        value = json.loads(result.read())
        status = result.status
        connection.close()
        return status, value

    @staticmethod
    def update(identifier, fields, quote, entity='profile'):
        return {'id': identifier, 'entity': entity,
            'fields': [{'key': key, 'value': value} for key, value in fields.items()],
            'quote': quote, 'scope': 'current', 'subject': 'beneficiary',
            'uncertain': False, 'correction': False}

    def message(self, text, updates, target, *, situations=()):
        self.extractions.append({'updates': updates, 'requests': [], 'fact_ids': [],
            'agenda': {'concerns': [], 'priorityReason': {}},
            'situation_proposals': list(situations), 'goal_quote': ''})
        self.targets.append(target)
        payload = {'guide': copy.deepcopy(self.state['guide']), 'record': copy.deepcopy(self.state['record']),
            'requestId': str(uuid.uuid4()), 'action': {'type': 'message', 'message': text},
            'aiConsent': True, 'contextPolicy': CONTEXT_POLICY}
        if self.state.get('continuation'):
            payload['continuation'] = self.state['continuation']
        status, out = self.request('/api/conversation/turn', payload)
        self.assertEqual(status, 200, out)
        self.assertEqual(out['generated'], {'status': 'complete', 'move': target})
        self.state = out
        return out

    def test_pcp_capture_after_cobra_timing_and_naples_returns_complete_json(self):
        opening = 'I am turning 65 years old in November and want to enroll in Medicare soon.'
        self.message(opening, [self.update('RC01', {'choice': 'self'}, opening)], 'T05',
            situations=[{'kind': 'age65', 'subject': 'beneficiary', 'scope': 'intended',
                'quote': opening, 'uncertain': False, 'correction': False,
                'month': 11, 'year': None, 'status': '', 'when': ''}])
        insurance = 'I have COBRA health insurance.'
        self.message(insurance, [self.update('T05', {'choice': 'cobra'}, insurance),
                                self.update('RC09', {'choice': 'cobra'}, insurance)], 'T03')
        end = 'My COBRA coverage ends in December 2026.'
        self.message(end, [self.update('RC11', {'coverageEnd': 'December 2026'}, end)], 'T03')
        location = 'I live in Naples, ZIP 34102.'
        before = self.message(location, [self.update('T03', {'zip': '34102'}, 'ZIP 34102.')], 'T06')
        self.assertEqual(before['assessment']['nextQuestion']['id'], 'T06')

        pcp = 'My primary care doctor is Dr Example Person at Example Primary Care in Naples.'
        after = self.message(pcp, [
            self.update('T06', {'text': 'Dr Example Person'}, pcp),
            self.update('RC21', {'practice': 'Example Primary Care', 'city': 'Naples'}, pcp, entity='new')], 'T07')
        # Both decoded HTTP output and strict JSON re-encoding must work after
        # provider capture, comparison derivation and response composition.
        json.dumps(after, allow_nan=False)
        fields = after['guide']['fields']
        self.assertEqual(fields['needs.providersStatus']['value'], 'list')
        # The retained engine rebuilds the baseline provider summary from its
        # structured RC21 practice list when those details are supplied.
        self.assertEqual(fields['needs.providers']['value'], 'Example Primary Care')
        self.assertEqual(fields['situation.age65']['value'], {'month': 11, 'year': None})
        self.assertEqual(fields['coverage.current']['value'], ['cobra'])
        self.assertEqual(fields['comparison.scope.zip']['value'], '34102')
        self.assertEqual(after['record']['facts']['RC11']['value']['coverageEnd'], '2026-12')
        self.assertEqual(after['record']['facts']['RC21']['value']['items'][0],
            {'entity': 'doctor-1', 'choice': 'details', 'practice': 'Example Primary Care', 'city': 'Naples'})
        self.assertFalse(after['personalRecommendation'])
        self.assertIn('comparison', after)
        self.assertNotIn('comparison', after['record'])
        expected = ['daylight_guide_commands', 'daylight_resolved_conversation'] * 5
        self.assertEqual([call['text']['format']['name'] for call in self.calls], expected)
        self.assertEqual(self.counted, expected)
        self.assertEqual(self.extractions, [])
        self.assertEqual(self.targets, [])
        # Settlement is checked against this disposable ledger, not real usage.
        with self.service.budget.db() as db:
            rows = db.execute("SELECT status FROM ai_charges WHERE id NOT LIKE 'approved-smoke-%'").fetchall()
        self.assertEqual(rows, [('settled',)] * 10)


if __name__ == '__main__':
    unittest.main()
