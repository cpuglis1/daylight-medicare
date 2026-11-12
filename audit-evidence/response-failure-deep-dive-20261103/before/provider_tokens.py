"""Variant-local exact token counting through the verified secure transport.

Same counted payload and bounds as the pinned counter. No generation or retry.
"""
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request
from ai_budget import BudgetError, token_int
from provider_transport import urlopen


def count_input_tokens(client, payload):
    body = {key: payload[key] for key in ('model', 'instructions', 'input', 'tools', 'text')}
    try:
        request = Request('https://api.openai.com/v1/responses/input_tokens',
            data=json.dumps(body).encode(), method='POST',
            headers={'Authorization':'Bearer '+client.key, 'Content-Type':'application/json'})
        with urlopen(request, timeout=15) as response:
            raw = response.read(10_001)
        if len(raw) > 10_000:
            raise BudgetError('AI token count exceeded its bound.')
        count = json.loads(raw)
        if count.get('object') != 'response.input_tokens':
            raise BudgetError('AI input token count is unavailable.')
        return token_int(count.get('input_tokens'))
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError, TypeError):
        raise BudgetError('AI input token count could not be verified. No paid generation was started; manual guidance remains available.') from None
