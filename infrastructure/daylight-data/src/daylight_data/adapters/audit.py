"""Reproducible source transport and independent SQLite control report."""
from __future__ import annotations
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import platform
import sqlite3
import time
from urllib.parse import quote

from . import TYPED_LAYERS, account, iter_layer_records, iter_layer_projections
from .common import canonical_json


def audit_adapters(root: Path | str, include_projections: bool = True) -> dict:
    root = Path(root).resolve()
    report = {'schema': 'daylight-adapter-control-run/1', 'reference_year': 2026,
              'python': platform.python_version(), 'layers': {}, 'database_import_performed': False,
              'consumer_acceptance_created': False}
    for layer in TYPED_LAYERS:
        start = time.monotonic()
        control = account(iter_layer_records(root, layer))
        control['elapsed_seconds'] = round(time.monotonic() - start, 3)
        independent = {}
        for key, value in control['tables'].items():
            source, table = key.rsplit('#', 1)
            if source.endswith(('.sqlite', '.sqlite3')):
                uri = 'file:' + quote(str(root / source), safe='/') + '?mode=ro&immutable=1'
                with closing(sqlite3.connect(uri, uri=True)) as database:
                    escaped = '"' + table.replace('"', '""') + '"'
                    expected = database.execute('SELECT COUNT(*) FROM ' + escaped).fetchone()[0]
                independent[key] = {'expected_rows': expected, 'observed_rows': value['input_rows'],
                                    'matches': expected == value['input_rows']}
                if expected != value['input_rows']:
                    raise ValueError(f'Incomplete source table: {key}')
        control['independent_sqlite_controls'] = independent
        if include_projections:
            start = time.monotonic()
            counts = Counter(row.entity_type for row in iter_layer_projections(root, layer))
            control['full_projection_counts'] = dict(sorted(counts.items()))
            control['projection_elapsed_seconds'] = round(time.monotonic() - start, 3)
        report['layers'][layer] = control
    report['not_implemented_layers'] = [f'L{n:02}' for n in range(1, 16) if f'L{n:02}' not in TYPED_LAYERS]
    report['limitations'] = ['Source-row streaming and initial projections only; no PostgreSQL load or acceptance receipt.',
                             'Deterministic source order retains original duplicates and quarantine.',
                             'Other layer populations and typed domain projections remain required and unimplemented.']
    return report


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--skip-projections', action='store_true')
    args = parser.parse_args()
    report = audit_adapters(args.repository_root, not args.skip_projections)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(canonical_json({layer: row['source_rows'] for layer, row in report['layers'].items()}))


if __name__ == '__main__':
    main()
