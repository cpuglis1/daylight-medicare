"""Record local implementation hashes, without environment or customer files."""
import hashlib
import json
from pathlib import Path

packet=Path(__file__).resolve().parent
root=packet.parents[1]
paths=[
    'alternatives/advisor-first/natural_flow.py',
    'alternatives/advisor-first/natural_agent.py',
    'alternatives/advisor-first/natural_state.py',
    'alternatives/advisor-first/narrative_agent.py',
    'alternatives/advisor-first/situation.py',
    'alternatives/advisor-first/server.py',
    'alternatives/advisor-first/model-policy.json',
    'alternatives/advisor-first/web/advisor.js',
    'alternatives/advisor-first/README.md',
    'alternatives/advisor-first/AGENTS.md',
    'DAYLIGHT_REQUIREMENTS.md',
    'docs/product/MASTER_DESIGN.md',
    'docs/product/NATURAL_ADVISOR_FLOW_PLAN_2026-10-30.md',
]
paths += [str(path.relative_to(root)) for path in (root/'alternatives/advisor-first/tests').glob('test_*.py')]
result={}
for relative in sorted(paths):
    data=(root/relative).read_bytes()
    old=packet/'before'/relative
    result[relative]={'sha256':hashlib.sha256(data).hexdigest(), 'bytes':len(data)}
    if old.is_file():
        result[relative]['beforeSha256']=hashlib.sha256(old.read_bytes()).hexdigest()
        result[relative]['changedFromSnapshot']=old.read_bytes()!=data
(packet/'build-manifest.json').write_text(json.dumps(result,indent=2)+'\n')
print(f'Recorded {len(result)} implementation/document/test files.')
