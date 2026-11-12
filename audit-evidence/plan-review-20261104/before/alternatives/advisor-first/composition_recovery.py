"""Request-local composition recovery; no profile writes or stored drafts."""
import copy

from chat import ModelUnavailable


VALIDATION_CODES = {
    'The conversational response could not be checked.': 'invalid_structure',
    'The provider reply did not match the response format.': 'invalid_structure',
    'The response chose an unavailable question target.': 'invalid_question',
    'The response skipped a required clarification.': 'required_clarification',
    'The conversational agenda could not be checked.': 'invalid_agenda',
    'The response introduced a date or amount outside its sources.': 'ungrounded_literal',
    'The response introduced a named entity outside its sources.': 'ungrounded_entity',
    'The response referred to unavailable information.': 'invalid_reference',
    'The response included an unsupported personal finding or action.': 'unsupported_finding',
    'The insurance explanation needs reviewed evidence.': 'missing_evidence',
    'A personal statement needs a resolved report reference.': 'missing_report_reference',
    'A personal insurance statement needs its resolved coverage report.': 'missing_coverage_reference',
    'A spouse-job statement needs its resolved worker relationship.': 'missing_worker_reference',
    'An application statement needs a resolved progress report.': 'missing_progress_reference',
    'A coverage statement conflicts with its resolved report.': 'missing_coverage_reference',
    'The provider-access explanation is outside its referenced evidence.': 'missing_evidence',
    'The response exceeded the conversational text allowance.': 'text_bound',
    'The conversational response was empty.': 'empty_response',
}
OPTIONAL_FIELDS = {'education', 'education_followups', 'task_work', 'conversation_assessment'}


class CompositionRejected(ModelUnavailable):
    """Only raised after a completed response has settled its usage."""
    def __init__(self, error, draft=None, partial=None):
        super().__init__(str(error))
        self.code = VALIDATION_CODES.get(str(error), 'invalid_structure')
        self.partial = partial
        # Feedback returns only to the same selected model, during this request.
        # Failed prose is never logged, cached, persisted or made factual evidence.
        self.feedback = {'failure': self.code, 'rejected_draft': {}}
        if isinstance(draft, dict):
            for key, limit in (('reply', 1800), ('question', 350), ('question_target', 100)):
                if isinstance(draft.get(key), str):
                    self.feedback['rejected_draft'][key] = draft[key][:limit]


REPAIR_INSTRUCTIONS = '''
The previous draft failed application validation. validation_feedback identifies the
failure and includes untrusted draft text, not evidence. Write a fresh, self-contained
response using the same resolved reports, sources, learner context and current goal.
Correct the unsupported claim or structure; keep qualifications material to the advice.
If a detail cannot be supported, help with what is supported or ask one consequential
question. Do not mention the internal validation process. Return the same JSON contract.
'''


def independent_component(validate, draft, context, moves):
    """Retain whole validated components, never sentence fragments or new wording.

    A question can survive only if the model selected an approved current meaning,
    its original wording passes, and its premises pass the answer's factual guards.
    Free-form orphaned follow-ups are not useful fallback questions.
    """
    if not isinstance(draft, dict):
        return None
    core = {key: value for key, value in draft.items() if key not in OPTIONAL_FIELDS}
    if isinstance(core.get('reply'), str) and core['reply'].strip():
        candidate = {**core, 'question_target': None, 'question': ''}
        try:
            checked = validate(candidate, context, moves)
        except (ModelUnavailable, TypeError, ValueError, KeyError):
            pass
        else:
            return {**checked, **{key: copy.deepcopy(draft[key]) for key in OPTIONAL_FIELDS if key in draft},
                    'education_followups': []}, 'reply'
    target, question = core.get('question_target'), core.get('question')
    if (not isinstance(target, str) or not any(move['id'] == target for move in moves)
            or not isinstance(question, str) or not question.strip()
            or not isinstance(core.get('agenda_update'), dict) or core['agenda_update'].get('pause') is not False):
        return None
    try:
        checked = validate({**core, 'reply': ''}, context, moves)
        if checked['question'] != question.strip():
            return None
        # The core also has assertion checks specific to reply. Apply them to
        # the standalone question, so removing the answer grants no exemption.
        validate({**core, 'reply': question, 'question_target': None, 'question': ''}, context, moves)
    except (ModelUnavailable, TypeError, ValueError, KeyError):
        return None
    return {**checked, 'education': {'purpose': 'advance', 'updates': [], 'visual': 'none'},
            'education_followups': [],
            'task_work': {'check_ids': [], 'blocking_concepts': [], 'next_step': 'answer'}}, 'question'
