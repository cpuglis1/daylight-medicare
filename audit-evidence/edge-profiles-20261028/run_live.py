"""Bounded synthetic spot-checks via the running :8891 API.

One new, expiring empty guest session; fictional answer state remains visit-only.
Uses normal CSRF/Origin/consent, existing live AI and the shared daily ledger.
No credentials are read here, no retries and no profile save/delete calls.
"""
import copy
from datetime import datetime,timezone
import http.client
import json
from pathlib import Path
import sys
import uuid

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'alternatives/chat-first/cms-slice/tests'))
import edge_persona_scenarios as edge


class Client:
    def __init__(self):self.cookie='';self.csrf='';self.attempts=0;self.traces=[]
    def http(self,method,path,body=None):
        c=http.client.HTTPConnection('127.0.0.1',8891,timeout=55)
        headers={'Content-Type':'application/json','Origin':'http://127.0.0.1:8891','Cookie':self.cookie,'X-Daylight-CSRF':self.csrf}
        c.request(method,path,json.dumps(body)if body is not None else None,headers);r=c.getresponse()
        if r.getheader('Set-Cookie'):self.cookie=r.getheader('Set-Cookie').split(';')[0]
        data=json.loads(r.read());status=r.status;c.close();return status,data
    def initial(self):
        status,d=self.http('GET','/api/conversation/initial');assert status==200
        self.g=d['guide'];self.r=d['record'];self.a=d['assessment'];self.pending=None;self.traces=[]
    def turn(self,a):
        if a['type']=='message':
            assert self.attempts<5,'The five-generation spot-check ceiling was reached.'
            _,budget=self.http('GET','/api/status');assert budget['agent_available']and budget['ai_budget']['remainingUsd']>=.0335
            self.attempts+=1
        status,d=self.http('POST','/api/conversation/turn',{'guide':self.g,'record':self.r,'action':a,'requestId':str(uuid.uuid4()),'aiConsent':True,'pendingId':self.pending})
        self.traces.append({'action':a,'httpStatus':status,'response':d})
        if status==200:
            self.g=d['guide'];self.r=d['record'];self.a=d['assessment'];self.pending=d['pendingId']
            assert not d['personalRecommendation']and not self.a['personalizedRecommendationAllowed']and not self.a['externalVerificationReady']
        return status,d
    def choice(self,id,**fields):
        status,d=self.turn({'type':'choice','id':id,'fields':fields});assert status==200,d
    def next(self,step):return self.turn({'type':'next','step':step})
    def snapshot(self):return {'guide':self.g,'record':self.r,'assessment':self.a,'pending':bool(self.pending)}


if __name__=='__main__':
    c=Client();status,info=c.http('GET','/api/guest/session');assert status==200;c.csrf=info['csrf']
    _,before=c.http('GET','/api/status');assert before['ai_budget']['remainingUsd']>=.18
    results=[]
    def finish(id,name,checks):
        if c.pending:c.turn({'type':'reject'})
        c.next('samples');c.next('resume')
        row={'id':id,'name':name,'checks':checks,'trace':copy.deepcopy(c.traces),'final':copy.deepcopy(c.snapshot()),
             'result':'PASS'if all(x['passed']for x in checks)else'FAIL'}
        results.append(row)
        (HERE/'live-results.json').write_text(json.dumps({'syntheticInputs':True,'oneExpiringEmptyGuestSession':True,'answersSaved':False,'automaticRetries':False,'messageAttempts':c.attempts,'beforeStatus':before,'cases':results},indent=2)+'\n')
        print(id,row['result'],flush=True)
    def check(label,actual,expected):return {'label':label,'actual':actual,'expected':expected,'passed':actual==expected}

    c.initial();c.choice('T01',choice='compare');c.choice('RC01',choice='self');c.choice('T04',choice='month',month='January 2027');c.choice('T05',choice='cobra');c.choice('RC11',coverageEnd='December 2026');c.turn({'type':'task','task':'timing','preparing':True})
    status,d=c.turn(edge.P6_AMBIGUOUS['action'])
    checks=[check('ambiguous replacement is pending',bool(c.pending),True),check('prior end date preserved',c.r['facts']['RC11']['value']['coverageEnd'],'2026-12')]
    finish('P6','Conflicting dates',checks)

    c.initial();c.choice('T01',choice='compare');asked=[]
    for _ in range(15):
        q=c.a['nextQuestion']
        if not q:break
        asked.append(q['id']);c.turn({'type':'unknown','id':q['id']})
    finish('P7','Mostly unknowns',[check('no repeated unknown question',len(asked),len(set(asked))),check('all seven unknowns visible',len(c.a['unresolvedReportedInputs']),7),check('only goal recorded',sorted(c.g['fields']),['intent.goal'])])

    c.initial();c.choice('T01',choice='compare');c.choice('RC01',choice='self');c.choice('T04',choice='month',month='December 2026');c.choice('T05',choice='cobra');c.choice('T03',zip='34102');signature=c.a['nextQuestion']['signature']
    c.turn(edge.P8_SIDE['action']);checks=[check('side question preserves task',c.a['task'],'compare'),check('active question preserved',c.a['nextQuestion']['signature']if c.a['nextQuestion']else None,signature)]
    c.turn(edge.P8_LEARN['action']);checks.append(check('explicit learning changes task',c.a['task'],'learn'))
    c.choice('T01',choice='compare');checks.append(check('return reuses earlier facts',c.a['nextQuestion']['id']if c.a['nextQuestion']else None,'T06'))
    finish('P8','Goal changes',checks)

    c.initial();c.choice('T01',choice='compare');c.choice('RC01',choice='someone');c.choice('T04',choice='month',month='January 2027');c.choice('T05',choice='cobra');c.choice('RC11',coverageEnd='December 2026');c.turn({'type':'task','task':'timing','preparing':True})
    status,d=c.turn(edge.P9_HELPER['action']);finish('P9','Different people',[check('mother role preserved',c.g['fields']['subject.role']['value'],'someone'),check('helper insurance not merged',c.g['fields']['coverage.current']['value'],['cobra'])])

    c.initial();status,d=c.turn(edge.P10_SAME['action']);items=c.r['facts'].get('RC22',{}).get('value',{}).get('items',[])
    finish('P10','Same-name medicines',[check('two distinct strength reports retained',len(items),2),check('both strengths retained',sorted(i.get('strength','')for i in items),['10 mg','5 mg'])])
    _,after=c.http('GET','/api/status');_,stored=c.http('GET','/api/guest/profile');assert stored['guide']is None
    report=json.loads((HERE/'live-results.json').read_text());report.update(checkedAt=datetime.now(timezone.utc).isoformat(),afterStatus=after,emptyGuestProfileConfirmed=True)
    (HERE/'live-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'messageAttempts':c.attempts,'observedDailyChargeDifference':after['ai_budget']['requestCount']-before['ai_budget']['requestCount'],'estimatedUsdDifference':round(after['ai_budget']['estimatedUsd']-before['ai_budget']['estimatedUsd'],9),'profilesPassed':sum(r['result']=='PASS'for r in results),'profilesFailed':sum(r['result']=='FAIL'for r in results)}),flush=True)
