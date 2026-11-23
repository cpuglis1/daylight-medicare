"""D186 consented hosted history. No local demo writes; no provider I/O here.

The schema is installed by a separate migration owner. The runtime role must not
own tables, bypass RLS, or have DDL/deletion-journal permissions. A response_ready
event means saved before HTTP delivery, not proof that a browser displayed it.
"""
from contextlib import contextmanager
import hashlib
import json
import re
import socket
from threading import Lock

from guest_profiles import ProfileError
from identifier_guard import find_identifiers, IDENTIFIER_MESSAGE
from pilot_access import HISTORY_NOTICE, participant

SCHEMA_VERSION = 1
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_REPLY_BYTES = 1024 * 1024
SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS hosted_history;
CREATE TABLE IF NOT EXISTS hosted_history.visits (
    visit text PRIMARY KEY, link_id text, consent_version text NOT NULL,
    consent_at bigint NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    last_activity timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL DEFAULT now() + interval '90 days',
    deleted boolean NOT NULL DEFAULT false
);
CREATE TABLE IF NOT EXISTS hosted_history.turns (
    visit text NOT NULL REFERENCES hosted_history.visits(visit), request_id text NOT NULL,
    signature text NOT NULL, accepted_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz, status text NOT NULL CHECK (status IN ('accepted','response_ready','failed')),
    submitted jsonb NOT NULL, response jsonb, metadata jsonb NOT NULL,
    usage jsonb, error_code integer,
    PRIMARY KEY (visit, request_id)
);
CREATE TABLE IF NOT EXISTS hosted_history.deletions (
    visit text PRIMARY KEY, deleted_at timestamptz NOT NULL DEFAULT now(), reason text NOT NULL
);
ALTER TABLE hosted_history.visits ENABLE ROW LEVEL SECURITY;
ALTER TABLE hosted_history.visits FORCE ROW LEVEL SECURITY;
ALTER TABLE hosted_history.turns ENABLE ROW LEVEL SECURITY;
ALTER TABLE hosted_history.turns FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS visit_isolation ON hosted_history.visits;
CREATE POLICY visit_isolation ON hosted_history.visits
    USING (visit = current_setting('daylight.visit', true))
    WITH CHECK (visit = current_setting('daylight.visit', true));
DROP POLICY IF EXISTS turn_isolation ON hosted_history.turns;
CREATE POLICY turn_isolation ON hosted_history.turns
    USING (visit = current_setting('daylight.visit', true))
    WITH CHECK (visit = current_setting('daylight.visit', true));
REVOKE ALL ON SCHEMA hosted_history FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA hosted_history FROM PUBLIC;
CREATE OR REPLACE FUNCTION hosted_history.guard_turn_update() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, hosted_history AS $$
BEGIN
    IF OLD.status <> 'accepted' OR NEW.status NOT IN ('response_ready','failed')
       OR ROW(NEW.visit,NEW.request_id,NEW.signature,NEW.accepted_at,NEW.submitted,NEW.metadata)
          IS DISTINCT FROM ROW(OLD.visit,OLD.request_id,OLD.signature,OLD.accepted_at,OLD.submitted,OLD.metadata)
    THEN RAISE EXCEPTION 'History is immutable after acceptance'; END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS immutable_turn ON hosted_history.turns;
CREATE TRIGGER immutable_turn BEFORE UPDATE ON hosted_history.turns
    FOR EACH ROW EXECUTE FUNCTION hosted_history.guard_turn_update();
CREATE OR REPLACE FUNCTION hosted_history.delete_visit(target text) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, hosted_history AS $$
BEGIN
    IF target IS DISTINCT FROM current_setting('daylight.visit', true) THEN
        RAISE EXCEPTION 'Visit mismatch';
    END IF;
    INSERT INTO hosted_history.deletions(visit,reason) VALUES (target,'participant_request')
        ON CONFLICT(visit) DO NOTHING;
    DELETE FROM hosted_history.turns WHERE visit=target;
    UPDATE hosted_history.visits SET deleted=true WHERE visit=target;
    RETURN true;
END $$;
REVOKE ALL ON FUNCTION hosted_history.delete_visit(text) FROM PUBLIC;
"""
# D199 migration (applied by root through postgres peer auth, never by the runtime role):
# checked reply blocks are saved before the page may show them. Rows follow their turn
# on deletion and expiry through the foreign key.
BLOCKS_SQL = """
CREATE TABLE IF NOT EXISTS hosted_history.turn_blocks (
    visit text NOT NULL, request_id text NOT NULL, blocks jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (visit, request_id),
    FOREIGN KEY (visit, request_id) REFERENCES hosted_history.turns(visit, request_id) ON DELETE CASCADE
);
ALTER TABLE hosted_history.turn_blocks ENABLE ROW LEVEL SECURITY;
ALTER TABLE hosted_history.turn_blocks FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS block_isolation ON hosted_history.turn_blocks;
CREATE POLICY block_isolation ON hosted_history.turn_blocks
    USING (visit = current_setting('daylight.visit', true))
    WITH CHECK (visit = current_setting('daylight.visit', true));
REVOKE ALL ON hosted_history.turn_blocks FROM PUBLIC;
"""
# Applied with psycopg.sql.Identifier for the runtime role (daylight_app on the host).
BLOCKS_GRANT_SQL = 'GRANT SELECT, INSERT, UPDATE(blocks, updated_at) ON hosted_history.turn_blocks TO {}'

# Auth/recovery bearer values and model internals are never history content.
PRIVATE_KEYS = frozenset({'csrf', 'token', 'reviewToken', 'continuation', 'pendingId',
    'cookie', 'authorization', 'api_key', 'apikey', 'password', 'secret',
    'system_prompt', 'prompt', 'reasoning', 'chain_of_thought'})
PRIVATE_LOWER = {key.lower() for key in PRIVATE_KEYS}
REQUEST_KEYS = frozenset({'guide','record','action','requestId','aiConsent','pendingId',
    'contextPolicy','continuation','model','aiProvider','plansContext','plansContextPolicy'})


def content(value, *, submitted=False, depth=0):
    """Bounded JSON projection. Refuse prohibited input before any durable write."""
    if depth > 30:
        raise ProfileError('Use a bounded conversation request.', 422)
    if isinstance(value, dict):
        return {k: content(v, submitted=submitted, depth=depth + 1) for k,v in value.items()
                if k.lower() not in PRIVATE_LOWER}
    if isinstance(value, list):
        return [content(v, submitted=submitted, depth=depth + 1) for v in value]
    if isinstance(value, str):
        if find_identifiers(value) or re.search(r'\bsk-[A-Za-z0-9_-]{16,}', value):
            if submitted:
                raise ProfileError(IDENTIFIER_MESSAGE, 422)
            return '[identifier removed]'
    return value


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


class HistoryUnavailable(ProfileError):
    def __init__(self):
        super().__init__('Chat history could not be saved. Chat is paused; you can still browse.', 503)


def durable_delete(environment, visit, *, socket_path='/run/daylight-delete/socket'):
    """The private maintenance broker journals to S3 before removing a visit."""
    if environment not in {'pilot','test'} or not re.fullmatch('[0-9a-f]{32}',str(visit)):
        raise HistoryUnavailable()
    try:
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
            client.settimeout(80)
            client.connect(socket_path)
            client.sendall((json.dumps({'environment':environment,'visit':visit})+'\n').encode())
            raw=b''
            while not raw.endswith(b'\n') and len(raw)<=128:
                part=client.recv(129-len(raw))
                if not part:break
                raw+=part
            if len(raw)>128 or json.loads(raw)!={'deleted':True}:
                raise HistoryUnavailable()
    except Exception:
        raise ProfileError('Deletion could not be confirmed. Please try again or contact the demo owner.',503) from None


class PostgresHistory:
    def __init__(self, dsn, *, connect=None, deletion_environment=None):
        if deletion_environment is not None and deletion_environment not in {'pilot','test'}:
            raise ValueError('Use a dedicated hosted deletion environment.')
        if connect is None:
            import psycopg
            connect = psycopg.connect
        self.connect = connect
        self.dsn = dsn
        self.deletion_environment = deletion_environment

    def check_runtime_role(self):
        with self.db('0'*32) as db:
            row=db.execute('''SELECT r.rolsuper,r.rolbypassrls,
                has_schema_privilege(current_user,'hosted_history','CREATE'),
                EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                    WHERE n.nspname='hosted_history' AND c.relowner=r.oid)
                FROM pg_roles r WHERE r.rolname=current_user''').fetchone()
            if row != (False,False,False,False):
                raise HistoryUnavailable()

    @contextmanager
    def db(self, visit):
        if not isinstance(visit, str) or not re.fullmatch(r'[0-9a-f]{32}', visit):
            raise HistoryUnavailable()
        try:
            with self.connect(self.dsn, connect_timeout=3) as db:
                db.execute("SET LOCAL statement_timeout = '3s'")
                db.execute("SET LOCAL lock_timeout = '2s'")
                db.execute("SELECT set_config('daylight.visit', %s, true)", (visit,))
                yield db
        except ProfileError:
            raise
        except Exception:
            # Never return a connection string, SQL parameter, or driver exception.
            raise HistoryUnavailable() from None

    def begin(self, visit, request, policy, payload, metadata):
        link, consent, consent_at = policy
        if consent != HISTORY_NOTICE:
            raise ProfileError('Saved chat requires agreement to the history notice.', 428)
        signature = hashlib.sha256(encoded(payload).encode()).hexdigest()
        submitted=encoded(content(payload,submitted=True))
        if len(submitted.encode()) > 80000:
            raise ProfileError('Use a bounded conversation request.', 413)
        with self.db(visit) as db:
            size,=db.execute("""SELECT pg_total_relation_size('hosted_history.visits') +
                pg_total_relation_size('hosted_history.turns')""").fetchone()
            if size + MAX_REPLY_BYTES + 80000 > MAX_ARCHIVE_BYTES:
                raise HistoryUnavailable()
            db.execute('''INSERT INTO hosted_history.visits(visit,link_id,consent_version,consent_at)
                VALUES (%s,%s,%s,%s) ON CONFLICT(visit) DO NOTHING''', (visit,link,consent,consent_at))
            row = db.execute('''SELECT deleted, expires_at>now() FROM hosted_history.visits
                WHERE visit=%s FOR UPDATE''', (visit,)).fetchone()
            if not row or row[0] or not row[1]:
                raise ProfileError('This saved visit has ended.', 410)
            prior = db.execute('''SELECT signature,status FROM hosted_history.turns
                WHERE visit=%s AND request_id=%s''', (visit,request)).fetchone()
            if prior:
                if prior[0] != signature:
                    raise ProfileError('This request reference belongs to another turn.', 409)
                return prior[1]
            if db.execute("SELECT 1 FROM hosted_history.turns WHERE visit=%s AND status='accepted' LIMIT 1",(visit,)).fetchone():
                raise HistoryUnavailable()
            count, = db.execute('SELECT count(*) FROM hosted_history.turns WHERE visit=%s', (visit,)).fetchone()
            if count >= 200:
                raise ProfileError('This demo visit has reached its turn limit. You can still browse.', 429)
            db.execute('''INSERT INTO hosted_history.turns
                (visit,request_id,signature,status,submitted,metadata)
                VALUES (%s,%s,%s,'accepted',%s::jsonb,%s::jsonb)''',
                (visit,request,signature,submitted,encoded(metadata)))
            db.execute("""UPDATE hosted_history.visits SET last_activity=now(),
                expires_at=now()+interval '90 days' WHERE visit=%s""", (visit,))
        return None

    def finish(self, visit, request, response, usage, error_code=None):
        response_json,usage_json=encoded(content(response)),encoded(usage)
        if len(response_json.encode()) + len(usage_json.encode()) > MAX_REPLY_BYTES:
            raise HistoryUnavailable()
        with self.db(visit) as db:
            result = db.execute('''UPDATE hosted_history.turns SET finished_at=now(),status=%s,
                response=%s::jsonb,usage=%s::jsonb,error_code=%s
                WHERE visit=%s AND request_id=%s AND status='accepted' ''',
                ('failed' if error_code else 'response_ready', response_json,
                 usage_json, error_code, visit, request))
            if result.rowcount != 1:
                raise HistoryUnavailable()

    def check_blocks(self):
        """True only when the D199 block table exists with exactly insert/update/select rights."""
        try:
            with self.db('0'*32) as db:
                row = db.execute("""SELECT to_regclass('hosted_history.turn_blocks') IS NOT NULL,
                    has_table_privilege(current_user,'hosted_history.turn_blocks','INSERT'),
                    has_table_privilege(current_user,'hosted_history.turn_blocks','DELETE')""").fetchone()
        except HistoryUnavailable:
            return False
        return bool(row) and row[0] is True and row[1] is True and row[2] is False

    def publish_blocks(self, visit, request, blocks):
        """Save checked blocks for an accepted turn; the page may show them only after this commits."""
        stored = content(blocks)
        if stored != blocks:
            return False  # an identifier was found: keep the block hidden until the full reply
        value = encoded(stored)
        if len(value.encode()) > MAX_REPLY_BYTES:
            return False
        with self.db(visit) as db:
            result = db.execute("""INSERT INTO hosted_history.turn_blocks(visit,request_id,blocks)
                SELECT %s,%s,%s::jsonb WHERE EXISTS (SELECT 1 FROM hosted_history.turns
                    WHERE visit=%s AND request_id=%s AND status='accepted')
                ON CONFLICT (visit,request_id) DO UPDATE SET blocks=excluded.blocks, updated_at=now()""",
                (visit, request, value, visit, request))
            return result.rowcount == 1

    def read(self, visit):
        """Internal scoped read. No unauthenticated HTTP archive/export endpoint."""
        with self.db(visit) as db:
            return db.execute('''SELECT request_id,status,submitted,response,metadata,usage,error_code,
                accepted_at,finished_at FROM hosted_history.turns t JOIN hosted_history.visits v USING(visit)
                WHERE t.visit=%s AND NOT v.deleted AND v.expires_at>now()
                ORDER BY accepted_at,request_id''', (visit,)).fetchall()

    def ready(self, visit, request):
        with self.db(visit) as db:
            return bool(db.execute('''SELECT 1 FROM hosted_history.turns t
                JOIN hosted_history.visits v USING(visit) WHERE t.visit=%s AND request_id=%s
                AND status='response_ready' AND NOT v.deleted AND v.expires_at>now()''',
                (visit,request)).fetchone())

    def delete(self, visit):
        if self.deletion_environment is not None:
            durable_delete(self.deletion_environment,visit)
            return
        with self.db(visit) as db:
            db.execute('SELECT hosted_history.delete_visit(%s)', (visit,))


class VisitLocks:
    """Non-blocking per-visit turn locks with a bounded number of concurrent visits."""
    def __init__(self, limit=4):
        self.limit, self.busy, self.guard = limit, set(), Lock()

    def acquire(self, visit):
        with self.guard:
            if visit is None or visit in self.busy or len(self.busy) >= self.limit:
                return False
            self.busy.add(visit)
            return True

    def release(self, visit):
        with self.guard:
            self.busy.discard(visit)


def install(server, access, history, budget, metadata):
    """Wrap the existing turn, never the local runtime, before installing the gate."""
    required = {'release','data_snapshot','model','reasoning','prompt_policy'}
    if (not required <= set(metadata) <= required | {'service_tier'}
            or metadata.get('service_tier', 'default') not in {'default', 'ultrafast'}
            or any(not isinstance(v,str) or not v for v in metadata.values())
            or metadata['model'] != 'gpt-6.1-sol' or metadata['reasoning'] != 'low'):
        raise ValueError('Hosted history requires exact release/data/model attribution.')
    original = server.adaptive.turn
    # Only this process may replay its already-authorized, still-live RAM receipt.
    # After a crash, accepted/ready records never cause automatic paid replay.
    completed = set()

    def turn(owner, payload):
        visit = participant.get()
        if (not isinstance(payload,dict) or set(payload)-REQUEST_KEYS
                or not re.fullmatch(r'[A-Za-z0-9-]{10,80}', str(payload.get('requestId','')))):
            raise ProfileError('Use a current conversation request.', 422)
        policy = access.visit_policy(visit)
        action = payload.get('action', {})
        if not isinstance(action,dict):
            raise ProfileError('Use a supported conversation action.', 422)
        paid = payload.get('aiConsent') is True or action.get('type') == 'message'
        if paid and getattr(server,'hosted_paused',False):
            raise ProfileError('Chat is paused. You can still use the guide.',503)
        if policy[1] != HISTORY_NOTICE:
            if paid:
                raise ProfileError('Saved chat requires agreement to the history notice.', 428)
            return original(owner,payload)  # deterministic browsing, no silent archive
        content(payload, submitted=True)
        request = payload['requestId']
        state = history.begin(visit,request,policy,payload,metadata)
        if state is not None:
            if state == 'response_ready' and (visit,request) in completed:
                # Require the existing flow receipt; don't re-execute after eviction.
                with server.adaptive.lock:
                    entry = server.adaptive.turn_journal.get((owner,request))
                    if entry is not None:
                        return server.adaptive.replay_response(owner,entry['response'])
            raise ProfileError('This turn is already recorded. Recover the visit before sending again.', 409)
        try:
            result = original(owner,payload)
        except Exception as error:
            history.finish(visit,request,None,budget.visit_usage(visit),
                           error.code if isinstance(error,ProfileError) else 500)
            raise
        # This commit must finish before the HTTP handler can send the reply.
        history.finish(visit,request,result,budget.visit_usage(visit))
        completed.add((visit,request))
        return result

    # D199: one turn at a time per visit (not per server), with a small overall cap
    # so several invited visitors can chat at once on the one host.
    lock = VisitLocks()
    def serialized_turn(owner,payload):
        visit = participant.get()
        if not lock.acquire(visit):
            raise ProfileError('Daylight is busy. Please wait before sending again.', 429)
        try:
            return turn(owner,payload)
        finally:
            lock.release(visit)
    server.adaptive.turn = serialized_turn
    server.hosted_history = history
    server.hosted_turn_lock = lock
    return server
