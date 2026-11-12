"""Actual PostgreSQL tests using only fresh fictional databases, never real rows."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid

import psycopg
from psycopg import sql

PACKAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PACKAGE/'src'))
from daylight_data.database import migrate
from psycopg.types.json import Jsonb

SPEC=importlib.util.spec_from_file_location('compact_database',PACKAGE/'tools/compact_database.py')
c=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(c)


@unittest.skipUnless(os.environ.get('DAYLIGHT_COMPACT_TESTS') == '1', 'Explicit local fictional PostgreSQL fixture run required')
class CompactPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.names=['daylight_compact_fixture_'+uuid.uuid4().hex[:10]+'_test' for _ in range(2)]
        cls.admin=c.connect('postgres')
        for name in cls.names:cls.admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        cls.source=c.connect(cls.names[0]);cls.target=c.connect(cls.names[1])
        for db in (cls.source,cls.target):
            migrate(db)
            db.execute('INSERT INTO dl_control.artifact VALUES(%s,1,%s,DEFAULT)',('a'*64,'fictional'))
            db.execute("INSERT INTO dl_control.source_snapshot(snapshot_id,layer_id,artifact_sha256,original_path,benefit_year) VALUES('fixture','L03',%s,'fictional',2026)",('a'*64,))
            db.execute("INSERT INTO dl_control.derivation(derivation_id,snapshot_id,adapter_version,configuration_hash) VALUES(%s,'fixture','fictional','fictional')",('b'*64,))
        for ordinal in range(1,5):
            cls.source.execute('INSERT INTO dl_evidence.source_record VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                ('b'*64,'fixture',ordinal,str(ordinal)*64,'key-'+str(ordinal),'original_ordinal','c'*64,
                 Jsonb({'null':None,'literal':'null','array':[True,False,None], 'text':'café 🟡','ordinal':ordinal}),'retained'))
            cls.source.execute('''INSERT INTO dl_evidence.observation VALUES(
                %s,'fictional',%s,'fixture',%s,NULL,NULL,2026,12.3400,%s,NULL,NULL,%s,
                'unknown','source_observed','not_reviewed','held','dated','research_only',%s,%s)''',
                ('b'*64,'item-'+str(ordinal),ordinal,'' if ordinal%2 else None,'0.00' if ordinal%2 else None,
                 Jsonb({'protected_cost_basis':'unresolved','not_zero':True}),
                 Jsonb({'missing':None,'text':'unknown','nested':{'none':False},'ordinal':ordinal})))
        cls.target.execute((PACKAGE/'redesign/r1/schema.sql').read_text())
        cls.target.execute("INSERT INTO dl_compact.source_set VALUES(1,%s,'fixture')",('b'*64,))
        cls.source_set={'source_set_id':1,'derivation_id':'b'*64,'source_table':'fixture'}
        cls.initial=c.load_chunk(cls.source,cls.target,cls.source_set,1,2)

    @classmethod
    def tearDownClass(cls):
        cls.source.close();cls.target.close()
        for name in cls.names:cls.admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
        cls.admin.close()

    def test_every_binary_column_roundtrips_including_null_empty_decimal_and_qualifiers(self):
        params=('b'*64,'fixture',1,2)
        self.assertEqual(c.binary_hash(self.source,c.RAW_QUERY,params),c.binary_hash(self.target,c.RAW_QUERY,params))
        self.assertEqual(c.binary_hash(self.source,c.OBS_QUERY,params),c.binary_hash(self.target,c.OBS_QUERY,params))
        self.assertEqual(self.initial['raw_rows'],2)
        self.assertEqual(self.initial['projection_rows'],2)

    def test_failed_parity_rolls_back_rows_symbols_and_checkpoint_together(self):
        with patch.object(c,'binary_hash',return_value=('0'*64,0)):
            with self.assertRaisesRegex(ValueError,'parity'):
                c.load_chunk(self.source,self.target,self.source_set,3,4)
        self.assertEqual(self.target.execute('SELECT count(*) AS n FROM dl_compact.source_record').fetchone()['n'],2)
        self.assertEqual(self.target.execute('SELECT count(*) AS n FROM dl_compact.load_checkpoint').fetchone()['n'],1)

    def test_research_view_works_and_physical_tables_are_private(self):
        with self.target.transaction():
            self.target.execute('SET LOCAL ROLE daylight_research_reader')
            self.assertEqual(self.target.execute('SELECT count(*) AS n FROM dl_evidence.observation').fetchone()['n'],2)
        with self.assertRaises(psycopg.errors.InsufficientPrivilege),self.target.transaction():
            self.target.execute('SET LOCAL ROLE daylight_research_reader')
            self.target.execute('SELECT * FROM dl_compact.source_record')

    def test_original_immutability_and_consumer_hold_survive(self):
        with self.assertRaises(psycopg.errors.RaiseException),self.target.transaction():
            self.target.execute("UPDATE dl_compact.observation SET raw_value='altered'")
        with self.target.transaction():
            self.target.execute('SET LOCAL ROLE daylight_released_reader')
            self.assertEqual(self.target.execute('SELECT count(*) AS n FROM dl_released.offerings').fetchone()['n'],0)

    def test_writer_can_persist_stop_but_cannot_clear_it(self):
        with self.assertRaises(psycopg.errors.InsufficientPrivilege),self.target.transaction():
            self.target.execute('SET LOCAL ROLE daylight_writer')
            self.target.execute("SELECT dl_control.persist_source_stop('fictional','test only')")
            self.target.execute("UPDATE dl_control.source_access_state SET state='permitted' WHERE source_id='fictional'")


if __name__=='__main__':unittest.main()
