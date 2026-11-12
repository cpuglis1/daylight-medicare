"""Regressions for owner intake, medical-listing semantics and scope safeguards."""
import json,sqlite3,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'cms-slice/scripts'))
from l08_r5_common import BASE
from l08_r5_normalize import ICON_MAP

class WellcareReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db=sqlite3.connect('file:'+str(BASE/'providers.sqlite3')+'?mode=ro',uri=True)
        cls.doc='2f2e2fb72f58032e5643e250680e74784185b96dfb853bf701e6d52837b6b056'
    @classmethod
    def tearDownClass(cls):cls.db.close()
    def provider(self,pid):
        return json.loads(self.db.execute('SELECT fields_json FROM r5_wellcare_records WHERE document_sha256=?AND publisher_provider_id=?',(self.doc,pid)).fetchone()[0])

    def test_six_owner_files_are_four_unique_publications(self):
        files=json.loads((BASE/'owner-file-observations.json').read_text())
        self.assertEqual(len(files),6);self.assertEqual(len({x['sha256']for x in files}),4)
        self.assertEqual(sum(x['pages']for x in json.loads((BASE/'document-inventory.json').read_text())),1428)

    def test_all_six_plan_names_bridge_uniquely_without_invented_printed_CMS_ID(self):
        bs=json.loads((BASE/'plan-directory-bindings.json').read_text())
        self.assertEqual({b['offering_id']for b in bs},{'2026:H1032:'+p+':000'for p in ['198','199','202','239','241','243']})
        self.assertTrue(all(b['CMS_ID_printed_in_directory']is False for b in bs))
        self.assertTrue(all(b['published_as_of']=='09/23/2026'for b in bs))

    def test_closed_panel_symbol_is_retained_and_missing_symbol_is_unknown(self):
        wise=self.provider('3177892');kupracz=self.provider('5150047')
        self.assertTrue(wise['symbol_flags']['not_accepting_new_patients'])
        self.assertIsNone(kupracz['symbol_flags']['not_accepting_new_patients'])
        self.assertTrue(kupracz['symbol_flags']['wheelchair_access'])
        self.assertEqual(wise['name_raw'],'Wise, Shannon MD')

    def test_same_black_color_pixels_different_masks_have_different_meanings(self):
        assets={x['asset_key']:x for x in json.loads((BASE/'image-asset-inventory.json').read_text())}
        wh=next(k for k,v in ICON_MAP.items()if v=='wheelchair_access');closed=next(k for k,v in ICON_MAP.items()if v=='not_accepting_new_patients')
        self.assertEqual(assets[wh]['pixels_sha256'],assets[closed]['pixels_sha256'])
        self.assertNotEqual(assets[wh]['mask_sha256'],assets[closed]['mask_sha256'])

    def test_repeated_page_heading_does_not_cut_off_continued_Collier_address(self):
        r=self.provider('5265267');self.assertEqual(r['name_raw'],'Calatayud Rojas, Ana APRN')
        self.assertEqual(r['addresses'][0]['street_raw'],'6376 Pine Ridge Rd, Unit 200')
        self.assertEqual(r['addresses'][0]['city_raw'],'Naples');self.assertEqual(r['addresses'][0]['postal_raw'],'34119')

    def test_source_run_on_street_is_retained_without_invented_spacing(self):
        r=self.provider('3026765');self.assertEqual(r['addresses'][0]['street_raw'],'6140winkler Rd, Ste A')
        self.assertNotIn('6140 Winkler',r['addresses'][0]['street_raw'])

    def test_house_number_24_is_not_a_24_hour_schedule(self):
        # This carrier ID appears at several sites; select the source site,
        # rather than assuming that a publisher provider ID is a location ID.
        rs=[json.loads(s)for s, in self.db.execute('SELECT fields_json FROM r5_wellcare_records WHERE document_sha256=?AND publisher_provider_id=?',(self.doc,'15635'))]
        r=next(r for r in rs if any(a['street_raw']=='24 Del Prado Blvd N, Suite 100'for a in r['addresses']))
        self.assertFalse(any(x['raw'].startswith('24 ')for x in r['hours_raw']))

    def test_publisher_ID_does_not_collapse_distinct_sites(self):
        rs=[json.loads(s)for s, in self.db.execute('SELECT fields_json FROM r5_wellcare_records WHERE document_sha256=?AND publisher_provider_id=?',(self.doc,'15635'))]
        streets={a['street_raw']for r in rs for a in r['addresses']}
        self.assertIn('39 Barkley Cir',streets);self.assertIn('24 Del Prado Blvd N, Suite 100',streets)
        self.assertEqual(len({r['id']for r in rs}),len(rs))

    def test_supplemental_network_listing_does_not_erase_plan_coverage_conditions(self):
        raw=self.db.execute("SELECT fields_json FROM r5_wellcare_records WHERE document_sha256=?AND section_raw='Additional Benefits' LIMIT 1",(self.doc,)).fetchone()[0]
        r=json.loads(raw);text=' '.join(x['raw']for x in r['section_conditions'])
        self.assertIn('may not be covered for all plans',text)
        self.assertIn('Not all benefits are available in all counties',text)

    def test_co_located_Landmark_and_abbreviated_North_are_not_silently_merged(self):
        e=json.loads((BASE/'new-hospital-evidence.json').read_text())
        self.assertEqual(len(e),24)
        self.assertNotIn('AHCA:489522',{x['hospital_id']for x in e})
        self.assertFalse(any(x['name_raw'].startswith('Landmark')for x in e))

    def test_count_conflict_is_explicit_and_does_not_create_synthetic_doctors(self):
        cs=json.loads((BASE/'publisher-count-discrepancies.json').read_text())
        self.assertEqual(len(cs),4);self.assertEqual(sum(x['difference']for x in cs),8)
        self.assertEqual(self.db.execute('SELECT count(*)FROM r5_wellcare_records').fetchone()[0],14158)

    def test_no_inferred_NPI_personal_guarantee_or_full_year_relationship(self):
        r=self.provider('3177892');self.assertIsNone(r['npi']);self.assertIsNone(r['provider_relationship_period'])
        self.assertFalse(r['personal_participation_verified'])

if __name__=='__main__':unittest.main()
