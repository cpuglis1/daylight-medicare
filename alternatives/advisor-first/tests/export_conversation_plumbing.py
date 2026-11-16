"""Export actual assembled fictional requests, without a network/model call.

The counter returns a sentinel only to exercise the production packing function.
No token estimates or live latency claims are produced.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import test_conversation_contract as contract
from chat import ResponsesClient
from natural_agent import NaturalAgent, PILOT_SCOPE_INSTRUCTIONS, PILOT_FIRST_REPLY_INSTRUCTION
from advisor_models import MODELS, DEFAULT_MODEL
from claude_client import ClaudeClient
from composition_recovery import REPAIR_INSTRUCTIONS
import conversation_prompts

ROOT=Path(__file__).resolve().parents[3]
PACKET=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'audit-evidence/conversation-plumbing-20261114'


def write_json(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')


def main():
    dest=PACKET/'exact-prompts';dest.mkdir(parents=True,exist_ok=True)
    for name,text in dict(interpreter=conversation_prompts.INTERPRETATION,
            composer=conversation_prompts.COMPOSITION,repair_suffix=REPAIR_INSTRUCTIONS,
            composer_with_repair=conversation_prompts.COMPOSITION+REPAIR_INSTRUCTIONS,
            pilot_scope_suffix=PILOT_SCOPE_INSTRUCTIONS,
            pilot_first_reply_suffix=PILOT_FIRST_REPLY_INSTRUCTION).items():
        (dest/(name+'.txt')).write_text(text)
    h=contract.ConversationContract();h.setUp()
    try:
        client=ResponsesClient(key='fictional',model=DEFAULT_MODEL,transport=h.flow.agent.client.transport)
        h.flow.model_agents[DEFAULT_MODEL]=NaturalAgent.from_agent(h.flow.agent,client=client)
        text='I want to learn how coverage works and compare the options for me.'
        h.message(text,extraction=h.interpreted(text,task='compare',focus='coverage_paths',
            updates=[h.update('RC01',{'choice':'self'},'for me')]),
            compose=dict(reply_blocks=['We can compare the available coverage structures.'],
                question_target=None,question='Would working through the relevant details help?',
                conversation_assessment=dict(goal_progress='open',next_move='next_step')),
            model=DEFAULT_MODEL,aiProvider=MODELS[DEFAULT_MODEL].provider)
        agent=h.flow.model_agents[DEFAULT_MODEL]
        agent.count_tokens=lambda client,payload:1 # sentinel, never represented as a measurement
        for index,payload in enumerate(h.calls):
            name='interpreter' if index==0 else 'composer'
            payload=copy.deepcopy(payload)
            agent.count_request_tokens(agent.client,payload)
            write_json(dest/(name+'-request.json'),payload)
            write_json(dest/(name+'-input.json'),json.loads(payload['input'][0]['content']))
            write_json(dest/(name+'-schema.json'),payload['text']['format']['schema'])
            claude=copy.deepcopy(payload);claude['model']='claude-opus-5-5'
            write_json(dest/(name+'-anthropic-adapter.json'),ClaudeClient('fictional').body(claude))
        agent.composition_recovery=True
        h.compositions.append(dict(reply='Long fictional draft. '*100,question_target=None,question=''))
        text='Let us continue working through the choices.'
        h.message(text,extraction=h.interpreted(text,task='compare'),
            compose=dict(reply='We can continue with the details that matter.',question_target=None,question=''),
            model=DEFAULT_MODEL,aiProvider=MODELS[DEFAULT_MODEL].provider)
        repaired=copy.deepcopy(h.calls[-1])
        assert 'validation_feedback' in json.loads(repaired['input'][0]['content'])
        agent.count_request_tokens(agent.client,repaired)
        write_json(dest/'composer-repair-request.json',repaired)
        sizes={}
        for label in ('baseline','final-payloads'):
            sizes[label]={}
            for p in (PACKET/label).glob('daylight*.json'):
                payload=json.loads(p.read_text())
                agent.count_request_tokens(agent.client,payload)
                name=p.stem
                write_json(dest/(label+'-'+name+'-packed.json'),payload)
                sizes[label][name]={
                    'instructions_bytes':len(payload['instructions'].encode()),
                    'input_bytes':len(payload['input'][0]['content'].encode()),
                    'payload_bytes':len(json.dumps(payload).encode())}
        write_json(PACKET/'payload-measurements.json',sizes)
        write_json(dest/'manifest.json',{
            'fictional':True,'live_calls':0,'token_counts_measured':False,
            'default_model':DEFAULT_MODEL,
            'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dest.iterdir()) if p.name!='manifest.json'},
            'source':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (ROOT/'alternatives/advisor-first').glob('*.py')}})
        print(json.dumps(sizes,indent=2))
    finally:h.doCleanups()


if __name__=='__main__':main()
