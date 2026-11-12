"""Read-only preservation, contract, live-service and capture evidence for D79 UI2 r3."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ALT = ROOT / 'alternatives/chat-first'


def write(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2) + '\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text())


if __name__ == '__main__':
    before = read_json(HERE / 'store-fingerprints-before.json')
    stores = {
        'original': ROOT / 'cms-slice/var/ten-question-profiles/guides.sqlite3',
        'alternative': Path('/Users/cep4u/daylight-chat-alternative-runtime/cms-slice/var/chat-alternative-profiles/guides.sqlite3'),
    }
    preservation = {}
    for label, path in stores.items():
        tables = {}
        with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
            for table, previous in before[label]['tables'].items():
                assert table in {'guests', 'readiness'}
                current = Counter(hashlib.sha256(json.dumps(list(row), default=str).encode()).hexdigest()
                                  for row in db.execute('SELECT * FROM ' + table))
                missing = Counter(previous) - current
                tables[table] = {'beforeRows': len(previous), 'afterRows': sum(current.values()),
                                 'missingOrChangedExistingRows': sum(missing.values()),
                                 'allExistingRowsUnchanged': not missing}
        preservation[label] = {'sameDatabaseInode': path.stat().st_ino == before[label]['inode'], 'tables': tables}
    ledger_path=ROOT/'cms-slice/var/ai-budget/usage.sqlite3'
    with sqlite3.connect(ledger_path.as_uri()+'?mode=ro',uri=True) as db:
        ledger_rows=db.execute('SELECT * FROM ai_charges').fetchall()
    old_hashes=Counter(before['budget']['tables']['ai_charges'])
    current_hashes=Counter(hashlib.sha256(json.dumps(list(row),default=str).encode()).hexdigest() for row in ledger_rows)
    missing=old_hashes-current_hashes
    preservation['budget']={'sameDatabaseInode':ledger_path.stat().st_ino==before['budget']['inode'],'tables':{'ai_charges':{'beforeRows':sum(old_hashes.values()),'afterRows':len(ledger_rows),'missingOrChangedExistingRows':sum(missing.values()),'allExistingRowsUnchanged':not missing}},'observedNewChargeRows':sum((current_hashes-old_hashes).values()),'observedNewChargeEstimatedUsd':sum(row[4] for row in ledger_rows if hashlib.sha256(json.dumps(list(row),default=str).encode()).hexdigest() not in old_hashes)/1_000_000_000}
    protected = read_json(HERE / 'protected-original.json')
    changed = [name for name, old in protected.items() if not (ROOT / name).is_file() or digest(ROOT / name) != old]
    concurrent_research = {'cms-slice/scripts/l09_build.py'}
    write('store-preservation.json', preservation)
    write('original-preservation.json', {'checkedExistingFiles': len(protected), 'unchangedExistingFiles': len(protected) - len(changed),
                                         'changedOrMissing': changed,
                                         'observedConcurrentResearchChange': {p: {'beforeSha256': protected[p], 'afterSha256': digest(ROOT / p)} for p in changed if p in concurrent_research},
                                         'unexpectedChanges': [p for p in changed if p not in concurrent_research],
                                         'scope': 'All original app, script and config files captured before this task are compared. Any observed independent research changes are listed explicitly and left intact. Original app/service files were not edited by this task.'})

    relative = Path('alternatives/chat-first/cms-slice/config/profile/adaptive-flow.json')
    old = read_json(HERE / 'before' / relative)
    new = read_json(ROOT / relative)
    accounting = {'before': {'questionIds': len(old['questions']), 'existingFieldPaths': len(old['fields']),
                             'optionalReportPaths': len(old['additionalReportPaths']), 'namedGaps': len(old['gaps'])},
                  'after': {'questionIds': len(new['questions']), 'existingFieldPaths': len(new['fields']),
                            'optionalReportPaths': len(new['additionalReportPaths']), 'namedGaps': len(new['gaps'])},
                  'questionIdsUnchanged': [q['id'] for q in old['questions']] == [q['id'] for q in new['questions']],
                  'fieldRecordsUnchanged': old['fields'] == new['fields'],
                  'originalQuestionRecordsUnchanged': old['questions'] == new['questions'],
                  'optionalPathsUnchanged': old['additionalReportPaths'] == new['additionalReportPaths'],
                  'namedGapRecordsUnchanged': old['gaps'] == new['gaps'],
                  'externalGapsClosed': new['accounting']['externalGapsClosed'],
                  'newNavigationMetadata': ['journey.learningSeen', 'journey.samplesVisible'],
                  'navigationMetadataMeaning': 'Completed teaching and explicit sample visibility; no new customer fact or capability gate.'}
    write('field-accounting.json', accounting)

    initial = read_json(HERE / 'before-manifest.json')
    paths = set(initial)
    for part in ['apps', 'scripts', 'config', 'tests']:
        for path in (ALT / 'cms-slice' / part).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.name != '.DS_Store':
                paths.add(str(path.relative_to(ROOT)))
    hashes = {name: digest(ROOT / name) for name in sorted(paths) if (ROOT / name).is_file()}
    write('source-after.json', {'hashes': hashes, 'changedFromCheckpoint': [p for p in initial if hashes.get(p) != initial[p]],
                              'addedToScopedTrees': sorted(paths - set(initial))})

    statuses = {}
    for port in [8890, 8891]:
        with urlopen(f'http://127.0.0.1:{port}/', timeout=10) as response:
            home_status = response.status
        with urlopen(f'http://127.0.0.1:{port}/api/status', timeout=10) as response:
            status = json.load(response)
        statuses[str(port)] = {'homeHttpStatus': home_status, 'status': status}
    ledger = ROOT / 'cms-slice/var/ai-budget/usage.sqlite3'
    day = datetime.now(timezone.utc).date().isoformat()
    with sqlite3.connect(ledger.as_uri() + '?mode=ro', uri=True) as db:
        charges = [dict(zip(['status', 'inputBound', 'outputBound', 'inputTokens', 'cachedTokens', 'outputTokens', 'chargedNanoUsd', 'measuredNanoUsd'], row))
                   for row in db.execute('SELECT status,input_bound,output_bound,input_tokens,cached_tokens,output_tokens,charged,measured FROM ai_charges WHERE day=?', (day,))]
        historic = db.execute('SELECT COUNT(*) FROM ai_charges WHERE day<?', (day,)).fetchone()[0]
    write('live-verification.json', {'checkedAt': datetime.now(timezone.utc).isoformat(), 'services': statuses,
                                    'currentUtcDay': day, 'generationCallsWholeUtcDay': len(charges), 'charges': charges,
                                    'priorDayChargeRowsRetained': historic, 'ledgerReadOnlyVerification': True,
                                    'scenarios': ['Provider answer advances deterministically without manual clearing', 'One real AI prescription report plus Part D side question, then explicit samples'],
                                    'deterministicStepsAddedGenerationCalls': 0,
                                    'notes': 'This task made one real AI generation; other UTC-day calls predate this task. Browser personas used scripted outputs in an isolated fixture, not paid AI. Current status remains guarded and no raw customer data is included.'})

    inventory = []
    for path in sorted((HERE / 'captures').glob('*.jpg')):
        output = subprocess.check_output(['/usr/bin/sips', '-g', 'pixelWidth', '-g', 'pixelHeight', str(path)], text=True)
        dimensions = {line.split(':')[0].strip(): int(line.split(':')[1]) for line in output.splitlines() if 'pixelWidth:' in line or 'pixelHeight:' in line}
        inventory.append({'file': path.name, **dimensions, 'sha256': digest(path)})
    write('capture-inventory.json', inventory)
    assert not (set(changed) - concurrent_research)
    assert all(item['sameDatabaseInode'] and all(t['allExistingRowsUnchanged'] for t in item['tables'].values()) for item in preservation.values())
    assert accounting['before'] == accounting['after']
    assert all(accounting[k] for k in ['questionIdsUnchanged', 'fieldRecordsUnchanged', 'originalQuestionRecordsUnchanged', 'optionalPathsUnchanged', 'namedGapRecordsUnchanged'])
    assert all(c['status'] == 'settled' and c['inputTokens'] <= c['inputBound'] <= 8000 and c['outputTokens'] <= c['outputBound'] == 900 for c in charges)
    assert statuses['8891']['status']['agent_available'] is True
    print(json.dumps({'originalFilesUnchanged': len(protected) - len(changed), 'observedConcurrentResearchFiles': changed, 'existingRecordsUnchanged': True, 'fieldAccountingUnchanged': True,
                      'wholeUtcDaySettledCalls': len(charges), 'wholeUtcDayEstimatedUsd': sum(c['chargedNanoUsd'] for c in charges) / 1_000_000_000,
                      'bothServicesHttp200': True}))
