"""Pilot-only notice: 2026 sample data only (owner direction, DQ-01, November 7, 2026)."""
from pathlib import Path
import sys
import tempfile
import time
import unittest
import uuid

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import test_natural_agent as fixtures
from chat import ModelUnavailable
from natural_agent import (COMPOSE_INSTRUCTIONS, PILOT_FIRST_REPLY_INSTRUCTION,
                           PILOT_SCOPE_INSTRUCTIONS, PILOT_SCOPE_NOTICE)


class PilotScopeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.NaturalAgentTests()
        self.fixture.setUp()
        self.agent = self.fixture.agent

    def compose(self, reply, owner='owner'):
        self.fixture.answer = self.fixture.composition(reply=reply)
        with self.agent.reserve_turn() as reservation:
            return self.agent.compose(owner, self.fixture.context, self.fixture.moves,
                                      str(uuid.uuid4()), reservation)

    def sent_instructions(self):
        return self.fixture.calls[-1]['instructions']

    def test_other_deployments_are_unchanged(self):
        self.compose('We can focus on the first steps.')
        self.assertEqual(self.sent_instructions(), COMPOSE_INSTRUCTIONS)

    def test_first_pilot_reply_is_asked_for_the_notice_once(self):
        self.agent.pilot_scope = True
        self.compose('This is a pilot, for 2026 sample data only. We can start with the first steps.')
        first = self.sent_instructions()
        self.assertTrue(first.startswith(COMPOSE_INSTRUCTIONS))
        self.assertIn(PILOT_SCOPE_INSTRUCTIONS, first)
        self.assertTrue(first.endswith(PILOT_FIRST_REPLY_INSTRUCTION))
        self.compose('We can focus on the first steps.')
        later = self.sent_instructions()
        self.assertIn(PILOT_SCOPE_INSTRUCTIONS, later)
        self.assertNotIn(PILOT_FIRST_REPLY_INSTRUCTION, later)

    def test_a_reply_that_omits_the_notice_is_followed_by_another_request(self):
        self.agent.pilot_scope = True
        self.compose('We can focus on the first steps.')
        self.compose('We can focus on the first steps.')
        self.assertTrue(self.sent_instructions().endswith(PILOT_FIRST_REPLY_INSTRUCTION))

    def test_each_visit_gets_its_own_notice(self):
        self.agent.pilot_scope = True
        self.compose('This is a pilot, for 2026 sample data only.', owner='visit-a')
        self.compose('We can focus on the first steps.', owner='visit-b')
        self.assertTrue(self.sent_instructions().endswith(PILOT_FIRST_REPLY_INSTRUCTION))

    def test_notice_facts_pass_literal_checks_only_in_the_pilot(self):
        with self.assertRaisesRegex(ModelUnavailable, 'date or amount outside its sources'):
            self.compose(PILOT_SCOPE_NOTICE)
        self.agent.pilot_scope = True
        for reply in (PILOT_SCOPE_NOTICE, 'This is a pilot, for 2026 sample data only.'):
            self.assertEqual(self.compose(reply)['reply'], reply)

    def test_pilot_does_not_loosen_amount_checks(self):
        self.agent.pilot_scope = True
        with self.assertRaisesRegex(ModelUnavailable, 'date or amount outside its sources'):
            # $20 is in the fixture's current_message and therefore echoable
            # (own-words grounding, Nov 9); an amount the person never said is not.
            self.compose('This is a pilot, for 2026 sample data only. A premium could be $37.')


class PilotServerWiringTests(unittest.TestCase):
    def test_only_the_pilot_server_turns_on_the_notice(self):
        import server
        from pilot_access import PilotAccess
        from pilot_budget import PilotBudget
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / 'pilot'
            PilotBudget.open(PilotAccess.initialize(state, ends_at=int(time.time()) + 86400),
                             initialize=True)
            pilot = server.build(0, fixture=True, pilot_state=state)
            ordinary = server.build(0, fixture=True, database=Path(tmp) / 'private/test.sqlite3')
            try:
                self.assertIs(pilot.adaptive.agent.pilot_scope, True)
                self.assertFalse(getattr(ordinary.adaptive.agent, 'pilot_scope', False))
            finally:
                pilot.server_close()
                ordinary.server_close()


if __name__ == '__main__':
    unittest.main()
