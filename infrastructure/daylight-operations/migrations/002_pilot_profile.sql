-- Additive A05 contract. Runtime and login-role provisioning are separate.
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='daylight_pilot_profile') THEN
    CREATE ROLE daylight_pilot_profile NOLOGIN NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='daylight_pilot_staff_gateway') THEN
    CREATE ROLE daylight_pilot_staff_gateway NOLOGIN NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='daylight_pilot_audited_reader') THEN
    CREATE ROLE daylight_pilot_audited_reader NOLOGIN NOBYPASSRLS;
  END IF;
END $$;

CREATE TABLE dl_ops.pilot_profile_grant (
  participant uuid NOT NULL,
  session_digest bytea PRIMARY KEY CHECK (octet_length(session_digest)=32),
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz
);

CREATE TABLE dl_ops.pilot_profile (
  participant uuid PRIMARY KEY,
  profile jsonb NOT NULL CHECK (jsonb_typeof(profile)='object'
                               AND NOT dl_ops.has_commercial_key(profile))
);

CREATE FUNCTION dl_ops.can_access_pilot_profile(owner_id uuid) RETURNS boolean
LANGUAGE sql SECURITY DEFINER VOLATILE SET search_path = pg_catalog AS $$
  SELECT EXISTS (
    SELECT 1 FROM dl_ops.pilot_profile_grant AS g
    WHERE g.participant=owner_id AND g.revoked_at IS NULL
      AND g.expires_at>clock_timestamp()
      AND current_setting('daylight.pilot_session', true) ~ '^[0-9a-f]{64}$'
      AND g.session_digest=sha256(convert_to(current_setting('daylight.pilot_session', true), 'UTF8'))
  )
$$;

REVOKE ALL ON FUNCTION dl_ops.can_access_pilot_profile(uuid) FROM PUBLIC;
REVOKE ALL ON dl_ops.pilot_profile_grant, dl_ops.pilot_profile FROM PUBLIC;
ALTER TABLE dl_ops.pilot_profile ENABLE ROW LEVEL SECURITY;
ALTER TABLE dl_ops.pilot_profile FORCE ROW LEVEL SECURITY;
CREATE POLICY pilot_profile_owner ON dl_ops.pilot_profile TO daylight_pilot_profile
  USING (dl_ops.can_access_pilot_profile(participant))
  WITH CHECK (dl_ops.can_access_pilot_profile(participant));
GRANT USAGE ON SCHEMA dl_ops TO daylight_pilot_profile;
GRANT EXECUTE ON FUNCTION dl_ops.can_access_pilot_profile(uuid),
  dl_ops.has_commercial_key(jsonb) TO daylight_pilot_profile;
GRANT SELECT, INSERT, UPDATE(profile), DELETE ON dl_ops.pilot_profile TO daylight_pilot_profile;

-- Staff access receipts contain opaque record IDs and a fixed purpose only.
CREATE TABLE dl_ops.pilot_access_audit (
  id uuid PRIMARY KEY,
  actor uuid NOT NULL,
  participant uuid NOT NULL,
  event_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  purpose text NOT NULL CHECK (purpose IN ('support', 'access_review', 'incident', 'deletion'))
);
CREATE TRIGGER pilot_access_audit_immutable BEFORE UPDATE OR DELETE ON dl_ops.pilot_access_audit
  FOR EACH ROW EXECUTE FUNCTION dl_ops.reject_mutation();
REVOKE ALL ON dl_ops.pilot_access_audit FROM PUBLIC;

-- The trusted staff gateway must authenticate the actor and commit before
-- returning a record. Never grant these roles to an interactive staff login.
GRANT USAGE ON SCHEMA dl_ops TO daylight_pilot_staff_gateway, daylight_pilot_audited_reader;
GRANT SELECT ON dl_ops.pilot_profile TO daylight_pilot_audited_reader;
GRANT INSERT ON dl_ops.pilot_access_audit TO daylight_pilot_audited_reader;
GRANT SELECT ON dl_ops.pilot_access_audit TO daylight_pilot_staff_gateway;
CREATE POLICY pilot_staff_function_read ON dl_ops.pilot_profile FOR SELECT
  TO daylight_pilot_audited_reader USING (true);

CREATE FUNCTION dl_ops.read_pilot_profile_for_staff(owner_id uuid, actor_id uuid, access_purpose text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER VOLATILE SET search_path = pg_catalog AS $$
DECLARE result jsonb;
BEGIN
  INSERT INTO dl_ops.pilot_access_audit (id, actor, participant, purpose)
    VALUES (gen_random_uuid(), actor_id, owner_id, access_purpose);
  SELECT profile INTO result FROM dl_ops.pilot_profile WHERE participant=owner_id;
  RETURN result;
END
$$;
REVOKE ALL ON FUNCTION dl_ops.read_pilot_profile_for_staff(uuid,uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION dl_ops.read_pilot_profile_for_staff(uuid,uuid,text) TO daylight_pilot_staff_gateway;
ALTER FUNCTION dl_ops.read_pilot_profile_for_staff(uuid,uuid,text) OWNER TO daylight_pilot_audited_reader;
