"""Bind fictional tool and inference trials to the advisor's native visit state.

Only the reviewed held-out line groups and supported families are executable.
Answer keys and calibration traces never supply profile values or tool outputs.
"""

from hashlib import sha256
import json

import starts_facts


HELDOUT_HASHES = {
    'tool_use': '070daee33abc08f90d0b315db6c6edaa381250bbe6a33b7b2bf48cf872d90254',
    'unsupported_inferences': '1a98b7db925db3333b3ebf92daca0450e138e768a52e373e450959fb57c284d8',
}

# Unknown fields are genuine absent reports. The same readback after Send is
# diagnostic evidence about captured state, independent of what the reply says.
INFERENCE_CHECKS = {
    'coverage': ({'enrollment.partA': None, 'enrollment.partB': None}, {'RC04': None}),
    'priorities': ({'needs.priorities': None, 'needs.priorityOther': None,
                    'needs.costPreference': None}, {}),
    'window': ({'coverage.requestedStartMonth': None, 'enrollment.partA': None,
                'enrollment.partB': None}, {'RC04': None, 'RC05': None}),
    'income': ({}, {'RC18': None}),
    'retirement': ({'situation.retirement': None}, {'RC11': None}),
    'selection': ({'intent.selectedPlan': None}, {}),
}

# The directory fixture needs a real selected plan and exact-office result.
# The current composer exposes neither a directory lookup nor that result as
# a tool response, so pass_trace remains calibration-only.
TOOL_RULES = {
    'needed': ('working_coverage_sep', False),
    'preloaded': ('partd_penalty', True),
    'nomatch': (None, False),
    # These case families retain their existing IDs and split assignments.
    'handoff_no_send': ('hsa_medicare', False),
    'handoff_summary': (None, False),
}
SUMMARY_REPORT = (
    'I wrote down $18 a month on one listing and $31 on the other. '
    'I haven’t found the pharmacy costs yet.'
)


def _choice(identifier, choice):
    """Construct an ordinary structured answer for a fictional visit."""
    return {'type': 'choice', 'id': identifier, 'fields': {'choice': choice}}


def _start(case, line_hash):
    """Return the explicit setup and assertions for one reviewed row."""
    family = case['scenario_family']
    relationship = 'someone' if case['journey'] == 'caregiver' else 'self'
    setup = [_choice('T01', 'compare'), _choice('RC01', relationship)]
    history = []
    fields = {'intent.goal': 'compare', 'subject.role': relationship}
    reports = {}
    start = {'lineHash': line_hash, 'setup': setup, 'history': history, 'fields': fields,
             'reports': reports, 'relationship': relationship}
    if case['judge'] == 'tool_use':
        fact_id, supplied = TOOL_RULES[family]
        start['toolRule'] = {'factId': fact_id, 'codeSupplied': supplied,
                             'outsideCatalog': 'arizona' if family == 'nomatch' else None}
        if family == 'handoff_summary':
            # Prior visitor reports are memory only. There is no fabricated
            # price response, selected plan, or transfer in this setup.
            history.append((SUMMARY_REPORT, '', ''))
        if family == 'preloaded':
            # The ordinary applicable-rule selector supplies the accepted
            # Part D statement for Original Medicare without drug coverage.
            setup.append(_choice('RC07', 'original'))
            reports['RC07'] = {'choice': 'original'}
            fields['coverage.current'] = None
    else:
        absent_fields, absent_reports = INFERENCE_CHECKS[family]
        fields.update(absent_fields)
        reports.update(absent_reports)
        start['postFields'] = dict(absent_fields)
        start['postReports'] = dict(absent_reports)
        if family == 'selection':
            start['selected_plan'] = starts_facts.PLAN
            start['requires_source_lookup'] = False
    return start


def build_starts(rows):
    """Bind supported case IDs after verifying the full held-out group digests."""
    starts = {}
    for suite, expected in HELDOUT_HASHES.items():
        group = sorted((case_id, case, line_hash) for case_id, (case, line_hash) in rows.items()
                       if case.get('judge') == suite and case.get('split') == 'heldout')
        actual = sha256(''.join(line_hash for _, _, line_hash in group).encode()).hexdigest()
        if actual != expected:
            raise ValueError(f'The held-out {suite} corpus does not match the reviewed bindings.')
        supported = TOOL_RULES if suite == 'tool_use' else INFERENCE_CHECKS
        for case_id, case, line_hash in group:
            if case_id == case['id'] and case['scenario_family'] in supported:
                starts[case_id] = _start(case, line_hash)
    return starts


def verify_start(flow, state, start):
    """Prove the pinned source and its native rule selection before the paid turn."""
    from applicable_rules import applicable_rules

    rule = start.get('toolRule')
    if not rule:
        return
    fact_id = rule['factId']
    outside_catalog = rule['outsideCatalog']
    if outside_catalog and any(
            outside_catalog in ' '.join(str(fact.get(key, '')) for key in
                                        ('title', 'question', 'summary', 'text')).casefold()
            for fact in flow.facts.values()):
        raise ValueError('The reviewed catalog now contains material for the out-of-scope request.')
    if fact_id is None:
        return
    starts_facts.verify_start(flow, state, {'source_id': fact_id})
    if flow.facts.get(fact_id, {}).get('text') != flow.rule_facts[fact_id]['text']:
        raise ValueError('The lookup catalog lacks the exact accepted source for the trial.')
    native_rules = applicable_rules(lambda identifier: flow.report(state['record'], identifier),
                                    lambda field: flow.value(state['guide'], field))
    if any(r['fact_id'] == fact_id for r in native_rules) != rule['codeSupplied']:
        raise ValueError('The native rule selector does not match the required starting state.')


def verify_observation(trace, start):
    """Require the actual initial model request to match the intended tool setup."""
    rule = start.get('toolRule')
    selected_plan = start.get('selected_plan')
    if rule is None and not selected_plan:
        return True
    if not trace:
        return False
    first = next((call['request'] for call in trace.get('modelCalls', [])
                  if call.get('kind') == 'compose' and isinstance(call.get('request'), dict)), {})
    if selected_plan:
        try:
            plans = json.loads(first['input'][0]['content'])['resolved_context']['plans_context']
            return (plans['selected_id'] == selected_plan and plans['scope']['year'] == 2026
                    and plans['compared_ids'] == [])
        except (KeyError, IndexError, TypeError, ValueError):
            return False
    lookup = next((tool for tool in first.get('tools', [])
                   if tool.get('type') == 'function' and tool.get('name') == 'lookup_medicare_sources'), None)
    if lookup is None:
        return False
    fact_id = rule['factId']
    try:
        context = json.loads(first['input'][0]['content'])['resolved_context']
        supplied = context['evidence']
        available = lookup['parameters']['properties']['source_ids']['items']['enum']
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    if not isinstance(supplied, list) or not isinstance(available, list):
        return False
    if fact_id is not None and (fact_id not in available or
            any(item.get('id') == fact_id for item in supplied) != rule['codeSupplied']):
        return False
    if start['history']:
        return any(exchange.get('user') == SUMMARY_REPORT for exchange in context.get('recent_exchanges', []))
    return True


def prepare_trial(service, owner, state, start):
    """Open a real plan listing while keeping the comparison shortlist empty."""
    permissions = starts_facts.prepare_trial(service, owner, state, start)
    request = permissions.get('plansContext')
    if request is not None and request['comparedIds'] != []:
        raise ValueError('The opened listing must have an empty comparison shortlist.')
    return permissions
