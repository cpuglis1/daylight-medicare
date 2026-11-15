#!/usr/bin/env python3
"""Replay D146 public-source fixtures and the local fictional HTTP workflow."""

import argparse
from collections import Counter
from contextlib import closing
from dataclasses import replace
from datetime import date, datetime
import http.client
import json
import os
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
from threading import Event, Thread
from time import monotonic
from unittest.mock import patch

from daylight_data.serving import pilot_foundation
from daylight_data.serving.binding import ResearchServingError
from daylight_data.serving.pilot_doctors import Confirmation, PilotDoctors

ROOT = Path(__file__).resolve().parents[3]
PACKET = ROOT / 'audit-evidence/pilot-doctors-20261112'
L08 = ROOT / 'docs/data/l08-provider-networks-2026-10-27'
HTTP = '/api/pilot-doctors/'


def audit_fixture_sources(fixtures):
    """Check fixture expectations against native SQLite, independently of the projection."""
    with closing(sqlite3.connect((L08 / 'original-medicare-r6/original-medicare.sqlite3').as_uri()
                                 + '?mode=ro&immutable=1', uri=True)) as federal, closing(sqlite3.connect(
                                     (L08 / 'wellcare-r5/providers.sqlite3').as_uri() + '?mode=ro&immutable=1',
                                     uri=True)) as carrier:
        for item in fixtures['search']:
            for row in item.get('source', {}).get('rows', []):
                assert federal.execute("SELECT npi FROM observations WHERE source_id='clinicians' AND source_row=?",
                                       (row,)).fetchone()[0] in item['expected_npis'], item
        for item in fixtures['evidence']:
            plan = item['selection']['offering_id']
            for table, key in item.get('native', {}).items():
                if table == 'r5_wellcare_records':
                    query = '''SELECT 1 FROM r5_wellcare_records r JOIN r5_plan_directory_bindings b
                               USING(document_sha256) WHERE r.id=? AND b.offering_id=? AND r.county_raw='Collier' '''
                elif table == 'r4_humana_entries':
                    query = '''SELECT 1 FROM r4_humana_entries r JOIN plan_documents b USING(document_sha256)
                               WHERE r.id=? AND b.offering_id=? AND r.name_kind='credentialed_clinician_name'
                               AND b.scope_state='published_exact_plan_directory; explicitly_partial' '''
                elif table == 'aetna_query_observations':
                    query = '''SELECT 1 FROM aetna_query_observations WHERE id=? AND offering_id=?
                               AND json_extract(fields_json, '$.fields.published_network_label')='In Network' '''
                elif table == 'pdf_records':
                    query = '''SELECT 1 FROM pdf_records r JOIN plan_documents b USING(document_sha256)
                               WHERE r.id=? AND b.offering_id=? AND b.scope_state='exact_2026_product_publication' '''
                else:
                    assert table == 'relationships'
                    query = "SELECT 1 FROM relationships WHERE rowid=? AND offering_id=? AND state='source_listed_observation'"
                assert carrier.execute(query, (key, plan)).fetchone(), item
            if item.get('hold'):
                assert carrier.execute('SELECT 1 FROM plan_networks WHERE offering_id=? AND state=?',
                                       (plan, item['hold'])).fetchone(), item
            if item.get('assignment_row'):
                row = federal.execute("""SELECT npi,json_extract(fields_json,'$.ind_assgn'),
                    json_extract(fields_json,'$.grp_assgn') FROM observations
                    WHERE source_id='clinicians' AND source_row=?""", (item['assignment_row'],)).fetchone()
                assert row[0] in item['selection']['candidate_id'], item
                if 'assignment' in item:
                    assert list(row[1:]) == item['assignment'], item
            if item.get('optout_row'):
                npi, start, end = federal.execute('SELECT npi,start_raw,end_raw FROM optout_periods WHERE source_row=?',
                                                  (item['optout_row'],)).fetchone()
                assert npi in item['selection']['candidate_id'] and start < item['selection']['intended_date'] < end


def run_search(service, cases):
    results = []
    for item in cases:
        started = monotonic()
        response = service.search(**item['query'])
        duration = round((monotonic() - started) * 1000, 1)
        candidates = response['candidates']
        expected_npis = set(item.get('expected_npis', []))
        expected_candidates = set(item.get('expected_candidates', []))
        found_npis = {npi for candidate in candidates for npi in candidate['source_npis']}
        found_candidates = {candidate['candidate_id'] for candidate in candidates}
        assert not response['automatic_confirmation'] and all(not x['identity_confirmed'] for x in candidates)
        assert not response['county_completeness_established']
        known = bool(expected_npis or expected_candidates)
        passed = (expected_npis <= found_npis and expected_candidates <= found_candidates) if known else not candidates
        results.append(item | {'passed': passed, 'known_answer': known, 'duration_ms': duration,
            'total_source_candidates': response['total_source_candidates'],
            'top_five': [{k: c[k] for k in ('candidate_id','kind','label','source_npis','source','matching_site_count')}
                         for c in candidates]})
    return results


def run_evidence(service, cases):
    results = []
    for item in cases:
        try:
            sel = service.selection(**item['selection'])
            if confirmation := item.get('fixture_confirmation'):
                values = {k: v if k == 'membership' else date.fromisoformat(v) for k, v in confirmation.items()}
                service.confirmations[sel] = [Confirmation(sel, **values, source='fictional:targeted-confirmation')]
            try:
                response = service.evidence(sel)
            finally:
                service.confirmations.pop(sel, None)
            assert response['appointment_availability'] == 'not_checked' and not response['participant_release']
            if item.get('hold'):
                assert item['hold'] in response['held_plan_joins'] and response['plan_source_gaps'], item
            if item.get('assignment_row'):
                assert any(a['source']['key']['source_row'] == item['assignment_row']
                           for a in response['assignment']), item
            if item.get('optout_row'):
                assert response['assignment_optout_overlap'] and any(
                    a['source']['key']['source_row'] == item['optout_row'] for a in response['opt_out']), item
            if item.get('native'):
                for table, key in item['native'].items():
                    assert any(a['source']['source_table'] == table and key in a['source']['key'].values()
                               for a in response['observations']), item
            if response['state'] in {'unknown', 'stale', 'conflict'}:
                assert response['outside_evidence_needed'] and response.get('membership') is None
        except ResearchServingError as error:
            response = {'state': str(error)}
        assert response['state'] == item['expected'], (item['id'], response['state'], item['expected'])
        results.append(item | {'actual': response})
    return results


def verify_http(service, fixtures):
    sys.path.insert(0, str(ROOT / 'alternatives/advisor-first'))
    from demo_server import build_demo
    selection = fixtures['evidence'][0]['selection']
    aetna = fixtures['evidence'][4]['selection']
    federal = fixtures['evidence'][15]['selection']
    checks = []
    with TemporaryDirectory(prefix='daylight-d146-check-') as tmp:
        database = Path(tmp) / 'fictional.sqlite3'
        demo = build_demo(0, fixture=True, database=database, doctor_service=service)
        thread = Thread(target=demo.serve_forever, daemon=True)
        thread.start()

        def request(path, payload=None, headers=None):
            connection = http.client.HTTPConnection('127.0.0.1', demo.server_port, timeout=15)
            supplied = {'Origin': f'http://127.0.0.1:{demo.server_port}', 'Content-Type': 'application/json', **(headers or {})}
            try:
                connection.request('POST' if payload is not None else 'GET', path,
                                   json.dumps(payload) if payload is not None else None, supplied)
                response = connection.getresponse()
                return response.status, json.loads(response.read()), dict(response.getheaders())
            finally:
                connection.close()

        def new_guest():
            code, info, headers = request('/api/guest/session')
            assert code == 200
            return {'Cookie': headers['Set-Cookie'].split(';')[0], 'X-Daylight-CSRF': info['csrf']}

        def check(label, action, status=200, expected=None):
            code, body, headers = action()
            assert code == status, (label, code, body)
            assert headers['Cache-Control'] == 'no-store'
            if expected is not None:
                assert all(body.get(k) == v for k, v in expected.items()), (label, body)
            checks.append(label)
            return body

        try:
            owner = new_guest()
            another_guest = new_guest()

            def post(route, payload, headers=owner):
                return request(HTTP + route, payload, headers)

            def select(value, previous=None, confirmed=True):
                return post('selection', {'expected_revision': previous, 'selection': value, 'confirmed': confirmed})

            check('fixture capability flag with live model unavailable', lambda: request('/api/status'),
                  expected={'live_conversation_available': False})
            assert request('/api/status')[1]['local_demo']['doctor_fixture']
            check('guest required', lambda: post('search', {'name': 'Mark Josephson'}, {}), 401)
            check('CSRF required', lambda: post('search', {'name': 'Mark Josephson'}, {'Cookie':owner['Cookie']}), 403)
            check('cross-origin blocked', lambda: post('search', {'name': 'Mark Josephson'},
                                                       owner | {'Origin': 'http://localhost:1'}), 403)
            check('source purpose cannot be selected by browser', lambda: post('search',
                  {'name': 'Mark Josephson', 'purpose': 'participant'}), 422)
            check('search has no automatic selection', lambda: post('search', {'name': 'Mark Josephson'}),
                  expected={'automatic_confirmation': False})
            check('fresh visit has no selection', lambda: post('visit', {}),
                  expected={'revision': None, 'has_selection': False})
            offices = check('all offices under explicit actor', lambda: post('sites',
                            {'candidate_id': federal['candidate_id'], 'offset': 0}))
            assert offices['site_count'] > 1 and len({s['site_id'] for s in offices['sites']}) > 1
            check('explicit confirmation required', lambda: select(selection, confirmed=False), 422)
            rev = check('exact selection', lambda: select(selection))['revision']
            check('visit recovery returns only selection presence and revision', lambda: post('visit', {}),
                  expected={'revision': rev, 'has_selection': True})
            previous = check('first dated listing receipt', lambda: post('evidence', {'revision': rev}),
                             expected={'state': 'dated_listing'})['receipt_id']
            check('revision isolated between visits', lambda: post('evidence', {'revision': rev}, another_guest), 409)
            check('older concurrent write cannot replace newer selection', lambda: select(selection), 409)

            current = selection
            for field, new_value in [('offering_id', '2026:H1032:199:000'), ('intended_date', '2026-09-22'),
                                     ('candidate_and_site', aetna), ('route', federal),
                                     ('site_id', 'CMS:site:FL341105729NA11190BLVD400')]:
                current = new_value if field in {'candidate_and_site','route'} else current | {field: new_value}
                old, rev = rev, check('correction ' + field, lambda: select(current, rev))['revision']
                check('invalidated after ' + field, lambda: post('evidence', {'revision': old}), 409)
                value = check('new receipt for ' + field, lambda: post('evidence', {'revision': rev}))
                assert value['selection'] == current and value['receipt_id'] != previous
                previous = value['receipt_id']

            # A result calculated while the input was edited must not be sent.
            entered, resume = Event(), Event()
            observed = []
            original = service.evidence

            def slow(selected):
                entered.set()
                assert resume.wait(5)
                return original(selected)

            with patch.object(service, 'evidence', side_effect=slow):
                caller = Thread(target=lambda: observed.append(post('evidence', {'revision': rev})), daemon=True)
                caller.start()
                assert entered.wait(5)
                try:
                    cleared = check('clear as soon as an input is edited', lambda: select(None, rev, False))
                finally:
                    resume.set()
                    caller.join(10)
            assert observed[0][0] == 409
            checks.append('in-flight evidence discarded after correction')
            check('cleared choice has no result', lambda: post('evidence', {'revision': cleared['revision']}), 409)
            again = check('select original tuple after corrections', lambda: select(selection, cleared['revision']))['revision']
            assert again != rev
            check('old revision remains invalid after returning to earlier selection', lambda: post('evidence', {'revision': rev}), 409)
            assert demo.profiles.get(owner['Cookie'].split('=', 1)[1])['guide'] is None
            assert not demo.adaptive.turn_journal
            checks.append('no saved guide or conversation journal entry')
        finally:
            demo.shutdown()
            demo.server_close()
            thread.join(5)
    return checks


def verify_controls(service, fixture):
    sel = service.selection(**fixture['selection'])
    reader = service.reader
    expired = datetime.fromisoformat(reader.manifest['policy']['technical_read_until_utc'])
    with patch.object(reader, 'clock', return_value=expired):
        result = service.evidence(sel)
        assert result['state'] == 'stale' and not result['observations']
    control = pilot_foundation.source_controls(reader.source_dsn)
    stop = {'source_id':'fictional:stop','state':'stopped','reason':'offline fixture','updated_at':expired.isoformat()}
    with patch.object(pilot_foundation, 'source_controls', return_value=control | {'source_access_states': [stop]}):
        for action in (lambda: service.search(name='Mark Josephson'), lambda: service.evidence(sel)):
            try:
                action()
            except ResearchServingError as error:
                assert str(error) == 'PILOT_SOURCE_WITHDRAWAL_OR_CONTROL_CHANGE'
            else:
                raise AssertionError('cached corpus survived a simulated STOP')
    assert pilot_foundation.source_controls(reader.source_dsn) == control
    try:
        service.evidence(replace(sel, intended_date=date(2027, 1, 1)))
    except ResearchServingError as error:
        assert str(error) == 'PILOT_WRONG_YEAR'
    else:
        raise AssertionError('wrong year served')
    return ['expired package returns stale without rows', 'simulated STOP denies search and evidence with warm cache',
            'source STOP ledger unchanged', 'wrong year rejected']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binding', type=Path)
    parser.add_argument('output_dir', type=Path)
    args = parser.parse_args()
    fixtures = json.loads((PACKET / 'fixtures.json').read_text())
    audit_fixture_sources(fixtures)
    reader = pilot_foundation.PilotFoundation(args.binding, root=ROOT,
        package_dsn=os.environ['DAYLIGHT_FOUNDATION_PACKAGE_DSN'],
        source_dsn=os.environ['DAYLIGHT_FOUNDATION_SOURCE_DSN'])
    started = monotonic()
    service = PilotDoctors(reader)
    build_seconds = round(monotonic() - started, 2)
    search = run_search(service, fixtures['search'])
    for row in search:
        if not row['passed']:
            print('search miss', row['query'], row.get('expected_npis', row.get('expected_candidates')), flush=True)
    evidence = run_evidence(service, fixtures['evidence'])
    controls = verify_controls(service, fixtures['evidence'][0])
    http = verify_http(service, fixtures)
    coverage = service.coverage()
    known = [item for item in search if item['known_answer']]
    hits = sum(item['passed'] for item in known)
    receipt = {'binding_id': service.binding_id, 'index_build_seconds': build_seconds,
        'search': {'queries': len(search), 'known_answer_queries': len(known), 'top_five_hits': hits,
                   'top_five_recall': hits / len(known), 'known_answer_distinct_identities': len({
                       ('npi', key) for item in known for key in item.get('expected_npis', [])} | {
                       ('source', key) for item in known for key in item.get('expected_candidates', [])}),
                   'no_match_cases': sum(not x['known_answer'] for x in search),
                   'automatic_confirmations': 0, 'results': search},
        'evidence_case_count': len(evidence), 'evidence_states': dict(Counter(x['expected'] for x in evidence)),
        'evidence_results': evidence, 'http_checks': http, 'control_checks': controls}
    for file, data in [('checks.json', receipt), ('coverage.json', coverage)]:
        with (args.output_dir / file).open('x') as stream:
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.write('\n')
    assert len(search) >= 50 and receipt['search']['known_answer_distinct_identities'] >= 25
    assert hits / len(known) >= .95 and all(x['passed'] for x in search if not x['known_answer'])
    assert len(evidence) >= 15 and len(coverage['plans']) == 72
    print(f'{hits}/{len(known)} top-five, {len(evidence)} evidence cases, {len(http)} HTTP checks, {len(controls)} controls')


if __name__ == '__main__':
    main()
