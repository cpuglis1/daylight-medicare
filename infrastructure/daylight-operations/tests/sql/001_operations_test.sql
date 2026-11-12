-- Assertions for migrations/001_operations.sql. Run by tests/run_sql_tests.sh
-- against a disposable database. Any failed assertion stops with an error.
\set ON_ERROR_STOP 1

-- Passes only when the statement fails with the expected SQLSTATE:
-- 23514 check violation, 42501 permission denied, P0001 append-only trigger,
-- 22P02 invalid text representation.
CREATE FUNCTION pg_temp.expect_error(statement text, label text, expected text) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  BEGIN
    EXECUTE statement;
  EXCEPTION WHEN OTHERS THEN
    IF SQLSTATE <> expected THEN
      RAISE EXCEPTION 'wrong rejection for %: got % (%), expected %', label, SQLSTATE, SQLERRM, expected;
    END IF;
    RAISE NOTICE 'ok (rejected %): %', SQLSTATE, label;
    RETURN;
  END;
  RAISE EXCEPTION 'expected rejection but statement succeeded: %', label;
END $$;

-- Commercial-key guard: keys at any depth, case-insensitive; values ignored.
DO $$ BEGIN
  ASSERT dl_ops.has_commercial_key('{"commission": 1}'), 'top-level key';
  ASSERT dl_ops.has_commercial_key('{"a": [{"b": {"Carrier_Contract": true}}]}'), 'nested key';
  ASSERT dl_ops.has_commercial_key('{"initial_commission_cents": 694}'), 'compound key';
  ASSERT NOT dl_ops.has_commercial_key('{"referral_required": true}'), 'specialist referral is a plan term';
  ASSERT NOT dl_ops.has_commercial_key('{"note": "commission"}'), 'values are not keys';
  ASSERT NOT dl_ops.has_commercial_key('[1, "x", null]'), 'arrays of scalars';
  ASSERT NOT dl_ops.has_commercial_key('"scalar"'), 'scalar document';
  RAISE NOTICE 'ok: has_commercial_key';
END $$;

-- A valid decision record, then the protections around it.
INSERT INTO dl_ops.decision_record (decision_id, purpose, state, inputs, inputs_sha256, evidence_versions,
  method_version, policy_version, candidate_ids, ordered_ids, reason_codes, holds, checklist_coverage)
VALUES ('00000000-0000-0000-0000-000000000001', 'published_term_comparison', 'available',
  '{"priority_order": ["monthly_premium"], "zip": "34102"}', repeat('a', 64),
  '{"catalog": "r13"}', 'plans-method-v1', 'policy-v1',
  ARRAY['H1036-217-000','H1032-198-000'], ARRAY['H1032-198-000','H1036-217-000'],
  ARRAY['PUBLISHED_TERMS_ONLY'], '[]', '{"formulary_coverage": {"covered": true}}');

SELECT pg_temp.expect_error($q$INSERT INTO dl_ops.decision_record (purpose, state, inputs, inputs_sha256,
  evidence_versions, method_version, policy_version, candidate_ids)
  VALUES ('personal_recommendation','held','{"carrier_payout": 1}', repeat('b',64), '{}', 'm', 'p', ARRAY['x'])$q$,
  'commercial key in decision inputs', '23514');
SELECT pg_temp.expect_error($q$INSERT INTO dl_ops.decision_record (purpose, state, inputs, inputs_sha256,
  evidence_versions, method_version, policy_version, candidate_ids, ordered_ids)
  VALUES ('published_term_comparison','available','{}', repeat('c',64), '{}', 'm', 'p', ARRAY['a'], ARRAY['b'])$q$,
  'ordered id outside the candidate set', '23514');
SELECT pg_temp.expect_error($q$INSERT INTO dl_ops.decision_record (purpose, state, inputs, inputs_sha256,
  evidence_versions, method_version, policy_version, candidate_ids)
  VALUES ('best_for_revenue','held','{}', repeat('d',64), '{}', 'm', 'p', ARRAY['a'])$q$,
  'unknown purpose', '23514');
SELECT pg_temp.expect_error($q$UPDATE dl_ops.decision_record SET state='held'$q$, 'decision update', 'P0001');
SELECT pg_temp.expect_error($q$DELETE FROM dl_ops.decision_record$q$, 'decision delete', 'P0001');

-- Licensed review (Option B) records staff minutes and cannot be edited.
INSERT INTO dl_ops.licensed_review (decision_id, reviewer_npn, outcome, staff_minutes)
VALUES ('00000000-0000-0000-0000-000000000001', '1234567', 'approved', 4.5);
SELECT pg_temp.expect_error($q$UPDATE dl_ops.licensed_review SET outcome='returned'$q$, 'review update', 'P0001');
SELECT pg_temp.expect_error($q$INSERT INTO dl_ops.licensed_review (decision_id, reviewer_npn, outcome, staff_minutes)
  VALUES ('00000000-0000-0000-0000-000000000001', 'ABC', 'approved', 1)$q$, 'non-numeric NPN', '23514');

-- Traces: metadata only.
INSERT INTO dl_ops.model_call_trace (surface, stage, provider, model, operation, outcome, request_sha256,
  input_tokens, output_tokens, latency_ms, metadata, decision_id)
VALUES ('advisor-8893', 'daylight_resolved_conversation', 'Anthropic', 'claude-opus-5-5', 'generate', 'completed',
  repeat('e',64), 1200, 300, 1830, '{"service_tier": "standard", "attempt": 1}', '00000000-0000-0000-0000-000000000001');
SELECT pg_temp.expect_error($q$INSERT INTO dl_ops.model_call_trace (surface, stage, provider, model, operation,
  outcome, request_sha256, latency_ms, metadata)
  VALUES ('advisor-8893','s','OpenAI','gpt-6.1-sol','generate','completed', repeat('f',64), 10,
  '{"prompt": "my doctor is Dr. Smith"}')$q$, 'prompt text in trace metadata', '23514');
SELECT pg_temp.expect_error($q$INSERT INTO dl_ops.model_call_trace (surface, stage, provider, model, operation,
  outcome, request_sha256, latency_ms) VALUES ('advisor-8893','s','OpenAI','m','generate','completed','not-a-hash',1)$q$,
  'malformed request hash', '23514');
SELECT pg_temp.expect_error($q$INSERT INTO dl_ops.model_call_trace (surface, stage, provider, model, operation,
  outcome, request_sha256, latency_ms, visit_ref)
  VALUES ('advisor-8893','s','OpenAI','m','generate','completed', repeat('1',64), 1, 'Jane Doe')$q$,
  'visit reference must be an opaque hash', '23514');
SELECT pg_temp.expect_error($q$DELETE FROM dl_ops.model_call_trace$q$, 'trace delete', 'P0001');

-- Cases: state is the latest event; staff minutes accumulate.
INSERT INTO dl_ops.work_case (case_id, kind, summary, opened_by)
VALUES ('00000000-0000-0000-0000-0000000000c1', 'exception', 'Doctor not found in directory', 'system');
INSERT INTO dl_ops.work_case_event (case_id, state, actor, staff_minutes)
VALUES ('00000000-0000-0000-0000-0000000000c1', 'open', 'system', 0),
       ('00000000-0000-0000-0000-0000000000c1', 'resolved', 'reviewer', 6);
DO $$ BEGIN
  ASSERT (SELECT state FROM dl_ops.work_case_current) = 'resolved', 'latest case state';
  ASSERT (SELECT staff_minutes FROM dl_ops.work_case_current) = 6, 'case staff minutes';
  RAISE NOTICE 'ok: work_case_current';
END $$;

-- Enrollment status from submission to effective date.
INSERT INTO dl_ops.enrollment (enrollment_id, offering_id, coverage_year, platform, agent_of_record_npn, external_ref)
VALUES ('00000000-0000-0000-0000-0000000000e1', 'H1032-198-000', 2026, 'healthsherpa', '1234567', 'app-001');
INSERT INTO dl_ops.enrollment_event (enrollment_id, status, source) VALUES
  ('00000000-0000-0000-0000-0000000000e1', 'submitted', 'platform_webhook'),
  ('00000000-0000-0000-0000-0000000000e1', 'accepted', 'carrier_portal');
INSERT INTO dl_ops.enrollment_event (enrollment_id, status, source, effective_date) VALUES
  ('00000000-0000-0000-0000-0000000000e1', 'effective', 'carrier_notice', '2026-12-01');
SELECT pg_temp.expect_error($q$INSERT INTO dl_ops.enrollment_event (enrollment_id, status, source)
  VALUES ('00000000-0000-0000-0000-0000000000e1','effective','manual')$q$, 'effective without a date', '23514');
SELECT pg_temp.expect_error($q$INSERT INTO dl_ops.enrollment (offering_id, coverage_year, platform, agent_of_record_npn)
  VALUES ('Humana Gold', 2026, 'healthsherpa', '1')$q$, 'malformed offering id', '23514');
DO $$ BEGIN
  ASSERT (SELECT status FROM dl_ops.enrollment_current) = 'effective', 'latest enrollment status';
  ASSERT (SELECT effective_date FROM dl_ops.enrollment_current) = '2026-12-01', 'effective date';
  RAISE NOTICE 'ok: enrollment_current';
END $$;

-- Commission lines live behind the fulfillment boundary.
INSERT INTO dl_fulfillment.commission_line (statement_ref, carrier, offering_id, agent_npn, period, kind, amount_cents, enrollment_id)
VALUES ('stmt-2026-12', 'Fictional Carrier', 'H1032-198-000', '1234567', '2026-12-01', 'initial', 69400,
        '00000000-0000-0000-0000-0000000000e1'),
       ('stmt-2026-12', 'Fictional Carrier', NULL, '1234567', '2026-12-01', 'adjustment', -500, NULL);
DO $$ BEGIN
  ASSERT (SELECT paid_cents FROM dl_fulfillment.reconciliation) = 69400, 'reconciled amount';
  ASSERT (SELECT count(*) FROM dl_fulfillment.unmatched_lines) = 1, 'unmatched line';
  RAISE NOTICE 'ok: reconciliation';
END $$;

-- Role boundaries.
SET ROLE daylight_ops_app;
SELECT count(*) FROM dl_ops.decision_record;
INSERT INTO dl_ops.model_call_trace (surface, stage, provider, model, operation, outcome, request_sha256, latency_ms)
VALUES ('advisor-8893', 'count', 'OpenAI', 'gpt-6.1-sol', 'count', 'completed', repeat('2',64), 40);
SELECT pg_temp.expect_error($q$SELECT * FROM dl_fulfillment.commission_line$q$, 'app reads commissions', '42501');
SELECT pg_temp.expect_error($q$SELECT * FROM dl_fulfillment.reconciliation$q$, 'app reads reconciliation', '42501');
SELECT pg_temp.expect_error($q$INSERT INTO dl_ops.licensed_review (decision_id, reviewer_npn, outcome, staff_minutes)
  VALUES ('00000000-0000-0000-0000-000000000001','1','approved',1)$q$, 'app writes a licensed review', '42501');
RESET ROLE;

SET ROLE daylight_ops_reviewer;
SELECT count(*) FROM dl_ops.decision_record;
INSERT INTO dl_ops.licensed_review (decision_id, reviewer_npn, outcome, staff_minutes)
VALUES ('00000000-0000-0000-0000-000000000001', '7654321', 'returned', 2);
SELECT pg_temp.expect_error($q$INSERT INTO dl_ops.decision_record (purpose, state, inputs, inputs_sha256,
  evidence_versions, method_version, policy_version, candidate_ids)
  VALUES ('published_term_comparison','held','{}', repeat('3',64), '{}', 'm', 'p', ARRAY['a'])$q$,
  'reviewer writes a decision', '42501');
SELECT pg_temp.expect_error($q$SELECT * FROM dl_fulfillment.commission_line$q$, 'reviewer reads commissions', '42501');
RESET ROLE;

SET ROLE daylight_fulfillment;
SELECT count(*) FROM dl_ops.enrollment_current;
SELECT count(*) FROM dl_fulfillment.reconciliation;
INSERT INTO dl_fulfillment.commission_line (statement_ref, carrier, agent_npn, period, kind, amount_cents)
VALUES ('stmt-2027-01', 'Fictional Carrier', '1234567', '2027-01-01', 'renewal', 34700);
SELECT pg_temp.expect_error($q$SELECT * FROM dl_ops.decision_record$q$, 'fulfillment reads decision inputs', '42501');
SELECT pg_temp.expect_error($q$SELECT * FROM dl_ops.model_call_trace$q$, 'fulfillment reads traces', '42501');
SELECT pg_temp.expect_error($q$INSERT INTO dl_ops.enrollment_event (enrollment_id, status, source)
  VALUES ('00000000-0000-0000-0000-0000000000e1','cancelled','manual')$q$, 'fulfillment edits enrollment status', '42501');
RESET ROLE;

SELECT 'ALL OPERATIONS SQL ASSERTIONS PASSED' AS result;
