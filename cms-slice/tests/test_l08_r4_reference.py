"""Concrete regressions for real retained-directory extraction failures."""
import json,sqlite3,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'cms-slice/scripts'))
from l08_r4_common import BASE

class ReferenceRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db=sqlite3.connect('file:'+str(BASE/'providers.sqlite3')+'?mode=ro',uri=True)
        cls.hmo=next(r[0]for r in cls.db.execute("SELECT DISTINCT document_sha256 FROM r4_humana_entries WHERE document_sha256 LIKE 'a3f%'") )
        cls.entries=[json.loads(r[0])for r in cls.db.execute('SELECT fields_json FROM r4_humana_entries WHERE document_sha256=? AND page=63',(cls.hmo,))]
    @classmethod
    def tearDownClass(cls):cls.db.close()

    def test_person_and_practice_stay_distinct(self):
        person=next(x for x in self.entries if x['name_raw']=='Krill, Gregory E MD*')
        self.assertEqual(person['name_kind'],'credentialed_clinician_name')
        self.assertIn('Established patients only',person['conditions_raw'])
        self.assertEqual(person['shared_practice_context']['name_raw'],'LPG Family Internal Medicine At Bass Road')
        self.assertIsNone(person['npi'])

    def test_distinct_later_clinician_address_ends_site_inheritance(self):
        p=next(x for x in self.entries if x['name_raw']=='Mendez-Hernandez, Eluar MD')
        self.assertIsNone(p['shared_practice_context'])
        self.assertEqual(p['site_association_state'],'no_explicit_site_in_bounded_entry')

    def test_PCP_suffix_is_not_stripped_or_person_identifier(self):
        p=next(x for x in self.entries if x['name_raw']=='Khan, Nabila DO'and any(i['value']=='126635I'for i in x['source_native_ids']))
        self.assertEqual(p['source_native_ids'][0]['value'],'126635I')
        self.assertTrue(p['source_native_ids'][0]['not_unique_person_identifier'])

    def test_footer_legend_is_not_a_provider_name(self):
        links=self.db.execute("SELECT fields_json FROM r4_address_entry_links WHERE fields_json LIKE '%Board Certified Provider%'").fetchall()
        self.assertGreater(len(links),20)
        for row, in links:self.assertNotIn('Board Certified Provider',json.loads(row)['typed_name_raw'])
        self.assertEqual(self.db.execute('SELECT count(*)FROM r4_address_entry_links WHERE entry_id IS NULL').fetchone()[0],0)

    def test_identified_Aetna_group_and_physicians_share_bounded_source_site(self):
        sh='84eb6aa79455773d53056847ca585a538a8ed12cce0f06ac424a5ff75e12ae6f'
        rs=[json.loads(self.db.execute('SELECT fields_json FROM r4_legacy_dispositions WHERE parent_record_id=?',('r2:'+sh+':'+str(i),)).fetchone()[0])for i in[19,20]]
        self.assertEqual(rs[0]['shared_layout_id'],rs[1]['shared_layout_id'])
        self.assertTrue(rs[0]['shared_layout_id'])
        self.assertEqual(rs[1]['domain_disposition'],'published_clinical_or_supplemental_section')

    def test_superscript_city_symbol_does_not_hide_Spring_Hill_site(self):
        rid='r2:af9a5ad197d7d1ee6275b6a9461899dd0ba03bf4e1a294c2c582ed2b553bd11a:3540'
        r=json.loads(self.db.execute('SELECT fields_json FROM r4_legacy_dispositions WHERE parent_record_id=?',(rid,)).fetchone()[0])
        self.assertEqual(r['recovered_direct_sites'][0]['city_raw'],'Spring Hill')
        self.assertIn('⁵',r['recovered_direct_sites'][0]['city_line_raw'])

    def test_wrapped_city_and_ZIP_keep_both_source_lines(self):
        gid='84eb6aa79455773d53056847ca585a538a8ed12cce0f06ac424a5ff75e12ae6f:identified-practice-run:3130'
        r=json.loads(self.db.execute('SELECT fields_json FROM r4_legacy_shared_layouts WHERE id=?',(gid,)).fetchone()[0])
        self.assertEqual(r['shared_addresses'][0]['city_lines'],[3138,3139])
        self.assertEqual(r['shared_addresses'][0]['postal_raw'],'33903')

    def test_same_name_site_publisher_rows_not_silently_deduplicated(self):
        rows=[json.loads(s)for s, in self.db.execute("SELECT fields_json FROM r4_public_observations WHERE network_raw='Medicare PPO'")]
        self.assertEqual(len(rows),123)
        woodmont=[r for r in rows if r['fields']['name_raw']=='HCA Florida Woodmont Hospital']
        self.assertEqual(len(woodmont),2)
        self.assertEqual({r['fields']['phone_raw']for r in woodmont},{'(954) 724-6100','(954) 721-2200'})

    def test_no_exact_plan_claim_from_ambiguous_PPO_network_reference(self):
        for s, in self.db.execute('SELECT fields_json FROM r4_public_observations'):self.assertIsNone(json.loads(s)['exact_offering_id'])
        hold=json.loads((BASE/'PPO-network-crosswalk-hold.json').read_text())
        self.assertEqual(hold['exact_offerings'],14);self.assertEqual(hold['new_exact_hospital_plan_cells_asserted'],0)

    def test_owner_links_are_labeled_truthfully(self):
        h=json.loads((BASE/'wellcare-download-handoff.json').read_text())
        self.assertEqual(len(h['plans']),6);self.assertEqual(h['verified_direct_PDF_links'],0)
        self.assertTrue(all(r['direct_pdf_url']is None for r in h['plans']))

if __name__=='__main__':unittest.main()
