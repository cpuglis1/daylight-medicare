"""Context distinctions read from the pinned CMS field names and carrier headers."""
import gzip,hashlib,json,pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from l03_semantic_context import financial_context,source_question_target,printed_attribute_headers,plan_cost_question,pharmacy_column_questions,pharmacy_table_rows,pharmacy_columns_by_line

class SourceScope(unittest.TestCase):
    def test_rendered_Erickson_three_columns_and_four_physical_tier_rows(self):
        p=json.loads(gzip.decompress((pathlib.Path(__file__).parent/'fixtures/l03-semantic-r9/pharmacy-page.json.gz').read_bytes()))
        self.assertEqual(hashlib.sha256(p['text'].encode()).hexdigest(),p['view_sha256'])
        self.assertEqual(len(pharmacy_column_questions(p['text'])),3)
        frames,starts=pharmacy_table_rows(p['text'])
        self.assertEqual(list(starts.values()),['Published pharmacy table row: Tier '+n for n in ['1','2','3','3']])
        self.assertEqual(len(starts),4)
    def test_one_and_three_month_schedules_are_distinct(self):
        a=financial_context('mrx_gen_ira_mostd_copay_1m','Insulin Copayment amount for Standard Mail Order Cost-Sharing one month supply')
        b=financial_context('mrx_gen_ira_mostd_copay_3m','Insulin Copayment amount for Standard Mail Order Cost-Sharing three month supply')
        self.assertEqual(a['source_supply_months'],1);self.assertEqual(b['source_supply_months'],3);self.assertNotEqual(a,b)
    def test_tier_row_identity_is_material(self):
        a=financial_context('mrx_tier_post_copay_amt','Copayment',{'mrx_tier_post_id':'1'})
        b=financial_context('mrx_tier_post_copay_amt','Copayment',{'mrx_tier_post_id':'2'})
        self.assertNotEqual(a,b)
    def test_daily_rate_not_monthly_charge(self):
        a=financial_context('/rxTiers/rxTier3/rxTier3PreIcl/preIclPreferredRetailOneMonthDailyCopayment')
        b=financial_context('/rxTiers/rxTier3/rxTier3PreIcl/preIclPreferredRetailOneMonthCopayment')
        self.assertEqual(a['price_denominator'],'day');self.assertNotIn('price_denominator',b)
    def test_insulin_distinct_from_other_drugs(self):
        self.assertEqual(financial_context('/rxInsulin/rxInsulinTier2PreIcl/insulinPreIclRetailOneMonthCopayment')['drug_scope'],'insulin')
        self.assertNotIn('drug_scope',financial_context('/rxTiers/rxTier2PreIcl/preIclRetailOneMonthCopayment'))
    def test_network_and_pharmacy_basis_are_distinct(self):
        a=financial_context('preIclPreferredMailOrderTwoMonthCopayment')
        b=financial_context('preIclMailOrderTwoMonthCopayment')
        self.assertNotEqual(a['pharmacy'],b['pharmacy'])
    def test_endpoints_share_exact_target_not_whole_Rx_object(self):
        self.assertEqual(source_question_target('Minimum Copayment Amount for Medicare Part B Chemotherapy/Radiation Drugs'),source_question_target('Maximum Coinsurance percentage for Medicare Part B Chemotherapy/Radiation Drugs'))
        self.assertNotEqual(source_question_target('Copayment for insulin'),source_question_target('Copayment for other Medicare Part B Drugs'))
    def test_identical_printed_price_retains_changed_supply_header(self):
        t='Retail pharmacy\n(1-month supply of covered drugs)\nTier 3 Preferred brand 24.00% / 24.00%\nRetail/mail pharmacy\n(3-month supply of covered drugs)\nTier 3 Preferred brand 24.00% / 24.00%'
        frames=printed_attribute_headers(t)
        self.assertNotEqual(frames[3],frames[6])
        self.assertIn('1-month',frames[3]['supply_header']['text']);self.assertIn('3-month',frames[6]['supply_header']['text'])

    def test_MOOP_membership_is_a_condition_not_an_amount(self):
        native={'pbp':[{'planLevelCostSharing':{'maxEnrolleeCostLimit':{'maxEnrolleeCostLimitDetails':{'medicareServices':[{'categoryCode':'2','moopCombinedOutOfNetwork':'1'}]}}}}]}
        group,role,context=plan_cost_question('/pbp/0/planLevelCostSharing/maxEnrolleeCostLimit/maxEnrolleeCostLimitDetails/medicareServices/0/moopCombinedOutOfNetwork',native)
        self.assertEqual(role,'source_plan_condition');self.assertEqual(context['category_code'],'2');self.assertEqual(context['network'],'out_of_network');self.assertEqual(context['source_budget_scope'],'combined')
    def test_MOOP_amount_and_its_selector_share_one_exact_network_schedule(self):
        base='/pbp/0/planLevelCostSharing/maxEnrolleeCostLimit/maxEnrolleeCostLimitDetails/'
        self.assertEqual(plan_cost_question(base+'inNWMoop',{})[:2],plan_cost_question(base+'inNWMoopAmount',{})[:2])
        self.assertNotEqual(plan_cost_question(base+'inNWMoopAmount',{})[0],plan_cost_question(base+'combinedMoopAmount',{})[0])
    def test_preferred_standard_columns_are_distinct_required_questions(self):
        t='Retail pharmacy\n(1-month supply of covered drugs)\n              Preferred/Standard\nTier 3          24% / 24%'
        cols=pharmacy_column_questions(t)
        self.assertEqual([c['printed_label']for c in cols],['Preferred','Standard'])
        self.assertEqual(len({c['source_pharmacy_column']for c in cols}),2)

    def test_30_and_100_day_columns_are_six_distinct_contexts(self):
        t='Retail Cost-Sharing       Standard Mail-Order       Preferred Mail-Order\nDay supply 30-day 100-day 30-day 100-day 30-day 100-day\nTier 1 $0 $0 $0 $0 $0 $0'
        cols=pharmacy_column_questions(t)
        self.assertEqual(len(cols),6);self.assertEqual([c['printed_label']for c in cols],['30-day','100-day']*3)
    def test_five_tiers_are_five_physical_rows(self):
        t='Insulin Cost-Sharing\n'+'\n'.join('Tier '+str(n)+': Drug $35 $105'for n in range(1,6))
        frames,starts=pharmacy_table_rows(t)
        self.assertEqual(len(starts),5);self.assertEqual(len(set(frames.values())),5)
    def test_cost_before_next_line_tier_label_is_one_row(self):
        frames,starts=pharmacy_table_rows('Cost Sharing $20 $19 $20 $20\nTier 2 (Generic)\nCost Sharing 25% 25% 25%\nTier 3 (Preferred Brand)')
        self.assertEqual(list(starts),[1,3]);self.assertEqual(frames[1],frames[2]);self.assertEqual(frames[3],frames[4])

    def test_tier_before_cost_stays_with_correct_tier(self):
        frames,starts=pharmacy_table_rows('Tier 1.\nCost-Sharing Standard retail: $10 $10\nTier 2.\nCost-Sharing Standard retail: 15% 15%')
        self.assertEqual(list(starts),[1,3]);self.assertIn('Tier 1',frames[2]);self.assertIn('Tier 2',frames[4])
    def test_repeated_supply_table_uses_its_own_header(self):
        t='Retail pharmacy\n(1-month supply)\nPreferred/Standard\nTier 1 $0 $2\nRetail/mail pharmacy\n(3-month supply)\nPreferred/Standard\nTier 1 $0 $6'
        f=pharmacy_columns_by_line(t)
        self.assertEqual(f[4][0]['header_line'],3);self.assertEqual(f[8][0]['header_line'],7)
    def test_narrative_after_table_has_no_tier_scope(self):
        f,_=pharmacy_table_rows('                  Cost-Sharing $10 $10\n                                       Tier 1.\n               You may pay $30 for other services.')
        self.assertNotIn(3,f)

if __name__=='__main__':unittest.main()
