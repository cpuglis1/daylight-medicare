"""Bind independently reviewed format outcomes to unchanged original obligations.

This is an additive review candidate, never a database/source-release loader.
Exact field-format evidence is distinct from complete benefit agreement.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / 'docs/data/l03-ma-benefits-2026-11-02-whole-offering-r12'
OUT = PACKET / 'native-format-integration-r1'
sha = lambda body: hashlib.sha256(body).hexdigest()
canonical_bytes = lambda row: json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-freeze', type=Path, required=True)
    parser.add_argument('--expected-review-freeze-sha256', required=True)
    args = parser.parse_args()
    if OUT.exists():
        raise ValueError('Preserve generated revisions.')
    bindings = []

    def read(path):
        raw = path.read_bytes()
        bindings.append({'path': str(path.relative_to(ROOT)), 'sha256': sha(raw), 'bytes': len(raw)})
        return raw

    def json_at(path):
        return json.loads(read(path))

    def lines_at(path):
        return [json.loads(line) for line in gzip.decompress(read(path)).splitlines()]

    def verify_freeze(path, expected=None):
        raw = read(path)
        if expected is not None:
            assert sha(raw) == expected
        entries = json.loads(raw)['files']
        if isinstance(entries, dict):
            entries = [{'path': name, 'sha256': value} for name, value in entries.items()]
        for entry in entries:
            relative = Path(entry['path'])
            member = ROOT / relative if str(relative).startswith(('docs/', 'audit-evidence/')) else path.parent / relative
            body = member.read_bytes()
            assert sha(body) == entry['sha256'], str(member)
            if 'bytes' in entry:
                assert len(body) == entry['bytes']
        return len(entries)

    review_freeze = args.review_freeze.resolve()
    assert review_freeze.is_relative_to(PACKET)
    review = review_freeze.parent
    replayed = verify_freeze(review_freeze, args.expected_review_freeze_sha256)
    verify_freeze(PACKET / 'native-format-catalog-correction-r2/FREEZE_R2.json',
        '07608d6a8e361d2eeaab8eb4bbcc838e4d68634d1ec3d2855e0ac4f3bd3dc0d2')
    verify_freeze(PACKET / 'joint-inventory-accounting-r1/JOINT_PROPOSAL_FREEZE_R1.json',
        '492a669f973db8605f0a0841c21b83eef78c69c5cf70ddb5fbe21198aebc730d')
    originals = {row['id']: row for row in lines_at(
        PACKET / 'joint-inventory-accounting-r1/original-offering-canonical-4675-unchanged.jsonl.gz')}
    original_ledger = {row['original_id']: row for row in lines_at(
        PACKET / 'joint-inventory-accounting-r1/original-4675-hash-and-primary-owner-ledger.jsonl.gz')}
    assert len(originals) == len(original_ledger) == 4675
    for identifier, original in originals.items():
        assert sha(canonical_bytes(original)) == original_ledger[identifier]['original_content_sha256']
    worklist = json_at(PACKET / 'UNRESOLVED_WORKLIST_R2.json')
    pointer_bindings = defaultdict(list)
    for group in worklist['groups'].values():
        for row in group['records']:
            for observation in row['source_observations']:
                if observation['layer'] == 'cms_json':
                    pointer = observation['native_locator']['pointer']
                    pointer_bindings[(row['canonical_id'], pointer)].append(observation)
    native_path = ROOT / 'docs/data/l03-ma-benefits-2026-11-01-whole-offering-r11/source-preparation/generated-r2/CMS-native-member.json'
    native_raw = read(native_path)
    assert sha(native_raw) == 'e40e423ec93ffecbd482ecc3c707ba53654bf522ac2d58cea720799f0080d52f'
    native = json.loads(native_raw)

    def at(pointer):
        value = native
        for part in pointer.strip('/').split('/'):
            value = value[int(part)] if isinstance(value, list) else value[part]
        return value

    decisions_path = review / 'PER_OBSERVATION_DECISIONS_1223.json'
    decisions = json_at(decisions_path)['records']
    assert len(decisions) == 1223
    integrated = []
    per_id = defaultdict(list)
    for ordinal, decision in enumerate(decisions, 1):
        assert canonical_bytes(at(decision['pointer'])) == canonical_bytes(decision['raw'])
        identifiers = ([decision['canonical_id']] if decision.get('canonical_id') else
            [entry['canonical_id'] for entry in decision['canonical_source_assessment_bindings']])
        assert identifiers and len(identifiers) == len(set(identifiers))
        joined = []
        for identifier in identifiers:
            original = originals[identifier]
            sources = pointer_bindings[(identifier, decision['pointer'])]
            assert sources
            assert all(source['observation_id'] in original['observation_ids'] for source in sources)
            joined.append({'original_id': identifier, 'kind': original['kind'],
                'original_content_sha256': original_ledger[identifier]['original_content_sha256'],
                'original_predicate': original['predicate'], 'original_context': original['context'],
                'original_states_unchanged': original['states'], 'source_observations': sources})
        identifier = 'R12-NATIVE-FORMAT-INTEGRATION-' + sha(canonical_bytes(
            [decision['packet'], decision['probe_record_ordinal'], decision['pointer']]))[:24]
        record = {'id': identifier, 'review_record_ordinal': ordinal,
            'review_record_sha256': sha(canonical_bytes(decision)),
            'original_bindings': joined, 'independently_reviewed_candidate': decision,
            'integration_role': 'field_format_and_source_projection_evidence_only',
            'original_canonical_payload_or_state_changed': False,
            'complete_benefit_meaning_agreement': False, 'new_canonical_obligation': False,
            'source_mapping_adopted': False, 'accepted_for_reference': False,
            'consumer_release': False}
        integrated.append(record)
        for original in joined:
            per_id[original['original_id']].append(identifier)
    assert len({row['id'] for row in integrated}) == 1223
    # These remain separately addressable evidence, not labels inherited by all
    # records with the same native field name.
    side_artifacts = [
        'FINAL_MODULE_PROJECTION_REPLAY.json', 'PBPD_HEADER_PROJECTION_REPLAY.json',
        'PBPD_CATEGORY_ROLLUP_REPLAY.json', 'POS_CONTROL_DECISIONS_63.json',
        'FINITE_FOLLOW_UP_REGISTER.json']
    side_refs = []
    for filename in side_artifacts:
        body = read(review / filename)
        side_refs.append({'path': str((review / filename).relative_to(ROOT)), 'sha256': sha(body)})
    OUT.mkdir()
    with (OUT / 'per-observation-format-integration.jsonl.gz').open('xb') as raw:
        with gzip.GzipFile(fileobj=raw, filename='', mode='wb', mtime=0) as handle:
            for row in integrated:
                handle.write(canonical_bytes(row) + b'\n')
    with (OUT / 'per-original-format-link-index.jsonl.gz').open('xb') as raw:
        with gzip.GzipFile(fileobj=raw, filename='', mode='wb', mtime=0) as handle:
            for identifier, original in sorted(originals.items()):
                handle.write(canonical_bytes({'original_id': identifier, 'kind': original['kind'],
                    'original_content_sha256': original_ledger[identifier]['original_content_sha256'],
                    'format_integration_record_ids': per_id.get(identifier, []),
                    'original_required_state_unchanged': True, 'equivalence_granted_by_link': False}) + b'\n')
    receipt = {'schema': 'daylight.native-format-integration-candidate.v1',
        'observed_at': datetime.now(timezone.utc).isoformat(), 'inputs': bindings,
        'independent_review_frozen_members_replayed': replayed,
        'packet_observations': len(integrated), 'originals_with_format_links': len(per_id),
        'verdict_counts': {packet: dict(Counter(row['independently_reviewed_candidate']['format_evidence_verdict']
            for row in integrated if row['independently_reviewed_candidate']['packet'] == packet))
            for packet in ['clinical', 'dental', 'residual']},
        'source_projection_and_follow_up_artifacts': side_refs,
        'original_required_before_after': [4675, 4675], 'global_required_before_after': [392570, 392570],
        'required_missing_unchanged': 16, 'new_obligations_adopted': 0,
        'new_semantic_aliases_adopted': 0, 'new_source_acceptances': 0,
        'new_decoded_labels_invented_by_integration': 0, 'database_writes': 0,
        'whole_offering_complete': False, 'consumer_release': False,
        'generator': {'path': str(Path(__file__).relative_to(ROOT)), 'sha256': sha(Path(__file__).read_bytes())},
        'scope_limit': 'This joins independent format evidence to original source-scoped obligations. It neither grants complete benefit agreement nor transforms research into source acceptance or personal authority.'}
    with (OUT / 'INTEGRATION_ACCOUNTING.json').open('x') as handle:
        json.dump(receipt, handle, indent=2); handle.write('\n')
    print(json.dumps({'packet_observations': len(integrated), 'originals_with_format_links': len(per_id),
        'new_adoption': False, 'new_acceptance': False}))


if __name__ == '__main__':
    main()
