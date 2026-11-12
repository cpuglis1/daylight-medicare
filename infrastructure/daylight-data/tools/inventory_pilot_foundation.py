#!/usr/bin/env python3
"""Measure retained and projected D146 source grains, with no participant inputs."""
import argparse
import json
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from daylight_data.serving.binding import digest
from daylight_data.serving.pilot_foundation import PilotFoundation


QUERIES = {
    'provider_entities_by_namespace_type': """
        SELECT split_part(data->>'entity_key','/',1) AS namespace, data->>'type' AS entity_type,
            count(*) AS entity_rows FROM provider_entities GROUP BY 1,2 ORDER BY 1,2
    """,
    'provider_structured_sites_by_locality': """
        SELECT address->>'state' AS state, address->>'city' AS city,
            address->>'postalCode' AS postal, count(*) AS location_rows
        FROM (SELECT (data->>'address_json')::jsonb AS address FROM provider_sites) s
        GROUP BY 1,2,3 ORDER BY 1,2,3
    """,
    'provider_role_sites_by_namespace_locality_specialty': """
        WITH sites AS (
            SELECT data->>'entity_key' AS site, (data->>'address_json')::jsonb AS address
            FROM provider_sites
        ), edges AS (
            SELECT data->>'entity_key' AS role, data->>'provider_key' AS actor, locations.site,
                specialties.specialty->>'text' AS specialty
            FROM provider_roles r
            LEFT JOIN LATERAL jsonb_array_elements_text(
                CASE WHEN jsonb_typeof((r.data->>'locations_json')::jsonb)='array'
                     THEN (r.data->>'locations_json')::jsonb ELSE '[]'::jsonb END) AS locations(site) ON true
            LEFT JOIN LATERAL jsonb_array_elements(
                CASE WHEN jsonb_typeof((r.data->>'specialty_json')::jsonb)='array'
                     THEN (r.data->>'specialty_json')::jsonb ELSE '[]'::jsonb END) AS specialties(specialty) ON true
        )
        SELECT split_part(role,'/',1) AS namespace, address->>'state' AS state, address->>'city' AS city,
            specialty, count(*) AS source_role_site_specialty_rows, count(DISTINCT actor) AS actor_keys,
            count(DISTINCT sites.site) AS resolved_location_keys
        FROM edges LEFT JOIN sites USING(site) GROUP BY 1,2,3,4 ORDER BY 1,2,3,4
    """,
    'ma_network_evidence_per_plan_and_state': """
        WITH evidence AS (
            SELECT data->>'offering_id' AS offering, data->>'state' AS state, 'role_site_network' AS grain
            FROM ma_role_networks
            UNION ALL SELECT data->>'offering_id',data->>'state','plan_network' FROM ma_plan_networks
            UNION ALL SELECT data->>'offering_id',data->>'state','hospital_plan' FROM ma_hospital_plan
            UNION ALL SELECT data->>'offering_id',data->>'scope_state','directory_plan' FROM ma_plan_documents
            UNION ALL SELECT data->>'offering_id','qualified_plan_name_to_CMS_bridge','wellcare_directory_plan'
            FROM ma_wellcare_plan_documents
        )
        SELECT o.data->>'id' AS offering_id,o.data->>'parent' AS carrier,e.grain,e.state,count(e.offering) AS rows
        FROM ma_offerings o LEFT JOIN evidence e ON o.data->>'id'=e.offering
        GROUP BY 1,2,3,4 ORDER BY 2,1,3,4
    """,
    'ma_role_evidence_by_carrier_locality_state': """
        SELECT p.data->>'parent' AS carrier, a.address->>'state' AS state, a.address->>'city' AS city,
            r.data->>'state' AS evidence_state, count(*) AS rows,
            count(DISTINCT r.data->>'provider_key') AS provider_keys,
            count(DISTINCT a.site) AS resolved_site_keys
        FROM ma_role_networks r JOIN ma_offerings p ON p.data->>'id'=r.data->>'offering_id'
        LEFT JOIN (SELECT data->>'entity_key' AS site,(data->>'address_json')::jsonb AS address FROM provider_sites) a
            ON a.site=r.data->>'location_key'
        GROUP BY 1,2,3,4 ORDER BY 1,2,3,4
    """,
    'ma_pdf_listings_by_family_locality_domain': """
        SELECT r.data->>'family' AS publisher_family, address->>'state' AS state, address->>'city' AS city,
            r.data->>'domain' AS native_listing_domain,
            count(*) AS listing_address_rows, count(DISTINCT r.data->>'id') AS listing_rows
        FROM ma_pdf_listings r
        LEFT JOIN LATERAL jsonb_array_elements(
            CASE WHEN jsonb_typeof((r.data->>'fields_json')::jsonb->'addresses')='array'
                 THEN (r.data->>'fields_json')::jsonb->'addresses' ELSE '[]'::jsonb END) a(address) ON true
        GROUP BY 1,2,3,4 ORDER BY 1,2,3,4
    """,
    'humana_directory_by_printed_county_specialty': """
        SELECT f->>'county_raw' AS publisher_county,f->>'specialty_raw' AS specialty,
            f->>'section_raw' AS section, data->>'site_state' AS site_state, count(*) AS listing_rows
        FROM (SELECT data,(data->>'fields_json')::jsonb AS f FROM ma_humana_listings) a
        GROUP BY 1,2,3,4 ORDER BY 1,2,3,4
    """,
    'wellcare_directory_by_printed_county_locality_specialty': """
        SELECT f->>'county_raw' AS publisher_county,address->>'city_raw' AS city,
            f->>'specialty_raw' AS specialty,f->>'section_raw' AS section,
            count(*) AS listing_address_rows,count(DISTINCT f->>'id') AS listing_rows
        FROM (SELECT (data->>'fields_json')::jsonb AS f FROM ma_wellcare_listings) a
        LEFT JOIN LATERAL jsonb_array_elements(
            CASE WHEN jsonb_typeof(f->'addresses')='array' THEN f->'addresses' ELSE '[]'::jsonb END) n(address) ON true
        GROUP BY 1,2,3,4 ORDER BY 1,2,3,4
    """,
    'aetna_query_by_plan_locality_category': """
        WITH observations AS (
            SELECT data->>'offering_id' AS offering,data->>'category' AS category,
                (data->>'fields_json')::jsonb->'fields' AS fields FROM ma_aetna_query
            UNION ALL
            SELECT data->>'offering_id',(data->>'fields_json')::jsonb->>'category',
                (data->>'fields_json')::jsonb->'fields' FROM ma_aetna_additive_query
            WHERE data->>'family'='aetna'
        )
        SELECT offering,category,coalesce(fields->>'city',fields->>'city_raw') AS city,
            coalesce(fields->>'specialty_or_role_raw',fields->>'specialty_raw') AS specialty,
            count(*) AS query_listing_rows,count(DISTINCT nullif(fields->>'npi','')) AS explicit_npis
        FROM observations GROUP BY 1,2,3,4 ORDER BY 1,2,3,4
    """,
    'federal_clinician_rows_by_locality_specialty': """
        SELECT data->>'state_raw' AS state,data->>'city_raw' AS city,
            left(data->>'postal_raw',5) AS postal, f->>'pri_spec' AS primary_specialty,
            count(*) AS clinician_rows,count(DISTINCT nullif(data->>'npi','')) AS explicit_npis,
            count(DISTINCT nullif(f->>'adrs_id','')) AS source_address_ids
        FROM (SELECT data,(data->>'fields_json')::jsonb AS f FROM federal_provider_rows
              WHERE data->>'source_id'='clinicians') a
        GROUP BY 1,2,3,4 ORDER BY 1,2,3,4
    """,
    'federal_clinicians_by_selection': """
        SELECT count(*) AS projected_clinician_rows,
            count(DISTINCT nullif(data->>'npi','')) AS projected_npis,
            count(DISTINCT nullif((data->>'fields_json')::jsonb->>'adrs_id','')) AS source_address_ids
        FROM federal_provider_rows WHERE data->>'source_id'='clinicians'
    """,
    'federal_provider_observations_by_source': """
        SELECT data->>'source_id' AS source_id,count(*) AS projected_rows,
            count(DISTINCT nullif(data->>'npi','')) AS explicit_npis
        FROM federal_provider_rows GROUP BY 1 ORDER BY 1
    """,
    'federal_retained_denominators_by_source': """
        SELECT data->>'id' AS source_id,f->'national_source_rows' AS native_national_rows,
            f->'selected_rows' AS retained_source_rows,f->'selected_state_row_counts' AS retained_by_state
        FROM (SELECT data,(data->>'fields_json')::jsonb AS f FROM federal_sources) a ORDER BY 1
    """,
    'federal_hospitals_by_locality': """
        SELECT data->>'state_raw' AS state,data->>'county_raw' AS county,data->>'city_raw' AS city,
            data->>'type_raw' AS facility_type,count(*) AS rows
        FROM federal_hospitals GROUP BY 1,2,3,4 ORDER BY 1,2,3,4
    """,
    'pharmacy_location_pairs_by_county_and_identity_state': """
        SELECT data->>'county_fips' AS county_fips,data->>'scope_group' AS scope_group,
            data->>'identity_status' AS identity_status,count(*) AS source_npi_zip_pairs,
            count(DISTINCT data->>'npi') AS npis
        FROM pharmacy_locations GROUP BY 1,2,3 ORDER BY 1,2,3
    """,
    'pharmacy_locality_by_native_zip_and_county': """
        SELECT data->>'county_fips' AS county_fips,data->>'network_zip' AS source_zip,
            count(*) AS source_npi_zip_pairs
        FROM pharmacy_locations WHERE data->>'county_fips' IN ('12021','12071','12051','12015','12043','12087')
        GROUP BY 1,2 ORDER BY 1,2
    """,
    'pharmacy_network_by_carrier_county_channel': """
        SELECT (p.data->>'payload')::jsonb->>'parent' AS carrier,
            l.data->>'county_fips' AS supported_county_fips,
            n.data->>'retail_status' AS retail_status,n.data->>'mail_status' AS mail_status,
            count(*) AS native_network_rows,count(DISTINCT n.data->>'offering_id') AS plans,
            count(DISTINCT (n.data->>'pharmacy_npi',n.data->>'PHARMACY_ZIPCODE')) AS npi_zip_pairs
        FROM pharmacy_network n JOIN drug_plans p ON n.data->>'offering_id'=p.data->>'offering_id'
        LEFT JOIN pharmacy_locations l ON n.data->>'pharmacy_npi'=l.data->>'npi'
            AND n.data->>'PHARMACY_ZIPCODE'=l.data->>'network_zip'
        GROUP BY 1,2,3,4 ORDER BY 1,2,3,4
    """,
    'pharmacy_network_by_plan_channel': """
        SELECT n.data->>'offering_id' AS offering_id,n.data->>'retail_status' AS retail_status,
            n.data->>'mail_status' AS mail_status,count(*) AS native_network_rows
        FROM pharmacy_network n GROUP BY 1,2,3 ORDER BY 1,2,3
    """,
    'formulary_counts_by_native_grain': """
        SELECT data->>'table_name' AS source_table,count(*) AS rows,
            count(DISTINCT nullif(data->>'formulary_id','')) AS formulary_ids,
            count(DISTINCT nullif(data->>'rxcui','')) AS rxcuis,
            count(DISTINCT nullif(data->>'ndc','')) AS ndcs
        FROM formulary_rows GROUP BY 1 ORDER BY 1
    """,
    'drug_coverage_and_cost_by_plan': """
        WITH prices AS (
            SELECT data->>'offering_id' AS offering_id,count(*) AS price_rows,
                count(*) FILTER (WHERE data->>'days_supply'='30') AS price_30_day_rows,
                count(*) FILTER (WHERE data->>'days_supply'='90') AS price_90_day_rows
            FROM average_prices GROUP BY 1
        ), pairs AS (
            SELECT data->>'offering_id' AS offering_id,count(*) AS basic_formulary_price_pairs
            FROM average_price_pairs GROUP BY 1
        ), costs AS (
            SELECT data->>'offering_id' AS offering_id,
                count(*) FILTER (WHERE data->>'table_name'='beneficiary') AS beneficiary_rows,
                count(*) FILTER (WHERE data->>'table_name'='insulin') AS insulin_rows
            FROM cost_schedules GROUP BY 1
        ), plans AS (
            SELECT data->>'offering_id' AS offering_id,(data->>'payload')::jsonb AS f FROM drug_plans
        )
        SELECT p.offering_id,f->>'parent' AS carrier,f->>'kind' AS plan_type,f->>'formulary_id' AS formulary_id,
            f->>'formulary_version' AS formulary_version,f->'basic_rows' AS basic_rows,
            f->'excluded_rows' AS supplemental_excluded_rows,f->'indication_rows' AS supplemental_indication_rows,
            prices.price_rows,prices.price_30_day_rows,prices.price_90_day_rows,pairs.basic_formulary_price_pairs,
            costs.beneficiary_rows,costs.insulin_rows,s.data->>'condition_source_state' AS condition_source_state
        FROM plans p LEFT JOIN prices USING(offering_id) LEFT JOIN pairs USING(offering_id)
        LEFT JOIN costs USING(offering_id) LEFT JOIN criteria_plan_status s ON p.offering_id=s.data->>'offering_id'
        ORDER BY carrier,p.offering_id
    """,
    'physical_quantity_unit_status': """
        SELECT data->>'state' AS state,count(*) AS native_quantity_contexts
        FROM quantity_units GROUP BY 1 ORDER BY 1
    """,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binding', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    foundation = PilotFoundation(args.binding, root=root,
        package_dsn=os.environ['DAYLIGHT_FOUNDATION_PACKAGE_DSN'],
        source_dsn=os.environ['DAYLIGHT_FOUNDATION_SOURCE_DSN'])
    check = foundation.read('drug_plans', year=2026, county_fips='12021', purpose='offline_research',
                            filters={'offering_id': '2026:H0710:010:000'}, limit=1)
    if check['state'] != 'source_observations':
        raise ValueError('Inventory target validation failed')
    with psycopg.connect(foundation.package_dsn, row_factory=dict_row,
                         options='-c default_transaction_read_only=on -c statement_timeout=120000') as conn:
        conn.execute('SET LOCAL search_path=dl_pilot_foundation,pg_catalog')
        results = {}
        for key, query in QUERIES.items():
            try:
                results[key] = conn.execute(query).fetchall()
            except psycopg.Error as error:
                raise RuntimeError(f'Inventory query failed: {key}') from error
    foundation._check_controls()
    ids = {row['offering_id'] for row in results['ma_network_evidence_per_plan_and_state']}
    if len(ids) != 72 or len(results['drug_coverage_and_cost_by_plan']) != 71:
        raise ValueError('Inventory denominator mismatch')
    report = {
        'package_id': check['package_id'], 'binding_id': check['binding_id'],
        'interpretation': [
            'Counts are retained source grains. Rows, actor keys, location keys, NPIs and listing/address observations are separate denominators.',
            'Cities, ZIPs and printed county headings preserve source text. A city or ZIP alone does not establish county membership.',
            'Grouped distinct counts can overlap across localities, carriers or specialties. Missing buckets and source nonmatches stay unknown.',
            'Formulary, price and schedule locality is the declared offering scope, not a local store measurement. Shared formularies repeat by plan in the per-plan table.',
            'Federal rows are separate from MA directory evidence. Raw Opt-Out addresses, when present, do not establish a practice site.',
        ],
        'dataset_counts': {key: {'projected': value['rows'], 'source_table': value['retained_source_table_rows']}
                           for key, value in foundation.manifest['datasets'].items()},
        'inventory_sha256': digest(results), **results,
    }
    with args.output.open('x') as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write('\n')
    print(f'{len(QUERIES)} inventory tables, 72 MA and 71 drug-bearing plan denominators')


if __name__ == '__main__':
    main()
