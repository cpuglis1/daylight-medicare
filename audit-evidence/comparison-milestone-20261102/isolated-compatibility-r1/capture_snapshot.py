"""Capture one coherent source tree; preserve sealed data as enumerated links."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import sys

REPO = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SNAP = OUT / 'snapshot'

def digest(data):
    return hashlib.sha256(data).hexdigest()

def main():
    if SNAP.exists():
        raise RuntimeError('Preserve the existing snapshot; this is a one-capture driver.')
    start = datetime.now(timezone.utc).isoformat()
    # Read-only original reference preflight discovers every ancestor required
    # by the unchanged accepted-subset verifier. It runs no collection method.
    seen = set()
    tracing = True
    def audit(event, args):
        if tracing and event == 'open' and isinstance(args[0], str):
            path = Path(args[0]).absolute()
            if path.is_relative_to(REPO) and path.is_file():
                seen.add(path)
    sys.addaudithook(audit)
    sys.path.insert(0, str(REPO / 'cms-slice/scripts'))
    from l03_scoped_reference import lookup
    result = lookup({'year': 2026, 'offering_id': '2026:H1035:019:000'}, research=False)
    tracing = False
    if len(result['entries']) != 12:
        raise RuntimeError('Unexpected exact-reference preflight result.')
    copied = set()
    external = set()
    for path in seen:
        if '__pycache__' in path.parts:
            copied.add(path.parent.parent / (path.name.split('.')[0] + '.py'))
        elif path.suffix == '.py':
            copied.add(path)
        else:
            external.add(path)
    app = REPO / 'alternatives/advisor-first'
    for path in app.rglob('*'):
        if path.is_file() and not {'var', '__pycache__', '.pytest_cache'}.intersection(path.relative_to(app).parts):
            if path.suffix.lower() in {'.db', '.sqlite', '.sqlite3', '.pdf', '.pyc'}:
                raise RuntimeError('Unexpected prohibited snapshot file: ' + str(path))
            copied.add(path)
    lock = json.loads((app / 'engine-lock.json').read_text())
    copied.update(REPO / name for name in lock)
    # The lock pins its declared engine surface; imported stdlib-only support
    # modules in the same directory must also come from this capture.
    copied.update((REPO / 'alternatives/chat-first/cms-slice/scripts').glob('*.py'))
    for name in ['alternatives/chat-first/cms-slice/config', 'infrastructure/daylight-data/src']:
        for path in (REPO / name).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                copied.add(path)
    copied.update(REPO / name for name in [
        'alternatives/chat-first/cms-slice/apps/chat/zip-counties.json',
        'alternatives/chat-first/cms-slice/apps/chat-alternative/zip-counties.json',
        'alternatives/chat-first/cms-slice/apps/chat-alternative/baseline-content.json',
        'infrastructure/daylight-data/config/profile-contract.2026.json',
        'infrastructure/daylight-data/config/source-composition.2026.json',
        'docs/product/plan-comparison-2026-11-01/question-decision-map.json',
        'docs/data/integration-review-2026-10-29/review-catalog.json',
        'audit-evidence/advisor-conversation-quality-20261102/journey-spec.json',
        'audit-evidence/advisor-conversation-quality-20261102/evaluate_journey.py',
        'audit-evidence/comparison-milestone-20261102/run_actual_journey.py',
    ])
    # Root-bound identity factories use only these sealed local controls plus
    # the existing Unix socket. Their executable modules are copied above.
    packet = REPO / 'docs/data/infrastructure-execution-2026-10-30-local-full-db/build-r3'
    external.update(packet / name for name in ['BUILD_MANIFEST.json', 'TARGET.json', 'LOAD_COMPLETE.json'])
    external.update((packet / 'units').glob('*.json'))
    external.add(REPO / 'infrastructure/daylight-data/config/source-composition.2026.json')
    # The same source-purpose policy is copied for synthetic tests and retained
    # externally for the explicit real-repository identity factory.
    all_paths = sorted(copied | external)
    before = {str(path.relative_to(REPO)): digest(path.read_bytes()) for path in all_paths}
    rows = []
    for path in all_paths:
        name = str(path.relative_to(REPO))
        target = SNAP / name
        target.parent.mkdir(parents=True, exist_ok=True)
        data = path.read_bytes()
        if digest(data) != before[name]:
            raise RuntimeError('Source drift during capture: ' + name)
        if path in copied:
            target.write_bytes(data)
            kind = 'copied'
        else:
            target.symlink_to(path)
            kind = 'external_immutable_data_symlink'
        rows.append({'path': name, 'sha256': before[name], 'bytes': len(data), 'kind': kind,
                     'also_external_identity_control': path in copied and path in external,
                     'external_path': str(path) if path in external else None})
    mismatches = []
    for row in rows:
        name = row['path']
        if digest((REPO/name).read_bytes()) != before[name] or digest((SNAP/name).read_bytes()) != before[name]:
            mismatches.append(name)
    after_app = {str(p.relative_to(REPO)) for p in app.rglob('*') if p.is_file()
                 and not {'var', '__pycache__', '.pytest_cache'}.intersection(p.relative_to(app).parts)}
    expected_app = {str(p.relative_to(REPO)) for p in copied if p.is_relative_to(app)}
    manifest = {'schema': 'daylight.isolated-compatibility-capture.v1', 'started_utc': start,
        'completed_utc': datetime.now(timezone.utc).isoformat(), 'original_repository': str(REPO),
        'snapshot_root': str(SNAP), 'capture_equal_before_copy_and_after': not mismatches and after_app == expected_app,
        'mismatches': mismatches, 'app_population_changed': sorted(after_app ^ expected_app),
        'files': rows, 'copied_files': sum(r['kind'] == 'copied' for r in rows),
        'external_files': len(external), 'copied_bytes': sum(r['bytes'] for r in rows if r['kind'] == 'copied'),
        'sealed_external_data_are_not_snapshot_copies': True, 'databases_copied': 0,
        'pdfs_copied': 0, 'application_logic_changed': False, 'runtime_touched': False,
        'preflight': {'method': 'original accepted-reference lookup, read-only', 'offering': '2026:H1035:019:000', 'entries': 12}}
    (OUT/'CAPTURE.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (SNAP/'INPUT_HASHES.json').write_text(json.dumps(before, indent=2, sort_keys=True) + '\n')
    for row in rows:
        if row['kind'] == 'copied':
            (SNAP/row['path']).chmod(0o444)
    (SNAP/'INPUT_HASHES.json').chmod(0o444)
    print(json.dumps({k: v for k, v in manifest.items() if k != 'files'}, indent=2))
    if not manifest['capture_equal_before_copy_and_after']:
        raise RuntimeError('Unstable source capture; retain attempt and do not run suite.')

if __name__ == '__main__':
    main()
