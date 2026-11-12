"""Disposable, fictional browser check. Models disabled; no active user records."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import uuid
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'alternatives/advisor-first/tests'), str(ROOT/'alternatives/advisor-first')]
from server import build
from test_plan_review import PlanReviewTests
case = PlanReviewTests();case.setUp();case.fill(lists=True)
seed = (copy.deepcopy(case.case.g),copy.deepcopy(case.case.r));case.guard.stop()
fixture = tempfile.TemporaryDirectory(prefix='daylight-plan-review-')
app = build(8917, fixture=True, database=Path(fixture.name)/'profiles.sqlite3')
base = app.RequestHandlerClass
class Preview(base):
    def headers_for(self, *args, **kwargs):
        original = self.send_header
        def header(name,value):
            if name=='Content-Security-Policy': value=value.replace("frame-ancestors 'none'","frame-ancestors 'self'")
            original(name,value)
        self.send_header=header
        try: return super().headers_for(*args,**kwargs)
        finally: self.send_header=original
    def raw(self,text,mime='text/html; charset=utf-8'):
        data=text.encode();self.headers_for(200,mime,len(data));self.wfile.write(data)
    def do_GET(self):
        if self.path=='/api/conversation/initial':
            self.server.profiles.require(self.token())
            owner=self.server.profiles.digest(self.token())
            out=self.server.adaptive.turn(owner,{'guide':copy.deepcopy(seed[0]),'record':copy.deepcopy(seed[1]),
                'action':{'type':'refresh'},'requestId':str(uuid.uuid4())})
            return self.respond(200,out)
        if self.path in {'/','/index.html'}:
            page=(ROOT/'alternatives/advisor-first/web/index.html').read_text()
            return self.raw(page.replace('</head>','<script src="/test-destination.js" defer></script></head>'))
        if self.path=='/test-destination.js':
            return self.raw('''DaylightPlansHandoff.register(handoff=>{
const host=document.getElementById('current');host.replaceChildren();
const h=document.createElement('h1');h.textContent='Plans destination fixture';host.append(h);
const p=document.createElement('p');p.textContent='Received reviewed profile for '+handoff.scope.year+' in '+handoff.scope.county.name+'. Open checks: '+handoff.holds.length+'. Recommendations remain held.';host.append(p);
const b=document.createElement('button');b.textContent='Return to review test';b.onclick=()=>location.reload();host.append(b);h.tabIndex=-1;h.focus();return true;
});''','text/javascript')
        if self.path in {'/__review/phone','/__review/tablet'}:
            width,height=(390,844) if self.path.endswith('phone') else (820,1000)
            return self.raw(f'<!doctype html><title>Responsive fixture</title><body style="margin:0"><iframe title="Daylight fixture" src="/" width="{width}" height="{height}" style="border:0"></iframe>')
        return super().do_GET()
app.RequestHandlerClass=Preview
print('Offline fixture: http://127.0.0.1:8917/',flush=True)
try: app.serve_forever()
finally: app.server_close();fixture.cleanup()
