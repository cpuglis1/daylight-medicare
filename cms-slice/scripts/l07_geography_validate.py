#!/usr/bin/env python3
"""Independent source, county-classification and per-plan location audit."""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l07-pharmacy-networks-2026-10-27'
COUNTIES = {'12021': 'Collier', '12071': 'Lee', '12051': 'Hendry', '12087': 'Monroe'}


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for b in iter(lambda: stream.read(1048576), b''): h.update(b)
    return h.hexdigest()


def canon(address):
    return [re.sub('[^A-Z0-9]', '', str(address.get(f, '')).upper()) for f in ['address_1', 'address_2', 'city', 'state']] + [address.get('postal_code', '')[:5]]


def expected_scope(status, candidates):
    if status != 'unique_zip_matched_location' or len(candidates) != 1:
        return 'identity_or_location_unresolved', None
    c = candidates[0]
    if c['registry_address']['state'] != 'FL': return 'outside_Florida_as_registered', None
    g = c.get('geography')
    if not g or g['status'] != 'Match' or not g.get('county_fips', '').startswith('12'):
        return 'Florida_county_unresolved', None
    return COUNTIES.get(g['county_fips'], 'other_Florida_county'), g['county_fips']


def geographic_street_key(value):
    value = re.split(r'\s+(?:STE|SUITE|UNIT|APT|BLDG|#)\b', value, flags=re.I)[0].upper()
    words = {'ROAD':'RD','BOULEVARD':'BLVD','STREET':'ST','DRIVE':'DR','TRAIL':'TRL','LANE':'LN',
             'PARKWAY':'PKWY','NORTHEAST':'NE','SOUTHEAST':'SE','NORTHWEST':'NW','SOUTHWEST':'SW',
             'NORTH':'N','SOUTH':'S','EAST':'E','WEST':'W','COURT':'CT','AVENUE':'AVE','CIRCLE':'CIR','HIGHWAY':'HWY'}
    for word, abbreviated in words.items(): value = re.sub(r'\b'+word+r'\b', abbreviated, value)
    return re.sub('[^A-Z0-9]', '', value)


def validate(package, output):
    manifest = json.loads((package / 'manifest.json').read_text()); checks = {}
    for group in ['input_sha256', 'code_sha256']:
        for p, h in manifest[group].items(): checks[group + ':' + p] = sha(ROOT / p) == h
    for p, h in manifest['files_sha256'].items(): checks['output:' + p] = sha(package / p) == h
    if not all(checks.values()): raise ValueError('Location package changed')
    inputs = {a['address_id']: a for a in json.loads((BASE / 'identity-build-r1/florida-geography-input.json').read_text())}
    expected_geo, all_batch_ids = {}, set()
    source_observations = 0
    for batch in json.loads((BASE / 'geography-acquisition-r1/source-manifest.json').read_text())['batches']:
        receipt = batch['output']; raw = ROOT / receipt['path']
        if sha(raw) != receipt['sha256']: raise ValueError('Original Census batch changed')
        submitted = list(csv.reader(io.StringIO((ROOT / batch['input']['path']).read_text())))
        returned = list(csv.reader(io.StringIO(raw.read_text())))
        if {r[0] for r in submitted} != {r[0] for r in returned} or len(submitted) != len(returned):
            raise ValueError('Census input/response denominator differs')
        for row in submitted:
            if row[0] in inputs:
                address = inputs[row[0]]
                if re.sub('[^A-Z0-9]', '', row[1].upper()) != re.sub('[^A-Z0-9]', '', ' '.join(x for x in [address['address_1'], address['address_2']] if x).upper()):
                    raise ValueError('Wrong pharmacy address submitted to Census')
        for ordinal, row in enumerate(returned, 1):
            if row[0] in all_batch_ids: raise ValueError('Duplicate Census submission')
            all_batch_ids.add(row[0]); source_observations += len(row)
            g = {'address_id': row[0], 'status': row[2], 'source': {**receipt, 'record_ordinal': ordinal},
                 'basis': 'Census batch address-range geography'}
            if row[2] == 'Match':
                if len(row) != 12: raise ValueError('Unrecognized Census match layout')
                g.update(county_fips=row[8]+row[9], coordinates=row[5], match_type=row[3], matched_address=row[4])
            expected_geo[row[0]] = g
    if not set(inputs) <= all_batch_ids: raise ValueError('Florida address omitted from Census research')
    for receipt in json.loads((BASE / 'geography-followup-r2/source-manifest.json').read_text())['requests']:
        raw = ROOT / receipt['path']
        if sha(raw) != receipt['sha256']: raise ValueError('Census followup changed')
        matches = json.loads(raw.read_text()).get('result', {}).get('addressMatches', [])
        if len(matches) != 1 or len(matches[0].get('geographies', {}).get('Counties', [])) != 1: continue
        county = matches[0]['geographies']['Counties'][0]
        expected_geo[receipt['address_id']] = {'address_id': receipt['address_id'], 'status': 'Match',
            'county_fips': county['STATE']+county['COUNTY'], 'county_name': county['NAME'],
            'coordinates': matches[0].get('coordinates'), 'matched_address': matches[0]['matchedAddress'],
            'source': receipt, 'basis': 'Census structured-address geography; suite retained in identity source'}
        source_observations += 5
    decisions_path = next(ROOT / p for p in manifest['input_sha256'] if p.endswith('/decisions.json'))
    decisions = json.loads(decisions_path.read_text())
    for decision in decisions:
        source = decision['source']; path = ROOT / source['path']
        if sha(path) != source['sha256']: raise ValueError('County address query changed')
        native = json.loads(path.read_text()); address = inputs[decision['address_id']]
        number = re.match(r'\d+', address['address_1']).group()
        street = re.sub(r'^\d+\s+', '', re.split(r'\s+(?:SUITE|STE|UNIT|APT)\b', address['address_1'])[0])
        for index in decision['feature_indexes']:
            attributes = native['features'][index]['attributes']
            if decision['county_fips'] == '12021':
                if 'SlIq32SqARUHIhSx' not in source['requested_url'] or str(attributes['ADDRNUM']) != number:
                    raise ValueError('County/house number mismatch')
                norm = lambda s: re.sub('[^A-Z0-9]', '', s.upper())
                if norm(attributes['FULLNAME']) != norm(street):
                    route = decision['route_evidence']
                    if not route or sha(ROOT / route['path']) != route['sha256']: raise ValueError('Unsupported street alias')
                    roads = json.loads((ROOT / route['path']).read_text())['features']
                    names = {r['attributes']['FULLNAME'] for r in roads if r['attributes']['FEDROUTE']=='41'}
                    if not {'9th ST N', 'Tamiami TRL N'} <= names: raise ValueError('Road alias lacks route support')
                    if street not in ['TAMIAMI TRL N', 'US 41 N'] or attributes['FULLNAME'] not in names:
                        raise ValueError('Unrelated street alias used')
            elif decision['county_fips'] == '12071':
                if ('LvWGAAhHwbCJ2GMP' not in source['requested_url'] or str(attributes['Add_Number']) != number or
                        attributes['County'] != 'LEE COUNTY' or
                        geographic_street_key(attributes['Full_Address']) != geographic_street_key(address['address_1'])):
                    raise ValueError('Lee county address mismatch')
                if 'UNIT 117' in address['address_1'] and attributes['Unit'] != '117': raise ValueError('Wrong pharmacy unit')
            else: raise ValueError('Unexpected county decision')
            source_observations += len(attributes)
        if expected_geo[decision['address_id']]['status'] != 'Match':
            expected_geo[decision['address_id']] = {'address_id': decision['address_id'], 'status': 'Match',
                'county_fips': decision['county_fips'], 'county_name': decision['county_name'],
                'source': source, 'feature_indexes': decision['feature_indexes'], 'route_evidence': decision['route_evidence'], 'basis': decision['basis']}
    if json.loads((package / 'geography-evidence.json').read_text()) != expected_geo:
        raise ValueError('Geographic fields differ from exact retained source evidence')
    identities = {}
    with gzip.open(BASE / 'identity-build-r1/identities.jsonl.gz', 'rt') as f:
        for line in f:
            r = json.loads(line); identities[r['npi']] = r
    original = {(r['npi'], r['network_zip']): r for r in json.loads((BASE / 'identity-build-r1/network-location-joins.json').read_text())}
    seen, categories, exceptions = set(), Counter(), []
    con = sqlite3.connect('file:' + str(package / 'inventory.sqlite3') + '?mode=ro', uri=True)
    with gzip.open(package / 'locations.jsonl.gz', 'rt') as f:
        for line in f:
            row = json.loads(line); key = row['npi'], row['network_zip']; seen.add(key); old = original[key]
            if any(row[k] != old[k] for k in old): raise ValueError('Published identity join altered')
            expected_candidates = []
            item = identities.get(row['npi'])
            if item:
                if row['identity_source'] != item['source']: raise ValueError('Identity evidence pointer changed')
                for group in item['locations']:
                    a = group[0]
                    if canon(a) not in old['candidate_location_keys']: continue
                    aid = hashlib.sha256(json.dumps(canon(a)).encode()).hexdigest()[:20]
                    expected_candidates.append({'address_id': aid, 'registry_address': a,
                        'geography': expected_geo.get(aid) if a['state']=='FL' else None,
                        'source_state': 'Florida' if a['state']=='FL' else 'outside_Florida_as_registered'})
            if expected_candidates != row['candidate_locations']: raise ValueError('Candidate address/geography changed')
            category, county = expected_scope(old['status'], expected_candidates)
            if (row['scope_group'], row['county_fips']) != (category, county): raise ValueError('Unsupported county classification')
            stored = con.execute('SELECT record_json FROM locations WHERE npi=? AND network_zip=?', key).fetchone()
            if not stored or json.loads(stored[0]) != row: raise ValueError('SQLite location differs from export')
            categories[category] += 1
            if category in ['identity_or_location_unresolved', 'Florida_county_unresolved']: exceptions.append(row)
    if seen != set(original): raise ValueError('Identity/location relation omitted')
    if exceptions != json.loads((package / 'exceptions.json').read_text()): raise ValueError('Exception list incomplete')
    names = json.loads((package / 'individual-registry-names.json').read_text())
    for r in names:
        source = r['source']; native = json.loads((ROOT / source['path']).read_text())['results'][source['result_index']]
        if r['npi'] != str(native['number']) or r['individual_name'] != {f:native.get('basic',{}).get(f) for f in ['first_name','middle_name','last_name','name_prefix','name_suffix']}:
            raise ValueError('Individual dispensing-provider name mismatch')
    checks.update({'all_Census_fields_and_county_GIS_decisions_source_checked': True,
                   'all_network_NPI_zip_pairs_preserved': len(seen)==66248,
                   'all_candidate_locations_and_county_classifications_recomputed': True,
                   'all_individual_registry_names_checked': len(names)==15,
                   'all_location_exceptions_retained': True})
    result = {'schema':'l07-independent-location-validation/1','passed':all(checks.values()),'checks':checks,
              'network_NPI_zip_pairs_checked':len(seen),'Florida_addresses_checked':len(inputs),
              'geography_source_field_observations_checked':source_observations,'county_GIS_decisions_checked':len(decisions),
              'scope_groups':dict(categories),'unexplained_field_mismatches':0,'manifest_sha256':sha(package/'manifest.json'),
              'limits':'Published listings plus dated registry/address geography. Unresolved national identities/locations remain gaps; no live operation or exact historical-address guarantee.'}
    output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,indent=2))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',type=Path,default=BASE/'location-build-r1')
    p.add_argument('--out',type=Path,default=BASE/'location-build-r1-validation.json');a=p.parse_args();validate(a.package.resolve(),a.out.resolve())
