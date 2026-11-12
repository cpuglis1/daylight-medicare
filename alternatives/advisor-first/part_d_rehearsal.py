"""Route the unified demo's fictional conversation to its private local fixture."""
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from urllib.parse import urlsplit

PREFIX = '/d146'
FIXTURE_COOKIE = 'daylight_demo_8895_fixture'
REHEARSAL_COOKIE = 'daylight_d146_8895_fixture'
GET = {'/', '/prescription-profile-preview.js', '/ten-config.json', '/api/status',
       '/api/guest/session', '/api/guest/profile', '/api/guest/readiness',
       '/api/conversation/initial', '/api/sample-plans'}
POST = {'/api/conversation/turn', '/api/conversation/recover', '/api/conversation/resume',
        '/api/conversation/save', '/api/plans/handoff', '/api/plans/catalog', '/api/plans/part-d',
        '/api/plans/medigap', '/api/plans/priorities', '/api/plans/workspace', '/api/recommendation',
        '/api/prescription-preview/profile',
        *('/api/pilot-doctors/' + name for name in ('search', 'sites', 'visit', 'selection', 'evidence'))}
ROUTES = {'GET': GET, 'HEAD': GET, 'POST': POST, 'DELETE': {'/api/guest/profile'}}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def rehearsal_route(handler, port):
    path = urlsplit(handler.path).path
    if path != PREFIX and not path.startswith(PREFIX + '/'):
        return False
    route = path.removeprefix(PREFIX)
    if not port or handler.path != path:
        handler.reject(404, 'The fictional prescription rehearsal is unavailable.')
    elif not route and handler.command in {'GET', 'HEAD'}:
        handler.send_response(308)
        handler.send_header('Location', PREFIX + '/')
        handler.send_header('Cache-Control', 'no-store')
        handler.send_header('Content-Length', '0')
        handler.end_headers()
    elif route in ROUTES.get(handler.command, ()):
        forward(handler, port, route)
    else:
        handler.reject(404, 'This route is unavailable in the fictional rehearsal.')
    return True


def forward(handler, port, route):
    try:
        body = handler.rfile.read(handler.body_length) if handler.body_length else None
    except TimeoutError:
        return handler.reject(408, 'Request body timed out.')
    if body is not None and len(body) != handler.body_length:
        return handler.reject(400, 'Request body is incomplete.')
    origin = f'http://127.0.0.1:{port}'
    headers = {name: handler.headers[name] for name in ('Content-Type', 'X-Daylight-CSRF')
               if handler.headers.get(name)}
    if handler.headers.get('Origin'):
        headers['Origin'] = origin
    cookies = [piece.strip() for raw in handler.headers.get_all('Cookie', [])
               for piece in raw.split(';') if piece.strip().startswith(REHEARSAL_COOKIE + '=')]
    if cookies:
        headers['Cookie'] = '; '.join(FIXTURE_COOKIE + piece[len(REHEARSAL_COOKIE):] for piece in cookies)
    request = Request(origin + route, data=body, headers=headers, method=handler.command)
    try:
        response = build_opener(ProxyHandler({}), NoRedirect).open(request, timeout=180)
    except HTTPError as error:
        response = error
    except OSError:
        return handler.reject(502, 'The fictional prescription rehearsal is unavailable.')
    with response:
        raw = response.read()
        cookie = response.headers.get('Set-Cookie')
        if cookie and cookie.startswith(FIXTURE_COOKIE + '=') and '; Path=/;' in cookie:
            cookie = REHEARSAL_COOKIE + cookie[len(FIXTURE_COOKIE):].replace('; Path=/;', '; Path=/d146/;', 1)
        else:
            cookie = None
        mime = response.headers.get('Content-Type', 'application/json; charset=utf-8')
        if handler.command == 'HEAD':
            return handler.headers_for(response.status, mime, int(response.headers['Content-Length']), cookie)
        return handler.respond(response.status, raw, mime, cookie)
