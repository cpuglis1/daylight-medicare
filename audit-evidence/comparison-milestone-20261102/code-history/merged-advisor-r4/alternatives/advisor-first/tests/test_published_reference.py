"""Read-only checks against the original accepted r4 lookup; no personal data."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
from published_reference import (HELD_PURPOSES, PublishedReferenceAdapter,
                                 PublishedReferenceError,
                                 PublishedReferenceRequestError)


DOCUMENTED = '2026:H1035:019:000'
RESTRICTED = '2026:H0710:010:000'
_RUN = subprocess.run


class PublishedReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapter = PublishedReferenceAdapter()
        cls.full = cls.adapter.lookup(DOCUMENTED)

    def test_reference_is_identical_to_original_accepted_lookup(self):
        worker = '''import json,sys
sys.path.insert(0,sys.argv[1])
from l03_scoped_reference import lookup
print(json.dumps(lookup({'year':2026,'offering_id':sys.argv[2]},research=False)))
'''
        original = _RUN([sys.executable, '-I', '-S', '-B', '-c', worker,
                         str(REPO/'cms-slice/scripts'), DOCUMENTED],
                        capture_output=True, text=True, check=True, timeout=30, env={})
        self.assertEqual(self.full['reference'], json.loads(original.stdout))
        self.assertEqual(len(self.full['reference']['entries']), 12)
        self.assertEqual(self.full['purpose'], 'reference_lookup')
        self.assertEqual(self.full['audience'], 'internal_research_workspace')
        self.assertTrue(all(self.full['authority'][purpose]['state'] == 'held'
                            for purpose in HELD_PURPOSES))

    def test_exact_receipt_and_all_six_dispositions_are_bound(self):
        out = self.full
        receipt = REPO/'cms-slice/data-sources/l03-published-reference-review.json'
        self.assertEqual(out['review_receipt'], json.loads(receipt.read_text()))
        self.assertEqual(out['binding']['review_registry_sha256'],
                         hashlib.sha256(receipt.read_bytes()).hexdigest())
        self.assertEqual(out['binding']['manifest_sha256'],
                         'fb163f824e35cbb52b5aa11bd520de64bd4fa5e51b574f7d3de4c3accbaab881')
        dispositions = {row['id']: hashlib.sha256(json.dumps(
            row, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            for row in out['accepted_dispositions']}
        self.assertEqual(len(dispositions), 6)
        self.assertEqual(dispositions, out['review_receipt']['accepted_dispositions'])
        self.assertEqual(len(out['review_receipt']['accepted_entry_ids']), 535)

    def test_scalar_request_keeps_original_hospital_schedule_and_qualifications(self):
        entry_id = DOCUMENTED + ':r4:INN_hospital_band1_amount'
        out = self.adapter.lookup(DOCUMENTED, entry_ids=[entry_id])['reference']
        self.assertEqual([entry['id'] for entry in out['entries']], [entry_id])
        selected = out['entries'][0]
        self.assertEqual(selected['unit'], 'USD/day')
        self.assertTrue(selected['qualifications'])
        self.assertTrue(selected['carrier_evidence'])
        related = {row['id']: row for row in out['related_reference_entries']}
        for field in ('INN_hospital_band1_begin_day', 'INN_hospital_band1_end_day'):
            expected = next(row for row in self.full['reference']['entries'] if row.get('field') == field)
            self.assertEqual(related[expected['id']], expected)

    def test_disputed_values_stay_masked_and_restricted_offering_stays_visible(self):
        holds = self.full['reference']['holds']
        self.assertTrue(holds)
        self.assertTrue(all(row['value'] is None and row['state'] == 'unknown_held' for row in holds))
        restricted = self.adapter.lookup(RESTRICTED)['reference']
        self.assertEqual(restricted['offering']['offering_id'], RESTRICTED)
        self.assertEqual(restricted['offering']['carrier_document_state'], 'restricted')
        self.assertEqual(restricted['entries'], [])
        self.assertEqual(restricted['related_reference_entries'], [])
        self.assertFalse(restricted['comprehensive'])
        self.assertFalse(restricted['personal_applicability'])
        self.assertFalse(restricted['recommendations'])

    def test_held_or_wrong_offering_ids_are_rejected_by_original_authority(self):
        held = self.full['reference']['holds'][0]['issue_id']
        for offering, ids in ((DOCUMENTED, [held]),
                              (RESTRICTED, [self.full['reference']['entries'][0]['id']]),
                              ('2026:H0000:999:000', None)):
            with self.subTest(offering=offering, ids=ids):
                with self.assertRaises(PublishedReferenceRequestError):
                    self.adapter.lookup(offering, entry_ids=ids)

    def test_invalid_scope_and_permission_overrides_never_start_worker(self):
        with patch('published_reference.subprocess.run') as worker:
            for year in (2027, '2026', True):
                with self.assertRaises(PublishedReferenceRequestError):
                    self.adapter.lookup(DOCUMENTED, year=year)
            for ids in ([], ['duplicate', 'duplicate'], 'not-a-list', [None]):
                with self.assertRaises(PublishedReferenceRequestError):
                    self.adapter.lookup(DOCUMENTED, entry_ids=ids)
            for extra in ({'research': True}, {'accepted': True}, {'profile': {}}, {'registry': 'other'}):
                with self.assertRaises(TypeError):
                    self.adapter.lookup(DOCUMENTED, **extra)
            worker.assert_not_called()

    def test_each_call_replays_original_in_isolation_from_parent_modules(self):
        poisoned = types.ModuleType('l03_scoped_reference')
        poisoned.lookup = lambda *args, **kwargs: self.fail('Parent module leaked to original replay')
        with patch.dict(sys.modules, {'l03_scoped_reference': poisoned}):
            with patch('published_reference.subprocess.run', wraps=_RUN) as worker:
                first = self.adapter.lookup(RESTRICTED)
                second = self.adapter.lookup(RESTRICTED)
        self.assertEqual(worker.call_count, 2)
        self.assertEqual(first['reference'], second['reference'])
        self.assertEqual(first['binding'], second['binding'])
        self.assertEqual(worker.call_args.kwargs['env'], {})

    def test_real_original_registry_revocation_fails_without_releasing_values(self):
        # Copy only the administrative receipt into a temporary test directory;
        # original data, source code and the actual default registry stay intact.
        receipt = copy.deepcopy(self.full['review_receipt'])
        receipt['revoked'] = True
        worker = '''import json,sys
sys.path.insert(0,sys.argv[1])
from l03_scoped_reference import lookup,ReferenceHeld
try:
    lookup({'year':2026,'offering_id':sys.argv[3]},research=False,registry=sys.argv[2])
except ReferenceHeld:
    print(json.dumps({'state':'held','values_returned':False}))
else:
    raise AssertionError('Revoked authority returned a reference')
'''
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory)/'revoked-test-receipt.json'
            registry.write_text(json.dumps(receipt))
            result = _RUN([sys.executable, '-I', '-S', '-B', '-c', worker,
                           str(REPO/'cms-slice/scripts'), str(registry), DOCUMENTED],
                          capture_output=True, text=True, check=True, timeout=30, env={})
        self.assertEqual(json.loads(result.stdout), {'state': 'held', 'values_returned': False})

    def test_replay_failures_do_not_expose_stderr_or_retry_as_research(self):
        secret = 'DO_NOT_EXPOSE_WORKER_EXCEPTION_OR_CREDENTIAL'
        failures = [subprocess.CompletedProcess([], 1, '', secret),
                    subprocess.CompletedProcess([], 0, '{broken-json', secret),
                    subprocess.CompletedProcess([], 0, json.dumps({
                        'ok': False, 'error_code': 'REFERENCE_AUTHORITY_HELD'}), secret)]
        for failure in failures:
            with self.subTest(code=failure.returncode, stdout=failure.stdout):
                with patch('published_reference.subprocess.run', return_value=failure) as worker:
                    with self.assertRaises(PublishedReferenceError) as raised:
                        self.adapter.lookup(DOCUMENTED)
                    self.assertNotIn(secret, str(raised.exception))
                    self.assertEqual(worker.call_count, 1)
        with patch('published_reference.subprocess.run', side_effect=subprocess.TimeoutExpired(
                ['private-command'], 30, output=secret, stderr=secret)):
            with self.assertRaises(PublishedReferenceError) as raised:
                self.adapter.lookup(DOCUMENTED)
            self.assertEqual(str(raised.exception), 'REFERENCE_LOOKUP_TIMEOUT')


if __name__ == '__main__':
    unittest.main()
