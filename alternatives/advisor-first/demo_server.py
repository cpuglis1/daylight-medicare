#!/usr/bin/env python3
"""D145 unified local Daylight demo: one loopback port, real demo data."""
import argparse
import getpass
import json
import os
from pathlib import Path
import sys

from server import REPO, build
from catalog_research import CatalogResearch, CRITICAL_BENEFITS_PATH
from demo_http import install

PACKAGE = REPO / 'infrastructure/daylight-data'
DEFAULT_BINDING = PACKAGE / '.state/pilot-subset/2026-11-12-r1/binding.json'


def build_demo(port=8895, *, fixture=False, database=None, binding_path=DEFAULT_BINDING, dsn=None):
    if port in {8890,8891,8893,8894,8896}:
        raise ValueError('Use a separate port for the unified demo.')
    sys.path.insert(0, str(PACKAGE / 'src'))
    from daylight_data.pilot_subset.store import repositories
    binding = json.loads(Path(binding_path).read_text())
    dsn = dsn or os.environ.get('DAYLIGHT_PILOT_DATABASE_URL') or (
        f'host={PACKAGE / ".state/socket"} port=55485 '
        f'dbname={binding["database"]} user={getpass.getuser()}')
    medigap, pdp = repositories(binding_path, dsn=dsn)
    service = build(port, fixture=fixture, database=database, local_demo=True,
        research_catalog=CatalogResearch(critical_benefits_path=CRITICAL_BENEFITS_PATH),
        medigap_repository=medigap, part_d_repository=pdp)
    return install(service, binding=binding, fixture=fixture)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8895)
    parser.add_argument('--fixture',action='store_true',help='Offline fictional conversation; no model calls.')
    parser.add_argument('--binding',type=Path,default=DEFAULT_BINDING)
    args=parser.parse_args()
    service=build_demo(args.port,fixture=args.fixture,binding_path=args.binding)
    print(f'Daylight unified local demo: http://localhost:{service.server_port}/',flush=True)
    print('Current UI + API, demo database, isolated guest store; no :8893/:8894 proxy.',flush=True)
    try:
        service.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        service.server_close()


if __name__ == '__main__':
    main()
