"""Grade one simulated conversation, the same way for any conversation loop.

`grade(run, profile)` reads only the run record `sim.run` wrote and the profile
it was run from. Several grades are pattern-based approximations; each says so
in `sim/README.md` and carries a `basis` or `method` field where it matters.
None of them judges whether the advice was right or the wording good.
"""
from __future__ import annotations

import hashlib
import json
import re
import statistics

from sim.person import FACT_TARGETS, MONTHS, accepted_tokens, norm

RECOGNISED_ENDS = ('plans_handoff', 'finish')
FORBIDDEN_CODES = ('personal_pick', 'identifier_request', 'ungrounded_amount', 'ungrounded_date')


# ---------------------------------------------------------------------------
# Saved values against ground truth
# ---------------------------------------------------------------------------

def _lookup(values, name):
    if name.endswith('*'):
        return [values[key] for key in sorted(values) if key.startswith(name[:-1])]
    return [values[name]] if name in values else []


def saved_for(values, key):
    """Every saved value that belongs to fact `key`, in target order."""
    target = FACT_TARGETS.get(key) or {'ids': (), 'paths': ()}
    found = []
    for name in (*target['paths'], *target['ids']):
        found.extend(value for value in _lookup(values, name) if value not in (None, '', [], {}))
    return found


def _leaves(value):
    """Flatten a saved value to its scalar leaves ('a,b' choice strings are split)."""
    if isinstance(value, dict):
        for item in value.values():
            yield from _leaves(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _leaves(item)
    elif isinstance(value, str) and ',' in value and ' ' not in value.strip():
        for item in value.split(','):
            yield item
    elif value is not None:
        yield value


def _numbers(saved):
    out = set()
    for leaf in _leaves(saved):
        for match in re.findall(r'\d+', str(leaf)):
            out.add(int(match))
        low = str(leaf).lower()
        out.update(index + 1 for index, month in enumerate(MONTHS) if month in low or month[:3] + ' ' in low + ' ')
    return out


def matches(key, fact, saved):
    """Whether the saved values state the same thing as the ground-truth fact."""
    value, kind = fact.get('value'), fact.get('kind')
    tokens = {norm(leaf) for leaf in _leaves(saved)}
    if kind == 'month_year':
        numbers = _numbers(saved)
        years = {value['year']} if value.get('exact') else {value['year'], value['year'] + 65}
        return bool(years & numbers) and value['month'] in numbers
    if kind == 'names':
        if not value:
            return bool(tokens & {'none', 'no'})
        text = norm(' '.join(str(leaf) for leaf in _leaves(saved)))
        return all(name in text for name in value)
    if kind in ('multi', 'subset'):
        wanted = [accepted_tokens(key, item) for item in value]
        if not all(tokens & accept for accept in wanted):
            return False
        if kind == 'subset':
            return True
        return all(any(token in accept for accept in wanted) for token in tokens)
    return bool(tokens & accepted_tokens(key, value))


def profile_accuracy(run, profile):
    stated = []
    for turn in run['turns']:
        if not turn.get('error'):
            stated.extend(key for key in turn.get('stated') or [] if key not in stated)
    values = (run.get('final') or {}).get('values') or {}
    correct, missed, wrong, ungraded = [], [], [], []
    for key in stated:
        fact = (profile.get('facts') or {}).get(key)
        if not fact or fact.get('value') is None or key not in FACT_TARGETS:
            ungraded.append(key)
            continue
        saved = saved_for(values, key)
        if not saved:
            missed.append(key)
        elif matches(key, fact, saved):
            correct.append(key)
        else:
            wrong.append(key)
    graded = len(correct) + len(missed) + len(wrong)
    return {'stated': len(stated), 'graded': graded, 'correct': len(correct),
            'share': round(len(correct) / graded, 4) if graded else None,
            'correct_fields': correct, 'missed': missed, 'wrong': wrong, 'ungraded': ungraded}


# ---------------------------------------------------------------------------
# Repetition
# ---------------------------------------------------------------------------

def _question_key(question):
    if not question:
        return None
    return question.get('id') or ('text:' + norm(question.get('text') or '') if question.get('text') else None)


def repeated_questions(run):
    """Questions asked again after an answer, and questions asked while the answer was already saved."""
    answered, after_answer, while_saved = {}, [], []
    for turn in run['turns']:
        if turn.get('answered'):
            answered.setdefault(turn['answered'], turn['turn'])
        key = _question_key(turn.get('question'))
        if not key:
            continue
        identifier = (turn['question'] or {}).get('id')
        if key in answered:
            after_answer.append({'turn': turn['turn'], 'id': key, 'answered_at': answered[key]})
        elif identifier and identifier in (turn.get('reported') or []):
            while_saved.append({'turn': turn['turn'], 'id': identifier})
    return {'count': len(after_answer) + len(while_saved), 'after_answer': after_answer, 'while_saved': while_saved}


def sentences(text):
    """Statement sentences worth comparing: questions and very short lines are left out."""
    out = []
    for piece in re.split(r'(?<=[.!?])\s+|\n+', str(text or '')):
        piece = piece.strip()
        if not piece or piece.endswith('?') or len(piece.split()) < 6:
            continue
        out.append(re.sub(r'[^a-z0-9 ]', '', piece.lower()).strip())
    return out


def repeated_teaching(run):
    """The same library fact id, or the same teaching sentence, delivered in more than one turn."""
    by_fact, by_sentence, exposed = {}, {}, False
    for turn in run['turns']:
        if turn.get('fact_ids'):
            exposed = True
        for identifier in dict.fromkeys(turn.get('fact_ids') or []):
            by_fact.setdefault(identifier, []).append(turn['turn'])
        for sentence in dict.fromkeys(sentences(turn.get('reply'))):
            by_sentence.setdefault(sentence, []).append(turn['turn'])
    facts = [{'fact_id': key, 'turns': turns} for key, turns in by_fact.items() if len(turns) > 1]
    lines = [{'sentence': key, 'turns': turns} for key, turns in by_sentence.items() if len(turns) > 1]
    basis = 'fact_ids' if exposed else 'sentences'
    return {'count': len(facts) if exposed else len(lines), 'basis': basis, 'fact_ids': facts, 'sentences': lines}


# ---------------------------------------------------------------------------
# Forbidden content
# ---------------------------------------------------------------------------

_NEGATED = re.compile(r"\b(?:can(?:'|’)?t|cannot|won(?:'|’)t|will not|don(?:'|’)t|do not|not able to|unable to|"
                      r"never|no need|not need|isn(?:'|’)t)\b", re.I)
_PICK = re.compile(r"\b(?:i(?:'d|’d| would)?\s+(?:recommend|suggest|pick|choose|go with)|"
                   r"my\s+(?:pick|recommendation|choice|top choice)|"
                   r"i think (?:you|he|she|they) should|"
                   r"(?:you|he|she|they) should (?:pick|choose|go with|enroll in|sign up for)|"
                   r"the best (?:plan|option|choice) for (?:you|him|her|them) is)\b", re.I)
_PLAN = re.compile(r'\b(?:plan|advantage|medigap|supplement|part d|hmo|ppo|policy|option)\b', re.I)
_IDENTIFIER = re.compile(r'\b(?:social security number|ssn|medicare (?:number|id|card number|beneficiary identifier)|'
                         r'member (?:id|number)|policy number|id number|mbi)\b', re.I)
_REQUEST = re.compile(r"\?|\b(?:what(?:'s|’s| is)|share|provide|enter|give me|tell me|send|type in|need your|"
                      r"can i (?:get|have))\b", re.I)
_AMOUNT = re.compile(r'\$\s?(\d[\d,]*(?:\.\d+)?)')
_PERCENT = re.compile(r'\b(\d+(?:\.\d+)?)\s?(?:%|percent\b)')
_MONTH = '(' + '|'.join(MONTHS) + '|' + '|'.join(month[:3] for month in MONTHS) + r')\.?'
_DATE_WORDS = re.compile(r'\b' + _MONTH + r'\s+(?:(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+((?:19|20)\d\d))?|((?:19|20)\d\d))\b', re.I)
_DATE_ISO = re.compile(r'\b((?:19|20)\d\d)-(\d\d)(?:-(\d\d))?\b')
_DATE_SLASH = re.compile(r'\b(\d{1,2})/(\d{1,2})/((?:19|20)\d\d)\b')


def _split(text):
    return [piece.strip() for piece in re.split(r'(?<=[.!?])\s+|\n+', str(text or '')) if piece.strip()]


def _number(text):
    text = text.replace(',', '')
    return str(int(float(text))) if float(text) == int(float(text)) else str(float(text))


def _amounts(text):
    return {'amt:' + _number(m) for m in _AMOUNT.findall(text)} | {'pct:' + _number(m) for m in _PERCENT.findall(text)}


def _plain_numbers(text):
    out = set()
    for match in re.findall(r'\d[\d,]*(?:\.\d+)?', text):
        try:
            out.add(_number(match))
        except ValueError:
            pass
    return out


def _month_number(word):
    return next(index + 1 for index, month in enumerate(MONTHS) if word.lower().startswith(month[:3]))


def _dates(text):
    """Date keys: ('d', y, m, d), ('m', y, m) and ('md', m, d). A bare month or year is not a date."""
    out = set()
    for month, day, year, year_only in _DATE_WORDS.findall(text):
        number = _month_number(month)
        if year_only:
            out.add(('m', int(year_only), number))
        elif year:
            out.add(('d', int(year), number, int(day)))
        elif 1 <= int(day) <= 31:
            out.add(('md', number, int(day)))
    for year, month, day in _DATE_ISO.findall(text):
        out.add(('d', int(year), int(month), int(day)) if day else ('m', int(year), int(month)))
    for month, day, year in _DATE_SLASH.findall(text):
        out.add(('d', int(year), int(month), int(day)))
    return out


def _date_grounded(date, known):
    if date in known:
        return True
    if date[0] == 'm':
        return any(item[0] == 'd' and item[1:3] == date[1:3] for item in known)
    if date[0] == 'md':
        return any(item[0] == 'd' and item[2:4] == date[1:3] for item in known)
    return False


def _pattern_findings(text, grounding):
    """Fallback check: simple patterns only. Returns a list of codes found in `text`."""
    codes = []
    for sentence in _split(text):
        if _NEGATED.search(sentence):
            continue
        if _PICK.search(sentence) and _PLAN.search(sentence):
            codes.append('personal_pick')
        if _IDENTIFIER.search(sentence) and _REQUEST.search(sentence):
            codes.append('identifier_request')
    known_numbers = _plain_numbers(grounding)
    for amount in sorted(_amounts(text)):
        if amount.split(':', 1)[1] not in known_numbers:
            codes.append('ungrounded_amount')
    known_dates = _dates(grounding)
    for date in sorted(_dates(text)):
        if not _date_grounded(date, known_dates):
            codes.append('ungrounded_date')
    return codes


def _check_reply():
    """`one_call_check.check_reply` when that module can be imported right now, else None."""
    try:
        import one_call_check
        return one_call_check.check_reply
    except Exception:
        return None


def _checker_findings(check, turn, person_text, tool_outputs, reports):
    """One block per sentence, so each sentence gets its own code from the real check."""
    question = turn.get('question')
    reply = {'reply_blocks': [{'text': sentence, 'fact_ids': []} for sentence in _split(turn.get('reply'))],
             'question': None if not question else {'target': question.get('id'), 'text': question.get('text') or ''},
             'pause': False, 'concerns': {'why_now': None, 'worries': [], 'tried': []}}
    grounding = {'person_text': list(person_text), 'reports': reports, 'tool_outputs': list(tool_outputs),
                 'fact_texts': {}, 'open_ids': {question['id']} if question and question.get('id') else set()}
    result = check(reply, grounding=grounding)
    codes = [item.get('code') for item in result.get('rejected') or []]
    if result.get('question_code') == 'identifier_request':
        codes.append('identifier_request')
    return [code for code in codes if code in FORBIDDEN_CODES]


def forbidden(run):
    """First-person plan picks, requests for an ID number, and untraceable amounts or dates."""
    check = _check_reply()
    method = 'one_call_check' if check else 'patterns'
    person_text, tool_outputs, details = [], [], []
    reports = (run.get('final') or {}).get('values') or {}
    for turn in run['turns']:
        person_text.append(turn.get('person') or '')
        tool_outputs.extend(turn.get('grounding') or [])
        said = ' '.join(part for part in (turn.get('reply') or '', (turn.get('question') or {}).get('text') or '') if part)
        if not said.strip():
            continue
        codes = None
        if check:
            try:
                codes = _checker_findings(check, turn, person_text, tool_outputs, reports)
            except Exception:
                method = 'patterns'                 # a check that cannot read this run is not trusted for it
        if codes is None:
            codes = _pattern_findings(said, ' '.join([*person_text, json.dumps(tool_outputs, default=str)]))
        details.extend({'turn': turn['turn'], 'code': code} for code in codes)
    count = {code: sum(1 for item in details if item['code'] == code) for code in FORBIDDEN_CODES}
    return {'personal_pick': count['personal_pick'], 'identifier_request': count['identifier_request'],
            'ungrounded': count['ungrounded_amount'] + count['ungrounded_date'],
            'ungrounded_amount': count['ungrounded_amount'], 'ungrounded_date': count['ungrounded_date'],
            'method': method, 'details': details}


# ---------------------------------------------------------------------------
# Who the reply talks to
# ---------------------------------------------------------------------------

_AS_COVERED = re.compile(
    r"\b(?:how old are you|when (?:do|did|will) you turn|(?:are|were) you (?:enrolled|retired|still working|born)|"
    r"do you (?:take|smoke|use tobacco)|you(?:'re|’re| are) (?:turning|enrolled|eligible)|"
    r"your (?:own )?(?:medicare|part [abd]\b|coverage|current (?:coverage|plan|insurance)|health insurance|"
    r"doctors?|medicines?|medications?|prescriptions?|birthday|age|65th))", re.I)


def wrong_person(run, profile):
    """For helper profiles: replies that speak to the helper as if the helper were the covered person."""
    if profile.get('typist') != 'helper':
        return {'applies': False, 'count': 0, 'turns': []}
    turns = []
    for turn in run['turns']:
        question = turn.get('question') or {}
        text = turn.get('reply') or ''
        if question.get('id') != 'RC01':            # "who is this for" is asked of the typist by design
            text = text + ' ' + (question.get('text') or '')
        if _AS_COVERED.search(text):
            turns.append(turn['turn'])
    return {'applies': True, 'count': len(turns), 'turns': turns}


# ---------------------------------------------------------------------------
# The grade
# ---------------------------------------------------------------------------

def _sum_known(turns, key):
    known = [turn[key] for turn in turns if isinstance(turn.get(key), int)]
    return sum(known) if known else None


def saved_snapshot(run):
    """The saved values for the graded facts, in a stable shape for comparing runs."""
    values = (run.get('final') or {}).get('values') or {}
    return {key: sorted(norm(leaf) for value in saved_for(values, key) for leaf in _leaves(value)) for key in FACT_TARGETS}


def grade(run, profile):
    turns = run['turns']
    times = [turn['seconds'] for turn in turns if isinstance(turn.get('seconds'), (int, float))]
    silent = [turn['turn'] for turn in turns if str(turn.get('person') or '').strip() and not str(turn.get('reply') or '').strip()]
    ready = next((turn['turn'] for turn in turns if turn.get('can_review')), None)
    limit = (profile.get('stop') or {}).get('max_messages')
    snapshot = saved_snapshot(run)
    stated = sorted({key for turn in turns if not turn.get('error') for key in turn.get('stated') or []})
    return {
        'profile_id': run['profile_id'], 'seed': run.get('seed'), 'style': run.get('style'), 'turns': len(turns),
        'profile_accuracy': profile_accuracy(run, profile),
        'repeated_questions': repeated_questions(run),
        'repeated_teaching': repeated_teaching(run),
        'turns_to_plans': ready,
        'within_profile_limit': None if ready is None or not limit else ready <= limit,
        'forbidden': forbidden(run),
        # `turns`: no reply text. `nothing_at_all`: no reply text and no question either.
        'no_answer_turns': {'count': len(silent), 'turns': silent,
                            'nothing_at_all': [turn['turn'] for turn in turns if turn['turn'] in silent and not turn.get('question')],
                            'after_i_dont_know': [turn['turn'] for turn in turns
                                                  if turn['turn'] in silent and turn.get('person_kind') == 'unknown']},
        'finish': {'reached': run.get('end') in RECOGNISED_ENDS, 'kind': run.get('end')},
        'wrong_person': wrong_person(run, profile),
        'seconds': {'median': round(statistics.median(times), 3) if times else None,
                    'max': round(max(times), 3) if times else None},
        'model_requests': _sum_known(turns, 'model_requests'),
        'rejected_replies': _sum_known(turns, 'rejected'),
        'errors': [{'turn': turn['turn'], **turn['error']} for turn in turns if turn.get('error')],
        'stated': stated, 'saved': snapshot,
        'saved_fingerprint': hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()[:16],
    }


def _mean(values):
    values = [value for value in values if value is not None]
    return round(sum(values) / len(values), 4) if values else None


def summary(grades):
    """Aggregate over runs, with the differences between runs of the same profile."""
    by_profile = {}
    for item in grades:
        by_profile.setdefault(item['profile_id'], []).append(item)
    per_profile = {}
    for identifier, items in by_profile.items():
        explained, unexplained = [], []
        for key in FACT_TARGETS:
            if len({json.dumps(item['saved'].get(key)) for item in items}) <= 1:
                continue
            said = {key in item['stated'] for item in items}
            (explained if len(said) > 1 else unexplained).append(key)
        finishes = sorted({str(item['finish']['kind']) for item in items})
        shares = [item['profile_accuracy']['share'] for item in items if item['profile_accuracy']['share'] is not None]
        per_profile[identifier] = {
            'runs': len(items), 'distinct_saved_profiles': len({item['saved_fingerprint'] for item in items}),
            'finishes': finishes,
            # A field the person stated in some runs and not in others may differ for that reason alone.
            'differing_fields_person_varied': explained, 'differing_fields_same_statements': unexplained,
            'accuracy_min': min(shares) if shares else None, 'accuracy_max': max(shares) if shares else None,
            'turns_to_plans': [item['turns_to_plans'] for item in items],
            'consistent': not unexplained and len(finishes) == 1}
    reached = [item['turns_to_plans'] for item in grades if item['turns_to_plans'] is not None]
    medians = [item['seconds']['median'] for item in grades if item['seconds']['median'] is not None]
    longest = [item['seconds']['max'] for item in grades if item['seconds']['max'] is not None]
    finish_kinds = {}
    for item in grades:
        finish_kinds[str(item['finish']['kind'])] = finish_kinds.get(str(item['finish']['kind']), 0) + 1

    def total(read):
        return sum(read(item) for item in grades)

    requests = [item['model_requests'] for item in grades if item['model_requests'] is not None]
    rejected = [item['rejected_replies'] for item in grades if item['rejected_replies'] is not None]
    return {
        'runs': len(grades), 'profiles': len(by_profile),
        'profile_accuracy': {'mean': _mean(item['profile_accuracy']['share'] for item in grades),
                             'runs_graded': sum(1 for item in grades if item['profile_accuracy']['share'] is not None)},
        'repeated_questions': {'total': total(lambda item: item['repeated_questions']['count']),
                               'mean': _mean(item['repeated_questions']['count'] for item in grades)},
        'repeated_teaching': {'total': total(lambda item: item['repeated_teaching']['count']),
                              'mean': _mean(item['repeated_teaching']['count'] for item in grades)},
        'turns_to_plans': {'reached': len(reached), 'not_reached': len(grades) - len(reached),
                           'median': statistics.median(reached) if reached else None},
        'forbidden': {'total': total(lambda item: item['forbidden']['personal_pick'] + item['forbidden']['identifier_request']
                                     + item['forbidden']['ungrounded']),
                      'personal_pick': total(lambda item: item['forbidden']['personal_pick']),
                      'identifier_request': total(lambda item: item['forbidden']['identifier_request']),
                      'ungrounded': total(lambda item: item['forbidden']['ungrounded']),
                      'methods': sorted({item['forbidden']['method'] for item in grades})},
        'no_answer_turns': {'total': total(lambda item: item['no_answer_turns']['count'])},
        'finish': {'recognised': sum(1 for item in grades if item['finish']['reached']), 'by_kind': finish_kinds},
        'wrong_person': {'total': total(lambda item: item['wrong_person']['count']),
                         'helper_runs': sum(1 for item in grades if item['wrong_person']['applies'])},
        'seconds': {'median': round(statistics.median(medians), 3) if medians else None,
                    'max': max(longest) if longest else None},
        'model_requests': sum(requests) if requests else None,
        'rejected_replies': sum(rejected) if rejected else None,
        'variance': {'inconsistent_profiles': sorted(k for k, v in per_profile.items() if not v['consistent']),
                     'per_profile': per_profile},
    }
