"""Current doctor-entry HTTP lifecycle; fictional data and scripted AI only.

Controlled failures below test diagnostics/recovery, not the historical owner's
unreproduced incident. No real profile, runtime, ledger or model is used.
"""
import copy
import json
from pathlib import Path
import sys
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_provider_http as fixture
from chat import ModelUnavailable
from natural_flow import CONTEXT_POLICY


class ProviderIncidentRecoveryTests(fixture.ProviderHttpTests):
    def seed_to_provider_question(self):
        opening = 'I turn 65 in November and want Medicare soon.'
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
        self.message(location, [self.update('T03', {'zip': '34102'}, location)], 'T06')

    def provider_updates(self, text, *, detailed=True, reverse=False):
        updates = [self.update('T06', {'choice': 'list', 'text': 'dr charlie fiction'}, text)]
        if detailed:
            updates.append(self.update('RC21', {'choice': 'details',
                'practice': 'dr charlie fiction', 'city': 'naples'}, text, entity='new'))
        return list(reversed(updates)) if reverse else updates

    def submit_provider(self, *, detailed=True, reverse=False):
        self.seed_to_provider_question()
        text = 'My PCP is dr charlie fiction in naples'
        return self.message(text, self.provider_updates(text, detailed=detailed, reverse=reverse), 'T07')

    def payload(self, text):
        return {'guide': copy.deepcopy(self.state['guide']), 'record': copy.deepcopy(self.state['record']),
            'requestId': str(uuid.uuid4()), 'action': {'type': 'message', 'message': text},
            'aiConsent': True, 'contextPolicy': CONTEXT_POLICY,
            'continuation': self.state['continuation']}

    def queue_provider(self, text):
        self.extractions.append({'updates': self.provider_updates(text), 'requests': [], 'fact_ids': [],
            'agenda': {'concerns': [], 'priorityReason': {}},
            'situation_proposals': [], 'goal_quote': ''})
        self.targets.append('T07')

    def assert_report_and_holds(self, out):
        json.dumps(out, allow_nan=False)
        self.assertEqual(out['guide']['fields']['needs.providersStatus']['value'], 'list')
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T07')
        self.assertEqual(out['guide']['fields']['situation.age65']['value'], {'month': 11, 'year': None})
        self.assertEqual(out['record']['facts']['RC11']['value']['coverageEnd'], '2026-12')
        self.assertFalse(out['personalRecommendation'])
        self.assertNotIn('comparison', out['record'])

    def test_original_fictional_model_shape_t06_only_is_json_safe(self):
        out = self.submit_provider(detailed=False)
        self.assert_report_and_holds(out)
        self.assertEqual(out['guide']['fields']['needs.providers']['value'], 'dr charlie fiction')
        self.assertNotIn('RC21', out['record']['facts'])

    def test_current_lowercase_mixed_provider_proposals_are_json_safe(self):
        out = self.submit_provider()
        self.assert_report_and_holds(out)
        self.assertEqual(out['record']['facts']['RC21']['value']['items'], [
            {'entity': 'doctor-1', 'choice': 'details', 'practice': 'dr charlie fiction', 'city': 'naples'}])

    def test_reversed_provider_proposals_preserve_one_item(self):
        out = self.submit_provider(reverse=True)
        self.assert_report_and_holds(out)
        self.assertEqual(len(out['record']['facts']['RC21']['value']['items']), 1)

    def test_exact_http_replay_does_not_repeat_ai_or_provider_capture(self):
        self.seed_to_provider_question()
        text = 'My PCP is dr charlie fiction in naples'
        self.queue_provider(text)
        payload = self.payload(text)
        status, out = self.request('/api/conversation/turn', payload)
        self.assertEqual(status, 200)
        calls = len(self.calls)
        status, replay = self.request('/api/conversation/turn', payload)
        self.assertEqual(status, 200)
        self.assertEqual(len(self.calls), calls)
        self.assertEqual(out['guide'], replay['guide'])
        self.assertEqual(out['record'], replay['record'])
        self.assertEqual(out['continuation'], replay['continuation'])
        self.assert_report_and_holds(replay)

    def test_known_composition_unavailability_keeps_captured_provider_and_next_question(self):
        self.seed_to_provider_question()
        text = 'My PCP is dr charlie fiction in naples'
        self.queue_provider(text)
        with patch.object(self.service.adaptive.agent, 'validate_composition',
                          side_effect=ModelUnavailable('The response could not be checked.')):
            status, out = self.request('/api/conversation/turn', self.payload(text))
        self.assertEqual(status, 200)
        self.assertEqual(out['generated']['status'], 'unavailable')
        self.assert_report_and_holds(out)
        self.assertEqual(out['reply'], '')
        self.assertEqual(len(self.calls), 10)

    def test_controlled_unexpected_failure_is_value_free_and_exact_replay_recovers_capture(self):
        self.seed_to_provider_question()
        text = 'My PCP is dr charlie fiction in naples'
        self.queue_provider(text)
        payload = self.payload(text)
        # Deliberately injected after the existing resolved checkpoint. This is
        # not asserted to be the owner's exception or its historical location.
        with patch.object(self.service.adaptive, 'compose_response',
                          side_effect=RuntimeError('Private failure Canary-921735')):
            with self.assertLogs('natural_flow', level='ERROR') as logs:
                status, failed = self.request('/api/conversation/turn', payload)
        self.assertEqual(status, 500)
        self.assertEqual(set(failed), {'error'})
        self.assertIn('The service could not complete this request.', failed['error'])
        diagnostic = '\n'.join(logs.output)
        self.assertIn('code=unexpected_exception type=RuntimeError', diagnostic)
        self.assertRegex(diagnostic, r'natural_flow\.py:[0-9]+')
        for forbidden in ('Canary', '921735', 'charlie', 'naples', payload['requestId'], payload['continuation']):
            self.assertNotIn(forbidden, diagnostic)
            self.assertNotIn(forbidden, json.dumps(failed))
        calls = len(self.calls)
        self.assertEqual(calls, 9, 'Only the four earlier pairs and provider extraction were issued.')
        status, recovered = self.request('/api/conversation/turn', payload)
        self.assertEqual(status, 200)
        self.assertEqual(len(self.calls), calls, 'Recovery must not re-extract or recompose automatically.')
        self.assert_report_and_holds(recovered)
        self.assertEqual(len(recovered['record']['facts']['RC21']['value']['items']), 1)
        with self.service.budget.db() as db:
            statuses = [row[0] for row in db.execute(
                "SELECT status FROM ai_charges WHERE id NOT LIKE 'approved-smoke-%'")]
        self.assertEqual(statuses.count('settled'), 9)
        self.assertEqual(statuses.count('cancelled'), 1)
        self.assertEqual(statuses.count('held'), 0)

    def test_sensitive_provider_save_omission_and_explicit_roundtrip_are_separate(self):
        self.submit_provider()
        self.state['guide']['preferences'].update(saveGuide=True, saveSensitive=False)
        payload = {'guide': self.state['guide'], 'record': self.state['record'],
            'expectedVersion': 0, 'expectedReadinessVersion': 0, 'operationId': str(uuid.uuid4())}
        status, first = self.request('/api/conversation/save', payload)
        self.assertEqual(status, 200)
        _, safe_profile = self.request('/api/guest/profile')
        _, safe_readiness = self.request('/api/guest/readiness')
        self.assertNotIn('charlie', json.dumps([safe_profile, safe_readiness]).lower())
        self.assertNotIn('RC21', safe_readiness['record']['facts'])
        self.state['guide']['preferences']['saveSensitive'] = True
        payload.update(expectedVersion=first['version'], expectedReadinessVersion=first['readinessVersion'],
                       operationId=str(uuid.uuid4()))
        status, receipt = self.request('/api/conversation/save', payload)
        self.assertEqual(status, 200)
        _, saved = self.request('/api/guest/profile')
        _, readiness = self.request('/api/guest/readiness')
        status, resumed = self.request('/api/conversation/turn', {'guide': saved['guide'],
            'record': readiness['record'], 'requestId': str(uuid.uuid4()), 'action': {'type': 'refresh'}})
        self.assertEqual(status, 200)
        self.assertEqual(resumed['record']['facts']['RC21']['value']['items'][0]['city'], 'naples')
        self.assertEqual(len(self.calls), 10, 'Save/resume must not acquire AI permission or call the model.')
        self.assertNotIn('messages', saved['guide'])
        self.assertNotIn('comparison', readiness['record'])

