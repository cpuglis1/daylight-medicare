-- Metadata only. No customer profile, health report, transcript or result persistence.
CREATE TABLE dl_control.profile_contract (
  contract_sha256 text PRIMARY KEY,
  question_count integer NOT NULL CHECK(question_count=41),
  field_count integer NOT NULL CHECK(field_count=78),
  gap_count integer NOT NULL CHECK(gap_count=14),
  contract_payload jsonb NOT NULL
);
GRANT SELECT ON dl_control.profile_contract TO daylight_writer,daylight_validator,daylight_reviewer,daylight_research_reader;
GRANT INSERT ON dl_control.profile_contract TO daylight_writer;
CREATE TRIGGER contract_immutable BEFORE UPDATE OR DELETE ON dl_control.profile_contract FOR EACH ROW EXECUTE FUNCTION dl_control.reject_mutation();
