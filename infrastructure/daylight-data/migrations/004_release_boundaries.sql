-- Preflight deny-by-default boundary. Promotion/receipt verification is not implemented
-- by this migration; all consumer queries remain held until exact-authority replay.
CREATE TABLE dl_review.acceptance_binding (
  binding_id text PRIMARY KEY,
  exact_target_sha256 text NOT NULL,
  purpose text NOT NULL,
  receipt_sha256 text NOT NULL,
  receipt_locator text NOT NULL,
  reviewer_actor text NOT NULL,
  original_authority_replay jsonb NOT NULL,
  revoked_at timestamptz,
  expires_at timestamptz
);
CREATE TABLE dl_review.release (
  release_id text PRIMARY KEY,
  manifest_sha256 text NOT NULL UNIQUE,
  manifest jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE dl_review.active_release (
  channel text PRIMARY KEY CHECK(channel IN ('research','accepted')),
  release_id text NOT NULL REFERENCES dl_review.release
);
CREATE VIEW dl_released.offerings WITH (security_barrier=true) AS
 SELECT offering_id,benefit_year,contract_id,plan_id,segment_id,plan_name,category
 FROM dl_evidence.offering WHERE false;
GRANT USAGE ON SCHEMA dl_review TO daylight_reviewer,daylight_research_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA dl_review TO daylight_reviewer,daylight_research_reader;
GRANT USAGE ON SCHEMA dl_released TO daylight_released_reader;
GRANT SELECT ON dl_released.offerings TO daylight_released_reader;
-- No runtime role has write authority to accept or select releases in preflight.
CREATE TRIGGER release_immutable BEFORE UPDATE OR DELETE ON dl_review.release FOR EACH ROW EXECUTE FUNCTION dl_control.reject_mutation();
