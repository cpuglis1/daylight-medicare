"""Separate integrity guards, usable replies and known defects in the saved runs."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent

if __name__=='__main__':
    controlled=json.loads((HERE/'controlled-results.json').read_text())
    live=json.loads((HERE/'live-results.json').read_text())
    old={c['id']:c for c in controlled['cases']};new={c['id']:c for c in live['cases']}
    rows=[]
    for id in ['P6','P7','P8','P9','P10']:
        c=old[id];l=new[id]
        blocked=[t for t in l['trace']if t['action']['type']=='message'and t['httpStatus']!=200]
        outcome='BLOCKED_REPLY'if blocked else l['result']
        rows.append({'id':id,'name':c['definition']['name'],'controlled':c['result'],
                     'controlledFailedChecks':c['failedChecks'],'liveWorkflow':outcome,
                     'liveGuardChecks':l['checks'],'blockedReplies':[{'httpStatus':t['httpStatus'],'error':t['response'].get('error')}for t in blocked],
                     'samplesAllowed':c['sampleArrival'],'personalRecommendationReady':False})
    output={'rows':rows,'controlledProfilesPassed':sum(r['controlled']=='PASS'for r in rows),
            'controlledProfilesFailed':sum(r['controlled']=='FAIL'for r in rows),
            'liveCleanWorkflows':sum(r['liveWorkflow']=='PASS'for r in rows),
            'liveBlockedReplies':sum(r['liveWorkflow']=='BLOCKED_REPLY'for r in rows),
            'liveOtherFailures':sum(r['liveWorkflow']=='FAIL'for r in rows),
            'note':'P9 passed the data-integrity assertions but its live reply returned HTTP 503. It is not counted as a clean conversation. Each live wording was tried once, with no automatic retry.',
            'paidGenerationAttempts':live['messageAttempts'],
            'observedUtcDay':live['afterStatus']['ai_budget']['day'],
            'estimatedUsd':round(live['afterStatus']['ai_budget']['estimatedUsd']-live['beforeStatus']['ai_budget']['estimatedUsd'],9)}
    (HERE/'assessment.json').write_text(json.dumps(output,indent=2)+'\n')
    profiles=[{'id':c['id'],'definition':c['definition'],
               'submittedActions':[t.get('action')or t.get('rejectedAction')for t in c['trace']],
               'observedFinalGuide':c['finalGuide'],'observedFinalRecord':c['finalRecord'],
               'result':c['result'],'failedChecks':c['failedChecks']}for c in sorted(old.values(),key=lambda c:int(c['id'][1:]))]
    (HERE/'PROFILES.json').write_text(json.dumps({'fictional':True,'customerRecords':False,'profiles':profiles},indent=2)+'\n')
    print(json.dumps({k:v for k,v in output.items()if k!='rows'},indent=2))
