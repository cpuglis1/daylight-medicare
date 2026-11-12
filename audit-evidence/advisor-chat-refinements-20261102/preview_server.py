"""Disposable UI preview with a short simulated wait, never real AI."""
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'alternatives/advisor-first'))
from server import build

app = build(8916,fixture=True,database=Path('/tmp/daylight-chat-refinements-20261102/delayed.sqlite3'))
original = app.adaptive.turn
def delayed_turn(owner,payload):
    if payload.get('action',{}).get('type') == 'message':
        time.sleep(3)
    return original(owner,payload)
app.adaptive.turn = delayed_turn
print('Mocked UI preview at http://127.0.0.1:8916/',flush=True)
try:
    app.serve_forever()
finally:
    app.server_close()
