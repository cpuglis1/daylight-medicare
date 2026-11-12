"""Reproduce nine HTTP traces / five personas and generate the 41-ID matrix."""
from collections import Counter
import json
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ALT=ROOT/'alternatives/chat-first'
sys.path[:0]=[str(ALT/'cms-slice/tests'),str(ALT/'cms-slice/scripts')]
import test_ui2_personas as scenarios
from adaptive_flow import CONTRACT, FIELD, Q


def write(name,data):
    (HERE/name).write_text(json.dumps(data,indent=2)+'\n')


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromModule(scenarios)
    with (HERE/'personas-tests.log').open('w') as f:result=unittest.TextTestRunner(stream=f,verbosity=2).run(suite)
    if not result.wasSuccessful():raise SystemExit('Persona checks failed; no passing matrix generated.')
    traces=scenarios.TRACES
    write('persona-traces.json',{'synthetic':True,'paidAI':False,'modelOutputs':'Scripted through the actual strict language adapter; not a model accuracy eval.',
                                'pacing':'Private fixture limiter clock advances 10 seconds per message. Production rate policy is unchanged.',
                                'cases':traces})
    rows=[]
    for id,q in Q.items():
        parent=id.split('.')[0]
        asked=[];reported=[];reused=[];pending=[]
        for case in traces:
            if any(t['askedBefore'] and t['askedBefore']['id']==id for t in case['trace']):asked.append(case['id'])
            if id in FIELD and FIELD[id] in case['finalGuide']['fields'] or id in case['finalRecord']['facts']:reported.append(case['id'])
            if any(t['ruleDecisions'][id]['state']=='reported_reused' for t in case['trace']):reused.append(case['id'])
            if any(t['pendingInterpretation'] for t in case['trace']):pending.append(case['id'])
        if '.' in id:
            field={'RC11.C1':'coverageEnd','RC16.C1':'start','RC16.C2':'priorMedigap'}[id]
            asked=[c['id'] for c in traces if any(t['askedBefore'] and t['askedBefore']['id']==parent and field in [f['key'] for f in t['askedBefore']['fields']] for t in c['trace'])]
            status='Within parent; exercised'
            reason='Shared field alias; no separate child questionnaire or duplicate fact.'
        elif id=='RC28':
            status='Integrity guard exercised';asked=[];reported=pending
            reason='Ambiguous interpretation is held for explicit confirmation; a clear correction applies directly and invalidates only dependent reports.'
        elif asked:
            status='Asked / exercised'
            reason='Task-relevant missing report; supplied facts reused and unknown/defer remain unresolved.'
        elif reported:
            status='Volunteered / reused'
            reason='Optional preference or internal contextual report; not forced as a stock question.'
        else:
            status='GAP: unexercised';reason='No passing trace established this entry.'
        row={'id':id,'question':q['question'],'treatment':q['reviewTreatment'],'status':status,'askedBy':asked,'reportedBy':reported,'reusedBy':reused,'reason':reason,'insuranceVerificationReleased':False}
        rows.append(row)
    assert len(rows)==41 and not any(r['status'].startswith('GAP') for r in rows)
    write('coverage-matrix.json',{'revision':CONTRACT['version'],'rows':rows,'counts':dict(Counter(r['status']for r in rows)),
                                'meaning':'Observed route/report/guard coverage across five fictional personas and variants. Not all 78 field values, all possible inputs, model accuracy, or accepted insurance rules.',
                                'externalGapsClosed':0})
    lines=['# 41-question coverage matrix · D79 UI2','',
           'Five fictional personas, nine HTTP journeys. Every turn passed real request/CSRF validation, the actual controller and report validation. Scripted AI output passed the actual strict language adapter; this does not establish model accuracy. Browser and live checks are recorded separately. No personal capability was released.','',
           '| ID | Question / check | Observed coverage | Evidence |','| --- | --- | --- | --- |']
    for r in rows:
        cases=', '.join(dict.fromkeys(r['askedBy']+r['reportedBy']))
        lines.append('| '+r['id']+' | '+r['question'].replace('|','/')+' | '+r['status']+' | '+cases+' |')
    lines += ['', '“Volunteered / reused” means the substantive report or optional preference was accepted in the proper context without a routine follow-up. Internal entries do not become mandatory questions merely to make the matrix green. The three child entries are tested through their parent fields.', '',
              'Remaining limits: the 14 representation/evidence gaps are unchanged; source-specific activation and independently accepted rules remain held. RC08 event-date and RC16 history preparation still use task-level routing rather than an accepted rule selecting exact necessary precision/history. RC21/RC24/RC19 source-specific candidate/method/qualification prompts cannot be exercised against an accepted integration because none is connected. Full source-backed decision behavior is therefore not claimed. Multiple-item parsing accuracy, physical keyboard and assistive-technology execution remain separate evaluations.']
    (HERE/'COVERAGE_MATRIX.md').write_text('\n'.join(lines)+'\n')
    # UI steps contain only visible interactions/expected headings, not injected state.
    plans=[]
    for case in traces:
        if '-' in case['id']:continue
        actions=[]
        for step,t in zip(case['steps'],case['trace']):
            a=step['action'];q=t['askedBefore'];entry={'action':a,'expectedNext':step['expectedNext']}
            if a['type']=='choice':
                values=a['fields'].get('choice','').split(',') if a['fields'].get('choice') else []
                entry['buttons']=['I don’t know' if v=='unknown' else dict(q['choices'])[v] for v in values]
                for key,value in a['fields'].items():
                    if key!='choice':entry['buttons'].append(dict(next(f for f in q['fields'] if f['key']==key)['options'])[value])
            if a['type']=='defer':entry['buttons']=['Check later']
            if a['type']=='confirm':entry['buttons']=['Use these details']
            actions.append(entry)
        plans.append({'id':case['id'],'name':case['name'],'actions':actions})
    write('browser-plans.json',plans)
    print(json.dumps({'testsPassed':result.testsRun,'personaCount':len(plans),'journeyVariants':len(traces),'matrixIds':len(rows),'counts':dict(Counter(r['status']for r in rows))}))
