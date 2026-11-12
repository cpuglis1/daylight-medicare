"""Exercise the actual UI proxy against an isolated loopback upstream."""
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
from pathlib import Path
from threading import Thread
import unittest

spec = importlib.util.spec_from_file_location('ui_proxy', Path(__file__).parents[1] / 'ui-8894/serve.py')
proxy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proxy)


class ProxySecurityTests(unittest.TestCase):
    def setUp(self):
        self.received = []
        received = self.received

        class Upstream(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append((self.headers.get('Origin'), self.rfile.read(int(self.headers.get('Content-Length', 0)))))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{}')

            def log_message(self, *args):
                pass

        self.upstream = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
        self.origin = f'http://127.0.0.1:{self.upstream.server_port}'
        self.proxy = ThreadingHTTPServer(('127.0.0.1', 0), proxy.handler(self.origin))
        for service in (self.upstream, self.proxy):
            Thread(target=service.serve_forever, daemon=True).start()
            self.addCleanup(service.server_close)
            self.addCleanup(service.shutdown)

    def request(self, headers=None, path='/api/conversation/turn'):
        conn = http.client.HTTPConnection('127.0.0.1', self.proxy.server_port, timeout=3)
        base = {'Origin': f'http://127.0.0.1:{self.proxy.server_port}', 'Content-Type': 'application/json'}
        base.update(headers or {})
        conn.request('POST', path, b'{}', base)
        result = conn.getresponse()
        code = result.status
        result.read()
        conn.close()
        return code

    def test_rejects_origin_host_and_fetch_site_before_upstream(self):
        self.assertEqual(self.request({'Origin': 'https://attacker.example'}), 403)
        self.assertEqual(self.request({'Host': 'attacker.example'}), 403)
        self.assertEqual(self.request({'Sec-Fetch-Site': 'cross-site'}), 403)
        self.assertEqual(self.received, [])
        self.assertEqual(self.request(), 200)
        self.assertEqual(self.received, [(self.origin, b'{}')])

    def test_rejects_oversize_ambiguous_and_invalid_lengths(self):
        for headers, status in (({'Content-Length': '80001'}, 413),
                                ({'Content-Length': '-1'}, 400),
                                ({'Content-Length': 'unknown'}, 400),
                                ({'Transfer-Encoding': 'chunked'}, 400)):
            self.assertEqual(self.request(headers), status)
        self.assertEqual(self.received, [])

    def test_local_upstream_is_required(self):
        for origin in ('https://example.com', 'http://user:pw@localhost:8893', 'http://localhost:8893/path'):
            with self.assertRaises(ValueError):
                proxy.handler(origin)


if __name__ == '__main__':
    unittest.main()
