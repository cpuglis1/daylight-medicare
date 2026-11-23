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
OWNER_COOKIE = '__Host-daylight_owner'
INVITATION_PATTERN = r'[0-9a-f]{32}\.[0-9]{1,12}\.[0-9a-f]{64}'
GUEST_COOKIE = 'daylight_pilot_fixture'
JOIN_ASSETS = {'/pilot/join': ('join.html', 'text/html'),
               '/pilot/history': ('history.html', 'text/html'),
               '/pilot/history.js': ('history.js', 'text/javascript'),
               '/pilot/join.js': ('join.js', 'text/javascript'),
               '/pilot/join.css': ('join.css', 'text/css'),
               '/pilot/atkinson.woff2': ('../web/fonts/atkinson-400.woff2', 'font/woff2')}
FLAGS = ('guest_chat', 'all_chat', 'paid_features')
HISTORY_NOTICE = 'hosted-demo-history-2026-11-18-v1'
GET_ROUTES = {'/api/status', '/api/guest/session', '/api/conversation/initial', '/api/sample-plans'}
POST_ROUTES = {'/api/conversation/turn', '/api/conversation/recover', '/api/conversation/resume',
               '/api/comparison/journey', '/api/comparison/review', '/api/profile/readiness'}
DISPLAY_ROUTES = frozenset({'/api/plans/catalog', '/api/plans/detail', '/api/plans/medigap', '/api/plans/part-d',
                            # D199: the Plans workspace (profile, "Sorted for") and its priority control.
                            '/api/plans/workspace', '/api/plans/priorities'})
# D199: sign-up guides (D161), served read-only from the release.
DISPLAY_GET_ROUTES = frozenset({'/api/enrollment/content'})
ACCESS_EVENTS = GET_ROUTES | POST_ROUTES | {'/pilot/redeem'}
# D200: a visitor on a shared invitation may start a fresh visit five times. Each
# fresh start clears the current saved chat and replaces that visit, so it does not
# use one of the link's visits; per-visit and cumulative spending limits are unchanged.
RESTART_LIMIT = 5
RESTART_SQL = '''CREATE TABLE IF NOT EXISTS visit_restarts (id TEXT PRIMARY KEY REFERENCES invites(id),
    generation INTEGER NOT NULL)'''
RESTART_PARENT_SQL = '''CREATE TABLE IF NOT EXISTS visit_restart_parent (
    id TEXT PRIMARY KEY REFERENCES invites(id), parent TEXT NOT NULL REFERENCES invites(id))'''
# Visits a link has issued by redemption; a fresh start replaces a visit and is not counted.
LINK_VISITS = '''SELECT count(*) FROM visit_policy p WHERE p.link_id=?
    AND p.id NOT IN (SELECT id FROM visit_restarts)'''
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
        with self.db() as db:
            self.hosted_schema = bool(db.execute("SELECT 1 FROM sqlite_master WHERE name='visit_policy'").fetchone())
            if self.hosted_schema:
                db.execute(RESTART_SQL)   # additive; existing visits count as generation 0
                db.execute(RESTART_PARENT_SQL)

    def migrate_hosted(self):
        """Explicit additive migration; preserves every invite, cookie and revocation."""
        with self.db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS shared_links (id TEXT PRIMARY KEY,
                expires INTEGER NOT NULL, revoked INTEGER NOT NULL DEFAULT 0, max_visits INTEGER NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS visit_policy (id TEXT PRIMARY KEY REFERENCES invites(id),
                link_id TEXT, consent_version TEXT, consent_at INTEGER)''')
            db.execute(RESTART_SQL)
            db.execute(RESTART_PARENT_SQL)
        self.hosted_schema = True

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
                    CREATE TABLE shared_links (
                        id TEXT PRIMARY KEY, expires INTEGER NOT NULL,
                        revoked INTEGER NOT NULL DEFAULT 0, max_visits INTEGER NOT NULL);
                    CREATE TABLE visit_policy (
                        id TEXT PRIMARY KEY REFERENCES invites(id), link_id TEXT,
                        consent_version TEXT, consent_at INTEGER);
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

    def issue_shared(self, *, expires_at, max_visits=20):
        """Operator-only reusable invitation, bounded even when cookies are cleared."""
        if not self.hosted_schema:
            raise ValueError('Migrate invitation state before issuing a shared link.')
        key = secrets.token_hex(16)
        with self.db() as db:
            end, = db.execute('SELECT expires FROM cohort').fetchone()
            if (type(expires_at) is not int or not self.clock() < expires_at <= end
                    or type(max_visits) is not int or not 1 <= max_visits <= 100):
                raise ValueError('Use a cohort expiry and at most 100 visits.')
            if db.execute('SELECT count(*) FROM shared_links').fetchone()[0] >= 20:
                raise ValueError('At most 20 shared invitations are permitted.')
            db.execute('INSERT INTO shared_links(id,expires,max_visits) VALUES (?,?,?)',
                       (key, expires_at, max_visits))
        payload = f'{key}.{expires_at}'
        return key, f'{payload}.{hmac.digest(self.key, payload.encode(), "sha256").hex()}'

    def token_parts(self, token):
        if not isinstance(token, str) or not re.fullmatch(INVITATION_PATTERN, token):
            raise ProfileError('Invitation is unavailable.', 401)
        key, expiry, signature = token.split('.')
        payload = f'{key}.{expiry}'.encode()
        if not hmac.compare_digest(signature, hmac.digest(self.key, payload, 'sha256').hex()):
            raise ProfileError('Invitation is unavailable.', 401)
        return key,int(expiry)

    def owner_invitation(self, token):
        """Only the separately issued owner link in the test cohort may reenter."""
        if self.root.name!='test':return False
        try:
            path=self.root/'owner-master-invitation.json'
            if path.is_symlink() or path.stat().st_mode & 0o077:return False
            receipt=json.loads(path.read_text())
            key,expiry=self.token_parts(token)
            if receipt.get('link')!=key:return False
            with self.db() as db:
                row=db.execute('''SELECT max_visits FROM shared_links WHERE id=? AND expires=?
                    AND expires>? AND revoked=0 AND (SELECT expires FROM cohort)>?''',
                    (key,expiry,self.clock(),self.clock())).fetchone()
                used=db.execute(LINK_VISITS,(key,)).fetchone()[0]
                return bool(row and used<row[0])
        except (OSError,ValueError,ProfileError,sqlite3.Error):return False

    def resume(self, session, *, consent_version=None):
        if not isinstance(session,str) or not re.fullmatch('[0-9a-f]{64}',session):
            raise ProfileError('A pilot invitation is required.',401)
        if consent_version not in {None,HISTORY_NOTICE}:raise ProfileError('Review the current history notice.',428)
        with self.db() as db:
            key,_=self._active(db,'session',digest(session))
            if consent_version:
                if not self.hosted_schema:raise ProfileError('History consent is unavailable.',503)
                db.execute('''UPDATE visit_policy SET consent_version=?,consent_at=?
                    WHERE id=? AND consent_version IS NULL''',(consent_version,int(self.clock()),key))
            expiry=db.execute('SELECT expires FROM invites WHERE id=?',(key,)).fetchone()[0]
        return session,expiry-int(self.clock())

    def owner_token(self, session):
        """Recover only this authenticated owner's parent, including pre-D197 visits."""
        if self.root.name!='test':return None
        try:
            visit,_=self.authenticate(session)
            with self.db() as db:
                row=db.execute('''SELECT l.id,l.expires FROM visit_policy p JOIN shared_links l
                    ON l.id=p.link_id WHERE p.id=?''',(visit,)).fetchone()
            if not row:return None
            payload=f'{row[0]}.{row[1]}'
            token=payload+'.'+hmac.digest(self.key,payload.encode(),'sha256').hex()
            return token if self.owner_invitation(token) else None
        except (ProfileError,ValueError,sqlite3.Error):return None

    def redeem(self, token, *, consent_version=None, request_id=None, existing_session=None):
        key,expiry=self.token_parts(token)
        if consent_version not in {None,HISTORY_NOTICE}:raise ProfileError('Review the current history notice.',428)
        if request_id is not None and (not isinstance(request_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{20,100}',request_id)):
            raise ProfileError('Reload this invitation and try again.',422)
        if existing_session:
            try:
                visit,_=self.authenticate(existing_session)
                policy=self.visit_policy(visit)
                if (policy[0] or visit)==key:
                    return self.resume(existing_session,consent_version=consent_version)
            except ProfileError:pass
        now = int(self.clock())
        session = (hmac.digest(self.key,('join-request:'+request_id).encode(),'sha256').hex()
                   if request_id is not None else secrets.token_hex(32))
        with self.db() as db:
            prior=db.execute('SELECT id FROM invites WHERE session=?',(digest(session),)).fetchone()
            if prior:
                self._active(db,'id',prior[0])
                policy=db.execute('SELECT link_id,consent_version FROM visit_policy WHERE id=?',(prior[0],)).fetchone() if self.hosted_schema else (None,None)
                if (policy[0] or prior[0])!=key or policy[1]!=consent_version:
                    raise ProfileError('This invitation retry does not match the original choice.',409)
                return session,expiry-now
            link = db.execute('''SELECT max_visits FROM shared_links WHERE id=? AND expires=?
                AND expires>? AND revoked=0 AND (SELECT expires FROM cohort)>?''',
                (key, int(expiry), now, now)).fetchone() if self.hosted_schema else None
            parent = None
            if link:
                used, = db.execute(LINK_VISITS, (key,)).fetchone()
                if not getattr(self, 'unlimited_shared_admissions', False) and used >= link[0]:
                    raise ProfileError('Invitation is unavailable.', 401)
                parent, key = key, secrets.token_hex(16)
                db.execute('INSERT INTO invites(id,expires) VALUES (?,?)', (key, int(expiry)))
            updated = db.execute('''UPDATE invites SET session=? WHERE id=? AND expires=?
                AND expires>? AND revoked=0 AND session IS NULL
                AND (SELECT expires FROM cohort)>?''', (digest(session), key, int(expiry), now, now))
            if updated.rowcount != 1:
                raise ProfileError('Invitation is unavailable.', 401)
            if consent_version not in {None, HISTORY_NOTICE}:
                raise ProfileError('Review the current history notice.', 428)
            if consent_version and not self.hosted_schema:
                raise ProfileError('History consent is unavailable.', 503)
            if self.hosted_schema:
                db.execute('INSERT INTO visit_policy VALUES (?,?,?,?)',
                           (key, parent, consent_version, now if consent_version else None))
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
        policy = db.execute('SELECT link_id FROM visit_policy WHERE id=?', (row[0],)).fetchone() if self.hosted_schema else None
        if policy and policy[0] and not db.execute('''SELECT 1 FROM shared_links
                WHERE id=? AND revoked=0 AND expires>?''', (policy[0], self.clock())).fetchone():
            raise ProfileError('Pilot access has expired or was revoked.', 401)
        return row

    def visit_policy(self, key):
        with self.db() as db:
            self._active(db, 'id', key)
            row = db.execute('SELECT link_id,consent_version,consent_at FROM visit_policy WHERE id=?', (key,)).fetchone() if self.hosted_schema else None
            return row or (None, None, None)

    def _restarts_left(self, db, key, now):
        if not self.hosted_schema:
            return 0
        policy = db.execute('SELECT link_id FROM visit_policy WHERE id=?', (key,)).fetchone()
        if not policy or not policy[0]:
            return 0
        if not db.execute('''SELECT 1 FROM shared_links WHERE id=? AND revoked=0 AND expires>?
                AND (SELECT expires FROM cohort)>?''', (policy[0], now, now)).fetchone():
            return 0
        row = db.execute('SELECT generation FROM visit_restarts WHERE id=?', (key,)).fetchone()
        return max(0, getattr(self, 'restart_limit', RESTART_LIMIT) - (row[0] if row else 0))

    def session_root(self, key):
        """D206: resets share one original admission's allowance, without storing a token."""
        with self.db() as db:
            seen = set()
            while key not in seen and len(seen) <= RESTART_LIMIT:
                seen.add(key)
                parent = db.execute('SELECT parent FROM visit_restart_parent WHERE id=?', (key,)).fetchone()
                if not parent:
                    generation = db.execute('SELECT generation FROM visit_restarts WHERE id=?', (key,)).fetchone()
                    if generation and generation[0]:
                        raise ProfileError('Session allowance needs reconciliation.', 409)
                    return key
                key = parent[0]
        raise ProfileError('Session allowance needs reconciliation.', 409)

    def restarts_left(self, key):
        now = int(self.clock())
        with self.db() as db:
            self._active(db, 'id', key)
            return self._restarts_left(db, key, now)

    def restart(self, key):
        """End this shared-link visit and open a fresh one for the same browser, atomically."""
        now = int(self.clock())
        with self.db() as db:
            self._active(db, 'id', key)
            if self._restarts_left(db, key, now) < 1:
                raise ProfileError('This invitation has no fresh starts left.', 409)
            link_id, consent = db.execute('SELECT link_id,consent_version FROM visit_policy WHERE id=?', (key,)).fetchone()
            expiry, = db.execute('SELECT expires FROM invites WHERE id=?', (key,)).fetchone()
            row = db.execute('SELECT generation FROM visit_restarts WHERE id=?', (key,)).fetchone()
            fresh, session = secrets.token_hex(16), secrets.token_hex(32)
            db.execute('INSERT INTO invites(id,expires,session) VALUES (?,?,?)', (fresh, expiry, digest(session)))
            db.execute('INSERT INTO visit_policy VALUES (?,?,?,?)', (fresh, link_id, consent, now if consent else None))
            db.execute('INSERT INTO visit_restarts VALUES (?,?)', (fresh, (row[0] if row else 0) + 1))
            db.execute('INSERT INTO visit_restart_parent VALUES (?,?)', (fresh, key))
            db.execute('UPDATE invites SET revoked=1 WHERE id=?', (key,))
            left = self._restarts_left(db, fresh, now)
        return session, expiry - now, left

    def revoke_shared(self, key):
        with self.db() as db:
            if db.execute('UPDATE shared_links SET revoked=1 WHERE id=?', (key,)).rowcount != 1:
                raise ValueError('Unknown shared invitation.')

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


def install_pilot_gate(server, access, budget, *, hosted_origin=False, plan_display=False):
    parent = server.RequestHandlerClass
    pacing = PilotTurnPacing()
    manifest = Path(__file__).resolve().parents[2] / 'release-manifest.json'
    release = getattr(server,'hosted_release',None) or (hashlib.sha256(manifest.read_bytes()).hexdigest() if manifest.is_file() else 'unpackaged')

    class Handler(parent):
        def landing_navigation(self):
            landing=self.path in {'/','/pilot/join'} or re.fullmatch('/pilot/invite/'+INVITATION_PATTERN,self.path)
            return bool(self.command=='GET' and landing and
                self.headers.get('Sec-Fetch-Mode') in {None,'navigate'} and
                self.headers.get('Sec-Fetch-Dest') in {None,'document'})

        def validate_request(self):
            original=self.path
            try:
                if self.landing_navigation():self.path='/pilot/join'
                return super().validate_request()
            finally:self.path=original

        def cookie_value(self,name):
            raw=self.headers.get('Cookie','')
            if raw.count(name+'=')!=1:return None
            try:
                item=SimpleCookie(raw).get(name)
                return item.value if item else None
            except Exception:return None

        def entry_state(self):
            session=self.cookie_value(COOKIE)
            active=False;saved=False;invitation_id=None
            try:
                key,_=access.authenticate(session)
                policy=access.visit_policy(key)
                active=True;saved=policy[1]==HISTORY_NOTICE;invitation_id=policy[0] or key
            except ProfileError:pass
            owner=self.owner_reentry_token()
            return {'active':active,'savedHistory':saved,'invitationId':invitation_id,
                    'ownerReentry':bool(owner)}

        def owner_reentry_token(self):
            token=self.cookie_value(OWNER_COOKIE)
            if access.owner_invitation(token):return token
            token=access.owner_token(self.cookie_value(COOKIE))
            if token:
                age=int(token.split('.')[1])-int(access.clock())
                self._pilot_extra_cookies.append(f'{OWNER_COOKIE}={token}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age={age}')
            return token

        def redirect_entry(self):
            self.send_response(303)
            self.send_header('Location','/pilot/join')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length','0')
            self.end_headers()

        def respond(self, code, value, mime='application/json; charset=utf-8', cookie=None):
            history = getattr(server, 'hosted_history', None)
            if history and code == 200 and isinstance(value, dict):
                if self.path == '/api/conversation/progress':
                    value = {k:v for k,v in value.items() if k in {'state','stage'}}
                    if value.get('state') == 'complete' and access.visit_policy(participant.get())[1] == HISTORY_NOTICE:
                        if not history.ready(participant.get(),self.body().get('requestId')):
                            value = {'state':'working','stage':'working'}
                if self.path in {'/api/conversation/recover','/api/conversation/resume'} and value.get('response'):
                    key = participant.get()
                    if access.visit_policy(key)[1] == HISTORY_NOTICE:
                        requests = [value.get('requestId')]
                        requests.extend(t.get('requestId') for t in value.get('history',[]) if isinstance(t,dict))
                        if not all(history.ready(key,request) for request in requests):
                            return super().respond(503, {'error':'Chat history could not be verified. Chat is paused.'})
                if self.path == '/api/status':
                    agent = server.adaptive.agent
                    consented = access.visit_policy(participant.get())[1] == HISTORY_NOTICE
                    available = consented and agent.enabled and agent.client.available and budget.messaging_available(participant.get())
                    value = {**value, 'conversation_logging': True,
                             'history_notice': HISTORY_NOTICE, 'history_retention_days': 90,
                             'agent_available': available, 'live_conversation_available': available,
                             'model_configured':agent.client.available,'model_id':agent.client.model,
                             'ai_budget':budget.summary(agent.client.model)}
            return super().respond(code,value,mime,cookie)

        def origin(self):
            origin = super().origin()
            if getattr(server, 'pilot_tls', False) and origin.startswith('http://'):
                return 'https://' + origin.removeprefix('http://')
            return origin

        def send_response(self, code, message=None):
            super().send_response(code, message)
            for cookie in getattr(self,'_pilot_extra_cookies',[]):self.send_header('Set-Cookie',cookie)
            if hosted_origin or getattr(server, 'pilot_tls', False):
                self.send_header('Strict-Transport-Security', 'max-age=31536000')
            if hosted_origin:
                self.send_header('X-Daylight-Release', release)
                route = getattr(self, 'path', '')
                access_log.info('%s', json.dumps({
                    'event': 'pilot_http', 'route': route if route in ACCESS_EVENTS else 'other',
                    'status': int(code), 'time': int(time.time()), 'release': release,
                }))

        def body(self):
            if hasattr(self, '_pilot_body'):
                return self._pilot_body
            self._pilot_body = super().body()
            return self._pilot_body

        def send_header(self, name, value):
            if name == 'Set-Cookie' and value.startswith(GUEST_COOKIE + '='):
                value += '; Secure'
            return super().send_header(name, value)

        def _dispatch(self, callback):
            self.__dict__.pop('_pilot_body', None)
            self._pilot_extra_cookies=[]
            try:
                if plan_display and not self.validate_request():
                    return
                invitation_navigation = self.landing_navigation()
                if not self.safe() or (self.headers.get('Sec-Fetch-Site') == 'cross-site' and not invitation_navigation):
                    raise ProfileError('Request origin rejected.', 403)
                if '?' in self.path or not self.path.startswith('/') or self.path.startswith('//'):
                    raise ProfileError('Use the pilot URL without parameters.', 422)
                invite_path=bool(re.fullmatch('/pilot/invite/'+INVITATION_PATTERN,self.path))
                if self.command=='GET' and self.path=='/pilot/access':
                    return self.respond(200,self.entry_state())
                if self.command == 'GET' and (self.path in JOIN_ASSETS or invite_path):
                    name, mime = JOIN_ASSETS['/pilot/join' if invite_path else self.path]
                    if name == 'join.html' and getattr(server, 'hosted_history', None):
                        name = 'history-join.html'
                    return self.respond(200, (Path(__file__).parent / 'pilot-web' / name).read_bytes(), mime)
                if self.command == 'POST' and self.headers.get('Origin') != self.origin():
                    raise ProfileError('Request origin rejected.', 403)
                if self.command == 'POST' and self.path == '/pilot/redeem':
                    body = self.body()
                    consent = body.get('historyConsent')
                    if consent is not None and not getattr(server, 'hosted_history', None):
                        raise ProfileError('Saved chat is unavailable.', 503)
                    token=body.get('invitation')
                    prior=self.cookie_value(COOKIE)
                    if not token:
                        try:session,age=access.resume(prior,consent_version=consent)
                        except (ProfileError,TypeError,AttributeError):
                            token=self.cookie_value(OWNER_COOKIE)
                            if not access.owner_invitation(token):raise ProfileError('Open your full invitation link to start a visit.',401)
                            session,age=access.redeem(token,consent_version=consent,request_id=body.get('requestId'))
                    else:
                        session, age = access.redeem(token, consent_version=consent,
                            request_id=body.get('requestId'),existing_session=prior)
                    if token and access.owner_invitation(token):
                        self._pilot_extra_cookies.append(f'{OWNER_COOKIE}={token}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age={age}')
                    cookie = f'{COOKIE}={session}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age={age}'
                    return self.respond(200, {'joined': True,'newVisit':session!=prior}, cookie=cookie)
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
                    if self.command == 'GET' and plan_display:
                        routes = routes | DISPLAY_GET_ROUTES
                    if self.command == 'POST' and getattr(server,'hosted_history',None):
                        routes = routes | {'/api/pilot/history/delete','/api/conversation/progress','/api/pilot/restart'}
                    if self.command == 'GET' and getattr(server,'hosted_history',None):
                        routes = routes | {'/api/pilot/restart'}
                    # D199: present only when the hosted service actually installed them.
                    if self.command == 'POST' and getattr(server,'hosted_recommendation',False):
                        routes = routes | {'/api/recommendation'}
                    if self.command == 'POST' and getattr(server.adaptive,'conversation_checks',None) is not None:
                        routes = routes | {'/api/conversation/checks'}
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
                    if self.path == '/api/pilot/restart' and self.command == 'GET':
                        return self.respond(200, {'left': access.restarts_left(key), 'limit': getattr(access, 'restart_limit', RESTART_LIMIT)})
                    if self.path == '/api/pilot/restart':
                        self.csrf()
                        if self.body() != {'confirm': True}:
                            raise ProfileError('Confirm starting a new conversation.', 422)
                        if access.restarts_left(key) < 1:
                            raise ProfileError('This invitation has no fresh starts left.', 409)
                        if not server.hosted_turn_lock.acquire(key):
                            raise ProfileError('Wait for the current reply before starting over.', 409)
                        try:
                            server.hosted_history.delete(key)
                            session, age, left = access.restart(key)
                            server.adaptive.forget_owner(guest)
                        finally:
                            server.hosted_turn_lock.release(key)
                        return self.respond(200, {'restarted': True, 'left': left, 'limit': getattr(access, 'restart_limit', RESTART_LIMIT)},
                            cookie=f'{COOKIE}={session}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age={age}')
                    if self.path == '/api/pilot/history/delete':
                        self.csrf()
                        if self.body() != {'confirm': True}:
                            raise ProfileError('Confirm deletion of this saved visit.', 422)
                        if not server.hosted_turn_lock.acquire(key):
                            raise ProfileError('Wait for the current reply before deleting this visit.', 409)
                        try:
                            owner_token=self.owner_reentry_token()
                            server.hosted_history.delete(key)
                            access.revoke(key)
                            server.adaptive.forget_owner(guest)
                        finally:
                            server.hosted_turn_lock.release(key)
                        return self.respond(200, {'deleted': True, 'backup_expiry_days': 30,
                            'ownerReentry':bool(owner_token)},
                            cookie=f'{COOKIE}=; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=0')
                    if self.path == '/api/conversation/turn':
                        self.csrf()
                        self._pilot_body = super().body()
                        action = self._pilot_body.get('action')
                        is_message = (self._pilot_body.get('aiConsent') is True
                                      or isinstance(action, dict) and action.get('type') == 'message')
                        if is_message and (not access.chat_enabled(key) or not budget.messaging_available(key)):
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
                if error.code==401 and self.path=='/' and self.landing_navigation():return self.redirect_entry()
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
