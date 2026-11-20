"""Real PostgreSQL persistence/RLS tests, only in an explicitly disposable DB.

DAYLIGHT_HISTORY_TEST_DSN must select a database starting daylight_history_check_.
No model, network provider, production profile or display source is accessed.
"""
import os
import secrets
import unittest
import psycopg
from psycopg import sql

try:
    import guest_profiles
except ModuleNotFoundError:
    import server  # Local repo's pinned engine path; standalone bundle supplies it.
from guest_profiles import ProfileError
from hosted_history import BLOCKS_SQL, BLOCKS_GRANT_SQL, PostgresHistory, SCHEMA_SQL
from pilot_access import HISTORY_NOTICE

DSN=os.environ.get('DAYLIGHT_HISTORY_TEST_DSN')


@unittest.skipUnless(DSN,'Explicit disposable PostgreSQL test DSN is not set')
class PostgresHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.role='daylight_history_check_'+secrets.token_hex(5)
        with psycopg.connect(DSN) as db:
            name,=db.execute('SELECT current_database()').fetchone()
            if not name.startswith('daylight_history_check_'):
                raise RuntimeError('Refusing a non-test database.')
            db.execute(SCHEMA_SQL)
            db.execute(BLOCKS_SQL)
            db.execute(sql.SQL('CREATE ROLE {} NOLOGIN').format(sql.Identifier(cls.role)))
            db.execute(sql.SQL('GRANT USAGE ON SCHEMA hosted_history TO {}').format(sql.Identifier(cls.role)))
            db.execute(sql.SQL('GRANT SELECT,INSERT,UPDATE ON hosted_history.visits,hosted_history.turns TO {}').format(sql.Identifier(cls.role)))
            db.execute(sql.SQL('GRANT EXECUTE ON FUNCTION hosted_history.delete_visit(text) TO {}').format(sql.Identifier(cls.role)))
            db.execute(sql.SQL(BLOCKS_GRANT_SQL).format(sql.Identifier(cls.role)))

    @classmethod
    def tearDownClass(cls):
        with psycopg.connect(DSN) as db:
            db.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(cls.role)))
            db.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(cls.role)))

    def setUp(self):
        def connect(dsn,**kwargs):
            db=psycopg.connect(dsn,**kwargs)
            db.execute(sql.SQL('SET ROLE {}').format(sql.Identifier(self.role)))
            return db
        self.history=PostgresHistory(DSN,connect=connect)
        self.a=secrets.token_hex(16);self.b=secrets.token_hex(16)
        self.policy=(None,HISTORY_NOTICE,1)
        self.payload={'action':{'type':'message','message':'Fictional Medicare question'},'csrf':'never archive'}
        self.metadata={'release':'b'*64,'model':'gpt-6.1-sol','reasoning':'low'}

    def begin(self,visit=None,request='request-one',payload=None):
        return self.history.begin(visit or self.a,request,self.policy,payload or self.payload,self.metadata)

    def test_durable_before_delivery_idempotent_and_release_attributed(self):
        self.history.check_runtime_role()
        self.assertIsNone(self.begin())
        self.assertEqual(self.begin(),'accepted')
        self.history.finish(self.a,'request-one',{'reply':'Checked reply','reviewToken':'private'}, {'charges':[]})
        reopened=PostgresHistory(DSN,connect=self.history.connect)
        rows=reopened.read(self.a)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0][1],'response_ready')
        self.assertNotIn('csrf',rows[0][2]);self.assertNotIn('reviewToken',rows[0][3])
        self.assertEqual(rows[0][4],self.metadata)
        self.assertEqual(self.begin(),'response_ready')
        with self.assertRaises(ProfileError):self.begin(payload={'action':{'message':'Different'}})

    def test_rls_blocks_other_visit_even_when_query_omits_filter(self):
        self.begin();self.begin(self.b)
        with self.history.db(self.a) as db:
            rows=db.execute('SELECT visit FROM hosted_history.turns').fetchall()
            self.assertEqual(rows,[(self.a,)])
            self.assertEqual(db.execute('UPDATE hosted_history.turns SET error_code=999 WHERE visit=%s',(self.b,)).rowcount,0)
        with self.assertRaises(ProfileError):
            with self.history.db(self.a) as db:
                db.execute('INSERT INTO hosted_history.visits(visit,consent_version,consent_at) VALUES (%s,%s,1)',(secrets.token_hex(16),HISTORY_NOTICE))

    def test_delete_journal_prevents_resurrection_and_retains_other_visit(self):
        self.begin();self.begin(self.b)
        self.history.delete(self.a)
        self.assertEqual(self.history.read(self.a),[])
        self.assertEqual(len(self.history.read(self.b)),1)
        with self.assertRaises(ProfileError):self.begin()
        with psycopg.connect(DSN) as db:
            self.assertEqual(db.execute('SELECT reason FROM hosted_history.deletions WHERE visit=%s',(self.a,)).fetchone()[0],'participant_request')
        with self.assertRaises(ProfileError):
            with self.history.db(self.a) as db:db.execute('SELECT * FROM hosted_history.deletions')
        with self.assertRaises(ProfileError):
            with self.history.db(self.a) as db:db.execute('SELECT hosted_history.delete_visit(%s)',(self.b,))

    def test_expiry_blocks_new_turn_and_recovery(self):
        self.begin();self.history.finish(self.a,'request-one',{'reply':'Hello'}, {})
        with psycopg.connect(DSN) as db:
            db.execute("UPDATE hosted_history.visits SET expires_at=now()-interval '1 second' WHERE visit=%s",(self.a,))
        self.assertFalse(self.history.ready(self.a,'request-one'))
        self.assertEqual(self.history.read(self.a),[])
        with self.assertRaises(ProfileError):self.begin(request='later-request')

    def test_concurrent_duplicate_has_one_acceptance(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=5) as pool:
            results=list(pool.map(lambda _:self.begin(),range(10)))
        self.assertEqual(results.count(None),1)
        self.assertEqual(results.count('accepted'),9)

    def test_oversized_reply_is_not_written_or_marked_ready(self):
        self.begin()
        with self.assertRaises(ProfileError):
            self.history.finish(self.a,'request-one',{'reply':'x'*1048576},{})
        self.assertFalse(self.history.ready(self.a,'request-one'))

    def test_unfinished_turn_blocks_further_turns(self):
        self.begin()
        with self.assertRaises(ProfileError):self.begin(request='second-turn')
        self.assertEqual(len(self.history.read(self.a)),1)

    def test_history_cannot_rewrite_submitted_or_completed_content(self):
        self.begin()
        with self.assertRaises(ProfileError):
            with self.history.db(self.a) as db:
                db.execute("UPDATE hosted_history.turns SET submitted='{}'::jsonb WHERE visit=%s",(self.a,))
        self.history.finish(self.a,'request-one',{'reply':'Original reply'},{})
        with self.assertRaises(ProfileError):
            with self.history.db(self.a) as db:
                db.execute("UPDATE hosted_history.turns SET response='{}'::jsonb WHERE visit=%s",(self.a,))
        self.assertEqual(self.history.read(self.a)[0][3],{'reply':'Original reply'})


if __name__=='__main__':unittest.main()


class PostgresBlockTests(PostgresHistoryTests):
    """D199: checked blocks are archived per visit before display and follow deletion."""
    def test_blocks_archive_only_for_an_accepted_turn_and_stay_isolated(self):
        self.assertTrue(self.history.check_blocks())
        self.assertFalse(self.history.publish_blocks(self.a,'request-one',['No turn yet']))
        self.begin()
        self.assertTrue(self.history.publish_blocks(self.a,'request-one',['First checked block']))
        self.assertTrue(self.history.publish_blocks(self.a,'request-one',['First checked block','Second']))
        with self.history.db(self.a) as db:
            self.assertEqual(db.execute('SELECT blocks FROM hosted_history.turn_blocks').fetchall(),
                             [(['First checked block','Second'],)])
        with self.history.db(self.b) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM hosted_history.turn_blocks').fetchone(),(0,))
        self.assertFalse(self.history.publish_blocks(self.a,'request-one',['Fictional SSN 123-45-6789']))
        self.history.finish(self.a,'request-one',{'reply':'Done'},{'charges':[]})
        self.assertFalse(self.history.publish_blocks(self.a,'request-one',['Too late']))
        with self.history.db(self.a) as db:
            db.execute('SELECT hosted_history.delete_visit(%s)',(self.a,))
            self.assertEqual(db.execute('SELECT count(*) FROM hosted_history.turn_blocks').fetchone(),(0,))

