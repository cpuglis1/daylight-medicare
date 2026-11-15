"""Unexpected errors reveal code locations, never private exception content."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from controller_diagnostics import unexpected_failure


class ControllerDiagnosticsTests(unittest.TestCase):
    def test_exception_body_and_external_paths_are_omitted(self):
        try:
            raise RuntimeError('Private Doctor Canary, request-secret-123')
        except RuntimeError as error:
            result = unexpected_failure(error)
        self.assertEqual(result, {'code': 'unexpected_exception', 'type': 'RuntimeError',
                                  'locations': 'unavailable'})
        self.assertNotIn('Canary', json.dumps(result))
        self.assertNotIn(str(Path(__file__).resolve()), json.dumps(result))

    def test_controller_failure_records_source_location_but_preserves_exception(self):
        from test_natural_flow import NaturalFlowTests
        harness = NaturalFlowTests()
        harness.setUp()
        def fail(*args):
            raise RuntimeError('Private Doctor Canary, request-secret-123')
        harness.flow.message = fail
        payload = harness.payload({'type': 'message', 'message': 'Private Doctor Canary'})
        from chat import ModelUnavailable
        import natural_flow
        with self.assertLogs('natural_flow', level='ERROR') as logs:
            # November 13, 2026: a typed message never ends in a bare server error. The person gets one
            # calm line and can send again; the original exception is kept as the cause and never shown.
            with self.assertRaises(ModelUnavailable) as caught:
                harness.take(payload)
        self.assertEqual(str(caught.exception), natural_flow.TURN_FAILED)
        self.assertIsInstance(caught.exception.__cause__, RuntimeError)
        self.assertNotIn('Canary', str(caught.exception))
        output = '\n'.join(logs.output)
        self.assertIn('code=unexpected_exception type=RuntimeError', output)
        self.assertRegex(output, r'natural_flow\.py:[0-9]+')
        self.assertNotIn('Canary', output)
        self.assertNotIn('request-secret', output)
        self.assertNotIn(harness.owner, output)
        self.assertNotIn(harness.owner, harness.flow.natural_active)


if __name__ == '__main__':
    unittest.main()
