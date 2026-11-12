import json,pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import l03_user_documents as intake
import l03_user_reconcile as reconcile
import l03_user_reference as reference

class L03OwnerSourceTests(unittest.TestCase):
    def test_money_decimal_and_units(self):
        self.assertTrue(reconcile.value_occurs('.2','USD/month','Up to $0.20 monthly'))
        self.assertFalse(reconcile.value_occurs('.2','USD/month','$0.25 monthly'))
        self.assertFalse(reconcile.value_occurs(0,'USD','$0.20'))
        self.assertFalse(reconcile.value_occurs(20,'percent','$20 copay'))
        self.assertTrue(reconcile.value_occurs(13900,'USD/year','$13,900'))
        self.assertFalse(reconcile.value_occurs(90,'day','$90'))
    def test_shared_column_preserves_labels_and_exact_plan(self):
        text='Benefits                 H1032, Plan 240, 000           H1032, Plan 241, 000\nWallet                   $142 monthly                   $101 monthly\n'
        v,m=intake.shared_wellcare_view(text,'2026:H1032:241:000')
        self.assertIn('Wallet',v);self.assertIn('$101',v);self.assertNotIn('$142',v)
        self.assertEqual(m['selected_column'],2)
    def test_single_plan_assistance_columns_not_removed(self):
        t='H1032, Plan 202, 000\nQMB $0; SLMB 20%\n'
        v,m=intake.shared_wellcare_view(t,'2026:H1032:202:000')
        self.assertEqual(t,v);self.assertFalse(m['shared_plan_columns'])
    def test_absent_plan_does_not_get_neighbor(self):
        t='H1032, Plan 240, 000       H1032, Plan 241, 000\n$142                     $101'
        v,m=intake.shared_wellcare_view(t,'2026:H1032:243:000')
        self.assertEqual(v,'');self.assertTrue(m['exact_plan_absent'])
    def test_new_reference_cannot_be_published(self):
        with self.assertRaises(PermissionError):reference.published_lookup({'year':2026})
    def test_full_matrix_has_exact_segments_and_missing_erickson(self):
        m=intake.load(intake.ROOT/'plan-document-matrix.json');self.assertEqual(len(m),72)
        self.assertEqual(sum(p['documented']for p in m),67)
        missing=[p['offering_id']for p in m if not p['documented']]
        self.assertEqual(missing,['2026:H5652:'+p+':000'for p in ['001','002','004','006','008']])
        self.assertTrue(next(p for p in m if p['offering_id']=='2026:H1045:048:002')['documented'])
        self.assertFalse(any(p['offering_id']=='2026:H1045:048:000'for p in m))
    def test_all_native_and_ocr_pages_accounted(self):
        cat=intake.load(intake.ROOT/'source-catalog.json');self.assertEqual(len(cat),43)
        counts={}
        for p in intake.rows(intake.ROOT/'new-source-pages.jsonl.gz'):
            counts[p['document_sha256']]=counts.get(p['document_sha256'],0)+1
            self.assertEqual(intake.sha(p['text'].encode()),p['text_sha256'])
            if 'layout_text'in p:self.assertEqual(intake.sha(p['layout_text'].encode()),p['layout_text_sha256'])
        self.assertEqual(counts,{p['sha256']:p['pdf_pages']for p in cat})
    def test_source_cases_keep_differences_and_qualifications(self):
        a=intake.load(intake.ROOT/'source-led-comparisons.json');self.assertEqual(len({x['offering_id']for x in a}),20)
        held=[x for x in a if x['source_values_equal']is False];self.assertTrue(held)
        for x in a:self.assertTrue(x['qualifications']);self.assertFalse(x['accepted_for_reference'])
        x=next(x for x in a if x['offering_id']=='2026:H2509:003:000'and x['field']=='INN_annual_medical_MOOP')
        self.assertEqual(x['expected_from_SB'],'0');self.assertEqual(x['CMS_actual'],'9250.00');self.assertFalse(x['source_values_equal'])
    def test_wellcare_distinct_wallets_and_caps(self):
        a=intake.load(intake.ROOT/'supplemental-source-led-checks.json')
        get=lambda p,f:next(x for x in a if x['offering_id']=='2026:H1032:'+p+':000'and x['field']==f)
        self.assertEqual(get('241','shared_Spendables_allowance')['value'],'101')
        self.assertEqual(get('243','shared_Spendables_allowance')['value'],'160')
        self.assertEqual(get('243','routine_comprehensive_dental_plan_payment_maximum')['value'],'4000')
        self.assertIn('roll',get('243','shared_Spendables_allowance')['interpretation'])
    def test_blank_zero_and_not_covered_remain_distinct(self):
        blanks=zeros=0
        for x in intake.rows(intake.ROOT/'field-dispositions.jsonl.gz'):
            if x['normalized'].get('state')=='source_blank':
                blanks+=1;self.assertEqual(x['r6_state'],'source_blank_retained')
            if x['raw']in ['0','0.00']:zeros+=1
            self.assertFalse(x['carrier_corroborated']);self.assertFalse(x['consumer_usable'])
        self.assertGreater(blanks,0);self.assertGreater(zeros,0)
if __name__=='__main__':unittest.main()
