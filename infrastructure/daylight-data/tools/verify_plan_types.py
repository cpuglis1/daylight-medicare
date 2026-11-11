"""Read-only full serving parity and API gate checks; no model/customer calls."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import secrets
import time

from daylight_data.plan_types.common import canonical,digest
from daylight_data.plan_types.prepare import stream_items,verify_bundle
from daylight_data.plan_types.store import COLUMNS,Repository,connect


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--bundle',required=True,type=Path)
    p.add_argument('--expected-database',required=True)
    p.add_argument('--output',required=True,type=Path)
    args=p.parse_args()
    if args.output.exists():raise RuntimeError('Preserve earlier verification output')
    manifest=verify_bundle(args.bundle)
    dsn=os.environ['DAYLIGHT_PLAN_TYPES_DATABASE_URL']
    result={'build_id':manifest['build_id'],'consumer_release':'held','source_checks':[]}
    started=time.monotonic()
    with connect(dsn,readonly=True) as c,c.transaction():
        c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        actual=c.execute('SELECT current_database() AS database').fetchone()['database']
        if actual!=args.expected_database:raise RuntimeError('Wrong explicit verification database')
        result['database']=actual
        for source in manifest['sources']:
            expected={}
            for item in stream_items(args.bundle,source):
                if item['item_id'] in expected:raise RuntimeError('Duplicate prepared identity')
                expected[item['item_id']]=digest({k:item.get(k) for k in COLUMNS})
            count=0
            with c.cursor(name='plan_type_parity') as cursor:
                cursor.execute('SELECT '+','.join(COLUMNS)+' FROM dl_plan_types.item WHERE build_id=%s AND source_id=%s',
                               (manifest['build_id'],source['source_id']))
                while rows:=cursor.fetchmany(1000):
                    for row in rows:
                        if expected.pop(row['item_id'],None)!=digest(row):
                            raise RuntimeError('Serving value/condition/source parity mismatch')
                        count+=1
            if expected or count!=source['item_count']:raise RuntimeError('Serving population mismatch')
            result['source_checks'].append({'source_path':source['path'],'items':count,'all_columns_match':True})
        result['legacy_controls']=c.execute('''SELECT
            (SELECT count(*) FROM dl_compact.source_set) AS compact_source_sets,
            (SELECT count(*) FROM dl_review.acceptance_binding) AS original_acceptance_bindings,
            (SELECT count(*) FROM dl_review.release) AS original_releases,
            (SELECT count(*) FROM dl_released.offerings) AS original_released_offerings,
            (SELECT count(*) FROM dl_plan_types.review_event WHERE build_id=%s) AS new_review_events,
            (SELECT pg_total_relation_size('dl_plan_types.item')) AS serving_item_bytes,
            current_setting('transaction_read_only') AS read_only''',(manifest['build_id'],)).fetchone()
        result['filed_rate_states']=c.execute('''SELECT count(*) AS total,
            count(*) FILTER(WHERE source_status='REPLACED') AS replaced,
            count(*) FILTER(WHERE amount_cents=0) AS zero,
            count(*) FILTER(WHERE effective_from IS NULL OR effective_through IS NULL) AS incomplete_period,
            count(county_fips) AS material_county_assertions
            FROM dl_plan_types.item WHERE build_id=%s AND kind='medigap_filed_rate' ''',(manifest['build_id'],)).fetchone()
    repo=Repository(lambda:connect(dsn,readonly=True),manifest['build_id'])
    result['status']=repo.status()
    from fastapi.testclient import TestClient
    from daylight_data.plan_types.api import create_app
    token,secret=secrets.token_urlsafe(48),secrets.token_urlsafe(48)
    with TestClient(create_app(repo,token,secret)) as client:
        request={'reference_year':2026,'county_fips':'12021','intended_use':'developer_source_inspection',
                 'kind':'pdp_offering','page_size':100}
        headers={'Authorization':'Bearer '+token}
        good=client.post('/internal/research/plan-types/query',json=request,headers=headers)
        consumer=client.post('/v1/plan-types/query',json=request,headers=headers)
        unauthorized=client.post('/internal/research/plan-types/query',json=request)
        personal=client.post('/internal/research/plan-types/query',json={**request,'profile':{}},headers=headers)
        if (good.status_code!=200 or len(good.json()['records'])!=manifest['counts']['pdp_offering']
                or consumer.status_code!=503 or unauthorized.status_code!=401 or personal.status_code!=422):
            raise RuntimeError('API research/consumer/permission contract failed')
        result['api']={'research_http':good.status_code,'pdp_records':len(good.json()['records']),
                       'consumer_http':consumer.status_code,'unauthorized_http':unauthorized.status_code,
                       'personal_input_http':personal.status_code}
    result.update(passed=True,verified_items=sum(s['items'] for s in result['source_checks']),
                  elapsed_seconds=time.monotonic()-started)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as f:f.write(canonical(result)+'\n')
    print(canonical({k:v for k,v in result.items() if k not in {'source_checks','status'}}))


if __name__=='__main__':main()
