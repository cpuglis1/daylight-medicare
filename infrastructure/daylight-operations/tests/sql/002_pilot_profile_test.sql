\set ON_ERROR_STOP on
BEGIN;
INSERT INTO dl_ops.pilot_profile VALUES
  ('00000000-0000-0000-0000-000000000001', '{"fictional":1}'),
  ('00000000-0000-0000-0000-000000000002', '{"fictional":2}');
INSERT INTO dl_ops.pilot_profile_grant VALUES
  ('00000000-0000-0000-0000-000000000001', sha256(convert_to(repeat('a',64),'UTF8')), now() + interval '1 hour', NULL),
  ('00000000-0000-0000-0000-000000000002', sha256(convert_to(repeat('b',64),'UTF8')), now() + interval '1 hour', NULL);

SET LOCAL ROLE daylight_pilot_profile;
DO $$ BEGIN
  IF EXISTS (SELECT FROM dl_ops.pilot_profile) THEN RAISE EXCEPTION 'missing scope exposed a profile'; END IF;
  PERFORM set_config('daylight.pilot_session', repeat('a',64), true);
  IF (SELECT array_agg(profile->>'fictional') FROM dl_ops.pilot_profile) <> ARRAY['1']
     OR (SELECT count(*) FROM dl_ops.pilot_profile) <> 1 THEN
    RAISE EXCEPTION 'beneficiary one has the wrong scope';
  END IF;
  UPDATE dl_ops.pilot_profile SET profile='{}' WHERE participant='00000000-0000-0000-0000-000000000002';
  IF FOUND THEN RAISE EXCEPTION 'cross-beneficiary update'; END IF;
  BEGIN
    INSERT INTO dl_ops.pilot_profile VALUES ('00000000-0000-0000-0000-000000000003', '{}');
    RAISE EXCEPTION 'cross-beneficiary insert';
  EXCEPTION WHEN insufficient_privilege THEN NULL;
  END;
  BEGIN
    PERFORM 1 FROM dl_ops.pilot_profile_grant;
    RAISE EXCEPTION 'app could inspect grant credentials';
  EXCEPTION WHEN insufficient_privilege THEN NULL;
  END;
  PERFORM set_config('daylight.pilot_session', repeat('b',64), true);
  IF (SELECT array_agg(profile->>'fictional') FROM dl_ops.pilot_profile) <> ARRAY['2']
     OR (SELECT count(*) FROM dl_ops.pilot_profile) <> 1 THEN
    RAISE EXCEPTION 'beneficiary two has the wrong scope';
  END IF;
END $$;

RESET ROLE;
UPDATE dl_ops.pilot_profile_grant SET revoked_at=clock_timestamp()
  WHERE participant='00000000-0000-0000-0000-000000000002';
SET LOCAL ROLE daylight_pilot_profile;
DO $$ BEGIN
  IF EXISTS (SELECT FROM dl_ops.pilot_profile) THEN RAISE EXCEPTION 'revoked grant retained access'; END IF;
END $$;
RESET ROLE;
SET LOCAL ROLE daylight_pilot_staff_gateway;
DO $$ BEGIN
  BEGIN
    PERFORM 1 FROM dl_ops.pilot_profile;
    RAISE EXCEPTION 'staff read without audit';
  EXCEPTION WHEN insufficient_privilege THEN NULL;
  END;
  IF dl_ops.read_pilot_profile_for_staff('00000000-0000-0000-0000-000000000001',
                                        '00000000-0000-0000-0000-000000000004','support')
     IS DISTINCT FROM '{"fictional":1}'::jsonb THEN
    RAISE EXCEPTION 'audited read failed';
  END IF;
  IF NOT EXISTS (SELECT FROM dl_ops.pilot_access_audit
                 WHERE actor='00000000-0000-0000-0000-000000000004' AND purpose='support') THEN
    RAISE EXCEPTION 'missing access receipt';
  END IF;
END $$;
ROLLBACK;
