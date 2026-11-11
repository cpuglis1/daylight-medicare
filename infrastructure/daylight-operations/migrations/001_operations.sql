-- Daylight operations database: the customer plane. Separate from the research
-- database (public evidence only). Two schemas keep the commercial boundary
-- structural (PRINCIPLES.md §3, D64):
--   dl_ops          decisions, licensed reviews, model-call traces, cases, enrollment status
--   dl_fulfillment  commission statements and reconciliation; no decision-side role can read it
-- Traces hold metadata only: no prompt, response or transcript content.

CREATE SCHEMA IF NOT EXISTS dl_ops;
CREATE SCHEMA IF NOT EXISTS dl_fulfillment;
REVOKE ALL ON SCHEMA dl_ops, dl_fulfillment FROM PUBLIC;

DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='daylight_ops_app') THEN CREATE ROLE daylight_ops_app NOLOGIN; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='daylight_ops_reviewer') THEN CREATE ROLE daylight_ops_reviewer NOLOGIN; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='daylight_fulfillment') THEN CREATE ROLE daylight_fulfillment NOLOGIN; END IF;
END $$;

CREATE FUNCTION dl_ops.reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'append-only operations record'; END $$;

-- True when any object key, at any depth, names commercial economics.
-- Keys only; values are not inspected. Mirrors daylight_operations.records.
CREATE FUNCTION dl_ops.has_commercial_key(doc jsonb) RETURNS boolean
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT coalesce(jsonb_path_exists(doc,
    'lax $.**.keyvalue() ? (@.key like_regex "(^|_)(commissions?|payouts?|compensation|referral_fees?|carrier_contracts?|carrier_appointments?|lifetime_value|revenue)($|_)" flag "i")',
    '{}', true), false)
$$;

-- Recommendation and comparison decisions (I06 reproducibility record).
CREATE TABLE dl_ops.decision_record (
  decision_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  visit_ref text CHECK (visit_ref ~ '^[a-f0-9]{64}$'),
  purpose text NOT NULL CHECK (purpose IN ('published_term_comparison','personal_recommendation','coverage_path_comparison')),
  state text NOT NULL CHECK (state IN ('held','available','no_supported_terms')),
  inputs jsonb NOT NULL,
  inputs_sha256 text NOT NULL CHECK (inputs_sha256 ~ '^[a-f0-9]{64}$'),
  evidence_versions jsonb NOT NULL,
  method_version text NOT NULL,
  policy_version text NOT NULL,
  model_versions jsonb NOT NULL DEFAULT '{}',
  candidate_ids text[] NOT NULL,
  ordered_ids text[] NOT NULL DEFAULT '{}',
  tie_groups jsonb NOT NULL DEFAULT '[]',
  excluded jsonb NOT NULL DEFAULT '[]',
  reason_codes text[] NOT NULL DEFAULT '{}',
  holds jsonb NOT NULL DEFAULT '[]',
  checklist_coverage jsonb NOT NULL DEFAULT '{}',
  CHECK (NOT dl_ops.has_commercial_key(inputs)),
  CHECK (NOT dl_ops.has_commercial_key(evidence_versions)),
  CHECK (NOT dl_ops.has_commercial_key(model_versions)),
  CHECK (NOT dl_ops.has_commercial_key(tie_groups)),
  CHECK (NOT dl_ops.has_commercial_key(excluded)),
  CHECK (NOT dl_ops.has_commercial_key(holds)),
  CHECK (NOT dl_ops.has_commercial_key(checklist_coverage)),
  CHECK (ordered_ids <@ candidate_ids)
);
CREATE TRIGGER decision_record_append_only BEFORE UPDATE OR DELETE ON dl_ops.decision_record
  FOR EACH ROW EXECUTE FUNCTION dl_ops.reject_mutation();

-- Option B: a licensed agent reviews the decision record without contacting the customer.
CREATE TABLE dl_ops.licensed_review (
  review_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  decision_id uuid NOT NULL REFERENCES dl_ops.decision_record,
  reviewer_npn text NOT NULL CHECK (reviewer_npn ~ '^[0-9]{1,10}$'),
  outcome text NOT NULL CHECK (outcome IN ('approved','returned','escalated')),
  reviewed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  staff_minutes numeric(6,1) NOT NULL CHECK (staff_minutes >= 0),
  note text CHECK (char_length(note) <= 2000)
);
CREATE TRIGGER licensed_review_append_only BEFORE UPDATE OR DELETE ON dl_ops.licensed_review
  FOR EACH ROW EXECUTE FUNCTION dl_ops.reject_mutation();

-- One row per model call. Metadata only.
CREATE TABLE dl_ops.model_call_trace (
  trace_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  surface text NOT NULL CHECK (surface ~ '^[a-z0-9:._-]{1,40}$'),
  stage text NOT NULL CHECK (stage ~ '^[A-Za-z0-9:._-]{1,80}$'),
  provider text NOT NULL CHECK (provider ~ '^[A-Za-z]{1,20}$'),
  model text NOT NULL CHECK (model ~ '^[A-Za-z0-9:._/-]{1,80}$'),
  operation text NOT NULL CHECK (operation IN ('count','generate')),
  outcome text NOT NULL CHECK (outcome IN ('completed','incomplete','contract_error','transport_error','error')),
  failure_category text CHECK (failure_category ~ '^[a-z0-9_]{1,40}$'),
  request_sha256 text NOT NULL CHECK (request_sha256 ~ '^[a-f0-9]{64}$'),
  visit_ref text CHECK (visit_ref ~ '^[a-f0-9]{64}$'),
  decision_id uuid REFERENCES dl_ops.decision_record,
  input_tokens integer CHECK (input_tokens >= 0),
  cached_tokens integer CHECK (cached_tokens >= 0),
  cache_write_tokens integer CHECK (cache_write_tokens >= 0),
  output_tokens integer CHECK (output_tokens >= 0),
  latency_ms integer NOT NULL CHECK (latency_ms >= 0),
  metadata jsonb NOT NULL DEFAULT '{}',
  -- Only these short fields; anything else (prompt text included) is rejected.
  CHECK (jsonb_typeof(metadata) = 'object'
         AND (metadata - ARRAY['service_tier','incomplete_reason','attempt']) = '{}'::jsonb
         AND pg_column_size(metadata) <= 512),
  CHECK (NOT dl_ops.has_commercial_key(metadata))
);
CREATE INDEX model_call_trace_time ON dl_ops.model_call_trace (occurred_at);
CREATE INDEX model_call_trace_visit ON dl_ops.model_call_trace (visit_ref) WHERE visit_ref IS NOT NULL;
CREATE TRIGGER model_call_trace_append_only BEFORE UPDATE OR DELETE ON dl_ops.model_call_trace
  FOR EACH ROW EXECUTE FUNCTION dl_ops.reject_mutation();

-- Exception and handoff queue. State lives in append-only events.
CREATE TABLE dl_ops.work_case (
  case_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  opened_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  kind text NOT NULL CHECK (kind IN ('exception','handoff_request','licensed_review','enrollment_followup','data_issue')),
  decision_id uuid REFERENCES dl_ops.decision_record,
  summary text NOT NULL CHECK (char_length(summary) BETWEEN 1 AND 500),
  opened_by text NOT NULL CHECK (char_length(opened_by) BETWEEN 1 AND 80)
);
CREATE TABLE dl_ops.work_case_event (
  event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_id uuid NOT NULL REFERENCES dl_ops.work_case,
  occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  state text NOT NULL CHECK (state IN ('open','in_progress','waiting','resolved','cancelled')),
  actor text NOT NULL CHECK (char_length(actor) BETWEEN 1 AND 80),
  staff_minutes numeric(6,1) NOT NULL DEFAULT 0 CHECK (staff_minutes >= 0),
  note text CHECK (char_length(note) <= 2000)
);
CREATE TRIGGER work_case_append_only BEFORE UPDATE OR DELETE ON dl_ops.work_case
  FOR EACH ROW EXECUTE FUNCTION dl_ops.reject_mutation();
CREATE TRIGGER work_case_event_append_only BEFORE UPDATE OR DELETE ON dl_ops.work_case_event
  FOR EACH ROW EXECUTE FUNCTION dl_ops.reject_mutation();
CREATE VIEW dl_ops.work_case_current AS
  SELECT c.*, e.state, e.occurred_at AS state_at,
         (SELECT coalesce(sum(x.staff_minutes),0) FROM dl_ops.work_case_event x WHERE x.case_id=c.case_id) AS staff_minutes
  FROM dl_ops.work_case c
  JOIN LATERAL (SELECT state, occurred_at FROM dl_ops.work_case_event e
                WHERE e.case_id=c.case_id ORDER BY event_id DESC LIMIT 1) e ON true;

-- Enrollment status: submitted → accepted → effective, from any source.
CREATE TABLE dl_ops.enrollment (
  enrollment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  decision_id uuid REFERENCES dl_ops.decision_record,
  offering_id text NOT NULL CHECK (offering_id ~ '^[HRS][0-9]{4}-[0-9]{3}-[0-9]{3}$'),
  coverage_year integer NOT NULL CHECK (coverage_year BETWEEN 2026 AND 2100),
  platform text NOT NULL CHECK (platform IN ('healthsherpa','carrier_portal','other')),
  agent_of_record_npn text NOT NULL CHECK (agent_of_record_npn ~ '^[0-9]{1,10}$'),
  external_ref text CHECK (char_length(external_ref) <= 120),
  UNIQUE (platform, external_ref)
);
CREATE TABLE dl_ops.enrollment_event (
  event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  enrollment_id uuid NOT NULL REFERENCES dl_ops.enrollment,
  status text NOT NULL CHECK (status IN ('submitted','accepted','rejected','effective','cancelled','disenrolled')),
  source text NOT NULL CHECK (source IN ('platform_webhook','carrier_portal','carrier_notice','commission_statement','manual')),
  observed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  effective_date date,
  payload_sha256 text CHECK (payload_sha256 ~ '^[a-f0-9]{64}$'),
  CHECK (status <> 'effective' OR effective_date IS NOT NULL)
);
CREATE TRIGGER enrollment_append_only BEFORE UPDATE OR DELETE ON dl_ops.enrollment
  FOR EACH ROW EXECUTE FUNCTION dl_ops.reject_mutation();
CREATE TRIGGER enrollment_event_append_only BEFORE UPDATE OR DELETE ON dl_ops.enrollment_event
  FOR EACH ROW EXECUTE FUNCTION dl_ops.reject_mutation();
CREATE VIEW dl_ops.enrollment_current AS
  SELECT n.enrollment_id, n.offering_id, n.coverage_year, n.platform, n.agent_of_record_npn,
         e.status, e.source, e.observed_at AS status_at,
         (SELECT max(x.effective_date) FROM dl_ops.enrollment_event x
           WHERE x.enrollment_id=n.enrollment_id AND x.status='effective') AS effective_date
  FROM dl_ops.enrollment n
  JOIN LATERAL (SELECT status, source, observed_at FROM dl_ops.enrollment_event e
                WHERE e.enrollment_id=n.enrollment_id ORDER BY event_id DESC LIMIT 1) e ON true;

-- Commercial boundary. Decision-side roles have no access to this schema.
CREATE TABLE dl_fulfillment.commission_line (
  line_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  imported_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  statement_ref text NOT NULL CHECK (char_length(statement_ref) BETWEEN 1 AND 120),
  carrier text NOT NULL CHECK (char_length(carrier) BETWEEN 1 AND 120),
  offering_id text CHECK (offering_id ~ '^[HRS][0-9]{4}-[0-9]{3}-[0-9]{3}$'),
  agent_npn text NOT NULL CHECK (agent_npn ~ '^[0-9]{1,10}$'),
  period date NOT NULL,
  kind text NOT NULL CHECK (kind IN ('initial','renewal','chargeback','adjustment')),
  amount_cents bigint NOT NULL,
  enrollment_id uuid REFERENCES dl_ops.enrollment
);
CREATE TRIGGER commission_line_append_only BEFORE UPDATE OR DELETE ON dl_fulfillment.commission_line
  FOR EACH ROW EXECUTE FUNCTION dl_ops.reject_mutation();
CREATE VIEW dl_fulfillment.reconciliation AS
  SELECT c.enrollment_id, c.offering_id, c.status, c.effective_date,
         coalesce(sum(l.amount_cents),0) AS paid_cents, count(l.line_id) AS line_count
  FROM dl_ops.enrollment_current c
  LEFT JOIN dl_fulfillment.commission_line l ON l.enrollment_id=c.enrollment_id
  GROUP BY c.enrollment_id, c.offering_id, c.status, c.effective_date;
CREATE VIEW dl_fulfillment.unmatched_lines AS
  SELECT * FROM dl_fulfillment.commission_line WHERE enrollment_id IS NULL;

-- Grants. The app writes decisions, traces, cases and enrollment events.
GRANT USAGE ON SCHEMA dl_ops TO daylight_ops_app, daylight_ops_reviewer, daylight_fulfillment;
GRANT SELECT, INSERT ON dl_ops.decision_record, dl_ops.model_call_trace, dl_ops.work_case,
  dl_ops.work_case_event, dl_ops.enrollment, dl_ops.enrollment_event TO daylight_ops_app;
GRANT SELECT ON dl_ops.licensed_review, dl_ops.work_case_current, dl_ops.enrollment_current TO daylight_ops_app;
-- Reviewers read decisions and record reviews; they never edit a decision.
GRANT SELECT ON dl_ops.decision_record, dl_ops.licensed_review, dl_ops.work_case, dl_ops.work_case_event,
  dl_ops.work_case_current TO daylight_ops_reviewer;
GRANT INSERT ON dl_ops.licensed_review, dl_ops.work_case_event TO daylight_ops_reviewer;
-- Fulfillment sees enrollment status only on the decision side, never decision inputs or traces.
GRANT SELECT ON dl_ops.enrollment, dl_ops.enrollment_event, dl_ops.enrollment_current TO daylight_fulfillment;
GRANT USAGE ON SCHEMA dl_fulfillment TO daylight_fulfillment;
GRANT SELECT, INSERT ON dl_fulfillment.commission_line TO daylight_fulfillment;
GRANT SELECT ON dl_fulfillment.reconciliation, dl_fulfillment.unmatched_lines TO daylight_fulfillment;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA dl_ops FROM PUBLIC;
GRANT EXECUTE ON FUNCTION dl_ops.has_commercial_key(jsonb) TO daylight_ops_app, daylight_ops_reviewer, daylight_fulfillment;
