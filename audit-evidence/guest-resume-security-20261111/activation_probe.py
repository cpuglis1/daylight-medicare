"""Health and free recovery only; no conversation turns or model requests."""
import http.client
import json


def request(port, path, body=None, headers=None):
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
    conn.request('POST' if body is not None else 'GET', path,
                 json.dumps(body) if body is not None else None, headers or {})
    response = conn.getresponse()
    result = response.status, response.getheader('Set-Cookie'), response.read()
    conn.close()
    return result


results = {}
for port in (8893, 8894):
    status, _, _ = request(port, '/api/status')
    assert status == 200
    results[str(port)] = status
status, cookie, raw = request(8894, '/api/guest/session')
assert status == 200
headers = {'Origin': 'http://127.0.0.1:8894', 'Content-Type': 'application/json',
           'Cookie': cookie.split(';')[0], 'X-Daylight-CSRF': json.loads(raw)['csrf']}
status, _, raw = request(8894, '/api/conversation/resume',
                         {'requestId': 'fictional-activation-reference'}, headers)
assert status == 200 and json.loads(raw) == {'status': 'expired'}
results['fresh_unowned_resume'] = {'http': status, 'status': 'expired'}
headers['Origin'] = 'https://example.invalid'
status, _, _ = request(8894, '/api/conversation/resume', {}, headers)
assert status == 403
results['foreign_origin'] = status
status, _, raw = request(8894, '/visit-resume.js')
assert status == 200 and b'DaylightVisitResume' in raw
results['refresh_script'] = status
results['conversation_turn_requests'] = 0
results['model_requests'] = 0
print(json.dumps(results, indent=2))
