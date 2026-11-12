"""Fictional integrity/STOP/freshness checks; no network or model calls."""
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import Mock, patch

from daylight_data.pilot_subset import store
from daylight_data.plan_types.common import digest


class Connection:
    def __init__(self, manifest, responses):
        self.row = {'snapshot_id': digest(manifest), 'manifest': manifest}
        self.responses, self.stops = responses, set()

    def __enter__(self): return self
    def __exit__(self, *args): pass
    def transaction(self): return nullcontext()

    def execute(self, query, params=()):
        if 'FROM dl_pilot.snapshot' in query:
            value = self.row
        elif 'FROM dl_pilot.stop_event' in query:
            value = {'exists': 1} if self.stops & {'all', params[0]} else None
        elif 'FROM dl_pilot.pdp_response' in query:
            value = {'payload': self.responses[params[0]]} if params[0] in self.responses else None
        else:
            value = None
        return Mock(fetchone=lambda: deepcopy(value))


class PilotSubsetTests(TestCase):
    def setUp(self):
        source = {'code': store.code_binding(), 'runtime': store.runtime_binding(),
                  'review_due': {'L04': '2026-11-24T00:00:00+00:00', 'L10': '2026-11-28T00:00:00+00:00'}}
        build = digest(source)
        source['build_id'] = build
        self.patch = patch.object(store, 'PDP_BUILD', build)
        self.patch.start(); self.addCleanup(self.patch.stop)
        responses = {kind: {'build_id': build, 'next_after': None, 'source_review_due': False,
                           'records': [{'fictional': True, 'ordinal': n} for n in range(count)]}
                     for kind, count in store.KINDS.items()}
        manifest = {'schema': 'collier-display-subset/1', 'consumer_release': 'held',
            'implementation': store.implementation_binding(), 'csg_build': store.CSG_BUILD,
            'pdp_build': build, 'pdp_source_manifest': source,
            'pdp_response_sha256': {k: digest(v) for k, v in responses.items()}}
        self.connection = Connection(manifest, responses)
        self.snapshot = store.Snapshot(lambda: self.connection, digest(manifest))
        self.repository = store.PdpRepository(self.snapshot,
            now=lambda: datetime(2026, 11, 12, tzinfo=timezone.utc))
        self.request = {'reference_year': 2026, 'county_fips': '12021',
            'intended_use': 'developer_source_inspection', 'kind': 'pdp_offering', 'page_size': 100}

    def test_exact_population_and_freshness(self):
        self.assertEqual(len(self.repository.query(self.request)['records']), 10)
        self.repository.now = lambda: datetime(2026, 11, 24, tzinfo=timezone.utc)
        self.assertTrue(self.repository.query(self.request)['source_review_due'])
        self.assertFalse(self.connection.responses['pdp_offering']['source_review_due'])

    def test_request_does_not_expand_to_research_or_personal_data(self):
        for change in ({'reference_year': 2027}, {'reference_year': True}, {'county_fips': '12099'},
                       {'kind': 'medigap_filed_rate'}, {'page_size': True}, {'page_size': 20},
                       {'intended_use': 'recommendation'}, {'medicine': 'Fictional medicine'},
                       {'commission': 100}):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'UNSUPPORTED_PILOT_QUERY'):
                self.repository.query({**self.request, **change})

    def test_snapshot_changed_or_missing_fails_closed(self):
        self.connection.row['manifest']['consumer_release'] = 'accepted'
        with self.assertRaisesRegex(RuntimeError, 'PILOT_SNAPSHOT_MISMATCH'):
            self.repository.query(self.request)
        self.connection.row = None
        with self.assertRaisesRegex(RuntimeError, 'PILOT_SNAPSHOT_MISMATCH'):
            self.repository.query(self.request)

    def test_wrong_expected_revision_fails_closed(self):
        self.snapshot.expected = '0' * 64
        with self.assertRaisesRegex(RuntimeError, 'PILOT_SNAPSHOT_MISMATCH'):
            self.repository.query(self.request)

    def test_changed_or_missing_payload_fails_closed(self):
        self.connection.responses['pdp_offering']['records'].pop()
        with self.assertRaisesRegex(RuntimeError, 'PILOT_PAYLOAD_MISMATCH'):
            self.repository.query(self.request)
        self.connection.responses.pop('pdp_offering')
        with self.assertRaisesRegex(RuntimeError, 'PILOT_PAYLOAD_MISMATCH'):
            self.repository.query(self.request)

    def test_changed_runtime_fails_closed(self):
        with patch.object(store, 'runtime_binding', return_value={'fictional': 'changed'}):
            with self.assertRaisesRegex(RuntimeError, 'RUNTIME_BINDING_MISMATCH'):
                self.repository.query(self.request)

    def test_changed_adapter_fails_closed(self):
        with patch.object(store, 'implementation_binding', return_value={'fictional': 'changed'}):
            with self.assertRaisesRegex(RuntimeError, 'PILOT_BINDING_MISMATCH'):
                self.repository.query(self.request)

    def test_scoped_and_global_stops_are_checked_on_each_read(self):
        self.repository.query(self.request)
        for scope in ('pdp', 'all'):
            self.connection.stops = {scope}
            with self.assertRaisesRegex(RuntimeError, 'SOURCE_STOP'):
                self.repository.query(self.request)
        self.connection.stops = {'medigap'}
        self.assertEqual(len(self.repository.query(self.request)['records']), 10)

    def test_medigap_stop_prevents_underlying_query(self):
        native = Mock()
        wrapper = store.MedigapRepository(self.snapshot, native)
        self.connection.stops = {'medigap'}
        with self.assertRaisesRegex(RuntimeError, 'SOURCE_STOP'):
            wrapper.query(zipcode='34101')
        native.query.assert_not_called()
        self.connection.stops = {'pdp'}
        wrapper.query(zipcode='34101')
        native.query.assert_called_once_with(zipcode='34101')
