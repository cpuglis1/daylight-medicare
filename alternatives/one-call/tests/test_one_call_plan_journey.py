"""D214 full one-call visit with retained local evidence and no live models.

Starts from a fictional person's words through a scripted Responses transport,
then uses the real question/identity controls, signed HTTP visit, source readers,
calculator, review/handoff and plan-card endpoint. Source STOPs are simulated in
memory; the source ledger and persistent guest/budget stores are never changed.
"""
from contextlib import ExitStack
from datetime import date
from itertools import count
import getpass
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1])); import _paths  # noqa: E401,F401
sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = _paths.REPO
sys.path.insert(0, str(ROOT / 'infrastructure/daylight-data/src'))

from chat import ModelUnavailable, ResponsesClient
from natural_flow import CONTEXT_POLICY
import one_call_server
import _one_call_support as support
from _one_call_support import Script, message, reply, save, update
from test_one_call_server import ServerCase, loopback_only

from daylight_data.pilot_subset.store import repositories
from daylight_data.serving.binding import ResearchServingError
from daylight_data.serving.part_d_local import local_candidate
from daylight_data.serving.pilot_doctors import PilotDoctors

WORDS = ("It's for me. Compare my 2026 Medicare Advantage and Part D drug costs. I'm in 34102. "
         'I have Part A and Part B and no other insurance. I see Dr. Mark Josephson in Naples. '
         'I take Metformin 500 mg tablet, 30 tablets for 30 days, picked up at Publix in Naples FL 34102. '
         'I have no help paying for prescriptions. I stay local and want lower monthly payments.')
UPDATES = (
    update('RC01', {'choice': 'self'}, "It's for me"),
    update('T01', {'choice': 'compare'}, 'Compare my 2026 Medicare Advantage and Part D drug costs'),
    update('T03', {'zip': '34102'}, "I'm in 34102"),
    update('RC03', {'year': '2026'}, '2026'),
    update('RC04', {'choice': 'both'}, 'I have Part A and Part B'),
    update('T05', {'choice': 'none'}, 'no other insurance'),
    update('T06', {'text': 'Dr. Mark Josephson in Naples'}, 'I see Dr. Mark Josephson in Naples'),
    update('T07', {'text': 'Metformin'}, 'I take Metformin'),
    update('RC22', {'name': 'Metformin', 'strength': '500 mg', 'form': 'tablet'}, 'Metformin 500 mg tablet', entity='medicine-1'),
    update('RC23', {'quantity': '30 tablets', 'daysSupply': '30', 'pharmacy': 'Publix in Naples FL 34102', 'channel': 'retail'},
           '30 tablets for 30 days, picked up at Publix in Naples FL 34102', entity='medicine-1'),
    update('RC18', {'choice': 'none'}, 'no help paying for prescriptions'),
    update('T08', {'choice': 'local'}, 'I stay local'),
    update('T09', {'choice': 'lower_monthly'}, 'want lower monthly payments'),
)


@unittest.skipUnless((ROOT / 'infrastructure/daylight-data/.state/socket').exists(), 'Requires retained local PostgreSQL evidence')
class RetainedJourney(unittest.TestCase):
    request = ServerCase.request
    session = ServerCase.session
    send_turn = ServerCase.turn

    @classmethod
    def setUpClass(cls):
        cls.stack = cls.enterClassContext(ExitStack())
        cls.temp = Path(cls.stack.enter_context(tempfile.TemporaryDirectory(prefix='daylight-d214-journey-')))
        cls.drugs = local_candidate(ROOT)
        cls.doctors = PilotDoctors(cls.drugs.foundation)
        binding = json.loads(one_call_server.DEFAULT_BINDING.read_text())
        dsn = f'host={ROOT / "infrastructure/daylight-data/.state/socket"} port=55485 dbname={binding["database"]} user={getpass.getuser()}'
        cls.medigap, cls.pdp = repositories(one_call_server.DEFAULT_BINDING, dsn=dsn)
        cls.script = Script()
        cls.service = one_call_server.build_one_call(0, fixture=True,
            database=cls.temp / 'fictional.sqlite3',
            client=ResponsesClient(key='synthetic-offline-only', model='gpt-5.4', transport=cls.script),
            medigap_repository=cls.medigap, part_d_repository=cls.pdp, reconcile=False,
            conversation_checks=True, doctor_service=cls.doctors, prescription_service=cls.drugs)
        cls.stack.callback(one_call_server.close, cls.service)
        thread = threading.Thread(target=cls.service.serve_forever, daemon=True)
        thread.start(); cls.stack.callback(thread.join, 10); cls.stack.callback(cls.service.shutdown)
        cls.port = cls.service.server_port

    def setUp(self):
        loopback_only(self)
        # The replay sends consecutive answers faster than a visitor can read them.
        # Advance only the fixture HTTP arrival clock between requests.
        import guide_server
        clock = count(0, 30)
        self.enterContext(patch.object(guide_server, 'time', SimpleNamespace(monotonic=lambda: next(clock))))
        support.pin_today(self, date(2026, 11, 22))
        guard = patch('urllib.request.urlopen', side_effect=AssertionError('External HTTP forbidden'))
        guard.start(); self.addCleanup(guard.stop)
        self.ledger = support.temporary_ledger(self, self.service.adaptive.agent)
        self.auth, self.state = self.session(self.port)
        self.asked = []
        self.turn({'type': 'start'})

    def turn(self, action, *, consent=False):
        status, out = self.send_turn(self.port, self.auth, self.state, action,
                                     consent=consent, policy=CONTEXT_POLICY if consent else None)
        self.assertEqual(status, 200, out)
        target = out.get('conversationNext', {}).get('target')
        if target:
            self.asked.append(target)
        self.state = out
        return out

    def choice(self, identifier, **fields):
        return self.turn({'type': 'choice', 'id': identifier, 'fields': fields})

    def answer(self, value):
        q = self.state['conversationCheck']['question']
        return self.turn({'type': 'check_answer', 'token': q['token'], 'value': value})

    def plans(self):
        body = {'inputs': self.state['recommendationInputs'], 'continuation': self.state['continuation']}
        status, _, raw = self.request(self.port, 'POST', '/api/recommendation', body, self.auth)
        result = json.loads(raw)
        self.assertEqual(status, 200, result)
        return result

    def begin(self):
        self.script.add([save(*UPDATES)], [message(reply('I have saved those details.', question='What matters most?', target='T10'))])
        self.turn({'type': 'message', 'message': WORDS}, consent=True)
        self.assertEqual(self.state['guide']['fields']['needs.medicinesStatus']['value'], 'yes')
        self.assertEqual(self.state['conversationCheck']['question']['kind'], 'doctor')
        for _ in range(8):
            q = self.state['conversationCheck']['question']
            if q['kind'] != 'doctor':
                break
            if q['field'] == 'doctor_location':
                self.answer('Naples')
            elif q['field'] == 'doctor':
                choices = [c for c in q['choices'] if c['value'].startswith(('Wellcare:', 'NPI:'))]
                self.answer((choices or q['choices'])[0]['value'])
            elif q['field'] == 'office':
                choices = [c for c in q['choices'] if '311' in c['label'] and '306' in c['label']]
                self.answer((choices or q['choices'])[0]['value'])
            else:
                self.fail('Unexpected doctor question: ' + str(q))
        self.assertTrue(any(r['kind'] == 'doctor' and r.get('office_parts')
                            for r in self.state['conversationCheck']['results']))
        self.assertEqual(self.state['conversationCheck']['question']['field'], 'formulary_product')
        self.answer('861007')
        self.choice('MG_AGE', choice='65'); self.choice('MG_SEX', choice='Male')
        self.choice('MG_TOBACCO', choice='Non-Tobacco')

    def finish_cost(self):
        answers = {
            'quantity': 30, 'unit': 'tablet', 'days_supply': 30,
            'fills': 'December 1, 2026 / 1', 'outlet_zip': '34102',
            'channel': 'retail', 'period': '2026-12-01', 'assistance': 'none',
            'prior_spending': 'confirmed_zero',
        }
        for _ in range(18):
            q = self.state['conversationCheck']['question']
            if q is None:
                break
            if q['field'] == 'pharmacy':
                choices = [c for c in q['choices'] if '1841534534' in str(c['value'])]
                self.assertTrue(choices, q)
                self.answer(choices[0]['value'])
            elif q['field'] in answers:
                self.answer(answers[q['field']])
            else:
                self.fail('Unexpected prescription question: ' + str(q))
        self.assertIsNone(self.state['conversationCheck']['question'])
        self.assertTrue(any(r['kind'] == 'drug_comparison' for r in self.state['conversationCheck']['results']))

    def test_complete_words_to_sources_to_review_and_all_three_card_types(self):
        self.begin(); self.finish_cost()
        self.choice('T10', choice='total_cost')
        self.turn({'type': 'review_plans'})
        self.assertEqual(self.state['review']['kind'], 'plan_profile')
        self.turn({'type': 'confirm_plan_review', 'token': self.state['review']['token']})
        self.assertEqual(self.state['plansHandoff']['destination'], 'plans')
        result = self.plans()
        self.assertEqual(len(result['advantage']['plans']), 72)
        self.assertEqual(len(result['part_d']['plans']), 10)
        self.assertGreater(len(result['medigap']['plans']), 0)
        counts = {}
        for kind in ('advantage', 'medigap', 'part_d'):
            rows = [c for p in result[kind]['plans'].values() for c in p['card_checks']]
            counts[kind] = {key: sum(c['indicator'] == key for c in rows) for key in ('supported', 'warning', 'information')}
            self.assertTrue(all(c['indicator'] == 'warning' for c in rows if c['id'] == 'total_cost'))
            self.assertGreater(counts[kind]['supported'], 0)
        ma = [c for p in result['advantage']['plans'].values() for c in p['card_checks']]
        self.assertTrue(any(c['id'] == 'doctors' and c['indicator'] == 'supported' for c in ma))
        self.assertTrue(any(c['id'] == 'doctors' and c['indicator'] == 'warning' for c in ma))
        costs = [c for kind in ('advantage', 'part_d') for p in result[kind]['plans'].values()
                 for c in p['card_checks'] if c['id'] == 'drug_cost' and c['indicator'] == 'supported']
        self.assertTrue(costs)
        self.assertTrue(all(c['start'] == '2026-12-01' for c in costs))
        self.assertTrue(all('not total annual' in c['note'] for c in costs))
        self.assertFalse(result['plan_card_checks']['ranking_changed'])
        self.assertFalse(result['plan_card_checks']['total_cost_supported'])

    def test_office_spelling_dates_and_failed_final_composition_through_plans(self):
        def say(words, updates=(), **kwargs):
            if updates:
                self.script.add([save(*updates)])
            self.script.add([message(reply('Thank you.', **kwargs))])
            return self.turn({'type': 'message', 'message': words}, consent=True)

        birthday = 'I turn 65 on December 14'
        say("Hi. " + birthday + " and my Medicare card came last month. I'm in 34104. "
            "I'm on a budget and I'd love dental. Where do I start?", [
                update('RC01', {'choice': 'self'}, birthday),
                update('S_AGE65', {'month': '12'}, birthday),
                update('T03', {'zip': '34104'}, "I'm in 34104")],
            question='May I confirm a few details?', detail_step='invite')
        field = lambda key: self.state['guide']['fields'][key]['value']
        self.assertEqual(field('situation.age65'), {'month': 12, 'year': 2026, 'first_day': False})
        say('First, can I learn more about the two main routes?', question='What feels most uncertain?')
        say('I want to find coverage and keep my costs predictable.', [
            update('T01', {'choice': 'compare'}, 'I want to find coverage'),
            update('T09', {'choice': 'predictable'}, 'keep my costs predictable')],
            question='May I confirm a few details?', detail_step='invite')
        say('Yes, let’s go through those details.', detail_step='agree',
            question='Which Medicare parts do you have now?', target='RC04')
        parts = 'Part A and Part B both start December 1, 2026'
        say('My card says ' + parts + '.', [
            update(key, {'status': 'approved', 'month': '12', 'year': '2026'}, parts)
            for key in ('COV_PART_A', 'COV_PART_B')], question='What health insurance do you have now?', target='T05')
        for part in 'AB':
            self.assertEqual(field('enrollment.part' + part)['date'], '2026-12-01')
            self.assertEqual(field('enrollment.part' + part)['precision'], 'day')
        self.assertEqual(self.state['conversationNext'].get('target'), 'T05')
        say('I retired two years ago. I have a marketplace plan until Medicare starts. No job insurance.', [
            update('S_RETIREMENT', {'status': 'retired', 'when': 'two years ago'}, 'I retired two years ago'),
            update('T05', {'choice': 'marketplace'}, 'I have a marketplace plan until Medicare starts')],
            question='Are there doctors you want to keep?', target='T06')
        self.assertEqual(field('coverage.current'), ['marketplace'])
        doctor = 'Dr. Shannon Wise, at her office on Goodlette-Frank Road in Naples FL'
        say(doctor + '.', [
            update('T06', {'text': 'Dr. Shannon Wise'}, doctor),
            update('RC21', {'practice': 'her office on Goodlette-Frank Road', 'city': 'Naples'}, doctor, entity='new')],
            question='Which prescriptions should we include?', target='T07')
        self.assertEqual(field('needs.providers'), 'Dr. Shannon Wise')
        for step, label in [('doctor', 'shannon leigh wise'), ('office', '730 goodlette')]:
            q = self.state['conversationCheck']['question']
            self.assertEqual((q['field'], q['item']), (step, 'doctor-1'))
            self.answer(next(row['value'] for row in q['choices'] if label in row['label'].lower()))
        self.assertIsNone(self.state['conversationCheck']['question'])
        doc = next(row for row in self.state['conversationCheck']['results'] if row['kind'] == 'doctor')
        self.assertIn('730 GOODLETTE', doc['office_parts']['line'].upper())
        say('Lisinorpil', [update('T07', {'text': 'Lisinorpil'}, 'Lisinorpil')],
            question='Will you need routine care away from home?', target='T08')
        q = self.state['conversationCheck']['question']
        self.assertEqual((q['field'], q['item']), ('formulary_product', 'medicine-1'))
        self.assertIn('similar spelling', q['why'])
        self.assertFalse(any(row['key'] == 'formulary' for row in self.state['conversationCheck']['results']))
        label = 'LISINOPRIL 5 MG ORAL TABLET'
        self.answer(next(row['value'] for row in q['choices'] if row['label'].upper() == label))
        self.choice('T08', choice='local')
        say('Total cost matters most to me.', [update('T10', {'choice': 'total_cost'}, 'Total cost matters most')],
            question='What else matters to you?')
        self.assertEqual((self.state['assessment'].get('nextQuestion') or {}).get('id'), 'MG_SEX')
        self.turn({'type': 'choice', 'id': 'MG_SEX', 'fields': {'choice': 'Female'}}, consent=True)
        self.assertEqual(self.state['assessment']['nextQuestion']['id'], 'MG_TOBACCO')
        self.script.compositions.append(ModelUnavailable('offline composition unavailable'))
        self.turn({'type': 'choice', 'id': 'MG_TOBACCO', 'fields': {'choice': 'Non-Tobacco'}}, consent=True)
        self.assertFalse(self.script.compositions, 'The button must exercise the failing composer')
        self.assertEqual(self.state['generated']['status'], 'unavailable')
        self.assertFalse(self.state.get('notice') or self.state.get('reply'))
        self.assertEqual(self.state['conversationNext'], {'kind': 'action', 'action': 'plan_review'})
        self.assertEqual(field('medigap.tobaccoCategory'), 'Non-Tobacco')
        self.assertEqual(self.asked.count('T05'), 1)
        self.assertNotIn('MG_AGE', self.asked)
        self.assertEqual(self.state['medigapProfile']['age_basis'], 'birthday')
        self.assertEqual(self.state['medigapProfile']['inputs']['age'], 65)
        close = self.state['comparisonClose']
        self.assertTrue(close['show'])
        checked = next(row['value'] for row in close['learned'] if row['label'] == 'Checked')
        self.assertIn('SHANNON LEIGH WISE', checked.upper())
        self.assertIn(label, checked.upper())
        self.assertNotIn('her office', checked.lower())
        self.assertNotIn('start date', str(close['steps']).lower())
        self.assertIn('December 1, 2026', str(close['learned']))
        self.turn({'type': 'review_plans'})
        self.turn({'type': 'confirm_plan_review', 'token': self.state['review']['token']})
        self.assertEqual(self.state['plansHandoff']['destination'], 'plans')
        result = self.plans()
        for kind in ('advantage', 'medigap', 'part_d'):
            plans = result[kind]['plans']
            self.assertTrue(plans, kind)
            for plan in plans.values():
                checks = {item['id']: item for item in plan['card_checks']}
                self.assertIn('medicines', checks)
                if kind != 'part_d':
                    self.assertIn('doctors', checks)
        self.assertTrue(any(label in row['note'].upper() for p in result['part_d']['plans'].values()
                            for row in p['card_checks'] if row['id'] == 'medicines'))
        for plan in result['medigap']['plans'].values():
            doctor = next(row for row in plan['card_checks'] if row['id'] == 'doctors')
            self.assertIn('730 GOODLETTE', doctor['note'].upper())
            self.assertIn('2026-10-02', doctor['evidence_dates'])
            if doctor['outcome'] == 'SELECT network needs checking':
                self.assertEqual(doctor['indicator'], 'warning')

    def test_product_correction_withdraws_drug_checks_and_costs(self):
        self.begin(); self.finish_cost()
        self.turn({'type': 'check_edit', 'key': 'formulary', 'field': 'products'})
        result = self.plans()
        rows = [c for kind in ('advantage', 'part_d') for p in result[kind]['plans'].values() for c in p['card_checks']]
        self.assertFalse(any(c['id'] in {'medicines', 'drug_cost'} and c['indicator'] == 'supported' for c in rows))
        self.assertTrue(any(c['id'] == 'doctors' and c['indicator'] == 'supported' for c in rows))

    def test_source_withdrawal_removes_positive_findings_without_another_turn(self):
        self.begin(); self.finish_cost()
        with patch.object(self.drugs, '_scope', side_effect=ResearchServingError('PILOT_SOURCE_STOP')):
            result = self.plans()
            rows = [c for kind in ('advantage', 'part_d') for p in result[kind]['plans'].values() for c in p['card_checks']]
            self.assertFalse(any(c['id'] in {'medicines', 'pharmacy', 'drug_cost'} and c['indicator'] == 'supported' for c in rows))
        with patch.object(self.doctors, 'network_matrix', side_effect=ResearchServingError('PILOT_EVIDENCE_STALE')):
            result = self.plans()
            rows = [c for kind in ('advantage', 'medigap') for p in result[kind]['plans'].values() for c in p['card_checks']]
            self.assertFalse(any(c['id'] == 'doctors' and c['indicator'] == 'supported' for c in rows))


if __name__ == '__main__':
    unittest.main()
