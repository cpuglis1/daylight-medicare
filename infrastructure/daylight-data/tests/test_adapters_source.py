"""Source identity, exact values and dependency failure cases; no real profiles."""
import json
import gzip
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from decimal import Decimal

from daylight_data.adapters import iter_layer_projections
from daylight_data.adapters.common import canonical_json, offering_parts, sha256_file, sqlite_records, make_source, account
from daylight_data.adapters.closure import build_source_closure, write_closure_report
from daylight_data.adapters.l02 import iter_collier_offerings

ROOT = Path(__file__).resolve().parents[3]


class SourceContractTests(unittest.TestCase):
    def test_exact_decimal_and_padded_identities(self):
        self.assertEqual(json.loads(canonical_json({'amount': Decimal('0.0001')}))['amount'], '0.0001')
        self.assertEqual(offering_parts('2026:H1045:048:002')['segment_id'], '002')
        for invalid in ('2027:H1045:048:002', '2026:H1045:48:2', '2026:H1045:048:0'):
            with self.assertRaises(ValueError):
                offering_parts(invalid)

    def test_sqlite_primary_key_and_duplicate_rows_have_stable_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'source.sqlite3'
            with sqlite3.connect(path) as db:
                db.executescript('CREATE TABLE keyed(id TEXT PRIMARY KEY, amount TEXT); CREATE TABLE duplicate(value TEXT);')
                db.executemany('INSERT INTO keyed VALUES (?,?)', [('b', '1.0001'), ('a', '0.0001')])
                db.executemany('INSERT INTO duplicate VALUES (?)', [('same',), ('same',)])
            before = sha256_file(path)
            first = list(sqlite_records(root, path, 'L06'))
            second = list(sqlite_records(root, path, 'L06'))
            self.assertEqual([row.record_id for row in first], [row.record_id for row in second])
            self.assertEqual([row.raw['id'] for row in first if row.source_table == 'keyed'], ['a', 'b'])
            duplicate = [row for row in first if row.source_table == 'duplicate']
            self.assertEqual(len(duplicate), 2)
            self.assertNotEqual(duplicate[0].record_id, duplicate[1].record_id)
            self.assertEqual(before, sha256_file(path))

    def test_recursive_closure_keeps_hashes_and_explicit_private_missing_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet = root / 'docs/data/l99/selected'
            packet.mkdir(parents=True)
            raw = packet / 'raw.bin'; raw.write_bytes(b'exact bytes')
            child = packet / 'child.json'
            child.write_text(json.dumps({'files': {'raw.bin': sha256_file(raw)},
                                          'allowed_use': 'research only', 'source_stop': '403 STOP retained'}))
            manifest = packet / 'manifest.json'
            manifest.write_text(json.dumps({'files': {'child.json': sha256_file(child),
                                                      'raw.bin': '0' * 64, 'missing.pdf': '1' * 64},
                                             'secret_path': '.env', 'raw_path': str(root / '.env'),
                                             'quoted_text': 'docs/data/unrelated/private-looking-prose.json'}))
            (root / '.env').write_text('DO NOT READ')
            stores = ['cms-slice/var/ten-question-profiles/guides.sqlite3',
                      'cms-slice/var/ai-budget/usage.sqlite3',
                      'alternatives/chat-first/cms-slice/var/ten-question-profiles/guides.sqlite3']
            protected = {}
            for store in stores:
                dummy = root / store
                dummy.parent.mkdir(parents=True, exist_ok=True)
                dummy.write_bytes(b'synthetic private placeholder')
                protected[store] = sha256_file(dummy)
            source_manifest = json.loads(manifest.read_text())
            source_manifest['protected_files'] = protected
            manifest.write_text(json.dumps(source_manifest))
            config = root / 'composition.json'
            config.write_text(json.dumps({'composition_digest': 'fixture', 'layers': [
                {'layer_id': 'L99', 'seeds': [{'path': str(manifest.relative_to(root)), 'sha256': sha256_file(manifest)}]}]}))
            report = build_source_closure(root, config)
            self.assertEqual(report['summary']['logical_files'], 3)
            self.assertFalse(any('private-looking-prose' in item['original_reference'] for item in report['dependencies']))
            states = {item['status'] for item in report['missing_dependencies']}
            self.assertTrue({'missing_dependency', 'hash_mismatch'} <= states)
            self.assertTrue(any(item['status'] == 'excluded_private_material' for item in report['excluded_references']))
            self.assertTrue(any(item['policy_key'] == 'source_stop' for item in report['source_policy_observations']))
            self.assertFalse(any(item['original_path'].endswith('.env') for item in report['artifacts']))
            self.assertFalse(any('/var/' in item['original_path'] for item in report['artifacts']))
            self.assertTrue(all(any(item['original_reference'] == store and item['status'] == 'excluded_private_material'
                                    for item in report['excluded_references']) for store in stores))
            self.assertEqual(report['closure_digest'], build_source_closure(root, config)['closure_digest'])
            index_path = root / 'closure-index.json'
            first = write_closure_report(report, index_path)
            second = write_closure_report(report, index_path)
            self.assertEqual(first['full_report'], second['full_report'])
            raw_report = gzip.decompress(Path(str(index_path) + '.gz').read_bytes())
            self.assertEqual(hashlib.sha256(raw_report).hexdigest(), first['full_report']['uncompressed_sha256'])
            self.assertEqual(json.loads(raw_report)['closure_digest'], report['closure_digest'])


    def test_exact_packet_manifest_alias_and_absolute_hash_map(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet = root / 'docs/data/l99/packet'
            packet.mkdir(parents=True)
            source = root / 'plans/Exact_PA_2026.pdf'
            source.parent.mkdir()
            source.write_bytes(b'exact synthetic PDF bytes')
            second = root / 'plans/Other_2026.pdf'
            second.write_bytes(b'another exact synthetic PDF')
            status = packet / 'plan-acquisition-status.json'
            status.write_text(json.dumps([{'PA_file': source.name}]))
            manifest = packet / 'manifest.json'
            manifest.write_text(json.dumps({'files': {status.name: sha256_file(status)},
                                             'source_inputs': {str(source): sha256_file(source)},
                                             'custom_review_pinned_bytes': {str(second): sha256_file(second)}}))
            config = root / 'composition.json'
            config.write_text(json.dumps({'composition_digest': 'fixture', 'layers': [
                {'layer_id': 'L99', 'seeds': [{'path': str(manifest.relative_to(root)), 'sha256': sha256_file(manifest)}]}]}))
            report = build_source_closure(root, config)
            self.assertEqual(report['missing_dependencies'], [])
            self.assertEqual(report['summary']['logical_files'], 4)
            alias = next(row for row in report['dependencies'] if row['relation'] == 'PA_file')
            self.assertEqual(alias['status'], 'resolved')
            self.assertEqual(alias['resolution_basis'], 'exact_packet_manifest_source_input_alias')
            self.assertEqual(alias['alias_expected_sha256'], sha256_file(source))
            self.assertEqual(alias['alias_manifest_sha256'], sha256_file(manifest))


    def test_code_change_creates_new_derivation_and_control_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.json'
            source.write_text('[]')
            with patch('daylight_data.adapters.common.adapter_code_sha256', return_value='a' * 64):
                first = make_source(root, source, 'L01', 'rows', 1, 'one', {'value': 1}, 'fixture')
            with patch('daylight_data.adapters.common.adapter_code_sha256', return_value='b' * 64):
                changed = make_source(root, source, 'L01', 'rows', 1, 'one', {'value': 1}, 'fixture')
            self.assertEqual(first.record_id, changed.record_id)
            self.assertNotEqual(first.derivation_id, changed.derivation_id)
            controls = account(iter([first, changed]))
            self.assertEqual(controls['derivation_ids'], sorted([first.derivation_id, changed.derivation_id]))
            self.assertEqual(controls['adapter_code_hashes'], ['a' * 64, 'b' * 64])


class SelectedSourceTests(unittest.TestCase):
    def test_l01_exact_78_entries_keep_all_qualification_links(self):
        rows = list(iter_layer_projections(ROOT, 'L01'))
        self.assertEqual(len(rows), 78)
        notes = {row.fields['local_id'] for row in rows if row.entity_type == 'federal_reference_qualification'}
        for row in rows:
            self.assertEqual(row.output_acceptance_state, 'exact_existing_receipt_gate_required')
            self.assertFalse(row.fields['personal_applicability_determined'])
            self.assertTrue(set(row.fields.get('qualification_ids', [])) <= notes)
        premium = next(row for row in rows if row.fields['local_id'] == 'a_premium_full')
        self.assertEqual(premium.fields['amount_decimal'], Decimal('565'))

    def test_l02_exact_collier_72_is_observed_not_verified(self):
        rows = list(iter_collier_offerings(ROOT))
        self.assertEqual(len(rows), 72)
        self.assertEqual(len({row.raw['id'] for row in rows}), 72)
        self.assertTrue(all(row.raw['release'] == 'research_only' for row in rows))
        self.assertTrue(all(row.raw['personal_applicability'] == 'not_assessed' for row in rows))

    def test_l04_10_offerings_310_fields_67_counties_and_source_accounting(self):
        # Complete source tables are streamed, including out-of-scope rows. Domain
        # field and county populations must match the selected bounded reference.
        counts = {}
        field_amounts = []
        for row in iter_layer_projections(ROOT, 'L04'):
            counts[row.entity_type] = counts.get(row.entity_type, 0) + 1
            self.assertEqual(row.output_acceptance_state, 'research_only')
            if row.entity_type == 'pdp_field_observation' and 'amount_decimal' in row.fields:
                field_amounts.append(row.fields['amount_decimal'])
        self.assertEqual(counts['offering'], 10)
        self.assertEqual(counts['pdp_field_observation'], 310)
        self.assertEqual(counts['pdp_region_county'], 67)
        self.assertTrue(all(isinstance(value, Decimal) for value in field_amounts))

    def test_l09_contract_grain_exact_observations_and_definitions(self):
        rows = list(iter_layer_projections(ROOT, 'L09'))
        observations = [row for row in rows if row.entity_type == 'quality_observation']
        self.assertEqual(len(observations), 2448)
        self.assertEqual(sum(row.entity_type == 'offering_quality_binding' for row in rows), 82)
        self.assertEqual(sum(row.entity_type == 'quality_measure_definition' for row in rows), 45)
        self.assertEqual(len({row.fields['contract_id'] for row in observations}), 24)
        self.assertTrue(all(row.fields['grain'] == 'contract_rating_kind_measure_and_year' for row in observations))
        self.assertTrue(all(row.fields['value_decimal'] is None or isinstance(row.fields['value_decimal'], Decimal) for row in observations))


if __name__ == '__main__':
    unittest.main()
