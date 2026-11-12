#!/usr/bin/env python3
"""Reproduce this packet's read-only file/SQLite preservation comparison.

No service, API, budget method or write-capable database connection is used.
Only the output JSON in this evidence folder is written.  Row values never appear
in the output: personal rows are represented exclusively by SHA-256 digests.
"""
import collections
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3


PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[1]
NANO = 1_000_000_000


def row_hash(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()


def main():
    checked = datetime.now(timezone.utc)
    day = checked.date().isoformat()
    protected = json.loads((PACKET / 'protected-before.json').read_text())
    before_stores = json.loads((PACKET / 'stores-before.json').read_text())
    report = {
        'checkedAtUtc': checked.isoformat(),
        'scope': 'Only files and SQLite tables enumerated in the before snapshots. Each database is read through a mode=ro URI and one read transaction. No runtime or API calls.',
        'hashMethod': 'Files: SHA-256(bytes). Rows: SHA-256(json.dumps(tuple(row), sort_keys=True).encode()). Row comparisons use multisets; no personal values are emitted.',
        'limits': [
            'This is a dated snapshot, not a monitor. Run this script again after further diagnostics or browser sessions.',
            'A new browser session may add an unsaved guest row without creating a saved profile; additions and modifications remain distinguishable by exact row hashes.',
            'Measured ledger amounts are token-based estimates, not an invoice. Reserved or uncertain amounts are retained accounting holds, not proof of billed usage.',
            'This script does not test provider quota/credit availability and does not change or release any hold.',
        ],
        'protectedFiles': {}, 'stores': {},
    }
    for relative, before in protected.items():
        path = ROOT / relative
        after = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        report['protectedFiles'][relative] = {
            'beforeSha256': before, 'afterSha256': after, 'unchanged': before == after}
    for relative, before in before_stores.items():
        path = ROOT / relative
        database = {
            'beforeInode': before['inode'], 'afterInode': path.stat().st_ino,
            'inodeUnchanged': before['inode'] == path.stat().st_ino, 'tables': {},
        }
        connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
        try:
            connection.execute('PRAGMA query_only=ON')
            connection.execute('BEGIN')
            for table, old_hashes in before['tables'].items():
                quoted_table = '"' + table.replace('"', '""') + '"'
                rows = connection.execute('SELECT * FROM ' + quoted_table).fetchall()
                hashes = [row_hash(row) for row in rows]
                old, new = collections.Counter(old_hashes), collections.Counter(hashes)
                missing = list((old - new).elements())
                additions = list((new - old).elements())
                result = {
                    'beforeCount': len(old_hashes), 'afterCount': len(hashes),
                    'existingRowsUnchanged': not missing, 'exactRowsUnchanged': old == new,
                    'missingOrChangedBeforeRowCount': len(missing), 'addedRowCount': len(additions),
                    'afterRowSha256': hashes, 'missingOrChangedBeforeRowSha256': missing,
                    'addedRowSha256': additions,
                }
                if table == 'ai_charges':
                    columns = [row[1] for row in connection.execute('PRAGMA table_info("ai_charges")')]
                    remaining = collections.Counter(additions)
                    added_rows = []
                    for row, digest in zip(rows, hashes):
                        if remaining[digest]:
                            added_rows.append(dict(zip(columns, row)))
                            remaining[digest] -= 1
                    result['expectedSharedBudgetAdditions'] = {
                        'description': 'Append-only reservations/settlements from authorized fictional verification. No pre-existing row change is excused as budget activity; old rows are compared exactly.',
                        'statuses': dict(collections.Counter(row['status'] for row in added_rows)),
                        'days': dict(collections.Counter(row['day'] for row in added_rows)),
                        'chargedNanoUsd': sum(row['charged'] for row in added_rows),
                        'measuredNanoUsd': sum(row['measured'] or 0 for row in added_rows),
                        'heldNanoUsd': sum(row['charged'] for row in added_rows if row['status'] in {'reserved', 'uncertain'}),
                        'originalReservationBoundsNanoUsd': sum(row['reserved'] for row in added_rows),
                        'inputTokens': sum(row['input_tokens'] or 0 for row in added_rows),
                        'outputTokens': sum(row['output_tokens'] or 0 for row in added_rows),
                    }
                    # Match the pinned ledger's current-day/carryover accounting
                    # query directly, avoiding its write-capable summary method.
                    current = connection.execute(
                        "SELECT charged,measured,status FROM ai_charges WHERE day=? OR (day<? AND (status IN ('reserved','uncertain') OR finished_day=?))",
                        (day, day, day)).fetchall()
                    accounted = sum(row[0] for row in current)
                    measured = sum(row[1] or 0 for row in current)
                    held = sum(row[0] for row in current if row[2] in {'reserved', 'uncertain'})
                    result['currentUtcDayAccounting'] = {
                        'day': day, 'includesPriorUncertainAndLateCompletions': True,
                        'requestCount': len(current),
                        'statuses': dict(collections.Counter(row[2] for row in current)),
                        'dailyCapNanoUsd': 5*NANO, 'accountedNanoUsd': accounted,
                        'measuredNanoUsd': measured, 'heldNanoUsd': held,
                        'remainingNanoUsd': max(0, 5*NANO - accounted),
                        'accountedUsd': accounted / NANO, 'measuredUsd': measured / NANO,
                        'heldUsd': held / NANO, 'remainingUsd': max(0, 5*NANO - accounted) / NANO,
                        'reconciliationBlocked': bool(connection.execute(
                            "SELECT 1 FROM ai_meta WHERE key='blocked'").fetchone()),
                        'providerAvailability': 'Not checked; local cap remaining does not establish provider credit or quota.',
                    }
                database['tables'][table] = result
        finally:
            connection.rollback()
            connection.close()
        report['stores'][relative] = database
    report['summary'] = {
        'protectedFileCount': len(protected),
        'protectedFilesUnchanged': all(x['unchanged'] for x in report['protectedFiles'].values()),
        'allPreExistingRowsUnchanged': all(table['existingRowsUnchanged']
            for database in report['stores'].values() for table in database['tables'].values()),
        'allInodesUnchanged': all(database['inodeUnchanged'] for database in report['stores'].values()),
        'productionProfileRowsExactlyUnchanged': all(table['exactRowsUnchanged'] for table in
            report['stores']['alternatives/advisor-first/var/profiles/guides.sqlite3']['tables'].values()),
    }
    (PACKET / 'preservation-after.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['summary']))
    budget = report['stores']['cms-slice/var/ai-budget/usage.sqlite3']['tables']['ai_charges']
    print(json.dumps({'budgetDelta': budget['expectedSharedBudgetAdditions'],
                      'currentBudget': budget['currentUtcDayAccounting']}))


if __name__ == '__main__':
    main()
