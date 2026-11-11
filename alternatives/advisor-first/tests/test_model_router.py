"""AI-03/AI-04: the fail-closed model router and the provider-bypass checks.

Offline only. Provider calls are never made: curl is replaced by a fake
process, and the route file under test is either the shipped one or a
fictional copy written to a temporary folder.
"""
import ast
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import Request

ADVISOR = Path(__file__).resolve().parents[1]
REPO = ADVISOR.parents[1]
sys.path.insert(0, str(ADVISOR))
import model_router as router
import provider_transport as transport
from transport_diagnostics import failure_details, recoverable_connection

RESPONSES = 'https://api.openai.com/v1/responses'
COUNT = 'https://api.openai.com/v1/responses/input_tokens'
MESSAGES = 'https://api.anthropic.com/v1/messages'
US_RESPONSES = 'https://us.api.openai.com/v1/responses'
PROJECT = 'proj_FictionalPilot0001'
HEADERS = (('Authorization', 'Bearer FICTIONAL-KEY'), ('Content-type', 'application/json'))
PILOT = {router.ENVIRONMENT_VARIABLE: 'pilot'}


def route_file(routes, folder):
    path = Path(folder) / 'routes.json'
    path.write_text(json.dumps({'schema': router.SCHEMA, 'routes': routes}))
    return path


def openai_route(**changes):
    route = {'id': 'pilot-openai', 'environment': 'pilot', 'provider': 'openai', 'data': 'health',
             'models': ['gpt-6.1-sol'],
             'endpoints': {'responses': US_RESPONSES,
                           'input_tokens': 'https://us.api.openai.com/v1/responses/input_tokens'},
             'project': PROJECT, 'region': 'us'}
    route.update(changes)
    return route


def configured_pilot():
    with tempfile.TemporaryDirectory() as folder:
        return router.load_routes(route_file([openai_route()], folder))


class Process:
    def __init__(self, output):
        self.stdin, self.stdout = io.BytesIO(), io.BytesIO(output)
        self.sent = b''
        original = self.stdin.close

        def close():
            if not self.stdin.closed:
                self.sent = self.stdin.getvalue()
            original()
        self.stdin.close = close

    def poll(self):
        return 0

    def wait(self, timeout=None):
        return 0

    def terminate(self):
        pass

    def kill(self):
        pass


class RouteFileTests(unittest.TestCase):
    def test_shipped_file_loads_and_pilot_stays_blocked_until_filled_in(self):
        routes = router.load_routes()
        pilot = [route for route in routes if route.environment == 'pilot']
        self.assertEqual([route.provider for route in pilot], ['openai'])
        self.assertTrue(all(route.data == 'health' and route.region == 'us' for route in pilot))
        self.assertFalse(any(route.configured for route in pilot))
        self.assertEqual(router.allowed_models('pilot', routes), frozenset())
        self.assertIn('gpt-6.1-sol', router.allowed_models('development', routes))

    def test_pilot_is_openai_only(self):
        for route in router.load_routes():
            if route.environment == 'pilot':
                self.assertEqual(route.provider, 'openai')

    def test_completed_pilot_route_is_configured(self):
        routes = configured_pilot()
        self.assertTrue(routes[0].configured)
        self.assertEqual(router.allowed_models('pilot', routes), frozenset({'gpt-6.1-sol'}))

    def test_rejects_unsafe_route_files(self):
        cases = {
            'wildcard model': openai_route(models=['gpt-*']),
            'plain http': openai_route(endpoints={'responses': 'http://us.api.openai.com/v1/responses',
                                                  'input_tokens': None}),
            'other host': openai_route(endpoints={'responses': 'https://api.example.com/v1/responses',
                                                  'input_tokens': None}),
            'look-alike host': openai_route(endpoints={'responses': 'https://api.openai.com.example.net/v1/responses',
                                                       'input_tokens': None}),
            'wrong path': openai_route(endpoints={'responses': 'https://api.openai.com/v1/chat/completions',
                                                  'input_tokens': None}),
            'query string': openai_route(endpoints={'responses': US_RESPONSES + '?x=1', 'input_tokens': None}),
            'missing endpoint': openai_route(endpoints={'responses': US_RESPONSES}),
            'key in project': openai_route(project='sk-proj-FICTIONAL0000000000'),
            'health outside US': openai_route(region='eu'),
            'pilot marked fictional': openai_route(data='fictional'),
            'unknown environment': openai_route(environment='staging'),
            'unknown provider': openai_route(provider='bedrock'),
            'extra field': openai_route(fallback='development-openai'),
        }
        for name, route in cases.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(ValueError):
                    router.load_routes(route_file([route], folder))

    def test_one_route_per_model_and_unique_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                router.load_routes(route_file([openai_route(), openai_route(id='pilot-two')], folder))
            with self.assertRaises(ValueError):
                router.load_routes(route_file([openai_route(), openai_route(models=['gpt-5.4'])], folder))


class AuthorizeTests(unittest.TestCase):
    def authorize(self, body, url=RESPONSES, headers=HEADERS, routes=None):
        return router.authorize(url, headers, body, routes=routes)

    def blocked(self, category, *args, **kwargs):
        with self.assertRaises(router.RouteBlocked) as caught, self.assertLogs(router.LOGGER, 'WARNING') as logs:
            self.authorize(*args, **kwargs)
        self.assertEqual(caught.exception.category, category)
        self.assertNotIn('FICTIONAL', ''.join(logs.output))
        return caught.exception

    def test_development_request_keeps_endpoint_and_forces_store_false(self):
        result = self.authorize({'model': 'gpt-6.1-sol', 'input': 'FICTIONAL-TEXT', 'store': True})
        self.assertEqual((result.route, result.url), ('development-openai', RESPONSES))
        self.assertIs(result.body['store'], False)
        self.assertTrue(result.changed)
        unchanged = self.authorize({'model': 'gpt-6.1-sol', 'store': False})
        self.assertFalse(unchanged.changed)
        missing = self.authorize({'model': 'gpt-6.1-sol'})
        self.assertIs(missing.body['store'], False)

    def test_token_counting_has_no_store_field_added(self):
        result = self.authorize({'model': 'gpt-6.1-sol', 'input': 'x'}, url=COUNT)
        self.assertNotIn('store', result.body)
        self.assertEqual(result.url, COUNT)

    def test_unlisted_model_endpoint_and_missing_model_are_blocked(self):
        self.blocked('model_not_allowed', {'model': 'gpt-4o'})
        self.blocked('model_not_allowed', {'input': 'no model'})
        self.blocked('endpoint_not_allowed', {'model': 'gpt-6.1-sol'},
                     url='https://api.openai.com/v1/chat/completions')

    def test_hosted_tools_and_provider_state_are_refused(self):
        function = {'type': 'function', 'name': 'lookup', 'parameters': {'type': 'object'}}
        self.authorize({'model': 'gpt-6.1-sol', 'tools': [function], 'tool_choice': 'auto'})
        for tool in ({'type': 'web_search'}, {'type': 'file_search'}, {'type': 'code_interpreter'},
                     {'type': 'mcp', 'server_url': 'https://example.com'}, 'web_search'):
            with self.subTest(tool=tool):
                self.blocked('hosted_tool_blocked', {'model': 'gpt-6.1-sol', 'tools': [tool]})
        self.blocked('hosted_tool_blocked', {'model': 'gpt-6.1-sol', 'tool_choice': {'type': 'web_search'}})
        self.blocked('hosted_tool_blocked', {'model': 'gpt-6.1-sol', 'include': ['file_search_call.results']})
        for field, value in (('previous_response_id', 'resp_1'), ('conversation', 'conv_1'),
                             ('background', True), ('prompt', {'id': 'pmpt_1'})):
            with self.subTest(field=field):
                self.blocked('feature_not_allowed', {'model': 'gpt-6.1-sol', field: value})
        self.authorize({'model': 'gpt-6.1-sol', 'background': False,
                        'include': ['reasoning.encrypted_content']})

    def test_anthropic_server_tools_are_refused_in_development(self):
        self.authorize({'model': 'claude-opus-5-5', 'messages': []}, url=MESSAGES)
        self.blocked('hosted_tool_blocked', {'model': 'claude-opus-5-5', 'tools': [{'type': 'web_search_20250305'}]},
                     url=MESSAGES)
        self.blocked('feature_not_allowed', {'model': 'claude-opus-5-5', 'mcp_servers': []}, url=MESSAGES)

    def test_pilot_refuses_development_routes_and_waits_for_configuration(self):
        with patch.dict(os.environ, PILOT):
            self.blocked('route_not_configured', {'model': 'gpt-6.1-sol'})
            self.blocked('model_not_allowed', {'model': 'gpt-5.4'})
            self.blocked('provider_not_allowed', {'model': 'claude-opus-5-5'}, url=MESSAGES)

    def test_configured_pilot_rewrites_endpoint_and_sets_only_its_project(self):
        caller = HEADERS + (('Openai-project', 'proj_SomethingElse001'), ('Openai-organization', 'org_x'))
        with patch.dict(os.environ, PILOT):
            result = self.authorize({'model': 'gpt-6.1-sol'}, headers=caller, routes=configured_pilot())
        self.assertEqual(result.url, US_RESPONSES)
        names = [name.lower() for name, _ in result.headers]
        self.assertEqual(names.count('openai-project'), 1)
        self.assertNotIn('openai-organization', names)
        self.assertIn(('OpenAI-Project', PROJECT), result.headers)

    def test_unknown_environment_blocks_everything(self):
        with patch.dict(os.environ, {router.ENVIRONMENT_VARIABLE: 'production'}):
            with self.assertRaises(router.RouteBlocked) as caught:
                self.authorize({'model': 'gpt-6.1-sol'})
            self.assertEqual(caught.exception.category, 'environment_invalid')
            self.assertEqual(router.allowed_models(), frozenset())


class TransportTests(unittest.TestCase):
    def request(self, body, url=RESPONSES):
        return Request(url, data=json.dumps(body).encode(), method='POST', headers=dict(HEADERS))

    def test_blocked_route_never_starts_curl_and_is_not_retried(self):
        with patch.object(transport.subprocess, 'Popen') as popen, self.assertLogs(router.LOGGER, 'WARNING'):
            with self.assertRaises(transport.ProviderTransportError) as caught:
                with transport.urlopen(self.request({'model': 'gpt-4o', 'input': 'FICTIONAL'})):
                    self.fail('A blocked route cannot yield a response.')
        popen.assert_not_called()
        diagnostic = failure_details(caught.exception, 'preflight')
        self.assertEqual(diagnostic['transport_category'], 'model_not_allowed')
        self.assertFalse(recoverable_connection({**diagnostic, 'phase': 'stream'}))

    def test_pilot_without_configuration_sends_nothing(self):
        with patch.dict(os.environ, PILOT), patch.object(transport.subprocess, 'Popen') as popen, \
                self.assertLogs(router.LOGGER, 'WARNING'):
            with self.assertRaises(transport.ProviderTransportError) as caught:
                with transport.urlopen(self.request({'model': 'gpt-6.1-sol', 'input': 'FICTIONAL'})):
                    pass
        popen.assert_not_called()
        self.assertEqual(caught.exception.transport_category, 'route_not_configured')

    def test_configured_pilot_sends_to_the_route_with_store_false(self):
        process = Process(b'HTTP/2 200\r\nContent-Type: application/json\r\n\r\n{"ok":true}')
        with patch.dict(os.environ, PILOT), patch.object(router, 'ROUTES', configured_pilot()), \
                patch.object(transport.subprocess, 'Popen', return_value=process) as popen:
            with transport.urlopen(self.request({'model': 'gpt-6.1-sol', 'input': 'FICTIONAL', 'store': True})) as stream:
                self.assertEqual(json.loads(stream.read(100)), {'ok': True})
        popen.assert_called_once()
        sent = process.sent.decode()
        self.assertIn('url = "' + US_RESPONSES + '"', sent)
        self.assertIn('header = "OpenAI-Project: ' + PROJECT + '"', sent)
        self.assertNotIn('api.openai.com/v1/responses"', sent.replace(US_RESPONSES, ''))
        body = json.loads(json.loads(re.search(r'^data-binary = (".*")$', sent, re.M)[1]))
        self.assertIs(body['store'], False)

    def test_transport_accepts_only_canonical_urls(self):
        self.assertEqual(transport.ENDPOINTS, frozenset(router.CANONICAL))


class BypassGuardTests(unittest.TestCase):
    def test_provider_hosts(self):
        for host in ('api.openai.com', 'us.api.openai.com', 'API.OPENAI.COM.', b'api.anthropic.com',
                     'example.openai.azure.com', 'generativelanguage.googleapis.com',
                     'us-central1-aiplatform.googleapis.com', 'bedrock-runtime.us-east-1.amazonaws.com'):
            with self.subTest(host=host):
                self.assertTrue(router.is_provider_host(host))
        for host in ('localhost', '127.0.0.1', 'notopenai.com', 'openai.com.example.net',
                     's3.us-east-1.amazonaws.com', 'www.googleapis.com', None):
            with self.subTest(host=host):
                self.assertFalse(router.is_provider_host(host))

    def test_hook_refuses_python_lookups_of_provider_hosts(self):
        with self.assertRaises(PermissionError):
            router.bypass_hook('socket.getaddrinfo', ('api.openai.com', 443, 0, 1, 6, 0))
        router.bypass_hook('socket.getaddrinfo', ('localhost', 8893, 0, 1, 6, 0))
        router.bypass_hook('open', ('api.openai.com', 'r', 0))


SKIP_DIRS = {'tests', 'var', 'runtime', '__pycache__', 'web', 'web-8894', 'pilot-web', 'node_modules'}
# Files that build model requests. They name only canonical URLs and send them
# through provider_transport, which asks the router first.
REQUEST_BUILDERS = {'natural_agent.py', 'narrative_agent.py', 'provider_tokens.py', 'claude_client.py'}
PROVIDER_SDKS = ('openai', 'anthropic', 'google.generativeai', 'google.genai', 'vertexai',
                 'litellm', 'mistralai', 'cohere')
DIRECT_HTTP = ('http.client', 'requests', 'httpx', 'urllib3', 'aiohttp', 'socket', 'subprocess')
HOST = re.compile(r'(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})', re.I)


def advisor_sources():
    for root, folders, files in os.walk(ADVISOR):
        folders[:] = [name for name in folders if name not in SKIP_DIRS and not name.startswith('.')]
        for name in files:
            if name.endswith('.py'):
                path = Path(root) / name
                yield path, ast.parse(path.read_text(encoding='utf-8'), str(path))


def imported(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, None
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                yield node.module, alias.name


def strings(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value


class ProviderBypassSourceTests(unittest.TestCase):
    """AI-03 CI check: the advisor reaches model providers only through the router."""

    def test_no_provider_sdk_anywhere_in_the_advisor(self):
        offenders = []
        for path, tree in advisor_sources():
            for module, _ in imported(tree):
                if any(module == sdk or module.startswith(sdk + '.') for sdk in PROVIDER_SDKS):
                    offenders.append(f'{path.relative_to(REPO)} imports {module}')
            if any('bedrock-runtime' in value for value in strings(tree)):
                offenders.append(f'{path.relative_to(REPO)} names bedrock-runtime')
        self.assertEqual(offenders, [], 'Call models only through provider_transport and model_router.')

    def test_provider_addresses_appear_only_in_request_builders(self):
        offenders = []
        for path, tree in advisor_sources():
            if path.name == 'model_router.py':
                continue
            for value in strings(tree):
                for host in HOST.findall(value):
                    if router.is_provider_host(host) and path.name not in REQUEST_BUILDERS:
                        offenders.append(f'{path.relative_to(REPO)} names {host}')
                for url in re.findall(r'https?://[^\s\'"]+', value):
                    if router.is_provider_host(re.sub(r'^https?://([^/]+).*', r'\1', url)) and url not in router.CANONICAL:
                        offenders.append(f'{path.relative_to(REPO)} names non-canonical {url}')
        self.assertEqual(offenders, [], 'Use a canonical URL in a request builder; routes choose the endpoint.')

    def test_request_builders_send_only_through_provider_transport(self):
        for name in sorted(REQUEST_BUILDERS):
            with self.subTest(name):
                tree = ast.parse((ADVISOR / name).read_text(encoding='utf-8'))
                imports = list(imported(tree))
                self.assertIn(('provider_transport', 'urlopen'), imports)
                self.assertNotIn(('urllib.request', 'urlopen'), imports)
                self.assertFalse([module for module, _ in imports
                                  if any(module == lib or module.startswith(lib + '.') for lib in DIRECT_HTTP)])

    def test_transport_asks_the_router_before_sending(self):
        tree = ast.parse((ADVISOR / 'provider_transport.py').read_text(encoding='utf-8'))
        calls = {f'{node.func.value.id}.{node.func.attr}' for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                 and isinstance(node.func.value, ast.Name)}
        self.assertIn('model_router.authorize', calls)

    def test_server_installs_the_bypass_guard_before_loading_the_pinned_engine(self):
        tree = ast.parse((ADVISOR / 'server.py').read_text(encoding='utf-8'))
        guard = engine = None
        for node in tree.body:
            if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Attribute)
                    and node.value.func.attr == 'install_bypass_guard'):
                guard = node.lineno
            if isinstance(node, ast.ImportFrom) and node.module == 'guide_server' and engine is None:
                engine = node.lineno
        self.assertIsNotNone(guard, 'server.py must install the provider bypass guard.')
        self.assertIsNotNone(engine)
        self.assertLess(guard, engine)

    def test_pilot_service_runs_in_the_pilot_route_environment(self):
        service = (REPO / 'infrastructure/daylight-pilot/daylight-pilot.service').read_text(encoding='utf-8')
        self.assertIn(f'Environment={router.ENVIRONMENT_VARIABLE}=pilot', service.splitlines())


if __name__ == '__main__':
    unittest.main()
