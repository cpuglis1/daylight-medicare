"""Run the new counterexamples; preserve failures as findings, never green them."""
import json
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT/'alternatives/chat-first/cms-slice/tests'),str(ROOT/'alternatives/chat-first/cms-slice/scripts')]
import test_edge_personas as tests
import edge_persona_scenarios as edge

if __name__=='__main__':
    with (HERE/'controlled-tests.log').open('w')as output:
        result=unittest.TextTestRunner(stream=output,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
    rows=[]
    for case in tests.TRACES:
        bad=[c for c in case['checks']if not c['passed']]
        rows.append({**case,'result':'FAIL'if bad else'PASS','failedChecks':bad,
                     'personaTurns':sum('action'in t and t['action'].get('type')not in {'next'} for t in case['trace']),
                     'questionPresentations':sum(bool(t.get('askedBefore'))for t in case['trace']),
                     'sampleArrival':any(t.get('action',{}).get('step')=='samples'for t in case['trace'])})
    summary={'testCount':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
             'profilesCreated':len(edge.PROFILES),'profilesPassed':sum(r['result']=='PASS'for r in rows),'profilesFailed':sum(r['result']=='FAIL'for r in rows),
             'modelOutputs':'Scripted through actual HTTP, strict language adapter and controller. This does not establish model accuracy.',
             'runtimeOrCustomerDataModified':False,'cases':rows,
             'failingTests':[{'test':t.id(),'traceback':trace}for t,trace in result.failures+result.errors]}
    (HERE/'controlled-results.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items()if k not in {'cases','failingTests'}},indent=2))
    raise SystemExit(0 if result.wasSuccessful()else 1)
