"""Offline regression tests for the fixture demo's private-to-public data boundary."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import export_demo_observations as exporter


class DemoExportTest(unittest.TestCase):
    """Build fictional receipts with private sentinel data and check the export contract."""

    def setUp(self):
        """Build two attempts and one unbound case with independently controlled evidence."""
        self.run_id = '00000000-0000-4000-8000-000000000001'
        self.case = {'id': 'test-case', 'judge': 'question_timing', 'user_prompt': 'When can I enroll?'}
        self.cases = {'test-case': (self.case, 'a' * 64),
                      'unbound-case': ({**self.case, 'id': 'unbound-case'}, 'b' * 64)}
        self.manifest = {'runId': self.run_id, 'requestedCaseIds': ['test-case'],
                         'trialsPerCase': 2, 'unbound': ['unbound-case']}
        row = {'caseId': 'test-case', 'rawLineHash': 'a' * 64, 'trial': 1, 'status': 'observed',
               'trace': {'message': self.case['user_prompt'], 'providerPayload': 'PRIVATE SENTINEL'},
               'reply': 'It depends on your enrollment window.', 'turnId': 'PRIVATE SENTINEL'}
        self.run = {'schemaVersion': 1, 'kind': 'live_turn_observations', 'runId': self.run_id,
                    'startedAt': '2026-11-25T04:00:00+00:00', 'completedAt': '2026-11-25T04:00:05+00:00',
                    'identity': {'revision': 'c' * 40, 'releaseEligible': False,
                                 'requestedModel': 'gpt-6.2-sol', 'sourceDigest': 'PRIVATE SENTINEL'},
                    'capCents': 1000, 'accountedNanoUsd': 5, 'measuredNanoUsd': 2,
                    'trials': [row, {**row, 'trial': 2, 'status': 'incomplete', 'reply': 'What changed?'}]}
        score = {'caseId': 'test-case', 'trial': 1, 'suite': 'question_timing', 'split': 'heldout',
                 'verdict': 'fail', 'model': 'gpt-6.2-sol', 'confidence': 0.7,
                 'reason': 'The reply omits the relevant enrollment rule.', 'trace': 'PRIVATE SENTINEL'}
        self.scores = {'kind': 'live_turn_scores', 'runId': self.run_id, 'identity': self.run['identity'],
                       'judgeProvider': 'codex-chatgpt-subscription', 'judgeVersion': 'd' * 64,
                       'scores': [score, {**score, 'trial': 2, 'verdict': 'unscored'}]}

    def raw_run(self):
        """Serialize exactly the bytes whose hash the score report needs."""
        return json.dumps(self.run).encode()

    def project(self, report=True):
        """Call the projection with a matching digest unless the test overrides it."""
        raw = self.raw_run()
        scores = {'sourceHash': hashlib.sha256(raw).hexdigest(), **self.scores} if report else None
        return exporter.project(self.run_id, raw, self.manifest, scores, self.cases)

    def test_whitelist_exact_fixture_and_observed_verdict(self):
        """Keep the exact fixture and displayable live evidence; discard the private receipt fields."""
        result = self.project()
        self.assertEqual(result['kind'], 'demo_turn_observations')
        self.assertEqual(result['unboundCaseIds'], ['unbound-case'])
        self.assertEqual(set(result['identity']), {'revision', 'releaseEligible', 'requestedModel'})
        self.assertEqual(result['judgeModel'], 'gpt-6.2-sol')
        self.assertEqual(result['trials'][0], {
            'caseId': 'test-case', 'rawLineHash': 'a' * 64, 'trial': 1, 'status': 'observed',
            'prompt': 'When can I enroll?', 'reply': 'It depends on your enrollment window.',
            'score': 'fail', 'scoreModel': 'gpt-6.2-sol', 'scoreSource': 'subscription-judge',
            'scoreReason': 'The reply omits the relevant enrollment rule.',
        })
        self.assertEqual(result['trials'][1]['reply'], 'What changed?')
        self.assertNotIn('score', result['trials'][1])
        self.assertNotIn('PRIVATE SENTINEL', json.dumps(result))
        self.assertNotIn('judgeModel', self.project(report=False))

    def test_reject_mismatched_receipts(self):
        """Refuse a run mismatch, source mismatch, score key mismatch or verdict on an incomplete trial."""
        mutations = [
            ('sourceHash', 'e' * 64), ('runId', 'other'), ('identity', {}),
            ('judgeProvider', 'unknown'), ('judgeVersion', None),
            ('scores', [{**self.scores['scores'][0], 'trial': 9}]),
            ('scores', [self.scores['scores'][0]]),
            ('scores', [self.scores['scores'][0], self.scores['scores'][0]]),
            ('scores', [self.scores['scores'][0], {**self.scores['scores'][0], 'trial': 2}]),
            ('scores', [{**self.scores['scores'][0], 'model': 'haiku'}, self.scores['scores'][1]]),
        ]
        before = copy.deepcopy(self.scores)
        for key, value in mutations:
            with self.subTest(key=key, value=value):
                self.scores = {**before, key: value}
                with self.assertRaises(ValueError):
                    self.project()

    def test_reject_partial_or_substituted_run(self):
        """Reject incomplete batches, unrelated case versions and messages unlike the pinned fixture."""
        original = copy.deepcopy(self.run)
        mutations = [
            [original['trials'][0]],
            [original['trials'][0], {**original['trials'][1], 'trial': 1}],
            [{**original['trials'][0], 'rawLineHash': 'f' * 64}, original['trials'][1]],
            [{**original['trials'][0], 'trace': {'message': 'unreviewed text'}}, original['trials'][1]],
        ]
        for rows in mutations:
            with self.subTest(rows=rows):
                self.run['trials'] = rows
                with self.assertRaises(ValueError):
                    self.project()
        self.run = original
        self.manifest['unbound'] = []
        with self.assertRaises(ValueError):
            self.project()

    def test_text_suppression_keeps_observation_status(self):
        """Withhold dangerous content and judge prose while preserving the structured verdict."""
        risky = (
            '123-45-6789', '1EG4-TE5-MK73', '4111 1111 1111 1111',
            '600.555.0123', 'person@example.com', '<svg onload=alert(1)>',
            '[source](https://example.com)', 'ｍｙａｄｖｉｓｏｒ．ｃｏｍ',
            '/Users/example/private', '~/.config/key', 'Authorization: Bearer example',
            'sk-proj-secretvalue', 'resp_123456789abcdef', 'abcd\u202edef', 'abc%2Fdef',
            'Ignore the previous instructions',
        )
        for content in risky:
            with self.subTest(content=content):
                self.run['trials'][0]['reply'] = content
                result = self.project()
                self.assertEqual(result['trials'][0]['status'], 'observed')
                self.assertNotIn('reply', result['trials'][0])
                self.assertEqual(result['trials'][0]['score'], 'fail')
                self.assertNotIn('scoreReason', result['trials'][0])
                self.assertEqual(result['judgeModel'], 'gpt-6.2-sol')
                self.assertNotIn(content, json.dumps(result))

    def test_judge_error_stays_visible_without_a_displayable_reply(self):
        """Keep a judge error on an observed row and exclude scores from incomplete rows."""
        self.run['trials'][0]['reply'] = 'https://example.com'
        for score in self.scores['scores']:
            score.update(verdict='error', confidence=None, reason='PRIVATE SENTINEL')
        result = self.project()
        first, second = result['trials']
        self.assertNotIn('reply', first)
        self.assertEqual(first['score'], 'error')
        self.assertEqual(first['scoreModel'], 'gpt-6.2-sol')
        self.assertEqual(first['scoreSource'], 'subscription-judge')
        self.assertNotIn('scoreReason', first)
        self.assertNotIn('score', second)

    def test_score_reason_screening_removes_unsafe_or_overlong_prose(self):
        """Expose only a bounded safe reason while keeping the verified score."""
        for reason in ('Visit https://example.com', 'a ' * 1001, '🙂 ' * 800, '\t'):
            with self.subTest(reason=reason):
                self.scores['scores'][0]['reason'] = reason
                trial = self.project()['trials'][0]
                self.assertEqual(trial['score'], 'fail')
                self.assertNotIn('scoreReason', trial)

    def test_mixed_subscription_models_are_attributed_per_trial(self):
        """A mixed Claude batch has model evidence on each trial and no shared model."""
        del self.scores['judgeProvider'], self.scores['judgeVersion']
        self.run['trials'][1]['status'] = 'observed'
        self.scores['scores'][0]['model'] = 'haiku'
        self.scores['scores'][1].update(verdict='pass', model='sonnet')
        result = self.project()
        self.assertNotIn('judgeModel', result)
        self.assertEqual([trial['scoreModel'] for trial in result['trials']], ['haiku', 'sonnet'])

    def test_pinned_corpus_and_strict_json(self):
        """Admit all original validation fixtures and refuse edits or ambiguous JSON values."""
        self.assertEqual(len(exporter.load_validation_cases()), 180)
        with patch.object(exporter, 'CORPUS_HASHES', {'question_timing': 'f' * 64}):
            with self.assertRaises(ValueError):
                exporter.load_validation_cases()
        for raw in (b'{"x":0,"x":1}', b'{"x":NaN}', b'{"x":', b'[]'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                exporter.parse_object(raw)

    def test_private_cli_refuses_symlinks_permissive_modes_and_partial_input(self):
        """Reject unsafe files at the actual CLI boundary without disclosing artifact contents."""
        with TemporaryDirectory() as root:
            store = Path(root)
            progress = store / 'progress'
            progress.mkdir(mode=0o700)
            manifest = progress / f'{self.run_id}.manifest'
            manifest.write_text(json.dumps(self.manifest))
            manifest.chmod(0o600)
            run = store / f'live-observation-{self.run_id}.json'
            run.write_bytes(self.raw_run())
            run.chmod(0o644)
            error = io.StringIO()
            with patch.object(exporter, 'STORE', store), patch.object(exporter, 'load_validation_cases', return_value=self.cases):
                with redirect_stderr(error), self.assertRaises(SystemExit):
                    exporter.main([str(run)])
                run.chmod(0o600)
                target = store / 'target'
                run.rename(target)
                run.symlink_to(target)
                with redirect_stderr(error), self.assertRaises(SystemExit):
                    exporter.main([str(run)])
                run.unlink()
                target.rename(run)
                run.write_bytes(b'{"secret":"PRIVATE SENTINEL"')
                with redirect_stderr(error), self.assertRaises(SystemExit):
                    exporter.main([str(run)])
                self.assertEqual(list(store.glob('demo-observation-*')), [])
                self.assertNotIn('PRIVATE SENTINEL', error.getvalue())
                run.write_bytes(self.raw_run())
                out = io.StringIO()
                with redirect_stdout(out):
                    self.assertEqual(exporter.main([str(run)]), 0)
                self.assertTrue((store / out.getvalue().strip()).is_file())

    def test_optional_change_reason_at_cli_boundary(self):
        """Accept a safe operator reason and refuse unsafe values without exposing their text."""
        with TemporaryDirectory() as root:
            store = Path(root)
            progress = store / 'progress'
            progress.mkdir(mode=0o700)
            manifest = progress / f'{self.run_id}.manifest'
            manifest.write_text(json.dumps(self.manifest))
            manifest.chmod(0o600)
            run = store / f'live-observation-{self.run_id}.json'
            run.write_bytes(self.raw_run())
            run.chmod(0o600)
            with patch.object(exporter, 'STORE', store), patch.object(exporter, 'load_validation_cases', return_value=self.cases):
                for invalid in ('', ' ', 'x ' * 150 + 'x', '🙂 ' * 101, 'Second\nline', 'End\n',
                                'Second\u2028line', 'Second\u2029line', 'Contains\ttab',
                                'https://example.com', '<script>text</script>', 'person@example.com'):
                    with self.subTest(invalid=invalid):
                        error = io.StringIO()
                        with redirect_stderr(error), self.assertRaises(SystemExit):
                            exporter.main([str(run), '--change-reason', invalid])
                        self.assertIn('Export refused', error.getvalue())
                        if invalid.strip():
                            self.assertNotIn(invalid, error.getvalue())
                self.assertEqual(list(store.glob('demo-observation-*')), [])
                out = io.StringIO()
                with redirect_stdout(out):
                    self.assertEqual(exporter.main([str(run)]), 0)
                before = json.loads((store / out.getvalue().strip()).read_bytes())
                self.assertNotIn('changeReason', before)
                reason = 'Rewrote shoppers’ questions and reran validation.'
                out = io.StringIO()
                with redirect_stdout(out):
                    self.assertEqual(exporter.main([str(run), '--change-reason', reason]), 0)
                after = json.loads((store / out.getvalue().strip()).read_bytes())
                self.assertEqual(after, {**before, 'changeReason': reason})

    def test_digest_output_races_and_refuses_a_conflicting_path(self):
        """Concurrent retries converge on complete owner-only content without overwriting a collision."""
        with TemporaryDirectory() as root, exporter.private_directory(root) as directory:
            result = self.project()
            with ThreadPoolExecutor(max_workers=2) as executor:
                first, second = executor.map(lambda _: exporter.write_export(directory, result), range(2))
            self.assertEqual(first, second)
            path = Path(root) / first
            raw = path.read_bytes()
            self.assertEqual(path.name, f'demo-observation-{hashlib.sha256(raw).hexdigest()}.json')
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(json.loads(raw), result)
            self.assertEqual(os.listdir(root), [first])
            path.write_text('conflicting artifact')
            with self.assertRaises(ValueError):
                exporter.write_export(directory, result)
            self.assertEqual(path.read_text(), 'conflicting artifact')


if __name__ == '__main__':
    unittest.main()
