"""AI-07 acceptance: the model proposes, software checks, then the reply is composed.

Done-when (Engine & AI tracker): every model interpretation passes a schema and
rule check before any output; rejected proposals route to clarification or a
safe failure. Each test names the clause it pins. Offline only: the scripted
Responses transport from test_natural_flow, fictional text, no provider calls.
"""
import ast
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import test_natural_flow as flow_fixtures
from advisor_flow import fingerprint
from chat import ModelUnavailable

TEXT = 'My current health insurance is through my current job.'
NEUTRAL_REPLY = 'We can work through the next useful detail together.'


class Harness(unittest.TestCase):
    def setUp(self):
        self.f = flow_fixtures.NaturalFlowTests()
        self.f.setUp()
        # Negative composition tests must not be rescued by the fixture's
        # convenience follow-up question.
        self.f.supply_fixture_followup = False

    def employer_report(self):
        return [self.f.update('T05', {'choice': 'employer'}, TEXT)]


class InterpretationIsCheckedBeforeUse(Harness):
    """Stage one: the model's reading of the message is a proposal only."""

    def test_malformed_interpretation_changes_nothing_and_never_reaches_composition(self):
        before = fingerprint(self.f.g, self.f.r)
        self.f.extractions.append({'unexpected': 'shape'})
        with self.assertRaises(ModelUnavailable):
            self.f.turn({'type': 'message', 'message': TEXT})
        self.assertEqual(fingerprint(self.f.g, self.f.r), before)
        self.assertEqual(self.f.stage_payloads('daylight_resolved_conversation'), [])

    def test_report_without_a_supporting_quote_is_never_recorded(self):
        unsupported = self.f.update('T05', {'choice': 'retiree'}, 'coverage from my old employer')
        self.f.message(TEXT, [unsupported])
        self.assertNotIn('coverage.current', self.f.g['fields'])
        reported = {item['id'] for item in self.f.composed_context()['reports']}
        self.assertNotIn('guide.coverage.current', reported)

    def test_uncertain_report_becomes_a_required_clarification_not_a_fact(self):
        text = 'I think my health insurance is through my job, maybe.'
        out = self.f.message(text, [self.f.update('T05', {'choice': 'employer'}, text, uncertain=True)])
        self.assertNotIn('coverage.current', self.f.g['fields'])
        self.assertIn({'id': 'T05', 'status': 'needs_clarification'}, self.f.composed_context()['uncertainties'])
        candidates = self.f.stage_payloads('daylight_resolved_conversation')[-1]['question_candidates']
        self.assertEqual([(item['id'], item.get('required')) for item in candidates], [('T05', True)])
        self.assertEqual(out['generated']['move'], 'T05')


class ReplyIsCheckedBeforeAnyOutput(Harness):
    """Stage two: a composed reply reaches the person only after its checks pass."""

    CASES = {
        'unsupported personal finding': ({'reply': 'You are eligible for a Special Enrollment Period when that job ends.'},
                                         'eligible for a Special'),
        'personal cost claim': ({'reply': 'Your premium will be $412 a month.'}, '412'),
        'amount outside the sources': ({'reply': 'Plans in this area often cost about $412 a month.'}, '412'),
        'claimed research': ({'reply': "I've checked the plans and doctors near you for this."}, 'checked the plans'),
        'unknown evidence': ({'reply': NEUTRAL_REPLY, 'evidence_refs': ['fabricated-source']}, 'fabricated'),
        'unknown report': ({'reply': NEUTRAL_REPLY, 'report_refs': ['fabricated-report']}, 'fabricated'),
        'unapproved question': ({'reply': NEUTRAL_REPLY, 'question_target': 'NOT-APPROVED'}, 'NOT-APPROVED'),
    }
    # Nov 8–9, 2026 (owner exception to D88): a rejected reply is replaced by one
    # reviewed statement plus the approved question, never by silence. The
    # rejected words themselves still never reach the output.

    def reviewed_floor(self, out):
        statements = {fact['summary'] for fact in self.f.flow.facts.values() if fact.get('summary')}
        statements |= {'Let’s keep going with the next useful detail.', 'Let’s keep going. You can ask me anything about your coverage.'}
        body = out['reply'].split('\n\n')[0]
        self.assertIn(body, statements, out['reply'])
        self.assertTrue(out['assessment']['nextQuestion'] or out['reply'].rstrip().endswith('?'))

    def test_rejected_reply_is_never_shown_and_accepted_facts_survive(self):
        for name, (compose, marker) in self.CASES.items():
            with self.subTest(name):
                self.setUp()
                out = self.f.message(TEXT, self.employer_report(), compose=compose)
                self.assertEqual(out['generated']['status'], 'unavailable')
                self.assertFalse(out['generated']['retryable'])
                self.reviewed_floor(out)
                self.assertNotIn(marker, json.dumps(out))
                self.assertEqual(self.f.flow.value(self.f.g, 'coverage.current'), ['employer'])
                # Without the production repair slot there is no second request.
                self.assertEqual(len(self.f.calls), 2)

    def test_sound_reply_without_a_question_keeps_the_reply_and_asks_the_continuation(self):
        # Nov 9, 2026: a correct answer is not discarded for a missing question;
        # the educational continuation is appended instead (P08 T6).
        out = self.f.message(TEXT, self.employer_report(), compose={'reply': 'Noted.', 'question_target': None, 'question': ''})
        self.assertEqual(out['generated']['status'], 'complete')
        self.assertTrue(out['reply'].startswith('Noted.'))
        self.assertTrue(out['reply'].rstrip().endswith('What would you like to understand next?'))
        self.assertEqual(out['generated']['validation_recovery']['reason'], 'missing_followup')
        self.assertEqual(len(self.f.calls), 2)

    def test_production_repair_slot_is_used_once_and_only_checked_parts_are_shown(self):
        agent = self.f.flow.agent
        agent.composition_recovery, agent.connection_retries = True, 1
        self.f.compositions.append({'reply': 'Your premium will be $412 a month.'})
        out = self.f.message(TEXT, self.employer_report(), compose={'reply': 'Your deductible is $900.'})
        self.assertEqual([call['text']['format']['name'] for call in self.f.calls],
                         ['daylight_guide_commands', 'daylight_resolved_conversation',
                          'daylight_resolved_conversation'])
        blob = json.dumps(out)
        self.assertNotIn('412', blob)
        self.assertNotIn('900', blob)
        self.reviewed_floor(out)
        if out['generated']['status'] == 'complete':
            # Only the independently validated canonical question survives.
            self.assertEqual(out['generated']['validation_recovery']['replacement'],
                             'independently_validated_component')
        else:
            self.assertEqual(out['generated']['status'], 'unavailable')

    def test_checked_reply_is_shown(self):
        out = self.f.message(TEXT, self.employer_report(), compose={'reply': NEUTRAL_REPLY})
        self.assertEqual(out['generated']['status'], 'complete')
        self.assertEqual(out['reply'], NEUTRAL_REPLY)


class NothingStreamsBeforeTheChecks(unittest.TestCase):
    def test_only_fixed_status_events_are_emitted_while_a_model_call_runs(self):
        for name in ('narrative_agent.py', 'natural_agent.py', 'natural_flow.py'):
            tree = ast.parse((HERE / name).read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'emit':
                    with self.subTest(file=name, line=node.lineno):
                        self.assertEqual(len(node.args), 2)
                        kind, data = node.args
                        self.assertIsInstance(kind, ast.Constant)
                        self.assertEqual(kind.value, 'status')
                        # The payload is a fixed message, never model text.
                        self.assertIsInstance(data, ast.Dict)
                        self.assertTrue(all(isinstance(value, ast.Constant) for value in data.values))


if __name__ == '__main__':
    unittest.main()
