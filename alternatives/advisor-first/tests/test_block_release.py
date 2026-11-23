"""Checked-block release and the interpreter-notes switch (:8895, Nov 17, 2026); no network."""
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server  # noqa: F401  (loads the pinned engine paths)
import block_release
from block_release import Releaser, scan
import natural_agent
import turn_progress


def draft(blocks, refs=None, close=True):
    fields = {'question_target': None, 'question': 'Q?', 'report_refs': [], 'evidence_refs': ['f1'],
              'agenda_update': {'current_concern': '', 'pause': False}, 'addressed_requests': []}
    if refs is not None:
        fields['block_refs'] = refs
    text = json.dumps(fields, separators=(',', ':'))[:-1] + ',"reply_blocks":' + json.dumps(blocks)
    return text + (',"offer_concept":""}' if close else '')


class ScanTests(unittest.TestCase):
    def test_finished_blocks_only(self):
        full = draft(['First block.', 'Second block.'])
        cut = full[:full.index('Second') + 4]           # second block still being written
        fields, blocks = scan(cut)
        self.assertEqual(blocks, ['First block.'])
        self.assertEqual(fields['question'], 'Q?')
        self.assertEqual(scan(full)[1], ['First block.', 'Second block.'])

    def test_nothing_before_the_blocks_key(self):
        self.assertEqual(scan('{"question_target":null,"question":"Q'), (None, []))
        self.assertEqual(scan(''), (None, []))

    def test_escapes_and_quotes_inside_blocks(self):
        blocks = ['He said "Part B" — fine.\nNew line.', 'Two']
        self.assertEqual(scan(draft(blocks))[1], blocks)

    def test_refs_listed_first_are_read(self):
        fields, _ = scan(draft(['A.'], refs=[['f1']]))
        self.assertEqual(fields['block_refs'], [['f1']])


class ReleaserTests(unittest.TestCase):
    def run_stream(self, text, check=lambda f, b: True, guard=None, step=7):
        published = []
        r = Releaser(check, published.append, guard=guard)
        for end in range(step, len(text) + step, step):
            r(text[:end])
        return r, published

    def test_blocks_publish_in_order_as_they_finish(self):
        r, published = self.run_stream(draft(['One.', 'Two.', 'Three.']))
        self.assertEqual(published, [['One.'], ['One.', 'Two.'], ['One.', 'Two.', 'Three.']])
        self.assertEqual(r.summary()['released'], 3)
        self.assertIsNotNone(r.summary()['first_ms'])

    def test_a_failed_check_stops_release(self):
        r, published = self.run_stream(draft(['Good.', 'Bad.', 'Later.']), check=lambda f, b: b != 'Bad.')
        self.assertEqual(published[-1], ['Good.'])
        self.assertTrue(r.stopped)

    def test_a_check_error_is_a_failed_check(self):
        def broken(fields, block):
            raise KeyError('missing')
        r, published = self.run_stream(draft(['One.']), check=broken)
        self.assertEqual(published, [])
        self.assertTrue(r.stopped)

    def test_say_once_skips_a_block_and_continues_with_its_refs(self):
        seen = []
        def guard(block, refs):
            seen.append((block, refs))
            return block != 'Repeat.'
        r, published = self.run_stream(draft(['Repeat.', 'New.'], refs=[['f1'], []]), guard=guard)
        self.assertEqual(published, [['New.']])
        self.assertEqual(seen, [('Repeat.', ['f1']), ('New.', [])])
        self.assertEqual(r.summary()['held'], 1)

    def test_summary_carries_no_text(self):
        r, _ = self.run_stream(draft(['Private words.']))
        self.assertNotIn('Private', json.dumps(r.summary()))


class ProgressTests(unittest.TestCase):
    def test_blocks_ride_only_on_a_working_receipt(self):
        progress = turn_progress.Progress()
        with turn_progress.track(progress, 'owner', 'request-1'):
            turn_progress.accepted()
            turn_progress.publish_blocks(['Checked block.'])
            self.assertEqual(progress.read('owner', 'request-1')['blocks'], ['Checked block.'])
        self.assertEqual(progress.read('owner', 'request-1'), {'state': 'complete'})
        self.assertNotIn('blocks', progress.receipts[('owner', 'request-1')])

    def test_publish_outside_a_turn_is_a_no_op(self):
        turn_progress.publish_blocks(['Nothing happens.'])

    def test_publish_is_bounded(self):
        progress = turn_progress.Progress()
        progress.begin(('o', 'r'))
        with self.assertRaises(ValueError):
            progress.publish(('o', 'r'), ['x'] * 5)
        with self.assertRaises(ValueError):
            progress.publish(('o', 'r'), [''])


class SwitchTests(unittest.TestCase):
    def test_release_and_speed_switches(self):
        with patch.dict(os.environ, {block_release.ENV: 'on', block_release.SPEED_ENV: '5'}):
            self.assertTrue(block_release.enabled())
            self.assertEqual(block_release.reveal_speed(), 5.0)
        with patch.dict(os.environ, {block_release.ENV: '', block_release.SPEED_ENV: '99'}):
            self.assertFalse(block_release.enabled())
            self.assertEqual(block_release.reveal_speed(), 3.0)

    def test_notes_mode_env_and_override_file(self):
        with patch.object(natural_agent, 'NOTES_OVERRIDE', Path('/nonexistent/interpreter-notes')):
            with patch.dict(os.environ, {natural_agent.NOTES_ENV: 'compact'}):
                self.assertEqual(natural_agent.interpreter_notes_mode(), 'compact')
            with patch.dict(os.environ, {natural_agent.NOTES_ENV: 'anything'}):
                self.assertEqual(natural_agent.interpreter_notes_mode(), 'standard')

    def test_notes_override_file_wins(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            flag = Path(folder) / 'interpreter-notes'
            flag.write_text('compact\n')
            with patch.object(natural_agent, 'NOTES_OVERRIDE', flag), \
                    patch.dict(os.environ, {natural_agent.NOTES_ENV: 'standard'}):
                self.assertEqual(natural_agent.interpreter_notes_mode(), 'compact')
            with patch.object(natural_agent, 'NOTES_OVERRIDE', flag), patch.dict(os.environ, {}, clear=False):
                os.environ.pop(natural_agent.NOTES_ENV, None)
                # :8893/:8894 set no switch, so the :8895 override file never reaches them.
                self.assertEqual(natural_agent.interpreter_notes_mode(), 'standard')
            flag.write_text('standard')
            with patch.object(natural_agent, 'NOTES_OVERRIDE', flag), \
                    patch.dict(os.environ, {natural_agent.NOTES_ENV: 'compact'}):
                self.assertEqual(natural_agent.interpreter_notes_mode(), 'standard')


if __name__ == '__main__':
    unittest.main()


import tests.test_conversation_records as records_journey


class ReleaseJourney(unittest.TestCase):
    """The real :8895 records path with scripted model output."""

    def journey(self, env, blocks):
        with patch.dict(os.environ, env):
            case = records_journey.RecordsJourney('test_opening_fills_coverage_and_whose_job_and_targets_parts')
            case.setUp()
            out = case.opening(compose_override=case.ask_recommended(blocks=blocks))
            return case, out

    def schema_order(self, case):
        calls = [c for c in case.calls if isinstance(c, dict)
                 and c.get('text', {}).get('format', {}).get('name') == 'daylight_resolved_conversation']
        return list(calls[-1]['text']['format']['schema']['properties'])

    def test_checked_blocks_are_released_and_kept(self):
        bland = records_journey.BLAND
        case, out = self.journey({block_release.ENV: 'on'}, [(bland, []), ('Your timing depends on your job coverage.', [])])
        release = case.flow.agent.local.block_release
        self.assertGreaterEqual(release.summary()['released'], 1)
        self.assertTrue(' '.join(out['reply'].split()).startswith(' '.join('\n\n'.join(release.released).split())))
        order = self.schema_order(case)
        self.assertLess(order.index('block_refs'), order.index('reply_blocks'))
        # Only the fields the block check reads come first; the other notes follow the blocks.
        before = order[:order.index('block_refs')]
        self.assertEqual(set(before), set(natural_agent.RELEASE_CHECK_FIELDS) & set(order))
        for later in ('education', 'task_work', 'conversation_assessment', 'addressed_requests', 'offer_concept'):
            self.assertGreater(order.index(later), order.index('reply_blocks'))
        self.assertNotIn('_released_blocks', out)

    def test_switch_off_changes_nothing(self):
        case, out = self.journey({block_release.ENV: ''}, [(records_journey.BLAND, [])])
        self.assertIsNone(case.flow.agent.local.block_release)
        order = self.schema_order(case)
        self.assertGreater(order.index('block_refs'), order.index('reply_blocks'))

    def test_a_failing_later_block_keeps_only_what_was_shown(self):
        bland = records_journey.BLAND
        case, out = self.journey({block_release.ENV: 'on'}, [(bland, []), ('Part B costs $999 a month for everyone.', [])])
        release = case.flow.agent.local.block_release
        self.assertEqual(release.released, [bland])
        self.assertTrue(release.stopped)
        self.assertTrue(out['reply'].startswith(bland))
        self.assertNotIn('$999', out['reply'])

    def test_compact_notes_policy_reaches_only_the_interpreter(self):
        for mode, expected in (('compact', True), ('standard', False)):
            with self.subTest(mode=mode), patch.object(natural_agent, 'NOTES_OVERRIDE', Path('/nonexistent/x')):
                case, _ = self.journey({natural_agent.NOTES_ENV: mode}, [(records_journey.BLAND, [])])
                extraction = [c for c in case.calls if isinstance(c, dict)
                              and c.get('text', {}).get('format', {}).get('name') == 'daylight_guide_commands'][-1]
                context = json.loads(extraction['input'][0]['content'])['confirmed_context']
                self.assertEqual('notes_policy' in context, expected)
                stages = case.flow.agent.local.model_stages
                self.assertTrue(any(row.get('notes') == mode for row in stages if row['stage'] == 'extract'))
