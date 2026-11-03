"""Detached safety regressions and bounded offline source-layout inspections.

These tests establish no source interpretation, acceptance or pilot completion.
"""
import copy
import gzip
import importlib.util
import json
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'tools/reconcile_whole_offering.py'
spec = importlib.util.spec_from_file_location('r12_reconcile_under_test', MODULE)
r12 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r12)
ROOT = Path(__file__).resolve().parents[3]
PACKET = ROOT / r12.R12


class SourceMeaningTests(unittest.TestCase):
    def test_blank_and_null_cannot_be_zero_or_negative(self):
        self.assertEqual(r12.scalar_state('')['state'], 'source_blank')
        self.assertEqual(r12.scalar_state(None)['state'], 'source_null')
        self.assertFalse(r12.scalar_state('')['negative_or_zero_inferred'])
        self.assertEqual(r12.scalar_state('0.00')['value'], '0.00')

    def test_native_json_is_verified_at_its_exact_pointer(self):
        record = {'raw_sha256': 'test', 'source_row_ordinal': 9, 'raw_payload': {
            'id': 'OBS-test', 'layer': 'cms_json', 'source_id': 'SRC-test', 'unit_id': 'SEM-test',
            'payload': json.dumps({'locator': {'pointer': '/source/bands'},
                                   'raw': ['375.00', '0.00'], 'source_role': 'member_cost_schedule'})}}
        result = r12.interpret_observation(record, {}, {'source': {'bands': ['375.00', '0.00']}})
        self.assertEqual(result['source_meaning']['native_value']['value'], ['375.00', '0.00'])
        changed = {'source': {'bands': ['375.00']}}
        with self.assertRaisesRegex(r12.ReconciliationError, 'pointer/raw mismatch'):
            r12.interpret_observation(record, {}, changed)

    def test_official_table_code_does_not_decode_native_json(self):
        record = {'raw_sha256': 'test', 'source_row_ordinal': 9, 'raw_payload': {
            'id': 'OBS-test', 'layer': 'cms_table', 'source_id': 'SRC-test', 'unit_id': 'SEM-test',
            'payload': json.dumps({'dictionary_question': 'Number of intervals',
                'locator': {'field': 'native_flat_field'}, 'raw': '2',
                'normalized': {'state': 'decoded_code', 'type': 'enum', 'value': 'one interval'}})}}
        result = r12.interpret_observation(record, {}, {})['source_meaning']
        self.assertEqual(result['normalized_answer']['value'], 'one interval')
        self.assertFalse(result['applies_to_native_json'])
        record['raw_payload']['payload'] = json.dumps({'dictionary_question': 'Unknown control',
            'locator': {'field': 'unmapped'}, 'raw': '9', 'normalized': {'state': 'unresolved_code'}})
        result = r12.interpret_observation(record, {}, {})['source_meaning']
        self.assertFalse(result['unknown_code_is_negative'])
        self.assertIn('unresolved', result['interpretation'])

    def test_component_equal_is_not_full_meaning_agreement(self):
        check = {'pointer': '/amount', 'expected_source_component': '375.00',
                 'level': 'component_only', 'complete_meaning_agreement': False}
        result = r12.check_component({'amount': '375.000'}, check)
        self.assertTrue(result['exact_component_equal'])
        self.assertEqual(result['full_meaning_outcome'], 'insufficient_evidence')
        self.assertIsNone(result['reviewed_factual_mapping'])
        with self.assertRaises(r12.ReconciliationError):
            r12.check_component({'amount': ''}, check)
        check['complete_meaning_agreement'] = True
        with self.assertRaises(r12.ReconciliationError):
            r12.check_component({'amount': '375.00'}, check)

    def test_missing_requirement_and_acceptance_cannot_be_promoted(self):
        record = {'accepted_for_reference': False, 'new_acceptance': False,
                  'independent_review': None, 'required_evidence_missing': True,
                  'comparison_outcome': 'insufficient_evidence'}
        r12.assert_review_release(record)
        for field, value in [('comparison_outcome', 'exact_agreement'),
                             ('independent_review', 'invented-review-id'),
                             ('accepted_for_reference', True)]:
            changed = {**record, field: value}
            with self.assertRaises(r12.ReconciliationError):
                r12.assert_review_release(changed)

    def test_base_and_optional_and_category_type_remain_distinct(self):
        case = {'carrier_families': [], 'service_categories': ['base:7f:1']}
        record = {'canonical_id': 'test', 'subject': 'source', 'native_service_contexts': [
            {'variant': 'base', 'category_code': '7f', 'category_type_id': 2}]}
        self.assertFalse(r12.case_matches(case, record))
        record['native_service_contexts'][0]['category_type_id'] = 1
        self.assertTrue(r12.case_matches(case, record))
        record['native_service_contexts'][0]['variant'] = 'optional_rider:001'
        self.assertFalse(r12.case_matches(case, record))

    def test_ocr_words_keep_exact_character_positions_and_boxes(self):
        words = [dict(block_num=1, par_num=1, line_num=1, word_num=1,
            left=90, top=50, width=15, height=12, text='$0', conf=91),
            dict(block_num=2, par_num=1, line_num=1, word_num=1,
            left=600, top=51, width=20, height=12, text='40%', conf=92)]
        lines = r12.ocr_lines(words)
        self.assertEqual(len(lines), 1)
        for word in lines[0]['words']:
            self.assertEqual(lines[0]['text'][word['start']:word['end']], word['text'])
        self.assertEqual(lines[0]['words'][1]['left'], 600)

    def test_day_endpoint_repair_preserves_original_raw_value_and_no_enum_transfer(self):
        observation = {'id': 'OBS-fixture-day', 'layer': 'cms_table', 'complete_native_payload': {
            'locator': {'field': 'pbp_b1a_copay_ad_endd_int1_t1'},
            'dictionary_question': 'End Day Interval 1', 'raw': '999',
            'normalized': {'state': 'typed_numeric', 'unit': 'USD', 'value': '999'}}}
        result = r12.propose_table_control(observation, [])
        self.assertEqual(result['source_type_correction']['proposed_unit'], 'day_index')
        self.assertEqual(result['source_type_correction']['new_value'], '999')
        self.assertEqual(result['original_normalized_answer']['unit'], 'USD')
        self.assertFalse(result['source_type_correction']['numeric_value_changed'])
        self.assertFalse(result['native_JSON_code_mapping_applied'])
        self.assertFalse(result['complete_meaning_agreement'])

    def test_day_index_correction_cannot_be_applied_to_currency_or_native_json(self):
        observation = {'id': 'OBS-fixture-money', 'layer': 'cms_table', 'complete_native_payload': {
            'locator': {'field': 'pbp_b1a_copay_mcs_amt_int1_t1'},
            'dictionary_question': 'Copayment Amt Interval 1', 'raw': '375.00',
            'normalized': {'state': 'typed_numeric', 'unit': 'USD', 'value': '375.00'}}}
        self.assertIsNone(r12.propose_table_control(observation, [])['source_type_correction'])
        observation['layer'] = 'cms_json'
        with self.assertRaisesRegex(r12.ReconciliationError, 'original table'):
            r12.propose_table_control(observation, [])

    def test_repair_rejects_changed_source_word_binding_or_missing_textual_anchor(self):
        cell = {'source_text_candidate': 'Provider approval is required.',
                'source_words': [{'ordinal': 1, 'text': 'Provider'}]}
        cell['full_source_word_binding_sha256'] = r12.digest(cell['source_words'])
        proposal = {'kind': 'condition', 'key': 'FIXTURE-PA',
            'statement': 'Provider approval is required.', 'independent_review': None,
            'accepted_for_reference': False, 'source_cell_ids': ['cell'],
            'exact_source_anchors': ['approval is required']}
        r12.validate_atomic_source_proposal(proposal, {'cell': cell})
        changed = copy.deepcopy(cell); changed['source_words'][0]['text'] = 'Never'
        with self.assertRaisesRegex(r12.ReconciliationError, 'word binding'):
            r12.validate_atomic_source_proposal(proposal, {'cell': changed})
        proposal['exact_source_anchors'] = []
        with self.assertRaisesRegex(r12.ReconciliationError, 'textual anchors'):
            r12.validate_atomic_source_proposal(proposal, {'cell': cell})

    def test_exact_control_rule_cannot_invent_independent_review(self):
        observation = {'id': 'OBS-fixture-control', 'layer': 'cms_table', 'complete_native_payload': {
            'locator': {'field': 'pbp_b2_hosp_ben_period'}, 'dictionary_question': 'What is your SNF benefit period?',
            'raw': '1', 'normalized': {'state': 'decoded_code', 'value': 'Original Medicare'}}}
        rule = {'exact_field_patterns': ['pbp_b2_hosp_ben_period'], 'independent_review': 'invented',
                'accepted_for_reference': False}
        with self.assertRaisesRegex(r12.ReconciliationError, 'invent review'):
            r12.propose_table_control(observation, [rule])


class OfflineLayoutInspections(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = PACKET / 'layout-defect-census-r2/corrected-medical-source-cells.jsonl.gz'
        if not path.is_file():
            raise unittest.SkipTest('Unaccepted new r12 source-layout artifact not present')
        with gzip.open(path, 'rt') as stream:
            cls.cells = [json.loads(line) for line in stream]

    def test_psychiatric_and_acute_parent_cells_do_not_merge_schedules(self):
        def text(scope, column):
            return next(row['source_text_candidate'] for row in self.cells
                        if row['source_scope']['source_scope_key'] == scope and row['source_column'] == column)
        acute = text('EOC-068-0636', 'cost_in_network')
        psychiatric = text('EOC-071-0652', 'cost_in_network')
        self.assertIn('days 1 to 7', acute)
        self.assertNotIn('days 1 to 6', acute)
        self.assertIn('days 1 to 6', psychiatric)
        self.assertIn('60 lifetime reserve days', psychiatric)
        self.assertNotIn('Outpatient observation', psychiatric)

    def test_merged_hearing_cell_retains_complete_vendor_rule(self):
        cells = [row for row in self.cells if row['source_scope']['source_scope_key'] == 'EOC-063-0263']
        cost = next(row for row in cells if row['source_column'] == 'merged_cost_columns')
        text = cost['source_text_candidate']
        self.assertIn('You must obtain prior authorization from UnitedHealthcare Hearing.', text)
        self.assertIn('Hearing aids purchased outside of UnitedHealthcare Hearing are not covered.', text)
        self.assertFalse(any(row['source_column'] in {'cost_in_network', 'cost_out_of_network'} for row in cells))
        self.assertTrue(cost['merged_column_native_span_evidence'])

    def test_corrected_parent_cells_cannot_claim_atomic_or_semantic_completion(self):
        for row in self.cells:
            self.assertFalse(row['atomic_proposition'])
            self.assertFalse(row['printed_meaning_review_complete'])
            self.assertFalse(row['accepted_for_reference'])
            self.assertEqual(row['full_source_word_binding_sha256'], r12.digest(row['source_words']))

    def test_medical_repair_costs_keep_condition_dependencies_and_missing_denominator(self):
        path = PACKET / 'medical-atomic-repairs-r1/proposed-atomic-units.jsonl.gz'
        with gzip.open(path, 'rt') as stream:
            units = {row['key']: row for row in map(json.loads, stream)}
        keys = set(units['ACUTE-IN-BANDS']['condition_keys'])
        self.assertTrue({'ACUTE-RESET', 'ACUTE-ADMISSION', 'ACUTE-UNLIMITED',
                         'ACUTE-POSTSTABLE', 'ACUTE-TRANSPLANT'}.issubset(keys))
        self.assertNotIn('PSYCH-190', keys)
        self.assertIn('ROUTINE-FOOT-6', units['ROUTINE-FOOT-IN']['condition_keys'])
        for unit in units.values():
            for key in unit['condition_keys']:
                self.assertEqual(units[key]['kind'], 'condition')
                self.assertIn(units[key]['id'], unit['condition_ids'])
            self.assertFalse(unit['accepted_for_reference'])
            self.assertFalse(unit['complete_meaning_reconciliation_complete'])
        receipt = r12.load(PACKET / 'medical-atomic-repairs-r1/ATOMIC_REPAIR_RECEIPT.json')
        self.assertEqual(receipt['after']['original_ids_preserved'], 4675)
        self.assertEqual(receipt['after']['original_ids_retired'], 0)
        self.assertEqual(receipt['after']['required_missing_unchanged'], 16)


class ComponentAndSourceBoundaryTests(unittest.TestCase):
    def test_full_width_instruction_replay_uses_exact_ordered_union(self):
        with gzip.open(PACKET / 'layout-defect-census-r2/corrected-medical-source-cells.jsonl.gz', 'rt') as stream:
            cells = [r for r in map(json.loads, stream) if r['source_scope']['source_scope_key'] == 'EOC-044-0250']
        result = r12.combine_full_width_source_parent(cells, 'EOC-044-0250')
        self.assertEqual(result['source_column'], 'full_width_paragraph')
        self.assertFalse(result['atomic_proposition'])
        self.assertEqual(result['source_word_count'], sum(len(r['source_words']) for r in cells))
        self.assertIn('more than one service', result['source_text_candidate'].lower())
        with self.assertRaisesRegex(r12.ReconciliationError, 'Duplicate'):
            r12.combine_full_width_source_parent([cells[0], cells[0], cells[2]], 'EOC-044-0250')
        with self.assertRaisesRegex(r12.ReconciliationError, 'Only the reviewed'):
            r12.combine_full_width_source_parent(cells, 'ordinary-hospital-row')

    def test_sb_preventive_lists_do_not_merge_wellness_and_colorectal(self):
        with gzip.open(PACKET / 'sb-source-repairs-r2/proposed-SB-source-units.jsonl.gz', 'rt') as stream:
            units = {r['key']: r for r in map(json.loads, stream)}
        wellness = units['SB-PREVENTIVE-LIST-WELLNESS']; colorectal = units['SB-PREVENTIVE-LIST-COLORECTAL']
        self.assertIn('Annual wellness visit', wellness['exact_source_text_in_region_reading_order'])
        self.assertNotIn('colorectal', wellness['exact_source_text_in_region_reading_order'].lower())
        self.assertIn('Colorectal', colorectal['exact_source_text_in_region_reading_order'])
        self.assertNotEqual(wellness['source_word_binding_sha256'], colorectal['source_word_binding_sha256'])
        self.assertEqual(sum(u['semantic_obligation_candidate'] for u in units.values()), 82)
        self.assertEqual(sum(u['kind'] == 'source_context' for u in units.values()), 3)

    def test_native_range_mode_is_not_a_transferred_flat_enum(self):
        cms = {'pbp': [{'benefitDetails': {'benefitDetailsInfo': [{'categoryCode': 'x', 'categoryTypeId': 1,
            'benefitDetails': {'CopaymentComponent': {'bdCopaymentAmountYesNoMinMax': '3',
                'bdCopayAmountMin': '0.00', 'bdCopayAmountMax': '65.00'}}}]}}]}
        pointer = '/pbp/0/benefitDetails/benefitDetailsInfo/0/benefitDetails/CopaymentComponent/bdCopaymentAmountYesNoMinMax'
        obs = {'id': 'OBS-fictional', 'layer': 'cms_json', 'complete_native_payload': {'locator': {'pointer': pointer}, 'raw': '3', 'source_role': 'member_cost_schedule'}}
        rules = {'bdCopaymentAmountYesNoMinMax': {'kind': 'component_cost_mode', 'source_interpretation': 'fixture',
                  'proposed_modes': {'1': 'scalar', '2': 'not_selected', '3': 'range'}}}
        result = r12.interpret_native_control(obs, cms, rules, {})
        self.assertEqual(result['producer_proposed_typed_meaning']['proposed_mode'], 'range')
        self.assertFalse(result['official_native_enum_dictionary_supplied'])
        self.assertFalse(result['accepted_for_reference'])
        self.assertEqual(result['specific_mapping_holds'], [])
        cms['pbp'][0]['benefitDetails']['benefitDetailsInfo'][0]['benefitDetails']['CopaymentComponent']['bdCopayAmountMax'] = ''
        result = r12.interpret_native_control(obs, cms, rules, {})
        self.assertIn('SELECTED_RANGE_MODE_HAS_MISSING_ENDPOINT', result['specific_mapping_holds'])

    def test_pos_reference_requires_exact_unique_uuid_not_similar_cost(self):
        first = {'groupId': 'a', 'groupNameControl': 'groupA', 'copaymentFG': {'amount': '40'}}
        second = {'groupId': 'b', 'groupNameControl': 'groupB', 'copaymentFG': {'amount': '40'}}
        cms = {'pbp': [{'costShareGroups': {'pointOfServiceGroups': {'pointOfServiceGroupsDetails': {'posGroupsData': [first, second]}}}}]}
        result = r12.exact_pos_group(cms, 'b')
        self.assertTrue(result['source_pointer'].endswith('/1'))
        self.assertEqual(result['complete_native_group'], second)
        self.assertFalse(result['shared_dollar_allowance_inferred'])
        self.assertFalse(result['ordinary_unrestricted_OON_inferred'])
        with self.assertRaisesRegex(r12.ReconciliationError, 'missing or duplicated'):
            r12.exact_pos_group(cms, 'missing')
        cms['pbp'][0]['costShareGroups']['pointOfServiceGroups']['pointOfServiceGroupsDetails']['posGroupsData'].append(second)
        with self.assertRaisesRegex(r12.ReconciliationError, 'missing or duplicated'):
            r12.exact_pos_group(cms, 'b')

    def test_context_specific_native_field_roles_do_not_follow_misleading_names(self):
        with gzip.open(PACKET / 'clinical-native-format-review-r2/clinical-native-format-reviews.jsonl.gz', 'rt') as stream:
            records = list(map(json.loads, stream))
        ambulance = [r for r in records if r['native_service_context']['categoryCode'] == '10a'
                     and r['source_field'] in {'admissionWaivedYesNo', 'admittedHopsitalYesNo'}]
        self.assertEqual(len(ambulance), 3)
        for r in ambulance:
            expected = 'financial_component_present' if r['source_field'] == 'admissionWaivedYesNo' else 'financial_component_waived_on_hospital_admission'
            self.assertEqual(r['producer_proposed_typed_meaning']['question_role'], expected)
        cap = next(r for r in records if r['source_field'] == 'bdMaxPerVisitAmount')
        self.assertIn('month', cap['producer_proposed_typed_meaning']['unit'].lower())
        differences = [r for r in records if 'PAIRED_NATIVE_FLAT_CODES_DIFFER_REQUIRES_SOURCE_SCOPE_REVIEW' in r['specific_mapping_holds']]
        self.assertEqual(len(differences), 7)
        for r in differences:
            self.assertFalse(r['complete_meaning_reconciliation_complete'])
            self.assertFalse(r['accepted_for_reference'])
            self.assertTrue(any(not q['literal_codes_equal'] for q in r['same_category_flat_question_candidates']))

    def test_complete_footer_retains_alternative_populations_and_modal_not_zero(self):
        meanings = {r['id']: r for r in r12.load(PACKET / 'repeated-footer-source-repairs-r1/proposed-footer-meaning-units.json')}
        claim = meanings['R12-FOOTER-MAY-REDUCE']
        self.assertEqual(claim['applicability']['any_of'], ['R12-FOOTER-QMB', 'R12-FOOTER-MEDICAID'])
        self.assertEqual(claim['applicability']['modal'], 'may')
        self.assertFalse(claim['reduced_price_or_zero_inferred'])
        with gzip.open(PACKET / 'repeated-footer-source-repairs-r1/complete-footer-source-parents.jsonl.gz', 'rt') as stream:
            parents = list(map(json.loads, stream))
        self.assertEqual(len(parents), 69)
        for parent in parents:
            self.assertEqual(parent['source_word_binding_sha256'], r12.digest(parent['exact_source_words']))
            self.assertIn('(QMB) or have full Medicaid benefits', parent['complete_full_width_paragraph_text'])
            self.assertIn('may be less', parent['complete_full_width_paragraph_text'])
            self.assertTrue(parent['source_parent_not_atomic_obligation'])
        receipt = r12.load(PACKET / 'repeated-footer-source-repairs-r1/FOOTER_REPAIR_RECEIPT.json')
        self.assertEqual(receipt['retained_old_truncated_clauses'], 138)
        self.assertEqual(receipt['new_required_adopted'], 0)
        self.assertFalse(receipt['canonical_novelty_or_deduplication_decided'])

    def test_global_binding_requires_both_section_and_page_and_preserves_bad_heading(self):
        readings = r12.load(PACKET / 'clinical-global-source-readings-r1.json')['readings']
        record = {'canonical_id': 'fictional-source', 'material_source_context': {'source_section': 'Section 5.2 Payment for routine care'},
                  'source_pages': [{'document_kind': 'EOC', 'physical_page': 35}]}
        result = r12.global_source_readings(record, readings)
        self.assertEqual([r['id'] for r in result], ['R12-GLOBAL-TRIAL-PAYMENT'])
        self.assertTrue(any('hypothetical example' in text for text in result[0]['producer_source_readings']))
        record['source_pages'][0]['physical_page'] = 104
        self.assertEqual(r12.global_source_readings(record, readings), [])
        record.update(canonical_id='CANONICAL-abc4bb27415965a163b0791c7d19',
                      material_source_context={'source_section': 'Section 7.2 Rules for oxygen equipment'},
                      source_pages=[{'document_kind': 'EOC', 'physical_page': 39}])
        self.assertEqual(r12.global_source_readings(record, readings), [])


if __name__ == '__main__':
    unittest.main()
