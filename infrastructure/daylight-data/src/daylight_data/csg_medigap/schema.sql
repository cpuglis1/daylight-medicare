-- D128: private licensed evidence, separate from dl_plan_types public sources.
CREATE SCHEMA dl_csg_medigap;
REVOKE ALL ON SCHEMA dl_csg_medigap FROM PUBLIC;
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='daylight_csg_reader') THEN
    CREATE ROLE daylight_csg_reader NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='daylight_csg_loader') THEN
    CREATE ROLE daylight_csg_loader NOLOGIN;
  END IF;
END $$;
CREATE TABLE dl_csg_medigap.schema_revision (
  singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton), sha256 text NOT NULL
);
CREATE TABLE dl_csg_medigap.build (
  build_id text PRIMARY KEY CHECK(build_id ~ '^[0-9a-f]{64}$'),
  manifest jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CHECK(manifest->>'consumer_release'='held'),
  CHECK(manifest->'scope'->>'county_fips'='12021')
);
CREATE TABLE dl_csg_medigap.source (
  build_id text NOT NULL REFERENCES dl_csg_medigap.build,
  source_sha256 text NOT NULL CHECK(source_sha256 ~ '^[0-9a-f]{64}$'),
  filename text NOT NULL,
  zip text NOT NULL CHECK(zip IN ('34101','34102','34103','34104','34105','34106','34107','34108')),
  age smallint NOT NULL CHECK(age BETWEEN 65 AND 74),
  gender text NOT NULL CHECK(gender IN ('Female','Male')),
  tobacco text NOT NULL CHECK(tobacco IN ('Non-Tobacco','Tobacco User')),
  requested_date date NOT NULL CHECK(requested_date=DATE '2026-11-10'),
  metadata jsonb NOT NULL,
  PRIMARY KEY(build_id,source_sha256), UNIQUE(build_id,filename),
  UNIQUE(build_id,zip,age,gender,tobacco,requested_date)
);
CREATE TABLE dl_csg_medigap.rate (
  build_id text NOT NULL, id text NOT NULL CHECK(id ~ '^[0-9a-f]{64}$'),
  source_sha256 text NOT NULL, variant text NOT NULL,
  naic text NOT NULL CHECK(naic ~ '^[0-9]{5}$'),
  monthly_cents bigint CHECK(monthly_cents>=0), annual_cents bigint CHECK(annual_cents>=0),
  monthly_with_discounts_cents bigint CHECK(monthly_with_discounts_cents>=0),
  annual_with_discounts_cents bigint CHECK(annual_with_discounts_cents>=0),
  source_effective_date date NOT NULL,
  rating_class text, rating_type text, select_observed boolean,
  payload_sha256 text NOT NULL, payload jsonb NOT NULL,
  PRIMARY KEY(build_id,id),
  FOREIGN KEY(build_id,source_sha256) REFERENCES dl_csg_medigap.source,
  CHECK(variant IN ('A','B','C','D','F','HDF','G','HDG','K','L','M','N')),
  CHECK(payload->>'consumer_release'='held' AND payload->'personal_quote'='false'::jsonb)
);
CREATE INDEX csg_exact_rates ON dl_csg_medigap.rate(build_id,source_sha256,variant,naic,id);
CREATE TABLE dl_csg_medigap.benefit (
  build_id text NOT NULL, source_sha256 text NOT NULL, variant text NOT NULL,
  payload_sha256 text NOT NULL, payload jsonb NOT NULL,
  PRIMARY KEY(build_id,source_sha256,variant),
  FOREIGN KEY(build_id,source_sha256) REFERENCES dl_csg_medigap.source,
  CHECK(variant IN ('A','B','C','D','F','HDF','G','HDG','K','L','M','N')),
  CHECK(payload->>'consumer_release'='held')
);
CREATE TABLE dl_csg_medigap.completion (
  build_id text PRIMARY KEY REFERENCES dl_csg_medigap.build, counts jsonb NOT NULL,
  completed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE dl_csg_medigap.selection_event (
  event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  build_id text NOT NULL REFERENCES dl_csg_medigap.completion,
  reason text NOT NULL CHECK(length(reason)>0),
  actor name NOT NULL DEFAULT session_user, recorded_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE dl_csg_medigap.stop_event (
  event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  build_id text NOT NULL REFERENCES dl_csg_medigap.build, source_sha256 text,
  reason text NOT NULL CHECK(length(reason)>0),
  actor name NOT NULL DEFAULT session_user, recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CHECK(source_sha256 IS NULL OR source_sha256 ~ '^[0-9a-f]{64}$'),
  FOREIGN KEY(build_id,source_sha256) REFERENCES dl_csg_medigap.source
);
CREATE VIEW dl_csg_medigap.active_research AS
 SELECT b.* FROM dl_csg_medigap.build b JOIN dl_csg_medigap.selection_event e USING(build_id)
 WHERE e.event_id=(SELECT max(event_id) FROM dl_csg_medigap.selection_event);
CREATE FUNCTION dl_csg_medigap.immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'CSG evidence and event history are immutable'; END $$;
CREATE FUNCTION dl_csg_medigap.unsealed() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS(SELECT FROM dl_csg_medigap.completion WHERE build_id=NEW.build_id) THEN
    RAISE EXCEPTION 'CSG build is complete; use a new revision';
  END IF;
  RETURN NEW;
END $$;
CREATE FUNCTION dl_csg_medigap.complete() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actual jsonb; expected jsonb;
BEGIN
  SELECT manifest->'counts' INTO expected FROM dl_csg_medigap.build WHERE build_id=NEW.build_id;
  SELECT jsonb_build_object(
    'sources',(SELECT count(*) FROM dl_csg_medigap.source WHERE build_id=NEW.build_id),
    'rates',(SELECT count(*) FROM dl_csg_medigap.rate WHERE build_id=NEW.build_id),
    'benefits',(SELECT count(*) FROM dl_csg_medigap.benefit WHERE build_id=NEW.build_id)) INTO actual;
  IF actual IS DISTINCT FROM expected OR NEW.counts IS DISTINCT FROM expected OR actual->>'sources'<>'320' THEN
    RAISE EXCEPTION 'CSG completion counts disagree';
  END IF;
  IF EXISTS(SELECT FROM dl_csg_medigap.source s WHERE s.build_id=NEW.build_id AND
    (SELECT count(*) FROM dl_csg_medigap.benefit b WHERE b.build_id=s.build_id AND b.source_sha256=s.source_sha256)<>12) THEN
    RAISE EXCEPTION 'CSG source is missing benefit sheets';
  END IF;
  IF EXISTS(SELECT FROM dl_csg_medigap.source s CROSS JOIN LATERAL jsonb_each_text(s.metadata->'rate_counts') e
    WHERE s.build_id=NEW.build_id AND (SELECT count(*) FROM dl_csg_medigap.rate r
      WHERE r.build_id=s.build_id AND r.source_sha256=s.source_sha256 AND r.variant=e.key)<>e.value::integer) THEN
    RAISE EXCEPTION 'CSG per-source variant counts disagree';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER complete_counts BEFORE INSERT ON dl_csg_medigap.completion
  FOR EACH ROW EXECUTE FUNCTION dl_csg_medigap.complete();
DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['schema_revision','build','source','rate','benefit','completion','selection_event','stop_event'] LOOP
    EXECUTE format('CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON dl_csg_medigap.%I FOR EACH ROW EXECUTE FUNCTION dl_csg_medigap.immutable()',t);
    EXECUTE format('CREATE TRIGGER no_truncate BEFORE TRUNCATE ON dl_csg_medigap.%I FOR EACH STATEMENT EXECUTE FUNCTION dl_csg_medigap.immutable()',t);
  END LOOP;
  FOREACH t IN ARRAY ARRAY['source','rate','benefit'] LOOP
    EXECUTE format('CREATE TRIGGER seal BEFORE INSERT ON dl_csg_medigap.%I FOR EACH ROW EXECUTE FUNCTION dl_csg_medigap.unsealed()',t);
  END LOOP;
END $$;
REVOKE ALL ON ALL TABLES IN SCHEMA dl_csg_medigap FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA dl_csg_medigap FROM PUBLIC;
GRANT USAGE ON SCHEMA dl_csg_medigap TO daylight_csg_reader,daylight_csg_loader;
GRANT SELECT ON ALL TABLES IN SCHEMA dl_csg_medigap TO daylight_csg_reader,daylight_csg_loader;
GRANT INSERT ON dl_csg_medigap.build,dl_csg_medigap.source,dl_csg_medigap.rate,
 dl_csg_medigap.benefit,dl_csg_medigap.completion,dl_csg_medigap.selection_event,dl_csg_medigap.stop_event
 TO daylight_csg_loader;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA dl_csg_medigap TO daylight_csg_loader;
-- No existing public-evidence/app role receives access; no consumer view exists.
