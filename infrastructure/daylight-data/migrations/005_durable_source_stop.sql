-- A worker may retain/add a STOP, but cannot clear it on restart or retry.
CREATE FUNCTION dl_control.guard_source_stop() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.state='stopped' AND NEW.state<>'stopped' AND current_user='daylight_writer' THEN
    RAISE EXCEPTION 'worker cannot clear a persisted source STOP';
  END IF;
  RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION dl_control.guard_source_stop() FROM PUBLIC;
CREATE TRIGGER source_stop_guard BEFORE UPDATE ON dl_control.source_access_state
  FOR EACH ROW EXECUTE FUNCTION dl_control.guard_source_stop();
