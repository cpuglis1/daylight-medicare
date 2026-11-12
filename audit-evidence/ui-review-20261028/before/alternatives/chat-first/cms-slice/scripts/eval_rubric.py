#!/usr/bin/env python3
"""Regrade local eval files without API calls; screening is not clinical review.

Normalizes equivalent currency formats and separately flags unexplained terms,
repeated explanation offers, and unnecessary tools on pure conversation turns.
"""
from decimal import Decimal
import json,re,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'reports'
def numbers(text):
 return {Decimal(n.replace(',','')) for n in re.findall(r'(?<!\w)\d+(?:,\d{3})*(?:\.\d+)?(?!\w)',text)}
def grade(report):
 findings=[];repeated_offers=0;tool_extras=0;after_first=[]
 jargon_defs={'original medicare':r'hospital|medical coverage|government|federal','medicare advantage':r'private|insurer','medigap':r'supplement|out.of.pocket|share of|leftover|gaps','part d':r'drug|prescription','prior authorization':r'approv|permission','snp':r'special needs|qualif'}
 for s in report['sessions']:
  explained=set();first_paid=False;previous_offer=False
  for i,t in enumerate(s['turns']):
   if first_paid:after_first.append(t)
   if t['metrics'].get('model_calls',0):first_paid=True
   if t['message']=='[opening]':continue
   visible=t['reply']+' '+t['question'];lower=visible.casefold()
   unsupported=numbers(visible)-numbers(t.get('fact_text',''))
   jargon=[]
   for term,definition in jargon_defs.items():
    if term in lower and term not in explained:
     if re.search(definition,lower):explained.add(term)
     else:jargon.append(term)
   offer=bool(re.search(r'overview|explain|walk.?through|side.by.side|main choices|fork|paths|map of',t['question'],re.I))
   repeated=bool(previous_offer and offer and re.search(r'explain|new to this|understand|more simply',t['message'],re.I))
   repeated_offers+=repeated
   previous_offer=offer
   if 'already know Medicare basics' in t['message'] or s['id']=='uneasy' and i in [1,2]:tool_extras+=bool(t['metrics'].get('tool_names',[]))
   findings.append({'session':s['id'],'turn_index':i,'unsupported_normalized_numbers':[str(v) for v in sorted(unsupported)],'unexplained_jargon':jargon,'repeated_explanation_offer':repeated})
 return {'normalized_unsupported_number_turns':sum(bool(f['unsupported_normalized_numbers']) for f in findings),'jargon_before_definition_occurrences':sum(len(f['unexplained_jargon']) for f in findings),'jargon_before_definition_turns':sum(bool(f['unexplained_jargon']) for f in findings),'repeated_explanation_offer_flags':repeated_offers,'unneeded_tools_on_pure_identity_or_brief_turns':tool_extras,'cached_share_after_first_model_turn':sum(t['metrics'].get('cached_input_tokens',0) for t in after_first)/max(1,sum(t['metrics'].get('input_tokens',0) for t in after_first)),'findings':findings}

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('reports',nargs='*',type=Path)
 args=parser.parse_args()
 paths=args.reports or [ROOT/(name+'.json') for name in ['baseline-eval','after-gpt54-none-eval','after-gpt54-low-eval','after-mini-none-eval','after-mini-low-eval']]
 for path in paths:
  report=json.loads(path.read_text());score=grade(report);report['review_rubric']=score
  path.write_text(json.dumps(report,indent=2)+'\n')
  aggregate={key:value for key,value in score.items() if key!='findings'}
  print(path.name,json.dumps(aggregate))
  summary=path.with_suffix('.md')
  if summary.exists():
   original=summary.read_text().split('\n## Additional rubric screening')[0]
   summary.write_text(original+'\n## Additional rubric screening\n\n'+'\n'.join('- '+key+': '+str(value) for key,value in aggregate.items())+'\n\nThese are deterministic screening flags, not a semantic or clinical accuracy guarantee. Equivalent currency formats are normalized. Cached share here excludes the first model-using turn in each session.\n')
