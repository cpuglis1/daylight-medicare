"""D178 offline progress contracts. Model transport is scripted/network denied."""
import copy
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import test_quiet_recovery as fixture
import turn_progress as progress
from guest_profiles import ProfileError


class ProgressStore(unittest.TestCase):
    def test_progress_assets_require_explicit_surface_enablement(self):
        import demo_http
        for enabled in (False, True):
            server=SimpleNamespace(RequestHandlerClass=object, adaptive=SimpleNamespace(),server_port=0)
            if enabled:server.adaptive.turn_progress=progress.Progress()
            demo_http.install(server,binding={},fixture=True)
            handler=object.__new__(server.RequestHandlerClass)
            body=handler.index_html()
            self.assertEqual(b'src="/turn-progress.js"' in body,enabled)
            self.assertEqual(b'href="/turn-progress.css"' in body,enabled)

    def test_owner_request_isolation_bounded_retention_and_codes_only(self):
        clock = [0]
        p = progress.Progress(clock=lambda: clock[0], ttl=10, limit=2)
        p.begin(('one', 'request-0001'))
        self.assertEqual(p.read('two', 'request-0001'), {'state':'unknown'})
        self.assertEqual(p.read('one', 'request-0002'), {'state':'unknown'})
        p.update(('one','request-0001'), stage='doctors')
        self.assertEqual(p.read('one','request-0001'), {'state':'working','stage':'doctors'})
        p.begin(('one','request-0002'));p.begin(('two','request-0003'))
        self.assertEqual(p.read('one','request-0001'), {'state':'unknown'})
        with self.assertRaises(ValueError): p.update(('one','request-0002'),stage='private draft')
        clock[0] = 11
        self.assertEqual(p.read('two','request-0003'), {'state':'unknown'})
        self.assertFalse(p.receipts)

    def test_actual_nested_operations_restore_stage_and_preserve_failure(self):
        p = progress.Progress(); key = ('owner','request-0001')
        def check(expected): self.assertEqual(p.read(*key), {'state':'working','stage':expected})
        def nested():
            check('doctors')
            progress.run('plans',lambda: check('plans'))
            check('doctors')
            raise LookupError('test source hold')
        with self.assertRaises(LookupError):
            with progress.track(p,*key):
                self.assertEqual(p.read(*key),{'state':'unknown'})
                progress.accepted();progress.run('doctors',nested)
        self.assertEqual(p.read(*key),{'state':'failed'})
        progress.run('medicines',lambda: None)
        self.assertEqual(p.read(*key),{'state':'failed'})

    def test_unaccepted_and_disabled_work_leaves_no_receipt(self):
        p = progress.Progress()
        with progress.track(p,'owner','request-0001'):
            self.assertEqual(progress.run('plans',lambda: 42),42)
        with progress.track(None,'owner','request-0001'):
            progress.accepted();progress.run('plans',lambda: None)
        self.assertFalse(p.receipts)

    def test_concurrent_turns_do_not_share_context(self):
        p=progress.Progress();gate=threading.Barrier(3);release=threading.Event();errors=[]
        def work(owner,stage):
            try:
                with progress.track(p,owner,'request-0001'):
                    progress.accepted()
                    def hold(): gate.wait(timeout=3);release.wait(3)
                    progress.run(stage,hold)
            except BaseException as e: errors.append(e)
        threads=[threading.Thread(target=work,args=('one','doctors')),
                 threading.Thread(target=work,args=('two','medicines'))]
        for t in threads:t.start()
        try:
            gate.wait(timeout=3)
            self.assertEqual(p.read('one','request-0001')['stage'],'doctors')
            self.assertEqual(p.read('two','request-0001')['stage'],'medicines')
        finally:
            release.set()
            for t in threads:t.join(3)
        self.assertFalse(errors)
        self.assertEqual(p.read('one','request-0001'),{'state':'complete'})


class ProgressController(fixture.QuietRecovery):
    for name in dir(fixture.QuietRecovery):
        if name.startswith('test_'): locals()[name] = None

    def setUp(self):
        super().setUp()
        self.flow.turn_progress = progress.Progress()

    def assertStage(self, expected):
        key = next(reversed(self.flow.turn_progress.receipts))
        before = copy.deepcopy((self.g,self.r))
        calls = len(self.calls)
        for _ in range(40):
            self.assertEqual(self.flow.turn_progress.read(*key),{'state':'working','stage':expected})
        self.assertEqual(calls,len(self.calls))
        self.assertEqual(before,(self.g,self.r))

    def test_typed_and_structured_turns_keep_model_budget_and_validation(self):
        extract=self.flow.agent.extract;compose=self.flow.agent.compose
        def extracting(*args,**kwargs):self.assertStage('working');return extract(*args,**kwargs)
        def composing(*args,**kwargs):self.assertStage('composing');return compose(*args,**kwargs)
        with patch.object(self.flow.agent,'extract',extracting), patch.object(self.flow.agent,'compose',composing):
            out=self.ask('Help me organize enrollment.',task='timing',target='T05',checks=['job_loss'],
                updates=[self.update('RC01',{'choice':'self'},'me')])
            self.assertEqual(out['metrics']['llmCalls'],2)
            self.compositions.append(self.draft('Your premium is $99999.','RC09'))
            out=self.turn({'type':'choice','id':'T05','fields':{'choice':'employer'}})
            self.assertEqual(out['metrics']['llmCalls'],1)
            self.assertNotIn('99999',out['reply'])
            self.assertNotIn('notice',out)
        self.assertTrue(all(v['state']=='complete' for v in self.flow.turn_progress.receipts.values()))

    def test_replay_and_rejected_request_do_not_restart_progress(self):
        payload=self.payload({'type':'refresh'},aiConsent=False)
        first=self.flow.turn(self.owner,payload)
        key=(self.owner,payload['requestId'])
        stamp=copy.deepcopy(self.flow.turn_progress.receipts[key])
        again=self.flow.turn(self.owner,payload)
        self.assertEqual(first['continuation'],again['continuation'])
        self.assertEqual(stamp,self.flow.turn_progress.receipts[key])
        with self.assertRaises(ProfileError):
            self.flow.turn(self.owner,{**payload,'action':{'type':'start'}})
        self.assertEqual(stamp,self.flow.turn_progress.receipts[key])
        with self.assertRaises(ProfileError):self.flow.turn(self.owner,{'requestId':[]})

    def test_poll_does_not_take_the_flow_lock(self):
        self.flow.turn_progress.begin((self.owner,'request-0001'))
        done=threading.Event()
        with self.flow.lock:
            t=threading.Thread(target=lambda:(self.flow.turn_progress.read(self.owner,'request-0001'),done.set()))
            t.start()
            self.assertTrue(done.wait(1),'Progress blocked behind conversation work')
        t.join()
