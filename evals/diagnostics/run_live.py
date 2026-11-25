#!/usr/bin/env python3
"""Single-turn diagnostics against the isolated local Daylight advisor.

Only checked-in fictional fixtures are executable. This CLI builds an ephemeral
loopback advisor but never dispatches HTTP requests or creates a release comparison. A reviewed
daily ledger is retained separately so running the CLI twice cannot reset its
provider cap or outstanding holds. Raw fictional traces are exported privately.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import os
import secrets
import subprocess
import sys
from tempfile import TemporaryDirectory
from uuid import uuid4

from adapter_cases import STARTS

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ADVISOR = REPO / 'alternatives/advisor-first'
STORE = ADVISOR / 'var/eval-diagnostics'
sys.path.insert(0, str(ADVISOR))

from server import build  # Imports and verifies the pinned shared engine.
from advisor_budget import AdvisorDailyBudget, BudgetError, NANO
from advisor_memory import CONTEXT_POLICY
from advisor_models import MODELS
from identifier_guard import find_identifiers
from comparison_profile import _load_contract


class DiagnosticBudget(AdvisorDailyBudget):
    """Apply a run ceiling in the same transaction as each ordinary reservation."""

    def record_model(self, db, key, model):
        """Attribute one reservation and atomically reject excess run spend."""
        charged = db.execute(
            'SELECT charged FROM ai_charges WHERE id=?', (key,)
        ).fetchone()[0]
        self.check_run_allowance(db, charged)
        super().record_model(db, key, model)
        db.execute('INSERT INTO diagnostic_charges VALUES (?,?)', (key, self.run_id))

    def check_run_allowance(self, db, added):
        """Refuse a new charge or repricing that exceeds the same run ceiling."""
        previous = db.execute(
            'SELECT COALESCE(SUM(c.charged),0) FROM ai_charges c '
            'JOIN diagnostic_charges d ON c.id=d.charge_id WHERE d.run_id=?',
            (self.run_id,),
        ).fetchone()[0]
        if previous + added > self.run_cap:
            raise BudgetError('The diagnostic run allowance has been reached.')


def install_run_budget(budget, run_id, cap):
    """Tighten a private ledger before any trial can reserve a funded call."""
    if type(budget) is not AdvisorDailyBudget or not 0 < cap <= 10 * NANO:
        raise ValueError('Use the reviewed diagnostic budget with a cap up to $10.')
    with budget.db() as db:
        db.execute('CREATE TABLE IF NOT EXISTS diagnostic_charges ('
                   'charge_id TEXT PRIMARY KEY, run_id TEXT NOT NULL)')
        db.execute('CREATE INDEX IF NOT EXISTS diagnostic_charge_run ON diagnostic_charges(run_id)')
    budget.__class__ = DiagnosticBudget
    budget.run_id = run_id
    budget.run_cap = cap
    budget.finish_admitted_turn = False


def digest(payload):
    """Hash a JSON value for an observed runtime or fixture identity."""
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def corpus_cases():
    """Read local case inputs and hash their complete immutable source lines."""
    rows = {}
    for source in sorted((HERE / 'cases').glob('*.jsonl')):
        for line in source.read_bytes().splitlines():
            row = json.loads(line)
            if row['id'] in rows:
                raise ValueError('Duplicate case ID.')
            rows[row['id']] = (row, hashlib.sha256(line).hexdigest())
    return rows


def identity(flow, model):
    """Record local source and effective evidence hashes, without attestation."""
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO, check=True,
                              capture_output=True, text=True, timeout=10).stdout.strip()
    runtime_files = [path for path in ADVISOR.glob('*') if path.suffix in {'.py', '.json'}]
    runtime_files += list((ADVISOR / 'web').glob('*.json'))
    runtime_files += [Path(__file__), HERE / 'adapter_cases.py', *sorted(HERE.glob('starts_*.py'))]
    profile_contract, design = _load_contract()
    return {'revision': revision, 'sourceDigest': digest({
                str(path.relative_to(REPO)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in runtime_files}),
            'evidenceDigest': digest({'facts': flow.facts, 'ownerRules': flow.rule_facts,
                                     'profileContract': profile_contract['content_sha256'],
                                     'questionDesign': digest(design)}),
            'requestedModel': model,
            'runtime': 'local-advisor-first',
            'releaseEligible': False,
            'releaseBlockers': ['No signed runtime identity or immutable provider revision.',
                                'Executable coverage is limited to the reviewed typed starts.',
                                'Live judge scoring and matched baseline are unavailable.']}


def turn(flow, owner, state, action, **permissions):
    """Submit a normal advisor turn with a fresh request ID and current binding."""
    turn_id = str(uuid4())
    payload = {key: state[key] for key in ('guide', 'record', 'continuation') if key in state}
    return turn_id, flow.turn(owner, {**payload, **permissions, 'requestId': turn_id, 'action': action})


def seed(flow, owner, start, module=None):
    """Create a clean signed visit and apply typed, no-AI setup actions."""
    guide, record = flow.initial()
    _, state = turn(flow, owner, {'guide': guide, 'record': record}, {'type': 'start'})
    for action in start['setup']:
        _, state = turn(flow, owner, state, action)
    if module and hasattr(module, 'prepare_state'):
        state = module.prepare_state(flow, owner, state, start)
    for key, expected in start.get('reports', {}).items():
        actual = state['record']['facts'].get(key, {}).get('value')
        if actual != expected:
            raise ValueError(f'The advisor did not record the required {key} report.')
    for field, expected in start['fields'].items():
        if flow.value(state['guide'], field) != expected:
            raise ValueError('The advisor did not record the required starting fact.')
    if state['record']['facts'].get('RC01', {}).get('value', {}).get('choice') != start.get('relationship', 'self'):
        raise ValueError('The required relationship report did not persist.')
    actual_question = (state['assessment'].get('nextQuestion') or {}).get('id')
    if start.get('question') and actual_question != start['question']:
        raise ValueError('The required starting question is not active.')
    chain = state['continuation'].split('.')[0]
    for user, reply, question in start['history']:
        flow.memory.remember(owner, chain, CONTEXT_POLICY, user, reply, question)
    if module and hasattr(module, 'verify_start'):
        module.verify_start(flow, state, start)
    return state


def trial(service, case, line_hash, start, repetition, model, module=None):
    """Observe one trial in an independent visit, preserving explicit errors."""
    flow = service.adaptive
    owner = secrets.token_hex(32)
    result = {'caseId': case['id'], 'rawLineHash': line_hash, 'trial': repetition,
              'startingFixtureDigest': digest(start)}
    try:
        state = seed(flow, owner, start, module)
        if find_identifiers(case['user_prompt']):
            raise ValueError('Sensitive identifier in fixture.')
        extra = module.prepare_trial(service, owner, state, start) if module and hasattr(module, 'prepare_trial') else {}
        turn_id, out = turn(flow, owner, state, {'type': 'message', 'message': case['user_prompt']},
                            model=model, aiProvider=MODELS[model].provider, aiConsent=True,
                            contextPolicy=CONTEXT_POLICY, **extra)
        trace = service.turn_traces.get(turn_id, owner)
        if trace:
            # The file's owner hash indexes trace access and is not an observation.
            trace.pop('owner', None)
            trace.pop('error', None)
            for call in trace.get('modelCalls', []):
                call.pop('error', None)
        if trace:
            trace['advisorSources'] = (out.get('advisor') or {}).get('sources', [])
        if trace and module and hasattr(module, 'observe_state'):
            trace['caseStateCheck'] = module.observe_state(flow, owner, out, start)
        if trace and ('postFields' in start or 'postReports' in start):
            trace['profileChecks'] = {
                'fields': {k: {'expected': v, 'actual': flow.value(out['guide'], k)}
                           for k, v in start.get('postFields', {}).items()},
                'reports': {k: {'expected': v, 'actual': out['record']['facts'].get(k, {}).get('value')}
                            for k, v in start.get('postReports', {}).items()}}
        valid_start = not module or not hasattr(module, 'verify_observation') or module.verify_observation(trace, start)
        calls = trace.get('modelCalls', []) if trace else []
        generated = out.get('generated') or {}
        observed = any(call.get('kind') == 'compose' and call.get('status') == 'ok'
                       and call.get('request') and call.get('providerStatus') == 'completed'
                       and call.get('response', {}).get('model') == model for call in calls)
        return {**result, 'turnId': turn_id, 'reply': out.get('reply'),
                'nextQuestion': (out.get('assessment') or {}).get('nextQuestion'),
                'trace': trace,
                'status': 'observed' if observed and valid_start and out.get('reply')
                and generated.get('status') == 'complete' else 'incomplete'}
    except (ValueError, RuntimeError, KeyError, OSError) as error:
        return {**result, 'status': 'error', 'errorType': type(error).__name__}
    finally:
        flow.forget_owner(owner)


def main(argv=None):
    """Preview the selected cases or write a private live diagnostic report."""
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--case', action='append')
    selection.add_argument('--available-validation', action='store_true',
                           help='Run only executable validation cases and report uncovered IDs in preflight.')
    parser.add_argument('--trials', type=int, default=2)
    parser.add_argument('--cap-cents', type=int, default=1000)
    parser.add_argument('--model', default='gpt-6.1-sol', choices=sorted(MODELS))
    parser.add_argument('--owner-authorized-live', action='store_true',
                        help='Run actual API trials only for an explicitly owner-requested run.')
    args = parser.parse_args(argv)
    cases = corpus_cases()
    import starts_conversation, starts_facts, starts_tools
    starts = dict(STARTS)
    modules = {}
    for module in (starts_conversation, starts_facts, starts_tools):
        for key, binding in module.build_starts(cases).items():
            starts[key] = binding
            modules[key] = module
    if args.available_validation:
        heldout = [key for key, (case, _) in cases.items() if case['split'] == 'heldout']
        args.case = [key for key in heldout if key in starts]
        print(json.dumps({'validationCases': len(heldout), 'executable': len(args.case),
                          'unbound': [key for key in heldout if key not in starts]}), flush=True)
    if not 1 <= args.trials <= 10 or not 1 <= args.cap_cents <= 1000:
        parser.error('Use 1 to 10 trials and a cap of 1 to 1000 cents.')
    if len(set(args.case)) != len(args.case) or any(case not in cases for case in args.case):
        parser.error('Select known, distinct case IDs.')
    missing = sorted(set(args.case) - starts.keys())
    if missing:
        parser.error('Cases lack an executable starting state: ' + ', '.join(missing))
    if any(cases[key][1] != starts[key]['lineHash'] for key in args.case):
        parser.error('An executable case changed since its starting state was bound.')
    if not args.owner_authorized_live:
        print(json.dumps({'kind': 'live_turn_preview', 'caseIds': args.case,
                          'trials': args.trials, 'capCents': args.cap_cents}))
        return 0

    try:
        _load_contract()
    except ValueError:
        parser.error('The sealed advisor profile contract or one of its bound sources is unavailable. '
                     'See LIVE_ADAPTER.md for local provisioning.')
    STORE.mkdir(mode=0o700, parents=True, exist_ok=True)
    if STORE.is_symlink() or STORE.stat().st_mode & 0o077:
        raise ValueError('Use a private diagnostic directory.')
    budget_file = STORE / 'usage.sqlite3'
    if budget_file.is_symlink() or (budget_file.exists() and
            (not budget_file.is_file() or budget_file.stat().st_mode & 0o077)):
        raise ValueError('Use a private diagnostic usage ledger.')
    started = datetime.now(timezone.utc).isoformat()
    run_id = str(uuid4())
    with TemporaryDirectory(prefix='trial-', dir=STORE) as directory:
        scratch = Path(directory)
        with build(port=0, database=scratch / 'profiles.sqlite3', turn_traces=scratch / 'traces',
                   diagnostic_budget=budget_file) as service:
            install_run_budget(service.budget, run_id, args.cap_cents * (NANO // 100))
            metadata = identity(service.adaptive, args.model)
            rows = []
            # Retain completed turns across interruptions, separately from importable completed batches.
            journal_dir = STORE / 'progress'
            journal_dir.mkdir(mode=0o700, exist_ok=True)
            manifest = {'runId': run_id, 'requestedCaseIds': args.case, 'trialsPerCase': args.trials,
                        'unbound': [key for key in heldout if key not in starts] if args.available_validation else []}
            with (journal_dir / (run_id + '.manifest')).open('x') as handle:
                json.dump(manifest, handle)
            with (journal_dir / (run_id + '.jsonl')).open('x') as handle:
                for key in args.case:
                    for n in range(1, args.trials + 1):
                        row = trial(service, *cases[key], starts[key], n, args.model, modules.get(key))
                        rows.append(row)
                        handle.write(json.dumps(row) + '\n')
                        handle.flush()
                        os.fsync(handle.fileno())
                    print(f'{len(rows)} trials captured; last case {key}', flush=True)
            with service.budget.db() as db:
                accounted, measured = db.execute(
                    'SELECT COALESCE(SUM(c.charged),0), COALESCE(SUM(c.measured),0) FROM ai_charges c '
                    'JOIN diagnostic_charges d ON c.id=d.charge_id WHERE d.run_id=?',
                    (run_id,),
                ).fetchone()
    output = STORE / f'live-observation-{run_id}.json'
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as handle:
        json.dump({'schemaVersion': 1, 'kind': 'live_turn_observations', 'runId': run_id,
                   'identity': metadata, 'capCents': args.cap_cents, 'trials': rows,
                   'startedAt': started, 'completedAt': datetime.now(timezone.utc).isoformat(),
                   'accountedNanoUsd': accounted, 'measuredNanoUsd': measured}, handle)
    print(output)
    return 1 if any(row['status'] != 'observed' for row in rows) else 0


if __name__ == '__main__':
    raise SystemExit(main())
