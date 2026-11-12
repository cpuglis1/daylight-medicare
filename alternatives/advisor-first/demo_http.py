"""D145: serve the current :8894 UI and advisor API in one loopback process.

Keep the backend's original guide contract; override only static serving. This
reproduces the old UI/proxy split without an upstream HTTP hop.
"""
import json
from pathlib import Path
from urllib.parse import urlsplit

from guest_profiles import ProfileError
from part_d_rehearsal import rehearsal_route

WEB = Path(__file__).resolve().parent / 'web-8894'
DOCTOR_WEB = Path(__file__).resolve().parent / 'doctor-demo'
DOCTOR_ASSETS = {'/doctor-check/': 'index.html', '/doctor-check/flow.js': 'flow.js',
                 '/doctor-check/flow.css': 'flow.css'}
DOCTOR_LINK = b'<a class="text-button" href="/doctor-check/">Check a doctor</a>'
DOCTOR_CHAT_ASSETS = (
    b'<link rel="stylesheet" href="/doctor-check/flow.css">\n'
    b'<script src="/doctor-check/flow.js" defer></script>\n'
)
STATIC = {'.html':'text/html; charset=utf-8', '.js':'text/javascript; charset=utf-8',
          '.css':'text/css; charset=utf-8', '.json':'application/json; charset=utf-8',
          '.svg':'image/svg+xml', '.jpg':'image/jpeg', '.woff2':'font/woff2'}


def install(server, *, binding, fixture, doctor_routes=None, doctor_chat=False, rehearsal_port=None):
    if doctor_routes is not None and not (fixture or doctor_chat and server.server_port == 8895):
        raise ValueError('Doctor research requires the loopback chat or offline fixture.')
    doctor_chat = doctor_chat and doctor_routes is not None
    if doctor_chat:
        standalone = (DOCTOR_WEB / 'index.html').read_bytes()
        fields = standalone.split(b'<main id="main" class="doctor-flow">', 1)[1].split(b'</main>', 1)[0]
        doctor_template = b'<template id="daylight-doctor-template">' + fields + b'</template>\n'
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
                    'snapshot_id':binding['snapshot_id'], 'doctor_fixture':fixture and doctor_routes is not None,
                    'doctor_chat':doctor_chat, 'prescription_rehearsal':bool(rehearsal_port)}}
            if self.command == 'HEAD':
                raw = value if isinstance(value, bytes) else json.dumps(value).encode()
                return self.headers_for(code, mime, len(raw), cookie)
            return super().respond(code, value, mime, cookie)

        def static_file(self):
            path = urlsplit(self.path).path
            if doctor_routes is not None and path in DOCTOR_ASSETS:
                if doctor_chat and path == '/doctor-check/':
                    return None
                return DOCTOR_WEB / DOCTOR_ASSETS[path]
            relative = 'index.html' if path == '/' else path.lstrip('/')
            if any(part.startswith('.') for part in Path(relative).parts):
                return None
            candidate = (WEB / relative).resolve()
            return candidate if (candidate.is_relative_to(WEB.resolve())
                and candidate.suffix in STATIC and candidate.is_file()) else None

        def index_html(self):
            body = (WEB / 'index.html').read_bytes()
            if doctor_routes is not None:
                if doctor_chat:
                    body = body.replace(b'<script src="/advisor.js"', DOCTOR_CHAT_ASSETS + b'<script src="/advisor.js"', 1)
                    body = body.replace(b'</body>', doctor_template + b'</body>', 1)
                else:
                    body = body.replace(b'</header>', DOCTOR_LINK + b'\n  </header>', 1)
            return body

        def send_static(self, found):
            body = self.index_html() if found == WEB / 'index.html' else found.read_bytes()
            return self.respond(200, body, STATIC[found.suffix])

        def do_GET(self):
            if not self.validate_request() or rehearsal_route(self, rehearsal_port):
                return
            found = self.static_file()
            if found:
                return self.send_static(found)
            return super().do_GET()

        def do_HEAD(self):
            if not self.validate_request() or rehearsal_route(self, rehearsal_port):
                return
            found = self.static_file()
            if found:
                return self.send_static(found)
            return self.respond(405, {'error':'HEAD is available for static files only.'})

        def do_POST(self):
            if self.validate_request() and not rehearsal_route(self, rehearsal_port):
                url = urlsplit(self.path)
                prefix = '/api/pilot-doctors/'
                if url.path.startswith(prefix):
                    if doctor_routes is None:
                        return self.reject(404, 'Doctor evidence is unavailable on this surface.')
                    if url.query:
                        return self.reject(422, 'Use the doctor fixture request body.')
                    return doctor_routes.dispatch(self, url.path.removeprefix(prefix))
                return super().do_POST()

        def do_PUT(self):
            if self.validate_request() and not rehearsal_route(self, rehearsal_port):
                return super().do_PUT()

        def do_DELETE(self):
            if self.validate_request() and not rehearsal_route(self, rehearsal_port):
                return super().do_DELETE()

    server.RequestHandlerClass = Handler
    return server
