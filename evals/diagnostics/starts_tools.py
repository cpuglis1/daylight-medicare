"""Bind fictional tool and inference trials to the advisor's native visit state.

Only the reviewed held-out line groups and supported families are executable.
Answer keys and calibration traces never supply profile values or tool outputs.
"""

from hashlib import sha256
import json

import starts_facts


HELDOUT_HASHES = {
    'tool_use': 'd221c73e83c6e914ea6a886d17ae07386822e6a4e45af87c417e0726a6a3eb46',
    'unsupported_inferences': '98cb9d1edd1b1024e47dadf3ccb69b025eacc3e55f5df8be6feb80c52dd9fb6d',
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

TOOL_RULES = {
    'needed': ('working_coverage_sep', False),
    'preloaded': ('partd_penalty', True),
    'nomatch': (None, False),
}
# Neither human handoff case has a corresponding model tool. The only
# composition function is the source lookup (natural_agent.py); the local
# Plans handoff in natural_flow.py is a catalog receipt, not a human transfer.

# These utterances recreate the earlier conversational preferences described
# by the corpus. They are visit memory only, with no authority to record facts.
PRIOR_PREFERENCES = {
    '2': 'Please keep the earlier explanations in plain language.',
    '4': 'I want to make the decision myself.',
    '5': 'Please take this one step at a time.',
}


def _choice(identifier, choice):
    """Construct an ordinary structured answer for a fictional visit."""
    return {'type': 'choice', 'id': identifier, 'fields': {'choice': choice}}


def _start(case, line_hash):
    """Return the explicit setup and assertions for one reviewed row."""
    family = case['scenario_family']
    relationship = 'someone' if case['journey'] == 'caregiver' else 'self'
    setup = [_choice('T01', 'compare'), _choice('RC01', relationship)]
    history = []
    pref = PRIOR_PREFERENCES.get(case['id'].rsplit('-', 1)[1])
    if pref:
        history.append((pref, '', ''))
    fields = {'intent.goal': 'compare', 'subject.role': relationship}
    reports = {}
    start = {'lineHash': line_hash, 'setup': setup, 'history': history, 'fields': fields,
             'reports': reports, 'relationship': relationship}
    if case['judge'] == 'tool_use':
        fact_id, supplied = TOOL_RULES[family]
        start['toolRule'] = {'factId': fact_id, 'codeSupplied': supplied}
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
        if family == 'priorities':
            history.append(('What does a low premium mean?', '', ''))
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
    if fact_id is None:
        if any('arizona' in ' '.join(str(fact.get(key, '')) for key in
                                     ('title', 'summary', 'text')).casefold()
               for fact in flow.facts.values()):
            raise ValueError('The reviewed catalog now contains Arizona material.')
        return
    if fact_id not in flow.rule_facts or fact_id not in flow.facts:
        raise ValueError('The accepted source needed for this trial is unavailable.')
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
    if not any(tool.get('type') == 'function' and tool.get('name') == 'lookup_medicare_sources'
               for tool in first.get('tools', [])):
        return False
    supplied = next((entry['output']['evidence'] for entry in trace.get('toolCalls', [])
                     if entry.get('tool') == 'sources_supplied_by_code'), None)
    return (supplied is not None and
            any(item.get('id') == rule['factId'] for item in supplied) == rule['codeSupplied'])


def prepare_trial(service, owner, state, start):
    """Open a real plan card while keeping the comparison shortlist empty."""
    permissions = starts_facts.prepare_trial(service, owner, state, start)
    request = permissions.get('plansContext')
    if request is not None and request['comparedIds'] != []:
        raise ValueError('The opened card must have an empty comparison shortlist.')
    return permissions
