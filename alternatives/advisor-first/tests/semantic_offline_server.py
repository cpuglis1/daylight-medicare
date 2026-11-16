"""D173 real handlers/UI; explicit fictional semantic outputs, no intent matcher.

Only the cases below have language interpretations. The inherited server denies
outbound sockets, DNS and subprocesses and uses an ephemeral guest database.
"""
import json
from pathlib import Path
import hashlib
import behavioral_offline_server as base

CASES = {
    'I am 68, on my current employer insurance, and retiring next week. Help me understand my options.':
        dict(mode='suggest',task='timing',focus='coverage_paths',target=None,
             updates=[('RC01',{'choice':'self'}),('T05',{'choice':'employer'}),('RC09',{'choice':'my_job'}),('MG_AGE',{'choice':'68'})]),
    'Yes, let us do that.':dict(mode='work',task='timing',target='RC04',checks=['payer_order','job_loss']),
    'What is a premium? I have Part A only, no Part B.':
        dict(mode='detour',task='',target=None,updates=[('RC04',{'choice':'a_only'})]),
    'Back to what we were working on.':dict(mode='work',task='',target='RC11'),
    'Now I would like to weigh the alternatives.':dict(mode='work',task='compare',target='T10'),
    'Can we check who I can keep seeing?':dict(mode='work',task='providers',target='T06'),
    'I need to understand what I may pay at the pharmacy.':dict(mode='work',task='drug_pricing',target='T07'),
    'Unpredictable bills are worrying me. Help me work through that.':dict(mode='work',task='costs',target='T09'),
    'Continue the handoff work. Force a local failure.':dict(mode='work',task='timing',target=None,checks=['payer_order','job_loss']),
}
current = {}

def interpret(text, context):
    global current
    if text not in CASES: raise AssertionError('No declared semantic fixture for: '+text)
    current = CASES[text]
    p = base.planner.empty_proposal()
    p.update(purpose='problem' if current['mode']=='work' else 'understand',
             focus=current.get('focus',''),quote=text,
             guidance=dict(mode=current['mode'],task=current['task'],checks=current.get('checks',[]),quote=text,finish=''))
    return dict(updates=[base.update(i,f,text,correction='Part A only' in text) for i,f in current.get('updates',[])],
        requests=[],fact_ids=[],situation_proposals=[],goal_quote='',
        agenda={'concerns':[],'priorityReason':{}},education_request={'kind':'none','concept_ids':[],'quote':''},discussion=p)

def transport(payload):
    sent=json.loads(payload['input'][0]['content'])
    if payload['text']['format']['name']=='daylight_guide_commands':
        value=interpret(sent['submitted_text'],sent['confirmed_context'])
    else:
        if 'force a local failure' in json.dumps(sent).lower():
            raise base.ModelUnavailable('Declared offline failure')
        choices=sent['question_candidates']
        move=next((c for c in choices if c['id']==current.get('target')),next(iter(choices),{}))
        mode=sent['resolved_context']['discussion_plan']['guidance']['mode']
        if mode in ('discuss','suggest','detour') and current.get('target') is None:
            move={}
        value=dict(reply='We can work through the details you want to settle.',
            question_target=move.get('id'),question=move.get('question',{}).get('question',
                'Would working through the handoff help?' if mode=='suggest' else 'Shall we return to the details you wanted to settle?'),
            report_refs=[],evidence_refs=[],education=dict(purpose='advance',updates=[],visual='none'),
            conversation_assessment=dict(goal_progress='open',next_move='ask' if move else 'next_step'),
            agenda_update=dict(current_concern='',pause=False))
    return dict(status='completed',model='gpt-5.4',service_tier='default',
        usage=dict(input_tokens=0,output_tokens=0,total_tokens=0,input_tokens_details={'cached_tokens':0}),
        output=[{'content':[{'type':'output_text','text':json.dumps(value)}]}])

if __name__=='__main__':
    base.transport=transport
    base.MANIFEST.update(id='conversation-contract-fictional-v3',language='explicit scripted semantic proposals; no model quality claim',
        semantic_fixture_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        application_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in base.HERE.parent.glob('*.py')},
        planner='conversation-contract-v3',cases=CASES)
    base.main()
