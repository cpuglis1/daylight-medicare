"""Adversarial validator probes, NOT model-output or UI observations.

Loads the current production contract, question builder, and teaching corpus.
Uses only fictional in-memory reports; forbids network and supplies no database.
No paid generation, server startup, guest-store read, or source edit occurs.
"""
import copy
import json
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT / 'alternatives/advisor-first'
sys.path.insert(0, str(HERE))

def denied(*args, **kwargs):
    raise AssertionError('Network/model transport forbidden in this probe')

socket.create_connection = denied
socket.socket.connect = denied
import server  # Registers pinned imports; does not start a server.
from chat import ResponsesClient
from natural_flow import CONTEXT_POLICY, NaturalConversation

flow = NaturalConversation(
    None, None,
    json.loads((HERE / 'web/guide-contract.json').read_text()),
    json.loads((HERE / 'web/teaching-facts.json').read_text()),
    json.loads((HERE / 'web/readiness-content.json').read_text()),
    ResponsesClient(key='synthetic-unused', model='gpt-5.4', transport=denied),
    True, None, fixture=False)
g, r = flow.initial()
flow.capture(g, r, {'id':'RC01', 'entity':'profile', 'fields':{'choice':'self'}})
flow.capture(g, r, {'id':'T05', 'entity':'profile', 'fields':{'choice':'none'}})
context = flow.context(g, r, CONTEXT_POLICY, flow.question('T07'))
context['evidence'] = [copy.deepcopy(flow.facts['basics'])]
moves = flow.eligible('fictional-validator-review', g, r)
base = {'question_target':None, 'reply':'', 'question':'', 'report_refs':[],
        'evidence_refs':[], 'agenda_update':{'current_concern':'','pause':False},
        'education':{'purpose':'advance','updates':[],'visual':'none'},
        'education_followups':[]}
results = []

def probe(name, ctx=context, candidate_moves=moves, **updates):
    value = {**copy.deepcopy(base), **updates}
    try:
        output = flow.agent.validate_composition(value, copy.deepcopy(ctx), copy.deepcopy(candidate_moves))
        results.append({'case':name, 'outcome':'ACCEPTED', 'reply':output['reply'], 'question':output['question']})
    except Exception as error:
        results.append({'case':name, 'outcome':'REJECTED', 'error':str(error)})

probe('Contradiction of actual resolved current-coverage report',
      reply='You currently have insurance through your employer.',
      report_refs=['guide.coverage.current'])
probe('Insurance assertion not entailed by actual basics evidence',
      reply='Medicare Advantage covers every doctor.', evidence_refs=['basics'])
probe('Harmless application-process bridge',
      reply='You can leave the application question for later.')
probe('Harmless modal may plus verb outside enumerated list',
      reply='We may revisit this after you have had time to think.')
probe('Wrong meaning under eligible production T07 question target',
      question_target='T07', question='What kind of coverage do you have?')

g2, r2 = flow.initial()
flow.capture(g2, r2, {'id':'RC01', 'entity':'profile', 'fields':{'choice':'self'}})
moves2 = flow.eligible('fictional-validator-review', g2, r2)
context2 = flow.context(g2, r2, CONTEXT_POLICY, flow.question('T05'))
context2['evidence'] = [copy.deepcopy(flow.facts['basics'])]
probe('Two questions under eligible production T05 target', ctx=context2,
      candidate_moves=moves2, question_target='T05',
      question='What coverage do you have now? Which prescriptions do you take?')

artifact = {
    'scope':'Adversarial full-validator unit probes; not model or UI observations',
    'network':'forbidden', 'paid_model_calls':0, 'database':None,
    'production_contract_paths':[str(HERE / name) for name in
        ['web/guide-contract.json','web/teaching-facts.json','web/readiness-content.json','advisor-evidence.json']],
    'fictional_coverage_report':next(item for item in context['reports'] if item['id']=='guide.coverage.current'),
    'production_evidence':context['evidence'],
    'eligible_question_ids':[move['id'] for move in moves],
    'production_questions':{key:flow.question(key) for key in ['T05','T07']},
    'results':results}
print(json.dumps(artifact, indent=2))
