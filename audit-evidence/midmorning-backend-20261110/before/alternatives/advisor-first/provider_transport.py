"""Variant-local verified TLS transport using the system curl TLS backend.

Credentials and JSON travel through a private stdin pipe, never command arguments
or files. This performs one request, with no redirects or automatic retry.
Before anything is sent, model_router checks the request against the static
route list (AI-04); a request with no matching route is refused, never rerouted.
"""
from contextlib import contextmanager, suppress
from email.parser import BytesHeaderParser
from http.client import HTTPException
import io
import json
import math
import re
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import Request

from identifier_guard import find_transport_identifiers
import model_router


# Canonical URLs callers may build; the matching route picks the endpoint.
ENDPOINTS = frozenset(model_router.CANONICAL)
FAILURE = 'The verified AI connection could not complete.'
BODY_BOUND = 1_000_000


class ProviderTransportError(URLError):
    """Only fixed failure categories and the curl exit status may escape."""
    def __init__(self, category, curl_exit_code=None):
        super().__init__(FAILURE)
        self.transport_category = category
        self.curl_exit_code = curl_exit_code


def _failed(process, category):
    code = process.poll()
    if code is None:
        try:
            code = process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            code = None
    kinds = {5:'proxy',6:'dns',7:'connect',18:'partial_response',28:'timeout',35:'tls',
             51:'certificate',58:'certificate',60:'certificate',
             52:'empty_response',55:'send',56:'receive',92:'http2'}
    return ProviderTransportError(kinds.get(code,category),code)


def _quote(value):
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace(
        '\t', '\\t').replace('\r', '\\r').replace('\n', '\\n') + '"'


def _configuration(request):
    if not isinstance(request, Request) or request.full_url not in ENDPOINTS:
        raise ValueError('Use an approved AI endpoint.')
    if request.get_method() != 'POST':
        raise ValueError('Use a POST AI request.')
    data = request.data
    if not isinstance(data, bytes) or not 1 <= len(data) <= BODY_BOUND:
        raise ValueError('Use a bounded JSON object.')
    try:
        body = data.decode('utf-8')
        parsed = json.loads(body)
        if not isinstance(parsed, dict):
            raise ValueError('Use a JSON object.')
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('Use a JSON object.') from error
    # HP-07 backstop: an identifier in an outgoing model request means an
    # earlier check was bypassed. Refuse to send; report only the category.
    if find_transport_identifiers(body):
        raise ProviderTransportError('identifier_blocked')
    # AI-03/AI-04: the static route list decides whether this request may go,
    # to which endpoint and with which project header. There is no fallback.
    try:
        route = model_router.authorize(request.full_url, request.header_items(), parsed)
    except model_router.RouteBlocked as error:
        raise ProviderTransportError(error.category) from None
    if route.changed:
        body = json.dumps(route.body, ensure_ascii=False, separators=(',', ':'))
    # Object-only JSON also excludes curl's @filename data-binary syntax.
    fields = [('url', route.url), ('request', 'POST')]
    for name, value in route.headers:
        if (not re.fullmatch(r'[A-Za-z0-9!#$%&\'*+.^_`|~-]+', name)
                or not isinstance(value, str) or '\r' in value or '\n' in value
                or '\x00' in value):
            raise ValueError('Use valid request headers.')
        fields.append(('header', name + ': ' + value))
    fields.append(('data-binary', body))
    return ('\n'.join(name + ' = ' + _quote(value) for name, value in fields) + '\n').encode('utf-8')


def _cleanup(process):
    for pipe in (process.stdin, process.stdout):
        if pipe is not None:
            with suppress(OSError):
                pipe.close()
    if process.poll() is None:
        with suppress(OSError):
            process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            with suppress(OSError):
                process.kill()
            process.wait(timeout=2)
    else:
        process.wait()


def _exit_ok(process):
    try:
        code = process.wait(timeout=2)
    except subprocess.TimeoutExpired as error:
        raise ProviderTransportError('process_timeout') from error
    if code:
        raise _failed(process,'process_exit')


def _headers(process):
    for _ in range(5):
        line = process.stdout.readline(1025)
        match = re.fullmatch(rb'HTTP/\d(?:\.\d)? (\d{3})(?: [^\r\n]*)?\r?\n', line)
        if not match:
            raise _failed(process,'invalid_headers' if line else 'empty_headers')
        status = int(match[1])
        lines = []
        size = 0
        while True:
            line = process.stdout.readline(8193)
            size += len(line)
            if not line or len(line) > 8192 or size > 65536:
                raise _failed(process,'invalid_headers')
            if line in {b'\n', b'\r\n'}:
                break
            lines.append(line)
        if status >= 200:
            return status, BytesHeaderParser().parsebytes(b''.join(lines))
    raise ProviderTransportError('too_many_interim_responses')


class _Stream:
    def __init__(self, process, status, headers):
        self.process, self.status, self.headers = process, status, headers

    def read(self, size=-1):
        bounded = BODY_BOUND + 1 if size is None or size < 0 else min(size, BODY_BOUND + 1)
        value = self.process.stdout.read(bounded)
        if len(value) > BODY_BOUND:
            raise URLError(FAILURE)
        # A short bounded read reached EOF. Check curl's status before a
        # partial body gets mistaken for a completed provider JSON response.
        if len(value) < bounded:
            _exit_ok(self.process)
        return value

    def readline(self, size=-1):
        value = self.process.stdout.readline(200001 if size is None or size < 0 else size)
        if not value:
            _exit_ok(self.process)
        return value

    def __iter__(self):
        return self

    def __next__(self):
        line = self.readline()
        if not line:
            raise StopIteration
        return line

    def getcode(self):
        return self.status


@contextmanager
def urlopen(request, timeout=40):
    """Open exactly one approved POST while preserving urllib's error contract."""
    configuration = _configuration(request)
    if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout) or not 0 < timeout <= 120):
        raise ValueError('Use a bounded connection timeout.')
    # -q must be first: ignore user curl configuration. Default certificate and
    # hostname checks stay enabled. No location, retry or insecure option.
    arguments = ['/usr/bin/curl', '-q', '--config', '-', '--include',
        '--suppress-connect-headers', '--no-buffer', '--silent', '--proto', '=https',
        '--connect-timeout', str(min(10, timeout)), '--max-time', str(timeout)]
    process = None
    try:
        process = subprocess.Popen(arguments, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        process.stdin.write(configuration)
        process.stdin.close()
        status, headers = _headers(process)
        stream = _Stream(process, status, headers)
        if not 200 <= status < 300:
            body = process.stdout.read(8192)
            raise HTTPError(request.full_url, status, 'AI provider HTTP request failed.',
                            headers, io.BytesIO(body))
        yield stream
    except (HTTPError, ProviderTransportError):
        raise
    except (OSError, HTTPException) as error:
        raise URLError(FAILURE) from error
    finally:
        if process is not None:
            _cleanup(process)
