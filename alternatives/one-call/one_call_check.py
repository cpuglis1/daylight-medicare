"""The narrow reply check for the one-call loop.

`check_reply` removes a reply block, or drops the question, only for content
that carries regulatory weight and can be decided from structure and literal
grounding. The same content checks run on every block and on the question:

- `ungrounded_amount`: money or a percentage, in digits, words or a currency
  code, that the grounding does not hold as money or as a percentage
- `ungrounded_date`: a calendar date, a month placed by a position word ("the
  end of July") or a quarter that the grounding does not hold
- `ungrounded_name`: a doctor, plan, insurer or medicine name that appears
  nowhere in the grounding
- `ungrounded_check_claim`: a statement that a named or personal doctor,
  medicine or plan is covered, in network, accepted or on a tier, with no check
  result for it in the tool outputs and no such report in the person's own words
- `personal_pick`: a coverage choice made for the person, in the first person
  ("I'd go with ...") or the second ("you should enroll in ...", "... is the
  right choice for you"), or an offer to enroll them
- `held_claim`: advisor-first's held Medicare Advantage deadline claim
- `identifier_request`: asking for a Social Security, Medicare or other ID
  number, directly or as "the number on your card"
- `unknown_fact_id`: a `fact_ids` entry that is not in the fact library (blocks)

It never judges wording, tone, length or which topic was chosen, and it never
edits text. Every rule is written so that doubt passes: in the two-call loop
most dropped replies were correct replies, so a missed invention is the
accepted cost of a very low false-rejection rate.

Grounding is one search space built from the whole visit: the person's own
messages, the saved reports, every tool output and every fact text.

What stays undetectable, because there is no dictionary of names here:

- a bare medicine name, above all a lower-case generic, in a sentence that
  makes no coverage claim and has no dose or "you take" beside it
- an insurer or plan name that is not beside a plan word, an insurer verb
  ("offers a plan") or an enrolment verb, unless advisor-first's
  `CARRIER_ALIASES` lists it; a lower-case or all-capitals name likewise
- a doctor written without "Dr." or "doctor" in front
- an amount or date that the grounding holds for something else: the check
  matches values, it does not bind a value to what it measures
- durations and counts ("8 months", "20 employees"), which are not checked
- a pronoun claim ("it is covered") whose subject is in another sentence

What it can wrongly reject, listed so that it can be measured:

- a general coverage statement about something the fact library never mentions
  that names no program ("dental is not covered" with no "by Original Medicare")
- an enrolment instruction ("you should sign up for Part B ...") that rewords a
  fact text or card instead of repeating it
- a true amount or date that is in no fact text, tool output or message
"""
import calendar
from decimal import Decimal, InvalidOperation
import difflib
import re
import unicodedata

import _paths  # noqa: F401  (puts advisor-first on sys.path)
from conversation_claims import asserted_coverage_text, personal_result_assertion
from natural_agent import (CARRIER_ALIASES, FIRST_PERSON_PICK, MONTHS, PROCESS_SUGGESTION,
                           _NUMBER_WORDS, _literal_claims, _month_aliases)
from pilot_knowledge import HELD_MA_DEADLINE, held_deadline_claim

UNGROUNDED_AMOUNT = 'ungrounded_amount'
UNGROUNDED_DATE = 'ungrounded_date'
UNGROUNDED_NAME = 'ungrounded_name'
UNGROUNDED_CHECK_CLAIM = 'ungrounded_check_claim'
PERSONAL_PICK = 'personal_pick'
HELD_CLAIM = 'held_claim'
IDENTIFIER_REQUEST = 'identifier_request'
UNKNOWN_FACT_ID = 'unknown_fact_id'
MALFORMED_BLOCK = 'malformed_block'
TARGET_NOT_OPEN = 'target_not_open'
MALFORMED_QUESTION = 'malformed_question'
# The order in which codes are tried; a block or question reports the first.
CONTENT_CODES = (IDENTIFIER_REQUEST, PERSONAL_PICK, HELD_CLAIM, UNGROUNDED_AMOUNT, UNGROUNDED_DATE,
                 UNGROUNDED_NAME, UNGROUNDED_CHECK_CLAIM)
BLOCK_CODES = (MALFORMED_BLOCK,) + CONTENT_CODES + (UNKNOWN_FACT_ID,)
QUESTION_CODES = (MALFORMED_QUESTION,) + CONTENT_CODES + (TARGET_NOT_OPEN,)

_DEPTH = 12


# --------------------------------------------------------------------------
# Text and grounding

def _plain(text):
    """Accents removed, typographic quotes and spaces made plain. Case is kept."""
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(char for char in text if not unicodedata.combining(char))
    return (text.replace('\u2019', "'").replace('\u2018', "'").replace('\u201c', '"')
            .replace('\u201d', '"').replace('\u00a0', ' ').replace('\u202f', ' '))


def _strings(value, depth=0):
    """Every key and leaf of a JSON-like value as text."""
    if depth > _DEPTH or value is None or isinstance(value, bool):
        return
    if isinstance(value, str):
        yield value
    elif isinstance(value, (int, float, Decimal)):
        yield str(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str):
                yield key
            yield from _strings(item, depth + 1)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            yield from _strings(item, depth + 1)
    else:
        yield str(value)


def _tool_values(outputs):
    """Tool results without the model's own arguments.

    A runner entry `{'name', 'arguments', 'output'}` grounds only through its
    output: an argument is text the model wrote, not a source.
    """
    if not isinstance(outputs, (list, tuple)):
        return [outputs]
    return [item['output'] if isinstance(item, dict) and 'output' in item and 'arguments' in item else item
            for item in outputs]


_MONTH_NAMES = [name.casefold() for name in MONTHS]
_MONTH_INDEX = {name: index + 1 for index, name in enumerate(_MONTH_NAMES)}
_MONTH_INDEX.update({name[:3]: index + 1 for index, name in enumerate(_MONTH_NAMES)})
_MONTH_INDEX['sept'] = 9
_MONTH_WORDS = sorted(_MONTH_INDEX, key=len, reverse=True)
_YEAR = r'((?:19|20)\d{2})(?!\d)'
_ISO = re.compile(r'(?<!\d)((?:19|20)\d{2})-(0[1-9]|1[0-2])(?:-(0[1-9]|[12]\d|3[01]))?(?!\d)')
_SLASH_FULL = re.compile(r'(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?![\d/])')
_SLASH_SHORT = re.compile(r'(?<![\d/.])(\d{1,2})/(\d{1,2})(?![\d/.])')
_SLASH_MONTH_YEAR = re.compile(r'(?<![\d/])(\d{1,2})/((?:19|20)\d{2})(?![\d/])')
_DASH_FULL = re.compile(r'(?<![\d-])(\d{1,2})-(\d{1,2})-((?:19|20)\d{2})(?![\d-])')
_COMPACT = re.compile(r'(?<!\d)((?:19|20)\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)')


def _date_patterns(months):
    month = r'\b(' + '|'.join(months) + r')\b\.?'
    day = r'(\d{1,2})(?:st|nd|rd|th)?(?![\d%])'
    return (
        # "February 28", "Feb. 28th, 2027"
        re.compile(month + r',?\s+(?:the\s+)?' + day + r'(?:,?\s+(?:of\s+)?' + _YEAR + r')?'),
        # "February 2027", "February of 2027"
        re.compile(month + r',?\s+(?:of\s+)?' + _YEAR),
        # "28 February 2027", "the 1st of December"
        re.compile(r'(?<![\d.,$])' + day + r'\s+(?:of\s+)?' + month + r'(?:,?\s+(?:of\s+)?' + _YEAR + r')?'),
    )


# A reply date needs a capitalised month, so "you may 1) call" is not a date.
_REPLY_DATES = _date_patterns([name.capitalize() for name in _MONTH_WORDS])
_GROUNDING_DATES = _date_patterns(_MONTH_WORDS)


def _valid(year, month, day):
    if not 1 <= month <= 12:
        return False
    if day is None:
        return True
    return 1 <= day <= calendar.monthrange(year or 2024, month)[1]


def _full_year(text):
    year = int(text)
    return year if len(text) == 4 else 2000 + year


def _dates(text, patterns, lenient):
    """Dates written in `text` as (year or None, month, day or None).

    `lenient` is for grounding: it also reads day-first numeric dates and short
    numeric forms, so a correct reply date is not lost to a notation difference.
    """
    found = set()

    def add(year, month, day):
        if _valid(year, month, day):
            found.add((year, month, day))
    with_day, with_year, day_first = patterns
    for match in with_day.finditer(text):
        add(int(match[3]) if match[3] else None, _MONTH_INDEX[match[1].casefold()], int(match[2]))
    for match in with_year.finditer(text):
        add(int(match[2]), _MONTH_INDEX[match[1].casefold()], None)
    for match in day_first.finditer(text):
        add(int(match[3]) if match[3] else None, _MONTH_INDEX[match[2].casefold()], int(match[1]))
    for match in _ISO.finditer(text):
        add(int(match[1]), int(match[2]), int(match[3]) if match[3] else None)
    for match in _SLASH_FULL.finditer(text):
        add(_full_year(match[3]), int(match[1]), int(match[2]))
        if lenient:
            add(_full_year(match[3]), int(match[2]), int(match[1]))
    if lenient:
        for match in _SLASH_SHORT.finditer(text):
            add(None, int(match[1]), int(match[2]))
        for match in _SLASH_MONTH_YEAR.finditer(text):
            add(int(match[2]), int(match[1]), None)
        for match in _DASH_FULL.finditer(text):
            add(int(match[3]), int(match[1]), int(match[2]))
        for match in _COMPACT.finditer(text):
            add(int(match[1]), int(match[2]), int(match[3]))
    return found


def _field_dates(value, found, depth=0):
    """Dates held as separate fields, such as {'year': 2027, 'month': 2}."""
    if depth > _DEPTH:
        return
    if isinstance(value, dict):
        folded = {key.casefold(): item for key, item in value.items() if isinstance(key, str)}
        for key, item in folded.items():
            if not key.endswith('month'):
                continue
            month = item if type(item) is int else _MONTH_INDEX.get(item.casefold()) if isinstance(item, str) else None
            if not month:
                continue
            year, day = folded.get(key[:-5] + 'year'), folded.get(key[:-5] + 'day')
            year = year if type(year) is int and 1900 <= year <= 2100 else None
            day = day if type(day) is int else None
            if _valid(year, month, day):
                found.add((year, month, day))
        for item in value.values():
            _field_dates(item, found, depth + 1)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _field_dates(item, found, depth + 1)


_WORD = re.compile(r'[A-Za-z0-9]+')
_CAMEL = re.compile(r'[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+')


def _canonical(number):
    try:
        value = Decimal(number)
    except (InvalidOperation, ValueError):
        return None
    return format(value.normalize(), 'f')


def _spaced(text):
    """Lower-case words with single spaces, for comparing wording."""
    return ' '.join(_WORD.findall(text.casefold()))


def _carrier_pattern(name):
    return re.compile(r'\b' + re.escape(name).replace(r'\ ', r'\s+') + r'\b', re.I)


# Money and percentages, in digits, words or a currency code.
# natural_agent._literal_claims also returns bare numbers and bare month names,
# which this check must not judge, and gives no positions, so it is not used.
_WORD_VALUES = dict(_NUMBER_WORDS, zero=0, sixteen=16, seventeen=17, eighteen=18, nineteen=19, seventy=70,
                    eighty=80, thousand=1000)
_NUMBER_WORD = '(?:' + '|'.join(sorted(_WORD_VALUES, key=len, reverse=True)) + ')'
_SPELLED = r'\b' + _NUMBER_WORD + r'(?:(?:[\s-]+|\s+and\s+)' + _NUMBER_WORD + r')*\b'
_DIGITS = r'(?:\d{1,3}(?:,\d{3})+|\d+)'
_SCALE = {'k': 1000, 'thousand': 1000, 'million': 1000000}
_MONEY = re.compile(
    r'(?:\$|\busd\s?|\bus\$)\s?(?P<a>' + _DIGITS + r')(?:\.(?P<ac>\d{1,2})(?!\d))?(?:\s?(?P<scale>k|thousand|million)\b)?'
    r'|(?<![\w.,$])(?P<b>' + _DIGITS + r')(?:\.(?P<bc>\d{1,2}))?\s*(?:dollars?|bucks?|usd)\b'
    r'|(?P<w>' + _SPELLED + r')\s+(?:dollars?|bucks?)\b', re.I)
_PERCENT = re.compile(
    r'(?:(?<![\w.,])(?P<n>\d+(?:\.\d+)?)\s?(?:%|percent\b|per cent\b|percentage points?\b)'
    r'|(?P<w>' + _SPELLED + r')\s+(?:percent|per cent)\b)'
    r'(?!\s+(?:sure|certain|confident|positive|clear|accurate|right|correct|comfortable|ready)\b)', re.I)
# A number the person gave as a price without a currency sign: "i pay 510 for it", "it's 45 a month".
_NOT_A_PRICE = r'(?!\s*(?:%|percent|mg|mcg|ml|tablets?|pills?|years?|yrs?|months?|weeks?|days?|employees|people|times|hours?|visits?))'
_PERSON_PRICE = re.compile(
    r'\b(?:pay|pays|paid|paying|costs?|costing|charges?|charged|premiums?|priced?|spend|spends|spending|spent|bills?'
    r'|billed|owes?|owed|deductibles?|copays?|fees?|afford|budget|income|earns?|salary|pension|rent|worth)\b'
    r'(?:\W+[a-z\']+){0,4}?\W+(' + _DIGITS + r'(?:\.\d{1,2})?)(?![\d,/-])' + _NOT_A_PRICE
    + r'|(?<![\w.,/-])(' + _DIGITS + r'(?:\.\d{1,2})?)\s*(?:a|per|each|every|/)\s*(?:month|mo|year|yr|week|visit|refill)\b')
# Number fields that are never an amount of money or a percentage.
_NOT_AMOUNT = set('''zip postal fips age ages year years month months day days date dates week weeks count counts
    index phone fax employees quantity qty tier rank version id ids size length birth birthday'''.split())
_LABEL_KEYS = ('id', 'label', 'kind', 'field', 'name', 'type')


def _spelled_value(text):
    total = current = 0
    for word in re.findall(_NUMBER_WORD, text.casefold()):
        value = _WORD_VALUES[word]
        if value == 100:
            current = max(current, 1) * 100
        elif value == 1000:
            total, current = total + max(current, 1) * 1000, 0
        else:
            current += value
    return Decimal(total + current)


def _money(text):
    """(canonical value, match) for each amount of money written in `text`."""
    for match in _MONEY.finditer(text):
        if match['w']:
            value = _spelled_value(match['w'])
        else:
            whole, cents = (match['a'], match['ac']) if match['a'] else (match['b'], match['bc'])
            value = Decimal(whole.replace(',', '') + ('.' + cents if cents else ''))
            value *= _SCALE.get((match['scale'] or '').casefold(), 1)
        yield _canonical(value), match


def _percent(text):
    """(canonical value, match) for each percentage written in `text`."""
    for match in _PERCENT.finditer(text):
        yield _canonical(_spelled_value(match['w']) if match['w'] else Decimal(match['n'])), match


def _key_words(key):
    return set(re.findall(r'[a-z]+', re.sub(r'([a-z])([A-Z])', r'\1 \2', key).casefold())) if isinstance(key, str) else set()


def _number_fields(value, words=frozenset(), depth=0):
    """Canonical numbers held as fields of a report or tool output, where the field can be an amount.

    A field named for a date, an age, a count or a place code is left out, and
    so is every field of an entry whose own label says the same. A field
    counted in cents is read as dollars.
    """
    if depth > _DEPTH or isinstance(value, bool):
        return
    if isinstance(value, dict):
        labels = set()
        for key in _LABEL_KEYS:
            if isinstance(value.get(key), str):
                labels |= _key_words(value[key])
        for key, item in value.items():
            yield from _number_fields(item, words | _key_words(key) | labels, depth + 1)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _number_fields(item, words, depth + 1)
    elif isinstance(value, (int, float, Decimal)) or (isinstance(value, str) and re.fullmatch(r'\d+(?:\.\d+)?', value)):
        if words & _NOT_AMOUNT:
            return
        number = Decimal(str(value))
        number = _canonical(number / 100 if words & {'cents', 'cent'} else number)
        if number is not None:
            yield number


_CHECK_TOOLS = {'check_doctor': 'doctor', 'check_medicine': 'medicine', 'get_plan_status': 'plan'}
_PLAN_STATUS_KEYS = ('recommendation', 'plans_pages', 'outcomes', 'plan_review')


def _checks(outputs):
    """(kind, words) for each check result among the tool outputs.

    An entry is recognised by its tool name, or by the shape of a bare output
    kept from an earlier turn. A failed call, or a check that returned no
    result yet, supports nothing.
    """
    for item in outputs if isinstance(outputs, (list, tuple)) else [outputs]:
        name, output = None, item
        if isinstance(item, dict) and 'output' in item and ('name' in item or 'arguments' in item):
            name, output = item.get('name'), item['output']
        if not isinstance(output, dict) or output.get('ok') is False:
            continue
        kind = _CHECK_TOOLS.get(name) if isinstance(name, str) else None
        if kind is None and output.get('kind') in ('doctor', 'medicine'):
            kind = output['kind']
        if kind is None and any(key in output for key in _PLAN_STATUS_KEYS):
            kind = 'plan'
        if kind is None or (kind != 'plan' and output.get('status', 'result') != 'result'):
            continue
        yield kind, set(_WORD.findall(_plain(' '.join(_strings(output))).casefold()))


# Closed-class English words. A capitalised one is never a name, and as the
# subject of a claim it points at something this check cannot see.
_FUNCTION_WORDS = set('''a an the this that these those my your his her its our their some any no every each either
    neither both all most many much few several one two it he she they we you i me him them us who whom whose which
    what where when why how if whether because although though while since until unless and or but nor so yet for of
    in on at by to from with without about above below under over into onto upon after before during between among
    through across against along around near off out up down is are was were be been being am do does did has have
    had will would shall should can could may might must not also just only even still already always never often
    sometimes usually generally typically here there then than as such same other another else too very more less
    least nobody everybody everyone someone anyone anybody somebody nothing everything something anything today
    tomorrow yesterday now soon later let lets yours mine ours theirs hers'''.split())
# Classes of care and coverage: what a general statement is about.
_CARE_WORDS = set('''doctor doctors provider providers specialist specialists hospital hospitals clinic clinics
    pharmacy pharmacies medicine medicines medication medications prescription prescriptions drug drugs generic
    generics brand brands visit visits care service services stay stays supplies equipment test tests screening
    screenings shot shots vaccine vaccines treatment treatments surgery surgeries therapy plan plans policy
    policies coverage insurance benefit benefits cost costs'''.split())


class _Grounding:
    """One normalised search space over everything the reply may rest on."""

    def __init__(self, grounding):
        grounding = grounding if isinstance(grounding, dict) else {}
        person = grounding.get('person_text') or []
        person = [person] if isinstance(person, str) else [item for item in person if isinstance(item, str)]
        reports = grounding.get('reports')
        tools = _tool_values(grounding.get('tool_outputs') or [])
        facts = grounding.get('fact_texts')
        facts = facts if isinstance(facts, dict) else {}
        self.fact_ids = {key for key in facts if isinstance(key, str)}
        open_ids = grounding.get('open_ids') or ()
        self.open_ids = {open_ids} if isinstance(open_ids, str) else {item for item in open_ids if isinstance(item, str)}

        parts = [_plain(item) for item in person]
        parts += [_plain(item) for source in (reports, tools, list(facts.values())) for item in _strings(source)]
        self.text = '\n'.join(parts).casefold()

        self.vocabulary, self.pairs = set(), set()
        for part in parts:
            words = []
            for word in _WORD.findall(re.sub(r"'s\b", '', part)):
                words.append(word.casefold())
                pieces = _CAMEL.findall(word)
                if len(pieces) > 1:
                    self.vocabulary.update(piece.casefold() for piece in pieces)
            self.vocabulary.update(words)
            # "united healthcare" grounds "UnitedHealthcare".
            self.pairs.update(a + b for a, b in zip(words, words[1:]) if len(a) > 2 and len(b) > 2)
        for short, full in CARRIER_ALIASES.items():
            names = [short] + sorted(full)
            if any(re.search(r'\b' + re.escape(name) + r'\b', self.text) for name in names):
                for name in names:
                    self.vocabulary.update(_WORD.findall(name))
        self._fuzzy = {}

        # What the fact library talks about in general, and what this person
        # brought: the difference marks a word as the person's own item.
        self.fact_vocabulary = {word.casefold() for text in _strings(list(facts.values()))
                                for word in _WORD.findall(_plain(text))}
        self.person_vocabulary = {word.casefold() for text in person for word in _WORD.findall(_plain(text))}
        # Instructions that a fact text or tool output itself states.
        stated = [_plain(item) for source in (tools, list(facts.values())) for item in _strings(source)]
        self.stated = ' ' + ' \n '.join(_spaced(item) for item in stated) + ' '
        self.carriers = {short for short, full in CARRIER_ALIASES.items()
                         if any(_carrier_pattern(name).search(self.text) for name in [short] + sorted(full))}
        self.checks = list(_checks(grounding.get('tool_outputs') or []))
        # The person's own sentences, for a result they reported themselves, and
        # the people they named ("my wife Odalys"), who are not items to check.
        self.person_lines = [line for item in person for line in _SENTENCE_END.split(
            re.sub(r'\b(dr|drs|mr|mrs|ms|st|vs)\.', r'\1', _plain(item).casefold())) if line.strip()]
        self.people = {match[1] for line in self.person_lines for match in _NAMED_PERSON.finditer(line)}

        # Money and percentages. A number grounds an amount only where the
        # grounding itself holds it as one: written as money or as a percentage,
        # a number the person gave as a price, or a number field of a report or
        # tool output that is not a date, an age, a count or a place code.
        undated = self.text
        for pattern in (_ISO, _SLASH_FULL, _DASH_FULL, _COMPACT) + _GROUNDING_DATES:
            undated = pattern.sub(' ', undated)
        self.money = {value for value, _match in _money(undated)}
        self.percent = {value for value, _match in _percent(undated)}
        for item in person:
            for match in _PERSON_PRICE.finditer(_plain(item).casefold()):
                number = _canonical((match[1] or match[2]).replace(',', ''))
                if number is not None:
                    self.money.add(number)
        self.fields = set()
        for source in (reports, tools):
            self.fields.update(_number_fields(source))

        self.dates = _dates(self.text, _GROUNDING_DATES, lenient=True)
        for source in (reports, tools):
            _field_dates(source, self.dates)
        # Month-only grounding: resolved report dates (advisor-first's own
        # rule), and a month the person named. The existing month finder is
        # used here because it does not read the modal "may" as a month.
        report_list = ([{'id': key, 'value': item} for key, item in reports.items()] if isinstance(reports, dict)
                       else reports if isinstance(reports, list) else [])
        months = set(_month_aliases(report_list))
        for item in person:
            months.update(claim.casefold() for claim in _literal_claims(_plain(item)))
        for name in months:
            if name in _MONTH_INDEX:
                self.dates.add((None, _MONTH_INDEX[name], None))

    def has_word(self, word):
        """A name word is grounded exactly, as a plural, as a joined pair or as a near spelling."""
        word = word.casefold()
        if word in self.vocabulary or word in self.pairs:
            return True
        if word.endswith('s') and word[:-1] in self.vocabulary or word + 's' in self.vocabulary:
            return True
        if len(word) < 6:
            return False
        if word not in self._fuzzy:
            near = [item for item in self.vocabulary if item[0] == word[0] and abs(len(item) - len(word)) <= 2]
            self._fuzzy[word] = bool(difflib.get_close_matches(word, near, n=1, cutoff=0.85))
        return self._fuzzy[word]

    def has_date(self, year, month, day):
        """A reply date is grounded by a known date in the same month that fits its day and year.

        A known month without a day supports its first and last day. A known
        date without a year supports any year, unless another fitting date
        carries a year: then the reply's year must be one of those.
        """
        fits = []
        for known_year, known_month, known_day in self.dates:
            if known_month != month:
                continue
            if day is None or day == known_day:
                fits.append(known_year)
            elif known_day is None:
                span = year or known_year
                last = {calendar.monthrange(span, month)[1]} if span else {28, 29} if month == 2 else {
                    calendar.monthrange(2023, month)[1]}
                if day == 1 or day in last:
                    fits.append(known_year)
        if not fits:
            return False
        return year is None or year in fits or all(known is None for known in fits)

    def has_month(self, month, year=None):
        """Some known date falls in this month, under the same rule for the year as has_date."""
        fits = [known_year for known_year, known_month, _day in self.dates if known_month == month]
        return bool(fits) and (year is None or year in fits or all(known is None for known in fits))

    def has_money(self, value):
        return _canonical(value) in self.money | self.fields

    def has_percent(self, value):
        return bool({_canonical(value), _canonical(value / 100)} & self.fields) or _canonical(value) in self.percent

    def states(self, text):
        """A fact text or tool output states these same words, in this order."""
        words = _spaced(text)
        return bool(words) and ' ' + words + ' ' in self.stated

    def is_general(self, word):
        """A word the fact library itself uses, or a class of care: not this person's own item."""
        word = re.sub(r"'s\Z", '', word).casefold()
        return (word in _FUNCTION_WORDS or word in _NEUTRAL or word in _CARE_WORDS or word in self.fact_vocabulary
                or (word.endswith('s') and word[:-1] in self.fact_vocabulary) or word + 's' in self.fact_vocabulary)

    def has_check(self, kind, words, result):
        """A check result in the tool outputs supports a claim of this kind about these name words.

        A doctor or medicine claim needs a result of that kind; with name
        words, one of them must appear in it. A plan status output supports a
        claim only by naming the item. A result the person reported in their
        own words ("dr rookmere takes medicare") may be said back to them.
        """
        words = [word.casefold() for word in words if len(word) > 2]
        for check_kind, text in self.checks:
            if words and any(word in text for word in words) and (check_kind in (kind, 'plan') or kind == 'named'):
                return True
            if not words and check_kind == kind:
                return True
        noun = {'doctor': _DOCTOR_NOUN, 'medicine': _MEDICINE_NOUN}.get(kind)
        for line in self.person_lines:
            if not _REPORTED_RESULT[result].search(line):
                continue
            if any(word in _WORD.findall(line) for word in words) or (
                    not words and noun and re.search(r'\b(?:' + noun + r')\b', line)):
                return True
        return False


# --------------------------------------------------------------------------
# Amounts and dates

_VAGUE_BEFORE = re.compile(r'\b(?:few|couple|several|some|many|of)\s+\Z', re.I)


def _ungrounded_amount(text, ground):
    for value, match in _money(text):
        if match['w'] and not set(re.findall(_NUMBER_WORD, match['w'].casefold())) - {'hundred', 'thousand'} \
                and _VAGUE_BEFORE.search(text[:match.start()]):
            continue   # "a few hundred dollars" states no amount
        if not ground.has_money(Decimal(value)):
            return True
    for value, _match in _percent(text):
        if not ground.has_percent(Decimal(value)):
            return True
    return False


_TITLE_MONTH = r'\b(' + '|'.join(name.capitalize() for name in _MONTH_WORDS) + r')\b'
# A month placed by a position word is a date claim: "the end of July", "mid-September".
_PLACED_MONTH = re.compile(
    r'\b(?:(?:end|beginning|start|middle|first|first day|last day|first week|last week|first half|second half)\s+of\s+'
    r'|(?:[Mm]id|[Ee]arly|[Ll]ate)[\s-]+)' + _TITLE_MONTH)
_QUARTER = re.compile(r'\bQ([1-4])\s*(?:of\s+)?' + _YEAR
                      + r'|\b(first|second|third|fourth)\s+quarter\s+of\s+' + _YEAR, re.I)
_ORDINALS = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4}


def _ungrounded_date(text, ground):
    for year, month, day in _dates(text, _REPLY_DATES, lenient=False):
        if ground.has_date(year, month, day):
            continue
        # "02/03/2027" may have been written day first.
        if day and day <= 12 and _SLASH_FULL.search(text) and ground.has_date(year, day, month):
            continue
        return True
    for match in _PLACED_MONTH.finditer(text):
        if not ground.has_month(_MONTH_INDEX[match[1].casefold()]):
            return True
    for match in _QUARTER.finditer(text):
        quarter = int(match[1]) if match[1] else _ORDINALS[match[3].casefold()]
        year = int(match[2] or match[4])
        if not any(ground.has_month(month, year) for month in range(quarter * 3 - 2, quarter * 3 + 1)):
            return True
    return False


# --------------------------------------------------------------------------
# Names

_WEEKDAYS = {'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'}
_STATES = set('''alabama alaska arizona arkansas california colorado connecticut delaware florida georgia hawaii
    idaho illinois indiana iowa kansas kentucky louisiana maine maryland massachusetts michigan minnesota
    mississippi missouri montana nebraska nevada hampshire jersey mexico york carolina dakota ohio oklahoma oregon
    pennsylvania rhode island tennessee texas utah vermont virginia washington wisconsin wyoming columbia district
    north south west new puerto rico'''.split())
# Program terms and generic plan-type words. They name kinds of coverage, never
# one company's product, so they are never treated as an invented name.
_NEUTRAL = _WEEKDAYS | _STATES | set(_MONTH_INDEX) | set('''
    medicare medigap medicaid advantage original part parts plan plans social security administration extra help
    cobra daylight supplement supplemental insurance initial special general annual open enrollment period election
    health savings account marketplace prescription drug coverage premium deductible network tier star stars
    maintenance organization preferred provider private fee service needs dual eligible employer group retiree
    union federal employee employees benefits high medical cost select point veterans affairs tricare champva individual
    family standard basic traditional bronze silver gold platinum finder page tab obamacare
    mom mum dad mother father husband wife spouse partner son daughter sister brother grandma grandpa
    grandmother grandfather aunt uncle mr mrs ms miss dr doctor yes no ok okay'''.split())

_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:['-][A-Za-z0-9]+)*|\d+(?:[.,]\d+)*")
_BOUNDARY = re.compile(r'[.!?:;"\n*#>\u2022\u2013\u2014]|\s-\s')
# "Dr." in any case takes the next word as a name; further words only when
# the name is written in ordinary capitals. "doctor" spelled out takes a
# capitalised word only, so "your doctor accepts" is not a name.
_NAME_WORD = r"[A-Za-z][A-Za-z]*(?:['-][A-Za-z]+)*"
_CAPITAL_WORD = r"[A-Z][A-Za-z]*(?:['-][A-Za-z]+)*"
_DOCTOR = re.compile(r"\b[Dd][Rr][Ss]?\b\.?[ \t]+(" + _NAME_WORD + r")((?:[ \t]+(?:[A-Z]\.|" + _CAPITAL_WORD + r")){0,2})")
_DOCTOR_WORD = re.compile(r"\b(?:[Dd]octor|DOCTOR)[ \t]+(" + _CAPITAL_WORD + r")")
_DESIGNATORS = {'plan', 'plans', 'hmo', 'ppo', 'pdp', 'pffs', 'snp', 'advantage', 'medigap', 'supplement',
                'supplemental', 'insurance', 'rx'}
_PLAN_AFTER = re.compile(r"\s+\(?(?:plans?|polic(?:y|ies)|networks?|insurance|coverage|premiums?|formulary|hmo|ppo|pdp|members?)\b", re.I)
# "Cigna offers a plan": the subject of an insurer's verb, even as the first word of a sentence.
_INSURER_VERB = re.compile(
    r"\s+(?:offers?|sells?|markets?|provides?|runs?)\s+(?:(?:a|an|the|several|many|some|its|their|two|three|no|one|\d+)\s+)?"
    r"(?:[a-z-]+\s+){0,2}?(?:plans?|polic(?:y|ies)|coverage|networks?)\b", re.I)
_PLAN_BEFORE = re.compile(
    r"(?:\b(?:plans?|polic(?:y|ies)|coverage|insurance|insurers?|carriers?|compan(?:y|ies))\s+"
    r"(?:from|through|with|by|like|called|named|at|such as|including)"
    r"|\b(?:enroll(?:ing|ed)? in|join(?:ing|ed)?|switch(?:ing|ed)? to|sign(?:ing|ed)? up (?:for|with)|mov(?:e|ing|ed) to"
    r"|stay(?:ing|ed)? with|stick(?:ing)? with|go(?:ing)? with|offered by|sold by|run by"
    r"|picks?|picked|picking|chooses?|chose|choosing|prefers?))"
    r"\s+(?:the\s+|a\s+|an\s+|your\s+)?\Z", re.I)
_MEDICINE_BEFORE = re.compile(
    r"(?:\b(?:take|takes|taking|took|taken|prescribed|refill|refills|refilling)\s+"
    r"(?:your\s+|the\s+|her\s+|his\s+|their\s+|a\s+|an\s+)?(?:(?:generic|brand-name|brand name|daily|weekly)\s+)?"
    r"|\b(?:medicines?|medications?|meds|drugs?|prescriptions?|refills?|generic|brand[- ]name)\s*[,:(-]?\s*"
    r"(?:like|such as|including|called|named|for|of|is|are|was|were)?\s*(?:your\s+|the\s+)?)\Z", re.I)
_MEDICINE_AFTER = re.compile(
    r"\s+(?:\d+(?:\.\d+)?\s*(?:mg|mcg|ml|g|iu|units?|milligrams?|micrograms?)"
    r"|prescriptions?|tablets?|pills?|capsules?|refills?|doses?|dosage|inhalers?|injections?|pens?|patch(?:es)?|generic)\b", re.I)
_LIST_GAP = re.compile(r',?\s+(?:and\s+|or\s+)?\Z|,\s*\Z')


def _name_words(token):
    """The words of one written name token, without a possessive ending."""
    return [word for word in re.split(r"['-]", re.sub(r"'s\Z", '', token)) if word]


def _candidate(token):
    """A capitalised word that could be part of a name: not a short acronym, not a program term."""
    core = re.sub(r"'s\Z", '', token)
    return (len(core) > 2 and core[0].isupper() and (any(char.islower() for char in core) or len(core) > 5)
            and not any(char.isdigit() for char in core) and core.casefold() not in _NEUTRAL)


def _doctor_names(text):
    """The name words written after each doctor cue in `text`."""
    for match in _DOCTOR.finditer(text):
        first, more = match[1], match[2]
        tokens = [first]
        if first[0].isupper() and not first.isupper():
            tokens += more.replace('.', ' ').split()
        yield match, [word for token in tokens for word in _name_words(token)
                      if len(word) > 1 and word.casefold() not in _NEUTRAL and word.casefold() not in _FUNCTION_WORDS]
    for match in _DOCTOR_WORD.finditer(text):
        yield match, [word for word in _name_words(match[1])
                      if len(word) > 2 and word.casefold() not in _NEUTRAL and word.casefold() not in _FUNCTION_WORDS]


def _ungrounded_name(text, ground):
    text = _plain(text)
    # A doctor: every written name word after the cue must be the person's or a source's.
    for _match, words in _doctor_names(text):
        if any(not ground.has_word(word) for word in words):
            return True
    # An insurer advisor-first knows by more than one name, wherever and however it is written.
    for short, full in CARRIER_ALIASES.items():
        if short not in ground.carriers and any(_carrier_pattern(name).search(text) for name in [short] + sorted(full)):
            return True
    # Capitalised runs, checked only where the sentence marks them as a plan,
    # an insurer or a medicine. A capitalised word anywhere else is not judged.
    tokens = []
    position, start = 0, True
    for match in _TOKEN.finditer(text):
        gap = text[position:match.start()]
        first = start or bool(_BOUNDARY.search(gap))
        tokens.append((match.group(), match.start(), match.end(), first))
        position, start = match.end(), False
    runs, current = [], []
    for token in tokens:
        word, begin, _end, first = token
        joined = current and not first and re.fullmatch(r'[ \t]+|[ \t]*&[ \t]*', text[current[-1][2]:begin])
        if word[0].isupper() and joined:
            current.append(token)
        else:
            if current:
                runs.append(current)
            current = [token] if word[0].isupper() else []
    if current:
        runs.append(current)
    previous_end, previous_named = None, False
    for run in runs:
        begin, end = run[0][1], run[-1][2]
        sentence_start = max((item[1] for item in tokens if item[3] and item[1] <= begin), default=0)
        before, after = text[sentence_start:begin], text[end:]
        # As the owner of a plan word or the subject of an insurer's verb, even
        # the first word of a sentence is a name unless it is a function word.
        subject = bool(_INSURER_VERB.match(after) or (run[-1][0].endswith("'s") and _PLAN_AFTER.match(after)))
        named = bool(
            subject or any(item[0].casefold() in _DESIGNATORS for item in run)
            or _PLAN_AFTER.match(after) or _PLAN_BEFORE.search(before)
            or _MEDICINE_AFTER.match(after) or _MEDICINE_BEFORE.search(before)
            or (previous_named and _LIST_GAP.fullmatch(text[previous_end:begin])))
        if named:
            for word, _begin, _end, first in run:
                # Otherwise the first word of a sentence is capitalised whatever it is.
                if not _candidate(word) or (first and not (
                        subject and re.sub(r"'s\Z", '', word).casefold() not in _FUNCTION_WORDS)):
                    continue
                if any(len(part) > 2 and not ground.has_word(part) for part in _name_words(word)):
                    return True
        previous_end, previous_named = end, named
    return False


# --------------------------------------------------------------------------
# Check results

# A sentence that states the result of a check ("is in network", "is covered",
# "accepts Medicare", "is on tier 1") about this person's doctor or medicine, or
# about a named item, must rest on a check result among the tool outputs. A
# general statement ("hospital stays are covered under Part A") is not one.
# conversation_claims.personal_result_assertion is the existing pattern for
# "your doctors are covered"; the patterns here add named items, tiers and the
# active forms, and conversation_claims.asserted_coverage_text keeps questions,
# conditions and "whether" clauses out, as it does in advisor-first.
_BE = r"\b(?:is|isn't|are|aren't|was|wasn't|were|weren't|will be|won't be|would be|should be|stays?|remains?)\s+"
_RESULT = re.compile(
    _BE + r"(?:(?:not|also|still|already|currently|now|definitely|fully|both|all|each)\s+)*"
    r"(?P<what>covered|in[- ](?:(?:the|that|your|their|its|this)\s+)?network|out[- ]of[- ]network"
    r"|on\s+(?:the|its|their|that|your|every|each|most|this|a)\s+(?:plan'?s?\s+)?(?:formulary|drug list)"
    r"|(?:on|in)\s+(?:(?:a|the)\s+)?(?:[a-z]+\s+)?tier\s*\w+"
    r"|(?:a|an)\s+tier[- ]?\w+\s+(?:drug|medicine|medication|generic|brand))\b", re.I)
_ACCEPTS = re.compile(
    r"\b(?:accepts?|takes?|participates?\s+in)\s+(?:original\s+)?(?:medicare|medicaid|assignment"
    r"|(?:that|this|the|your|their)\s+plan|new\s+(?:medicare\s+)?patients)\b", re.I)
_BY_A_PROGRAM = re.compile(r"\s+(?:by|under|through|with|in)\s+(?:original\s+medicare|medicare(?!\s+advantage\s+plan)"
                           r"|part\s+[abcd]\b|medigap|medicaid)", re.I)
_DOCTOR_NOUN = r"doctors?|providers?|specialists?|cardiologists?|physicians?|surgeons?|dentists?|hospitals?|clinics?|pharmac(?:y|ies)"
_MEDICINE_NOUN = r"medicines?|medications?|meds|prescriptions?|drugs?|pills?|inhalers?"
_NOT_THE_ITEM = r"(?!\s+(?:visits?|care|bills?|costs?|services|appointments?|coverage|plans?|list|needs)\b)"
_OWN_ITEM = re.compile(r"\b(?:your|his|her|their|[a-z]+'s)\s+(?:[a-z-]+\s+){0,2}?(?:(?P<doctor>" + _DOCTOR_NOUN
                       + r")|(?P<medicine>" + _MEDICINE_NOUN + r"))\b" + _NOT_THE_ITEM
                       + r"(?P<name>(?:\s+[A-Za-z][A-Za-z-]+)?)", re.I)
_COVERS_OWN = re.compile(
    r"\b(?:covers?|includes?|pays?\s+for)\s+(?:your|his|her|their|[a-z]+'s)\s+(?:[a-z-]+\s+){0,2}?"
    r"(?:(?P<doctor>" + _DOCTOR_NOUN + r")|(?P<medicine>" + _MEDICINE_NOUN + r"))\b" + _NOT_THE_ITEM, re.I)
_COVERS_NAMED = re.compile(r"\b(?:covers?|includes?)\s+(?:(?:your|the|his|her)\s+)?(" + _NAME_WORD + r")")
# A program or a kind of plan as the subject: general teaching, not one plan's result.
_GENERAL_SUBJECT = re.compile(
    r"(?:\b(?:a|an|any|each|every|most|some|many|all)\s+(?:[a-z-]+\s+){0,3}?plans?|\bplans"
    r"|\b(?:medicare|medicaid|medigap|part\s+[a-d]|advantage))"
    r"(?:\s+(?:also|usually|generally|only|still|typically|often))?\s*\Z", re.I)
# The same kind of result in the person's own words.
_REPORTED_RESULT = {
    'covered': re.compile(r"\bcover(?:ed|s)?\b"),
    'network': re.compile(r"\bnetwork\b"),
    'accepts': re.compile(r"\b(?:accepts?|takes?|participat\w+)\s+(?:in\s+)?(?:original\s+)?"
                          r"(?:medicare|medicaid|assignment|my|our|the|that|this|new)\b"),
    'tier': re.compile(r"\btier\b|\bformulary\b|\bdrug list\b"),
}
_NAMED_PERSON = re.compile(r"\b(?:wife|husband|spouse|partner|mom|mum|mother|dad|father|son|daughter|sister|brother"
                           r"|friend|aunt|uncle|grandma|grandmother|grandpa|grandfather)\W+(?:is\s+|named\s+|called\s+)?"
                           r"([a-z][a-z'-]+)")
_ADVERBS = {'also', 'still', 'usually', 'generally', 'typically', 'often', 'probably', 'likely', 'already', 'now',
            'currently', 'then', 'definitely', 'both', 'all', 'each'}


def _result_kind(what):
    what = what.casefold()
    return 'covered' if what == 'covered' else 'network' if 'network' in what else 'tier'


def _claim_subject(before, ground):
    """(kind, name words) for what a result is claimed about, or None for a general statement."""
    window = before[-90:]

    def near(end):
        # The subject sits right before the result: at most three words between.
        return len(_PICK_WORD.findall(window[end:])) <= 3
    doctors = [(match.end(), words) for match, words in _doctor_names(window) if near(match.end())]
    if doctors:
        return 'doctor', max(doctors)[1]
    own = None
    for own in _OWN_ITEM.finditer(window):
        pass
    if own and near(own.end()):
        name = own['name'].strip()
        return ('doctor' if own['doctor'] else 'medicine',
                [name] if name and not ground.is_general(name) else [])
    words = _PICK_WORD.findall(window)
    while words and words[-1].casefold() in _ADVERBS:
        words.pop()
    if not words:
        return None
    head = re.sub(r"'s\Z", '', words[-1])
    if len(head) < 3 or head.isdigit() or head.casefold() in _FUNCTION_WORDS or head.casefold() in ground.people:
        return None   # a pronoun, a letter, or a person: "Odalys is covered under your plan"
    if not ground.is_general(head):
        return 'named', [head]
    # "... and Bayside Clinic accepts Medicare": a general noun with a name in
    # front of it. The first word of the clause is capitalised whatever it is.
    if len(words) > 2 and _candidate(words[-2]) and not ground.is_general(words[-2]):
        return 'named', [re.sub(r"'s\Z", '', words[-2])]
    return None


# A result named inside a clause that states no result. "We'll make sure Dr. Wise is covered",
# "you'll want a plan that covers your doctor" and "a plan only works for you if lisinopril is
# covered" say what will be checked, what is wanted or what would have to hold. None of them
# says a check found anything. The frame is recognised only in the clause the result sits in,
# right before its subject, and only in forms that look ahead: "I checked that ...", "I can
# confirm that ...", "a quick check shows ..." and "I found plans that include ..." are
# statements of a result and are still claims.
_LOOKING_AHEAD = (r"(?:we'll|we will|i'll|i will|you'll|you will|let's|let us|to|can|could|need(?:s|ed)? to"
                  r"|want(?:s|ed)? to|going to|have to|has to|should|must|helps? (?:me|us|you)(?: to)?)")
_UP_TO_SUBJECT = r"(?:\s+that)?(?:\s+\S+){0,6}\s*\Z"
_RESULT_NOT_STATED = (
    # a condition: "... only if Dr. Wise is covered", "as long as she is in network"
    re.compile(r"\b(?:only if|if|as long as|so long as|unless|provided|assuming|once|until|in case)\b" + _UP_TO_SUBJECT, re.I),
    # something still to be done: "we'll make sure ...", "so we can check that ...", "to verify that ..."
    re.compile(r"\b" + _LOOKING_AHEAD + r"\s+(?:\w+\s+)?(?:make sure|ensure|double[- ]check|check|verify|find out|determine)\b"
               + _UP_TO_SUBJECT, re.I),
    re.compile(r"\b(?:we'll|we will|i'll|i will|let's|let us|to|need(?:s|ed)? to|want(?:s|ed)? to|going to|have to|has to)"
               r"\s+(?:\w+\s+)?(?:confirm|see)\b" + _UP_TO_SUBJECT, re.I),
    # the kind of plan that is wanted: "you'll want a plan that covers ...", "focus on plans that include ..."
    re.compile(r"\b(?:want|wants|need|needs|look(?:ing)? for|focus(?:ing)? on|find|choose|pick|prefer|consider"
               r"|narrow(?:ing)?(?: down)? to|aim(?:ing)? for|search(?:ing)? for|stick(?:ing)? (?:to|with)|only count)\b"
               r"[^.;:]{0,40}?\b(?:plans?|options?|polic(?:y|ies)|coverage|ones?)\s+(?:that|which|where|in which)\b"
               r"(?:\s+\S+){0,6}\s*\Z", re.I),
)


def _not_asserted(line, start):
    """Whether the result that starts at ``start`` sits in a condition, a task still to do or a wish."""
    clause = re.split(r"[,;:\u2014\u2013]", line[:start])[-1]
    return any(pattern.search(clause) for pattern in _RESULT_NOT_STATED)


def _ungrounded_check_claim(text, ground):
    plain = _ABBREVIATION.sub(r'\1', _plain(text))
    for line in asserted_coverage_text(plain).split('\n'):
        claims, general = [], False   # claims: (kind, name words, kind of result)
        for match in _RESULT.finditer(line):
            subject = _claim_subject(line[:match.start()], ground)
            if not subject:
                continue
            if _not_asserted(line, match.start()):
                general = True   # looked ahead to, wished for or conditional: no result is stated
                continue
            if match['what'].casefold() == 'covered' and _BY_A_PROGRAM.match(line[match.end():]) \
                    and (subject[0] == 'named' or not subject[1]):
                # "your prescriptions are covered under Part D" and "acupuncture
                # is covered under Part B" are general teaching, not a check.
                general = True
                continue
            claims.append(subject + (_result_kind(match['what']),))
        for match in _ACCEPTS.finditer(line):
            subject = _claim_subject(line[:match.start()], ground)
            if subject:
                claims.append(subject + ('accepts',))
        for match in _COVERS_OWN.finditer(line):
            if _GENERAL_SUBJECT.search(line[:match.start()]) or _not_asserted(line, match.start()):
                general = True   # "a Part D plan covers your prescriptions from its own list"
                continue
            claims.append(('doctor' if match['doctor'] else 'medicine', [], 'covered'))
        for match in _COVERS_NAMED.finditer(line):
            word = match[1]
            if _GENERAL_SUBJECT.search(line[:match.start()]):
                continue   # "Original Medicare covers ..." is general teaching
            if _not_asserted(line, match.start()):
                general = True
                continue
            if re.match(r"[Dd][Rr][Ss]?\Z|[Dd]octor\Z", word):
                names = [words for found, words in _doctor_names(line[match.start(1):]) if found.start() == 0]
                claims.append(('doctor', names[0] if names else [], 'covered'))
            elif not ground.is_general(word) and word.casefold() not in ground.people and (
                    _candidate(word) or word.casefold() in ground.person_vocabulary):
                claims.append(('named', [word], 'covered'))
        if personal_result_assertion(line) and not claims and not general:
            claims.append(('doctor' if re.search(r'\b(?:' + _DOCTOR_NOUN + r')\b', line, re.I) else 'medicine', [],
                           'network' if 'network' in line.casefold() else 'covered'))
        if any(not ground.has_check(*claim) for claim in claims):
            return True
    return False


# --------------------------------------------------------------------------
# Personal pick

# natural_agent.FIRST_PERSON_PICK is the trigger, but alone it is too broad for
# this check: it also matches "I'd suggest we look at your doctors next" and
# "I'd keep that letter handy". A trigger counts here only when what follows
# it is a coverage choice.
_PICK_VERBS = {'keep': 'keeping', 'stay': 'staying', 'switch': 'switching', 'choose': 'choosing', 'pick': 'picking',
               'go with': 'going with', 'drop': 'dropping', 'leave': 'leaving', 'stick with': 'sticking with',
               'get': 'getting', 'buy': 'buying', 'enroll': 'enrolling', 'sign up': 'signing up', 'join': 'joining',
               'take': 'taking', 'delay': 'delaying', 'decline': 'declining', 'cancel': 'canceling',
               'select': 'selecting', 'opt': 'opting', 'lean': 'leaning', 'skip': 'skipping', 'wait': 'waiting'}
_PICK_FORMS = set(_PICK_VERBS) | set(_PICK_VERBS.values()) | {'cancelling'}
_VERB = '|'.join(sorted(_PICK_VERBS, key=len, reverse=True))
_EXTRA_PICK = re.compile(
    r"\bI(?:'d| would| wouldn't| would not)(?: personally| probably| still| just| definitely| honestly)? (?:" + _VERB + r")\b"
    r"|\b(?:I|we)(?:'d| would)?(?: personally| probably| still| just| definitely| strongly| really| honestly)? (?:recommend|suggest|advise)\b"
    r"|\bmy (?:vote|choice)\b"
    r"|\bI(?: really| honestly| do| personally)? think (?:you should|you ought to|you(?:'d| would) be better off"
    r"|your best (?:bet|option|choice|move) (?:is|would be)|the best (?:plan|option|choice|fit)(?: for you)? (?:is|would be))", re.I)
_ADVICE_HEAD = re.compile(r"(?:recommend|suggest|advise|should|ought to|better off|is|would be)\Z|\Amy ", re.I)
_OBJECT_WORDS = {'plan', 'plans', 'policy', 'policies', 'coverage', 'insurance', 'medigap', 'medicare', 'medicaid',
                 'advantage', 'supplement', 'supplemental', 'cobra', 'hmo', 'ppo', 'pdp', 'part'}
_ATTACHED = {'on', 'with', 'in', 'to', 'for', 'into', 'toward', 'towards', 'up', 'off', 'onto'}
_DETERMINERS = {'a', 'an', 'the', 'your', 'this', 'that', 'these', 'those', 'either', 'both', 'his', 'her', 'their',
                'my', 'our', 'its'}
_NOT_ADJECTIVES = {'at', 'of', 'to', 'into', 'about', 'through', 'on', 'in', 'for', 'with', 'from', 'over', 'before',
                   'after', 'until', 'when', 'if', 'how', 'what', 'whether', 'and', 'or', 'it', 'you', 'we', 'us'}
_AFTER_CHOICE = {'and', 'or', 'with', 'plus', 'now', 'instead', 'over', 'rather', 'for', 'because', 'since', 'if',
                 'when', 'while', 'as', 'so', 'but', 'then', 'here', 'right', 'this', 'next', 'during', 'before',
                 'after', 'until', 'at', 'in', 'on', 'to', 'unless', 'through', 'from', 'first', 'too', 'again',
                 'once', 'than', 'that', 'which', 'by', 'alongside', 'together', 'anyway', 'though', 'yet',
                 'anymore', 'entirely', 'altogether', 'today', 'soon', 'later', 'early', 'already', 'still'}
# "I'd suggest Original Medicare first" names the next topic, not a choice.
_AFTER_TOPIC = _AFTER_CHOICE - {'first', 'next', 'as', 'here', 'this', 'then', 'before'}
_ABBREVIATION = re.compile(r'\b(Dr|Drs|Mr|Mrs|Ms|St|vs)\.')
_FILLERS = {'is', 'would', 'be', 'to', 'that', 'here', 'still', 'just', 'also'}
_MODALS = {'should', 'could', 'might', 'may', 'would', 'can', 'to', 'just', 'not', 'also', 'both', 'all'}
_TIME_WORDS = _WEEKDAYS | set(_MONTH_INDEX)
_PICK_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*|\d+")
_SENTENCE_END = re.compile(r'(?<=[.!?])\s+|\n+')
_CLAUSE_END = re.compile(r'[.!?;:,\n\u2013\u2014]|\s-\s')


def _coverage_choice(words, after=_AFTER_CHOICE, need=None):
    """True when `words` open with a coverage noun phrase: "your employer plan", "on Part B", "Plan G".

    need='capital': the phrase must be written as a particular path or product
    ("Original Medicare", "Plan N"), not "a plan". need='name': it must name
    one product, by a plan letter or a capitalised word that is not a program term.
    """
    core = _coverage_words(words, after)
    if not core or need is None:
        return bool(core)
    if need == 'capital':
        return any(word[0].isupper() for word in core)
    return any((len(word) == 1 and word.isupper() and index and core[index - 1].casefold() == 'plan')
               or (len(word) > 1 and word[0].isupper() and word.casefold() not in _NEUTRAL)
               for index, word in enumerate(core))


def _coverage_words(words, after=_AFTER_CHOICE):
    """The coverage words that open `words`, or [] when they do not open with a coverage noun phrase."""
    index = 0
    while index < len(words) and index < 2 and words[index].casefold() in _ATTACHED:
        index += 1
    while index < len(words) and (words[index].casefold() in _DETERMINERS or words[index].endswith("'s")):
        index += 1
    adjectives = 0
    while index < len(words) and adjectives < 2:
        word = words[index]
        if word.casefold() in _OBJECT_WORDS or word[0].isupper():
            break
        if word.casefold() in _NOT_ADJECTIVES:
            return []
        adjectives, index = adjectives + 1, index + 1
    core = []
    while index < len(words):
        word = words[index]
        if (word.casefold() in _OBJECT_WORDS or (word[0].isupper() and word.casefold() not in _TIME_WORDS)
                or (core and len(word) == 1 and word.isalpha())):
            core.append(word)
            index += 1
        else:
            break
    # "your Part B start date" continues past the coverage words: not a choice.
    return core if core and (index == len(words) or words[index].casefold() in after) else []


def _pick_verb(words):
    """The length of a choice verb at the start of `words`, or 0."""
    if len(words) > 1 and (words[0] + ' ' + words[1]).casefold() in _PICK_FORMS:
        return 2
    return 1 if words and words[0].casefold() in _PICK_FORMS else 0


def _advised_choice(words, verb_next=False):
    """What follows "I recommend", "my advice", "I think you should": a coverage choice or a process step."""
    index = 0
    while index < len(words) and words[index].casefold() in _FILLERS:
        index += 1
    after_to = index > 0 and words[index - 1].casefold() == 'to'
    subject = index < len(words) and words[index].casefold() in {'we', 'you', 'us', "let's"}
    if subject:
        index += 1
        while index < len(words) and words[index].casefold() in _MODALS:
            index += 1
    rest = words[index:]
    if not rest:
        return False
    length = _pick_verb(rest)
    if length:
        return _coverage_choice(rest[length:])
    if subject or after_to or verb_next or rest[0].casefold().endswith('ing'):
        return False   # another verb: a next step in the process, not a choice of coverage
    return _coverage_choice(rest, _AFTER_TOPIC)


# The same choice put to the person in the second person. Advisor-first holds
# these as one literal inside natural_agent._validate_composition_core ("best
# plan for you", "you should enroll"), which cannot be imported and also rejects
# general teaching ("you can join ..."). The patterns below keep its cases and
# require a coverage choice after them.
_YOU_SHOULD = re.compile(r"\byou(?: should| ought to|'d better| had better|'ll want to| will want to)"
                         r"(?: probably| definitely| really| just| also| still)?\s+", re.I)
_BETTER_OFF = re.compile(r"\byou(?:'re| are|'d be| would be|'ll be| will be)(?: probably| likely| definitely)? better off\b", re.I)
_BEST_IS = re.compile(
    r"\bthe (?:best|right|ideal|perfect|better) (?:plan|option|choice|fit|route|path|match|pick|bet)"
    r"(?: for you| for your (?:situation|needs))? (?:is|would be|will be|looks like|sounds like)\b"
    r"|\byour best (?:bet|option|choice|match|fit|move|plan|pick|route|path) (?:is|would be|will be|looks like|sounds like)\b", re.I)
_IS_BEST = re.compile(
    r"\b(?:is|are|would be|will be|looks like|sounds like|seems like|is probably|is likely|is clearly|is definitely"
    r"|is still|remains)\s+"
    r"(?:(?:the|a|an)\s+(?:right|best|better|ideal|perfect|smartest|safest|wisest|good|great|strong|solid|clear|obvious"
    r"|natural)\s+(?:choice|option|fit|plan|pick|match|bet|route|path|move|one|answer)\s+for\s+you\b"
    r"|your\s+(?:best|safest|smartest|strongest|ideal)\s+(?:choice|option|fit|plan|pick|match|bet|route|path|move|answer)\b"
    r"|(?:the\s+)?(?:right|best|better|ideal|perfect)\s+(?:(?:choice|option|fit|plan|pick|match)\s+)?for\s+you\b"
    r"|the\s+(?:one|plan|option|policy)\s+(?:to\s+(?:get|pick|choose|go with|buy|take)|for you|I'd\s+(?:pick|choose|get|go with))"
    r"|the\s+way\s+to\s+go\b|what\s+I'd\s+(?:pick|choose|get|go with))", re.I)
_NOT_ASSERTED = re.compile(r"\b(?:which|what|whichever|whatever|whether|if|no|not|neither|nor|can't|cannot|don't|won't"
                           r"|isn't|aren't|may|might|could|unless|until)\b", re.I)
_IMPERATIVE = re.compile(
    r"\A(?:(?:honestly|so|then|ok|okay|well|yes|sure|definitely|simply|just|please|my take|bottom line|short answer)[,:]?\s+)*"
    r"(?:go with|pick|choose|stick with|enroll in|sign up for|switch to|stay with|buy|join)\s+", re.I)
_TO_LOOK = re.compile(r"\bif\b|\bto (?:see|compare|view|read|learn|open|start|explore|look)\b", re.I)
_POPULAR = re.compile(
    r"\b(?:many|most|lots of|a lot of|plenty of|the majority of)\s+(?:people|folks|members|retirees|seniors)\b"
    r"[^.?!;]{0,50}?\b(?:picks?|chooses?|go with|goes with|prefers?|enroll in|sign up for|end up with|opt for)\s+", re.I)
_ENROLL_OFFER = re.compile(
    r"\b(?:I|we|me)\b(?P<between>[^.?!;,]{0,40}?)\b(?:enroll|sign|switch|move|put)\s+(?:you|her|him|them)\s+(?:up\s+)?"
    r"(?:in|into|for|to|with|on|onto)\s+", re.I)
_REFUSAL = re.compile(r"\b(?:can't|cannot|won't|will not|don't|do not|not|never|unable)\b", re.I)


def _clause_words(text):
    return _PICK_WORD.findall(_CLAUSE_END.split(text, 1)[0])


def _coverage_subject(before):
    """The words before "... is the right choice for you" name a coverage choice."""
    clause = re.split(r'[,;:\u2013\u2014]', before)[-1]
    if _NOT_ASSERTED.search(clause):
        return False   # "which plan is best for you depends on ..."
    words = _PICK_WORD.findall(clause)
    if not words:
        return False
    length = _pick_verb(words)
    if length:
        return _coverage_choice(words[length:])   # "keeping your employer plan is ..."
    if words[0].casefold().endswith('ing'):
        return False   # "comparing both is your best option"
    index = len(words)
    while index and (words[index - 1].casefold() in _OBJECT_WORDS
                     or (words[index - 1][0].isupper() and words[index - 1].casefold() not in _TIME_WORDS)):
        index -= 1
    trailing = words[index:]
    # A lone first word is capitalised whatever it is: "That is the right choice for you".
    if index == 0 and len(trailing) == 1 and trailing[0].casefold() not in _OBJECT_WORDS:
        return False
    return bool(trailing)


def _personal_pick(text, ground):
    text = _ABBREVIATION.sub(r'\1', PROCESS_SUGGESTION.sub(' ', _plain(text)))
    for sentence in _SENTENCE_END.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue
        for pattern in (FIRST_PERSON_PICK, _EXTRA_PICK):
            for match in pattern.finditer(sentence):
                head = match.group()
                if head.casefold() == 'if i were you':
                    continue   # the choice itself follows in its own clause and is matched there
                tail = re.sub(r'\A\s*:\s*', ' ', sentence[match.end():])   # "My pick: Plan G"
                words = _clause_words(tail)
                if _ADVICE_HEAD.search(head):
                    if _advised_choice(words, bool(re.search(r'(?:should|ought to)\Z', head, re.I))):
                        return True
                elif _coverage_choice(words):
                    return True
        for match in _ENROLL_OFFER.finditer(sentence):
            # "Shall I enroll you in Plan G?" Declining to ("I can't enroll you in a plan") is fine.
            if not _REFUSAL.search(match['between']) and _coverage_choice(_clause_words(sentence[match.end():])):
                return True
        if ground.states(sentence):
            continue   # the instruction is a fact text's or a tool output's own sentence
        for match in _YOU_SHOULD.finditer(sentence):
            words = _clause_words(sentence[match.end():])
            length = _pick_verb(words)
            clause = _CLAUSE_END.split(sentence[match.start():], 1)[0]
            if length and _coverage_choice(words[length:]) and not ground.states(clause):
                return True
        for match in _BETTER_OFF.finditer(sentence):
            if _advised_choice(_clause_words(sentence[match.end():])):
                return True
        for match in _BEST_IS.finditer(sentence):
            if _advised_choice(_clause_words(sentence[match.end():])):
                return True
        if not sentence.endswith('?'):
            for match in _IS_BEST.finditer(sentence):
                if _coverage_subject(sentence[:match.start()]):
                    return True
        match = _IMPERATIVE.match(sentence)
        if match and not _TO_LOOK.search(sentence[match.end():]) \
                and _coverage_choice(_clause_words(sentence[match.end():]), need='capital'):
            return True
        for match in _POPULAR.finditer(sentence):
            if _coverage_choice(_clause_words(sentence[match.end():]), need='name'):
                return True
    return False


# --------------------------------------------------------------------------
# Identifier requests

# identifier_guard.find_identifiers detects identifier values a person typed.
# A request for one contains no value, so it needs its own narrow pattern:
# Daylight asking the person to give a number to Daylight.
_ID = (r"(?:social security (?:number|no\b\.?|#)|\bssn\b|medicare (?:number|no\b\.?|#|id\b(?: number)?|card number"
       r"|claim number|beneficiary (?:id|identifier|number))|\bmbi\b"
       r"|(?:member|policy|subscriber|group|account|claim|id|identification|driver'?s licen[cs]e|licen[cs]e|passport"
       r"|tax(?:payer)?(?: id)?|card|credit card|debit card|bank account|routing) (?:id )?number"
       r"|(?:member|subscriber|policy|tax) id\b"
       r"|last (?:four|4)(?: digits)?(?: of (?:your|the|her|his|their))? (?:social|ssn|medicare))")
_OWNER = r"(?:your|her|his|their|[a-z]+'s)"
_BETWEEN = r"\s+(?:[a-z'-]+\s+){0,3}?"
# "the number on your red, white and blue card", "the eleven characters on your Medicare card"
_ON_CARD = (r"the\s+(?!(?:phone|telephone|customer|contact|help|toll)\b)(?:[a-z0-9-]+\s+){0,2}?(?:numbers?|digits|characters|letters and numbers|code|id)\s+"
            r"(?:on|from|off|printed on|shown on|at the top of)\s+(?:" + _OWNER + r"|the)\s+(?:[a-z-]+,?\s+){0,7}?card\b")
# "your Social" as the end of the request
_SOCIAL = _OWNER + r"\s+social(?=\s*(?:[.?!,;]|\Z|(?:so|when|and|if|to|for|please)\b))"
_WANTED = r"(?:(?:" + _OWNER + r"|the)" + _BETWEEN + _ID + r"|" + _ON_CARD + r"|" + _SOCIAL + r")"
_ID_REQUEST = re.compile(
    r"\bwhat(?:'s| is| are| was)\s+(?:[^.?!]{0,80}?\s)?" + _WANTED
    + r"|(?:\A|[,;]\s*|\band\s+|\bplease\s+|\b(?:can|could|would|will) you\s+(?:please\s+|just\s+)?|\bgo ahead and\s+)"
      r"(?:share|give|tell|send|provide|enter|type|read|confirm|verify|supply|submit|add|text|email|write)"
      r"(?:\s+(?:me|us))?(?:\s+(?:in|out|down|off))?\s+(?:with\s+)?" + _WANTED
    + r"|\b(?:I|we)(?:'ll| will)?(?: just| also| still)? (?:need|require|must have)\s+" + _WANTED
    + r"|\b(?:may|can|could) (?:I|we) (?:have|get|ask for|take)\s+" + _WANTED
    + r"|\bdo you have\s+" + _OWNER + _BETWEEN + _ID + r"\s+(?:handy|available|nearby|ready|with you|in front of you)",
    re.I)
_ID_NEGATED = re.compile(r"\b(?:don't|do not|never|no need|needn't|won't|will not|doesn't|does not|shouldn't|should not"
                         r"|without|avoid|can't|cannot|isn't|aren't|not)\b", re.I)
# The number is to be given to someone else: "... to the agent", "... when you call the plan".
_ID_ELSEWHERE = re.compile(
    r"\A\s*(?:(?:with|to|on|at|into|for)\s+(?:the|your|a|an|their|them|him|her|that|any|social|medicare|ssa)\b"
    r"|when\s+(?:you|they|she|he)\s+(?:call|apply|sign|enroll|contact|visit|talk|speak|go|fill|register|create|log|set"
    r"|check|get|meet|see|use)\b)", re.I)


def _identifier_request(text):
    text = _plain(text)
    for sentence in _SENTENCE_END.split(text):
        sentence = sentence.strip()
        for match in _ID_REQUEST.finditer(sentence):
            lead = re.split(r'[,;:\u2013\u2014]', sentence[:match.start()])[-1]
            if _ID_NEGATED.search(lead + match.group()):
                continue   # "there's no need to, and please don't share your Medicare number"
            if _ID_ELSEWHERE.match(sentence[match.end():]):
                continue   # "enter your Medicare number on the plan's form"
            return True
    return False


# --------------------------------------------------------------------------
# The check

_HELD = {'held_claim_ids': [HELD_MA_DEADLINE]}


def _content_code(text, ground):
    """The first content code that applies to one block's or the question's text, or None."""
    if _identifier_request(text):
        return IDENTIFIER_REQUEST
    if _personal_pick(text, ground):
        return PERSONAL_PICK
    # Advisor-first's own guard, applied whatever knowledge surface is configured.
    if held_deadline_claim(text, _HELD):
        return HELD_CLAIM
    plain = _plain(text)
    if _ungrounded_amount(plain, ground):
        return UNGROUNDED_AMOUNT
    if _ungrounded_date(plain, ground):
        return UNGROUNDED_DATE
    if _ungrounded_name(text, ground):
        return UNGROUNDED_NAME
    if _ungrounded_check_claim(text, ground):
        return UNGROUNDED_CHECK_CLAIM
    return None


def _block_code(block, ground):
    if (not isinstance(block, dict) or not isinstance(block.get('text'), str)
            or not isinstance(block.get('fact_ids', []), (list, tuple))):
        return MALFORMED_BLOCK
    code = _content_code(block['text'], ground)
    if code:
        return code
    if any(not isinstance(item, str) or item not in ground.fact_ids for item in block.get('fact_ids', [])):
        return UNKNOWN_FACT_ID
    return None


def _question_code(question, ground):
    if question is None:
        return None
    if not isinstance(question, dict) or not isinstance(question.get('text'), str):
        return MALFORMED_QUESTION
    # The question is shown like any other text, so it gets every content check.
    code = _content_code(question['text'], ground)
    if code:
        return code
    target = question.get('target')
    if target is not None and (not isinstance(target, str) or target not in ground.open_ids):
        return TARGET_NOT_OPEN
    return None


def check_reply(reply, *, grounding):
    """Check one parsed reply against the visit's grounding. See CONTRACT.md.

    Returns {'ok', 'blocks', 'rejected', 'question', 'question_code'}. A rejected
    block is removed whole and listed once with the first code that applied, in
    the order of BLOCK_CODES. Kept blocks keep their order and their text. The
    question is dropped whole for the first code of QUESTION_CODES that applies.
    """
    ground = _Grounding(grounding)
    reply = reply if isinstance(reply, dict) else {}
    blocks = reply.get('reply_blocks')
    blocks = list(blocks) if isinstance(blocks, (list, tuple)) else []
    kept, rejected = [], []
    for index, block in enumerate(blocks):
        code = _block_code(block, ground)
        if code:
            rejected.append({'index': index, 'code': code})
        else:
            kept.append(block)
    question = reply.get('question')
    question_code = _question_code(question, ground)
    if question_code:
        question = None
    return {'ok': not rejected and question_code is None, 'blocks': kept, 'rejected': rejected,
            'question': question, 'question_code': question_code}
