"""Capture bounded initial import evidence; no customer-store access or network."""
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
from datetime import datetime,timezone

from psycopg.types.json import Jsonb
from daylight_data.adapters import iter_layer_records,account
from daylight_data.adapters.common import canonical_json,sha256_file
from daylight_data.database import connect
from daylight_data.profile_metadata import import_contract
from daylight_data.storage import FileArchive

ROOT=Path(__file__).resolve().parents[3]
PACKAGE=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'docs/data/infrastructure-execution-2026-10-29'


def main():
    results={'schema':'daylight-infrastructure-preflight/1','observed_at':datetime.now(timezone.utc).isoformat(),
             'benefit_year':2026,'target_date':'2026-11-05','python':platform.python_version(),
             'database_environment':'isolated_project_local_private_unix_socket',
             'cloud_deployment':False,'new_acceptance':False,'layers':{},'remaining_layers':['L03','L05','L06','L07','L08','L10','L11','L12','L13','L14','L15']}
    with connect(os.environ['DAYLIGHT_DATA_DATABASE_URL']) as connection:
        results['postgres_version']=connection.execute('SELECT version()').fetchone()[0]
        results['migrations']=[{'name':row[0],'sha256':row[1]} for row in connection.execute('SELECT name,sha256 FROM dl_migrations.applied ORDER BY name')]
        results['profile_metadata']=import_contract(connection,PACKAGE/'config/profile-contract.2026.json',ROOT)
        for layer in ['L01','L02','L04','L09']:
            controls=account(iter_layer_records(ROOT,layer))
            row=connection.execute("""SELECT j.job_id,r.input_rows,r.retained_rows,r.quarantined_rows,r.stream_sha256,r.controls,
                 extract(epoch from j.finished_at-j.created_at) FROM dl_control.job j JOIN dl_control.ingest_receipt r USING(job_id)
                 WHERE j.payload->>'layer_id'=%s AND j.state='complete' ORDER BY j.job_id DESC LIMIT 1""",(layer,)).fetchone()
            if not row:
                raise RuntimeError('Layer has no complete actual import')
            if row[1]!=controls['source_rows'] or row[4]!=controls['stream_digest']:
                raise RuntimeError('Source/import population or digest mismatch')
            table_checks=[]
            for derivation in controls['derivation_ids']:
                loaded=connection.execute('SELECT source_table,count(*) FROM dl_evidence.source_record WHERE derivation_id=%s GROUP BY source_table',(derivation,)).fetchall()
                if not loaded:
                    raise RuntimeError('Current exact adapter code is not loaded')
                for table,count in loaded:
                    checkpoint=connection.execute('SELECT retained_rows FROM dl_control.checkpoint WHERE job_id=%s AND derivation_id=%s AND source_table=%s',
                        (row[0],derivation,table)).fetchone()
                    if checkpoint is None or checkpoint[0]!=count:
                        raise RuntimeError('Actual table/checkpoint population mismatch')
                    table_checks.append({'derivation_id':derivation,'source_table':table,'actual_retained_rows':count})
            projections=dict(connection.execute("""SELECT entity_type,count(*) FROM dl_evidence.observation
                    WHERE derivation_id=ANY(%s) GROUP BY entity_type ORDER BY entity_type""",(controls['derivation_ids'],)))
            results['layers'][layer]={'job_id':row[0],'source_rows':row[1],'retained_rows':row[2],'quarantined_rows_retained':row[3],
                'stream_sha256':row[4],'source_table_controls':row[5],'actual_table_checks':table_checks,
                'adapter_code_hashes':controls['adapter_code_hashes'],'derivation_ids':controls['derivation_ids'],
                'source_import_seconds':str(row[6]),'projections':projections,'unexplained_source_loss':0,
                'original_authority_replay':'pending','all_material_domain_fields_typed':'pending',
                'consumer_output':'held','new_acceptance':False}
        # Check useful structured fields, retaining exact source grain and denominator.
        l04=results['layers']['L04']['derivation_ids']; l09=results['layers']['L09']['derivation_ids']; l02=results['layers']['L02']['derivation_ids']
        results['query_controls']={
            'pdp_offerings':connection.execute('SELECT count(*) FROM dl_evidence.offering WHERE derivation_id=ANY(%s)',(l04,)).fetchone()[0],
            'pdp_counties':connection.execute("SELECT count(DISTINCT county_fips) FROM dl_evidence.observation WHERE derivation_id=ANY(%s) AND entity_type='pdp_region_county'",(l04,)).fetchone()[0],
            'quality_observations':connection.execute("SELECT count(*) FROM dl_evidence.observation WHERE derivation_id=ANY(%s) AND entity_type='quality_observation'",(l09,)).fetchone()[0],
            'l02_retained_national_offering_identities':connection.execute('SELECT count(*) FROM dl_evidence.offering WHERE derivation_id=ANY(%s)',(l02,)).fetchone()[0]}
        if results['query_controls']!={'pdp_offerings':10,'pdp_counties':67,'quality_observations':2448,'l02_retained_national_offering_identities':5962}:
            raise RuntimeError('Structured query control mismatch: '+json.dumps(results['query_controls'],sort_keys=True))
        archive=FileArchive(PACKAGE/'.state/archive')
        objects=connection.execute('SELECT sha256,byte_length FROM dl_control.artifact ORDER BY sha256').fetchall()
        for digest,size in objects:
            if archive.verify(digest)!=size:
                raise RuntimeError('Archived bytes differ')
        results['archive']={'verified_objects':len(objects),'verified_bytes':sum(row[1] for row in objects),'adapter':'private_filesystem',
                            's3_actual_target_round_trip':'pending'}
        results['physical_rows_including_immutable_historical_derivations']=connection.execute('SELECT count(*) FROM dl_evidence.source_record').fetchone()[0]
    results['selected_source_rows']=sum(layer['source_rows'] for layer in results['layers'].values())
    results['implementation_files']={str(path.relative_to(ROOT)):sha256_file(path) for path in sorted(PACKAGE.rglob('*'))
       if path.is_file() and not any(part.startswith('.') or part=='__pycache__' for part in path.relative_to(PACKAGE).parts)}
    OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT/'platform-imports.json').write_text(json.dumps(results,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:results[k] for k in ['selected_source_rows','query_controls','archive','physical_rows_including_immutable_historical_derivations']},indent=2))


if __name__=='__main__':
    main()
