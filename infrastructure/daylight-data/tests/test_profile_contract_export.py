"""Integrity checks for exported definitions and actual parent/capability bindings."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('profile_contract_export', ROOT / 'infrastructure/daylight-data/tools/export_profile_contract.py')
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


class ProfileContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((ROOT / 'infrastructure/daylight-data/config/profile-contract.2026.json').read_text())

    def test_exact_export_is_reproducible_and_source_bound(self):
        self.assertEqual(self.contract, exporter.build_export())
        value = copy.deepcopy(self.contract)
        claimed = value.pop('content_sha256')
        self.assertEqual(claimed, hashlib.sha256(exporter.canonical_bytes(value)).hexdigest())

    def test_children_and_variants_reuse_their_actual_parent_fields(self):
        questions = {x['id']: x for x in self.contract['questions']}
        expected = {'RC11.C1': ('RC11', 'readiness.facts.RC11.value.coverageEnd'), 'RC16.C1': ('RC16', 'readiness.facts.RC16.value.start'), 'RC16.C2': ('RC16', 'readiness.facts.RC16.value.priorMedigap')}
        self.assertEqual({x['id']: (x['parent'], x['fields'][0]) for x in self.contract['child_aliases']}, expected)
        for row in self.contract['clarification_variants']:
            self.assertIn(row['parent'], questions)
            self.assertTrue(set(row['fields']) <= set(questions[row['parent']]['fields']))
        self.assertEqual(len(questions), 41)
        self.assertEqual(len(self.contract['fields']), 78)
        self.assertEqual(len(self.contract['representation_gaps']), 14)
        self.assertEqual(len(self.contract['clarification_variants']), 11)

    def test_report_metadata_cannot_claim_verification_or_enable_recommendations(self):
        self.assertFalse(self.contract['customer_rows_included'])
        self.assertFalse(self.contract['mandatory_interview_added'])
        self.assertFalse(self.contract['personal_recommendations_enabled'])
        self.assertFalse(self.contract['existing_runtime_policy']['personalizedRecommendationEnabled'])
        for field in self.contract['field_envelope_definitions'].values():
            self.assertIsNone(field['value']);self.assertFalse(field['verified'])
        for question in self.contract['questions']:
            self.assertFalse(question['unknownDeferredSatisfiesRequired'])
        self.assertNotIn('guide', self.contract);self.assertNotIn('readiness', self.contract)


if __name__ == '__main__':
    unittest.main()
