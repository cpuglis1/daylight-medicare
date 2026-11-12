"""Operator-only exact native-ID research lookup for the declared L03 pilot.

Not exposed by the plan HTTP adapter. No arbitrary table/JSON-path queries and no
source expansion. Whole-source population/semantic verification is not implied.
"""
import re

from .binding import ResearchServingError, load_local_binding
from .repository import ResearchPlanRepository, json_safe, repository_from_env

SELECTION = {name: ('L03', table, '/semantic-inventory-r9/') for name, table in
             [('native_observations', 'observation'), ('native_sources', 'source_disposition'),
              ('native_relationships', 'relationship'), ('native_clauses', 'clause')]}
SELECT = """SELECT r.*,d.snapshot_id,d.adapter_code_sha256,s.original_path,s.artifact_sha256,
 s.source_use_state AS snapshot_source_use_state
 FROM dl_evidence.source_record r JOIN dl_control.derivation d USING(derivation_id)
 JOIN dl_control.source_snapshot s USING(snapshot_id)
 WHERE r.derivation_id=%s AND r.source_table=%s AND {predicate}
 AND r.source_row_ordinal>%s ORDER BY r.source_row_ordinal LIMIT 101"""
QUERIES = {
    'native_observations': SELECT.format(predicate="r.raw_payload->>'id'=ANY(%s)"),
    'native_sources': SELECT.format(predicate="r.raw_payload->>'source_id'=ANY(%s)"),
    'native_relationships': SELECT.format(predicate="(r.raw_payload->>'parent_id'=ANY(%s) OR r.raw_payload->>'child_id'=ANY(%s))"),
    'native_clauses': SELECT.format(predicate="r.raw_payload->>'id'=ANY(%s)"),
}


class NativeLineageRepository(ResearchPlanRepository):
    def lookup(self, kind, native_ids, *, after_ordinal=0):
        if (kind not in SELECTION or not isinstance(native_ids, (tuple, list))
                or not 1 <= len(native_ids) <= 100
                or any(not isinstance(v, str) or not re.fullmatch(r'(?:OBS|SRC|SEM|SOURCE_AMOUNT|CLAUSE)-[A-Za-z0-9_-]{1,120}', v) for v in native_ids)
                or len(set(native_ids)) != len(native_ids)
                or type(after_ordinal) is not int or after_ordinal < 0):
            raise ResearchServingError('INVALID_NATIVE_LINEAGE_REQUEST')
        prefixes = {'native_observations': ('OBS-',), 'native_sources': ('SRC-', 'SOURCE_AMOUNT-'),
                    'native_relationships': ('SEM-',), 'native_clauses': ('CLAUSE-',)}[kind]
        if any(not v.startswith(prefixes) for v in native_ids):
            raise ResearchServingError('NATIVE_LINEAGE_ID_KIND_MISMATCH')
        selection = self.binding.selections[kind]
        params = [selection['derivation_id'], selection['source_table'], list(native_ids)]
        if kind == 'native_relationships':
            params.append(list(native_ids))
        params.append(after_ordinal)
        with self._read() as (connection, access):
            rows = connection.execute(QUERIES[kind], params).fetchall()
            more, page = len(rows) > 100, rows[:100]
            result = self._envelope(access)
            result.update(lookup_kind=kind, requested_ids=list(native_ids),
                          records=json_safe(page), has_more=more,
                          next_after_ordinal=page[-1]['source_row_ordinal'] if more else None,
                          source_query=QUERIES[kind], query_parameters=json_safe(params),
                          condition_semantics_verified=False,
                          operator_only=True)
            if kind != 'native_relationships':
                field = 'source_id' if kind == 'native_sources' else 'id'
                present = [r['raw_payload'].get(field) for r in page]
                result['returned_native_ids'] = present
                result['missing_ids'] = sorted(set(native_ids) - set(present)) if not more and after_ordinal == 0 else None
            return result


def native_repository_from_env(*, repository_root, dsn=None, timeout_ms=30000):
    # Reuse the same exact local physical-identity guard. The native repository
    # independently checks its own source/derivation/current-job controls.
    base = repository_from_env(repository_root=repository_root, dsn=dsn, timeout_ms=timeout_ms)
    binding = load_local_binding(repository_root, selection=SELECTION)
    return NativeLineageRepository(base._connection_factory, binding, timeout_ms=timeout_ms)
