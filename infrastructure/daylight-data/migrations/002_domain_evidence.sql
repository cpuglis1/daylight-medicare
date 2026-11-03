CREATE TABLE dl_evidence.source_record (
  derivation_id text NOT NULL REFERENCES dl_control.derivation,
  source_table text NOT NULL,
  source_row_ordinal bigint NOT NULL CHECK(source_row_ordinal>0),
  record_id text NOT NULL,
  source_row_key text NOT NULL,
  ordinal_basis text NOT NULL,
  raw_sha256 text NOT NULL,
  raw_payload jsonb NOT NULL,
  disposition text NOT NULL,
  PRIMARY KEY(derivation_id,source_table,source_row_ordinal)
);
CREATE TABLE dl_evidence.offering (
  derivation_id text NOT NULL REFERENCES dl_control.derivation,
  offering_id text NOT NULL CHECK(offering_id ~ '^2026:[A-Z][0-9]{4}:[0-9]{3}:[0-9]{3}$'),
  benefit_year integer NOT NULL CHECK(benefit_year=2026),
  contract_id text NOT NULL CHECK(contract_id ~ '^[A-Z][0-9]{4}$'),
  plan_id text NOT NULL CHECK(plan_id ~ '^[0-9]{3}$'),
  segment_id text NOT NULL CHECK(segment_id ~ '^[0-9]{3}$'),
  plan_name text,
  category text,
  source_table text NOT NULL,
  source_row_ordinal bigint NOT NULL,
  output_acceptance_state text NOT NULL DEFAULT 'research_only',
  PRIMARY KEY(derivation_id,offering_id),
  FOREIGN KEY(derivation_id,source_table,source_row_ordinal) REFERENCES dl_evidence.source_record,
  CHECK(offering_id=benefit_year::text||':'||contract_id||':'||plan_id||':'||segment_id)
);
CREATE TABLE dl_evidence.observation (
  derivation_id text NOT NULL REFERENCES dl_control.derivation,
  entity_type text NOT NULL,
  entity_id text NOT NULL,
  source_table text NOT NULL,
  source_row_ordinal bigint NOT NULL,
  offering_id text,
  county_fips text CHECK(county_fips IS NULL OR county_fips ~ '^[0-9]{5}$'),
  benefit_year integer CHECK(benefit_year IS NULL OR benefit_year=2026),
  amount numeric,
  amount_unit text,
  amount_basis text,
  amount_period text,
  raw_value text,
  value_state text NOT NULL,
  evidence_state text NOT NULL,
  semantic_review_state text NOT NULL,
  source_use_state text NOT NULL,
  freshness_state text NOT NULL,
  output_acceptance_state text NOT NULL,
  conditions jsonb NOT NULL,
  fields jsonb NOT NULL,
  PRIMARY KEY(derivation_id,entity_type,entity_id),
  FOREIGN KEY(derivation_id,source_table,source_row_ordinal) REFERENCES dl_evidence.source_record
);
CREATE TRIGGER record_immutable BEFORE UPDATE OR DELETE ON dl_evidence.source_record FOR EACH ROW EXECUTE FUNCTION dl_control.reject_mutation();
CREATE TRIGGER offering_immutable BEFORE UPDATE OR DELETE ON dl_evidence.offering FOR EACH ROW EXECUTE FUNCTION dl_control.reject_mutation();
CREATE TRIGGER observation_immutable BEFORE UPDATE OR DELETE ON dl_evidence.observation FOR EACH ROW EXECUTE FUNCTION dl_control.reject_mutation();
CREATE INDEX source_record_identity ON dl_evidence.source_record(record_id);
CREATE INDEX offering_identity ON dl_evidence.offering(offering_id);
CREATE INDEX observation_query ON dl_evidence.observation(entity_type,offering_id,county_fips,entity_id);
GRANT USAGE ON SCHEMA dl_evidence TO daylight_writer,daylight_validator,daylight_reviewer,daylight_research_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA dl_evidence TO daylight_writer,daylight_validator,daylight_reviewer,daylight_research_reader;
GRANT INSERT ON ALL TABLES IN SCHEMA dl_evidence TO daylight_writer;
