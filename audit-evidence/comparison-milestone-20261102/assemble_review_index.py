"""Account for exact original offering IDs across additive review packets.

This is a navigation/accounting index. It does not judge meaning, accept source
claims, deduplicate proposed atoms, or change the frozen denominator.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / 'docs/data/l03-ma-benefits-2026-11-02-whole-offering-r12'
WORKLIST = PACKET / 'UNRESOLVED_WORKLIST_R2.json'
WORKLIST_SHA = '9f1a8ed71f68ea8212ff5e50512eab7616896081ddc71434d3c5b4e12b0e4362'
sha = lambda body: hashlib.sha256(body).hexdigest()


def fingerprint(row):
    return sha(json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode())


def load_rows(path):
    data = path.read_bytes()
    decoded = gzip.decompress(data).decode() if path.suffix == '.gz' else data.decode()
    rows = [json.loads(line) for line in decoded.splitlines() if line]
    by_id = {}
    for ordinal, row in enumerate(rows, 1):
        identifier = row['canonical_id']
        if identifier in by_id:
            raise ValueError('Duplicate original ID in ' + str(path) + ': ' + identifier)
        by_id[identifier] = {'record_ordinal': ordinal, 'record_sha256': fingerprint(row)}
    return by_id, {'path': str(path.relative_to(ROOT)), 'sha256': sha(data), 'records': len(rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clinical', type=Path, required=True)
    parser.add_argument('--dental-base', type=Path, required=True)
    parser.add_argument('--dental-overlay', type=Path, action='append', default=[])
    parser.add_argument('--residual', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Preserve existing index revisions.')
    assert sha(WORKLIST.read_bytes()) == WORKLIST_SHA
    worklist = json.loads(WORKLIST.read_text())
    original = {}
    for group, entry in worklist['groups'].items():
        for row in entry['records']:
            assert row['canonical_id'] not in original
            original[row['canonical_id']] = {'kind': row['kind'], 'original_group': group,
                'original_states': row['original_states']}
    assert len(original) == 4675
    assert Counter(row['kind'] for row in original.values()) == {'claim': 1778, 'condition': 2897}
    inputs, sources = [], {}
    for role, path in [('clinical', args.clinical), ('dental-base', args.dental_base),
            ('residual', args.residual)] + [('dental-overlay-' + str(index), path)
                for index, path in enumerate(args.dental_overlay, 1)]:
        records, binding = load_rows(path.resolve())
        assert set(records) <= set(original), role
        sources[role] = records
        inputs.append({'role': role, **binding})
    clinical, dental, residual = (set(sources[role]) for role in ('clinical','dental-base','residual'))
    assert len(clinical) == 2126 and len(dental) == 1102 and len(residual) == 1482
    assert not clinical & residual and not dental & residual
    assert len(clinical & dental) == 35
    assert clinical | dental | residual == set(original)
    for role, records in sources.items():
        if role.startswith('dental-overlay-'):
            assert set(records) <= dental, role
    indexed = []
    for identifier, old in sorted(original.items()):
        primary = 'clinical' if identifier in clinical else 'residual' if identifier in residual else 'dental'
        current_record = primary if primary != 'dental' else next(role for role in reversed(sources)
            if role.startswith('dental-') and identifier in sources[role])
        references = [{'role': role, **records[identifier]} for role, records in sources.items() if identifier in records]
        indexed.append({'canonical_id': identifier, **old, 'primary_review_role': primary,
            'current_primary_record_role': current_record,
            'review_record_refs': references, 'accounting_is_semantic_closure': False})
    args.output.mkdir(parents=True)
    with (args.output/'per-id-review-index.jsonl.gz').open('xb') as raw:
        with gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0) as handle:
            for row in indexed:
                handle.write((json.dumps(row, sort_keys=True, separators=(',', ':'))+'\n').encode())
    receipt = {'schema':'daylight.whole-offering-review-navigation.v1',
        'observed_at':datetime.now(timezone.utc).isoformat(),'inputs':inputs,
        'original_worklist_sha256':WORKLIST_SHA,'original_required_ids':4675,
        'original_kinds':{'claim':1778,'condition':2897},'unique_primary_assignments':len(indexed),
        'primary_assignments':dict(Counter(row['primary_review_role'] for row in indexed)),
        'explicit_clinical_transfer_from_dental':sorted(clinical & dental),
        'unassigned_original_ids':[],'new_canonical_ids_created':0,'original_states_mutated':False,
        'proposed_atoms_deduplicated_or_adopted':False,'meaning_review_completed_by_index':False,
        'new_acceptance':False,'whole_offering_complete':False,'consumer_release':False,
        'index_sha256':sha((args.output/'per-id-review-index.jsonl.gz').read_bytes())}
    with (args.output/'ACCOUNTING_RECEIPT.json').open('x') as handle:
        json.dump(receipt, handle, indent=2); handle.write('\n')
    print(json.dumps({'indexed_original_ids':len(indexed),'primary_assignments':receipt['primary_assignments'],
        'new_acceptance':False}))


if __name__ == '__main__':
    main()
