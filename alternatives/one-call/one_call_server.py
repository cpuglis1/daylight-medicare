#!/usr/bin/env python3
"""The one-call variant on its own loopback port (8897).

Same interface files, same advisor API and the same data wiring as the unified
local demo on :8895 (``demo_server.build_demo``), with ``OneCallConversation``
as the conversation class. Nothing in advisor-first is edited: its server is
built as it builds itself, the conversation it constructed is re-classed in
place (``OneCallConversation.adopt``), and the switches :8895 turns on are
applied here.

``--fixture`` starts the server with no database, no model and no network. A
test may also inject a scripted client in fixture mode, which runs the real
one-call turn against that client.

The owner ran this variant against a live model for the first time on 2026-11-22.
No test and no agent has made a live call with it.
"""
import _paths  # noqa: F401  (puts advisor-first on sys.path and registers the pinned engine)

import argparse
import getpass
import json
import logging
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from advisor_models import MODELS
from catalog_research import CatalogResearch, CRITICAL_BENEFITS_PATH
from demo_http import install
from server import REPO, build
import log_guard

from one_call_flow import (LOGGERS, ONE_CALL_REASONING_EFFORT, ONE_CALL_REQUEST_BYTES, TRACE_FILE,
                           OneCallConversation, trace_switch_on)

LOGGER = logging.getLogger(__name__)

PORT = 8897
SURFACE = 'one-call-8897'          # a label for the status route; not a pilot-knowledge acceptance surface
# 8890, 8891 and 8896 are preserved surfaces; 8893, 8894 and 8895 are advisor-first's own.
REFUSED_PORTS = frozenset({8890, 8891, 8893, 8894, 8895, 8896})
PACKAGE = REPO / 'infrastructure/daylight-data'
DEFAULT_BINDING = PACKAGE / '.state/pilot-subset/2026-11-12-r1/binding.json'
# advisor-first's server keeps a live local demo's guest store inside its own private folder
# and refuses any other place. The variant gets its own file there, apart from :8895's.
LIVE_DATABASE = _paths.ADVISOR / 'var/demo-8895/one-call-8897.sqlite3'


def configure(flow, *, medigap_repository=None, part_d_repository=None):
    """Turn on what ``demo_server.build_demo`` turns on for :8895, on any conversation.

    Parts A and B, the discussion planner, turn progress, the guided close, the
    composed opening, the profile and education records with their two
    follow-on switches, the Plans fixes and, when a Medigap source is given,
    the closing price read. The environment switches :8895 honours are honoured
    here. Used for the 8897 server and for the bake-off's two flow factories,
    so both loops run with the same switches.
    """
    import conversation_planner
    import conversation_records
    import enrollment_flow
    import plans_fixes
    import turn_progress
    enrollment_flow.enable(flow)
    conversation_planner.enable(flow)
    flow.turn_progress = turn_progress.Progress()
    flow.guided_close = True
    flow.composed_opening = True
    if conversation_records.switch_on():
        conversation_records.enable(flow)
        if conversation_records.pending_switch_on():
            conversation_records.enable_pending(flow)
        if conversation_records.fixes_switch_on():
            conversation_records.enable_fixes(flow)
    if plans_fixes.switch_on():
        plans_fixes.enable(flow)
        if medigap_repository is not None and part_d_repository is not None:
            def selection_read(product, g, r):
                import medigap_profile, part_d_pilot, part_d_profile
                from medigap_pilot import DATE as date_, prices as prices_
                if product == 'part_d':
                    view = part_d_profile.profile(g, r)
                    if view.get('status') != 'ready':
                        return []
                    scope = {key: view['inputs'][key] for key in ('zipcode', 'county_fips', 'year')}
                    return part_d_pilot.published_plans(part_d_repository, scope, flow.reference['zips']).get('plans', [])
                view = medigap_profile.for_flow(flow, g, r)
                if view.get('status') != 'ready':
                    return []
                return prices_(medigap_repository, {**view['inputs'], 'effective_date': date_}).get('plans', [])
            flow.plans_selection_read = selection_read
    if medigap_repository is not None:
        from medigap_pilot import DATE, prices
        flow.closing_price_read = lambda inputs: turn_progress.run(
            'plans', prices, medigap_repository, {**inputs, 'effective_date': DATE})
    return flow


def attach_checks(flow, *, doctor_service, prescription_service, part_d_repository, research_catalog=None):
    """The doctor and medicine checks, as ``demo_server.build_demo`` attaches them for :8895."""
    from comparison_research import RESEARCH_SCOPE
    from conversation_checks import ConversationChecks
    from part_d_pilot import published_plans
    catalog = research_catalog or CatalogResearch()

    def plans():
        advantage = catalog.query(RESEARCH_SCOPE)
        try:
            drug = published_plans(part_d_repository, {'zipcode': '34102', 'county_fips': '12021', 'year': 2026},
                                   flow.reference['zips'])
        except (OSError, RuntimeError, ValueError, AttributeError, TypeError):
            drug = {'plans': []}
        return ([{'id': plan['offering_id'], 'name': plan['name']} for plan in advantage['plans']]
                + [{'id': plan['id'], 'name': plan['name']} for plan in drug['plans']])
    flow.conversation_checks = ConversationChecks(flow, doctor_service, prescription_service, plans)
    return flow


def build_one_call(port=PORT, *, fixture=False, client=None, database=None, binding_path=DEFAULT_BINDING, dsn=None,
                   medigap_repository=None, part_d_repository=None, research_catalog=None, count_tokens=None,
                   conversation_checks=False, doctor_service=None, prescription_service=None,
                   reconcile=None, one_call=True):
    """Build the server. ``one_call=False`` builds the same wiring around advisor-first's
    own two-call conversation, for the bake-off's like-for-like comparison."""
    if port in REFUSED_PORTS:
        raise ValueError('That port belongs to another Daylight surface. The one-call variant uses %d.' % PORT)
    if client is not None and not fixture:
        raise ValueError('An injected client is for the offline fixture mode only.')
    if conversation_checks and (doctor_service is None and prescription_service is None):
        raise ValueError('Conversation checks need a doctor or a prescription service.')
    binding = {'database': 'offline-fixture', 'snapshot_id': 'none'}
    scratch = None
    if fixture:
        if database is None:
            scratch = TemporaryDirectory(prefix='daylight-one-call-fixture-')
            database = Path(scratch.name) / 'guest.sqlite3'
    else:
        if medigap_repository is None or part_d_repository is None:
            # The same bound display stores :8895 reads. Needs the local database.
            sys.path.insert(0, str(PACKAGE / 'src'))
            from daylight_data.pilot_subset.store import repositories
            binding = json.loads(Path(binding_path).read_text())
            dsn = dsn or os.environ.get('DAYLIGHT_PILOT_DATABASE_URL') or (
                f'host={PACKAGE / ".state/socket"} port=55485 '
                f'dbname={binding["database"]} user={getpass.getuser()}')
            medigap_repository, part_d_repository = repositories(binding_path, dsn=dsn)
        database = database or LIVE_DATABASE
    catalog = research_catalog or CatalogResearch(critical_benefits_path=CRITICAL_BENEFITS_PATH)
    try:
        service = build(port, fixture=fixture, database=database, local_demo=True, client=client,
                        count_tokens=count_tokens, research_catalog=catalog,
                        medigap_repository=medigap_repository, part_d_repository=part_d_repository)
    except Exception:
        if scratch:
            scratch.cleanup()
        raise
    try:
        flow = OneCallConversation.adopt(service.adaptive) if one_call else service.adaptive
        configure(flow, medigap_repository=medigap_repository, part_d_repository=part_d_repository)
        if fixture and client is not None:
            # The real turn against the injected scripted client: no key, no budget ledger, no network.
            flow.fixture = False
            flow.agent.enabled = True
            flow.model_agents = {client.model: flow.agent}
        elif one_call and not fixture:
            # Function tools are sent in the OpenAI Responses shape only.
            flow.model_agents = {identifier: agent for identifier, agent in flow.model_agents.items()
                                 if identifier in MODELS and MODELS[identifier].provider == 'OpenAI'}
        if conversation_checks:
            attach_checks(flow, doctor_service=doctor_service, prescription_service=prescription_service,
                          part_d_repository=part_d_repository)
        if one_call:
            if medigap_repository is not None and part_d_repository is not None:
                import recommendation_http

                def recommendation(inputs, *, checks=(), expected_doctors=(), reported=()):
                    return recommendation_http.evaluate(service, inputs, medigap_repository, part_d_repository,
                                                        checks=checks, expected_doctors=expected_doctors, reported=reported)
                flow.one_call_recommendation = recommendation
            if reconcile is not None:
                flow.reconciler.enabled = bool(reconcile)
            if not fixture and trace_switch_on():
                # One content-free line per typed turn, for the cost of a visit (python3 -m sim.cost).
                # advisor-first's server confines only the guest store to its own folder, so the
                # trace stays inside this variant's.
                flow.one_call_trace = str(TRACE_FILE)
        log_guard.install(names=LOGGERS)
        base = service.RequestHandlerClass

        class Handler(base):
            # Installed beneath demo_http's handler, so this sees the status it assembled.
            def respond(self, code, value, mime='application/json; charset=utf-8', cookie=None):
                if one_call and self.path == '/api/conversation/checks' and code == 200 and isinstance(value, dict):
                    # The interface replaces what the chat shows with this answer every few seconds,
                    # so it gets the same short form the turn showed. The full results stay in the
                    # controller for the Plans page and the engine.
                    value = flow.shown_checks(value)
                if one_call and self.path == '/api/status' and code == 200 and isinstance(value, dict):
                    local = dict(value.get('local_demo') or {})
                    # This loop publishes no reply blocks before the turn ends.
                    local.update(surface=SURFACE, block_release=False,
                                 plan_card_checks=callable(getattr(flow, 'plan_card_projection', None)))
                    value = {**value, 'local_demo': local, 'one_call': {
                        'loop': 'one-call', 'request_bytes': ONE_CALL_REQUEST_BYTES,
                        'discovery': 'permission_before_profile',
                        'reconcile': bool(flow.reconciler.enabled),
                        'reasoning_effort': ONE_CALL_REASONING_EFFORT,
                        'turn_trace': bool(getattr(flow, 'one_call_trace', None)),
                        'recommendation_engine': callable(getattr(flow, 'one_call_recommendation', None)),
                        'live_runs': 'owner_only'}}
                return super().respond(code, value, mime, cookie)
        service.RequestHandlerClass = Handler
        service = install(service, binding=binding, fixture=fixture, conversation_checks=bool(conversation_checks))
        service.one_call_scratch = scratch       # keeps the fixture's temporary store alive with the server
    except Exception:
        service.server_close()
        if scratch:
            scratch.cleanup()
        raise
    return service


def close(service):
    """Close a built server and remove the fixture's temporary guest store, if it has one."""
    service.server_close()
    scratch = getattr(service, 'one_call_scratch', None)
    if scratch:
        scratch.cleanup()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--port', type=int, default=PORT)
    parser.add_argument('--fixture', action='store_true',
                        help='Offline: no database, no model, no network. Typed messages get the reviewed fallback.')
    parser.add_argument('--binding', type=Path, default=DEFAULT_BINDING)
    parser.add_argument('--doctor-foundation', type=Path, help='Local doctor research binding, for --conversation-checks.')
    parser.add_argument('--conversation-checks', action='store_true',
                        help='Use the current chat reports for local doctor and prescription checks.')
    args = parser.parse_args(argv)
    if args.fixture and (args.conversation_checks or args.doctor_foundation):
        parser.error('--fixture starts without any data service.')
    if args.doctor_foundation and not args.conversation_checks:
        parser.error('--doctor-foundation is used by --conversation-checks.')
    if args.doctor_foundation and not all(os.environ.get(key) for key in (
            'DAYLIGHT_FOUNDATION_PACKAGE_DSN', 'DAYLIGHT_FOUNDATION_SOURCE_DSN')):
        parser.error('Set both local foundation DSNs to enable doctor checks.')
    doctor_service = prescription_service = None
    if args.conversation_checks:
        sys.path.insert(0, str(PACKAGE / 'src'))
        from daylight_data.serving.part_d_local import local_candidate
        prescription_service = local_candidate(REPO)
        if args.doctor_foundation:
            from daylight_data.serving.binding import ResearchServingError
            from daylight_data.serving.pilot_doctors import PilotDoctors
            from daylight_data.serving.pilot_foundation import PilotFoundation
            try:
                doctor_service = PilotDoctors(PilotFoundation(
                    args.doctor_foundation, root=REPO, package_dsn=os.environ['DAYLIGHT_FOUNDATION_PACKAGE_DSN'],
                    source_dsn=os.environ['DAYLIGHT_FOUNDATION_SOURCE_DSN']))
            except (OSError, ResearchServingError) as error:
                print(f'Doctor research is unavailable ({type(error).__name__}).', flush=True)
    service = build_one_call(args.port, fixture=args.fixture, binding_path=args.binding,
                             conversation_checks=args.conversation_checks, doctor_service=doctor_service,
                             prescription_service=prescription_service)
    print(f'Daylight one-call variant: http://127.0.0.1:{service.server_port}/', flush=True)
    print('Experimental. Same interface and data wiring as :8895; one model call per typed message.', flush=True)
    if not args.conversation_checks:
        print('Started without --conversation-checks: no doctor or medicine picker will appear. '
              'Use "Start Daylight One-Call 8897.command" for the full wiring.', flush=True)
    try:
        service.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        close(service)


if __name__ == '__main__':
    main()
