-- Group membership and inherited login permissions must not bypass a STOP.
REVOKE UPDATE,INSERT ON dl_control.source_access_state FROM daylight_writer;
CREATE FUNCTION dl_control.persist_source_stop(p_source_id text,p_reason text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,dl_control AS $$
BEGIN
  IF length(p_source_id)=0 OR length(p_reason)=0 OR p_source_id IS NULL OR p_reason IS NULL THEN
    RAISE EXCEPTION 'source identity and reason required';
  END IF;
  INSERT INTO dl_control.source_access_state(source_id,state,reason)
    VALUES(p_source_id,'stopped',p_reason)
    ON CONFLICT(source_id) DO UPDATE SET state='stopped',reason=EXCLUDED.reason,updated_at=clock_timestamp();
  UPDATE dl_control.job SET state='stopped',owner_id=NULL,lease_until=NULL,fence=fence+1
    WHERE source_id=p_source_id AND state IN ('pending','running');
END $$;
REVOKE ALL ON FUNCTION dl_control.persist_source_stop(text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION dl_control.persist_source_stop(text,text) TO daylight_writer;
