"""Task/verification/outcome contracts with fictional input and no model calls."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from task_work import (CHECK_IDS, VERSION, attach_result, build_context, empty_record,
    neutral_selection, plan, unsupported_action_claim, validate_record)
from advisor_memory import CONTEXT_POLICY, VisitMemory


def context(*reports, task='providers', goal='Can I see this doctor with my coverage?'):
    return {'task': task, 'reports': list(reports), 'known': [],
        'advisor_brief': {'goal':goal, 'reported_goal':'compare', 'pending_question':'RC21',
            'decision':{'practical_focus':'doctors'}},
        'education_context': {'learning': {'covered':[]}, 'current_clarification':[]}}


def selection(*checks, blockers=(), step='answer'):
    return {'check_ids':list(checks), 'blocking_concepts':list(blockers), 'next_step':step}


class TaskWorkTests(unittest.TestCase):
    def test_exact_plan_office_service_and_payment_are_separate_checks(self):
        current = context({'id':'guide.coverage.current','status':'reported','value':['advantage']},
                          {'id':'readiness.RC21.items.doctor-1.practice','status':'reported','value':'Fictional office'})
        before = copy.deepcopy(current)
        record, result = plan(current, selection('coverage_identity','provider_identity',
            'provider_participation','service_benefit'))
        self.assertEqual(current, before)
        self.assertEqual(len(result['checks']), 4)
        for check in result['checks']:
            self.assertEqual(check['verification_state'], 'not_verified')
            self.assertEqual(check['execution_state'], 'not_started')
            self.assertTrue(check['next_step'])
        self.assertFalse(result['task_resolved'])
        self.assertEqual(result['supported_findings'], [])
        self.assertNotIn('Fictional office', str(record))
        self.assertNotIn('Fictional office', str(result))

    def test_missing_context_does_not_mean_missing_user_data_or_noncoverage(self):
        snapshot = build_context(context())
        for check in snapshot['checks']:
            self.assertEqual(check['input_state'], 'not_in_current_context')
            self.assertEqual(check['verification_state'], 'not_verified')
        self.assertEqual(snapshot['active_checks'], [])
        self.assertEqual(len(snapshot['checks']), len(CHECK_IDS))

    def test_report_unknown_and_deferred_are_not_verified_or_zero(self):
        current = context()
        current['known'] = [{'id':'readiness.RC25.amount','status':'deferred'},
                            {'id':'guide.coverage.current','status':'unknown'}]
        _, result = plan(current, selection('personal_cost','coverage_identity'))
        checks = {row['check_id']:row for row in result['checks']}
        self.assertEqual(checks['personal_cost']['input_states'], ['deferred'])
        self.assertEqual(checks['coverage_identity']['input_states'], ['unknown'])
        self.assertNotIn('amount', checks['personal_cost'])
        self.assertFalse(result['task_resolved'])

    def test_ongoing_connections_survive_a_teaching_detour_without_a_second_goal_copy(self):
        current = context()
        first, _ = plan(current, selection('provider_participation'))
        second, result = plan(current, selection('personal_cost', step='teach'), first)
        self.assertEqual(second['selection']['check_ids'], ['provider_participation','personal_cost'])
        self.assertEqual(result['return_point'], 'RC21')
        self.assertNotIn(current['advisor_brief']['goal'], str(first))
        public = build_context(current, second)
        self.assertNotIn(second['task_binding'], str(public))
        self.assertEqual(public['active_checks'], ['provider_participation','personal_cost'])

    def test_changed_explicit_goal_drops_earlier_task_connections(self):
        current = context()
        first, _ = plan(current, selection('provider_participation'))
        current['advisor_brief']['goal'] = 'Help me understand enrollment timing instead.'
        second, result = plan(current, selection('enrollment_timing'), first)
        self.assertEqual(second['selection']['check_ids'], ['enrollment_timing'])
        self.assertEqual(len(result['checks']), 1)

    def test_several_consequential_connections_accumulate_without_becoming_a_universal_form(self):
        current = context()
        first, _ = plan(current, selection('coverage_identity','provider_identity',
                                         'provider_participation','service_benefit'))
        second, result = plan(current, selection('personal_cost'), first)
        self.assertEqual(len(second['selection']['check_ids']), 5)
        self.assertEqual(validate_record(second),second)
        self.assertEqual(len(result['checks']), 5)
        self.assertNotIn('enrollment_timing', second['selection']['check_ids'])

    def test_caregiver_task_can_connect_practical_help_without_inferring_permission_or_eligibility(self):
        current = context({'id':'guide.subject.role','status':'reported','value':'helper'},
            goal='I need help for my mother with transport and costs.')
        _, result = plan(current, selection('help_and_logistics','personal_cost'))
        help_check = result['checks'][1]
        self.assertEqual(help_check['check_id'],'help_and_logistics')
        self.assertIn('does not establish permission',help_check['distinction'])
        self.assertEqual(help_check['verification_state'],'not_verified')
        self.assertEqual(result['completed_external_actions'],[])
        self.assertFalse(result['task_resolved'])

    def test_invalid_work_record_cannot_partially_mutate_visit_memory(self):
        memory = VisitMemory()
        record, _ = plan(context(), selection('personal_cost'))
        memory.remember('owner','visit',CONTEXT_POLICY,'Question','Response','',task_work_record=record)
        malformed = {**record,'selection':{'verified':True}}
        with self.assertRaises(ValueError):
            memory.remember('owner','visit',CONTEXT_POLICY,'Changed','Changed','',task_work_record=malformed)
        self.assertEqual(memory.task_work('owner','visit',CONTEXT_POLICY),record)

    def test_blocking_teaching_is_grounded_in_current_confusion_not_a_model_flag(self):
        current = context()
        current['education_context']['current_clarification'] = ['medicare_advantage']
        record, result = plan(current, selection('provider_participation',
            blockers=['medicare_advantage','cost_components'], step='teach'),
            accepted_teaching=[{'concept_id':'medicare_advantage','depth':'introduced'}])
        self.assertEqual(record['selection']['blocking_concepts'], ['medicare_advantage'])
        self.assertEqual(result['teaching'], [{'concept_id':'medicare_advantage',
            'state':'explanation_delivered_not_comprehension'}])
        self.assertEqual(result['return_point'], 'RC21')
        self.assertFalse(result['task_resolved'])

    def test_pause_retains_open_work_and_can_resume(self):
        current = context()
        first, paused = plan(current, selection('personal_cost'), paused=True)
        self.assertEqual(paused['next_step'], 'pause')
        _, resumed = plan(current, selection(step='answer'), first, paused=False)
        self.assertEqual(resumed['next_step'], 'answer')
        self.assertEqual(resumed['checks'][0]['check_id'], 'personal_cost')

    def test_invalid_agent_metadata_cannot_manufacture_outcomes(self):
        for proposed in ({'check_ids':['personal_cost'],'blocking_concepts':[],
                          'next_step':'answer','verified':True},
                         selection('made_up_check'), selection(*CHECK_IDS)):
            record, result = plan(context(), proposed)
            self.assertEqual(record['selection'], neutral_selection())
            self.assertFalse(result['task_resolved'])

    def test_local_receipt_is_separate_from_outside_work_and_requires_validity(self):
        record, planned = plan(context(), selection('provider_participation'))
        out = {'preparation': {'id':'fixture:prepared'}, 'task_work':planned}
        attach_result(out, record, action='run_preparation', preparation_valid=True)
        self.assertEqual(out['task_work']['outcome'], 'preparation_completed')
        self.assertEqual(out['task_work']['completed_external_actions'], [])
        self.assertFalse(out['task_work']['task_resolved'])
        self.assertEqual(out['task_work']['checks'][0]['verification_state'], 'not_verified')
        denied = {'preparation':{'id':'fixture:prepared'}}
        attach_result(denied, record, action='run_preparation', preparation_valid=False)
        self.assertNotIn('local_operation', denied['task_work'])

    def test_failed_or_historical_turn_does_not_reissue_work_as_a_current_result(self):
        record, planned = plan(context(), selection('provider_participation'))
        out = {'task_work':planned}
        attach_result(out, record, historical=True)
        self.assertNotIn('task_work', out)
        out = {'task_work':planned,'generated':{'status':'unavailable'}}
        attach_result(out, record)
        self.assertNotIn('task_work', out)

    def test_visit_work_is_owner_chain_permission_expiry_and_deletion_bound(self):
        now = [0]
        memory = VisitMemory(clock=lambda:now[0])
        record, _ = plan(context(), selection('provider_participation'))
        memory.remember('owner','visit',CONTEXT_POLICY,'Fictional question','Fictional response','',
                        task_work_record=record)
        self.assertEqual(memory.task_work('owner','visit',CONTEXT_POLICY), record)
        self.assertEqual(memory.task_work('other','visit',CONTEXT_POLICY), empty_record())
        self.assertEqual(memory.task_work('owner','other',CONTEXT_POLICY), empty_record())
        now[0] = 3601
        self.assertEqual(memory.task_work('owner','visit',CONTEXT_POLICY), empty_record())
        memory.remember('owner','visit',CONTEXT_POLICY,'Question','Response','',task_work_record=record)
        memory.forget_owner('owner')
        self.assertEqual(memory.task_work('owner','visit',CONTEXT_POLICY), empty_record())
        memory.remember('owner','visit',CONTEXT_POLICY,'Question','Response','',task_work_record=record)
        self.assertEqual(memory.task_work('owner','visit','natural-context-v2'), empty_record())

    def test_no_unsupported_completed_contact_or_callback_promise(self):
        for text in ("I called the office.", "We've just sent your referral.",
                     "I will call you tomorrow.", "I'll get back to you.",
                     'We booked your appointment.', 'I requested a referral.',
                     'We identified your exact plan.', 'We have matched the office.'):
            self.assertTrue(unsupported_action_claim(text), text)
        for text in ("I haven't called the office.", 'You can ask the office.',
                     'I can help prepare questions.', "I'll explain what to ask.",
                     'We can work through this together.'):
            self.assertFalse(unsupported_action_claim(text), text)


if __name__ == '__main__':
    unittest.main()
