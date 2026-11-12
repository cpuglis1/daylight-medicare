"""Daylight :8894 UI refresh preview.

Serves the refreshed front end in ``web-8894/`` and forwards every other
request, unchanged, to the running :8893 advisor backend. It adds no backend,
storage, budget, cookie namespace or model access of its own: the guest
session, profile, plans catalog and AI budget are exactly :8893's.

Run from the repository root while :8893 is running:

    python3 alternatives/advisor-first/ui-8894/serve.py
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
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


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def handler(upstream):
    target = urlsplit(upstream)
    opener = urllib.request.build_opener(NoRedirect)

    class Handler(BaseHTTPRequestHandler):
        server_version = 'Daylight8894'
        sys_version = ''

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

        def forward(self):
            length = int(self.headers.get('Content-Length') or 0)
            body = self.rfile.read(length) if length else None
            headers = {name: self.headers[name] for name in FORWARD if self.headers.get(name)}
            headers['Host'] = target.netloc
            if self.headers.get('Origin'):
                headers['Origin'] = f'{target.scheme}://{target.netloc}'
            request = urllib.request.Request(upstream + self.path, data=body, method=self.command, headers=headers)
            try:
                response = opener.open(request, timeout=180)
            except urllib.error.HTTPError as error:
                response = error
            except OSError:
                payload = b'{"error":"The MidMorning service on :8893 is not reachable. Start it, then try again."}'
                return self.send(502, payload, [('Content-Type', 'application/json; charset=utf-8'), *SECURITY.items()])
            with response:
                payload = response.read()
                kept = [(k, v) for k, v in response.headers.items() if k.lower() not in HOP]
                self.send(response.status, payload, kept)

        def do_GET(self):
            found = self.static_file()
            if found is None:
                return self.forward()
            self.send(200, found.read_bytes(), [('Content-Type', STATIC[found.suffix]), *SECURITY.items()])

        do_HEAD = do_GET

        def do_POST(self):
            self.forward()

        do_PUT = do_DELETE = do_POST

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--port', type=int, default=8894)
    parser.add_argument('--upstream', default='http://127.0.0.1:8893')
    args = parser.parse_args()
    if args.port in PROTECTED_PORTS:
        raise SystemExit('That port belongs to a preserved Daylight surface.')
    if urlsplit(args.upstream).hostname not in {'127.0.0.1', 'localhost'}:
        raise SystemExit('The preview forwards only to a local Daylight service.')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(args.upstream.rstrip('/')))
    print(f'Daylight UI refresh at http://localhost:{args.port}/ (backend {args.upstream})', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
