"""Failure-oriented checks for the CMS acquisition and interpretation boundaries."""
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from l08_r6_http import AccessStopped, CMSClient, collect, page_url
from l08_r6_collect import release
from l08_r6_reference import assignment_state, enrollment_state, lookup, optout_state


class PageClient:
    def __init__(self, pages):
        self.pages, self.offsets = pages, []

    def json(self, url):
        offset = int(parse_qs(urlparse(url).query)['offset'][0])
        self.offsets.append(offset)
        rows = self.pages[offset]
        return rows, {'url': url, 'sha256': str(offset)}


class CMSAcquisitionTests(unittest.TestCase):
    def test_short_page_does_not_silently_finish(self):
        c = PageClient({0: [{'n': '1'}], 1: [{'n': '2'}], 2: []})
        r, a = collect(c, 'https://data.cms.gov/data-api/v1/dataset/x/data', sort='n', expected_rows=2)
        self.assertEqual(c.offsets, [0, 1, 2])
        self.assertEqual(len(r), 2)
        self.assertTrue(a['terminal_empty_page'])

    def test_repeated_page_rejected(self):
        c = PageClient({0: [{'n': '1'}], 1: [{'n': '1'}]})
        with self.assertRaisesRegex(ValueError, 'Repeated'):
            collect(c, 'https://data.cms.gov/data-api/v1/dataset/x/data', sort='n')

    def test_publisher_total_mismatch_rejected(self):
        c = PageClient({0: [{'n': '1'}], 1: []})
        with self.assertRaisesRegex(ValueError, 'publisher total'):
            collect(c, 'https://data.cms.gov/data-api/v1/dataset/x/data', sort='n', expected_rows=2)

    def test_missing_terminal_page_rejected(self):
        c = PageClient({0: [{'n': '1'}]})
        with self.assertRaisesRegex(ValueError, 'Pagination limit'):
            collect(c, 'https://data.cms.gov/data-api/v1/dataset/x/data', sort='n', max_pages=1)

    def test_ignored_filter_rejected(self):
        c = PageClient({0: [{'State': 'CA'}]})
        def check(r):
            if r['State'] != 'FL':
                raise ValueError('Ignored filter')
        with self.assertRaisesRegex(ValueError, 'Ignored filter'):
            collect(c, 'https://data.cms.gov/data-api/v1/dataset/x/data', sort='State', row_check=check)

    def test_denial_persists_and_other_route_not_tried(self):
        calls = []
        def transport(url):
            calls.append(url)
            raise HTTPError(url, 403, 'Forbidden', {}, io.BytesIO(b'denied'))
        with tempfile.TemporaryDirectory() as temp:
            c = CMSClient(temp, transport)
            with self.assertRaises(AccessStopped):
                c.get('https://data.cms.gov/data-api/v1/dataset/a/data')
            with self.assertRaises(AccessStopped):
                c.get('https://data.cms.gov/data-api/v1/dataset/b/data')
            self.assertEqual(len(calls), 1)

    def test_prior_denied_PDC_route_and_non_CMS_host_stay_stopped(self):
        for url in ['https://data.cms.gov/provider-data/api/1/datastore/sql',
                    'https://example.com/data', 'http://data.cms.gov/data.json']:
            with self.assertRaises(AccessStopped):
                CMSClient.guard(url)

    def test_filter_encoding_preserves_spaces_and_identifiers(self):
        q = parse_qs(urlparse(page_url('https://data.cms.gov/data-api/v1/dataset/x/data', 5,
                                      filters={'State Code': 'FL'})).query)
        self.assertEqual(q['filter[State Code][condition][value]'], ['FL'])
        self.assertEqual(q['offset'], ['5'])

    def test_release_pinned_instead_of_latest(self):
        d = {'title': 'Test : 2026-10-01', 'modified': '2026-10-19', 'distribution': [
            {'format': 'API', 'description': 'latest', 'accessURL': 'floating'},
            {'format': 'API', 'accessURL': 'pinned'}]}
        future = {'title': 'Test : 2027-01-01', 'modified': '2027-01-01', 'distribution': []}
        _, api = release({'datasets': [d, future]}, 'Test')
        self.assertEqual(api['accessURL'], 'pinned')


class InterpretationTests(unittest.TestCase):
    def test_may_accept_assignment_is_not_yes_or_no(self):
        self.assertEqual(assignment_state('M'), 'published_may_accept_assignment')
        self.assertEqual(assignment_state(''), 'unknown_not_published')
        self.assertTrue(assignment_state('N').startswith('unknown'))

    def test_ordering_only_does_not_imply_billing_enrollment(self):
        self.assertEqual(enrollment_state('33-99'), 'published_ordering_referring_only_enrollment')
        self.assertIn('unclassified', enrollment_state('99-99'))

    def test_optout_dates_not_a_simple_current_boolean(self):
        self.assertIn('contains', optout_state('2025-01-01', '2027-01-01'))
        self.assertIn('boundary', optout_state('2025-01-01', '2026-10-28'))
        self.assertIn('reversed', optout_state('2027-01-01', '2025-01-01'))
        self.assertIn('unknown', optout_state('', '2025-01-01'))

    def test_missing_provider_is_unknown(self):
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE observations(source_id,source_row,npi,enrollment_id,fields_json)')
        r = lookup(db, '1234567890')
        self.assertEqual(r['direct_source_observations'], [])
        self.assertIn('unknown', r['no_match_means'])
        self.assertFalse(r['MA_network_participation_established'])

    def test_same_npi_multiple_sites_are_preserved(self):
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE observations(source_id,source_row,npi,enrollment_id,fields_json)')
        for n, city in enumerate(['NAPLES', 'FORT MYERS'], 2):
            db.execute('INSERT INTO observations VALUES(?,?,?,?,?)',
                       ('clinicians', n, '1234567890', 'I1', json.dumps({'city': city, 'ind_assgn': 'M', 'grp_assgn': 'Y'})))
        r = lookup(db, '1234567890')
        self.assertEqual(len(r['direct_source_observations']), 2)
        self.assertEqual({x['fields']['city'] for x in r['direct_source_observations']}, {'NAPLES', 'FORT MYERS'})

    def test_assignment_optout_overlap_is_explicitly_held(self):
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE observations(source_id,source_row,npi,enrollment_id,fields_json)')
        for kind,fields in [('clinicians',{'ind_assgn':'Y','grp_assgn':'Y'}),
                            ('optout',{'Optout Effective Date':'2025-01-01','Optout End Date':'2027-01-01'})]:
            db.execute('INSERT INTO observations VALUES(?,?,?,?,?)',
                       (kind,2,'1234567890','I1' if kind=='clinicians' else '',json.dumps(fields)))
        r=lookup(db,'1234567890')
        self.assertEqual(r['participation_resolution'],'held_assignment_optout_source_overlap')
        self.assertEqual(r['unmatched_clinician_enrollment_ids'],['I1'])


if __name__ == '__main__':
    unittest.main()
