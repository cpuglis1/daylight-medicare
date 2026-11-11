"""Request-local evidence for a turn, not a dialogue script or profile store."""
import copy


PROGRESS = ('open', 'useful_stopping_point', 'paused')
MOVES = ('explain', 'clarify', 'ask', 'next_step', 'finish')


def question_binding(question, role, fields=(), subject='beneficiary'):
    """Bind meaning to a server-owned displayed question, never a client hint."""
    if not question or not question.get('question'):
        return None
    return {'id': question['id'], 'question': question['question'],
            'entity': question.get('entity', 'profile'),
            # The approved question establishes whose report is being requested;
            # it does not establish whether that beneficiary is the speaker.
            'subject': subject, 'relationship': role,
            'fields': list(fields or [f['key'] for f in question.get('fields', [])])}


def bound_answer(binding, identifier, *, subject='beneficiary', entity='profile'):
    return bool(isinstance(binding, dict) and binding.get('id') == identifier
                and binding.get('subject') == subject and subject != 'unresolved'
                and binding.get('entity') == entity and binding.get('question'))


def outcome(identifier, status, reason, entity='profile'):
    # Values/quotes are intentionally absent. Current resolved reports remain
    # the only source for accepted values supplied to composition.
    return {'target': identifier, 'entity': entity, 'status': status, 'reason': reason}


def working_assessment(context, outcomes=(), answer_context=None):
    """One view over existing permissioned state; no new inferred facts."""
    brief = context.get('advisor_brief', {})
    return {
        'goal': {'stated': brief.get('goal'), 'reported_category': brief.get('reported_goal'),
                 'current_concern': brief.get('current_concern'),
                 'previous_continuation': brief.get('continuation')},
        'understanding': {'evidence_in': 'learner_context',
                          'teaching_history_in': 'education_context.learning',
                          'assessment_is_tentative': True, 'unobserved_is_unknown': True},
        'decision': {'report_refs': [r['id'] for r in context.get('reports', [])],
                     'other_report_states': copy.deepcopy(context.get('known', [])),
                     'unresolved': copy.deepcopy(context.get('uncertainties', [])),
                     'capabilities_in': ['comparison_status', 'task_work']},
        'current_turn': {'answer_context': copy.deepcopy(answer_context),
                         'capture_outcomes': copy.deepcopy(list(outcomes))},
        'history_is_partial': True,
        'missing_record_does_not_prove_unanswered': True,
    }


def assessment(value):
    """Model judgment is advisory; malformed optional metadata grants nothing."""
    if (not isinstance(value, dict) or set(value) != {'goal_progress', 'next_move'}
            or value.get('goal_progress') not in PROGRESS or value.get('next_move') not in MOVES):
        return None
    return copy.deepcopy(value)


def continuation(draft, delivered, proposed_assessment=None, *, recovery=False):
    """Distinguish an intended ending from a question changed by validation."""
    changed = bool(recovery or draft.get('question', '').strip() != delivered.get('question', '').strip()
                   or draft.get('question_target') != delivered.get('question_target'))
    return {'assessment': assessment(proposed_assessment),
            'delivered': 'question' if delivered.get('question') else 'answer_only',
            'validation_changed_continuation': changed}


def checked_continuation(value):
    if (not isinstance(value, dict)
            or set(value) != {'assessment', 'delivered', 'validation_changed_continuation'}
            or value['delivered'] not in {'question', 'answer_only', 'withheld'}
            or type(value['validation_changed_continuation']) is not bool
            or value['assessment'] is not None and assessment(value['assessment']) is None):
        raise ValueError('Use bounded continuation metadata.')
    return copy.deepcopy(value)
