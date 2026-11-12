"""Variant-local exact token counting through the verified secure transport.

Same counted payload and bounds as the pinned counter. No generation or retry.
"""
import json
import logging
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request
from ai_budget import BudgetError, token_int
from provider_transport import urlopen
from transport_diagnostics import failure_details, recoverable_connection

LOGGER = logging.getLogger(__name__)


class TokenCountUnavailable(BudgetError):
    """Compatibility with the existing gate; this is not a spending-cap error."""
    failure_code = 'input_token_verification'

    def __init__(self, diagnostic):
        super().__init__('The AI connection check could not finish. Your current work is preserved.')
        self.diagnostic = diagnostic


def _unavailable(diagnostic):
    LOGGER.warning('Daylight token verification %s', json.dumps(diagnostic,sort_keys=True))
    return TokenCountUnavailable(diagnostic)


def count_input_tokens(client, payload):
    # Counting is not generation: retry one dropped connection without
    # issuing a paid call or changing the exact payload being verified.
    for attempt in range(2):
        try:
            return _count_once(client, payload)
        except TokenCountUnavailable as error:
            if attempt or not recoverable_connection({**error.diagnostic, 'phase': 'stream'}):
                raise
            time.sleep(0.5)


def _count_once(client, payload):
    body = {key: payload[key] for key in ('model', 'instructions', 'input', 'tools', 'text')}
    try:
        if hasattr(client, 'count'):
            count = token_int(client.count(payload))
            if count < 1:
                raise _unavailable({'phase':'preflight','reason':'count_value_invalid'})
            return count
        request = Request('https://api.openai.com/v1/responses/input_tokens',
            data=json.dumps(body).encode(), method='POST',
            headers={'Authorization':'Bearer '+client.key, 'Content-Type':'application/json'})
        with urlopen(request, timeout=15) as response:
            raw = response.read(10_001)
        if len(raw) > 10_000:
            raise _unavailable({'phase':'preflight','reason':'count_response_too_large'})
        count = json.loads(raw)
        if count.get('object') != 'response.input_tokens':
            raise _unavailable({'phase':'preflight','reason':'count_response_identity'})
        try:
            value = token_int(count.get('input_tokens'))
            if value < 1:
                raise BudgetError('Invalid input count.')
        except BudgetError:
            raise _unavailable({'phase':'preflight','reason':'count_value_invalid'}) from None
        return value
    except TokenCountUnavailable:
        raise
    except (HTTPError, URLError, TimeoutError) as error:
        raise _unavailable(failure_details(error,'preflight')) from None
    except (BudgetError, ValueError, KeyError, TypeError, AttributeError) as error:
        raise _unavailable({'phase':'preflight','reason':'count_response_format',
                            'exception':type(error).__name__}) from None
