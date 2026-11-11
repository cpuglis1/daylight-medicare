"""Adverse source/scope tests: parsing must never manufacture complete evidence."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from daylight_data.comparison_pipeline import adapters

OFFERING = '2026:H1045:048:002'
OTHER = '2026:H0000:001:000'
FAMILIES = ('authorization', 'referral', 'network_and_setting', 'deductible',
            'frequency_and_quantity', 'covered_days', 'shared_allowance',
            'qualification', 'exclusion', 'waiver_and_replacement')


def record(identifier='r9-one', root='ORIGINAL-one'):
    identity = dict(year=2026, contract='H1045', plan='048', segment='002',
                    geography='Published county', geographic_variant='Exact selected source variant')
    def observation(side):
        evidence = {'side': side, 'source_sha256': ('a' if side == 'cms' else 'b') * 64,
                    'interpretation_review_id': 'fixture-source-reading'}
        if side == 'cms':
            evidence.update(member='official.txt', pointer='/exact/field')
        else:
            evidence.update(pdf_page=2, passage_sha256='c' * 64,
                            location={'column': 'in-network'}, headers=['full header'],
                            footnotes=['Full qualification, including history and exceptions.'])
        return {
            'identity': deepcopy(identity),
            'service': {'category': 'office', 'subtype': 'Exact qualified office examination'},
            'context': {'network': 'in_network', 'setting': 'office', 'population': 'published members',
                        'assistance_basis': 'general plan schedule'},
            'cost': {'kind': 'copayment', 'amount': '10.00', 'range_basis': 'Source printed amount'},
            'unit': {'currency_or_percentage': 'USD', 'denominator': 'one qualified visit', 'period': 'per visit'},
            'boundaries': {'day_bands': [], 'quantity': 'One encounter', 'frequency': 'Source encounter rule',
                           'reset': 'No accumulating allowance is asserted by this fixture'},
            'conditions': {f: {'state': 'asserted', 'assertion': 'Exact source qualification: ' + f,
                               'obligation_ids': [root], 'evidence_ids': ['fixture-proof'],
                               'interpretation_review_id': 'fixture-source-reading'} for f in FAMILIES},
            'exceptions': [{'if': 'source exception', 'then': 'retain distinct alternative'}],
            'variant': {'kind': 'base', 'identifier': 'base-selected', 'enrollment_basis': 'source membership',
                        'effective_period': '2026 plan year'},
            'shared_budgets': [], 'evidence': [evidence],
        }
    return {'id': identifier, 'inventory_root_ids': [root], 'cms': observation('cms'),
            'carrier': observation('carrier'), 'outcome': 'exact_agreement',
            'interpretation_review_receipt': 'fixture-not-an-acceptance', 'accepted_for_reference': False}


def bundle(*components):
    return {'artifact_type': 'r9_component_bundle', 'id': 'bundle',
            'components': list(components), 'offering_id': OFFERING}


def cell(**changes):
    value = {'artifact_type': 'carrier_price_cell', 'id': 'cell', 'offering_id': OFFERING,
             'original_ids': ['ORIGINAL-cell'], 'source_complete': True,
             'cell_text': '$0 if eligible; 40% after the stated visit limit. Other tests may have separate charges.',
             'condition_context': {'header': 'Full row', 'history': 'Retain prior-procedure history',
                                   'waiver': {'if': 'source-specific exception', 'then': 'different rate'}},
             'evidence': [{'source_sha256': 'b' * 64, 'pdf_page': 2, 'headers': ['Full header'],
                           'footnotes': ['All qualifiers'], 'location': {'column': 'complete cost cell'}}]}
    value.update(changes)
    return value


def native(value, *, authority=None):
    return {'artifact_type': 'native_literal', 'id': 'native', 'offering_id': OFFERING,
            'original_ids': ['ORIGINAL-native'], 'payload': {'a/b': {'~key': value}},
            'pointer': '/a~1b/~0key', 'authority': authority,
            'evidence': [{'source_sha256': 'd' * 64, 'member': 'original.json', 'pointer': '/a~1b/~0key'}]}


def hold_codes(task):
    return {h['code'] for h in task['holds']}


class PipelineAdapterTests(unittest.TestCase):
    def test_direct_strict_record_keeps_original_ids_full_meaning_and_false_gates(self):
        value = record(); before = deepcopy(value)
        result = adapters.normalize_task(value)
        self.assertEqual(result['offering_id'], OFFERING)
        self.assertEqual(result['original_ids'], ['ORIGINAL-one'])
        self.assertEqual(result['components'], [before])
        self.assertEqual(result['comparison_checks'][0]['actual_r9_result']['outcome'], 'exact_agreement')
        self.assertTrue(result['research_only'])
        self.assertFalse(result['accepted_for_reference'])
        self.assertFalse(result['consumer_usable'])
        self.assertEqual(value, before)
        result['components'][0]['carrier']['evidence'][0]['footnotes'].append('changed result')
        self.assertEqual(value, before)
        self.assertEqual({'independent_review_required', 'reference_acceptance_held'}, hold_codes(result))
        self.assertTrue(all({'code', 'category', 'path', 'source_dependencies'} <= set(h) for h in result['holds']))

    def test_output_and_fingerprints_deterministic_across_dict_key_order(self):
        a = record(); b = dict(reversed(list(a.items())))
        self.assertEqual(adapters.normalize_task(a), adapters.normalize_task(b))
        self.assertEqual(adapters.adapter_version(), adapters.adapter_version())
        deps = adapters.adapter_dependencies()
        self.assertEqual(deps['schema']['sha256'], '37e66820165e819baf6113955c54e727615e440ad655ac8fbea1ef519740140d')
        self.assertTrue(all(len(x['sha256']) == 64 for x in deps.values()))

    def test_all_bundle_components_and_order_survive_even_same_amount(self):
        first, second = record('a', 'A'), record('b', 'B')
        second['carrier']['unit']['period'] = 'calendar year'
        second['carrier']['evidence'][0]['passage_sha256'] = 'e' * 64
        result = adapters.normalize_task(bundle(first, second))
        self.assertEqual(result['components'], [first, second])
        self.assertEqual(result['original_ids'], ['A', 'B'])
        self.assertEqual(len(result['comparison_checks']), 2)
        self.assertEqual(result['comparison_checks'][1]['actual_r9_result']['outcome'], 'conflict')
        swapped = adapters.normalize_task(bundle(second, first))
        self.assertEqual(result['task_id'], swapped['task_id'])
        self.assertNotEqual(result['input_fingerprint'], swapped['input_fingerprint'])

    def test_every_component_and_side_checked_for_identity_drift(self):
        for index in (0, 1, 2):
            for side in ('cms', 'carrier'):
                with self.subTest(index=index, side=side):
                    values = [record(str(i), str(i)) for i in range(3)]
                    values[index][side]['identity'].update(contract='H0000', plan='001', segment='000')
                    with self.assertRaisesRegex(ValueError, 'offering_scope_mismatch'):
                        adapters.normalize_task(bundle(*values))
        with self.assertRaisesRegex(ValueError, 'offering_scope_mismatch'):
            adapters.normalize_task(record(), offering_id=OTHER)

    def test_bundle_original_scope_cannot_drop_or_invent_roots(self):
        for ids in (['A'], ['A', 'B', 'invented']):
            value = bundle(record('a', 'A'), record('b', 'B')); value['original_ids'] = ids
            with self.assertRaisesRegex(ValueError, 'original_scope_mismatch'):
                adapters.normalize_task(value)
        value['original_ids'] = ['B', 'A']
        self.assertEqual(adapters.normalize_task(value)['original_ids'], ['B', 'A'])

    def test_duplicate_components_are_not_silently_dropped(self):
        a = record()
        result = adapters.normalize_task(bundle(a, a))
        self.assertEqual(len(result['components']), 2)
        self.assertIn('repeated_component', hold_codes(result))
        b = deepcopy(a); b['carrier']['unit']['period'] = 'month'
        with self.assertRaisesRegex(ValueError, 'component_id_collision'):
            adapters.normalize_task(bundle(a, b))

    def test_empty_nested_or_nonrecord_components_quarantined(self):
        for values in ([], [None], [bundle(record())]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                adapters.normalize_task(bundle(*values))

    def test_whole_record_schema_rejects_extras_and_wrong_dimension_shapes(self):
        for mutate in (
            lambda r: r.update(extra_meaning='must not be silently stripped'),
            lambda r: r['carrier']['service'].update(meaning='forbidden schema field'),
            lambda r: r['carrier']['boundaries'].update(reset={'unsupported': 'wrong type'}),
            lambda r: r['carrier']['cost'].update(amount={'state': 'unknown', 'reason': 'wrong amount shape'}),
        ):
            value = record(); mutate(value)
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'strict_r9_schema_violation'):
                adapters.normalize_task(value)

    def test_guard_source_placeholder_stays_held_even_when_both_sides_match(self):
        value = record()
        for side in ('cms', 'carrier'):
            value[side]['context']['network'] = 'source_default_network'
        task = adapters.normalize_task(value)
        self.assertEqual(task['components'][0], value)
        self.assertEqual(task['comparison_checks'][0]['actual_r9_result']['outcome'], 'insufficient_evidence')
        self.assertIn('comparison_not_complete', hold_codes(task))
        self.assertIn('stored_outcome_mismatch', hold_codes(task))

    def test_unknown_conditions_and_nulls_are_not_zero_or_no(self):
        value = record()
        value['carrier']['cost'] = {'state': 'unresolved', 'reason': 'Unknown financial applicability'}
        value['carrier']['conditions']['authorization']['state'] = 'unknown'
        value['carrier']['boundaries'] = None
        task = adapters.normalize_task(value)
        self.assertEqual(task['components'][0]['carrier']['cost'], value['carrier']['cost'])
        self.assertIsNone(task['components'][0]['carrier']['boundaries'])
        self.assertIn('unresolved_source_meaning', hold_codes(task))
        self.assertEqual(task['comparison_checks'][0]['actual_r9_result']['outcome'], 'insufficient_evidence')

    def test_strict_decimal_numbers_keep_numeric_type_and_exact_legacy_fingerprint(self):
        value = record()
        for side in ('cms', 'carrier'):
            value[side]['cost']['amount'] = Decimal('0.125')
        task = adapters.normalize_task(value)
        self.assertEqual(task['components'][0]['carrier']['cost']['amount'], 0.125)
        self.assertIsInstance(task['components'][0]['carrier']['cost']['amount'], float)
        self.assertEqual(task['comparison_checks'][0]['actual_r9_result']['outcome'], 'exact_agreement')
        self.assertTrue(all(x['encoding'] == 'exact_json_number' for x in task['decimal_encoding']))
        original_numbers = deepcopy(value)
        for side in ('cms', 'carrier'):
            original_numbers[side]['cost']['amount'] = 0.125
        self.assertEqual(json.dumps(task['components'][0], sort_keys=True), json.dumps(original_numbers, sort_keys=True))
        string_input = deepcopy(value)
        for side in ('cms', 'carrier'):
            string_input[side]['cost']['amount'] = '0.125'
        string_task = adapters.normalize_task(string_input)
        self.assertNotEqual(task['input_fingerprint'], string_task['input_fingerprint'])
        self.assertEqual(task['task_id'], string_task['task_id'])
        self.assertIsInstance(value['carrier']['cost']['amount'], Decimal)

    def test_strict_unrepresentable_decimal_quarantines_without_string_laundering(self):
        value = record()
        value['carrier']['evidence'][0]['location']['confidence'] = Decimal('0.1000000000000000000000000001')
        with self.assertRaisesRegex(ValueError, 'strict_decimal_not_roundtrippable'):
            adapters.normalize_task(value)
        value = record()
        value['carrier']['unit']['period'] = Decimal('0.5')
        with self.assertRaisesRegex(ValueError, 'strict_r9_schema_violation'):
            adapters.normalize_task(value)

    def test_source_artifact_decimal_keeps_full_precision_and_explicit_type_proof(self):
        amount = Decimal('0.1000000000000000000000000100')
        task = adapters.normalize_task(native(amount))
        self.assertEqual(task['source_artifacts'][0]['literal_value'], str(amount))
        self.assertEqual(task['source_artifacts'][0]['literal_value_type'], 'Decimal')
        self.assertTrue(all(x['encoding'] == 'exact_decimal_string' for x in task['decimal_encoding']))
        self.assertNotEqual(task['input_fingerprint'], adapters.normalize_task(native(str(amount)))['input_fingerprint'])
        json.dumps(task, allow_nan=False)

    def test_float_monetary_and_nonfinite_values_quarantined(self):
        value = record(); value['carrier']['cost']['amount'] = 0.1
        with self.assertRaisesRegex(ValueError, 'inexact_monetary_type'):
            adapters.normalize_task(value)
        for bad in (float('nan'), float('inf'), Decimal('NaN'), Decimal('Infinity')):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, 'nonfinite_number'):
                adapters.normalize_task(native(bad))
        value = record(); value['carrier']['boundaries']['day_bands'] = [
            {'begin': 1, 'end': 2, 'amount': 0.1, 'unit': 'USD/day'}]
        with self.assertRaisesRegex(ValueError, 'inexact_monetary_type'):
            adapters.normalize_task(value)

    def test_no_acceptance_inheritance_or_input_mapping_execution(self):
        value = record(); value['accepted_for_reference'] = True
        with self.assertRaisesRegex(ValueError, 'strict_r9_schema_violation'):
            adapters.normalize_task(value)
        envelope = bundle(record()); envelope.update(accepted_for_reference=True, consumer_usable=True,
                                                    mapping_registry={'anything': 'accepted_mapping'})
        result = adapters.normalize_task(envelope)
        self.assertFalse(result['accepted_for_reference'])
        self.assertFalse(result['consumer_usable'])
        self.assertFalse(result['components'][0]['accepted_for_reference'])
        self.assertEqual(result['source_artifacts'][0]['raw_record'], envelope)

    def test_provenance_and_period_differences_are_not_normalized_away(self):
        value = record()
        value['cms']['cost'] = {'kind': 'nonmonetary', 'amount': {'state': 'documented_inapplicable', 'evidence_id': 'CMS-proof'}, 'range_basis': 'Exact nonmonetary predicate'}
        value['carrier']['cost'] = deepcopy(value['cms']['cost'])
        value['carrier']['cost']['amount']['evidence_id'] = 'carrier-proof'
        value['carrier']['unit']['period'] = 'month'
        task = adapters.normalize_task(value)
        result = task['comparison_checks'][0]['actual_r9_result']
        self.assertEqual(result['outcome'], 'conflict')
        self.assertEqual(set(result['differences']), {'cost', 'unit'})
        self.assertEqual(task['components'], [value])

    def test_unknown_identity_not_filled_from_caller_scope(self):
        value = record(); value['cms']['identity'] = None; value['carrier']['identity'] = None
        with self.assertRaisesRegex(ValueError, 'offering_scope_unresolved'):
            adapters.normalize_task(value)
        task = adapters.normalize_task(value, offering_id=OFFERING)
        self.assertIsNone(task['components'][0]['carrier']['identity'])
        self.assertIn('component_identity_unresolved', hold_codes(task))
        with self.assertRaisesRegex(ValueError, 'unsupported_offering'):
            adapters.normalize_task(value, offering_id='unpadded')

    def test_no_unpadded_or_wrong_year_identity_coercion(self):
        for value in ('2026:H1045:48:2', '2027:H1045:048:002', True):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'unsupported_offering'):
                adapters.normalize_task(native('1'), offering_id=value)
        value = record(); value['carrier']['identity']['segment'] = '2'
        with self.assertRaisesRegex(ValueError, 'strict_r9_schema_violation'):
            adapters.normalize_task(value)

    def test_complete_price_cell_keeps_entire_cell_context_and_source(self):
        value = cell(unsupported_qualifiers=['Prior treatment history not yet resolved', {'after_cap': 'member liability'}])
        before = deepcopy(value); task = adapters.normalize_task(value)
        self.assertEqual(task['components'], [])
        artifact = task['source_artifacts'][0]
        self.assertEqual(artifact['raw_record'], value)
        self.assertEqual([x['amount_decimal'] for x in artifact['literal_price_tokens']], ['0', '40'])
        self.assertEqual([x['literal_unit'] for x in artifact['literal_price_tokens']], ['$', 'percent'])
        self.assertTrue(all(x['meaning_state'] == 'unresolved' for x in artifact['literal_price_tokens']))
        self.assertIn('whole_price_cell_interpretation_required', hold_codes(task))
        self.assertIn('unsupported_price_qualifier', hold_codes(task))
        self.assertEqual(value, before)
        self.assertFalse(task['accepted_for_reference'])

    def test_partial_and_unknown_cells_do_not_become_zero_or_ready_records(self):
        value = cell(cell_text='Cost depends on your treatment history.', source_complete=False)
        value.pop('condition_context'); value.pop('evidence')
        task = adapters.normalize_task(value)
        self.assertEqual(task['components'], [])
        self.assertEqual(task['source_artifacts'][0]['literal_price_tokens'], [])
        self.assertTrue({'price_cell_partial_or_unstated', 'condition_context_missing',
                         'source_evidence_missing'} <= hold_codes(task))
        value['source_complete'] = 'true'
        with self.assertRaisesRegex(ValueError, 'invalid_source_completeness'):
            adapters.normalize_task(value)
        with self.assertRaisesRegex(ValueError, 'missing_full_price_cell'):
            adapters.normalize_task(cell(cell_text=''))

    def test_literal_prices_keep_sign_precision_and_do_not_guess_malformed_values(self):
        task = adapters.normalize_task(cell(cell_text='-$5.00; USD 0.00000000000001; $1,250.50. 40%; invalid $1,50. and $1e3.'))
        tokens = task['source_artifacts'][0]['literal_price_tokens']
        self.assertEqual([x['amount_decimal'] for x in tokens], ['-5.00', '0.00000000000001', '1250.50', '40'])
        self.assertEqual([x['source_text'] for x in tokens], ['-$5.00', 'USD 0.00000000000001', '$1,250.50', '40%'])

    def test_dollar_glyph_is_not_imputed_to_an_iso_currency(self):
        task = adapters.normalize_task(cell(cell_text='$100; USD 100; 40%'))
        tokens = task['source_artifacts'][0]['literal_price_tokens']
        self.assertEqual([x['literal_unit'] for x in tokens], ['$', 'USD', 'percent'])
        self.assertTrue(all(x['meaning_state'] == 'unresolved' for x in tokens))
        self.assertEqual(task['components'], [])

    def test_native_literals_never_get_global_yes_no_zero_enum_mapping(self):
        fingerprints = []
        for raw in ('1', 1, '0', 0, False, None, ''):
            with self.subTest(raw=raw):
                task = adapters.normalize_task(native(raw))
                artifact = task['source_artifacts'][0]
                self.assertEqual(artifact['literal_value'], raw)
                self.assertEqual(artifact['literal_value_type'], type(raw).__name__)
                self.assertEqual(artifact['meaning_state'], 'unknown')
                self.assertEqual(task['components'], [])
                self.assertIn('native_meaning_unresolved', hold_codes(task))
                fingerprints.append(task['input_fingerprint'])
        self.assertEqual(len(fingerprints), len(set(fingerprints)))

    def test_supplied_native_authority_is_retained_not_executed_or_approved(self):
        authority = {'module': 'os.system', 'function': 'arbitrary', '1': 'Yes', 'accepted_for_reference': True}
        task = adapters.normalize_task(native('1', authority=authority))
        self.assertEqual(task['source_artifacts'][0]['raw_record']['authority'], authority)
        self.assertEqual(task['source_artifacts'][0]['literal_value'], '1')
        self.assertIn('native_authority_requires_review', hold_codes(task))
        self.assertFalse(task['accepted_for_reference'])

    def test_native_pointer_escape_bounds_and_missing_null_distinction(self):
        task = adapters.normalize_task(native(None))
        self.assertIsNone(task['source_artifacts'][0]['literal_value'])
        for pointer in ('/missing', '/a~2b', 'not-a-pointer'):
            value = native(None); value['pointer'] = pointer
            with self.subTest(pointer=pointer), self.assertRaises(ValueError):
                adapters.normalize_task(value)
        value = native(None); value.update(payload=['one'], pointer='/01')
        with self.assertRaisesRegex(ValueError, 'native_pointer_not_found'):
            adapters.normalize_task(value)
        value['pointer'] = '/1'
        with self.assertRaisesRegex(ValueError, 'native_pointer_not_found'):
            adapters.normalize_task(value)
        value['pointer'] = '/0'
        self.assertEqual(adapters.normalize_task(value)['source_artifacts'][0]['literal_value'], 'one')

    def test_native_unicode_and_whitespace_preserved_literally(self):
        text = '  "literal"\t\u0085\u2028\u2029\r\n  '
        task = adapters.normalize_task(native(text))
        self.assertEqual(task['source_artifacts'][0]['literal_value'], text)
        self.assertEqual(task['source_artifacts'][0]['raw_record']['payload']['a/b']['~key'], text)

    def test_invalid_values_cycles_and_dispatch_code_are_quarantined(self):
        cyclic = {}; cyclic['self'] = cyclic
        for value in (None, [], native({1: 'non-string key'}), native(cyclic), native({'set': {1}})):
            with self.subTest(value=type(value).__name__), self.assertRaises(ValueError):
                adapters.normalize_task(value)
        for family in ('os.system', '__import__', None, ['strict_r9']):
            value = native('1'); value['artifact_type'] = family
            with self.subTest(family=family), self.assertRaisesRegex(ValueError, 'unsupported_adapter_family'):
                adapters.normalize_task(value)
        with self.assertRaises(TypeError):
            adapters.ADAPTER_REGISTRY['arbitrary'] = ('arbitrary', lambda *_: {})

    def test_existing_source_gap_transports_full_declaration_without_values(self):
        value = {'artifact_type': 'source_gap', 'id': 'gap-one', 'offering_id': OFFERING,
                 'original_ids': ['ORIGINAL-missing'],
                 'gap': {'required_capability': 'Exact procedure frequency and history rule',
                         'source_access_state': 'not_acquired', 'no_new_gap': True},
                 'evidence': [{'source_sha256': 'e' * 64, 'pointer': '/required/original'}]}
        task = adapters.normalize_task(value)
        self.assertEqual(task['source_artifacts'][0]['raw_record'], value)
        self.assertEqual(task['original_ids'], ['ORIGINAL-missing'])
        self.assertEqual(task['components'], [])
        self.assertTrue(task['research_only'])
        self.assertFalse(task['accepted_for_reference'])
        self.assertFalse(task['consumer_usable'])
        hold = next(h for h in task['holds'] if h['code'] == 'required_source_missing')
        self.assertEqual(hold['category'], 'source')
        self.assertEqual(hold['path'], '/gap')
        self.assertEqual(hold['source_dependencies'], value['evidence'])

    def test_empty_or_invalid_source_gap_is_quarantined(self):
        for gap in ({}, None, [], ''):
            value = {'artifact_type': 'source_gap', 'id': 'gap-one', 'offering_id': OFFERING,
                     'original_ids': ['ORIGINAL-missing'], 'gap': gap}
            with self.subTest(gap=gap), self.assertRaisesRegex(ValueError, 'invalid_source_gap'):
                adapters.normalize_task(value)

    def test_sealed_authority_drift_rejected_even_after_validator_cache_warmup(self):
        adapters.normalize_task(record())
        bad = dict(adapters._AUTHORITY_PINS)
        bad['schema'] = (bad['schema'][0], '0' * 64)
        with patch.object(adapters, '_AUTHORITY_PINS', bad):
            with self.assertRaisesRegex(ValueError, 'sealed_authority_changed'):
                adapters.normalize_task(record())

    def test_guard_unsupported_context_quarantines_without_weakening_sealed_code(self):
        value = record(); value['carrier']['evidence'][0]['location']['state'] = {'original': ['raw']}
        before = deepcopy(value)
        with self.assertRaisesRegex(ValueError, 'sealed_guard_rejected_component'):
            adapters.normalize_task(value)
        self.assertEqual(value, before)

    def test_task_identity_survives_source_change_but_evaluation_inputs_change(self):
        value = cell(); before = adapters.normalize_task(value)
        value['cell_text'] = '$35 after a different qualification'
        after = adapters.normalize_task(value)
        self.assertEqual(before['task_id'], after['task_id'])
        self.assertEqual(before['source_record_id'], 'cell')
        self.assertNotEqual(before['input_fingerprint'], after['input_fingerprint'])
        value['id'] = 'another-source-cell'
        self.assertNotEqual(after['task_id'], adapters.normalize_task(value)['task_id'])

    def test_same_source_task_identity_survives_quarantine_then_valid_input(self):
        value = record(); valid = adapters.normalize_task(value)
        broken = deepcopy(value); broken['carrier']['service']['meaning'] = 'invalid schema extra'
        quarantine_id = adapters.stable_task_id(OFFERING, broken['id'])
        with self.assertRaisesRegex(ValueError, 'strict_r9_schema_violation'):
            adapters.normalize_task(broken)
        self.assertEqual(quarantine_id, valid['task_id'])
        self.assertEqual(valid['task_id'], adapters.normalize_task(value)['task_id'])
        with self.assertRaisesRegex(ValueError, 'unsupported_offering'):
            adapters.stable_task_id('not-an-offering', value['id'])

    def test_null_quantity_field_is_quarantined_by_exact_schema(self):
        value = record(); value['carrier']['boundaries']['quantity'] = None
        with self.assertRaisesRegex(ValueError, 'strict_r9_schema_violation'):
            adapters.normalize_task(value)

    def test_geographic_variant_conflict_preserved_within_same_offering(self):
        value = record(); value['carrier']['identity']['geographic_variant'] = 'Different published variant'
        task = adapters.normalize_task(value)
        self.assertEqual(task['components'], [value])
        self.assertEqual(task['comparison_checks'][0]['actual_r9_result']['outcome'], 'conflict')
        self.assertIn('identity', task['comparison_checks'][0]['actual_r9_result']['differences'])


if __name__ == '__main__':
    unittest.main()
