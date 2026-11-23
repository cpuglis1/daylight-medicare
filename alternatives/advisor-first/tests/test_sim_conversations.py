"""The simulated-conversation runner (tools/evaluation/sim_conversations.py, D155 Q7, Q8).

Covers: (1) all checked-in cases load, keys match files, probes are known
checks, and the default subset probes every check; (2) a full run against a
fixture advisor over loopback HTTP with a fake `claude` executable plays the
opening, a scripted event and simulated replies, links each turn ID to its
saved trace, asks one judge per check plus one per must item, escalates a
low-confidence verdict to the strong judge, and writes a report;
(3) a 429 from the advisor's 8-turns-per-minute limit is waited out
and retried, not recorded as a failed turn; the budget meter stops the run
before a turn that could pass the cap, stops on a meter that falls (UTC day
reset) or disappears, never allows a cap above $10 (--all included), and
refuses an unmetered server unless allowed; (4) scoring applies floors,
failOnAny and not-applicable, and a judge error marks the check 'error';
(5) a judge returning junk, or a failed must item, fails the exit code;
(6) a non-loopback base is refused; (7) `claude -p` runs with --safe-mode in
an empty temp folder. No live models, no real spend.
"""
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import threading
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / 'tools/evaluation'))
from server import build  # First: it puts the pinned engine on sys.path.
import sim_conversations as sim

# A fake `claude -p`: logs each call, answers the person schema with a fixed
# reply and the verdict schema per FAKE_JUDGE (pass | lowconf | junk | fail).
FAKE = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
schema = json.loads(args[args.index('--json-schema') + 1])
model = args[args.index('--model') + 1]
prompt = sys.stdin.read()
with open(os.environ['FAKE_LOG'], 'a') as log:
    log.write(json.dumps({'model': model, 'person': 'leaving' in schema['properties'],
                          'safe': '--safe-mode' in args, 'cwd': os.getcwd(),
                          'privacy': 'never asks for, invites' in prompt}) + '\n')
mode = os.environ.get('FAKE_JUDGE', 'pass')
if 'leaving' in schema['properties']:
    out = {'message': "I'm not sure.", 'leaving': False}
elif mode == 'junkchecks' and 'pass means Daylight did NOT do it' not in prompt and 'pass means Daylight covered it' not in prompt:
    print('not json at all'); sys.exit(0)
elif mode == 'junk':
    print('not json at all'); sys.exit(0)
elif mode == 'lowconf' and model == 'cheap':
    out = {'applicable': True, 'pass': False, 'confidence': 0.3, 'reason': 'unsure'}
elif mode == 'itemfail' and 'pass means Daylight did NOT do it' in prompt:
    out = {'applicable': True, 'pass': False, 'confidence': 0.9, 'reason': 'item missed'}
elif mode == 'fail' and 'never asks for, invites' in prompt:
    out = {'applicable': True, 'pass': False, 'confidence': 0.9, 'reason': 'asked for the number in turn 2'}
else:
    out = {'applicable': True, 'pass': True, 'confidence': 0.95, 'reason': 'fine'}
print(json.dumps({'type': 'result', 'structured_output': out}))
'''


class Base(unittest.TestCase):
    """A fixture advisor with traces on, a fake claude, and a temp output dir."""

    def setUp(self):
        """Start the server and install the fake claude on CLAUDE_BIN."""
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        fake = self.dir / 'claude'
        fake.write_text(FAKE)
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        self.log = self.dir / 'calls.jsonl'
        env = mock.patch.dict(os.environ, {'CLAUDE_BIN': str(fake), 'FAKE_LOG': str(self.log)})
        env.start()
        self.addCleanup(env.stop)
        service = build(0, fixture=True, database=self.dir / 'g.sqlite3', turn_traces=self.dir / 'traces')
        thread = threading.Thread(target=service.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (service.shutdown(), service.server_close(), thread.join(5)))
        self.base = f'http://127.0.0.1:{service.server_port}'
        # A fake clock: the runner's rate-limit sleep advances time.monotonic,
        # which the advisor's per-minute turn limit reads, so no real waiting.
        self.slept = []
        real = sim.time.monotonic
        offset = [0.0]
        def sleep(seconds):
            self.slept.append(seconds)
            offset[0] += seconds
        for patch in (mock.patch.object(sim.time, 'sleep', sleep),
                      mock.patch.object(sim.time, 'monotonic', lambda: real() + offset[0])):
            patch.start()
            self.addCleanup(patch.stop)

    def calls(self):
        """The fake claude's call log."""
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def run_main(self, *extra):
        """Run main() into the temp dir; returns (exit code, results.json)."""
        out = self.dir / 'out'
        code = sim.main(['--base', self.base, '--allow-unmetered', '--out', str(out),
                         '--judge-models', 'cheap,strong', '--person-model', 'person', *extra])
        return code, json.loads((out / 'results.json').read_text())


class CaseTests(unittest.TestCase):
    """The checked-in case files."""

    def test_cases_load_and_the_default_subset_covers_every_check(self):
        """Every case validates; the default subset probes all nine checks."""
        checks = [c['id'] for c in sim.load_checks()]
        cases = sim.load_cases(check_ids=set(checks))
        self.assertEqual(len(cases), 20)
        subset = sim.default_subset(cases, checks)
        self.assertLess(len(subset), len(cases))
        self.assertEqual({p for k in subset for p in cases[k]['probes']}, set(checks))

    def test_case_opening_overrides_the_persona(self):
        """c08 replaces P16's fake SSN opening with its own digit-free offer."""
        case = sim.load_cases(check_ids={c['id'] for c in sim.load_checks()})['c08-p16-daughter-for-mom']
        self.assertNotIn('000-42', case['opening'])

    def test_a_case_with_an_unknown_probe_is_refused(self):
        """A probe that is not a check id stops the run before any conversation."""
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory)
        (directory / 'x1.yaml').write_text('key: x1\ntitle: t\nprobes: [made_up]\ntypist: self\n'
                                           'person_brief: b\nopening: hi\n')
        with self.assertRaisesRegex(sim.RunError, 'probes'):
            sim.load_cases(directory, check_ids={'privacy'})

    def test_non_loopback_base_is_refused(self):
        """The runner only drives a local advisor."""
        for base in ('http://example.com:8893', 'https://127.0.0.1:8893', 'http://127.0.0.1:8893/x'):
            with self.subTest(base=base), self.assertRaises(sim.RunError):
                sim.Advisor(base)


class RunTests(Base):
    """End to end against a fixture advisor."""

    def test_one_case_plays_events_links_traces_and_judges_each_check(self):
        """c11 runs to max_messages with its event, every turn has a trace, nine check judges plus must items."""
        code, result = self.run_main('--case', 'c11-switch-self-to-mom')
        run = result['runs'][0]
        case = sim.load_cases(check_ids={c['id'] for c in sim.load_checks()})['c11-switch-self-to-mom']
        persons = [t['person'] for t in run['turns'] if t['person'] is not None]
        self.assertEqual(persons[0], case['opening'])
        self.assertEqual(persons[3], case['events'][0]['say'])
        self.assertEqual(len(persons), case['max_messages'])
        self.assertEqual(run['stopped'], 'max_messages')
        self.assertTrue(self.slept, 'ten turns pass the 8-per-minute limit, so the runner waited')
        self.assertTrue(all(t['trace'] and t['trace']['turnId'] == t['turnId'] for t in run['turns']))
        self.assertEqual(set(run['checks']), {c['id'] for c in sim.load_checks()})
        self.assertEqual(len(run['items']), len(case['must_not_claim']) + len(case.get('must_cover') or []))
        judges = [c for c in self.calls() if not c['person']]
        self.assertEqual(len(judges), 9 + len(run['items']))
        self.assertTrue(all(c['model'] == 'cheap' for c in judges))
        self.assertEqual(code, 0)
        self.assertTrue((self.dir / 'out/report.md').exists())
        self.assertTrue(all(c['safe'] for c in self.calls()), 'every claude call uses --safe-mode')
        self.assertTrue(all(Path(c['cwd']).name.startswith('sim-claude-') for c in self.calls()), 'an empty temp cwd')

    def test_low_confidence_escalates_to_the_strong_judge(self):
        """A cheap verdict under 0.7 is replaced by the strong judge's verdict."""
        with mock.patch.dict(os.environ, {'FAKE_JUDGE': 'lowconf'}):
            _, result = self.run_main('--case', 'c13-dont-know-repeatedly', '--probes-only')
        verdicts = result['runs'][0]['checks']
        self.assertTrue(all(v['judge'] == 'strong' and v['pass'] for v in verdicts.values()))

    def test_a_failed_gate_fails_the_run(self):
        """One privacy failure fails a failOnAny gate and the exit code."""
        with mock.patch.dict(os.environ, {'FAKE_JUDGE': 'fail'}):
            code, result = self.run_main('--case', 'c17-privacy-probe', '--probes-only')
        self.assertEqual(result['summary']['privacy']['status'], 'fail')
        self.assertEqual(code, 1)

    def test_junk_judge_output_is_an_error_not_a_pass(self):
        """Unparseable judge output is recorded as an error, the check's status is 'error' and the exit code is 1."""
        with mock.patch.dict(os.environ, {'FAKE_JUDGE': 'junk'}):
            code, result = self.run_main('--case', 'c13-dont-know-repeatedly', '--probes-only')
        verdicts = result['runs'][0]['checks']
        self.assertTrue(all('error' in v for v in verdicts.values()))
        self.assertEqual(result['summary']['no_reask']['status'], 'error')
        self.assertEqual(code, 1)

    def test_a_check_error_alone_fails_the_exit_code(self):
        """Judges error on checks but every must item passes: the exit code is still 1."""
        with mock.patch.dict(os.environ, {'FAKE_JUDGE': 'junkchecks'}):
            code, result = self.run_main('--case', 'c17-privacy-probe', '--probes-only')
        self.assertTrue(result['runs'][0]['items'] and all(i.get('pass') for i in result['runs'][0]['items']))
        self.assertIn('error', {s['status'] for s in result['summary'].values()})
        self.assertEqual(code, 1)

    def test_an_unreachable_advisor_is_a_run_error_and_a_missing_meter(self):
        """A refused connection raises RunError from request() and reads as no meter, never an OSError."""
        import socket
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        advisor = sim.Advisor(f'http://127.0.0.1:{port}')
        with self.assertRaises(sim.RunError):
            advisor.request('/api/status')
        self.assertIsNone(advisor.spent_usd())

    def test_a_failed_must_item_fails_the_exit_code(self):
        """Checks all pass but one must_not_claim item fails: the exit code is 1."""
        with mock.patch.dict(os.environ, {'FAKE_JUDGE': 'itemfail'}):
            code, result = self.run_main('--case', 'c17-privacy-probe', '--probes-only')
        self.assertTrue(all(s['status'] in {'pass', 'no_data'} for s in result['summary'].values()))
        self.assertTrue(any(not i['pass'] for i in result['runs'][0]['items']))
        self.assertEqual(code, 1)

    def test_an_errored_conversation_fails_the_exit_code(self):
        """A conversation that raises mid-run is recorded and makes the exit code 1."""
        with mock.patch.object(sim, 'run_conversation', side_effect=RuntimeError('advisor said 500')):
            code, result = self.run_main('--case', 'c13-dont-know-repeatedly')
        self.assertIn('500', result['runs'][0]['error'])
        self.assertEqual(code, 1)

    def test_unmetered_server_is_refused_without_the_flag(self):
        """A fixture server has no budget meter, so a run needs --allow-unmetered."""
        code = sim.main(['--base', self.base, '--case', 'c13-dont-know-repeatedly', '--out', str(self.dir / 'o')])
        self.assertEqual(code, 2)
        self.assertEqual(self.calls(), [])

    def test_budget_cap_stops_before_a_turn_that_could_pass_it(self):
        """With each turn costing $3 and a $10 cap, the run stops after three turns."""
        spent = iter(i * 3.0 for i in range(100))
        with mock.patch.object(sim.Advisor, 'spent_usd', lambda self: next(spent)):
            code = sim.main(['--base', self.base, '--case', 'c13-dont-know-repeatedly',
                             '--case', 'c11-switch-self-to-mom', '--out', str(self.dir / 'o'),
                             '--judge-models', 'cheap', '--person-model', 'person'])
        result = json.loads((self.dir / 'o/results.json').read_text())
        self.assertEqual(code, 1)
        self.assertIn('cap', result['meta']['budgetStop'])
        self.assertLessEqual(result['meta']['spentUsd'], 10.0)
        self.assertEqual(result['runs'], [])

    def meter_run(self, readings):
        """Run c13 with the meter returning `readings` in order; returns (code, results)."""
        values = iter(readings)
        with mock.patch.object(sim.Advisor, 'spent_usd', lambda self: next(values)):
            code = sim.main(['--base', self.base, '--case', 'c13-dont-know-repeatedly', '--out', str(self.dir / 'm'),
                             '--judge-models', 'cheap', '--person-model', 'person'])
        return code, json.loads((self.dir / 'm/results.json').read_text())

    def test_a_meter_that_goes_down_stops_the_run(self):
        """The server's daily budget resets at UTC midnight; the run stops instead of counting from zero."""
        code, result = self.meter_run([9.0, 9.5, 0.2] + [0.2 + i for i in range(100)])
        self.assertEqual(code, 1)
        self.assertIn('went down', result['meta']['budgetStop'])
        self.assertAlmostEqual(result['meta']['spentUsd'], 0.5)

    def test_a_meter_that_disappears_stops_the_run(self):
        """A meter that reads None mid-run is a budget stop, not an uncapped turn or a crash."""
        code, result = self.meter_run([1.0, 1.1, None] + [None] * 100)
        self.assertEqual(code, 1)
        self.assertIn('disappeared', result['meta']['budgetStop'])

    def test_cap_above_ten_is_refused_even_with_all(self):
        """--cap-usd 30 is a usage error with or without --all, before any call."""
        for extra in ((), ('--all',)):
            with self.subTest(extra=extra), self.assertRaises(SystemExit) as stop, \
                    mock.patch('sys.stderr'):
                sim.main(['--base', self.base, '--cap-usd', '30', '--dry-run', *extra])
            self.assertEqual(stop.exception.code, 2)
        self.assertEqual(self.calls(), [])


class ScoreTests(unittest.TestCase):
    """Floors, failOnAny and not applicable."""

    def test_floor_failonany_and_not_applicable(self):
        """95% floor passes at 19/20; failOnAny fails at 19/20 even with a 50% floor; not-applicable is excluded."""
        checks = [{'id': 'a', 'floor': 0.95, 'failOnAny': False}, {'id': 'b', 'floor': 0.5, 'failOnAny': True},
                  {'id': 'c', 'floor': 0.95, 'failOnAny': False}]
        ok = {'applicable': True, 'pass': True}
        bad = {'applicable': True, 'pass': False}
        na = {'applicable': False, 'pass': False}
        runs = [{'checks': {'a': ok, 'b': ok, 'c': na}} for _ in range(19)] + [{'checks': {'a': bad, 'b': bad, 'c': na}}]
        summary = sim.score(runs, checks)
        self.assertEqual(summary['a']['status'], 'pass')
        self.assertEqual(summary['b']['status'], 'fail')
        self.assertEqual(summary['c']['status'], 'no_data')

    def test_an_errored_verdict_is_an_error_not_a_pass(self):
        """19 passes plus one judge error on a failOnAny gate is 'error', not 'pass'."""
        checks = [{'id': 'g', 'floor': 1.0, 'failOnAny': True}]
        runs = [{'checks': {'g': {'applicable': True, 'pass': True}}} for _ in range(19)]
        runs.append({'checks': {'g': {'error': 'judge returned junk'}}})
        self.assertEqual(sim.score(runs, checks)['g']['status'], 'error')


if __name__ == '__main__':
    unittest.main()
