"""Request-local composition recovery; no profile writes or stored drafts."""
import copy

from chat import ModelUnavailable


VALIDATION_CODES = {
    'An active conversational response needs a follow-up question.': 'missing_followup',
    'The conversational response could not be checked.': 'invalid_structure',
    'The provider reply did not match the response format.': 'invalid_structure',
    'The response chose an unavailable question target.': 'invalid_question',
    'The response skipped a required clarification.': 'required_clarification',
    'The conversational agenda could not be checked.': 'invalid_agenda',
    'The response introduced a date or amount outside its sources.': 'ungrounded_literal',
    'The response introduced a named entity outside its sources.': 'ungrounded_entity',
    'The response referred to unavailable information.': 'invalid_reference',
    'The response denied information the Plans page is showing.': 'false_unavailability',
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
OPTIONAL_FIELDS = {'education', 'education_followups', 'task_work', 'conversation_assessment', '_reply_blocks', 'addressed_requests',
                   'block_refs', 'offer_concept'}


def normalize_blocks(value):
    """Adapt the bounded :8895 wire blocks to the existing renderer contract."""
    if not isinstance(value, dict):
        return value
    value = {k:v for k,v in value.items() if k != '_reply_blocks'}
    if 'reply_blocks' not in value:
        return value  # legacy variants and explicitly scripted old fixtures
    blocks = value.pop('reply_blocks')
    if (not isinstance(blocks, list) or len(blocks) > 4
            or any(not isinstance(b, str) or not b.strip() for b in blocks)):
        raise ModelUnavailable('The conversational response could not be checked.')
    value.update(reply='\n\n'.join(b.strip() for b in blocks), _reply_blocks=blocks)
    return value


def neutral_metadata():
    return {'education': {'purpose':'advance', 'updates':[], 'visual':'none'},
            'education_followups': [],
            'task_work': {'check_ids':[], 'blocking_concepts':[], 'next_step':'answer'}}


def recovery_display(context, question, retained_reply=''):
    """A code-owned continuation, without an unrelated lesson or error banner.

    A usable answer or question advances quietly; unfinished requests remain in
    visit context. The question/why comes from the current approved meaning,
    never from rejected prose or a fabricated acknowledgement of a report.
    """
    asked = bool(context.get('_person_asked') or context.get('discussion_plan', {}).get('answer_first')
                 or context.get('education_context', {}).get('user_requested'))
    reply = retained_reply.strip()
    if reply:
        return {'reply': reply, 'notice': None,
                'answer_state': 'partial' if asked else 'continued'}
    if question:
        why = question.get('why') if isinstance(question, dict) else None
        return {'reply': why.strip() if isinstance(why, str) else '',
                'notice': None,
                'answer_state': 'unanswered' if asked else 'continued'}
    return {'reply': 'I don’t have a reliable answer to that yet.', 'notice': None,
            'answer_state': 'unanswered'}


def independent_blocks(validate, draft, context, moves):
    """Keep only model-declared, independently checked whole blocks.

    No sentence splitting or phrase deletion. Each surviving block must pass
    alone, then the assembled result passes again. Dropped teaching metadata
    cannot mark an unseen concept delivered. Legacy prose is never split.
    """
    blocks = draft.get('_reply_blocks')
    if not context.get('discussion_plan') or not isinstance(blocks, list) or len(blocks) < 2:
        return None
    core = {k:v for k,v in draft.items() if k not in OPTIONAL_FIELDS}
    kept = []
    for block in blocks:
        try:
            checked = validate({**core, 'reply':block, 'question_target':None, 'question':''}, context, moves)
        except (ModelUnavailable, TypeError, ValueError, KeyError):
            continue
        if checked['reply'] == block.strip():
            kept.append(block.strip())
    if not kept or len(kept) == len(blocks):
        return None
    candidate = {**core, 'reply':'\n\n'.join(kept)}
    for option in (candidate, {**candidate, 'question_target':None, 'question':''}):
        try:
            checked = validate(option, context, moves)
        except (ModelUnavailable, TypeError, ValueError, KeyError):
            continue
        return {**checked, **neutral_metadata()}, 'reply_blocks'
    return None


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
    retained = independent_blocks(validate, draft, context, moves)
    if retained:
        return retained
    target, question = core.get('question_target'), core.get('question')
    if (not isinstance(target, str) or not any(move['id'] == target for move in moves)
            or not isinstance(question, str) or not question.strip()
            or not isinstance(core.get('agenda_update'), dict) or core['agenda_update'].get('pause') is not False):
        return None
    try:
        question_context = {**context, '_retaining_question': True} if context.get('discussion_plan') else context
        checked = validate({**core, 'reply': ''}, question_context, moves)
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
