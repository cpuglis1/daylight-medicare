"""D161 (owner direction, November 12, 2026): Parts A and B as the foundation.

``enrollment_journey.status`` (the enrollment record) derives what is in place
from the person's reports. This module is its front in the conversation: it
reads the person's own words into the registered reports, words the status
line, and builds the cards and the dashboard summary software shows.

Code computes every date and status; the model explains. Nothing here calls a
model or asks for or stores a Social Security number, Medicare number or
password. Nothing says an application was sent, approved or in effect unless
the person reported it, and a reported fact is labelled as reported. Wording
lives in ``enrollment-content.json``; a sentence marked ``new`` there awaits
the owner's sign-off and is served only where this module is enabled (:8895).
"""
from datetime import date, timedelta
from functools import lru_cache
import json
import logging
from pathlib import Path
import copy
import re

import enrollment_journey
import recommendation_engine
import ux_pass

LOGGER = logging.getLogger(__name__)
PATH_FIELD = 'intent.coveragePath'
COMPONENT_FIELD = 'intent.components'
PART_FIELDS = {'A': 'enrollment.partA', 'B': 'enrollment.partB'}
# November 13, 2026 (approved design): where the person is with Social Security, which path they
# asked to start with, and which path they named first. All three are the person's own taps or words.
CONTACT_FIELD = 'enrollment.contact'
START_FIELD = 'intent.pathStart'
ASKED_FIELD = 'intent.pathAsked'
HAVE_FIELD = 'coverage.reported'   # what the person says they already have, e.g. {'medigap_letter': 'G'}
FIRST_ELIGIBLE_FIELD = 'enrollment.firstEligible'
FIELDS = (*PART_FIELDS.values(), COMPONENT_FIELD, CONTACT_FIELD, START_FIELD, ASKED_FIELD, HAVE_FIELD,
          FIRST_ELIGIBLE_FIELD)
STARTS = ('original_medigap', 'medicare_advantage', 'both')
PATHS = ('original_only', 'original_medigap', 'medicare_advantage', 'keep_current', 'wait')
COMPONENTS = ('medigap', 'part_d')
DECISIONS = ('chosen', 'not_needed', 'keep_existing', 'decide_later')
STATUSES = ('applied', 'approved', 'active', 'needs_info', 'denied')
SSA_PHONE = '1-800-772-1213'
CONTENT = Path(__file__).resolve().parent / 'enrollment-content.json'


def enable(flow):
    """Register the three additive report fields and turn the journey on.

    Called for the unified local demo only. The pinned contract file is not
    edited; the fields join node R00's writes exactly as D157's path did.
    """
    node = next(node for node in flow.contract['nodes'] if node['id'] == 'R00')
    node['writes'] = [*node['writes'], *[field for field in FIELDS if field not in node['writes']]]
    flow.d161 = True


def enabled(flow):
    return bool(getattr(flow, 'd161', False))


@lru_cache(maxsize=1)
def content():
    return json.loads(CONTENT.read_text(encoding='utf-8'))


def statement(identifier):
    return content()['statements'][identifier]['text']


def sources(*keys):
    listed, seen = [], set()
    for key in keys:
        source = content()['sources'].get(key)
        if source and source['url'] not in seen:
            seen.add(source['url'])
            listed.append(dict(source))
    return listed


def _statement_sources(*identifiers):
    return sources(*[key for identifier in identifiers for key in content()['statements'][identifier]['sources']])


def _long(iso):
    return ux_pass._long(date.fromisoformat(iso))


# ---------------------------------------------------------------------------
# The person's own words -> reports (build item 4). Sentence by sentence;
# questions, negations and plans ("I need to sign up") are never a report.
# ---------------------------------------------------------------------------

_NEGATED = re.compile(r"(?i)\b(?:no|neither|not|never|haven'?t|hasn'?t|didn'?t|don'?t|doesn'?t|won'?t|can'?t|cannot)\b")
_UNREAL = re.compile(r"(?i)^\s*(?:if|once|after|before|until|should|could|can|do|does|did|how|what|where|why|who|which|is|are|will)\b"
                     r"|\b(?:tell me|show me|help me|to get)\b"
                     r"|\b(?:want(?:ed)? to|need(?:ed)? to|going to|plan(?:ning)? to|have to|has to|supposed to|trying to|about to|"
                     r"how (?:do|to|can|would)|should i|can i|do i|thinking (?:of|about))\b")
_OTHER_PRODUCT = re.compile(r"(?i)\b(?:advantage|medigap|supplement|part d\b|drug plan|plan [a-n]\b|hmo|ppo|cobra|job|employer)\b")
# "I just called and finished my application" (owner's test conversation, November 13, 2026).
_APPLIED = re.compile(r"(?i)\b(?:i|we|he|she|they)(?:'ve| have| has)? (?:just |already |finally |also )?"
                      r"(?:(?:called|phoned|went)(?: \w+){0,3} and )?"
                      r"(?:applied|signed up|filed|(?:sent|submitted|mailed|faxed|turned|finished|completed|did|put|filled)(?: in| off| out)? "
                      r"(?:my|the|his|her|our|their) (?:application|forms?|paperwork))\b")
_APPLIED_ELSEWHERE = re.compile(r"(?i)\b(?:applied|signed up) (?:for|to|with) (?:a |an |the |my )?"
                                r"(?!medicare\b|part\b|parts\b|social security|it\b|both\b|a and b\b|them\b|that\b|this\b)\w+")
_HAVE = re.compile(r"(?i)\b(?:i|we|he|she)(?:'ve)? (?:now |already |finally )?(?:have|has|got|received)\b[^.!?]*\bparts? [ab]\b"
                   r"|\bparts? [ab]\b[^.!?]*\b(?:is|are|has been|have been) (?:now |already )?(?:active|in effect|in place|in force)\b")
_NEEDS_INFO = re.compile(r"(?i)\b(?:they|social security|ssa|the office)\b[^.!?]*\b(?:need|needs|needed|asked|asking|want|wants|wanted|requested|requesting|sent)\b"
                         r"[^.!?]*\b(?:information|info|documents?|documentation|proof|paperwork|forms?|evidence|letter)\b")
_DENIED = re.compile(r"(?i)\b(?:denied|rejected|turned (?:me |us |him |her )?down)\b")
_APPROVED = re.compile(r"(?i)\b(?:approved|accepted|went through)\b")
_STARTS = re.compile(r"(?i)\b(?:parts? [ab]|medicare|coverage)\b[^.!?]*\b(?:starts?|begins?|is effective|will start|will begin|kicks in|takes effect)\b")
_STARTED = re.compile(r"(?i)\b(?:parts? [ab]|medicare|coverage)\b[^.!?]*\b(?:started|began|took effect|kicked in|has been active since|active since)\b")
_ABOUT_MEDICARE = re.compile(r"(?i)\bmedicare\b|\bparts? [ab]\b|\bsocial security\b|\bssa\b|\bapplication\b")
_PLAN_PRODUCT = re.compile(r"(?i)\badvantage\b|\bmedigap\b|\bsupplement\b|\bdrug plan\b|\bpart d\b")

_MONTHS = {name[:3].lower(): index + 1 for index, name in enumerate(ux_pass.MONTH_NAMES)}
_MONTH = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_DATE_WORDS = re.compile(r"(?i)\b%s\b\.?(?: (?:the )?(\d{1,2})(?:st|nd|rd|th)?\b)?(?:,? (20\d{2})\b)?" % _MONTH)
_DATE_OF = re.compile(r"(?i)\b(?:the )?(\d{1,2})(?:st|nd|rd|th)? of %s\b(?:,? (20\d{2}))?" % _MONTH)
_DATE_SLASH = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2}|\d{4}))?\b")


def _resolve(month, day, year, today, tense):
    """A full date from the person's words. ``tense`` picks the year when it
    was not said: a start still to come is the next such date, one already
    under way the most recent, otherwise the nearest."""
    try:
        if year:
            return date(year, month, day)
        options = [date(today.year + shift, month, day) for shift in (-1, 0, 1)]
    except ValueError:
        return None
    if tense == 'future':
        # "Part B starts November 1", said on November 12, means the one just past.
        recent = today - timedelta(days=92)
        options = [item for item in options if item >= recent] or options[-1:]
        return options[0]
    if tense == 'past':
        options = [item for item in options if item <= today] or options[:1]
        return options[-1]
    return min(options, key=lambda item: abs((item - today).days))


def said_date(text, today, tense=None, month_only=False):
    """One date in the person's sentence, or None. A month with no day is a
    date only where coverage is concerned: coverage starts on the first."""
    found = _DATE_OF.search(text)
    if found:
        return _resolve(_MONTHS[found.group(2)[:3].lower()], int(found.group(1)),
                        int(found.group(3)) if found.group(3) else None, today, tense)
    for found in _DATE_WORDS.finditer(text):
        if not (found.group(2) or month_only):
            continue
        # "May" is also a verb; without a day it must follow a preposition or carry a year.
        if (not found.group(2) and found.group(1).lower() == 'may' and not found.group(3)
                and not re.search(r"(?i)\b(?:in|on|of|since|from) may\b", text)):
            continue
        return _resolve(_MONTHS[found.group(1)[:3].lower()], int(found.group(2) or 1),
                        int(found.group(3)) if found.group(3) else None, today, tense)
    found = _DATE_SLASH.search(text)
    if found:
        year = int(found.group(3)) if found.group(3) else None
        return _resolve(int(found.group(1)), int(found.group(2)), year + 2000 if year and year < 100 else year, today, tense)
    if re.search(r"(?i)\btoday\b|\bthis morning\b|\bjust now\b", text):
        return today
    if re.search(r"(?i)\byesterday\b", text):
        return today - timedelta(days=1)
    return None


def _parts_in(text):
    parts = []
    lowered = text.casefold()
    both = re.search(r"\bboth parts\b|\bparts? a[^.!?]{0,12}\bboth\b|\ba (?:and|&|\+) (?:part )?b\b|\ba, b\b", lowered) or (
        re.search(r"\bboth\b", lowered) and re.search(r"\bparts?\b", lowered))
    if both or re.search(r"\bparts? a\b", lowered):
        parts.append('A')
    if both or re.search(r"\bpart b\b", lowered):
        parts.append('B')
    return parts


def _targets(journey, mentioned, *preferred):
    if mentioned:
        return mentioned
    for states in preferred:
        chosen = [part for part in ('A', 'B') if journey['parts'][part]['state'] in states]
        if chosen:
            return chosen
    return ['A', 'B']


def _speaker(found, sentence, role):
    """Reports are about the beneficiary. "She applied" is not a report about
    someone asking for themselves, and a helper's "I applied" is about the
    helper unless they say who it was for."""
    subject = found.group(0).split()[0].casefold().split("'")[0]
    if subject in ('he', 'she', 'they'):
        return role != 'self'
    if subject in ('i', 'we'):
        return role != 'someone' or bool(re.search(r"(?i)\bfor (?:him|her|them|my \w+)\b", sentence))
    return True


def _units(text, today):
    """Sentences; "Part A starts November 1 and Part B starts December 1" is
    read as two reports, each with its own part and date."""
    units = []
    for sentence in ux_pass.sentences(text):
        if sentence.rstrip().endswith('?'):
            units.append(sentence)
            continue
        clauses = [clause for clause in re.split(r",|;|\band\b(?! (?:part )?b\b)", sentence) if clause.strip()]
        dated = [clause for clause in clauses if re.search(r"(?i)\bparts? [ab]\b", clause)
                 and said_date(clause, today, None, month_only=True)]
        units.extend(clauses if len(dated) > 1 else [sentence])
    return units


# What a person already has, in the ways people say it (15-profile run, November 13, 2026):
# "A and B since July 2017", "I've had Parts A and B since February 2025", "Original Medicare
# since 2020, Plan G", "A and B start January 1". Sentence patterns built around one test
# conversation read 2 of 15 of these.
_WHOLE = re.compile(r"(?i)\boriginal medicare\b|\b(?:regular|traditional) medicare\b")
_BARE_MEDICARE = re.compile(r"(?i)\bmedicare\b(?! advantage| supplement| number| card| savings| part [cd]\b)")
# A mention of the parts, then how the sentence ties a time or possession to it. "Since" counts only
# before a date ("since it covers any doctor" is a reason), and a verb counts only next to the
# mention ("I started looking at Original Medicare" and "I have a question about Part B" say nothing).
_M = r"(?:parts? a\b|part b\b|a (?:and|&|\+) (?:part )?b\b|a, b\b|both parts\b|original medicare\b|(?:regular|traditional) medicare\b|medicare\b)"
_DATEISH = (r"(?:(?:19|20)\d{2}|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|last|then|\d{1,2}[/ ]|i turned|he turned|"
            r"she turned|i was|he was|she was|the (?:first|1st|start|beginning))")
_PAST_TENSE = re.compile(r"(?i)\b%s[^.!?]*?\b(?:started|began|took effect|kicked in|since (?:\w+ ){0,2}?%s)"
                         r"|\b(?:(?:i|we|he|she)(?:'ve| have| has|'s) had|i have|we have|he has|she has|i've got|i'm on|i am on|"
                         r"he's on|she's on|been on|(?:my|our) (?:mom|mother|dad|father|husband|wife|parent|aunt|uncle|"
                         r"grandmother|grandfather|brother|sister|partner) has(?: had)?) "
                         r"(?:had |both |my |our |his |her |now |already |only |just )*%s"
                         % (_M, _DATEISH, _M))
_FUTURE_TENSE = re.compile(r"(?i)\b%s[^.!?]*?\b(?:starts?|begins?|will start|will begin|kicks? in|takes? effect|is effective|are effective)\b" % _M)
_NEITHER = re.compile(r"(?i)^\s*no (?:part )?a\b[, ]*(?:and |or |nor )?no (?:part )?b\b|\bneither part\b|"
                      r"\b(?:don'?t|do not|doesn'?t|does not) have (?:either part|(?:part )?a (?:or|nor|and) (?:part )?b\b|parts? a (?:or|and) b\b)")
_ONLY_PART = re.compile(r"(?i)\b(?:only|just)\b[^.!?]{0,40}\b(?:have|has|had|got|took|signed up for|enrolled in)\b[^.!?]{0,20}\bpart ([ab])\b"
                        r"|\b(?:have|has|had|got|took|signed up for|enrolled in)\b[^.!?]{0,20}\b(?:only|just) part ([ab])\b"
                        r"|\bpart ([ab]) only\b")
_YEAR_ONLY = re.compile(r"(?i)\b(?:since|in|from|started in|began in|started|began) ((?:19|20)\d{2})\b")


def _coverage_report(sentence, mentioned, today, role=None):
    """{part: report} when the sentence says which parts are in place or starting, else {}."""
    if _UNREAL.search(sentence) or re.search(r"(?i)\b(?:i|we) (?:heard|read)\b|\b(?:they|people) say\b", sentence):
        return {}
    if role == 'self' and re.search(r"(?i)\b(?:my|our) (?:mom|mother|dad|father|husband|wife|parent|aunt|uncle|grandmother|"
                                    r"grandfather|brother|sister|partner|friend|neighbor) (?:has|had|is|was)\b", sentence):
        return {}
    only = _ONLY_PART.search(sentence)
    if only and not _NEGATED.search(sentence) and len(mentioned) == 1:
        # "I only ever signed up for Part A" (live run of profile PP03).
        return {mentioned[0]: {'status': 'active', 'date': None, 'date_kind': 'start', 'only': True}}
    past, future = _PAST_TENSE.search(sentence), _FUTURE_TENSE.search(sentence)
    if not (past or future):
        return {}
    parts = list(mentioned)
    bare = False
    if not parts and _WHOLE.search(sentence):
        parts = ['A', 'B']
    elif not parts and _BARE_MEDICARE.search(sentence) and not _PLAN_PRODUCT.search(sentence):
        parts, bare = ['A', 'B'], True
    if not parts:
        return {}
    if _NEGATED.search(sentence):
        # "Part A since 2015 but never took Part B": only a part whose own clause is not negated.
        clauses = re.split(r"(?i),|;|\bbut\b|\band\b(?! (?:part )?b\b)", sentence)
        kept = []
        for part in parts:
            own = [clause for clause in clauses if re.search(r"(?i)\bparts? %s\b|\ba (?:and|&) b\b|\bboth\b|\boriginal medicare\b" % part.lower(), clause)]
            if own and not any(_NEGATED.search(clause) for clause in own):
                kept.append(part)
        parts = kept
        if not parts:
            return {}
    year = _YEAR_ONLY.search(sentence)
    if year and not today.year - 40 <= int(year.group(1)) <= today.year + 1:
        year = None
    if bare and not year and not said_date(sentence, today, None, month_only=True):
        return {}   # "Medicare started sending me mail" says nothing about the parts
    if future and not past:
        when = said_date(sentence, today, 'future', month_only=True)
        if not when:
            return {}
        return {part: {'status': 'approved' if when > today else 'active', 'date': when.isoformat(), 'date_kind': 'start'}
                for part in parts}
    when = None if year and not _DATE_WORDS.search(sentence.replace(year.group(0), '')) and not _DATE_SLASH.search(sentence) \
        else said_date(sentence, today, 'past', month_only=True)
    if when and when > today:
        when = None
    report = {'status': 'active', 'date': when.isoformat() if when else None, 'date_kind': 'start'}
    if not when and year and int(year.group(1)) <= today.year:
        report['since'] = year.group(1)
    return {part: dict(report) for part in parts}


_HAS_PLAN = re.compile(r"(?i)\b(?:since|started|paying|pays?|holder|keep|keeping|(?:i|we|he|she)(?:'ve| have| has|'s)? had|i have|we have|"
                       r"he has|she has|i've got|i'm on|he's on|she's on|my|his|her)\b")
_WANTS = re.compile(r"(?i)\b(?:want|wants|buy|get|add|switch|looking|shopping|thinking|considering|cost|costs|price|prices|"
                    r"how much|difference|compare|versus|vs|should|could|would|recommend|says?|said|heard|read)\b")


def held_from_text(text):
    """The Medigap plan letter the person says they hold: {'medigap_letter': 'G'} or {}."""
    for sentence in ux_pass.sentences((text or '').replace('’', "'")):
        plain = sentence.strip()
        if not plain or plain.endswith('?') or _UNREAL.search(plain) or _WANTS.search(plain):
            continue
        for clause in re.split(r";|\bbut\b", plain):
            letter = re.search(r"(?i)\bplan ([a-dfgk-n])\b", clause)
            if not letter or re.search(r"(?i)\b(?:not|never|no|don't|doesn't|didn't)\b[^,]*\bplan %s\b" % letter.group(1), clause):
                continue
            inventory = _WHOLE.search(plain) or _parts_in(plain) or re.search(r"(?i)\b(?:drug|prescription) plan\b", plain)
            if _HAS_PLAN.search(clause) or inventory:
                return {'medigap_letter': letter.group(1).upper()}
    return {}


def reports_from_text(text, journey, today, role=None):
    """Enrollment reports in the person's own words: {part: report}."""
    found = {}
    for sentence in _units((text or '').replace('’', "'"), today):
        if sentence.rstrip().endswith('?'):
            continue
        explicit = explicit_parts(sentence, role)
        if explicit:
            found.update(explicit)
            continue
        mentioned = _parts_in(sentence)
        about = bool(mentioned or _ABOUT_MEDICARE.search(sentence))
        starts, started = _STARTS.search(sentence), _STARTED.search(sentence)
        if (starts or started) and not _NEGATED.search(sentence) and not _UNREAL.search(sentence):
            when = said_date(sentence, today, 'past' if started else 'future', month_only=True)
            medicare = mentioned or (re.search(r"(?i)\bmedicare\b", sentence) and not _PLAN_PRODUCT.search(sentence))
            if when and medicare:
                for part in mentioned or ['A', 'B']:
                    found[part] = {'status': 'approved' if when > today else 'active',
                                   'date': when.isoformat(), 'date_kind': 'start'}
                continue
        had = _coverage_report(sentence, mentioned, today, role)
        if had:
            found.update(had)
            continue
        waiting = any(journey['parts'][part]['state'] in ('pending', 'needs_info') for part in ('A', 'B'))
        open_part = any(journey['parts'][part]['state'] != 'active' for part in ('A', 'B'))
        if (_NEEDS_INFO.search(sentence) and (about or waiting or open_part and not _OTHER_PRODUCT.search(sentence))
                and not _UNREAL.search(sentence)):
            for part in _targets(journey, mentioned, ('pending', 'needs_info'), ('needed', 'unknown')):
                found[part] = {'status': 'needs_info', 'date': None, 'date_kind': 'application'}
            continue
        if _NEGATED.search(sentence) or _UNREAL.search(sentence):
            continue
        if _DENIED.search(sentence) and about:
            for part in _targets(journey, mentioned, ('pending', 'needs_info'), ('needed', 'unknown')):
                found[part] = {'status': 'denied', 'date': None, 'date_kind': 'application'}
        elif _APPROVED.search(sentence) and about and not _OTHER_PRODUCT.search(sentence):
            when = said_date(sentence, today, None, month_only=True)
            for part in _targets(journey, mentioned, ('pending', 'needs_info'), ('needed', 'unknown')):
                found[part] = {'status': 'approved', 'date': when.isoformat() if when else None,
                               'date_kind': 'start' if when else 'application'}
        elif (_APPLIED.search(sentence) and _speaker(_APPLIED.search(sentence), sentence, role)
              and not _APPLIED_ELSEWHERE.search(sentence) and not (_OTHER_PRODUCT.search(sentence) and not mentioned)):
            when = said_date(sentence, today, 'past')
            for part in _targets(journey, mentioned, ('needed', 'unknown')):
                found[part] = {'status': 'applied', 'date': when.isoformat() if when else None,
                               'date_kind': 'application'}
        elif (_HAVE.search(sentence) and mentioned and _speaker(_HAVE.search(sentence), sentence, role)
              and not re.search(r"(?i)\b(?:questions?|about|problem|bill|letter|mail|ad)\b", sentence)):
            for part in mentioned:
                found[part] = {'status': 'active', 'date': None, 'date_kind': 'start'}
    return found


def explicit_parts(text, role=None):
    """Unambiguous negative/only reports outrank possession and model inference.

    No eligibility inference: denying B alone does not assert A. Quoted UI
    status and another person's coverage are not beneficiary reports.
    """
    found = {}
    for sentence in re.split(r'(?<=[.!?])\s+|;', (text or '').replace('’', "'")):
        if ('?' in sentence or _UNREAL.search(sentence) or re.search(
                r"(?i)\b(?:says?|said|think|maybe|might|if|suppose)\b", sentence)):
            continue
        other = re.search(r"(?i)\b(?:my|our) (?:mother|father|mom|dad|wife|husband|friend|neighbor)\b", sentence)
        if role == 'self' and other or role == 'someone' and not other and re.search(r"(?i)\bI\b", sentence):
            continue
        statuses = {}
        if re.search(r"(?i)\bneither(?: (?:part )?a (?:nor|or) (?:part )?b| part| yet)\b|\bno (?:part )?a\b[, ]*(?:and )?no (?:part )?b\b", sentence) or _NEITHER.search(sentence):
            statuses = {'A': 'not_enrolled', 'B': 'not_enrolled'}
        else:
            only = _ONLY_PART.search(sentence)
            if only:
                part = next(v for v in only.groups() if v).upper()
                statuses = {part: 'active', 'B' if part == 'A' else 'A': 'not_enrolled'}
            for part in ('A', 'B'):
                if re.search(r"(?i)\b(?:no|without|not enrolled in|do not have|don't have|haven't (?:started|added)|never (?:started|had|took)) (?:part )?%s\b" % part, sentence):
                    statuses[part] = 'not_enrolled'
        for part, status in statuses.items():
            found[part] = {'status': status, 'date': None, 'date_kind': 'start', 'basis': 'explicit'}
    return found


def part_conflicts(text, role=None):
    """Contradictory current reports need clarification, not last-clause wins."""
    if re.search(r'\b(?:actually|correction|to correct|I meant|instead)\b', text, re.I):
        return []
    values = {'A': set(), 'B': set()}
    for clause in re.split(r'(?<=[.!?])\s+|;|\bbut\b', text, flags=re.I):
        if '?' in clause: continue
        reports = explicit_parts(clause, role) or _coverage_report(clause, _parts_in(clause), _today(), role)
        for part, report in reports.items():
            if report['status'] in ('active', 'not_enrolled'):
                values[part].add(report['status'])
    return [part for part, statuses in values.items() if len(statuses) > 1]


_MEDIGAP = r"(?:medigap|medicare supplement|supplement(?:al)?(?: (?:plan|policy|insurance|coverage))?)"
_PART_D = r"(?:part d|(?:drug|prescription|rx) (?:plan|coverage|insurance))"
_INTENT = re.compile(r"(?i)\b(?:i|we)(?:'ll| will| would|'d|'m| am)? (?:just |only |like |rather |going to |gonna )*"
                     r"(?:want|take|need|do|have|get|keep|stay|stick|go|choose|pick|prefer|decided)\b")
_AB_ONLY = re.compile(r"(?i)\b(?:just|only)\b[^.!?]*\b(?:parts? a (?:and|&|\+) (?:part )?b|original medicare)\b"
                      r"|\b(?:parts? a (?:and|&|\+) (?:part )?b|original medicare)\b[^.!?]*\b(?:only|alone|by itself|nothing else|and that'?s (?:it|all))\s*[.!]?\s*$"
                      r"|\bno (?:supplement|medigap)\b[^.!?]*\b(?:and|or) no (?:drug plan|part d)\b")
_KEEP = re.compile(r"(?i)\b(?:keep|keeping|stay(?:ing)? (?:on|with)|stick(?:ing)? with|remain(?:ing)? on)\b[^.!?]*"
                   r"\b(?:what i have|what we have|my (?:current |existing |employer |retiree |cobra |job |work |union |va |tricare )?"
                   r"(?:coverage|insurance|plan|benefits))\b")
_WAIT = re.compile(r"(?i)\b(?:i(?:'ll| will)|i(?:'m| am) going to|i(?:'d| would) rather|i want to|let me|we(?:'ll| will))\s+"
                   r"(?:just )?(?:wait|hold off|put (?:it|this|that) off|delay)\b|\bnot ready to (?:sign up|enroll|apply)\b")
_WAITING_ON = re.compile(r"(?i)\bwait(?:ing)? (?:for|on) (?!now\b)|\bwait(?:ing)? (?:to hear|until i hear)\b")


def _component(sentence, product):
    """This sentence's decision about one optional piece, or None."""
    if not re.search(r"(?i)\b%s\b" % product, sentence):
        return None
    # "No supplement or drug plan yet" is where someone stands, not a decision against one, and
    # "so I drop the drug plan and pick one up later if I need pills" is a say-back to be checked
    # (live runs of profiles PP11 and PP08, November 13, 2026).
    if re.search(r"(?i)\b(?:yet|so far|right now|at the moment|for now i have)\b", sentence) and not re.search(
            r"(?i)\b(?:don'?t|do not|won'?t) (?:need|want)\b", sentence):
        return None
    if re.match(r"(?i)\s*(?:ok(?:ay)?[,.]?\s+)?so\b", sentence) or re.search(r"(?i)\bif\b", sentence):
        return None
    if re.search(r"(?i)\b(?:decide|think about|look at|come back to|figure out|deal with)\b[^.!?]*\blater\b|\b%s\b[^.!?]*\blater\b" % product, sentence):
        return 'decide_later'
    if re.search(r"(?i)\b(?:don'?t|do not|won'?t|will not|wouldn'?t) (?:need|want|plan on|think i need|get|buy|take)\b[^.!?]*\b%s\b"
                 r"|\b(?:skip|skipping|pass on|passing on)\b (?:a |an |the |any )?%s\b"
                 r"|\bno %s\b[^.!?]{0,12}\b(?:for me|for us|thanks|thank you|needed)\b"
                 r"|\b%s\b[^.!?]*\b(?:not needed|isn'?t needed|not for me)\b" % (product, product, product, product), sentence):
        return 'not_needed'
    if _NEGATED.search(sentence):
        return None
    # "I have the letter saying my drug coverage counted" is about coverage that ended, not a decision to
    # keep it (live run of profile PP03, November 13, 2026). "Have" must take the product as its own object.
    past = re.search(r"(?i)\b(?:letter|notice|ended|ending|ends|counted|creditable|used to|had|lost|losing)\b", sentence)
    if re.search(r"(?i)\b(?:keep|keeping|stay(?:ing)? with|stick(?:ing)? with)\b[^.!?]*\b%s\b" % product, sentence) or (
            not past and re.search(r"(?i)\b(?:already have|already has|i have|i've got|we have)\b"
                                   r"(?: (?:a|an|my|our|the|some|good|other|separate))?(?: \w+){0,2}? %s\b" % product, sentence)):
        return 'keep_existing'
    if re.search(r"(?i)\b(?:i(?:'ll| will)? (?:take|go with|get|buy|choose|pick|add)|i (?:want|chose|picked|decided on)|sign me up for|let'?s (?:go with|do|add))\b"
                 r"[^.!?]*\b%s\b" % product, sentence):
        return 'chosen'
    return None


def choices_from_text(text):
    """An explicit finish or component decision in the person's own words:
    {'path': ..., 'components': {...}}; ``path`` may be absent."""
    found = {'components': {}}
    for sentence in ux_pass.sentences((text or '').replace('’', "'")):
        plain = sentence.strip()
        if not plain or plain.rstrip().endswith('?'):
            continue
        chosen = bool(_INTENT.search(plain) or ux_pass._CHOOSE.search(plain) or len(plain.split()) <= 7)
        if _AB_ONLY.search(plain) and chosen and not re.search(r"(?i)\b(?:don'?t|do not|not) (?:want|just|only)\b", plain):
            found['path'] = 'original_only'
            found['components'] = {'medigap': 'not_needed', 'part_d': 'not_needed'}
            continue
        if _KEEP.search(plain) and not _NEGATED.search(plain) and not re.match(r"(?i)\s*(?:if|should|could|can|do|does|what|how)\b", plain):
            # "keep my Medigap" or "keep my drug plan" is one piece, not the whole plan.
            if not re.search(r"(?i)\b%s\b|\b%s\b" % (_MEDIGAP, _PART_D), plain):
                found['path'] = 'keep_current'
                continue
        if _WAIT.search(plain) and not _WAITING_ON.search(plain):
            found['path'] = 'wait'
            continue
        for name, product in (('medigap', _MEDIGAP), ('part_d', _PART_D)):
            decision = _component(plain, product)
            if decision:
                found['components'][name] = decision
        # "I'm keeping the Plan G" (live run of profile PP07, November 13, 2026).
        if ('medigap' not in found['components'] and not _NEGATED.search(plain)
                and re.search(r"(?i)\b(?:keep|keeping|stay(?:ing)? with|stick(?:ing)? with)\b[^.!?]*\bplan [a-dfgk-n]\b", plain)):
            found['components']['medigap'] = 'keep_existing'
    return found


def journey(flow, g, r, today=None):
    if getattr(flow, 'd166', False):
        from conversation_planner import decision_guide
        g = decision_guide(flow, g)
    return enrollment_journey.status(flow, g, r, today=today)


def _today():
    import ux_flow
    return ux_flow.today()


def _put_components(flow, g, changes, source):
    if getattr(flow, 'd166', False):
        from conversation_planner import decision_guide
        current = flow.value(decision_guide(flow, g), COMPONENT_FIELD)
    else:
        current = flow.value(g, COMPONENT_FIELD)
    merged = {**(current if isinstance(current, dict) else {}), **changes}
    merged = {name: merged[name] for name in COMPONENTS if merged.get(name) in DECISIONS}
    if merged and merged != current:
        flow.put(g, COMPONENT_FIELD, merged, source)
        return True
    return False


_YEAR_END = r"(?:end of (?:the |this )?year|eoy|year[- ]?end)"


def note_retirement(flow, g, message, today):
    """"Retiring at the end of the year" is kept as the month it means, resolved once, when it
    is said (record v2 reads it as the reported end of job coverage). Only for a retirement the
    existing capture already accepted as this person's own; a month they gave is never replaced."""
    current = flow.value(g, 'situation.retirement')
    if not isinstance(current, dict) or current.get('status') != 'retiring':
        return False
    when = (current.get('when') or '').strip()
    said = re.search(r"(?i)\bretir(?:e|ing|ement)\b[^.!?;]*\b" + _YEAR_END + r"\b", message or '')
    if re.fullmatch(r"(?i)(?:at |by |in |on )?(?:the )?" + _YEAR_END, when) or (not when and said):
        flow.put(g, 'situation.retirement', {'status': 'retiring', 'when': 'December %d' % today.year}, 'user_text')
        return True
    return False


def capture(flow, g, r, message):
    """Write what the person just reported. Returns the changed field names."""
    changed = []
    today = _today()
    semantic = getattr(flow, 'records_v1', False)
    if note_retirement(flow, g, '' if semantic else message, today):
        # D183: on :8895 only the interpreter's accepted "when" is normalized.
        changed.append('situation.retirement')
    if semantic:
        # D183 (fix a): Medicare status, plans already held, first eligibility and
        # the birth month come from the interpreter's quote-grounded proposals
        # (conversation_records.apply_coverage_reports, RC16 updates). No
        # sentence patterns decide profile facts on :8895. Derived both-parts
        # status from a held Advantage or Medigap plan stays (not words).
        held = set(flow.value(g, 'coverage.current') or [])
        basis = 'advantage' if 'advantage' in held else 'medigap' if 'medigap' in held else None
        if basis and flow.report(r, 'RC04').get('choice') in (None, '', 'both'):
            for part, field in PART_FIELDS.items():
                if flow.value(g, field) is None:
                    flow.put(g, field, {'status': 'active', 'date': None, 'date_kind': 'start', 'basis': basis}, 'user_text')
                    changed.append(field)
        return changed
    if flow.value(g, 'subject.role') == 'self':
        for sentence in re.split(r'[;\n]|(?<=[.!?])\s+', message):
            if '?' in sentence or _NEGATED.search(sentence) or _UNREAL.search(sentence):
                continue
            if re.search(r'(?i)\bI (?:first qualified|first became eligible) for Medicare\b', sentence):
                when = said_date(sentence, today, tense='past', month_only=True)
                if when and re.search(r'\b(?:19|20)\d{2}\b', sentence):
                    value = when.isoformat()[:7]
                    if value != flow.value(g, FIRST_ELIGIBLE_FIELD) and when <= today:
                        flow.put(g, FIRST_ELIGIBLE_FIELD, value, 'user_text')
                        changed.append(FIRST_ELIGIBLE_FIELD)
            if re.search(r'(?i)\bI (?:joined|started) my first Medicare Advantage plan\b', sentence):
                when = said_date(sentence, today, tense='past', month_only=True)
                if when and re.search(r'\b20\d{2}\b', sentence) and when <= today:
                    prior = flow.report(r, 'RC16')
                    value = {**prior, 'choice': 'yes', 'start': when.isoformat()[:7]}
                    if value != prior:
                        flow.fact(r, 'RC16', value, 'user_text')
                        changed.append('RC16')
    record = journey(flow, g, r, today)
    reports = reports_from_text(message, record, today, flow.value(g, 'subject.role'))
    conflicts = part_conflicts(message, flow.value(g, 'subject.role'))
    for part in conflicts:
        reports[part] = {'status': 'conflicting', 'date': None, 'date_kind': 'start'}
    for part, report in reports.items():
        if report.get('date') and report.get('date_kind') == 'start' and not said_date(message, today, month_only=False):
            # Normalized first-of-month is an internal calculation input, not
            # a day the person supplied. Carry precision to every display.
            report['precision'] = 'month'
        previous = flow.value(g, PART_FIELDS[part])
        if isinstance(previous, dict) and report['date'] is None and previous.get('status') == report['status']:
            continue   # the same report without its date never erases the date
        if previous != report:
            flow.put(g, PART_FIELDS[part], report, 'user_text')
            changed.append(PART_FIELDS[part])
    explicit = explicit_parts(message, flow.value(g, 'subject.role'))
    if explicit:
        statuses = {part: (explicit.get(part) or flow.value(g, field) or {}).get('status')
                    for part, field in PART_FIELDS.items()}
        choice = ({('active', 'not_enrolled'): 'a_only', ('not_enrolled', 'active'): 'b_only',
                   ('not_enrolled', 'not_enrolled'): 'neither'}.get((statuses['A'], statuses['B'])))
        flow.fact(r, 'RC04', {'choice': 'unknown' if conflicts else choice or 'unknown'}, 'confirmed_agent_interpretation')
    # A Medicare Advantage plan or a Medigap policy means both parts are in place. Derived,
    # labeled as such, and never over a report the person gave about the parts themselves.
    held = set(flow.value(g, 'coverage.current') or [])
    basis = 'advantage' if 'advantage' in held else 'medigap' if 'medigap' in held else None
    if basis and flow.report(r, 'RC04').get('choice') in (None, '', 'both'):
        for part, field in PART_FIELDS.items():
            if flow.value(g, field) is None:
                flow.put(g, field, {'status': 'active', 'date': None, 'date_kind': 'start', 'basis': basis}, 'user_text')
                changed.append(field)
    letter = held_from_text(message)
    if letter:
        known = flow.value(g, HAVE_FIELD)
        merged = {**(known if isinstance(known, dict) else {}), **letter}
        if merged != known:
            flow.put(g, HAVE_FIELD, merged, 'user_text')
            changed.append(HAVE_FIELD)
    # D166 owns explicit decisions separately from coverage reports and topics.
    # The older text heuristic treats curiosity and current coverage as choices.
    if getattr(flow, 'd166', False):
        return changed
    choices = choices_from_text(message)
    if choices.get('path') and flow.value(g, PATH_FIELD) != choices['path']:
        flow.put(g, PATH_FIELD, choices['path'], 'user_text')
        changed.append(PATH_FIELD)
    if choices['components'] and _put_components(flow, g, choices['components'], 'user_text'):
        changed.append(COMPONENT_FIELD)
        if (any(value in ('chosen', 'keep_existing') for value in choices['components'].values())
                and flow.value(g, PATH_FIELD) == 'original_only'):
            # Adding a piece is still the Original Medicare path, no longer "only".
            flow.put(g, PATH_FIELD, 'original_medigap', 'user_text')
            changed.append(PATH_FIELD)
    return changed


# --- The call branch, the trade-off card and "For your call" -----------------
# Wording signed off by the owner on November 13, 2026 (DESIGN_2026-11-13.md, section 6).

def call_branch(flow, g, record):
    """Where the person is with Social Security, as one question with tapped answers.
    The stage follows what they reported; nothing here is inferred."""
    states = [record['parts'][part]['state'] for part in ('A', 'B')]
    contact = flow.value(g, CONTACT_FIELD)
    contact = contact if isinstance(contact, dict) else {}
    if all(state == 'active' for state in states):
        return None
    reports = {part: flow.value(g, PART_FIELDS[part]) for part in ('A', 'B')}
    statuses = [report.get('status') for report in reports.values() if isinstance(report, dict)]
    after = [content()['after'][key]['text'] for key in ('after_review', 'after_letter', 'after_card', 'after_tell')]
    happened = {'question': 'What happened on the call?', 'choices': [
        {'label': 'I applied', 'action': {'report': 'applied'}},
        {'label': 'They gave me start dates', 'dates': True},
        {'label': 'They need more from me', 'action': {'report': 'needs_info'}},
        {'label': 'I only asked questions', 'action': {'report': 'asked'}}]}
    if 'needs_info' in statuses or 'denied' in statuses:
        return {'stage': 'needs_info'}
    if 'approved' in statuses or 'active' in statuses:
        return {'stage': 'dates'}
    if 'applied' in statuses:
        # Later answers stay one tap away: the dates, or a request for more.
        return {'stage': 'applied', 'line': 'You can keep comparing plans while Social Security reviews your application.',
                'after': after, 'choices': happened['choices'][1:3]}
    state = contact.get('state')
    if state == 'not_now':
        return {'stage': 'not_now'}
    if state == 'called':
        asked = contact.get('outcome') == 'asked'
        return {'stage': 'called', **happened,
                **({'line': 'Okay. Tell me anything they said about dates and I’ll use it.'} if asked else {})}
    if state == 'planned':
        return {'stage': 'planned', 'line': 'Your call guide is open. Tell me what they say and I’ll update your next step.',
                'choices': [{'label': 'I already called', 'action': {'contact': 'called'}}]}
    return {'stage': 'ask', 'question': 'Where are you with Social Security?', 'choices': [
        {'label': 'I plan to call', 'action': {'contact': 'planned'}, 'guide': 'phone'},
        {'label': 'I already called', 'action': {'contact': 'called'}},
        {'label': 'Not what I need right now', 'action': {'contact': 'not_now'}}]}


def trade_off_card(flow, g, preference):
    """Both paths side by side from accepted sentences, then one question before narrowing.
    A tap records where to start, never a choice."""
    first = 'medicare_advantage' if preference == 'lower_monthly' else 'original_medigap'
    because = {'predictable': 'You said predictable costs matter more.',
               'lower_monthly': 'You said a lower monthly cost matters more.'}.get(preference, '')
    columns = [
        {'id': 'original_medigap', 'title': 'Original Medicare with Medigap',
         'statement_ids': ['trade_medigap_helps', 'trade_medigap_premium', 'trade_original_access', 'trade_medigap_drugs'],
         'amounts': [{'label': 'Medigap', 'source': 'medigap'}]},
        {'id': 'medicare_advantage', 'title': 'Medicare Advantage',
         'statement_ids': ['trade_ma_limit', 'trade_ma_premium', 'trade_ma_network', 'trade_ma_drugs'],
         'amounts': [{'label': 'Plan premium', 'source': 'ma_premium'}, {'label': 'Yearly in-network limit', 'source': 'ma_limit'}]}]
    for column in columns:
        column['lines'] = [statement(identifier) for identifier in column['statement_ids']]
    if first == 'medicare_advantage':
        question = 'Both paths are on the card. Start with Medicare Advantage plans, and keep Medigap open to compare?'
        order = [('Start with Medicare Advantage', 'medicare_advantage'), ('Start with Medigap', 'original_medigap')]
    else:
        question = 'Both paths are on the card. Start with Medigap prices, and keep Medicare Advantage open to compare?'
        order = [('Start with Medigap', 'original_medigap'), ('Start with Medicare Advantage', 'medicare_advantage')]
    asked = flow.value(g, ASKED_FIELD)
    note = ''
    if asked in ('original_medigap', 'medicare_advantage') and asked != first:
        note = 'You asked about %s first, so it stays open.' % ('Medicare Advantage' if asked == 'medicare_advantage' else 'Medigap')
    identifiers = ['no_limit'] + [identifier for column in columns for identifier in column['statement_ids']]
    return {'kind': 'trade_off', 'title': 'What each path trades', 'because': because, 'top': statement('no_limit'),
            'columns': columns, 'question': question, 'note': note,
            'choices': [{'label': label, 'action': {'start_with': value}} for label, value in order]
                       + [{'label': 'Show me both', 'action': {'start_with': 'both'}}],
            'text': ' '.join(filter(None, [because, statement('no_limit')] + [line for column in columns for line in column['lines']])),
            'statement_ids': identifiers, 'sources': _statement_sources(*identifiers)}


_NAMED_ADVANTAGE = re.compile(r"(?i)\bmedicare advantage\b|\badvantage plans?\b|\bpart c\b")
_NAMED_MEDIGAP = re.compile(r"(?i)\bmedigap\b|\bmedicare supplement\b|\bsupplement(?:al)? (?:plan|policy|insurance|coverage)\b")


def note_asked(flow, g, message):
    """The path a person names first is remembered, so it is not quietly dropped later."""
    if flow.value(g, ASKED_FIELD) or not isinstance(message, str):
        return
    found = [(match.start(), path) for pattern, path in ((_NAMED_ADVANTAGE, 'medicare_advantage'), (_NAMED_MEDIGAP, 'original_medigap'))
             for match in [pattern.search(message)] if match]
    if found:
        flow.put(g, ASKED_FIELD, min(found)[1], 'user_text')


def call_notes(flow, g, r, record):
    """"For your call": the person's own lines and questions for Social Security, built only
    from what they reported. Nothing appears for a fact they did not give."""
    say, ask, know = [], [], []
    today = _today()
    birthday = flow.value(g, 'situation.age65')
    if isinstance(birthday, dict) and birthday.get('month') and birthday.get('year'):
        month, year = int(birthday['month']), int(birthday['year'])
        turned = (year, month) <= (today.year, today.month)
        say.append('“I %s 65 in %s %d.”' % ('turned' if turned else 'turn', ux_pass.MONTH_NAMES[month - 1], year))
    coverage = flow.value(g, 'coverage.current') or []
    job = flow.report(r, 'RC09').get('choice') if r is not None else None
    working = 'current_work_coverage' in record['unsupported']
    if working and ('employer' in coverage or job == 'my_job') and job in (None, '', 'my_job'):
        line = '“I have health coverage through my current job.'
        end = record.get('coverage_end')        # enrollment-journey-v2 (Codex); absent on v1
        if isinstance(end, dict) and end.get('date') and end.get('basis') == 'reported':
            when = date.fromisoformat(end['date'])
            month_end = 'at the end of %s %d' % (ux_pass.MONTH_NAMES[when.month - 1], when.year)
            if str(end.get('source', '')).endswith('coverageEnd'):
                line += ' That coverage ends %s.' % ('on ' + _long(end['date']) if end.get('precision') == 'day' else month_end)
            else:
                line += ' I plan to retire %s.' % ('on ' + _long(end['date']) if end.get('precision') == 'day' else month_end)
        say.append(line + '”')
    reports = {part: flow.value(g, PART_FIELDS[part]) for part in ('A', 'B')}
    applied = [report for report in reports.values() if isinstance(report, dict) and report.get('status') == 'applied']
    if applied:
        dated = next((report['date'] for report in applied if report.get('date')), None)
        if dated:
            ask.append('“I applied on %s. Can you tell me where it stands?”' % _long(dated))
    elif working:
        ask.append('“When should I sign up for Part B so it starts when my job coverage ends?”')
        ask.append('“Do I need my employer to fill in form CMS-L564?”')
        know = [statement('current_work'), statement('medigap_clock')]
    if not say and not ask:
        return None
    return {'title': 'For your call', 'say': say, 'ask': ask, 'know': know,
            'sources': _statement_sources('current_work', 'medigap_clock') if know else []}


def parts_answer(flow, g, r, message, updates):
    """A report of applying for, or having, the parts also answers "Which Medicare
    parts do you have now?" (RC04), so that question is not asked after the person
    has already said it (owner's test conversation, November 13, 2026). Only when
    RC04 has no answer, and only when the person's words settle both parts."""
    if not enabled(flow) or not isinstance(message, str) or not message.strip():
        return None
    if flow.report(r, 'RC04') or any(update.get('id') == 'RC04' for update in updates):
        return None
    today = _today()
    found = reports_from_text(message, journey(flow, g, r, today), today, flow.value(g, 'subject.role'))
    choice = None
    plain = (message or '').replace('’', "'")
    if not found and any(_NEITHER.search(sentence) for sentence in ux_pass.sentences(plain)):
        choice = 'neither'
    elif len(found) == 1 and next(iter(found.values())).get('only'):
        choice = 'a_only' if 'A' in found else 'b_only'
    elif found:
        status = {}
        for part in ('A', 'B'):
            known = found.get(part) or flow.value(g, PART_FIELDS[part])
            status[part] = known.get('status') if isinstance(known, dict) else None
        choice = _parts_choice(status)
    else:
        # A Medicare Advantage plan or a Medigap policy means both parts are in place.
        held = set(flow.value(g, 'coverage.current') or [])
        for update in updates:
            if update.get('id') == 'T05' and not update.get('uncertain'):
                held |= {item.strip() for item in str((update.get('fields') or {}).get('choice', '')).split(',')}
        if held & DERIVES_BOTH:
            choice = 'both'
    if not choice:
        return None
    return {'id': 'RC04', 'entity': 'profile', 'fields': {'choice': choice}, 'quote': message.strip()[:200],
            'scope': 'current', 'subject': 'beneficiary', 'uncertain': False, 'correction': False,
            'direct_choice': True}


# The two-path dashboard has no Medigap or Part D tab: both are steps of Original Medicare.
_OLD_TAB = re.compile(r"(?i)\b(the )?(?:Medicare Supplement \(Medigap\)|Medicare Supplement|Medigap|Part D(?: drug plans?)?) tab\b")


# "The Original Medicare (step 3, prescriptions) tab on the Plans page" read badly in every run of
# November 13, 2026. A reply says "the Plans page"; software shows the button.
_STEP_TAB = re.compile(r"(?:(the|The) )?[“\"]?Original Medicare \(step \d[^)]*\)[”\"]?(?: tab)?(?: (?:on|of|in) the Plans page)?")
_PAGE_TAB = re.compile(r"(?:on |in )?the Plans page[’']s [“\"]?Original Medicare \(step \d[^)]*\)[”\"]?(?: tab)?")


def tab_names(text):
    """Replies point to the Plans page, never to a tab or a step by name."""
    if not isinstance(text, str) or ('tab' not in text and '(step' not in text):
        return text
    text = _OLD_TAB.sub(lambda match: ('the ' if match.group(1) and match.group(1).islower() else
                                        'The ' if match.group(1) else '') + 'Plans page', text)
    text = _PAGE_TAB.sub('the Plans page', text)
    text = _STEP_TAB.sub(lambda match: 'The Plans page' if match.group(1) == 'The' or match.start() == 0 else 'the Plans page', text)
    text = re.sub(r"\b(on|in|under) the Plans page\b", lambda m: ('on' if m.group(1).islower() else 'On') + ' the Plans page', text)
    text = re.sub(r"(the Plans page) (?:under|in|on) the Plans page", r"\1", text)
    text = re.sub(r"Plans page([.,])[”\"]", r"Plans page\1", text)
    # One mention a sentence: "the Plans page now lists ... on the Plans page" loses the second.
    fixed = []
    for sentence in ux_pass.sentences(text):
        first = sentence.find('Plans page')
        if first >= 0 and sentence.find('Plans page', first + 1) >= 0:
            head, tail = sentence[:first + 10], sentence[first + 10:]
            tail = re.sub(r"\s*(?:on|in|under|of) the Plans page", '', tail)
            sentence = head + tail
        fixed.append(sentence)
    text = ''.join(fixed)
    return text


def plans_pages(pages):
    """What the model is told the Plans page is called, for this dashboard."""
    pages = copy.deepcopy(pages)
    for key in ('medigap', 'part_d'):
        if isinstance(pages.get(key), dict):
            pages[key]['tab'] = 'the Plans page'
    if isinstance(pages.get('purpose'), str):
        pages['purpose'] = pages['purpose'].replace('say so, name the tab,', 'say so in a few plain words (software shows the button to it),')
        pages['purpose'] += ' Never name a tab or a step; say “the Plans page” at most.'
    return pages


DERIVES_BOTH = frozenset({'advantage', 'medigap'})


def _parts_choice(status):
    """The RC04 answer two part statuses amount to, or None when they do not settle it."""
    have = {part: status.get(part) == 'active' for part in ('A', 'B')}
    waiting = {part: status.get(part) in ('applied', 'approved', 'needs_info') for part in ('A', 'B')}
    if have['A'] and have['B']:
        return 'both'
    if have['A'] and waiting['B']:
        return 'a_only'
    if have['B'] and waiting['A']:
        return 'b_only'
    if waiting['A'] and waiting['B']:
        return 'pending'
    return None


def _answer_parts(flow, g, r):
    """A tapped report also answers "which parts do you have now", once, if it is unanswered."""
    if r is None or flow.report(r, 'RC04'):
        return
    status = {}
    for part in ('A', 'B'):
        known = flow.value(g, PART_FIELDS[part])
        status[part] = known.get('status') if isinstance(known, dict) else None
    choice = _parts_choice(status)
    if choice:
        flow.apply(g, r, {'id': 'RC04', 'entity': 'profile', 'fields': {'choice': choice}}, 'user_choice')


def _tapped(flow, g, r, action):
    """The call branch and the path to start with (approved design, November 13, 2026).
    Every one is the person's own tap; none needs a model call."""
    today = _today()
    kind = next(key for key in ('contact', 'report', 'starts', 'start_with') if key in action)
    value = action[kind]
    if kind == 'start_with':
        if value not in STARTS:
            raise ValueError('Use a current coverage decision.')
        flow.put(g, START_FIELD, value, 'user_choice')
        return
    if kind == 'contact':
        if value not in ('planned', 'called', 'not_now'):
            raise ValueError('Use a current coverage decision.')
        flow.put(g, CONTACT_FIELD, {'state': value, 'date': today.isoformat()}, 'user_choice')
        return
    record = journey(flow, g, r, today) if r is not None else None
    states = {part: record['parts'][part]['state'] for part in ('A', 'B')} if record else {'A': 'unknown', 'B': 'unknown'}
    if kind == 'report':
        if value not in ('applied', 'needs_info', 'asked'):
            raise ValueError('Use a current coverage decision.')
        if value == 'applied':
            # Whatever is not already in place or already applied for.
            targets = [part for part in ('A', 'B') if states[part] in ('needed', 'unknown')]
            if not targets and not any(state == 'pending' for state in states.values()):
                raise ValueError('Both parts are already in place.')
            for part in targets:
                flow.put(g, PART_FIELDS[part], {'status': 'applied', 'date': None, 'date_kind': 'application'}, 'user_choice')
        elif value == 'needs_info':
            targets = ([part for part in ('A', 'B') if states[part] in ('pending', 'needs_info')]
                       or [part for part in ('A', 'B') if states[part] in ('needed', 'unknown')])
            if not targets:
                raise ValueError('Both parts are already in place.')
            for part in targets:
                flow.put(g, PART_FIELDS[part], {'status': 'needs_info', 'date': None, 'date_kind': 'application'}, 'user_choice')
        flow.put(g, CONTACT_FIELD, {'state': 'called', 'outcome': value, 'date': today.isoformat()}, 'user_choice')
        _answer_parts(flow, g, r)
        return
    # Start dates the person was given. They are theirs: shown as "you told me", never as confirmed.
    if not isinstance(value, dict) or not value or set(value) - {'A', 'B'}:
        raise ValueError('Give a start date for Part A, Part B or both.')
    for part, text in value.items():
        try:
            when = date.fromisoformat(str(text))
        except ValueError:
            raise ValueError('Give each start date as a calendar date.') from None
        if not date(1966, 7, 1) <= when <= date(today.year + 2, 12, 31):
            raise ValueError('That start date is outside the range Daylight can use.')
        flow.put(g, PART_FIELDS[part], {'status': 'approved' if when > today else 'active',
                                        'date': when.isoformat(), 'date_kind': 'start'}, 'user_choice')
    flow.put(g, CONTACT_FIELD, {'state': 'called', 'outcome': 'dates', 'date': today.isoformat()}, 'user_choice')
    _answer_parts(flow, g, r)


def decide(flow, g, action, r=None):
    """A tapped dashboard decision (build item 5). No model call. A tab is a
    view and never comes here; only an explicit decision button does."""
    if getattr(flow, 'records_v1', False) and set(action) == {'type', 'selected_plan'}:
        # D183: "Choose this plan" on the Plans page is the person's choice, kept
        # on the server (intent.selectedPlan) for Before you enroll (issue 30).
        import conversation_records
        conversation_records.select_plan(flow, g, action['selected_plan'])
        return
    tapped = [key for key in ('contact', 'report', 'starts', 'start_with') if key in action]
    if enabled(flow) and len(tapped) == 1 and set(action) == {'type', tapped[0]}:
        return _tapped(flow, g, r, action)
    if not enabled(flow) or set(action) - {'type', 'path', 'component', 'value'}:
        raise ValueError('Use a current coverage decision.')
    path, component, value = action.get('path'), action.get('component'), action.get('value')
    if path is not None:
        allowed = (*PATHS, 'original', 'undecided') if getattr(flow, 'd166', False) else PATHS
        if path not in allowed or component is not None or value is not None:
            raise ValueError('Use a current coverage decision.')
        flow.put(g, PATH_FIELD, path, 'user_choice')
        if getattr(flow, 'd166', False):
            from conversation_planner import DECISION_VERSION, VERSION
            flow.put(g, DECISION_VERSION, VERSION, 'user_choice')
        if path == 'original_only':
            _put_components(flow, g, {'medigap': 'not_needed', 'part_d': 'not_needed'}, 'user_choice')
        return
    if component not in COMPONENTS or value not in DECISIONS:
        raise ValueError('Use a current coverage decision.')
    _put_components(flow, g, {component: value}, 'user_choice')
    if value in ('chosen', 'keep_existing') and flow.value(g, PATH_FIELD) == 'original_only':
        path = 'original' if getattr(flow, 'd166', False) and component == 'part_d' else 'original_medigap'
        flow.put(g, PATH_FIELD, path, 'user_choice')


# ---------------------------------------------------------------------------
# Words for what the record says (build items 1 and 3)
# ---------------------------------------------------------------------------

def _part_text(state, start, report):
    reported = report.get('status') if isinstance(report, dict) else None
    display_date = (date.fromisoformat(start['date']).strftime('%B %Y')
                    if start.get('date') and start.get('precision') == 'month'
                    else _long(start['date']) if start.get('date') else '')
    if state == 'approved_future':
        return 'starts %s (you told me)' % display_date
    if state == 'active':
        if start['basis'] == 'reported':
            return 'active since %s (you told me)' % display_date
        if isinstance(report, dict) and re.fullmatch(r'(?:19|20)\d{2}', str(report.get('since') or '')):
            return 'active since %s (you told me)' % report['since']
        # Owner sign-off November 13, 2026: both labels. Medicare.gov: joining a plan needs Parts A and B.
        derived = {'advantage': 'active (from your Medicare Advantage plan)',
                   'medigap': 'active (from your Medigap policy)'}
        return derived.get(report.get('basis') if isinstance(report, dict) else None, 'active')
    if state == 'pending':
        return 'applied, waiting to hear'
    if state == 'needs_info':
        if reported == 'denied':
            return 'denied (you told me)'
        if reported == 'active':
            return 'start date to confirm'
        return 'Social Security asked for more'
    if state == 'expected_automatically':
        return 'expected automatically'
    return 'not yet' if state == 'needed' else 'not confirmed'


COMPONENT_WORDS = {
    'medigap': {'chosen': 'A Medigap policy', 'not_needed': 'No Medigap policy', 'keep_existing': 'Coverage you already have',
                'decide_later': 'Decide later', 'unknown': 'Not decided'},
    'part_d': {'chosen': 'A Part D drug plan', 'not_needed': 'No Part D plan', 'keep_existing': 'Coverage you already have',
               'decide_later': 'Decide later', 'unknown': 'Not decided'}}
PLAN_TITLES = {'ab_only': 'Parts A and B only', 'original_plus': 'Original Medicare', 'medicare_advantage': 'Medicare Advantage',
               'keep_current': 'keep your current coverage', 'wait': 'wait for now'}


def intended(record, path):
    """The finish this person has chosen. The record marks a finish complete
    only once Parts A and B are in place or applied for; the choice itself is
    theirs as soon as they make it."""
    if record['finish']:
        return record['finish']
    if path in ('keep_current', 'wait'):
        return path
    values = list(record['components'].values())
    if path != 'medicare_advantage' and all(value == 'not_needed' for value in values):
        return 'ab_only'
    if path != 'medicare_advantage' and all(value in ('chosen', 'not_needed', 'keep_existing') for value in values):
        return 'original_plus'
    return None


def _next_text(record, reports, social, coverage=()):
    step, route = record['next_step'], record['route']
    identifier = step['id']
    by = ''
    if step['by']:
        by = ' by %s%s' % (_long(step['by']), {'estimated': ' (from your birthday month)',
                                               'reported': ' (the date you told me)',
                                               # D183 (owner review): the job-coverage window.
                                               'job_dates': ' (from the dates you told me)'}.get(step['basis'], ''))
    denied = any(isinstance(report, dict) and report.get('status') == 'denied' for report in reports.values())
    if identifier == 'sign_up':
        if social:
            return 'check with Social Security whether you’re being signed up automatically'
        verb = {'add_part_b': 'add Part B through Social Security',
                'add_part_a': 'sign up for Part A through Social Security'}.get(route, 'sign up through Social Security')
        return verb + by
    if identifier == 'choose_path' and 'medigap' in coverage:
        # Someone who already has a Medigap policy is on the Original Medicare path.
        return 'decide on prescription coverage'
    if identifier == 'choose_advantage_plan':
        # Looking at Medicare Advantage never drops the Parts A and B step.
        needed = [part for part in ('A', 'B') if record['parts'][part]['state'] == 'needed']
        window = record['window']
        if needed and window and window['phase'] != 'after' and not record['unsupported'] and not social:
            return ('choose a Medicare Advantage plan, and sign up for %s through Social Security by %s (from your birthday month)'
                    % ('Parts A and B' if len(needed) == 2 else 'Part ' + needed[0], _long(window['end'])))
    if identifier == 'confirm_start_date':
        if step['by']:
            return 'check that your Medicare card or letter shows the start date of %s' % _long(step['by'])
        return 'tell me the start date on your Medicare card or letter'
    if identifier == 'confirm_with_social_security':
        return ('ask Social Security about the denial at %s' if denied
                else 'confirm your sign-up timing with Social Security at %s') % SSA_PHONE
    return {'wait_for_decision': 'wait for Social Security’s decision letter',
            'answer_request': 'answer Social Security’s request',
            'choose_path': 'choose Original Medicare or Medicare Advantage',
            'choose_medigap': 'decide how to cover your share of medical costs',
            'choose_part_d': 'decide on prescription coverage',
            'choose_advantage_plan': 'choose a Medicare Advantage plan'}.get(identifier, '')


def _quiet(record):
    """No report yet: the record asserts nothing, so the line stays out."""
    return (all(part['state'] == 'unknown' for part in record['parts'].values())
            and record['next_step']['id'] == 'nothing_needed' and record['finish'] is None)


def status_line(record, reports, path, social=False, coverage=(), *, reuse_card_start_dates=False):
    """One compact line for the chat and the top of the plans pages."""
    if _quiet(record):
        return None
    parts = [{'part': part, 'state': record['parts'][part]['state'],
              'text': _part_text(record['parts'][part]['state'], record['parts'][part]['start'], reports.get(part))}
             for part in ('A', 'B')]
    plan = intended(record, path)
    following = _next_text(record, reports, social, coverage or ())
    if reuse_card_start_dates and record['next_step']['id'] == 'confirm_start_date':
        missing = [part for part in ('A', 'B') if not (
            (report := reports.get(part) or {}).get('date') and report.get('date_kind') == 'start'
            and report.get('precision') != 'month')]
        if not missing:
            following = ''
        elif len(missing) == 1:
            following = 'tell me the Part %s start date on your Medicare card or letter' % missing[0]
    status = 'Part A: %s · Part B: %s.' % (parts[0]['text'], parts[1]['text'])
    text = status
    if plan in ('ab_only', 'keep_current', 'wait'):
        text += ' Your plan: %s.' % PLAN_TITLES[plan]
    window = record['window']
    waiting = (plan == 'wait' and window and window['phase'] != 'after' and not record['unsupported']
               and any(part['state'] == 'needed' for part in parts))
    if following:
        text += ' Next: %s.' % following
    elif waiting:
        text += ' Your sign-up window runs through %s (from your birthday month).' % _long(window['end'])
    return {'text': text, 'status': status, 'parts': parts, 'plan': plan,
            'next': {'id': record['next_step']['id'], 'text': following, 'by': record['next_step']['by'],
                     'basis': record['next_step']['basis']}}


REASON_STATEMENTS = (('railroad', 'railroad'), ('current_work_coverage', 'current_work'),
                     ('window_passed', 'window_passed'), ('not_age_based', 'not_age_based'))


def _signup_rows():
    phone = {'label': 'By phone', 'value': SSA_PHONE,
             'note': 'Monday through Friday, 8 a.m. to 7 p.m. TTY 1-800-325-0778.'}
    office = {'label': 'In person', 'value': 'A local Social Security office', 'note': 'Call first for an appointment.'}
    online = {'label': 'Online', 'value': 'ssa.gov/medicare/sign-up', 'url': 'https://www.ssa.gov/medicare/sign-up'}
    return online, phone, office


def general_signup_card():
    """How to sign up, for the Parts A and B step before Daylight knows enough
    to pick a route. The same sentences as the route card and all three guides.
    It asserts nothing about this person and is never sent as a chat card."""
    online, phone, office = _signup_rows()
    identifiers = ('signup_routes', 'never_ids')
    lines = [statement(identifier) for identifier in identifiers]
    return {'kind': 'signup_route', 'route': 'general', 'title': 'How to sign up for Part A and Part B',
            'rows': [online, phone, office], 'lines': lines, 'guides': ['online_ab', 'add_part_b', 'phone'],
            'statement_ids': list(identifiers), 'text': ' '.join(lines), 'sources': _statement_sources(*identifiers)}


def route_card(record, social=False):
    """Where and how to apply, once, with sources (build item 2)."""
    route = record['route']
    online, phone, office = _signup_rows()
    card = {'kind': 'signup_route', 'route': route, 'rows': [], 'lines': [], 'guides': [], 'statement_ids': []}

    def say(*identifiers):
        card['statement_ids'].extend(identifiers)
        card['lines'].extend(statement(identifier) for identifier in identifiers)

    if route == 'sign_up_a_and_b':
        card['title'] = 'How to sign up for Part A and Part B'
        if social:
            say('automatic', 'automatic_check')
        say('signup_routes')
        card['rows'] = [online, phone, office]
        card['guides'] = ['online_ab', 'phone']
    elif route == 'add_part_b':
        card['title'] = 'How to add Part B'
        say('add_part_b')
        card['rows'] = [{'label': 'Online, when coverage from a job is ending', 'value': 'ssa.gov/medicare/sign-up/part-b-only',
                         'url': 'https://www.ssa.gov/medicare/sign-up/part-b-only'},
                        {'label': 'By fax or mail', 'value': 'Form CMS-40B',
                         'note': 'With form CMS-L564 from the employer if coverage from a job is ending.'}, phone]
        card['guides'] = ['add_part_b', 'phone']
    elif route == 'add_part_a':
        card['title'] = 'How to sign up for Part A'
        say('part_a_only')
        card['rows'] = [online, phone, office]
        card['guides'] = ['online_ab', 'phone']
    elif route == 'confirm_with_social_security':
        card['title'] = 'Confirm with Social Security'
        # Redirect, don't deflect: the accepted general rule first, then who confirms.
        for reason, identifier in REASON_STATEMENTS:
            if reason in record['unsupported']:
                say(identifier)
        say('confirm_ssa')
        card['rows'] = [phone]
        card['guides'] = ['phone']
    elif route == 'automatic':
        card['title'] = 'You’re signed up automatically'
        say('automatic')
    else:
        return None
    say('never_ids')
    card['text'] = ' '.join(card['lines'])
    card['sources'] = _statement_sources(*card['statement_ids'])
    return card


def extra_evidence(message):
    """Checked general rules the conversation may relay when the person raises the subject.

    The insulin limit, Plans C and F, and Plan G beside Plan N were refused in the 15-profile run
    (November 13, 2026) because nothing gave the model the words. Each entry in the content file
    is matched by word groups, all of which must appear in the message."""
    text = ' ' + re.sub(r"\s+", ' ', (message or '').replace('’', "'").casefold()) + ' '
    found = []
    for identifier, entry in (content().get('evidence') or {}).items():
        if all(any(re.search(r"(?<![a-z0-9])(?:%s)" % group_pattern, text) for group_pattern in group) for group in entry['match']):
            found.append({'id': identifier, 'title': entry['title'], 'text': entry['text'], 'summary': entry['text'],
                          'kind': 'reviewed_general_education', 'sources': sources(*entry['sources'])})
    return found


def have_card(flow, g, r):
    """What the person already has, as one card, once both parts are in place.

    Eleven of fifteen test profiles already had Parts A and B and were greeted like new
    enrollees (November 13, 2026). Wording signed off by the owner the same day."""
    record = journey(flow, g, r, _today())
    if not all(part['state'] == 'active' for part in record['parts'].values()):
        return None
    coverage = flow.value(g, 'coverage.current') or []
    held = flow.value(g, HAVE_FIELD)
    letter = held.get('medigap_letter') if isinstance(held, dict) else None
    letter = letter if re.fullmatch(r'[A-DFGK-N]', str(letter or '')) else None
    reports = {part: flow.value(g, field) for part, field in PART_FIELDS.items()}
    rows = [{'label': 'Part %s' % part, 'value': _part_text('active', record['parts'][part]['start'], reports[part])}
            for part in ('A', 'B')]
    if 'advantage' in coverage:
        rows.append({'label': 'Medicare Advantage', 'value': 'You have a Medicare Advantage plan.'})
    else:
        if letter or 'medigap' in coverage:
            rows.append({'label': 'Your share of medical costs', 'value': 'You have Plan %s.' % letter if letter else 'You have a Medigap policy.'})
        if 'drug' in coverage:
            rows.append({'label': 'Prescriptions', 'value': 'You have a drug plan.'})
    if len(rows) == 2:
        return None   # only the parts are known, and the status line already says that
    return {'kind': 'coverage_now', 'title': 'What you have now', 'rows': rows}


def finish_card(record, line):
    """A chosen finish gets its own summary (build item 3)."""
    plan = line and line['plan']
    if not plan:
        return None
    rows = [{'label': 'Part %s' % part['part'], 'value': part['text'][:1].upper() + part['text'][1:]} for part in line['parts']]
    notes = []
    if plan in ('ab_only', 'original_plus'):
        rows += [{'label': 'Your share of medical costs', 'value': COMPONENT_WORDS['medigap'][record['components']['medigap']]},
                 {'label': 'Prescriptions', 'value': COMPONENT_WORDS['part_d'][record['components']['part_d']]}]
    if plan == 'ab_only':
        notes = ['no_limit', 'part_d_penalty']
    if line['next']['text']:
        rows.append({'label': 'Next', 'value': line['next']['text'][:1].upper() + line['next']['text'][1:] + '.'})
    lines = [statement(identifier) for identifier in notes]
    return {'kind': 'finish_summary', 'finish': plan, 'title': 'Your plan: ' + PLAN_TITLES[plan], 'rows': rows,
            'lines': lines, 'text': ' '.join(lines), 'statement_ids': notes, 'sources': _statement_sources(*notes),
            'change': 'You can change this any time. Just tell me.'}


# ---------------------------------------------------------------------------
# Coordinated dates and the dashboard (build items 5 and 7)
# ---------------------------------------------------------------------------

def coordinated_dates(record, timing, age65):
    """Every date in one place, each marked estimated or reported. Estimates
    come from the D157 timing helper only; unsupported situations show none."""
    rows = []
    supported = not record['unsupported']
    window = record['window']
    if window and supported and window['phase'] != 'after' and any(
            part['state'] == 'needed' for part in record['parts'].values()):
        rows.append({'label': 'Sign-up window', 'value': '%s to %s' % (_long(window['start']), _long(window['end'])),
                     'basis': 'estimated', 'note': 'From your birthday month.'})
    for part in ('A', 'B'):
        start = record['parts'][part]['start']
        if start['date'] and start['basis'] == 'reported':
            rows.append({'label': 'Part %s start' % part, 'value': _long(start['date']), 'basis': 'reported', 'note': 'You told me.'})
        elif start['date'] and timing:
            if part == 'B':
                when = ('before %s' % ux_pass._month(timing['eligibility_month']) if timing['part_b_basis'] == 'signup_before_month'
                        else 'in %s' % ux_pass.MONTH_NAMES[timing['signup_month'].month - 1])
                note = 'If you sign up %s.' % when
            else:
                note = 'Premium-free Part A, the month you turn 65.'
            rows.append({'label': 'Part %s could start' % part, 'value': _long(start['date']), 'basis': 'estimated', 'note': note})
    part_b = record['parts']['B']['start']
    medigap = None
    if supported and part_b['date'] and part_b['basis'] == 'reported' and isinstance(age65, dict):
        begins = date.fromisoformat(part_b['date'])
        try:
            turned = date(age65['year'], age65['month'], 1)
        except (KeyError, TypeError, ValueError):
            turned = None
        # The signed rule: six months from the month Part B starts at 65 or older.
        if turned and begins.day == 1 and begins >= ux_pass._add_months(turned, -1):
            medigap = (begins, ux_pass._month_end(ux_pass._add_months(begins, 5)), 'reported', 'From the Part B start you told me.')
    elif supported and timing and timing.get('medigap_window') and record['parts']['B']['state'] == 'needed':
        span = timing['medigap_window']
        medigap = (span['start'], span['end'], 'estimated', 'If Part B starts %s.' % ux_pass._long(span['start']))
    if medigap:
        rows.append({'label': 'Medigap window', 'value': '%s through %s' % (ux_pass._month(medigap[0]), ux_pass._month(medigap[1])),
                     'basis': medigap[2], 'note': medigap[3]})
    return rows


def before_enroll(record, path, line):
    """Before you enroll, for the action this person intends (build item 7)."""
    plan = line['plan'] if line else intended(record, path)
    both = all(part['state'] == 'active' for part in record['parts'].values())
    either = any(part['state'] == 'active' for part in record['parts'].values())
    status = line['status'] if line else ''
    if plan in ('ab_only', 'keep_current', 'wait'):
        return {'applies': False, 'action': PLAN_TITLES[plan],
                'text': 'Before you enroll is for joining a Medicare Advantage or drug plan. Your plan doesn’t include one.'}
    if path == 'medicare_advantage':
        return {'applies': True, 'action': 'a Medicare Advantage plan', 'needs': statement('join_needs'),
                'ready': both, 'status': status, 'statement_ids': ['join_needs'], 'sources': _statement_sources('join_needs')}
    if record['components']['part_d'] == 'chosen':
        return {'applies': True, 'action': 'a Part D drug plan', 'needs': statement('join_needs'),
                'ready': either, 'status': status, 'statement_ids': ['join_needs'], 'sources': _statement_sources('join_needs')}
    return {'applies': True, 'action': None}


def _ab_step(record, line):
    states = [part['state'] for part in record['parts'].values()]
    if all(state == 'active' for state in states):
        state = 'done'
    elif any(state in ('needed', 'unknown', 'needs_info') for state in states):
        state = 'open'
    else:
        state = 'pending'
    return {'id': 'ab', 'title': 'Parts A and B', 'state': state,
            'text': line['status'] if line else 'Not confirmed yet'}


def dashboard(record, line, path, coverage=(), task='', held=None):
    """Two paths, three decisions each. Each decision ends as done, not
    needed, keep what I have or decide later; a tab is only a view."""
    ab = _ab_step(record, line)
    components = dict(record['components'])
    held = held if isinstance(held, dict) else {}
    letter = held.get('medigap_letter') if re.fullmatch(r'[A-DFGK-N]', str(held.get('medigap_letter') or '')) else None
    has_medigap = 'medigap' in (coverage or ()) or bool(letter)
    has_drug = 'drug' in (coverage or ())
    has_advantage = 'advantage' in (coverage or ())
    # What a person has is a fact; keeping it is their decision (owner sign-off November 13, 2026).
    have = [['keep_existing', 'Keep it'], ['compare', 'Compare'], ['decide_later', 'Decide later']]
    medigap_settled = components['medigap'] in ('chosen', 'not_needed', 'keep_existing') or has_medigap
    original = [ab,
                {'id': 'medigap', 'title': 'Your share of medical costs', 'state': components['medigap'],
                 'text': (('You have Plan %s.' % letter if letter else 'You have a Medigap policy.')
                          if has_medigap and components['medigap'] in ('unknown', 'keep_existing')
                          else COMPONENT_WORDS['medigap'][components['medigap']]),
                 'have': has_medigap,
                 'choices': have if has_medigap and components['medigap'] == 'unknown' else
                            [['chosen', 'Done'], ['keep_existing', 'Keep what I have'],
                             ['not_needed', 'Not needed'], ['decide_later', 'Decide later']]},
                {'id': 'part_d', 'title': 'Prescriptions', 'state': components['part_d'],
                 'text': ('You have a drug plan.' if has_drug and components['part_d'] in ('unknown', 'keep_existing')
                          else COMPONENT_WORDS['part_d'][components['part_d']]),
                 'have': has_drug,
                 'choices': have if has_drug and components['part_d'] == 'unknown' else
                            [['chosen', 'Done'], ['keep_existing', 'Keep what I have'],
                             ['not_needed', 'Not needed'], ['decide_later', 'Decide later']]}]
    advantage = [ab,
                 {'id': 'plan', 'title': 'Choose a plan', 'state': 'unknown',
                  'text': 'You have a Medicare Advantage plan.' if has_advantage else 'Not decided', 'have': has_advantage,
                  'choices': [['chosen', 'Done'], ['decide_later', 'Decide later']]},
                 {'id': 'drugs', 'title': 'Check that plan’s drug coverage', 'state': 'unknown', 'text': 'Not checked',
                  'choices': [['chosen', 'Done'], ['not_needed', 'Not needed'], ['decide_later', 'Decide later']]}]
    # Owner, November 13: a path opens at step 1, Parts A and B, until both parts are in
    # place; the browser then returns to the step the person last saw. Someone who only
    # needs drug coverage still opens at step 3.
    settled = ab['state'] == 'done'
    open_original = ('part_d' if task == 'drug_pricing' or (settled and medigap_settled)
                     else 'medigap' if settled else 'ab')
    return {'paths': {'original': {'title': 'Original Medicare', 'steps': original, 'open': open_original},
                      'advantage': {'title': 'Medicare Advantage', 'steps': advantage, 'open': 'plan' if settled else 'ab'}},
            'recorded_path': path if path in (*PATHS, 'original') else None, 'plan': line['plan'] if line else None}


def view(flow, g, r):
    """Everything the browser shows about enrollment, for every response."""
    import ux_flow
    if getattr(flow, 'd166', False):
        from conversation_planner import decision_guide
        g = decision_guide(flow, g)
    from adaptive_flow import metadata
    today = _today()
    record = journey(flow, g, r, today)
    reports = {part: flow.value(g, field) for part, field in PART_FIELDS.items()}
    path = flow.value(g, PATH_FIELD)
    social = flow.value(g, 'coverage.socialBenefits') == 'yes'
    coverage = flow.value(g, 'coverage.current') or []
    line = status_line(record, reports, path, social, coverage,
                       reuse_card_start_dates=getattr(flow, 'reuse_card_start_dates', False))
    timing = ux_flow.timing(flow, g, r)
    return {'version': 'enrollment-view-v1', 'record': record, 'line': line,
            'route': route_card(record, social) if line else None,
            # Nothing known yet: the Parts A and B step still says how to sign up and offers every guide.
            'signup': None if line else general_signup_card(),
            # Approved design, November 13: where the person is with Social Security, and their lines for the call.
            'call': call_branch(flow, g, record), 'notes': call_notes(flow, g, r, record),
            'start': flow.value(g, START_FIELD) if flow.value(g, START_FIELD) in STARTS else None,
            'dates': coordinated_dates(record, timing, flow.value(g, 'situation.age65')),
            'dashboard': dashboard(record, line, path, coverage, metadata(r).get('task', ''), flow.value(g, HAVE_FIELD)),
            'before': before_enroll(record, path, line),
            'content': {'version': content()['version'], 'last_checked': content()['last_checked']},
            # D183 (:8895 only): the Plans page may send "Choose this plan" to the server.
            **({'selectedPlan': flow.value(g, 'intent.selectedPlan'), 'selectedPlanSupported': True}
               if getattr(flow, 'records_v1', False) else {})}


SIGNUP_ASK = re.compile(r"(?i)\bhow (?:do|can|would|does) (?:i|we|he|she|one|someone)\b[^?]*\b(?:sign up|enroll|apply|add part b|get part [ab])\b"
                        r"|\bwhere (?:do|can) (?:i|we)\b[^?]*\b(?:sign up|enroll|apply)\b|\bhow to (?:sign up|enroll|apply)\b")
CARD_ROUTES = ('sign_up_a_and_b', 'add_part_b', 'add_part_a', 'confirm_with_social_security')


def cards(flow, owner, chain, g, r, message, attached, *, record_signup=True):
    """Cards this turn adds: a chosen finish's summary when the choice is made
    or what is in place changes, and the sign-up route once, on a turn with no
    other card or whenever the person asks how to sign up."""
    found = []
    current = view(flow, g, r)
    record, line = current['record'], current['line']
    if 'advantage' in (flow.value(g, 'coverage.current') or []):
        trial = trial_right(flow, g, r, _today())
        if trial:
            key = 'trial-right:' + trial['rows'][0]['value'] + ':' + trial['rows'][-1]['value']
            if not flow.ux.shown(owner, chain, key):
                found.append(trial)
                flow.ux.record(owner, chain, '', card=key)
    if not line:
        return found
    summary = finish_card(record, line)
    if summary:
        key = 'finish:%s:%s' % (line['plan'], '|'.join(part['state'] for part in line['parts']))
        if not flow.ux.shown(owner, chain, key):
            found.append(summary)
            flow.ux.record(owner, chain, '', card=key)
    asked = bool(SIGNUP_ASK.search(message or ''))
    route = current['route']
    if (route and route['route'] in CARD_ROUTES
            and (asked or record['next_step']['id'] in ('sign_up', 'confirm_with_social_security'))
            and (asked or not (attached or found))
            and (asked or not flow.ux.shown(owner, chain, 'signup_route:' + route['route']))):
        found.append(route)
        if record_signup:
            flow.ux.record(owner, chain, '', card='signup_route:' + route['route'])
    return found


def trial_at_first_eligibility(flow, guide, record):
    from applicable_rules import _month_start

    start = _month_start(flow.report(record, 'RC16').get('start'))
    first = recommendation_engine.first_eligibility(guide, record)
    birthday = flow.value(guide, 'situation.age65')
    birthday_month = (f"{birthday['year']:04d}-{birthday['month']:02d}"
                      if isinstance(birthday, dict) and birthday.get('year') and birthday.get('month') else None)
    return bool(start and first == start.isoformat()[:7] == birthday_month)


def trial_right(flow, guide, record, today):
    from applicable_rules import _add_months, _month_start

    report = flow.report(record, 'RC16')
    start = _month_start(report.get('start'))
    if report.get('choice') != 'yes' or not start or start > today:
        return None
    matched = trial_at_first_eligibility(flow, guide, record)
    boundary = _add_months(start, 12)
    state = ('The first 12 months have passed.' if today >= boundary else
             'You reported joining when first eligible at 65.' if matched else
             'Whether you joined when first eligible at 65 is still open.')
    fact = flow.facts.get('ma_trial_right', {})
    return {'kind': 'trial_right', 'title': 'Medicare Advantage trial right',
            'rows': [{'label': 'First Advantage plan started', 'value': start.strftime('%B %Y') + ' (you told me)'},
                     {'label': '12 months from that start', 'value': boundary.strftime('%B %Y') + ' (from your start month)'},
                     {'label': 'Where you stand', 'value': state}],
            'sources': fact.get('sources', [])}


def context(flow, g, r):
    """What the model is told. States only; software shows every date."""
    if getattr(flow, 'd166', False):
        from conversation_planner import decision_guide
        g = decision_guide(flow, g)
    record = journey(flow, g, r, _today())
    return {'parts': {part: record['parts'][part]['state'] for part in ('A', 'B')},
            'next_step': record['next_step']['id'], 'route': record['route'],
            'chosen_plan': intended(record, flow.value(g, PATH_FIELD)), 'held': list(record['unsupported']),
            'rules': [
                'Software shows this person’s Part A and Part B status and next step on a line above the conversation, '
                'and shows every sign-up date in cards. Never state, compute or change a date, deadline or penalty yourself.',
                'Never say an application was sent, received, approved or in effect. Software shows what the person reported.',
                'Parts A and B alone, keeping current coverage and waiting are complete, valid choices. When chosen_plan is '
                'set, respect it; do not urge a supplement, a drug plan or Medicare Advantage.',
                'The application happens at Social Security. Never ask for a Social Security number, Medicare number or password.',
                'A person can keep exploring plans while an application is pending.',
                'held lists situations where software gives the general rule and Social Security confirms the personal date.']}
