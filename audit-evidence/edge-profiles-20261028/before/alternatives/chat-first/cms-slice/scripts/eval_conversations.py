#!/usr/bin/env python3
"""Synthetic local endpoint eval; visible text is written only to ignored JSON."""
import argparse
import json
from pathlib import Path
import re
import statistics
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
ROOT=Path(__file__).resolve().parents[1]
PROFILE=dict(recipient='self',zip='34102',medicare='yes',drugs='yes',hearing='unsure',vision='unsure',dental='unsure')
KEYS=['model_calls','input_tokens','cached_input_tokens','output_tokens','reasoning_tokens','estimated_cost_usd']

def post(endpoint,body):
    for attempt in range(4):
        try:
            with urlopen(Request(endpoint,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'}),timeout=180) as response: return json.load(response)
        except HTTPError as error:
            if error.code==429 and attempt<3: time.sleep(20); continue
            return {'error':'HTTP '+str(error.code)}

def run(endpoint,output,baseline=False,scenario_file=None):
    sessions=[]
    for scenario in json.loads((scenario_file or ROOT/'tests/fixtures/milkman_scenarios.json').read_text()):
        history=[]; state={}; turns=[]
        if not baseline:
            welcome="Hi, I'm Daylight Medicare, an automated guide to Medicare in Naples. I can explain how Medicare works or help you look through 2027 plans. I'm not a person or an insurance agent, and I'll never ask for ID numbers."
            turns.append(dict(message='[opening]',reply=welcome,question='How familiar are you with Medicare so far?',word_count=len(welcome.split())+8,questions=1,metrics={k:0 for k in KEYS},flags=dict(unsupported_numbers=[],recommendation=False,unchecked_priority_satisfied=False,repeated_question=False,jargon_before_explanation=[]),fact_text='Local static welcome; no model call.',error=None,fallback=False))
        for message in ([''] if baseline else [])+scenario['messages']:
            if message=='{compare}':
                result=post(endpoint.replace('/live-chat','/catalog'),{'action':'compare','plan_ids':['S4802-083-000-2027','S4802-146-000-2027']})
                ids=[p['id'] for p in result.get('plans',[])]
                state['on_screen']=dict(view='comparison',category=None,sorted_by=[],unscored=[],plan_ids=ids)
                state['selections']=dict(plan_ids=ids,rxcuis=[],pharmacy_npi=None)
                history += [dict(role='user',content='Compare selected plans '+', '.join(ids)),dict(role='assistant',content='Selected plans displayed in source ID order.')]
                continue
            body=dict(message=message,history=history if baseline else history[-12:])
            body.update({'intake':PROFILE} if baseline else {'state':state})
            result=post(endpoint,body); reply=result.get('text',''); question=result.get('question',''); visible=reply+' '+question
            metrics=result.get('debug',{})
            facts=' '.join(f['text'] for f in result.get('facts',[]))
            nums=lambda s:set(re.findall(r'(?<!\w)\d+(?:[,.]\d+)*(?!\w)',s))
            flags=dict(unsupported_numbers=sorted(nums(visible)-nums(facts)),recommendation=bool(re.search(r'best plan for you|you should enroll|I recommend',visible,re.I)),unchecked_priority_satisfied=bool(re.search(r'(?:your|her|his) (?:doctor|cardiologist).{0,30}(?:is covered|in.network|accepted)',visible,re.I)),repeated_question=bool(question and any(t['question'].casefold()==question.casefold() for t in turns)),jargon_before_explanation=[])
            earlier=' '.join(t['reply'] for t in turns).lower()
            for term in ['medigap','medicare advantage','part d','snp']:
                if term in visible.lower() and term not in earlier and not re.search(r'supplement|private|drug|special needs',visible,re.I): flags['jargon_before_explanation'].append(term)
            turns.append(dict(message=message or '[opening]',reply=reply,question=question,word_count=len(visible.split()),questions=visible.count('?'),metrics=metrics,flags=flags,fact_text=facts,error=result.get('error'),fallback=result.get('fallback',False)))
            if message: history.append(dict(role='user',content=message))
            history.append(dict(role='assistant',content=(visible+ ('\n'+facts if baseline else '')).strip()[:2000] or 'Unable to answer.'))
            for k,v in result.get('state_update',{}).items():
                if v is not None: state[k]=v
            if result.get('on_screen'): state['on_screen']=result['on_screen']
        totals={k:sum(t['metrics'].get(k,0) or 0 for t in turns) for k in KEYS}
        sessions.append(dict(id=scenario['id'],turns=turns,totals=totals))
        print(f"{scenario['id']}: {totals['model_calls']} calls, ${totals['estimated_cost_usd']:.5f}",flush=True)
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps({'sessions':sessions},indent=2)+'\n')
    turns=[t for s in sessions for t in s['turns']]; later=[t for s in sessions for t in s['turns'][1:]]
    totals={k:sum(s['totals'][k] for s in sessions) for k in KEYS}
    costs=[t['metrics'].get('estimated_cost_usd',0) or 0 for t in turns]
    summary=dict(turns=len(turns),sessions=len(sessions),median_words=statistics.median(t['word_count'] for t in turns),over_120_share=sum(t['word_count']>120 for t in turns)/len(turns),median_cost_usd=statistics.median(costs),mean_session_cost_usd=statistics.mean(s['totals']['estimated_cost_usd'] for s in sessions),ten_turn_cost_projection_usd=statistics.mean(costs)*10,cached_share_after_first=sum(t['metrics'].get('cached_input_tokens',0) for t in later)/max(1,sum(t['metrics'].get('input_tokens',0) for t in later)),cache_hit_turn_share_after_first=sum(t['metrics'].get('cached_input_tokens',0)>0 for t in later)/len(later),question_violations=sum(t['questions']>1 for t in turns),repeated_questions=sum(t['flags']['repeated_question'] for t in turns),unsupported_number_turns=sum(bool(t['flags']['unsupported_numbers']) for t in turns),recommendation_turns=sum(t['flags']['recommendation'] for t in turns),unchecked_priority_turns=sum(t['flags']['unchecked_priority_satisfied'] for t in turns),jargon_flags=sum(len(t['flags']['jargon_before_explanation']) for t in turns),errors=sum(bool(t['error']) for t in turns),fallbacks=sum(t['fallback'] for t in turns),**totals)
    note='Account key is shared with another project; account billing cannot be attributed to Daylight Medicare. Recommend a dedicated Daylight Medicare key/project. Costs are standard-rate estimates. Rubric flags are screening, not semantic quality proof; review tool appropriateness and visible text locally.'
    report=dict(endpoint=endpoint,baseline=baseline,summary=summary,sessions=sessions,billing_note=note)
    output.write_text(json.dumps(report,indent=2)+'\n')
    output.with_suffix('.md').write_text('# '+output.stem+'\n\n'+'\n'.join('- '+k+': '+str(v) for k,v in summary.items())+'\n\n'+note+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--endpoint',default='http://127.0.0.1:8770/api/live-chat'); p.add_argument('--output',type=Path,default=ROOT/'reports/baseline-eval.json'); p.add_argument('--baseline',action='store_true'); p.add_argument('--scenario-file',type=Path); a=p.parse_args(); run(a.endpoint,a.output,a.baseline,a.scenario_file)
