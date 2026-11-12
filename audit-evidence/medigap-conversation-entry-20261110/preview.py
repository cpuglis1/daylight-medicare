"""Disposable fictional browser rehearsal; never uses the running stores or AI."""
import copy
from http.server import ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'alternatives/advisor-first'
sys.path[:0] = [str(APP), str(APP / 'tests')]
from server import build
from test_medigap_pilot import FictionalRepository
from adaptive_flow import metadata

with tempfile.TemporaryDirectory(prefix='medigap-profile-ui-') as temp:
    service = build(0, fixture=True, database=Path(temp) / 'profiles.sqlite3', medigap_repository=FictionalRepository())
    flow = service.adaptive
    guide, record = flow.initial()
    helper = '--helper' in sys.argv
    for identifier, fields in [('RC01', {'choice': 'someone' if helper else 'self'}), ('T02', {'choice': 'some'}),
            ('T03', {'zip': '34101'}), ('MG_AGE', {'choice': '68'}), ('MG_SEX', {'choice': 'Female'})]:
        if '--empty' in sys.argv or helper and identifier == 'MG_AGE':
            continue
        flow.capture(guide, record, {'id': identifier, 'fields': fields})
    metadata(record).update(task='compare', preparing=True)
    # Imported fictional legacy reports, so first interaction exercises normal
    # session binding without manufacturing a server-signed initial response.
    for envelope in guide['fields'].values():
        envelope['confirmation'] = 'confirmed_by_user'
    for envelope in record['facts'].values():
        envelope['confirmation'] = 'confirmed_by_user'
    record['natural']['provenance'] = {}
    flow.initial = lambda: copy.deepcopy((guide, record))
    thread = threading.Thread(target=service.serve_forever, daemon=True);thread.start()
    spec = importlib.util.spec_from_file_location('preview_ui', APP / 'ui-8894/serve.py')
    ui = importlib.util.module_from_spec(spec);spec.loader.exec_module(ui)
    preview = ThreadingHTTPServer(('127.0.0.1', 0), ui.handler(f'http://127.0.0.1:{service.server_port}'))
    print(json.dumps({'url': f'http://127.0.0.1:{preview.server_port}/', 'fixture': True}), flush=True)
    try:
        preview.serve_forever()
    finally:
        preview.server_close();service.shutdown();service.server_close();thread.join()
