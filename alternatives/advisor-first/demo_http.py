"""D145: serve the current :8894 UI and advisor API in one loopback process.

Keep the backend's original guide contract; override only static serving. This
reproduces the old UI/proxy split without an upstream HTTP hop.
"""
import json
from pathlib import Path
from urllib.parse import urlsplit

from guest_profiles import ProfileError

WEB = Path(__file__).resolve().parent / 'web-8894'
STATIC = {'.html':'text/html; charset=utf-8', '.js':'text/javascript; charset=utf-8',
          '.css':'text/css; charset=utf-8', '.json':'application/json; charset=utf-8',
          '.svg':'image/svg+xml', '.jpg':'image/jpeg', '.woff2':'font/woff2'}


def install(server, *, binding, fixture):
    base = server.RequestHandlerClass

    class Handler(base):
        def reject(self, code, message):
            self.close_connection = True
            self.respond(code, {'error': message})
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
                    or self.command not in {'GET','HEAD'} and origin is None):
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
            if len(value) > 6 or int(value) > 80000:
                return self.reject(413, 'Request is too large.')
            self.body_length = int(value)
            if self.command in {'GET','HEAD'} and self.body_length:
                return self.reject(400, 'This request cannot include a body.')
            return True

        def body(self):
            if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
                raise ProfileError('Use a bounded JSON request.', 415)
            if not 1 <= self.body_length <= 80000:
                raise ProfileError('Request is too large.', 413)
            try:
                raw = self.rfile.read(self.body_length)
            except TimeoutError:
                self.close_connection = True
                raise ProfileError('Request body timed out.', 408) from None
            if len(raw) != self.body_length:
                self.close_connection = True
                raise ProfileError('Request body is incomplete.', 400)
            try:
                value = json.loads(raw)
            except (ValueError, UnicodeError):
                raise ProfileError('Invalid JSON.', 422) from None
            if not isinstance(value, dict):
                raise ProfileError('Use a JSON object.', 422)
            return value

        def respond(self, code, value, mime='application/json; charset=utf-8', cookie=None):
            if self.path == '/api/status' and code == 200 and isinstance(value, dict):
                value = {**value, 'local_demo': {'surface':'unified-8895', 'fixture':fixture,
                    'upstream_proxy':False, 'plan_database':binding['database'],
                    'snapshot_id':binding['snapshot_id']}}
            if self.command == 'HEAD':
                raw = value if isinstance(value, bytes) else json.dumps(value).encode()
                return self.headers_for(code, mime, len(raw), cookie)
            return super().respond(code, value, mime, cookie)

        def static_file(self):
            path = urlsplit(self.path).path
            relative = 'index.html' if path == '/' else path.lstrip('/')
            if any(part.startswith('.') for part in Path(relative).parts):
                return None
            candidate = (WEB / relative).resolve()
            return candidate if (candidate.is_relative_to(WEB.resolve())
                and candidate.suffix in STATIC and candidate.is_file()) else None

        def do_GET(self):
            if not self.validate_request():
                return
            found = self.static_file()
            if found:
                return self.respond(200, found.read_bytes(), STATIC[found.suffix])
            return super().do_GET()

        def do_HEAD(self):
            if not self.validate_request():
                return
            found = self.static_file()
            if found:
                return self.respond(200, found.read_bytes(), STATIC[found.suffix])
            return self.respond(405, {'error':'HEAD is available for static files only.'})

        def do_POST(self):
            if self.validate_request():
                return super().do_POST()

        def do_PUT(self):
            if self.validate_request():
                return super().do_PUT()

        def do_DELETE(self):
            if self.validate_request():
                return super().do_DELETE()

    server.RequestHandlerClass = Handler
    return server
