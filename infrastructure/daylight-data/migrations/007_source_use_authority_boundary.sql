-- Ingest credentials can record captured bytes, never grant processing/redisplay rights.
REVOKE INSERT ON dl_control.source_snapshot FROM daylight_writer;
GRANT INSERT(snapshot_id,layer_id,artifact_sha256,original_path,benefit_year)
  ON dl_control.source_snapshot TO daylight_writer;
