"""Offline delivery checks; no model, conversation or network calls."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conversation_output import generated_conversation


class ConversationOutputTests(unittest.TestCase):
    def output(self):
        return {'reply': 'Model-authored explanation.', 'generated': {'status': 'complete'},
                'facts': [{'title': 'Prepared lesson', 'text': 'Prepared text',
                           'source': 'https://www.medicare.gov/basics'}],
                'advisor': {'visual': 'transition', 'teachingFactIds': ['enrollment_intro'],
                            'sources': [{'url': 'https://www.medicare.gov/basics', 'label': 'Source'}]},
                'understanding': {'title': 'Your coverage transition', 'blocks': ['Prepared text']},
                'record': {'reported': 'unchanged'}, 'assessment': {'nextQuestion': {'id': 'T05'}}}

    def test_generated_reply_sources_and_report_state_survive_without_templates(self):
        out = self.output()
        before = copy.deepcopy(out)
        generated_conversation(out)
        self.assertEqual(out['reply'], before['reply'])
        self.assertEqual(out['advisor']['sources'], before['advisor']['sources'])
        self.assertEqual(out['advisor']['teachingFactIds'], before['advisor']['teachingFactIds'])
        self.assertEqual(out['record'], before['record'])
        self.assertEqual(out['assessment'], before['assessment'])
        self.assertEqual(out['facts'], [])
        self.assertNotIn('understanding', out)
        self.assertEqual(out['advisor']['visual'], 'none')

    def test_failed_or_manual_response_does_not_substitute_prepared_prose(self):
        for generation in ({}, {'status': 'unavailable'}):
            out = self.output()
            out['generated'] = generation
            out['reply'] = 'Prepared fallback.'
            generated_conversation(out)
            self.assertEqual(out['reply'], '')
            self.assertEqual(out['facts'], [])
            self.assertEqual(out['advisor']['teachingFactIds'], [])
            self.assertEqual(len(out['advisor']['sources']), 1)

    def test_legacy_source_links_and_repeated_filtering_are_preserved(self):
        out = self.output()
        out.pop('advisor')
        generated_conversation(out)
        before = copy.deepcopy(out)
        self.assertEqual(out['advisor']['sources'][0]['url'], 'https://www.medicare.gov/basics')
        self.assertEqual(generated_conversation(out), before)


if __name__ == '__main__':
    unittest.main()
