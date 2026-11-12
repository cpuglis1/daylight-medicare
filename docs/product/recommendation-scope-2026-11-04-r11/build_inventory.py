"""Rebuild the proposed dated Collier plan display and its review evidence."""

import argparse
from collections import Counter
import csv
import gzip
from hashlib import sha256
import io
import json
from pathlib import Path
import re
from zipfile import ZipFile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
L02 = ROOT / 'docs/data/l02-ma-availability-2026-10-25'
BUILD = L02 / 'build-r5'
COUNTY = BUILD / '12021'
L03 = ROOT / 'docs/data/l03-ma-benefits-2026-10-25/source-reconciliation-r7'
CATALOG = HERE.parent / 'recommendation-scope-2026-11-04-r5/catalog.json'

CONDITION_NAMES = {
    'CardiovascularDisorders': 'Cardiovascular disorders',
    'ChronicHeartFailure': 'Chronic heart failure',
    'DiabetesMellitus': 'Diabetes mellitus',
    'ChronicLungDisorders': 'Chronic lung disorders',
}
SNP_LABELS = {
    'Dual-Eligible': 'Dual Eligible Special Needs Plan',
    'Chronic or Disabling Condition': 'Chronic Condition Special Needs Plan',
    'Institutional': 'Institutional Special Needs Plan',
}
CONDITION_FIELD = 'Chronic or Disabling Condition SNP (C-SNP) Condition Type'


def digest(path):
    hashed = sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            hashed.update(chunk)
    return hashed.hexdigest()


def read_json(path):
    return json.loads(path.read_bytes())


def archive(source):
    path = L02 / 'acquisition-r1/raw' / source['sha256']
    if digest(path) != source['sha256']:
        raise ValueError(f'Source bytes changed for {source["id"]}')
    return path


def landscape_rows(source):
    result = {}
    with ZipFile(archive(source)) as zipped:
        member, = (item for item in source['members'] if item['name'].endswith('.csv'))
        raw = zipped.read(member['name'])
        if sha256(raw).hexdigest() != member['sha256']:
            raise ValueError('Landscape member changed')
        for ordinal, row in enumerate(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline='')), 2):
            if (row['State Territory Abbreviation'], row['County Name']) != ('FL', 'Collier'):
                continue
            if row['Contract Category Type'] not in {'MA', 'MA-PD', 'SNP'} or int(row['Plan ID']) >= 800:
                continue
            key = ':'.join((row['Contract Year'], row['Contract ID'], f"{int(row['Plan ID']):03d}",
                            f"{int(row['Segment ID']):03d}"))
            if key in result or not re.fullmatch(r'2026:[A-Z][0-9]{4}:[0-9]{3}:[0-9]{3}', key):
                raise ValueError(f'Unexpected or repeated Landscape identity {key}')
            locator = {'source': 'landscape', 'member': member['name'],
                       'member_sha256': member['sha256'], 'record_ordinal': ordinal}
            result[key] = (locator, row)
    return result


def erickson_evidence(offering_ids):
    docs = read_json(L03 / 'plan-document-matrix.json')
    wanted = {row['document_matches']['EOC']['sha256']: row['offering_id']
              for row in docs if row['offering_id'] in offering_ids}
    result = {}
    with gzip.open(L03 / 'new-source-pages.jsonl.gz', 'rt', encoding='utf-8') as stream:
        for page in map(json.loads, stream):
            oid = wanted.get(page['document_sha256'])
            if oid is None or page['pdf_page'] > 15:
                continue
            text = ' '.join(page['text'].split())
            if ('live in an Erickson Retirement Community' in text
                    and 'Section 2.2 Plan service area' in text and 'Florida: Collier;' in text):
                if oid in result:
                    raise ValueError(f'Multiple Erickson restriction passages for {oid}')
                document_hash = page['document_sha256']
                if (digest(L03 / 'acquisition/raw' / document_hash) != document_hash
                        or sha256(page['text'].encode()).hexdigest() != page['text_sha256']):
                    raise ValueError(f'Erickson document or page extract changed for {oid}')
                result[oid] = {key: page[key] for key in ('document_sha256', 'pdf_page', 'text_sha256')}
    if set(result) != set(offering_ids):
        raise ValueError('Erickson residence/service-area evidence incomplete')
    return result


def build():
    manifest = read_json(BUILD / 'build-manifest.json')
    source_manifest = BUILD / 'source-manifest.json'
    if digest(source_manifest) != manifest['source_manifest_sha256']:
        raise ValueError('L02 source manifest changed')
    for name in ('12021/offerings.json', '12021/source-differences.json', '12021/contract-only-observations.json'):
        if digest(BUILD / name) != manifest['outputs'][name]:
            raise ValueError(f'Frozen L02 output changed for {name}')
    sources = read_json(source_manifest)['sources']
    raw = landscape_rows(sources['landscape'])
    frozen = read_json(COUNTY / 'offerings.json')
    if len(raw) != 72 or sorted(raw) != [row['id'] for row in frozen]:
        raise ValueError('Raw scoped source and frozen 72-plan set differ')
    catalog = read_json(CATALOG)['plans']
    frozen_display = sorted((row['id'], row['name'], row['plan_type']) for row in frozen)
    catalog_display = sorted((row['offering_id'], row['name'],
                              row['published']['coverage']['value']['plan_type']) for row in catalog)
    if catalog_display != frozen_display:
        raise ValueError('Existing 72-plan catalog display identities differ')

    differences = read_json(COUNTY / 'source-differences.json')
    difference_by_id = {row['offering_id']: row for row in differences}
    residence = erickson_evidence([oid for oid in raw if oid.startswith('2026:H5652:')])
    plans = []
    with ZipFile(archive(sources['pbp'])) as pbp:
        for row in frozen:
            oid = row['id']
            locator, original = raw[oid]
            restrictions = json.loads(row['restriction_raw'])
            if (row['name'] != original['Plan Name']
                    or row['plan_type'] != original['Plan Type'] or row['category'] != original['Contract Category Type']
                    or row['drug'] != original['Part D Coverage Indicator']
                    or any(original[key] != value for key, value in restrictions.items())):
                raise ValueError(f'Published field or restriction differs from source for {oid}')

            year, contract, plan, segment = oid.split(':')
            member = f'{contract}-{plan}-{segment}-{year}.json'
            raw_member = pbp.read(member)
            package = json.loads(raw_member)
            pbp_plan, = package['pbp']
            profile = pbp_plan['planCharacteristics']
            identity = (str(package['contractYear']), pbp_plan['contractId'],
                        f"{int(pbp_plan['planId']):03d}", f"{int(pbp_plan['segmentId']):03d}")
            if (identity != (year, contract, plan, segment) or profile['planName'] != row['name']
                    or profile['isSnp'] != row['snp'] or row['snp'] == 'Yes' and profile['snpType'] != row['snp_type']
                    or profile['planDeleted'] != '0' or profile['planSegmentDeleted'] != '0'
                    or profile['isEmployerOnlyPlan'] != 'No'):
                raise ValueError(f'PBP identity, classification or controls differ for {oid}')
            if row['drug'] != profile['isOfferRx']:
                difference = difference_by_id.get(oid)
                if (difference is None or difference['field'] != 'Part D'
                        or (row['drug'], profile['isOfferRx']) != ('No', 'Not Applicable')):
                    raise ValueError(f'New PBP Part D difference for {oid}')
            elif oid in difference_by_id:
                raise ValueError(f'Stale Part D difference for {oid}')

            labels = []
            if row['snp'] == 'Yes':
                labels.append(SNP_LABELS[row['snp_type']])
            if row['snp_type'] == 'Institutional':
                labels.append(restrictions['SNP Institutional Type'])
            if row['snp_type'] == 'Chronic or Disabling Condition':
                labels.append('Published condition categories — ' + ', '.join(
                    CONDITION_NAMES[token] for token in restrictions[CONDITION_FIELD].split(',')))
            if oid in residence:
                labels.append('Residence in an Erickson Retirement Community required')
            plans.append({
                'display_candidate': {'offering_id': oid, 'name': row['name'], 'type': row['plan_type'],
                                      'published_restrictions': labels},
                'review_evidence': {'landscape': locator, 'restriction_source_fields': restrictions,
                    'pbp_member': member, 'pbp_member_sha256': sha256(raw_member).hexdigest(),
                    'erickson_pbp_geography_discrepancy': (
                        profile['geographicName'] if oid in residence else None),
                    'part_d_source_difference': difference_by_id.get(oid),
                    'residence_and_county_carrier_page': residence.get(oid)},
            })

    return {
        'schema': 'daylight-d91-published-inventory-review/1',
        'decision': 'pending', 'accepted_release_id': None,
        'proposed_purpose': 'published_inventory_display',
        'scope': {'year': 2026, 'county_fips': '12021', 'county': 'Collier County, Florida',
                  'landscape_data_date': '2026-09-02', 'observed_offerings': len(plans),
                  'expected_full_market_count': None, 'verified_availability_count': 0},
        'evidence_bindings': {
            'l02_build_manifest_sha256': digest(BUILD / 'build-manifest.json'),
            'l02_source_manifest_sha256': digest(source_manifest),
            'l02_offerings_sha256': digest(COUNTY / 'offerings.json'),
            'r5_catalog_sha256': digest(CATALOG),
            'landscape_zip_sha256': sources['landscape']['sha256'], 'pbp_zip_sha256': sources['pbp']['sha256'],
            'carrier_document_matrix_sha256': digest(L03 / 'plan-document-matrix.json'),
        },
        'counts': {'landscape_and_pbp_exact_identity_name_matches': len(plans),
                   'snp_classifications': dict(Counter(row['snp_type'] for row in frozen if row['snp'] == 'Yes')),
                   'erickson_restrictions': len(residence), 'retained_part_d_differences': len(differences),
                   'retained_contract_only_observations': len(read_json(COUNTY / 'contract-only-observations.json'))},
        'plans': plans,
    }


def render_rows(packet):
    lines = ['# Proposed 2026 Collier catalog rows', '', 'Dated September 2, 2026 CMS Landscape snapshot. Display review pending.', '',
             '| Exact offering ID | Published name | Published type | Proposed restriction wording |',
             '| --- | --- | --- | --- |']
    for row in packet['plans']:
        plan = row['display_candidate']
        values = [plan['offering_id'], plan['name'], plan['type'], ' / '.join(plan['published_restrictions']) or '—']
        lines.append('| ' + ' | '.join(v.replace('|', r'\|') for v in values) + ' |')
    lines += ['', 'A dash means no restriction label is proposed from the fields reviewed for this catalog. Qualification, availability and enrollment status remain unverified.', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    packet = build()
    outputs = {'display-candidate.json': json.dumps(packet, ensure_ascii=False, indent=2) + '\n',
               'CATALOG.md': render_rows(packet)}
    for name, data in outputs.items():
        path = HERE / name
        if args.check:
            if path.read_text(encoding='utf-8') != data:
                raise SystemExit(f'Replay differs for {name}')
        else:
            path.write_text(data, encoding='utf-8')
    print(json.dumps(packet['counts'], indent=2))
