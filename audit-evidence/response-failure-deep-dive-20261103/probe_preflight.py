"""Three independent exact-count diagnostics; paid generation is forbidden."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import time
from urllib.error import HTTPError
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
VARIANT = ROOT/'alternatives/advisor-first'
sys.path.insert(0,str(VARIANT))
from server import build
from natural_flow import CONTEXT_POLICY
import provider_tokens
import provider_transport
from transport_diagnostics import failure_details

class CountProbeFinished(RuntimeError):pass

def run():
    messages=[
        "I'm helping my mother understand Medicare. She lives in Naples. We need to work out coverage and practical help, and I'm not sure where to start.",
        "I'm checking Medicare coverage for myself in Collier County. I'd like to keep my cardiologist and understand what visits could cost. Where should I start?",
        'What is Medicare?']
    result={'paid_generation_calls':0,'automatic_retries':False,'probes':[]}
    with tempfile.TemporaryDirectory(prefix='preflight-probe-',dir=VARIANT/'var') as folder:
        app=build(0,database=Path(folder)/'fictional.sqlite3')
        flow=app.adaptive
        count=flow.agent.count_tokens
        original_open=provider_tokens.urlopen
        original_popen=provider_transport.subprocess.Popen
        active={}
        def observed_open(*args,**kwargs):
            try:
                with original_open(*args,**kwargs) as response:
                    yield response
            except Exception as error:
                active['diagnostic']=failure_details(error,'preflight')
                raise
        from contextlib import contextmanager
        opened=contextmanager(observed_open)
        processes=[]
        def observed_process(*args,**kwargs):
            process=original_popen(*args,**kwargs);processes.append(process);return process
        def observed_count(client,payload):
            (Path(__file__).parent/('probe-'+str(active['number'])+'-request.json')).write_text(json.dumps(payload,indent=2)+'\n')
            try:
                active['tokens']=count(client,payload)
            except Exception as error:
                active['error_type']=type(error).__name__
            active['curl_exit_codes']=[p.poll() for p in processes]
            raise CountProbeFinished()
        flow.agent.count_tokens=observed_count
        def no_generation(*args,**kwargs):
            result['paid_generation_calls']+=1
            raise AssertionError('No generation is permitted.')
        flow.agent.client.transport=no_generation
        for number,message in enumerate(messages,1):
            active={'number':number};processes.clear()
            owner=uuid.uuid4().hex;g,r=flow.initial()
            state=flow.turn(owner,{'guide':g,'record':r,'action':{'type':'start'},'requestId':uuid.uuid4().hex})
            started=time.perf_counter()
            with patch('provider_tokens.urlopen',opened),patch('provider_transport.subprocess.Popen',observed_process):
                try:
                    flow.turn(owner,{'guide':state['guide'],'record':state['record'],
                        'continuation':state['continuation'],'requestId':uuid.uuid4().hex,
                        'action':{'type':'message','message':message},'aiConsent':True,'contextPolicy':CONTEXT_POLICY})
                except CountProbeFinished:pass
            active['seconds']=round(time.perf_counter()-started,3)
            result['probes'].append(copy.deepcopy(active))
            print(json.dumps(active),flush=True)
        app.server_close()
    (Path(__file__).parent/'preflight-probes.json').write_text(json.dumps(result,indent=2)+'\n')
    assert result['paid_generation_calls']==0

if __name__=='__main__':run()
