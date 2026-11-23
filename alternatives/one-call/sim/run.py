"""Drive a conversation flow with a simulated person and record what happened.

The harness talks to any flow through `flow.turn(owner, payload)`, the same
entry point the web server uses, so the two-call loop and the one-call loop are
run and graded the same way. It sends typed messages only.

Offline by default. The command line refuses to start unless an offline model
or flow is supplied, or `--live` is given with the owner's clearance and a call
limit. Without `--live` every turn runs with outbound network calls blocked.
Nothing here logs conversation content: progress lines carry counts and ids only.
"""
from __future__ import annotations

import argparse
import copy
from contextlib import contextmanager
import importlib
import importlib.util
import inspect
import json
from pathlib import Path
import socket
import sys
import time
import uuid
from unittest.mock import patch

if __package__ in (None, ''):                      # `python3 sim/run.py` from the variant folder
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sim import graders                            # noqa: E402
from sim.person import (CLEARANCE_MESSAGE, FACT_TARGETS, ModelPerson, ScriptedPerson, load_profiles,  # noqa: E402
                        read_question, require_clearance)

VERSION = 'sim-run-1'
RECOGNISED_ENDS = ('plans_handoff', 'finish')
# Model requests per typed turn, as (fewest, most). Estimates for budgeting only.
# two-call: read + reply, plus at most one recovery attempt (advisor-first AGENTS.md, D90).
# one-call: one reply request, at most one more after tools, plus the background
# record pass (CONTRACT.md, one_call_agent and one_call_reconcile).
CALLS_PER_TURN = {'two-call': (2, 3), 'one-call': (2, 3)}
# Requests a turn makes after its response is returned, so the response cannot report them.
BACKGROUND_CALLS = {'two-call': 0, 'one-call': 1}
TYPICAL_TURNS = 12


class Refused(Exception):
    """The command line will not start this run."""


class CallLimit(Exception):
    """The run reached the model-call limit the owner set."""


# ---------------------------------------------------------------------------
# Network guard
# ---------------------------------------------------------------------------

def _no_network(*args, **kwargs):
    raise AssertionError('Network is blocked in an offline simulated run.')


@contextmanager
def offline_network():
    """Fail closed if anything tries to open a connection."""
    with patch.object(socket, 'create_connection', _no_network), \
         patch.object(socket, 'getaddrinfo', _no_network), \
         patch.object(socket.socket, 'connect', _no_network), \
         patch.object(socket.socket, 'connect_ex', _no_network):
        yield


# ---------------------------------------------------------------------------
# Reading a response
# ---------------------------------------------------------------------------

def next_question(out):
    """The question this response puts to the person, or None."""
    assessment = out.get('assessment') or {}
    asked = read_question(assessment.get('nextQuestion'))
    if asked:
        return asked
    check = (out.get('conversationCheck') or {}).get('question')
    asked = read_question(check)
    if asked:
        return asked
    move = out.get('conversationNext') or {}
    if move.get('kind') == 'clarification':
        return read_question(move.get('question'))
    return None


def plans_handed_off(out):
    """Plans are ready and this response delivered the closing or the hand-off to them."""
    if not (out.get('planReadiness') or {}).get('canReview'):
        return False
    move = out.get('conversationNext') or {}
    if move.get('kind') == 'action' and move.get('action') == 'plan_review':
        return True
    if (out.get('comparisonClose') or {}).get('show'):
        return True
    return any(isinstance(card, dict) and card.get('kind') == 'plans_ready' for card in out.get('cards') or [])


def _first_number(*values):
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, list):
            return len(value)
    return None


def model_requests(out):
    """Model requests this turn made, when the response says."""
    metrics = out.get('metrics') or {}
    one = metrics.get('oneCall') if isinstance(metrics.get('oneCall'), dict) else {}
    return _first_number(metrics.get('llmCalls'), metrics.get('requests'), one.get('requests'),
                         metrics.get('modelRequests'))


def rejected_replies(out):
    """Reply blocks the check rejected this turn, when the response says."""
    metrics = out.get('metrics') or {}
    for holder in (metrics.get('oneCall'), metrics.get('check'), out.get('generated'), metrics):
        if isinstance(holder, dict):
            found = _first_number(holder.get('rejected'), holder.get('rejectedBlocks'), holder.get('checkRejected'))
            if found is not None:
                return found
    return None


def fact_ids(out):
    """Library fact ids this reply used, when the response exposes them."""
    found = []
    advisor = out.get('advisor') if isinstance(out.get('advisor'), dict) else {}
    for identifier in advisor.get('teachingFactIds') or []:
        found.append(str(identifier))
    for fact in out.get('facts') or []:
        if isinstance(fact, dict) and fact.get('id'):
            found.append(str(fact['id']))
        elif isinstance(fact, str):
            found.append(fact)
    one = (out.get('metrics') or {}).get('oneCall')
    if isinstance(one, dict):
        found.extend(str(identifier) for identifier in one.get('factIds') or [])
    return list(dict.fromkeys(found))


def grounding_values(out):
    """Code-made values in this response that an amount or date in the reply may come from."""
    parts = []
    for key in ('cards', 'facts', 'enrollment', 'comparisonClose'):
        if out.get(key):
            parts.append({key: copy.deepcopy(out[key])})
    one = (out.get('metrics') or {}).get('oneCall')
    if isinstance(one, dict) and one.get('toolOutputs'):
        parts.append({'toolOutputs': copy.deepcopy(one['toolOutputs'])})
    return json.loads(json.dumps(parts, default=str))


def read_state(flow, owner, guide, record):
    """Saved profile values and states from `guide`/`record`.

    values: guide field path or question id -> saved value.
    states: question id -> state. Uses advisor-first's `profile_view` when the
    flow is one of its conversations, and the stored fields otherwise.
    """
    values, states = {}, {}
    for path, field in ((guide or {}).get('fields') or {}).items():
        if isinstance(field, dict) and field.get('status') != 'stale' and field.get('value') not in (None, '', [], {}):
            values[path] = copy.deepcopy(field['value'])
    for identifier, fact in ((record or {}).get('facts') or {}).items():
        if isinstance(fact, dict) and not fact.get('stale') and fact.get('value') not in (None, '', [], {}):
            values[identifier] = copy.deepcopy(fact['value'])
            states[identifier] = 'reported'
    for target in FACT_TARGETS.values():
        if any(_lookup(values, name) is not None for name in (*target['ids'], *target['paths'])):
            for identifier in target['ids']:
                states.setdefault(identifier, 'reported')
    if callable(getattr(flow, 'report', None)) and callable(getattr(flow, 'value', None)):
        try:
            records = sys.modules.get('conversation_records') or importlib.import_module('conversation_records')
            for row in records.profile_view(flow, owner, guide, record, None)['fields']:
                states[row['id']] = row['state']
                if row.get('value') not in (None, '', [], {}):
                    values.setdefault(row['id'], copy.deepcopy(row['value']))
        except Exception:                          # a flow without that view still has its stored fields
            pass
    return {'values': values, 'states': states}


def _lookup(values, name):
    if name.endswith('*'):
        return next((values[key] for key in sorted(values) if key.startswith(name[:-1])), None)
    return values.get(name)


def _context_policy(flow):
    policy = getattr(flow, 'CONTEXT_POLICY', None)
    if policy is None and 'natural_flow' in sys.modules:
        policy = getattr(sys.modules['natural_flow'], 'CONTEXT_POLICY', None)
    return policy


# ---------------------------------------------------------------------------
# One conversation
# ---------------------------------------------------------------------------

def _make_person(make_person, profile, seed):
    try:
        accepts_seed = 'seed' in inspect.signature(make_person).parameters
    except (TypeError, ValueError):
        accepts_seed = False
    return make_person(profile, seed=seed) if accepts_seed else make_person(profile)


def run_one(make_flow, make_person, profile, *, seed=0, max_turns=40, clock=time.monotonic):
    """One profile, one run. Returns the run record the graders read."""
    flow = make_flow()
    person = _make_person(make_person, profile, seed)
    owner = uuid.uuid4().hex
    guide, record = flow.initial() if callable(getattr(flow, 'initial', None)) else ({}, {})
    policy = _context_policy(flow)
    state = {'guide': guide, 'record': record, 'continuation': None}

    def send(action, consent):
        payload = {'guide': copy.deepcopy(state['guide']), 'record': copy.deepcopy(state['record']),
                   'action': action, 'requestId': str(uuid.uuid4()), 'aiConsent': consent}
        if policy is not None:
            payload['contextPolicy'] = policy
        if state['continuation']:
            payload['continuation'] = state['continuation']
        out = flow.turn(owner, payload)
        state['guide'], state['record'] = out.get('guide', state['guide']), out.get('record', state['record'])
        state['continuation'] = out.get('continuation', state['continuation'])
        return out

    turns, end, errors = [], 'max_turns', 0
    try:
        send({'type': 'start'}, False)
    except CallLimit:
        raise
    except Exception as caught:                    # a flow may not need a start action
        turns_error = {'type': type(caught).__name__, 'status': _status(caught)}
    else:
        turns_error = None
    text = person.opening()
    while text is not None and len(turns) < max_turns:
        said = dict(getattr(person, 'last', None) or {})
        started = clock()
        out, error = {}, None
        try:
            out = send({'type': 'message', 'message': text}, True)
        except CallLimit:
            end = 'call_limit'
            break
        except Exception as caught:                # recorded by type and status only, never by message
            error = {'type': type(caught).__name__, 'status': _status(caught)}
        seconds = round(clock() - started, 3)
        asked = None if error else next_question(out)
        saved = read_state(flow, owner, state['guide'], state['record'])
        move = out.get('conversationNext') or {}
        turns.append({
            'turn': len(turns) + 1, 'person': text, 'person_kind': said.get('kind'),
            'stated': list(said.get('stated') or []), 'answered': said.get('answered'),
            'reply': str(out.get('reply') or ''),
            'question': None if asked is None else {'id': asked['id'], 'text': asked['text']},
            'cards': [card.get('kind') for card in out.get('cards') or [] if isinstance(card, dict)],
            'fact_ids': fact_ids(out), 'grounding': grounding_values(out),
            'generated': (out.get('generated') or {}).get('status'),
            'can_review': bool((out.get('planReadiness') or {}).get('canReview')),
            'next': {'kind': move.get('kind'), 'action': move.get('action')},
            'seconds': seconds, 'model_requests': model_requests(out), 'rejected': rejected_replies(out),
            'reported': sorted(k for k, v in saved['states'].items() if v == 'reported'), 'error': error})
        if error:
            errors += 1
            if errors >= 2:
                end = 'error'
                break
        else:
            errors = 0
            if plans_handed_off(out):
                end = 'plans_handoff'
                break
            if move.get('kind') == 'finish':
                end = 'finish'
                break
        text = person.answer('' if error else out.get('reply') or '', asked)
        if text is None:
            end = 'person_stopped'
    final = read_state(flow, owner, state['guide'], state['record'])
    return {'version': VERSION, 'profile_id': profile['id'], 'corpus': profile.get('corpus'), 'seed': seed,
            'style': getattr(person, 'style', None), 'typist': profile.get('typist'),
            'person': type(person).__name__, 'turns': turns, 'end': end, 'start_error': turns_error,
            'final': {'guide': state['guide'], 'record': state['record'],
                      'values': final['values'], 'states': final['states']}}


def _status(caught):
    status = getattr(caught, 'status', getattr(caught, 'code', None))
    return status if isinstance(status, (int, str)) and len(str(status)) <= 60 else None


def run(make_flow, make_person, profiles, *, runs=1, max_turns=40, clock=time.monotonic):
    """Every profile, `runs` times each (seeds 0..runs-1). Returns {'runs': [...]}."""
    results = []
    for profile in profiles:
        for seed in range(runs):
            results.append(run_one(make_flow, make_person, profile, seed=seed, max_turns=max_turns, clock=clock))
    return {'version': VERSION, 'profiles': len(profiles), 'runs_per_profile': runs, 'max_turns': max_turns,
            'runs': results}


# ---------------------------------------------------------------------------
# Budget and estimate
# ---------------------------------------------------------------------------

def estimate_calls(profile_count, runs, loop, *, max_turns=40, model_person=False):
    """A range of model calls for a bake-off. An estimate, not a measurement."""
    low, high = CALLS_PER_TURN[loop]
    extra = 1 if model_person else 0
    conversations = profile_count * runs
    return {'conversations': conversations, 'calls_per_turn': [low + extra, high + extra],
            'typical_turns': min(TYPICAL_TURNS, max_turns), 'max_turns': max_turns,
            'per_conversation': [(low + extra) * min(TYPICAL_TURNS, max_turns), (high + extra) * max_turns],
            'total_typical': conversations * (low + extra) * min(TYPICAL_TURNS, max_turns),
            'total_max': conversations * (high + extra) * max_turns}


class LimitedFlow:
    """Stops a live bake-off before it can pass the owner's call limit."""

    def __init__(self, flow, counter, per_turn_max, unreported=0):
        self._flow, self._counter, self._per_turn_max, self._unreported = flow, counter, per_turn_max, unreported

    def __getattr__(self, name):
        return getattr(self._flow, name)

    def turn(self, owner, payload):
        typed = isinstance(payload, dict) and (payload.get('action') or {}).get('type') == 'message'
        if typed and self._counter['used'] + self._per_turn_max > self._counter['limit']:
            raise CallLimit()
        out = self._flow.turn(owner, payload)
        if typed:
            used = model_requests(out)
            self._counter['used'] += (self._per_turn_max if used is None
                                      else min(self._per_turn_max, used + self._unreported))
        return out


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def _load_object(spec):
    """'package.module:name' or '/path/file.py:name' -> the named object."""
    if ':' not in spec:
        raise Refused('Name the object as module:callable or path.py:callable.')
    location, name = spec.rsplit(':', 1)
    if location.endswith('.py'):
        module_spec = importlib.util.spec_from_file_location('sim_supplied_' + uuid.uuid4().hex, location)
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
    else:
        module = importlib.import_module(location)
    return getattr(module, name)


def scripted_flow(loop, transport):
    """The real conversation class for `loop`, wired to a scripted transport (no key, no network)."""
    import _paths
    from chat import ResponsesClient
    advisor = _paths.ADVISOR
    if loop == 'one-call':
        try:
            from one_call_flow import OneCallConversation as conversation
        except ImportError:
            raise Refused('The one-call conversation is not importable here. Name a flow with --flow-factory.') from None
    else:
        from natural_flow import NaturalConversation as conversation
    return conversation(None, None,
                        json.loads((advisor / 'web/guide-contract.json').read_text()),
                        json.loads((advisor / 'web/teaching-facts.json').read_text()),
                        json.loads((advisor / 'web/readiness-content.json').read_text()),
                        ResponsesClient(key='synthetic-offline-only', model='gpt-5.4', transport=transport),
                        True, None, fixture=False)


def parser():
    p = argparse.ArgumentParser(prog='python3 -m sim.run', description=__doc__.split('\n\n')[0])
    p.add_argument('--profiles', required=True, help='profiles.json, personas.json or the folder holding one')
    p.add_argument('--loop', required=True, choices=sorted(CALLS_PER_TURN))
    p.add_argument('--runs', type=int, default=1)
    p.add_argument('--out', required=True, help='folder for the per-run JSON files and the summary')
    p.add_argument('--only', default='', help='comma-separated profile ids')
    p.add_argument('--max-turns', type=int, default=40)
    p.add_argument('--patience', default='none',
                   help="'none' (answer until --max-turns), 'profile' (the profile's own stop rule) or a number of messages")
    p.add_argument('--scripted-model', help='offline: module:callable or path.py:callable, a transport(payload) -> response')
    p.add_argument('--flow-factory', help='module:callable returning a conversation flow (offline unless --live)')
    p.add_argument('--live', action='store_true', help='allow model calls; needs --clearance, --max-calls and --flow-factory')
    p.add_argument('--clearance', help='the owner\'s own clearance text for a live run')
    p.add_argument('--max-calls', type=int, help='live: the most model calls this run may make')
    p.add_argument('--person', choices=('scripted', 'model'), default='scripted')
    p.add_argument('--person-client', help='live, --person model: module:callable returning a client with .transport')
    return p


def check_start(args, profile_count):
    """Decide whether the run may start. Returns the call estimate for a live run, else None."""
    if args.runs < 1 or args.max_turns < 1:
        raise Refused('Use at least one run and one turn.')
    if not args.live:
        if args.clearance or args.max_calls or args.person == 'model' or args.person_client:
            raise Refused('Clearance, a call limit and a model-played person belong to a live run. Add --live or drop them.')
        if args.scripted_model and args.flow_factory:
            raise Refused('Choose one of --scripted-model and --flow-factory.')
        if not args.scripted_model and not args.flow_factory:
            raise Refused('Refusing to start: supply an offline model with --scripted-model (or an offline flow with '
                          '--flow-factory), or use --live with --clearance. ' + CLEARANCE_MESSAGE)
        return None
    try:
        require_clearance(args.clearance)
    except PermissionError as refused:
        raise Refused('Refusing a live run: ' + str(refused)) from None
    if args.scripted_model:
        raise Refused('Choose one: --scripted-model is offline, --live is not.')
    estimate = estimate_calls(profile_count, args.runs, args.loop, max_turns=args.max_turns,
                              model_person=args.person == 'model')
    print('Estimated model calls: about %d at %d turns a conversation, at most %d '
          '(%d conversations, %d to %d calls a typed turn, up to %d turns).' % (
              estimate['total_typical'], estimate['typical_turns'], estimate['total_max'], estimate['conversations'],
              estimate['calls_per_turn'][0], estimate['calls_per_turn'][1], estimate['max_turns']))
    if not args.max_calls or args.max_calls < 1:
        raise Refused('Refusing a live run: set the budget with --max-calls.')
    if not args.flow_factory:
        raise Refused('Refusing a live run: name the live flow with --flow-factory. This harness builds no live client.')
    if args.person == 'model' and not args.person_client:
        raise Refused('Refusing a live run: --person model needs --person-client.')
    return estimate


def _patience(value, profile):
    if value == 'none':
        return None
    if value == 'profile':
        return (profile.get('stop') or {}).get('max_messages')
    if str(value).isdigit() and int(value) > 0:
        return int(value)
    raise Refused("Use --patience none, profile or a number of messages.")


def _table(rows):
    head = ['profile', 'run', 'style', 'turns', 'end', 'accuracy', 'repeated questions', 'repeated teaching',
            'turns to plans', 'forbidden', 'no answer', 'wrong person', 'median s', 'max s']
    lines = ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    for row in rows:
        lines.append('| ' + ' | '.join('' if cell is None else str(cell) for cell in row) + ' |')
    return '\n'.join(lines)


def summary_markdown(result, grades, summary, *, loop, live):
    rows = []
    for one, grade in zip(result['runs'], grades):
        share = grade['profile_accuracy']['share']
        forbidden = grade['forbidden']
        rows.append([one['profile_id'], one['seed'], one['style'], len(one['turns']), one['end'],
                     '' if share is None else '%d%% (%d of %d)' % (round(share * 100), grade['profile_accuracy']['correct'],
                                                                 grade['profile_accuracy']['graded']),
                     grade['repeated_questions']['count'], grade['repeated_teaching']['count'], grade['turns_to_plans'],
                     forbidden['personal_pick'] + forbidden['identifier_request'] + forbidden['ungrounded'],
                     grade['no_answer_turns']['count'], grade['wrong_person']['count'] if grade['wrong_person']['applies'] else '',
                     grade['seconds']['median'], grade['seconds']['max']])
    unstable = [identifier for identifier, item in summary['variance']['per_profile'].items() if not item['consistent']]
    lines = ['# Simulated-person run: ' + loop, '',
             'Mode: ' + ('live (owner-cleared)' if live else 'offline (scripted model, network blocked)') + '.',
             '%d conversations: %d profiles, %d runs each.' % (len(result['runs']), result['profiles'], result['runs_per_profile']),
             '', _table(rows), '', '## Across runs', '',
             '- Profile accuracy (mean of runs with graded facts): ' + (
                 'n/a' if summary['profile_accuracy']['mean'] is None else '%d%%' % round(summary['profile_accuracy']['mean'] * 100)),
             '- Repeated questions: %d. Repeated teaching: %d.' % (summary['repeated_questions']['total'], summary['repeated_teaching']['total']),
             '- Reached plans: %d of %d (median turns %s).' % (summary['turns_to_plans']['reached'], summary['runs'], summary['turns_to_plans']['median']),
             '- Recognised finish: %d of %d.' % (summary['finish']['recognised'], summary['runs']),
             '- Forbidden content: %d. Turns with no answer: %d. Helper addressed as the covered person: %d.' % (
                 summary['forbidden']['total'], summary['no_answer_turns']['total'], summary['wrong_person']['total']),
             '- Turn time: median %s s, longest %s s.' % (summary['seconds']['median'], summary['seconds']['max']),
             '- Profiles whose runs ended differently (saved profile or finish): ' + (', '.join(unstable) or 'none') + '.',
             '', 'Several grades are approximations. Read `sim/README.md` before drawing conclusions.', '']
    return '\n'.join(lines)


def write_results(out_dir, result, grades, summary, *, loop, live, clearance=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for one, grade in zip(result['runs'], grades):
        (out_dir / ('%s-run%d.json' % (one['profile_id'], one['seed']))).write_text(
            json.dumps({'loop': loop, 'live': live, 'run': one, 'grade': grade}, indent=2, default=str) + '\n')
    (out_dir / 'summary.json').write_text(json.dumps(
        {'loop': loop, 'live': live, 'clearance': clearance, 'summary': summary}, indent=2, default=str) + '\n')
    (out_dir / 'summary.md').write_text(summary_markdown(result, grades, summary, loop=loop, live=live))
    return out_dir


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        profiles = load_profiles(args.profiles)
        if args.only:
            wanted = {item.strip() for item in args.only.split(',') if item.strip()}
            profiles = [profile for profile in profiles if profile['id'] in wanted]
        if not profiles:
            raise Refused('No profiles to run.')
        estimate = check_start(args, len(profiles))
        counter = {'used': 0, 'limit': args.max_calls or 0}
        if args.flow_factory:
            factory = _load_object(args.flow_factory)
        else:
            transport = _load_object(args.scripted_model)

            def factory():
                return scripted_flow(args.loop, transport)
        played = 1 if args.person == 'model' else 0
        per_turn_max = CALLS_PER_TURN[args.loop][1] + played

        def make_flow():
            flow = factory()
            return LimitedFlow(flow, counter, per_turn_max, BACKGROUND_CALLS[args.loop] + played) if args.live else flow

        if args.person == 'model':
            client = _load_object(args.person_client)()

            def make_person(profile, seed=0):
                return ModelPerson(profile, client, clearance=args.clearance, max_calls=args.max_turns, seed=seed)
        else:
            def make_person(profile, seed=0):
                return ScriptedPerson(profile, seed=seed, max_messages=_patience(args.patience, profile))

        by_id = {profile['id']: profile for profile in profiles}
        if args.live:
            result = run(make_flow, make_person, profiles, runs=args.runs, max_turns=args.max_turns)
        else:
            with offline_network():
                result = run(make_flow, make_person, profiles, runs=args.runs, max_turns=args.max_turns)
    except Refused as refused:
        print(str(refused), file=sys.stderr)
        return 2
    grades = [graders.grade(one, by_id[one['profile_id']]) for one in result['runs']]
    summary = graders.summary(grades)
    if estimate is not None:
        summary['model_calls'] = {'estimate': estimate, 'limit': counter['limit'], 'counted': counter['used']}
    folder = write_results(args.out, result, grades, summary, loop=args.loop, live=args.live,
                           clearance=args.clearance if args.live else None)
    print('Wrote %d run files and the summary to %s' % (len(result['runs']), folder))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
