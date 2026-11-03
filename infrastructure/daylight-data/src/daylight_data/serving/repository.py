"""Bounded PostgreSQL reads of the exact 2026 Collier MA research selection.

No profiles, new acquisition, mutation, source-use approval or consumer promotion.
The developer research envelope preserves native observations and all holds.
"""
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
import copy
import os
import re
import time

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from .binding import VERSION, SCOPE, ResearchServingError, digest, load_local_binding
from pathlib import Path

PURPOSES = ('published_display', 'personal_comparison', 'ranking', 'recommendation', 'quote', 'enrollment')
STATE_KEYS = ('value_state', 'evidence_state', 'semantic_review_state', 'source_use_state',
              'freshness_state', 'output_acceptance_state')

CATALOG = """WITH scope AS MATERIALIZED (
 SELECT o.fields->>'id' AS native_id,r.raw_payload->>'id' AS raw_native_id,
 o.source_row_ordinal AS source_ordinal,o.source_row_ordinal,o.source_table,o.derivation_id,
 o.fields,o.conditions,o.value_state,o.evidence_state,o.semantic_review_state,o.source_use_state,
 o.freshness_state,o.output_acceptance_state,r.raw_sha256,r.record_id,r.source_row_key,r.ordinal_basis,
 s.snapshot_id,s.original_path,s.artifact_sha256,d.adapter_code_sha256
 FROM dl_evidence.observation o
 JOIN dl_evidence.source_record r USING(derivation_id,source_table,source_row_ordinal)
 JOIN dl_control.derivation d USING(derivation_id)
 JOIN dl_control.source_snapshot s USING(snapshot_id)
 WHERE o.derivation_id=%s AND o.entity_type='collier_offering_scope' AND o.source_table='collier_offerings')
 SELECT c.*,n.offering_id AS national_id,n.plan_name AS national_name,
 n.contract_id,n.plan_id,n.segment_id,n.category,
 n.derivation_id AS national_derivation_id,n.source_table AS national_source_table,
 n.source_row_ordinal AS national_source_ordinal,
 EXISTS(SELECT 1 FROM dl_evidence.observation x WHERE x.derivation_id=%s
   AND x.entity_type='ma_semantic_claim_representation' AND x.offering_id=c.native_id) AS r9_identity_present
 FROM scope c LEFT JOIN dl_evidence.offering n
 ON n.derivation_id=%s AND n.offering_id=c.native_id
 ORDER BY c.source_ordinal"""

OBSERVATIONS = """WITH selected AS MATERIALIZED (
 SELECT o.derivation_id,o.entity_type,o.entity_id FROM dl_evidence.observation o
 WHERE o.derivation_id=%s AND o.entity_type=ANY(%s) AND o.entity_id>%s
 AND {identity_predicate} ORDER BY o.entity_id LIMIT %s)
 SELECT o.*,r.raw_payload,r.raw_sha256,r.record_id,r.source_row_key,r.ordinal_basis,
 d.snapshot_id,d.adapter_code_sha256,s.original_path,s.artifact_sha256
 FROM selected k JOIN dl_evidence.observation o USING(derivation_id,entity_type,entity_id)
 JOIN dl_evidence.source_record r USING(derivation_id,source_table,source_row_ordinal)
 JOIN dl_control.derivation d USING(derivation_id)
 JOIN dl_control.source_snapshot s USING(snapshot_id)
 ORDER BY o.entity_id"""
# Predicates below are fixed module constants. User strings are always parameters.
PLAN_OBSERVATIONS = OBSERVATIONS.format(identity_predicate='o.offering_id=%s')
QUALITY_OBSERVATIONS = OBSERVATIONS.format(identity_predicate="o.fields->>'contract_id'=%s")


def json_safe(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: json_safe(child) for key, child in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_safe(child) for child in value]
    return value


def _scope(scope):
    if (not isinstance(scope, dict) or set(scope) != set(SCOPE)
            or type(scope.get('year')) is not int or scope != SCOPE):
        raise ResearchServingError('UNSUPPORTED_RESEARCH_SCOPE')
    return dict(SCOPE)


def _limit(limit):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ResearchServingError('PAGE_LIMIT_OUT_OF_RANGE')


def validate_local_dsn(dsn, repository_root, binding):
    """The current local factory never silently follows another host/cluster."""
    info = conninfo_to_dict(dsn)
    expected = str((Path(repository_root).resolve() / 'infrastructure/daylight-data/.state/socket').resolve())
    if (info.get('host') != expected or info.get('port') != '55485'
            or info.get('dbname') != binding.database or info.get('hostaddr') or info.get('service')):
        raise ResearchServingError('EXACT_LOCAL_RESEARCH_TARGET_REQUIRED')


def validate_local_connection(connection, target):
    """Initial read-only ownership phase, before any source query or role change."""
    with connection.transaction():
        connection.execute('SET TRANSACTION READ ONLY')
        row = connection.execute("""SELECT current_database() AS database,d.oid AS database_oid,
            shobj_description(d.oid,'pg_database') AS marker,
            (SELECT system_identifier::text FROM pg_control_system()) AS cluster_system_identifier,
            current_setting('port') AS port,inet_server_addr() IS NULL AS unix_socket
            FROM pg_database d WHERE datname=current_database()""").fetchone()
        if (any(row.get(key) != target.get(key) for key in
                ('database', 'database_oid', 'marker', 'cluster_system_identifier'))
                or row['port'] != '55485' or row['unix_socket'] is not True):
            raise ResearchServingError('ACTUAL_LOCAL_RESEARCH_TARGET_MISMATCH')
        return dict(row)


def _lineage(row):
    return {key: row.get(key) for key in ('derivation_id', 'snapshot_id', 'artifact_sha256',
        'original_path', 'source_table', 'source_row_ordinal', 'source_row_key', 'ordinal_basis',
        'raw_sha256', 'record_id', 'adapter_code_sha256')}


class ResearchPlanRepository:
    def __init__(self, connection_factory, binding, *, timeout_ms=5000):
        if not callable(connection_factory) or not 1 <= timeout_ms <= 30000:
            raise ResearchServingError('RESEARCH_REPOSITORY_CONFIGURATION')
        self._connection_factory, self.binding, self.timeout_ms = connection_factory, binding, timeout_ms

    def close(self):
        """Connections are already closed at each call; no shared session/pool."""

    @contextmanager
    def _read(self):
        with self._connection_factory() as connection:
            if connection.info.server_version // 10000 not in {17, 18}:
                raise ResearchServingError('UNSUPPORTED_POSTGRES_MAJOR')
            with connection.transaction():
                connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
                connection.execute('SET LOCAL ROLE daylight_research_reader')
                connection.execute("SELECT set_config('statement_timeout',%s,true)", (str(self.timeout_ms),))
                database = connection.execute('SELECT current_database() AS database').fetchone()['database']
                if database != self.binding.database:
                    raise ResearchServingError('DATABASE_BINDING_MISMATCH')
                selected = self.binding.selections
                rows = connection.execute("""SELECT d.derivation_id,d.adapter_code_sha256,s.original_path,s.artifact_sha256
                    FROM dl_control.derivation d JOIN dl_control.source_snapshot s USING(snapshot_id)
                    WHERE d.derivation_id=ANY(%s)""", ([v['derivation_id'] for v in selected.values()],)).fetchall()
                expected = {(v['derivation_id'], v['adapter_code_sha256'], v['source_path'], v['source_sha256']) for v in selected.values()}
                if {(r['derivation_id'], r['adapter_code_sha256'], r['original_path'], r['artifact_sha256']) for r in rows} != expected:
                    raise ResearchServingError('DATABASE_SOURCE_BINDING_MISMATCH')
                jobs = connection.execute("""SELECT j.job_id,j.state,j.payload->>'build_id' AS job_build_id,
                    r.controls->>'build_id' AS receipt_build_id,r.retained_rows,r.stream_sha256
                    FROM dl_control.job j JOIN dl_control.ingest_receipt r USING(job_id)
                    WHERE j.job_id=ANY(%s)""", ([r['job_id'] for r in self.binding.unit_receipts],)).fetchall()
                expected_jobs = {(r['job_id'], 'complete', self.binding.build_id, self.binding.build_id,
                                  r['source_rows'], r['stream_sha256']) for r in self.binding.unit_receipts}
                if {(r['job_id'], r['state'], r['job_build_id'], r['receipt_build_id'], r['retained_rows'], r['stream_sha256']) for r in jobs} != expected_jobs:
                    raise ResearchServingError('DATABASE_EXECUTION_BINDING_MISMATCH')
                access = connection.execute("""SELECT source_id,state,reason,updated_at FROM dl_control.source_access_state
                    WHERE source_id=ANY(%s) ORDER BY source_id""",
                    (['sealed-local:L02', 'sealed-local:L03', 'sealed-local:L09', 'L02', 'L03', 'L09'],)).fetchall()
                yield connection, json_safe(access)

    def _envelope(self, access):
        snapshot = digest({'binding': self.binding.binding_id, 'source_access_states': access})
        return {'contract_id': VERSION, 'status': 'research_only', 'scope': dict(SCOPE),
                'binding': {'snapshot_id': snapshot, 'build_id': self.binding.build_id,
                            'manifest_sha256': self.binding.manifest_sha256,
                            'adapter_sha256': self.binding.adapter_sha256,
                            'selected_derivations': copy.deepcopy(self.binding.selections),
                            'accepted_release_id': None},
                'authority': {purpose: {'state': 'held', 'authority_refs': [],
                    'reason_codes': ['EXACT_RELEASE_REQUIRED', 'SOURCE_USE_REVIEW_REQUIRED', 'POLICY_NOT_ACCEPTED']}
                    for purpose in PURPOSES},
                'source_access_states': access,
                'limitations': ['Developer source inspection, not a released consumer inventory.',
                    '72 selected source offerings are not an accepted all-market denominator or personal availability.',
                    'L03 rows are source-scoped research claims/conditions, not verified benefits.',
                    'L09 evidence is contract-grain context, not plan-specific personal fit.',
                    'Standalone PDP, Medigap and other coverage paths need separate identity/query scopes.'],
                'personal_recommendation_available': False, 'new_acceptance': False}

    def _catalog(self, connection):
        d = self.binding.selections
        rows = connection.execute(CATALOG, (d['collier']['derivation_id'], d['semantic']['derivation_id'], d['national']['derivation_id'])).fetchall()
        ids = [r['native_id'] for r in rows]
        if (len(rows) != 72 or len(set(ids)) != 72
                or any(not isinstance(i, str) or not re.fullmatch(r'2026:[A-Z][0-9]{4}:[0-9]{3}:[0-9]{3}', i) for i in ids)
                or any(r['native_id'] != r['raw_native_id'] or r['native_id'] != r['national_id']
                       or r['r9_identity_present'] is not True for r in rows)):
            raise ResearchServingError('EXACT_72_IDENTITY_BRIDGE_MISMATCH')
        return rows

    @staticmethod
    def _plan(row):
        year, contract, plan, segment = row['native_id'].split(':')
        fields = row['fields']
        return {'offering_id': row['native_id'],
                'identity': {'kind': 'cms_offering', 'year': int(year), 'contract_id': contract,
                             'plan_id': plan, 'segment_id': segment},
                'source_ordinal': row['source_ordinal'], 'native_id': row['raw_native_id'],
                'display_name': fields.get('name') or row.get('national_name'),
                'plan_type': fields.get('plan_type'), 'category': fields.get('category'),
                'source_native_fields': copy.deepcopy(fields), 'restrictions': copy.deepcopy(row['conditions']),
                'states': {key: row[key] for key in STATE_KEYS}, 'lineage': _lineage(row),
                'identity_bridge': {'national_id': row['national_id'], 'r9_present': True,
                    'national_derivation_id': row['national_derivation_id'],
                    'national_source_table': row['national_source_table'],
                    'national_source_ordinal': row['national_source_ordinal']},
                'verified_availability': False, 'personal_applicability': 'not_assessed',
                'output_authority': 'held', 'source_native_flags_are_not_authority': True}

    def list_plans(self, scope, after_ordinal=None, limit=20, *, expected_snapshot_id=None):
        _scope(scope); _limit(limit)
        after = 0 if after_ordinal is None else after_ordinal
        if type(after) is not int or not 0 <= after <= 72:
            raise ResearchServingError('INVALID_SOURCE_ORDINAL_CURSOR')
        with self._read() as (connection, access):
            result = self._envelope(access)
            if expected_snapshot_id is not None and expected_snapshot_id != result['binding']['snapshot_id']:
                raise ResearchServingError('STALE_RESEARCH_SNAPSHOT')
            rows = self._catalog(connection)
            selected = [row for row in rows if row['source_ordinal'] > after]
            page = selected[:limit]
            more = len(selected) > limit
            result.update(total=72, plans=[self._plan(row) for row in page],
                page={'has_more': more, 'next_after_ordinal': page[-1]['source_ordinal'] if more else None,
                      'ordering': 'source_ordinal', 'snapshot_id': result['binding']['snapshot_id']})
            return json_safe(result)

    def inspect_plan(self, offering_id, layers=('L02', 'L03', 'L09'), limit=10, *,
                     after_entity_id_by_layer=None, expected_snapshot_id=None):
        _limit(limit)
        if not isinstance(offering_id, str) or not re.fullmatch(r'2026:[A-Z][0-9]{4}:[0-9]{3}:[0-9]{3}', offering_id):
            raise ResearchServingError('INVALID_RESEARCH_OFFERING_ID')
        if not isinstance(layers, (tuple, list)) or not layers or len(set(layers)) != len(layers) or set(layers) - {'L02', 'L03', 'L09'}:
            raise ResearchServingError('UNSUPPORTED_RESEARCH_LAYER')
        cursors = {} if after_entity_id_by_layer is None else after_entity_id_by_layer
        if not isinstance(cursors, dict) or set(cursors) - set(layers) or any(
                not isinstance(v, str) or len(v) > 2048 for v in cursors.values()):
            raise ResearchServingError('INVALID_RESEARCH_EVIDENCE_CURSOR')
        with self._read() as (connection, access):
            result = self._envelope(access)
            if expected_snapshot_id is not None and expected_snapshot_id != result['binding']['snapshot_id']:
                raise ResearchServingError('STALE_RESEARCH_SNAPSHOT')
            row = next((r for r in self._catalog(connection) if r['native_id'] == offering_id), None)
            if row is None:
                raise ResearchServingError('OFFERING_OUTSIDE_SELECTED_SCOPE')
            result['plan'] = self._plan(row)
            result['evidence_by_layer'] = {}
            for layer in layers:
                if layer == 'L02':
                    result['evidence_by_layer'][layer] = {'records': [result['plan']], 'has_more': False,
                        'next_after_entity_id': None, 'meaning': 'Exact source identity and restrictions; availability not verified.'}
                    continue
                if layer == 'L03':
                    derivation = self.binding.selections['semantic']['derivation_id']
                    types = ['ma_semantic_claim_representation', 'ma_semantic_condition_representation']
                    query, identity = PLAN_OBSERVATIONS, offering_id
                else:
                    derivation = self.binding.selections['quality']['derivation_id']
                    types, query, identity = ['quality_observation'], QUALITY_OBSERVATIONS, row['contract_id']
                records = connection.execute(query, (derivation, types, cursors.get(layer, ''), identity, limit + 1)).fetchall()
                more, page = len(records) > limit, records[:limit]
                result['evidence_by_layer'][layer] = {
                    'records': [self._observation(r, layer) for r in page], 'has_more': more,
                    'next_after_entity_id': page[-1]['entity_id'] if more else None,
                    'snapshot_id': result['binding']['snapshot_id'],
                    'scope': 'offering' if layer == 'L03' else 'contract_not_plan_specific',
                    'complete_offering_conditions_verified': False,
                    'page_is_complete_condition_inventory': False,
                    'condition_handling': 'Each returned native condition/context is intact; linked whole-offering interpretation remains unreviewed.'}
                if layer == 'L09':
                    linked = connection.execute(PLAN_OBSERVATIONS,
                        (self.binding.selections['quality_binding']['derivation_id'],
                         ['offering_quality_binding'], '', offering_id, 2)).fetchall()
                    result['evidence_by_layer'][layer]['offering_contract_binding'] = [self._observation(r, layer) for r in linked]
                    result['evidence_by_layer'][layer]['binding_state'] = 'source_observed' if len(linked) == 1 else 'missing_or_ambiguous'
            return json_safe(result)

    @staticmethod
    def _observation(row, layer):
        return {'layer_id': layer, 'entity_id': row['entity_id'], 'entity_type': row['entity_type'],
                'offering_id': row['offering_id'], 'county_fips': row['county_fips'],
                'benefit_year': row['benefit_year'], 'amount': row['amount'], 'amount_unit': row['amount_unit'],
                'amount_basis': row['amount_basis'], 'amount_period': row['amount_period'],
                'raw_value': row['raw_value'], 'source_native_fields': copy.deepcopy(row['fields']),
                'raw_source_payload': copy.deepcopy(row['raw_payload']), 'conditions': copy.deepcopy(row['conditions']),
                'states': {key: row[key] for key in STATE_KEYS}, 'lineage': _lineage(row),
                'output_authority': 'held', 'native_acceptance_flags_do_not_promote_this_projection': True}


def repository_from_env(*, repository_root, dsn=None, packet=None, timeout_ms=5000):
    """Guard the current exact local target; core accepts other checked factories.

    Supply only the explicitly authorized infrastructure DSN. This function never
    discovers application credentials or loads any .env file.
    """
    selected = dsn if dsn is not None else os.environ.get('DAYLIGHT_DATA_DATABASE_URL')
    if not isinstance(selected, str) or not selected:
        raise ResearchServingError('RESEARCH_DATABASE_URL_REQUIRED')
    binding = load_local_binding(repository_root, **({'packet': packet} if packet else {}))
    validate_local_dsn(selected, repository_root, binding)
    def connection():
        result = psycopg.connect(selected, autocommit=True, connect_timeout=5, row_factory=dict_row,
                                options='-c default_transaction_read_only=on -c lock_timeout=1000 -c statement_timeout=5000')
        try:
            validate_local_connection(result, binding.target)
            return result
        except BaseException:
            result.close()
            raise
    return ResearchPlanRepository(connection, binding, timeout_ms=timeout_ms)
