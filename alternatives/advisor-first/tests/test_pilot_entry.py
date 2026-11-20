"""D197 fictional, in-memory HTTP invitation entry and owner reentry checks."""
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
import test_hosted_history as hosted
from pilot_access import PilotAccess, COOKIE, OWNER_COOKIE, HISTORY_NOTICE
from pilot_budget import PilotBudget
from guest_profiles import ProfileError


class EntryTests(unittest.TestCase):
    setUp=hosted.HostedTests.setUp
    app=hosted.HostedTests.app

    def link(self):
        return self.access.issue_shared(expires_at=self.end,max_visits=4)

    def count(self):
        with self.access.db() as db:return db.execute('SELECT count(*) FROM invites').fetchone()[0]

    def test_lost_response_retry_is_atomic_and_one_visit(self):
        _,token=self.link()
        def redeem(_):return self.access.redeem(token,consent_version=HISTORY_NOTICE,request_id='a'*32)[0]
        with ThreadPoolExecutor(max_workers=5) as pool:sessions=list(pool.map(redeem,range(10)))
        self.assertEqual(len(set(sessions)),1);self.assertEqual(self.count(),1)
        with self.assertRaises(ProfileError):self.access.redeem(token,request_id='a'*32)
        _,other=self.link()
        with self.assertRaises(ProfileError):self.access.redeem(other,consent_version=HISTORY_NOTICE,request_id='a'*32)

    def test_resume_upgrades_only_future_consent_without_new_admission(self):
        _,token=self.link();session,_=self.access.redeem(token,request_id='b'*32)
        resumed,_=self.access.redeem(token,request_id='c'*32,existing_session=session,consent_version=HISTORY_NOTICE)
        self.assertEqual(resumed,session);self.assertEqual(self.count(),1)
        visit,_=self.access.authenticate(session)
        self.assertEqual(self.access.visit_policy(visit)[1],HISTORY_NOTICE)

    def test_root_friendly_but_api_still_requires_invite(self):
        app=self.app(hosted.MemoryHistory())
        code,_,headers=hosted.request(app,'/',extra_headers={'Origin':None,'Sec-Fetch-Site':'cross-site','Sec-Fetch-Mode':'navigate','Sec-Fetch-Dest':'document'})
        self.assertEqual(code,303);self.assertEqual(headers['Location'],'/pilot/join')
        self.assertEqual(hosted.request(app,'/api/guest/session')[0],401)
        self.assertEqual(hosted.request(app,'/pilot/access',extra_headers={'Sec-Fetch-Site':'cross-site'})[0],403)

    def test_durable_and_legacy_entry_pages_admit_nobody_on_get(self):
        _,token=self.link();app=self.app(hosted.MemoryHistory())
        for path in ('/pilot/join','/pilot/invite/'+token):
            code,body,_=hosted.request(app,path,extra_headers={'Origin':None,'Sec-Fetch-Site':'cross-site','Sec-Fetch-Mode':'navigate','Sec-Fetch-Dest':'document'})
            self.assertEqual(code,200);self.assertIn(b'continue-invitation',body)
        self.assertEqual(self.count(),0)

    def test_owner_cookie_reenters_only_exact_test_parent(self):
        self.access=PilotAccess.initialize(self.root/'test',ends_at=self.end)
        self.budget=PilotBudget.open(self.access,initialize=True)
        link,token=self.link()
        receipt=self.access.root/'owner-master-invitation.json'
        receipt.write_text(json.dumps({'link':link,'expires':self.end,'max_visits':4}));receipt.chmod(0o600)
        self.assertTrue(self.access.owner_invitation(token))
        app=self.app(hosted.MemoryHistory())
        code,body,headers=hosted.request(app,'/pilot/redeem',{'invitation':token,'requestId':'d'*32,'historyConsent':HISTORY_NOTICE})
        self.assertEqual(code,200)
        values=headers.get_all('Set-Cookie');cookies='; '.join(v.split(';')[0] for v in values)
        self.assertTrue(any(v.startswith(OWNER_COOKIE+'=') and 'HttpOnly' in v and 'Secure' in v for v in values))
        session=next(v.split(';')[0].split('=',1)[1] for v in values if v.startswith(COOKIE+'='))
        visit,_=self.access.authenticate(session);self.access.revoke(visit)
        code,body,_=hosted.request(app,'/pilot/redeem',{'requestId':'e'*32},cookies=cookies)
        self.assertEqual(code,200);self.assertTrue(json.loads(body)['newVisit']);self.assertEqual(self.count(),2)
        self.access.revoke_shared(link)
        self.assertFalse(self.access.owner_invitation(token))
        self.assertEqual(hosted.request(app,'/pilot/redeem',{'requestId':'f'*32},cookies=cookies)[0],401)

    def test_existing_owner_visit_can_acquire_reentry_without_original_url(self):
        self.access=PilotAccess.initialize(self.root/'test',ends_at=self.end)
        self.budget=PilotBudget.open(self.access,initialize=True)
        link,token=self.link();receipt=self.access.root/'owner-master-invitation.json'
        receipt.write_text(json.dumps({'link':link}));receipt.chmod(0o600)
        session,_=self.access.redeem(token)
        app=self.app(hosted.MemoryHistory())
        code,body,headers=hosted.request(app,'/pilot/access',cookies=COOKIE+'='+session)
        self.assertEqual(code,200);self.assertTrue(json.loads(body)['ownerReentry'])
        self.assertTrue(any(v.startswith(OWNER_COOKIE+'=') for v in headers.get_all('Set-Cookie')))

    def test_accelerator_never_gets_owner_reentry(self):
        link,token=self.link();app=self.app(hosted.MemoryHistory())
        receipt=self.access.root/'owner-master-invitation.json';receipt.write_text(json.dumps({'link':link}));receipt.chmod(0o600)
        self.assertFalse(self.access.owner_invitation(token))
        code,_,headers=hosted.request(app,'/pilot/redeem',{'invitation':token,'requestId':'g'*32})
        self.assertEqual(code,200)
        self.assertTrue(all(not c.startswith(OWNER_COOKIE+'=') for c in headers.get_all('Set-Cookie')))
        self.assertEqual(hosted.request(app,'/pilot/redeem',{'requestId':'h'*32},cookies=OWNER_COOKIE+'='+token)[0],401)

if __name__=='__main__':unittest.main()
