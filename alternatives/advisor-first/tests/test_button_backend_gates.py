"""Finite-answer/backend dependency audit. No model calls or browser required."""
import copy
import itertools
import unittest

import test_natural_flow as support
from adaptive_flow import Q, FIELD, metadata
from guest_profiles import ProfileError
from natural_state import set_target
from comparison_profile import build_comparison_profile


class ButtonBackendGateTests(unittest.TestCase):
    def fresh(self):
        case=support.NaturalFlowTests()
        case.setUp()
        return case

    @staticmethod
    def apply(case,identifier,fields,entity='profile',source='user_choice'):
        case.flow.apply(case.g,case.r,{'id':identifier,'entity':entity,'fields':fields},source)
        case.flow.validate(case.g,case.r)

    @staticmethod
    def bind(case):
        chain=case.flow.current_chain[case.owner]
        case.continuation=case.flow.bind(case.owner,case.g,case.r,chain)
        case.flow.state_heads[(case.owner,chain)]=case.continuation

    def test_every_rendered_question_choice_is_supported_without_model_or_invented_verification(self):
        # All 41 approved inventory meanings, including documented children,
        # collapse into 38 distinct parent questions. The current constructor
        # intentionally hides text-entry/status choices that are not buttons.
        self.assertEqual(len(Q),41)
        parents=[identifier for identifier,q in Q.items() if q['kind']!='documented_child']
        self.assertEqual(len(parents),38)
        checked=[]
        for identifier in parents:
            prototype=self.fresh()
            for value,label in prototype.flow.question(identifier)['choices']:
                with self.subTest(question=identifier,button=label):
                    case=self.fresh()
                    out=case.choice(identifier,choice=value)
                    assessment=out['assessment']
                    self.assertFalse(assessment['personalizedRecommendationAllowed'])
                    self.assertFalse(assessment['externalVerificationReady'])
                    self.assertEqual(case.calls,[])
                    if identifier in FIELD:
                        if value=='unknown':
                            self.assertEqual(metadata(case.r)['baselineDispositions'][identifier],'unknown')
                        else:
                            reported=case.flow.value(case.g,FIELD[identifier])
                            self.assertEqual(reported,[value] if identifier in {'T05','T08','T10'} else value)
                    else:
                        if value=='unknown':
                            self.assertEqual(case.r['dispositions'][identifier]['state'],'explicit_unknown')
                        else:
                            self.assertEqual(case.flow.report(case.r,identifier)['choice'],value)
                    checked.append((identifier,value))
        self.assertGreater(len(checked),60)
        self.assertIn(('T04','soonest'),checked)
        self.assertIn(('T05','medicaid'),checked)

    def test_every_insurance_button_takes_only_its_applicable_timing_branch(self):
        prototype=self.fresh()
        for value,label in prototype.flow.question('T05')['choices']:
            with self.subTest(coverage=label):
                case=self.fresh()
                case.task('timing')
                case.choice('RC01',choice='self')
                case.choice('T04',choice='soonest')
                out=case.choice('T05',choice=value)
                nextq=out['assessment']['nextQuestion']
                if value=='employer':
                    self.assertEqual(nextq['id'],'RC09')
                    self.assertNotIn('RC09',case.r['facts'])
                elif value in {'cobra','retiree'}:
                    self.assertEqual(case.flow.report(case.r,'RC09')['choice'],value)
                    self.assertEqual(nextq['id'],'RC11')
                    self.assertEqual([field['key'] for field in nextq['fields']],['coverageEnd'])
                else:
                    self.assertIsNone(nextq)
                    self.assertNotIn('RC09',case.r['facts'])
                # Medicaid is not Medicare, and no selection establishes A/B
                # enrollment, employment end, payer order or program eligibility.
                self.assertNotIn('RC04',case.r['facts'])
                self.assertNotIn('RC11',case.r['facts'])
                self.assertNotIn('RC19',case.r['facts'])
                self.assertEqual(case.calls,[])

    def test_each_worker_button_preserves_worker_kind_and_only_requested_dates(self):
        for worker in ('my_job','spouse_job','family_job','retiree','cobra'):
            with self.subTest(worker=worker):
                case=self.fresh()
                case.task('timing')
                case.choice('RC01',choice='self')
                case.choice('T04',choice='soonest')
                case.choice('T05',choice='employer')
                out=case.choice('RC09',choice=worker)
                self.assertEqual(out['assessment']['nextQuestion']['id'],'RC11')
                expected=['coverageEnd'] if worker in {'retiree','cobra'} else ['jobEnd','coverageEnd']
                self.assertEqual([field['key'] for field in out['assessment']['nextQuestion']['fields']],expected)
                self.assertEqual(case.flow.report(case.r,'RC09')['choice'],worker)
                self.assertEqual(case.calls,[])

    def test_payer_order_threshold_choices_follow_qualification_and_current_worker(self):
        for qualification,threshold in (('age65','20'),('disability','100')):
            for size in ('yes','no','unknown'):
                with self.subTest(qualification=qualification,size=size):
                    case=self.fresh()
                    metadata(case.r)['checks']=['payer_order']
                    case.task('timing')
                    case.choice('RC01',choice='self')
                    case.choice('T04',choice='soonest')
                    out=case.choice('T05',choice='employer')
                    self.assertEqual(out['assessment']['nextQuestion']['id'],'RC04')
                    case.choice('RC04',choice='both')
                    case.choice('RC09',choice='my_job')
                    out=case.choice('RC11',jobEnd='March 2027',coverageEnd='April 2027')
                    self.assertEqual(out['assessment']['nextQuestion']['id'],'RC06')
                    out=case.choice('RC06',choice=qualification)
                    self.assertEqual(out['assessment']['nextQuestion']['id'],'RC10')
                    self.assertIn(threshold,out['assessment']['nextQuestion']['question'])
                    out=case.choice('RC10',choice=size)
                    self.assertIsNone(out['assessment']['nextQuestion'])
                    self.assertFalse(out['assessment']['externalVerificationReady'])
                    self.assertEqual(case.calls,[])

    def test_compare_buttons_continue_baseline_and_travel_detail_only_when_needed(self):
        for travel in ('local','elsewhere_us','outside_us','unknown'):
            with self.subTest(travel=travel):
                case=self.fresh()
                case.task('compare')
                self.assertEqual(case.flow.assess(case.g,case.r)['nextQuestion']['id'],'RC01')
                out=case.choice('RC01',choice='self')
                self.assertEqual(out['assessment']['nextQuestion']['id'],'T04')
                out=case.choice('T04',choice='soonest')
                self.assertEqual(out['assessment']['nextQuestion']['id'],'T05')
                out=case.choice('T05',choice='medicaid')
                self.assertEqual(out['assessment']['nextQuestion']['id'],'T03')
                out=case.choice('T03',zip='34102')
                self.assertEqual(out['assessment']['nextQuestion']['id'],'T06')
                out=case.choice('T06',choice='none')
                self.assertEqual(out['assessment']['nextQuestion']['id'],'T07')
                out=case.choice('T07',choice='no')
                self.assertEqual(out['assessment']['nextQuestion']['id'],'T08')
                out=case.choice('T08',choice=travel)
                if travel in {'elsewhere_us','outside_us'}:
                    self.assertEqual(out['assessment']['nextQuestion']['id'],'RC20')
                    self.assertEqual([field['key'] for field in out['assessment']['nextQuestion']['fields']],['location'])
                else:
                    self.assertIsNone(out['assessment']['nextQuestion'])
                self.assertFalse(out['assessment']['personalizedRecommendationAllowed'])
                self.assertEqual(case.calls,[])

    def test_unknown_and_check_later_are_supported_for_every_parent_question(self):
        for identifier,q in Q.items():
            if q['kind']=='documented_child':
                continue
            for kind in ('unknown','defer'):
                with self.subTest(question=identifier,button=kind):
                    case=self.fresh()
                    if identifier=='RC23':
                        self.apply(case,'RC22',{'name':'Example medicine','strength':'5 mg','form':'tablet'},'medicine-1')
                    metadata(case.r)['editing']=identifier
                    current=case.flow.assess(case.g,case.r)['nextQuestion']
                    self.assertEqual(current['id'],identifier)
                    out=case.turn({'type':kind,'id':identifier},aiConsent=False)
                    self.assertEqual(case.calls,[])
                    self.assertFalse(out['assessment']['personalizedRecommendationAllowed'])
                    if identifier in FIELD:
                        self.assertIn(identifier,metadata(case.r)['baselineDispositions'])
                    else:
                        self.assertTrue(identifier in case.r['dispositions'] or any(
                            key.startswith(identifier+'.') for key in metadata(case.r)['skippedDetails']))

    def seed_pending_pair(self,identifier):
        case=self.fresh()
        case.task('providers' if identifier=='RC21' else 'drug_pricing')
        case.choice('RC01',choice='self')
        prefix='doctor' if identifier=='RC21' else 'medicine'
        for number in (1,2):
            if identifier=='RC21':
                fields={'practice':'Example clinic '+str(number),'city':'Naples'}
            else:
                fields={'name':'Example med '+str(number),'strength':'5 mg','form':'tablet'}
            case.turn({'type':'choice','id':'RC21' if identifier=='RC21' else 'RC22',
                'entity':prefix+'-'+str(number),'fields':fields},aiConsent=False)
            if identifier=='RC23':
                case.turn({'type':'choice','id':'RC23','entity':prefix+'-'+str(number),
                    'fields':{'quantity':'30 tablets','daysSupply':'30'}},aiConsent=False)
        key={'RC21':'city','RC22':'strength','RC23':'quantity'}[identifier]
        case.r['facts'][identifier]['stale']=True
        targets=[{'id':identifier,'entity':prefix+'-'+str(number),'fields':{key:'proposed value'}}
                 for number in (1,2)]
        case.flow.queue_pending(case.owner,targets,case.g,case.r)
        set_target(case.r,case.flow.question(identifier,[key],prefix+'-1'))
        self.bind(case)
        return case,prefix,key

    def test_unknown_and_check_later_buttons_preserve_and_complete_each_aggregate_queue(self):
        for identifier in ('RC21','RC22','RC23'):
            for first,second in (('unknown','defer'),('defer','unknown')):
                with self.subTest(question=identifier,first=first):
                    case,prefix,key=self.seed_pending_pair(identifier)
                    out=case.turn({'type':first,'id':identifier},aiConsent=False)
                    self.assertEqual(case.flow.pending_for(case.owner)['update']['entity'],prefix+'-2')
                    self.assertEqual(out['assessment']['nextQuestion']['entity'],prefix+'-2')
                    self.assertTrue(case.r['facts'][identifier]['stale'])
                    self.assertNotIn(key,case.r['facts'][identifier]['value']['items'][0])
                    self.assertIn(key,case.r['facts'][identifier]['value']['items'][1])
                    # Recomputing candidates must not discard the sibling queue.
                    self.assertEqual(case.flow.eligible(case.owner,case.g,case.r)[0]['question']['entity'],prefix+'-2')
                    case.turn({'type':second,'id':identifier},aiConsent=False)
                    self.assertIsNone(case.flow.pending_for(case.owner))
                    self.assertFalse(case.r['facts'][identifier]['stale'])
                    items=case.r['facts'][identifier]['value']['items']
                    self.assertEqual(len(items),2)
                    self.assertTrue(all(key not in item for item in items))
                    self.assertEqual(case.calls,[])

    def test_pending_disposition_rejects_a_different_question_or_item_without_mutation(self):
        for wrong in ({'type':'unknown','id':'T05'},
                      {'type':'defer','id':'RC22','entity':'medicine-2'}):
            case,_,_=self.seed_pending_pair('RC22')
            before=copy.deepcopy((case.g,case.r,case.flow.pending_for(case.owner)))
            with self.assertRaises(ProfileError):
                case.turn(wrong,aiConsent=False)
            self.assertEqual((case.g,case.r,case.flow.pending_for(case.owner)),before)
            self.assertEqual(case.calls,[])

    def test_submitted_assistance_selections_replace_instead_of_readding_removed_programs(self):
        programs=['medicaid','extra_help','part_b_help','ssi']
        for size in range(1,5):
            for desired in itertools.combinations(programs,size):
                with self.subTest(selected=desired):
                    case=self.fresh()
                    self.apply(case,'RC18',{'choice':','.join(programs)})
                    self.apply(case,'RC18',{'choice':','.join(desired)})
                    self.assertEqual(case.flow.report(case.r,'RC18')['programs'],sorted(desired))
                    self.assertEqual(case.calls,[])

    def test_assistance_text_reports_add_while_decline_and_unknown_keep_known_programs(self):
        case=self.fresh()
        self.apply(case,'RC18',{'choice':'medicaid'})
        self.apply(case,'RC18',{'choice':'extra_help'},source='confirmed_agent_interpretation')
        self.assertEqual(case.flow.report(case.r,'RC18')['programs'],['extra_help','medicaid'])
        self.apply(case,'RC18',{'choice':'declined'})
        self.assertEqual(case.flow.report(case.r,'RC18')['programs'],['extra_help','medicaid'])
        self.apply(case,'RC18',{'choice':'unknown'})
        self.assertEqual(case.r['facts']['RC18']['value']['programs'],['extra_help','medicaid'])
        self.apply(case,'RC18',{'choice':'none'})
        self.assertEqual(case.flow.report(case.r,'RC18')['programs'],[])

    def test_priority_buttons_enforce_three_without_erasing_the_existing_selection(self):
        case=self.fresh()
        self.apply(case,'T10',{'choice':'doctors,drugs,total_cost'})
        before=copy.deepcopy((case.g,case.r))
        with self.assertRaises(ProfileError):
            self.apply(case,'T10',{'choice':'doctors,drugs,total_cost,travel'})
        self.assertEqual((case.g,case.r),before)
        self.apply(case,'T10',{'choice':'doctors,drugs,total_cost,travel'},source='confirmed_agent_interpretation')
        self.assertEqual(len(case.flow.value(case.g,'needs.priorities')),4)

    def test_fill_controls_require_a_retained_medicine_and_preserve_sibling_association(self):
        case=self.fresh()
        for number in (1,2):
            self.apply(case,'RC22',{'name':'Example '+str(number),'strength':'5 mg','form':'tablet'},'medicine-'+str(number))
        for number in (1,2):
            self.apply(case,'RC23',{'quantity':str(30*number)+' tablets','channel':'retail'},'medicine-'+str(number))
        before=copy.deepcopy((case.g,case.r))
        with self.assertRaises(ProfileError):
            self.apply(case,'RC23',{'daysSupply':'30'},'medicine-3')
        self.assertEqual((case.g,case.r),before)
        self.assertEqual({item['entity']:item['quantity'] for item in case.flow.report(case.r,'RC23')['items']},
                         {'medicine-1':'30 tablets','medicine-2':'60 tablets'})
        self.assertEqual(case.calls,[])

    def test_no_doctors_and_no_prescriptions_suspend_older_details_and_keep_them_recoverable(self):
        for baseline,detail,prefix,key,none,status in (
                ('T06','RC21','doctor','practice','none','needs.providersStatus'),
                ('T07','RC22','medicine','name','no','needs.medicinesStatus')):
            with self.subTest(button=baseline):
                case=self.fresh()
                case.task('providers' if baseline=='T06' else 'drug_pricing')
                case.choice('RC01',choice='self')
                fields={key:'Example retained item'}
                fields.update({'city':'Naples'} if detail=='RC21' else {'strength':'5 mg','form':'tablet'})
                case.turn({'type':'choice','id':detail,'entity':prefix+'-1','fields':fields},aiConsent=False)
                if detail=='RC22':
                    case.turn({'type':'choice','id':'RC23','entity':'medicine-1',
                        'fields':{'quantity':'30 tablets','daysSupply':'30'}},aiConsent=False)
                name_field='needs.providers' if baseline=='T06' else 'needs.medications'
                previous=copy.deepcopy(case.g['fields'][name_field])
                retained=copy.deepcopy(case.r['facts'][detail]['value'])
                out=case.choice(baseline,choice=none)
                self.assertEqual(case.flow.value(case.g,status),none)
                self.assertIsNone(case.flow.value(case.g,name_field))
                self.assertTrue(case.r['facts'][detail]['stale'])
                self.assertEqual(case.r['facts'][detail]['value'],retained)
                self.assertEqual(case.g['fields'][name_field]['value'],previous['value'])
                self.assertEqual(case.g['fields'][name_field]['revision'],previous['revision'])
                if detail=='RC22':
                    self.assertTrue(case.r['facts']['RC23']['stale'])
                context=case.flow.context(case.g,case.r,policy=support.CONTEXT_POLICY)
                self.assertFalse(any(item['id']=='guide.'+name_field or item['id'].startswith('readiness.'+detail+'.')
                                     for item in context['reports']))
                comparison=build_comparison_profile(case.g,case.r)
                self.assertFalse(any(item['usable_as_report'] for item in comparison['facts']
                                     if item['native_ref']=='guide.'+name_field or item['native_ref'].startswith('readiness.'+detail+'.')))
                self.assertIsNone(out['assessment']['nextQuestion'])
                self.assertEqual(case.calls,[])

    def test_correcting_insurance_removes_old_work_date_target_and_stales_work_reports(self):
        case=self.fresh()
        case.task('timing')
        case.choice('RC01',choice='self')
        case.choice('T04',choice='soonest')
        case.choice('T05',choice='employer')
        out=case.choice('RC09',choice='my_job')
        self.assertEqual(out['assessment']['nextQuestion']['id'],'RC11')
        out=case.choice('T05',choice='medicaid')
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertTrue(case.r['facts']['RC09']['stale'])
        self.assertIsNone(case.r['natural']['dialogue']['lastTarget'])
        self.assertEqual(case.calls,[])

    def test_research_unknown_and_deferred_subject_buttons_do_not_repeat_who_question(self):
        for kind in ('research','unknown','defer'):
            with self.subTest(button=kind):
                case=self.fresh()
                case.task('compare')
                self.assertEqual(case.r['natural']['dialogue']['lastTarget']['id'],'RC01')
                out=case.choice('RC01',choice='research') if kind=='research' else case.turn({'type':kind,'id':'RC01'},aiConsent=False)
                self.assertNotEqual((out['assessment']['nextQuestion'] or {}).get('id'),'RC01')
                self.assertIsNone(case.flow.value(case.g,'subject.role'))
                self.assertEqual(case.calls,[])

    def test_active_item_field_target_is_preserved_even_with_an_existing_sibling_aggregate(self):
        case=self.fresh()
        case.task('drug_pricing')
        case.choice('RC01',choice='self')
        for number in (1,2):
            case.turn({'type':'choice','id':'RC22','entity':'medicine-'+str(number),
                'fields':{'name':'Example '+str(number),'strength':'5 mg','form':'tablet'}},aiConsent=False)
        case.turn({'type':'choice','id':'RC23','entity':'medicine-1',
            'fields':{'quantity':'30 tablets','daysSupply':'30'}},aiConsent=False)
        # An approved advisor target may choose the second medicine first. The
        # existing first-medicine fill must not redirect its visible controls.
        set_target(case.r,case.flow.question('RC23',['channel'],'medicine-2'))
        self.bind(case)
        question=case.flow.assess(case.g,case.r)['nextQuestion']
        self.assertEqual(question['entity'],'medicine-2')
        self.assertEqual([field['key'] for field in question['fields']],['channel'])
        out=case.turn({'type':'defer','id':'RC23'},aiConsent=False)
        self.assertEqual(metadata(case.r)['skippedDetails']['RC23.medicine-2.channel'],'deferred')
        self.assertNotIn('RC23.medicine-1.channel',metadata(case.r)['skippedDetails'])
        self.assertEqual(case.calls,[])

    def test_new_items_after_explicit_none_do_not_resurrect_retired_names_or_identity(self):
        for baseline,detail,prefix,key,none in (
                ('T06','RC21','doctor','practice','none'),('T07','RC22','medicine','name','no')):
            for same_name in (True,False):
                with self.subTest(question=baseline,same_name=same_name):
                    case=self.fresh()
                    case.task('providers' if detail=='RC21' else 'drug_pricing')
                    case.choice('RC01',choice='self')
                    old={key:'Old Example'}
                    old.update({'city':'Naples'} if detail=='RC21' else {'strength':'5 mg','form':'tablet'})
                    case.turn({'type':'choice','id':detail,'entity':prefix+'-1','fields':old},aiConsent=False)
                    case.choice(baseline,choice=none)
                    new={key:'Old Example' if same_name else 'New Example'}
                    new.update({'city':'Miami'} if detail=='RC21' else {'strength':'20 mg','form':'tablet'})
                    case.turn({'type':'choice','id':detail,'entity':'new','fields':new},aiConsent=False)
                    items=case.flow.report(case.r,detail)['items']
                    self.assertEqual(items,[{'entity':prefix+'-2','choice':'details',**new}])
                    field='needs.providers' if detail=='RC21' else 'needs.medications'
                    self.assertEqual(case.flow.value(case.g,field),new[key])
                    self.assertTrue(any(entry.get('triggerId')==detail and entry.get('previous',{}).get('items',[{}])[0].get(key)=='Old Example'
                                        for entry in case.r['history']))
                    self.assertEqual(case.calls,[])

    def test_no_items_buttons_retire_pending_item_clarifications_instead_of_reasking(self):
        for identifier,baseline,none in (('RC21','T06','none'),('RC22','T07','no'),('RC23','T07','no')):
            with self.subTest(detail=identifier):
                case,_,_=self.seed_pending_pair(identifier)
                out=case.choice(baseline,choice=none)
                self.assertIsNone(case.flow.pending_for(case.owner))
                self.assertIsNone(out['assessment']['nextQuestion'])
                self.assertTrue(case.r['facts'][identifier]['stale'])
                self.assertEqual(case.calls,[])

    def test_partial_field_buttons_and_submissions_resolve_only_the_supplied_pending_fields(self):
        scenarios=[
            ('RC11','profile',{'jobEnd':'March 2027','coverageEnd':'April 2027'}),
            ('RC16','profile',{'priorMedigap':'yes','start':'November 2025'}),
            ('RC22','medicine-1',{'strength':'20 mg','form':'capsule'}),
            ('RC23','medicine-1',{'daysSupply':'60','channel':'mail'}),
        ]
        for identifier,entity,fields in scenarios:
            with self.subTest(question=identifier):
                case=self.fresh()
                case.task('medigap' if identifier=='RC16' else 'timing' if identifier=='RC11' else 'drug_pricing')
                case.choice('RC01',choice='self')
                if identifier in {'RC22','RC23'}:
                    case.turn({'type':'choice','id':'RC22','entity':entity,
                        'fields':{'name':'Example','strength':'5 mg','form':'tablet'}},aiConsent=False)
                    if identifier=='RC23':
                        case.turn({'type':'choice','id':'RC23','entity':entity,
                            'fields':{'quantity':'30 tablets','daysSupply':'30','channel':'retail'}},aiConsent=False)
                    case.r['facts'][identifier]['stale']=True
                case.flow.queue_pending(case.owner,[{'id':identifier,'entity':entity,'fields':fields}],case.g,case.r)
                set_target(case.r,case.flow.question(identifier,list(fields),entity))
                self.bind(case)
                first,second=list(fields)
                out=case.turn({'type':'stage','id':identifier,'entity':entity,'fields':{first:fields[first]}},aiConsent=False)
                self.assertEqual(case.flow.pending_for(case.owner)['update']['fields'],{second:fields[second]})
                self.assertEqual([field['key'] for field in out['assessment']['nextQuestion']['fields']],[second])
                if identifier in {'RC22','RC23'}:
                    self.assertTrue(case.r['facts'][identifier]['stale'])
                    # The remaining proposal is not silently accepted.
                    item=case.r['facts'][identifier]['value']['items'][0]
                    self.assertNotEqual(item.get(second),fields[second])
                out=case.turn({'type':'stage','id':identifier,'entity':entity,'fields':{second:fields[second]}},aiConsent=False)
                self.assertIsNone(case.flow.pending_for(case.owner))
                if identifier in {'RC22','RC23'}:
                    self.assertFalse(case.r['facts'][identifier]['stale'])
                    item=case.flow.report(case.r,identifier)['items'][0]
                    self.assertTrue(all(item[key]==value for key,value in fields.items()))
                self.assertEqual(case.calls,[])

    def test_accepted_typed_no_items_retires_the_same_targets_as_the_buttons(self):
        for identifier,baseline,none,text in (
                ('RC21','T06','none','I do not have any doctors to include now.'),
                ('RC22','T07','no','I do not take any prescriptions now.'),
                ('RC23','T07','no','I do not take any prescriptions now.')):
            with self.subTest(detail=identifier):
                case,_,_=self.seed_pending_pair(identifier)
                out=case.message(text,[case.update(baseline,{'choice':none},text,correction=True)])
                self.assertIsNone(case.flow.pending_for(case.owner))
                self.assertNotIn((out['assessment']['nextQuestion'] or {}).get('id'),{'RC21','RC22','RC23','RC24'})
                self.assertTrue(case.r['facts'][identifier]['stale'])
                self.assertEqual(len(case.calls),2)  # Scripted in-process transport, never a provider call.

    def test_retiring_items_preserves_an_unrelated_pending_clarification(self):
        for typed in (False,True):
            with self.subTest(typed=typed):
                case,_,_=self.seed_pending_pair('RC22')
                case.flow.queue_pending(case.owner,[{'id':'RC11','entity':'profile','fields':{'coverageEnd':'April 2027'}}],case.g,case.r)
                text='I do not take any prescriptions now.'
                out=(case.message(text,[case.update('T07',{'choice':'no'},text,correction=True)])
                     if typed else case.choice('T07',choice='no'))
                self.assertEqual(case.flow.pending_for(case.owner)['update']['id'],'RC11')
                self.assertEqual(out['assessment']['nextQuestion']['id'],'RC11')
                self.assertNotIn('RC11',case.r['facts'])

    def test_ambiguous_current_medicare_path_selection_requests_clarification_without_mutation(self):
        for choices in ('original,advantage','advantage,original','advantage,medigap',
                        'medigap,advantage','medicaid,advantage,medigap'):
            with self.subTest(selection=choices):
                case=self.fresh()
                case.task('compare')
                case.choice('RC01',choice='self')
                case.choice('T05',choice='medicaid')
                before=copy.deepcopy((case.g,case.r,case.continuation))
                with self.assertRaisesRegex(ProfileError,'current coverage'):
                    case.choice('T05',choice=choices)
                self.assertEqual((case.g,case.r,case.continuation),before)
                self.assertEqual(case.calls,[])

    def test_other_reported_coverage_combinations_remain_supported_without_enrollment_inference(self):
        for choices in ('original,medigap,drug','advantage,medicaid','advantage,retiree',
                        'advantage,employer','original,medicaid','employer,medicaid'):
            with self.subTest(selection=choices):
                case=self.fresh()
                case.task('compare')
                case.choice('RC01',choice='self')
                out=case.choice('T05',choice=choices)
                self.assertEqual(case.flow.value(case.g,'coverage.current'),choices.split(','))
                self.assertNotIn('RC04',case.r['facts'])
                self.assertNotIn('RC19',case.r['facts'])
                self.assertFalse(out['assessment']['externalVerificationReady'])
                self.assertEqual(case.calls,[])

    def test_typed_ambiguous_current_paths_stay_pending_until_the_person_clarifies(self):
        case=self.fresh()
        case.task('compare')
        case.choice('RC01',choice='self')
        text='I have Original Medicare and Medicare Advantage now.'
        out=case.message(text,[case.update('T05',{'choice':'original,advantage'},text)])
        self.assertIsNone(case.flow.value(case.g,'coverage.current'))
        self.assertEqual(case.flow.pending_for(case.owner)['update']['id'],'T05')
        self.assertEqual(out['assessment']['nextQuestion']['id'],'T05')
        self.assertNotIn('RC04',case.r['facts'])
        self.assertEqual(len(case.calls),2)  # In-process scripted transport only.
        out=case.choice('T05',choice='advantage')
        self.assertEqual(case.flow.value(case.g,'coverage.current'),['advantage'])
        self.assertIsNone(case.flow.pending_for(case.owner))
        self.assertNotIn('RC04',case.r['facts'])

    def test_legacy_ambiguous_paths_are_held_without_rewriting_saved_values(self):
        for values in (['original','advantage'],['advantage','medigap']):
            with self.subTest(legacy=values):
                case=self.fresh()
                case.task('compare')
                case.choice('RC01',choice='self')
                case.choice('T05',choice='medicaid')
                # Simulate a retained profile predating the new finite gate.
                case.g['fields']['coverage.current']['value']=values
                self.bind(case)
                before=copy.deepcopy((case.g,case.r))
                assessment=case.flow.assess(case.g,case.r)
                self.assertEqual(assessment['nextQuestion']['id'],'T05')
                self.assertEqual(assessment['ruleDecisions']['T05']['state'],'conflicting')
                candidates=case.flow.eligible(case.owner,case.g,case.r)
                self.assertEqual([item['id'] for item in candidates],['T05'])
                self.assertTrue(candidates[0]['required'])
                context=case.flow.context(case.g,case.r,policy=support.CONTEXT_POLICY)
                self.assertFalse(any(item['id']=='guide.coverage.current' for item in context['reports']))
                self.assertIn({'id':'guide.coverage.current','status':'conflicting'},context['known'])
                profile=build_comparison_profile(case.g,case.r)
                fact=next(item for item in profile['facts'] if item['native_ref']=='guide.coverage.current')
                self.assertFalse(fact['usable_as_report'])
                self.assertEqual(fact['report_state'],'conflicting')
                self.assertEqual((case.g,case.r),before)
                out=case.choice('T05',choice='advantage')
                self.assertEqual(case.flow.value(case.g,'coverage.current'),['advantage'])
                self.assertNotEqual((out['assessment']['nextQuestion'] or {}).get('id'),'T05')
                profile=build_comparison_profile(case.g,case.r)
                self.assertFalse(any(issue['code']=='CURRENT_COVERAGE_PATH_AMBIGUOUS' for issue in profile['integrity_issues']))
                self.assertEqual(case.calls,[])


if __name__=='__main__':
    unittest.main()
