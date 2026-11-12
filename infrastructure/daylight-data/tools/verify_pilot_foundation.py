#!/usr/bin/env python3
"""Exercise the bound D146 read interface with public-source and fictional fixtures."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import psycopg

from daylight_data.serving import pilot_foundation as module
from daylight_data.serving.binding import ResearchServingError


ROOT = Path(__file__).resolve().parents[3]
SCOPE = {'year': 2026, 'county_fips': '12021', 'purpose': 'offline_research'}
HUMANA = '2026:H1036:217:000'
WELLCARE = '2026:H1032:198:000'
PUBLIX = '1841534534'


def verify(reader):
    checks = []

    def require(label, condition):
        if not condition:
            raise AssertionError(label)
        checks.append(label)

    def query(dataset, filters=None, **kwargs):
        scope = SCOPE | {key: kwargs.pop(key) for key in SCOPE if key in kwargs}
        return reader.read(dataset, **scope, filters=filters, **kwargs)

    def reject(label, code, action):
        try:
            action()
        except ResearchServingError as error:
            require(label, str(error) == code)
        else:
            raise AssertionError(label)

    unknown = query('provider_entities', name='Fictionalxyzzyperson NoSuchPractice')
    require('unmatched identity stays unknown', unknown['state'] == 'unknown_no_retained_observation')
    listing = query('ma_wellcare_listings', name='Mark Josephson')['records']
    site = [row for row in listing if any(address.get('postal_raw') == '34102'
            and '311' in address.get('street_raw', '') for address in
            json.loads(row['data']['fields_json'])['addresses'])]
    require('dated directory name and source site', bool(site))
    require('source PDF hash, page and native key are preserved',
            all(row['data']['page'] > 0 and len(row['data']['document_sha256']) == 64
                and row['locator']['key']['id'] == row['data']['id'] for row in site))
    docs = query('ma_wellcare_plan_documents', {'offering_id': WELLCARE})['records']
    require('exact plan has a qualified directory bridge', any(
        json.loads(row['data']['fields_json'])['partial_network_reference'] for row in docs))
    exact = query('ma_role_networks', {'offering_id': '2026:H1045:028:000',
                                      'state': 'held_network_join'}, limit=1)
    require('held network joins remain held', exact['records'][0]['data']['state'] == 'held_network_join')

    location = query('pharmacy_locations', {'npi': PUBLIX, 'network_zip': '34102'})['records']
    require('exact pharmacy has Collier source location',
            len(location) == 1 and location[0]['data']['county_fips'] == '12021'
            and bool(json.loads(location[0]['data']['record_json'])['identity_source']['sha256']))
    for offering, status, source_ordinal in [(HUMANA, 'standard', 31819782),
                                             (WELLCARE, 'preferred', 28798708)]:
        records = query('pharmacy_network', {'offering_id': offering, 'pharmacy_npi': PUBLIX,
                                            'PHARMACY_ZIPCODE': '34102'})['records']
        require(f'published retail class and native row {offering}',
                len(records) == 1 and records[0]['data']['retail_status'] == status
                and records[0]['data']['source_ordinal'] == source_ordinal)
    unresolved = query('pharmacy_network', {'pharmacy_npi': '1285263780',
                                           'PHARMACY_ZIPCODE': 'XXXXX'})['records']
    resolved = query('pharmacy_network', {'pharmacy_npi': '1427893932',
                                         'PHARMACY_ZIPCODE': '33908'}, limit=1)['records']
    require('masked HealthPark NPI and retail NPI remain distinct', len(unresolved) == 7 and bool(resolved))
    require('no nearest ZIP substitution', query('pharmacy_network', {'offering_id': WELLCARE,
            'pharmacy_npi': PUBLIX, 'PHARMACY_ZIPCODE': '34103'})['records'] == [])

    identities = {}
    for rxcui, ndc in [('861007', '70010006310'), ('860975', '70010049105')]:
        products = query('drug_products', {'rxcui': rxcui})['records']
        require(f'exact drug identity {rxcui}', len(products) == 1)
        identities[rxcui] = json.loads(products[0]['data']['payload'])['name']
        rows = query('formulary_rows', {'formulary_id': '00026411', 'ndc': ndc, 'rxcui': rxcui,
                                      'table_name': 'basic'})['records']
        require(f'exact formulary and flag locator {rxcui}', len(rows) == 1 and
                json.loads(rows[0]['data']['raw_json'])['FORMULARY_VERSION'] == '16')
        price = query('average_prices', {'offering_id': HUMANA, 'ndc': ndc, 'days_supply': '30'})
        require(f'average and raw PSV distinct from estimate {rxcui}', len(price['records']) == 1 and
                price['records'][0]['data']['disposition'] == 'published_average' and
                bytes.fromhex(price['records'][0]['data']['raw_line']).startswith(b'H1036|217|000|'))
    require('drug forms kept distinct', len(set(identities.values())) == 2)
    costs = query('cost_schedules', {'offering_id': HUMANA}, limit=1)
    next_costs = query('cost_schedules', {'offering_id': HUMANA}, limit=1,
                       after=costs['next_after'], expected_binding=costs['binding_id'])
    require('schedule page is bound and deterministic', costs['records'][0]['ordinal'] <
            next_costs['records'][0]['ordinal'] and costs['capability']['state'] == 'offline_candidate')
    require('review and participant acceptance remain absent',
            costs['acceptance']['source_for_participant_use'] is None and costs['acceptance']['method'] is None
            and costs['acceptance']['participant_output'] is None and not costs['acceptance']['participant_release'])

    fips = {'offering_id': WELLCARE}
    reject('wrong year', 'PILOT_WRONG_YEAR', lambda: query('drug_plans', fips, year=2027))
    reject('wrong plan geography', 'PILOT_UNSUPPORTED_PLAN_GEOGRAPHY',
           lambda: query('drug_plans', fips, county_fips='12071'))
    reject('participant use without acceptance', 'PILOT_PARTICIPANT_ACCEPTANCE_MISSING',
           lambda: query('drug_plans', fips, purpose='participant'))
    reject('personal estimate purpose', 'PILOT_PURPOSE_NOT_ALLOWED',
           lambda: query('average_prices', {'offering_id': WELLCARE}, purpose='estimate'))
    reject('cursor without binding', 'PILOT_BINDING_CHANGED', lambda: query('cost_schedules', fips, after=1))
    reject('cursor on another revision', 'PILOT_BINDING_CHANGED',
           lambda: query('cost_schedules', fips, after=1, expected_binding='old'))
    reject('unsupported filter', 'PILOT_INVALID_QUERY', lambda: query('drug_plans', {'year': '2026'}))

    expires = datetime.fromisoformat(reader.manifest['policy']['technical_read_until_utc'])
    with patch.object(reader, 'clock', return_value=expires - timedelta(microseconds=1)):
        require('last instant before expiry permits offline read', bool(query('drug_plans', fips)['records']))
    with patch.object(reader, 'clock', return_value=expires):
        reject('expiry is exclusive', 'PILOT_EVIDENCE_STALE', lambda: query('drug_plans', fips))
    live = module.source_controls(reader.source_dsn)
    stop = {'source_id': 'fictional:withdrawn', 'state': 'stopped', 'reason': 'test fixture',
            'updated_at': datetime.now(timezone.utc).isoformat()}
    with patch.object(module, 'source_controls', return_value=live | {'source_access_states': [stop]}):
        reject('new withdrawal refuses data', 'PILOT_SOURCE_WITHDRAWAL_OR_CONTROL_CHANGE',
               lambda: query('drug_plans', fips))
    with patch.object(module, 'source_controls', side_effect=psycopg.OperationalError('fixture')):
        reject('unreachable source authority refuses data', 'PILOT_SOURCE_CONTROLS_UNAVAILABLE',
               lambda: query('drug_plans', fips))
    with patch.object(module, 'file_hash', return_value='changed'):
        reject('changed selection or inherited STOP control refuses data', 'PILOT_SOURCE_CONTROL_CHANGED',
               lambda: query('drug_plans', fips))
    with TemporaryDirectory() as directory:
        broken = Path(directory) / 'binding.json'
        broken.write_text(json.dumps(reader.manifest | {'database': 'changed'}))
        reject('tampered binding refuses startup', 'PILOT_BINDING_INVALID',
               lambda: module.PilotFoundation(broken, root=ROOT,
                                             package_dsn=reader.package_dsn, source_dsn=reader.source_dsn))
    with psycopg.connect(reader.package_dsn) as conn:
        require('new database defaults to read-only',
                conn.execute('SHOW default_transaction_read_only').fetchone()[0] == 'on')
        try:
            conn.execute('CREATE TEMP TABLE fictional_write_probe (value text)')
        except psycopg.errors.ReadOnlySqlTransaction:
            checks.append('write rejected on the new database')
            conn.rollback()
        else:
            conn.rollback()
            raise AssertionError('write unexpectedly allowed')
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binding', type=Path)
    parser.add_argument('receipt', type=Path)
    args = parser.parse_args()
    reader = module.PilotFoundation(args.binding, root=ROOT,
        package_dsn=os.environ['DAYLIGHT_FOUNDATION_PACKAGE_DSN'],
        source_dsn=os.environ['DAYLIGHT_FOUNDATION_SOURCE_DSN'])
    checks = verify(reader)
    with args.receipt.open('x') as stream:
        json.dump({'binding_id': reader.manifest['binding_id'], 'passed': len(checks), 'checks': checks,
                   'withdrawal_fixture': 'mocked live-ledger response; no real STOP written'}, stream, indent=2)
        stream.write('\n')
    print(f'{len(checks)} D146 read and boundary assertions passed')


if __name__ == '__main__':
    main()
