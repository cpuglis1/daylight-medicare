#!/usr/bin/env python3
"""D145 unified local Daylight demo: one loopback port, real demo data."""
import argparse
from contextlib import ExitStack
import getpass
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Thread

from server import REPO, build
from catalog_research import CatalogResearch, CRITICAL_BENEFITS_PATH
from demo_http import install

PACKAGE = REPO / 'infrastructure/daylight-data'
DEFAULT_BINDING = PACKAGE / '.state/pilot-subset/2026-11-12-r1/binding.json'


def build_demo(port=8895, *, fixture=False, database=None, binding_path=DEFAULT_BINDING, dsn=None,
               doctor_service=None, doctor_chat=False, rehearsal_port=None,
               conversation_checks=False, prescription_service=None):
    if port in {8890,8891,8893,8894,8896}:
        raise ValueError('Use a separate port for the unified demo.')
    if rehearsal_port is not None and not (fixture or port == 8895):
        raise ValueError('The prescription rehearsal is for the local 8895 demo.')
    sys.path.insert(0, str(PACKAGE / 'src'))
    doctor_routes = None
    if doctor_service is not None:
        if fixture and (database is None or Path(database).exists()):
            raise ValueError('Doctor fixtures require a fresh isolated guest database.')
        if not fixture and (port != 8895 or not (doctor_chat or conversation_checks)):
            raise ValueError('Doctor chat is available on the local 8895 demo only.')
        from doctor_fixture_http import DoctorFixtureRoutes
        doctor_routes = DoctorFixtureRoutes(doctor_service)
    from daylight_data.pilot_subset.store import repositories
    binding = json.loads(Path(binding_path).read_text())
    dsn = dsn or os.environ.get('DAYLIGHT_PILOT_DATABASE_URL') or (
        f'host={PACKAGE / ".state/socket"} port=55485 '
        f'dbname={binding["database"]} user={getpass.getuser()}')
    medigap, pdp = repositories(binding_path, dsn=dsn)
    service = build(port, fixture=fixture, database=database, local_demo=True,
        research_catalog=CatalogResearch(critical_benefits_path=CRITICAL_BENEFITS_PATH),
        medigap_repository=medigap, part_d_repository=pdp)
    # D161: Parts A and B as the foundation. The unified local demo only, until
    # the owner releases it to the participant interface.
    import enrollment_flow
    enrollment_flow.enable(service.adaptive)
    import conversation_planner
    if port == 8895 or fixture:
        conversation_planner.enable(service.adaptive)
    from medigap_pilot import DATE, prices
    service.adaptive.closing_price_read = lambda inputs: prices(medigap, {**inputs, 'effective_date': DATE})
    if not fixture and port == 8895:
        # A per-turn trace for the local demo: codes, times and counts only (no words).
        service.adaptive.turn_trace = str(Path(__file__).resolve().parent / 'var' / 'demo-8895' / 'turn-trace.jsonl')
    if conversation_checks:
        if not fixture and port != 8895:
            service.server_close()
            raise ValueError('Conversation checks are for the local 8895 evaluation only.')
        from conversation_checks import ConversationChecks
        from part_d_pilot import published_plans
        from comparison_research import RESEARCH_SCOPE
        catalog = CatalogResearch()
        def plans():
            ma = catalog.query(RESEARCH_SCOPE)
            try:
                drug = published_plans(pdp, {'zipcode':'34102','county_fips':'12021','year':2026}, service.adaptive.reference['zips'])
            except (OSError, RuntimeError, ValueError):
                drug = {'plans': []}
            return ([{'id':p['offering_id'],'name':p['name']} for p in ma['plans']]
                    + [{'id':p['id'],'name':p['name']} for p in drug['plans']])
        service.adaptive.conversation_checks = ConversationChecks(service.adaptive, doctor_service, prescription_service, plans)
    return install(service, binding=binding, fixture=fixture, doctor_routes=doctor_routes,
                   doctor_chat=doctor_chat and not conversation_checks, rehearsal_port=rehearsal_port,
                   conversation_checks=conversation_checks)


def start_prescription_rehearsal(stack, *, binding_path, doctor_service=None, candidate=None):
    if candidate is None:
        sys.path.insert(0, str(PACKAGE / 'src'))
        from daylight_data.serving.part_d_local import local_candidate
        candidate = local_candidate(REPO)
    from part_d_visit_http import install_profile_preview

    scratch = stack.enter_context(TemporaryDirectory(prefix='daylight-d146-8895-'))
    fixture = stack.enter_context(build_demo(0, fixture=True, database=Path(scratch) / 'guest.sqlite3',
        binding_path=binding_path, doctor_service=doctor_service, doctor_chat=doctor_service is not None))
    install_profile_preview(fixture, candidate)
    Thread(target=fixture.serve_forever, daemon=True).start()
    stack.callback(fixture.shutdown)
    return fixture.server_port


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8895)
    parser.add_argument('--fixture',action='store_true',help='Offline fictional conversation; no model calls.')
    parser.add_argument('--binding',type=Path,default=DEFAULT_BINDING)
    parser.add_argument('--doctor-foundation', type=Path, help='Enable offline fictional doctor checks.')
    parser.add_argument('--doctor-chat', action='store_true', help='Put local research doctor checks in chat.')
    parser.add_argument('--prescription-rehearsal', action='store_true',
                        help='Offer a model-free fictional prescription check from local chat.')
    parser.add_argument('--conversation-checks', action='store_true',
                        help='Use the current chat reports for local doctor and prescription checks.')
    args=parser.parse_args()
    if args.doctor_chat and (not args.doctor_foundation or not args.fixture and args.port != 8895):
        parser.error('--doctor-chat requires a foundation binding on the loopback demo.')
    if args.doctor_foundation and not (args.fixture or args.doctor_chat or args.conversation_checks):
        parser.error('--doctor-foundation requires --fixture or --doctor-chat')
    if args.doctor_foundation and not all(os.environ.get(key) for key in (
            'DAYLIGHT_FOUNDATION_PACKAGE_DSN', 'DAYLIGHT_FOUNDATION_SOURCE_DSN')):
        parser.error('Set both local foundation DSNs to enable doctor checks.')
    if args.prescription_rehearsal and args.port != 8895 and not args.fixture:
        parser.error('--prescription-rehearsal is available on the local 8895 demo only.')
    with ExitStack() as stack:
        scratch = stack.enter_context(TemporaryDirectory(prefix='daylight-demo-fixture-'))
        doctor_service = None
        if args.doctor_foundation:
            sys.path.insert(0, str(PACKAGE / 'src'))
            from daylight_data.serving.pilot_foundation import PilotFoundation
            from daylight_data.serving.binding import ResearchServingError
            from daylight_data.serving.pilot_doctors import PilotDoctors
            try:
                doctor_service = PilotDoctors(PilotFoundation(args.doctor_foundation, root=REPO,
                    package_dsn=os.environ['DAYLIGHT_FOUNDATION_PACKAGE_DSN'],
                    source_dsn=os.environ['DAYLIGHT_FOUNDATION_SOURCE_DSN']))
            except (OSError, ResearchServingError) as error:
                if not (args.doctor_chat or args.conversation_checks) or args.fixture:
                    raise
                print(f'Doctor research is unavailable ({type(error).__name__}).', flush=True)
        rehearsal_port = None
        if args.prescription_rehearsal and not args.conversation_checks:
            with ExitStack() as rehearsal:
                try:
                    rehearsal_port = start_prescription_rehearsal(rehearsal, binding_path=args.binding,
                        doctor_service=doctor_service)
                except (OSError, ValueError) as error:
                    print(f'Prescription rehearsal is unavailable ({type(error).__name__}).', flush=True)
                else:
                    stack.enter_context(rehearsal.pop_all())
        prescription_service = None
        if args.conversation_checks:
            sys.path.insert(0,str(REPO/'infrastructure/daylight-data/src'))
            from daylight_data.serving.part_d_local import local_candidate
            prescription_service = local_candidate(REPO)
        service=stack.enter_context(build_demo(args.port, fixture=args.fixture, binding_path=args.binding,
            database=Path(scratch)/'fictional.sqlite3' if args.fixture and doctor_service else None,
            doctor_service=doctor_service, doctor_chat=args.doctor_chat, rehearsal_port=rehearsal_port,
            conversation_checks=args.conversation_checks, prescription_service=prescription_service))
        print(f'Daylight unified local demo: http://localhost:{service.server_port}/',flush=True)
        print('Current UI + API, demo database, isolated guest store; no :8893/:8894 proxy.',flush=True)
        try:
            service.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
