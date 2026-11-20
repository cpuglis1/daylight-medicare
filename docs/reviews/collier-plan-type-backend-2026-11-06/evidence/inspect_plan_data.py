"""Bounded read-only inspection for the Collier PDP/Medigap backend review.

Run with the daylight-data virtualenv from the repository root. This reads the
documented private local research target; it never imports data or selects a release.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[4]
OUTPUT = Path(__file__).with_name("database.json")
DSN = (
    f"host={ROOT}/infrastructure/daylight-data/.state/socket port=55485 "
    "dbname=daylight_research_2026_r2 user=cep4u"
)

QUERIES = {
    "target_and_release": """SELECT current_database() AS database,
      current_setting('server_version') AS server_version,
      current_setting('transaction_read_only') AS read_only,
      (SELECT count(*) FROM dl_review.acceptance_binding) AS acceptance_bindings,
      (SELECT count(*) FROM dl_review.release) AS releases,
      (SELECT count(*) FROM dl_review.active_release) AS active_releases,
      (SELECT count(*) FROM dl_released.offerings) AS released_offerings""",
    "selected_source_counts": """SELECT s.layer_id,ss.source_set_id,
      ss.derivation_id,ss.source_table,s.original_path,s.artifact_sha256,
      s.source_use_state,
      (SELECT count(*) FROM dl_compact.source_record r
        WHERE r.source_set_id=ss.source_set_id) AS raw_rows,
      (SELECT count(*) FROM dl_compact.observation o
        WHERE o.source_set_id=ss.source_set_id) AS observation_rows
      FROM dl_compact.source_set ss
      JOIN dl_control.derivation d USING(derivation_id)
      JOIN dl_control.source_snapshot s USING(snapshot_id)
      WHERE s.layer_id IN ('L04','L10')
      ORDER BY s.layer_id,ss.source_set_id""",
    "pdp_collier_join": """WITH selected AS MATERIALIZED (
      SELECT ss.source_set_id,ss.source_table
      FROM dl_compact.source_set ss
      JOIN dl_control.derivation d USING(derivation_id)
      JOIN dl_control.source_snapshot s USING(snapshot_id)
      WHERE s.layer_id='L04' AND ss.source_table IN ('pdp_records','counties')),
      counties AS MATERIALIZED (
      SELECT o.county_fips,o.fields->>'region_code' AS region
      FROM dl_compact.observation o JOIN selected ss USING(source_set_id)
      JOIN dl_compact.symbol t ON t.symbol_id=o.entity_type_id
      WHERE ss.source_table='counties' AND t.value='pdp_region_county'),
      plans AS MATERIALIZED (
      SELECT o.offering_id,o.fields->>'region_code' AS region
      FROM dl_compact.observation o JOIN selected ss USING(source_set_id)
      JOIN dl_compact.symbol t ON t.symbol_id=o.entity_type_id
      WHERE ss.source_table='pdp_records' AND t.value='offering')
      SELECT c.county_fips,c.region,count(*) AS published_plan_relationships,
      count(DISTINCT p.offering_id) AS distinct_pdp_ids,
      count(*) FILTER(WHERE p.offering_id IS NULL) AS unmatched
      FROM counties c LEFT JOIN plans p USING(region)
      WHERE c.county_fips='12021' GROUP BY c.county_fips,c.region""",
    "pdp_fields": """SELECT t.value AS entity_type,count(*) AS rows,
      count(o.amount) AS typed_amount_rows,count(o.offering_id) AS offering_id_rows,
      count(o.county_fips) AS county_rows
      FROM dl_compact.observation o
      JOIN dl_compact.source_set ss USING(source_set_id)
      JOIN dl_control.derivation d USING(derivation_id)
      JOIN dl_control.source_snapshot s USING(snapshot_id)
      JOIN dl_compact.symbol t ON t.symbol_id=o.entity_type_id
      WHERE s.layer_id='L04' AND ss.source_table='pdp_records'
      GROUP BY t.value ORDER BY t.value""",
    "medigap_rate_shape": """SELECT s.original_path,t.value AS entity_type,
      count(*) AS rows,count(o.amount) AS typed_amount_rows,
      count(o.offering_id) AS cms_offering_id_rows,
      count(o.county_fips) AS material_county_rows,
      count(o.benefit_year) AS material_benefit_year_rows,
      count(*) FILTER(WHERE o.fields->>'source_status'='REPLACED') AS replaced_rows,
      count(*) FILTER(WHERE o.amount=0) AS source_zero_rows,
      count(*) FILTER(WHERE o.fields->>'rate_effective_from' IS NULL
         OR o.fields->>'rate_effective_through' IS NULL) AS incomplete_period_rows,
      count(*) FILTER(WHERE o.conditions ? 'schedule_id') AS schedule_condition_rows
      FROM dl_compact.observation o
      JOIN dl_compact.source_set ss USING(source_set_id)
      JOIN dl_control.derivation d USING(derivation_id)
      JOIN dl_control.source_snapshot s USING(snapshot_id)
      JOIN dl_compact.symbol t ON t.symbol_id=o.entity_type_id
      WHERE s.layer_id='L10' AND ss.source_table IN
        ('illustrations','carrier_premiums','rate-cells','schedules')
      GROUP BY s.original_path,t.value ORDER BY s.original_path,t.value""",
    "layer_evidence_states": """SELECT s.layer_id,e.source_use_state,
      e.semantic_review_state,e.freshness_state,e.output_acceptance_state,
      count(*) AS observations
      FROM dl_compact.observation o
      JOIN dl_compact.source_set ss USING(source_set_id)
      JOIN dl_control.derivation d USING(derivation_id)
      JOIN dl_control.source_snapshot s USING(snapshot_id)
      JOIN dl_compact.evidence_state e USING(state_id)
      WHERE s.layer_id IN ('L04','L10')
      GROUP BY s.layer_id,e.source_use_state,e.semantic_review_state,
        e.freshness_state,e.output_acceptance_state ORDER BY s.layer_id""",
}


def main():
    if OUTPUT.exists():
        raise RuntimeError("Preserve the earlier observation; use a new evidence revision")
    result = {"observed_at_utc": datetime.now(timezone.utc).isoformat(),
              "meaning": "Research transport/shape inspection, not new data acceptance",
              "queries": {}}
    with psycopg.connect(DSN, autocommit=True, connect_timeout=5,
                        row_factory=dict_row,
                        options="-c default_transaction_read_only=on "
                        "-c statement_timeout=15000 -c lock_timeout=1000") as connection:
        with connection.transaction():
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            for name, sql in QUERIES.items():
                start = time.monotonic()
                rows = connection.execute(sql).fetchall()
                result["queries"][name] = {"sql": sql, "rows": rows,
                                           "elapsed_seconds": time.monotonic() - start}
                if name == "target_and_release":
                    if rows[0]["database"] != "daylight_research_2026_r2" or rows[0]["read_only"] != "on":
                        raise RuntimeError("Unexpected inspection target or transaction mode")
    with OUTPUT.open("x") as handle:
        json.dump(result, handle, indent=2, default=str)
        handle.write("\n")
    for name in ("target_and_release", "pdp_collier_join", "pdp_fields", "medigap_rate_shape", "layer_evidence_states"):
        print(name, json.dumps(result["queries"][name]["rows"], default=str))


if __name__ == "__main__":
    main()
