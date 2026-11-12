#!/usr/bin/env python3
"""D86 isolated local service. Shared engine is read-only and hash pinned."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ENGINE = REPO / 'alternatives/chat-first/cms-slice/scripts'

def verify_engine():
    for name, expected in json.loads((HERE/'engine-lock.json').read_text()).items():
        path = REPO/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError('The pinned shared engine changed. Review and update engine-lock.json before starting: '+name)

verify_engine()
sys.path.insert(0, str(ENGINE))
from guide_server import make_server
from chat_conversation import ChatConversation
from profile_readiness import ProfileReadiness
from runtime_env import load_model_env
from natural_flow import NaturalConversation
from situation import FIELDS as SITUATION_FIELDS
from natural_state import legacy_projection
from advisor_budget import AdvisorDailyBudget

def build(port=8893, *, fixture=False, database=None, client=None, count_tokens=None):
    if port in {8890,8891,8896}:
        raise ValueError('That port belongs to a preserved Daylight surface.')
    if not fixture:
        load_model_env(REPO/'.env')
    db = Path(database).resolve() if database else HERE/'var/profiles/guides.sqlite3'
    if not fixture and not db.is_relative_to(HERE/'var'):
        raise ValueError('Live advisor records must stay in this variant’s private var directory.')
    policy=json.loads((HERE/'model-policy.json').read_text())
    if set(policy)-{'version','reasoning_effort','composition_reasoning_effort','output_tokens'} or not {'version','reasoning_effort','output_tokens'} <= set(policy) or policy['reasoning_effort'] not in {'none','low','medium'} or policy['output_tokens']!=900:
        raise ValueError('Use the reviewed bounded model policy.')
    service=make_server(port, database=db, web=HERE/'web', client=client,
        enable_live=not fixture, live_limit=None, count_tokens=count_tokens,
        budget_database=None if fixture else REPO/'cms-slice/var/ai-budget/usage.sqlite3',
        cookie_namespace='daylight_advisor_fixture' if fixture else 'daylight_advisor_dev',
        ui_config={'mockAI':fixture,'advisorFirst':True,'variant':'D86','modelPolicy':policy},
        conversation_class=ChatConversation, profile_gate_class=ProfileReadiness,
        adaptive_class=NaturalConversation)
    try:
        if service.budget:
            # The pinned factory captures this same object in its HTTP handlers
            # and all agents. Adopt the local approved policy in place so every
            # path enforces/reports it without editing the shared engine.
            AdvisorDailyBudget.adopt(service.budget, policy_path=HERE/'budget-policy.json')
    except Exception:
        service.server_close()
        raise
    service.adaptive.agent.reasoning_effort=policy['reasoning_effort']
    service.adaptive.agent.composition_reasoning_effort=policy.get('composition_reasoning_effort', 'none')
    if service.adaptive.agent.composition_reasoning_effort not in {'none','low','medium'}:
        service.server_close()
        raise ValueError('Use the reviewed composition reasoning setting.')
    # Compatibility is transient: source/plan gates consume reported inputs,
    # while the stored natural record retains its honest capture status.
    original_gate_validate=service.profile_gate.validate_inputs
    def natural_gate_validate(guide,record):
        guide,record=service.adaptive.validate(guide,record)
        guide,record=legacy_projection(guide,record)
        return original_gate_validate(guide,record)
    service.profile_gate.validate_inputs=natural_gate_validate
    # Cover the retained direct profile PUT as well as conversation/save.
    # Tighten the local instance; never modify shared profile/storage code.
    original_save=service.profiles.save
    def private_situation_save(token,csrf,expected,operation,guide):
        guide,_=service.adaptive.validate(guide,service.adaptive.initial()[1])
        if not guide['preferences'].get('saveSensitive'):
            for field in SITUATION_FIELDS.values():guide['fields'].pop(field,None)
        return original_save(token,csrf,expected,operation,guide)
    service.profiles.save=private_situation_save
    return service

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8893)
    parser.add_argument('--fixture',action='store_true')
    parser.add_argument('--database',type=Path)
    args=parser.parse_args()
    service=build(args.port,fixture=args.fixture,database=args.database)
    print(f'Daylight advisor-first at http://127.0.0.1:{service.server_port}/',flush=True)
    try:service.serve_forever()
    except KeyboardInterrupt:pass
    finally:service.server_close()
