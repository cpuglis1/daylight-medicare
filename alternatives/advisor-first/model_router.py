"""AI-04 fail-closed model router; the AI-03 enforcement point.

Every live model request leaves Daylight through ``provider_transport.urlopen``,
and that function asks this module to authorize the request before anything is
sent. Authorization is a static allowlist checked in beside this file
(``model-routes.json``). A request is sent only when one route for the active
environment names its provider, its exact model and the endpoint, and the
request uses only allowed features. Nothing here falls back to another
provider, model, project or endpoint. A request that does not match is refused
with a fixed category, and the caller's existing failure path runs without a
retry; the deterministic plan tools are unaffected.

Callers keep building requests against the canonical provider URL. The route
chooses the physical endpoint (for example a US processing host) and the
project header, so a deployment change is a reviewed edit to the allowlist,
not to each caller.

The active environment comes from ``DAYLIGHT_MODEL_ENVIRONMENT``: development
when unset, and any unknown value blocks every request. Routes that carry real
health information (``data: "health"``) stay blocked until their endpoints,
project and US region are recorded.

Model traffic that is allowed always runs in provider_transport's curl
process. ``install_bypass_guard`` therefore refuses any in-process (Python)
network lookup of a model provider host, which catches code that skips the
router, including the hash-pinned shared engine that this variant cannot edit.

Nothing here logs or keeps prompt text, keys or responses: only the block
category, environment and endpoint kind.
"""
from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
ROUTES_PATH = HERE / 'model-routes.json'
SCHEMA = 'daylight-model-routes/v1'
ENVIRONMENT_VARIABLE = 'DAYLIGHT_MODEL_ENVIRONMENT'
DEFAULT_ENVIRONMENT = 'development'
# Each environment carries one class of data. Development uses fictional
# people only; anything in the pilot is treated as real health information.
ENVIRONMENT_DATA = {'development': 'fictional', 'pilot': 'health'}
LOGGER = logging.getLogger(__name__)

# The only URLs a caller may build. The route decides where each one goes.
CANONICAL = {
    'https://api.openai.com/v1/responses': ('openai', 'responses'),
    'https://api.openai.com/v1/responses/input_tokens': ('openai', 'input_tokens'),
    'https://api.anthropic.com/v1/messages': ('anthropic', 'messages'),
    'https://api.anthropic.com/v1/messages/count_tokens': ('anthropic', 'count_tokens'),
}
PATHS = {'responses': '/v1/responses', 'input_tokens': '/v1/responses/input_tokens',
         'messages': '/v1/messages', 'count_tokens': '/v1/messages/count_tokens'}
KINDS = {'openai': ('responses', 'input_tokens'), 'anthropic': ('messages', 'count_tokens')}
PROVIDER_DOMAINS = {'openai': 'openai.com', 'anthropic': 'anthropic.com'}
OPENAI_PROJECT = re.compile(r'proj_[A-Za-z0-9]{8,64}')

# Request fields that keep state at the provider or call provider-hosted tools.
OPENAI_STATEFUL = ('previous_response_id', 'conversation', 'prompt', 'background')
OPENAI_TOOL_CHOICES = frozenset({'none', 'auto', 'required'})
OPENAI_INCLUDES = frozenset({'reasoning.encrypted_content', 'message.output_text.logprobs'})
ANTHROPIC_SERVER_FEATURES = ('mcp_servers', 'container')
ROUTING_HEADERS = frozenset({'openai-project', 'openai-organization'})

CATEGORIES = frozenset({'environment_invalid', 'endpoint_not_allowed', 'provider_not_allowed',
                        'model_not_allowed', 'route_not_configured', 'feature_not_allowed',
                        'hosted_tool_blocked'})


class RouteBlocked(Exception):
    """A request that no route allows. Carries only a fixed category."""

    def __init__(self, category):
        if category not in CATEGORIES:
            raise ValueError('Use a fixed route category.')
        super().__init__('The model request is not on the approved route list.')
        self.category = category


@dataclass(frozen=True)
class Route:
    id: str
    environment: str
    provider: str
    data: str
    models: tuple
    endpoints: tuple  # (kind, url or None) pairs
    project: object  # str or None
    region: str

    def endpoint(self, kind):
        return dict(self.endpoints).get(kind)

    @property
    def configured(self):
        if any(url is None for _, url in self.endpoints):
            return False
        if self.data == 'health':
            return self.project is not None and self.region == 'us'
        return True


@dataclass(frozen=True)
class Authorized:
    route: str
    url: str
    headers: tuple  # (name, value) pairs ready to send
    body: dict
    changed: bool


def _endpoint(provider, kind, url):
    if url is None:
        return None
    if not isinstance(url, str):
        raise ValueError('Use a URL string or null for each endpoint.')
    parts = urlsplit(url)
    host = (parts.hostname or '').lower()
    domain = PROVIDER_DOMAINS[provider]
    if (parts.scheme != 'https' or parts.port is not None or parts.username or parts.password
            or parts.query or parts.fragment or url != f'https://{host}{parts.path}'
            or not (host == domain or host.endswith('.' + domain)) or parts.path != PATHS[kind]):
        raise ValueError(f'Use an HTTPS {provider} endpoint ending in {PATHS[kind]}.')
    return url


def _route(item):
    keys = {'id', 'environment', 'provider', 'data', 'models', 'endpoints', 'project', 'region'}
    if not isinstance(item, dict) or set(item) - (keys | {'note'}) or keys - set(item):
        raise ValueError('Each route needs exactly: ' + ', '.join(sorted(keys)) + ' (and an optional note).')
    identifier, environment, provider, data = (item[key] for key in ('id', 'environment', 'provider', 'data'))
    if not isinstance(identifier, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,63}', identifier):
        raise ValueError('Use a short lowercase route id.')
    if environment not in ENVIRONMENT_DATA:
        raise ValueError('Use a known environment.')
    if provider not in KINDS:
        raise ValueError('Use a supported provider.')
    if data != ENVIRONMENT_DATA[environment]:
        raise ValueError(f'The {environment} environment carries {ENVIRONMENT_DATA[environment]} data only.')
    models = item['models']
    if (not isinstance(models, list) or not models or len(set(models)) != len(models)
            or not all(isinstance(model, str) and re.fullmatch(r'[a-z0-9][a-z0-9.\-]{1,63}', model)
                       for model in models)):
        raise ValueError('List exact model ids; wildcards and duplicates are not allowed.')
    endpoints = item['endpoints']
    if not isinstance(endpoints, dict) or set(endpoints) != set(KINDS[provider]):
        raise ValueError(f'List exactly these {provider} endpoints: ' + ', '.join(KINDS[provider]) + '.')
    project = item['project']
    if project is not None:
        if provider != 'openai' or not isinstance(project, str) or not OPENAI_PROJECT.fullmatch(project):
            raise ValueError('Use an OpenAI project id (proj_…) or null. Never put a key here.')
    region = item['region']
    if not isinstance(region, str) or not region:
        raise ValueError('Record the processing region.')
    if data == 'health' and region != 'us':
        raise ValueError('Routes that carry health information must process in the US.')
    return Route(identifier, environment, provider, data, tuple(models),
                 tuple((kind, _endpoint(provider, kind, endpoints[kind])) for kind in KINDS[provider]),
                 project, region)


def load_routes(path=ROUTES_PATH):
    """Read and validate the allowlist. Any defect stops the service from starting."""
    document = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(document, dict) or document.get('schema') != SCHEMA or not isinstance(document.get('routes'), list):
        raise ValueError(f'Use the {SCHEMA} route file.')
    routes = tuple(_route(item) for item in document['routes'])
    if len({route.id for route in routes}) != len(routes):
        raise ValueError('Route ids must be unique.')
    seen = set()
    for route in routes:
        for model in route.models:
            key = (route.environment, route.provider, model)
            if key in seen:
                raise ValueError('Each model may appear in one route per environment.')
            seen.add(key)
    return routes


ROUTES = load_routes()


def environment():
    value = os.environ.get(ENVIRONMENT_VARIABLE, DEFAULT_ENVIRONMENT)
    if value not in ENVIRONMENT_DATA:
        raise RouteBlocked('environment_invalid')
    return value


def allowed_models(env=None, routes=None):
    """Model ids that can be called right now in this environment."""
    try:
        env = env or environment()
    except RouteBlocked:
        return frozenset()
    return frozenset(model for route in (ROUTES if routes is None else routes)
                     if route.environment == env and route.configured for model in route.models)


def _check_openai(kind, body):
    for key in OPENAI_STATEFUL:
        if body.get(key) not in (None, False):
            raise RouteBlocked('feature_not_allowed')
    tools = body.get('tools')
    if tools is not None and (not isinstance(tools, list)
                              or not all(isinstance(tool, dict) and tool.get('type') == 'function' for tool in tools)):
        raise RouteBlocked('hosted_tool_blocked')
    choice = body.get('tool_choice')
    if choice is not None and not (isinstance(choice, str) and choice in OPENAI_TOOL_CHOICES
                                   or isinstance(choice, dict) and choice.get('type') == 'function'):
        raise RouteBlocked('hosted_tool_blocked')
    include = body.get('include')
    if include is not None and (not isinstance(include, list)
                                or not all(isinstance(item, str) and item in OPENAI_INCLUDES for item in include)):
        raise RouteBlocked('hosted_tool_blocked')
    if kind == 'responses' and body.get('store') is not False:
        return {**body, 'store': False}, True
    return body, False


def _check_anthropic(body):
    for key in ANTHROPIC_SERVER_FEATURES:
        if key in body:
            raise RouteBlocked('feature_not_allowed')
    tools = body.get('tools')
    if tools is not None and (not isinstance(tools, list) or not all(
            isinstance(tool, dict) and tool.get('type', 'custom') == 'custom' for tool in tools)):
        raise RouteBlocked('hosted_tool_blocked')
    return body, False


def authorize(url, headers, body, routes=None):
    """Return where and how to send this request, or raise RouteBlocked.

    ``headers`` are (name, value) pairs from the caller; ``body`` is the parsed
    JSON object. The returned body has ``store`` forced to false for OpenAI
    Responses, and the returned headers carry only the route's own project.
    """
    env = environment()
    try:
        provider, kind = CANONICAL[url]
        if not isinstance(body, dict):
            raise RouteBlocked('feature_not_allowed')
        candidates = [route for route in (ROUTES if routes is None else routes)
                      if route.environment == env and route.provider == provider]
        if not candidates:
            raise RouteBlocked('provider_not_allowed')
        model = body.get('model')
        route = next((route for route in candidates if model in route.models), None)
        if route is None:
            raise RouteBlocked('model_not_allowed')
        if not route.configured:
            raise RouteBlocked('route_not_configured')
        try:
            body, changed = _check_openai(kind, body) if provider == 'openai' else _check_anthropic(body)
        except (TypeError, ValueError, AttributeError):
            # An unexpected request shape is refused, never passed through.
            raise RouteBlocked('feature_not_allowed') from None
    except KeyError:
        error = RouteBlocked('endpoint_not_allowed')
        LOGGER.warning('Daylight model route blocked %s', json.dumps(
            {'category': error.category, 'environment': env}, sort_keys=True))
        raise error from None
    except RouteBlocked as error:
        LOGGER.warning('Daylight model route blocked %s', json.dumps(
            {'category': error.category, 'environment': env, 'endpoint': kind}, sort_keys=True))
        raise
    sent = tuple((name, value) for name, value in headers if name.lower() not in ROUTING_HEADERS)
    if route.project is not None:
        sent += (('OpenAI-Project', route.project),)
    return Authorized(route.id, route.endpoint(kind), sent, body, changed)


def is_provider_host(host):
    """True for hosts that serve model inference."""
    if isinstance(host, bytes):
        host = host.decode('ascii', 'ignore')
    if not isinstance(host, str):
        return False
    host = host.lower().rstrip('.')
    for domain in ('openai.com', 'anthropic.com', 'openai.azure.com', 'generativelanguage.googleapis.com'):
        if host == domain or host.endswith('.' + domain):
            return True
    # Vertex AI regional hosts look like us-central1-aiplatform.googleapis.com.
    if host == 'aiplatform.googleapis.com' or host.endswith(('.aiplatform.googleapis.com', '-aiplatform.googleapis.com')):
        return True
    return host.startswith('bedrock') and host.endswith('.amazonaws.com')


def bypass_hook(event, args):
    if event == 'socket.getaddrinfo' and args and is_provider_host(args[0]):
        raise PermissionError('MODEL_PROVIDER_BYPASS_BLOCKED')


_GUARD = {'installed': False}


def install_bypass_guard():
    """Refuse in-process lookups of model provider hosts for this process.

    Approved model traffic runs only in provider_transport's curl subprocess,
    after authorize(). A Python-level lookup of a provider host means a caller
    skipped the router. Audit hooks cannot be removed once installed.
    """
    if not _GUARD['installed']:
        sys.addaudithook(bypass_hook)
        _GUARD['installed'] = True
