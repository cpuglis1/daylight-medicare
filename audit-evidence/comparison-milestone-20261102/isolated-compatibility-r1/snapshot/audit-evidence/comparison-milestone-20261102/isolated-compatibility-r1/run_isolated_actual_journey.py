"""Fictional HTTP journey over the real profile adapter and retained sources.

The Responses transport is scripted locally. No customer stores, paid model
calls, cloud resources or source acceptance are involved. --serve leaves a
disposable, visibly mocked preview for rendered inspection.
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

ROOT = Path(__file__).resolve().parents[3]
REAL_RESEARCH_ROOT = Path('/Users/cep4u/daylight')
APP = ROOT / 'alternatives/advisor-first'
sys.path.insert(0, str(APP))
from server import build
from chat import ResponsesClient
from identity_journey import local_identity_journey
from natural_flow import CONTEXT_POLICY

# Preload every serving dependency from the captured code before the factory
# inserts its real repository path for checked immutable controls/socket.
sys.path.insert(0, str(ROOT / 'infrastructure/daylight-data/src'))
import daylight_data.serving.drug_candidates
import daylight_data.serving.identity
import daylight_data.serving.provider_identity
import daylight_data.serving.provider_candidates

CARE = ('I want to compare coverage for myself. I understand the basics. '
        'I want to keep Pacific Nephrology Medical Grp in Inglewood. '
        'I take DOXEPIN 10 mg oral capsule.')
CORRECTION = 'Correction: my DOXEPIN strength is 20 mg instead of 10 mg.'


class ScriptedTransport:
    def __init__(self): self.calls = []

    def __call__(self, payload):
        self.calls.append(copy.deepcopy(payload))
        sent = json.loads(payload['input'][0]['content'])
        schema = payload['text']['format']['name']
        if schema == 'daylight_guide_commands':
            text = sent['submitted_text']
            updates = []
            def add(identifier, fields, entity='profile', correction=False):
                updates.append({'id': identifier, 'entity': entity,
                    'fields': [{'key': key, 'value': value} for key, value in fields.items()],
                    'quote': text, 'scope': 'current', 'subject': 'beneficiary',
                    'uncertain': False, 'correction': correction})
            if text == CARE:
                add('T01', {'choice': 'compare'}); add('RC01', {'choice': 'self'})
                add('T02', {'choice': 'comfortable'})
                add('T06', {'text': 'Pacific Nephrology Medical Grp'})
                add('RC21', {'practice': 'Pacific Nephrology Medical Grp', 'city': 'Inglewood'}, 'new')
                add('T07', {'text': 'DOXEPIN 10 mg oral capsule'})
                add('RC22', {'name': 'DOXEPIN', 'strength': '10 mg', 'form': 'oral capsule'}, 'new')
            elif text == CORRECTION:
                add('RC22', {'strength': '20 mg'}, 'medicine-1', correction=True)
            value = {'updates': updates, 'requests': [], 'fact_ids': [],
                'goal_quote': 'I want to compare coverage for myself.' if text == CARE else '', 'situation_proposals': [],
                'education_request': {'kind': 'none', 'concept_ids': [], 'quote': ''},
                'agenda': {'concerns': [], 'priorityReason': {
                    'topic': '', 'reason': '', 'quote': '', 'subject': 'beneficiary', 'scope': 'current'}}}
        elif schema == 'daylight_resolved_conversation':
            move = next(iter(sent['question_candidates']), None)
            value = {'question_target': move['id'] if move else None,
                'reply': 'We can organize your reported details and the checks still needed.',
                'question': move['question']['question'] if move else '',
                'report_refs': [], 'evidence_refs': [],
                'education': {'purpose': 'advance', 'updates': [], 'visual': 'none'},
                'agenda_update': {'current_concern': '', 'pause': False}}
        else: raise AssertionError('Unexpected scripted model stage')
        return {'status': 'completed', 'model': 'gpt-5.4', 'service_tier': 'default',
            'usage': {'input_tokens': 300, 'output_tokens': 70, 'total_tokens': 370,
                'input_tokens_details': {'cached_tokens': 0}},
            'output': [{'content': [{'type': 'output_text', 'text': json.dumps(value)}]}]}


class Journey:
    def __init__(self, server):
        self.server, self.cookie, self.csrf, self.state = server, None, None, None
        self.requests = []
        _, session = self.request('/api/guest/session'); self.csrf = session['csrf']
        _, self.state = self.request('/api/conversation/initial')
        self.turn({'type': 'start'})

    def request(self, path, payload=None, method=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=30)
        headers = {'Origin': 'http://127.0.0.1:' + str(self.server.server_port)}
        if self.cookie: headers['Cookie'] = self.cookie
        if payload is not None:
            headers['Content-Type'] = 'application/json'; headers['X-Daylight-CSRF'] = self.csrf
        start = time.perf_counter()
        connection.request(method or ('POST' if payload is not None else 'GET'), path,
            json.dumps(payload) if payload is not None else None, headers)
        response = connection.getresponse()
        cookie = response.getheader('Set-Cookie')
        if cookie: self.cookie = cookie.split(';')[0]
        out = json.loads(response.read()); status = response.status; connection.close()
        self.requests.append({'path': path, 'status': status,
            'elapsed_ms': round((time.perf_counter() - start) * 1000, 3)})
        return status, out

    def body(self, **extra):
        return {'guide': copy.deepcopy(self.state['guide']), 'record': copy.deepcopy(self.state['record']),
            'requestId': str(uuid.uuid4()),
            **({'continuation': self.state['continuation']} if self.state.get('continuation') else {}), **extra}

    def turn(self, action, ai=False):
        status, out = self.request('/api/conversation/turn', self.body(action=action,
            aiConsent=ai, contextPolicy=CONTEXT_POLICY if ai else None))
        if status != 200: raise AssertionError(('turn', status, out))
        self.state = out; return out

    def identity(self, path, **extra):
        status, out = self.request(path, self.body(**extra))
        if status != 200: raise AssertionError((path, status, out))
        assert out['continuation'] == self.state['continuation']
        assert 'guide' not in out and 'record' not in out
        return out


def run(server, transport, output, input_manifest):
    if output.exists(): raise ValueError('Preserve existing audit receipts.')
    source_inputs = json.loads(input_manifest.read_text())
    def stable_inputs():
        return all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest
            for name, digest in source_inputs.items())
    if not stable_inputs(): raise AssertionError('Merged source changed before the journey.')
    checks, stages = [], []
    def check(name, condition):
        checks.append({'name': name, 'passed': bool(condition)})
        if not condition: raise AssertionError(name)
    journey = Journey(server)
    first = journey.turn({'type': 'message', 'message': CARE}, ai=True)
    check('typed_message_two_scripted_stages', len(transport.calls) == 2)
    check('no_interpretation_acceptance_card', not first.get('review'))
    view = journey.identity('/api/identity/view')['identity']
    stages.append({'stage': 'reported_items', 'identity': view})
    check('real_adapter_has_both_current_care_items',
        {(row['kind'], row['item_id']) for row in view['items']} ==
        {('drug_product', 'medicine-1'), ('provider_site', 'doctor-1')})
    drug = journey.identity('/api/identity/drug/search', itemId='medicine-1')['identity']
    product = next(row for row in drug['candidates'] if row.get('details', {}).get('rxcui') == '1000048')
    check('actual_drug_candidate_selectable', product['selectable'] is True)
    selected_drug = journey.identity('/api/identity/confirm', choiceToken=drug['choice_token'],
        candidateId=product['candidate_id'], confirmed=True)['identity']
    check('explicit_drug_selection_bound', selected_drug['assessment']['identity_state'] == 'bound')
    entities = journey.identity('/api/identity/provider/search', itemId='doctor-1')['identity']
    stages.append({'stage': 'provider_name_discovery', 'identity': entities})
    check('name_discovery_is_not_site_selection', all(row['selectable'] is False for row in entities['candidates']))
    entity = next(row for row in entities['candidates'] if 'pacific nephrology' in str(row['label']).casefold())
    sites = journey.identity('/api/identity/provider/search', itemId='doctor-1',
        selector=entity['selector'], choiceToken=entities['choice_token'])['identity']
    stages.append({'stage': 'provider_site_choice', 'identity': sites})
    site = next(row for row in sites['candidates'] if row['selectable']
        and row.get('site', {}).get('address', {}).get('city') == 'Inglewood')
    check('explicit_site_fixture_preserves_reported_city_without_filtering_alternatives',
        any(row.get('site', {}).get('address', {}).get('city') == 'Culver City' for row in sites['candidates']))
    selected_site = journey.identity('/api/identity/confirm', choiceToken=sites['choice_token'],
        candidateId=site['candidate_id'], confirmed=True)['identity']
    check('explicit_site_selection_bound', selected_site['assessment']['identity_state'] == 'bound')
    calls_before = len(transport.calls)
    prepared = journey.identity('/api/comparison/journey')
    attached = prepared['comparison']['case_preparation']['identity_preparation']
    stages.append({'stage': 'comparison_preparation', 'comparison': prepared['comparison'], 'identity': prepared['identity']})
    check('real_adapter_two_technical_associations', len(attached['assessments']) == 2 and
        all(row['technical_report_association']['identity_state'] == 'bound' for row in attached['assessments']))
    check('all_consumer_source_purposes_held', all(row['state'] == 'held' for row in prepared['comparison']['authority'].values()))
    check('coverage_not_promoted', attached['coverage_findings'] == [] and
        all(row['coverage_state'] == 'unresolved' for row in attached['assessments']))
    check('source_selections_no_model_stage', len(transport.calls) == calls_before)
    check('nothing_saved_or_added_to_model_context', attached['saved'] is False and attached['ai_context_changed'] is False)
    # Reach the genuine existing end summary using current, consequential
    # questions, rather than manufacturing a summary in the browser.
    answers = {'T02': {'choice': 'comfortable'}, 'T04': {'choice': 'month', 'month': '2026-11'},
        'T05': {'choice': 'original'}, 'T03': {'zip': '34102'},
        'T08': {'choice': 'local'}, 'T09': {'choice': 'no_preference'},
        'T10': {'choice': 'doctors'}}
    for _ in range(24):
        question = journey.state['assessment'].get('nextQuestion')
        if not question: break
        identifier = question['id']
        if identifier not in answers: raise AssertionError(('unplanned current question', question))
        journey.turn({'type': 'choice', 'id': identifier, 'entity': question.get('entity', 'profile'),
            'fields': answers[identifier]})
    check('genuine_end_summary_reachable_with_positive_items',
        journey.state['assessment'].get('nextQuestion') is None and
        journey.state['assessment']['state'] == 'external_validation_held' and
        not journey.state['assessment'].get('intakePaused') and not journey.state['assessment'].get('conversationOpen'))
    stages.append({'stage': 'genuine_summary', 'assessment': journey.state['assessment']})
    journey.turn({'type': 'message', 'message': CORRECTION}, ai=True)
    corrected = journey.identity('/api/comparison/journey')['comparison']['case_preparation']['identity_preparation']
    check('reported_strength_correction_invalidates_old_drug_selection',
        next(row for row in corrected['assessments'] if row['kind'] == 'drug_product')['technical_report_association']['identity_state'] == 'unresolved')
    check('unrelated_provider_selection_preserved_after_drug_correction',
        next(row for row in corrected['assessments'] if row['kind'] == 'provider_site')['technical_report_association']['identity_state'] == 'bound')
    status, foreign = journey.request('/api/identity/confirm', journey.body(choiceToken=drug['choice_token'],
        candidateId=product['candidate_id'], confirmed=True))
    check('old_drug_offer_cannot_reconfirm_after_correction', status == 422)
    journey.identity('/api/identity/forget')
    empty = journey.identity('/api/comparison/journey')['comparison']['case_preparation']['identity_preparation']
    check('forget_clears_visit_bindings', empty['preparation']['selected_count'] == 0)
    check('source_candidates_never_sent_to_scripted_model', not any(
        needle in json.dumps(call) for call in transport.calls for needle in
        ('retained_L08_composite_directory_site', 'L05:4a39eaf9', 'source_observation_locators')))
    # A second fictional guest exercises the actual saved-profile adapter. A
    # resumed conversation retains reported care details, but the old visit's
    # source offers and technical selections must not become saved authority.
    resumed = Journey(server)
    resumed.turn({'type': 'message', 'message': CARE}, ai=True)
    offered = resumed.identity('/api/identity/drug/search', itemId='medicine-1')['identity']
    chosen = next(row for row in offered['candidates'] if row.get('details', {}).get('rxcui') == '1000048')
    resumed.identity('/api/identity/confirm', choiceToken=offered['choice_token'],
        candidateId=chosen['candidate_id'], confirmed=True)
    before_resume = resumed.identity('/api/comparison/journey')['comparison']['case_preparation']['identity_preparation']
    check('resume_fixture_has_one_explicit_source_selection', before_resume['preparation']['selected_count'] == 1)
    resumed.state['guide']['preferences'].update(saveGuide=True, saveSensitive=True)
    status, receipt = resumed.request('/api/conversation/save', {
        'guide': resumed.state['guide'], 'record': resumed.state['record'],
        'expectedVersion': 0, 'expectedReadinessVersion': 0, 'operationId': str(uuid.uuid4())})
    check('fictional_sensitive_profile_save_succeeds', status == 200)
    status, saved = resumed.request('/api/guest/profile')
    check('saved_profile_is_readable_by_same_fictional_guest', status == 200)
    status, readiness = resumed.request('/api/guest/readiness')
    check('saved_readiness_is_readable_by_same_fictional_guest', status == 200)
    saved_text = json.dumps([saved, readiness])
    check('saved_profile_excludes_visit_source_authority', not any(needle in saved_text for needle in
        (offered['choice_token'], chosen['candidate_id'], 'identity_preparation', 'source_observation_locators')))
    old_chain = resumed.state['continuation'].split('.')[0]
    calls_before_resume = len(transport.calls)
    resumed.state = {'guide': saved['guide'], 'record': readiness['record']}
    refreshed = resumed.turn({'type': 'refresh'})
    check('saved_profile_refresh_starts_a_new_conversation_chain',
        refreshed['continuation'].split('.')[0] != old_chain)
    after_resume = resumed.identity('/api/comparison/journey')
    check('resumed_real_adapter_preserves_both_reported_care_items',
        {(row['kind'], row['item_id']) for row in after_resume['identity']['items']} ==
        {('drug_product', 'medicine-1'), ('provider_site', 'doctor-1')})
    resumed_preparation = after_resume['comparison']['case_preparation']['identity_preparation']
    check('resume_does_not_retain_old_visit_source_selections',
        resumed_preparation['preparation']['selected_count'] == 0 and
        all(row['technical_report_association']['identity_state'] == 'unresolved'
            for row in resumed_preparation['assessments']))
    status, _ = resumed.request('/api/identity/confirm', resumed.body(choiceToken=offered['choice_token'],
        candidateId=chosen['candidate_id'], confirmed=True))
    check('old_visit_offer_cannot_be_replayed_after_resume', status == 422)
    check('save_resume_and_source_preparation_add_no_model_stage', len(transport.calls) == calls_before_resume)
    stages.append({'stage': 'saved_profile_resume', 'comparison': after_resume['comparison'],
        'identity': after_resume['identity'], 'fictional_save_receipt': receipt})
    if not stable_inputs(): raise AssertionError('Merged source changed during the journey.')
    report = {'schema': 'daylight.actual-identity-http-journey.v1',
        'observed_at': datetime.now(timezone.utc).isoformat(), 'passed': all(row['passed'] for row in checks),
        'checks': checks, 'requests': journey.requests + resumed.requests, 'stages': stages,
        'fixture_kind': 'fictional_reports_mirroring_public_source_names_with_scripted_responses_transport',
        'real_profile_adapter': True, 'real_postgresql_sources': True, 'postgres_writes': 0,
        'real_customer_store_reads': False, 'paid_ai_calls': 0, 'consumer_release': False, 'new_acceptance': False,
        'scripted_model_stages': len(transport.calls),
        'merged_source_inputs_sha256': source_inputs, 'merged_source_inputs_unchanged': True,
        'merged_source_input_manifest': str(input_manifest.resolve().relative_to(ROOT)),
        'merged_source_input_manifest_sha256': hashlib.sha256(input_manifest.read_bytes()).hexdigest(),
        'code_sha256': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in
            [Path(__file__), APP/'server.py', APP/'identity_http.py', APP/'identity_journey.py', APP/'comparison_journey.py']}}
    with output.open('x') as handle: json.dump(report, handle, indent=2); handle.write('\n')
    print(json.dumps({'passed': report['passed'], 'checks': len(checks), 'http_requests': len(report['requests']),
        'output': str(output)}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path); parser.add_argument('--serve', type=int)
    parser.add_argument('--input-manifest', type=Path,
        default=Path(__file__).parent/'ADVISOR_TEST_INPUTS_R3.json')
    args = parser.parse_args()
    transport = ScriptedTransport()
    with tempfile.TemporaryDirectory(prefix='daylight-milestone-fictional-') as temporary:
        service = local_identity_journey(repository_root=REAL_RESEARCH_ROOT, internal_research=True)
        server = build(args.serve or 0, fixture=True, database=Path(temporary)/'fictional.sqlite3',
            identity_service=service, client=ResponsesClient(key='synthetic', model='gpt-5.4', transport=transport))
        # Only the transport is simulated: use the current two-stage flow and
        # real report provenance/adapter. The fixture banner remains visible.
        server.adaptive.fixture = False; server.adaptive.agent.enabled = True
        if args.serve:
            print('Mocked preview at http://127.0.0.1:'+str(server.server_port)+'/', flush=True)
            print('Exact fictional opening: '+CARE, flush=True)
            try: server.serve_forever()
            finally: server.server_close()
        else:
            if args.output is None: parser.error('--output or --serve is required')
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            try: run(server, transport, args.output.resolve(), args.input_manifest)
            finally: server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__': main()
