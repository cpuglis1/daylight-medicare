"""Audit-only launcher: captured code, controlled local transport and data reads."""
from pathlib import Path
import atexit
import hashlib
import json
import os
import runpy
import socket
import sys
import time

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[2]
SNAP = OUT/'snapshot'
mode = 'reference'
if mode not in {'reference'}:
    raise ValueError('Use one explicit bounded mode.')
receipt = OUT / (mode + '-execution-guard.json')
if receipt.exists():
    raise ValueError('Preserve prior attempts.')
capture = json.loads((OUT/'CAPTURE.json').read_text())
external = {str((REPO/r['path']).absolute()): r['sha256'] for r in capture['files'] if r['external_path']}
reads, violations, connects = set(), [], []
started = time.time()
def audit(event, args):
    if event == 'open' and isinstance(args[0], str):
        path = Path(os.path.abspath(args[0]))
        if path.is_relative_to(REPO) and not path.is_relative_to(OUT):
            write = ((isinstance(args[1], str) and any(c in args[1] for c in 'wax+'))
                     or (len(args) > 2 and isinstance(args[2], int) and args[2] & (os.O_WRONLY | os.O_RDWR)))
            if write or str(path) not in external:
                violations.append({'event': event, 'path': str(path), 'write': bool(write)})
                raise PermissionError('Audit forbids mutable workspace or customer-store access: ' + str(path))
            reads.add(str(path))
    elif event in {'socket.connect', 'socket.connect_ex'}:
        address = args[1]
        connects.append(str(address))
        if isinstance(address, tuple) and address[0] not in {'127.0.0.1', '::1', 'localhost'}:
            violations.append({'event': event, 'address': str(address)})
            raise PermissionError('Audit forbids external network transport.')
        if isinstance(address, str) and not address.startswith(str(REPO/'infrastructure/daylight-data/.state/socket') + '/'):
            violations.append({'event': event, 'address': address})
            raise PermissionError('Audit allows only the declared research PostgreSQL Unix socket.')
sys.addaudithook(audit)

def finish():
    modules = {}
    for name, module in list(sys.modules.items()):
        filename = getattr(module, '__file__', None)
        if filename and str(filename).startswith(str(REPO)):
            modules[name] = str(filename)
    mismatches = []
    for row in capture['files']:
        target = SNAP/row['path']
        if hashlib.sha256(target.read_bytes()).hexdigest() != row['sha256']:
            mismatches.append(row['path'])
        if row['external_path'] and hashlib.sha256(Path(row['external_path']).read_bytes()).hexdigest() != row['sha256']:
            mismatches.append('external:' + row['path'])
    data = {'mode': mode, 'elapsed_seconds': round(time.time()-started, 3),
        'workspace_access_violations': violations, 'external_reads': sorted(reads),
        'connect_addresses': sorted(set(connects)), 'loaded_workspace_modules': modules,
        'snapshot_and_external_hash_mismatches': mismatches,
        'all_workspace_modules_loaded_from_snapshot': all(str(p).startswith(str(SNAP)+'/') for p in modules.values()),
        'paid_transport_enabled': False, 'runtime_processes_read_or_changed': False}
    receipt.write_text(json.dumps(data, indent=2) + '\n')
atexit.register(finish)

if mode == 'reference':
    sys.path.insert(0, str(SNAP/'alternatives/advisor-first/tests'))
    sys.argv = ['unittest', 'test_published_reference', '-v']
    runpy.run_module('unittest', run_name='__main__')
else:
    sys.argv = ['run_isolated_actual_journey.py', '--output', str(OUT/'actual-identity-http-journey.json'),
                '--input-manifest', str(SNAP/'INPUT_HASHES.json')]
    runpy.run_path(str(SNAP/'audit-evidence/comparison-milestone-20261102/isolated-compatibility-r1/run_isolated_actual_journey.py'), run_name='__main__')
