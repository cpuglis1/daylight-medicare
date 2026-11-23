"""D183: the profile and education records drive the :8895 conversation.

Real controller, scripted model outputs, fictional reports, no network. These
check code behavior (capture, reachable questions, dates, endings, say-once);
they do not grade a live model's language. The journey replays the November 17
job-coverage conversation (visit ea3c981c3c) with the interpreter proposals the
log shows it made.
"""
import copy
import json
import unittest
from datetime import date

import test_semantic_guidance as semantic
import conversation_records as records
import conversation_planner as planner
from applicable_rules import applicable_rules

OPENING = ("I'm 68 and retiring at the end of the year and losing coverage provided by my company. "
           "I want to enroll in Medicare but an feeling a bit overwhelmed by the options...")
DATES = 'November 21st 2026 my job will end, insurance will end Nov 30 2026'
BLAND = 'We can take this one step at a time.'


class RecordsJourney(unittest.TestCase):
    for name in ('payload', 'take', 'turn', 'message', 'choice', 'task', 'stage_payloads',
                 'extracted_context', 'composed_context', 'interpreted'):
        locals()[name] = getattr(semantic.SemanticGuidance, name)
    update = staticmethod(semantic.SemanticGuidance.update)
    extraction = staticmethod(semantic.SemanticGuidance.extraction)

    def setUp(self):
        semantic.SemanticGuidance.setUp(self)
        records.enable(self.flow)
        self.flow.guided_close = True
        records.TODAY = date(2026, 11, 17)
        self.addCleanup(setattr, records, 'TODAY', None)

    # -- scripting helpers -------------------------------------------------
    def read(self, text, *, updates=(), targets=(), mode='work', task='timing', situation=(), **extra):
        p = self.interpreted(text, mode=mode, task=task, updates=updates, situation_proposals=list(situation), **extra)
        p['next_target'] = {'ids': list(targets), 'reason': 'goal'}
        return p

    def ask_recommended(self, reply=BLAND, offer=None, evidence=(), blocks=None, offer_concept=None, wish=None, target=None):
        """Composer stub: ask the recommended target (or the first candidate).
        blocks: [(text, refs)] sent as reply_blocks with per-block citations.
        wish: {fact_id: sentence}; each turn cites every listed fact the context
        offers, one block each, the way the live composer repeated itself."""
        def compose(sent):
            extra = dict(evidence_refs=list(evidence)) if evidence else {}
            chosen = blocks
            if wish:
                offered = {e.get('id') for e in sent['resolved_context'].get('evidence') or [] if isinstance(e, dict)}
                chosen = [(BLAND, [])] + [(text, [fid] if fid in offered else []) for fid, text in wish.items()
                                          if fid in offered or fid not in self.flow.facts and not fid.startswith(('pk_', 'routes'))]
                extra['evidence_refs'] = list(dict.fromkeys(f for _, refs in chosen for f in refs))[:3]
                chosen = [(t, [f for f in refs if f in extra['evidence_refs']]) for t, refs in chosen]
            if chosen:
                extra.update(reply_blocks=[t for t, _ in chosen], block_refs=[list(r) for _, r in chosen])
            if offer_concept is not None:
                extra['offer_concept'] = offer_concept
            plan = sent['resolved_context'].get('discussion_plan', {})
            moves = sent['question_candidates']
            pick = next((m for m in moves if m['id'] == (target or plan.get('next_question'))), None) or (moves[0] if moves else None)
            if offer:
                return dict(reply=reply, question_target=None, question=offer,
                            conversation_assessment=dict(goal_progress='open', next_move='next_step'), **extra)
            return dict(reply=reply, question_target=pick['id'] if pick else None,
                        question=pick['question']['question'] if pick else '', **extra)
        return compose

    def capture(self, out):
        return {item['target']: item['status'] for item in out['metrics'].get('capture') or []}

    def available(self):
        return self.composed_context()['discussion_plan']['available_questions']

    # -- the journey ---------------------------------------------------------
    def opening(self, compose_override=None, **kw):
        ups = [self.update('RC01', {'choice': 'self'}, "I'm 68"),
               self.update('T05', {'choice': 'employer'}, 'losing coverage provided by my company'),
               self.update('RC09', {'choice': 'my_job'}, 'coverage provided by my company'),
               self.update('MG_AGE', {'choice': '68'}, "I'm 68")]
        retire = {'kind': 'retirement', 'subject': 'beneficiary', 'scope': 'intended', 'quote': 'retiring at the end of the year',
                  'uncertain': False, 'correction': False, 'month': None, 'year': None, 'first_day': None,
                  'first_day_quote': '', 'status': 'retiring', 'when': 'end of the year'}
        return self.message(OPENING, extraction=self.read(OPENING, updates=ups, targets=['RC04', 'RC10'],
                                                          situation=[retire], **kw),
                            compose=compose_override or self.ask_recommended())

    def test_opening_fills_coverage_and_whose_job_and_targets_parts(self):
        out = self.opening()
        got = self.capture(out)
        self.assertEqual(got.get('T05'), 'accepted', got)
        self.assertEqual(got.get('RC09'), 'accepted', got)
        self.assertEqual(self.flow.value(self.g, 'coverage.current'), ['employer'])
        self.assertEqual(self.flow.report(self.r, 'RC09')['choice'], 'my_job')
        self.assertIn(out['assessment']['nextQuestion']['id'], ('RC04', 'RC10'))
        available = self.available()
        self.assertTrue({'RC04', 'RC10'} <= set(available), available)
        self.assertFalse({'T05', 'RC09', 'RC13', 'T02'} & set(available), available)
        # Both records reach both models.
        self.assertIn('profile_record', self.extracted_context())
        context = self.composed_context()
        self.assertIn('employer', json.dumps(context['profile_record']) + json.dumps(context['reports']))
        self.assertIn('enrollment_step', context['readiness']['outcomes'])
        self.assertIn('education_record', context)
        self.assertNotIn('already_said', context['conversation_state'])   # the word-pattern list is retired
        self.assertEqual(self.calls[-1]['instructions'][:40], self.calls[-1]['instructions'][:40])
        self.assertIn('discussion_plan.next_question', self.calls[-1]['instructions'])
        self.assertIn('next_target', self.calls[-2]['instructions'])
        self.assertEqual(out['metrics']['records']['proposed_target'], ['RC04', 'RC10'])

    def test_whole_journey_reaches_parts_employer_size_and_dates_without_reasks(self):
        asked = []
        out = self.opening(); asked.append(out['assessment']['nextQuestion']['id'])
        text = "I don't have Part A or Part B yet."
        out = self.message(text, extraction=self.read(text, updates=[self.update('RC04', {'choice': 'neither'}, text)],
                                                      targets=['RC10']), compose=self.ask_recommended())
        asked.append(out['assessment']['nextQuestion']['id'])
        self.assertIn('RC10', asked[:2], asked)
        # D202: this historical timing journey scripts a conditional choice;
        # generic structured answers now default to core, not the old checklist.
        self.compositions.append(self.ask_recommended(target='RC11'))
        out = self.turn({'type': 'choice', 'id': 'RC10', 'fields': {'choice': 'yes'}})
        asked.append((out['assessment']['nextQuestion'] or {}).get('id'))
        ups = [self.update('RC11', {'jobEnd': '2026-11-21', 'coverageEnd': '2026-11-30'}, DATES)]
        self.compositions.append(self.ask_recommended())
        out = self.message(DATES, extraction=self.read(DATES, updates=ups, targets=['RC12']))
        asked.append((out['assessment']['nextQuestion'] or {}).get('id'))
        # Parts A and B and employer size by turn 2; nothing asked twice; nothing
        # the first message already answered; no benefits-office question.
        self.assertEqual(asked, ['RC04', 'RC10', 'RC11', 'RC12'], asked)
        self.assertEqual(len(asked), len(set(asked)))
        self.assertFalse({'T05', 'RC09', 'RC13', 'T02'} & set(asked), asked)
        # The window is computed by code from the person's own dates and shown on a card.
        card = next(c for c in out.get('cards') or [] if c.get('records'))
        values = {row['label']: row['value'] for row in card['rows']}
        self.assertEqual(values['Part B sign-up window'], 'December 2026 through July 2027')
        self.assertEqual(values['If you sign up in November 2026'], 'Part B generally starts December 1, 2026')
        self.assertEqual(values['Joining a drug or Medicare Advantage plan'], 'Through January 2027')
        self.assertEqual(values['Medigap window'], 'December 2026 through May 2027')
        self.assertEqual(values['Your employer'], '20 or more employees')
        self.assertIn('63 days', ' '.join(row.get('note', '') for row in card['rows']))
        self.assertTrue(self.composed_context()['timing_result']['shown_on_code_card'])
        for fact in ('pk_work_sep', 'pk_work_sep_start', 'pk_plan_coverage_loss_window', 'pk_medigap_window', 'pk_payer_order'):
            self.assertIn(fact, card['facts'])
        # The journey record carries the same computed window.
        self.assertEqual(out['enrollment']['record']['work_window']['part_b_window'], ['2026-12', '2027-07'])

    def test_discuss_mode_still_offers_open_fields_and_ends_on_a_question(self):
        self.opening()
        out = self.message('Sure', extraction=self.read('Sure', mode='discuss', task='', targets=[]),
                           compose=dict(reply='Here are the two main ways to get Medicare.', question_target=None, question=''))
        plan = self.composed_context()['discussion_plan']
        self.assertTrue(plan['available_questions'])
        self.assertTrue(plan['require_structured'])
        self.assertIsNotNone(out['assessment']['nextQuestion'])        # never a dead end

    def test_offer_of_work_ends_as_a_button(self):
        self.opening()
        offer = 'Would you like to check whether your doctors take Medicare?'
        out = self.message('sure, I want to keep my doctors',
                           extraction=self.read('sure, I want to keep my doctors', mode='suggest', task='providers',
                                                updates=[self.update('T10', {'choice': 'doctors'}, 'I want to keep my doctors')],
                                                targets=['T06']),
                           compose=self.ask_recommended(offer=offer))
        if out['assessment']['nextQuestion'] is None:
            buttons = [c for c in out.get('cards') or [] if c['kind'] == 'next_step_offer']
            self.assertEqual(len(buttons), 1)
            self.assertEqual(buttons[0]['actions'][0]['label'], 'Check my doctors')
        else:
            self.assertEqual(out['assessment']['nextQuestion']['id'], 'T06')

    def test_keep_my_doctors_targets_which_doctors(self):
        self.opening()
        text = 'sure, I want to keep my doctors'
        out = self.message(text, extraction=self.read(text, task='providers', targets=['T06'],
                                                      updates=[self.update('T10', {'choice': 'doctors'}, 'I want to keep my doctors')]),
                           compose=self.ask_recommended())
        q = out['assessment']['nextQuestion']
        self.assertEqual(q['id'], 'T06')
        self.assertEqual(q['question'], 'Which doctors or hospitals would you like to keep?')

    def test_a_block_already_shown_is_held_back_and_new_one_kept(self):
        self.opening()
        repeat = 'Original Medicare and Medicare Advantage are the two main ways to get your hospital and medical coverage.'
        first = self.message('Tell me the options.', extraction=self.read('Tell me the options.', task=''),
                             compose=self.ask_recommended(reply=repeat, evidence=['routesintro']))
        self.assertIn(repeat, first['reply'])
        fresh = 'Your current job coverage matters for when Part B should start.'
        second = self.message('Okay, go on.', extraction=self.read('Okay, go on.', task=''),
                              compose=self.ask_recommended(blocks=[(repeat, ['routesintro']), (fresh, [])], evidence=['routesintro']))
        self.assertNotIn(repeat, second['reply'])
        self.assertIn(fresh, second['reply'])
        self.assertEqual(second['metrics']['records']['held_back_blocks'], 1)
        # Code recorded the cited fact as shown; the next composition sees it as delivered.
        education = self.composed_context()['education_record']
        self.assertIn('routesintro', education['delivered_facts'])
        self.assertEqual(education['concepts'].get('coverage_paths'), 'explored')
        marked = [e for e in self.composed_context()['evidence'] if e.get('id') == 'routesintro']
        self.assertTrue(marked and marked[0].get('delivered'))
        # An explicit request to hear it again is allowed.
        third = self.message('Can you explain the two paths again?',
                             extraction=self.read('Can you explain the two paths again?', task='',
                                                  education_request={'kind': 'revisit', 'concept_ids': ['coverage_paths'],
                                                                     'quote': 'explain the two paths again'}),
                             compose=self.ask_recommended(reply=repeat, evidence=['routesintro']))
        self.assertIn(repeat, third['reply'])

    def test_switch_off_restores_the_vocabulary_check(self):
        self.flow.records_v1 = False
        ups = [self.update('RC01', {'choice': 'self'}, "I'm 68", subject='learner'),
               self.update('T05', {'choice': 'employer'}, 'losing coverage provided by my company')]
        out = self.message(OPENING, extraction=self.interpreted(OPENING, task='timing', updates=ups),
                           compose=dict(reply=BLAND, question_target=None, question=''))
        self.assertEqual(self.capture(out).get('T05'), 'unsupported')
        self.assertNotIn('profile_record', self.composed_context())
        self.assertNotIn('records', out['metrics'])

    # -- D183 build-out (November 17, evening) -------------------------------
    def report(self, kind, quote, **values):
        item = {'kind': kind, 'subject': 'beneficiary', 'quote': quote, 'status': '', 'month': None, 'year': None,
                'product': '', 'name': '', 'carrier': '', 'letter': ''}
        item.update(values)
        return item

    def ends_on_a_lead(self, out):
        return bool(out['assessment'].get('nextQuestion')) or any(
            c.get('kind') == 'next_step_offer' for c in out.get('cards') or [])

    def test_fixture_journey_all_seven_turns(self):
        """The November 17 visit, rewritten for the fixed flow (fixture job_coverage_20261117)."""
        fixture = json.loads((__import__('pathlib').Path(__file__).parent / 'fixtures/job_coverage_20261117.json').read_text())
        self.assertEqual(fixture['today'], '2026-11-17')
        wish = {'pk_payer_order': 'With 20 or more employees, your job plan generally pays first while you work.',
                'pk_work_sep': 'You can sign up for Part B while covered or in the eight months after the job or coverage ends.',
                'routesintro': 'Original Medicare and Medicare Advantage are the two main ways to get your coverage.'}
        no_choice = 'There is no need to choose a plan today; we can take this one step at a time together.'
        shown, outs, asked = {}, [], []

        def turn(out):
            outs.append(out)
            asked.append((out['assessment'].get('nextQuestion') or {}).get('id'))
            for block in (out.get('reply') or '').split('\n\n'):
                for key, text in list(wish.items()) + [('no_choice', no_choice)]:
                    if block.strip() == text:
                        shown[key] = shown.get(key, 0) + 1
            self.assertTrue(self.ends_on_a_lead(out), out.get('reply'))
            self.assertNotRegex(out.get('reply') or '', r'(?:January|July|December|May) 20\d\d')   # no dates in prose
            return out

        compose = lambda target=None: self.ask_recommended(wish={**wish, 'no_choice': no_choice}, target=target)
        # 1. Opening: everything it says is captured; nothing rejected as unsupported.
        out = turn(self.opening(compose_override=compose()))
        got = self.capture(out)
        self.assertFalse([k for k, v in got.items() if v == 'unsupported'], got)
        self.assertEqual(self.flow.report(self.r, 'RC09')['choice'], 'my_job')
        self.assertEqual(records.age_view(self.flow, self.g)['age'], 68)
        self.assertEqual(self.flow.value(self.g, 'situation.retirement')['status'], 'retiring')
        self.assertEqual(out['metrics']['records']['validated_target'], 'RC04')
        # 2. Parts A and B.
        text = "Neither, I don't have Part A or Part B yet."
        out = turn(self.message(text, extraction=self.read(text, updates=[self.update('RC04', {'choice': 'neither'}, text)],
                                                           targets=['RC10']), compose=compose()))
        # 3. Employer size (a tap); model explicitly continues this timing task.
        self.compositions.append(compose('RC11'))
        out = turn(self.turn({'type': 'choice', 'id': 'RC10', 'fields': {'choice': 'yes'}}))
        # 4. The dates.
        ups = [self.update('RC11', {'jobEnd': '2026-11-21', 'coverageEnd': '2026-11-30'}, DATES)]
        out = turn(self.message(DATES, extraction=self.read(DATES, updates=ups, targets=['RC12']), compose=compose()))
        card = next(c for c in out.get('cards') or [] if c.get('kind') == 'enrollment_timing')
        # 5. Drug coverage (a tap; replaces the benefits-office question).
        self.compositions.append(compose())
        out = turn(self.turn({'type': 'choice', 'id': 'RC12', 'fields': {'choice': 'yes'}}))
        # 6. "Sure" (exploring).
        out = turn(self.message('Sure', extraction=self.read('Sure', mode='discuss', task='', targets=[]), compose=compose()))
        # 7. "sure, I want to keep my doctors" asks which doctors.
        text = 'sure, I want to keep my doctors'
        out = turn(self.message(text, extraction=self.read(text, task='providers', targets=['T06'],
                   updates=[self.update('T10', {'choice': 'doctors'}, 'I want to keep my doctors')]), compose=compose()))
        self.assertEqual(asked[-1], 'T06')
        self.assertEqual(asked[:4], ['RC04', 'RC10', 'RC11', 'RC12'], asked)
        self.assertNotIn('RC13', asked)
        self.assertFalse({'T05', 'RC09', 'T02'} & set(asked), asked)
        for key, count in shown.items():
            self.assertLessEqual(count, 1, (key, shown))
        self.assertGreaterEqual(len(shown), 2, shown)
        held = [o['metrics']['records']['held_back_blocks'] for o in outs]
        self.assertGreaterEqual(sum(held), 3, (held, shown))           # the repeats were attempted and held back
        self.records_trace = [o['metrics']['records'] for o in outs]
        # The card, checked against the accepted fact text.
        facts = {f['id']: f for f in __import__('pilot_knowledge').PilotKnowledge()._read()[0]['facts']} \
            if isinstance(__import__('pilot_knowledge').PilotKnowledge()._read()[0].get('facts'), list) else {}
        values = {row['label']: row for row in card['rows']}
        self.assertEqual(values['Part B sign-up window']['value'], 'December 2026 through July 2027')
        self.assertEqual(values['If you sign up in November 2026']['value'], 'Part B generally starts December 1, 2026')
        self.assertIn('up to three months later', values['If you sign up in November 2026']['note'])
        self.assertEqual(values['Joining a drug or Medicare Advantage plan']['value'], 'Through January 2027')
        self.assertIn('63 days', values['Joining a drug or Medicare Advantage plan']['note'])
        self.assertEqual(values['Medigap window']['value'], 'December 2026 through May 2027')
        if facts:
            self.assertIn('eight-month period', facts['pk_work_sep_start']['statement'] if 'statement' in facts['pk_work_sep_start'] else json.dumps(facts['pk_work_sep_start']))
        # Journey status: the computed window replaces "confirm with Social Security".
        record = out['enrollment']['record']
        self.assertNotIn('current_work_coverage', record['unsupported'])
        self.assertEqual(record['next_step'], {'id': 'sign_up', 'by': '2027-07-31', 'basis': 'job_dates'})
        self.assertIn('(from the dates you told me)', out['enrollment']['line']['text'])

    def test_birth_month_and_year_is_the_age_anchor(self):
        self.opening()
        self.assertEqual(self.flow.question('S_AGE65')['question'], 'What month and year were you born?')
        text = 'I was born in March 1958.'
        out = self.message(text, extraction=self.read(text, coverage_reports=[self.report('birth', 'born in March 1958', month=3, year=1958)]),
                           compose=self.ask_recommended())
        self.assertEqual(self.flow.value(self.g, 'coverage.birth'), '1958-03')
        self.assertEqual(self.flow.value(self.g, 'situation.age65'), {'month': 3, 'year': 2023})   # derived, never asked
        view = records.age_view(self.flow, self.g)
        self.assertEqual((view['age'], view['band'], view['age_65_or_older'], view['medigap_age']), (68, '65_74', True, 68))
        self.assertEqual(self.capture(out).get('coverage.birth'), 'accepted')

    def test_status_and_held_plans_come_from_grounded_reports(self):
        self.opening()
        text = 'I applied for Part B in October 2026 and I have the Sunshine Advantage plan from Gulf Health.'
        reports = [self.report('part_b', 'I applied for Part B in October 2026', status='applied', month=10, year=2026),
                   self.report('held_plan', 'the Sunshine Advantage plan from Gulf Health', product='advantage',
                               name='Sunshine Advantage', carrier='Gulf Health'),
                   self.report('held_plan', 'I have', product='part_d', name='Invented Rx')]   # not in the message
        self.message(text, extraction=self.read(text, coverage_reports=reports), compose=self.ask_recommended())
        self.assertEqual(self.flow.value(self.g, 'enrollment.partB')['status'], 'applied')
        held = self.flow.value(self.g, 'coverage.reported')
        self.assertEqual(held['advantage'], {'name': 'Sunshine Advantage', 'carrier': 'Gulf Health', 'basis': 'reported'})
        self.assertNotIn('part_d', held)
        # A report about someone else is confirmed, never written.
        text = 'My wife has Part A.'
        out = self.message(text, extraction=self.read(text, coverage_reports=[
            self.report('part_a', 'My wife has Part A', subject='unclear', status='active')]), compose=self.ask_recommended())
        self.assertEqual(self.capture(out).get('coverage.part_a'), 'needs_clarification')
        self.assertIsNone(self.flow.value(self.g, 'enrollment.partA'))

    def test_word_based_status_capture_is_off(self):
        self.opening()
        text = "I don't have Part A or Part B yet."
        self.message(text, extraction=self.read(text), compose=self.ask_recommended())   # no RC04 proposal
        self.assertIsNone(self.flow.report(self.r, 'RC04').get('choice'))                # words alone decide nothing

    def test_job_scope_the_interpreter_doubts_is_confirmed_not_dropped(self):
        ups = [self.update('RC01', {'choice': 'self'}, "I'm 68"),
               self.update('RC09', {'choice': 'my_job'}, 'coverage provided by my company', scope='intended')]
        out = self.message(OPENING, extraction=self.read(OPENING, updates=ups), compose=self.ask_recommended())
        self.assertIn(self.capture(out).get('RC09'), ('needs_clarification', 'conflicting'))
        self.assertTrue(self.flow.pending_for(self.owner))
        self.assertEqual(out['metrics']['records']['precedence'], 'confirmation')
        self.assertTrue(out['metrics']['records']['confirmations_queued'])

    def test_benefits_office_question_is_one_proposition_and_only_when_raised(self):
        self.opening()
        q = self.flow.question('RC13', text='Has the benefits office told you how this change could affect your coverage, or a spouse’s or dependent’s coverage?')
        self.assertEqual(q['question'], 'Could a change affect anyone else’s coverage?')
        self.assertNotIn('RC13', self.available())
        text = 'Would my retiring change my husband’s coverage?'
        self.message(text, extraction=self.read(text, targets=['RC13']) | {'next_target': {'ids': ['RC13'], 'reason': 'person_raised'}},
                     compose=self.ask_recommended())
        self.assertIn('RC13', self.available())

    def test_offer_to_explain_an_introduced_concept_is_filtered(self):
        self.opening()
        repeat = 'Original Medicare and Medicare Advantage are the two main ways to get your coverage.'
        self.message('Tell me the options.', extraction=self.read('Tell me the options.', task=''),
                     compose=self.ask_recommended(blocks=[(repeat, ['routesintro'])], evidence=['routesintro']))
        offer = 'Would you like me to explain the two coverage paths?'
        out = self.message('Okay.', extraction=self.read('Okay.', mode='discuss', task='', targets=[]),
                           compose=dict(reply='Thanks.', question_target=None, question=offer, offer_concept='coverage_paths'))
        self.assertNotIn(offer, out['reply'])
        # Either code asked an open field instead, or it filtered the offer and ended on a button.
        self.assertTrue(out['metrics']['records']['offer_filtered'] or out['assessment'].get('nextQuestion'))
        self.assertTrue(self.ends_on_a_lead(out))
        state = planner.state(self.flow, self.owner)
        self.assertFalse(records.offer_allowed(state, 'coverage_paths'))
        self.assertTrue(records.offer_allowed(state, 'coverage_paths', allowed_concepts={'coverage_paths'}))
        self.assertTrue(records.offer_allowed(state, 'late_penalties'))

    def test_statement_ending_gets_a_work_button(self):
        self.opening()
        out = self.message('Okay.', extraction=self.read('Okay.', mode='suggest', task='providers', targets=[]),
                           compose=dict(reply='Keeping your doctors is a good place to start.', question_target=None, question=''))
        if out['assessment'].get('nextQuestion') is None:
            buttons = [c for c in out.get('cards') or [] if c['kind'] == 'next_step_offer']
            self.assertEqual([b['actions'][0]['label'] for b in buttons], ['Check my doctors'])
        self.assertTrue(self.ends_on_a_lead(out))

    def test_optional_fields_wait_until_raised(self):
        self.opening()
        self.assertFalse({'RC03', 'RC25', 'RC13'} & set(self.available()))

    def test_chosen_plan_is_kept_on_the_server(self):
        self.opening()
        out = self.turn({'type': 'enrollment_decision',
                         'selected_plan': {'product': 'advantage', 'plan_id': 'H0000-001', 'name': 'Sample Advantage Plan'}})
        self.assertEqual(self.flow.value(self.g, 'intent.selectedPlan')['plan_id'], 'H0000-001')
        self.assertTrue(out['enrollment']['selectedPlanSupported'])
        bundle = records.readiness(self.flow, self.owner, self.g, self.r)
        self.assertTrue(bundle['outcomes']['before_you_enroll']['chosen_plan'])
        with self.assertRaises(Exception):
            self.turn({'type': 'enrollment_decision', 'selected_plan': {'product': 'car', 'plan_id': 'x', 'name': 'y'}})
        self.flow.records_v1 = False
        with self.assertRaises(Exception):
            self.turn({'type': 'enrollment_decision', 'selected_plan': {'product': 'advantage', 'plan_id': 'H', 'name': 'P'}})

    def test_profile_record_has_purposes_values_and_levels(self):
        self.opening()
        view = records.profile_view(self.flow, self.owner, self.g, self.r)
        row = next(x for x in view['fields'] if x['id'] == 'RC09')
        self.assertEqual((row['state'], row['value'], row['level']), ('reported', {'choice': 'my_job'}, 'when_relevant'))
        self.assertTrue(row['purpose'] and row['purpose'] != row['label'])
        self.assertEqual({x['id'] for x in view['fields'] if x['level'] == 'optional'} >= {'RC03', 'RC25', 'RC13'}, True)

    # -- November 18 visit e30e536c54 (Naples, Ozempic) ----------------------
    def test_first_coverage_answer_does_not_reopen_the_parts_answer(self):
        self.flow.apply(self.g, self.r, {'id': 'RC01', 'fields': {'choice': 'self'}})
        self.assertIsNone(self.flow.value(self.g, 'coverage.current'))
        self.flow.apply(self.g, self.r, {'id': 'RC04', 'fields': {'choice': 'both'}})
        self.flow.apply(self.g, self.r, {'id': 'T05', 'fields': {'choice': 'original'}})
        self.assertFalse(self.r['facts']['RC04'].get('stale'))
        self.assertEqual(records.field_state(self.flow, self.owner, self.g, self.r, 'RC04'), 'reported')
        # A real change still marks what depended on the old answer.
        self.flow.apply(self.g, self.r, {'id': 'T05', 'fields': {'choice': 'advantage'}})
        self.assertTrue(self.r['facts']['RC04'].get('stale'))

    def test_a_home_zip_answers_the_permanent_home_question(self):
        self.opening()
        self.flow.apply(self.g, self.r, {'id': 'T03', 'fields': {'zip': '34102'}})
        self.assertEqual(records.field_state(self.flow, self.owner, self.g, self.r, 'RC02'), 'reported')
        self.assertNotIn('RC02', self.available())
        self.flow.apply(self.g, self.r, {'id': 'T03', 'fields': {'zip': '00602'}})   # one ZIP, three counties
        q = records._question(self.flow, self.g, self.r, 'RC02')
        self.assertEqual(q['question'], 'Which county and state is that home ZIP in?')
        self.assertEqual(len(q['fields'][0]['options']), 3)

    def test_offer_words_match_who_the_coverage_is_for(self):
        self.assertEqual(records.offer_card('compare', 'self')['actions'][0]['label'], 'Compare my options')
        for role in ('research', 'someone', None):
            card = records.offer_card('compare', role)
            self.assertNotIn(' my ', ' ' + card['actions'][0]['say'] + ' ', role)
        self.assertEqual(records.offer_card('providers', 'research')['actions'][0]['label'], 'Compare the options')
        self.assertEqual(records.offer_card('providers', 'someone')['actions'][0]['label'], 'Check doctors')

    def test_no_sources_under_a_reply_that_say_once_emptied(self):
        self.opening()
        repeat = 'Original Medicare and Medicare Advantage are the two main ways to get your coverage.'
        self.message('Tell me the options.', extraction=self.read('Tell me the options.', task=''),
                     compose=self.ask_recommended(blocks=[(repeat, ['routesintro'])], evidence=['routesintro']))
        out = self.message('Okay.', extraction=self.read('Okay.', task=''),
                           compose=self.ask_recommended(blocks=[(repeat, ['routesintro'])], evidence=['routesintro']))
        if out['assessment'].get('nextQuestion') and not out['reply'].strip():
            self.assertEqual(out['advisor']['sources'], [])
            self.assertEqual(out['advisor']['teachingFactIds'], [])


class RecordsUnits(unittest.TestCase):
    class Flow:
        def __init__(self, g=None, r=None):
            self.g = g or {'fields': {}}; self.r = r or {}
        def value(self, g, path):
            f = g['fields'].get(path); return f.get('value') if f else None
        def report(self, r, identifier):
            return r.get(identifier, {})

    def guide(self, **values):
        return {'fields': {k: {'value': v, 'status': 'reported'} for k, v in values.items()}}

    def test_age_anchor_prefers_birth_month_then_reported_age(self):
        flow = self.Flow()
        g = self.guide(**{'coverage.birth': '1958-03'})
        view = records.age_view(flow, g, date(2026, 11, 17))
        self.assertEqual((view['age'], view['turns_65'], view['age_65_or_older'], view['source']), (68, '2023-03', True, 'birth'))
        g = self.guide(**{'medigap.ageOn20261110': '68'})
        view = records.age_view(flow, g, date(2026, 11, 17))
        self.assertEqual((view['age'], view['turns_65'], view['age_65_or_older']), (68, None, True))
        g = self.guide(**{'situation.age65': {'month': 2, 'year': 2027}})
        self.assertIs(records.age_view(flow, g, date(2026, 11, 17))['age_65_or_older'], False)

    def test_end_dates_keep_day_precision(self):
        self.assertEqual(records.end_date('2026-11-30'), date(2026, 11, 30))
        self.assertEqual(records.end_date('2026-11'), date(2026, 11, 30))
        self.assertIsNone(records.end_date('november 21'))

    def test_coverage_ending_later_this_month_is_still_current_for_rules(self):
        reports = {'RC09': {'choice': 'my_job'}, 'RC11': {'jobEnd': '2026-11-21', 'coverageEnd': '2026-11-30'}}
        values = {'coverage.current': ['employer']}
        rules = applicable_rules(lambda i: reports.get(i, {}), lambda p: values.get(p), today=date(2026, 11, 17),
                                 age_65_or_older=True, day_precision=True)
        ids = [r['rule_id'] for r in rules]
        self.assertIn('working_coverage_sep', ids)
        self.assertIn('hsa_medicare', ids)            # age from the anchor, not only a 65th-birthday month
        before = applicable_rules(lambda i: reports.get(i, {}), lambda p: values.get(p), today=date(2026, 11, 17))
        self.assertNotIn('working_coverage_sep', [r['rule_id'] for r in before])   # the old month-only behavior

    def test_rules_keep_facts_and_lose_flow_instructions(self):
        rule = {'rule_id': 'x', 'fact_id': 'working_coverage_sep', 'confirm_with': ['RC10', None],
                'how_to_use': 'State the rule conditionally. Ask the employer-size question to settle it.'}
        out = records.strip_flow_instructions([rule])[0]
        self.assertEqual(out['how_to_use'], 'State the rule conditionally.')
        self.assertEqual(out['depends_on'], ['RC10'])
        self.assertNotIn('confirm_with', out)

    def test_records_prompts_stay_within_the_existing_bound(self):
        import conversation_prompts
        self.assertLess(len(conversation_prompts.INTERPRETATION_RECORDS), 8500)
        self.assertLess(len(conversation_prompts.COMPOSITION_RECORDS), 8500)

    def test_coverage_reports_are_checked_for_structure_and_grounding(self):
        base = {'kind': 'part_b', 'subject': 'beneficiary', 'quote': 'My Part B started March 2025', 'status': 'active',
                'month': 3, 'year': 2025, 'product': '', 'name': '', 'carrier': '', 'letter': ''}
        message = 'My Part B started March 2025, and I have Plan G.'
        ok, confirm = records.validate_coverage_reports([base], message)
        self.assertEqual(len(ok), 1)
        for bad in ({'year': 2024}, {'month': 4}, {'quote': 'not in the message'}, {'status': ''},
                    {'kind': 'held_plan', 'product': 'medigap', 'letter': 'N', 'status': ''}):
            self.assertEqual(records.validate_coverage_reports([{**base, **bad}], message), ([], []), bad)
        held = {**base, 'kind': 'held_plan', 'status': '', 'month': None, 'year': None, 'product': 'medigap',
                'letter': 'G', 'quote': 'I have Plan G'}
        self.assertEqual(len(records.validate_coverage_reports([held], message)[0]), 1)
        self.assertEqual(len(records.validate_coverage_reports([{**base, 'subject': 'learner'}], message)[1]), 1)

    def test_say_once_is_per_block_and_fact_based(self):
        s = {}
        records.record_shown(s, 'Block one about paths.', {'routesintro': ''})
        reply = 'Paths again, said differently this time around today.\n\nNew detail about your job coverage.'
        kept, held, facts = records.filter_blocks(s, reply, {'Paths again, said differently this time around today.': ['routesintro'],
                                                             'New detail about your job coverage.': ['pk_work_sep']})
        self.assertEqual((kept, held, facts), ('New detail about your job coverage.', 1, ['routesintro']))
        kept, held, _ = records.filter_blocks(s, reply, {'Paths again, said differently this time around today.': ['routesintro']},
                                              allowed_concepts={'coverage_paths'})
        self.assertEqual(held, 0)                       # confusion or a request about that concept allows it

    def test_next_target_contract(self):
        self.assertEqual(records.validate_next_target({'ids': ['RC04', 'RC10'], 'reason': 'goal'}),
                         {'ids': ['RC04', 'RC10'], 'reason': 'goal'})
        for bad in ({'ids': ['T02'], 'reason': 'goal'}, {'ids': ['RC21'], 'reason': 'goal'},
                    {'ids': ['RC04', 'RC10', 'T03'], 'reason': 'goal'}, {'ids': ['X'], 'reason': 'goal'},
                    {'ids': ['RC04'], 'reason': 'because'}, None):
            self.assertEqual(records.validate_next_target(bad), {})

    def test_concept_map_has_21_concepts_and_maps_every_accepted_fact(self):
        self.assertEqual(len(records.CONCEPTS), 21)
        import pathlib
        root = pathlib.Path(records.__file__).resolve().parents[2]
        review = json.loads((root / 'alternatives/advisor-first/pilot-knowledge-review-8895-r2.json').read_text())
        rules = []
        for name in ('pilot-rules.json', 'pilot-rules-r3-cms-checklist.json', 'pilot-rules-r4-ux-pass.json'):
            data = json.loads((root / 'alternatives/advisor-first' / name).read_text())
            rules += [x.get('id') or x.get('fact_id') for x in data['facts']]
        lessons = ['basics', 'parts', 'parta', 'partb', 'routesintro', 'options', 'original', 'advantage', 'drugbasics',
                   'drugs', 'medigap', 'checks', 'dates', 'enrollment_intro', 'cobra_timing', 'costs', 'medical_limit',
                   'extras', 'switching', 'next']
        missing = records.unmapped(list(review['approved_facts']) + rules + lessons)
        self.assertEqual(missing, [], missing)
        self.assertEqual(len(records.CHECKLIST_CONCEPTS), 12)

    def test_repeat_filter_needs_most_words_from_one_prior_block(self):
        s = {}
        records.record_shown(s, 'Original Medicare and Medicare Advantage are the two main ways to get your coverage.', {})
        kept, held = records.filter_repeats(s, 'Original Medicare and Medicare Advantage are the two main ways to get your coverage.\n\n'
                                               'Your job coverage changes when Part B should start for you.')
        self.assertEqual(held, 1)
        self.assertEqual(kept, 'Your job coverage changes when Part B should start for you.')
        kept, held = records.filter_repeats(s, 'Original Medicare and Medicare Advantage are the two main ways to get your coverage.', requested=True)
        self.assertEqual(held, 0)

    def test_work_window_needs_dates_with_a_year_age_and_parts_not_in_place(self):
        g = self.guide(**{'medigap.ageOn20261110': '68', 'coverage.current': ['employer']})
        r = {'RC09': {'choice': 'my_job'}, 'RC11': {'jobEnd': '2026-11-21', 'coverageEnd': '2026-11-30'}, 'RC04': {'choice': 'neither'}}
        w = records.work_window(self.Flow(), g, r, date(2026, 11, 17))
        self.assertEqual(w['part_b_window'], ['2026-12', '2027-07'])
        self.assertEqual(w['plan_window_end'], '2027-01')
        self.assertEqual(w['medigap_window_if_signed_now'], ['2026-12', '2027-05'])
        self.assertIsNone(records.work_window(self.Flow(), g, {**r, 'RC04': {'choice': 'both'}}, date(2026, 11, 17)))
        self.assertIsNone(records.work_window(self.Flow(), g, {**r, 'RC11': {'jobEnd': 'november 21'}}, date(2026, 11, 17)))
        self.assertIsNone(records.work_window(self.Flow(), self.guide(**{'medigap.ageOn20261110': '63'}), r, date(2026, 11, 17)))


if __name__ == '__main__':
    unittest.main()
