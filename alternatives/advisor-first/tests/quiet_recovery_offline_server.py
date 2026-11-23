"""D175 actual HTTP/UI, declared drafts only; outbound model calls forbidden."""
import hashlib
import json
from pathlib import Path
import semantic_offline_server as fixture

fixture.CASES.update({
    'Start the fictional comparison.':dict(mode='work', task='compare', target='T09',
        updates=[('RC01', {'choice':'self'})]),
    'Continue with the fictional doctor check.':dict(mode='work', task='providers', target='T06',
        draft=['Your current coverage is still unknown.']),
    'What will this cost in the fictional example?':dict(mode='work', task='costs', target='T05',
        draft=['We can compare the details that matter for this decision.', 'Your premium is $99999.'],
        question_quote=True),
})
original = fixture.transport

def transport(payload):
    result = original(payload)
    if payload['text']['format']['name'] == 'daylight_guide_commands':
        value=json.loads(result['output'][0]['content'][0]['text'])
        if fixture.current.get('question_quote'):
            value['discussion']['question_quote']=value['discussion']['quote']
    else:
        value=json.loads(result['output'][0]['content'][0]['text'])
        sent=json.loads(payload['input'][0]['content'])
        # A declared bound-answer fault; no user-language interpretation.
        answered = fixture.current.get('target') == 'T09' and not any(
            c['id']=='T09' for c in sent['question_candidates'])
        value['reply_blocks'] = (['Your coverage is through a current job.'] if answered
            else fixture.current.get('draft', [value['reply']]))
        value.pop('reply', None)
    result['output'][0]['content'][0]['text']=json.dumps(value)
    return result

if __name__ == '__main__':
    original_build=fixture.base.build
    def build(*args, **kwargs):
        service=original_build(*args, **kwargs)
        service.adaptive.agent.composition_recovery=True
        return service
    fixture.base.build=build
    fixture.base.transport=transport
    fixture.base.MANIFEST.update(id='quiet-recovery-fictional-v1',
        language='declared semantic proposals and invalid drafts; no model quality claim',
        fixture_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        application_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in fixture.base.HERE.parent.glob('*.py')})
    fixture.base.main()
