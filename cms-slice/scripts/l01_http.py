"""Shared additive HTTP contract for both protected Daylight variants."""
import json
import threading

from l01 import Acceptance, L01, L01Error, L01Held, SCHEMA

CONTRACT = {'contract': 'l01-http/1', 'result_schema': SCHEMA,
            'status': '/api/l01/status', 'evaluate': '/api/l01/evaluate',
            'methods': {'status': 'GET', 'evaluate': 'POST'},
            'research_over_http': False, 'financial_input_storage': False,
            'required_common_inputs': ['operation', 'year', 'month', 'state'],
            'capabilities': ['published_standard', 'published_cost_lookup', 'premiums', 'irmaa', 'hospital_stay', 'snf_stay', 'ordinary_b', 'benefit_reset'],
            'unavailable': ['personal_total', 'recommendations'],
            'acceptance': 'Exact national package, claim, rule, conflict and output bindings; independent receipts required'}


def attach(server, service=None):
    """Wrap each variant's existing handler without replacing routes or storage.

    Uses the variant's existing origin, body, response and no-log implementation.
    These nonpersistent calculations do not read guest data or call the model.
    """
    if getattr(server, 'l01_service', None) is not None:
        return server
    service = service or L01()
    base = server.RequestHandlerClass
    slots = threading.BoundedSemaphore(4)

    class WithL01(base):
        def do_GET(self):
            if self.path not in {'/api/l01/status', '/api/l01/contract'}:
                return super().do_GET()
            if not self.safe():
                return self.respond(403, {'error': 'Request origin rejected.'})
            try:
                return self.respond(200, CONTRACT if self.path.endswith('/contract') else service.gate.status())
            except (OSError, L01Error, KeyError, TypeError, json.JSONDecodeError):
                return self.respond(503, {'state': 'unavailable', 'error': 'L01 package unavailable; no consumer amount released.'})

        def do_POST(self):
            if self.path != '/api/l01/evaluate':
                return super().do_POST()
            if not self.safe():
                return self.respond(403, {'error': 'Request origin rejected.'})
            if not slots.acquire(blocking=False):
                return self.respond(429, {'state': 'unavailable', 'error': 'Please retry this component check later.'})
            try:
                return self.respond(200, service.evaluate(self.body()))
            except L01Held as error:
                return self.respond(503, {'state': error.state, 'error': 'This L01 component requires exact current independent acceptance.',
                                          'acceptance_status': 'held', 'personal_total_available': False, 'recommendations_available': False})
            except (L01Error, KeyError, TypeError, json.JSONDecodeError):
                return self.respond(422, {'state': 'unknown', 'error': 'Use the supported typed L01 request; unreviewed fields are rejected.'})
            except OSError:
                return self.respond(503, {'state': 'unavailable', 'error': 'Source package unavailable.'})
            finally:
                slots.release()

    server.RequestHandlerClass = WithL01
    server.l01_service = service
    return server
