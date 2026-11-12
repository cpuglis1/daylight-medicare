-- D94 additive physical redesign. Apply only in an owned, empty compact target.
-- All legacy logical columns and source/method/purpose states survive in views.
CREATE SCHEMA dl_compact;
REVOKE ALL ON SCHEMA dl_compact FROM PUBLIC;

CREATE UNLOGGED TABLE dl_compact.stage_source (LIKE dl_evidence.source_record INCLUDING DEFAULTS);
CREATE UNLOGGED TABLE dl_compact.stage_observation (LIKE dl_evidence.observation INCLUDING DEFAULTS);
CREATE UNLOGGED TABLE dl_compact.stage_offering (LIKE dl_evidence.offering INCLUDING DEFAULTS);

DROP VIEW dl_released.offerings;
DROP TABLE dl_evidence.offering;
DROP TABLE dl_evidence.observation;
DROP TABLE dl_evidence.source_record;

CREATE TABLE dl_compact.source_set (
  source_set_id smallint PRIMARY KEY,
  derivation_id text NOT NULL UNIQUE REFERENCES dl_control.derivation,
  source_table text NOT NULL,
  UNIQUE(derivation_id,source_table)
);
CREATE TABLE dl_compact.symbol (
  symbol_id smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  value text NOT NULL UNIQUE
);
CREATE TABLE dl_compact.evidence_state (
  state_id smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  value_state text NOT NULL,
  evidence_state text NOT NULL,
  semantic_review_state text NOT NULL,
  source_use_state text NOT NULL,
  freshness_state text NOT NULL,
  output_acceptance_state text NOT NULL,
  UNIQUE(value_state,evidence_state,semantic_review_state,source_use_state,
         freshness_state,output_acceptance_state)
);
CREATE TABLE dl_compact.source_record (
  source_set_id smallint NOT NULL REFERENCES dl_compact.source_set,
  source_row_ordinal bigint NOT NULL CHECK(source_row_ordinal>0),
  record_hash bytea NOT NULL CHECK(octet_length(record_hash)=32),
  source_row_key text NOT NULL,
  ordinal_basis_id smallint NOT NULL REFERENCES dl_compact.symbol,
  raw_hash bytea NOT NULL CHECK(octet_length(raw_hash)=32),
  raw_payload jsonb NOT NULL,
  disposition_id smallint NOT NULL REFERENCES dl_compact.symbol,
  PRIMARY KEY(source_set_id,source_row_ordinal)
) WITH(toast_tuple_target=512);
ALTER TABLE dl_compact.source_record ALTER COLUMN record_hash SET STORAGE PLAIN;
ALTER TABLE dl_compact.source_record ALTER COLUMN raw_hash SET STORAGE PLAIN;

CREATE TABLE dl_compact.observation (
  source_set_id smallint NOT NULL REFERENCES dl_compact.source_set,
  source_row_ordinal bigint NOT NULL,
  entity_type_id smallint NOT NULL REFERENCES dl_compact.symbol,
  entity_id text NOT NULL,
  offering_id text,
  county_fips text CHECK(county_fips IS NULL OR county_fips ~ '^[0-9]{5}$'),
  benefit_year integer CHECK(benefit_year IS NULL OR benefit_year=2026),
  amount numeric,
  amount_unit_id smallint REFERENCES dl_compact.symbol,
  amount_basis_id smallint REFERENCES dl_compact.symbol,
  amount_period_id smallint REFERENCES dl_compact.symbol,
  raw_value text,
  state_id smallint NOT NULL REFERENCES dl_compact.evidence_state,
  conditions jsonb NOT NULL,
  fields jsonb NOT NULL,
  PRIMARY KEY(source_set_id,entity_type_id,entity_id),
  FOREIGN KEY(source_set_id,source_row_ordinal)
    REFERENCES dl_compact.source_record(source_set_id,source_row_ordinal)
) WITH(toast_tuple_target=512);

CREATE TABLE dl_compact.offering (
  source_set_id smallint NOT NULL REFERENCES dl_compact.source_set,
  offering_id text NOT NULL CHECK(offering_id ~ '^2026:[A-Z][0-9]{4}:[0-9]{3}:[0-9]{3}$'),
  benefit_year integer NOT NULL CHECK(benefit_year=2026),
  contract_id text NOT NULL CHECK(contract_id ~ '^[A-Z][0-9]{4}$'),
  plan_id text NOT NULL CHECK(plan_id ~ '^[0-9]{3}$'),
  segment_id text NOT NULL CHECK(segment_id ~ '^[0-9]{3}$'),
  plan_name text,
  category text,
  source_row_ordinal bigint NOT NULL,
  output_acceptance_state text NOT NULL,
  PRIMARY KEY(source_set_id,offering_id),
  FOREIGN KEY(source_set_id,source_row_ordinal)
    REFERENCES dl_compact.source_record(source_set_id,source_row_ordinal),
  CHECK(offering_id=benefit_year::text||':'||contract_id||':'||plan_id||':'||segment_id)
);

-- The source-lineage index services exact ranges, providers and drug identities.
CREATE INDEX compact_observation_lineage ON dl_compact.observation
  (source_set_id,source_row_ordinal) INCLUDE(entity_type_id);
-- Omit unrelated null-offering rows instead of indexing every research record.
CREATE INDEX compact_observation_offering ON dl_compact.observation
  (source_set_id,offering_id,entity_type_id,entity_id) WHERE offering_id IS NOT NULL;
CREATE INDEX compact_offering_identity ON dl_compact.offering(offering_id);

CREATE VIEW dl_evidence.source_record AS
 SELECT s.derivation_id,s.source_table,r.source_row_ordinal,
        encode(r.record_hash,'hex') AS record_id,r.source_row_key,
        b.value AS ordinal_basis,encode(r.raw_hash,'hex') AS raw_sha256,
        r.raw_payload,d.value AS disposition
 FROM dl_compact.source_record r
 JOIN dl_compact.source_set s USING(source_set_id)
 JOIN dl_compact.symbol b ON b.symbol_id=r.ordinal_basis_id
 JOIN dl_compact.symbol d ON d.symbol_id=r.disposition_id;

CREATE VIEW dl_evidence.observation AS
 SELECT s.derivation_id,t.value AS entity_type,o.entity_id,s.source_table,
        o.source_row_ordinal,o.offering_id,o.county_fips,o.benefit_year,o.amount,
        u.value AS amount_unit,b.value AS amount_basis,p.value AS amount_period,
        o.raw_value,e.value_state,e.evidence_state,e.semantic_review_state,
        e.source_use_state,e.freshness_state,e.output_acceptance_state,
        o.conditions,o.fields
 FROM dl_compact.observation o
 JOIN dl_compact.source_set s USING(source_set_id)
 JOIN dl_compact.symbol t ON t.symbol_id=o.entity_type_id
 JOIN dl_compact.evidence_state e USING(state_id)
 LEFT JOIN dl_compact.symbol u ON u.symbol_id=o.amount_unit_id
 LEFT JOIN dl_compact.symbol b ON b.symbol_id=o.amount_basis_id
 LEFT JOIN dl_compact.symbol p ON p.symbol_id=o.amount_period_id;

CREATE VIEW dl_evidence.offering AS
 SELECT s.derivation_id,o.offering_id,o.benefit_year,o.contract_id,o.plan_id,
        o.segment_id,o.plan_name,o.category,s.source_table,o.source_row_ordinal,
        o.output_acceptance_state
 FROM dl_compact.offering o JOIN dl_compact.source_set s USING(source_set_id);

CREATE VIEW dl_released.offerings WITH(security_barrier=true) AS
 SELECT offering_id,benefit_year,contract_id,plan_id,segment_id,plan_name,category
 FROM dl_evidence.offering WHERE false;
GRANT SELECT ON dl_evidence.source_record,dl_evidence.observation,dl_evidence.offering
 TO daylight_writer,daylight_validator,daylight_reviewer,daylight_research_reader;
GRANT SELECT ON dl_released.offerings TO daylight_released_reader;

CREATE TRIGGER compact_source_immutable BEFORE UPDATE OR DELETE ON dl_compact.source_record
 FOR EACH ROW EXECUTE FUNCTION dl_control.reject_mutation();
CREATE TRIGGER compact_observation_immutable BEFORE UPDATE OR DELETE ON dl_compact.observation
 FOR EACH ROW EXECUTE FUNCTION dl_control.reject_mutation();
CREATE TRIGGER compact_offering_immutable BEFORE UPDATE OR DELETE ON dl_compact.offering
 FOR EACH ROW EXECUTE FUNCTION dl_control.reject_mutation();
CREATE TRIGGER compact_set_immutable BEFORE UPDATE OR DELETE ON dl_compact.source_set
 FOR EACH ROW EXECUTE FUNCTION dl_control.reject_mutation();
CREATE TRIGGER compact_symbol_immutable BEFORE UPDATE OR DELETE ON dl_compact.symbol
 FOR EACH ROW EXECUTE FUNCTION dl_control.reject_mutation();
CREATE TRIGGER compact_state_immutable BEFORE UPDATE OR DELETE ON dl_compact.evidence_state
 FOR EACH ROW EXECUTE FUNCTION dl_control.reject_mutation();

CREATE TABLE dl_compact.migration (
  singleton boolean PRIMARY KEY CHECK(singleton),
  manifest jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TRIGGER compact_migration_immutable BEFORE UPDATE OR DELETE ON dl_compact.migration
 FOR EACH ROW EXECUTE FUNCTION dl_control.reject_mutation();
CREATE TABLE dl_compact.load_checkpoint (
  source_set_id smallint NOT NULL REFERENCES dl_compact.source_set,
  first_ordinal bigint NOT NULL,
  last_ordinal bigint NOT NULL,
  raw_rows bigint NOT NULL,
  projection_rows bigint NOT NULL,
  raw_binary_sha256 text NOT NULL,
  projection_binary_sha256 text NOT NULL,
  copied_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY(source_set_id,first_ordinal,last_ordinal)
);
REVOKE ALL ON ALL TABLES IN SCHEMA dl_compact FROM PUBLIC;
