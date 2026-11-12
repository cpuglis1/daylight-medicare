"""Fictional request sizing only; optional token endpoint, never generation.

Creates two payloads through the actual interpreter/composer with scripted local
responses and a temporary ledger. --provider-count sends only those fictional
payloads to the existing token-count endpoint. No customer reports are loaded.
"""
import argparse
import copy
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'alternatives/advisor-first/tests'))
import test_natural_agent as helpers
from education import catalog_context
from request_packing import request_sizes
from runtime_env import load_model_env
from chat import ResponsesClient
from ai_budget import count_input_tokens

parser = argparse.ArgumentParser()
parser.add_argument('--provider-count', action='store_true')
args = parser.parse_args()
h = helpers.NaturalAgentTests()
h.setUp()
try:
    h.agent.budget = h.ledger()
    catalog = catalog_context()
    context = {'task':'compare', 'current_message':'How does prescription coverage work?',
        'reports':[
            {'id':'guide.intent.goal','value':'compare','status':'reported'},
            {'id':'guide.subject.role','value':'self','status':'reported'},
            {'id':'guide.knowledge.general','value':'new','status':'reported'},
            {'id':'guide.coverage.current','value':['retiree'],'status':'reported'}],
        'safeReports':{'intent.goal':'compare','subject.role':'self','knowledge.general':'new','coverage.current':['retiree']},
        'resolved_changes':[{'id':'guide.coverage.current','previous_value':['cobra'],
                             'current_value':['retiree']}],
        'recent_exchanges':[{'user':f'Fictional question {i}: please explain that a little further.',
                            'assistant':'We can work through the options and keep reported details separate from findings.',
                            'question':'What would you like to understand next?'} for i in range(6)],
        'education_context':{'catalog':catalog,'learning':{'focus':['prescription_coverage'],
            'covered':[{'concept_id':c['concept_id'],'depth':'introduced','needs_clarification':False,
                        'deliveries':1,'aspects':list(c['aspects'])} for c in catalog['concepts']]}},
        'evidence':[copy.deepcopy(h.agent.facts[k]) for k in ('drugbasics','drugs','routesintro')]}
    captured = {}
    original = h.agent.count_request_tokens
    stage = 'extract'
    def count(client, payload):
        before = copy.deepcopy(payload)
        result = original(client, payload)
        captured[stage] = (before, copy.deepcopy(payload))
        return result
    h.agent.count_request_tokens = count
    with h.agent.reserve_turn() as reservation:
        h.answer = h.extraction([])
        h.agent.extract('fictional-sizing', context['current_message'], h.g, context, str(uuid.uuid4()), reservation)
        stage = 'compose'
        moves = [{'id':d['id'],'question':{'id':d['id'],'question':d['question'],
                                         'choices':d['options'],'fieldNames':d['fields']}}
                 for d in h.agent.definitions[:12]]
        h.answer = h.composition(question_target='T05',reply='',question='What health insurance do you have now?')
        h.agent.compose('fictional-sizing',context,moves,str(uuid.uuid4()),reservation)
    client = None
    if args.provider_count:
        load_model_env(ROOT / '.env')
        client = ResponsesClient(model='gpt-5.4')
        if not client.available:
            raise RuntimeError('Token-count service is not configured.')
    output = {'scope':'Synthetic request structure stress check; all 41 interpreter meanings, the existing maximum of 12 composer candidates, and all 17 learning concepts. Not a conversation-quality evaluation.',
              'generation_calls':0, 'token_count_requests':0, 'measurements':{}}
    for stage, (before, after) in captured.items():
        result = {'before':request_sizes(before),'after':request_sizes(after)}
        if client:
            key = 'confirmed_context' if stage == 'extract' else 'resolved_context'
            baseline = copy.deepcopy(after)
            content = json.loads(baseline['input'][0]['content'])
            content[key]['recent_exchanges'] = []
            baseline['input'][0]['content'] = json.dumps(content,ensure_ascii=False,separators=(',',':'))
            result['provider_input_tokens'] = {}
            for name, payload in [('before',before),('after',after),('zero_history',baseline)]:
                result['provider_input_tokens'][name] = count_input_tokens(client,payload)
                output['token_count_requests'] += 1
        output['measurements'][stage] = result
    destination = Path(__file__).with_name('request-sizing.json')
    destination.write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(output,indent=2))
finally:
    h.doCleanups()
