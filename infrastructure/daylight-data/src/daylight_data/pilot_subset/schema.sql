CREATE SCHEMA dl_pilot;
REVOKE ALL ON SCHEMA dl_pilot FROM PUBLIC;
CREATE TABLE dl_pilot.snapshot (
  singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
  snapshot_id text NOT NULL CHECK(snapshot_id ~ '^[0-9a-f]{64}$'),
  manifest jsonb NOT NULL
);
CREATE TABLE dl_pilot.pdp_response (
  kind text PRIMARY KEY CHECK(kind IN ('pdp_offering','pdp_county','pdp_restriction')),
  payload jsonb NOT NULL
);
-- Append a local STOP immediately if the source is revoked after this export.
CREATE TABLE dl_pilot.stop_event (
  event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  scope text NOT NULL CHECK(scope IN ('all','medigap','pdp')),
  reason text NOT NULL CHECK(length(reason)>0),
  recorded_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE FUNCTION dl_pilot.immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'pilot snapshots are immutable; export a new revision'; END $$;
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON dl_pilot.snapshot
  FOR EACH ROW EXECUTE FUNCTION dl_pilot.immutable();
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON dl_pilot.pdp_response
  FOR EACH ROW EXECUTE FUNCTION dl_pilot.immutable();
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON dl_pilot.stop_event
  FOR EACH ROW EXECUTE FUNCTION dl_pilot.immutable();
CREATE TRIGGER no_truncate BEFORE TRUNCATE ON dl_pilot.snapshot
  FOR EACH STATEMENT EXECUTE FUNCTION dl_pilot.immutable();
CREATE TRIGGER no_truncate BEFORE TRUNCATE ON dl_pilot.pdp_response
  FOR EACH STATEMENT EXECUTE FUNCTION dl_pilot.immutable();
CREATE TRIGGER no_truncate BEFORE TRUNCATE ON dl_pilot.stop_event
  FOR EACH STATEMENT EXECUTE FUNCTION dl_pilot.immutable();
REVOKE ALL ON ALL TABLES IN SCHEMA dl_pilot FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA dl_pilot FROM PUBLIC;
GRANT USAGE ON SCHEMA dl_pilot TO daylight_csg_reader,daylight_plan_research_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA dl_pilot TO daylight_csg_reader,daylight_plan_research_reader;
