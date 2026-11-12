"""D138: account for the twelve CMS pre-enrollment checklist items.

Item names come from ``daylight_operations.checklist`` (CMS CY2026 Agent/Broker
Training and Testing Guidelines; 42 CFR 422.2274(c)(12) and 423.2274(c)(12)).
Whether software coverage satisfies the "agents and brokers discuss" standard
is an open counsel question; this module only counts.

Two deterministic views, neither of which uses a model:

* ``content_audit(facts)``: does reviewed teaching content exist for the item?
  An item with no reviewed statement can never be covered in a conversation.
* ``receipt(facts, education_record)``: which items has this visit actually
  been taught, judged only from the reviewed facts the delivered-concept
  record cites. Teaching delivered is not comprehension, and a receipt is not
  an enrollment authorization.

Each item lists the points its reviewed content must state. A point is met by
any reviewed fact whose text matches; the item is covered in a visit when every
point is met by a fact that was delivered in that visit.
"""
import re

ITEMS = (
    ('plan_type_and_network_providers', 'Plan type, and whether your doctors, pharmacy and hospitals are in the network',
     (r'Medicare Advantage is a private plan|private insurance company’s plan', r'\bdoctors?\b', r'\bpharmac(?:y|ies)\b', r'\bhospitals?\b', r'\bnetworks?\b')),
    ('formulary_coverage', 'Whether your medicines are on the plan’s list of covered drugs',
     (r'list of covered medicines|formulary',)),
    ('other_needed_benefits', 'Other benefits you need, such as dental, vision and hearing',
     (r'\bdental\b',)),
    ('premiums_including_part_b', 'Premiums, including the Part B premium',
     (r'\bpremium is the amount\b|\bmonthly premium\b', r'Part B premium')),
    ('cost_sharing', 'What you pay when you use care: deductibles, copays and coinsurance',
     (r'\bdeductible\b', r'\bcopays?\b|\bcoinsurance\b')),
    ('out_of_network_rules', 'What happens when you use doctors outside the plan’s network',
     (r'out[- ]of[- ]network|outside (?:the|its|a) plan’s network|outside the network',)),
    ('coverage_outside_us', 'Coverage outside the United States',
     (r'outside the (?:U\.S\.|United States)',)),
    ('effect_on_current_coverage', 'How a new plan affects the coverage you have now, including Medigap',
     (r'\bMedigap\b', r'medical underwriting|health questions', r'current (?:coverage|insurance|plan) (?:ends|will end|stops)|ends? (?:your|their|the) current (?:coverage|insurance|plan)')),
    ('plan_year_changes_and_eoc', 'Plans can change each year; the Evidence of Coverage has the full rules',
     (r'each year|January 1', r'Evidence of Coverage')),
    ('how_to_file_complaints', 'How to file a complaint',
     (r'\bcomplaints?\b|\bgrievances?\b',)),
    ('special_needs_plan_requirements', 'Who can join a Special Needs Plan',
     (r'Special Needs Plan',)),
    ('right_to_cancel', 'Your right to cancel an enrollment',
     (r'\bcancel\b.{0,80}\benrollment\b|\benrollment\b.{0,80}\bcancel',)),
)
ITEM_IDS = tuple(item[0] for item in ITEMS)

# The fixed "Before you enroll" step shows these reviewed statements, in this
# order, for each item. A test checks that each list states every point.
STATEMENTS = {
    'plan_type_and_network_providers': ('advantage', 'drugbasics', 'original_nationwide'),
    'formulary_coverage': ('drugbasics',),
    'other_needed_benefits': ('extras',),
    'premiums_including_part_b': ('costs', 'advantage'),
    'cost_sharing': ('costs',),
    'out_of_network_rules': ('original_nationwide',),
    'coverage_outside_us': ('cms_outside_us',),
    'effect_on_current_coverage': ('cms_current_coverage', 'switching'),
    'plan_year_changes_and_eoc': ('cms_plan_year_eoc',),
    'how_to_file_complaints': ('cms_complaints',),
    'special_needs_plan_requirements': ('cms_special_needs_plans',),
    'right_to_cancel': ('cms_right_to_cancel',),
}


def _text(fact):
    return ' '.join(str(fact.get(key, '')) for key in ('title', 'text'))


def _matching(facts, pattern, only=None):
    return sorted(key for key, fact in facts.items()
                  if (only is None or key in only) and re.search(pattern, _text(fact), re.I | re.S))


def content_audit(facts):
    """Which checklist items have complete reviewed content, and which points are missing."""
    rows = []
    for identifier, title, points in ITEMS:
        found = [_matching(facts, pattern) for pattern in points]
        rows.append({'id': identifier, 'title': title, 'has_content': all(found),
                     'facts': sorted({key for group in found for key in group}),
                     'missing_points': sum(1 for group in found if not group), 'points': len(points)})
    return {'items': rows, 'ready': [row['id'] for row in rows if row['has_content']],
            'gaps': [row['id'] for row in rows if not row['has_content']]}


def delivered_facts(education_record):
    """Reviewed fact ids the visit's delivered-concept record cites."""
    concepts = (education_record or {}).get('concepts', {})
    return {ref for item in concepts.values() if isinstance(item, dict)
            and item.get('depth') in {'introduced', 'explored'}
            for ref in item.get('evidence_refs', []) if isinstance(ref, str)}


def receipt(facts, education_record):
    """Per-visit account in the ``daylight_operations`` receipt shape, plus a summary."""
    delivered = delivered_facts(education_record)
    items = {}
    for identifier, title, points in ITEMS:
        used = [_matching(facts, pattern, delivered) for pattern in points]
        items[identifier] = {'covered': all(used), 'title': title,
                             'facts': sorted({key for group in used for key in group})}
    covered = [key for key in ITEM_IDS if items[key]['covered']]
    return {'version': 'cms-checklist-r1', 'items': items, 'covered': len(covered), 'total': len(ITEM_IDS),
            'missing': [key for key in ITEM_IDS if key not in covered], 'complete': len(covered) == len(ITEM_IDS),
            'teaching_is_not_comprehension': True, 'enrollment_authorization': False}


def before_enroll(facts, education_record=None):
    """The fixed step: every item with its reviewed statements, in a stable order.

    Deterministic and model-free. ``digest`` identifies the exact wording shown,
    so a time record can say which version a person saw.
    """
    import hashlib
    import json
    seen = receipt(facts, education_record)
    items = []
    for identifier, title, points in ITEMS:
        shown = [{'id': key, 'title': facts[key].get('title', ''), 'text': facts[key].get('text', '')}
                 for key in STATEMENTS[identifier] if key in facts]
        complete = all(_matching(facts, pattern, {row['id'] for row in shown}) for pattern in points)
        items.append({'id': identifier, 'title': title, 'statements': shown, 'complete': complete,
                      'covered_in_conversation': seen['items'][identifier]['covered']})
    digest = hashlib.sha256(json.dumps([[item['id'], [row['text'] for row in item['statements']]] for item in items],
                                       ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return {'version': 'before-you-enroll-r1', 'items': items, 'digest': digest,
            'complete': all(item['complete'] for item in items),
            'conversation': {'covered': seen['covered'], 'total': seen['total']}}
