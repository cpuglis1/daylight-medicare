"""Offline factual fixture checks for exact sources and selected Plans context."""

import json
from pathlib import Path
import socketserver
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import run_live as runner
from comparison_profile import SOURCE_PATHS
import starts_facts


class FactsStartsTest(unittest.TestCase):
    """Exercise source admission and the normal signed local visit setup."""

    def setUp(self):
        """Load only the pinned fictional starts from the immutable corpus."""
        self.rows = runner.corpus_cases()
        self.starts = starts_facts.build_starts(self.rows)

    def test_requires_exact_source_and_offered_lookup(self):
        """Missing source or tool is incomplete, while skipping an offered tool is observable."""
        start = self.starts['medicare_factual_support-work_cobra-1']
        with self.assertRaises(ValueError):
            starts_facts.verify_start(SimpleNamespace(rule_facts={}), {}, start)

        tool = {'type': 'function', 'name': 'lookup_medicare_sources',
                'parameters': {'properties': {'source_ids': {'items': {'enum': []}}}}}
        request = {'tools': [tool]}
        trace = {'modelCalls': [{'kind': 'compose', 'request': request}], 'toolCalls': []}
        self.assertFalse(starts_facts.verify_observation(trace, start))
        tool['parameters']['properties']['source_ids']['items']['enum'].append(start['source_id'])
        self.assertTrue(starts_facts.verify_observation(trace, start))

    def test_plan_year_requires_selected_2026_context(self):
        """A response is observable only when the exact catalog selection reaches composition."""
        start = self.starts['required_coverage-plan_year-1']
        context = {'selected_id': start['selected_plan'], 'scope': {'year': 2027}}
        request = {'input': [{'content': json.dumps({'resolved_context': {'plans_context': context}})}]}
        trace = {'modelCalls': [{'kind': 'compose', 'request': request}]}
        self.assertFalse(starts_facts.verify_observation(trace, start))
        context['scope']['year'] = 2026
        request['input'][0]['content'] = json.dumps({'resolved_context': {'plans_context': context}})
        self.assertTrue(starts_facts.verify_observation(trace, start))

    @unittest.skipUnless(
        all((runner.REPO / path).is_file() for path in SOURCE_PATHS.values()),
        'Provision the pinned local advisor sources in LIVE_ADAPTER.md.',
    )
    def test_all_typed_starts_apply_to_the_real_local_advisor(self):
        """All admitted starts preserve their reports, prior turns and exact local references."""
        runner._load_contract()
        with TemporaryDirectory() as directory, \
                patch.object(socketserver.TCPServer, 'server_bind'), \
                patch.object(socketserver.TCPServer, 'server_activate'):
            with runner.build(0, fixture=True, database=Path(directory) / 'guest.sqlite3') as service:
                flow = service.adaptive
                for case_id, start in self.starts.items():
                    with self.subTest(case_id=case_id):
                        self.assertEqual(start['lineHash'], self.rows[case_id][1])
                        state = runner.seed(flow, case_id, start, starts_facts)
                        self.assertEqual(len(flow.recent_exchanges(case_id, None, runner.CONTEXT_POLICY)),
                                         len(start['history']))
                        permission = starts_facts.prepare_trial(service, case_id, state, start)
                        if 'selected_plan' in start:
                            self.assertEqual(permission['plansContext']['selectedId'], start['selected_plan'])
                        else:
                            self.assertEqual(permission, {})
                        flow.forget_owner(case_id)


if __name__ == '__main__':
    unittest.main()
