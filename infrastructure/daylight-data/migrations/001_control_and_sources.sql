CREATE SCHEMA IF NOT EXISTS dl_control;
CREATE SCHEMA IF NOT EXISTS dl_evidence;
CREATE SCHEMA IF NOT EXISTS dl_review;
CREATE SCHEMA IF NOT EXISTS dl_released;
REVOKE ALL ON SCHEMA dl_control, dl_evidence, dl_review, dl_released FROM PUBLIC;

DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='daylight_writer') THEN CREATE ROLE daylight_writer NOLOGIN; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='daylight_validator') THEN CREATE ROLE daylight_validator NOLOGIN; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='daylight_reviewer') THEN CREATE ROLE daylight_reviewer NOLOGIN; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='daylight_research_reader') THEN CREATE ROLE daylight_research_reader NOLOGIN; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='daylight_released_reader') THEN CREATE ROLE daylight_released_reader NOLOGIN; END IF;
END $$;

CREATE TABLE dl_control.artifact (
  sha256 text PRIMARY KEY CHECK (sha256 ~ '^[a-f0-9]{64}$'),
  byte_length bigint NOT NULL CHECK (byte_length >= 0),
  object_key text NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE dl_control.source_snapshot (
  snapshot_id text PRIMARY KEY,
  layer_id text NOT NULL CHECK (layer_id ~ '^L(0[1-9]|1[0-5])$'),
  artifact_sha256 text NOT NULL REFERENCES dl_control.artifact,
  original_path text NOT NULL,
  benefit_year integer NOT NULL CHECK (benefit_year=2026),
  source_use_state text NOT NULL DEFAULT 'not_newly_reviewed',
  UNIQUE(layer_id,original_path,artifact_sha256)
);
CREATE TABLE dl_control.derivation (
  derivation_id text PRIMARY KEY,
  snapshot_id text NOT NULL REFERENCES dl_control.source_snapshot,
  adapter_version text NOT NULL,
  configuration_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE dl_control.source_access_state (
  source_id text PRIMARY KEY,
  state text NOT NULL CHECK(state IN ('permitted','stopped','held')),
  reason text NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE dl_control.job (
  job_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  idempotency_key text NOT NULL UNIQUE,
  source_id text NOT NULL,
  payload jsonb NOT NULL,
  state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','running','complete','failed','stopped')),
  owner_id text,
  fence bigint NOT NULL DEFAULT 0,
  lease_until timestamptz,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  finished_at timestamptz
);
CREATE TABLE dl_control.checkpoint (
  job_id bigint NOT NULL REFERENCES dl_control.job,
  derivation_id text NOT NULL REFERENCES dl_control.derivation,
  source_table text NOT NULL,
  last_ordinal bigint NOT NULL CHECK(last_ordinal>=0),
  retained_rows bigint NOT NULL CHECK(retained_rows>=0),
  fence bigint NOT NULL,
  PRIMARY KEY(job_id,derivation_id,source_table)
);
CREATE TABLE dl_control.ingest_receipt (
  job_id bigint PRIMARY KEY REFERENCES dl_control.job,
  input_rows bigint NOT NULL,
  retained_rows bigint NOT NULL,
  quarantined_rows bigint NOT NULL,
  stream_sha256 text NOT NULL,
  controls jsonb NOT NULL,
  completed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CHECK(input_rows=retained_rows),
  CHECK(quarantined_rows BETWEEN 0 AND retained_rows)
);
CREATE FUNCTION dl_control.reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'immutable evidence/control record'; END $$;
CREATE TRIGGER artifact_immutable BEFORE UPDATE OR DELETE ON dl_control.artifact FOR EACH ROW EXECUTE FUNCTION dl_control.reject_mutation();
CREATE TRIGGER snapshot_immutable BEFORE UPDATE OR DELETE ON dl_control.source_snapshot FOR EACH ROW EXECUTE FUNCTION dl_control.reject_mutation();
CREATE TRIGGER derivation_immutable BEFORE UPDATE OR DELETE ON dl_control.derivation FOR EACH ROW EXECUTE FUNCTION dl_control.reject_mutation();

GRANT USAGE ON SCHEMA dl_control TO daylight_writer,daylight_validator,daylight_reviewer,daylight_research_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA dl_control TO daylight_writer,daylight_validator,daylight_reviewer,daylight_research_reader;
GRANT INSERT ON dl_control.artifact,dl_control.source_snapshot,dl_control.derivation,dl_control.ingest_receipt TO daylight_writer;
GRANT INSERT,UPDATE ON dl_control.job,dl_control.checkpoint,dl_control.source_access_state TO daylight_writer;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA dl_control TO daylight_writer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA dl_control FROM PUBLIC;
