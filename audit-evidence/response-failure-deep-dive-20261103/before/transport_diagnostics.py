"""Fixed-category transport diagnostics; never retain bodies, messages or text."""
import json
from urllib.error import HTTPError

_KINDS = {'HTTPError', 'URLError', 'TimeoutError', 'SSLError', 'ConnectionError',
          'ConnectionResetError', 'JSONDecodeError', 'KeyError', 'TypeError'}
_PHASES = {'preflight', 'stream', 'decode', 'validate'}
_CODES = {'invalid_json_schema', 'invalid_request_error', 'invalid_api_key',
          'insufficient_quota', 'credit_balance_exhausted', 'rate_limit_exceeded',
          'server_error', 'service_unavailable', 'context_length_exceeded'}


def failure_details(error, phase, stream=None):
    result = {'exception': type(error).__name__ if type(error).__name__ in _KINDS else 'unknown',
              'phase': phase if phase in _PHASES else 'unknown'}
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
