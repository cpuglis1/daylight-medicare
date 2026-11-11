"""Contextual support alongside the frozen published-experiment capture module.

The original classifier remains authoritative for self-contained observations
and valid field shapes. This adapter supplies only a missing question meaning;
it never constructs a synthetic user quote or an enrollment conclusion.
"""
import copy
import calendar
import re

from natural_state import classify_situation as classify_explicit_situation
from turn_contract import bound_answer


def classify_situation(message, kind, value, existing=None, answer_context=None):
    result = classify_explicit_situation(message, kind, value, existing)
    if (result['reason'] != 'missing_supporting_clause'
            or not bound_answer(answer_context, 'S_' + kind.upper())):
        return result
    # Preserve the existing classifier's uncertainty/conflict policy on the
    # actual whole answer. Context changes meaning support, never certainty.
    if re.search(r'\b(?:if|suppose|hypothetically|for example)\b', message, re.I):
        return {**result, 'reason': 'hypothetical'}
    # A validated field literal is data, not an epistemic qualifier (month
    # names can also be ordinary words). Apply uncertainty checks to the rest.
    qualifiers = message
    if type(value.get('month')) is int and 1 <= value['month'] <= 12:
        qualifiers = re.sub(r'\b' + calendar.month_name[value['month']] + r'\b', '', qualifiers, flags=re.I)
    reason = ('question_not_report' if '?' in message else 'tentative' if re.search(
        r"\b(?:I think|I (?:do not|don['’]t) think|I guess|I believe|I thought|maybe|may|might|could|probably|not sure|not certain|unsure|uncertain|apparently)\b",
        qualifiers, re.I) else None)
    if reason:
        return {**result, 'decision': 'clarify', 'reason': reason}
    old = existing.get('value', existing) if isinstance(existing, dict) else None
    if not isinstance(old, dict) or existing.get('status') in {'unknown', 'skipped', 'stale'}:
        return {**result, 'decision': 'accept', 'reason': 'contextual_report'}
    # An omitted component may retain an already reported value. This does not
    # supply a value absent from both the record and this answer.
    resolved = {key: copy.deepcopy(old.get(key) if item is None else item) for key, item in value.items()}
    changed = any(key in old and old[key] is not None and old[key] != item for key, item in resolved.items())
    correction = bool(re.search(r'\b(?:actually|correction|correct that|I meant|instead|rather|now|not retired)\b|^no\b', message, re.I))
    return {'decision': 'clarify' if changed and not correction else 'accept',
            'reason': 'conflicting_report' if changed and not correction else 'explicit_correction' if changed else 'contextual_report',
            'value': resolved}
