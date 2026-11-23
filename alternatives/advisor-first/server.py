#!/usr/bin/env python3
"""D86 isolated local service. Shared engine is read-only and hash pinned."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ENGINE = REPO / 'alternatives/chat-first/cms-slice/scripts'

def verify_engine():
    for name, expected in json.loads((HERE/'engine-lock.json').read_text()).items():
        path = REPO/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError('The pinned shared engine changed. Review and update engine-lock.json before starting: '+name)

verify_engine()
import model_router
# AI-03/AI-04: approved model calls leave only through provider_transport's curl
# process after the route check. Refuse in-process lookups of provider hosts
# before loading the pinned engine, which has its own direct provider calls.
model_router.install_bypass_guard()
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
from session_recovery import install_session_recovery
from plan_review_http import install_plan_review
from plans_http import install_plans
from medigap_pilot import install_medigap
from medigap_profile import FIELDS as MEDIGAP_FIELDS, profile as medigap_profile_view
from part_d_pilot import install_part_d
from part_d_profile import profile as part_d_profile_view
import enrollment_flow

def build(port=8893, *, fixture=False, database=None, client=None, count_tokens=None,
          research_repository=None, reference_adapter=None, identity_service=None,
          comparison_preview=False, research_catalog=None, pilot_state=None, pilot_origin=None,
          medigap_repository=None, part_d_repository=None, local_demo=False, pilot_display_binding=None,
          pilot_ledger=None, hosted_setup=None, hosted_plans_review=False, hosted_recommendation=False,
          hosted_checks=False):
    if port in {8890,8891,8896}:
        raise ValueError('That port belongs to a preserved Daylight surface.')
    if pilot_origin is not None:
        origin = urlsplit(pilot_origin)
        if (pilot_state is None or origin.scheme != 'https' or not origin.hostname
                or origin.username is not None or origin.password is not None
                or pilot_origin != f'https://{origin.netloc}' or origin.port is not None):
            raise ValueError('Use an explicit HTTPS origin without a path or port for the hosted pilot rehearsal.')
    if local_demo and (port in {8893, 8894} or pilot_state is not None or pilot_origin is not None
                       or research_repository is not None or identity_service is not None or comparison_preview):
        raise ValueError('The unified local demo uses its own port and display-only data services.')
    demo_store = HERE/'var/demo-8895'
    default_db = demo_store/('fixture.sqlite3' if fixture else 'guides.sqlite3') if local_demo else HERE/'var/profiles/guides.sqlite3'
    db = Path(database).resolve() if database else default_db
    if local_demo and not fixture and not db.is_relative_to(demo_store.resolve()):
        raise ValueError('The unified local demo must use its separate private store.')
    pilot = pilot_budget = None
    if (pilot_ledger is not None or hosted_setup is not None) and not (pilot_state and pilot_origin):
        raise ValueError('Hosted setup requires the isolated pilot state and HTTPS origin.')
    # D199: owner-approved hosted invited-demo features; never available without hosted setup.
    if (hosted_plans_review or hosted_recommendation or hosted_checks) and (
            hosted_setup is None or not pilot_display_binding):
        raise ValueError('Hosted demo features require the hosted setup and bound display stores.')
    if pilot_display_binding and (not pilot_state or not pilot_origin or not fixture
                                  or not medigap_repository or not part_d_repository):
        raise ValueError('The hosted display rehearsal requires its HTTPS origin and explicit bound display stores.')
    if pilot_state is not None:
        if (not fixture or comparison_preview or any(option is not None for option in (
                database, client, count_tokens, research_repository, reference_adapter,
                identity_service, research_catalog)) or
                not pilot_display_binding and (medigap_repository is not None or part_d_repository is not None)):
            raise ValueError('Pilot rehearsal requires fixture mode and its isolated stores.')
        from pilot_access import GUEST_COOKIE, PilotAccess, install_pilot_gate
        from pilot_budget import PilotBudget
        pilot = PilotAccess(pilot_state)
        pilot_budget = PilotBudget.open(pilot, ledger_path=pilot_ledger)
        db = pilot.root / 'fictional-profiles.sqlite3'
        if db.is_symlink():
            raise ValueError('Pilot rehearsal requires a regular local profile store.')
    previews = None
    if comparison_preview:
        temporary_roots = (Path('/tmp').resolve(), Path(tempfile.gettempdir()).resolve())
        if (not fixture or not database or db.exists()
                or not any(db.is_relative_to(root) for root in temporary_roots)
                or any(service is not None for service in (research_repository, reference_adapter,
                                                           identity_service, research_catalog, medigap_repository, part_d_repository))):
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
    config = {'mockAI':fixture,'advisorFirst':True,'advisorName':'Daylight','variant':'D86','modelPolicy':policy,
              **({'comparisonPreview':True} if previews is not None else {}),
              'understandingContract':UNDERSTANDING_VERSION,'taskWorkContract':TASK_WORK_VERSION,
              'responseReliabilityContract':RESPONSE_RELIABILITY_VERSION}
    service=make_server(port, database=db, web=HERE/'web', client=client, public_origin=pilot_origin,
        enable_live=not fixture, live_limit=None, count_tokens=count_tokens or count_input_tokens,
        budget_database=None if fixture else REPO/'cms-slice/var/ai-budget/usage.sqlite3',
        cookie_namespace=(('daylight_demo_8895_fixture' if fixture else 'daylight_demo_8895_dev') if local_demo
                          else GUEST_COOKIE if pilot else ('daylight_advisor_fixture' if fixture else 'daylight_advisor_dev')),
        ui_config=config, conversation_class=ChatConversation, profile_gate_class=ProfileReadiness,
        adaptive_class=NaturalConversation)
    # D159: the owner's general-education acceptance applies only to :8895.
    service.adaptive.pilot_knowledge.surface = (
        'unified-8895' if local_demo and service.server_port == 8895 else None)
    # Keep shared-profile presentation local; the pinned engine's Daylight
    # busy messages now use the current brand without response rewriting.
    parent_handler = service.RequestHandlerClass
    class BrandedResponseHandler(parent_handler):
        def respond(self, code, value, mime='application/json; charset=utf-8', cookie=None):
            if code == 200 and self.path == '/api/conversation/initial' and isinstance(value, dict) and 'guide' in value:
                value = {**value, 'medigapProfile': medigap_profile_view(value['guide'])}
                value['partDProfile'] = part_d_profile_view(value['guide'], value['record'])
                if enrollment_flow.enabled(service.adaptive):
                    # D161: the two-path dashboard is there from the first screen, before any turn.
                    value['enrollment'] = enrollment_flow.view(service.adaptive, value['guide'], value['record'])
            return super().respond(code, value, mime, cookie)
    service.RequestHandlerClass = BrandedResponseHandler
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
            agent.composition_recovery = True
        config['connectionRecovery'] = {'maxRetriesPerStage': 1, 'countsTowardDailyCap': True}
        routed = model_router.allowed_models()
        config['models'] = [{'id': identifier, 'label': MODELS[identifier].label,
                            'provider': MODELS[identifier].provider,
                            'available': (provider_client.available and provider_client.model == identifier
                                          and identifier in routed)}
                           for identifier, provider_client in clients.items()]
        config['defaultModel'] = DEFAULT_MODEL
        parent_handler = service.RequestHandlerClass
        class RecoveryStatusHandler(parent_handler):
            def respond(self, code, value, mime='application/json; charset=utf-8', cookie=None):
                if (code == 200 and isinstance(value, dict) and service.budget
                        and self.path in {'/api/ai/usage', '/api/status'}):
                    value = {**value, 'providerBudgets': service.budget.provider_summaries()}
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
            for field in MEDIGAP_FIELDS.values():guide['fields'].pop(field,None)
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
    service = install_plans(install_plan_review(install_session_recovery(install_identity_routes(service, identity_service))),
                            local_review=research_catalog is not None or hosted_plans_review)
    service = install_medigap(service, medigap_repository)
    service = install_part_d(service, part_d_repository)
    if local_demo or hosted_recommendation:
        # D147: evaluation-only tiered recommendation on the local demo. D199: the owner
        # approved it for the hosted invited fictional demo as well (still evaluation-only).
        from recommendation_http import install_recommendation
        service = install_recommendation(service, medigap_repository, part_d_repository)
        service.hosted_recommendation = bool(hosted_recommendation)
    if pilot:
        # Owner direction (DQ-01 pilot scope): replies say this is a pilot on 2026 sample data.
        for agent in {service.adaptive.agent, *getattr(service.adaptive, 'model_agents', {}).values()}:
            agent.budget = pilot_budget
            agent.pilot_scope = True
        if pilot_display_binding:
            from demo_http import install

            service = install(service, binding=pilot_display_binding, fixture=True, hosted_origin=pilot_origin,
                              conversation_checks=hosted_checks)
        if hosted_setup is not None:
            try:
                hosted_setup(service, pilot, pilot_budget, config)
            except Exception:
                service.server_close()
                raise
        service = install_pilot_gate(service, pilot, pilot_budget, hosted_origin=pilot_origin is not None,
                                     plan_display=bool(pilot_display_binding))
    return service

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8893)
    parser.add_argument('--fixture',action='store_true')
    parser.add_argument('--pilot-state', type=Path, help='Run the isolated fictional pilot rehearsal.')
    parser.add_argument('--pilot-origin', help='HTTPS origin of the fictional pilot behind a loopback proxy.')
    parser.add_argument('--pilot-tls-cert', type=Path)
    parser.add_argument('--pilot-tls-key', type=Path)
    parser.add_argument('--database',type=Path)
    parser.add_argument('--comparison-preview', action='store_true',
                        help='Show the D91 educational comparison in an isolated fixture visit.')
    parser.add_argument('--local-research', action='store_true',
                        help='Connect the exact existing private 2026 research build; no consumer release.')
    parser.add_argument('--pilot-data', type=Path,
                        help='Use a verified local display-subset binding and DAYLIGHT_PILOT_DATABASE_URL.')
    parser.add_argument('--pilot-display-binding', type=Path,
                        help='Run the hosted fictional display rehearsal with a bound PostgreSQL subset.')
    parser.add_argument('--identity-research',action='store_true',
                        help='Explicit internal-only identity review; no consumer source purpose or personal findings.')
    args=parser.parse_args()
    if args.pilot_display_binding and (not args.fixture or not args.pilot_state or not args.pilot_origin or any(
            (args.database, args.pilot_data, args.local_research, args.identity_research, args.comparison_preview))):
        parser.error('--pilot-display-binding requires --fixture, --pilot-state and --pilot-origin without other data modes')
    if args.pilot_data and (args.local_research or args.identity_research or args.comparison_preview or args.pilot_state):
        parser.error('--pilot-data is a separate local display mode; do not combine research/identity/preview/pilot rehearsal modes')
    if (args.pilot_tls_cert or args.pilot_tls_key) and not (
            args.pilot_tls_cert and args.pilot_tls_key and args.pilot_state and args.fixture):
        parser.error('Pilot TLS requires the certificate, key and fixture pilot state.')
    if args.comparison_preview and (not args.fixture or args.local_research or args.identity_research):
        parser.error('--comparison-preview requires --fixture and separate temporary storage')
    repository = None
    reference_adapter = None
    identity_service = None
    research_catalog = None
    medigap_repository = None
    part_d_repository = None
    if args.local_research or args.pilot_data:
        from catalog_research import CatalogResearch, CRITICAL_BENEFITS_PATH
        research_catalog = CatalogResearch(critical_benefits_path=CRITICAL_BENEFITS_PATH)
    if args.local_research:
        from comparison_research import local_repository
        from published_reference import PublishedReferenceAdapter
        repository = local_repository()
        reference_adapter = PublishedReferenceAdapter()
        from medigap_pilot import local_repository as local_medigap_repository
        medigap_repository = local_medigap_repository()
        from part_d_pilot import local_repository as local_part_d_repository
        part_d_repository = local_part_d_repository()
    if args.pilot_data:
        import sys
        sys.path.insert(0, str(REPO / 'infrastructure/daylight-data/src'))
        from daylight_data.pilot_subset.store import repositories
        medigap_repository, part_d_repository = repositories(args.pilot_data)
    pilot_display_binding = None
    if args.pilot_display_binding:
        sys.path.insert(0, str(REPO / 'infrastructure/daylight-data/src'))
        from daylight_data.pilot_subset.store import repositories

        pilot_display_binding = json.loads(args.pilot_display_binding.read_text())
        medigap_repository, part_d_repository = repositories(args.pilot_display_binding)
    if args.identity_research:
        from identity_journey import local_identity_journey
        identity_service=local_identity_journey(internal_research=True)
    service=build(args.port,fixture=args.fixture,database=args.database,
                  research_repository=repository,reference_adapter=reference_adapter,identity_service=identity_service,
                  comparison_preview=args.comparison_preview,research_catalog=research_catalog,
                  pilot_state=args.pilot_state,pilot_origin=args.pilot_origin,
                  medigap_repository=medigap_repository,part_d_repository=part_d_repository,
                  pilot_display_binding=pilot_display_binding)
    try:
        if args.pilot_origin:
            import logging
            logger = logging.getLogger('daylight.pilot.access')
            logger.setLevel(logging.INFO)
            logger.addHandler(logging.StreamHandler())
            logger.propagate = False
        scheme = 'http'
        if args.pilot_tls_cert:
            import ssl
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(args.pilot_tls_cert, args.pilot_tls_key)
            service.socket = context.wrap_socket(service.socket, server_side=True, do_handshake_on_connect=False)
            service.pilot_tls = True
            scheme = 'https'
        print(f'Daylight advisor-first at {scheme}://127.0.0.1:{service.server_port}/',flush=True)
        service.serve_forever()
    except KeyboardInterrupt:pass
    finally:service.server_close()
