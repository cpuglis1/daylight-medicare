"""Pure server evaluator bridge for semantic DOM fixtures. No HTTP, DB or provider."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from profile_readiness import ProfileReadiness
W=ROOT/'apps/chat-alternative';payload=json.load(sys.stdin)
a=ProfileReadiness(None,None,json.loads((W/'guide-contract.json').read_text()),json.loads((W/'readiness-content.json').read_text()),json.loads((W/'sample-plans.json').read_text()))
print(json.dumps(a.assess(payload['guide'],payload['record'],payload.get('requestedCapabilities'))))
