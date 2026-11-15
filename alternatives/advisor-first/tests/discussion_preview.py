"""Offline D166 visual QA server. Fictional scripted transport, ephemeral store.

Run from the repository with its Python environment. This is never a model
evaluation: only reviewed source sentences and scripted proposals are returned.
Outgoing socket connections are forbidden, including model and data transports.
"""
import json
from pathlib import Path
import socket
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import build
from chat import ResponsesClient
import conversation_planner as planner
import enrollment_flow
from demo_http import install


def transport(payload):
    sent = json.loads(payload['input'][0]['content'])
    if payload['text']['format']['name'] == 'daylight_guide_commands':
        text = sent['submitted_text']
        p = planner.conservative_request(text)
        value = {'updates': [], 'requests': [], 'fact_ids': [], 'situation_proposals': [],
                 'goal_quote': '', 'agenda': {'concerns': [], 'priorityReason': {}},
                 'education_request': {'kind': 'none', 'concept_ids': [], 'quote': ''}, 'discussion': p}
    else:
        ctx = sent['resolved_context']
        focus = ctx['discussion_plan']['focus']
        preferred = {'medigap': 'medigap', 'original': 'original', 'coverage_paths': 'routesintro', 'advantage': 'advantage'}.get(focus, 'costs')
        fact = next((e for e in ctx['evidence'] if e['id'] == preferred), None)
        move = next(iter(sent['question_candidates']), {})
        value = {'reply': fact['summary'] if fact else 'We can compare those options without choosing a path yet.',
                 'question_target': move.get('id'),
                 'question': move.get('question', {}).get('question', 'What would help you next?'),
                 'report_refs': [], 'evidence_refs': [fact['id']] if fact else [],
                 'education': {'purpose': 'advance', 'updates': [], 'visual': 'none'},
                 'agenda_update': {'current_concern': '', 'pause': False}}
    return {'status': 'completed', 'model': 'gpt-5.4', 'service_tier': 'default',
            'usage': {'input_tokens': 300, 'output_tokens': 70, 'total_tokens': 370,
                      'input_tokens_details': {'cached_tokens': 0}},
            'output': [{'content': [{'type': 'output_text', 'text': json.dumps(value)}]}]}


def forbidden(*args, **kwargs):
    raise AssertionError('Offline preview forbids outgoing network connections')


if __name__ == '__main__':
    socket.socket.connect = forbidden
    socket.create_connection = forbidden
    with tempfile.TemporaryDirectory(prefix='daylight-d166-preview-') as directory:
        server = build(0, fixture=True, database=Path(directory) / 'fictional.sqlite3',
            client=ResponsesClient(key='synthetic', model='gpt-5.4', transport=transport))
        server.adaptive.fixture = False
        server.adaptive.agent.enabled = True
        server.adaptive.model_agents = {'gpt-5.4': server.adaptive.agent}
        enrollment_flow.enable(server.adaptive)
        planner.enable(server.adaptive)
        install(server, binding={'database': 'fictional', 'snapshot_id': 'offline'}, fixture=True)
        print('Offline preview: http://127.0.0.1:%d' % server.server_port, flush=True)
        try:
            server.serve_forever()
        finally:
            server.server_close()
