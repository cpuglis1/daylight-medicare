"""Provider capture through the reported journey; synthetic transport only."""
import json
import unittest

import test_natural_flow as support


class ProviderCaptureRegressionTests(unittest.TestCase):
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
                self.assertEqual(case.flow.value(case.g, 'needs.providers'), 'ashley tunkle')
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
