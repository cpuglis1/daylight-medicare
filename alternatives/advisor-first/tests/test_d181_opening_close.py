"""D181: composed starting points, closing content and suggested priorities.

Real controller, fictional reports, scripted model outputs, no network.
"""
import unittest
import test_guided_close as gc
import journey_completion as close


class D181(unittest.TestCase):
    for name in ('payload','take','turn','message','choice','task','stage_payloads','extracted_context',
                 'composed_context','interpreted','ask','draft','fill','work','check_answer'):
        locals()[name] = getattr(gc.GuidedClose, name)
    update = staticmethod(gc.fixture.QuietRecovery.update)
    extraction = staticmethod(gc.fixture.QuietRecovery.extraction)
    setUp = gc.GuidedClose.setUp

    def fill_no_coverage(self, omit=()):
        self.flow.guided_close = False
        for identifier, fields in [('RC01',{'choice':'self'}),('T01',{'choice':'compare'}),
            ('T03',{'zip':'34102'}),('T05',{'choice':'none'}),('RC04',{'choice':'neither'}),
            ('T06',{'choice':'none'}),('T07',{'choice':'no'}),('T08',{'choice':'local'}),
            ('T09',{'choice':'predictable'}),('T10',{'choice':'doctors'}),
            ('MG_AGE',{'choice':'66'}),('MG_SEX',{'choice':'Female'}),('MG_TOBACCO',{'choice':'Non-Tobacco'})]:
            if identifier not in omit: self.choice(identifier, **fields)
        self.flow.guided_close = True

    def test_starting_point_is_answered_by_the_normal_composed_turn(self):
        reply = 'Medicare starts with Part A and Part B. Would you like to see the two coverage paths?'
        self.compositions.append(self.draft(reply))
        calls = len(self.calls)
        out = self.turn({'type':'choice','id':'T01','fields':{'choice':'learn'}})
        self.assertNotIn('openingChoice', out)
        self.assertEqual(out['reply'], reply)
        self.assertEqual(len(self.calls) - calls, 1)          # one composition, no extraction
        self.assertEqual(self.g['fields']['intent.goal']['value'], 'learn')

    def test_without_consent_the_stored_opening_path_is_unchanged_for_other_surfaces(self):
        out = self.choice('T01', choice='learn')
        self.assertEqual(out.get('openingChoice'), 'learn')

    def test_close_states_situation_direction_and_at_most_three_actionable_steps(self):
        self.fill()
        out = self.work()
        brief = out['comparisonClose']
        self.assertTrue(brief['show'])
        self.assertLessEqual(len(brief['steps']), 3)
        for step in brief['steps']:
            self.assertTrue(step['text'][0].isupper(), step['text'])
            self.assertNotIn('1-800', step['text'])
        self.assertTrue(brief['steps'][0]['text'].startswith('Tell me when your job coverage ends'))
        self.assertTrue(brief['direction'].startswith('Original Medicare with Medigap is worth looking at first'))
        self.assertEqual(brief['destination'], 'supplement')        # handoff opens the Medigap prices
        self.assertIn('keeping your doctors', brief['direction'])
        self.assertIn('predictable costs', brief['direction'])
        self.assertEqual([item['label'] for item in brief['learned']][:2], ['Your situation', 'What matters most'])
        self.assertIsNone(brief['recommendation'])
        self.assertEqual(out['coveragePath']['state'], 'undecided')

    def test_lower_monthly_preference_gives_no_direction(self):
        self.fill(omit=('T09',))
        self.flow.guided_close = False
        self.choice('T09', choice='lower_monthly')
        self.flow.guided_close = True
        out = self.work()
        self.assertTrue(out['comparisonClose']['show'])
        self.assertIsNone(out['comparisonClose']['direction'])

    def test_birthday_month_is_asked_before_the_close_then_parked(self):
        self.fill_no_coverage()
        first = self.work()
        self.assertEqual((first['assessment']['nextQuestion'] or {}).get('id'), 'S_AGE65')
        self.assertFalse((first.get('comparisonClose') or {}).get('show'))
        second = self.work('I am not sure, can we keep going?')
        self.assertEqual((second['assessment']['nextQuestion'] or {}).get('id'), 'S_AGE65')
        third = self.work('Please keep going.')
        self.assertTrue(third['comparisonClose']['show'])     # one question never owns the conversation

    def test_priorities_question_starts_with_what_the_person_said(self):
        self.fill(omit=('T10',))
        out = self.message('Please help me compare these options.',
            extraction=self.interpreted('Please help me compare these options.', task='compare'),
            compose=self.draft('We can use what matters to you.', target='T10'))
        asked = out['assessment']['nextQuestion']
        self.assertEqual(asked['id'], 'T10')
        self.assertEqual(asked['suggestedChoices'], ['bills'])
        self.assertNotIn('needs.priorities', self.g['fields'])  # nothing recorded until Send
        self.assertEqual(close.suggested_priorities(self.flow, self.g), ['bills'])

    def test_medigap_price_details_come_before_a_medigap_close(self):
        self.fill(omit=('MG_AGE','MG_SEX','MG_TOBACCO'))
        asked = []
        for _ in range(3):
            out = self.work()
            self.assertFalse((out.get('comparisonClose') or {}).get('show'))
            asked.append(out['assessment']['nextQuestion']['id'])
            self.flow.guided_close = False
            self.choice(asked[-1], choice={'MG_AGE':'66','MG_SEX':'Female','MG_TOBACCO':'Non-Tobacco'}[asked[-1]])
            self.flow.guided_close = True
        self.assertEqual(sorted(asked), ['MG_AGE','MG_SEX','MG_TOBACCO'])
        out = self.work()
        self.assertTrue(out['comparisonClose']['show'])
        self.assertEqual(out['medigapProfile']['status'], 'ready')

    def test_no_medigap_details_when_the_close_does_not_point_to_medigap(self):
        self.fill(omit=('T09','T10','MG_AGE','MG_SEX','MG_TOBACCO'))
        self.flow.guided_close = False
        self.choice('T09', choice='lower_monthly'); self.choice('T10', choice='total_cost')
        self.flow.guided_close = True
        out = self.work()
        self.assertTrue(out['comparisonClose']['show'])
        self.assertIsNone(out['comparisonClose']['direction'])

    def test_under_65_with_parts_a_and_b_is_not_priced_as_turning_65(self):
        import medigap_profile
        self.fill(omit=('RC04','MG_AGE'))
        self.flow.guided_close = False
        self.choice('RC04', choice='both'); self.choice('MG_AGE', choice='64')
        self.flow.guided_close = True
        view = medigap_profile.for_flow(self.flow, self.g, self.r)
        self.assertEqual(view['status'], 'missing')
        self.assertIn('RC06', view['missing'])                 # how they qualified, asked once
        self.flow.guided_close = False
        self.choice('RC06', choice='disability')
        self.flow.guided_close = True
        view = medigap_profile.for_flow(self.flow, self.g, self.r)
        self.assertEqual(view['status'], 'unsupported')
        self.assertNotEqual(view['inputs']['age'], 65)
        self.flow.guided_close = False
        self.choice('RC06', choice='age65')
        self.flow.guided_close = True
        view = medigap_profile.for_flow(self.flow, self.g, self.r)
        self.assertEqual(view['status'], 'ready')
        self.assertEqual(view['inputs']['age'], 65)
        # Other surfaces keep D138 unchanged.
        self.assertEqual(medigap_profile.profile(self.g)['inputs']['age'], 65)

    def test_two_doctors_in_one_sentence_are_two_doctors(self):
        from conversation_checks import doctor_items
        self.assertEqual(doctor_items('dr. smith in naples and dr. tunkle'), ['dr. smith in naples', 'dr. tunkle'])
        self.assertEqual(doctor_items('Dr. Smith, Dr. Lee'), ['Dr. Smith', 'Dr. Lee'])
        self.assertEqual(doctor_items('Dr. Maria Lopez, Naples'), ['Dr. Maria Lopez, Naples'])
        self.assertEqual(doctor_items('Naples Heart and Vascular'), ['Naples Heart and Vascular'])
        self.assertEqual(doctor_items('Dr. Smith and Drake Clinic'), ['Dr. Smith and Drake Clinic'])

    def test_composer_never_names_buttons(self):
        import conversation_prompts
        self.assertNotIn('offer Review your info before See plans', conversation_prompts.COMPOSITION)
        self.assertIn('name no button or tab', conversation_prompts.COMPOSITION)
        self.assertLess(len(conversation_prompts.COMPOSITION), 8500)

    def test_check_follow_up_skips_start_question_when_parts_a_and_b_are_in_place(self):
        self.fill(omit=('RC04','T06','T07','T08','T09','T10'))
        self.flow.guided_close = False
        self.choice('RC04', choice='both')
        self.flow.guided_close = True
        out = {'assessment': {'nextQuestion': self.flow.question('T04')}}
        self.flow.skip_settled_start(self.owner, self.g, self.r, out)
        self.assertNotEqual((out['assessment']['nextQuestion'] or {}).get('id'), 'T04')
        self.flow.guided_close = False                           # other surfaces unchanged
        out = {'assessment': {'nextQuestion': self.flow.question('T04')}}
        self.flow.skip_settled_start(self.owner, self.g, self.r, out)
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T04')

    def test_one_clinician_with_several_offices_is_one_question(self):
        import copy
        from behavioral_offline_server import Doctors, Drugs
        from conversation_checks import ConversationChecks
        class Directory(Doctors):
            def search(self, **query):
                found = super().search(**query)
                for p in found['candidates']:
                    p['site_count'] = 2
                return found
            def sites(self, **query):
                result = super().sites(**query)
                result['sites'].append({**copy.deepcopy(result['sites'][0]), 'site_id': 'second-office'})
                return result
        self.choice('RC01', choice='self'); self.choice('T03', zip='34102')
        self.checks = ConversationChecks(self.flow, Directory([]), Drugs(), lambda: [])
        self.choice('T06', text='Dr. Nera Vale in Naples')
        first = self.checks.reconcile(self.owner, self.g, self.r)
        self.assertEqual(first['question']['field'], 'office')          # no separate "Which of these" step
        values = [c['value'] for c in first['question']['choices']]
        self.assertIn('__refine__', values)
        again = self.check_answer('__refine__')                          # not this doctor: search again
        self.assertIn(again['question']['field'], ('doctor_location', 'doctor'))


if __name__ == '__main__':
    unittest.main()
