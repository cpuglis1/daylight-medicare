"""Medicare facts come from a fresh lookup, never memory (D155 Q5).

Covers step 5 of the rebalance:
(1) a reply whose fact its sources don't support is repaired up to
FACT_REPAIR_LIMIT times, while other validation failures keep one repair;
(2) when every repair fails, code answers by quoting the reviewed source
retrieved for this message, with its citation, or, when nothing was retrieved
and the person asked something, shows SOURCE_GAP_NOTE and logs the gap without
the person's words; an approved question still follows (D109);
(3) when the person asked nothing, no gap note is shown;
(4) a model-reported source_gap appends the note;
(5) retrieval runs fresh for every message, including a repeated mention and
a pronoun follow-up, and reaches the composer as message_evidence_ids;
(6) the composer is told never to state a Medicare fact from memory.
No live models; all data is fictional.
"""
import copy
import json
import unittest
from unittest.mock import patch
import uuid

import test_composition_recovery as recovery
import test_natural_flow as flow_harness
from natural_agent import COMPOSE_INSTRUCTIONS, FACT_REPAIR_LIMIT, SOURCE_GAP_NOTE

INVENTED = 'An example amount is $777777.'
ASKED = 'How much does Part B cost me?'


class SourceFallbackTests(recovery.CompositionRecoveryTests):
    """Reuses the fault-injection harness; only this class's tests run here."""

    def setUp(self):
        """Ask a fictional Part B question with the reviewed Part B source in evidence."""
        super().setUp()
        self.source = {'id': 'partb', 'title': 'Part B basics',
                       'summary': 'Part B helps pay for doctor visits and outpatient care.'}
        self.context.update(current_message=ASKED, evidence=[copy.deepcopy(self.source)],
                            message_evidence_ids=['partb'])

    def invented(self, count=1 + FACT_REPAIR_LIMIT, **changes):
        """Return `count` drafts that each state an amount no source supports."""
        return [self.draft(reply=INVENTED, **changes) for _ in range(count)]

    def test_unsourced_fact_gets_three_repairs_then_quotes_the_retrieved_source(self):
        """Four calls in all, then the reply quotes the reviewed summary and cites it."""
        self.responses = self.invented()
        answer = self.compose()
        self.assertEqual(len(self.calls), 1 + FACT_REPAIR_LIMIT)
        self.assertEqual(self.reservation.stage('compose').attempts, 1 + FACT_REPAIR_LIMIT)
        self.assertIn(self.source['summary'], answer['reply'])
        self.assertIn('Part B basics', answer['reply'])
        self.assertNotIn('777777', json.dumps(answer))
        self.assertEqual(answer['evidence_refs'], ['partb'])
        self.assertEqual(answer['source_fallback'], {'kind': 'quoted', 'reason': 'ungrounded_literal',
                                                     'evidence_ids': ['partb']})
        self.assertEqual(answer['question'], self.draft()['question'])

    def test_repair_that_succeeds_on_the_third_try_is_used(self):
        """A valid draft on the last allowed repair is returned with its repair count."""
        self.responses = self.invented(FACT_REPAIR_LIMIT) + [self.draft()]
        answer = self.compose()
        self.assertEqual(answer['reply'], self.draft()['reply'])
        self.assertEqual(answer['validation_recovery']['repairs'], FACT_REPAIR_LIMIT)

    def test_no_retrieved_source_shows_gap_note_and_still_asks(self):
        """Without a retrieved source the reply is the gap note, logged by kind only."""
        self.context['message_evidence_ids'] = []
        self.responses = self.invented()
        with self.assertLogs('natural_agent', level='WARNING') as logs:
            answer = self.compose()
        self.assertEqual(answer['reply'], SOURCE_GAP_NOTE)
        self.assertEqual(answer['source_fallback']['kind'], 'gap')
        self.assertEqual(answer['question'], self.draft()['question'])
        output = '\n'.join(logs.output)
        self.assertIn('source gap kind=gap', output)
        self.assertNotIn('Part B cost', output)

    def test_gap_with_invalid_question_uses_an_approved_candidate(self):
        """When the model's question also fails, code asks the approved candidate's question."""
        self.context['message_evidence_ids'] = []
        self.responses = self.invented(question='With your $888888 premium, what insurance do you have now?')
        answer = self.compose()
        self.assertEqual(answer['reply'], SOURCE_GAP_NOTE)
        self.assertEqual(answer['question_target'], 'T05')
        self.assertNotIn('888888', json.dumps(answer))

    def test_no_question_asked_shows_no_gap_note(self):
        """A statement ('This is for me.') never gets 'sources don't cover that'."""
        self.context.update(current_message='This is for me.', message_evidence_ids=[])
        self.responses = self.invented()
        answer = self.compose()
        self.assertEqual(answer['reply'], '')
        self.assertNotIn('source_fallback', answer)
        self.assertEqual(answer['question'], self.draft()['question'])

    def test_other_validation_failures_keep_one_repair(self):
        """An unsupported finding is not a fact lookup failure: two calls, no quote."""
        bad = self.draft(reply='We have verified your coverage.')
        self.responses = [bad, copy.deepcopy(bad)]
        answer = self.compose()
        self.assertEqual(len(self.calls), 2)
        self.assertNotIn('source_fallback', answer)

    def test_model_reported_gap_appends_the_note(self):
        """source_gap true adds the gap note after the model's covered answer, in one call."""
        self.responses = [self.draft(source_gap=True)]
        answer = self.compose()
        self.assertEqual(answer['reply'], self.draft()['reply'] + '\n\n' + SOURCE_GAP_NOTE)
        self.assertEqual(answer['source_fallback']['reason'], 'model_reported')
        self.assertEqual(len(self.calls), 1)

    def test_compose_instructions_forbid_facts_from_memory(self):
        """The composer is told every fact comes from this turn's evidence and how to flag a gap."""
        self.assertIn('Never state a Medicare fact, rule, amount or date from memory', COMPOSE_INSTRUCTIONS)
        self.assertIn('source_gap true', COMPOSE_INSTRUCTIONS)


# Run only the tests above, not the inherited recovery suite a second time.
for _name in [name for name in dir(recovery.CompositionRecoveryTests) if name.startswith('test_')]:
    if _name not in SourceFallbackTests.__dict__:
        setattr(SourceFallbackTests, _name, None)


class FreshRetrievalTests(unittest.TestCase):
    def setUp(self):
        """Start a self visit in the natural-flow harness."""
        self.case = flow_harness.NaturalFlowTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.agent = self.case.flow.agent

    def test_repeated_mention_and_pronoun_follow_up_retrieve_again(self):
        """Each message is looked up on its own; 'what about that?' re-retrieves the last source."""
        self.assertEqual(self.agent.message_evidence_ids('What is Part B?'), ['partb'])
        self.assertEqual(self.agent.message_evidence_ids('What is Part B?'), ['partb'])
        self.assertEqual(self.agent.message_evidence_ids('What about that?', ['partb']), ['partb'])
        self.assertEqual(self.agent.message_evidence_ids('This is for me.', ['partb']), [])

    def test_composer_receives_the_sources_retrieved_for_each_message(self):
        """The compose context carries message_evidence_ids and their facts, on every mention."""
        self.case.message('This is for me.', [self.case.update('RC01', {'choice': 'self'}, 'This is for me.')])
        for _ in range(2):
            self.case.message('What is Part B?')
            context = self.case.composed_context()
            self.assertEqual(context['message_evidence_ids'], ['partb'])
            self.assertIn('partb', [item['id'] for item in context['evidence']])


if __name__ == '__main__':
    unittest.main()
