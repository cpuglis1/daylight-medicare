"""Provider capture through the reported journey; synthetic transport only."""
import json
import unittest

import test_natural_flow as support


class ProviderCaptureRegressionTests(unittest.TestCase):
    def test_two_doctor_locations_follow_two_medicine_strengths_without_name_fallback(self):
        case = support.NaturalFlowTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        role = "I'm helping my mom review her Medicare."
        coverage = 'She has Original Medicare, a Medigap policy and a separate Part D drug plan.'
        medicines = 'She takes Example Med 5 mg tablets and Example Med 10 mg tablets.'
        providers = 'Dr. Rivera at Example Clinic in Naples, and Dr. Lee at Example Hospital in Tampa.'
        reply = ('I have these on the review list:\n'
                 '- Dr. Rivera at Example Clinic in Naples\n'
                 '- Dr. Lee at Example Hospital in Tampa')
        turns = [
            (role + " She's happy with her doctors but wants to understand whether her coverage still makes sense.",
             [case.update('RC01', {'choice': 'someone'}, role)],
             {'question_target': 'T05', 'question': 'What health insurance does your mom have now?'}),
            (coverage + ' She wants to keep them while she looks.',
             [case.update('T05', {'choice': 'original,medigap,drug'}, coverage)],
             {'question_target': 'T07', 'question': 'Which prescriptions should we include in the review?'}),
            (medicines + ' Please keep those as two separate entries.',
             [case.update('T07', {'text': medicines}, medicines),
              case.update('RC22', {'name': 'Example Med', 'strength': '5 mg', 'form': 'tablets'},
                          'Example Med 5 mg tablets', entity='new'),
              case.update('RC22', {'name': 'Example Med', 'strength': '10 mg', 'form': 'tablets'},
                          'Example Med 10 mg tablets', entity='new')],
             {'question_target': 'T06', 'question': 'Which doctors or hospitals would she like to keep?'}),
            (providers,
             [case.update('T06', {'text': providers}, providers),
              case.update('RC21', {'practice': 'Dr. Rivera at Example Clinic', 'city': 'Naples'},
                          'Dr. Rivera at Example Clinic in Naples', entity='new'),
              case.update('RC21', {'practice': 'Dr. Lee at Example Hospital', 'city': 'Tampa'},
                          'Dr. Lee at Example Hospital in Tampa', entity='new')],
             {'question_target': 'T03', 'question': 'What ZIP code do you live in?',
              'reply': reply, 'report_refs': ['guide.needs.providers']}),
        ]
        for text, updates, compose in turns:
            out = case.message(text, updates, compose=compose)
            self.assertEqual(out['generated'], {'status': 'complete', 'move': compose['question_target']})
            self.assertFalse(out.get('notice'))
        self.assertEqual(out['reply'], reply)
        self.assertEqual(out['assessment']['nextQuestion']['id'], 'T03')
        self.assertEqual(case.flow.value(case.g, 'coverage.current'), ['original', 'medigap', 'drug'])
        self.assertEqual([(item['practice'], item['city']) for item in case.flow.report(case.r, 'RC21')['items']],
                         [('Dr. Rivera at Example Clinic', 'Naples'), ('Dr. Lee at Example Hospital', 'Tampa')])
        drugs = case.flow.report(case.r, 'RC22')['items']
        self.assertEqual([(item['name'], item['strength'], item['form']) for item in drugs],
                         [('Example Med', '5 mg', 'tablets'), ('Example Med', '10 mg', 'tablets')])
        self.assertEqual(len({item['entity'] for item in drugs}), 2)
        self.assertFalse(out['assessment']['personalizedRecommendationAllowed'])
        self.assertFalse(out['assessment']['externalVerificationReady'])
        self.assertEqual(len(case.calls), 8)  # Existing two stages per turn, no repair calls.
        json.dumps(out)

    def case_at_provider_question(self):
        case = support.NaturalFlowTests()
        case.setUp()
        case.task('compare')
        case.choice('RC01', choice='self')
        case.choice('T03', zip='34102')
        case.choice('T04', choice='unknown')
        case.choice('T05', choice='cobra')
        case.choice('RC11', coverageEnd='November 2026')
        case.choice('T02', choice='new')
        for topic in ('parts', 'routesintro'):
            case.turn({'type': 'read_concept', 'id': topic}, aiConsent=False)
        self.assertEqual(case.flow.assess(case.g, case.r)['nextQuestion']['id'], 'T06')
        return case

    def test_lowercase_provider_answer_is_captured_and_full_response_serializes(self):
        text = 'My PCP is ashley tunkle in naples'
        variants = (
            [('RC21', {'practice': 'ashley tunkle', 'city': 'naples'}, 'new')],
            [('T06', {'text': 'ashley tunkle'}, 'profile'),
             ('RC21', {'practice': 'ashley tunkle', 'city': 'naples'}, 'new')],
            [('T06', {'choice': 'list', 'text': 'ashley tunkle in naples'}, 'profile'),
             ('RC21', {'practice': 'ashley tunkle', 'city': 'naples'}, 'profile')],
        )
        for reports in variants:
            with self.subTest(reports=reports):
                case = self.case_at_provider_question()
                out = case.message(text, [case.update(identifier, fields, text, entity=entity)
                    for identifier, fields, entity in reports])
                self.assertEqual(out['generated']['status'], 'complete')
                self.assertEqual(case.flow.value(case.g, 'needs.providersStatus'), 'list')
                self.assertIn('ashley tunkle',case.flow.value(case.g, 'needs.providers'))
                providers = case.flow.report(case.r, 'RC21')['items']
                self.assertEqual([(item['entity'], item['practice'], item['city']) for item in providers],
                                 [('doctor-1', 'ashley tunkle', 'naples')])
                reports = {item['id']: item['value'] for item in case.composed_context()['reports']}
                self.assertEqual(reports['readiness.RC21.doctor-1.practice'], 'ashley tunkle')
                self.assertEqual(reports['readiness.RC21.doctor-1.city'], 'naples')
                self.assertNotEqual((out['assessment']['nextQuestion'] or {}).get('id'), 'T06')
                self.assertFalse(out['assessment']['personalizedRecommendationAllowed'])
                self.assertEqual([call['text']['format']['name'] for call in case.calls],
                                 ['daylight_guide_commands', 'daylight_resolved_conversation'])
                serialized = json.loads(json.dumps(out))
                self.assertEqual(serialized['record']['facts']['RC21']['value']['items'], providers)

    def test_plain_provider_name_without_item_proposal_still_serializes_and_advances(self):
        case = self.case_at_provider_question()
        text = 'My PCP is ashley tunkle in naples'
        out = case.message(text, [case.update('T06', {'text': 'ashley tunkle in naples'}, text)])
        self.assertEqual(out['generated']['status'], 'complete')
        self.assertEqual(case.flow.value(case.g, 'needs.providers'), 'ashley tunkle in naples')
        self.assertNotIn('RC21', case.r['facts'])
        self.assertNotEqual((out['assessment']['nextQuestion'] or {}).get('id'), 'T06')
        json.dumps(out)


if __name__ == '__main__':
    unittest.main()
