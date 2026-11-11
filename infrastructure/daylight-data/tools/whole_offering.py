#!/usr/bin/env python3
"""Prepare exact H5652-002 sources without closing any semantic obligation.

Offline census and source audit come first. Optional native hydration calls only
the frozen guarded SELECT-only API, in sequential batches of at most 100 IDs.
No source expansion, acquisition, acceptance, profile or database mutation.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import zipfile

from comparison_pilot import (ARCHIVE, BASE, EOC, MEMBER_SHA, OFFERING, SB,
                              canonical, digest, file_sha, load, source_projection, verify_inputs)

VERSION = 'l03-whole-offering-source-preparation/1'
EXPECTED_GLOBAL = {'claim': 143505, 'condition': 249065}
EXPECTED_OFFERING = {'claim': 1778, 'condition': 2897}
EXPECTED_DIGEST = '7010f371467e1ddc0ea8ab58af2d9d26a04803c844ae0829a8c271da1acd5cee'
R10 = Path('docs/data/l03-ma-benefits-2026-11-01-comparison-pilot-r10')
DOCS = {SB: 'SB', EOC: 'EOC'}
REQUIREMENT_SOURCE_IDS = frozenset('''32be6178df7b24b44dea7723ff35
4c879b3839c7e5a483d43325ef17
508cb642d33ce284c48f31b97931
6a29f663c05e96e14a3acd036487
72463e885a40f8b1ae6201faa8d6
7525136f0f09e24bc1eb841b8fbd
9222276fc8648b2d0ca4020850cb
aa1fffd9c3efe16221c9258806c9
abca5b0a2e40e6ae317a3d7fd20c
c0ea242144a4fa87f9a139b6229d
c3b7b24cebbe39e40ced201fd0af
db9dca89f33dae2fe55c6987b4bf
ef37deb99566018a746c09ea85e5
f3233f44796e645743bf99d0f91d
f596d94904eac3e57b174a80f053
ff2bb4f072be4ad919bba031686f'''.split())
REQUIREMENT_SOURCE_IDS = frozenset('SOURCE_REQUIREMENT-' + value for value in REQUIREMENT_SOURCE_IDS)
REQUIREMENT_QUERY = '''SELECT r.*,d.snapshot_id,d.adapter_code_sha256,s.original_path,s.artifact_sha256,
 s.source_use_state AS snapshot_source_use_state
 FROM dl_evidence.source_record r JOIN dl_control.derivation d USING(derivation_id)
 JOIN dl_control.source_snapshot s USING(snapshot_id)
 WHERE r.derivation_id=%s AND r.source_table=%s AND r.raw_payload->>'source_id'=ANY(%s)
 AND r.source_row_ordinal>%s ORDER BY r.source_row_ordinal LIMIT 101'''


class WholeOfferingError(ValueError):
    pass


def write_new(path, value, *, compressed=False, raw=False):
    """Exclusive, private, deterministic artifacts; partial outputs are retained."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    body = value if raw else (canonical(value) + '\n').encode()
    if compressed:
        body = gzip.compress(body, compresslevel=1, mtime=0)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
        stream.write(body); stream.flush(); os.fsync(stream.fileno())
    return {'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body)}


def source_group(row):
    detail = row['detail']
    if 'required_evidence_missing' in row['states']:
        return 'required_evidence_missing'
    if detail.get('source_basis') == 'carrier_only_blind_to_CMS_expected_amounts':
        return 'carrier_assertion_or_predicate'
    if detail.get('source_semantics') == 'official_CMS_question_and_codes':
        return 'CMS_official_coded_predicate'
    return detail.get('source_basis', 'source_basis_requires_native_inspection')


def census(records, *, expected_digest=EXPECTED_DIGEST, enforce_counts=True):
    hasher = hashlib.sha256(b'[')
    counts, states, offering_states = Counter(), Counter(), Counter()
    selected, previous = [], None
    for ordinal, row in enumerate(records):
        if previous is not None and row['id'] <= previous:
            raise WholeOfferingError('Canonical IDs duplicated or reordered')
        if row['kind'] not in {'claim', 'condition'} or row['accepted_for_reference'] is not False:
            raise WholeOfferingError('Canonical kind/acceptance changed')
        if ordinal:
            hasher.update(b',')
        hasher.update(canonical(row).encode()); previous = row['id']
        counts[row['kind']] += 1; states.update(row['states'])
        if row['offering_id'] == OFFERING:
            selected.append(row); offering_states.update(row['states'])
    hasher.update(b']')
    if hasher.hexdigest() != expected_digest:
        raise WholeOfferingError('Global canonical digest changed')
    offering = Counter(row['kind'] for row in selected)
    missing = sorted(row['id'] for row in selected if 'required_evidence_missing' in row['states'])
    if enforce_counts and (dict(counts) != EXPECTED_GLOBAL or dict(offering) != EXPECTED_OFFERING
                           or len(missing) != 16 or offering_states != Counter({
                               'evidence_reconciliation_pending': 4659, 'required_evidence_missing': 16})):
        raise WholeOfferingError('Frozen global/offering denominator or state counts changed')
    groups = defaultdict(Counter)
    sections = defaultdict(Counter)
    for row in selected:
        groups[source_group(row)][row['kind']] += 1
        sections[row['context'].get('source_section') or row['subject']][row['kind']] += 1
    native_ids = {key: sorted({identifier for row in selected for identifier in row[key]})
                  for key in ('representation_ids', 'observation_ids', 'source_ids')}
    return selected, {'global_required': dict(counts), 'global_states': dict(states),
        'inventory_digest': hasher.hexdigest(), 'offering_required': dict(offering),
        'offering_states': dict(offering_states), 'missing_ids': missing,
        'native_id_counts': {key: len(value) for key, value in native_ids.items()},
        'source_groups': {key: dict(value) for key, value in sorted(groups.items())},
        'source_sections_or_subjects': {key: dict(value) for key, value in sorted(sections.items())},
        'new_fully_supported': 0, 'new_awaiting_review': 0, 'new_accepted': 0,
        'whole_offering_pilot_complete': False, 'source_hydration_is_semantic_verification': False}, native_ids


def read_carrier_pages(repository):
    path = repository / BASE / 'source-reconciliation-r7/new-source-pages.jsonl.gz'
    pages, seen, counts = [], set(), Counter()
    with gzip.open(path, 'rt') as stream:
        for ordinal, line in enumerate(stream, 1):
            row = json.loads(line)
            if row['document_sha256'] not in DOCS:
                continue
            key = row['document_sha256'], row['pdf_page']
            if key in seen:
                raise WholeOfferingError('Duplicate carrier source page')
            seen.add(key); counts[DOCS[key[0]]] += 1
            for field in ('text', 'layout_text'):
                if hashlib.sha256(row[field].encode()).hexdigest() != row[field + '_sha256']:
                    raise WholeOfferingError('Carrier source text/layout hash mismatch')
            pages.append({**{key: value for key, value in row.items() if key != 'ocr_words'},
                'retained_source_row_ordinal': ordinal, 'retained_source_row_sha256': digest(row),
                'ocr_words_retained_in_original_only': True,
                'ocr_words_sha256': digest(row.get('ocr_words')),
                'pixel_checked_by_this_producer': False,
                'extraction_equals_printed_semantics': False})
    if counts != Counter({'SB': 13, 'EOC': 193}):
        raise WholeOfferingError('Complete matched SB/EOC page population changed')
    return pages, dict(counts)


def read_cms(repository):
    path = repository / 'docs/data/l02-ma-availability-2026-10-25/acquisition-r1/raw' / ARCHIVE
    with zipfile.ZipFile(path) as archive:
        member = archive.read('H5652-002-000-2026.json')
    if hashlib.sha256(member).hexdigest() != MEMBER_SHA:
        raise WholeOfferingError('Exact CMS member changed')
    document = json.loads(member)
    plan = document['pbp'][0]
    if (document['contractYear'] != 2026 or plan['contractId'] != 'H5652'
            or plan['planId'] != '002' or plan['segmentId'] != 0):
        raise WholeOfferingError('CMS exact offering identity mismatch')
    services = plan['benefitDetails']['benefitDetailsInfo']
    if len(services) != 93:
        raise WholeOfferingError('CMS full native service population changed')
    index = [{'service_id': OFFERING + ':benefitDetails:' + str(i),
        'category_code': row['categoryCode'], 'category_type_id': row['categoryTypeId'],
        'pointer': '/pbp/0/benefitDetails/benefitDetailsInfo/' + str(i),
        'source_object_sha256': digest(row), 'source_components': sorted(row['benefitDetails'])}
        for i, row in enumerate(services)]
    return member, plan, index


def inpatient_scope(rows, cms_index):
    """Preparation candidates only; same family is never an equivalence mapping."""
    services = {row['service_id'] for row in cms_index if row['category_code'] in {'1a', '1a1'}}
    chosen = {row['id'] for row in rows if (set(row['context'].get('service_ids', [])) & services
              or row['subject'] == 'Published service family: inpatient')}
    propositions = {row['context'].get('complete_source_proposition_scope')
                    for row in rows if row['id'] in chosen} - {None}
    chosen.update(row['id'] for row in rows
                  if row['context'].get('complete_source_proposition_scope') in propositions)
    return {'canonical_ids': sorted(chosen), 'CMS_service_ids': sorted(services),
        'counts': dict(Counter(row['kind'] for row in rows if row['id'] in chosen)),
        'selection': 'complete CMS 1a/1a1 schedules and controls plus whole frozen inpatient-family proposition sibling groups',
        'cross_source_equivalence': 'not_established', 'printed_scope_interpretation': 'requires_pixel_and_independent_review',
        'full_meaning_outcome': 'insufficient_evidence', 'accepted_for_reference': False,
        'required_context': ['all day bands and later days', 'day versus admission/stay basis',
            'authorization and referral', 'network/POS and stabilized emergency exception',
            'admission and transfer reset', 'hospital benefit-period applicability',
            'Medicare-covered-day qualification', 'QMB/full-Medicaid qualification',
            'selective annual deductible', 'out-of-pocket maximum',
            'transplant network and lodging/transport exceptions',
            'psychiatric/general-hospital subtype boundary'],
        'source_text_discrepancy': 'Original PDF text extraction is reported to shift characters. Retained OCR/native text is locator support, not printed semantic truth.'}


def select_jsonl(repository, relative):
    result = []
    with gzip.open(repository / relative, 'rt') as stream:
        for line in stream:
            if OFFERING not in line:
                continue
            row = json.loads(line)
            if row.get('offering_id') == OFFERING:
                result.append(row)
    return result


def build_offline(repository):
    bindings = verify_inputs(repository)
    freeze = load(repository / BASE / 'semantic-inventory-r9/freeze.json')
    inputs = load(repository / BASE / 'semantic-inventory-r9/inputs.json')
    for name in ('service-reconciliation.jsonl.gz', 'field-dispositions.jsonl.gz'):
        relative = BASE / 'source-reconciliation-r7' / name
        expected = inputs[str(relative)]
        if file_sha(repository / relative) != expected:
            raise WholeOfferingError('Frozen r7 source ledger changed')
        bindings.append({'path': str(relative), 'sha256': expected,
                         'bytes': (repository / relative).stat().st_size})
    path = repository / BASE / 'semantic-inventory-r9/master-inventory.jsonl.gz'
    with gzip.open(path, 'rt') as stream:
        rows, audit, ids = census(json.loads(line) for line in stream)
    prior = load(repository / R10 / 'pilot-spec.json')['selected_canonical_ids']
    if len(prior) != 71 or not set(prior) <= {row['id'] for row in rows}:
        raise WholeOfferingError('Prior prepared tranche not preserved')
    member, plan, cms_index = read_cms(repository)
    pages, counts = read_carrier_pages(repository)
    services = select_jsonl(repository, BASE / 'source-reconciliation-r7/service-reconciliation.jsonl.gz')
    fields = select_jsonl(repository, BASE / 'source-reconciliation-r7/field-dispositions.jsonl.gz')
    if len(services) != 93:
        raise WholeOfferingError('Retained r7 full source service population changed')
    audit.update(carrier_pages=counts, CMS_native_service_records=len(cms_index),
                 retained_r7_service_records=len(services), retained_r7_field_dispositions=len(fields),
                 prior_prepared_ids=prior, canonical_ids_outside_r10=len(rows)-len(prior),
                 accepted_r4_entries_unchanged=535, independent_source_review_complete=False)
    missing = [row for row in rows if row['id'] in audit['missing_ids']]
    outputs = {'source-audit.json': audit, 'input-bindings.json': bindings,
        'native-id-request.json': {'offering_id': OFFERING, **ids},
        'CMS-service-index.json': cms_index, 'inpatient-scope.json': inpatient_scope(rows, cms_index),
        'required-missing-evidence.json': missing}
    blobs = {'offering-canonical.jsonl.gz': b''.join((canonical(row)+'\n').encode() for row in rows),
        'carrier-pages.jsonl.gz': b''.join((canonical(row)+'\n').encode() for row in pages),
        'retained-service-records.jsonl.gz': b''.join((canonical(row)+'\n').encode() for row in services),
        'retained-field-dispositions.jsonl.gz': b''.join((canonical(row)+'\n').encode() for row in fields),
        'CMS-native-member.json': member}
    return outputs, blobs, rows, ids, freeze['files_sha256']['inventory.sqlite3.gz']


def chunks(values):
    for start in range(0, len(values), 100):
        yield values[start:start+100]


def json_safe(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: json_safe(child) for key,child in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(child) for child in value]
    return value


def requirement_lookup(native, requested, *, allowed, offering_id=OFFERING):
    """Exact retained missing-requirement metadata; this is not new evidence.

    The frozen API's original prefix list predates SOURCE_REQUIREMENT IDs. This
    additive query keeps its physical/source/job/READ ONLY role guard intact.
    """
    if (offering_id != OFFERING or set(allowed) != REQUIREMENT_SOURCE_IDS
            or type(requested) is not list or not 1 <= len(requested) <= 100
            or len(set(requested)) != len(requested) or not set(requested) <= REQUIREMENT_SOURCE_IDS):
        raise WholeOfferingError('Exact frozen missing-requirement IDs required')
    selected = native.binding.selections['native_sources']
    params = [selected['derivation_id'], selected['source_table'], requested, 0]
    with native._read() as (connection, access):
        records = connection.execute(REQUIREMENT_QUERY, params).fetchall()
        if len(records) > 100:
            raise WholeOfferingError('Requirement metadata row bound exceeded')
        result = native._envelope(access)
        result.update(lookup_kind='native_sources', requested_ids=requested, records=json_safe(records),
            has_more=False, next_after_ordinal=None, source_query=REQUIREMENT_QUERY,
            query_parameters=params, operator_only=True, condition_semantics_verified=False,
            requirement_metadata_only=True, required_evidence_still_missing=True)
        return result


def hydrate(repository, output, ids, expected_source_sha, *, native=None, canonical_rows=None):
    if native is None:
        sys.path.insert(0, str(repository / 'infrastructure/daylight-data/src'))
        from daylight_data.serving.native_lineage import native_repository_from_env
        native = native_repository_from_env(repository_root=repository, timeout_ms=30000)
    snapshot = None
    receipt = {'schema': VERSION, 'offering_id': OFFERING, 'batches': [], 'unique_counts': {},
        'source_or_database_mutated': False, 'new_acceptance': False,
        'semantic_verification': False, 'independent_source_review_complete': False}
    clause_ids, edges = set(), set()
    canonical_links = defaultdict(list)
    for row in canonical_rows or []:
        for identifier in row['observation_ids']:
            canonical_links[identifier].append((set(row['representation_ids']), set(row['source_ids'])))
    requirements = {i for row in canonical_rows or [] if 'required_evidence_missing' in row['states']
                    for i in row['source_ids'] if i.startswith('SOURCE_REQUIREMENT-')}
    if canonical_rows is not None and requirements != REQUIREMENT_SOURCE_IDS:
        raise WholeOfferingError('Whole-offering missing-requirement source links changed')
    for kind, requested in [('native_observations', ids['observation_ids']),
                            ('native_sources', ids['source_ids']),
                            ('native_relationships', ids['representation_ids']),
                            ('native_clauses', clause_ids)]:
        seen = set()
        batches = list(chunks(sorted(requested)))
        if kind == 'native_sources' and requirements:
            batches = list(chunks(sorted(set(requested)-requirements))) + list(chunks(sorted(requirements)))
        for batch_ordinal, batch in enumerate(batches, 1):
            after, present, page_ordinal = 0, set(), 0
            while True:
                started = time.perf_counter()
                page = (requirement_lookup(native, batch, allowed=requirements)
                        if kind == 'native_sources' and set(batch) <= requirements
                        else native.lookup(kind, batch, after_ordinal=after))
                elapsed = round((time.perf_counter()-started)*1000, 3)
                if snapshot is None:
                    snapshot = page['binding']['snapshot_id']
                if (page['binding']['snapshot_id'] != snapshot or page['new_acceptance']
                        or page['binding']['accepted_release_id'] is not None
                        or any(value['state'] != 'held' for value in page['authority'].values())):
                    raise WholeOfferingError('Mixed native snapshot or authority promotion')
                for record in page['records']:
                    raw = record['raw_payload']
                    if (record['artifact_sha256'] != expected_source_sha
                            or record['original_path'] != str(BASE / 'semantic-inventory-r9/inventory.sqlite3.gz')
                            or hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(',', ':'),
                                ensure_ascii=False).encode()).hexdigest() != record['raw_sha256']):
                        raise WholeOfferingError('Native artifact/raw payload binding changed')
                    if kind == 'native_relationships':
                        key = (raw['parent_id'], raw['child_id'], raw['relation'], raw['source_id'])
                        if not ({raw['parent_id'],raw['child_id']} & set(batch)):
                            raise WholeOfferingError('Unrequested native relationship')
                        edges.add(key); seen.add(key)
                    else:
                        key = raw['source_id'] if kind == 'native_sources' else raw['id']
                        if key not in batch:
                            raise WholeOfferingError('Unrequested native ID')
                        present.add(key); seen.add(key)
                        if kind == 'native_observations' and canonical_rows is not None and not any(
                                raw.get('unit_id') in representations and raw.get('source_id') in sources
                                for representations,sources in canonical_links[key]):
                            raise WholeOfferingError('Canonical/native representation or source link changed')
                        if kind == 'native_observations' and raw['layer'] == 'carrier_clause':
                            clause_ids.add(json.loads(raw['payload'])['clause_id'])
                page_ordinal += 1
                name = f'native/{kind}/batch-{batch_ordinal:04d}-page-{page_ordinal:02d}.json.gz'
                artifact = write_new(output / name, page, compressed=True)
                receipt['batches'].append({'path': name, **artifact, 'kind': kind,
                    'requested_ids': batch, 'records': len(page['records']), 'elapsed_ms': elapsed,
                    'has_more': page['has_more'], 'source_query': page['source_query'],
                    'query_parameters': page['query_parameters']})
                if not page['has_more']:
                    break
                following = page['next_after_ordinal']
                if type(following) is not int or following <= after or page_ordinal >= 50:
                    raise WholeOfferingError('Native paging failed to advance or exceeded explicit bound')
                after = following
            if kind != 'native_relationships' and present != set(batch):
                raise WholeOfferingError('Referenced native IDs missing: ' + ','.join(sorted(set(batch)-present)))
            if batch_ordinal % 10 == 0:
                print(json.dumps({'progress': kind, 'batches': batch_ordinal, 'unique_rows': len(seen)}), flush=True)
        receipt['unique_counts'][kind] = len(seen)
        print(json.dumps({'complete_transport_only': kind, 'unique_rows': len(seen)}), flush=True)
    receipt['relationship_endpoints_outside_offering'] = sorted({i for edge in edges for i in edge[:2]} - set(ids['representation_ids']))
    receipt['clause_ids'] = sorted(clause_ids)
    receipt['snapshot_id'] = snapshot
    receipt['canonical_observation_links_verified'] = len(canonical_links) if canonical_rows is not None else None
    receipt['retained_missing_requirement_metadata_rows'] = len(requirements)
    receipt['missing_evidence_predicates_closed'] = 0
    receipt['all_referenced_native_ids_hydrated'] = True
    write_new(output / 'NATIVE_LOOKUP_RECEIPT.json', receipt)
    return receipt


def inpatient_components(document, producer, fresh):
    """Named component checks only; complete source meaning remains unresolved."""
    plan = document['pbp'][0]
    if (document['contractYear'] != 2026 or plan['contractId'] != 'H5652'
            or plan['planId'] != '002' or plan['segmentId'] != 0
            or producer['offering_id'] != OFFERING or fresh['offering']['offering_id'] != OFFERING
            or fresh['offering']['year'] != 2026):
        raise WholeOfferingError('Wrong exact inpatient identity/year')
    source = {row['id']: row for row in producer['observations']}
    expected = {row['id']: row for row in fresh['observations']}
    services = {row['categoryCode']: row['benefitDetails']
                for row in plan['benefitDetails']['benefitDetailsInfo'] if row['categoryCode'] in {'1a','1a1'}}
    if set(services) != {'1a','1a1'}:
        raise WholeOfferingError('Complete acute/additional-day source components required')
    checks = []
    def decimal(value):
        if type(value) is not str:
            raise WholeOfferingError('String source decimal required')
        try:
            number = Decimal(value)
        except InvalidOperation:
            raise WholeOfferingError('Invalid source decimal') from None
        if not number.is_finite():
            raise WholeOfferingError('Nonfinite source decimal')
        return number
    for native_id, expected_id in [('producer:sb-inpatient-row','SB-INPATIENT-IN'),
                                   ('producer:eoc-in-network-schedule','EOC-INPATIENT-IN')]:
        native_bands = source[native_id]['typed']['in_network_bands']
        exp = expected[expected_id]
        if (exp['network'] != 'in-network' or exp['structure']['unit'] != 'per day'
                or exp['structure']['currency'] != 'USD' or len(native_bands) != 2
                or len(exp['structure']['bands']) != 2
                or any(band['basis'] != 'per_day' or band['currency'] != 'USD' for band in native_bands)):
            raise WholeOfferingError('Wrong network/unit or incomplete source band set')
        aligned = [decimal(a['amount']) == decimal(b['amount'])
                   and a['begin_day'] == b['day_start'] and a['end_day'] == b['day_end']
                   for a,b in zip(native_bands, exp['structure']['bands'])]
        checks.append({'check':'initial_producer_vs_fresh_carrier_components',
            'producer_observation':native_id,'fresh_observation':expected_id,
            'amount_start_end_components_equal':all(aligned),
            'qualifications_and_source_wording_retained':{'producer':source[native_id],'fresh':exp},
            'complete_meaning_equivalence':False})
    tier = services['1a']['TierCopaymentComponent']
    bands = tier['bdCopaymentTier1DayIntervalStay']
    sb = source['producer:sb-inpatient-row']['typed']
    first, following = sb['in_network_bands']
    checks.extend([
        {'check':'CMS_first_day_band','decimal_amount_equal':decimal(bands['bdDayInterval1CopaymentAmount'])==decimal(first['amount']),
         'begin_end_equal':(bands['bdDayInterval1BeginDay'],bands['bdDayInterval1EndDay'])==(str(first['begin_day']),str(first['end_day'])),
         'scope':'named INN day-band components only'},
        {'check':'CMS_second_band_amount_and_start','decimal_amount_equal':decimal(bands['bdDayInterval2CopaymentAmount'])==decimal(following['amount']),
         'begin_equal':bands['bdDayInterval2BeginDay']==str(following['begin_day']),
         'end_meaning_equivalence':False},
    ])
    for native_id, expected_id in [('producer:sb-inpatient-row','SB-INPATIENT-OUT'),
                                   ('producer:eoc-out-of-network-schedule','EOC-INPATIENT-OUT')]:
        value=source[native_id]['typed']['out_of_network']; exp=expected[expected_id]
        if value['unit']!='percent' or value['basis']!='per_stay' or exp['network']!='out-of-network' or exp['structure']['unit']!='percent':
            raise WholeOfferingError('Wrong OON percent/stay basis')
        checks.append({'check':'OON_nominal_percentage_component','producer_observation':native_id,
            'fresh_observation':expected_id,'decimal_amount_equal':decimal(value['amount'])==decimal(exp['structure']['amount'])
                ==decimal(services['1a']['CostShareABPOSComponent']['bdCoinsAmt']),
            'complete_meaning_equivalence':False,'rate_basis_and_coverage_predicates_require_review':True})
    extra=services['1a1']['AdditionalDays1a1Component']
    return {'checks':checks,'complete_native_1a':services['1a'],'complete_native_1a1':services['1a1'],
        'later_days_control_review':{
            'acute_second_band_end_raw':bands['bdDayInterval2EndDay'],
            'additional_day_band_raw':extra['bdTierCopayment']['bdCopaymentTier1DayIntervalStay'],
            'unlimited_additional_days_raw':extra['bdUnlimitedAdditionalDays'],
            'carrier_open_end_literals':['and beyond','additional Medicare-covered days','unlimited days subject to plan rules'],
            'source_codes_not_converted_to_personal_cap_or_infinity':True,
            'reviewed_CMS_carrier_mapping':None,'outcome':'interpretation_required'},
        'other_native_controls_retained':{'period':services['1a']['InpatientHospitalAcuteBenefitPeriodComponent'],
            'authorization_referral':services['1a']['PriorAuthorizationReferralNmBenefitComponent'],
            'inactive_or_control_qualified_flat_tier_amount':{key:tier[key] for key in
                ('bdCopaymentAmountYesNo','bdCopaymentTier1YesNo','bdCopaymentTier1Amt')}},
        'full_meaning_outcome':'insufficient_evidence','source_interpretation_review_complete':False,
        'new_fully_supported':0,'new_awaiting_review':0,'new_accepted':0}


def derive_inpatient(repository, captured, producer_path, fresh_path, output):
    preparation=load(captured/'PREPARATION_RECEIPT.json')
    for name,artifact in preparation['artifacts'].items():
        if file_sha(captured/name)!=artifact['sha256']:
            raise WholeOfferingError('Captured offline artifact changed')
    if file_sha(producer_path)!='cd1aac9fb93ca88a45b6be3bc2d5cdedc80a0070166b3ec9a11758255c3f6319':
        raise WholeOfferingError('Initial producer transcription changed')
    if file_sha(fresh_path)!='7c460f9641b542bd938a272c8e595f15910529cc8621de8e77a2469bd021eeb8':
        raise WholeOfferingError('Frozen fresh candidate changed')
    rows=[json.loads(line) for line in gzip.open(captured/'offering-canonical.jsonl.gz','rt')]
    pages={(p['document_sha256'],p['pdf_page']):p for p in
           (json.loads(line)for line in gzip.open(captured/'carrier-pages.jsonl.gz','rt'))}
    scope=load(captured/'inpatient-scope.json'); chosen=set(scope['canonical_ids'])
    selected=[row for row in rows if row['id'] in chosen]
    obs_ids={i for row in selected for i in row['observation_ids']}
    representations={i for row in selected for i in row['representation_ids']}
    receipt=load(captured/'NATIVE_LOOKUP_RECEIPT.json'); native=defaultdict(dict)
    for batch in receipt['batches']:
        path=captured/batch['path']
        if file_sha(path)!=batch['sha256']:
            raise WholeOfferingError('Captured native batch changed')
        for record in load_gzip(path)['records']:
            raw=record['raw_payload']; kind=batch['kind']
            key=((raw['parent_id'],raw['child_id'],raw['relation'],raw['source_id']) if kind=='native_relationships'
                 else raw['source_id'] if kind=='native_sources' else raw['id'])
            if key in native[kind] and native[kind][key]!=raw:
                raise WholeOfferingError('Native repeated ID changed')
            native[kind][key]=raw
    clauses={identifier:json.loads(row['payload'])for identifier,row in native['native_clauses'].items()}
    reconstructed=0
    import re
    for clause in clauses.values():
        for field,text in [('source_fragments',clause['quote']),('parent_source_fragments',clause['parent_sentence'])]:
            if source_projection(clause[field],pages)!=re.sub(r'\s+',' ',text).strip():
                raise WholeOfferingError('Native quotation/logical parent does not reconstruct')
        reconstructed+=1
    selected_observations=[native['native_observations'][identifier]for identifier in sorted(obs_ids)]
    clause_ids={json.loads(row['payload'])['clause_id']for row in selected_observations if row['layer']=='carrier_clause'}
    selected_clauses={identifier:clauses[identifier]for identifier in sorted(clause_ids)}
    if any(not set(clause['required_unit_ids'])<=representations for clause in selected_clauses.values()):
        raise WholeOfferingError('Selected inpatient clause sibling omitted')
    edges=[raw for key,raw in sorted(native['native_relationships'].items())
           if {key[0],key[1]}&representations]
    if any(not {row['parent_id'],row['child_id']}<=representations for row in edges):
        raise WholeOfferingError('Inpatient relationship endpoint omitted')
    producer,fresh=load(producer_path),load(fresh_path)
    components=inpatient_components(load(captured/'CMS-native-member.json'),producer,fresh)
    producer_map={'IP-FORMAL-ORDER':'producer:eoc-inpatient-definition','IP-OBSERVATION':'producer:inpatient-versus-observation',
        'IP-RESET':'producer:eoc-out-of-network-schedule','IP-TRANSFER':'producer:admission-transfer-reset-and-covered-days',
        'IP-UNLIMITED':'producer:admission-transfer-reset-and-covered-days','IP-MOOP':'producer:eoc-in-network-schedule',
        'IP-POSTSTABLE-AUTHORIZED':'producer:authorized-stabilized-emergency-exception','ASSIST-FOOTNOTE':'producer:QMB-full-Medicaid-footer',
        'IP-TRANSPLANT-TYPES':'producer:transplant-network-and-review','IP-TRANSPLANT-NETWORK':'producer:transplant-network-and-review',
        'IP-TRANSPLANT-REVIEW':'producer:transplant-network-and-review','IP-TRANSPLANT-LOCAL':'producer:transplant-community-pattern-exception',
        'IP-TRANSPLANT-DISTANT':'producer:transplant-community-pattern-exception','CTX-PRIORAUTH-IN':'producer:eoc-double-dagger-general-rules'}
    conditions=[{'fresh_condition':row,'initial_producer_observation':producer_map.get(row['id']),
        'alignment_state':'candidate_scope_mapping_unreviewed' if row['id']in producer_map else 'not_compared_to_initial_inpatient_transcription',
        'complete_meaning_outcome':'insufficient_evidence','accepted_for_reference':False}
        for row in fresh['condition_candidates']]
    dictionary=load(repository/BASE/'build-r1/field-dictionary.json')
    definitions=[row for row in dictionary['fields']if row['file'].lower()=='pbp_b1a_inpat_hosp']
    layers=Counter()
    unclassified=Counter()
    for row in rows:
        row_layers=tuple(sorted({native['native_observations'][i]['layer']for i in row['observation_ids']}))
        layers[str(row_layers)]+=1
        if source_group(row)=='source_basis_requires_native_inspection':unclassified[str(row_layers)]+=1
    artifacts={}
    for name,value in {'component-comparison.json':components,'condition-alignment.json':conditions,
        'fresh-required-gaps.json':fresh['required_gaps'],'inpatient-canonical.json':selected,
        'inpatient-native-observations.json':selected_observations,'inpatient-native-clauses.json':selected_clauses,
        'inpatient-native-relationships.json':edges,
        'CMS-inpatient-dictionary-context.json':{'source':dictionary['source'],'member':dictionary['member'],
            'sha256':dictionary['sha256'],'fields':definitions,'factual_mapping_reviewed':False},
        'native-source-accounting.json':{'canonical_observation_layer_sets':dict(layers),
            'previous_226_unclassified_source_basis_native_layers':dict(unclassified),
            'native_source_scoped_row_counts':{kind:len(value)for kind,value in native.items()},
            'relationship_primary_key':['parent_id','child_id','relation','source_id'],
            'distinct_relationship_graph_edges':len({key[:3]for key in native['native_relationships']}),
            'all_native_clauses_reconstructed':reconstructed,'semantic_verification':False,
            'missing_evidence_predicates_closed':0}}.items():
        artifacts[name]=write_new(output/name,value)
    write_new(output/'DERIVATION_RECEIPT.json',{'schema':VERSION,'operator_sha256':file_sha(Path(__file__)),
        'capture_operator_sha256':preparation['operator_sha256'],
        'capture_receipt_sha256':file_sha(captured/'PREPARATION_RECEIPT.json'),
        'native_receipt_sha256':file_sha(captured/'NATIVE_LOOKUP_RECEIPT.json'),
        'producer_initial_sha256':file_sha(producer_path),'fresh_candidate_sha256':file_sha(fresh_path),
        'artifacts':artifacts,'selected_canonical_count':len(selected),'new_accepted':0,
        'full_meaning_outcome':'insufficient_evidence','whole_offering_pilot_complete':False})
    return artifacts


def load_gzip(path):
    with gzip.open(path,'rt')as stream:return json.load(stream)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--hydrate-native', action='store_true')
    parser.add_argument('--derive-inpatient-from', type=Path)
    parser.add_argument('--producer-transcription', type=Path)
    parser.add_argument('--fresh-expected', type=Path)
    args = parser.parse_args()
    repository, output = args.repository.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    started = time.perf_counter()
    try:
        if args.derive_inpatient_from:
            if args.hydrate_native or not args.producer_transcription or not args.fresh_expected:
                raise WholeOfferingError('Separate frozen transcription/expected inputs required; no DB in derivation mode')
            derive_inpatient(repository,args.derive_inpatient_from,args.producer_transcription,args.fresh_expected,output)
            print(json.dumps({'complete':'inpatient_component_preparation_only','full_meaning_outcome':'insufficient_evidence'}))
            return
        objects, blobs, rows, ids, source_sha = build_offline(repository)
        artifacts = {name: write_new(output/name, value) for name,value in objects.items()}
        artifacts.update({name: write_new(output/name, body, compressed=name.endswith('.gz'), raw=True)
                          for name,body in blobs.items()})
        print(json.dumps({'offline': 'complete_source_accounting_only',
                          'required': objects['source-audit.json']['offering_required'],
                          'native_ids': objects['source-audit.json']['native_id_counts']}), flush=True)
        native = hydrate(repository, output, ids, source_sha, canonical_rows=rows) if args.hydrate_native else None
        for binding in objects['input-bindings.json']:
            if file_sha(repository / binding['path']) != binding['sha256']:
                raise WholeOfferingError('Source changed during preparation')
        write_new(output/'PREPARATION_RECEIPT.json', {'schema': VERSION,
            'offering_id': OFFERING, 'operator_sha256': file_sha(Path(__file__)),
            'artifacts': artifacts, 'elapsed_seconds': round(time.perf_counter()-started,3),
            'native_unique_counts': native['unique_counts'] if native else None,
            'semantic_verification': False, 'new_acceptance': False,
            'whole_offering_pilot_complete': False, 'independent_source_review_complete': False})
        print(json.dumps({'complete': 'source_preparation_only', 'elapsed_seconds': round(time.perf_counter()-started,3)}))
    except BaseException as error:
        write_new(output/'FAILED.json', {'state': 'incomplete', 'error_type': type(error).__name__,
            'source_or_database_mutated': False, 'new_acceptance': False,
            'semantic_verification': False})
        raise


if __name__ == '__main__':
    main()
