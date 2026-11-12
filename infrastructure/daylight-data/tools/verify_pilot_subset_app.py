#!/usr/bin/env python3
"""Offline HTTP verification using fictional inputs and an isolated guest store.

Reads the actual demo DB and refuses model transport. No active app restart.
"""
import argparse
from datetime import datetime, timezone
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
from unittest.mock import patch

import psycopg
from daylight_data.csg_medigap.store import connect
from daylight_data.pilot_subset.store import repositories
from daylight_data.plan_types.common import digest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'alternatives/advisor-first'))
from server import build
from catalog_research import CatalogResearch, CRITICAL_BENEFITS_PATH
from part_d_pilot import published_plans
from medigap_pilot import prices


def verify(binding_path, dsn):
    medigap, pdp = repositories(binding_path, dsn=dsn)
    binding = json.loads(binding_path.read_text())
    profile = {'zipcode': '34101', 'age': 65, 'gender': 'Female',
               'tobacco': 'Non-Tobacco', 'effective_date': '2026-11-10'}
    scope = {'zipcode': '34101', 'county_fips': '12021', 'year': 2026}
    zips = {'34101': [['12021', 'Collier County', 'FL']]}
    results = []
    def checked(name, condition):
        if not condition: raise AssertionError(name)
        results.append(name)
    with connect(dsn, binding['database'], readonly=True) as c:
        checked('only pilot and private CSG application schemas',
            {r['nspname'] for r in c.execute("SELECT nspname FROM pg_namespace WHERE nspname LIKE 'dl_%'")} == {'dl_pilot','dl_csg_medigap'})
        checked('database defaults to read-only', c.execute('SHOW default_transaction_read_only').fetchone()['default_transaction_read_only'] == 'on')
        for role, table in [('daylight_csg_reader','dl_csg_medigap.rate'),
                            ('daylight_plan_research_reader','dl_pilot.pdp_response')]:
            row = c.execute('SELECT has_table_privilege(%s,%s,\'SELECT\') AS read, '
                            'has_table_privilege(%s,%s,\'INSERT,UPDATE,DELETE,TRUNCATE\') AS write',
                            (role,table,role,table)).fetchone()
            checked(role + ' can read but cannot write', row['read'] and not row['write'])
        checked('no public schema access', all(not r['allowed'] for r in c.execute(
            "SELECT has_schema_privilege('public',nspname,'USAGE') AS allowed FROM pg_namespace WHERE nspname IN ('dl_pilot','dl_csg_medigap')")))
        try:
            c.execute("INSERT INTO dl_pilot.stop_event(scope,reason) VALUES('all','fictional rollback check')")
        except psycopg.errors.ReadOnlySqlTransaction:
            results.append('actual write rejected by read-only connection')
        else:
            raise AssertionError('read-only write unexpectedly succeeded')
    old_now = pdp.now
    pdp.now = lambda: datetime(2026,11,24,tzinfo=timezone.utc)
    try:
        published_plans(pdp, scope, zips)
    except RuntimeError as error:
        checked('expired PDP source refuses display', str(error) == 'PART_D_SOURCE_BINDING')
    else:
        raise AssertionError('expired source displayed')
    pdp.now = old_now
    for change, expected in [({'age':75},'unsupported_pilot_age'),
                             ({'zipcode':'34109'},'unsupported_pilot_zip'),
                             ({'effective_date':'2027-01-01'},'unsupported_price_date')]:
        checked(expected, prices(medigap, {**profile, **change})['status'] == expected)
    checked('2027 PDP remains unsupported', published_plans(pdp,{**scope,'year':2027},zips)['status']=='unsupported_year')
    with tempfile.TemporaryDirectory(prefix='daylight-subset-fictional-') as temporary, \
            patch('urllib.request.urlopen', side_effect=AssertionError('External transport forbidden')):
        service = build(0, fixture=True, database=Path(temporary)/'fictional.sqlite3',
            medigap_repository=medigap, part_d_repository=pdp,
            research_catalog=CatalogResearch(critical_benefits_path=CRITICAL_BENEFITS_PATH))
        thread = threading.Thread(target=service.serve_forever, daemon=True); thread.start()
        cookie = csrf = None
        def request(path, body=None, *, authenticated=True, csrf_header=True):
            connection = http.client.HTTPConnection('127.0.0.1', service.server_port, timeout=20)
            headers = {'Origin': f'http://127.0.0.1:{service.server_port}'}
            if authenticated and cookie: headers['Cookie'] = cookie
            if body is not None:
                headers['Content-Type'] = 'application/json'
                if csrf_header: headers['X-Daylight-CSRF'] = csrf
            connection.request('POST' if body is not None else 'GET', path,
                               json.dumps(body) if body is not None else None, headers)
            response = connection.getresponse()
            result = response.status, json.loads(response.read()), response.getheader('Set-Cookie')
            connection.close()
            return result
        try:
            code, session, header = request('/api/guest/session')
            checked('isolated fictional session', code == 200)
            cookie, csrf = header.split(';')[0], session['csrf']
            for path, body, count in [('/api/plans/medigap',profile,178),
                                     ('/api/plans/medigap',{**profile,'zipcode':'34108','age':74,'gender':'Male','tobacco':'Tobacco User'},166),
                                     ('/api/plans/part-d',scope,10),
                                     ('/api/plans/catalog',{},72)]:
                code, value, _ = request(path,body)
                checked(path + ' renders complete population over HTTP', code == 200 and len(value['plans']) == count)
                if path.endswith('/catalog'):
                    held_examples = sum(example['state'] == 'held' for plan in value['plans']
                                        for example in plan['examples'].values())
                    checked('all 229 MA holds retained (141 fields plus 88 examples)',
                            value['coverage']['material_held_fields'] == 141 and held_examples == 88)
                    for plan in value['plans']:
                        detail_code, detail, _ = request('/api/plans/detail',{'offeringId':plan['id']})
                        checked('MA detail ' + plan['id'], detail_code == 200)
                checked(path + ' rejects missing CSRF', request(path,body,csrf_header=False)[0] == 403)
                checked(path + ' rejects missing cookie', request(path,body,authenticated=False)[0] in {401,403})
            code, status, _ = request('/api/research/status')
            checked('full research DB is not configured', code == 200 and status['configured'] is False)
        finally:
            service.shutdown(); service.server_close(); thread.join()
    return {'schema':'collier-subset-app-checks/1','passed':len(results),'checks':results,
            'live_model_calls':0,'active_services_restarted':False,
            'snapshot_id':binding['snapshot_id']}


if __name__ == '__main__':
    import os
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binding',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    args=parser.parse_args()
    value=verify(args.binding,os.environ['DAYLIGHT_PILOT_DATABASE_URL'])
    with args.receipt.open('x') as f: json.dump(value,f,indent=2); f.write('\n')
    print(json.dumps({'passed':value['passed'],'live_model_calls':0}))
