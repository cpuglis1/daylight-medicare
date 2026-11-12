#!/usr/bin/env python3
"""Build and verify a separate D146 offline PostgreSQL revision from sealed inputs."""
import argparse
from contextlib import ExitStack, closing
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import sqlite3

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.types.json import Jsonb

from daylight_data.serving.binding import PACKET, canonical, digest
from daylight_data.serving.pilot_foundation import SCHEMA, VERSION, file_hash, source_controls
from daylight_data.serving.provider_candidates import _name_groups


ROOT = Path(__file__).resolve().parents[3]
INFRA = Path('infrastructure/daylight-data')
POLICY_PATH = INFRA / 'config/pilot-foundation.2026.r1.json'
COMPOSITION_PATH = INFRA / 'config/source-composition.2026.json'
L05 = Path('docs/data/l05-drug-coverage-2026-10-25')
L06 = Path('docs/data/l06-drug-costs-2026-10-27')
L07 = Path('docs/data/l07-pharmacy-networks-2026-10-27')
L08 = Path('docs/data/l08-provider-networks-2026-10-27')
DATABASE = 'daylight_pilot_foundation_2026_r1'
RESEARCH_DATABASE = 'daylight_research_2026_r2'
REGIONAL_COUNTIES = "'12021','12071','12051','12015','12043','12087'"
# These prefixes select a research catchment; the source ZIP alone supplies no county.
REGIONAL_ZIP = "IN ('339','341','330')"
CONTROL_PATHS = (
    POLICY_PATH, COMPOSITION_PATH,
    L05 / 'SELECTION.json', L05 / 'CLOSEOUT_SELECTION.json', L05 / 'FIREFOX_ACQUISITION_SELECTION.json',
    L05 / 'CLOSEOUT.md', L06 / 'CURRENT_REFERENCE.json', L06 / 'COST_SELECTION.json',
    L06 / 'SELECTION.json', L07 / 'CURRENT_REFERENCE.json', L08 / 'CURRENT_REFERENCE.json',
    L08 / 'acquisition-r1/stopped-hosts.json', L08 / 'hospital-reference-r7/genuine-gaps.json',
    Path(PACKET) / 'TARGET.json',
)


def read_json(path):
    return json.loads((ROOT / path).read_text())


def readonly_sqlite(path):
    return sqlite3.connect((ROOT / path).as_uri() + '?mode=ro&immutable=1', uri=True)


def write_json(path, data):
    with path.open('x') as stream:
        json.dump(data, stream, indent=2, ensure_ascii=False, sort_keys=True)
        stream.write('\n')


def values(row):
    # SQLite BLOBs in these sources are native PSV lines. Keep every byte.
    return {key: value.hex() if isinstance(value, bytes) else value for key, value in dict(row).items()}


def names_for(row, path):
    value = row
    for field in path.split('.') if path else ():
        value = value.get(field) if isinstance(value, dict) else None
        if isinstance(value, str) and field.endswith(('_json', 'payload')):
            value = json.loads(value)
    if path == 'federal':
        facts = json.loads(row['fields_json'])
        value = ' '.join(facts.get(key) or '' for key in
                         ('Provider First Name', 'Provider Last Name', 'Facility Name'))
    return [' '.join(group) for group in _name_groups(value)] if path else []


class Builder:
    def __init__(self, conn, stack, layers):
        self.conn = conn
        self.stack = stack
        self.layers = layers
        self.sources = {}
        self.datasets = {}
        self.conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(SCHEMA)))
        self.conn.execute(sql.SQL('REVOKE ALL ON SCHEMA {} FROM PUBLIC').format(sql.Identifier(SCHEMA)))

    def source(self, path, layer):
        if path in self.sources:
            return self.sources[path]
        component = next(c for c in self.layers[layer]['components']
                         if c['path'] == str(path.parent))
        control = read_json(component['control_path'])
        files = control.get('files_sha256', control.get('files', {}))
        expected = files.get(path.name, files.get(str(path)))
        if isinstance(expected, dict):
            expected = expected['sha256']
        if not expected or file_hash(ROOT / path) != expected:
            raise ValueError(f'Sealed artifact mismatch: {path}')
        db = None
        if path.suffix.startswith('.sqlite'):
            db = self.stack.enter_context(closing(readonly_sqlite(path)))
            db.row_factory = sqlite3.Row
        self.sources[path] = expected, component['control_path'], db
        return self.sources[path]

    def add(self, name, layer, capability, path, table=None, *, filters, name_path=None,
            where='1', columns='*', npi_array=False):
        sha, parent, db = self.source(path, layer)
        full_count = None
        if db is not None:
            primary = sorted((r['pk'], r['name']) for r in db.execute(f'PRAGMA table_info({table})') if r['pk'])
            keys = [key for _, key in primary] or ['source_rowid']
            order = ','.join(key if key != 'source_rowid' else 'rowid' for key in keys)
            if keys == ['source_rowid']:
                columns = 'rowid AS source_rowid,' + columns
            full_count = db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
            rows = (values(row) for row in db.execute(f'SELECT {columns} FROM {table} WHERE {where} ORDER BY {order}'))
        else:
            if table == 'jsonl':
                stream = self.stack.enter_context(gzip.open(ROOT / path, 'rt'))
                # Distinguish export line from any CMS native source_row carried in the record.
                keys = ['export_line']
                rows = (dict(json.loads(line), export_line=index)
                        for index, line in enumerate(stream, 1))
            else:
                keys = ['source_index']
                rows = (dict(row, source_index=index) for index, row in enumerate(read_json(path)))

        target = sql.Identifier(SCHEMA, name)
        self.conn.execute(sql.SQL('''CREATE TABLE {} (
            ordinal bigint PRIMARY KEY, data jsonb NOT NULL, names text[] NOT NULL, npis jsonb NOT NULL
        )''').format(target))
        source_hash = hashlib.sha256()
        count = 0
        with self.conn.cursor() as cur, cur.copy(sql.SQL('COPY {} FROM STDIN').format(target)) as copy:
            for count, row in enumerate(rows, 1):
                source_hash.update(canonical([count, row]) + b'\n')
                npis = json.loads(row['npi_json']) if npi_array else []
                copy.write_row((count, Jsonb(row), names_for(row, name_path), Jsonb(npis)))
        for field in filters.split():
            if field == 'npi' and npi_array:
                self.conn.execute(sql.SQL('CREATE INDEX ON {} USING gin (npis)').format(target))
            else:
                self.conn.execute(sql.SQL('CREATE INDEX ON {} ((data ->> {}))').format(target, sql.Literal(field)))
        self.conn.execute(sql.SQL('ANALYZE {}').format(target))

        target_hash = hashlib.sha256()
        verified = 0
        with self.conn.cursor('verify_' + name) as cur:
            cur.execute(sql.SQL('SELECT ordinal,data FROM {} ORDER BY ordinal').format(target))
            for verified, row in enumerate(cur, 1):
                target_hash.update(canonical(row) + b'\n')
        if count != verified or source_hash.digest() != target_hash.digest():
            raise ValueError(f'Full-row parity failed: {name}')
        full_count = count if full_count is None else full_count
        self.datasets[name] = {'layer': layer, 'capability': capability, 'artifact': str(path),
                               'artifact_sha256': sha, 'component_manifest': parent,
                               'source_table': table, 'locator_fields': keys, 'filters': filters.split(),
                               'name_search': bool(name_path), 'npi_array': npi_array,
                               'rows': count, 'retained_source_table_rows': full_count,
                               'selection': where, 'columns': columns,
                               'row_stream_sha256': source_hash.hexdigest()}
        print(f'{name}: {count:,} / {full_count:,}', flush=True)


def populate(builder):
    formulary = L05 / 'build-r3/inventory.sqlite3'
    criteria = L05 / 'closeout-r1/build-r5'
    drugs = [
        ('drug_plans', 'plans', 'offering_id formulary_id', None),
        ('drug_products', 'drug_identities', 'rxcui', 'payload.name'),
        ('formulary_rows', 'drug_rows', 'formulary_id rxcui ndc contract_id table_name ordinal', None),
        ('formulary_conditions', 'condition_gaps', 'table_name ordinal', None),
        ('drug_benefit_context', 'benefit_context', 'offering_id', None),
    ]
    for name, table, filters, name_path in drugs:
        builder.add(name, 'L05', 'drug_formulary', formulary, table, filters=filters, name_path=name_path)
    for name, file, filters in [
        ('criteria_plan_status', 'plans.json', 'offering_id'),
        ('criteria_documents', 'documents.json', 'id'),
        ('criteria_links', 'condition-reference-links.jsonl.gz', 'rxcui source_row table'),
        ('criteria_sections', 'criteria-sections.jsonl.gz', 'section_id document_id'),
        ('quantity_units', 'quantity-units.jsonl.gz', 'rxcui source_row table'),
    ]:
        builder.add(name, 'L05', 'drug_formulary', criteria / file,
                    'jsonl' if file.endswith('.gz') else 'json_array', filters=filters)

    for name, file, table, filters in [
        ('average_prices', 'build-r1', 'prices', 'offering_id ndc days_supply'),
        ('average_price_pairs', 'build-r1', 'formulary_pairs', 'offering_id ndc'),
        ('cost_schedules', 'build-cost-r1', 'schedules', 'offering_id table_name'),
    ]:
        builder.add(name, 'L06', 'drug_cost_inputs', L06 / file / 'inventory.sqlite3', table, filters=filters)

    outlets = L07 / 'location-build-r4/inventory.sqlite3'
    network = L07 / 'build-r1/inventory.sqlite3'
    builder.add('pharmacy_locations', 'L07', 'pharmacy', outlets, 'locations',
                filters='npi network_zip county_fips identity_status scope_group')
    _, _, db = builder.source(network, 'L07')
    db.execute('ATTACH DATABASE ? AS geography', ((ROOT / outlets).as_uri() + '?mode=ro&immutable=1',))
    builder.add('pharmacy_network', 'L07', 'pharmacy', network, 'network',
                filters='offering_id pharmacy_npi PHARMACY_ZIPCODE retail_status mail_status',
                where=f"""PHARMACY_MAIL='Y' OR PHARMACY_ZIPCODE='XXXXX'
                    OR substr(PHARMACY_ZIPCODE,1,3) {REGIONAL_ZIP}
                    OR (pharmacy_npi, PHARMACY_ZIPCODE) IN
                       (SELECT npi,network_zip FROM geography.locations WHERE county_fips IN ({REGIONAL_COUNTIES}))""")

    carrier = L08 / 'wellcare-r5/providers.sqlite3'
    for name, table, filters, name_path in [
        ('provider_sources', 'sources', 'id sha256', None),
        ('provider_entities', 'entities', 'entity_key npi type observation_id', 'name_json'),
        ('provider_sites', 'locations', 'entity_key observation_id', 'name_json'),
        ('provider_roles', 'roles', 'entity_key provider_key organization_key observation_id', None),
        ('provider_observation_locators', 'observations', 'id entity_key source_id', None),
        ('provider_source_conflicts', 'source_conflicts', 'id kind', None),
    ]:
        columns = 'id,entity_key,type,source_id,pointer,modeled_leaf_count' if table == 'observations' else '*'
        builder.add(name, 'L08', 'provider_identity', carrier, table, filters=filters,
                    name_path=name_path, columns=columns, npi_array=table == 'entities')
    for name, table, filters, name_path in [
        ('ma_offerings', 'offerings', 'id parent category', 'name'),
        ('ma_plan_networks', 'plan_networks', 'offering_id network_key state', None),
        ('ma_role_networks', 'relationships', 'offering_id provider_key location_key role_key state', None),
        ('ma_hospitals', 'hospitals', 'id county source_id', 'name'),
        ('ma_hospital_plan', 'hospital_plan_matrix', 'hospital_id offering_id state', None),
        ('ma_documents', 'directory_documents', 'sha256 year', 'label'),
        ('ma_plan_documents', 'plan_documents', 'offering_id document_sha256', None),
        ('ma_pdf_listings', 'pdf_records', 'id family document_sha256 identifier', 'name_raw'),
        ('ma_pdf_site_resolutions', 'pdf_site_resolution', 'record_id state', None),
        ('ma_humana_listings', 'r4_humana_entries', 'id document_sha256 name_kind', 'fields_json.name_raw'),
        ('ma_humana_address_links', 'r4_address_entry_links', 'address_id entry_id', None),
        ('ma_humana_addresses', 'r3_address_observations', 'id document_sha256', None),
        ('ma_humana_query', 'r4_public_observations', 'id network_raw source_path', 'fields_json.fields.name_raw'),
        ('ma_wellcare_listings', 'r5_wellcare_records', 'id county_raw publisher_provider_id document_sha256', 'fields_json.name_raw'),
        ('ma_wellcare_plan_documents', 'r5_plan_directory_bindings', 'offering_id document_sha256', None),
        ('ma_aetna_query', 'aetna_query_observations', 'id offering_id category', 'fields_json.fields.name_raw'),
        ('ma_aetna_additive_query', 'r3_public_observations', 'id offering_id family', 'fields_json.fields.name_raw'),
    ]:
        builder.add(name, 'L08', 'provider_network', carrier, table, filters=filters, name_path=name_path)

    federal = L08 / 'original-medicare-r6/original-medicare.sqlite3'
    _, _, db = builder.source(federal, 'L08')
    # TEMP selectors do not write to the immutable source. Site-less rows for
    # these exact NPIs/enrollments stay associated but retain their native grain.
    db.execute(f"""CREATE TEMP TABLE local_identifiers AS
        SELECT DISTINCT npi,enrollment_id FROM observations WHERE state_raw='FL'
        AND substr(postal_raw,1,3) {REGIONAL_ZIP}""")
    db.execute("CREATE INDEX temp.local_npi ON local_identifiers(npi)")
    db.execute("CREATE INDEX temp.local_enrollment ON local_identifiers(enrollment_id)")
    npi = "npi IN (SELECT npi FROM local_identifiers WHERE npi<>'')"
    enrollment = "enrollment_id IN (SELECT enrollment_id FROM local_identifiers WHERE enrollment_id<>'')"
    for name, table, filters, where, name_path in [
        ('federal_sources', 'sources', 'id', '1', None),
        ('federal_provider_rows', 'observations', 'source_id npi enrollment_id city_raw postal_raw',
         f"source_id='optout' OR ({npi}) OR ({enrollment})", 'federal'),
        ('federal_assignments', 'assignments', 'npi enrollment_id', f'({npi}) OR ({enrollment})', None),
        ('federal_enrollments', 'enrollment_status', 'npi enrollment_id', f'({npi}) OR ({enrollment})', None),
        ('federal_optout', 'optout_periods', 'npi state', '1', None),
        ('federal_reassignments', 'reassignments', 'reassigning_id receiving_id',
         "reassigning_id IN (SELECT enrollment_id FROM local_identifiers WHERE enrollment_id<>'')", None),
    ]:
        builder.add(name, 'L08', 'original_medicare', federal, table, filters=filters, where=where,
                    name_path=name_path)
    hospitals = L08 / 'hospital-reference-r7/hospitals.sqlite3'
    builder.add('federal_hospitals', 'L08', 'original_medicare', hospitals, 'hospitals',
                filters='facility_id county_raw city_raw state_raw postal_raw', name_path='name_raw')
    builder.add('federal_hospital_metadata', 'L08', 'original_medicare', hospitals, 'metadata', filters='key')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--database', default=DATABASE)
    args = parser.parse_args()
    # New revisions must be explicit and never use an existing source/demo name.
    if args.database != DATABASE:
        parser.error('This r1 builder only creates ' + DATABASE)
    source_dsn = os.environ['DAYLIGHT_FOUNDATION_SOURCE_DSN']
    controls = source_controls(source_dsn)
    target = read_json(Path(PACKET) / 'TARGET.json')
    if (controls['database'] != RESEARCH_DATABASE
            or str(controls['database_oid']) != str(target['database_oid'])
            or controls['cluster_system_identifier'] != target['cluster_system_identifier']
            or any(row['state'] != 'permitted' for row in controls['source_access_states'])):
        raise ValueError('Authoritative source target or STOP state mismatch')
    composition = read_json(COMPOSITION_PATH)
    layers = {entry['layer_id']: {key: value for key, value in entry.items() if key != 'seeds'}
              for entry in composition['layers'] if entry['layer_id'] in {'L05', 'L06', 'L07', 'L08'}}
    hashes = {str(path): file_hash(ROOT / path) for path in CONTROL_PATHS}
    for layer in layers.values():
        for component in layer['components']:
            path = component['control_path']
            if file_hash(ROOT / path) != component['control_sha256']:
                raise ValueError(f'Selected source manifest mismatch: {path}')
            hashes[path] = component['control_sha256']

    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    # PostgreSQL CREATE DATABASE is nontransactional. A failed build leaves no
    # binding.json and the read interface cannot open the incomplete revision.
    admin_dsn = make_conninfo(source_dsn, dbname='postgres')
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(sql.Identifier(args.database)))
        conn.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC').format(sql.Identifier(args.database)))
        conn.execute(sql.SQL('ALTER DATABASE {} SET default_transaction_read_only=on').format(sql.Identifier(args.database)))

    package_dsn = make_conninfo(source_dsn, dbname=args.database)
    with ExitStack() as stack, psycopg.connect(package_dsn, options='-c default_transaction_read_only=off') as conn:
        builder = Builder(conn, stack, layers)
        populate(builder)
        if (source_controls(source_dsn) != controls or
                any(file_hash(ROOT / path) != sha for path, sha in hashes.items())):
            raise ValueError('Source controls changed during build')
        policy = read_json(POLICY_PATH)
        policy['inherited_stops']['registry_domains'] = read_json(policy['inherited_stops']['registry'])
        manifest = {
            'schema': VERSION, 'database': args.database, 'policy': policy,
            'created_at_utc': datetime.now(timezone.utc).isoformat(),
            'sources': layers, 'controls': hashes, 'source_control_snapshot': controls,
            'datasets': builder.datasets,
        }
        manifest['binding_id'] = digest(manifest)
        conn.execute('CREATE TABLE dl_pilot_foundation.binding (binding_id text PRIMARY KEY)')
        conn.execute('INSERT INTO dl_pilot_foundation.binding VALUES (%s)', (manifest['binding_id'],))
    with psycopg.connect(package_dsn) as conn:
        size, version = conn.execute('SELECT pg_database_size(current_database()), version()').fetchone()
    write_json(args.output / 'binding.json', manifest)
    write_json(args.output / 'parity.json', {'binding_id': manifest['binding_id'], 'database_bytes': size,
               'postgresql': version, 'datasets': builder.datasets,
               'checked_rows': sum(item['rows'] for item in builder.datasets.values()),
               'source_control_snapshot_unchanged': True})
    print(f'{args.database}: {size:,} bytes', flush=True)


if __name__ == '__main__':
    main()
