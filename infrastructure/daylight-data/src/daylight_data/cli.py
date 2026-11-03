"""Private operator commands. No command here grants source/output acceptance."""
import argparse
import json
import os
from pathlib import Path
import sys
from daylight_data import __version__
from daylight_data.adapters import TYPED_LAYERS, iter_layer_records, iter_layer_projections
from daylight_data.adapters.common import digest_json
from daylight_data.database import connect, migrate
from daylight_data.ingestion.jobs import enqueue, claim
from daylight_data.ingestion.loader import import_records, insert_projections
from daylight_data.storage import FileArchive


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',action='version',version=__version__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('migrate')
    sub.add_parser('health')
    ingest=sub.add_parser('import-layer')
    ingest.add_argument('--layer',choices=TYPED_LAYERS,required=True)
    ingest.add_argument('--repository',type=Path,required=True)
    ingest.add_argument('--archive',type=Path,required=True)
    ingest.add_argument('--batch-size',type=int,default=10000)
    ingest.add_argument('--projections',action='store_true')
    args=parser.parse_args(argv)
    dsn=os.environ['DAYLIGHT_DATA_DATABASE_URL']
    with connect(dsn) as connection:
        if args.command=='migrate':
            migrate(connection)
            print(json.dumps({'migrations':'verified_and_applied'}))
        elif args.command=='health':
            print(json.dumps({'postgres_major':connection.info.server_version//10000,
                              'migration_count':connection.execute('SELECT count(*) FROM dl_migrations.applied').fetchone()[0]}))
        elif args.command=='import-layer':
            # Ingestion may not inherit a migration-owner's acceptance privileges.
            connection.execute('SET ROLE daylight_writer')
            # A source-wide deterministic identity requires every selected source file hash.
            # Only these reviewed local adapters are callable, never a browser path/URL.
            from daylight_data.adapters import account
            controls=account(iter_layer_records(args.repository,args.layer))
            key=digest_json([args.layer,controls['stream_digest'],controls['derivation_ids'],controls['adapter_code_hashes'],'source-transport-r2'])
            job_id=enqueue(connection,key,{'layer_id':args.layer,'stream_digest':controls['stream_digest']},source_id='sealed-local:'+args.layer)
            state=connection.execute('SELECT state FROM dl_control.job WHERE job_id=%s',(job_id,)).fetchone()[0]
            if state=='complete':
                receipt={'job_id':job_id,'status':'identical_import_reused',
                         'input_rows':controls['source_rows'],'stream_sha256':controls['stream_digest']}
            else:
                # Claim the requested job only. Do not accidentally consume a different job.
                lease=claim(connection,'cli-local',lease_seconds=600,job_id=job_id)
                if lease is None or lease.job_id!=job_id:
                    raise RuntimeError('Job is stopped, held or owned by another worker')
                receipt=import_records(connection,FileArchive(args.archive),args.repository,lease,
                    iter_layer_records(args.repository,args.layer),args.batch_size)
                receipt.update(job_id=job_id,status='source_transport_complete')
            if args.projections:
                receipt['projections']=insert_projections(connection,iter_layer_projections(args.repository,args.layer))
            receipt['new_acceptance']=False
            print(json.dumps(receipt,sort_keys=True))


if __name__=='__main__':
    main()
