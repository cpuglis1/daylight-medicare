"""Focused regression for the reported doctor-name acknowledgment failure."""
import unittest
import test_natural_agent as support
from chat import ModelUnavailable


class ProviderNameAcknowledgmentTests(unittest.TestCase):
    def test_reported_name_accepts_honorific_and_conversational_prefix(self):
        case = support.NaturalAgentTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.context['reports'] = [{'id':'guide.needs.providers','value':'Ashley Tunkle','status':'reported'}]
        for name in ('Ashley Tunkle', 'Dr. Ashley Tunkle', 'Doctor Ashley Tunkle', 'Thanks Ashley Tunkle'):
            with self.subTest(name=name):
                case.answer = case.composition(reply=name + ' is on the list to keep in mind.',
                    report_refs=['guide.needs.providers'])
                self.assertEqual(case.compose()['reply'],case.answer['reply'])

    def test_normalization_does_not_allow_invented_or_extended_names(self):
        case = support.NaturalAgentTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.context['reports'] = [{'id':'guide.needs.providers','value':'Ashley Tunkle','status':'reported'}]
        for name in ('Dr. Avery Invented', 'Thanks Avery Invented', 'Dr. Ashley Tunkle Smith'):
            with self.subTest(name=name):
                case.answer = case.composition(reply=name + ' is on the list to keep in mind.',
                    report_refs=['guide.needs.providers'])
                with self.assertRaises(ModelUnavailable):
                    case.compose()


if __name__ == '__main__':
    unittest.main()
