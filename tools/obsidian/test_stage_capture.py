import json
from pathlib import Path
import tempfile
import unittest
from stage_capture import stage


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.capture = {'metadata': {'id': 'fictional-source-1', 'title': 'Fictional document', 'url': 'https://example.invalid/document'}, 'response': {'text': 'Original'}, 'isError': False, 'fetched_at': '2026-11-09T00:00:00Z', 'method': 'readable_fetch'}

    def test_staging_versions_previous_capture_and_is_idempotent(self):
        self.assertEqual(stage(self.root, 'drive', self.capture)['status'], 'staged')
        self.assertEqual(stage(self.root, 'drive', self.capture)['status'], 'unchanged')
        self.capture['response']['text'] = 'Changed'
        stage(self.root, 'drive', self.capture)
        history = list((self.root/'daylight_obsidian/.knowledge-imports/capture-history').rglob('*.json'))
        self.assertEqual(len(history), 1)
        self.assertEqual(json.loads(history[0].read_text())['response']['text'], 'Original')

    def test_identifier_cannot_escape_destination(self):
        self.capture['metadata']['id'] = '../../outside'
        with self.assertRaises(ValueError): stage(self.root, 'drive', self.capture)

    def test_unread_message_pages_are_rejected(self):
        c = {'metadata': {'id': 'fictional-chat-1', 'title': 'Fictional chat'}, 'fetched_at': '2026-11-09T00:00:00Z', 'pages': [{'turns': [], 'page': {'nextCursor': 'older'}}]}
        with self.assertRaises(ValueError): stage(self.root, 'chatgpt', c)
