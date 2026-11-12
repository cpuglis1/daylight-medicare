"""Isolated fictional-test server; captures only test composition for diagnosis."""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'alternatives/advisor-first'))
from server import build
from natural_agent import NaturalAgent
import narrative_agent
import natural_agent

failure_diagnostic=narrative_agent.provider_failure_diagnostic
def inspect_provider_error(event):
    # This isolated server accepts fictional tests only. No credentials or
    # request context is included in this provider event capture.
    (Path(__file__).parent/'fictional-provider-event.json').write_text(json.dumps(event,indent=2))
    return failure_diagnostic(event)
narrative_agent.provider_failure_diagnostic=inspect_provider_error
natural_agent.provider_failure_diagnostic=inspect_provider_error

original=NaturalAgent.validate_composition
extract_original=NaturalAgent.validate_output
counter={'extract':0,'compose':0}
def inspect_extract(self,value,message,guide,facts,eligible,owner):
    counter['extract']+=1
    result=extract_original(self,value,message,guide,facts,eligible,owner)
    (Path(__file__).parent/f'fictional-extract-{counter["extract"]}.json').write_text(json.dumps({'value':value,'resolved_proposals':result},indent=2))
    return result
NaturalAgent.validate_output=inspect_extract
extract_call=NaturalAgent.extract
def inspect_extract_failure(self,*args,**kwargs):
    try:
        return extract_call(self,*args,**kwargs)
    except Exception as error:
        (Path(__file__).parent/'fictional-provider-failure.json').write_text(json.dumps({
            'stage':'extract','error':str(error),'provider':getattr(self.local,'provider_failure',None)},indent=2))
        raise
NaturalAgent.extract=inspect_extract_failure
def inspect_fictional(self,value,context,moves):
    output={'value':value,'reports':context.get('reports'),'moves':moves}
    try:
        result=original(self,value,context,moves)
        output['accepted']=True
        return result
    except Exception as error:
        output.update(accepted=False,error=str(error))
        raise
    finally:
        counter['compose']+=1
        (Path(__file__).parent/f'fictional-compose-{counter["compose"]}.json').write_text(json.dumps(output,indent=2))
        (Path(__file__).parent/'fictional-composition.json').write_text(json.dumps(output,indent=2))
NaturalAgent.validate_composition=inspect_fictional
app=build(8892,database=ROOT/'alternatives/advisor-first/var/verification-natural/guides.sqlite3')
print('Fictional verification only at :8892',flush=True)
app.serve_forever()
