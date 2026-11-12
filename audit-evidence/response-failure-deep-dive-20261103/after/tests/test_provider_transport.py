"""Exercise the real curl adapter with process pipes; never contact a provider."""
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import provider_transport as transport
from transport_diagnostics import failure_details


class InputPipe(io.BytesIO):
    def close(self):
        if not self.closed:
            self.captured = self.getvalue()
        super().close()


class Process:
    def __init__(self, output, code=0, running=False):
        self.stdin, self.stdout = InputPipe(), io.BytesIO(output)
        self.code, self.running = code, running
        self.terminated = self.killed = False

    def poll(self):
        return None if self.running else self.code

    def wait(self, timeout=None):
        if self.running:
            raise subprocess.TimeoutExpired('curl', timeout)
        return self.code

    def terminate(self):
        self.terminated, self.running = True, False

    def kill(self):
        self.killed, self.running = True, False


class TransportTests(unittest.TestCase):
    def request(self, url='https://api.openai.com/v1/responses/input_tokens', **kwargs):
        return Request(url, data=kwargs.get('data', b'{"input":"PRIVATE-TEXT"}'),
            method=kwargs.get('method', 'POST'),
            headers={'Authorization':'Bearer PRIVATE-KEY', 'Content-Type':'application/json'})

    def test_http_versions_interim_and_secure_private_invocation(self):
        for head in (b'HTTP/1.1 200 OK\r\n', b'HTTP/2 200\r\n',
                     b'HTTP/1.1 100 Continue\r\n\r\nHTTP/2 200\r\n'):
            process = Process(head+b'Content-Type: application/json\r\n\r\n{"input_tokens":300}')
            with self.subTest(head=head), patch.object(transport.subprocess,'Popen',return_value=process) as popen:
                with transport.urlopen(self.request(),timeout=15) as stream:
                    self.assertEqual(json.loads(stream.read(10001)), {'input_tokens':300})
                    self.assertEqual(stream.getcode(),200)
                popen.assert_called_once()
                args = popen.call_args.args[0]
                self.assertEqual(args[:4], ['/usr/bin/curl','-q','--config','-'])
                self.assertIn('--suppress-connect-headers',args)
                self.assertIn('=https',args)
                self.assertEqual(args[-4:],['--connect-timeout','10','--max-time','15'])
                self.assertFalse({'--insecure','-k','--location','-L','--retry'} & set(args))
                self.assertNotIn('PRIVATE',str(args))
                self.assertEqual(popen.call_args.kwargs['stderr'],subprocess.DEVNULL)
                self.assertIn(b'PRIVATE-KEY',process.stdin.captured)
                self.assertIn(b'PRIVATE-TEXT',process.stdin.captured)
                self.assertTrue(process.stdout.closed)

    def test_curl_failures_keep_fixed_diagnostics_and_cleanup(self):
        for code, kind in ((6,'dns'),(28,'timeout'),(35,'tls'),(60,'certificate'),(92,'http2')):
            process=Process(b'',code)
            with self.subTest(code=code), patch.object(transport.subprocess,'Popen',return_value=process) as popen:
                with self.assertRaises(transport.ProviderTransportError) as caught:
                    with transport.urlopen(self.request()):
                        self.fail('A failed connection cannot yield a response.')
                diagnostic=failure_details(caught.exception,'preflight')
                self.assertEqual(diagnostic,{'exception':'ProviderTransportError','phase':'preflight',
                    'curl_exit_code':code,'transport_category':kind})
                self.assertNotIn('PRIVATE',str(caught.exception)+json.dumps(diagnostic))
                popen.assert_called_once()
                self.assertTrue(process.stdout.closed)

    def test_http_error_keeps_status_and_allowlisted_code_only(self):
        process=Process(b'HTTP/2 429\r\n\r\n{"error":{"code":"rate_limit_exceeded","message":"PRIVATE-ERROR"}}')
        with patch.object(transport.subprocess,'Popen',return_value=process):
            with self.assertRaises(HTTPError) as caught:
                with transport.urlopen(self.request()):
                    self.fail('HTTP failure cannot be delivered as success.')
            detail=failure_details(caught.exception,'preflight')
            self.assertEqual(detail['http_status'],429)
            self.assertEqual(detail['provider_code'],'rate_limit_exceeded')
            self.assertNotIn('PRIVATE',json.dumps(detail)+str(caught.exception))
            caught.exception.close()

    def test_stream_failure_after_headers_is_not_silent_success(self):
        process=Process(b'HTTP/2 200\r\n\r\n',56)
        with patch.object(transport.subprocess,'Popen',return_value=process):
            with self.assertRaises(transport.ProviderTransportError) as caught:
                with transport.urlopen(self.request()) as stream:
                    list(stream)
        self.assertEqual(failure_details(caught.exception,'stream')['transport_category'],'receive')

    def test_early_consumer_exit_terminates_child(self):
        process=Process(b'HTTP/2 200\r\n\r\ndata: fictional\n',running=True)
        with patch.object(transport.subprocess,'Popen',return_value=process):
            with transport.urlopen(self.request()) as stream:
                self.assertEqual(next(stream),b'data: fictional\n')
        self.assertTrue(process.terminated)
        self.assertTrue(process.stdout.closed)

    def test_invalid_requests_never_start_a_child(self):
        for request in (self.request('http://api.openai.com/v1/responses'),
                        self.request('https://example.org/v1/responses'),
                        self.request(method='GET'),self.request(data=b'@secret'),self.request(data=b'[]')):
            with self.subTest(url=request.full_url),patch.object(transport.subprocess,'Popen') as popen:
                with self.assertRaises(ValueError):
                    with transport.urlopen(request):
                        pass
                popen.assert_not_called()
