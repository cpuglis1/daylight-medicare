"""Bounded education continuity, separate from reports and comprehension.

The catalog names concepts in retained reviewed teaching material. It adds no
Medicare claims or release authority. A delivery receipt says only that the
accepted response explained a concept; it never says the person understood it.
All functions are pure. The controller commits a planned record only after the
corresponding response succeeds, in the existing permissioned visit RAM.
"""
import copy
import re


VERSION = 'education-v1'
PURPOSES = frozenset({'advance', 'answer', 'teach', 'clarify', 'recap'})
DEPTHS = frozenset({'introduced', 'explored', 'needs_clarification'})
REASONS = frozenset({'new', 'deepen', 'requested_revisit', 'clarify'})
VISUALS = frozenset({'none', 'routes', 'original', 'advantage', 'parts', 'parta', 'partb'})
EVENT_LIMIT = 32
_EVENT = re.compile(r'[A-Za-z0-9:_-]{1,128}\Z')


def _concept(identifier, title, section, evidence, visuals=()):
    return {'concept_id': identifier, 'title': title, 'section': section,
            'evidence_refs': list(evidence), 'visuals': list(visuals)}


# Several concepts may share one source. Citing that source does not check off
# every concept within it, and reusing evidence for genuinely new depth is valid.
CONCEPTS = (
    _concept('medicare_basics', 'What Medicare is', 'foundations', ('basics',)),
    _concept('part_a', 'Part A', 'foundations', ('parts', 'parta'), ('parts', 'parta')),
    _concept('part_b', 'Part B', 'foundations', ('parts', 'partb'), ('parts', 'partb')),
    _concept('coverage_paths', 'The two coverage paths', 'coverage_paths',
             ('routesintro', 'options'), ('routes',)),
    _concept('original_medicare', 'Original Medicare', 'coverage_paths',
             ('original', 'options', 'parts'), ('original',)),
    _concept('medicare_advantage', 'Medicare Advantage', 'coverage_paths',
             ('advantage', 'options', 'routesintro'), ('advantage',)),
    _concept('prescription_coverage', 'Where prescription coverage fits', 'coverage_paths',
             ('drugbasics', 'drugs', 'options')),
    _concept('medigap', 'Where Medigap fits', 'coverage_paths', ('medigap', 'options', 'original')),
    _concept('provider_checks', 'Checking doctors and hospitals', 'personal_tradeoffs',
             ('checks', 'advantage', 'original')),
    _concept('medicine_checks', 'Checking exact medicines and pharmacies', 'personal_tradeoffs',
             ('checks', 'drugbasics', 'drugs')),
    _concept('cost_components', 'Monthly costs and costs when using care', 'personal_tradeoffs',
             ('costs',)),
    _concept('medical_spending_limits', 'Medical spending limits', 'personal_tradeoffs',
             ('medical_limit',)),
    _concept('routine_extra_benefits', 'Dental, vision and hearing', 'personal_tradeoffs',
             ('extras',)),
    _concept('enrollment_timing', 'Sign-up timing and coverage start', 'enrollment',
             ('enrollment_intro', 'dates')),
    _concept('current_coverage_timing', 'Why current insurance matters to timing', 'enrollment',
             ('enrollment_intro', 'dates')),
    _concept('medigap_switching', 'Checking Medigap and switching rights', 'enrollment',
             ('switching', 'medigap')),
    _concept('research_checks', 'What still needs checking before choosing', 'decision',
             ('checks', 'next')),
)
_CATALOG = {item['concept_id']: item for item in CONCEPTS}
_EVIDENCE = frozenset(ref for item in CONCEPTS for ref in item['evidence_refs'])
_LESSON_CONCEPTS = {
    'basics': ('medicare_basics',),
    'parts': ('part_a', 'part_b'),
    'parta': ('part_a',), 'partb': ('part_b',),
    'routesintro': ('coverage_paths',), 'options': ('coverage_paths',),
    'original': ('original_medicare',), 'advantage': ('medicare_advantage',),
    'drugbasics': ('prescription_coverage',), 'drugs': ('prescription_coverage',),
    'medigap': ('medigap',), 'checks': ('research_checks',),
    'dates': ('enrollment_timing',), 'enrollment_intro': ('enrollment_timing',),
    'costs': ('cost_components',), 'medical_limit': ('medical_spending_limits',),
    'extras': ('routine_extra_benefits',), 'switching': ('medigap_switching',),
    'next': ('research_checks',),
}


def catalog_context():
    """Public bounded concept map. This is not a mandatory lesson queue."""
    return {'version': VERSION, 'concepts': copy.deepcopy(list(CONCEPTS)),
            'delivery_is_not_comprehension': True,
            'required_for_recommendations': False}


def empty_record():
    return {'version': VERSION, 'revision': 0, 'concepts': {}, 'visuals': {},
            'focus': [], 'event_ids': []}


def concepts_for_evidence(identifiers):
    """Map explicit reviewed topic requests to their bounded concept scope."""
    refs = {item for item in identifiers if isinstance(item, str)}
    return [item['concept_id'] for item in CONCEPTS if refs & set(item['evidence_refs'])]


def concepts_for_lesson(fact_id):
    """Primary concept receipts for an explicit retained whole-lesson action.

    This intentionally differs from retrieval: the shared ``options`` source
    supports several concepts, but opening that lesson records only its primary
    overview. It does not imply every related subtopic has been explored.
    """
    return list(_LESSON_CONCEPTS.get(fact_id, ())) if isinstance(fact_id, str) else []


def validate_record(record):
    """Validate the small server-owned RAM representation without coercion."""
    if (not isinstance(record, dict)
            or set(record) != {'version', 'revision', 'concepts', 'visuals', 'focus', 'event_ids'}
            or record['version'] != VERSION
            or type(record['revision']) is not int or record['revision'] < 0
            or not isinstance(record['concepts'], dict)
            or set(record['concepts']) - set(_CATALOG)
            or not isinstance(record['visuals'], dict)
            or set(record['visuals']) - (VISUALS - {'none'})
            or not isinstance(record['focus'], list) or len(record['focus']) > 4
            or any(not isinstance(item, str) for item in record['focus'])
            or len(set(record['focus'])) != len(record['focus'])
            or any(item not in _CATALOG for item in record['focus'])
            or not isinstance(record['event_ids'], list) or len(record['event_ids']) > EVENT_LIMIT
            or any(not isinstance(item, str) or not _EVENT.fullmatch(item) for item in record['event_ids'])
            or len(set(record['event_ids'])) != len(record['event_ids'])):
        raise ValueError('Use a bounded server education record.')
    for item in record['concepts'].values():
        if (not isinstance(item, dict)
                or set(item) != {'depth', 'needs_clarification', 'deliveries', 'last_revision', 'evidence_refs'}
                or not isinstance(item['depth'], str)
                or item['depth'] not in {'not_covered', 'introduced', 'explored'}
                or type(item['needs_clarification']) is not bool
                or type(item['deliveries']) is not int or not 0 <= item['deliveries'] <= 999
                or type(item['last_revision']) is not int
                or not 0 < item['last_revision'] <= record['revision']
                or not isinstance(item['evidence_refs'], list)
                or any(not isinstance(ref, str) for ref in item['evidence_refs'])
                or len(set(item['evidence_refs'])) != len(item['evidence_refs'])
                or any(ref not in _EVIDENCE for ref in item['evidence_refs'])
                or (item['depth'] == 'not_covered' and item['deliveries'] != 0)
                or (item['depth'] != 'not_covered' and item['deliveries'] == 0)):
            raise ValueError('Use bounded concept delivery receipts.')
    if any(type(count) is not int or not 1 <= count <= 999 for count in record['visuals'].values()):
        raise ValueError('Use bounded visual delivery counts.')
    return copy.deepcopy(record)


def learning_context(record=None):
    """No raw dialogue, event IDs, or invented comprehension in model context."""
    value = validate_record(record) if record is not None else empty_record()
    return {'version': VERSION, 'revision': value['revision'],
            'covered': [dict(concept_id=identifier, **{
                key: item[key] for key in ('depth', 'needs_clarification', 'deliveries')})
                for identifier, item in value['concepts'].items()],
            'visuals_shown': sorted(value['visuals']), 'focus': list(value['focus'])}


def _valid_update(item, accepted_refs):
    if (not isinstance(item, dict)
            or set(item) != {'concept_id', 'depth', 'reason', 'evidence_refs'}
            or not isinstance(item.get('concept_id'), str)
            or item.get('concept_id') not in _CATALOG
            or not isinstance(item.get('depth'), str) or item.get('depth') not in DEPTHS
            or not isinstance(item.get('reason'), str) or item.get('reason') not in REASONS
            or not isinstance(item.get('evidence_refs'), list)
            or len(item['evidence_refs']) > 8
            or any(not isinstance(ref, str) for ref in item['evidence_refs'])
            or len(set(item['evidence_refs'])) != len(item['evidence_refs'])):
        return False
    refs = set(item['evidence_refs'])
    if not refs <= set(_CATALOG[item['concept_id']]['evidence_refs']) & accepted_refs:
        return False
    if item['depth'] == 'needs_clarification':
        return item['reason'] == 'clarify'
    return bool(refs)


def plan_update(record, output, accepted_evidence_refs=(), *, requested_revisit=False,
                revisit_concepts=(), event_id=None):
    """Plan optional delivery receipts and a contextual visual, never prose.

    ``accepted_evidence_refs`` comes from the already validated composition;
    receipts alone cannot authorize evidence. ``requested_revisit`` and scoped
    ``revisit_concepts`` come from the controller's user request, not this output.
    Ordinary button answers therefore cannot authorize repeated introductions.

    Bad optional metadata is dropped with fixed diagnostic codes. It does not
    turn an otherwise useful accepted response into a failed conversation.
    """
    issues = []
    try:
        previous = validate_record(record) if record is not None else empty_record()
    except (ValueError, TypeError):
        previous = empty_record()
        issues.append('invalid_prior_education')
    planned = copy.deepcopy(previous)
    cleaned = {'purpose': 'advance', 'updates': [], 'visual': 'none'}

    def result():
        return {'record': planned, 'education': cleaned, 'visual': cleaned['visual'],
                'accepted_updates': copy.deepcopy(cleaned['updates']), 'issues': list(issues)}

    if event_id is not None and (not isinstance(event_id, str) or not _EVENT.fullmatch(event_id)):
        issues.append('invalid_education_event')
        event_id = None
    if event_id is not None and event_id in previous['event_ids']:
        issues.append('replayed_education_event')
        return result()
    if (not isinstance(output, dict) or set(output) != {'purpose', 'updates', 'visual'}
            or not isinstance(output.get('purpose'), str) or output.get('purpose') not in PURPOSES
            or not isinstance(output.get('updates'), list) or len(output['updates']) > 4
            or not isinstance(output.get('visual'), str) or output.get('visual') not in VISUALS):
        issues.append('invalid_education_metadata')
        return result()
    cleaned['purpose'] = output['purpose']
    accepted_refs = set(ref for ref in accepted_evidence_refs if isinstance(ref, str))
    revisit = set(ref for ref in revisit_concepts if isinstance(ref, str) and ref in _CATALOG)
    seen = set()
    for item in output['updates']:
        if not _valid_update(item, accepted_refs):
            issues.append('invalid_education_update')
            continue
        identifier, depth, reason = item['concept_id'], item['depth'], item['reason']
        if identifier in seen:
            issues.append('duplicate_education_update')
            continue
        seen.add(identifier)
        old = previous['concepts'].get(identifier, {
            'depth': 'not_covered', 'needs_clarification': False, 'deliveries': 0,
            'last_revision': 0, 'evidence_refs': []})
        authorized_revisit = requested_revisit is True and identifier in revisit
        if reason == 'requested_revisit' and not authorized_revisit:
            issues.append('unrequested_education_revisit')
            continue
        if depth == 'needs_clarification':
            new = dict(old, needs_clarification=True)
        else:
            is_deeper = depth == 'explored' and old['depth'] == 'introduced'
            is_clarification = reason == 'clarify' and old['needs_clarification']
            if old['depth'] != 'not_covered' and not (
                    (is_deeper and reason == 'deepen') or is_clarification
                    or (reason == 'requested_revisit' and authorized_revisit)):
                issues.append('redundant_education_delivery')
                continue
            if reason == 'deepen' and not is_deeper:
                issues.append('invalid_education_depth_transition')
                continue
            new = dict(old,
                       depth='explored' if depth == 'explored' or old['depth'] == 'explored' else 'introduced',
                       needs_clarification=False,
                       deliveries=min(999, old['deliveries'] + 1),
                       evidence_refs=sorted(set(old['evidence_refs']) | set(item['evidence_refs'])))
        new['last_revision'] = previous['revision'] + 1
        planned['concepts'][identifier] = new
        cleaned['updates'].append(copy.deepcopy(item))

    teaching = [item for item in cleaned['updates'] if item['depth'] != 'needs_clarification']
    visual = output['visual']
    matching = [item for item in teaching if visual in _CATALOG[item['concept_id']]['visuals']]
    if visual != 'none':
        # Reusing a citation is fine. Replaying an already shown visual requires
        # an actual clarification or user-requested revisit of its concept.
        repeat = visual in previous['visuals']
        repeat_ok = any(item['reason'] == 'clarify' or (
            item['reason'] == 'requested_revisit'
            and requested_revisit is True and item['concept_id'] in revisit) for item in matching)
        if matching and (not repeat or repeat_ok):
            cleaned['visual'] = visual
            planned['visuals'][visual] = min(999, previous['visuals'].get(visual, 0) + 1)
        else:
            issues.append('redundant_or_unrelated_education_visual')
    if cleaned['updates'] or cleaned['visual'] != 'none':
        planned['revision'] += 1
        planned['focus'] = [item['concept_id'] for item in cleaned['updates']]
        if event_id is not None:
            planned['event_ids'] = (planned['event_ids'] + [event_id])[-EVENT_LIMIT:]
    return result()
