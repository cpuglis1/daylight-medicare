"""Variant-local exact token counting through the verified secure transport.

Counts the pinned counter's five base fields plus the tool settings and
reasoning the request carries, because the provider bills those as input too
(the pinned counter in cms-slice/scripts/ai_budget.py counts only the base
fields). No generation; one retry of a dropped connection.
"""
import json
import logging
import os
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


PREFLIGHT_ENV = 'DAYLIGHT_TOKEN_PREFLIGHT'
PREFLIGHT_MODES = frozenset({'provider_count', 'local_bound'})
LOCAL_BOUND_MARGIN = 512


def preflight_mode():
    """provider_count (default) asks OpenAI; local_bound is set only by the :8895 launcher."""
    mode = os.environ.get(PREFLIGHT_ENV, 'provider_count').strip() or 'provider_count'
    if mode not in PREFLIGHT_MODES:
        raise _unavailable({'phase':'preflight','reason':'preflight_mode_invalid'})
    return mode


def uses_local_bound(client):
    # Only OpenAI requests use the local bound. A client with its own counter
    # (the Anthropic development adapter) keeps its exact count.
    return preflight_mode() == 'local_bound' and not hasattr(client, 'count')


def local_input_bound(payload):
    """A ceiling on input tokens computed without a network call.

    OpenAI's tokenizer is byte-level: every text token covers at least one
    UTF-8 byte, so the request's own JSON bytes (which also carry escapes, keys
    and punctuation the model never sees) can only overstate the count. The
    structured-output schema is added a second time for its rendered form, plus
    a fixed margin for message framing. Reserving this ceiling keeps the ledger's
    reserve-before-sending rule; settlement then records the provider's exact
    usage, which must be at or below this bound.
    """
    body = {key: payload[key] for key in ('model', 'instructions', 'input', 'tools', 'text')}
    request = json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    schema = json.dumps(payload['text'], ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return len(request) + len(schema) + LOCAL_BOUND_MARGIN


def count_input_tokens(client, payload):
    if uses_local_bound(client):
        return local_input_bound(payload)
    # Counting is not generation: retry one dropped connection without
    # issuing a paid call or changing the exact payload being verified.
    for attempt in range(2):
        try:
            return _count_once(client, payload)
        except TokenCountUnavailable as error:
            if attempt or not recoverable_connection({**error.diagnostic, 'phase': 'stream'}):
                raise
            time.sleep(0.5)


#: Request fields the provider bills as input tokens. The tool settings matter:
#: on Nov 21, 2026 a lookup request with ``parallel_tool_calls: false`` was
#: billed 10,581 input tokens but counted 10,503 without that field, and the
#: overshoot left the charge unverified and paused all paid calls.
COUNTED_FIELDS = ('model', 'instructions', 'input', 'tools', 'text')
COUNTED_OPTIONAL_FIELDS = ('tool_choice', 'parallel_tool_calls', 'reasoning')


def _count_once(client, payload):
    """Count one request's input tokens exactly as the provider will bill them.

    Args:
        client: The model client (its ``count`` method, or its API key).
        payload: The Responses request about to be sent.
    Returns:
        The provider's input token count.
    Raises:
        TokenCountUnavailable: The count could not be obtained or verified.
    """
    try:
        if hasattr(client, 'count'):
            count = token_int(client.count(payload))
            if count < 1:
                raise _unavailable({'phase':'preflight','reason':'count_value_invalid'})
            return count
        # Built inside the try so a malformed payload fails closed as
        # TokenCountUnavailable. Optional fields are sent only when the request
        # carries them; most requests carry ``reasoning``, so it is counted on
        # extraction and compose calls as well as lookup ones.
        body = {key: payload[key] for key in COUNTED_FIELDS}
        body.update({key: payload[key] for key in COUNTED_OPTIONAL_FIELDS if key in payload})
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
