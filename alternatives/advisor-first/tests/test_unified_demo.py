"""D145: actual demo DB, fictional guests, no model or external transport."""
import hashlib
import http.client
import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

import test_http as support
from test_session_recovery_http import RecoveryHttpTests
from demo_server import build_demo
from demo_http import WEB, STATIC
from server import HERE, build


class UnifiedDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='daylight-unified-tests-')
        cls.block = patch('urllib.request.urlopen', side_effect=AssertionError('External transport forbidden'))
        cls.block.start()
        cls.server = build_demo(0, fixture=True, database=Path(cls.tmp.name)/'fictional.sqlite3')
        cls.thread = threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()
        cls.block.stop();cls.tmp.cleanup()

    def request(self, path, body=None, *, headers=None, method=None):
        conn = http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
        supplied = {'Origin':f'http://127.0.0.1:{self.server.server_port}'}
        if body is not None:supplied['Content-Type']='application/json'
        supplied.update(headers or {})
        conn.request(method or ('POST' if body is not None else 'GET'),path,
                     json.dumps(body) if body is not None else None,supplied)
        response=conn.getresponse();raw=response.read();result=(response.status,raw,dict(response.getheaders()))
        conn.close();return result

    def session(self):
        code,raw,headers=self.request('/api/guest/session')
        self.assertEqual(code,200)
        return json.loads(raw),headers['Set-Cookie'].split(';')[0]

    def test_every_current_frontend_file_is_served_unchanged(self):
        for path in WEB.rglob('*'):
            if not path.is_file() or path.suffix not in STATIC:continue
            relative=str(path.relative_to(WEB))
            with self.subTest(file=relative):
                code,raw,headers=self.request('/'+relative)
                self.assertEqual(code,200)
                self.assertEqual(hashlib.sha256(raw).digest(),hashlib.sha256(path.read_bytes()).digest())
                self.assertEqual(headers['Cache-Control'],'no-store')
        code,raw,headers=self.request('/')
        self.assertEqual(raw,(WEB/'index.html').read_bytes())
        code,raw,head=self.request('/',method='HEAD')
        self.assertEqual(code,200);self.assertEqual(raw,b'')
        self.assertEqual(int(head['Content-Length']),len((WEB/'index.html').read_bytes()))

    def test_direct_api_and_complete_demo_plan_displays(self):
        code,raw,_=self.request('/api/status');status=json.loads(raw)
        self.assertEqual(code,200);self.assertFalse(status['local_demo']['upstream_proxy'])
        self.assertEqual(status['local_demo']['plan_database'],'daylight_pilot_collier_2026_r1')
        session,cookie=self.session()
        auth={'Cookie':cookie,'X-Daylight-CSRF':session['csrf']}
        for route,body,count in [('/api/plans/catalog',{},72),
            ('/api/plans/medigap',{'zipcode':'34101','age':65,'gender':'Female','tobacco':'Non-Tobacco','effective_date':'2026-11-10'},178),
            ('/api/plans/part-d',{'zipcode':'34101','county_fips':'12021','year':2026},10)]:
            code,raw,_=self.request(route,body,headers=auth)
            self.assertEqual(code,200);self.assertEqual(len(json.loads(raw)['plans']),count)
        baseline=build(0,fixture=True,database=Path(self.tmp.name)/'baseline.sqlite3')
        try:
            self.assertEqual(self.server.adaptive.contract,baseline.adaptive.contract)
        finally:
            baseline.server_close()

    def test_isolated_cookie_store_and_existing_csrf_boundary(self):
        session,cookie=self.session()
        self.assertTrue(cookie.startswith('daylight_demo_8895_fixture='))
        self.assertEqual(self.request('/api/guest/profile',headers={'Cookie':cookie})[0],200)
        old=cookie.replace('daylight_demo_8895_fixture=','daylight_advisor_fixture=')
        self.assertEqual(self.request('/api/guest/profile',headers={'Cookie':old})[0],401)
        self.assertEqual(self.request('/api/plans/catalog',{},headers={'Cookie':cookie})[0],403)
        self.assertEqual(self.request('/api/plans/catalog',{},headers={'X-Daylight-CSRF':session['csrf']})[0],401)

    def test_host_origin_framing_and_file_boundaries(self):
        for headers,expected in [({'Host':'attacker.example'},403),({'Origin':'http://localhost:8894'},403),
                ({'Sec-Fetch-Site':'cross-site'},403),({'Content-Length':'80001'},413),
                ({'Content-Length':'-1'},400),({'Transfer-Encoding':'chunked'},400)]:
            self.assertEqual(self.request('/api/plans/catalog',{},headers=headers)[0],expected)
        for path in ('/../server.py','/.env','/fonts/../../server.py'):
            self.assertEqual(self.request(path)[0],404)
        for extra in ('Host: localhost:1\r\n','Content-Length: 2\r\n','Origin: http://attacker.example\r\n'):
            request=(f'POST /api/plans/catalog HTTP/1.1\r\nHost: 127.0.0.1:{self.server.server_port}\r\n'
                f'Origin: http://127.0.0.1:{self.server.server_port}\r\nContent-Length: 2\r\n{extra}\r\n{{}}')
            with socket.create_connection(('127.0.0.1',self.server.server_port),timeout=3) as connection:
                connection.sendall(request.encode());line=connection.recv(1024).split(b'\r\n')[0]
            self.assertIn(line.split()[1],(b'400',b'403'))

    def test_protected_ports_and_original_live_store_are_rejected(self):
        for port in (8890,8891,8893,8894,8896):
            with self.assertRaises(ValueError):build_demo(port)
        with self.assertRaises(ValueError):
            build(0,local_demo=True,database=HERE/'var/profiles/guides.sqlite3')


class UnifiedRecoveryTests(RecoveryHttpTests):
    def start_service(self):
        self.service=build_demo(0,fixture=True,database=self.database)
        self.thread=threading.Thread(target=self.service.serve_forever,daemon=True);self.thread.start()


# unittest discovers inherited module classes too; expose only the unified suite.
del RecoveryHttpTests

if __name__=='__main__':unittest.main()
