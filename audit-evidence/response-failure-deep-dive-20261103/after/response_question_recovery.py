"""Recover a grounded canonical question without relaxing any answer guard.

This runs the same complete validator at most twice. It never rewrites the
answer, guesses a question meaning, makes a model call or changes a report.
"""
from chat import ModelUnavailable

VERSION = 'response-reliability-r1'


REASONS = {
    'The response introduced a named entity outside its sources.':'ungrounded_entity',
    'The response introduced a date or amount outside its sources.':'ungrounded_literal',
    'The response included an unsupported personal finding or action.':'unsupported_finding',
    'A personal statement needs a resolved report reference.':'missing_report_reference',
    'A personal insurance statement needs its resolved coverage report.':'missing_coverage_reference',
    'A spouse-job statement needs its resolved worker relationship.':'missing_worker_reference',
}


def validate_with_question_recovery(validate, value, context, moves):
    try:
        return validate(value,context,moves), None
    except ModelUnavailable as original:
        reason = REASONS.get(str(original))
        if reason is None or not isinstance(value,dict):
            raise
        target = value.get('question_target')
        candidate = next((item for item in moves if item.get('id') == target),None) if isinstance(target,str) else None
        question = candidate.get('question') if candidate else None
        canonical = question.get('question') if isinstance(question,dict) else question
        if not isinstance(canonical,str) or not canonical or canonical == value.get('question'):
            raise
        try:
            checked = validate({**value,'question':canonical},context,moves)
        except ModelUnavailable:
            raise original from None
        return checked, {'component':'question','replacement':'approved_canonical_wording','reason':reason}
