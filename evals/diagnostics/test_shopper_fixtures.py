"""Offline regression checks for visitor-visible materials and fictional price notes.

These checks exercise the same fixture admission and observation verification
as the diagnostic runner. They never call the model or open a guest visit.
"""

import json
import unittest

import run_live
import starts_conversation
import starts_tools


class ShopperFixtureTest(unittest.TestCase):
    """Protect the distinct roles of catalog listings, visitor reports and plan IDs."""

    def test_dated_booklet_does_not_resolve_undated_printout(self):
        """Bind only the dated plan and require the actual selected entry in the trace."""
        rows = run_live.corpus_cases()
        starts = starts_conversation.build_starts(rows)
        for variant in range(1, 6):
            key = f'question_timing-year-{variant}'
            with self.subTest(case=key):
                start = starts[key]
                self.assertEqual(start['lineHash'], rows[key][1])
                self.assertTrue(any('Humana' in user for user, _, _ in start['history']))
                for selected, supported in ((start['datedBooklet'], True), ('2026:H5216:072:000', False)):
                    context = {'plans_context': {'selected_id': selected, 'scope': {'year': 2026}}}
                    content = json.dumps({'resolved_context': context})
                    trace = {'modelCalls': [{'kind': 'compose', 'request': {'input': [{'content': content}]}}]}
                    self.assertEqual(starts_conversation.verify_observation(trace, start), supported)

    def test_recap_requires_price_notes_in_composition(self):
        """Omitting earlier visitor notes makes a price recap unscorable."""
        start = starts_tools.build_starts(run_live.corpus_cases())['tool_use-handoff_summary-1']
        note = start['history'][0][0]
        lookup = {'name': 'lookup_medicare_sources', 'type': 'function',
                  'parameters': {'properties': {'source_ids': {'items': {'enum': []}}}}}
        for history, supported in (([], False), ([{'user': note}], True)):
            context = {'evidence': [], 'recent_exchanges': history}
            request = {'tools': [lookup], 'input': [{'content': json.dumps({'resolved_context': context})}]}
            trace = {'modelCalls': [{'kind': 'compose', 'request': request}]}
            self.assertEqual(starts_tools.verify_observation(trace, start), supported)
