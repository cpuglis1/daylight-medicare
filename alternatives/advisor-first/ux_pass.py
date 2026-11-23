"""D157 UX pass (owner direction, November 12, 2026).

Deterministic helpers for the participant conversation. Code decides; the AI
explains: every date here is computed from the person's own reports and the
reviewed general rules in ``pilot-rules-r4-ux-pass.json``. Nothing in this
module calls a model, reads plan rows or stores the person's words.

Contents
- enrollment timing: Initial Enrollment Period, Part A / Part B start and the
  Medigap Open Enrollment Period (CV-10, CV-13, CV-08);
- find-mode intent ("which is best for me") (CV-02, CV-29, CV-30);
- a visit-only say-once ledger of teaching points and sentence fingerprints
  (CV-14, CV-26, K-01 to K-03);
- reply clean-up that never fails a turn: label openers, repeated caveats,
  stacked limit statements, internal wording (CV-20, CV-27, CV-30, CV-32);
- question checks: verbatim re-asks, topic menus, a reason for every personal
  question (CV-09, CV-25, CV-31);
- the recorded coverage path (PG-10) and what is left before a tab (CV-37).
"""
from collections import OrderedDict
from datetime import date
import hashlib
import re
import threading
import time

__all__ = ['enrollment_timing', 'timing_card', 'medigap_window_line', 'find_intent', 'VisitLedger',
           'clean_reply', 'sentence_points', 'is_topic_menu', 'question_reason', 'shorter_question',
           'coverage_path', 'path_from_text', 'whats_left', 'JARGON', 'INTERNAL', 'HEDGE']

MONTH_NAMES = ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
               'September', 'October', 'November', 'December')


# ---------------------------------------------------------------------------
# Enrollment timing (Medicare.gov: "When does Medicare coverage start?",
# "When can I buy a Medigap policy?"). Owner sign-off November 12, 2026.
# ---------------------------------------------------------------------------

def _add_months(day, months):
    total = day.year * 12 + day.month - 1 + months
    return date(total // 12, total % 12 + 1, 1)


def _month_end(day):
    following = _add_months(day, 1)
    return date.fromordinal(following.toordinal() - 1)


def _long(day):
    return '%s %d, %d' % (MONTH_NAMES[day.month - 1], day.day, day.year)


def _month(day):
    return '%s %d' % (MONTH_NAMES[day.month - 1], day.year)


def enrollment_timing(birthday, today=None, parts=None):
    """Fixed-rule dates from a reported 65th-birthday month.

    ``birthday`` is the resolved ``situation.age65`` report: the month and year
    the person turns 65 and whether the birthday is on the first of the month.
    ``parts`` is the resolved RC04 choice ('neither', 'a_only', 'b_only',
    'both') or None when not reported.

    Returns None unless the month and year are both reported. Medicare treats
    a birthday on the first as turning 65 the month before. A birthday whose
    first-of-month status was never reported is treated as later in the month
    and the result says so (``first_day_assumed``).
    """
    if not isinstance(birthday, dict):
        return None
    month, year = birthday.get('month'), birthday.get('year')
    if type(month) is not int or type(year) is not int or not 1 <= month <= 12 or not 2000 <= year <= 2100:
        return None
    today = today or date.today()
    first_day = birthday.get('first_day') is True
    turns = date(year, month, 1)
    eligible = _add_months(turns, -1) if first_day else turns
    start, last = _add_months(eligible, -3), _month_end(_add_months(eligible, 3))
    signup = date(today.year, today.month, 1)
    if today < start:
        phase = 'before'
    elif today > last:
        phase = 'after'
    else:
        phase = 'open'
    part_b = None
    if parts in ('b_only', 'both'):
        part_b_basis = 'reported'
    elif phase == 'before' or (phase == 'open' and signup < eligible):
        part_b, part_b_basis = eligible, 'signup_before_month'
    elif phase == 'open':
        part_b, part_b_basis = _add_months(signup, 1), 'signup_this_month'
    else:
        part_b_basis = 'outside_window'
    # Premium-free Part A starts the month the person turns 65 and can be
    # backdated up to 6 months, never earlier than that month.
    part_a = None
    if parts not in ('a_only', 'both'):
        part_a = max(eligible, _add_months(signup, -6))
    medigap = None
    if part_b is not None:
        medigap = {'start': part_b, 'end': _month_end(_add_months(part_b, 5))}
    return {'turns_65': turns, 'eligibility_month': eligible, 'first_day': first_day,
            'first_day_assumed': birthday.get('first_day') is None,
            'iep': {'start': start, 'end': last, 'phase': phase},
            'signup_month': signup, 'part_a_start': part_a, 'part_b_start': part_b,
            'part_b_basis': part_b_basis, 'medigap_window': medigap, 'parts': parts}


def timing_card(timing, coverage=(), said=()):
    """The code-built card the conversation shows once timing is computable.

    Wording follows the statements the owner signed off on November 12, 2026;
    every date is filled from ``enrollment_timing``. Returns None when there is
    nothing rule-based to state (for example after the window has closed, where
    the General or a Special Enrollment Period rule applies instead).
    """
    if not timing or timing['iep']['phase'] == 'after' or timing['parts'] == 'both':
        return None
    iep = timing['iep']
    rows = [{'label': 'Your sign-up window', 'value': '%s to %s' % (_long(iep['start']), _long(iep['end'])),
             'note': 'The 3 months before the month you turn 65, that month, and the 3 months after.'}]
    lines = ['Your Initial Enrollment Period runs %s through %s: the 3 months before the month you turn 65, '
             'that month, and the 3 months after.' % (_long(iep['start']), _long(iep['end']))]
    if timing['part_b_start']:
        when = ('before %s' % _month(timing['eligibility_month']) if timing['part_b_basis'] == 'signup_before_month'
                else 'in %s' % MONTH_NAMES[timing['signup_month'].month - 1])
        rows.append({'label': 'Part B starts', 'value': _long(timing['part_b_start']),
                     'note': 'If you sign up %s.' % when})
        lines.append('If you sign up %s, Part B starts %s.' % (when, _long(timing['part_b_start'])))
    if timing['part_a_start']:
        rows.append({'label': 'Premium-free Part A starts', 'value': _long(timing['part_a_start']),
                     'note': 'The month you turn 65.'})
        lines.append('Premium-free Part A starts %s, the month you turn 65.' % _long(timing['part_a_start']))
    window = timing['medigap_window']
    if window:
        rows.append({'label': 'Medigap window', 'value': '%s through %s' % (_month(window['start']), _month(window['end'])),
                     'note': 'Six months from the month Part B starts. After it, an insurer can ask health questions '
                             'and may decline or charge more.'})
    cobra = 'cobra' in (coverage or ())
    note = ''
    if cobra:
        # Said once (K-01, CV-14): when the conversation has already said COBRA
        # doesn't put off Part B, the card adds only what is new.
        first = 'COBRA isn’t coverage from a current job, so it doesn’t let someone put off Part B without a penalty. '
        second = ('Once someone is 65, Medicare pays first and COBRA pays second, and COBRA may pay only a small part '
                  'of a bill, so without Part B a person can be left paying most of the cost.')
        note = second if 'cobra_trap' in (said or ()) else first + second
        lines.append(note)
    return {'kind': 'enrollment_timing', 'title': 'Your Medicare timing', 'rows': rows, 'text': ' '.join(lines),
            'points': ['enrollment_window'] + (['cobra_trap', 'cobra_second'] if cobra else []),
            'footer': 'You sign up through Social Security.', 'cobra': note,
            'sources': [{'label': 'Medicare.gov: When does Medicare coverage start?',
                         'url': 'https://www.medicare.gov/basics/get-started-with-medicare/sign-up/when-does-medicare-coverage-start'}]
                       + ([{'label': 'Medicare.gov: Who pays first?',
                            'url': 'https://www.medicare.gov/health-drug-plans/coordination/who-pays-first'}] if cobra else []),
            'statement_ids': ['initial_enrollment_window'] + (['cobra_initial_window', 'cobra_pays_second'] if cobra else []),
            'dates': {'iep_start': iep['start'].isoformat(), 'iep_end': iep['end'].isoformat(),
                      'part_b_start': timing['part_b_start'].isoformat() if timing['part_b_start'] else None,
                      'part_a_start': timing['part_a_start'].isoformat() if timing['part_a_start'] else None,
                      'medigap_start': window['start'].isoformat() if window else None,
                      'medigap_end': window['end'].isoformat() if window else None}}


def medigap_window_line(timing, today=None):
    """One personal line for the Medigap tab and the chat (PG-03, CV-13)."""
    if not timing or not timing.get('medigap_window'):
        return None
    today = today or date.today()
    window = timing['medigap_window']
    span = '%s through %s' % (_month(window['start']), _month(window['end']))
    if today > window['end']:
        return {'state': 'closed', 'text': ''}
    state = 'open' if today >= window['start'] else 'upcoming'
    basis = '' if timing['part_b_basis'] == 'reported' else 'If your Part B starts %s, ' % _long(window['start'])
    lead = '%syour Medigap Open Enrollment Period runs %s.' % (basis, span)
    lead = lead[0].upper() + lead[1:]
    return {'state': state, 'start': window['start'].isoformat(), 'end': window['end'].isoformat(),
            'text': lead + ' During it, an insurer can’t turn you down or charge more because of your health.'}


# ---------------------------------------------------------------------------
# Find-mode intent (CV-02, CV-29, CV-30)
# ---------------------------------------------------------------------------

_FIND = re.compile(
    r"(?i)\b(?:(?:what|which)(?:'s| is| one is| are| would be)? (?:the )?(?:best|better|right) (?:plan|plans|option|options|one|choice|route|path|coverage)\b"
    r"|best (?:plan|plans|option|options|one|coverage|choice)\b"
    r"|(?:best|better|right|makes sense) for (?:me|my|us|him|her|them)\b"
    r"|show me (?:the |my |some )?(?:plans|options|prices|choices)"
    r"|(?:see|look at|find|get to) (?:the |my |some )?(?:best )?(?:plans|options|prices)"
    r"|what should (?:i|we|he|she) (?:get|pick|choose|do|buy)"
    r"|which (?:plan|one|option|route|path) should"
    r"|(?:isn'?t|not|is not) (?:specific|personal|tailored) (?:to|for) (?:me|my)"
    r"|for my situation"
    r"|just (?:tell|show) me"
    r"|(?:idk|i don'?t know|not sure|no idea) (?:which|what)(?: one)?(?: is| would be)? (?:better|best|right))")


# The first list was written around one test conversation and matched none of 17 option-seeking
# messages from fifteen other profiles (November 13, 2026). These are those people's words. Cards
# are also triggered from the state of the conversation (ux_flow), not from phrases alone.
_OPTIONS = re.compile(
    r"(?i)\b(?:(?:my|our|the) options\b|what are (?:my|our|the) (?:options|choices)"
    r"|which (?:way|plan|one|path|route|option)\b|cheapest|least expensive|lowest (?:premium|cost|price)"
    r"|how much (?:is|are|would|does|do|will)\b|what (?:would|does|do|will)\b.{0,40}\bcost\b"
    r"|in order (?:of|by)\b|(?:put|list|rank|sort) the plans|show me\b|name the best|give me a plan"
    r"|should (?:i|we|he|she) (?:leave|switch|stay|keep|drop|get|buy|change)\b|would you (?:actually )?recommend"
    r"|compare (?:the |my |these )?(?:plans|options|paths|two))")


def find_intent(text, wide=False):
    """True when the person asks for their options rather than more teaching. ``wide`` adds the
    second list; it is on for the two-path dashboard build only until the owner releases it."""
    if not isinstance(text, str):
        return False
    plain = text.replace('’', "'")
    return bool(_FIND.search(plain) or wide and _OPTIONS.search(plain))


# ---------------------------------------------------------------------------
# Teaching points and wording classes
# ---------------------------------------------------------------------------

POINTS = OrderedDict([
    ('cobra_trap', re.compile(r"(?i)\bcobra\b[^.!?]*\b(?:current[- ](?:employment|job|work)|(?:does(?:n['’]t| not)|won['’]t|will not) (?:count|extend|let|protect|delay)|"
                               r"put off part b|delay(?:ing)? part b|special enrollment|penalt|time to (?:sign up|enroll))")),
    ('cobra_second', re.compile(r"(?i)\bcobra\b[^.!?]*\bpays? (?:second|first|only|little)|\bmedicare pays first\b[^.!?]*\bcobra\b")),
    ('two_routes', re.compile(r"(?i)\b(?:two|2) (?:main )?(?:routes|paths|ways|options|choices)\b|"
                               r"\boriginal medicare\b[^.!?]*\b(?:or|versus|vs\.?|while|whereas|and)\b[^.!?]*\bmedicare advantage\b")),
    ('medigap_window', re.compile(r"(?i)\b(?:medigap|supplement)\b[^.!?]*\b(?:open enrollment|six[- ]month|6[- ]month|health questions)")),
    ('enrollment_window', re.compile(r"(?i)\binitial enrollment period\b|\b(?:seven|7)[- ]month (?:window|period)\b")),
    ('sep_8_month', re.compile(r"(?i)\b(?:8|eight)[- ]month\b[^.!?]*\b(?:special enrollment|window|period)|special enrollment period\b[^.!?]*\b(?:8|eight) months")),
    ('extra_help', re.compile(r"(?i)\bextra help\b|\bmedicare savings program")),
    ('prior_authorization', re.compile(r"(?i)\bprior authorization\b")),
    ('premium_vs_costs', re.compile(r"(?i)\b(?:lower|low|\$0) (?:monthly )?premium\b[^.!?]*\b(?:when you (?:get|use) care|copays?|out[- ]of[- ]pocket)")),
])
# Caveat points are dropped when repeated without being asked; teaching points
# are counted and reported to the model as already said.
CAVEATS = frozenset({'cobra_trap', 'cobra_second', 'sep_8_month'})
ASKED = {'cobra_trap': r'\bcobra\b', 'cobra_second': r'\bcobra\b', 'sep_8_month': r'special enrollment|8.month|eight.month',
         'two_routes': r'\b(?:routes?|paths?|original medicare|advantage|difference)\b',
         'medigap_window': r'\bmedigap\b|\bsupplement\b', 'extra_help': r'extra help|afford|income',
         'enrollment_window': r'\b(?:when|window|deadline|sign up|enroll)\b', 'premium_vs_costs': r'\bpremium|\bcost'}

HEDGE = re.compile(
    r"(?i)\bnot (?:yet )?a (?:finding|recommendation|commitment|guarantee|determination)\b|"
    r"\b(?:is|are|was)n['’]t a (?:finding|recommendation|commitment|guarantee|determination)\b|"
    r"\bwouldn['’]t call (?:either|any)\b|\bnot assume (?:either|any)\b|\bdoes(?:n['’]t| not) (?:confirm|establish|verify|prove|mean (?:either|one))\b|"
    r"\bcan['’]t (?:say|tell you) which (?:is|one is|route is|path is) (?:better|best)\b|"
    r"\bnot (?:a )?(?:finding|claim) that (?:one|either)\b|\bisn['’]t (?:the|a) winner\b|\bthe winner\b")
JARGON = OrderedDict([
    (re.compile(r"(?i)\bchecking participation\b"), 'checking whether the doctor is in a plan’s network'),
    (re.compile(r"(?i)\bparticipation check\b"), 'network check'),
    (re.compile(r"(?i)\bthe local check\b"), 'the doctor check'),
    (re.compile(r"(?i)\bthe exact office\b"), 'the office you visit'),
])
INTERNAL = re.compile(
    r"(?i)\bsupported (?:personal )?ranking\b|\bpersonal ranking\b|\brecording gap\b|\bpricing review\b|\bvalidation code\b|"
    r"\bcapabilit(?:y|ies)\b|\bfixture\b|\brehearsal\b|\bevaluation mode\b|\bresearch[- ]only\b|\bfor research only\b|"
    r"\bsample data\b|\bthis (?:is a )?(?:pilot|demo)\b|\bin this (?:pilot|demo)\b|\bthe pilot\b|\blocal evaluation\b|"
    r"\bdeterministic\b|\bprice source\b|\bsource[- ]bound\b")
# "The missing piece is whether you already have Medicare in place" (CV-15) and
# "Medigap premiums need the sex category … and tobacco category" (CV-28).
MISSING = re.compile(r"(?i)\b(?:missing piece|(?:what(?:['’]s| is)|the (?:one|only) (?:thing|detail)) (?:still )?missing|"
                     r"still (?:need|missing|don['’]t know|do not know)|(?:don['’]t|do not) (?:yet )?(?:know|have) (?:whether|if|your|which))\b")
ANNOUNCED = re.compile(r"(?i)\b(?:need|needs|needed|require|requires|required|missing)\b[^.!?]*"
                       r"\b(?:sex category|tobacco category|pricing details?|pricing categor(?:y|ies))\b")
_LABEL_OPENER = re.compile(r"(?i)^\s*(?:noted|got it|understood|recorded|okay,? noted)\s*[:—–-]\s*")
_SENTENCE = re.compile(r'[^.!?\n]+(?:[.!?]+["”’)]*\s*|\n+|$)')


def _norm(sentence):
    return re.sub(r'[^a-z0-9 ]', '', re.sub(r'\s+', ' ', sentence.casefold().replace('’', "'"))).strip()


def _print(sentence):
    return hashlib.sha256(_norm(sentence).encode()).hexdigest()[:20]


_ABBREVIATION = re.compile(r"(?:\b(?:Dr|Drs|Mr|Mrs|Ms|St|Jr|Sr|Mt|Ft|No|vs|etc|Inc|Co|Rd|Ave|Blvd|Ste|Apt|Mon|Tue|Tues|Wed|Thu|Thur|Thurs|"
                           r"Fri|Sat|Sun|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.|(?:\b[A-Za-z]\.){2,})[\"”’)]*\s*$")


def _continues(before, after):
    """True when the period that ended ``before`` did not end a sentence."""
    plain = before.rstrip()
    if '\n' in before[len(plain):] or not plain.endswith('.') and not re.search(r"\.[\"”’)]+$", plain):
        return False
    if _ABBREVIATION.search(plain):
        return True
    # "U." + "S.", "e." + "g.": no space after the period and a letter next. "Part B. That" is an end.
    if before == plain and re.match(r"[A-Za-z]", after) and re.search(r"(?:^|[\s(])[A-Za-z]\.$", plain):
        return True
    # "$236.50", "1.5": a period between digits with no space is a decimal point.
    return bool(re.search(r"\d\.$", before) and re.match(r"\d", after))


def sentences(text):
    """Whole sentences. A period after a title or an initial, or inside a number, is not an end:
    cutting at "Dr." once dropped half a sentence from a reply ("We'll keep Dr. Speake and Dr. For
    your preference...", profile PP13, November 13, 2026)."""
    merged = []
    for part in (m.group(0) for m in _SENTENCE.finditer(text or '')):
        if not part.strip():
            continue
        if merged and _continues(merged[-1], part):
            merged[-1] += part
        else:
            merged.append(part)
    return merged


def sentence_points(sentence):
    return [name for name, pattern in POINTS.items() if pattern.search(sentence)]


class VisitLedger:
    """Say-once record per visit: point names, counts and sentence hashes.

    RAM only, owner-and-chain keyed, 24 hours, bounded like the dialogue
    memory. It stores no words: sentence fingerprints are one-way hashes.
    """
    TTL, LIMIT = 86400, 128

    def __init__(self, clock=None):
        self._clock = clock or time.monotonic
        self._visits = OrderedDict()
        self._lock = threading.RLock()

    def _visit(self, owner, chain, create=True):
        now = self._clock()
        for key in [key for key, item in self._visits.items() if item['expires'] <= now]:
            del self._visits[key]
        if not isinstance(owner, str) or not owner or not isinstance(chain, str) or not chain:
            return None
        key = (owner, chain)
        visit = self._visits.get(key)
        if visit is None and create:
            visit = self._visits[key] = {'points': OrderedDict(), 'prints': set(), 'questions': {},
                                         'find_mode': False, 'turns': 0, 'cards': set(), 'tabs': set(),
                                         'ask_counts': {}, 'path': None, 'expires': now + self.TTL}
            while len(self._visits) > self.LIMIT:
                self._visits.popitem(last=False)
        if visit is not None:
            visit['expires'] = now + self.TTL
        return visit

    def view(self, owner, chain):
        with self._lock:
            visit = self._visit(owner, chain, create=False)
            if not visit:
                return {'points': {}, 'find_mode': False, 'turns': 0, 'cards': [], 'tabs': [], 'path': None,
                        'ask_counts': {}}
            return {'points': dict(visit['points']), 'find_mode': visit['find_mode'], 'turns': visit['turns'],
                    'cards': sorted(visit['cards']), 'tabs': sorted(visit['tabs']), 'path': visit['path'],
                    'ask_counts': dict(visit['ask_counts'])}

    def set_find_mode(self, owner, chain):
        with self._lock:
            visit = self._visit(owner, chain)
            if visit is not None:
                visit['find_mode'] = True

    def set_path(self, owner, chain, path):
        with self._lock:
            visit = self._visit(owner, chain)
            if visit is not None and path in PATHS:
                visit['path'] = path

    def seen(self, owner, chain, sentence):
        with self._lock:
            visit = self._visit(owner, chain, create=False)
            return bool(visit and _print(sentence) in visit['prints'])

    def said(self, owner, chain, point):
        with self._lock:
            visit = self._visit(owner, chain, create=False)
            return bool(visit and visit['points'].get(point))

    def shown(self, owner, chain, card):
        with self._lock:
            visit = self._visit(owner, chain, create=False)
            return bool(visit and card in visit['cards'])

    def record(self, owner, chain, reply, points=(), card=None, tab=None):
        with self._lock:
            visit = self._visit(owner, chain)
            if visit is None:
                return
            visit['turns'] += 1
            found = list(points)
            for sentence in sentences(reply):
                if len(_norm(sentence)) >= 25:
                    visit['prints'].add(_print(sentence))
                found.extend(sentence_points(sentence))
            for point in dict.fromkeys(found):
                visit['points'][point] = visit['points'].get(point, 0) + 1
            if card:
                visit['cards'].add(card)
            if tab:
                visit['tabs'].add(tab)

    def shown_question(self, owner, chain, key):
        """Count one more turn that ended on this question; returns the new count."""
        with self._lock:
            visit = self._visit(owner, chain)
            if visit is None or not key:
                return 0
            counts = visit.setdefault('question_shows', {})
            counts[key] = counts.get(key, 0) + 1
            return counts[key]

    def park(self, owner, chain, key):
        with self._lock:
            visit = self._visit(owner, chain)
            if visit is not None and key:
                visit.setdefault('parked', set()).add(key)

    def unpark(self, owner, chain, key):
        with self._lock:
            visit = self._visit(owner, chain, create=False)
            if visit:
                visit.get('parked', set()).discard(key)
                visit.get('question_shows', {}).pop(key, None)

    def parked(self, owner, chain, key):
        with self._lock:
            visit = self._visit(owner, chain, create=False)
            return bool(visit and key in visit.get('parked', ()))

    def asked(self, owner, chain, identifier, text):
        """Record a question; return how many times this exact wording was asked before."""
        with self._lock:
            visit = self._visit(owner, chain)
            if visit is None or not identifier:
                return 0
            key = (identifier, _print(text or ''))
            before = visit['questions'].get(key, 0)
            visit['questions'][key] = before + 1
            visit['ask_counts'][identifier] = visit['ask_counts'].get(identifier, 0) + 1
            return before

    def forget_owner(self, owner):
        with self._lock:
            for key in [key for key in self._visits if key[0] == owner]:
                del self._visits[key]


def clean_reply(reply, *, message='', said=None, seen=None, allow=(), known=(), drop=()):
    """Tidy one generated reply without ever failing the turn.

    ``said(point)`` and ``seen(sentence)`` read the visit ledger. A sentence is
    removed only when it is (a) a label opener ("Noted: …"), (b) a word-for-word
    repeat from earlier in this visit, (c) a caveat already delivered that the
    person did not raise again, (d) a second or later limit statement in the
    same reply, (e) internal wording, (f) a claim that a detail the person
    already gave (``known`` topic patterns) is missing, or (g) an announcement
    that a pricing detail is missing. If that would leave nothing, the
    original reply is kept. Returns the reply and a small count of what changed.
    """
    said, seen = said or (lambda point: False), seen or (lambda sentence: False)
    asked = (message or '').casefold()
    stats = {'label_openers': 0, 'verbatim_repeats': 0, 'repeated_caveats': 0, 'extra_limits': 0,
             'internal': 0, 'jargon': 0, 'false_missing': 0, 'announced_missing': 0,
             'points': [], 'repeated_points': []}
    kept, hedges, local_prints = [], 0, set()
    for index, sentence in enumerate(sentences(reply or '')):
        text = sentence
        if index == 0 and _LABEL_OPENER.match(text):
            stats['label_openers'] += 1
            remainder = _LABEL_OPENER.sub('', text).strip()
            # "Noted: Naples, 34102." is a label, not a sentence: drop it. A
            # real sentence after the label keeps its words.
            if len(remainder.split()) <= 8 and not re.search(r"(?i)\b(?:is|are|means|so|because|that|which|will|can|starts?)\b", remainder):
                continue
            tail = sentence[len(sentence.rstrip()):]
            text = remainder[:1].upper() + remainder[1:] + tail
        normal = _norm(text)
        if INTERNAL.search(text):
            stats['internal'] += 1
            continue
        if ANNOUNCED.search(text):
            stats['announced_missing'] += 1
            continue
        if MISSING.search(text) and any(re.search(topic, text, re.I) for topic in known):
            stats['false_missing'] += 1
            continue
        points = sentence_points(text)
        long_enough = len(normal) >= 25
        if long_enough and (seen(text) or _print(text) in local_prints):
            stats['verbatim_repeats'] += 1
            continue
        repeated = [p for p in points if said(p) and p not in allow]
        if repeated:
            stats['repeated_points'].extend(repeated)
            raised = any(re.search(ASKED.get(p, r'$^'), asked) for p in repeated)
            # ``drop`` names teaching points a software card answers this turn
            # with the person's own specifics, so the general version goes.
            if all(p in drop for p in points) or (not raised and all(p in CAVEATS for p in points)):
                stats['repeated_caveats'] += 1
                continue
        if HEDGE.search(text):
            hedges += 1
            if hedges > 1:
                stats['extra_limits'] += 1
                continue
        for pattern, plain in JARGON.items():
            if pattern.search(text):
                stats['jargon'] += 1
                text = pattern.sub(plain, text)
        if long_enough:
            local_prints.add(_print(text))
        stats['points'].extend(points)
        kept.append(text)
    cleaned = re.sub(r'[ \t]+\n', '\n', ''.join(kept)).strip()
    cleaned = re.sub(r' {2,}', ' ', cleaned)
    stats['points'] = list(dict.fromkeys(stats['points']))
    stats['repeated_points'] = list(dict.fromkeys(stats['repeated_points']))
    if not cleaned:
        return (reply or '').strip(), {**stats, 'kept_original': True}
    return cleaned, stats


# ---------------------------------------------------------------------------
# Questions (CV-09, CV-25, CV-31)
# ---------------------------------------------------------------------------

_MENU = re.compile(
    r"(?i)^\s*(?:what would (?:you like|be most helpful) to (?:understand|explore|learn|look at|go over)(?: next| first)?|"
    r"would (?:you like|it help) (?:a |to see a |me to give (?:you )?a )?(?:simpler picture|[^?]{0,60}) or [^?]{0,80}|"
    r"which (?:topic|part|of these) would you like(?: to (?:start with|explore|understand))?|"
    r"(?:should|shall) we (?:start with|look at) [^?]{0,60} or [^?]{0,60}|"
    r"what (?:else )?(?:can|should) i (?:explain|go over)[^?]{0,40})\??\s*$")


def is_topic_menu(question):
    """A question that offers topics to learn about instead of the next step."""
    return bool(isinstance(question, str) and _MENU.match(question.strip()))


REASONS = {
    'RC01': 'Plans and prices depend on who the coverage is for.',
    'T03': 'Plans and prices are different in each ZIP code.',
    'T05': 'What you have now decides when you can sign up and what you can add.',
    'RC04': 'Whether you already have Part A or Part B decides what you sign up for next.',
    'S_AGE65': 'The month you turn 65 sets your sign-up window and the date coverage can start.',
    'T06': 'Medicare Advantage plans have networks, so your doctors decide which plans fit.',
    'T07': 'Each drug plan covers a different list of medicines.',
    'T08': 'Where you get care decides whether a plan’s network works for you.',
    'T09': 'This sets how your plans are ordered: lowest monthly cost first, or most predictable costs first.',
    'T10': 'What matters most to you sets how your options are ordered.',
    'MG_AGE': 'Medigap prices are set by age.',
    'MG_SEX': 'Medigap insurers list separate Female and Male prices.',
    'MG_TOBACCO': 'Medigap insurers list separate prices for people who use tobacco.',
    'RC18': 'Help with costs changes what you pay for a drug plan.',
}
SHORT = {
    # A second ask uses one of these fixed wordings. Owner approval November 13, 2026.
    'T05': 'What coverage do you have today?',
    'T06': 'Any doctors or hospitals to keep?',
    'T07': 'Which medicines should I include?',
    'T08': 'Any routine care away from home?',
    'RC21': 'Which office do you visit for this doctor?',
    'RC23': 'What are the refill details for these medicines?',
    'S_AGE65': 'Which month and year?',
    'RC04': 'Do you have Part A, Part B, both or neither?',
    'T03': 'What’s your ZIP code?',
    'MG_AGE': 'How old are you?',
    'MG_SEX': 'Female or Male, for pricing?',
    'MG_TOBACCO': 'Any tobacco use?',
    'T09': 'Lower monthly cost, or more predictable costs?',
}


def question_reason(identifier):
    return REASONS.get((identifier or '').split('.')[0], '')


_LEAD = re.compile(r'^(?:because|since|so that|so|to|for)\b[^?]*?,\s+(?=(?:which|what|when|where|who|how|will|do|does|'
                   r'did|are|is|would|could|can|should|have|has)\b)', re.I)


def plain_question(text, labels=()):
    """The question alone. The reason has its own line and the options are
    buttons, so neither belongs in the question, and nothing follows the
    question mark. Returns (text, restructured)."""
    original = (text or '').strip()
    if '?' not in original:
        return original, False
    body = original[:original.index('?') + 1]
    # "..., so we can look at options in your area?": the reason has its own line.
    body = re.sub(r',?\s+so (?:that |we |i |you |daylight )[^?]*\?$', '?', body, flags=re.I)
    stripped = _LEAD.sub('', body)
    restructured = stripped != body
    body = stripped
    if ':' in body:
        head, tail = body.rsplit(':', 1)
        if sum(str(label).casefold() in tail.casefold() for label in labels) >= 2 or re.search(r'\bor\b', tail):
            body, restructured = head.rstrip() + '?', True
    return body[:1].upper() + body[1:], restructured


def shorter_question(identifier, text, helper=False):
    """A fixed, shorter wording for a second ask of the same meaning, or the question unchanged.

    Never a piece of the first wording: keeping the text after the last comma produced
    "Including your therapist?" and "Exact pharmacy and retail or mail order should we use?"
    (15-profile run, November 13, 2026). A helper is never asked about "you"."""
    short = SHORT.get((identifier or '').split('.')[0])
    if short and helper and re.search(r"(?i)\byou(?:r)?\b", short):
        short = None
    if short and _norm(short) != _norm(text or ''):
        return short
    return text


# ---------------------------------------------------------------------------
# Coverage path as a recorded fact (PG-10, X-04)
# ---------------------------------------------------------------------------

PATHS = ('original_medigap', 'medicare_advantage')
_ORIGINAL = re.compile(r"(?i)\b(?:medigap|supplement|plan [a-n]\b|original medicare)")
_ADVANTAGE = re.compile(r"(?i)\b(?:medicare advantage|advantage plan|hmo|ppo)\b|\bMA\b")
_CHOOSE = re.compile(r"(?i)\b(?:i(?:['’]ll| will)? (?:go|stick) with|i (?:want|choose|pick|prefer|decided on|am going with)|i['’]m going with|"
                     r"let['’]s (?:go|do)|sign me up for|i think i (?:want|will|['’]ll))\b")


def path_from_text(text):
    """An explicit choice of path in the person's own words, else None."""
    if not isinstance(text, str) or '?' in text or not _CHOOSE.search(text):
        return None
    original, advantage = bool(_ORIGINAL.search(text)), bool(_ADVANTAGE.search(text))
    if original == advantage:
        return None
    return 'original_medigap' if original else 'medicare_advantage'


def coverage_path(*, chosen=None, cost_preference=None, travel=None, task=''):
    """chosen / leaning / undecided, from the person's own reports only.

    A lean relays what the person said matters (predictable costs, care away
    from home or asking about Medigap point to Original Medicare with Medigap;
    lowest monthly cost points to Medicare Advantage). It decides where "See
    plans" opens. It is never a recommendation and yields to an explicit choice.
    """
    if chosen in PATHS:
        return {'state': 'chosen', 'path': chosen, 'because': ['You chose this path.']}
    toward = {'original_medigap': 0, 'medicare_advantage': 0}
    because = {'original_medigap': [], 'medicare_advantage': []}

    def lean(path, reason):
        toward[path] += 1
        because[path].append(reason)
    if cost_preference == 'predictable':
        lean('original_medigap', 'You said predictable costs matter more.')
    elif cost_preference == 'lower_monthly':
        lean('medicare_advantage', 'You said a lower monthly cost matters more.')
    if travel in ('elsewhere_us', 'outside_us'):
        lean('original_medigap', 'You get care away from home.')
    if task == 'medigap':
        lean('original_medigap', 'You asked about Medigap.')
    if toward['original_medigap'] == toward['medicare_advantage']:
        return {'state': 'undecided', 'path': None, 'because': []}
    path = max(toward, key=toward.get)
    return {'state': 'leaning', 'path': path, 'because': because[path]}


def whats_left(pages, path=None):
    """"2 details left to see your Medigap prices" from the tabs' own lists (CV-37)."""
    order = ['medigap', 'part_d'] if path != 'medicare_advantage' else ['part_d', 'medigap']
    names = {'medigap': 'your Medigap prices', 'part_d': 'your Part D drug plans'}
    for key in order:
        page = (pages or {}).get(key) or {}
        needed = page.get('still_needed') or []
        if page.get('status') == 'missing' and needed:
            count = len(needed)
            return {'tab': key, 'count': count, 'needed': list(needed),
                    'text': '%d detail%s left to see %s' % (count, '' if count == 1 else 's', names[key])}
    return None
