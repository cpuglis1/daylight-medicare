#!/usr/bin/env python3
"""Model published 2026 cost schedules without computing personal costs."""
import argparse
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l06-drug-costs-2026-10-27'
L05 = ROOT / 'docs/data/l05-drug-coverage-2026-10-25/build-r3'
CHANNELS = {'PREF': 'preferred_retail', 'NONPREF': 'standard_retail',
            'MAIL_PREF': 'preferred_mail', 'MAIL_NONPREF': 'standard_mail'}
BENEFICIARY = ['CONTRACT_ID', 'PLAN_ID', 'SEGMENT_ID', 'COVERAGE_LEVEL', 'TIER', 'DAYS_SUPPLY']
for suffix in CHANNELS:
    BENEFICIARY += [p + suffix for p in ['COST_TYPE_', 'COST_AMT_', 'COST_MIN_AMT_', 'COST_MAX_AMT_']]
BENEFICIARY += ['TIER_SPECIALTY_YN', 'DED_APPLIES_YN']
INSULIN = ['CONTRACT_ID', 'PLAN_ID', 'SEGMENT_ID', 'TIER', 'DAYS_SUPPLY']
INSULIN += [p + s.lower() + '_insln' for p in ['copay_amt_', 'coin_amt_'] for s in CHANNELS]
FIELDS = {'beneficiary': BENEFICIARY, 'insulin': INSULIN}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def number(raw):
    n = Decimal(raw)
    if not n.is_finite() or n < 0:
        raise ValueError('Nonfinite or negative amount')
    return format(n, 'f')


def model_row(kind, raw, benefit_type):
    fields = {}
    for key, value in raw.items():
        state = 'reported'
        if value == '':
            state = 'source_empty'
        elif value.isspace():
            state = 'source_blank'
        elif value == '.':
            state = 'source_missing_token'
        f = {'raw': value, 'source_state': state, 'value': None, 'unit': None}
        fields[key] = f
        if state != 'reported':
            f['meaning'] = ('tier_not_specified_for_defined_standard' if kind == 'insulin' and key == 'TIER'
                            and benefit_type == 'DS' else state)
            continue
        if key in ['CONTRACT_ID', 'PLAN_ID', 'SEGMENT_ID']:
            f['value'] = value
        elif key == 'COVERAGE_LEVEL':
            f['value'] = int(value)
            f['meaning'] = {'0': 'pre_deductible', '1': 'initial', '3': 'catastrophic'}[value]
        elif key == 'TIER':
            f['value'] = int(value)
        elif key == 'DAYS_SUPPLY':
            f['value'] = {'1': 30, '2': 90, '3': None, '4': 60}[value]
            f['unit'] = 'days' if value != '3' else None
            f['meaning'] = 'other_source_defined_supply' if value == '3' else 'source_supply_category'
        elif key.endswith('_YN'):
            f['value'] = {'Y': True, 'N': False}[value]
        elif key.startswith('COST_TYPE_'):
            f['value'] = int(value)
            f['meaning'] = {'0': 'not_offered', '1': 'copay', '2': 'coinsurance'}[value]
        else:
            f['native_numeric_value'] = number(value)
            f['value'] = f['native_numeric_value']
            if key.startswith('COST_AMT_'):
                code = raw['COST_TYPE_' + key[len('COST_AMT_'):]]
                if code == '0':
                    f.update(value=None, meaning='channel_not_offered')
                else:
                    f['unit'] = 'USD_per_source_supply' if code == '1' else 'fraction'
            elif key.startswith(('COST_MIN_AMT_', 'COST_MAX_AMT_')):
                # A source zero is preserved; it is never treated as a zero-dollar
                # ceiling or free benefit without the corresponding rule basis.
                f['unit'] = 'source_native_cost_bound'
                f['meaning'] = 'bound_retained_not_applied_in_calculator'
            else:
                f['unit'] = 'USD_per_source_supply' if key.startswith('copay_') else 'fraction'
            if f['unit'] == 'fraction' and Decimal(value) > 1:
                raise ValueError('Coinsurance is not a fraction in [0,1]')
    return fields


def pbp_comparisons(records, contexts):
    result = []
    for kind, rows in records.items():
        for row in rows:
            r, oid = row['raw'], row['offering_id']
            if kind == 'beneficiary' and r['COVERAGE_LEVEL'] != '1':
                continue
            c = contexts[oid]['rx']['rxDetails']['rxSetup']
            tier = r['TIER']
            supply = {'1': 'One', '2': 'Three', '4': 'Two'}.get(r['DAYS_SUPPLY'])
            if supply is None:
                continue
            if kind == 'beneficiary':
                native = c.get('rxTiers', {}).get('rxTier' + tier, {}).get('rxTier' + tier + 'PreIcl', {}).get('rxTier' + tier + 'PreIclDetails', {})
                pointer = '/rxDetails/rxSetup/rxTiers/rxTier' + tier + '/rxTier' + tier + 'PreIcl/rxTier' + tier + 'PreIclDetails/'
                fields = [(f'COST_AMT_{s}', 'preIcl' + channel + supply + 'Month' + ('Copayment' if r['COST_TYPE_' + s] == '1' else 'Coinsurance'), r['COST_TYPE_' + s] == '2')
                          for s, channel in [('PREF', 'PreferredRetail'), ('NONPREF', 'Retail'), ('MAIL_PREF', 'PreferredMailOrder'), ('MAIL_NONPREF', 'MailOrder')]
                          if r['COST_TYPE_' + s] != '0']
            else:
                ds = tier == '.' and c.get('rxSetupDetails', {}).get('drugBenefitType') == 'DS'
                native = (c.get('dsInsulinCostShare', {}).get('dsInsulinCostShareDetails', {}) if ds else
                          c.get('rxInsulin', {}).get('rxInsulinTier' + tier + 'PreIcl', {}).get('rxInsulinTier' + tier + 'PreIclDetails', {}))
                pointer = ('/rxDetails/rxSetup/dsInsulinCostShare/dsInsulinCostShareDetails/' if ds else
                           '/rxDetails/rxSetup/rxInsulin/rxInsulinTier' + tier + 'PreIcl/rxInsulinTier' + tier + 'PreIclDetails/')
                fields = [(p + '_amt_' + s + '_insln', ('insulinDs' if ds else 'insulinPreIcl') + channel + supply + 'Month' + term, p == 'coin')
                          for s, channel in [('pref', 'PreferredRetail'), ('nonpref', 'Retail'), ('mail_pref', 'PreferredMailOrder'), ('mail_nonpref', 'MailOrder')]
                          for p, term in [('copay', 'Copayment'), ('coin', 'Coinsurance')]
                          if r[p + '_amt_' + s + '_insln'].strip()]
            for field, key, coin in fields:
                value = str(native.get(key, ''))
                entry = {'table': kind, 'source_ordinal': row['source_ordinal'], 'offering_id': oid,
                         'tier_raw': tier, 'days_supply_raw': r['DAYS_SUPPLY'], 'source_field': field,
                         'source_value': r[field], 'PBP_field': key, 'PBP_raw': value,
                         'PBP_pointer_within_rx': pointer + key,
                         'PBP_numeric_basis': 'percentage_points' if coin else 'USD',
                         'PBP_member': contexts[oid]['member'], 'PBP_archive': contexts[oid]['source_archive']}
                if value.strip() in ['', 'Not Available']:
                    entry['status'] = 'no_explicit_named_PBP_field'
                else:
                    converted = Decimal(value) / (100 if coin else 1)
                    entry['PBP_value_in_source_units'] = str(converted)
                    entry['status'] = 'numeric_agreement' if converted == Decimal(r[field]) else 'difference_held'
                result.append(entry)
    return result


def build(acquisition, out):
    if out.exists():
        raise ValueError('Use a new cost-build revision')
    out.mkdir(parents=True)
    manifest = read(acquisition / 'source-manifest.json')
    if manifest['year'] != 2026 or (acquisition / 'SEALED').read_text().strip() != sha(acquisition / 'source-manifest.json'):
        raise ValueError('Acquisition year/seal mismatch')
    plans = {p['offering_id']: p for p in read(L05 / 'plans.json')}
    con_old = sqlite3.connect('file:' + str(L05 / 'inventory.sqlite3') + '?mode=ro', uri=True)
    contexts = {k: json.loads(v) for k, v in con_old.execute('SELECT offering_id,payload FROM benefit_context')}
    if len(plans) != 71 or set(plans) != set(contexts):
        raise ValueError('Target population/context changed')
    benefit_types = {oid: c['rx']['rxDetails']['rxSetup']['rxSetupDetails']['drugBenefitType'] for oid, c in contexts.items()}
    expected_tiers = {(oid, str(tier)) for oid, p in plans.items() for (tier,) in con_old.execute(
        "SELECT DISTINCT json_extract(raw_json,'$.TIER_LEVEL_VALUE') FROM drug_rows WHERE table_name='basic' AND formulary_id=?", (p['formulary_id'],))}
    con_old.close()
    con = sqlite3.connect(out / 'inventory.sqlite3')
    con.executescript('CREATE TABLE plans(offering_id TEXT PRIMARY KEY,payload TEXT); CREATE TABLE schedules(table_name TEXT,source_ordinal INTEGER,offering_id TEXT,raw_json TEXT,modeled_json TEXT,raw_line BLOB,PRIMARY KEY(table_name,source_ordinal)); CREATE INDEX schedule_plan ON schedules(offering_id,table_name);')
    con.executemany('INSERT INTO plans VALUES(?,?)', [(k, json.dumps(p, sort_keys=True)) for k, p in sorted(plans.items())])
    records = {'beneficiary': [], 'insulin': []}
    accounting, source_hashes, value_states = {}, {}, {}
    for kind in FIELDS:
        source = next(m for m in manifest['members'] if m['source'] == 'monthly' and m['table'] == kind)
        if sha(ROOT / source['path']) != source['sha256']:
            raise ValueError('Changed raw schedule')
        count = Counter(); digest = hashlib.sha256(); states = Counter()
        with zipfile.ZipFile(ROOT / source['path']) as archive:
            with archive.open(source['inner']['name']) as raw, (out / (kind + '-native.psv.gz')).open('wb') as target:
                with gzip.GzipFile(filename='', fileobj=target, mode='wb', mtime=0) as selected:
                    header = raw.readline(); digest.update(header)
                    if header.rstrip(b'\r\n').decode('ascii').split('|') != FIELDS[kind]:
                        raise ValueError('Unknown ' + kind + ' header')
                    selected.write(b'SOURCE_ORDINAL|' + header)
                    for ordinal, line in enumerate(raw, 2):
                        digest.update(line); count['national_rows'] += 1
                        cells = line.rstrip(b'\r\n').decode('ascii').split('|')
                        if len(cells) != len(FIELDS[kind]):
                            raise ValueError('Malformed native row')
                        values = dict(zip(FIELDS[kind], cells)); oid = '2026:' + ':'.join(cells[:3])
                        if oid not in plans:
                            count['outside_scope_rows'] += 1; continue
                        modeled = model_row(kind, values, benefit_types[oid])
                        for f in modeled.values():
                            states[f['source_state']] += 1
                        records[kind].append({'source_ordinal': ordinal, 'offering_id': oid, 'raw': values})
                        con.execute('INSERT INTO schedules VALUES(?,?,?,?,?,?)', (kind, ordinal, oid, json.dumps(values, sort_keys=True), json.dumps(modeled, sort_keys=True), line))
                        selected.write(str(ordinal).encode() + b'|' + line)
                        count['scoped_rows'] += 1
        if digest.hexdigest() != source['inner']['sha256']:
            raise ValueError('Native schedule hash mismatch')
        accounting[kind] = {**dict(count), 'modeled_native_fields': len(FIELDS[kind]),
                            'modeled_field_observations': count['scoped_rows'] * len(FIELDS[kind]), 'quarantined_rows': 0}
        source_hashes[kind] = {'native': source['inner'], 'archive_path': source['path'], 'archive_sha256': source['sha256']}
        value_states[kind] = dict(states)
    con.commit(); con.close()
    ben_index = defaultdict(list)
    for row in records['beneficiary']:
        r = row['raw']
        if r['COVERAGE_LEVEL'] == '1':
            ben_index[(row['offering_id'], r['TIER'], r['DAYS_SUPPLY'])].append(r)
    blank_channels = []
    for row in records['insulin']:
        r, oid = row['raw'], row['offering_id']
        for suffix in CHANNELS:
            if any(r[p + suffix.lower() + '_insln'].strip() for p in ['copay_amt_', 'coin_amt_']):
                continue
            candidates = [b['raw'] for b in records['beneficiary'] if b['offering_id'] == oid and b['raw']['COVERAGE_LEVEL'] == '1'
                          and b['raw']['DAYS_SUPPLY'] == r['DAYS_SUPPLY'] and (r['TIER'] == '.' or b['raw']['TIER'] == r['TIER'])]
            types = {b['COST_TYPE_' + suffix] for b in candidates}
            blank_channels.append({'offering_id': oid, 'source_ordinal': row['source_ordinal'], 'channel': CHANNELS[suffix],
                                   'matched_beneficiary_channel_types': sorted(types),
                                   'status': 'channel_not_offered' if types == {'0'} else 'unresolved_blank_channel'})
    comparable = pbp_comparisons(records, contexts)
    actual_tiers = {(r['offering_id'], r['raw']['TIER']) for r in records['beneficiary'] if r['raw']['COVERAGE_LEVEL'] == '1' and r['raw']['DAYS_SUPPLY'] == '1'}
    missing_tiers = sorted(expected_tiers - actual_tiers)
    duplicate_keys = {}
    for kind, rows in records.items():
        counts = Counter(tuple(r['raw'].get(k, '') for k in ['CONTRACT_ID', 'PLAN_ID', 'SEGMENT_ID', 'COVERAGE_LEVEL', 'TIER', 'DAYS_SUPPLY']) for r in rows)
        duplicate_keys[kind] = sum(v - 1 for v in counts.values() if v > 1)
    plan_coverage = [{'offering_id': oid, 'name': p['name'], 'kind': p['kind'], 'PBP_drug_benefit_type': benefit_types[oid],
                      'beneficiary_rows': sum(r['offering_id'] == oid for r in records['beneficiary']),
                      'insulin_rows': sum(r['offering_id'] == oid for r in records['insulin'])} for oid, p in sorted(plans.items())]
    coverage = {'schema': 'l06-cost-schedule-coverage/1', 'year': 2026, 'target_plans': len(plans),
                'plans_with_beneficiary_rows': sum(bool(r['beneficiary_rows']) for r in plan_coverage),
                'plans_with_insulin_rows': sum(bool(r['insulin_rows']) for r in plan_coverage),
                'accounting': accounting, 'source_state_observations': value_states,
                'modeled_field_observations': sum(r['modeled_field_observations'] for r in accounting.values()),
                'basic_formulary_plan_tier_pairs': len(expected_tiers), 'missing_initial_30_day_tier_schedules': missing_tiers,
                'blank_insulin_channel_pairs': len(blank_channels),
                'unresolved_blank_insulin_channels': sum(r['status'] != 'channel_not_offered' for r in blank_channels),
                'defined_standard_missing_tier_rows': sum(r['raw']['TIER'] == '.' and benefit_types[r['offering_id']] == 'DS' for r in records['insulin']),
                'PBP_amount_comparisons': dict(Counter(r['status'] for r in comparable)),
                'duplicate_schedule_keys': duplicate_keys,
                'consumer_release_enabled': False, 'personal_calculator_implemented': False,
                'interpretation_boundary': 'Published schedule/source fidelity with conservative field decoding; no clinically adjudicated approval, bound application, individual subsidy, pharmacy participation or beneficiary total'}
    for filename, data in [('coverage.json', coverage), ('plan-coverage.json', plan_coverage), ('field-map.json', FIELDS),
                           ('source-members.json', source_hashes), ('insulin-blank-channel-dispositions.json', blank_channels),
                           ('PBP-named-amount-comparisons.json', comparable)]:
        write(out / filename, data)
    write(out / 'scope.json', {'year': 2026, 'county_fips': '12021', 'PDP_region': '11', 'plan_count': 71,
                              'pharmacy_specific_pricing': 'Deferred by explicit owner decision',
                              'beneficiary_scope': 'Published schedules for people with no subsidy; insulin copay/coinsurance components separately retained',
                              'not_implemented': ['Personal price or annual cost calculator', 'Pharmacy selection', 'Personal subsidy eligibility', 'Recommendation or UI release']})
    inputs = [acquisition / 'source-manifest.json', L05 / 'plans.json', L05 / 'manifest.json', BASE / 'build-r1/manifest.json']
    code = [Path(__file__).resolve(), ROOT / 'cms-slice/scripts/l06_cost_acquire.py', ROOT / 'cms-slice/scripts/l06_cost_validate.py']
    write(out / 'manifest.json', {'schema': 'l06-published-cost-schedules/1', 'package_id': 'L06-PUBLISHED-COST-SCHEDULES-2026-' + out.name,
        'files_sha256': {p.name: sha(p) for p in out.iterdir() if p.is_file()},
        'code_sha256': {str(p.relative_to(ROOT)): sha(p) for p in code},
        'input_sha256': {str(p.relative_to(ROOT)): sha(p) for p in inputs},
        'human_acceptance': None, 'consumer_release_enabled': False})
    print(json.dumps(coverage, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--acquisition', type=Path, default=BASE / 'acquisition-cost-r1')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    build(args.acquisition.resolve(), args.out.resolve())
