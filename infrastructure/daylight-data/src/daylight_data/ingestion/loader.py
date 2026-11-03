"""COPY batches and cursor commit together. A parser change is a new derivation."""
from __future__ import annotations
from collections import Counter
from decimal import Decimal
import hashlib
from pathlib import Path
from psycopg.types.json import Jsonb
from psycopg import sql

from daylight_data.adapters.common import canonical_json, digest_json, ADAPTER_VERSION
from daylight_data.ingestion.jobs import require_lease, heartbeat


def insert_exact(connection, table, columns, values, identity):
    """Identical replay is allowed; a changed immutable projection is an error."""
    schema, name = table.split(".")
    relation = sql.Identifier(schema, name)
    names = sql.SQL(',').join(map(sql.Identifier,columns))
    placeholders = sql.SQL(',').join(sql.Placeholder() for _ in columns)
    connection.execute(sql.SQL("INSERT INTO {} ({}) VALUES({}) ON CONFLICT DO NOTHING").format(relation,names,placeholders),values)
    predicates = sql.SQL(' AND ').join(sql.SQL('{}=%s').format(sql.Identifier(key)) for key in identity)
    key_values = [values[columns.index(key)] for key in identity]
    row = connection.execute(sql.SQL("SELECT ROW({}) IS NOT DISTINCT FROM ROW({}) FROM {} WHERE {}").format(
        names,placeholders,relation,predicates),list(values)+key_values).fetchone()
    if row is None or not row[0]:
        raise ValueError("Immutable metadata/projection differs; create a new derivation")


def register_source(connection, archive, repository_root: Path, record):
    path = repository_root / record.source_path
    if not path.resolve().is_relative_to(repository_root.resolve()):
        raise ValueError("Source escapes approved repository")
    if hasattr(archive, 'put_file'):
        archived = archive.put_file(path, expected_sha256=record.source_sha256)
    else:
        with path.open("rb") as handle:
            archived = archive.put(handle, expected_sha256=record.source_sha256)
    with connection.transaction():
        insert_exact(connection,"dl_control.artifact",['sha256','byte_length','object_key'],
                     [archived.sha256,archived.byte_length,archived.object_key],['sha256'])
        insert_exact(connection,"dl_control.source_snapshot",['snapshot_id','layer_id','artifact_sha256','original_path','benefit_year'],
                     [record.snapshot_id,record.layer_id,record.source_sha256,record.source_path,2026],['snapshot_id'])
        insert_exact(connection,"dl_control.derivation",['derivation_id','snapshot_id','adapter_version','configuration_hash','adapter_code_sha256'],
                     [record.derivation_id,record.snapshot_id,ADAPTER_VERSION,
                      digest_json(["2026-source-preserving",record.source_table,record.adapter_code_sha256]),record.adapter_code_sha256],['derivation_id'])


def copy_batch(connection, lease, records):
    if not records:
        return
    if len(records)>50000:
        raise ValueError("Batch exceeds configured bound")
    groups = {}
    with connection.transaction():
        require_lease(connection,lease)
        connection.execute("""CREATE TEMP TABLE copy_batch (LIKE dl_evidence.source_record INCLUDING DEFAULTS) ON COMMIT DROP""")
        with connection.cursor().copy("""COPY copy_batch(derivation_id,source_table,source_row_ordinal,
            record_id,source_row_key,ordinal_basis,raw_sha256,raw_payload,disposition) FROM STDIN""") as copy:
            for row in records:
                copy.write_row((row.derivation_id,row.source_table,row.source_row_ordinal,row.record_id,
                    row.source_row_key,row.ordinal_basis,digest_json(row.raw),Jsonb(row.raw,dumps=canonical_json),row.disposition))
                groups.setdefault((row.derivation_id,row.source_table),[]).append(row.source_row_ordinal)
        bad = connection.execute("""SELECT 1 FROM copy_batch b JOIN dl_evidence.source_record r USING(derivation_id,source_table,source_row_ordinal)
            WHERE (b.record_id,b.source_row_key,b.ordinal_basis,b.raw_sha256,b.raw_payload,b.disposition)
              IS DISTINCT FROM (r.record_id,r.source_row_key,r.ordinal_basis,r.raw_sha256,r.raw_payload,r.disposition) LIMIT 1""").fetchone()
        if bad:
            raise ValueError("Existing derivation differs; create a new derivation")
        connection.execute("INSERT INTO dl_evidence.source_record SELECT * FROM copy_batch ON CONFLICT DO NOTHING")
        for (derivation,table),ordinals in groups.items():
            previous = connection.execute("SELECT last_ordinal FROM dl_control.checkpoint WHERE job_id=%s AND derivation_id=%s AND source_table=%s",
                (lease.job_id,derivation,table)).fetchone()
            prior = previous[0] if previous else 0
            fresh = sorted(item for item in ordinals if item>prior)
            if fresh and fresh != list(range(prior+1, fresh[-1]+1)):
                raise ValueError("Non-contiguous source cursor")
            last = max(prior,max(ordinals))
            connection.execute("""INSERT INTO dl_control.checkpoint(job_id,derivation_id,source_table,last_ordinal,retained_rows,fence)
                VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(job_id,derivation_id,source_table) DO UPDATE
                SET last_ordinal=EXCLUDED.last_ordinal,retained_rows=EXCLUDED.retained_rows,fence=EXCLUDED.fence""",
                (lease.job_id,derivation,table,last,last,lease.fence))
        require_lease(connection,lease)


def import_records(connection, archive, repository_root: Path, lease, records, batch_size: int = 10000):
    if not 1<=batch_size<=50000:
        raise ValueError("Invalid batch size")
    batch, registered, controls = [],set(),Counter()
    digest,total,quarantined = hashlib.sha256(),0,0
    for row in records:
        if row.derivation_id not in registered:
            register_source(connection,archive,repository_root,row)
            registered.add(row.derivation_id)
        total += 1
        quarantined += row.disposition.startswith("quarantined")
        controls[row.source_path+"#"+row.source_table] += 1
        digest.update(canonical_json([row.record_id,row.raw]).encode()+b"\n")
        batch.append(row)
        if len(batch)>=batch_size:
            copy_batch(connection,lease,batch)
            heartbeat(connection,lease)
            batch=[]
    copy_batch(connection,lease,batch)
    receipt={"input_rows":total,"retained_rows":total,"quarantined_rows":quarantined,
             "stream_sha256":digest.hexdigest(),"controls":dict(controls),"unexplained_loss":0}
    with connection.transaction():
        require_lease(connection,lease)
        actual=connection.execute("SELECT coalesce(sum(retained_rows),0) FROM dl_control.checkpoint WHERE job_id=%s",(lease.job_id,)).fetchone()[0]
        if actual!=total:
            raise ValueError("Checkpoint/source population mismatch")
        connection.execute("""INSERT INTO dl_control.ingest_receipt(job_id,input_rows,retained_rows,quarantined_rows,stream_sha256,controls)
             VALUES(%s,%s,%s,%s,%s,%s)""",(lease.job_id,total,total,quarantined,digest.hexdigest(),Jsonb(dict(controls))))
        connection.execute("UPDATE dl_control.job SET state='complete',finished_at=clock_timestamp(),lease_until=NULL WHERE job_id=%s",(lease.job_id,))
    return receipt


PROJECTION_COLUMNS=['derivation_id','entity_type','entity_id','source_table','source_row_ordinal',
    'offering_id','county_fips','benefit_year','amount','amount_unit','amount_basis','amount_period','raw_value',
    'value_state','evidence_state','semantic_review_state','source_use_state','freshness_state','output_acceptance_state','conditions','fields']
OFFERING_COLUMNS=['derivation_id','offering_id','benefit_year','contract_id','plan_id','segment_id',
    'plan_name','category','source_table','source_row_ordinal','output_acceptance_state']


def _copy_projections(connection,batch):
    with connection.transaction():
        connection.execute('CREATE TEMP TABLE projection_batch (LIKE dl_evidence.observation INCLUDING DEFAULTS) ON COMMIT DROP')
        connection.execute('CREATE TEMP TABLE offering_batch (LIKE dl_evidence.offering INCLUDING DEFAULTS) ON COMMIT DROP')
        offering_rows=[]
        names=','.join(PROJECTION_COLUMNS)
        with connection.cursor().copy(f'COPY projection_batch({names}) FROM STDIN') as copy:
            for item in batch:
                source,fields=item.source,dict(item.fields)
                if item.entity_type=='offering':
                    offering_rows.append((source.derivation_id,fields['offering_id'],fields['benefit_year'],fields['contract_id'],fields['plan_id'],fields['segment_id'],
                        fields.get('plan_name',fields.get('name')),fields.get('category'),source.source_table,source.source_row_ordinal,item.output_acceptance_state))
                raw_value=fields.get('raw_value',fields.get('source_value'))
                copy.write_row((source.derivation_id,item.entity_type,item.entity_id,source.source_table,source.source_row_ordinal,
                    fields.get('offering_id'),fields.get('county_fips'),fields.get('benefit_year'),
                    fields.get('amount_decimal',fields.get('amount') if isinstance(fields.get('amount'),(Decimal,int)) and not isinstance(fields.get('amount'),bool) else None),
                    fields.get('unit'),fields.get('basis',fields.get('cost_basis')),fields.get('period'),str(raw_value) if raw_value is not None else None,
                    item.value_state,item.evidence_state,item.semantic_review_state,item.source_use_state,item.freshness_state,item.output_acceptance_state,
                    Jsonb(item.conditions,dumps=canonical_json),Jsonb(fields,dumps=canonical_json)))
        with connection.cursor().copy(f"COPY offering_batch({','.join(OFFERING_COLUMNS)}) FROM STDIN") as copy:
            for row in offering_rows:
                copy.write_row(row)
        for staging,target,keys in [('projection_batch','observation','derivation_id,entity_type,entity_id'),
                                    ('offering_batch','offering','derivation_id,offering_id')]:
            # All names are fixed source constants, never request/source-provided SQL.
            duplicate=connection.execute(f'SELECT 1 FROM {staging} GROUP BY {keys} HAVING count(*)>1 LIMIT 1').fetchone()
            bad=connection.execute(f'SELECT 1 FROM {staging} b JOIN dl_evidence.{target} r USING({keys}) WHERE b IS DISTINCT FROM r LIMIT 1').fetchone()
            if duplicate or bad:
                raise ValueError('Immutable projection differs or source identity duplicates; create a new derivation')
            connection.execute(f'INSERT INTO dl_evidence.{target} SELECT * FROM {staging} ON CONFLICT DO NOTHING')


def insert_projections(connection, projections, batch_size=10000):
    """Bounded COPY into relational material fields, with exact immutable replay."""
    if not 1<=batch_size<=50000:
        raise ValueError('Invalid projection batch size')
    counts,batch=Counter(),[]
    for item in projections:
        counts[item.entity_type]+=1
        batch.append(item)
        if len(batch)>=batch_size:
            _copy_projections(connection,batch)
            batch=[]
    if batch:
        _copy_projections(connection,batch)
    return dict(counts)
