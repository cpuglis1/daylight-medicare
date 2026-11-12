"""Independent fictional HTTP/source probes; no runtime or real source access.

Includes the unchanged logical sequence of cross-chain reproduction r1, plus
deletion, current-head and source-context checks. Only statuses/counts and
hashes are retained. All guest/budget data belongs to disposable test fixtures.
"""
from datetime import datetime, timezone
from pathlib import Path
import copy
import hashlib
import json
import sys
import uuid

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / 'alternatives/advisor-first'
sys.path[:0] = [str(APP / 'tests'), str(APP)]
EXPECTED = {
    'identity_journey.py': '3a190575c66c496a5a79e3d9717ae4889b35f64e7727f7ec2c1854f735078a0b',
    'identity_http.py': '36e782195e7f51f2a0bafd873ca8e7f38187a837f7decaf7d8d45eb58eb26ba6',
}
for name, expected in EXPECTED.items():
    assert hashlib.sha256((APP / name).read_bytes()).hexdigest() == expected

from test_identity_http import IdentityHttpTests
from test_identity_journey import IdentityJourneyTests, OWNER
from identity_journey import IdentityJourneyError

checks = []


def check(name, condition):
    assert condition, name
    checks.append({'name': name, 'passed': True})


def fixture(operation):
    case = IdentityHttpTests()
    case.setUp()
    try:
        operation(case)
    finally:
        case.discovery.on_read = None
        case.doCleanups()


def cross_chain(case):
    old = case.state['continuation']
    status, offer = case.search()
    check('cross_chain_initial_offer_200', status == 200)
    identity = offer['identity']
    token = identity['choice_token']
    candidate = identity['candidates'][0]['candidate_id']
    status, current = case.request('/api/conversation/turn', {
        'guide': copy.deepcopy(case.state['guide']), 'record': copy.deepcopy(case.state['record']),
        'requestId': str(uuid.uuid4()), 'action': {'type': 'start'}})
    check('new_signed_chain_established', status == 200 and
          old.split('.')[0] != current['continuation'].split('.')[0])
    case.state = current
    check('old_offer_erased_immediately', token not in case.service._offers)
    status, rejected = case.request('/api/identity/confirm', case.payload(
        choiceToken=token, candidateId=candidate, confirmed=True))
    check('original_cross_chain_confirmation_now_rejects_422', status == 422)
    check('cross_chain_rejection_has_no_source_candidates', rejected['identity']['candidates'] == [])
    status, fresh = case.search()
    check('same_new_chain_fresh_offer_works', status == 200)
    fresh = fresh['identity']
    status, selected = case.request('/api/identity/confirm', case.payload(
        choiceToken=fresh['choice_token'], candidateId=fresh['candidates'][0]['candidate_id'], confirmed=True))
    check('fresh_same_chain_confirmation_works', status == 200 and
          selected['identity']['preparation']['selected_count'] == 1)


def deletion(case):
    status, offered = case.search()
    check('delete_initial_offer_200', status == 200)
    offered = offered['identity']
    token = offered['choice_token']
    status, _ = case.request('/api/identity/confirm', case.payload(
        choiceToken=token, candidateId=offered['candidates'][0]['candidate_id'], confirmed=True))
    check('delete_initial_selection_200', status == 200)
    owner = case.service._offers[token]['owner']
    status, pending = case.search()
    check('delete_pending_offer_200', status == 200)
    tokens = {token, pending['identity']['choice_token']}
    payload = {'expectedVersion': 999, 'confirmed': True}
    status, _ = case.request('/api/guest/profile', payload, method='DELETE', csrf=False)
    check('bad_csrf_delete_rejects_403', status == 403)
    check('bad_csrf_preserves_pending_and_selected', tokens <= set(case.service._offers) and
          any(key[0] == owner for key in case.service._selected))
    status, _ = case.request('/api/guest/profile', payload, method='DELETE')
    check('authenticated_delete_version_conflict_is_409', status == 409)
    check('authenticated_delete_409_clears_pending_and_selected', not tokens & set(case.service._offers) and
          not any(key[0] == owner for key in case.service._selected))


def changed_head(case):
    owner = case.server.profiles.digest(case.cookie.split('=', 1)[1])
    def change():
        with case.server.adaptive.lock:
            case.server.adaptive.current_chain[owner] = 'foreign-chain'
    case.discovery.on_read = change
    status, rejected = case.search()
    check('changed_head_after_source_read_rejects_409', status == 409)
    check('changed_head_response_suppresses_identity_and_comparison',
          'identity' not in rejected and 'comparison' not in rejected)
    calls = len(case.discovery.calls)
    case.discovery.on_read = None
    status, _ = case.search()
    check('stale_head_replay_stops_before_source_query', status == 409 and len(case.discovery.calls) == calls)


def consumer(case):
    case.service.purpose = None
    status, out = case.search()
    check('consumer_held_is_200', status == 200)
    check('consumer_held_has_no_source_candidates_or_bindings', out['identity']['candidates'] == [] and
          out['identity']['preparation']['bindings'] == [] and not case.discovery.calls and not case.exact.calls)


IdentityHttpTests.setUpClass()
try:
    for operation in (cross_chain, deletion, changed_head, consumer):
        fixture(operation)
finally:
    IdentityHttpTests.tearDownClass()

for mode in ('discovery_candidate_STOP', 'exact_source_record_STOP', 'exact_actor_snapshot_STOP'):
    case = IdentityJourneyTests()
    case.setUp()
    if mode == 'discovery_candidate_STOP':
        original = case.provider_discovery.search
        def stopped(*args, **kwargs):
            out = original(*args, **kwargs)
            out['candidates'][0]['states']['source_use_state'] = 'source_STOP'
            return out
        case.provider_discovery.search = stopped
        call = lambda: case.service.provider_search(OWNER, case.profile, item_id='doctor-1')
    else:
        if mode == 'exact_source_record_STOP':
            case.providers.value['sources'][0]['states']['source_use_state'] = 'source_STOP'
        else:
            case.providers.value['entity_candidates'][0]['snapshot_source_use_state'] = 'source_STOP'
        call = case.provider
    rejected = False
    try:
        call()
    except IdentityJourneyError:
        rejected = True
    check(mode + '_rejects_before_labels', rejected)

case = IdentityJourneyTests()
case.setUp()
case.providers.value['site_candidates'][0]['source_periods'] = {'entity': {'end': '2025-12-31'}}
case.providers.value['entity_candidates'][0]['source_native_fields']['status'] = {'active': False}
case.providers.value['role_observations'][0]['source_native_fields']['qualifiers'] = {'note': 'Fictional exact qualification'}
out = case.provider()
check('explicit_source_period_is_preserved', out['candidates'][0]['source_periods']['entity']['end'] == '2025-12-31')
check('literal_status_and_qualification_are_inspectable', any(
    row['source_native_context']['status'] == {'active': False} for row in out['source_contexts']) and any(
    row['source_native_context']['qualifiers'] == {'note': 'Fictional exact qualification'} for row in out['source_contexts']))
check('provider_result_discloses_unrouted_exact_windows', out['continuation_state'] == 'exact_entity_role_location_windows_not_routed')

report = {'schema': 'daylight.final-independent-identity-probes.v2',
    'observed_at': datetime.now(timezone.utc).isoformat(), 'passed': True, 'checks': checks,
    'prior_attempt': 'probe_final_identity.py and probe-final.log remain unchanged; additional comparison-template HTTP seed was not a valid controller fixture. No product defect or actual-source journey is claimed.',
    'operator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'code_sha256': {str((APP / name).relative_to(ROOT)): hashlib.sha256((APP / name).read_bytes()).hexdigest()
                    for name in EXPECTED},
    'fixtures': ['isolated real HTTP cookie/CSRF/HMAC/head/journal with scripted source dependencies',
                 'original cross-chain logical sequence with fixed fictional comparison adapter',
                 'core STOP/context probes use the actual comparison profile adapter over fictional reports; actual-source HTTP is root-owned'],
    'real_customer_access': False, 'actual_postgresql_queries': 0, 'paid_model_calls': 0,
    'runtime_or_service_actions': 0, 'new_source_or_consumer_acceptance': False}
target = Path(__file__).with_name('IDENTITY_PROBES.json')
with target.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({'passed': True, 'checks': len(checks), 'output': str(target)}))
