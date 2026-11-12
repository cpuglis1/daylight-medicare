#!/usr/bin/env python3
"""D86 isolated local service. Shared engine is read-only and hash pinned."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

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
from natural_agent import NaturalAgent
from advisor_models import DEFAULT_MODEL, MODELS, model_clients
from situation import FIELDS as SITUATION_FIELDS
from natural_state import legacy_projection
from guest_profiles import ProfileError
from advisor_budget import AdvisorDailyBudget
from provider_tokens import count_input_tokens
from research_http import install_research_routes
from identity_http import install_identity_routes
from understanding import VERSION as UNDERSTANDING_VERSION
from task_work import VERSION as TASK_WORK_VERSION
from response_question_recovery import VERSION as RESPONSE_RELIABILITY_VERSION

def build(port=8893, *, fixture=False, database=None, client=None, count_tokens=None,
          research_repository=None, reference_adapter=None, identity_service=None,
          comparison_preview=False, research_catalog=None):
    if port in {8890,8891,8896}:
        raise ValueError('That port belongs to a preserved Daylight surface.')
    db = Path(database).resolve() if database else HERE/'var/profiles/guides.sqlite3'
    previews = None
    if comparison_preview:
        temporary_roots = (Path('/tmp').resolve(), Path(tempfile.gettempdir()).resolve())
        if (not fixture or not database or db.exists()
                or not any(db.is_relative_to(root) for root in temporary_roots)
                or any(service is not None for service in (research_repository, reference_adapter,
                                                           identity_service, research_catalog))):
            raise ValueError('The D91 preview needs fixture mode and a fresh temporary database.')
        from comparison_preview import load_preview
        previews = load_preview()
    if not fixture:
        load_model_env(REPO/'.env')
    if not fixture and not db.is_relative_to(HERE/'var'):
        raise ValueError('Live advisor records must stay in this variant’s private var directory.')
    policy=json.loads((HERE/'model-policy.json').read_text())
    if set(policy)-{'version','reasoning_effort','composition_reasoning_effort','output_tokens'} or not {'version','reasoning_effort','output_tokens'} <= set(policy) or policy['reasoning_effort'] not in {'none','low','medium'} or policy['output_tokens']!=900:
        raise ValueError('Use the reviewed bounded model policy.')
    config = {'mockAI':fixture,'advisorFirst':True,'variant':'D86','modelPolicy':policy,
              **({'comparisonPreview':True} if previews is not None else {}),
              'understandingContract':UNDERSTANDING_VERSION,'taskWorkContract':TASK_WORK_VERSION,
              'responseReliabilityContract':RESPONSE_RELIABILITY_VERSION}
    service=make_server(port, database=db, web=HERE/'web', client=client,
        enable_live=not fixture, live_limit=None, count_tokens=count_tokens or count_input_tokens,
        budget_database=None if fixture else REPO/'cms-slice/var/ai-budget/usage.sqlite3',
        cookie_namespace='daylight_advisor_fixture' if fixture else 'daylight_advisor_dev',
        ui_config=config, conversation_class=ChatConversation, profile_gate_class=ProfileReadiness,
        adaptive_class=NaturalConversation)
    try:
        if service.budget:
            # The pinned factory captures this same object in its HTTP handlers
            # and all agents. Adopt the local approved policy in place so every
            # path enforces/reports it without editing the shared engine.
            AdvisorDailyBudget.adopt(service.budget, policy_path=HERE/'budget-policy.json',
                                     pricing_review_path=HERE/'pricing-review.json')
    except Exception:
        service.server_close()
        raise
    service.adaptive.agent.reasoning_effort=policy['reasoning_effort']
    service.adaptive.agent.composition_reasoning_effort=policy.get('composition_reasoning_effort', 'none')
    if service.adaptive.agent.composition_reasoning_effort not in {'none','low','medium'}:
        service.server_close()
        raise ValueError('Use the reviewed composition reasoning setting.')
    if not fixture:
        base = service.adaptive.agent
        clients = model_clients(base.client, REPO/'.env')
        service.adaptive.model_agents = {identifier: base if provider_client is base.client
            else NaturalAgent.from_agent(base, client=provider_client)
            for identifier, provider_client in clients.items()}
        for agent in service.adaptive.model_agents.values():
            agent.connection_retries = 1
        config['connectionRecovery'] = {'maxRetriesPerStage': 1, 'countsTowardDailyCap': True}
        config['models'] = [{'id': identifier, 'label': MODELS[identifier].label,
                            'provider': MODELS[identifier].provider,
                            'available': provider_client.available and provider_client.model == identifier}
                           for identifier, provider_client in clients.items()]
        config['defaultModel'] = DEFAULT_MODEL
        parent_handler = service.RequestHandlerClass
        class RecoveryStatusHandler(parent_handler):
            def respond(self, code, value, mime='application/json; charset=utf-8', cookie=None):
                if isinstance(value, dict) and 'automatic_retries' in value:
                    value = {**value, 'automatic_retries': True,
                             'connection_recovery': config['connectionRecovery']}
                return super().respond(code, value, mime, cookie)
        service.RequestHandlerClass = RecoveryStatusHandler
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
    original_delete=service.profiles.delete
    def delete_and_forget_visit(token,csrf,expected):
        owner=service.profiles.digest(token)
        with service.adaptive.lock:
            if owner in service.adaptive.natural_active:
                raise ProfileError('A message is still processing. Try deleting after it finishes.', 409)
            result=original_delete(token,csrf,expected)
            service.adaptive.forget_owner(owner)
            return result
    service.profiles.delete=delete_and_forget_visit
    service=install_research_routes(service, research_repository, reference_adapter,
                                    previews=previews, catalog=research_catalog)
    return install_identity_routes(service, identity_service)

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8893)
    parser.add_argument('--fixture',action='store_true')
    parser.add_argument('--database',type=Path)
    parser.add_argument('--comparison-preview', action='store_true',
                        help='Show the D91 educational comparison in an isolated fixture visit.')
    parser.add_argument('--local-research', action='store_true',
                        help='Connect the exact existing private 2026 research build; no consumer release.')
    parser.add_argument('--identity-research',action='store_true',
                        help='Explicit internal-only identity review; no consumer source purpose or personal findings.')
    args=parser.parse_args()
    if args.comparison_preview and (not args.fixture or args.local_research or args.identity_research):
        parser.error('--comparison-preview requires --fixture and separate temporary storage')
    repository = None
    reference_adapter = None
    identity_service = None
    research_catalog = None
    if args.local_research:
        from catalog_research import CatalogResearch
        from comparison_research import local_repository
        from published_reference import PublishedReferenceAdapter
        repository = local_repository()
        reference_adapter = PublishedReferenceAdapter()
        research_catalog = CatalogResearch()
    if args.identity_research:
        from identity_journey import local_identity_journey
        identity_service=local_identity_journey(internal_research=True)
    service=build(args.port,fixture=args.fixture,database=args.database,
                  research_repository=repository,reference_adapter=reference_adapter,identity_service=identity_service,
                  comparison_preview=args.comparison_preview,research_catalog=research_catalog)
    print(f'Daylight advisor-first at http://127.0.0.1:{service.server_port}/',flush=True)
    try:service.serve_forever()
    except KeyboardInterrupt:pass
    finally:service.server_close()
