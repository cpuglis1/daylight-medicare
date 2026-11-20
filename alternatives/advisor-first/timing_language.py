"""Reported timing language, never a Medicare date calculation."""
import calendar
import re

from adaptive_flow import month
from guest_profiles import ProfileError

MONTHS = 'january february march april may june july august september october november december'.split()
MONTH_PATTERN = r'(?:' + '|'.join(MONTHS) + r')'
MONTH_ALIASES = {name[:3]:name for name in MONTHS}
MONTH_ALIASES['sept'] = 'september'


def expanded_months(text):
    return re.sub(r'\b('+'|'.join(sorted(MONTH_ALIASES,key=len,reverse=True))+r')\b\.?',
                  lambda m: MONTH_ALIASES[m[1].lower()], text, flags=re.I)


def reported_end_date(value):
    """Keep missing years missing; accept ordinary ordinal day spelling."""
    if not isinstance(value, str):
        raise ProfileError('Use the end date actually reported.')
    text = expanded_months(re.sub(r'(?<=\d)(?:st|nd|rd|th)\b', '', value.strip().rstrip(','), flags=re.I))
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


def quoted_end_dates(quote):
    pattern = (r'\b'+MONTH_PATTERN+r'\b(?:\s+\d{1,2}(?:st|nd|rd|th)?\b,?)?'
               r'(?:\s+(?:19|20)\d{2}\b)?|\b(?:19|20)\d{2}-(?:0[1-9]|1[0-2])'
               r'(?:-\d{2})?\b|\b(?:0?[1-9]|1[0-2])[/.-](?:(?:19|20)?\d{2})\b'
               r'|\b(?:0[1-9]|1[0-2])\d{2}\b|no scheduled end|still working|ongoing')
    for match in re.finditer(pattern, expanded_months(quote), re.I):
        try:
            yield reported_end_date(match[0])
        except ProfileError:
            pass


def end_date_supported(value, quote):
    try:
        return reported_end_date(value) in quoted_end_dates(quote)
    except ProfileError:
        return False


def grounded_end_date(value, quote):
    """Keep the stated precision when a model has supplied an unsupported year.

    Only a unique matching month/day in the quoted report can survive. Never
    manufacture a year, change a stated date, or choose between two partial dates.
    """
    expected = reported_end_date(value)
    stated = set(quoted_end_dates(quote))
    if expected in stated:
        return expected
    if re.fullmatch(r'\d{4}-\d{2}(?:-\d{2})?', expected):
        name = MONTHS[int(expected[5:7])-1]
        candidates = {s for s in stated if re.fullmatch(MONTH_PATTERN+r'(?: \d{1,2})?', s)
            and s.split()[0] == name
            and (len(expected)==7 or len(s.split())==2 and int(s.split()[1])==int(expected[8:10]))}
        if len(candidates)==1:
            return candidates.pop()
    raise ProfileError('A date was not supplied at the stated precision.')


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
