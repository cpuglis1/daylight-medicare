-- Additive r3 read adapter over unchanged r2 data. Dictionary/page primary keys
-- and validated non-null FKs make these scalar lookups equivalent to the old
-- inner joins. Keep payload expansion outside the large outer join graph.
CREATE OR REPLACE VIEW dl_evidence.source_record AS
 SELECT s.derivation_id,s.source_table,r.source_row_ordinal,
        encode(r.record_hash,'hex') AS record_id,r.source_row_key,
        (SELECT b.value FROM dl_compact.symbol b WHERE b.symbol_id=r.ordinal_basis_id) AS ordinal_basis,
        encode(r.raw_hash,'hex') AS raw_sha256,
        (SELECT p.payloads->r.payload_position::integer FROM dl_compact.source_page p
         WHERE p.source_set_id=r.source_set_id AND p.page_first_ordinal=r.page_first_ordinal) AS raw_payload,
        (SELECT d.value FROM dl_compact.symbol d WHERE d.symbol_id=r.disposition_id) AS disposition
 FROM dl_compact.source_record r JOIN dl_compact.source_set s USING(source_set_id);
