"""Reported timing language, never a Medicare date calculation."""
import calendar
import re

from adaptive_flow import month
from guest_profiles import ProfileError

MONTHS = 'january february march april may june july august september october november december'.split()
MONTH_PATTERN = r'(?:' + '|'.join(MONTHS) + r')'


def reported_end_date(value):
    """Keep missing years missing; accept ordinary ordinal day spelling."""
    if not isinstance(value, str):
        raise ProfileError('Use the end date actually reported.')
    text = re.sub(r'(?<=\d)(?:st|nd|rd|th)\b', '', value.strip(), flags=re.I)
    partial = re.fullmatch(r'('+MONTH_PATTERN+r')(?:\s+(\d{1,2}))?', text, re.I)
    if partial:
        name = partial[1].lower()
        if partial[2]:
            day = int(partial[2])
            if not 1 <= day <= calendar.monthrange(2000, MONTHS.index(name)+1)[1]:
                raise ProfileError('That reported month and day are not valid.')
            return name+' '+str(day)
        return name
    return month(text)


def end_date_supported(value, quote):
    pattern = (r'\b'+MONTH_PATTERN+r'\b(?:\s+\d{1,2}(?:st|nd|rd|th)?\b,?)?'
               r'(?:\s+(?:19|20)\d{2}\b)?|\b(?:19|20)\d{2}-(?:0[1-9]|1[0-2])'
               r'(?:-\d{2})?\b|\b(?:0?[1-9]|1[0-2])[/.-](?:(?:19|20)?\d{2})\b'
               r'|\b(?:0[1-9]|1[0-2])\d{2}\b|no scheduled end|still working|ongoing')
    try:
        expected = reported_end_date(value)
    except ProfileError:
        return False
    for match in re.finditer(pattern, quote, re.I):
        try:
            if reported_end_date(match[0]) == expected:
                return True
        except ProfileError:
            pass
    return False


def after_coverage_supported(quote, active=None):
    """Validate a relative preference without converting it to a calendar date."""
    text = quote.replace('’', "'").strip().lower()
    if re.search(r'\b(?:if|suppose|hypothetical|example)\b|\?', text):
        return False
    if re.search(r"\b(?:don't|do not|doesn't|does not|not)\b.{0,30}\b(?:want|after|once|when)\b", text):
        return False
    relation = r'(?:after|once|when)\s+(?:(?:my|our|the|current|existing|health|job.based|work)\s+)*(?:cobra|insurance|coverage)(?:\s+coverage)?\s+(?:ends?|expires?|runs? out)\b'
    if not re.search(relation, text):
        return False
    return bool(active and active.get('id') == 'T04' or
                re.search(r'\b(?:medicare|coverage)\b.{0,35}\b(?:start|begin)\b', text) or
                re.search(r"\b(?:want|like|prefer|need)\b.{0,25}\b(?:it|medicare|coverage)\b.{0,15}\b(?:start|begin)\b", text))


def end_date_refinement(old, new):
    """Adding a year/day to the same reported month is additional precision."""
    try:
        previous, current = reported_end_date(old), reported_end_date(new)
    except (ProfileError, TypeError):
        return False
    partial = re.fullmatch(r'('+MONTH_PATTERN+r')(?: (\d{1,2}))?', previous)
    if not partial or not re.fullmatch(r'\d{4}-\d{2}(?:-\d{2})?', current):
        return False
    return int(current[5:7]) == MONTHS.index(partial[1])+1 and (
        partial[2] is None or len(current)==10 and int(current[8:])==int(partial[2]))
