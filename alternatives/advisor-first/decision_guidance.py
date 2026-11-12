"""Small decision brief from already permitted state; never profile authority.

This labels relevant possibilities without prescribing their sequence. Only
required dependencies take precedence. An educational detour may end without an ask.
"""
import copy


OBJECTIVES = {
    'timing': 'Understand which coverage and enrollment facts matter to the timing decision.',
    'current_coverage': 'Understand the current coverage situation before discussing a change.',
    'doctors': 'Understand the access tradeoff and what an exact provider check would require.',
    'drugs': 'Understand how medicine coverage fits and what a supported medicine check needs.',
    'travel': 'Understand how using care away from home affects the coverage-path discussion.',
    'total_cost': 'Understand the cost tradeoff and distinguish published amounts from personal totals.',
    'bills': 'Understand costs when using care and which amounts remain unverified.',
    'flexibility': 'Understand future flexibility and the conditions that still need checking.',
    'learning': 'Resolve the current explanation need at the requested depth.',
    'coverage_paths': 'Understand the coverage-path distinction relevant to the person’s concern.',
    'plan_preparation': 'Advance a supported coverage decision: understand relevant tradeoffs, gather consequential missing facts, and identify unresolved verification.',
    'other': 'Clarify the stated concern and identify one useful supported next step.',
}
QUESTION_FOCUS = {
    'timing': ('T05', 'S_AGE65', 'RC09', 'RC04', 'RC05', 'RC06', 'RC08', 'RC10', 'RC11',
               'RC11.C1', 'RC12', 'RC13', 'RC26', 'RC27', 'T04'),
    'current_coverage': ('T05', 'RC09', 'RC04', 'RC10', 'RC11', 'RC12', 'RC13'),
    'doctors': ('T06', 'RC21', 'T08', 'RC20', 'T10'),
    'drugs': ('T07', 'RC22', 'RC23', 'RC24', 'T09'),
    'travel': ('T08', 'RC20', 'T06', 'T10'),
    'total_cost': ('T09', 'RC25', 'RC14', 'RC15', 'RC16', 'T10'),
    'bills': ('T09', 'RC25', 'T10'),
    'flexibility': ('T05', 'RC04', 'RC05', 'RC26', 'RC27', 'T10'),
    'coverage_paths': ('T05', 'T10', 'T06', 'T08', 'T07', 'T09'),
    'plan_preparation': ('T03', 'T05', 'T06', 'T07', 'T10', 'T09', 'T08'),
    'learning': ('T02',),
    'other': ('T10',),
}
TASK_FOCUS = {'timing': 'timing', 'providers': 'doctors', 'drug_coverage': 'drugs',
              'drug_pricing': 'drugs', 'costs': 'total_cost', 'medigap': 'flexibility',
              'learn': 'learning', 'compare': 'plan_preparation', 'review': 'plan_preparation',
              'browse': 'plan_preparation'}
CONCEPT_FOCUS = {'enrollment_timing': 'timing', 'current_coverage_timing': 'timing',
    'provider_checks': 'doctors', 'medicine_checks': 'drugs',
    'prescription_coverage': 'drugs', 'cost_components': 'total_cost',
    'medical_spending_limits': 'bills', 'medigap_switching': 'flexibility',
    'coverage_paths': 'coverage_paths', 'original_medicare': 'coverage_paths',
    'medicare_advantage': 'coverage_paths', 'medigap': 'coverage_paths'}


def guidance(candidates, *, task='', concerns=(), age65=False,
             dispositions=None, pending_question=None, education_request=None):
    """Return independent candidate copies and a bounded, non-authoritative brief.

    education_request must already have current-message quote and concept checks.
    The same approved candidates remain selectable; relevance is not a new gate.
    """
    request = education_request or {}
    concepts = request.get('concept_ids', [])
    open_concerns = [item for item in concerns if item.get('status') == 'open'
                     and item.get('subject') == 'beneficiary'
                     and item.get('topic') in OBJECTIVES]
    practical_focus = open_concerns[-1]['topic'] if open_concerns else TASK_FOCUS.get(task, 'coverage_paths')
    # An open expressed concern remains useful context even when an inherited
    # broad task label says "compare". The model chooses the next move from
    # current intent and conversation, without a task label overruling it.
    if not open_concerns and age65 and task in {'', 'timing'}:
        practical_focus = 'timing'
    # A user's direct learning request takes conversational precedence without
    # reordering personal intake or converting learner curiosity into a
    # beneficiary priority. The explanation's focus and its practical return
    # point are distinct; all approved candidates remain selectable.
    focus = practical_focus
    if request.get('kind') in {'explain', 'clarify', 'revisit'} and concepts:
        focus = CONCEPT_FOCUS.get(concepts[0], 'learning')
    relevant = QUESTION_FOCUS[practical_focus]
    ranked = copy.deepcopy(candidates)
    for item in ranked:
        identifier = item['question']['id']
        item['decision_relevance'] = ('clarification' if item.get('required') else
            'current_decision' if identifier in relevant else
            'return_point' if identifier == pending_question else 'available_if_useful')
    # The tuple above is a relevance vocabulary, not a field-completion order.
    # Preserve candidate order except for actual dependency/ambiguity checks.
    ranked.sort(key=lambda item: not (item.get('required') or item['question']['id'] == 'RC01'))
    obstacles = []
    for identifier, state in (dispositions or {}).items():
        if identifier in relevant and state in {'unknown', 'deferred', 'conflicting'}:
            help_text = ('Help explain the decision; do not demand a preferred month.'
                         if identifier == 'T04' and state == 'unknown' else
                         'Leave this open unless the person reopens it.' if state == 'deferred' else
                         'Preserve uncertainty; clarify only when needed for this concern.')
            obstacles.append({'question_id': identifier, 'state': state, 'help': help_text})
    if not obstacles:
        obstacles = [{'question_id': item['question']['id'],
            'state': 'conflicting' if item.get('required') else 'missing',
            'help': 'Ask only if its answer changes the useful help available now.'}
            for item in ranked if item.get('required') or item['question']['id'] in relevant]
    kind = request.get('kind')
    policy = ('clarify_current_confusion' if kind == 'clarify' else
              'answer_first_return_when_useful' if kind in {'explain', 'revisit'} else
              'balance_understanding_and_decision_progress')
    return ranked, {'focus': focus, 'practical_focus': practical_focus, 'objective': OBJECTIVES[focus],
                    'obstacles': obstacles[:4], 'question_policy': policy,
                    'relevance_is_advisory': True,
                    'return_point_is_optional': True, 'personal_research': 'held'}
