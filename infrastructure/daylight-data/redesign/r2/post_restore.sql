-- Apply after a fresh compact-full.dump.gz restore, before serving record-ID
-- equality lookups. Derived only: no source values, holds or permissions change.
\ir ../r3/read_views.sql
CREATE INDEX compact_source_identity ON dl_compact.source_record
 USING hash ((encode(record_hash,'hex')));
ANALYZE dl_compact.source_record;
