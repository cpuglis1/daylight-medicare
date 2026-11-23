"""D180 full HTTP/UI, fictional identities and explicit scripted model messages.
No live model, saved guest store, outbound connection or language quality claim.
"""
import hashlib
import json
from pathlib import Path
import semantic_offline_server as fixture
import turn_progress

fixture.CASES.clear()
fixture.CASES.update({
    'I want to compare coverage for myself. I live in 34102, have Parts A and B, and have Original Medicare.':
        dict(mode='work',task='compare',target='T06',updates=[('RC01',{'choice':'self'}),
             ('T01',{'choice':'compare'}),('T03',{'zip':'34102'}),('RC04',{'choice':'both'}),('T05',{'choice':'original'})]),
    'Please include Dr. Nera Vale in Naples.':dict(mode='work',task='compare',target='T07',updates=[('T06',{'text':'Dr. Nera Vale in Naples'})]),
    'I take metformin.':dict(mode='work',task='compare',target='T08',updates=[('T07',{'text':'metformin'})]),
    'I receive routine care locally.':dict(mode='work',task='compare',target='T10',updates=[('T08',{'choice':'local'})]),
    'Keeping my doctors matters most.':dict(mode='work',task='compare',target='T09',updates=[('T10',{'choice':'doctors'})]),
    'What should I do on this page?':dict(mode='detour',task='',target=None),
    'I need to pause for today.':dict(mode='pause',task='',target=None),
})

def transport(payload):
    result=fixture.transport(payload)
    if payload['text']['format']['name']!='daylight_guide_commands':
        sent=json.loads(payload['input'][0]['content'])
        context=sent['resolved_context'];value=json.loads(result['output'][0]['content'][0]['text'])
        if context.get('closing_brief') or context.get('plans_context',{}).get('navigation'):
            value.update(question_target=None,question='')
        result['output'][0]['content'][0]['text']=json.dumps(value)
    return result

original_build=fixture.base.build
def build(*args,**kwargs):
    service=original_build(*args,**kwargs)
    service.adaptive.guided_close=True
    service.adaptive.turn_progress=turn_progress.Progress()
    service.adaptive.agent.composition_recovery=True
    return service

if __name__=='__main__':
    fixture.base.build=build;fixture.base.transport=transport
    root=fixture.base.HERE.parent
    fixture.base.MANIFEST.update(id='guided-close-fictional-v1',
        language='explicit scripts; actual controllers/UI; no live model quality claim',
        fixture_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        application_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob('*.py')},
        assets_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [root/'web-8894'/n for n in ['advisor.js','plans-workspace.js','conversation-checks.js',
             'guided-close.js','guided-close.css','turn-progress.js','turn-progress.css']]})
    fixture.base.main()
