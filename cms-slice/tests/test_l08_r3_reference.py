"""Actual source regressions and scope safeguards for the L08 bootstrap."""
import gzip,json,sqlite3,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'cms-slice/scripts'))
from l08_r3_common import BASE,PARENT
from l08_r3_build import match_campus

class L08R3ReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db=sqlite3.connect('file:'+str(BASE/'providers.sqlite3')+'?mode=ro',uri=True)
        cls.invs=json.loads((BASE/'humana-document-inventory.json').read_text())

    @classmethod
    def tearDownClass(cls):cls.db.close()

    def test_plan_service_area_does_not_make_other_region_directory_collier(self):
        wrong=[x for x in self.invs if not x['collier_geography_explicit']]
        self.assertEqual(len(wrong),6)
        # All these regional editions still mention Collier in the plan's
        # broader service area. Only their own provider-geography paragraph
        # determines whether they supply Collier directory coverage.
        for x in wrong:
            self.assertIn('Collier',(ROOT/x['text_path']).read_text())
            self.assertNotIn('Collier',x['geography_raw'])
            self.assertIsNone(self.db.execute('SELECT 1 FROM plan_documents WHERE document_sha256=?',(x['sha256'],)).fetchone())

    def test_bottom_column_phone_is_not_clipped(self):
        rows=[]
        for s in gzip.open(BASE/'humana-address-observations.jsonl.gz','rt'):
            r=json.loads(s)
            if r['fields']['name_candidate_raw']=='NCH Otpt Rehab Creekside':rows.append(r)
        self.assertTrue(rows)
        self.assertTrue(all(r['fields']['phone_raw']=='(239) 624-0380'for r in rows))

    def test_numbered_street_is_not_swallowed_by_preceding_pcp_qualifiers(self):
        rows=[json.loads(s)for s in gzip.open(BASE/'humana-address-observations.jsonl.gz','rt')if'400 8th St N'in s]
        self.assertTrue(rows)
        self.assertTrue(any(r['fields']['street_raw']=='400 8th St N'and r['fields']['city_raw']=='Naples'for r in rows))
        self.assertTrue(all('PCP#'not in(r['fields']['street_raw']or'')for r in rows))

    def test_alphanumeric_and_run_on_source_streets_are_retained_without_rewriting(self):
        values=[]
        for s in gzip.open(BASE/'humana-address-observations.jsonl.gz','rt'):
            r=json.loads(s)
            if '20600A' in s or '24301waldencenterdr' in s:values.append(r['fields']['street_raw'])
        self.assertIn('20600A Veterans Blvd Ste 1',values)
        self.assertIn('24301waldencenterdr Ste103',values)

    def test_golisano_name_is_not_confused_with_go_to_page_control(self):
        rows=json.loads((BASE/'humana-public-hospital-observations.json').read_text())
        self.assertEqual(len(rows),50)
        self.assertEqual(sum(r['fields']['name_raw']=='Golisano Childrens Hospital'for r in rows),1)
        self.assertFalse(any('Give Feedback'in r['fields']['name_raw']for r in rows))

    def test_axiom_current_record_closes_hmo_campus_without_rewriting_old_entity(self):
        x=json.loads((BASE/'axiom-current-identity.json').read_text())
        self.assertEqual(x['npi'],'1235024357')
        self.assertEqual(x['current_Aetna_publisher_provider_id'],'2341726')
        self.assertEqual(x['parent_older_NPI'],'1932138823')
        self.assertEqual(x['parent_older_publisher_provider_id'],'6200930')
        state=self.db.execute("SELECT state FROM hospital_plan_matrix WHERE hospital_id='AHCA:10107'AND offering_id='2026:H1609:027:000'").fetchone()[0]
        self.assertTrue(state.startswith('published'))

    def test_tampa_resolution_preserves_the_publisher_naples_error(self):
        x=json.loads((BASE/'humana-location-resolution.json').read_text())
        self.assertEqual(x['npi'],'1619487246');self.assertEqual(x['canonical_city'],'Tampa')
        old=json.loads(self.db.execute('SELECT native_json FROM observations WHERE id=?',(x['parent_observation_id'],)).fetchone()[0])
        self.assertEqual(old['address']['city'],'Naples')
        self.assertEqual(old['address']['postalCode'],'33614')

    def test_shared_group_is_a_source_layout_link_not_a_new_person_identity(self):
        rows=json.loads((BASE/'published-shared-group-sites.json').read_text())
        dura=next(x for x in rows if'Dura Medical LLC'in x['name_block_raw'])
        self.assertIn('Block, Dale, MS \uf03a',dura['name_block_raw'])
        self.assertEqual(dura['shared_addresses'][0]['street_raw'],'1575 Pine Ridge Rd Ste 16')
        self.assertIn('individual identities not inferred',dura['state'])
        self.assertNotIn('npi',dura)

    def test_current_blue_family_search_does_not_invent_2026_plan_id(self):
        rows=json.loads((BASE/'blue-current-family-observations.json').read_text())
        self.assertEqual(len(rows),5)
        self.assertTrue(all(r['benefit_year']is None and r['exact_CMS_offering']is None for r in rows))

    def test_address_alone_never_makes_a_clinician_the_hospital(self):
        hs=[dict(id=r[0],county=r[1],name=r[2],addresses=json.loads(r[3]))for r in self.db.execute('SELECT id,county,name,addresses_json FROM hospitals')]
        self.assertEqual(match_campus('Example Doctor MD','350 7th St N','Naples','34102',hs),[])
        self.assertEqual(match_campus('Naples Community Hospital','350 7th St N','Naples','34102',hs),['AHCA:9841'])
        self.assertEqual(match_campus('Naples Community Hospital','350 7th St N','Naples','34110',hs),[])

    def test_research_scope_and_denominator_remain_explicit(self):
        x=json.loads((BASE/'summary.json').read_text())
        self.assertFalse(x['full_L08_complete']);self.assertFalse(x['consumer_release_enabled']);self.assertFalse(x['human_accepted'])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM offerings').fetchone()[0],72)
        self.assertEqual(x['Aetna_five_plans_Collier_hospital_positive_cells'],35)

if __name__=='__main__':unittest.main()
