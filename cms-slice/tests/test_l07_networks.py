"""Adversarial published-network and exact-location join cases."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import l07_build as build
import l07_validate as audit
import l07_identity_build as identity
import l07_geography_validate as geography


class NetworkEvidenceTests(unittest.TestCase):
    def source_case(self):
        cells = ['H9999', '001', '000', '101234567890', '34104', 'Y', 'N', 'Y', 'N', '1',
                 '0', '1.2500', '.', '0', '', '3.75', '0.5', '0', '2']
        line = ('|'.join(cells) + '\r\n').encode()
        record = (1, 29, '2026:H9999:001:000', *cells, '1234567890', 'preferred', 'not_offered',
                  json.dumps(['0', '1.2500', None, '0', None, '3.75', '0.5', '0', '2']), line)
        return cells, line, record

    def test_complete_raw_and_derived_record(self):
        cells, line, record = self.source_case()
        audit.assert_record(record, 1, 29, '2026:H9999:001:000', cells, line)

    def test_altered_native_fee_detected(self):
        cells, line, record = self.source_case()
        altered = list(record); altered[13] = '9.99'
        with self.assertRaisesRegex(ValueError, 'Native field'):
            audit.assert_record(altered, 1, 29, '2026:H9999:001:000', cells, line)

    def test_missing_row_and_wrong_segment_detected(self):
        cells, line, record = self.source_case()
        for bad in [None, (1, 29, '2026:H9999:001:001', *record[3:])]:
            with self.assertRaisesRegex(ValueError, 'source row'):
                audit.assert_record(bad, 1, 29, '2026:H9999:001:000', cells, line)

    def test_zero_cannot_turn_into_missing_fee(self):
        cells, line, record = self.source_case()
        altered = list(record); fees = json.loads(record[25]); fees[0] = None; altered[25] = json.dumps(fees)
        with self.assertRaisesRegex(ValueError, 'Derived field'):
            audit.assert_record(altered, 1, 29, '2026:H9999:001:000', cells, line)

    def test_unavailable_outlet_does_not_become_standard(self):
        self.assertEqual(build.channel('N', 'N'), 'not_offered')
        self.assertEqual(build.channel('N', 'Y'), 'inconsistent_flags')
        self.assertEqual(build.channel('Y', 'N'), 'standard')
        self.assertEqual(build.channel('Y', ''), 'unknown_flag')

    def test_identifier_requires_documented_prefix(self):
        self.assertEqual(build.npi_from_number('101234567890'), '1234567890')
        self.assertIsNone(build.npi_from_number('991234567890'))
        self.assertIsNone(build.npi_from_number('1234567890'))

    def test_zip_mismatch_and_multiple_locations_remain_unresolved(self):
        def loc(street, postal):
            return [{'address_1': street, 'postal_code': postal, 'state': 'FL'}]
        person = {'registry_status': 'A', 'locations': [loc('1 FIRST ST', '341041111'), loc('2 SECOND ST', '341042222')]}
        self.assertEqual(identity.disposition('34104', person)[0], 'multiple_zip_matched_locations')
        self.assertEqual(identity.disposition('34105', person)[0], 'network_registry_zip_mismatch')
        self.assertEqual(identity.disposition('34104', None)[0], 'identity_missing')

    def test_inactive_identity_does_not_establish_store(self):
        status, candidates = identity.disposition('34104', {'registry_status': 'D', 'locations': []})
        self.assertEqual(status, 'identity_inactive_or_unknown'); self.assertEqual(candidates, [])

    def test_known_county_does_not_resolve_a_mismatched_store(self):
        candidates = [{'registry_address': {'state': 'FL'}, 'geography': {'status': 'Match', 'county_fips': '12021'}}]
        self.assertEqual(geography.expected_scope('network_registry_zip_mismatch', candidates), ('identity_or_location_unresolved', None))
        self.assertEqual(geography.expected_scope('unique_zip_matched_location', candidates), ('Collier', '12021'))

    def test_missing_geography_does_not_become_Collier(self):
        candidates = [{'registry_address': {'state': 'FL'}, 'geography': {'status': 'No_Match'}}]
        self.assertEqual(geography.expected_scope('unique_zip_matched_location', candidates), ('Florida_county_unresolved', None))

    def test_unpublished_ZIP_is_retained_as_unknown(self):
        record = {'registry_status': 'A', 'locations': [[{'address_1': '1 MAIN ST', 'postal_code': '34104'}]]}
        state, candidates = identity.disposition('XXXXX', record)
        self.assertEqual(state, 'network_zip_unpublished')
        self.assertEqual(candidates, record['locations'])


if __name__ == '__main__':
    unittest.main()
