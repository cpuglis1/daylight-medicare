"""All 320 retained fictional profiles through an isolated HTTP server and real DB.

Receipts contain counts/timing/hashes, never premium rows or participant data.
"""
from collections import defaultdict
import hashlib
import http.client
import json
from pathlib import Path
import statistics
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'alternatives/advisor-first'))
from server import build
from medigap_pilot import BUILD, local_repository

candidate = ROOT/'infrastructure/daylight-data/.state/csg-medigap/2026-11-10-db-r1/candidate-r1'
groups = defaultdict(dict)
for line in (candidate/'rates.jsonl').read_text().splitlines():
    row = json.loads(line)
    s = row['scenario']
    key = (s['zip'], s['age'], s['gender'], s['tobacco'], s['requested_effective_date'])
    groups[key][row['id']] = row
assert len(groups) == 320
calls, total = [], 0
with tempfile.TemporaryDirectory() as temp:
    service = build(0, fixture=True, database=Path(temp)/'fictional.sqlite3', medigap_repository=local_repository())
    thread = threading.Thread(target=service.serve_forever, daemon=True); thread.start()
    try:
        connection = http.client.HTTPConnection('127.0.0.1',service.server_port)
        connection.request('GET','/api/guest/session')
        response = connection.getresponse(); cookie = response.getheader('Set-Cookie').split(';')[0]
        csrf = json.loads(response.read())['csrf']; connection.close()
        for key, expected in sorted(groups.items()):
            body = dict(zip(('zipcode','age','gender','tobacco','effective_date'),key))
            headers = {'Content-Type':'application/json','Cookie':cookie,'X-Daylight-CSRF':csrf}
            connection = http.client.HTTPConnection('127.0.0.1',service.server_port)
            start = time.perf_counter()
            connection.request('POST','/api/plans/medigap',json.dumps(body),headers)
            response = connection.getresponse(); value = json.loads(response.read()); connection.close()
            calls.append((time.perf_counter()-start)*1000)
            assert response.status == 200 and value['status'] == 'matched_source_prices'
            assert value['source_build'] == BUILD and value['personal_quote'] is False
            assert value['source_review_holds'] == next(iter(expected.values()))['holds']
            assert {p['id'] for p in value['plans']} == set(expected)
            for p in value['plans']:
                original = expected[p['id']]
                for key in ('monthly_cents','annual_cents','monthly_with_discounts_cents','annual_with_discounts_cents',
                            'naic','variant','select_observed','source_effective_date','source_sha256','source_locator',
                            'policy_form','policy_edition','effective_end','policy_fee_timing','discount_eligibility'):
                    assert p[key] == original[key]
                assert p['source_fields'] == original['raw']
                assert p['company'] == original['company_name_raw']
                assert p['rating_class'] == original['rating_class_raw']
                assert p['rating_type'] == original['rating_type_raw']
            total += len(value['plans'])
    finally:
        service.shutdown();service.server_close();thread.join()
report = {'source_build':BUILD,'profiles':len(groups),'rates':total,'all_display_values_match':True,
          'mode':'isolated fictional HTTP server, actual PostgreSQL reads, no model calls',
          'milliseconds':{'median':statistics.median(calls),'p95':sorted(calls)[int(len(calls)*.95)-1],'max':max(calls)},
          'runtime_sha256':{name:hashlib.sha256((ROOT/'alternatives/advisor-first'/name).read_bytes()).hexdigest()
                            for name in ('server.py','medigap_pilot.py')},'passed':True}
Path(__file__).with_name('profile-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
