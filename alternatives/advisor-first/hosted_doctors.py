"""D221: one read-only doctor index shared by both hosted apps on a private Unix socket.

Only three existing evidence operations are exposed. No visit state, model key,
history, budgets, public listener or request logging. Source gates run on each read.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import socketserver
import sys

MAX_REQUEST = 65536
MAX_RESPONSE = 8 * 1024 * 1024
METHODS = frozenset({'search', 'sites', 'network_matrix'})


def receive(stream, limit):
    raw = stream.readline(limit + 1)
    if len(raw) > limit or not raw.endswith(b'\n'):
        raise ValueError('Invalid bounded evidence message')
    return json.loads(raw)


class DoctorClient:
    def __init__(self, path):
        self.path = str(path)

    def call(self, method, *args, **kwargs):
        from daylight_data.serving.binding import ResearchServingError
        raw = json.dumps({'method': method, 'args': args, 'kwargs': kwargs}).encode() + b'\n'
        if len(raw) > MAX_REQUEST:
            raise ResearchServingError('DOCTOR_QUERY_TOO_LARGE')
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                connection.settimeout(45)
                connection.connect(self.path)
                connection.sendall(raw)
                with connection.makefile('rb') as stream:
                    value = receive(stream, MAX_RESPONSE)
            if not value.get('ok'):
                raise ResearchServingError(value.get('error', 'DOCTOR_SERVICE_UNAVAILABLE'))
            return value['result']
        except ResearchServingError:
            raise
        except (OSError, ValueError, KeyError):
            raise ResearchServingError('DOCTOR_SERVICE_UNAVAILABLE') from None

    def health(self):
        return self.call('health')

    def search(self, **kwargs):
        return self.call('search', **kwargs)

    def sites(self, *args, **kwargs):
        return self.call('sites', *args, **kwargs)

    def network_matrix(self, *args, **kwargs):
        return self.call('network_matrix', *args, **kwargs)


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(45)
        from daylight_data.serving.binding import ResearchServingError
        try:
            request = receive(self.rfile, MAX_REQUEST)
            if (not isinstance(request, dict) or set(request) != {'method','args','kwargs'}
                    or not isinstance(request['args'], list) or not isinstance(request['kwargs'], dict)):
                raise ValueError('Invalid operation')
            method = request['method']
            if method == 'health' and not request['args'] and not request['kwargs']:
                from daylight_data.serving.doctor_sources import SCOPE
                with self.server.doctors.reader.snapshot(**SCOPE):
                    result = {'ready': True, 'release': self.server.release}
            elif isinstance(method, str) and method in METHODS:
                result = getattr(self.server.doctors, method)(*request['args'], **request['kwargs'])
            else:
                raise ValueError('Unsupported operation')
            value = {'ok': True, 'result': result}
        except ResearchServingError as error:
            # The existing service errors are fixed codes, never query values.
            value = {'ok': False, 'error': str(error)}
        except Exception:
            value = {'ok': False, 'error': 'DOCTOR_SERVICE_UNAVAILABLE'}
        raw = json.dumps(value).encode() + b'\n'
        if len(raw) > MAX_RESPONSE:
            raw = b'{"ok":false,"error":"DOCTOR_RESPONSE_TOO_LARGE"}\n'
        self.wfile.write(raw)


def serve(path, doctors, release):
    # Serial reads bound resource use; the apps retain independent visit locks.
    server = socketserver.UnixStreamServer(str(path), Handler)
    os.chmod(path, 0o600)
    server.doctors, server.release = doctors, release
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if set(config) != {'foundation_root','foundation_binding','foundation_dsn','controls_dsn','socket','release'}:
        parser.error('Use the exact read-only evidence configuration')
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'infrastructure/daylight-data/src'))
    from daylight_data.serving.pilot_foundation import PilotFoundation, HOSTED_PURPOSE
    from daylight_data.serving.pilot_doctors import PilotDoctors
    doctors = PilotDoctors(PilotFoundation(config['foundation_binding'], root=Path(config['foundation_root']),
        package_dsn=config['foundation_dsn'], source_dsn=config['controls_dsn'], served=HOSTED_PURPOSE))
    path = Path(config['socket'])
    if path.exists():
        if not path.is_socket():
            raise ValueError('Unexpected socket path')
        path.unlink()
    with serve(path, doctors, config['release']) as server:
        server.serve_forever()


if __name__ == '__main__':
    main()
