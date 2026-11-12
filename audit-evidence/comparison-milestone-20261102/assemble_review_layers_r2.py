"""Build an additive source-review navigation index without changing meaning.

Every relationship names its source role. Locator and broad qualification links
remain distinct; neither is treated as an equivalence or acceptance decision.
Existing packet revisions and the original navigation index are read-only.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / 'docs/data/l03-ma-benefits-2026-11-02-whole-offering-r12'
OUT = PACKET / 'review-navigation-r2'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fingerprint(row):
    return sha(json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode())


def load(relative, member=None):
    path = PACKET / relative
    data = path.read_bytes()
    if relative.endswith('.jsonl.gz'):
        value = [json.loads(line) for line in gzip.decompress(data).decode().splitlines() if line]
    else:
        value = json.loads(data)
    return value if member is None else value[member], {
        'path': str(path.relative_to(ROOT)), 'sha256': sha(data), 'member': member}


def main():
    if OUT.exists():
        raise ValueError('Preserve previous generated revisions; choose a new output.')
    base_receipt, base_binding = load('review-navigation-r1/ACCOUNTING_RECEIPT.json')
    base, index_binding = load('review-navigation-r1/per-id-review-index.jsonl.gz')
    assert base_receipt['index_sha256'] == index_binding['sha256']
    by_id = {row['canonical_id']: row for row in base}
    assert len(base) == len(by_id) == 4675
    assert Counter(row['kind'] for row in base) == {'claim': 1778, 'condition': 2897}
    assert Counter(row['primary_review_role'] for row in base) == {
        'clinical': 2126, 'dental': 1067, 'residual': 1482}
    inputs = [base_binding, index_binding]
    # Replay the exact original per-ID artifacts to which r1 points.
    for binding in base_receipt['inputs']:
        assert sha((ROOT / binding['path']).read_bytes()) == binding['sha256']
        inputs.append(binding)

    layers = {}
    links = defaultdict(list)

    def add_layer(key, relative, selector, meaning, member=None):
        rows, binding = load(relative, member)
        assert isinstance(rows, list)
        layer = {**binding, 'records': len(rows), 'relationship_meaning': meaning,
            'grants_whole_original_equivalence': False, 'grants_acceptance': False}
        layers[key] = layer
        linked_ids = set()
        unlinked = []
        for ordinal, row in enumerate(rows, 1):
            selected = sorted(set(selector(row)))
            if not selected:
                unlinked.append({'record_ordinal': ordinal,
                    'local_id': row.get('id', row.get('leaf_id')),
                    'reason': 'No direct original-ID field selected; local/source-parent lineage remains in the full artifact.'})
            for identifier, relation in selected:
                assert identifier in by_id, (key, identifier)
                linked_ids.add(identifier)
                links[identifier].append({'layer': key, 'record_ordinal': ordinal,
                    'record_sha256': fingerprint(row),
                    'local_id': row.get('id', row.get('leaf_id', row.get('canonical_id'))),
                    'relationship': relation})
        layer['linked_original_ids'] = len(linked_ids)
        layer['records_without_direct_original_ID_link'] = unlinked
        layer['link_count'] = sum(len(v) for v in links.values()) - sum(
            v['link_count'] for k, v in layers.items() if k != key)

    def own_id(row):
        return [(row['canonical_id'], 'original_ID_review_record')]

    def clinical_lineage(row):
        return [(identifier, 'exact_assertion_locator;not_whole_leaf_equivalence')
                for identifier in row['exact_locator_original_ids']] + [
            (identifier, 'broader_parent_scope_dependency;not_direct_equivalence')
            for identifier in row['qualified_parent_original_ids']]

    add_layer('clinical_leaf_lineage_r2',
        'clinical-meaning-refinement-r2/leaf-original-lineage-and-novelty-decisions-corrected.jsonl.gz',
        clinical_lineage, 'Corrected material-leaf lineage; exact locator and broader qualification remain separate.')
    add_layer('clinical_original_retention_r2',
        'clinical-meaning-refinement-r2/full-4675-original-disposition-ledger-corrected.jsonl.gz',
        lambda row: [(row['original_id'], 'original_payload_retention_and_dependency_ledger')],
        'Conservation ledger for all originals; not a semantic approval of other workstreams.')
    add_layer('dental_carrier_alignment_r2',
        'post-freeze-carrier-dental-review-r2/per-id-carrier-alignments.jsonl.gz', own_id,
        'Original carrier alignment, read together with corrected parent units and conditions.')
    add_layer('dental_native_correction_r3',
        'dental-corrections-r3/per-id-native-meaning-review-corrected.jsonl.gz', own_id,
        'Latest bounded native/case correction overlay; raw observations and original payloads unchanged.')
    add_layer('dental_parent_readings_correction_r3',
        'dental-corrections-r3/reviewed-parent-source-units-corrected.jsonl.gz',
        lambda row: [(identifier, 'parent_source_unit_context;not_whole_original_equivalence')
            for identifier in row['old_canonical_ids']],
        'Corrected carrier parent readings, with separate individual condition records in the same packet.')
    add_layer('clinical_boundary_links_r1',
        'clinical-boundary-completion-r1/SEVENTEEN_OLD_CELL_LINKS.json', own_id,
        'Nine source-cell readings linked to 14 mixed originals; zero ownership transfer or new obligation.')
    add_layer('residual_native_correspondences_r4',
        'residual-meaning-review-r4/native-question-category-correspondences.json', own_id,
        'Exact question/category correspondence candidates; format authority is separately reviewed.',
        member='per_observation')
    add_layer('residual_material_atoms_r4',
        'residual-meaning-review-r4/material-atomic-predicates.json',
        lambda row: [(evidence['canonical_id'], 'atom_source_evidence;not_whole_original_equivalence')
            for evidence in row['source_evidence'] if 'canonical_id' in evidence],
        'Corrected residual material predicates; source-evidence links do not adopt inventory additions.')
    add_layer('residual_material_rules_r4',
        'residual-meaning-review-r4/material-predicate-rules.json',
        lambda row: [(evidence['canonical_id'], 'rule_source_evidence;not_whole_original_equivalence')
            for evidence in row.get('source_evidence', []) if 'canonical_id' in evidence]
            + [(identifier, 'explicit_existing_atom_reuse_in_rule')
                for identifiers in row.get('atom_bindings', {}).values()
                for identifier in identifiers if identifier.startswith('CANONICAL-')],
        'Corrected Boolean and modality rules; no clinical applicability decision.')

    ledger, _ = load('clinical-meaning-refinement-r2/full-4675-original-disposition-ledger-corrected.jsonl.gz')
    ledger = {row['original_id']: row for row in ledger}
    for identifier, row in by_id.items():
        old = ledger[identifier]
        assert old['kind'] == row['kind']
        assert old['states'] == row['original_states']
        row['original_content_sha256'] = old['original_content_sha256']
        row['additive_review_links'] = links.get(identifier, [])
        row['all_links_are_navigation_only'] = True
        row['complete_meaning_agreement_granted_by_index'] = False

    # Independent review scope is packet-level, not 4,675 implied approvals.
    review_paths = [
        'independent-clinical-review-recovery-r1/REVIEW_FREEZE_R1.json',
        'independent-clinical-refinement-review-r1/REVIEW_FREEZE_R1.json',
        'independent-clinical-refinement-review-r2/REVIEW_FREEZE_R2.json',
        'independent-dental-native-review-recovery-r1/FREEZE_R1.json',
        'independent-residual-review-r4/FREEZE_INDEPENDENT_R4.json']
    reviews = []
    for relative in review_paths:
        review, binding = load(relative)
        entries = review['files']
        entries = [{'path': path, 'sha256': digest} for path, digest in entries.items()] if isinstance(entries, dict) else entries
        for entry in entries:
            path = Path(entry['path'])
            path = ROOT / path if str(path).startswith('docs/') else (PACKET / relative).parent / path
            assert sha(path.read_bytes()) == entry['sha256'], str(path)
        reviews.append({**binding, 'frozen_members_replayed': len(entries),
            'scope': 'Read the independent review; no per-original equivalence inferred by this navigation.'})

    result = {
        'schema': 'daylight.whole-offering-review-navigation.v2',
        'observed_at': datetime.now(timezone.utc).isoformat(),
        'offering_id': '2026:H5652:002:000', 'base_inputs': inputs,
        'layers': layers, 'independent_review_freezes': reviews,
        'original_required_ids': 4675, 'original_kinds': {'claim': 1778, 'condition': 2897},
        'primary_assignments': {'clinical': 2126, 'dental': 1067, 'residual': 1482},
        'global_r9_required_unchanged': 392570, 'required_missing_unchanged': 16,
        'exact_clinical_transfer_from_dental': base_receipt['explicit_clinical_transfer_from_dental'],
        'new_canonical_obligations_adopted': 0, 'originals_retired': 0,
        'original_states_mutated': False, 'new_reference_acceptances': 0,
        'whole_offering_semantic_closure': False, 'consumer_release': False,
        'authority_note': 'Navigation only. Source meaning, complete agreement, novelty, release acceptance and applicability remain separately scoped decisions.'}
    OUT.mkdir()
    with (OUT / 'per-id-review-index.jsonl.gz').open('xb') as raw:
        with gzip.GzipFile(fileobj=raw, filename='', mode='wb', mtime=0) as handle:
            for identifier in sorted(by_id):
                handle.write((json.dumps(by_id[identifier], sort_keys=True, separators=(',', ':')) + '\n').encode())
    result['index_sha256'] = sha((OUT / 'per-id-review-index.jsonl.gz').read_bytes())
    result['producer_script'] = {'path': str(Path(__file__).relative_to(ROOT)), 'sha256': sha(Path(__file__).read_bytes())}
    with (OUT / 'ACCOUNTING_RECEIPT.json').open('x') as handle:
        json.dump(result, handle, indent=2); handle.write('\n')
    print(json.dumps({'indexed_original_ids': len(by_id), 'layers': len(layers),
        'review_freezes_replayed': len(reviews), 'new_acceptance': False}))


if __name__ == '__main__':
    main()
