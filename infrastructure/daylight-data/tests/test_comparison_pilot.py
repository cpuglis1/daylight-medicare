"""Adversarial checks for research preparation, with no DB, network or AI."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / 'infrastructure/daylight-data/tools/comparison_pilot.py'
specification = importlib.util.spec_from_file_location('comparison_pilot', SCRIPT)
pilot = importlib.util.module_from_spec(specification)
specification.loader.exec_module(pilot)


def row(identifier, *, kind='claim', context=None, offering=pilot.OFFERING):
    return {'id': identifier, 'kind': kind, 'context': context or {},
            'offering_id': offering, 'accepted_for_reference': False,
            'states': ['evidence_reconciliation_pending'], 'detail': {}}


def inventory_digest(rows):
    return hashlib.sha256(pilot.canonical(rows).encode()).hexdigest()


class ComparisonPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = pilot.load(ROOT / pilot.PACKET / 'pilot-spec.json')
        cls.cms = pilot.load(ROOT / pilot.PACKET / 'generated/CMS-native-deductible.json')
        cls.pages = pilot.carrier_pages(ROOT)
        cls.selected = pilot.load(ROOT / pilot.PACKET / 'generated/selected-canonical.json')

    def test_amount_agreement_does_not_close_complete_meaning(self):
        result = pilot.component_comparisons(self.cms, self.spec)
        self.assertTrue(result['nominal_amount']['decimal_equal'])
        self.assertTrue(result['category_set_equal'])
        self.assertEqual(result['full_meaning_outcome'], 'insufficient_evidence')
        self.assertFalse(result['accepted_for_reference'])

    def test_wrong_exact_scope_cannot_become_component_agreement(self):
        for key, value in [('offering_id', '2027:H5652:002:000'), ('network', 'out_of_network'),
                           ('currency', 'EUR'), ('period', 'month'), ('variant', 'optional_rider')]:
            with self.subTest(key=key):
                spec = copy.deepcopy(self.spec)
                spec['carrier_transcription'][key] = value
                with self.assertRaises(pilot.PilotError):
                    pilot.component_comparisons(self.cms, spec)

    def test_missing_category_and_wrong_amount_stay_unaligned(self):
        spec = copy.deepcopy(self.spec)
        del spec['carrier_transcription']['category_mapping']['2']
        self.assertFalse(pilot.component_comparisons(self.cms, spec)['category_set_equal'])
        spec['carrier_transcription']['amount'] = '100'
        result = pilot.component_comparisons(self.cms, spec)
        self.assertFalse(result['no_conflict_found_in_compared_components'])
        self.assertFalse(result['accepted_for_reference'])

    def test_null_is_retained_without_inference_of_zero_or_no(self):
        before = copy.deepcopy(self.cms)
        result = pilot.component_comparisons(self.cms, self.spec)
        self.assertIsNone(self.cms['outOfNetworkDedAmount'])
        self.assertEqual(self.cms['hasOutOfNetworkDed'], '2')
        self.assertEqual(result['carrier_out_of_network_literal'], 'No deductible')
        self.assertEqual(before, self.cms)
        self.assertEqual(len(result['selected_CMS_categories']), 6)

    def test_float_or_nonfinite_CMS_amount_never_agrees(self):
        for amount in [1000.0, 'NaN', 'Infinity']:
            cms = copy.deepcopy(self.cms)
            cms['inNetworkDedAmount'] = amount
            result = pilot.component_comparisons(cms, self.spec)
            self.assertFalse(result['no_conflict_found_in_compared_components'])

    def test_complete_meaning_contract_refuses_the_actual_unreviewed_pair(self):
        result = pilot.compare_with_sealed_contract(ROOT, self.spec['structured_observations'])
        self.assertEqual(result['outcome'], 'insufficient_evidence')
        self.assertFalse(result['accepted_for_reference'])
        for family in pilot.FAMILIES:
            self.assertEqual(self.spec['structured_observations']['carrier']['conditions'][family]['state'], 'unresolved')

    def test_exceptions_keep_subtype_and_Medicare_FQHC_qualifier(self):
        exceptions = self.spec['carrier_transcription']['exceptions']
        colonoscopy = next(e for e in exceptions if e['predicate'] == 'diagnostic_colonoscopy')
        self.assertEqual(set(colonoscopy['categories']), {'9a1', '9b'})
        self.assertIn('Medicare_covered_service_at_FQHC', {e['predicate'] for e in exceptions})
        self.assertFalse(self.spec['carrier_transcription']['blind_independent_source_review_complete'])
        self.assertTrue(self.spec['condition_logic']['no_personal_evaluation'])

    def test_selected_complete_CMS_schedule_not_neighboring_MOOP(self):
        a = row('A', context={'source_container': pilot.CMS_PREFIX + '/deductible_schedule/in_network'})
        b = row('B', context={'source_container': '/pbp/0/planLevelCostSharing/maxEnrolleeCostLimit'})
        self.assertIsNotNone(pilot.select_reason(a, {}))
        self.assertIsNone(pilot.select_reason(b, {}))

    def test_whole_EOC_section_cannot_drop_a_condition_sibling(self):
        a = row('A', context={'source_section': 'Section 1.2 Our plan deductible',
                              'complete_source_proposition_scope': 'same-parent'})
        b = row('B', kind='condition', context={'complete_source_proposition_scope': 'same-parent'})
        with self.assertRaisesRegex(pilot.PilotError, 'sibling'):
            pilot.inventory(iter([a, b]), {}, inventory_digest([a, b]))

    def test_census_preserves_nonselected_and_other_offering_obligations(self):
        rows = [row('A', context={'source_section': 'Section 1.2 Our plan deductible'}),
                row('B', kind='condition'), row('C', offering='2026:H0000:001:000')]
        selected, ledger, census = pilot.inventory(iter(rows), {}, inventory_digest(rows))
        self.assertEqual(len(selected), 1)
        self.assertEqual(len(ledger), 2)
        self.assertEqual(census['required'], {'claim': 2, 'condition': 1})
        self.assertFalse(ledger[1]['tranche_selected'])

    def test_changed_denominator_duplicate_or_acceptance_is_rejected(self):
        rows = [row('A')]
        with self.assertRaises(pilot.PilotError):
            pilot.inventory(iter(rows), {}, '0' * 64)
        with self.assertRaises(pilot.PilotError):
            pilot.inventory(iter(rows + rows), {}, inventory_digest(rows + rows))
        rows[0]['accepted_for_reference'] = True
        with self.assertRaises(pilot.PilotError):
            pilot.inventory(iter(rows), {}, inventory_digest(rows))

    def test_quote_hash_and_line_bounds_are_enforced(self):
        page = {'text': 'Header\nFirst\nSecond', 'text_sha256': 'native-page', 'layout_text_sha256': 'native-layout'}
        quote = {'document_sha256': 'source', 'pdf_page': 1, 'line_start': 2, 'line_end': 3,
                 'quote_sha256': hashlib.sha256(b'First\nSecond').hexdigest()}
        result = pilot.exact_quotes({('source', 1): page}, {'quote_spans': [quote]})
        self.assertEqual(result[0]['quote'], 'First\nSecond')
        quote['line_end'] = 4
        with self.assertRaises(pilot.PilotError):
            pilot.exact_quotes({('source', 1): page}, {'quote_spans': [quote]})
        quote['line_end'], quote['quote_sha256'] = 3, '0' * 64
        with self.assertRaises(pilot.PilotError):
            pilot.exact_quotes({('source', 1): page}, {'quote_spans': [quote]})

    def test_exclusive_outputs_preserve_prior_receipts_and_sealed_parent(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'packet'
            pilot.write_outputs(output, {'proof.json': {'accepted': False}}, ROOT)
            before = (output / 'proof.json').read_bytes()
            with self.assertRaises(FileExistsError):
                pilot.write_outputs(output, {'proof.json': {'accepted': True}}, ROOT)
            self.assertEqual((output / 'proof.json').read_bytes(), before)
        with self.assertRaises(pilot.PilotError):
            pilot.write_outputs(ROOT / pilot.BASE / 'forbidden-new-child', {}, ROOT)

    def test_actual_native_lineage_reconstructs_assertions_parents_and_list_qualifiers(self):
        result, _ = pilot.native_lineage(ROOT, self.selected, self.pages, self.cms)
        self.assertEqual(result['observations'], 81)
        self.assertEqual(result['sources'], 19)
        self.assertEqual(result['clauses_and_logical_parents_reconstructed'], 31)
        self.assertEqual(result['relationship_edges_preserved'], 48)
        self.assertEqual(result['CMS_original_pointer_values_verified'], 14)
        self.assertEqual(result['inherited_list_quotes_reconstructed'], 7)
        self.assertFalse(result['condition_semantics_verified'])
        self.assertFalse(result['new_acceptance'])

    def test_native_payload_tamper_and_forged_authority_fail_closed(self):
        original = pilot.load
        for mode in ['raw_payload', 'authority']:
            with self.subTest(mode=mode):
                def changed(path):
                    value = original(path)
                    if path.name == 'native_observations.json':
                        if mode == 'raw_payload':
                            value[0]['records'][0]['raw_payload']['source_id'] = 'different-source'
                        else:
                            value[0]['authority']['recommendation']['state'] = 'permitted'
                    return value
                with patch.object(pilot, 'load', side_effect=changed), self.assertRaises(pilot.PilotError):
                    pilot.native_lineage(ROOT, self.selected, self.pages, self.cms)

    def test_native_projection_rejects_range_or_passage_corruption(self):
        body = 'First\nSecond'
        fragment = {'start': 0, 'end': 5, 'locator': {'document_sha256': 'source',
            'pdf_page': 1, 'line_start': 1, 'line_end': 2,
            'view_sha256': hashlib.sha256(body.encode()).hexdigest(),
            'passage_sha256': hashlib.sha256(body.encode()).hexdigest()}}
        pages = {('source', 1): {'layout_text': body}}
        self.assertEqual(pilot.source_projection([fragment], pages), 'First')
        fragment['end'] = 999
        with self.assertRaises(pilot.PilotError):
            pilot.source_projection([fragment], pages)
        fragment['end'], fragment['locator']['passage_sha256'] = 5, '0' * 64
        with self.assertRaises(pilot.PilotError):
            pilot.source_projection([fragment], pages)

    def test_assistance_context_quote_keeps_the_complete_qualification_paragraph(self):
        quotes = pilot.exact_quotes(self.pages, self.spec)
        quote = next(r['quote'] for r in quotes if r['id'] == 'EOC-prior-assistance-context')
        self.assertTrue(quote.startswith('Most people'))
        self.assertTrue(quote.endswith('to your provider.'))


if __name__ == '__main__':
    unittest.main()
