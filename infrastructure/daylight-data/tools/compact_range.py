"""Exact checkpoint-range reads, expanding each cold payload block once.

For full verification only. The bounded point-read compatibility views remain
unchanged. Partial/non-checkpoint ranges are rejected rather than omit a page.
"""
import hashlib
from psycopg import sql

RAW = sql.SQL('''WITH expanded AS MATERIALIZED (
 SELECT p.source_set_id,p.page_first_ordinal,(x.position-1)::smallint AS payload_position,x.raw_payload
 FROM dl_compact.source_page p
 CROSS JOIN LATERAL jsonb_array_elements(p.payloads) WITH ORDINALITY AS x(raw_payload,position)
 WHERE p.source_set_id=%s AND p.page_first_ordinal BETWEEN %s AND %s)
 SELECT s.derivation_id,s.source_table,r.source_row_ordinal,encode(r.record_hash,'hex') AS record_id,
 r.source_row_key,b.value AS ordinal_basis,encode(r.raw_hash,'hex') AS raw_sha256,e.raw_payload,d.value AS disposition
 FROM dl_compact.source_record r JOIN dl_compact.source_set s USING(source_set_id)
 JOIN expanded e USING(source_set_id,page_first_ordinal,payload_position)
 JOIN dl_compact.symbol b ON b.symbol_id=r.ordinal_basis_id
 JOIN dl_compact.symbol d ON d.symbol_id=r.disposition_id
 WHERE r.source_set_id=%s AND r.source_row_ordinal BETWEEN %s AND %s
 ORDER BY r.source_row_ordinal''')


def raw_hash(db,params):
    row=db.execute('''SELECT c.source_set_id FROM dl_compact.load_checkpoint c JOIN dl_compact.source_set s USING(source_set_id)
        WHERE s.derivation_id=%s AND s.source_table=%s AND c.first_ordinal=%s AND c.last_ordinal=%s''',params).fetchone()
    if not row:raise ValueError('Exact committed checkpoint required for packed range read')
    h=hashlib.sha256();size=0
    bounded=(row['source_set_id'],params[2],params[3])
    # Statistics on a materialized JSON expansion can underestimate a document
    # range and repeatedly rescan a spilled payload set. Use equijoins for this
    # bulk-only reader; point lookups keep their normal indexed nested loops.
    with db.transaction():
        db.execute('SET LOCAL enable_nestloop=off')
        with db.cursor().copy(sql.SQL('COPY ({}) TO STDOUT (FORMAT BINARY)').format(RAW),bounded+bounded) as incoming:
            for block in incoming:h.update(block);size+=len(block)
    return h.hexdigest(),size
