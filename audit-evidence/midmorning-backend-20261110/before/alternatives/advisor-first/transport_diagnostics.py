"""Fixed-category transport diagnostics; never retain bodies, messages or text."""
import json
from urllib.error import HTTPError

from model_router import CATEGORIES as ROUTE_CATEGORIES

_KINDS = {'HTTPError', 'URLError', 'ProviderTransportError', 'TimeoutError', 'SSLError', 'ConnectionError',
          'ConnectionResetError', 'JSONDecodeError', 'KeyError', 'TypeError'}
_PHASES = {'preflight', 'stream', 'decode', 'validate'}
_CODES = {'invalid_json_schema', 'invalid_request_error', 'invalid_api_key',
          'insufficient_quota', 'credit_balance_exhausted', 'rate_limit_exceeded',
          'server_error', 'service_unavailable', 'context_length_exceeded',
          'authentication_error', 'permission_error', 'rate_limit_error',
          'api_error', 'overloaded_error', 'billing_error'}


def recoverable_connection(diagnostic):
    """Only dropped network replies; no replay of rejected or invalid output."""
    if not isinstance(diagnostic, dict) or diagnostic.get('phase') != 'stream':
        return False
    # HTTP errors require provider-specific Retry-After handling; do not
    # automatically replay them through this connection-only policy.
    if 'http_status' in diagnostic:
        return False
    return (diagnostic.get('transport_category') in {
        'connect', 'timeout', 'empty_response', 'send', 'receive', 'http2', 'partial_response'}
        or diagnostic.get('exception') in {'TimeoutError', 'ConnectionError', 'ConnectionResetError'})


def failure_details(error, phase, stream=None):
    result = {'exception': type(error).__name__ if type(error).__name__ in _KINDS else 'unknown',
              'phase': phase if phase in _PHASES else 'unknown'}
    exit_code = getattr(error, 'curl_exit_code', None)
    if type(exit_code) is int and -15 <= exit_code <= 99:
        result['curl_exit_code'] = exit_code
    category = getattr(error, 'transport_category', None)
    if category in {'proxy','dns','connect','timeout','tls','certificate','empty_response',
                    'send','receive','http2','invalid_headers','empty_headers','partial_response','process_exit',
                    'process_timeout','too_many_interim_responses','identifier_blocked'} | ROUTE_CATEGORIES:
        result['transport_category'] = category
    if isinstance(error, HTTPError):
        result['http_status'] = error.code if type(error.code) is int else 0
        try:
            raw = error.read(10_001)
            body = json.loads(raw) if len(raw) <= 10_000 else {}
            detail = body.get('error', {}) if isinstance(body, dict) else {}
            if isinstance(detail, dict):
                code = detail.get('code') or detail.get('type')
                result['provider_code'] = code if isinstance(code, str) and code in _CODES else 'unknown'
        except (ValueError, TypeError, OSError):
            result['provider_code'] = 'unknown'
    if isinstance(stream, dict):
        for key in ('terminal', 'delta_events', 'text_chars'):
            value = stream.get(key)
            valid = type(value) is bool if key == 'terminal' else type(value) is int and value >= 0
            if valid:
                result[key] = value
    return result
