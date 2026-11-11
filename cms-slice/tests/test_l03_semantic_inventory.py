"""Source-backed decomposition regressions, separate from benefit verification.

Expected quotations/column membership below were read from retained pages.
These checks do not constitute the later independent whole-offering pilot.
"""
import gzip,hashlib,json,pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from l03_semantic_clauses import clean,decompose,detect_table_columns,source_cells,required_propositions,classify,sb_row_frames
from l03_pdf_geometry import native_line_cuts
FIX=pathlib.Path(__file__).parent/'fixtures/l03-semantic-r9'
PAGES=json.loads(gzip.decompress((FIX/'pages.json.gz').read_bytes()))
WORDS=json.loads(gzip.decompress((FIX/'native-words.json.gz').read_bytes()))


def page(n,who):return next(x for x in PAGES if x['pdf_page']==n and who in x['offering_id'])['text']

def body_only(text):
    return '\n'.join(l for l in text.splitlines()if not l.strip().startswith(('2026','Chapter')))


class SourcePages(unittest.TestCase):
    def test_fixtures_bound_to_exact_retained_page_views(self):
        for p in PAGES:self.assertEqual(hashlib.sha256(p['text'].encode()).hexdigest(),p['view_sha256'])

    def test_UHC_printed_header_gutter_not_old_cut_79(self):
        t=page(46,'H0710');g=detect_table_columns(t)
        self.assertEqual(g['boundaries'],[64,99]);self.assertEqual(g['roles'],['in_network','out_of_network'])

    def test_UHC_network_cost_columns_are_separate(self):
        t=page(46,'H0710');g=detect_table_columns(t);cells=source_cells(t,g['boundaries'],g['roles'])
        for column in ['cost_column_1:in_network','cost_column_2:out_of_network']:
            c=next(x for x in cells if x['column']==column)
            self.assertIn('You will pay the cost-',clean(c['text']))
            self.assertNotIn('No more than 20',clean(c['text']))

    def test_acupuncture_sentence_not_split_at_old_passage_boundary(self):
        t=page(46,'H0710');g=detect_table_columns(t)
        cell=next(x for x in source_cells(t,g['boundaries'],g['roles'])if x['column']=='service_column')
        atoms=decompose(cell['text'],{'chapter_role':'medical_benefits'})
        self.assertTrue(any('No more than 20 acupuncture treatments may be administered annually.' in clean(a['quote'])for a in atoms))

    def test_QMB_footer_is_whole_and_qualified(self):
        t=page(46,'H0710');g=detect_table_columns(t)
        cell=next(x for x in source_cells(t,g['boundaries'],g['roles'])if x['column']=='spanning_source_note')
        q=clean(cell['text']);self.assertIn('Qualified Medicare Beneficiary',q)
        self.assertIn('may be less',q);self.assertIn('Original Medicare.',q)

    def test_OCR_positions_keep_source_words_and_qualifiers(self):
        t=page(46,'H0710');g=detect_table_columns(t)
        words=json.loads(gzip.decompress((FIX/'UHC-46-OCR-words.json.gz').read_bytes()))['words']
        n=native_line_cuts(t,words);self.assertGreater(n['matched_fraction'],.95)
        cells=source_cells(t,g['boundaries'],g['roles'],n['cuts'])
        q=clean(next(c['text']for c in cells if c['column']=='service_column'))
        self.assertIn('No more than 20 acupuncture treatments may be administered annually.',q)
        self.assertNotIn('You will pay the cost-',q)

    def test_projection_characters_remain_exact(self):
        for t in [page(46,'H0710'),page(54,'H1036')]:
            g=detect_table_columns(t)
            for cell in source_cells(t,g['boundaries'],g['roles']):
                self.assertEqual(cell['text'],''.join(t[n]for n in cell['offsets']))

    def test_native_coordinates_fix_Humana_shifted_column(self):
        for p in [54,61]:
            t=page(p,'H1036');n=native_line_cuts(t,WORDS[str(p)]);g=detect_table_columns(t)
            cell=next(x for x in source_cells(t,g['boundaries'],g['roles'],n['cuts'])if x['column']=='service_column')
            q=clean(cell['text'])
            self.assertGreater(n['matched_fraction'],.99)
            if p==54:
                self.assertIn('medical equipment benefit',q);self.assertNotIn('Provider and Professional Services',q)
            else:
                self.assertIn('coordinated with your comprehensive prevention plan.',q)
                self.assertNotIn('copayment, or deductible for',q)

    def test_Liberty_six_service_list_crosses_page(self):
        t=body_only(page(39,'H5652'))+'\n'+body_only(page(40,'H5652'))
        atoms=decompose(t,{'chapter_role':'medical_benefits'})
        names=['Inpatient hospital care','Inpatient mental health care','Ambulatory surgical center (ASC), excluding diagnostic colonoscopy',
               'Outpatient hospital services, excluding diagnostic colonoscopy','Outpatient hospital observation services','Skilled nursing facility (SNF) care']
        for name in names:
            found=[a for a in atoms if name in clean(a['quote'])]
            self.assertTrue(found,name);self.assertEqual(found[0]['kind'],'condition',name)
            self.assertIn('deductible',found[0]['list_intro']['quote'])

    def test_Liberty_FQHC_exception_is_required(self):
        atoms=decompose(body_only(page(39,'H5652')),{'chapter_role':'medical_benefits'})
        a=next(a for a in atoms if 'Federally Qualified Health Center' in clean(a['quote']))
        self.assertEqual(a['kind'],'condition');self.assertIn('waiver_replacement',a['condition_families'])


class Semantics(unittest.TestCase):
    def atoms(self,t):return decompose(t,{'chapter_role':'medical_benefits'})

    def test_separate_authorization_referral_and_frequency(self):
        a=self.atoms('You need prior authorization and a referral for up to 12 visits per year.')[0]
        p=required_propositions(a)
        for family in ['authorization','referral','frequency_quantity']:self.assertIn(('condition',family),p)

    def test_qualified_price_has_claim_and_individual_conditions(self):
        a=self.atoms('You pay $30 per visit only if your provider is in-network.')[0]
        all_p=[p for x in self.atoms('You pay $30 per visit only if your provider is in-network.')for p in required_propositions(x)]
        self.assertIn(('claim','published_assertion'),all_p)
        self.assertTrue(any(k=='condition'for k,r in all_p))

    def test_decimal_and_abbreviation_not_fragmented(self):
        a=self.atoms('You pay $3.25 for care from Dr. Smith in the U.S. You pay $0 for screening.')
        self.assertEqual(len(a),2)

    def test_logical_parent_and_connectors_preserved(self):
        a=self.atoms('We cover care if you qualify and your provider obtains approval.')
        self.assertGreater(len(a),1)
        self.assertTrue(all(x['parent_sentence']=='We cover care if you qualify and your provider obtains approval.'for x in a))
        self.assertIn('if',[x['relation']for x in a])

    def test_covered_noun_list_not_document_outline(self):
        for t,kind in [('Covered services include, but are not limited to:\n• Physical therapy\n• Medical equipment','claim'),
                       ('Use this document to understand:\n• Our plan premiums\n• Your copayments','retained_structure')]:
            a=self.atoms(t);self.assertEqual(a[-1]['kind'],kind)

    def test_exclusion_list_keeps_negative_intro(self):
        a=self.atoms('The following services are not covered:\n• Cosmetic surgery\n• Personal convenience items')
        self.assertEqual(a[-1]['kind'],'condition');self.assertIn('exclusion',a[-1]['condition_families'])

    def test_noun_heading_is_context_not_an_invented_assertion(self):
        a=self.atoms('Provider and Professional Services')[0]
        self.assertEqual(a['kind'],'retained_structure')

    def test_CMS_approval_mention_does_not_drop_benefit(self):
        a=self.atoms('The OTC allowance covers CMS approved home and bathroom safety products.')[0]
        self.assertEqual(a['kind'],'claim')

    def test_administration_cannot_hide_explicit_condition(self):
        a=self.atoms('Call us for prior authorization before you receive this service.')[0]
        self.assertIn(a['kind'],['claim','condition']);self.assertIn('authorization',a['condition_families'])

    def test_calls_free_does_not_become_zero_benefit(self):
        kind,_,_=classify('Member Services: This call is free.',{'chapter_role':'contacts'})
        self.assertEqual(kind,'retained_administration')

    def test_procedural_timeline_is_not_benefit_condition(self):
        a=decompose('We need more information that may benefit you, we can take up to 14 more calendar days.',{'chapter_role':'appeals'})
        self.assertTrue(all(x['kind']=='retained_administration'for x in a))

    def test_negative_creditable_coverage_is_required(self):
        a=decompose('Discount cards are not creditable prescription drug coverage.',{'chapter_role':'introduction'})
        self.assertEqual(a[0]['kind'],'condition')

    def test_navigation_and_list_introducer_not_extra_claims(self):
        for t in ['For details on what medical care our plan covers and how much you pay','Covered services include, but are not limited to:']:
            self.assertTrue(self.atoms(t)[0]['kind'].startswith('retained_'))

    def test_missing_OCR_punctuation_does_not_merge_assertions(self):
        a=self.atoms('A qualified physician provides counseling We cover 2 attempts per year.')
        self.assertEqual(len(a),2)

    def test_SB_network_header_does_not_hide_first_benefit_line(self):
        t='                               In-network               Out-of-network\n   Routine hearing exam        $0 copay                 $90 copay\n   Hearing aids                $199 per aid             $199 per aid\n'
        g=detect_table_columns(t)
        self.assertEqual(g['roles'],['in_network','out_of_network'])
        self.assertEqual([e['line']for e in g['evidence']],[1])
        frames=sb_row_frames(t,g)
        self.assertEqual(frames[2],'Routine hearing exam');self.assertEqual(frames[3],'Hearing aids')

    def test_temporary_full_cost_exposure_is_required(self):
        a=decompose("If the pharmacy can't get enrollment information, you may need to pay the full cost of the prescription yourself.",{'chapter_role':'payment_procedure'})
        self.assertTrue(any(x['kind']in {'claim','condition'}for x in a))

    def test_reset_and_expiration_remain_individual_conditions(self):
        a=self.atoms('Unused credits expire at the end of each quarter and cannot be carried over.')
        self.assertTrue(any('frequency_quantity'in x['condition_families']for x in a))

    def test_short_indented_network_header_has_finite_gutter(self):
        g=detect_table_columns('             In-network           Out-of-network\n   Office    $0                   $35\n')
        self.assertEqual(g['roles'],['in_network','out_of_network'])

    def test_qualified_program_intro_is_required_and_decomposed(self):
        t='Once plan benefits and community resources have been exhausted, Chronic Condition Care Assistance funds may be available to members participating in a care management program, have been identified as high risk for hospitalization and have been diagnosed with at least one of the following chronic conditions:'
        a=self.atoms(t)
        self.assertGreaterEqual(len(a),4)
        self.assertTrue(all(x['kind']in {'claim','condition'}for x in a))

    def test_remaining_plan_share_is_required(self):
        self.assertEqual(self.atoms('The plan pays the rest.')[0]['kind'],'claim')

    def test_hyphenated_day_supply_has_boundary_obligation(self):
        self.assertIn('day_bands',self.atoms('Coverage is limited to a 34-day supply.')[0]['condition_families'])

    def test_once_resources_exhausted_is_qualification_not_frequency(self):
        a=self.atoms('Once plan benefits and community resources have been exhausted, funds may be available.')[0]
        self.assertEqual(a['kind'],'condition');self.assertIn('qualification',a['condition_families']);self.assertNotIn('frequency_quantity',a['condition_families'])

    def test_covered_list_does_not_leak_to_a_different_service(self):
        first='Covered services include:\n• Physical therapy\n\n'
        t=first+'A different service\n• Cosmetic surgery'
        a=decompose(t,{'chapter_role':'medical_benefits','scope_resets':[len(first)]})
        last=a[-1]
        self.assertNotEqual(last['rule'],'named_member_of_explicit_covered_service_list');self.assertIsNone(last['list_intro'])

    def test_no_CMS_expected_value_input_to_carrier_segmentation(self):
        import inspect
        for f in [decompose,source_cells,native_line_cuts]:
            self.assertNotIn('expected_amount',inspect.signature(f).parameters)

    def test_inline_OCR_bullets_keep_separate_coverage_exclusions(self):
        text="e Our plan can't cover a drug purchased outside the United States or its territories e.Our plan can't cover off-label use of a drug"
        atoms=decompose(text,{'chapter_role':'drug_coverage'})
        self.assertEqual(len(atoms),2)
        self.assertIn('outside the United States',atoms[0]['quote'])
        self.assertIn('off-label',atoms[1]['quote'])
        self.assertEqual(atoms[1]['relation'],'printed_list_next_assertion')

    def test_open_ended_service_example_list_is_not_quantity_limit(self):
        atom=decompose('Infection control, including but not limited to sterilization techniques.',{'chapter_role':'medical_benefits'})[0]
        self.assertNotIn('frequency_quantity',atom['condition_families'])

    def test_new_list_intro_does_not_inherit_previous_drug_stage_terms(self):
        text='You pay $0 after your deductible. Your costs may include the following:\n\n• Plan Premium (Section 4.1)'
        item=decompose(text,{'chapter_role':'drug_costs'})[-1]
        self.assertNotIn('deductible',item['condition_families'])
        self.assertIsNone(item.get('list_intro'))

    def test_actual_condition_intro_keeps_only_its_own_sentence(self):
        text='Other drugs cost $10. You must meet the following conditions:\n\n• A referral from your doctor'
        item=decompose(text,{'chapter_role':'medical_benefits'})[-1]
        self.assertEqual(item['list_intro']['quote'],'You must meet the following conditions:')

    def test_list_qualification_expires_before_a_later_unrelated_list(self):
        text='To qualify for Extra Help, meet the following conditions:\n\n• Low income\n\nYour pharmacy bills us directly.\n\n• If the pharmacy did not collect your copayment, contact us.'
        atoms=decompose(text,{'chapter_role':'drug_costs'})
        self.assertIsNotNone(atoms[1]['list_intro'])
        self.assertIsNone(atoms[-1]['list_intro'])

    def test_document_pronoun_definition_and_next_year_notice_are_retained(self):
        for text in ['When this Evidence of Coverage says “we,” “us,” or “our,” it means UnitedHealthcare.','Benefits, premium, deductible, and/or copayments/coinsurance may change on January 1, 2027.']:
            self.assertTrue(decompose(text,{'chapter_role':'introduction'})[0]['kind'].startswith('retained_'))


if __name__=='__main__':unittest.main()
