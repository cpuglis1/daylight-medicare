-- Supports bounded persistent-window reconciliation and exact source-row inspection.
-- Additive index only: no evidence, source-use, review or release state is changed.
CREATE INDEX observation_source_lineage ON dl_evidence.observation
    (derivation_id,source_table,source_row_ordinal) INCLUDE (entity_type);
