"""Fictional admission and budget boundaries; no provider or AWS calls."""
import unittest
import test_d206_hosted_policy as previous
from pilot_access import PilotAccess, HISTORY_NOTICE, ProfileError
from pilot_budget import PilotBudget


class AcceleratorAccess(unittest.TestCase):
    setUp = previous.HostedPolicy.setUp

    def test_existing_signed_link_survives_more_than_100_new_admissions(self):
        original = self.access.token_parts(self.token)
        for _ in range(105):
            session, _ = self.access.redeem(self.token, consent_version=HISTORY_NOTICE)
            self.access.authenticate(session)
        self.assertEqual(self.access.token_parts(self.token), original)
        with self.access.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM visit_policy').fetchone()[0],106)
            self.assertEqual(db.execute('SELECT max_visits FROM shared_links').fetchone()[0],20)
        self.assertEqual(self.access.restart_limit,4)
        self.assertEqual(self.budget.invite_cap,5_000_000_000)
        self.assertEqual(self.budget.daily_cap_nano_usd,50_000_000_000)
        self.assertEqual(self.budget.link_cap,50_000_000_000)

    def test_expiry_revocation_and_signature_still_required(self):
        with self.assertRaises(ProfileError): self.access.redeem(self.token[:-1]+'x')
        with self.access.db() as db: db.execute('UPDATE shared_links SET revoked=1')
        with self.assertRaises(ProfileError): self.access.redeem(self.token)
        with self.access.db() as db: db.execute('UPDATE shared_links SET revoked=0')
        self.access.clock=lambda:self.end+1
        with self.assertRaises(ProfileError): self.access.redeem(self.token)

    def test_owner_and_unconfigured_links_retain_count_limits(self):
        for configured in (False,True):
            access=PilotAccess.initialize(self.root/('owner' if configured else 'unconfigured'),ends_at=self.end)
            if configured:
                budget=PilotBudget.open(access,initialize=True);budget.configure_hosted('owner')
            _,token=access.issue_shared(expires_at=self.end,max_visits=1)
            access.redeem(token)
            with self.assertRaises(ProfileError):access.redeem(token)


if __name__=='__main__':unittest.main()
