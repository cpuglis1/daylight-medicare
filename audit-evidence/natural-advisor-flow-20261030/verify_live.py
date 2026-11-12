"""Bounded fictional local HTTP verification. Never retries a model request."""
import http.cookiejar
import json
from pathlib import Path
import time
import urllib.request
import urllib.error
import uuid

BASE='http://127.0.0.1:8892'
HERE=Path(__file__).resolve().parent
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def get(path):
    return json.load(opener.open(BASE+path,timeout=90))
session=get('/api/guest/session');state=get('/api/conversation/initial')
for previous in HERE.glob('live-turn-*.json'):
    previous.unlink()
messages=[
    "I've been retired for a few years, and am turning 65 in November.",
    "I'm just getting started. I haven't applied for Medicare yet. My health insurance is through my wife's current job.",
    "Before we get into dates, what is Medicare Part B?",
]
for index,message in enumerate(messages,1):
    payload={'guide':state['guide'],'record':state['record'],'action':{'type':'message','message':message},
             'aiConsent':True,'contextPolicy':'natural-context-v1','requestId':str(uuid.uuid4())}
    if state.get('continuation'):payload['continuation']=state['continuation']
    request=urllib.request.Request(BASE+'/api/conversation/turn',data=json.dumps(payload).encode(),
        headers={'Content-Type':'application/json','Origin':BASE,'X-Daylight-CSRF':session['csrf']})
    started=time.monotonic()
    try:
        state=json.load(opener.open(request,timeout=90))
    except urllib.error.HTTPError as error:
        body=error.read().decode()
        (HERE/'live-error.json').write_text(json.dumps({'turn':index,'status':error.code,'body':body},indent=2))
        (HERE/'live-status.json').write_text(json.dumps(get('/api/status'),indent=2))
        raise RuntimeError(f'Turn {index}: HTTP {error.code}: {body}') from error
    report={'message':message,'elapsedSeconds':round(time.monotonic()-started,3),'response':state}
    (HERE/f'live-turn-{index}.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'turn':index,'seconds':report['elapsedSeconds'],'reply':state.get('reply'),
                      'question':(state['assessment'].get('nextQuestion') or {}).get('question'),
                      'generated':state.get('generated'),'review':bool(state.get('review'))}),flush=True)
    if state.get('generated',{}).get('status')!='complete':break
    assert not state.get('review'), 'A routine report unexpectedly required acceptance.'
    if index==1:
        assert state['guide']['fields']['situation.age65']['value']=={'month':11,'year':None}
        assert 'coverage.current' not in state['guide']['fields']
    if index==2:
        assert state['guide']['fields'].get('coverage.current',{}).get('value')==['employer'], 'Explicit spouse-job insurance was omitted.'
        assert state['record']['facts'].get('RC09',{}).get('value',{}).get('choice')=='spouse_job'
        assert 'RC04' not in state['record']['facts'], 'Application progress was treated as actual A/B enrollment.'
        assert 'knowledge.general' not in state['guide']['fields'], 'Process progress was treated as expertise.'
        assert (state['assessment'].get('nextQuestion') or {}).get('id')!='T05', 'Already-reported insurance was asked again.'
(HERE/'live-status.json').write_text(json.dumps(get('/api/status'),indent=2))
