"""Bounded, fictional live checks. Existing consent/aggregate budget; no saved profile."""
import argparse
import json
from pathlib import Path
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'alternatives/advisor-first'))
import server
from advisor_flow import AdvisorConversation
from chat import ResponsesClient
from ai_budget import DailyBudget
from runtime_env import load_model_env

CASES={
 'retired':"I've been retired for a few years, and am turning 65 in November.",
 'retiree_insurance':'My retiree health insurance is through my former employer. I turn 65 in November 2026 and want help getting started with Medicare.',
 'work_transition':'My insurance is through my current job. I am retiring in March 2027 and want Medicare coverage to start in April 2027. Help me plan the transition.',
}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--effort',choices=['none','low'],required=True);parser.add_argument('--case',choices=CASES,required=True);args=parser.parse_args()
    load_model_env(ROOT/'.env')
    here=ROOT/'alternatives/advisor-first/web'
    flow=AdvisorConversation(None,None,json.loads((here/'guide-contract.json').read_text()),json.loads((here/'teaching-facts.json').read_text()),json.loads((here/'readiness-content.json').read_text()),ResponsesClient(),True,DailyBudget(ROOT/'cms-slice/var/ai-budget/usage.sqlite3'),fixture=False)
    flow.agent.reasoning_effort=args.effort;g,r=flow.initial();owner=uuid.uuid4().hex;started=time.monotonic()
    report={'case':args.case,'effort':args.effort,'model':flow.agent.client.model,'outputLimit':900,'saved':False}
    try:
        out=flow.turn(owner,{'guide':g,'record':r,'action':{'type':'message','message':CASES[args.case]},'requestId':str(uuid.uuid4()),'aiConsent':True})
        review=out.get('review')
        if review:
            candidate=flow.reviews[review['token']];cg,cr=candidate['guide'],candidate['record']
        else:cg,cr=out['guide'],out['record']
        checks={'noIrrelevantTeaching':not out['facts'],'noInventedInsuranceEnd':not flow.report(cr,'RC11').get('coverageEnd'),'noRecommendation':not out['personalRecommendation']}
        if args.case=='retired':
            checks.update(noRetireeCoverage=flow.value(cg,'coverage.current') is None and not flow.report(cr,'RC09'),noDesiredStart=flow.value(cg,'coverage.requestedStartMonth') is None,unknownYearPreserved=flow.value(cg,'situation.age65')=={'month':11,'year':None},nextIsCurrentInsurance=flow.assess(cg,cr)['nextQuestion']['id']=='T05')
        if args.case=='retiree_insurance':checks['actualRetireeCoverageRetained']=flow.value(cg,'coverage.current')==['retiree']
        if args.case=='work_transition':checks.update(actualEmployerRetained=flow.value(cg,'coverage.current')==['employer'],intendedStartRetained=flow.value(cg,'coverage.requestedStartMonth')=='2027-04',jobEndRetained=flow.report(cr,'RC11').get('jobEnd')=='2027-03')
        report.update(passed=all(checks.values()),checks=checks,reply=out['reply'],reviewRows=review['rows'] if review else [],usage=flow.agent.usage[-1] if flow.agent.usage else {},semanticRejections=getattr(flow.agent.local,'rejected',[]))
    except Exception as error:report.update(passed=False,errorType=type(error).__name__,error=str(error))
    report['seconds']=round(time.monotonic()-started,2)
    dest=Path(__file__).parent/f"model-{args.effort}-{args.case}.json";dest.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
