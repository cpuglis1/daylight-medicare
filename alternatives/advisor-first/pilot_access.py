"""Private invite state and an outer gate for the isolated pilot rehearsal."""
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import hmac
from http.cookies import SimpleCookie
import json
import logging
import os
from pathlib import Path
import re
import secrets
import sqlite3
from threading import Lock
import time

from guest_profiles import ProfileError


participant = ContextVar('pilot_participant', default=None)
COOKIE = '__Host-daylight_pilot'
GUEST_COOKIE = 'daylight_pilot_fixture'
JOIN_ASSETS = {'/pilot/join': ('join.html', 'text/html'),
               '/pilot/join.js': ('join.js', 'text/javascript'),
               '/pilot/join.css': ('join.css', 'text/css'),
               '/pilot/atkinson.woff2': ('../web/fonts/atkinson-400.woff2', 'font/woff2')}
FLAGS = ('guest_chat', 'all_chat', 'paid_features')
GET_ROUTES = {'/api/status', '/api/guest/session', '/api/conversation/initial', '/api/sample-plans'}
POST_ROUTES = {'/api/conversation/turn', '/api/conversation/recover', '/api/conversation/resume',
               '/api/comparison/journey', '/api/comparison/review', '/api/profile/readiness'}
DISPLAY_ROUTES = frozenset({'/api/plans/catalog', '/api/plans/detail', '/api/plans/medigap', '/api/plans/part-d'})
ACCESS_EVENTS = GET_ROUTES | POST_ROUTES | {'/pilot/redeem'}
access_log = logging.getLogger('daylight.pilot.access')


def digest(value):
    return hashlib.sha256(value.encode('ascii')).hexdigest()


class PilotTurnPacing:
    """Spec §3.4 pacing, keyed by verified invite across browser sessions."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = Lock()
        self.recent = {}
        self.active = set()

    @contextmanager
    def admit(self, key):
        with self.lock:
            now = self.clock()
            history = self.recent.setdefault(key, deque())
            while history and now - history[0] >= 60:
                history.popleft()
            if key in self.active:
                raise ProfileError('Wait for the current reply before sending another message.', 429)
            if len(history) >= 10 or (history and now - history[-1] < 3):
                raise ProfileError('Please wait a moment before sending another message.', 429)
            history.append(now)
            self.active.add(key)
        try:
            yield
        finally:
            with self.lock:
                self.active.remove(key)


class PilotAccess:
    def __init__(self, directory, clock=time.time):
        self.root = Path(directory).resolve(strict=True)
        self.clock = clock
        self.path = self.root / 'access.sqlite3'
        key = self.root / 'signing.key'
        if (not self.root.is_dir() or not self.path.is_file() or not key.is_file()
                or any(p.is_symlink() or p.stat().st_mode & 0o077 for p in (self.root, self.path, key))):
            raise ValueError('Pilot state requires a private directory and private regular files.')
        self.key = key.read_bytes()
        if len(self.key) != 32:
            raise ValueError('Invalid pilot signing key.')

    @classmethod
    def initialize(cls, directory, *, ends_at, clock=time.time):
        if type(ends_at) is not int or ends_at <= clock():
            raise ValueError('Use a future pilot expiry.')
        directory = Path(directory)
        directory.mkdir(mode=0o700)
        key = directory / 'signing.key'
        with os.fdopen(os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
            stream.write(secrets.token_bytes(32))
        path = directory / 'access.sqlite3'
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb'):
            pass
        db = sqlite3.connect(path)
        try:
            with db:
                db.executescript('''
                    CREATE TABLE cohort (expires INTEGER NOT NULL);
                    CREATE TABLE invites (
                        id TEXT PRIMARY KEY, expires INTEGER NOT NULL,
                        revoked INTEGER NOT NULL DEFAULT 0, session TEXT UNIQUE,
                        guest TEXT UNIQUE, completed INTEGER NOT NULL DEFAULT 0);
                    CREATE TABLE flags (name TEXT PRIMARY KEY, enabled INTEGER NOT NULL);
                ''')
                db.execute('INSERT INTO cohort VALUES (?)', (ends_at,))
                db.executemany('INSERT INTO flags VALUES (?,0)', [(name,) for name in FLAGS])
        finally:
            db.close()
        return cls(directory, clock)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True, timeout=3)
        try:
            with db:
                db.execute('BEGIN IMMEDIATE')
                yield db
        finally:
            db.close()

    def issue(self, *, expires_at):
        """Founder-only operation. A separately approved share issues a new invite."""
        key = secrets.token_hex(16)
        with self.db() as db:
            end, = db.execute('SELECT expires FROM cohort').fetchone()
            if type(expires_at) is not int or not self.clock() < expires_at <= end:
                raise ValueError('Invitation expiry must be within the pilot.')
            if db.execute('SELECT count(*) FROM invites').fetchone()[0] >= 20:
                raise ValueError('The rehearsal supports at most 20 invitations.')
            db.execute('INSERT INTO invites(id,expires) VALUES (?,?)', (key, expires_at))
        payload = f'{key}.{expires_at}'
        return key, f'{payload}.{hmac.digest(self.key, payload.encode(), "sha256").hex()}'

    def redeem(self, token):
        if not isinstance(token, str) or not re.fullmatch(r'[0-9a-f]{32}\.[0-9]{1,12}\.[0-9a-f]{64}', token):
            raise ProfileError('Invitation is unavailable.', 401)
        key, expiry, signature = token.split('.')
        payload = f'{key}.{expiry}'.encode()
        if not hmac.compare_digest(signature, hmac.digest(self.key, payload, 'sha256').hex()):
            raise ProfileError('Invitation is unavailable.', 401)
        now = int(self.clock())
        session = secrets.token_hex(32)
        with self.db() as db:
            updated = db.execute('''UPDATE invites SET session=? WHERE id=? AND expires=?
                AND expires>? AND revoked=0 AND session IS NULL
                AND (SELECT expires FROM cohort)>?''', (digest(session), key, int(expiry), now, now))
            if updated.rowcount != 1:
                raise ProfileError('Invitation is unavailable.', 401)
        return session, int(expiry) - now

    def authenticate(self, session):
        if not session or not re.fullmatch(r'[0-9a-f]{64}', session):
            raise ProfileError('A pilot invitation is required.', 401)
        with self.db() as db:
            return self._active(db, 'session', digest(session))

    def _active(self, db, column, value):
        # column is supplied only by the two internal callers.
        row = db.execute(f'''SELECT id,guest FROM invites WHERE {column}=? AND session IS NOT NULL
            AND expires>? AND revoked=0 AND (SELECT expires FROM cohort)>?''',
            (value, self.clock(), self.clock())).fetchone()
        if not row:
            raise ProfileError('Pilot access has expired or was revoked.', 401)
        return row

    def bind_guest(self, key, guest, *, previous=None):
        with self.db() as db:
            _, existing = self._active(db, 'id', key)
            if existing != previous and existing != guest:
                raise ProfileError('Reload the pilot visit.', 409)
            db.execute('UPDATE invites SET guest=? WHERE id=?', (guest, key))

    def revoke(self, key):
        with self.db() as db:
            if db.execute('UPDATE invites SET revoked=1 WHERE id=?', (key,)).rowcount != 1:
                raise ValueError('Unknown participant reference.')

    def set_flag(self, flag, enabled):
        if flag not in FLAGS or type(enabled) is not bool:
            raise ValueError('Use a defined pilot switch and a boolean value.')
        with self.db() as db:
            db.execute('UPDATE flags SET enabled=? WHERE name=?', (int(enabled), flag))

    def mark_completed(self, key):
        """Record an operator-observed supported outcome without conversation data."""
        with self.db() as db:
            if db.execute('UPDATE invites SET completed=1 WHERE id=? AND guest IS NOT NULL', (key,)).rowcount != 1:
                raise ValueError('Only an observed pilot visit may be marked completed.')

    def observed_visits(self):
        with self.db() as db:
            return dict(db.execute('SELECT id,completed FROM invites WHERE guest IS NOT NULL'))

    def chat_enabled(self, key):
        with self.db() as db:
            self._active(db, 'id', key)
            flags = dict(db.execute('SELECT name,enabled FROM flags'))
            return flags.get('all_chat') == flags.get('guest_chat') == 1


def install_pilot_gate(server, access, *, hosted_origin=False, plan_display=False):
    parent = server.RequestHandlerClass
    pacing = PilotTurnPacing()

    class Handler(parent):
        def origin(self):
            origin = super().origin()
            if getattr(server, 'pilot_tls', False) and origin.startswith('http://'):
                return 'https://' + origin.removeprefix('http://')
            return origin

        def send_response(self, code, message=None):
            super().send_response(code, message)
            if hosted_origin or getattr(server, 'pilot_tls', False):
                self.send_header('Strict-Transport-Security', 'max-age=31536000')
            if hosted_origin:
                route = getattr(self, 'path', '')
                access_log.info('%s', json.dumps({
                    'event': 'pilot_http', 'route': route if route in ACCESS_EVENTS else 'other',
                    'status': int(code), 'time': int(time.time()),
                }))

        def body(self):
            if hasattr(self, '_pilot_body'):
                return self._pilot_body
            return super().body()

        def send_header(self, name, value):
            if name == 'Set-Cookie' and value.startswith(GUEST_COOKIE + '='):
                value += '; Secure'
            return super().send_header(name, value)

        def _dispatch(self, callback):
            try:
                if plan_display and not self.validate_request():
                    return
                if not self.safe() or self.headers.get('Sec-Fetch-Site') == 'cross-site':
                    raise ProfileError('Request origin rejected.', 403)
                if '?' in self.path or not self.path.startswith('/') or self.path.startswith('//'):
                    raise ProfileError('Use the pilot URL without parameters.', 422)
                if self.command == 'GET' and self.path in JOIN_ASSETS:
                    name, mime = JOIN_ASSETS[self.path]
                    return self.respond(200, (Path(__file__).parent / 'pilot-web' / name).read_bytes(), mime)
                if self.command == 'POST' and self.headers.get('Origin') != self.origin():
                    raise ProfileError('Request origin rejected.', 403)
                if self.command == 'POST' and self.path == '/pilot/redeem':
                    session, age = access.redeem(self.body().get('invitation'))
                    cookie = f'{COOKIE}={session}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age={age}'
                    return self.respond(200, {'joined': True}, cookie=cookie)
                raw = self.headers.get('Cookie', '')
                if raw.count(COOKIE + '=') != 1:
                    raise ProfileError('A pilot invitation is required.', 401)
                cookies = SimpleCookie(raw)
                cookie = cookies.get(COOKIE)
                key, bound = access.authenticate(cookie.value if cookie else None)
                is_message = False
                if self.path.startswith('/api/'):
                    routes = GET_ROUTES if self.command == 'GET' else POST_ROUTES
                    if self.command == 'POST' and plan_display:
                        routes = routes | DISPLAY_ROUTES
                    if self.path not in routes:
                        raise ProfileError('This capability is unavailable in the pilot.', 404)
                    token = self.token()
                    if token and not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
                        raise ProfileError('Use the original pilot browser.', 401)
                    guest = server.profiles.digest(token) if token else None
                    if self.command == 'GET' and self.path == '/api/guest/session':
                        if guest is not None and bound is not None and guest != bound:
                            raise ProfileError('Use the original pilot browser.', 401)
                        token, info, new = server.profiles.session(token if bound else None)
                        access.bind_guest(key, server.profiles.digest(token), previous=bound)
                        cookie = f'{GUEST_COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict' if new else None
                        return self.respond(200, info, cookie=cookie)
                    if self.path not in {'/api/status', '/api/sample-plans'} and (not bound or guest != bound):
                        raise ProfileError('Use the original pilot browser.', 401)
                    if self.path == '/api/conversation/turn':
                        self.csrf()
                        self._pilot_body = super().body()
                        action = self._pilot_body.get('action')
                        is_message = (self._pilot_body.get('aiConsent') is True
                                      or isinstance(action, dict) and action.get('type') == 'message')
                        if is_message and not access.chat_enabled(key):
                            raise ProfileError('Chat is paused. You can still use the guide.', 503)
                elif self.command != 'GET':
                    raise ProfileError('This capability is unavailable in the pilot.', 404)
                context = participant.set(key)
                try:
                    if is_message:
                        with pacing.admit(key):
                            return callback()
                    return callback()
                finally:
                    participant.reset(context)
            except ProfileError as error:
                return self.respond(error.code, {'error': str(error)})
            except (OSError, sqlite3.Error, ValueError):
                return self.respond(503, {'error': 'Pilot access is temporarily unavailable.'})

        def do_GET(self):
            return self._dispatch(super().do_GET)

        def do_POST(self):
            return self._dispatch(super().do_POST)

        def do_PUT(self):
            return self.respond(404, {'error': 'This capability is unavailable in the pilot.'})

        do_DELETE = do_PUT

    server.RequestHandlerClass = Handler
    return server
