"""Actual public research + fictional guest journey; no paid AI or real stores.

Run with infrastructure/daylight-data/.venv/bin/python. This operator starts only
its own ephemeral loopback HTTP fixture, reads the exact existing PostgreSQL
selection, writes a new receipt, then closes its own fixture. It never starts,
stops, restarts, migrates or writes PostgreSQL.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import uuid

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from server import build
from comparison_research import RESEARCH_SCOPE, local_repository
from published_reference import PublishedReferenceAdapter


def main(output):
    if output.exists():
        raise ValueError('Preserve the previous journey receipt; choose a new output.')
    checks, requests = [], []
    def check(name, passed, **details):
        checks.append({'name': name, 'passed': bool(passed), **details})
        if not passed:
            raise AssertionError(name)
    repository = local_repository()
    with tempfile.TemporaryDirectory(prefix='daylight-comparison-journey-') as temporary:
        service = build(0, fixture=True, database=Path(temporary)/'synthetic.sqlite3',
                        research_repository=repository, reference_adapter=PublishedReferenceAdapter())
        thread = threading.Thread(target=service.serve_forever, daemon=True)
        thread.start()
        cookie, session, state = None, {}, None
        def request(path, payload=None):
            nonlocal cookie
            connection = http.client.HTTPConnection('127.0.0.1', service.server_port, timeout=20)
            headers = {'Origin': f'http://127.0.0.1:{service.server_port}'}
            if cookie:
                headers['Cookie'] = cookie
            if payload is not None:
                headers.update({'Content-Type':'application/json','X-Daylight-CSRF':session['csrf']})
            started = time.perf_counter()
            connection.request('POST' if payload is not None else 'GET', path,
                               json.dumps(payload) if payload is not None else None, headers)
            response = connection.getresponse()
            if response.getheader('Set-Cookie'):
                cookie = response.getheader('Set-Cookie').split(';')[0]
            value = json.loads(response.read())
            requests.append({'path':path,'operation':payload.get('operation') if payload else None,
                             'status':response.status,'elapsed_ms':round((time.perf_counter()-started)*1000,3)})
            status = response.status
            connection.close()
            return status, value
        def turn(action):
            nonlocal state
            payload = {'guide':state['guide'],'record':state['record'],
                'requestId':str(uuid.uuid4()),'action':action,
                **({'continuation':state['continuation']} if state.get('continuation') else {})}
            status, out = request('/api/conversation/turn',payload)
            check('conversation_action_' + action['type'] + '_' + str(action.get('id','')), status==200,
                  http_status=status)
            state = out
            return out
        try:
            status, session = request('/api/guest/session')
            check('isolated_guest_session',status==200)
            status, state = request('/api/conversation/initial')
            check('initial_profile',status==200)
            turn({'type':'task','task':'compare','preparing':True})
            # Explicit fictional reports exercise capture without model transport.
            for identifier, fields in [
                ('RC01',{'choice':'self'}),('T04',{'choice':'month','month':'November 2026'}),
                ('T05',{'choice':'original'}),('T03',{'zip':'34102'}),
                ('T06',{'text':'Fictional Example Clinic, Naples'}),
                ('T07',{'choice':'no'}),('T08',{'choice':'local'}),
                ('T09',{'choice':'no_preference'}),('T10',{'choice':'doctors'}),
            ]:
                turn({'type':'choice','id':identifier,'fields':fields})
            check('all41_accounted',len(state['comparison']['decision_record']['question_accounting'])==41)
            check('all14_gaps_preserved',len(state['comparison']['decision_record']['gap_accounting'])==14)
            old_comparison = state['comparison']['comparison_id']
            # Correct a care item through the same owner-bound HTTP controller.
            turn({'type':'edit','id':'T06'})
            turn({'type':'choice','id':'T06','fields':{'text':'Fictional Replacement Clinic, Naples'}})
            check('correction_rebinds_comparison',state['comparison']['comparison_id']!=old_comparison)
            check('correction_preserves_other_reports',state['guide']['fields']['coverage.current']['value']==['original'])
            status, catalog = request('/api/research/query',{'operation':'list','scope':RESEARCH_SCOPE,'limit':100})
            check('actual72_catalog',status==200 and catalog['total']==72 and len(catalog['plans'])==72)
            check('exact_unique_source_order',len({p['offering_id'] for p in catalog['plans']})==72 and
                  [p['source_ordinal'] for p in catalog['plans']]==list(range(1,73)))
            status, accepted = request('/api/research/query',{'operation':'reference',
                'offering_id':'2026:H1035:019:000','year':2026})
            check('actual_original_reference_replayed',status==200 and
                accepted['reference']['accepted_for_reference'] is True and
                len(accepted['reference']['entries'])==12 and
                accepted['binding']['replay']=='original_lookup_research_false_every_request')
            check('reference_conditions_and_holds_preserved',
                all(entry['qualifications'] and entry['carrier_evidence']
                    for entry in accepted['reference']['entries']) and
                all(hold['value'] is None and hold['state']=='unknown_held'
                    for hold in accepted['reference']['holds']) and
                all(value['state']=='held' for purpose,value in accepted['authority'].items()
                    if purpose!='reference_lookup'))
            band_id='2026:H1035:019:000:r4:INN_hospital_band1_amount'
            status, band = request('/api/research/query',{'operation':'reference',
                'offering_id':'2026:H1035:019:000','year':2026,'entry_ids':[band_id]})
            check('scalar_reference_keeps_related_schedule',status==200 and
                {entry['field'] for entry in band['reference']['related_reference_entries']} >=
                {'INN_hospital_band1_begin_day','INN_hospital_band1_end_day'})
            status, restricted = request('/api/research/query',{'operation':'reference',
                'offering_id':'2026:H0710:010:000','year':2026})
            check('historical_restricted_subset_kept_visible',status==200 and
                restricted['reference']['entries']==[] and
                restricted['reference']['offering']['carrier_document_state']=='restricted')
            status, _ = request('/api/research/query',{'operation':'reference',
                'offering_id':'2026:H1035:019:000','year':2027})
            check('reference_wrong_year_rejected',status==422)
            snapshot = catalog['binding']['snapshot_id']
            details = []
            for identity in ['2026:H5652:001:000','2026:H5652:002:000']:
                status, detail = request('/api/research/query',{'operation':'inspect','offering_id':identity,
                    'layers':['L02','L03','L09'],'limit':5,'expected_snapshot_id':snapshot})
                check('actual_detail_' + identity,status==200 and detail['binding']['snapshot_id']==snapshot)
                check('condition_and_lineage_retained_' + identity,all('conditions' in row and row['lineage'].get('raw_sha256')
                    and 'raw_source_payload' in row for layer in ('L03','L09') for row in detail['evidence_by_layer'][layer]['records']))
                details.append(detail)
            first = details[0]['evidence_by_layer']['L03']
            status, next_page = request('/api/research/query',{'operation':'inspect','offering_id':details[0]['plan']['offering_id'],
                'layers':['L03'],'limit':5,'expected_snapshot_id':snapshot,
                'after_entity_id_by_layer':{'L03':first['next_after_entity_id']}})
            check('actual_detail_pagination_no_overlap',status==200 and not
                {r['entity_id'] for r in first['records']} &
                {r['entity_id'] for r in next_page['evidence_by_layer']['L03']['records']})
            payload = {'guide':state['guide'],'record':state['record'],'requestId':str(uuid.uuid4()),
                       'continuation':state['continuation'],'scope':copy.deepcopy(RESEARCH_SCOPE)}
            status, out = request('/api/comparison/review',payload)
            check('profile_to_actual_research_connection',status==200 and
                out['comparison']['research']['retained_identity_count']==72)
            state['comparison'] = out['comparison']
            check('no_research_consumer_promotion',len(out['comparison']['units'])==1 and
                out['comparison']['universe']['evaluated_count']==0 and
                all(a['state']=='held' for a in out['comparison']['authority'].values()) and
                all(f['value'] is None and f['output_state']=='held' for f in out['comparison']['findings']))
            status, _ = request('/api/research/query',{'operation':'list','scope':{**RESEARCH_SCOPE,'year':2027}})
            check('wrong_year_does_not_substitute',status==422)
            status, _ = request('/api/research/query',{'operation':'list','scope':RESEARCH_SCOPE,
                                                     'expected_snapshot_id':'fixture:obsolete'})
            check('stale_source_snapshot_rejected',status==422)
            status, _ = request('/api/recommendations',{'guide':state['guide'],'record':state['record']})
            check('actual_recommendations_still_held',status in {409,503})
            state['guide']['preferences'].update(saveGuide=True,saveSensitive=False)
            status, _ = request('/api/conversation/save',{'guide':state['guide'],'record':state['record'],
                'expectedVersion':0,'expectedReadinessVersion':0,'operationId':str(uuid.uuid4())})
            check('fictional_minimal_save',status==200)
            _, saved = request('/api/guest/profile')
            _, readiness = request('/api/guest/readiness')
            serialized = json.dumps([saved,readiness])
            check('no_derived_trace_or_sensitive_care_item_saved',all(value not in serialized for value in
                ['comparison:', 'case_preparation', 'decision_record', 'Fictional Example Clinic','Fictional Replacement Clinic']))
            check('no_paid_ai',service.budget is None and service.agent.enabled is False)
            receipt = {'version':'local-comparison-journey-r3','observed_at':datetime.now(timezone.utc).isoformat(),
                'passed':all(c['passed'] for c in checks),'checks':checks,'http_requests':requests,
                'research_binding':catalog['binding'],'scope':RESEARCH_SCOPE,
                'fictional_guest_storage':True,'real_guest_records_accessed':False,'paid_ai_calls':0,
                'postgres_writes':0,'new_acceptance':False,'consumer_release':False,
                'exact_reference_binding':accepted['binding'],
                'source_revision_sha256':{str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in [HERE/'server.py',HERE/'research_http.py',HERE/'comparison_research.py',
                              HERE/'comparison_service.py',HERE/'comparison_case.py',
                              HERE/'comparison_engine.py',HERE/'comparison_methods.py',
                              HERE/'published_reference.py',HERE/'web/reference-view.js',
                              HERE/'web/research.js',HERE/'web/advisor.js']}}
            output.parent.mkdir(parents=True,exist_ok=True)
            output.write_text(json.dumps(receipt,indent=2)+'\n')
            print(json.dumps({'passed':receipt['passed'],'checks':len(checks),'receipt':str(output)}))
        finally:
            service.shutdown();service.server_close();thread.join();repository.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output.resolve())
