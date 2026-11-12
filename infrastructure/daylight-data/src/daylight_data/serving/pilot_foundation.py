"""Private D146 evidence reads. No application registration or participant purpose."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from .binding import ResearchServingError, digest
from .provider_candidates import _pattern, _query
from .repository import json_safe


SCHEMA = 'dl_pilot_foundation'
VERSION = 'daylight-pilot-foundation/1'
MAX_PAGE = 50
MAX_RESPONSE_BYTES = 8 * 1024**2


def file_hash(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def source_controls(dsn):
    """Any change to the local authoritative STOP ledger invalidates the snapshot."""
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=3,
                         options='-c default_transaction_read_only=on -c statement_timeout=5000') as conn:
        identity = conn.execute('''SELECT datname AS database, oid AS database_oid,
            (SELECT system_identifier::text FROM pg_control_system()) AS cluster_system_identifier
            FROM pg_database WHERE datname=current_database()''').fetchone()
        rows = conn.execute('''SELECT source_id,state,reason,updated_at
            FROM dl_control.source_access_state ORDER BY source_id''').fetchall()
    return {**identity, 'source_access_states': json_safe(rows)}


def enforce_scope(manifest, *, year, county_fips, purpose, now):
    policy = manifest['policy']
    if type(year) is not int or year != policy['year']:
        raise ResearchServingError('PILOT_WRONG_YEAR')
    if county_fips != policy['plan_county_fips']:
        raise ResearchServingError('PILOT_UNSUPPORTED_PLAN_GEOGRAPHY')
    if purpose == 'participant':
        raise ResearchServingError('PILOT_PARTICIPANT_ACCEPTANCE_MISSING')
    if purpose != 'offline_research' or purpose != policy['purpose']:
        raise ResearchServingError('PILOT_PURPOSE_NOT_ALLOWED')
    deadlines = [policy['technical_read_until_utc'],
                 *(date for date in policy['source_review_expiry'].values() if date)]
    if now >= min(datetime.fromisoformat(value) for value in deadlines):
        raise ResearchServingError('PILOT_EVIDENCE_STALE')


class PilotFoundation:
    """Exact and literal reads over the verified projection, gated on every call."""

    def __init__(self, binding_path, *, root, package_dsn, source_dsn,
                 clock=lambda: datetime.now(timezone.utc)):
        self.root = Path(root).resolve()
        self.manifest = json.loads(Path(binding_path).read_text())
        body = {key: value for key, value in self.manifest.items() if key != 'binding_id'}
        if body.get('schema') != VERSION or digest(body) != self.manifest.get('binding_id'):
            raise ResearchServingError('PILOT_BINDING_INVALID')
        self.package_dsn = package_dsn
        self.source_dsn = source_dsn
        self.clock = clock

    def _check_controls(self):
        try:
            live = source_controls(self.source_dsn)
            for path, expected in self.manifest['controls'].items():
                local = (self.root / path).resolve()
                if not local.is_relative_to(self.root) or file_hash(local) != expected:
                    raise ResearchServingError('PILOT_SOURCE_CONTROL_CHANGED')
        except (psycopg.Error, OSError):
            raise ResearchServingError('PILOT_SOURCE_CONTROLS_UNAVAILABLE') from None
        if live != self.manifest['source_control_snapshot'] or any(
                row['state'] != 'permitted' for row in live['source_access_states']):
            raise ResearchServingError('PILOT_SOURCE_WITHDRAWAL_OR_CONTROL_CHANGE')

    @contextmanager
    def snapshot(self, *, year, county_fips, purpose):
        """Bound read-only connection for internal, fixed-query projections."""
        scope = {'year': year, 'county_fips': county_fips, 'purpose': purpose}
        enforce_scope(self.manifest, **scope, now=self.clock())
        self._check_controls()
        try:
            with psycopg.connect(self.package_dsn, row_factory=dict_row, connect_timeout=3,
                                 options='-c default_transaction_read_only=on -c statement_timeout=5000') as conn:
                stamp = conn.execute('SELECT current_database() AS db, binding_id FROM dl_pilot_foundation.binding').fetchone()
                if stamp != {'db': self.manifest['database'], 'binding_id': self.manifest['binding_id']}:
                    raise ResearchServingError('PILOT_DATABASE_BINDING_MISMATCH')
                yield conn
        except psycopg.Error:
            raise ResearchServingError('PILOT_DATABASE_UNAVAILABLE') from None
        self._check_controls()
        enforce_scope(self.manifest, **scope, now=self.clock())

    def read(self, dataset, *, year, county_fips, purpose, filters=None, name=None,
             limit=MAX_PAGE, after=0, expected_binding=None):
        """Return source observations and an ordinal cursor bound to this revision."""
        scope = {'year': year, 'county_fips': county_fips, 'purpose': purpose}
        enforce_scope(self.manifest, **scope, now=self.clock())
        binding = self.manifest['binding_id']
        if ((after and expected_binding is None)
                or expected_binding is not None and expected_binding != binding):
            raise ResearchServingError('PILOT_BINDING_CHANGED')
        if not isinstance(dataset, str) or dataset not in self.manifest['datasets']:
            raise ResearchServingError('PILOT_DATASET_UNSUPPORTED')
        spec = self.manifest['datasets'][dataset]
        filters = {} if filters is None else filters
        if (type(after) is not int or not 0 <= after <= spec['rows']
                or type(limit) is not int or not 1 <= limit <= MAX_PAGE
                or not isinstance(filters, dict) or not set(filters) <= set(spec['filters'])
                or any(not isinstance(value, str) or not value or len(value) > 512
                       or '\x00' in value for value in filters.values())
                or (name is None and not filters)
                or (name is not None and not spec['name_search'])):
            raise ResearchServingError('PILOT_INVALID_QUERY')
        predicates = [sql.SQL('ordinal > %s')]
        params = [after]
        for key, value in filters.items():
            if key == 'npi' and spec['npi_array']:
                predicates.append(sql.SQL('npis ? %s'))
            else:
                predicates.append(sql.SQL('(data ->> {}) = %s').format(sql.Literal(key)))
            params.append(value)
        if name is not None:
            words, _ = _query(name)
            match = sql.SQL(' AND ').join([sql.SQL("variant ILIKE %s ESCAPE '!'")] * len(words))
            predicates.append(sql.SQL('EXISTS (SELECT 1 FROM unnest(names) AS variant WHERE {})').format(match))
            params.extend(_pattern(word) for word in words)
        with self.snapshot(**scope) as conn:
            query = sql.SQL('SELECT ordinal, data FROM {}.{} WHERE {} ORDER BY ordinal LIMIT %s').format(
                sql.Identifier(SCHEMA), sql.Identifier(dataset), sql.SQL(' AND ').join(predicates))
            rows = conn.execute(query, (*params, limit + 1)).fetchall()
        records = [
            {'ordinal': row['ordinal'], 'data': row['data'],
             'locator': {'artifact': spec['artifact'], 'artifact_sha256': spec['artifact_sha256'],
                         'source_table': spec['source_table'],
                         'key': {key: row['data'][key] for key in spec['locator_fields']}}}
            for row in rows[:limit]
        ]
        if len(json.dumps(records, ensure_ascii=False).encode()) > MAX_RESPONSE_BYTES:
            raise ResearchServingError('PILOT_RESPONSE_TOO_LARGE')
        return {
            'binding_id': binding, 'package_id': self.manifest['policy']['package_id'], **scope,
            'state': 'source_observations' if records else 'unknown_no_retained_observation',
            'capability': self.manifest['policy']['capabilities'][spec['capability']],
            'acceptance': self.manifest['policy']['acceptance'],
            'records': records, 'next_after': records[-1]['ordinal'] if len(rows) > limit else None,
        }
