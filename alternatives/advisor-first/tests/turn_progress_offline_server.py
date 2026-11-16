"""D178 real HTTP/controller/UI with gated fictional work. No outbound network.

Test controls hold an actual operation; they never inject a progress receipt.
Only the inherited explicitly scripted transport replaces a model provider.
"""
import hashlib
import json
from pathlib import Path
from threading import Event, RLock
import semantic_offline_server as fixture
import turn_progress

fixture.CASES.clear()
fixture.CASES.update({
    'Help me organize enrollment before I retire.':dict(mode='work',task='timing',target='T05',
        checks=['job_loss'],updates=[('RC01',{'choice':'self'})]),
    'I live in 34102. Check my doctor, Dr. Nera Vale in Naples.':dict(mode='work',task='providers',
        updates=[('RC01',{'choice':'self'}),('T03',{'zip':'34102'}),('T06',{'text':'Dr. Nera Vale in Naples'})]),
    'I live in 34102 and take metformin. Check my medicine.':dict(mode='work',task='drug_coverage',
        updates=[('RC01',{'choice':'self'}),('T03',{'zip':'34102'}),('T07',{'text':'metformin'})]),
})
lock=RLock();release=Event();queue=[];events=[];held=None;calls=[];bad=False

def pause(stage):
    global held
    with lock:
        if not queue or queue[0]!=stage:return
        queue.pop(0);release.clear();held=stage
        context=turn_progress._current.get()
        receipt=context['progress'].read(*context['key']) if context else None
        events.append({'operation':stage,'receipt':receipt})
    if not release.wait(90):raise AssertionError('Offline gate was not released')
    with lock:held=None

def transport(payload):
    stage='working' if payload['text']['format']['name']=='daylight_guide_commands' else 'composing'
    calls.append(stage);pause(stage)
    result=fixture.transport(payload)
    if bad and stage=='composing':
        value=json.loads(result['output'][0]['content'][0]['text'])
        value.pop('reply',None)
        value['reply_blocks']=['We can use the details you share to organize the next steps.', 'Your premium is $99999.']
        result['output'][0]['content'][0]['text']=json.dumps(value)
    return result

original_build=fixture.base.build
def build(*args,**kwargs):
    service=original_build(*args,**kwargs)
    service.adaptive.turn_progress=turn_progress.Progress()
    service.adaptive.agent.composition_recovery=True
    return service

original_install=fixture.base.install
def install(service,**kwargs):
    original_install(service,**kwargs)
    parent=service.RequestHandlerClass
    class Handler(parent):
        def do_POST(self):
            global queue,events,calls,bad
            if self.path=='/__test__/progress-gate':
                if not self.validate_request():return
                self.csrf();body=self.body()
                with lock:
                    if body.get('action')=='set':
                        queue=list(body['stages']);events=[];calls=[];bad=body.get('bad',False)
                    elif body.get('action')=='release':release.set()
                    result={'held':held,'events':list(events),'calls':list(calls)}
                return self.respond(200,result)
            return super().do_POST()
    service.RequestHandlerClass=Handler
    return service

def gated(cls,method,stage):
    original=getattr(cls,method)
    def call(*args,**kwargs):pause(stage);return original(*args,**kwargs)
    setattr(cls,method,call)

if __name__=='__main__':
    fixture.base.build=build;fixture.base.install=install;fixture.base.transport=transport
    gated(fixture.base.Doctors,'search','doctors')
    gated(fixture.base.Drugs,'products','medicines')
    root=fixture.base.HERE.parent
    fixture.base.MANIFEST.update(id='turn-progress-fictional-v1',
        language='explicit local scripts; controlled real operation waits; no live model or perception claim',
        fixture_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        application_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob('*.py')},
        assets_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [root/'web-8894'/n for n in ['advisor.js','turn-progress.js','turn-progress.css']]})
    fixture.base.main()
