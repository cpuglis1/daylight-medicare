"""D185-D187 explicit hosted entry point; no .env, local ledger or local stores.

Build the pinned factory with live mode OFF to avoid development ledger seeding,
then wire only the invite-allowlisted adaptive path to the hosted client/ledger.
The synthetic mode is for offline verification, never a live-provider probe.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from server import build, HERE, REPO
from chat import ResponsesClient
from hosted_history import PostgresHistory, install as install_history
from natural_agent import NaturalAgent
import model_router

MODEL = 'gpt-6.1-sol'


def enable_features(flow, medigap, pdp, history=None):
    # Explicit promotion of the existing conversation feature baseline. No
    # research tools, local trace or shadow service. D199 adds the owner-approved
    # facts surface, archived block release, plan review, sorting and checks.
    import enrollment_flow, conversation_planner, conversation_records, plans_fixes, turn_progress
    from pilot_access import participant
    enrollment_flow.enable(flow)
    conversation_planner.enable(flow)
    flow.pilot_knowledge.surface = 'hosted-demo'  # D199: r3 acceptance and the D163 hold
    class MetadataProgress(turn_progress.Progress):
        def publish(self,key,blocks):
            # D199: a checked block is shown only after it is saved to the visit's history.
            # Without the block archive, text stays hidden until the complete reply is archived.
            if history is None or not getattr(history,'publish_blocks',None):
                return
            try:
                saved = history.publish_blocks(participant.get(), key[1], blocks)
            except Exception:
                return
            if saved:
                super().publish(key,blocks)
    flow.turn_progress = MetadataProgress()
    flow.guided_close = flow.composed_opening = True
    conversation_records.enable(flow)
    conversation_records.enable_pending(flow)
    conversation_records.enable_fixes(flow)
    plans_fixes.enable(flow)
    from medigap_pilot import DATE, prices
    flow.closing_price_read = lambda inputs: turn_progress.run('plans', prices, medigap,
                                                              {**inputs,'effective_date':DATE})
    def selection_read(product,g,r):
        import medigap_profile, part_d_pilot, part_d_profile
        if product == 'part_d':
            view = part_d_profile.profile(g,r)
            if view.get('status') != 'ready': return []
            scope = {k:view['inputs'][k] for k in ('zipcode','county_fips','year')}
            return part_d_pilot.published_plans(pdp,scope,flow.reference['zips']).get('plans',[])
        view = medigap_profile.for_flow(flow,g,r)
        return (prices(medigap,{**view['inputs'],'effective_date':DATE}).get('plans',[])
                if view.get('status') == 'ready' else [])
    flow.plans_selection_read = selection_read


def build_hosted(port, *, state, origin, ledger, history, binding, medigap, pdp,
                 release, synthetic=False, key=None, paused=False, checks=None, demo_policy=None):
    if demo_policy not in {None, 'owner', 'accelerator'}:
        raise ValueError('Unknown hosted demo policy.')
    import block_release
    block_archive = False
    if block_release.enabled():
        # D199: early blocks need the per-block archive; otherwise refuse to start.
        if not getattr(history,'publish_blocks',None) or not (synthetic or history.check_blocks()):
            raise ValueError('Hosted history requires reply delivery after its archive commit.')
        block_archive = True
    if not all(isinstance(value,str) and len(value)==64 and all(c in '0123456789abcdef' for c in value)
               for value in (release,binding.get('snapshot_id'))):
        raise ValueError('Use exact release and source snapshot digests.')
    if not synthetic:
        if not isinstance(history,PostgresHistory):
            raise ValueError('Live hosted chat requires PostgreSQL history.')
        history.check_runtime_role()
        if os.environ.get('DAYLIGHT_MODEL_ENVIRONMENT') != 'hosted-demo':
            raise ValueError('This fictional hosted release requires the reviewed hosted-demo route.')
        if not paused and model_router.allowed_models() != {MODEL}:
            raise ValueError('The dedicated hosted provider route is not configured.')
        if not paused and (not isinstance(key,str) or not key.strip()):
            raise ValueError('The hosted API credential is not installed.')
    policy_hash = hashlib.sha256()
    for name in ('conversation_prompts.py','natural_agent.py','model-policy.json','model-routes.json'):
        policy_hash.update(name.encode()); policy_hash.update((HERE/name).read_bytes())
    metadata = {'release':release,'data_snapshot':binding['snapshot_id'], 'model':MODEL,
                'reasoning':'low','prompt_policy':policy_hash.hexdigest()}
    if demo_policy:
        metadata['service_tier'] = 'ultrafast' if demo_policy == 'accelerator' else 'default'

    def setup(service,access,budget,config):
        if not access.hosted_schema:
            raise ValueError('Migrate hosted invitation state first.')
        with budget.db() as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='pilot_visit_link'").fetchone():
                raise ValueError('Migrate shared-budget attribution first.')
        budget.requires_history_consent = True
        if demo_policy:
            budget.configure_hosted(demo_policy)
        client = ResponsesClient(key='' if synthetic or paused else key,model=MODEL,reasoning_effort='low')
        client.service_tier = metadata.get('service_tier', 'default')
        agent = NaturalAgent.from_agent(service.adaptive.agent,client=client)
        agent.enabled = not synthetic and not paused
        agent.budget = budget
        agent.pilot_scope = True
        agent.connection_retries = 1
        agent.composition_recovery = True
        service.adaptive.agent = agent
        service.adaptive.model_agents = {MODEL:agent} if not synthetic else {}
        service.adaptive.fixture = synthetic
        service.hosted_release = release
        service.hosted_synthetic = synthetic
        service.hosted_paused = paused
        service.hosted_budget = budget
        service.hosted_block_archive = block_archive
        config.update(mockAI=synthetic,defaultModel=MODEL,
            models=[{'id':MODEL,'label':'GPT-6.1 Sol','provider':'OpenAI','available':not synthetic and not paused}])
        enable_features(service.adaptive,medigap,pdp,history)
        if checks is not None:
            service.adaptive.conversation_checks = conversation_checks(service.adaptive,pdp,*checks)
        install_history(service,access,history,budget,metadata)

    # D199: Medicare Advantage values under the existing local review, evaluation-only
    # sorting and the doctor/medicine checks, for the invited fictional demo.
    return build(port,fixture=True,pilot_state=state,pilot_origin=origin,pilot_ledger=ledger,
        pilot_display_binding=binding,medigap_repository=medigap,part_d_repository=pdp,hosted_setup=setup,
        hosted_plans_review=True,hosted_recommendation=True,hosted_checks=checks is not None)


def conversation_checks(flow, pdp, doctors, drugs):
    """The same check controller :8895 uses, over the hosted doctor/drug readers."""
    from catalog_research import CatalogResearch
    from comparison_research import RESEARCH_SCOPE
    from conversation_checks import ConversationChecks
    from part_d_pilot import published_plans
    catalog = CatalogResearch()
    def plans():
        ma = catalog.query(RESEARCH_SCOPE)
        try:
            drug = published_plans(pdp,{'zipcode':'34102','county_fips':'12021','year':2026},flow.reference['zips'])
        except (OSError, RuntimeError, ValueError):
            drug = {'plans': []}
        return ([{'id':p['offering_id'],'name':p['name']} for p in ma['plans']]
                + [{'id':p['id'],'name':p['name']} for p in drug['plans']])
    return ConversationChecks(flow, doctors, drugs, plans)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True,type=Path)
    parser.add_argument('--synthetic',action='store_true')
    parser.add_argument('--paused',action='store_true',help='Real browsing, with all provider calls disabled.')
    args=parser.parse_args()
    config=json.loads(args.config.read_text())
    expected={'port','state','origin','ledger','history_dsn','display_dsn','binding','release','key_file','environment'}
    optional={'foundation_binding','foundation_root','foundation_dsn','controls_dsn'}  # D199 doctor/drug checks
    if not expected<=set(config)<=expected|optional|{'demo_policy'} or set(config)&optional not in (set(),optional):
        parser.error('Use the exact hosted configuration fields.')
    if config['environment'] not in {'pilot','test'}:
        parser.error('Use a dedicated hosted environment.')
    if 'demo_policy' in config and config['demo_policy'] != {'pilot':'accelerator','test':'owner'}[config['environment']]:
        parser.error('Demo policy does not match the dedicated environment.')
    sys.path.insert(0,str(REPO/'infrastructure/daylight-data/src'))
    from daylight_data.pilot_subset.store import repositories
    binding=json.loads(Path(config['binding']).read_text())
    medigap,pdp=repositories(config['binding'],dsn=config['display_dsn'])
    checks=None
    if 'foundation_binding' in config:
        from daylight_data.serving.part_d_local import hosted_readers
        checks=hosted_readers(Path(config['foundation_root']),config['foundation_binding'],package_dsn=config['foundation_dsn'],
                              controls_dsn=config['controls_dsn'])
    key=None
    if not args.synthetic and not args.paused:
        path=Path(config['key_file'])
        if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
            parser.error('Use a private regular runtime credential file.')
        key=path.read_text().strip()
    with build_hosted(config['port'],state=config['state'],origin=config['origin'],ledger=config['ledger'],
        history=PostgresHistory(config['history_dsn'],deletion_environment=config['environment']),binding=binding,medigap=medigap,pdp=pdp,
        release=config['release'],synthetic=args.synthetic,key=key,paused=args.paused,checks=checks,
        demo_policy=config.get('demo_policy')) as service:
        service.serve_forever()


if __name__=='__main__':
    main()
