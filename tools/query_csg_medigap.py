"""Read exact CSG export profiles offline; never substitute or release a price.

D124/D126/D127 pilot preparation. This stateless research lookup does not persist
participant inputs, contact CSG, apply underwriting, or activate the advisor.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from import_csg_medigap import VARIANTS


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_candidate(candidate):
    candidate = Path(candidate).resolve()
    manifest = json.loads((candidate / 'manifest.json').read_text())
    if manifest.get('schema') != 'csg-medigap-private-candidate/1':
        raise ValueError('Unsupported candidate schema')
    if manifest.get('consumer_release') != 'held':
        raise ValueError('This reader supports held research candidates only')
    expected = {'research.sqlite3', 'rates.jsonl', 'benefit-observations.json'}
    if set(manifest.get('files', {})) != expected:
        raise ValueError('Incomplete candidate manifest')
    for name, digest in manifest['files'].items():
        if sha256(candidate / name) != digest:
            raise ValueError(f'Candidate integrity failure: {name}')
    if manifest.get('source_count') != len(manifest.get('sources', [])):
        raise ValueError('Source count mismatch')
    for source in manifest['sources']:
        name = source['filename']
        if Path(name).name != name:
            raise ValueError('Invalid source filename')
        if sha256(candidate.parent / 'raw' / name) != source['sha256']:
            raise ValueError('Original source integrity failure')
    return candidate, manifest


def lookup(candidate, *, zipcode, age, gender, tobacco, effective_date, variant=None):
    if not isinstance(zipcode, str) or not re.fullmatch(r'\d{5}', zipcode):
        raise ValueError('An exact five-digit ZIP is required')
    if type(age) is not int or not 0 <= age <= 120:
        raise ValueError('An explicit integer age is required')
    if gender not in ('Female', 'Male') or tobacco not in ('Non-Tobacco', 'Tobacco User'):
        raise ValueError('Explicit source gender and tobacco categories are required')
    if not isinstance(effective_date, str) or not re.fullmatch(r'2026-\d{2}-\d{2}', effective_date):
        raise ValueError('An exact 2026 requested effective date is required')
    date.fromisoformat(effective_date)
    if variant is not None and variant not in VARIANTS:
        raise ValueError('Unknown source plan variant')
    candidate, manifest = verify_candidate(candidate)
    profile = {'zip': zipcode, 'age': age, 'gender': gender, 'tobacco': tobacco,
               'requested_effective_date': effective_date}
    result = {
        'schema': 'csg-exact-profile-lookup/1', 'profile': profile, 'variant': variant,
        'candidate_manifest_sha256': sha256(candidate / 'manifest.json'),
        'consumer_release': 'held', 'personal_quote': False,
        'eligibility': 'not_determined', 'all_market_complete': False,
        'holds': list(manifest['holds']), 'records': [], 'source_export_request': None,
        'meaning': 'Exact quote-input observations; no underwriting, class or discount eligibility decision',
    }
    if age >= 75:
        result.update(status='unsupported_pilot_age',
                      reason='Medigap pricing for ages 75+ is not supported in this pilot.',
                      insurance_eligibility='not_determined')
        return result
    if age < 65:
        result.update(status='unsupported_pilot_age',
                      reason='Medigap pricing in this pilot supports ages 65–74; under-65 pricing is not supported.',
                      insurance_eligibility='not_determined')
        return result
    matching_sources = [s for s in manifest['sources']
                        if all(s['scenario'].get(key) == value for key, value in profile.items())]
    if not matching_sources:
        result.update(status='needs_source_export',
                      reason='This exact profile/date has not been imported; this does not mean no plans are available',
                      source_export_request={
                          'page': 'https://tools.csgactuarial.com/medicare-supplement',
                          'profile': profile, 'client_label': '', 'household_discount': 'Not Applied',
                          'company_filter': 'none', 'health_condition_inputs': 'none',
                          'artifact': 'native XLSX export',
                          'instruction': 'Run the exact profile, verify the returned county and inputs, save the completed workbook, then build a new candidate',
                      })
        return result
    if len(matching_sources) != 1:
        raise ValueError('Conflicting source exports require reconciliation')
    sql = ('SELECT payload FROM rate_observations WHERE zip=? AND age=? AND gender=? '
           'AND tobacco=? AND requested_date=?')
    params = [zipcode, age, gender, tobacco, effective_date]
    if variant is not None:
        sql += ' AND variant=?'
        params.append(variant)
    sql += ' ORDER BY variant,naic,id'
    with closing(sqlite3.connect((candidate / 'research.sqlite3').as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('PRAGMA query_only=ON')
        records = [json.loads(row[0]) for row in db.execute(sql, params)]
    source_hash = matching_sources[0]['sha256']
    for record in records:
        if record['source_sha256'] != source_hash or any(record['scenario'].get(k) != v for k, v in profile.items()):
            raise ValueError('Stored record does not match the exact requested source profile')
        if record.get('consumer_release') != 'held' or record.get('personal_quote') is not False:
            raise ValueError('Unexpected record authority')
    result.update(status='matched_source_observations' if records else 'no_rows_in_source_export',
                  source_sha256=source_hash, records=records,
                  returned_rows=len(records))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--zip', required=True, dest='zipcode')
    parser.add_argument('--age', required=True, type=int)
    parser.add_argument('--gender', required=True, choices=['F', 'M'])
    parser.add_argument('--tobacco', required=True, choices=['NT', 'T'])
    parser.add_argument('--effective-date', required=True)
    parser.add_argument('--plan', choices=VARIANTS, dest='variant')
    args = vars(parser.parse_args())
    args['gender'] = {'F': 'Female', 'M': 'Male'}[args['gender']]
    args['tobacco'] = {'NT': 'Non-Tobacco', 'T': 'Tobacco User'}[args['tobacco']]
    print(json.dumps(lookup(**args), indent=2))


if __name__ == '__main__':
    main()
