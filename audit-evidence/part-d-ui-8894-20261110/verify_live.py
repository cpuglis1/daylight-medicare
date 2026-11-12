"""Read-only source verification using a fresh guest session; no saved profiles or turns."""
from pathlib import Path
import hashlib
import http.client
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'alternatives/advisor-first'))
sys.path.insert(0, str(ROOT / 'alternatives/chat-first/cms-slice/scripts'))
from part_d_pilot import BUILD, local_repository

connection = http.client.HTTPConnection('127.0.0.1', 8894, timeout=30)
connection.request('GET', '/api/guest/session')
response = connection.getresponse()
assert response.status == 200
cookie = response.getheader('Set-Cookie').split(';')[0]
session = json.load(response)
scope = {'zipcode': '34101', 'county_fips': '12021', 'year': 2026}
connection.request('POST', '/api/plans/part-d', json.dumps(scope), {
    'Content-Type': 'application/json', 'Cookie': cookie,
    'X-Daylight-CSRF': session['csrf'], 'Origin': 'http://127.0.0.1:8894'})
response = connection.getresponse()
result = json.load(response)
assert response.status == 200, (response.status, result)
assert result['display_authorization'] == 'D134'
assert result['status'] == 'published_plans' and len(result['plans']) == 10
source = local_repository().query({'reference_year': 2026, 'county_fips': '12021',
    'intended_use': 'developer_source_inspection', 'kind': 'pdp_offering', 'page_size': 100})
source_by_id = {row['cms_offering_id']: row['payload'] for row in source['records']}
assert set(source_by_id) == {plan['id'] for plan in result['plans']}
for plan in result['plans']:
    assert plan['fields'] == source_by_id[plan['id']]['fields']
    assert plan['source'] == source_by_id[plan['id']]['source']
assets = {}
for name in ['index.html', 'advisor.js', 'plans-workspace.js', 'part-d-plans.js', 'part-d-plans.css']:
    connection.request('GET', '/' + name)
    response = connection.getresponse()
    content = response.read()
    assert response.status == 200, (name, response.status)
    assert content == (ROOT / 'alternatives/advisor-first/web-8894' / name).read_bytes(), name
    assets[name] = hashlib.sha256(content).hexdigest()
connection.close()
receipt = {'http_status': 200, 'display_authorization': 'D134', 'build_id': BUILD,
    'plans': len(result['plans']), 'source_fields_equal': sum(len(p['fields']) for p in result['plans']),
    'all_ids_and_locators_equal': True, 'personal_costs_available': result['personal_costs_available'],
    'served_static_hashes': assets, 'conversation_turns': 0}
(OUT / 'live-http-verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
