#!/usr/bin/env python3
"""Run offline :8893 personas and report assertion-backed field coverage.

No live server, browser, model, provider key, saved customer profile or network is
used. Every witness must point to a concrete executed oracle assertion. Values
are synthetic. The immutable 78 + 14 inventory stays visible even when absent.
"""
from __future__ import annotations

import argparse
import copy
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
TESTS = HERE / 'tests'
CATALOG_PATH = TESTS / 'fixtures/profile_field_catalog.json'
DEFAULT_OUTPUT = ROOT / 'audit-evidence/advisor-persona-coverage-20261102'
sys.path.insert(0, str(TESTS))


def load_catalog(path=CATALOG_PATH):
    catalog = json.loads(Path(path).read_text())
    contract_binding = catalog['sources']['profile_contract']
    contract_path = ROOT / contract_binding['path']
    contract = json.loads(contract_path.read_text())
    for binding in catalog['sources'].values():
        if hashlib.sha256((ROOT / binding['path']).read_bytes()).hexdigest() != binding['sha256']:
            raise ValueError('CATALOG_SOURCE_DRIFT')
    if contract['content_sha256'] != contract_binding['content_sha256']:
        raise ValueError('CATALOG_CONTRACT_SELECTION_DRIFT')
    fields = catalog['fields']
    paths = [field['path'] for field in fields]
    if len(paths) != len(set(paths)):
        raise ValueError('CATALOG_DUPLICATE_PATH')
    original = [field['path'] for field in fields if field['inventory'] == 'original_78']
    additive = [field['path'] for field in fields if field['inventory'] == 'additive_14']
    if original != list(contract['fields']) or len(original) != 78:
        raise ValueError('CATALOG_ORIGINAL_DENOMINATOR_DRIFT')
    if additive != contract['additive_optional_report_paths'] or len(additive) != 14:
        raise ValueError('CATALOG_ADDITIVE_DENOMINATOR_DRIFT')
    if catalog['question_ids'] != [question['id'] for question in contract['questions']]:
        raise ValueError('CATALOG_QUESTION_INVENTORY_DRIFT')
    ids = catalog['question_ids']
    if len(ids) != 41 or len(set(ids)) != 41 or not {'RC11.C1', 'RC16.C1', 'RC16.C2'} <= set(ids):
        raise ValueError('CATALOG_QUESTION_DENOMINATOR_DRIFT')
    if catalog.get('questions') != [{'id': question['id'], 'kind': question['kind'],
            'parent': question.get('parent'), 'fields': question['fields']} for question in contract['questions']]:
        raise ValueError('CATALOG_QUESTION_FIELD_MAP_DRIFT')
    if len(paths) != catalog['denominators']['total_report_paths']:
        raise ValueError('CATALOG_TOTAL_DENOMINATOR_DRIFT')
    state_keys = {'known', 'unanswered', 'unknown', 'deferred', 'explicit_absence', 'correction', 'rejected'}
    for field in fields:
        if (set(field['state_expectations']) != state_keys
                or not all(isinstance(value, str) and value for value in field['state_expectations'].values())):
            raise ValueError('CATALOG_FIELD_STATE_EXPECTATION_MISSING')
        if field['status'] not in {'capture', 'derived', 'legacy', 'not_written', 'held'}:
            raise ValueError('CATALOG_STATUS_INVALID')
    return catalog


def _assertion_key(item):
    # JSON is used for equality only. It never invokes a command or supplies an oracle.
    return json.dumps({key: item.get(key) for key in
        ('scenario_id', 'step', 'assertion', 'actual', 'expected', 'passed',
         'covered_path', 'native_path', 'state', 'mode')},
        sort_keys=True, ensure_ascii=False)


def _effective_state(witness, result):
    """Retained stale values are never upgraded by a value-only oracle."""
    state = witness['state']
    if state not in {'known', 'explicit_none'}:
        return state
    snapshot = result.get('observed', {}) if witness['step'] == 'final' else next(
        (step.get('observed', {}) for step in result.get('steps', []) if step['step'] == witness['step']), {})
    path = witness['path']
    if path.startswith('guide.fields.'):
        envelope_state = snapshot.get('guide_status', {}).get(path.removeprefix('guide.fields.'))
        if envelope_state in {'stale', 'unknown', 'skipped', 'tentative', 'conflicting', 'superseded'}:
            return 'deferred' if envelope_state == 'skipped' else 'conflicting' if envelope_state == 'tentative' else envelope_state
    if path.startswith('readiness.facts.'):
        identifier = path.split('.')[2]
        if identifier in snapshot.get('stale_reports', []):
            return 'stale'
        disposition = snapshot.get('dispositions', {}).get(identifier)
        if disposition in {'explicit_unknown', 'deferred', 'conflicting', 'superseded', 'needs_review'}:
            return {'explicit_unknown': 'unknown', 'needs_review': 'stale'}.get(disposition, disposition)
    return state


def build_report(results, catalog):
    """Pure aggregation; merely declared or orphaned witness metadata fails closed."""
    by_path = {field['path']: [] for field in catalog['fields']}
    metadata = {field['path']: [] for field in catalog['metadata']}
    assertions = 0
    failures = []
    seen_scenarios = set()
    for result in results:
        identifier = result['scenario_id']
        if identifier in seen_scenarios:
            raise ValueError('DUPLICATE_SCENARIO_ID')
        seen_scenarios.add(identifier)
        executed = {_assertion_key(item) for item in result['assertions']}
        assertions += len(result['assertions'])
        failures.extend(item for item in result['assertions'] if item['passed'] is not True)
        for witness in result['coverage']:
            if (witness.get('scenario_id') != identifier
                    or witness.get('path') != witness.get('covered_path')
                    or _assertion_key(witness) not in executed):
                raise ValueError('ORPHAN_COVERAGE_WITNESS')
            if witness.get('mode') not in catalog['coverage_modes']:
                raise ValueError('UNSUPPORTED_COVERAGE_MODE')
            if witness.get('state') not in catalog['coverage_states']:
                raise ValueError('UNSUPPORTED_COVERAGE_STATE')
            path = witness['path']
            target = by_path if path in by_path else metadata if path in metadata else None
            if target is None:
                raise ValueError('UNCATALOGED_COVERAGE_PATH: ' + path)
            # A failed assertion remains in the evidence but earns zero coverage.
            if witness.get('passed') is True:
                accepted = copy.deepcopy(witness)
                accepted['state'] = _effective_state(witness, result)
                target[path].append(accepted)
    fields = []
    for field in catalog['fields']:
        witnesses = by_path[field['path']]
        states = Counter(item['state'] for item in witnesses)
        modes = Counter(item['mode'] for item in witnesses)
        captures = [item for item in witnesses if item['state'] in {'known', 'explicit_none'}
                    and item['mode'] in {'questioned', 'volunteered'}]
        derived = [item for item in witnesses if item['mode'] == 'derived'
                   and item['state'] in {'known', 'explicit_none'}]
        fields.append({**copy.deepcopy(field),
            'witness_count': len(witnesses), 'scenario_ids': sorted({item['scenario_id'] for item in witnesses}),
            'state_counts': dict(sorted(states.items())), 'mode_counts': dict(sorted(modes.items())),
            'successful_capture': bool(captures) and field['status'] != 'derived',
            'derived_witness': bool(derived) or field['status'] == 'derived'
                and any(item['state'] in {'known', 'explicit_none'} for item in witnesses),
            'known_reuse_witness': any(item['mode'] == 'reused' and item['state'] in {'known', 'explicit_none'} for item in witnesses),
            'untested_states': [state for state in ('known', 'unknown', 'deferred', 'unanswered', 'explicit_none', 'conflicting', 'stale') if not states[state]],
            'witnesses': witnesses})
    subsets = {}
    for name in ('original_78', 'additive_14', 'current_extension'):
        rows = [field for field in fields if field['inventory'] == name]
        subsets[name] = {'denominator': len(rows),
            'any_asserted_state': sum(bool(row['witness_count']) for row in rows),
            'successful_capture_paths': sum(row['successful_capture'] for row in rows),
            'derived_paths': sum(row['derived_witness'] for row in rows),
            'known_reuse_paths': sum(row['known_reuse_witness'] for row in rows),
            'explicit_absence_paths': sum(bool(row['mode_counts'].get('explicit_absence')) for row in rows),
            'rejection_paths': sum(bool(row['mode_counts'].get('rejected')) for row in rows),
            'no_assertion_paths': [row['path'] for row in rows if not row['witness_count']]}
    modes = {mode: {'witnesses': sum(row['mode_counts'].get(mode, 0) for row in fields),
                    'distinct_paths': sum(bool(row['mode_counts'].get(mode)) for row in fields)}
             for mode in catalog['coverage_modes']}
    questions = []
    for definition in catalog.get('questions', []):
        related = [field for field in fields if field['path'] in definition['fields']]
        displays = [copy.deepcopy(item) for result in results for item in result['assertions']
            if item['passed'] is True and item['assertion'] == 'next_question'
            and item['actual'] == definition['id']]
        questions.append({**copy.deepcopy(definition),
            'asserted_display_witnesses': displays,
            'field_paths_with_assertions': [field['path'] for field in related if field['witness_count']],
            'field_paths_with_successful_capture': [field['path'] for field in related if field['successful_capture']],
            'field_paths_without_assertions': [field['path'] for field in related if not field['witness_count']],
            'parent_alias_note': ('Parent-field reuse is not a separate displayed question.' if definition.get('parent') else None)})
    summary = {'kind': 'offline_current_8893_persona_field_coverage',
        'scenario_count': len(results), 'assertion_count': assertions,
        'failed_assertion_count': len(failures), 'passed': not failures,
        'paid_model_calls': sum(result.get('paid_model_calls', 0) for result in results),
        'synthetic_contract_calls': sum(result.get('synthetic_contract_calls', 0) for result in results),
        'denominators': copy.deepcopy(catalog['denominators']), 'inventories': subsets,
        'coverage_modes': modes,
        'classification_counts': dict(sorted(Counter(field['status'] for field in fields).items())),
        'all_report_paths_have_an_executed_assertion': all(field['witness_count'] for field in fields),
        'all_fields_have_successful_known_capture': all(field['successful_capture'] for field in fields),
        'all_field_state_combinations_exhaustive': False,
        'real_model_quality_evaluated': False, 'external_verification_established': False}
    if summary['paid_model_calls']:
        raise ValueError('PAID_CALL_IN_OFFLINE_REPORT')
    return {'summary': summary, 'sources': copy.deepcopy(catalog['sources']), 'questions': questions,
        'fields': fields,
        'metadata': [{**copy.deepcopy(item), 'witnesses': metadata[item['path']]} for item in catalog['metadata']],
        'failed_assertions': failures, 'limits': copy.deepcopy(catalog['limits'])}


def markdown(report):
    summary = report['summary']
    lines = ['# Current :8893 offline persona field coverage', '',
        f"{summary['scenario_count']} executed scenarios; {summary['assertion_count']} assertions; "
        f"{summary['failed_assertion_count']} failures; **zero paid model calls**.", '',
        'Original 78 paths, 14 additive gap-report paths and 4 current report extensions remain separate. '
        'Unknown, absence, rejection, derived links and reuse are not independently reported capture. '
        'These deterministic contracts test software state handling, not real LLM reasoning or consumer comprehension.', '',
        '| Inventory | Paths | Any assertion | Successful capture | Derived | Explicit absence | Rejection |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for name, row in summary['inventories'].items():
        lines.append(f"| {name} | {row['denominator']} | {row['any_asserted_state']} | {row['successful_capture_paths']} | {row['derived_paths']} | {row['explicit_absence_paths']} | {row['rejection_paths']} |")
    lines += ['', 'All observed state/mode counts below come from executed assertions. '
        'Each JSON witness includes its scenario, step, exact expected value and independently observed result. '
        'A blank state remains an untested state, not presumed support.', '',
        '| Field | Class | States witnessed | Modes witnessed | Scenario witnesses |',
        '| --- | --- | --- | --- | --- |']
    for field in report['fields']:
        states = ', '.join(f'{key} ({count})' for key, count in field['state_counts'].items()) or 'GAP: no assertion'
        modes = ', '.join(f'{key} ({count})' for key, count in field['mode_counts'].items()) or '—'
        ids = ', '.join(field['scenario_ids']) or '—'
        lines.append(f"| `{field['path']}` | {field['status']} | {states} | {modes} | {ids} |")
    lines += ['', '## Retained gaps and limits', '']
    for field in report['fields']:
        if field['status'] in {'held', 'legacy', 'not_written'} or not field['witness_count']:
            lines.append(f"- `{field['path']}`: {field['note']}")
    lines += ['', '## Separate visit/audit metadata', '',
        'These paths remain visible but are excluded from the personal report-field denominator. '
        'Their role is not equivalent to collecting another consumer answer.', '',
        '| Metadata path | Classification | Meaning |', '| --- | --- | --- |']
    for field in report['metadata']:
        lines.append(f"| `{field['path']}` | {field['classification']} | {field['note']} |")
    lines += ['', '## Remaining state coverage', '',
        'This corpus is not exhaustive across every valid option, correction, entity count, time scope or answer combination. '
        'The JSON exposes `untested_states` for every field. A no-writer rejection/absence test does not close a capture or semantic gap.', '']
    lines += ['## All 41 reviewed question meanings', '',
        'Field assertions are distinct from asserted question display. Documented child meanings reuse their parent fields; '
        'their mapped field coverage does not mean a new child question was shown.', '',
        '| ID | Kind / parent | Fields with assertions | Fields with capture | Asserted displays |',
        '| --- | --- | ---: | ---: | ---: |']
    for question in report['questions']:
        kind = question['kind'] + (f" / {question['parent']}" if question['parent'] else '')
        lines.append(f"| {question['id']} | {kind} | {len(question['field_paths_with_assertions'])}/{len(question['fields'])} | {len(question['field_paths_with_successful_capture'])}/{len(question['fields'])} | {len(question['asserted_display_witnesses'])} |")
    lines.append('')
    return '\n'.join(lines)


def run(fixtures, output):
    from persona_runner import run_scenario, load_scenarios
    catalog = load_catalog()
    scenarios = [scenario for fixture in fixtures for scenario in load_scenarios(fixture)]
    results = [run_scenario(scenario) for scenario in scenarios]
    report = build_report(results, catalog)
    output.mkdir(parents=True, exist_ok=True)
    files = {'coverage-matrix.json': report,
        'expected-profiles.json': [{'scenario_id': item['id'], 'name': item['name'], 'expected': item.get('expected', {})} for item in scenarios],
        'observed-profiles.json': [{'scenario_id': item['scenario_id'], 'observed': item['observed'], 'passed': item['passed']} for item in results],
        'executed-results.json': results, 'summary.json': report['summary']}
    for name, value in files.items():
        (output / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    with (output / 'coverage-matrix.csv').open('w', newline='') as target:
        writer = csv.DictWriter(target, fieldnames=['path', 'inventory', 'status',
            'witness_count', 'successful_capture', 'derived_witness',
            'known_reuse_witness', 'states', 'modes', 'scenario_ids', 'remaining_states', 'note'])
        writer.writeheader()
        for field in report['fields']:
            writer.writerow({key: field[key] for key in ('path', 'inventory', 'status',
                'witness_count', 'successful_capture', 'derived_witness', 'known_reuse_witness', 'note')} |
                {'states': json.dumps(field['state_counts'], sort_keys=True),
                 'modes': json.dumps(field['mode_counts'], sort_keys=True),
                 'scenario_ids': ', '.join(field['scenario_ids']),
                 'remaining_states': ', '.join(field['untested_states'])})
    (output / 'coverage-matrix.md').write_text(markdown(report))
    print(json.dumps(report['summary'], indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', action='append', type=Path)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    fixtures = args.fixtures or [TESTS / 'fixtures/persona_journeys.json', TESTS / 'fixtures/field_scenarios.json']
    raise SystemExit(0 if run(fixtures, args.output)['summary']['passed'] else 1)
