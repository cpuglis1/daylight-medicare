import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('sync', Path(__file__).with_name('sync.py'))
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'PRINCIPLES.md').write_text('# Principles\n\nFictional invariant.\n')

    def run_refresh(self):
        p = sync.Projection(self.root)
        p.refresh()
        return p

    def test_repeat_refresh_is_stable_and_original_unchanged(self):
        original = (self.root / 'PRINCIPLES.md').read_bytes()
        p = self.run_refresh()
        rec = p.state['sources']['local:PRINCIPLES.md']
        note = p.vault / rec['note']; first = note.read_bytes()
        again = self.run_refresh()
        self.assertEqual(note.read_bytes(), first)
        self.assertEqual((self.root / 'PRINCIPLES.md').read_bytes(), original)
        self.assertEqual(again.counts['updated'], 0)

    def test_annotations_survive_source_refresh_and_history_retained(self):
        p = self.run_refresh(); note = p.vault / p.state['sources']['local:PRINCIPLES.md']['note']
        note.write_text(note.read_text() + 'My annotation stays.\n')
        (self.root / 'PRINCIPLES.md').write_text('# Principles\n\nChanged fictional invariant.\n')
        self.run_refresh()
        self.assertIn('My annotation stays.', note.read_text())
        self.assertIn('Changed fictional invariant.', note.read_text())
        self.assertTrue(list((p.system / 'history').rglob('*.md')))

    def test_edited_generated_content_is_not_overwritten(self):
        p = self.run_refresh(); note = p.vault / p.state['sources']['local:PRINCIPLES.md']['note']
        changed = note.read_text().replace('Fictional invariant.', 'My corrected wording.')
        note.write_text(changed)
        q = self.run_refresh()
        self.assertEqual(note.read_text(), changed)
        self.assertEqual(q.counts['conflicts'], 1)
        self.assertTrue(list((p.vault / '91 Reviews/Incoming').glob('*.md')))

    def test_missing_source_retains_note_and_flags_loss(self):
        p = self.run_refresh(); note = p.vault / p.state['sources']['local:PRINCIPLES.md']['note']
        (self.root / 'PRINCIPLES.md').unlink()
        q = self.run_refresh()
        self.assertTrue(note.exists())
        self.assertTrue(any(e['kind'] == 'source_missing' for e in q.state['events']))

    def test_sensitive_paths_and_symlinks_are_not_ingested(self):
        (self.root / '.env').write_text('secret=fake')
        (self.root / 'var').mkdir(); (self.root / 'var/private.md').write_text('PRIVATE')
        (self.root / 'link.md').symlink_to('/etc/hosts')
        p = self.run_refresh()
        self.assertEqual(len(p.state['sources']), 1)
        self.assertNotIn('PRIVATE', ''.join(f.read_text() for f in (p.vault / '90 Sources').rglob('*.md')))

    def test_same_titles_use_distinct_ids(self):
        self.assertNotEqual(sync.note_path('Drive', 'Same', 'drive:one'), sync.note_path('Drive', 'Same', 'drive:two'))

    def test_output_cannot_escape_vault(self):
        with self.assertRaises(ValueError): sync.safe_target(self.root, '../escape.md')

    def test_links_point_to_imported_document(self):
        (self.root / 'readme.md').write_text('[Policy](PRINCIPLES.md)')
        p = self.run_refresh()
        note = p.vault / p.state['sources']['local:readme.md']['note']
        self.assertIn('[[90 Sources/Local/', note.read_text())

    def test_link_alias_does_not_split_markdown_table(self):
        value = sync.rewrite_links('| Source | [Policy](PRINCIPLES.md) |', self.root/'readme.md', self.root, {'PRINCIPLES.md': '90 Sources/Policy.md'})
        self.assertIn(r'[[90 Sources/Policy\|Policy]]', value)

    def test_backup_archive_readback(self):
        self.run_refresh()
        result = sync.backup(self.root)
        self.assertGreater(result['files_verified'], 0)
        self.assertTrue(Path(result['archive']).is_file())

    def test_chat_roles_and_truncation_stay_explicit(self):
        payload = {'pages': [{'turns': [{'id': 'turn', 'startedAt': 1, 'items': [
            {'type': 'userMessage', 'content': [{'type': 'text', 'text': 'An idea, not an approval'}]},
            {'type': 'agentMessage', 'id': 'reply', 'text': 'Hypothesis', 'truncated': True}]}]}]}
        text, gaps, _ = sync.chat_text(payload)
        self.assertIn('Owner message', text)
        self.assertIn('not verified authority', text)
        self.assertTrue(any('truncated' in g for g in gaps))

    def test_all_native_doc_tabs_are_read(self):
        content = sync.doc_text({'tabs': [{'title': 'One', 'body': {'content': [{'paragraph': {'elements': [{'textRun': {'content': 'FIRST'}}]}}]}}, {'title': 'Two', 'body': {'content': [{'paragraph': {'elements': [{'textRun': {'content': 'SECOND'}}]}}]}}]})
        self.assertIn('FIRST', content); self.assertIn('SECOND', content)


if __name__ == '__main__': unittest.main()
