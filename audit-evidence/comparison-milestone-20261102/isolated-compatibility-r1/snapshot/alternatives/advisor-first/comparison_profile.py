"""Pure, private comparison view of existing guide/readiness reports.

The caller must supply one owner-bound, consistent server snapshot. This module
does not authenticate, save, fetch evidence, send model context or authorize an
output. Returned values are private report data, not an AI-context allowlist.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

from natural_state import CONFIRMATIONS, validate_state

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / 'infrastructure/daylight-data/config/profile-contract.2026.json'
DESIGN_PATH = ROOT / 'docs/product/plan-comparison-2026-11-01/question-decision-map.json'
ADAPTER_VERSION = 'advisor-comparison-profile-20261101-r1'
SITUATION_PATHS = {'retirement': 'guide.fields.situation.retirement',
                   'age65': 'guide.fields.situation.age65'}
ENTITY = re.compile(r'(?:doctor|medicine)-(?:extra-)?[0-9]{1,3}\Z')
UNKNOWN = {'unknown', 'not sure', 'unsure', 'idk'}
DEFERRED = {'deferred', 'check later', 'later', 'add later'}
DECLINED = {'declined', 'decline'}
DISPOSITION_STATES = {'explicit_unknown': 'unknown', 'deferred': 'deferred',
    'not_saved': 'unanswered', 'needs_review': 'stale', 'blocked_dependency': 'unanswered',
    'declined': 'declined', 'conflicting': 'conflicting', 'superseded': 'superseded'}
SCOPE_KEYS = {'task', 'year', 'county_fips', 'state', 'mode', 'as_of', 'category',
              'geography', 'time_scope'}
SOURCE_PATHS = {
    'adaptive': 'alternatives/chat-first/cms-slice/config/profile/adaptive-flow.json',
    'inventory': 'alternatives/chat-first/cms-slice/config/profile/question-map.json',
    'template': 'alternatives/chat-first/cms-slice/config/profile/customer-profile.template.json',
    'runtime_policy': 'alternatives/chat-first/cms-slice/config/profile/capability-policy.json',
    'review_catalog': 'docs/data/integration-review-2026-10-29/review-catalog.json',
}


class ComparisonProfileError(ValueError):
    """Fixed-code errors contain no submitted values or private identifiers."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _digest(value):
    try:
        encoded = json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(',', ':'), allow_nan=False).encode()
    except (TypeError, ValueError, RecursionError):
        raise ComparisonProfileError('PROFILE_VALUE_NOT_JSON') from None
    return hashlib.sha256(encoded).hexdigest()


def _load_contract():
    try:
        contract = json.loads(CONTRACT_PATH.read_text())
        design = json.loads(DESIGN_PATH.read_text())
        unsigned = {k: v for k, v in contract.items() if k != 'content_sha256'}
        if _digest(unsigned) != contract['content_sha256']:
            raise ComparisonProfileError('PROFILE_CONTRACT_DIGEST_MISMATCH')
        if set(contract['source_bindings']) != set(SOURCE_PATHS):
            raise ComparisonProfileError('PROFILE_CONTRACT_SOURCE_DRIFT')
        for name, binding in contract['source_bindings'].items():
            if binding['path'] != SOURCE_PATHS[name]:
                raise ComparisonProfileError('PROFILE_CONTRACT_SOURCE_DRIFT')
            source = (ROOT / binding['path']).resolve()
            if not source.is_relative_to(ROOT.resolve()) or hashlib.sha256(source.read_bytes()).hexdigest() != binding['sha256']:
                raise ComparisonProfileError('PROFILE_CONTRACT_SOURCE_DRIFT')
        ids = {q['id'] for q in contract['questions']}
        expected_ids = {f'T{i:02d}' for i in range(1, 11)} | {f'RC{i:02d}' for i in range(1, 29)} | {'RC11.C1', 'RC16.C1', 'RC16.C2'}
        if (ids != expected_ids or len(contract['questions']) != 41 or len(contract['fields']) != 78
                or len(contract['representation_gaps']) != 14 or len(contract['child_aliases']) != 3
                or len(contract['clarification_variants']) != 11
                or {g['id'] for g in contract['representation_gaps']} != {f'G{i:02d}' for i in range(1, 15)}):
            raise ComparisonProfileError('PROFILE_CONTRACT_ACCOUNTING_MISMATCH')
        if (design['profile_contract_content_sha256'] != contract['content_sha256']
                or {q['question_id'] for q in design['questions']} != ids
                or len(design['questions']) != 41):
            raise ComparisonProfileError('PROFILE_DESIGN_ACCOUNTING_MISMATCH')
        definitions = {q['id']: q for q in contract['questions']}
        for question in design['questions']:
            if question['canonical_paths'] != definitions[question['question_id']]['fields']:
                raise ComparisonProfileError('PROFILE_DESIGN_FIELD_DRIFT')
        return contract, design
    except ComparisonProfileError:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, IndexError):
        raise ComparisonProfileError('PROFILE_CONTRACT_UNAVAILABLE') from None


def _revision(value):
    if type(value) is not int or value < 0:
        raise ComparisonProfileError('PROFILE_REVISION_INVALID')
    return value


def _envelope(container, key):
    value = container.get(key, {})
    if (not isinstance(value, dict) or value.get('status') is not None
            and not isinstance(value['status'], str)):
        raise ComparisonProfileError('PROFILE_ENVELOPE_INVALID')
    return value


def _state(value, envelope, *, disposition=None, field_missing=False):
    state = envelope.get('status')
    if envelope.get('stale') or state in {'stale', 'needs_review'}:
        return 'stale'
    if state in {'tentative', 'conflicting', 'superseded'}:
        return state
    if state == 'unknown':
        return 'unknown'
    if state == 'skipped':
        return 'deferred'
    if disposition:
        return disposition
    if field_missing or value is None or value == '':
        return 'unanswered'
    if isinstance(value, str):
        word = value.casefold().strip()
        if word in UNKNOWN:
            return 'unknown'
        if word in DEFERRED:
            return 'deferred'
        if word in DECLINED:
            return 'declined'
        if word == 'none':
            return 'explicit_none'
    return 'reported'


def _precision(value):
    if isinstance(value, dict) and set(value) == {'month', 'year'}:
        return 'month_without_year' if value['year'] is None else 'month_and_year'
    if isinstance(value, str):
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            return 'day'
        if re.fullmatch(r'\d{4}-\d{2}', value):
            return 'month'
        if re.fullmatch(r'\d{4}', value):
            return 'source_text_four_digits'
        if value == 'soonest':
            return 'preference_without_date'
    return 'source_native'


def build_comparison_profile(guide, record, *, requested_scope=None, subject_id='beneficiary'):
    """Normalize trusted in-memory reports; preserve unknowns and all 41 meanings.

    ``subject_id`` is a caller-bound logical subject within this snapshot, not a
    discovered person/account identity. ``requested_scope`` is a server request;
    it never supplies reported enrollment, residency, dates or output authority.
    """
    if (not isinstance(guide, dict) or not isinstance(record, dict)
            or guide.get('schemaVersion') != 2 or record.get('schemaVersion') != 1
            or not isinstance(guide.get('fields'), dict) or not isinstance(record.get('facts'), dict)
            or not isinstance(subject_id, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}', subject_id)):
        raise ComparisonProfileError('PROFILE_INPUT_INVALID')
    guide_revision, readiness_revision = _revision(guide.get('stateVersion')), _revision(record.get('stateVersion'))
    if requested_scope is not None and (not isinstance(requested_scope, dict) or set(requested_scope) - SCOPE_KEYS):
        raise ComparisonProfileError('PROFILE_SCOPE_INVALID')
    scope = copy.deepcopy(requested_scope or {})
    _digest(scope)
    try:
        validate_state(record)
    except (TypeError, ValueError, KeyError):
        raise ComparisonProfileError('PROFILE_NATURAL_STATE_INVALID') from None
    contract, design = _load_contract()
    natural = record.get('natural', {})
    conversation = record.get('conversation', {})
    if not isinstance(conversation, dict):
        raise ComparisonProfileError('PROFILE_CONVERSATION_INVALID')
    provenance = natural.get('provenance', {})
    baseline_dispositions = conversation.get('baselineDispositions', {})
    skipped = conversation.get('skippedDetails', {})
    item_revisions = conversation.get('itemRevisions', {})
    invalidations = conversation.get('itemInvalidations', {})
    if any(not isinstance(x, dict) for x in (baseline_dispositions, skipped, item_revisions, invalidations,
            record.get('dispositions', {}), record.get('entityDispositions', {}), conversation.get('details', {}))):
        raise ComparisonProfileError('PROFILE_DISPOSITION_INVALID')
    if any(not isinstance(state, str) or state not in {'unknown', 'deferred'}
           for state in [*baseline_dispositions.values(), *skipped.values()]):
        raise ComparisonProfileError('PROFILE_DISPOSITION_INVALID')
    issues, facts = [], []

    def issue(code, path, item_id=None):
        entry = {'code': code, 'path': path, 'severity': 'hold'}
        if item_id is not None:
            entry['item_id'] = item_id
        if entry not in issues:
            issues.append(entry)

    def report(path, value, envelope, native_ref, *, question=None, item_id=None,
               missing=False, role='reported_fact', disposition=None):
        if not isinstance(envelope, dict):
            raise ComparisonProfileError('PROFILE_ENVELOPE_INVALID')
        revision = envelope.get('revision')
        invalid = False
        if (path=='guide.fields.coverage.current' and isinstance(value,list)
                and 'advantage' in value and set(value)&{'original','medigap'}):
            issue('CURRENT_COVERAGE_PATH_AMBIGUOUS',path,item_id)
            invalid=True
        if revision is not None:
            _revision(revision)
        record_revision = guide_revision if path.startswith('guide.') else readiness_revision
        if revision is not None and revision > record_revision:
            issue('REPORT_REVISION_AHEAD_OF_RECORD', path, item_id)
            invalid = True
        base_ref = native_ref.split('.', 2)[:2]
        base_ref = '.'.join(base_ref) if native_ref.startswith('readiness.') else native_ref
        capture = provenance.get(native_ref, provenance.get(base_ref))
        method, confirmation, temporal_scope, capture_subject = 'legacy_unclassified', 'legacy_unclassified', 'unknown', 'unknown'
        supersedes = None
        if capture:
            is_field_capture = native_ref in provenance and native_ref.startswith('readiness.') and native_ref.count('.') > 1
            valid_revision = capture['revision'] <= (revision if revision is not None else -1) if is_field_capture else capture['revision'] == revision
            if not valid_revision:
                issue('PROVENANCE_REVISION_MISMATCH', path, item_id)
                invalid = True
            else:
                method, confirmation = capture['method'], CONFIRMATIONS[capture['status']]
                temporal_scope, capture_subject = capture['scope'], capture['subject']
                revision = capture['revision']
                supersedes = capture['supersedesRevision']
                if (envelope.get('confirmation') in CONFIRMATIONS.values()
                        and envelope['confirmation'] != confirmation):
                    issue('PROVENANCE_CONFIRMATION_MISMATCH', path, item_id)
                    invalid = True
                if capture_subject == 'unclear':
                    issue('REPORT_SUBJECT_UNCLEAR', path, item_id)
                    invalid = True
        elif envelope.get('confirmation') in CONFIRMATIONS.values():
            issue('UNTRACKED_NATURAL_CONFIRMATION', path, item_id)
            invalid = True
        if envelope.get('status') == 'derived' or envelope.get('source') == 'location_reference':
            method, confirmation = 'location_reference', 'derived_not_user_confirmation'
        state = _state(value, envelope, disposition=disposition, field_missing=missing)
        if (path == 'guide.fields.needs.medicinesStatus' and value == 'no'
                or path == 'guide.fields.needs.providersStatus' and value == 'none'
                or path == 'guide.fields.coverage.current' and value == ['none']):
            if state == 'reported':
                state = 'explicit_none'
        if invalid:
            state = 'conflicting'
        if question and item_id:
            key = question + '.' + item_id
            current_revision = item_revisions.get(key, envelope.get('revision', 0))
            if (type(current_revision) is not int or current_revision < 0
                    or type(invalidations.get(key, 0)) is not int or invalidations.get(key, 0) < 0):
                raise ComparisonProfileError('PROFILE_ITEM_REVISION_INVALID')
            if invalidations.get(key, -1) > current_revision:
                state = 'stale'
        parts = value if isinstance(value, dict) else {}
        known = [key for key, part in parts.items() if part is not None and part != '']
        missing_parts = [key for key, part in parts.items() if part is None or part == '']
        usable = state in {'reported', 'explicit_none'} and role != 'internal_link'
        fact = {'ref': {'path': path, 'item_id': item_id,
                       'subject_id': 'learner' if capture_subject == 'learner' else subject_id,
                       'scope': temporal_scope, 'report_revision': revision, 'record_revision': record_revision},
                'native_ref': native_ref, 'value': copy.deepcopy(value), 'report_state': state,
                'capture_method': method, 'confirmation_state': confirmation,
                'capture_subject': capture_subject, 'field_role': role,
                'temporal_scope': temporal_scope, 'precision': _precision(value),
                'supersedes_ref': ({'path': path, 'item_id': item_id, 'report_revision': supersedes} if supersedes is not None else None),
                'known_parts': known, 'missing_parts': missing_parts,
                'externally_verified': False,
                'usable_as_report': usable,
                'usable_for_bound_subject': usable and capture_subject == 'beneficiary'}
        if question:
            fact['question_id'] = question
        return fact

    questions_by_path = {}
    for question in contract['questions']:
        if question['kind'] != 'documented_child':
            for path in question['fields']:
                questions_by_path[path] = question['id']
    for path, policy in contract['fields'].items():
        question = questions_by_path[path]
        role = policy.get('field_role', 'reported_fact')
        if path.startswith('guide.fields.'):
            key = path.removeprefix('guide.fields.')
            envelope = _envelope(guide['fields'], key)
            disposition = baseline_dispositions.get(question)
            facts.append(report(path, envelope.get('value'), envelope, 'guide.' + key,
                                question=question, missing='value' not in envelope, role=role, disposition=disposition))
            continue
        match = re.fullmatch(r'readiness\.facts\.(RC\d{2})\.value\.(?:items\[\]\.)?([A-Za-z]+)', path)
        if not match:
            raise ComparisonProfileError('PROFILE_PATH_UNSUPPORTED')
        identifier, field = match.groups()
        envelope = _envelope(record['facts'], identifier)
        value = envelope.get('value', {})
        if not isinstance(value, dict):
            raise ComparisonProfileError('PROFILE_FACT_VALUE_INVALID')
        is_item = '.items[].' in path
        rows = value.get('items', []) if is_item else [value]
        if not isinstance(rows, list) or len(rows) > 30 or any(not isinstance(x, dict) for x in rows):
            raise ComparisonProfileError('PROFILE_ITEMS_INVALID')
        if is_item:
            ids = [x.get('entity') for x in rows]
            prefix = 'doctor-' if identifier == 'RC21' else 'medicine-'
            if any(not isinstance(x, str) or not ENTITY.fullmatch(x) or not x.startswith(prefix) for x in ids) or len(set(ids)) != len(ids):
                raise ComparisonProfileError('PROFILE_ITEM_ID_INVALID')
        for item in rows or [{}]:
            entity = item.get('entity') if is_item else None
            detail_key = identifier + '.' + (entity or 'profile') + '.' + field
            disposition = skipped.get(detail_key)
            entity_group = record.get('entityDispositions', {}).get(identifier, {})
            whole = record.get('dispositions', {}).get(identifier, {})
            if (not isinstance(entity_group, dict) or not isinstance(whole, dict)
                    or whole.get('state') is not None and not isinstance(whole['state'], str)):
                raise ComparisonProfileError('PROFILE_DISPOSITION_INVALID')
            entity_disposition = entity_group.get(entity, {})
            if (not isinstance(entity_disposition, dict)
                    or entity_disposition.get('state') is not None and not isinstance(entity_disposition['state'], str)):
                raise ComparisonProfileError('PROFILE_DISPOSITION_INVALID')
            if not disposition:
                disposition = DISPOSITION_STATES.get(entity_disposition.get('state'))
            if not disposition and (field == 'choice' or field not in item or whole.get('state') in {'needs_review', 'conflicting', 'superseded'}):
                disposition = DISPOSITION_STATES.get(whole.get('state'))
            native_ref = 'readiness.' + identifier + ('.' + (entity or 'profile') + '.' + field)
            facts.append(report(path, item.get(field), envelope, native_ref, question=identifier,
                                item_id=entity, missing=field not in item,
                                role=role, disposition=disposition))

    extensions = {'situation': {}}
    for kind, path in SITUATION_PATHS.items():
        key = path.removeprefix('guide.fields.')
        envelope = _envelope(guide['fields'], key)
        fact = report(path, envelope.get('value'), envelope, 'guide.' + key, missing='value' not in envelope)
        facts.append(fact)
        extensions['situation'][kind] = fact
    mirror = _envelope(guide['fields'], 'subject.role')
    extensions['subject_role_mirror'] = report('guide.fields.subject.role', mirror.get('value'), mirror,
                                              'guide.subject.role', missing='value' not in mirror)
    facts.append(extensions['subject_role_mirror'])
    assistance = _envelope(record['facts'], 'RC18')
    programs = assistance.get('value', {}).get('programs')
    extensions['assistance_programs'] = report('readiness.facts.RC18.value.programs[]', programs, assistance,
                                               'readiness.RC18.profile.programs', question='RC18', missing=programs is None)
    facts.append(extensions['assistance_programs'])
    agenda = copy.deepcopy(natural.get('agenda', {'concerns': [], 'priorityReasons': [], 'lastMove': None}))
    priority = _envelope(guide['fields'], 'needs.priorities')
    current_reasons = []
    for reason in agenda.get('priorityReasons', []):
        if (reason['priorityRevision'] == priority.get('revision') and priority.get('status') == 'reported'
                and reason['topic'] in priority.get('value', []) and 'T10' not in baseline_dispositions):
            current_reasons.append(reason)
        else:
            issue('STALE_PRIORITY_REASON', 'readiness.natural.agenda.priorityReasons')
    agenda['priorityReasons'] = current_reasons
    extensions.update(agenda=agenda, dialogue=copy.deepcopy(natural.get('dialogue', {})),
                      task=conversation.get('task', ''), preparing=conversation.get('preparing', False),
                      baseline_dispositions=copy.deepcopy(baseline_dispositions), skipped_details=copy.deepcopy(skipped),
                      item_invalidations=copy.deepcopy(invalidations))
    gap_reports = []
    for gap in contract['representation_gaps']:
        identifier = gap['id']
        path = 'readiness.conversation.details.' + identifier + '.value'
        entries = conversation.get('details', {}).get(identifier, [])
        if not isinstance(entries, list) or len(entries) > 30:
            raise ComparisonProfileError('PROFILE_GAP_REPORT_INVALID')
        reports = []
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get('value'), str):
                raise ComparisonProfileError('PROFILE_GAP_REPORT_INVALID')
            reports.append(report(path, entry['value'], {'value': entry['value'], 'revision': entry.get('revision'),
                'source': entry.get('source'), 'confirmation': entry.get('confirmation')},
                'conversation.details.' + identifier, item_id=entry.get('entity') if entry.get('entity') != 'profile' else None))
        gap_reports.append({'id': identifier, 'path': path, 'description': gap['fact'],
                            'reports': reports, 'gap_closed': False})
    by_path = {}
    for fact in facts:
        by_path.setdefault(fact['ref']['path'], []).append(fact)
    questions = []
    for question in design['questions']:
        related = [fact for path in question['canonical_paths'] for fact in by_path[path]]
        questions.append({'id': question['question_id'], 'parent_alias_of': question['parent_alias_of'],
            'canonical_paths': copy.deepcopy(question['canonical_paths']),
            'fact_refs': [copy.deepcopy(fact['ref']) for fact in related],
            'report_states': sorted({fact['report_state'] for fact in related}),
            'kind': question['kind'], 'source_capabilities': copy.deepcopy(question['source_capabilities']),
            'source_requiredness': question['source_requiredness'],
            'source_dependencies': copy.deepcopy(question['source_dependencies']),
            'gap_ids': copy.deepcopy(question['gap_ids']), 'decision_role': question['decision_role'],
            'ask_only_when': question['ask_only_when'], 'alias_reused': question['parent_alias_of'] is not None})
    output = {'adapter_version': ADAPTER_VERSION,
        'profile_binding': {'guide_revision': guide_revision, 'readiness_revision': readiness_revision,
            'subject_id': subject_id,
            'subject_role': (mirror.get('value') if extensions['subject_role_mirror']['usable_as_report']
                             and isinstance(mirror.get('value'), str)
                             and mirror['value'] in {'self', 'someone'} else None),
            'adapter_version': ADAPTER_VERSION,
            'contract_sha256': contract['content_sha256'], 'item_revisions': copy.deepcopy(item_revisions),
            'snapshot_consistency': 'caller_must_bind_consistent_snapshot'},
        'contract': {'id': contract['contract_id'], 'content_sha256': contract['content_sha256'],
            'source_bindings_verified': True, 'counts': copy.deepcopy(contract['counts']),
            'question_ids': [q['id'] for q in questions], 'baseline_paths': list(contract['fields']),
            'gap_ids': [g['id'] for g in gap_reports], 'child_aliases': copy.deepcopy(contract['child_aliases']),
            'clarification_variants': copy.deepcopy(contract['clarification_variants'])},
        'facts': facts, 'questions': questions, 'gap_reports': gap_reports, 'extensions': extensions,
        'integrity_issues': issues, 'requested_scope': scope}
    output['profile_binding']['normalized_sha256'] = _digest(output)
    return output
