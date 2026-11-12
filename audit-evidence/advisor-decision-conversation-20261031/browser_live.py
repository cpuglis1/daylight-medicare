"""Bounded fictional browser verification; isolated cookie and disposable profile.

At most seven paid stages, using the existing shared ledger and no automatic retry.
Responsive review routes are test-only iframe containers, not product UI.
"""
import argparse
import copy
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import uuid

PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[1]
VARIANT = ROOT / 'alternatives/advisor-first'
sys.path.insert(0, str(VARIANT))
import server

parser = argparse.ArgumentParser()
parser.add_argument('--resume-opening', type=Path)
parser.add_argument('--max-stages', type=int, default=7)
options = parser.parse_args()
opening = json.loads(options.resume_opening.read_text())[0] if options.resume_opening else None
if not 1 <= options.max_stages <= 7:
    raise ValueError('Use a maximum of seven stages per manual verification run.')

factory = server.make_server
def isolated(*args, **kwargs):
    kwargs['cookie_namespace'] = 'daylight_decision_conversation_live_test'
    return factory(*args, **kwargs)
server.make_server = isolated

receipts = []
turns = []
raw_responses = []
with tempfile.TemporaryDirectory(prefix='decision-browser-', dir=VARIANT/'var') as directory:
    app = server.build(8894, database=Path(directory)/'guides.sqlite3')
    reserve = app.adaptive.agent.reserve_turn
    turn = app.adaptive.turn
    complete = app.adaptive.agent._complete
    def captured_complete(payload, raw):
        response, text = complete(payload, raw)
        raw_responses.append({'schema':payload['text']['format']['name'],
                              'value':json.loads(text)})
        (PACKET/'raw-responses.json').write_text(json.dumps(raw_responses,indent=2)+'\n')
        return response, text
    def bounded_reserve(*args, **kwargs):
        stages = kwargs.get('stages', ('extract', 'compose'))
        if len(receipts) + len(stages) > options.max_stages:
            raise RuntimeError('The bounded browser verification allowance is complete.')
        reservation = reserve(*args, **kwargs)
        receipts.extend(stage.key for stage in reservation.stages.values())
        return reservation
    def captured_turn(*args, **kwargs):
        started = time.monotonic()
        out = turn(*args, **kwargs)
        action = (args[1] if len(args)>1 else kwargs.get('payload', {})).get('action', {})
        if action.get('type') in {'message', 'choice', 'stage'}:
            turns.append({'action': action, 'elapsedMs':round((time.monotonic()-started)*1000),
                          'response': out})
            (PACKET/'browser-live-turns.json').write_text(json.dumps(turns, indent=2)+'\n')
        return out
    app.adaptive.agent.reserve_turn = bounded_reserve
    app.adaptive.agent._complete = captured_complete
    app.adaptive.turn = captured_turn

    handler = app.RequestHandlerClass
    original_get = handler.do_GET
    original_headers = handler.headers_for
    review_mode = [False]
    def review_headers(self, code, mime, length=None, cookie=None):
        if not review_mode[0]:
            return original_headers(self, code, mime, length, cookie)
        # Only this disposable, loopback-only review server permits its own
        # product page inside the responsive test frame. Product CSP is intact.
        original_send = self.send_header
        def frame_header(name, value):
            if name == 'Content-Security-Policy':
                value = value.replace("frame-ancestors 'none'", "frame-ancestors 'self'")
            original_send(name, value)
        self.send_header = frame_header
        try:
            return original_headers(self, code, mime, length, cookie)
        finally:
            self.send_header = original_send
    handler.headers_for = review_headers
    def review_get(self):
        if self.path == '/api/conversation/initial' and review_mode[0] and (opening or turns):
            self.server.profiles.require(self.token())
            return self.respond(200, opening['response'] if opening else turns[0]['response'])
        if self.path == '/api/conversation/initial' and opening:
            app.profiles.require(self.token())
            owner = app.profiles.digest(self.token())
            seed = opening['response']
            out = app.adaptive.turn(owner, {'guide':copy.deepcopy(seed['guide']),
                'record':copy.deepcopy(seed['record']), 'action':{'type':'refresh'},
                'requestId':str(uuid.uuid4())})
            # Resume only the actual fictional prior exchange; no invented
            # facts/history and no repeated extraction or automatic retry.
            action=opening['action']
            previous_words=action.get('message')
            if previous_words is None:
                choices=dict(app.adaptive.question(action['id']).get('choices',[]))
                previous_words='; '.join(choices.get(value,value) for value in
                    action.get('fields',{}).get('choice','').split(',') if value)
            app.adaptive.remember_exchange(owner, previous_words, seed, 'natural-context-v2')
            return self.respond(200, out)
        if self.path not in {'/__review/phone', '/__review/tablet'}:
            return original_get(self)
        review_mode[0] = True
        width, height = (390, 844) if self.path.endswith('phone') else (820, 1000)
        page = ('<!doctype html><meta name="viewport" content="width=device-width">'
                '<title>Daylight responsive review</title>'
                '<body style="margin:0;background:#eee">'
                f'<iframe title="Daylight {width}px review" src="/" width="{width}" '
                f'height="{height}" style="border:0;display:block"></iframe></body>')
        data = page.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    handler.do_GET = review_get

    print(f'Isolated {options.max_stages}-stage real-model review: http://127.0.0.1:8894/', flush=True)
    try:
        app.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        ledger = ROOT/'cms-slice/var/ai-budget/usage.sqlite3'
        with sqlite3.connect(ledger.as_uri()+'?mode=ro', uri=True) as db:
            db.row_factory = sqlite3.Row
            rows = [dict(db.execute('SELECT * FROM ai_charges WHERE id=?', (key,)).fetchone())
                    for key in receipts]
        result = {'stages':len(rows), 'maximumStages':options.max_stages,
                  'maximumReservationUsd':round(options.max_stages*0.0335,4),
                  'fictionalInputs':True, 'isolatedCookieAndDisposableDatabase':True,
                  'measuredEstimateUsd':sum(row['measured'] or 0 for row in rows)/1e9,
                  'heldUsd':sum(row['charged'] for row in rows if row['status'] in {'reserved','uncertain'})/1e9}
        (PACKET/'browser-live-cost.json').write_text(json.dumps(result, indent=2)+'\n')
        app.server_close()
