"""Disposable mocked interaction proof; never calls a model or uses live profiles."""
from pathlib import Path
import copy
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'alternatives/advisor-first'))
from server import build

temporary = Path('/tmp/daylight-advisor-engagement-20261102')
temporary.mkdir(exist_ok=True, mode=0o700)
temporary.chmod(0o700)
app = build(8916, fixture=True, database=temporary / 'preview.sqlite3')
original = app.adaptive.turn


def preview_turn(owner, payload):
    action = payload.get('action', {})
    if action.get('type') == 'message':
        time.sleep(8)
        if action.get('message') == 'SIMULATED SEND FAILURE':
            raise ValueError('Simulated connection failure for disposable UI testing.')
    result = original(owner, payload)
    if ((action.get('type') == 'read_concept' and action.get('id') == 'routesintro')
            or action.get('message') == 'I turn 65 in November and want to understand my options.'):
        result['reply'] = ''
        result['facts'] = [copy.deepcopy(app.adaptive.facts['routesintro'])]
        result['generated'] = {'status': 'complete'}
        result.setdefault('advisor', {}).update(teachingFactIds=['routesintro'], educationFollowups=[
            'How does prescription coverage work with each path?',
            'How would I compare the costs?',
        ])
    return result


app.adaptive.turn = preview_turn
print('Mocked interaction preview at http://127.0.0.1:8916/', flush=True)
try:
    app.serve_forever()
finally:
    app.server_close()
