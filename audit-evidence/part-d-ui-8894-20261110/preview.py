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
from test_part_d_pilot import FictionalRepository as FictionalPDPRepository
from adaptive_flow import metadata

with tempfile.TemporaryDirectory(prefix='medigap-profile-ui-') as temp:
    service = build(0, fixture=True, database=Path(temp) / 'profiles.sqlite3', medigap_repository=FictionalRepository(), part_d_repository=FictionalPDPRepository())
    flow = service.adaptive
    original_fixture = flow.fixture_result
    def scripted_fixture(message, current):
        # Exact fictional answers for UI mechanics only. Production extraction
        # and the pinned generic fixture interpreter are never modified.
        identifier = (current or {}).get('id')
        key = 'zip' if identifier == 'T03' else 'year' if identifier == 'RC03' else None
        if key and message in ('34101', '34108', '2026', '2027'):
            return {'mode':'report','task':'','task_quote':'','requests':[],
                'updates':[{'id':identifier,'fields':[{'key':key,'value':message}],
                    'entity':'profile','subject':'beneficiary','scope':'current','quote':message,'uncertain':False,'correction':True}],
                'fact_ids':[],'reflection':'','confirmation':''}
        return original_fixture(message, current)
    flow.fixture_result = scripted_fixture
    thread = threading.Thread(target=service.serve_forever, daemon=True);thread.start()
    spec = importlib.util.spec_from_file_location('preview_ui', APP / 'ui-8894/serve.py')
    ui = importlib.util.module_from_spec(spec);spec.loader.exec_module(ui)
    preview = ThreadingHTTPServer(('127.0.0.1', 0), ui.handler(f'http://127.0.0.1:{service.server_port}'))
    print(json.dumps({'url': f'http://127.0.0.1:{preview.server_port}/', 'fixture': True}), flush=True)
    try:
        preview.serve_forever()
    finally:
        preview.server_close();service.shutdown();service.server_close();thread.join()
