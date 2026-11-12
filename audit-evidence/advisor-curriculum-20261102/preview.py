"""Disposable UI preview replaying the exact accepted attempt-5 model outputs.

Run this file with the infrastructure Python, then open http://127.0.0.1:8897/.
Use the captured opening exactly, then select Through a current job and Send.
The real controller/frontend run over temporary profiles and a temporary budget
ledger. The only model transport is the three-stage local replay below: there
is no provider request, real API key, or persistent customer profile access.
"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import threading


REPO = Path(__file__).resolve().parents[2]
HERE = REPO / 'alternatives/advisor-first'
CAPTURE = Path(__file__).resolve().parent / 'attempt-5'
sys.path.insert(0, str(HERE))

import server
from advisor_budget import AdvisorDailyBudget
from chat import ResponsesClient


def replay_transport():
    stages = []
    for filename, schema_name in (
        ('self-1-interpretation.json', 'daylight_guide_commands'),
        ('self-1-composition.json', 'daylight_resolved_conversation'),
        ('self-2-composition.json', 'daylight_resolved_conversation'),
    ):
        captured = json.loads((CAPTURE / filename).read_text())
        if not captured['accepted']:
            raise ValueError('Only accepted captured outputs belong in this preview.')
        message = captured.get('message') or captured.get('context', {}).get('current_message')
        stages.append((schema_name, message, captured['raw']))
    index = 0
    lock = threading.Lock()

    def transport(payload):
        nonlocal index
        with lock:
            if index >= len(stages):
                raise AssertionError('This disposable preview permits exactly three replayed stages.')
            expected_schema, expected_message, raw = stages[index]
            if payload['text']['format']['name'] != expected_schema:
                raise AssertionError('The preview received an unexpected model stage.')
            sent = json.loads(payload['input'][0]['content'])
            actual_message = (sent['submitted_text'] if expected_schema == 'daylight_guide_commands'
                              else sent['resolved_context']['current_message'])
            if actual_message != expected_message:
                raise AssertionError('Use the exact captured fictional opening and current-job answer.')
            index += 1
            print('Replayed captured model stage ' + str(index) + '/3.', flush=True)
            return {'status': 'completed', 'model': 'gpt-5.4', 'service_tier': 'default',
                    'usage': {'input_tokens': 300, 'output_tokens': 70, 'total_tokens': 370,
                              'input_tokens_details': {'cached_tokens': 0}},
                    'output': [{'content': [{'type': 'output_text',
                                             'text': json.dumps(copy.deepcopy(raw))}]}]}

    return transport


def main():
    with tempfile.TemporaryDirectory(prefix='daylight-curriculum-exact-ui-') as directory:
        temporary = Path(directory)
        client = ResponsesClient(key='synthetic-replay-only', model='gpt-5.4',
                                 transport=replay_transport())
        app = server.make_server(8897, database=temporary / 'profiles.sqlite3',
            budget_database=temporary / 'budget.sqlite3', web=HERE / 'web',
            client=client, enable_live=True, live_limit=None,
            count_tokens=lambda _client, _payload: 1000,
            cookie_namespace='daylight_curriculum_exact_preview',
            ui_config={'mockAI': False, 'advisorFirst': True, 'variant': 'D86'},
            conversation_class=server.ChatConversation,
            profile_gate_class=server.ProfileReadiness,
            adaptive_class=server.NaturalConversation)
        AdvisorDailyBudget.adopt(app.budget, policy_path=HERE / 'budget-policy.json')
        print('Exact captured fictional UI replay: http://127.0.0.1:8897/; '
              'three local model stages; disposable profiles and ledger; no paid calls.', flush=True)
        try:
            app.serve_forever()
        finally:
            app.server_close()


if __name__ == '__main__':
    main()
