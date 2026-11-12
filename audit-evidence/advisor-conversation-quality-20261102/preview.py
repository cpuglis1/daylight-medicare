"""Replay an accepted fictional seven-turn trace through the real UI/controller.

Usage after a technically complete, source-stable live attempt:
  python3 preview.py --capture live-attempts/20261102T...-... --check
  python3 preview.py --capture live-attempts/20261102T...-... --port 8897

Open the printed loopback URL in a fresh tab. Get started, then deliberately Send
the seven exact messages printed by --check. Resize that same visit for desktop,
tablet and phone inspection. One sequential visit at a time; restart this process
for a new visit. Ctrl-C closes only this disposable server and removes its stores.

The source HTML/CSS/JavaScript and NaturalConversation controller are unchanged.
Provider stages are local captured responses; outgoing sockets are disabled.
Temporary token usage/ledger entries are explicitly synthetic plumbing fixtures,
never provider cost/latency evidence. This is not new model-quality evidence.
"""
import argparse
import copy
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
from unittest.mock import patch

PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[1]
VARIANT = ROOT / 'alternatives/advisor-first'
SCHEMAS = ('daylight_guide_commands', 'daylight_resolved_conversation')
PROTECTED_PORTS = {8890, 8891, 8893, 8896}


def check_sources(expected):
    """Bind UI/controller source to the checked live build, including its lock."""
    for name, digest in expected.items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(VARIANT):
            continue
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('The captured runtime source no longer matches: ' + name)


def load_capture(path):
    path = (PACKET / path).resolve() if not path.is_absolute() else path.resolve()
    if path.parent != (PACKET / 'live-attempts').resolve():
        raise ValueError('Use a new fictional live-attempt directory in this packet.')
    result = json.loads((path / 'result.json').read_text())
    required = {'fictional_inputs': True, 'saved_profile': False,
                'automatic_retries': False, 'fresh_uninterrupted_visit': True,
                'prefix_replay': False, 'technical_complete': True, 'source_unchanged': True}
    if any(result.get(key) is not value for key, value in required.items()):
        raise ValueError('Preview requires a complete, fresh, unsaved, source-stable fictional run.')
    rows = result.get('turns', [])
    if len(rows) != 7 or [row.get('turn') for row in rows] != list(range(1, 8)):
        raise ValueError('Use the complete seven-turn trace, not a reconstructed prefix.')
    manifest = json.loads((path / 'run-build.json').read_text())
    expected = manifest['before_sha256']
    if expected != manifest['after_sha256']:
        raise ValueError('The capture spans changed sources.')
    check_sources(expected)
    stages, messages = [], []
    for row in rows:
        if (row.get('generated', {}).get('status') != 'complete'
                or not row.get('technical_checks') or not all(row['technical_checks'].values())
                or row.get('action', {}).get('type') != 'message'):
            raise ValueError('Each captured turn must have completed its technical checks.')
        text = row['action']['message']
        messages.append(text)
        for suffix, schema in zip(('interpretation', 'composition'), SCHEMAS):
            captured = json.loads((path / f"turn-{row['turn']}-{suffix}.json").read_text())
            message = captured.get('message') if suffix == 'interpretation' else captured.get('resolved_context', {}).get('current_message')
            if (message != text or 'error' in captured
                    or not isinstance(captured.get('raw_proposal'), dict)
                    or not isinstance(captured.get('validated'), dict)):
                raise ValueError('Every replay stage needs an accepted raw capture for the exact message.')
            stages.append({'schema': schema, 'message': text,
                           'raw': copy.deepcopy(captured['raw_proposal'])})
    return {'source': str(path), 'stages': stages, 'messages': messages,
            'source_hashes': expected, 'quality_pass': result.get('quality_pass')}


class CapturedTransport:
    """A single ordered capture; mismatches do not consume the next stage."""
    def __init__(self, stages, check_source=None):
        self.stages = copy.deepcopy(stages)
        self.index = 0
        self.lock = threading.Lock()
        self.check_source = check_source or (lambda: None)

    def __call__(self, payload):
        with self.lock:
            self.check_source()
            if self.index >= len(self.stages):
                raise AssertionError('Captured visit finished. Restart the preview for a fresh visit.')
            stage = self.stages[self.index]
            schema = payload['text']['format']['name']
            sent = json.loads(payload['input'][0]['content'])
            text = sent.get('submitted_text') if schema == SCHEMAS[0] else sent.get('resolved_context', {}).get('current_message')
            if schema != stage['schema'] or text != stage['message']:
                raise AssertionError('Use the exact next captured message and deliberate Send; no substitute response was generated.')
            self.index += 1
            print(f'Local captured stage {self.index}/{len(self.stages)}; synthetic preview usage only.', flush=True)
            return {'status': 'completed', 'model': 'gpt-5.4', 'service_tier': 'default',
                    'usage': {'input_tokens': 1000, 'output_tokens': 70, 'total_tokens': 1070,
                              'input_tokens_details': {'cached_tokens': 0}},
                    'output': [{'content': [{'type': 'output_text',
                                             'text': json.dumps(stage['raw'])}]}]}


def forbid_outbound(*args, **kwargs):
    raise AssertionError('Outbound connections are forbidden in this local replay preview.')


def serve(capture, port):
    if port in PROTECTED_PORTS or not 0 <= port <= 65535:
        raise ValueError('Use port 0 or an unused preview port, never a protected app port.')
    sys.path.insert(0, str(VARIANT))
    import server
    from advisor_budget import AdvisorDailyBudget
    from chat import ResponsesClient
    check_sources(capture['source_hashes'])
    policy = json.loads((VARIANT / 'model-policy.json').read_text())
    transport = CapturedTransport(capture['stages'], lambda: check_sources(capture['source_hashes']))
    with tempfile.TemporaryDirectory(prefix='daylight-quality-ui-') as directory, ExitStack() as guards:
        temporary = Path(directory)
        # No .env loader, real key, customer database or shared budget is used.
        client = ResponsesClient(key='synthetic-capture-preview', model='gpt-5.4', transport=transport)
        app = server.make_server(port, database=temporary / 'profiles.sqlite3',
            budget_database=temporary / 'budget.sqlite3', web=VARIANT / 'web',
            client=client, enable_live=True, live_limit=None,
            count_tokens=lambda _client, _payload: 1000,
            cookie_namespace='daylight_quality_capture_preview',
            ui_config={'mockAI': False, 'advisorFirst': True, 'variant': 'D86', 'modelPolicy': policy},
            conversation_class=server.ChatConversation,
            profile_gate_class=server.ProfileReadiness,
            adaptive_class=server.NaturalConversation)
        try:
            AdvisorDailyBudget.adopt(app.budget, policy_path=VARIANT / 'budget-policy.json')
            app.adaptive.agent.reasoning_effort = policy['reasoning_effort']
            app.adaptive.agent.composition_reasoning_effort = policy.get('composition_reasoning_effort', 'none')
            # Only inbound browser traffic is needed. Keep all model/token paths
            # network-forbidden even if a future adapter ignores the transport.
            guards.enter_context(patch.object(socket, 'create_connection', forbid_outbound))
            guards.enter_context(patch.object(socket.socket, 'connect', forbid_outbound))
            guards.enter_context(patch.object(socket.socket, 'connect_ex', forbid_outbound))
            print(json.dumps({'url': f'http://127.0.0.1:{app.server_port}/',
                              'captured_visit': capture['source'], 'provider_calls': 0,
                              'stores': 'disposable guest and synthetic budget databases',
                              'quality_pass_from_live_capture': capture['quality_pass'],
                              'stop': 'Ctrl-C; only this preview server is stopped and temporary stores removed.'}), flush=True)
            app.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            app.server_close()


def self_test():
    """Controlled transport fixtures only; no server, model, account or ledger."""
    def request(schema, text):
        body = {'submitted_text': text} if schema == SCHEMAS[0] else {'resolved_context': {'current_message': text}}
        return {'text': {'format': {'name': schema}}, 'input': [{'content': json.dumps(body)}]}
    original = {'updates': []}
    stages = [{'schema': SCHEMAS[0], 'message': 'fictional opening', 'raw': original},
              {'schema': SCHEMAS[1], 'message': 'fictional opening', 'raw': {'reply': 'scripted response'}}]
    replay = CapturedTransport(stages)
    original['updates'].append('changed outside replay')
    first = replay(request(SCHEMAS[0], 'fictional opening'))
    assert json.loads(first['output'][0]['content'][0]['text']) == {'updates': []}
    try:
        replay(request(SCHEMAS[1], 'invented different text'))
        raise AssertionError('A mismatched message was accepted.')
    except AssertionError as error:
        assert 'exact next' in str(error)
    assert replay.index == 1
    replay(request(SCHEMAS[1], 'fictional opening'))
    try:
        replay(request(SCHEMAS[0], 'fictional opening'))
        raise AssertionError('An extra stage was accepted.')
    except AssertionError as error:
        assert 'finished' in str(error)
    assert replay.index == 2
    try:
        forbid_outbound()
        raise AssertionError('An outbound connection was accepted.')
    except AssertionError as error:
        assert 'forbidden' in str(error)
    print(json.dumps({'controlled_fixture_checks': ['copy isolation', 'exact stage/message binding',
        'mismatch does not consume stage', 'bounded stage exhaustion', 'outbound refusal'],
        'passed': True, 'server_started': False, 'provider_calls': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, help='Successful new live-attempt directory; absolute or relative to this packet.')
    parser.add_argument('--port', type=int, default=8897)
    parser.add_argument('--check', action='store_true', help='Validate exact captures/source and print messages; no server starts.')
    parser.add_argument('--self-test', action='store_true', help='Run controlled transport fixtures without a server/provider.')
    args = parser.parse_args()
    if args.self_test:
        if args.capture or args.check:
            parser.error('--self-test cannot be combined with a capture.')
        self_test()
    elif args.capture:
        captured = load_capture(args.capture)
        if args.check:
            print(json.dumps({key: captured[key] for key in ('source', 'messages', 'quality_pass')}, indent=2))
        else:
            serve(captured, args.port)
    else:
        parser.print_help()
