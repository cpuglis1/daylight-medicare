"""Regression cases for real published-source normalization failures."""
import gzip
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from l08_r2_normalize import aetna_records,aetna_hospital_detail,BASE
from l08_r2_pdf_records import street_start


class L08FollowupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.examples=[]
        for line in gzip.open(BASE/'normalized-pdf-records.jsonl.gz','rt'):
            r=json.loads(line);name=r['provider_display_raw']or''
            if r['anchor_page']in [19,21,29,31]and any(k in name for k in ['Dell, Ioleen','Ferrante, Drue','Kurusanganapalli','Jaswal, Anitesh','McAtee, David','LPG Primary Care','Nye, Andre']):cls.examples.append(r)

    def find(self,name):return next(x for x in self.examples if name in(x['provider_display_raw']or''))

    def test_top_of_column_name_does_not_inherit_previous_doctors_npi(self):
        dell=self.find('Dell, Ioleen');ferrante=self.find('Ferrante, Drue')
        self.assertEqual(dell['identifier'],'1588777692')
        self.assertEqual(ferrante['identifier'],'1265427165')
        self.assertNotEqual(dell['id'],ferrante['id'])
        self.assertEqual(len(ferrante['addresses']),3)

    def test_wrapped_surname_is_separate_from_preceding_doctor(self):
        wrapped=self.find('Kurusanganapalli');previous=self.find('Jaswal, Anitesh')
        self.assertIn('Nagamani',wrapped['provider_display_raw'])
        self.assertEqual(wrapped['identifier'],'1154551992')
        self.assertEqual(previous['identifier'],'1639753049')

    def test_group_id_never_becomes_clinician_id_or_an_invented_site(self):
        group=self.find('LPG Primary Care');doctor=self.find('Nye, Andre')
        self.assertEqual(group['identifier'],'9469919')
        self.assertEqual(doctor['identifier'],'7910337')
        self.assertFalse(group['addresses'])
        self.assertFalse(doctor['addresses'])

    def test_missing_npi_does_not_drop_public_directory_cards(self):
        rows,_=aetna_records(BASE/'aetna-ui/H1609-027-pcp-25mi-page2.ax.txt')
        self.assertEqual(len(rows),20)
        self.assertTrue(any('publisher_provider_id'in r['fields']and'npi'not in r['fields']for r in rows))

    def test_virtual_office_is_retained_without_fabricating_street(self):
        rows,_=aetna_records(BASE/'aetna-ui/H5521-033-pcp-25mi-page16.ax.txt')
        r=next(r for r in rows if r['fields']['name_raw']=='Rathi, Dwarka, MD')
        self.assertEqual(r['fields']['office_kind_raw'],'Virtual Office')
        self.assertNotIn('street_raw',r['fields'])

    def test_expanded_plan_panel_supplies_exact_campus_observation(self):
        r=aetna_hospital_detail(BASE/'aetna-ui/rehab-detail-H1609-027.ax.txt')
        self.assertEqual(r['offering_id'],'2026:H1609:027:000')
        self.assertEqual(r['fields']['npi'],'1790432490')
        self.assertEqual(r['fields']['street_raw'],'14305 Collier Blvd')
        self.assertIn('H1609-027',r['fields']['published_plan_network_text'])
        self.assertIn('In Network',r['fields']['published_plan_network_text'])

    def test_unavailable_detail_is_not_negative_network_evidence(self):
        self.assertIsNone(aetna_hospital_detail(BASE/'aetna-ui/axiom-detail-H1609-027.ax.txt'))

    def test_printed_street_variants_preserve_footnotes_without_promoting_unit_only_address(self):
        for value in ['³ 1217 Piper Blvd, Ste 201','865 - 867 91st Avenue N','6801 1 Us Hwy 1 North','One Crisis Center Plaza']:
            self.assertTrue(street_start(value),value)
        self.assertFalse(street_start('Ste 104'))
        self.assertFalse(street_start('570, Ste 1100'))


if __name__=='__main__':unittest.main()
