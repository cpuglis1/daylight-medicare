#!/usr/bin/env python3
"""Independent source re-reader for the published 2026 cost schedules."""
import argparse
from collections import Counter
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def check_model(raw, modeled, table, benefit_type):
    if set(raw) != set(modeled):
        raise ValueError('Dropped or invented modeled source field')
    for name, source in raw.items():
        field = modeled[name]
        state = 'source_empty' if source == '' else ('source_blank' if source.isspace() else ('source_missing_token' if source == '.' else 'reported'))
        if field['raw'] != source or field['source_state'] != state:
            raise ValueError('Changed source field/state: ' + name)
        if state != 'reported':
            if field['value'] is not None:
                raise ValueError('Missing value turned into a numeric claim')
            if table == 'insulin' and name == 'TIER' and benefit_type == 'DS':
                if field.get('meaning') != 'tier_not_specified_for_defined_standard':
                    raise ValueError('Defined-standard missing tier incorrectly classified')
            continue
        value = field['value']
        if name in ['CONTRACT_ID', 'PLAN_ID', 'SEGMENT_ID']:
            if value != source:
                raise ValueError('Identifier or leading zeros changed')
        elif name == 'DAYS_SUPPLY':
            if value != {'1': 30, '2': 90, '3': None, '4': 60}[source]:
                raise ValueError('Supply category decoded incorrectly')
        elif name.endswith('_YN'):
            if value is not (source == 'Y'):
                raise ValueError('Flag decoded incorrectly')
        elif name == 'COVERAGE_LEVEL' or name == 'TIER' or name.startswith('COST_TYPE_'):
            if type(value) is not int or value != int(source):
                raise ValueError('Code decoded incorrectly')
            if name == 'COVERAGE_LEVEL' and field.get('meaning') != {'0': 'pre_deductible', '1': 'initial', '3': 'catastrophic'}[source]:
                raise ValueError('Benefit phase decoded incorrectly')
            if name.startswith('COST_TYPE_') and field.get('meaning') != {'0': 'not_offered', '1': 'copay', '2': 'coinsurance'}[source]:
                raise ValueError('Cost type decoded incorrectly')
        else:
            if Decimal(field['native_numeric_value']) != Decimal(source):
                raise ValueError('Native numeric value changed')
            if name.startswith('COST_AMT_') and raw['COST_TYPE_' + name[9:]] == '0':
                if value is not None or field.get('meaning') != 'channel_not_offered':
                    raise ValueError('Not-offered channel turned into free benefit')
            else:
                if Decimal(value) != Decimal(source):
                    raise ValueError('Modeled amount changed')
            if name.startswith('COST_AMT_') and raw['COST_TYPE_' + name[9:]] != '0':
                expected_unit = 'USD_per_source_supply' if raw['COST_TYPE_' + name[9:]] == '1' else 'fraction'
                if field['unit'] != expected_unit:
                    raise ValueError('Dollars confused with coinsurance')
            if name.startswith(('copay_', 'coin_')):
                if field['unit'] != ('USD_per_source_supply' if name.startswith('copay_') else 'fraction'):
                    raise ValueError('Insulin amount unit differs')


def validate(package, acquisition, output):
    manifest = json.loads((package / 'manifest.json').read_text())
    source = json.loads((acquisition / 'source-manifest.json').read_text())
    coverage = json.loads((package / 'coverage.json').read_text())
    checks = {}
    for group in ['files_sha256', 'code_sha256', 'input_sha256']:
        for name, expected in manifest[group].items():
            p = package / name if group == 'files_sha256' else ROOT / name
            checks[group + ':' + name] = sha(p) == expected
    if not all(checks.values()):
        raise ValueError('Changed artifact/code/input')
    targets = {p['offering_id']: p for p in json.loads((ROOT / 'docs/data/l05-drug-coverage-2026-10-25/build-r3/plans.json').read_text())}
    old = sqlite3.connect('file:' + str(ROOT / 'docs/data/l05-drug-coverage-2026-10-25/build-r3/inventory.sqlite3') + '?mode=ro', uri=True)
    contexts = {k: json.loads(v) for k, v in old.execute('SELECT offering_id,payload FROM benefit_context')}
    con = sqlite3.connect('file:' + str(package / 'inventory.sqlite3') + '?mode=ro', uri=True)
    checks['same_existing_71_target_plans'] = set(targets) == {r[0] for r in con.execute('SELECT offering_id FROM plans')} and len(targets) == 71
    counts = {}; all_rows = {}; scoped_fields = 0
    for table in ['beneficiary', 'insulin']:
        monthly = next(m for m in source['members'] if m['table'] == table and m['source'] == 'monthly')
        quarterly = next(m for m in source['members'] if m['table'] == table and m['source'] == 'quarterly')
        for label, member in [('monthly', monthly), ('quarterly', quarterly)]:
            if sha(ROOT / member['path']) != member['sha256']:
                raise ValueError('Changed source ZIP')
            with zipfile.ZipFile(ROOT / member['path']) as archive:
                native = archive.read(member['inner']['name'])
            checks[table + ':' + label + ':native_hash'] = hashlib.sha256(native).hexdigest() == member['inner']['sha256']
            if label == 'quarterly':
                checks[table + ':monthly_quarterly_bytes_equal'] = native == monthly_native
            else:
                monthly_native = native
        iterator = iter(con.execute('SELECT source_ordinal,offering_id,raw_json,modeled_json,raw_line FROM schedules WHERE table_name=? ORDER BY source_ordinal', (table,)))
        current = next(iterator, None)
        count = Counter(); all_rows[table] = []
        lines = monthly_native.splitlines(keepends=True)
        header = lines[0].rstrip(b'\r\n').decode('ascii').split('|')
        checks[table + ':field_count'] = len(header) == (24 if table == 'beneficiary' else 13)
        with gzip.open(package / (table + '-native.psv.gz'), 'rb') as flat:
            if flat.readline() != b'SOURCE_ORDINAL|' + lines[0]:
                raise ValueError('Flat header differs')
            for ordinal, line in enumerate(lines[1:], 2):
                count['national_rows'] += 1
                cells = line.rstrip(b'\r\n').decode('ascii').split('|')
                if len(cells) != len(header):
                    raise ValueError('Malformed source row')
                raw = dict(zip(header, cells)); oid = '2026:' + ':'.join(cells[:3])
                if oid not in targets:
                    count['outside_scope_rows'] += 1; continue
                count['scoped_rows'] += 1
                if current is None or current[0] != ordinal or current[1] != oid or current[4] != line:
                    raise ValueError('Missing, extra, shifted or altered source row')
                if json.loads(current[2]) != raw:
                    raise ValueError('Source field differs')
                benefit_type = contexts[oid]['rx']['rxDetails']['rxSetup']['rxSetupDetails']['drugBenefitType']
                check_model(raw, json.loads(current[3]), table, benefit_type)
                if flat.readline() != str(ordinal).encode() + b'|' + line:
                    raise ValueError('Flat output differs')
                all_rows[table].append((oid, ordinal, raw))
                scoped_fields += len(header)
                current = next(iterator, None)
            if current is not None or flat.read(1):
                raise ValueError('Extra data not present in native source')
        counts[table] = dict(count)
        expected = coverage['accounting'][table]
        checks[table + ':row_accounting'] = all(count[k] == expected[k] for k in ['national_rows', 'outside_scope_rows', 'scoped_rows']) and count['national_rows'] == count['outside_scope_rows'] + count['scoped_rows']
        checks[table + ':all_71_represented'] = {oid for oid, _, _ in all_rows[table]} == set(targets)
    checks['all_57123_modeled_fields_checked'] = scoped_fields == coverage['modeled_field_observations'] == 57123
    expected_tiers = {(oid, str(t)) for oid, p in targets.items() for (t,) in old.execute("SELECT DISTINCT json_extract(raw_json,'$.TIER_LEVEL_VALUE') FROM drug_rows WHERE table_name='basic' AND formulary_id=?", (p['formulary_id'],))}
    actual = {(oid, r['TIER']) for oid, _, r in all_rows['beneficiary'] if r['COVERAGE_LEVEL'] == '1' and r['DAYS_SUPPLY'] == '1'}
    checks['formulary_tier_denominator_reconstructed'] = len(expected_tiers) == coverage['basic_formulary_plan_tier_pairs']
    checks['missing_tier_schedule_list_exact'] = sorted(expected_tiers - actual) == [tuple(x) for x in coverage['missing_initial_30_day_tier_schedules']]
    ledger = json.loads((package / 'PBP-named-amount-comparisons.json').read_text())
    raw_by_key = {(table, ordinal): r for table, rows in all_rows.items() for _, ordinal, r in rows}
    status = Counter()
    for entry in ledger:
        r = raw_by_key[(entry['table'], entry['source_ordinal'])]
        if r[entry['source_field']] != entry['source_value']:
            raise ValueError('PBP comparison changed its CMS schedule value')
        value = contexts[entry['offering_id']]['rx']
        for key in entry['PBP_pointer_within_rx'].strip('/').split('/'):
            value = value.get(key, {}) if isinstance(value, dict) else {}
        value = '' if value == {} else str(value)
        if value != entry['PBP_raw']:
            raise ValueError('PBP comparison changed its held PBP value')
        if entry['status'] != 'no_explicit_named_PBP_field':
            normalized = Decimal(value) / (100 if entry['PBP_numeric_basis'] == 'percentage_points' else 1)
            expected_status = 'numeric_agreement' if normalized == Decimal(entry['source_value']) else 'difference_held'
            if expected_status != entry['status']:
                raise ValueError('PBP comparison agreement was fabricated')
        status[entry['status']] += 1
    checks['PBP_direct_amount_comparisons_recomputed'] = dict(status) == coverage['PBP_amount_comparisons']
    dispositions = json.loads((package / 'insulin-blank-channel-dispositions.json').read_text())
    for entry in dispositions:
        oid = entry['offering_id']; r = raw_by_key[('insulin', entry['source_ordinal'])]
        suffix = {'preferred_retail': 'PREF', 'standard_retail': 'NONPREF', 'preferred_mail': 'MAIL_PREF', 'standard_mail': 'MAIL_NONPREF'}[entry['channel']]
        if r['copay_amt_' + suffix.lower() + '_insln'].strip() or r['coin_amt_' + suffix.lower() + '_insln'].strip():
            raise ValueError('Blank channel disposition targets a reported amount')
        matches = {b['COST_TYPE_' + suffix] for boid, _, b in all_rows['beneficiary'] if boid == oid and b['COVERAGE_LEVEL'] == '1' and b['DAYS_SUPPLY'] == r['DAYS_SUPPLY'] and (r['TIER'] == '.' or b['TIER'] == r['TIER'])}
        if sorted(matches) != entry['matched_beneficiary_channel_types'] or entry['status'] != ('channel_not_offered' if matches == {'0'} else 'unresolved_blank_channel'):
            raise ValueError('Blank-channel source interpretation differs')
    checks['all_541_blank_insulin_channels_reconciled'] = len(dispositions) == coverage['blank_insulin_channel_pairs'] == 541
    checks['personal_store_pricing_remains_deferred'] = not coverage['consumer_release_enabled'] and not coverage['personal_calculator_implemented']
    con.close(); old.close()
    result = {'schema': 'l06-independent-cost-schedule-audit/1', 'passed': all(checks.values()),
              'manifest_sha256': sha(package / 'manifest.json'), 'checks': checks, 'table_accounting': counts,
              'modeled_source_fields_checked': scoped_fields, 'unexplained_field_mismatches': 0,
              'limits': 'Source fidelity, conservative field decoding, table coverage and named PBP numeric comparisons; not full carrier semantic acceptance or a personal cost calculation.'}
    if output.exists():
        raise ValueError('Do not overwrite a validation receipt')
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'checks'}, indent=2))
    if not result['passed']:
        raise ValueError('Validation failed: ' + str([k for k, v in checks.items() if not v]))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--package', type=Path, required=True)
    p.add_argument('--acquisition', type=Path, default=ROOT / 'docs/data/l06-drug-costs-2026-10-27/acquisition-cost-r1')
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    validate(args.package.resolve(), args.acquisition.resolve(), args.out.resolve())
