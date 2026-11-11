"""Recover receipts/state with synthetic reports and no provider transport."""
import copy
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_natural_flow as fixtures
from guest_profiles import ProfileError


class SessionRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.NaturalFlowTests()
        self.case.setUp()
        self.case.choice('RC01', choice='someone')

    def submitted(self):
        return self.case.payload({'type': 'message', 'message':
            'She has Original Medicare, Medigap and a separate Part D plan.'})

    def complete(self, payload):
        self.case.extractions.append(self.case.extraction())
        return self.case.take(payload)

    def test_restart_reconnects_reports_without_replaying_the_message(self):
        payload = self.submitted()
        restarted = fixtures.NaturalFlowTests()
        restarted.setUp()
        with self.assertRaises(ProfileError) as stopped:
            restarted.flow.turn(self.case.owner, payload)
        self.assertEqual(stopped.exception.code, 409)
        recovered = restarted.flow.recover(self.case.owner, payload)
        self.assertEqual(recovered['status'], 'reset')
        state = recovered['response']
        self.assertEqual(state['guide']['fields']['subject.role']['value'], 'someone')
        self.assertNotEqual(state['continuation'], payload['continuation'])
        self.assertEqual(restarted.calls, [])
        self.assertNotIn('review', state)
        self.assertNotIn('preparation', state)
        restarted.owner = self.case.owner
        restarted.g, restarted.r = state['guide'], state['record']
        restarted.continuation = state['continuation']
        result = restarted.message(payload['action']['message'])
        self.assertTrue(result['continuation'])
        self.assertEqual(len(restarted.calls), 2, 'Only the later deliberate Send calls the model.')

    def test_completed_reply_is_recovered_without_new_calls(self):
        payload = self.submitted()
        accepted = self.complete(payload)
        before = len(self.case.calls)
        for _ in range(2):
            recovered = self.case.flow.recover(self.case.owner, payload)
            self.assertEqual(recovered['status'], 'completed')
            self.assertEqual(recovered['response']['continuation'], accepted['continuation'])
            self.assertEqual(recovered['response']['reply'], accepted['reply'])
        self.assertEqual(len(self.case.calls), before)

    def test_lost_reconnect_receipt_cannot_roll_back_later_progress(self):
        payload = self.submitted()
        self.case.flow.state_heads.clear()
        self.case.flow.turn_journal.clear()
        recovered = self.case.flow.recover(self.case.owner, payload)['response']
        self.case.g, self.case.r = recovered['guide'], recovered['record']
        self.case.continuation = recovered['continuation']
        current = self.case.choice('T02', choice='comfortable')
        repeated = self.case.flow.recover(self.case.owner, payload)
        self.assertEqual(repeated['status'], 'resumed')
        self.assertEqual(repeated['response']['continuation'], current['continuation'])
        self.assertEqual(self.case.calls, [])

    def test_stale_snapshot_uses_latest_server_reports(self):
        payload = self.submitted()
        current = self.case.choice('T02', choice='comfortable')
        recovered = self.case.flow.recover(self.case.owner, payload)
        self.assertEqual(recovered['status'], 'resumed')
        self.assertEqual(recovered['response']['continuation'], current['continuation'])
        self.assertEqual(recovered['response']['guide']['fields']['knowledge.general']['value'], 'comfortable')
        self.assertEqual(self.case.calls, [])

    def test_completed_old_request_cannot_roll_back_a_later_correction(self):
        payload = self.submitted()
        self.complete(payload)
        current = self.case.choice('T02', choice='comfortable')
        before = len(self.case.calls)
        recovered = self.case.flow.recover(self.case.owner, payload)
        self.assertEqual(recovered['status'], 'resumed')
        self.assertEqual(recovered['response']['continuation'], current['continuation'])
        self.assertEqual(len(self.case.calls), before)

    def test_processing_turn_is_only_checked_never_restarted(self):
        payload = self.submitted()
        self.case.flow.natural_active.add(self.case.owner)
        before = copy.deepcopy(self.case.flow.state_heads)
        self.assertEqual(self.case.flow.recover(self.case.owner, payload), {'status': 'working'})
        self.assertEqual(self.case.flow.state_heads, before)
        self.assertEqual(self.case.calls, [])
        self.case.flow.natural_active.remove(self.case.owner)
        self.complete(payload)
        self.assertEqual(self.case.flow.recover(self.case.owner, payload)['status'], 'completed')

    def test_recovery_never_reuses_a_request_id_for_changed_content(self):
        payload = self.submitted()
        self.complete(payload)
        payload['action']['message'] = 'A different message.'
        with self.assertRaises(ProfileError) as stopped:
            self.case.flow.recover(self.case.owner, payload)
        self.assertEqual(stopped.exception.code, 409)

    def test_latest_snapshot_cannot_restore_withdrawn_saving_permission(self):
        self.case.g['preferences'].update(saveGuide=True, saveSensitive=True)
        self.case.choice('T02', choice='comfortable')
        payload = self.submitted()
        payload['guide']['preferences'].update(saveGuide=False, saveSensitive=False)
        state = self.case.flow.recover(self.case.owner, payload)['response']
        self.assertFalse(state['guide']['preferences']['saveGuide'])
        self.assertFalse(state['guide']['preferences']['saveSensitive'])
        self.assertEqual(self.case.calls, [])

    def test_recovery_does_not_execute_an_old_named_action(self):
        review = self.case.turn({'type': 'review_preparation'})
        payload = self.case.payload({'type': 'run_preparation', 'token': review['review']['token']})
        self.case.choice('T02', choice='comfortable')
        state = self.case.flow.recover(self.case.owner, payload)['response']
        self.assertNotIn('preparation', state)
        self.assertNotIn('review', state)
        self.assertEqual(self.case.calls, [])

    def test_recovery_is_owner_scoped_and_revocation_still_applies(self):
        payload = self.submitted()
        self.complete(payload)
        other = self.case.flow.recover(uuid.uuid4().hex, payload)
        self.assertEqual(other['status'], 'reset')
        self.assertNotEqual(other['response'].get('reply'), 'We can work through the next useful detail together.')
        self.case.flow.forget_owner(self.case.owner)
        with self.assertRaises(ProfileError) as stopped:
            self.case.flow.recover(self.case.owner, payload)
        self.assertEqual(stopped.exception.code, 401)

    def test_recovery_does_not_accept_invalid_profiles(self):
        payload = self.submitted()
        payload['record']['natural']['provenance'] = {'forged': {}}
        with self.assertRaises(ProfileError):
            self.case.flow.recover(self.case.owner, payload)
        self.assertEqual(self.case.calls, [])


if __name__ == '__main__':
    unittest.main()
