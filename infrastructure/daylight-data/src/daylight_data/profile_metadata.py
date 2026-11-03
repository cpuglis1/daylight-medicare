"""Existing question metadata, not a customer-profile persistence store."""
import hashlib
import json
from pathlib import Path
from psycopg.types.json import Jsonb
from daylight_data.ingestion.loader import insert_exact


def import_contract(connection, path: Path, repository_root: Path):
    content=path.read_bytes()
    payload=json.loads(content)
    expected={'question_definitions':41,'field_definitions':78,'representation_gaps':14,
              'documented_child_aliases':3,'clarification_variants':11}
    for key,count in expected.items():
        if payload['counts'][key]!=count:
            raise ValueError('Profile metadata denominator changed')
    for key,count in [('questions',41),('fields',78),('representation_gaps',14),('child_aliases',3),('clarification_variants',11)]:
        if len(payload[key])!=count:
            raise ValueError('Profile metadata population mismatch')
    if payload['customer_rows_included'] or payload['mandatory_interview_added'] or payload['personal_recommendations_enabled']:
        raise ValueError('Profile metadata attempts to expand its authority')
    for binding in payload['source_bindings'].values():
        source=repository_root/binding['path']
        if not source.resolve().is_relative_to(repository_root.resolve()):
            raise ValueError('Metadata binding escapes repository')
        if hashlib.sha256(source.read_bytes()).hexdigest()!=binding['sha256']:
            raise ValueError('Metadata source changed; new contract revision required')
    digest=hashlib.sha256(content).hexdigest()
    with connection.transaction():
        connection.execute('SET LOCAL ROLE daylight_writer')
        insert_exact(connection,'dl_control.profile_contract',
                     ['contract_sha256','question_count','field_count','gap_count','contract_payload'],
                     [digest,41,78,14,Jsonb(payload)],['contract_sha256'])
    return {'contract_sha256':digest,'questions':41,'fields':78,'gaps':14,
            'child_aliases':3,'clarification_variants':11,'customer_rows':0,'new_acceptance':False}
