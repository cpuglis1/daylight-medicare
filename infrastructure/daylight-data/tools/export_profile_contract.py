#!/usr/bin/env python3
"""Export existing profile definitions only; never open a customer store."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCES = {
    'adaptive': 'alternatives/chat-first/cms-slice/config/profile/adaptive-flow.json',
    'inventory': 'alternatives/chat-first/cms-slice/config/profile/question-map.json',
    'template': 'alternatives/chat-first/cms-slice/config/profile/customer-profile.template.json',
    'runtime_policy': 'alternatives/chat-first/cms-slice/config/profile/capability-policy.json',
    'review_catalog': 'docs/data/integration-review-2026-10-29/review-catalog.json',
}


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def build_export(root=ROOT):
    sources = {}
    documents = {}
    for name, relative in SOURCES.items():
        raw = (root / relative).read_bytes()
        documents[name] = json.loads(raw)
        sources[name] = {'path': relative, 'sha256': hashlib.sha256(raw).hexdigest()}
    adaptive, inventory, template, runtime, catalog = (documents[name] for name in SOURCES)
    questions = adaptive['questions']
    ids = {q['id'] for q in questions}
    fields = set(adaptive['fields'])
    aliases = [q for q in inventory['questionMap'] if q['kind'] == 'documented_child']
    variants = [q for q in inventory['questionMap'] if q['kind'] == 'runtime_variant']
    primary = [q for q in questions if q['kind'] != 'documented_child']
    expected = (len(questions), len(ids), len(primary), len(fields), len(adaptive['gaps']), len(aliases), len(variants))
    if expected != (41, 41, 38, 78, 14, 3, 11):
        raise ValueError(f'Profile denominator changed: {expected}; a new reviewed contract is required.')
    if fields != set(template['fieldDefinitions']) or fields != set(catalog['profile_fields']):
        raise ValueError('Canonical field definitions and review crosswalk do not agree.')
    if {q['id'] for q in catalog['questions']} != ids:
        raise ValueError('Question review crosswalk does not preserve the canonical inventory.')
    if catalog['clarification_variants'] != variants or catalog['profile_gaps'] != adaptive['gaps']:
        raise ValueError('Review variants or gaps differ from the canonical definitions.')
    by_id = {q['id']: q for q in questions}
    for question in [*questions, *variants]:
        if set(question['fields']) - fields:
            raise ValueError(f"Unknown field binding in {question['id']}")
    for alias in aliases:
        if alias['id'] not in ids or alias['parent'] not in ids or not set(alias['fields']) <= set(by_id[alias['parent']]['fields']):
            raise ValueError(f"Invalid child alias {alias['id']}")
    for capability in catalog['capabilities']:
        if set(capability['question_ids']) - ids:
            raise ValueError(f"Unknown question in capability {capability['capability_id']}")
    payload = {
        'contract_id': 'daylight-profile-contract-2026-r1',
        'coverage_year': 2026,
        'authority': 'metadata_only_existing_reported_input_contract',
        'customer_rows_included': False,
        'mandatory_interview_added': False,
        'personal_recommendations_enabled': False,
        'domain_policy_approved': False,
        'source_versions': {'adaptive': adaptive['version'], 'inventory': inventory['version'], 'runtime_policy': runtime['version'], 'review_catalog': catalog['metadata']['catalog_id']},
        'source_bindings': sources,
        'counts': {'question_definitions': 41, 'primary_questions': 38, 'documented_child_aliases': 3, 'field_definitions': 78, 'representation_gaps': 14, 'clarification_variants': 11, 'additive_optional_report_paths': len(adaptive['additionalReportPaths']), 'runtime_capabilities': len(runtime['capabilities']), 'proposed_capability_bridges': len(catalog['capabilities'])},
        'questions': questions,
        'fields': adaptive['fields'],
        'field_envelope_definitions': template['fieldDefinitions'],
        'field_review_crosswalk': catalog['profile_fields'],
        'child_aliases': aliases,
        'clarification_variants': variants,
        'representation_gaps': adaptive['gaps'],
        'additive_optional_report_paths': adaptive['additionalReportPaths'],
        'question_review_crosswalk': catalog['questions'],
        'proposed_capability_bridges': catalog['capabilities'],
        'existing_runtime_policy': runtime,
        'boundaries': [
            'No customer guide, readiness facts, messages, credentials or session rows are exported.',
            'Child aliases and retained wording variants reuse existing fields; they are not extra mandatory questions.',
            'Reports, source validation and exact capability acceptance remain separate gates.',
            'Proposed review crosswalks do not implement or accept new capabilities.',
            'Existing stores, consent, AI context, budget and unknown/deferred rules are unchanged.',
        ],
    }
    payload['content_sha256'] = hashlib.sha256(canonical_bytes(payload)).hexdigest()
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Compare the checked-in export without writing.')
    args = parser.parse_args()
    target = ROOT / 'infrastructure/daylight-data/config/profile-contract.2026.json'
    expected = json.dumps(build_export(), ensure_ascii=False, indent=2) + '\n'
    if args.check:
        if not target.exists() or target.read_text() != expected:
            raise SystemExit('Profile metadata export differs; inspect sources before explicitly rebuilding.')
        print('Profile metadata export matches its exact source hashes and 41/78/14 inventory.')
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(expected)
        print(f'Wrote {target}: metadata only, no customer store access.')


if __name__ == '__main__':
    main()
