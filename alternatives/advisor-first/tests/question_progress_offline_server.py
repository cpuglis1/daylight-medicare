"""D176 declared fictional capture/repeat failures through actual HTTP handlers."""
import hashlib
import json
from pathlib import Path
import semantic_offline_server as fixture

fixture.CASES.clear()
fixture.CASES.update({
    'Help me coordinate the transition from my current job insurance.':dict(mode='work',task='timing',target='RC11',
        checks=['job_loss','payer_order'],updates=[('RC01',{'choice':'self'}),('T05',{'choice':'employer'}),('RC09',{'choice':'my_job'})]),
    'My job ends Apr 8, and coverage ends Apr. 30th.':dict(mode='work',task='timing',target='RC11',
        checks=['job_loss','payer_order'],updates=[('RC11',{'jobEnd':'2028-04-08','coverageEnd':'2028-04-30'})]),
    'Continue with the next detail.':dict(mode='work',task='timing',target='RC04',checks=['job_loss','payer_order']),
    'Help me compare costs.':dict(mode='work',task='costs',target='T09',updates=[('RC01',{'choice':'self'})]),
    'That is difficult to answer.':dict(mode='work',task='costs',target='T09'),
    'I still need time to consider it.':dict(mode='work',task='costs',target='T09'),
    'I prefer predictable bills.':dict(mode='work',task='costs',target='T09',updates=[('T09',{'choice':'predictable'})]),
})
original_transport=fixture.transport

def transport(payload):
    out=original_transport(payload)
    if payload['text']['format']['name']=='daylight_resolved_conversation':
        value=json.loads(out['output'][0]['content'][0]['text'])
        value['reply_blocks']=[value.pop('reply')]
        out['output'][0]['content'][0]['text']=json.dumps(value)
    return out

if __name__=='__main__':
    original_build=fixture.base.build
    def build(*args,**kwargs):
        service=original_build(*args,**kwargs)
        service.adaptive.agent.composition_recovery=True
        return service
    fixture.base.build=build;fixture.base.transport=transport
    fixture.base.MANIFEST.update(id='question-progress-fictional-v1',
        language='declared interpretation, unsupported year and repeated target; no live model quality claim',
        fixture_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        application_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in fixture.base.HERE.parent.glob('*.py')},
        advisor_js_sha256=hashlib.sha256((fixture.base.HERE.parent/'web-8894/advisor.js').read_bytes()).hexdigest())
    fixture.base.main()
