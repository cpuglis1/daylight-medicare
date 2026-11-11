"""Exact selected source controls and research-only rule/contact projections."""
import copy
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from daylight_data.adapters import l11, l12, l13, l14, l15
from daylight_data.adapters.common import load_json, sha256_file

ROOT = Path(__file__).resolve().parents[3]
MODULES = {'L11': l11, 'L12': l12, 'L13': l13, 'L14': l14, 'L15': l15}
EXPECTED_ROWS = {'L11': 4578, 'L12': 19521, 'L13': 1097, 'L14': 8170, 'L15': 9}
EXPECTED_SQLITE_TABLES = {
    'L11': {'records': 4531},
    'L12': {'datasets': 29, 'parent_datasets': 20, 'parent_records': 9559, 'records': 9913},
    'L13': {'datasets': 15, 'records': 1082},
    'L14': {'build-r1': {'evidence': 526, 'gaps': 7, 'negative-search': 14, 'paths': 7,
        'pbp-reuse-inventory': 5, 'reconciliations': 11, 'records': 6890, 'reference': 23,
        'restricted-documents': 5, 'rules': 21, 'source-accounting': 3, 'source-anomalies': 7,
        'source-registry': 59, 'state-observations': 2},
        'gap-resolution-r2/build-r2': {'CMS-summary-observation': 15, 'Fenyx-comparisons': 22,
        'Fenyx-documents': 7, 'HCPP-profiles': 4, 'claims': 14, 'evidence': 285,
        'federal-register-amendments': 5, 'federal-register-searches': 3, 'gaps': 7,
        'new-source-registry': 55, 'pbp-section-d': 9, 'public-PDF-inventories': 2,
        'reference': 25, 'source-registry': 114, 'state-observation': 23}},
}


class RuleContactSourceTests(unittest.TestCase):
    def test_exact_controls_and_all_native_payload_fields_survive(self):
        # Stream one source row and its projection at a time, including large
        # parent/current dataset envelopes; never materialize the whole import.
        for layer, module in MODULES.items():
            with self.subTest(layer=layer):
                counts = Counter()
                source_hashes = {}
                entity_ids = set()
                records = 0
                for row in module.iter_records(ROOT):
                    records += 1
                    source_hashes[row.source_path] = row.source_sha256
                    key = row.source_table
                    if layer == 'L14':
                        component = row.source_path[len(l14.BASE) + 1:].rsplit('/', 1)[0]
                        key = (component, key)
                    counts[key] += 1
                    projection = module.project_record(row)
                    self.assertIs(projection.source, row)
                    self.assertNotIn(projection.entity_id, entity_ids)
                    entity_ids.add(projection.entity_id)
                    self.assertTrue(projection.entity_id.startswith(layer + ':'))
                    self.assertEqual(projection.output_acceptance_state, 'research_only')
                    self.assertFalse(projection.fields['adapter_context']['personal_applicability_determined'])
                    self.assertEqual(len(row.source_sha256), 64)
                    self.assertEqual(len(row.derivation_id), 64)
                    if 'payload' in row.raw:
                        native = json.loads(row.raw['payload'], parse_float=Decimal)
                    elif row.source_table in {'source_registry', 'policy_choices'}:
                        native = row.raw['native_value']
                    else:
                        native = row.raw
                    if isinstance(native, dict):
                        for field, value in native.items():
                            self.assertEqual(projection.fields[field], value)
                    else:
                        self.assertEqual(projection.fields['native_value'], native)
                self.assertEqual(records, EXPECTED_ROWS[layer])
                self.assertEqual(len(entity_ids), records)
                if layer in {'L11', 'L12', 'L13'}:
                    for table, count in EXPECTED_SQLITE_TABLES[layer].items():
                        self.assertEqual(counts[table], count)
                elif layer == 'L14':
                    self.assertEqual(dict(counts), {(component, table): count
                        for component, tables in EXPECTED_SQLITE_TABLES[layer].items() for table, count in tables.items()})
                else:
                    self.assertEqual(dict(counts), {'sites': 2, 'sources': 3, 'statewide': 1,
                        'liaison': 1, 'online_request': 1, 'directory_context': 1})
                for path, before in source_hashes.items():
                    self.assertEqual(sha256_file(ROOT / path), before, path)

    def test_l11_exceptions_clocks_jurisdiction_and_omitted_sqlite_sidecars(self):
        selected = {}
        for row in l11.iter_records(ROOT):
            if row.source_table == 'records' and (row.raw['dataset'], row.raw['id']) in {('rules.json', 'R01'), ('clocks.json', 'C01')}:
                selected[row.raw['id']] = l11.project_record(row)
            elif row.source_table in {'policy_choices', 'temporal-reconciliation.json'}:
                selected[row.source_row_key] = l11.project_record(row)
        rule = selected['R01']
        self.assertEqual(rule.fields['jurisdiction'], 'US')
        self.assertEqual(rule.fields['reference_date'], '2026-10-28')
        self.assertTrue(rule.fields['r2_qualified_R16_pending'])
        self.assertEqual(rule.conditions['conditions'], rule.fields['conditions'])
        self.assertIn('relationship_limit', rule.conditions)
        self.assertFalse(selected['C01'].fields['personal_calculation_enabled'])
        self.assertEqual(selected['C01'].fields['end'], 'start_plus_6_calendar_months_exclusive')
        policy = load_json(ROOT / l11.BASE / 'policy-choices.json')
        self.assertEqual({key: selected[key].fields['native_value'] for key in policy}, policy)
        temporal = selected['temporal-reconciliation.json']
        self.assertEqual(temporal.fields['applicability_statement'], load_json(ROOT / l11.BASE / 'temporal-reconciliation.json')['applicability_statement'])

    def test_l12_period_basis_and_parent_revision_are_not_a_personal_award(self):
        wanted = {}
        for row in l12.iter_records(ROOT):
            if row.source_table in {'records', 'parent_records'} and row.raw['dataset'] == 'florida-msp-lis-tables.json' and row.raw['id'] in {'A91-april-Individual', 'A91-interim_january-Individual'}:
                wanted[(row.source_table, row.raw['id'])] = l12.project_record(row)
        april = wanted[('records', 'A91-april-Individual')]
        january = wanted[('records', 'A91-interim_january-Individual')]
        parent = wanted[('parent_records', 'A91-april-Individual')]
        self.assertEqual(april.fields['fields']['QMB'], {'basis': 'countable_income_standard', 'source_status': 'published', 'unit': 'USD/month', 'value': '1330'})
        self.assertEqual(january.fields['fields']['QMB']['value'], '1342')
        self.assertEqual(january.fields['effective_end_exclusive'], april.fields['effective_start'])
        self.assertEqual(april.fields['fields']['LIS_base_resources']['basis'], 'base_resources_before_burial_exclusion')
        qmb = next(x for x in april.fields['adapter_context']['standard_numeric_observations'] if x['native_payload_pointer'] == '/fields/QMB/value')
        self.assertEqual(qmb['value_decimal'], Decimal('1330'))
        self.assertEqual(qmb['source_unit'], 'USD/month')
        self.assertEqual(qmb['source_basis'], 'countable_income_standard')
        self.assertEqual(qmb['source_value_state'], 'published')
        self.assertNotEqual(april.entity_id, parent.entity_id)
        self.assertEqual(parent.fields['adapter_context']['lineage_role'], 'retained_parent')

    def test_l13_rc06_is_source_reconciliation_not_profile_question_rc06(self):
        reconciliation = None
        sep = None
        for row in l13.iter_records(ROOT):
            if row.source_table != 'records':
                continue
            if row.raw['dataset'] == 'reconciliations.json' and row.raw['id'] == 'RC06':
                reconciliation = l13.project_record(row)
            if row.raw['dataset'] == 'regulatory-SEP-inventory.json' and row.raw['id'] == 'D:c:1':
                sep = l13.project_record(row)
        self.assertEqual(reconciliation.entity_id, 'L13:build-r1:records:reconciliations.json:RC06')
        self.assertEqual(reconciliation.fields['adapter_context']['rule_namespace'], 'L13.enrollment')
        self.assertFalse(reconciliation.fields['adapter_context']['profile_question_binding_inferred'])
        self.assertEqual(sep.conditions['parent_conditions'], sep.fields['parent_conditions'])
        self.assertEqual(sep.conditions['source_native_conditions'], sep.fields['source_native_conditions'])
        self.assertEqual(sep.fields['prior_CMS_approval'], 'not_explicitly_stated_in_this_root_check_full_context')
        self.assertFalse(sep.fields['personal_determination_enabled'])

    def test_l14_parent_paths_overlay_claims_and_restrictions_stay_separate(self):
        counts = Counter()
        profiles = {}
        for row in l14.iter_records(ROOT):
            projection = l14.project_record(row)
            counts[projection.entity_type] += 1
            if row.source_table == 'HCPP-profiles':
                profiles[row.raw['id']] = projection
            if row.source_table == 'Fenyx-comparisons':
                self.assertFalse(projection.fields['numeric_agreement_is_design_acceptance'])
                self.assertEqual(projection.conditions['all_source_conditions'], projection.fields['all_source_conditions'])
            if row.source_table == 'negative-search' and row.raw['id'] == 'individual_Cost_source_rows':
                self.assertEqual(projection.fields['native_value'], [])
                self.assertEqual(projection.value_state, 'source_native_context_field')
        self.assertEqual(counts['other_coverage_path'], 7)
        self.assertEqual(counts['other_coverage_additive_claim'], 14)
        self.assertEqual(profiles['H6142'].fields['PDP_interaction'], '2025_UHS_brochure_allows_standalone_PDP')
        self.assertEqual(profiles['H6334'].fields['PDP_interaction'], 'sponsor_warns_retiree_benefit_termination')
        self.assertTrue(all(x.fields['unrestricted_public_enrollment'] is False for x in profiles.values()))
        self.assertTrue(all(x.fields['personal_eligibility'] is None for x in profiles.values()))

    def test_l15_lossless_directory_and_contacts_do_not_become_service_availability(self):
        directory = load_json(ROOT / l15.DIRECTORY)
        recovered = {}
        projections = {}
        for row in l15.iter_records(ROOT):
            projections[(row.source_table, row.source_row_key)] = l15.project_record(row)
            if row.source_table in {'sites', 'sources'}:
                recovered.setdefault(row.source_table, []).append(dict(row.raw))
            elif row.source_table == 'directory_context':
                recovered.update(row.raw)
            else:
                recovered[row.source_table] = dict(row.raw)
        self.assertEqual(recovered, directory)
        baker = projections[('sites', 'collier-shine-site-2')]
        self.assertEqual(baker.fields['member_restriction'], 'members_only')
        self.assertIsNone(baker.fields['hours'])
        self.assertEqual(baker.fields['availability'], 'not_confirmed')
        self.assertEqual(baker.freshness_state, 'as_of_2026-10-29')
        self.assertEqual(projections[('statewide', 'statewide')].fields['tty']['value'], '1-800-955-8770')
        self.assertFalse(projections[('liaison', 'liaison')].fields['appointment_route'])
        request = projections[('online_request', 'online_request')]
        self.assertEqual(len(request.fields['fields']), 13)
        self.assertFalse(request.fields['submission_executed'])
        self.assertFalse(request.fields['personal_data_sent'])
        self.assertFalse(request.fields['delivery_confirmed'])

    def test_l15_changed_count_or_period_fails_instead_of_relabeling(self):
        original = load_json(ROOT / l15.DIRECTORY)
        for field, value in [('site_count', 3), ('as_of_date', '2027-01-01')]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path = root / l15.DIRECTORY
                path.parent.mkdir(parents=True)
                changed = copy.deepcopy(original)
                changed[field] = value
                path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):
                    list(l15.iter_records(root))


if __name__ == '__main__':
    unittest.main()
