"""D222: deliberate Plans Send and confirmed-office reuse, with no network/model."""
import copy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_one_call_flow import FlowCase
from _one_call_support import message, reply, save, update
import _one_call_support as support
from guest_profiles import ProfileError


def view():
    def plan(key, name, premium):
        return {'id': key, 'name': name, 'type': 'HMO', 'identity_state': 'reference', 'fields': {
            'premium': {'label': 'Monthly premium', 'state': 'reference', 'value': premium,
                        'conditions': ['Part B premium is separate.'], 'reason_codes': [], 'evidence_ref': key + ':premium'},
            'dental': {'label': 'Dental allowance', 'state': 'held', 'value': None,
                       'conditions': [], 'reason_codes': ['SOURCE_HELD'], 'evidence_ref': key + ':dental'}}}
    return {'view_digest': 'fictional-view', 'catalog_sha256': 'fictional-catalog',
            'projection_digest': 'fictional-projection', 'decision_evidence_digest': 'fictional-evidence',
            'publication': {}, 'scope': {'year': 2026, 'county_fips': '12021'},
            'recommendation': {'scope_supported': True, 'state': 'held', 'top_three': [],
                               'priority_order': [], 'reason_codes': ['METHOD_HELD']},
            'plans': [plan('fictional-a', 'Cedar Example HMO', '$17.00'),
                      plan('fictional-b', 'Willow Example HMO', '$29.00')]}


class PlansSend(FlowCase):
    def setUp(self):
        super().setUp()
        self.view = view()
        self.flow.plans_service = SimpleNamespace(for_handoff=lambda owner, handoff: copy.deepcopy(self.view),
            projection=lambda: (copy.deepcopy(self.view), None),
            decision_evidence_digest=lambda digest: self.view['decision_evidence_digest'])

    def payload(self):
        return {**self.visit.payload({'type': 'message', 'message': 'Tell me the key difference between these two plans.'}),
                'plansContextPolicy': 'plans-context-v1', 'plansContext': {
                    'version': 'plans-context-v1', 'reviewToken': None, 'viewDigest': self.view['view_digest'],
                    'visibleIds': ['fictional-a', 'fictional-b'], 'comparedIds': ['fictional-a', 'fictional-b'],
                    'selectedId': None, 'field': None, 'mode': 'compare', 'navigation': 'advantage'}}

    def test_selected_published_fields_reach_model_and_reply_validator(self):
        text = ('Cedar Example HMO has a $17.00 monthly premium; Willow Example HMO has a $29.00 monthly premium. '
                'These are published terms shown for review; Part B premiums are separate. Dental details remain unavailable.')
        self.script.add([message(reply({'text': text, 'fact_ids': ['fictional-a:premium', 'fictional-b:premium']}))])
        out = self.flow.turn(self.visit.owner, self.payload())
        sent = self.script.inputs()[0]
        self.assertEqual(sent['plans_context']['compared_ids'], ['fictional-a', 'fictional-b'])
        self.assertEqual(sent['plans_context']['plans'][0]['fields']['premium']['value'], '$17.00')
        self.assertIsNone(sent['plans_context']['plans'][0]['fields']['dental']['value'])
        self.assertEqual(out['reply'], text)
        self.assertFalse(out['metrics']['oneCall']['fallback'])
        self.assertEqual(len(self.script.sent), 1)
        self.assertEqual({row['id'] for row in out['planEvidence']}, {'fictional-a:premium', 'fictional-b:premium'})
        self.assertIsNone(self.flow._plans_context.get())

    def test_no_context_is_carried_to_an_unrelated_send(self):
        self.script.add([message(reply('Let us compare the published terms.'))])
        self.flow.turn(self.visit.owner, self.payload())
        # A separate visitor has neither the selection nor permission for it.
        other = support.Visit(self, self.flow, self.script)
        other.start()
        other.say('What can you help with?', [message(reply('I can help explain Medicare.'))])
        self.assertIsNone(self.script.inputs()[-1].get('plans_context'))

    def test_invalid_or_unconsented_context_never_calls_model(self):
        for change in ('consent', 'stale', 'invented'):
            with self.subTest(change=change):
                payload = self.payload()
                if change == 'consent': payload['aiConsent'] = False
                elif change == 'stale': payload['plansContext']['viewDigest'] = 'old'
                else: payload['plansContext']['comparedIds'] = ['made-up']
                with self.assertRaises(ProfileError): self.flow.turn(self.visit.owner, payload)
        self.assertEqual(self.script.sent, [])

    def test_medigap_and_part_d_selections_are_rehydrated_from_current_server_rows(self):
        import plans_fixes
        plans_fixes.enable(self.flow)
        for navigation, product in [('supplement', 'medigap'), ('part-d', 'part_d')]:
            with self.subTest(navigation=navigation):
                row = {'id': 'fictional-selected', 'company': 'Example Insurance', 'variant': 'G',
                       'monthly_cents': 17300, 'name': 'Example Drug Plan', 'fields': {
                           'total_premium': {'state': 'published', 'value': 2900, 'value_encoding': 'integer_cents'}}}
                self.flow.plans_selection_read = lambda kind, guide, record: [row] if kind == product else []
                payload = self.payload()
                payload['plansContext'].update(navigation=navigation, comparedIds=[], visibleIds=[],
                                               mode='all', selection=['fictional-selected'])
                self.script.add([message(reply('We can discuss the listed premium.'))])
                out = self.flow.turn(self.visit.owner, payload)
                self.visit.guide, self.visit.record, self.visit.continuation = out['guide'], out['record'], out['continuation']
                sent = self.script.inputs()[-1]
                self.assertEqual(sent['plans_context']['compared_ids'], ['fictional-selected'])
                field = next(iter(sent['plans_context']['plans'][0]['fields'].values()))
                self.assertEqual(field['value'], '$173.00' if product == 'medigap' else '$29.00')


class ConfirmedOffice(FlowCase):
    def test_next_question_receives_the_office_already_selected_in_chat(self):
        self.assertTrue(support.attach_fictional_checks(self.flow))
        self.visit.say("It's for me. I'm in 34102 and want to find coverage.",
                       [save(update('RC01', {'choice': 'self'}, "It's for me"),
                             update('T03', {'zip': '34102'}, "I'm in 34102"),
                             update('T01', {'choice': 'compare'}, 'want to find coverage'))],
                       [message(reply('Thank you.'))])
        out = self.visit.say('I see Dr. Nera Vale in Naples.',
                             [save(update('T06', {'text': 'Dr. Nera Vale in Naples'}, 'Dr. Nera Vale in Naples'))],
                             [message(reply('I have noted the doctor.'))])
        question = out['conversationCheck']['question']
        self.visit.tap({'type': 'check_answer', 'token': question['token'], 'value': 'Nera0'})
        self.visit.say('What is still open for my doctor?', [message(reply('We have your selected office.'))])
        current = self.script.inputs()[-1]['research_context']
        result = current['results'][0]
        self.assertEqual(result['name'], 'Dr. Nera Vale')
        self.assertIn('1 Test Lane', str(result['office_parts']))
        self.assertTrue(result['identity_confirmed'])
        self.assertNotIn('candidate_id', str(current))
        self.assertNotIn('choices', current)
        # A withdrawn source removes the finding, not the person's exact selection.
        from daylight_data.serving.binding import ResearchServingError
        with patch.object(self.flow.conversation_checks.doctors, 'network_matrix',
                          side_effect=ResearchServingError('PILOT_SOURCE_WITHDRAWN')):
            self.visit.say('What about this office now?', [message(reply('Your office selection is retained.'))])
        held = self.script.inputs()[-1]['research_context']
        self.assertEqual(held['results'], [])
        self.assertEqual(held['confirmed_doctors'], current['confirmed_doctors'])
        self.assertEqual(held['pending']['field'], 'doctor_retry')
        # A correction to another identity must not carry the old office forward.
        self.visit.say('Actually I see Dr. Tomas Reed, not Dr. Nera Vale.',
                       [save(update('T06', {'text': 'Dr. Tomas Reed'}, 'Dr. Tomas Reed', correction=True))],
                       [message(reply('I have noted the correction.'))])
        self.visit.say('What office are we using?', [message(reply('Please choose the correct office.'))])
        self.assertNotIn('Nera Vale', str(self.script.inputs()[-1]['research_context']))


if __name__ == '__main__': unittest.main()
