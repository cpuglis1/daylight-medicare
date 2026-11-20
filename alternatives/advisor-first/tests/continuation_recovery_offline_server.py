"""D177 declared recovery/worker-scope journeys over real handlers and UI."""
import hashlib
import json
from pathlib import Path
import semantic_offline_server as fixture

fixture.CASES.clear()
fixture.CASES.update({
    'Help me organize enrollment before I retire.':dict(mode='work',task='timing',target='T05',
        checks=['job_loss'],updates=[('RC01',{'choice':'self'})],fault_on_choice=True),
    'Help me prepare for the transition into Medicare.':dict(mode='work',task='timing',target='T05',
        checks=['job_loss'],updates=[('RC01',{'choice':'self'})],fault_on_choice=False),
    'Please connect this to the earlier enrollment request.':dict(mode='work',task='timing',
        target='RC09',checks=['job_loss'],resolve=True),
})

def transport(payload):
    sent=json.loads(payload['input'][0]['content'])
    if payload['text']['format']['name']=='daylight_guide_commands':
        value=fixture.interpret(sent['submitted_text'],sent['confirmed_context'])
        if not fixture.current.get('resolve'):
            value['discussion']['question_quote']=sent['submitted_text']
    else:
        context=sent['resolved_context'];candidates=sent['question_candidates']
        known=any(r['id']=='guide.coverage.current' and r.get('value')==['employer']
                  for r in context.get('reports',[]))
        target='RC09' if known else 'T05'
        move=next((m for m in candidates if m['id']==target),{})
        blocks=['We can organize the enrollment steps around the information you share.',
                'Your premium is $99999.']
        if known:
            blocks=(['Your premium is $99999.'] if fixture.current.get('fault_on_choice') else
                ['You reported current-job coverage. Next, we can check whether it comes through your spouse’s job or your own job.'])
        if fixture.current.get('resolve'):
            blocks=['We can use the employment source to organize the next steps, then keep the job and insurance end dates separate.']
        value=dict(reply_blocks=blocks,question_target=move.get('id'),
            question=move.get('question',{}).get('question',''),
            report_refs=[r['id'] for r in context.get('reports',[]) if r['id']=='guide.coverage.current'],
            evidence_refs=[],education=dict(purpose='advance',updates=[],visual='none'),
            conversation_assessment=dict(goal_progress='open',next_move='ask'),
            addressed_requests=[r['id'] for r in context.get('open_requests',[])] if fixture.current.get('resolve') else [],
            agenda_update=dict(current_concern='',pause=False))
    return dict(status='completed',model='gpt-5.4',service_tier='default',
        usage=dict(input_tokens=0,output_tokens=0,total_tokens=0,input_tokens_details={'cached_tokens':0}),
        output=[{'content':[{'type':'output_text','text':json.dumps(value)}]}])

if __name__=='__main__':
    original_build=fixture.base.build
    def build(*args,**kwargs):
        service=original_build(*args,**kwargs)
        service.adaptive.agent.composition_recovery=True
        return service
    fixture.base.build=build;fixture.base.transport=transport
    fixture.base.MANIFEST.update(id='continuation-recovery-fictional-v1',
        language='declared partial blocks, worker questions and later delivery; no live model-quality claim',
        fixture_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        application_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in fixture.base.HERE.parent.glob('*.py')},
        advisor_js_sha256=hashlib.sha256((fixture.base.HERE.parent/'web-8894/advisor.js').read_bytes()).hexdigest())
    fixture.base.main()
