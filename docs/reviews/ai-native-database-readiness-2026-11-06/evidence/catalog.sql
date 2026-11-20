BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '15s';
SELECT jsonb_build_object(
  'database', current_database(),
  'server_version', current_setting('server_version'),
  'transaction_read_only', current_setting('transaction_read_only'),
  'database_bytes', pg_database_size(current_database()),
  'operations_database_present', EXISTS(SELECT 1 FROM pg_database WHERE datname = 'daylight_operations'),
  'operations_schema_present_in_research', EXISTS(SELECT 1 FROM pg_namespace WHERE nspname='dl_ops'),
  'source_sets', (SELECT count(*) FROM dl_compact.source_set),
  'source_layers', (SELECT count(DISTINCT s.layer_id) FROM dl_compact.source_set c
     JOIN dl_control.derivation d USING(derivation_id) JOIN dl_control.source_snapshot s USING(snapshot_id)),
  'acceptance_bindings', (SELECT count(*) FROM dl_review.acceptance_binding),
  'release_manifests', (SELECT count(*) FROM dl_review.release),
  'active_releases', (SELECT count(*) FROM dl_review.active_release),
  'released_offerings', (SELECT count(*) FROM dl_released.offerings),
  'evidence_relations', (SELECT jsonb_object_agg(c.relname,c.relkind::text) FROM pg_class c
     JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='dl_evidence'
     AND c.relname IN ('source_record','observation','offering')),
  'compact_indexes', (SELECT jsonb_agg(jsonb_build_object('name',c.relname,'bytes',pg_relation_size(c.oid),
     'valid',i.indisvalid,'ready',i.indisready) ORDER BY c.relname)
     FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid JOIN pg_namespace n ON n.oid=c.relnamespace
     WHERE n.nspname='dl_compact'),
  'research_role_can_read_compressed_source', has_table_privilege('daylight_research_reader','dl_evidence.source_record','SELECT'),
  'research_role_can_insert_compressed_source', has_table_privilege('daylight_research_reader','dl_evidence.source_record','INSERT')
);
COMMIT;
