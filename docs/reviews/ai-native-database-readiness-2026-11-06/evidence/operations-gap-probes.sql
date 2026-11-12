-- Fictional diagnostics only; run after 001_operations.sql in a disposable cluster.
-- A true result records a missing guard, not intended production behavior.
BEGIN;
SET LOCAL ROLE daylight_ops_app;
INSERT INTO dl_ops.decision_record
  (decision_id,purpose,state,inputs,inputs_sha256,evidence_versions,method_version,policy_version,candidate_ids)
VALUES ('00000000-0000-4000-8000-000000000001','personal_recommendation','available',
  '{}',repeat('0',64),'{}','fictional-method','fictional-policy','{}');
SELECT jsonb_build_object('available_recommendation_without_evidence_review_or_confirmation_accepted',
  EXISTS(SELECT 1 FROM dl_ops.decision_record WHERE decision_id='00000000-0000-4000-8000-000000000001'
    AND evidence_versions='{}' AND checklist_coverage='{}' AND visit_ref IS NULL));
INSERT INTO dl_ops.enrollment(enrollment_id,offering_id,coverage_year,platform,agent_of_record_npn,external_ref)
VALUES ('00000000-0000-4000-8000-000000000002','H0000-000-000',2026,'other','1234567890','fictional-only');
INSERT INTO dl_ops.enrollment_event(enrollment_id,status,source,effective_date)
VALUES ('00000000-0000-4000-8000-000000000002','effective','manual','2026-12-01');
INSERT INTO dl_ops.enrollment_event(enrollment_id,status,source)
VALUES ('00000000-0000-4000-8000-000000000002','submitted','platform_webhook');
INSERT INTO dl_ops.enrollment_event(enrollment_id,status,source)
VALUES ('00000000-0000-4000-8000-000000000002','submitted','platform_webhook');
SELECT jsonb_build_object(
  'enrollment_without_decision_or_authorization_reference_accepted',
    (SELECT decision_id IS NULL FROM dl_ops.enrollment WHERE enrollment_id='00000000-0000-4000-8000-000000000002'),
  'late_callback_regresses_effective_to_submitted',
    (SELECT status='submitted' FROM dl_ops.enrollment_current WHERE enrollment_id='00000000-0000-4000-8000-000000000002'),
  'duplicate_callbacks_retained_without_idempotency_key',
    (SELECT count(*)=2 FROM dl_ops.enrollment_event WHERE enrollment_id='00000000-0000-4000-8000-000000000002' AND status='submitted')
);
ROLLBACK;
