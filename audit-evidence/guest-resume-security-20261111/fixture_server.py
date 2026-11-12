"""Temporary fictional backend and current UI for manual browser verification."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from threading import Thread
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'alternatives/advisor-first'))
from server import build


def only_loopback(event, args):
    if event in {'socket.bind', 'socket.connect', 'socket.getaddrinfo'}:
        address = args[0] if event == 'socket.getaddrinfo' else args[1][0]
        if address != '127.0.0.1':
            raise PermissionError('The browser fixture allows loopback traffic only.')


sys.addaudithook(only_loopback)
spec = importlib.util.spec_from_file_location('ui_proxy', ROOT / 'alternatives/advisor-first/ui-8894/serve.py')
proxy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proxy)
with tempfile.TemporaryDirectory(prefix='daylight-refresh-browser-') as folder:
    backend = build(0, fixture=True, database=Path(folder) / 'profiles.sqlite3')
    Thread(target=backend.serve_forever, daemon=True).start()
    ui = ThreadingHTTPServer(('127.0.0.1', 0), proxy.handler(f'http://127.0.0.1:{backend.server_port}'))
    print(json.dumps({'ui': ui.server_port, 'backend': backend.server_port, 'fixture': True}), flush=True)
    try:
        ui.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        ui.server_close()
        backend.shutdown()
        backend.server_close()
