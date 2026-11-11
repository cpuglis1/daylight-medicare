"""Bounded source-reader and domain-state regressions; no database imports."""
import base64
from dataclasses import replace
from decimal import Decimal
import gzip
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from daylight_data.adapters import l05, l06, l07
from daylight_data.adapters.common import canonical_json, make_source

ROOT = Path(__file__).resolve().parents[3]


def fixture_record(module, table, raw, ordinal=1):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / 'synthetic.json'
        path.write_text('{}')
        return make_source(root, path, module.LAYER_ID, table, ordinal, ordinal, raw, 'synthetic_fixture')


def selected_sql_row(module, relative, table, where='', parameters=()):
    path = ROOT / module.BASE / relative
    connection = sqlite3.connect('file:' + str(path) + '?mode=ro&immutable=1', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        escaped = '"' + table.replace('"', '""') + '"'
        row = connection.execute('SELECT * FROM ' + escaped + (' WHERE ' + where if where else '') + ' LIMIT 1', parameters).fetchone()
        return fixture_record(module, table, module._binary_payload(dict(row)))
    finally:
        connection.close()


class BoundedReaderTests(unittest.TestCase):
    def test_streamed_array_object_boundaries_and_exact_decimal(self):
        for module in (l05, l06, l07):
            with self.subTest(layer=module.LAYER_ID), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'source.json'
                # Strings and a numeric token cross the decoder's fixed read boundary.
                path.write_text('["' + 'x' * 65530 + '",12345678901234567890,{"amount":0.0001}]')
                rows = list(module._json_items(path))
                self.assertEqual(rows[0][2]['value'], 'x' * 65530)
                self.assertEqual(rows[1][2]['value'], 12345678901234567890)
                self.assertEqual(rows[2][2]['amount'], Decimal('0.0001'))
                path.write_text('{"b":{"state":"unknown"},"a":null}')
                rows = list(module._json_items(path))
                self.assertEqual([(r[0], r[1]) for r in rows], [(1, 'b'), (2, 'a')])
                self.assertIsNone(rows[1][2]['value'])
                with patch.object(module, 'JSON_ITEM_LIMIT', 32):
                    path.write_text('["' + 'x' * 100 + '"]')
                    with self.assertRaises(ValueError):
                        list(module._json_items(path))

    def test_exact_selected_inventory_without_new_storage(self):
        expected = {'L05': (294813, 150711364), 'L06': (916575, 162336507), 'L07': (4329305, 1624214014)}
        for module in (l05, l06, l07):
            with self.subTest(layer=module.LAYER_ID):
                report = module.inventory(ROOT)
                self.assertEqual((report['source_rows'], report['selected_source_bytes']), expected[module.LAYER_ID])
                self.assertTrue(report['controls_verified'])
                self.assertFalse(report['source_byte_hashes_verified'])

    def test_blob_envelope_round_trips_without_float_or_text_decode(self):
        original = b'\x00\xffH0710|010|000|0.0001\r\n'
        for module in (l05, l06, l07):
            encoded = module._binary_payload({'raw_line': original})
            self.assertEqual(base64.b64decode(encoded['raw_line']['data']), original)
            self.assertEqual(encoded['raw_line']['byte_length'], len(original))
            json.loads(canonical_json(encoded))


class DrugCoverageTests(unittest.TestCase):
    def test_exact_formulary_flags_units_and_contract_only_supplement(self):
        row = selected_sql_row(l05, 'build-r3/inventory.sqlite3', 'drug_rows', 'table_name=?', ('basic',))
        value = next(l05.project_record(row))
        self.assertEqual(value.fields['ndc'], '00002143380')
        self.assertEqual(value.fields['quantity_amount_decimal'], Decimal('2'))
        self.assertTrue(value.fields['prior_authorization'])
        self.assertIsNone(value.fields['physical_quantity_unit'])
        self.assertEqual(value.output_acceptance_state, 'research_only')
        row = selected_sql_row(l05, 'build-r3/inventory.sqlite3', 'drug_rows', 'table_name=?', ('excluded',))
        value = next(l05.project_record(row))
        self.assertEqual(value.fields['supplemental_identity_grain'], 'contract_plan_without_segment')
        self.assertNotIn('segment_id', value.fields)
        self.assertNotIn('offering_id', value.fields)

    def test_source_stop_and_no_snapshot_backdating_survive_plan_link(self):
        raw = {'table': 'basic', 'source_row': 2, 'formulary_id': '00026000', 'rxcui': '1551300',
               'fact': 'prior_authorization_criteria', 'kind': 'PA', 'plan_links': [
                   {'offering_id': '2026:S5921:383:000', 'source_state': 'source_access_STOP',
                    'September_continuity_asserted': False, 'locator_state': 'scoped_only',
                    'personal_approval': False}]}
        value = next(l05.project_record(fixture_record(l05, 'condition_reference_links', raw)))
        self.assertEqual(value.source_use_state, 'source_access_STOP')
        self.assertFalse(value.fields['September_continuity_asserted'])
        self.assertFalse(value.fields['personal_approval'])
        self.assertEqual(value.output_acceptance_state, 'research_only')


class DrugPriceTests(unittest.TestCase):
    def test_exact_1e4_price_and_average_grain(self):
        row = selected_sql_row(l06, 'build-r1/inventory.sqlite3', 'prices')
        value = next(l06.project_record(row))
        self.assertEqual(value.fields['amount_decimal'], Decimal('515.4679'))
        self.assertEqual(value.fields['amount_usd_1e4'], 5154679)
        self.assertEqual(value.fields['ndc'], '00002143380')
        self.assertFalse(value.fields['pharmacy_specific'])
        self.assertFalse(value.fields['personal_price'])
        self.assertIsNone(value.fields['physical_unit'])

    def test_schedule_channels_keep_not_offered_blank_and_native_bounds(self):
        row = selected_sql_row(l06, 'build-cost-r1/inventory.sqlite3', 'schedules', 'table_name=?', ('beneficiary',))
        values = list(l06.project_record(row))
        self.assertEqual(len(values), 5)
        preferred = next(v for v in values if v.fields.get('channel') == 'preferred_retail')
        self.assertEqual(preferred.value_state, 'not_offered')
        self.assertIsNone(preferred.fields['amount_decimal'])
        self.assertEqual(preferred.fields['native_amount_decimal'], Decimal('0'))
        self.assertEqual(preferred.fields['bound_meaning'], 'bound_retained_not_applied_in_calculator')
        row = selected_sql_row(l06, 'build-cost-r1/inventory.sqlite3', 'schedules', 'table_name=?', ('insulin',))
        values = list(l06.project_record(row))
        preferred = next(v for v in values if v.fields.get('channel') == 'preferred_retail')
        standard = next(v for v in values if v.fields.get('channel') == 'standard_retail')
        self.assertEqual(preferred.value_state, 'source_blank')
        self.assertIsNone(preferred.fields['copay_decimal'])
        self.assertEqual(standard.fields['copay_decimal'], Decimal('35.00'))
        self.assertEqual(standard.fields['coinsurance_decimal'], Decimal('0.25'))
        self.assertIsNone(standard.fields['tier'])


class PharmacyNetworkTests(unittest.TestCase):
    def test_network_unknown_selected_fee_and_published_zero_remain_distinct(self):
        row = selected_sql_row(l07, 'build-r1/inventory.sqlite3', 'network')
        value = next(l07.project_record(row))
        self.assertEqual(value.fields['npi'], '1003001934')
        self.assertIsNone(value.fields['dispensing_fee_usd']['SELECTED_DISPENSING_FEE_30'])
        self.assertEqual(value.fields['dispensing_fee_usd']['BRAND_DISPENSING_FEE_30'], Decimal('0.75'))
        changed = dict(row.raw, SELECTED_DISPENSING_FEE_30='0')
        zero = next(l07.project_record(replace(row, raw=changed)))
        self.assertEqual(zero.fields['dispensing_fee_usd']['SELECTED_DISPENSING_FEE_30'], Decimal('0'))
        self.assertNotIn('SELECTED_DISPENSING_FEE_30', zero.fields['dispensing_fee_missing_fields'])
        self.assertFalse(zero.fields['selected_fee_substitution_performed'])
        self.assertEqual(value.output_acceptance_state, 'research_only')

    def test_ambiguous_locations_preserve_all_candidates_and_native_zip(self):
        payload = {'npi': '1003001934', 'network_zip': 'XXXXX', 'status': 'multiple_zip_matched_locations',
                   'scope_group': 'identity_or_location_unresolved', 'county_fips': None,
                   'candidate_locations': [
                       {'address_id': 'a', 'registry_address': {'postal_code': '00101', 'address_1': 'FIRST'}},
                       {'address_id': 'b', 'registry_address': {'postal_code': '00102', 'address_1': 'SECOND'}}]}
        raw = {'npi': payload['npi'], 'network_zip': 'XXXXX', 'identity_status': payload['status'],
               'scope_group': payload['scope_group'], 'county_fips': None, 'record_json': json.dumps(payload)}
        value = next(l07.project_record(fixture_record(l07, 'locations', raw)))
        self.assertEqual(value.fields['network_zip'], 'XXXXX')
        self.assertEqual(len(value.fields['candidate_addresses']), 2)
        self.assertIsNone(value.fields['selected_address_id'])
        self.assertIsNone(value.fields['county_fips'])
        self.assertEqual(value.value_state, 'multiple_zip_matched_locations')


if __name__ == '__main__':
    unittest.main()
