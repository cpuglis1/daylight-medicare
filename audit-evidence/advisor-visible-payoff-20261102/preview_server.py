"""Disposable UI fixture. Synthetic responses only; no model or live profile."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'alternatives/advisor-first'))
from server import build
temporary = Path('/tmp/daylight-visible-payoff-20261102')
temporary.mkdir(exist_ok=True, mode=0o700)
app = build(8918, fixture=True, database=temporary / 'preview.sqlite3')
original = app.adaptive.turn

def preview_turn(owner, payload):
    result = original(owner, payload)
    action = payload.get('action', {})
    if action.get('type') == 'message':
        result['reportedRows'] = [
            {'id':'S_AGE65','label':'65th birthday','value':'November 2026','status':'reported'},
            {'id':'T04','label':'Preferred coverage start','value':'January 2027','status':'reported'},
            {'id':'T03','label':'ZIP','value':'60614','status':'reported'},
            {'id':'T06','label':'Doctors','value':'none','status':'reported'},
            {'id':'T07','label':'Prescriptions','value':'none','status':'reported'},
        ]
        result['reply'] = 'That gives us a useful starting point. Here are the dates you shared so you can check that I understood them.'
        result['facts'] = []
        result['generated'] = {'status':'complete'}
        result.setdefault('advisor', {}).update(visual='none', teachingFactIds=[])
    return result

app.adaptive.turn = preview_turn
print('Disposable mocked UI at http://127.0.0.1:8918/', flush=True)
try:
    app.serve_forever()
finally:
    app.server_close()
