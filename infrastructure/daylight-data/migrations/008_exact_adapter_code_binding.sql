-- Initial transport-r1 derivations remain immutable historical runs. New derivations
-- additionally record the exact adapter bytes; no inferred hash fills older rows.
ALTER TABLE dl_control.derivation ADD COLUMN adapter_code_sha256 text
  CHECK(adapter_code_sha256 IS NULL OR adapter_code_sha256 ~ '^[a-f0-9]{64}$');
