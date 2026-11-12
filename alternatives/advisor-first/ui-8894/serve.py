"""Daylight :8894 chat and optional fictional D146 rehearsal.

Serves the refreshed front end in ``web-8894/`` and forwards every other
request, unchanged, to the running :8893 advisor backend. It adds no backend,
storage, budget, cookie namespace or model access of its own: the guest
session, profile, plans catalog and AI budget are exactly :8893's.

Run from the repository root while :8893 is running:

    python3 alternatives/advisor-first/ui-8894/serve.py
"""
import argparse
from contextlib import ExitStack
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from urllib.parse import urlsplit
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent
WEB = (HERE.parent / 'web-8894').resolve()
PROTECTED_PORTS = {8890, 8891, 8893, 8896}
STATIC = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
          '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8',
          '.svg': 'image/svg+xml', '.jpg': 'image/jpeg', '.woff2': 'font/woff2'}
SECURITY = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
                                       "img-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            'Permissions-Policy': 'camera=(), microphone=(), geolocation=()'}
FORWARD = ('Content-Type', 'Cookie', 'X-Daylight-CSRF', 'Accept', 'Sec-Fetch-Site')
HOP = {'connection', 'keep-alive', 'transfer-encoding', 'content-length', 'server', 'date'}
D146 = '/d146'
BACKEND_COOKIE = 'daylight_demo_8895_fixture'
PREVIEW_COOKIE = 'daylight_d146_8894_fixture'
D146_GET = {'/', '/prescription-profile-preview.js', '/api/status', '/api/guest/session',
            '/api/guest/profile', '/api/guest/readiness', '/api/conversation/initial',
            '/ten-config.json', '/api/sample-plans'}
D146_POST = {'/api/conversation/turn', '/api/conversation/recover', '/api/conversation/resume',
             '/api/conversation/save', '/api/plans/handoff', '/api/plans/catalog', '/api/plans/part-d',
             '/api/plans/medigap', '/api/plans/priorities', '/api/plans/workspace',
             '/api/recommendation', '/api/prescription-preview/profile'}
D146_ROUTES = {'GET': D146_GET, 'HEAD': D146_GET, 'POST': D146_POST, 'DELETE': {'/api/guest/profile'}}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def local_origin(upstream):
    target = urlsplit(upstream)
    if (target.scheme != 'http' or target.hostname not in {'localhost', '127.0.0.1'}
            or target.username is not None or target.password is not None
            or target.path or target.query or target.fragment):
        raise ValueError('The preview requires a loopback HTTP origin.')
    return target


def handler(upstream, d146_upstream=None):
    target = local_origin(upstream)
    fixture = local_origin(d146_upstream) if d146_upstream else None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect)

    class Handler(BaseHTTPRequestHandler):
        server_version = 'Daylight8894'
        sys_version = ''

        def setup(self):
            super().setup()
            self.connection.settimeout(45)

        def log_message(self, fmt, *args):
            pass  # Never log paths or bodies; they can carry personal reports.

        def static_file(self):
            path = urlsplit(self.path).path
            relative = 'index.html' if path == '/' else path.lstrip('/')
            if not relative or any(part.startswith('.') for part in Path(relative).parts):
                return None
            candidate = (WEB / relative).resolve()
            if candidate.is_relative_to(WEB) and candidate.suffix in STATIC and candidate.is_file():
                return candidate
            return None

        def send(self, code, body, headers):
            self.send_response(code)
            for name, value in headers:
                self.send_header(name, value)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)

        def reject(self, code, message):
            self.close_connection = True
            self.send(code, json.dumps({'error': message}).encode(),
                      [('Content-Type', 'application/json; charset=utf-8'), *SECURITY.items()])
            return False

        def validate_request(self):
            host = self.headers.get('Host', '')
            allowed = {f'localhost:{self.server.server_port}', f'127.0.0.1:{self.server.server_port}'}
            if len(self.headers.get_all('Host', [])) != 1 or host not in allowed:
                return self.reject(403, 'Request host rejected.')
            origin = self.headers.get('Origin')
            if (len(self.headers.get_all('Origin', [])) > 1
                    or origin is not None and origin != 'http://' + host
                    or self.headers.get('Sec-Fetch-Site') == 'cross-site'
                    or self.command not in {'GET', 'HEAD'} and origin is None):
                return self.reject(403, 'Request origin rejected.')
            url = urlsplit(self.path)
            if url.scheme or url.netloc or not self.path.startswith('/') or url.fragment:
                return self.reject(422, 'Use a local request path.')
            lengths = self.headers.get_all('Content-Length', [])
            if self.headers.get('Transfer-Encoding') or len(lengths) > 1:
                return self.reject(400, 'Use one bounded request body.')
            value = lengths[0] if lengths else '0'
            if not value.isascii() or not value.isdecimal():
                return self.reject(400, 'Invalid request size.')
            if len(value) > 6:
                return self.reject(413, 'Request is too large.')
            self.body_length = int(value)
            if self.body_length > 80000:
                return self.reject(413, 'Request is too large.')
            if self.command in {'GET', 'HEAD'} and self.body_length:
                return self.reject(400, 'This request cannot include a body.')
            return True

        def forward(self, destination=target, path=None, *, d146=False):
            try:
                body = self.rfile.read(self.body_length) if self.body_length else None
            except TimeoutError:
                return self.reject(408, 'Request body timed out.')
            if body is not None and len(body) != self.body_length:
                return self.reject(400, 'Request body is incomplete.')
            headers = {name: self.headers[name] for name in FORWARD if self.headers.get(name)}
            if d146:
                cookies = headers.pop('Cookie', '').split(';')
                session = [piece.strip() for piece in cookies
                           if piece.strip().startswith(PREVIEW_COOKIE + '=')]
                if session:
                    headers['Cookie'] = '; '.join(
                        BACKEND_COOKIE + piece[len(PREVIEW_COOKIE):] for piece in session)
            headers['Host'] = destination.netloc
            if self.headers.get('Origin'):
                headers['Origin'] = destination.geturl()
            request = urllib.request.Request(destination.geturl() + (path or self.path),
                                             data=body, method=self.command, headers=headers)
            try:
                response = opener.open(request, timeout=180)
            except urllib.error.HTTPError as error:
                response = error
            except OSError:
                message = ('The fictional prescription rehearsal is unavailable.'
                           if d146 else 'The Daylight service on :8893 is not reachable. Start it, then try again.')
                return self.reject(502, message)
            with response:
                payload = response.read()
                kept = [(k, v) for k, v in response.headers.items() if k.lower() not in HOP]
                if d146:
                    kept = [(k, v) for k, v in kept if k.lower() != 'set-cookie'
                            or (v.startswith(BACKEND_COOKIE + '=') and '; Path=/;' in v)]
                    kept = [(k, PREVIEW_COOKIE + v[len(BACKEND_COOKIE):].replace(
                        '; Path=/;', f'; Path={D146}/;', 1)) if k.lower() == 'set-cookie'
                        else (k, v) for k, v in kept]
                self.send(response.status, payload, kept)

        def d146_route(self):
            path = urlsplit(self.path).path
            if path != D146 and not path.startswith(D146 + '/'):
                return False
            route = path.removeprefix(D146)
            allowed = D146_ROUTES.get(self.command, ())
            if fixture is None or self.path != path:
                self.reject(404, 'The fictional prescription rehearsal is unavailable.')
            elif not route and self.command in {'GET', 'HEAD'}:
                self.send(308, b'', [('Location', D146 + '/'), *SECURITY.items()])
            elif route in allowed:
                self.forward(fixture, route, d146=True)
            else:
                self.reject(404, 'This route is unavailable in the fictional rehearsal.')
            return True

        def do_GET(self):
            if not self.validate_request():
                return
            if self.d146_route():
                return
            found = self.static_file()
            if found is None:
                return self.forward()
            self.send(200, found.read_bytes(), [('Content-Type', STATIC[found.suffix]), *SECURITY.items()])

        do_HEAD = do_GET

        def do_POST(self):
            if self.validate_request() and not self.d146_route():
                self.forward()

        do_PUT = do_DELETE = do_POST

    return Handler


def start_d146_backend(stack, *, candidate=None):
    """Private fixture server. The ordinary :8893 session is never forwarded here."""
    sys.path.insert(0, str(HERE.parent))
    from demo_server import REPO, build_demo
    from part_d_visit_http import install_profile_preview

    temp = stack.enter_context(TemporaryDirectory(prefix='daylight-d146-8894-'))
    demo = stack.enter_context(build_demo(0, fixture=True, database=Path(temp) / 'guest.sqlite3'))
    if candidate is None:
        from daylight_data.serving.part_d_local import local_candidate
        candidate = local_candidate(REPO)
    install_profile_preview(demo, candidate)
    Thread(target=demo.serve_forever, daemon=True).start()
    stack.callback(demo.shutdown)
    return f'http://127.0.0.1:{demo.server_port}'


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--port', type=int, default=8894)
    parser.add_argument('--upstream', default='http://127.0.0.1:8893')
    parser.add_argument('--d146-preview', action='store_true',
                        help='Enable the fictional prescription rehearsal at /d146/.')
    args = parser.parse_args()
    if args.port in PROTECTED_PORTS:
        raise SystemExit('That port belongs to a preserved Daylight surface.')
    if urlsplit(args.upstream).hostname not in {'127.0.0.1', 'localhost'}:
        raise SystemExit('The preview forwards only to a local Daylight service.')
    with ExitStack() as stack:
        fixture = None
        if args.d146_preview:
            with ExitStack() as rehearsal:
                try:
                    fixture = start_d146_backend(rehearsal)
                except Exception as error:
                    # Fixture data availability cannot prevent ordinary chat startup.
                    print(f'D146 rehearsal unavailable ({type(error).__name__}).', file=sys.stderr, flush=True)
                else:
                    stack.enter_context(rehearsal.pop_all())
        server = stack.enter_context(ThreadingHTTPServer(
            ('127.0.0.1', args.port), handler(args.upstream.rstrip('/'), fixture)))
        print(f'Daylight chat at http://localhost:{args.port}/ (backend {args.upstream})', flush=True)
        if fixture:
            print(f'Fictional D146 chat at http://localhost:{args.port}{D146}/', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
