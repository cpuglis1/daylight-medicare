"""Ongoing-advisor state and request contracts; scripted transport, no paid AI.

These cases verify the interpreter/service/advisor handoffs. Scripted language is
not evidence that the real model reliably teaches or sounds conversational.
"""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_natural_flow as flow_tests
from natural_flow import CONTEXT_POLICY, PREVIOUS_CONTEXT_POLICY


class OngoingAdvisorTests(unittest.TestCase):
    # Reuse only the transport/visit harness, not the older test cases or its
    # legacy extraction fixtures. Every extraction below uses the new wire.
    setUp = flow_tests.NaturalFlowTests.setUp
    update = staticmethod(flow_tests.NaturalFlowTests.update)
    payload = flow_tests.NaturalFlowTests.payload
    take = flow_tests.NaturalFlowTests.take
    turn = flow_tests.NaturalFlowTests.turn
    message = flow_tests.NaturalFlowTests.message
    choice = flow_tests.NaturalFlowTests.choice
    stage_payloads = flow_tests.NaturalFlowTests.stage_payloads
    extracted_context = flow_tests.NaturalFlowTests.extracted_context
    composed_context = flow_tests.NaturalFlowTests.composed_context

    @staticmethod
    def extraction(updates=(), *, situations=(), goal='', facts=()):
        return {'updates': list(updates), 'requests': [], 'fact_ids': list(facts),
                'agenda': {'concerns': [], 'priorityReason': {}},
                'situation_proposals': list(situations), 'goal_quote': goal}

    @staticmethod
    def birthday(quote, *, year=None, subject='beneficiary', uncertain=False):
        return {'kind': 'age65', 'subject': subject, 'scope': 'intended',
                'quote': quote, 'uncertain': uncertain, 'correction': False,
                'month': 11, 'year': year, 'status': '', 'when': ''}

    @staticmethod
    def followup(target='T05', question='What health insurance do you have now?', **extra):
        return {'question_target': target, 'question': question,
                'reply': 'We can work through the next useful detail together.',
                'agenda_update': {'current_concern': 'enrollment timing', 'pause': False},
                **extra}

    @staticmethod
    def side_answer(**extra):
        return {'question_target': None, 'question': '',
                'reply': 'We can stay with this question before moving on.',
                'agenda_update': {'current_concern': 'coverage paths', 'pause': False},
                **extra}

    @staticmethod
    def teaching(concept, evidence, visual='none'):
        return {'purpose': 'teach', 'updates': [{'concept_id': concept,
                'depth': 'introduced', 'reason': 'new', 'evidence_refs': [evidence]}],
                'visual': visual}

    def open_enrollment(self, text=None):
        text = text or 'I am turning 65 years old in November and want to enroll in Medicare soon.'
        return self.message(text,
            extraction=self.extraction(
                [self.update('RC01', {'choice': 'self'}, text)],
                situations=[self.birthday(text)], goal='want to enroll in Medicare soon'),
            compose=self.followup())

    def memory_brief(self):
        return self.flow.memory.brief(self.owner, self.flow.current_chain[self.owner], CONTEXT_POLICY)

    def test_exact_birthday_variants_use_semantic_proposals_without_inferred_dates(self):
        variants = [
            'I am turning 65 years old in november and want to enroll in medicare soon',
            'Im turning 65 in november and am looking to understand my options',
        ]
        for text in variants:
            with self.subTest(text=text):
                self.setUp()
                out = self.message(text,
                    extraction=self.extraction(
                        [self.update('RC01', {'choice': 'self'}, text)],
                        situations=[self.birthday(text)]),
                    compose=self.followup())
                self.assertEqual(out['generated']['status'], 'complete')
                self.assertEqual(self.flow.value(self.g, 'situation.age65'), {'month': 11, 'year': None})
                self.assertEqual(self.flow.value(self.g, 'subject.role'), 'self')
                self.assertEqual(out['assessment']['nextQuestion']['id'], 'T05')
                for field in ('coverage.current', 'coverage.requestedStart', 'coverage.requestedStartMonth'):
                    self.assertNotIn(field, self.g['fields'])
                self.assertNotIn('RC04', self.r['facts'])
                self.assertNotIn('knowledge.general', self.g['fields'])

    def test_timing_answer_and_current_insurance_question_share_a_grounded_turn(self):
        self.open_enrollment()
        reply = ('The sign-up window and the date coverage starts are different. '
                 'Current insurance helps identify which timing questions matter.')
        out = self.message("I'm not sure, when should it start?",
            extraction=self.extraction(),
            compose=self.followup(reply=reply, evidence_refs=['enrollment_intro'],
                education=self.teaching('enrollment_timing', 'enrollment_intro')))
        self.assertEqual(out['generated'], {'status': 'complete', 'move': 'T05'})
        self.assertEqual(out['reply'], reply)
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T05')
        self.assertEqual(out['advisor']['teachingFactIds'], ['enrollment_intro'])
        self.assertTrue(out['advisor']['sources'])
        self.assertEqual(out['facts'], [], 'Do not repeat the reviewed lesson below generated prose.')
        sent = self.stage_payloads('daylight_resolved_conversation')[-1]
        self.assertIn('T05', {item['id'] for item in sent['question_candidates']})
        self.assertIn('enrollment_intro', {item['id'] for item in sent['resolved_context']['evidence']})
        self.assertEqual(len(self.calls), 4, 'A typed turn uses interpretation and advice, not a third planner.')

    def test_uncertain_coarse_goal_category_cannot_block_a_clear_enrollment_goal(self):
        text = 'I am turning 65 years old in november and want to enroll in medicare soon'
        goal = 'want to enroll in medicare soon'
        out = self.message(text,
            extraction=self.extraction([
                self.update('RC01', {'choice': 'self'}, text),
                self.update('T01', {'choice': 'compare'}, goal, uncertain=True)],
                situations=[self.birthday(text)], goal=goal),
            compose=self.followup())
        self.assertEqual(out['generated'], {'status': 'complete', 'move': 'T05'})
        candidates = self.stage_payloads('daylight_resolved_conversation')[-1]['question_candidates']
        targets = {item['id'] for item in candidates}
        self.assertIn('T05', targets)
        self.assertNotIn('T01', targets, 'A coarse category must not replace the stated practical purpose.')
        self.assertIsNone(self.flow.pending_for(self.owner))
        self.assertNotIn('intent.goal', self.g['fields'], 'Uncertain categorization is not a confirmed goal report.')
        self.assertEqual(self.memory_brief()['goal'], goal)
        self.assertEqual(self.flow.value(self.g, 'situation.age65'), {'month': 11, 'year': None})

        out = self.message("I'm not sure, when should it start?",
            extraction=self.extraction(),
            compose=self.followup(
                reply='The sign-up window and the date coverage starts are different.',
                evidence_refs=['enrollment_intro'],
                education=self.teaching('enrollment_timing', 'enrollment_intro')))
        self.assertEqual(out['generated'], {'status': 'complete', 'move': 'T05'})
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T05')
        self.assertEqual(self.composed_context()['advisor_brief']['goal'], goal)
        self.assertIsNone(self.flow.pending_for(self.owner))

    def test_educational_detour_preserves_goal_and_pending_question_in_ram(self):
        self.open_enrollment()
        self.message('What are the two Medicare paths?',
            extraction=self.extraction(),
            compose=self.side_answer(
                reply='Original Medicare and Medicare Advantage are two coverage routes with different rules and costs.',
                evidence_refs=['routesintro'],
                education=self.teaching('coverage_paths', 'routesintro', 'routes')))
        brief = self.memory_brief()
        self.assertEqual(brief['goal'], 'want to enroll in Medicare soon')
        self.assertEqual(brief['pending_question'], 'T05')
        self.assertEqual(brief['current_concern'], 'coverage paths')
        self.assertNotIn('knowledge.general', self.g['fields'], 'An educational question is not a familiarity report.')
        self.message('How does that affect keeping a doctor?',
            extraction=self.extraction(),
            compose=self.side_answer(agenda_update={'current_concern': 'keeping a doctor', 'pause': False}))
        context = self.composed_context()
        self.assertEqual(context['advisor_brief']['goal'], brief['goal'])
        self.assertEqual(context['advisor_brief']['pending_question'], 'T05')
        self.assertTrue(any('two Medicare paths' in item['user'] for item in context['recent_exchanges']))
        self.assertEqual(self.memory_brief()['pending_question'], 'T05')
        records = json.dumps({'guide': self.g, 'record': self.r})
        self.assertNotIn('want to enroll in Medicare soon', records)
        self.assertNotIn('keeping a doctor', records)
        self.assertNotIn('What are the two Medicare paths?', records)

    def test_explicit_pause_and_resume_preserve_the_same_practical_return_point(self):
        self.open_enrollment()
        out = self.message('Please pause the questions. I want to read for a moment.',
            extraction=self.extraction(),
            compose=self.side_answer(agenda_update={'current_concern': '', 'pause': True}))
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertTrue(self.memory_brief()['paused'])
        self.assertEqual(self.memory_brief()['pending_question'], 'T05')
        out = self.message("Okay, let's continue.", extraction=self.extraction(), compose=self.followup())
        self.assertTrue(self.composed_context()['advisor_brief']['paused'])
        self.assertFalse(self.memory_brief()['paused'])
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T05')
        self.assertEqual(self.memory_brief()['goal'], 'want to enroll in Medicare soon')

    def test_explicit_familiarity_reaches_advisor_without_replacing_enrollment_goal(self):
        for choice, text in (
                ('new', 'I know very little about Medicare.'),
                ('comfortable', 'I understand Medicare and feel comfortable with it.')):
            with self.subTest(familiarity=choice):
                self.setUp()
                self.open_enrollment()
                out = self.message(text,
                    extraction=self.extraction([
                        self.update('T02', {'choice': choice}, text, subject='learner')]),
                    compose=self.followup())
                brief = self.composed_context()['advisor_brief']
                self.assertEqual(brief['familiarity']['explicit_report'], choice)
                self.assertEqual(brief['goal'], 'want to enroll in Medicare soon')
                self.assertEqual(out['assessment']['nextQuestion']['id'], 'T05')
                self.assertNotIn('needs.priorities', self.g['fields'])
                self.assertNotIn('RC04', self.r['facts'])

    def test_v2_permission_never_receives_new_v3_history_or_working_goal(self):
        self.open_enrollment()
        out = self.message('What is Medicare?',
            extraction=self.extraction(facts=['basics']),
            compose=self.side_answer(), contextPolicy=PREVIOUS_CONTEXT_POLICY)
        self.assertEqual(out['generated']['status'], 'complete')
        for context in (self.extracted_context(), self.composed_context()):
            self.assertNotIn('recent_exchanges', context)
            self.assertNotIn('advisor_brief', context)
        self.assertEqual(self.memory_brief(), {})

    def test_research_only_report_keeps_education_open_without_personal_intake(self):
        text = 'I am only researching Medicare in general, not looking for coverage for a particular person.'
        out = self.message(text,
            extraction=self.extraction([
                self.update('RC01', {'choice': 'research'}, text)]),
            compose=self.side_answer(reply='Medicare is federal health insurance.', evidence_refs=['basics'],
                education=self.teaching('medicare_basics', 'basics')))
        self.assertEqual(self.flow.report(self.r, 'RC01')['choice'], 'research')
        self.assertIsNone(self.flow.value(self.g, 'subject.role'))
        self.assertEqual(out['generated']['status'], 'complete')
        self.assertIsNone(out['assessment']['nextQuestion'])
        self.assertTrue(out['assessment']['conversationOpen'])
        self.assertEqual(self.stage_payloads('daylight_resolved_conversation')[-1]['question_candidates'], [])
        self.assertTrue(self.composed_context()['advisor_brief']['research_only'])

        out = self.message('How do the two coverage routes differ?', extraction=self.extraction(),
            compose=self.side_answer(
                reply='Original Medicare and Medicare Advantage are two coverage routes with different rules and costs.',
                evidence_refs=['routesintro'],
                education=self.teaching('coverage_paths', 'routesintro', 'routes')))
        self.assertEqual(out['generated']['status'], 'complete')
        self.assertEqual(self.stage_payloads('daylight_resolved_conversation')[-1]['question_candidates'], [])
        self.assertIsNone(self.flow.pending_for(self.owner))
        for field in ('coverage.current', 'coverage.requestedStart', 'comparison.scope.zip'):
            self.assertNotIn(field, self.g['fields'])

    def test_birthday_correction_has_superseded_receipt_without_generic_rc28_intake(self):
        self.open_enrollment()
        self.choice('T04', choice='month', month='January 2027')
        self.choice('RC05', choice='details', month='May 2026')
        insurance = "My current health insurance is through my wife's current job."
        self.message(insurance, extraction=self.extraction([
            self.update('T05', {'choice': 'employer'}, insurance),
            self.update('RC09', {'choice': 'spouse_job'}, insurance)]),
            compose=self.followup('T03', 'What ZIP code do you live in?'))
        correction = 'Actually I turn 65 in December, not November.'
        concern = 'I want to understand my enrollment timing.'
        proposal = self.birthday(correction)
        proposal.update(month=12, correction=True)
        extracted = self.extraction([
            self.update('RC28', {'choice': 'different'}, correction, correction=True)],
            situations=[proposal])
        extracted['agenda']['concerns'] = [{'topic': 'timing', 'subject': 'beneficiary',
            'scope': 'current', 'status': 'open', 'quote': concern}]
        reply = ("Your 65th birthday is in December, not November. "
                 "Your health insurance is through your wife's current job.")
        out = self.message(correction + ' ' + concern, extraction=extracted,
            compose=self.followup('T03', 'What ZIP code do you live in?', reply=reply,
                report_refs=['guide.situation.age65', 'guide.coverage.current',
                             'readiness.RC09.profile.choice']))
        self.assertEqual(out['generated'], {'status': 'complete', 'move': 'T03'})
        self.assertEqual(out['reply'], reply)
        self.assertEqual(self.flow.value(self.g, 'situation.age65'), {'month': 12, 'year': None})
        self.assertNotIn('RC28', self.r['facts'])
        self.assertIn('RC28', self.flow.agent.local.rejected)
        self.assertIsNone(self.flow.pending_for(self.owner))
        context = self.composed_context()
        reports = {item['id']: item for item in context['reports']}
        self.assertEqual(reports['guide.situation.age65']['value'], {'month': 12, 'year': None})
        self.assertEqual(reports['readiness.RC09.profile.choice']['value'], 'spouse_job')
        self.assertFalse(any(ref.startswith('readiness.RC28.') or ref.startswith('readiness.RC05.')
                             for ref in reports))
        self.assertIn({'report_id': 'guide.situation.age65',
            'previous_value': {'month': 11, 'year': None},
            'current_value': {'month': 12, 'year': None}, 'status': 'superseded'},
            context['resolved_changes'])
        saved_records = json.dumps({'guide': self.g, 'record': self.r})
        self.assertNotIn('resolved_changes', saved_records)
        self.assertNotIn(reply, saved_records)
        self.assertNotIn('current_concern', saved_records)

    def test_model_contract_has_proposals_then_question_candidates_not_router_modes(self):
        self.open_enrollment()
        extraction_call, advisor_call = self.calls
        properties = extraction_call['text']['format']['schema']['properties']
        self.assertEqual(set(properties), {'updates', 'requests', 'fact_ids', 'agenda',
                                          'situation_proposals', 'goal_quote', 'education_request'})
        self.assertTrue({'mode', 'task', 'practical_request', 'move_id', 'reason_id'}.isdisjoint(properties))
        sent = json.loads(advisor_call['input'][0]['content'])
        self.assertIn('question_candidates', sent)
        self.assertNotIn('eligible_moves', sent)
        targets = {item['id'] for item in sent['question_candidates']}
        self.assertIn('T05', targets)
        self.assertTrue({'answer', 'teach', 'invite'}.isdisjoint(targets))
        self.assertTrue(all(item['purpose'] for item in sent['question_candidates']))
        evidence = {item['id'] for item in sent['resolved_context']['evidence']}
        self.assertIn('enrollment_intro', evidence, 'Useful teaching is available without an extractor-selected lesson.')
        output = advisor_call['text']['format']['schema']['properties']
        self.assertIn(None, output['question_target']['enum'])
        self.assertIn('T05', output['question_target']['enum'])
        self.assertNotIn('move_id', output)
        self.assertTrue(all(call['store'] is False and call['tools'] == [] for call in self.calls))

    def test_spouse_current_job_and_distinct_end_dates_remain_independent_reports(self):
        self.open_enrollment()
        text = "My current health insurance is through my wife's current job."
        self.message(text, extraction=self.extraction([
            self.update('T05', {'choice': 'employer'}, text),
            self.update('RC09', {'choice': 'spouse_job'}, text)]), compose=self.side_answer())
        self.assertEqual(self.flow.value(self.g, 'coverage.current'), ['employer'])
        self.assertEqual(self.flow.report(self.r, 'RC09')['choice'], 'spouse_job')
        self.assertNotIn('RC09', {item['id'] for item in self.stage_payloads('daylight_resolved_conversation')[-1]['question_candidates']})
        text = 'Her job ends in March 2027, and that health insurance ends in April 2027.'
        self.message(text, extraction=self.extraction([
            self.update('RC11', {'jobEnd': 'March 2027', 'coverageEnd': 'April 2027'}, text)]),
            compose=self.side_answer())
        report = self.flow.report(self.r, 'RC11')
        self.assertEqual(report['jobEnd'], '2027-03')
        self.assertEqual(report['coverageEnd'], '2027-04')
        self.assertEqual(self.flow.value(self.g, 'situation.age65'), {'month': 11, 'year': None})
        self.assertNotIn('coverage.requestedStartMonth', self.g['fields'])
        self.assertNotIn('RC04', self.r['facts'])

    def test_new_spouse_job_report_survives_the_next_compare_question_lens(self):
        self.open_enrollment()
        self.choice('T04', choice='month', month='January 2027')
        text = "My current health insurance is through my wife's current job."
        reply = "Your health insurance is through your wife's current job."
        out = self.message(text, extraction=self.extraction([
            self.update('T05', {'choice': 'employer'}, text),
            self.update('RC09', {'choice': 'spouse_job'}, text)]),
            compose=self.followup('T03', 'What ZIP code do you live in?',
                reply=reply, report_refs=['guide.coverage.current', 'readiness.RC09.profile.choice']))
        sent = self.stage_payloads('daylight_resolved_conversation')[-1]
        self.assertEqual(sent['question_candidates'][0]['id'], 'T03')
        reports = {item['id']: item for item in sent['resolved_context']['reports']}
        self.assertEqual(reports['readiness.RC09.profile.choice']['value'], 'spouse_job')
        self.assertEqual(reports['guide.coverage.current']['value'], ['employer'])
        self.assertNotIn('guide.coverage.requestedStartMonth', reports,
                         'The fresh-report delta must not attach unrelated older timing values.')
        self.assertEqual(out['generated'], {'status': 'complete', 'move': 'T03'})
        self.assertEqual(out['reply'], reply)

    def test_finite_spouse_job_send_uses_the_same_report_delta_with_one_model_call(self):
        self.choice('RC01', choice='self')
        self.choice('T05', choice='employer')
        self.choice('T04', choice='month', month='January 2027')
        reply = "Your health insurance is through your spouse's current job."
        self.compositions.append(self.followup('T03', 'What ZIP code do you live in?',
            reply=reply, report_refs=['guide.coverage.current', 'readiness.RC09.profile.choice']))
        out = self.turn({'type': 'choice', 'id': 'RC09', 'fields': {'choice': 'spouse_job'}})
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0]['text']['format']['name'], 'daylight_resolved_conversation')
        sent = self.stage_payloads('daylight_resolved_conversation')[-1]
        self.assertEqual(sent['question_candidates'][0]['id'], 'T03')
        reports = {item['id']: item for item in sent['resolved_context']['reports']}
        self.assertEqual(reports['readiness.RC09.profile.choice']['value'], 'spouse_job')
        self.assertNotIn('guide.coverage.requestedStartMonth', reports)
        self.assertIn('readiness.RC09.profile.choice',
                      sent['resolved_context']['submitted_answer']['report_refs'])
        self.assertEqual(out['generated'], {'status': 'complete', 'move': 'T03'})
        self.assertEqual(out['reply'], reply)

    def test_new_job_end_dates_include_prior_worker_relationship_under_compare_lens(self):
        self.open_enrollment()
        self.choice('T04', choice='month', month='January 2027')
        insurance = "My current health insurance is through my wife's current job."
        self.message(insurance, extraction=self.extraction([
            self.update('T05', {'choice': 'employer'}, insurance),
            self.update('RC09', {'choice': 'spouse_job'}, insurance)]),
            compose=self.followup('T03', 'What ZIP code do you live in?'))
        text = 'Her job ends in March 2027, and that health insurance ends in April 2027.'
        reply = "Your wife's job ends in March 2027, and that health insurance ends in April 2027."
        out = self.message(text, extraction=self.extraction([
            self.update('RC11', {'jobEnd': 'March 2027', 'coverageEnd': 'April 2027'}, text)]),
            compose=self.followup('T03', 'What ZIP code do you live in?', reply=reply,
                report_refs=['readiness.RC11.profile.jobEnd', 'readiness.RC11.profile.coverageEnd',
                             'readiness.RC09.profile.choice', 'guide.coverage.current']))
        sent = self.stage_payloads('daylight_resolved_conversation')[-1]
        self.assertEqual(sent['question_candidates'][0]['id'], 'T03')
        reports = {item['id']: item for item in sent['resolved_context']['reports']}
        self.assertEqual(reports['readiness.RC09.profile.choice']['value'], 'spouse_job')
        self.assertEqual(reports['readiness.RC11.profile.jobEnd']['value'], '2027-03')
        self.assertEqual(reports['readiness.RC11.profile.coverageEnd']['value'], '2027-04')
        self.assertNotIn('guide.coverage.requestedStartMonth', reports,
                         'Relational support must not expand into all prior timing values.')
        self.assertEqual(out['generated'], {'status': 'complete', 'move': 'T03'})
        self.assertEqual(out['reply'], reply)

    def test_desired_start_does_not_fill_unknown_birthday_year(self):
        self.open_enrollment()
        text = 'I want Medicare coverage to start in January 2027.'
        self.message(text, extraction=self.extraction([
            self.update('T04', {'choice': 'month', 'month': 'January 2027'}, text)]),
            compose=self.followup())
        self.assertEqual(self.flow.value(self.g, 'coverage.requestedStartMonth'), '2027-01')
        self.assertEqual(self.flow.value(self.g, 'situation.age65'), {'month': 11, 'year': None})
        self.assertNotIn('RC04', self.r['facts'])

    def test_helpers_own_birthday_never_becomes_beneficiary_circumstance(self):
        for subject in ('learner', 'beneficiary'):
            with self.subTest(proposed_subject=subject):
                self.setUp()
                text = 'This is for my father. I am turning 65 years old in November.'
                quote = 'I am turning 65 years old in November.'
                out = self.message(text,
                    extraction=self.extraction([
                        self.update('RC01', {'choice': 'someone'}, 'This is for my father.')],
                        situations=[self.birthday(quote, subject=subject)]),
                    compose=self.side_answer())
                self.assertEqual(out['generated']['status'], 'complete')
                self.assertEqual(self.flow.value(self.g, 'subject.role'), 'someone')
                self.assertNotIn('situation.age65', self.g['fields'])
                self.assertFalse(any(item['id'] == 'guide.situation.age65'
                                     for item in self.composed_context()['reports']))

    def test_tentative_circumstance_does_not_discard_clear_same_message_report(self):
        text = 'This is for me. I think I am turning 65 in November.'
        out = self.message(text,
            extraction=self.extraction([
                self.update('RC01', {'choice': 'self'}, 'This is for me.')],
                situations=[self.birthday('I think I am turning 65 in November.', uncertain=True)]),
            compose=self.side_answer())
        self.assertEqual(self.flow.value(self.g, 'subject.role'), 'self')
        self.assertNotIn('situation.age65', self.g['fields'])
        self.assertTrue(self.flow.pending_for(self.owner))
        self.assertNotIn('guide.situation.age65', {item['id'] for item in self.composed_context()['reports']})
        self.assertNotIn('review', out)

    def test_uncertain_helper_birthday_cannot_taint_a_clear_beneficiary_birthday(self):
        for helper_subject in ('learner', 'beneficiary'):
            with self.subTest(proposed_helper_subject=helper_subject):
                self.setUp()
                beneficiary = 'My father turns 65 in November.'
                helper = 'I think I turn 65 in December.'
                text = 'This is for my father. ' + beneficiary + ' ' + helper
                helper_proposal = self.birthday(helper, subject=helper_subject, uncertain=True)
                helper_proposal['month'] = 12
                out = self.message(text,
                    extraction=self.extraction([
                        self.update('RC01', {'choice': 'someone'}, 'This is for my father.')],
                        situations=[self.birthday(beneficiary), helper_proposal]),
                    compose=self.side_answer())
                self.assertEqual(out['generated']['status'], 'complete')
                self.assertEqual(self.flow.value(self.g, 'subject.role'), 'someone')
                self.assertEqual(self.flow.value(self.g, 'situation.age65'), {'month': 11, 'year': None})
                self.assertIsNone(self.flow.pending_for(self.owner))
                reports = {item['id']: item for item in self.composed_context()['reports']}
                self.assertEqual(reports['guide.situation.age65']['value'], {'month': 11, 'year': None})


if __name__ == '__main__':
    unittest.main()
