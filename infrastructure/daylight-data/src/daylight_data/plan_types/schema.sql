-- D96 additive serving schema. Never migrate/rewrite the compact research views.
CREATE SCHEMA dl_plan_types;
REVOKE ALL ON SCHEMA dl_plan_types FROM PUBLIC;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='daylight_plan_research_reader') THEN
    CREATE ROLE daylight_plan_research_reader NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='daylight_plan_loader') THEN
    CREATE ROLE daylight_plan_loader NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='daylight_plan_reviewer') THEN
    CREATE ROLE daylight_plan_reviewer NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='daylight_plan_publisher') THEN
    CREATE ROLE daylight_plan_publisher NOLOGIN;
  END IF;
END $$;

CREATE TABLE dl_plan_types.schema_revision (
  singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
  sha256 text NOT NULL CHECK(sha256 ~ '^[0-9a-f]{64}$')
);
CREATE TABLE dl_plan_types.build (
  build_id text PRIMARY KEY CHECK(build_id ~ '^[0-9a-f]{64}$'),
  manifest jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CHECK(manifest->>'consumer_release'='held'),
  CHECK(manifest->'scope'='{"reference_year":2026,"county_fips":"12021","pdp_region":"11"}'::jsonb)
);
CREATE TABLE dl_plan_types.source (
  build_id text NOT NULL REFERENCES dl_plan_types.build,
  source_id text NOT NULL,
  source_path text NOT NULL,
  artifact_sha256 text NOT NULL CHECK(artifact_sha256 ~ '^[0-9a-f]{64}$'),
  metadata jsonb NOT NULL,
  PRIMARY KEY(build_id,source_id),
  UNIQUE(build_id,source_path)
);
CREATE TABLE dl_plan_types.item (
  build_id text NOT NULL,
  source_id text NOT NULL,
  item_id text NOT NULL CHECK(item_id ~ '^[0-9a-f]{64}$'),
  kind text NOT NULL CHECK(kind IN ('pdp_offering','pdp_field','pdp_county','pdp_restriction',
    'medigap_variant','medigap_benefit','medigap_condition','medigap_product_lead',
    'medigap_listing','medigap_insurer','medigap_illustration','medigap_monthly_rate',
    'medigap_schedule','medigap_filed_rate','research_item','source_document')),
  entity_key text NOT NULL,
  source_pointer text NOT NULL,
  payload_sha256 text NOT NULL CHECK(payload_sha256 ~ '^[0-9a-f]{64}$'),
  payload jsonb NOT NULL,
  cms_offering_id text CHECK(cms_offering_id IS NULL OR cms_offering_id ~ '^2026:S[0-9]{4}:[0-9]{3}:[0-9]{3}$'),
  county_fips text CHECK(county_fips IS NULL OR county_fips ~ '^[0-9]{5}$'),
  region text,
  variant text,
  company_name text,
  naic text,
  policy_form text,
  rating_area text,
  schedule_key text,
  source_status text,
  effective_from date,
  effective_through date,
  amount_cents bigint,
  unit text CHECK(unit IS NULL OR unit IN ('USD/month','USD/year')),
  basis text,
  value_state text NOT NULL,
  holds text[] NOT NULL,
  conditions jsonb NOT NULL,
  PRIMARY KEY(build_id,item_id),
  FOREIGN KEY(build_id,source_id) REFERENCES dl_plan_types.source,
  CHECK(kind NOT IN ('pdp_offering','pdp_field','pdp_restriction') OR cms_offering_id IS NOT NULL),
  CHECK(kind <> 'pdp_county' OR (county_fips IS NOT NULL AND region IS NOT NULL)),
  CHECK(kind <> 'medigap_filed_rate' OR (schedule_key IS NOT NULL AND unit='USD/year')),
  CHECK(amount_cents IS NULL OR (unit IS NOT NULL AND basis IS NOT NULL)),
  CHECK(effective_from IS NULL OR effective_through IS NULL OR effective_from<=effective_through)
);
CREATE INDEX plan_types_kind_cursor ON dl_plan_types.item(build_id,kind,item_id);
CREATE INDEX plan_types_exact_key ON dl_plan_types.item(build_id,kind,entity_key);
CREATE INDEX plan_types_pdp_region ON dl_plan_types.item(build_id,region,cms_offering_id)
  WHERE kind='pdp_offering';
CREATE INDEX plan_types_schedule ON dl_plan_types.item(build_id,schedule_key)
  WHERE kind='medigap_filed_rate';
CREATE INDEX plan_types_county ON dl_plan_types.item(build_id,kind,county_fips);

CREATE TABLE dl_plan_types.checkpoint (
  build_id text NOT NULL,
  source_id text NOT NULL,
  item_count bigint NOT NULL CHECK(item_count>=0),
  stream_sha256 text NOT NULL,
  completed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY(build_id,source_id),
  FOREIGN KEY(build_id,source_id) REFERENCES dl_plan_types.source
);
CREATE TABLE dl_plan_types.completion (
  build_id text PRIMARY KEY REFERENCES dl_plan_types.build,
  counts jsonb NOT NULL,
  completed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE dl_plan_types.selection_event (
  event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  build_id text NOT NULL REFERENCES dl_plan_types.completion,
  reason text NOT NULL CHECK(length(reason)>0),
  actor name NOT NULL DEFAULT session_user,
  selected_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE dl_plan_types.review_event (
  event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  build_id text NOT NULL REFERENCES dl_plan_types.completion,
  capability text NOT NULL,
  gate text NOT NULL CHECK(gate IN ('source_use','method','output')),
  decision text NOT NULL CHECK(decision IN ('accepted','held','revoked')),
  receipt_sha256 text NOT NULL CHECK(receipt_sha256 ~ '^[0-9a-f]{64}$'),
  original_authority jsonb NOT NULL,
  expires_at timestamptz NOT NULL,
  actor name NOT NULL DEFAULT session_user,
  recorded_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE dl_plan_types.stop_event (
  event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  build_id text NOT NULL REFERENCES dl_plan_types.build,
  source_id text,
  reason text NOT NULL CHECK(length(reason)>0),
  actor name NOT NULL DEFAULT session_user,
  stopped_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE VIEW dl_plan_types.active_research AS
 SELECT b.* FROM dl_plan_types.build b JOIN dl_plan_types.selection_event e USING(build_id)
 WHERE e.event_id=(SELECT max(event_id) FROM dl_plan_types.selection_event);
CREATE VIEW dl_plan_types.pdp_offerings AS
 SELECT i.* FROM dl_plan_types.item i WHERE kind='pdp_offering';
CREATE VIEW dl_plan_types.medigap_rates AS
 SELECT i.* FROM dl_plan_types.item i WHERE kind IN
   ('medigap_filed_rate','medigap_monthly_rate','medigap_illustration');
-- No accepted serving view is created. Consumer endpoints remain disabled in v1.
CREATE FUNCTION dl_plan_types.guard_insert() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME IN ('source','item','checkpoint') AND
    EXISTS(SELECT 1 FROM dl_plan_types.completion WHERE build_id=NEW.build_id) THEN
    RAISE EXCEPTION 'completed plan-type build is sealed';
  END IF;
  IF TG_TABLE_NAME='item' AND EXISTS(SELECT 1 FROM dl_plan_types.checkpoint
      WHERE build_id=NEW.build_id AND source_id=NEW.source_id) THEN
    RAISE EXCEPTION 'completed plan-type source is sealed';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER source_seal BEFORE INSERT ON dl_plan_types.source
  FOR EACH ROW EXECUTE FUNCTION dl_plan_types.guard_insert();
CREATE TRIGGER item_seal BEFORE INSERT ON dl_plan_types.item
  FOR EACH ROW EXECUTE FUNCTION dl_plan_types.guard_insert();
CREATE TRIGGER checkpoint_seal BEFORE INSERT ON dl_plan_types.checkpoint
  FOR EACH ROW EXECUTE FUNCTION dl_plan_types.guard_insert();
CREATE FUNCTION dl_plan_types.guard_completion() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE expected jsonb; actual jsonb; total_sources integer;
BEGIN
  SELECT manifest->'counts',jsonb_array_length(manifest->'sources') INTO expected,total_sources
    FROM dl_plan_types.build WHERE build_id=NEW.build_id;
  SELECT jsonb_object_agg(kind,n) INTO actual FROM
    (SELECT kind,count(*) AS n FROM dl_plan_types.item WHERE build_id=NEW.build_id GROUP BY kind) x;
  IF expected IS DISTINCT FROM actual OR NEW.counts IS DISTINCT FROM actual OR
     (SELECT count(*) FROM dl_plan_types.checkpoint WHERE build_id=NEW.build_id)<>total_sources OR
     EXISTS(SELECT 1 FROM dl_plan_types.build b,
       LATERAL jsonb_array_elements(b.manifest->'sources') spec
       LEFT JOIN dl_plan_types.source s ON s.build_id=NEW.build_id AND s.source_id=spec->>'source_id'
       WHERE b.build_id=NEW.build_id AND (s.source_id IS NULL OR s.metadata IS DISTINCT FROM spec
          OR s.artifact_sha256 IS DISTINCT FROM spec->>'sha256'
          OR s.source_path IS DISTINCT FROM spec->>'path')) OR
     EXISTS(SELECT 1 FROM dl_plan_types.source s JOIN dl_plan_types.checkpoint c USING(build_id,source_id)
       WHERE s.build_id=NEW.build_id AND (c.item_count<>(s.metadata->>'item_count')::bigint
         OR c.stream_sha256<>s.metadata->>'stream_sha256'
         OR c.item_count<>(SELECT count(*) FROM dl_plan_types.item i
           WHERE i.build_id=s.build_id AND i.source_id=s.source_id))) THEN
    RAISE EXCEPTION 'incomplete or mismatched plan-type build';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER completion_guard BEFORE INSERT ON dl_plan_types.completion
  FOR EACH ROW EXECUTE FUNCTION dl_plan_types.guard_completion();
CREATE FUNCTION dl_plan_types.immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'plan-type evidence/events are immutable; append a new revision'; END $$;
DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['schema_revision','build','source','item','checkpoint','completion',
    'selection_event','review_event','stop_event'] LOOP
    EXECUTE format('CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON dl_plan_types.%I FOR EACH ROW EXECUTE FUNCTION dl_plan_types.immutable()',t);
  END LOOP;
END $$;
GRANT USAGE ON SCHEMA dl_plan_types TO daylight_plan_research_reader,
  daylight_plan_loader,daylight_plan_reviewer,daylight_plan_publisher;
GRANT SELECT ON ALL TABLES IN SCHEMA dl_plan_types TO daylight_plan_research_reader,
  daylight_plan_loader,daylight_plan_reviewer,daylight_plan_publisher;
GRANT INSERT ON dl_plan_types.build,dl_plan_types.source,dl_plan_types.item,
  dl_plan_types.checkpoint,dl_plan_types.completion TO daylight_plan_loader;
GRANT INSERT(build_id,capability,gate,decision,receipt_sha256,original_authority,expires_at)
  ON dl_plan_types.review_event TO daylight_plan_reviewer;
GRANT INSERT(build_id,reason) ON dl_plan_types.selection_event TO daylight_plan_publisher;
GRANT INSERT(build_id,source_id,reason) ON dl_plan_types.stop_event TO daylight_plan_publisher;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA dl_plan_types TO daylight_plan_reviewer,daylight_plan_publisher;
