"""Simulated people: profile loading, an offline scripted person and a gated model person.

The scripted person is deliberately simple. It answers the question the advisor
actually asked (by the question's id when there is one), from the profile's
ground truth, and records which facts it stated so a run can be graded. It reads
no Medicare rules and carries none: every phrase it says comes from the
profile's own fictional data.
"""
from __future__ import annotations

import copy
import json
import random
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Facts: one small vocabulary shared with the graders.
# ---------------------------------------------------------------------------

# fact key -> where a conversation flow saves it. `ids` are advisor-first
# question ids; `paths` are guide field paths ('*' matches a suffix).
FACT_TARGETS = {
    'who': {'ids': ('RC01',), 'paths': ('subject.role',)},
    'zip': {'ids': ('T03',), 'paths': ('comparison.scope.zip',)},
    'age': {'ids': ('MG_AGE',), 'paths': ('medigap.age*',)},
    'birth': {'ids': ('S_AGE65',), 'paths': ('coverage.birth', 'situation.age65')},
    'sex': {'ids': ('MG_SEX',), 'paths': ('medigap.pricingSex',)},
    'tobacco': {'ids': ('MG_TOBACCO',), 'paths': ('medigap.tobaccoCategory',)},
    'parts': {'ids': ('RC04',), 'paths': ()},
    'part_b_start': {'ids': ('RC05',), 'paths': ()},
    'coverage': {'ids': ('T05',), 'paths': ('coverage.current',)},
    'doctors': {'ids': ('T06',), 'paths': ('needs.providers', 'needs.providersStatus')},
    'medicines': {'ids': ('T07',), 'paths': ('needs.medications', 'needs.medicinesStatus')},
    'travel': {'ids': ('T08',), 'paths': ('needs.travel',)},
    'cost_preference': {'ids': ('T09',), 'paths': ('needs.costPreference',)},
    'priorities': {'ids': ('T10',), 'paths': ('needs.priorities',)},
    'plan_year': {'ids': ('RC03',), 'paths': ('comparison.scope.year',)},
}
QUESTION_FACTS = {identifier: key for key, target in FACT_TARGETS.items() for identifier in target['ids']}
# "What would you like help with?" is answered with the person's own ask from the opening.
# It is said, never graded: no corpus holds a structured goal.
QUESTION_FACTS['T01'] = 'goal'

# Other spellings a saved value or a choice may use for the same meaning.
ALIASES = {
    'who': {'self': ('self', 'me', 'myself'),
            'someone': ('someone', 'someoneihelp', 'helper', 'other', 'someoneelse')},
    'sex': {'female': ('female', 'f'), 'male': ('male', 'm')},
    'tobacco': {'no': ('no', 'nontobacco', 'nontobaccouser', 'none', 'never'),
                'yes': ('yes', 'tobaccouser', 'tobacco')},
    'travel': {'local': ('local', 'localonly', 'none', 'no'),
               'elsewhere_us': ('elsewhereus', 'elsewhereintheus'),
               'outside_us': ('outsideus', 'outsidetheus')},
    'cost_preference': {'lower_monthly': ('lowermonthly', 'lowermonthlypayments'),
                        'predictable': ('predictable', 'morepredictablecosts'),
                        'no_preference': ('nopreference', 'nopreferenceyet', 'none')},
    'parts': {'both': ('both', 'aandb'), 'a_only': ('aonly',), 'b_only': ('bonly',),
              'neither': ('neither', 'none'), 'pending': ('pending', 'appliedwaiting')},
}
# How the person says a canonical value when the question offers no choices.
PHRASES = {
    'who': {'self': "It's for me."},
    'sex': {'female': 'Female.', 'male': 'Male.'},
    'tobacco': {'no': 'No tobacco use.', 'yes': 'Yes, tobacco use.'},
    'travel': {'local': 'Local only.', 'elsewhere_us': 'Elsewhere in the U.S. too.',
               'outside_us': 'Outside the U.S. too.'},
    'cost_preference': {'lower_monthly': 'Lower monthly payments.', 'predictable': 'More predictable costs.',
                        'no_preference': 'No preference yet.'},
    'parts': {'both': 'Both Part A and Part B.', 'a_only': 'Part A only.', 'b_only': 'Part B only.',
              'neither': 'Neither part yet.', 'pending': 'Applied and waiting.'},
}
# Words that tie a profile's own script labels, or an id-less question, to a
# fact. Used only when the question carries no usable id.
FACT_WORDS = {
    'who': ('who is this for', 'who the coverage', 'whose coverage'),
    'zip': ('zip', 'county'),
    'birth': ('born', 'birthday', 'birth', 'turn 65'),
    'age': ('how old', 'age'),
    'sex': ('sex',),
    'tobacco': ('tobacco', 'smoke'),
    'part_b_start': ('part b start', 'when did part b'),
    'parts': ('part a', 'part b', 'parts', 'medicare dates', 'medicare enrollment', 'enrolled'),
    'doctors': ('doctor', 'hospital', 'provider'),
    'medicines': ('medicine', 'prescription', 'medication', 'drug'),
    'travel': ('travel', 'away from home'),
    'coverage': ('coverage', 'insurance'),
    'priorities': ('matters most', 'priorit'),
    'cost_preference': ('monthly', 'budget', 'premium'),
    'plan_year': ('which year', 'coverage year'),
}
PRIORITY_IDS = ('doctors', 'drugs', 'total_cost', 'bills', 'travel', 'other')
COVERAGE_WORDS = (('medicare advantage', 'advantage'), ('original medicare', 'original'), ('medigap', 'medigap'),
                  ('drug plan', 'drug'), ('part d', 'drug'), ('cobra', 'cobra'), ('employer', 'employer'),
                  ('retiree', 'retiree'), ('medicaid', 'medicaid'))
MONTHS = ('january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october',
          'november', 'december')
NUMBER_WORDS = {'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12,
                'fifteen': 15, 'twenty': 20, 'thirty': 30, 'forty': 40}
STYLES = ('terse', 'talkative', 'unsure')

DONT_KNOW = "I don't know."
DECLINE = "I'd rather not say."
UNCLEAR = "I'm not sure what you're asking. Could you put it another way?"
NO_REPLY = "I didn't see an answer. Are you still there?"

CLEARANCE_PREFIX = 'Owner clearance:'
CLEARANCE_MESSAGE = ('Live simulated runs need the owner\'s clearance and a budget. Pass the owner\'s own '
                     'clearance text, starting with "' + CLEARANCE_PREFIX + '", and a call limit. '
                     'An agent never starts a live run.')


def norm(value):
    """Lowercase letters and digits only: one spelling for ids, labels and saved values."""
    return re.sub(r'[^a-z0-9]', '', str(value).lower())


def accepted_tokens(key, value):
    """Every normalised spelling that counts as `value` for fact `key`."""
    tokens = {norm(value)}
    tokens.update(ALIASES.get(key, {}).get(str(value).lower(), ()))
    return tokens


def require_clearance(clearance):
    """Raise unless the caller passed the owner's explicit clearance text."""
    if (not isinstance(clearance, str) or not clearance.startswith(CLEARANCE_PREFIX)
            or len(clearance[len(CLEARANCE_PREFIX):].strip()) < 8):
        raise PermissionError(CLEARANCE_MESSAGE)
    return clearance


# ---------------------------------------------------------------------------
# Profile loading: three corpus shapes, one internal shape.
# ---------------------------------------------------------------------------

def _fact(kind, value, say):
    return {'kind': kind, 'value': value, 'say': say}


def _first_sentence(text, limit=220):
    text = str(text or '').strip()
    cut = re.split(r'(?<=[.!?])\s', text, maxsplit=1)[0]
    return cut[:limit]


def _clip(text, limit=220):
    """Whole sentences up to a length a person might type."""
    out = ''
    for sentence in re.split(r'(?<=[.!?])\s', str(text or '').strip()):
        if out and len(out) + len(sentence) + 1 > limit:
            break
        out = (out + ' ' + sentence).strip()
    return out[:limit]


def _name_of(entry):
    """The part of a ground-truth line a person would actually say."""
    text = str(entry).strip()
    text = re.split(r'[,;(]|\s+(?:in|at)\s+', text, maxsplit=1)[0].strip()
    return text.rstrip('.')


def _name_token(name):
    return norm(re.sub(r'^(dr\.?|doctor)\s+', '', name.strip(), flags=re.I))


def _listing(entries, nothing, *, doctors=False):
    """A names fact from a list (or one string) of ground-truth lines."""
    if entries is None:
        return None
    lines = []
    for item in entries if isinstance(entries, list) else [entries]:
        if isinstance(item, dict):
            item = ' '.join(str(item[k]) for k in ('name', 'strength', 'form') if item.get(k))
        if str(item).strip():
            lines.append(str(item).strip())
    if not lines:
        return None
    low = [line.lower() for line in lines]
    if any(norm(line) == 'declines' for line in low):
        return {'kind': 'names', 'value': None, 'say': DECLINE, 'declined': True}
    if all(line.startswith(('not part', 'not yet')) for line in low):
        return None                          # outside this profile's task: not a fact to state
    if all(line.startswith(('none', 'no ')) or norm(line) == 'no' for line in low):
        return _fact('names', [], nothing)
    names = [_name_of(line) for line in lines]
    if doctors:
        return _fact('names', [_name_token(name) for name in names], ', '.join(names) + '.')
    return _fact('names', [norm(name.split(' ')[0]) for name in names],
                 '; '.join(_first_sentence(line).rstrip('.') for line in lines) + '.')


def _doctor_listing(entries):
    return _listing(entries, 'No doctors I need to keep.', doctors=True)


def _birth(date_text):
    match = re.match(r'(\d{4})-(\d{2})', str(date_text or ''))
    if not match:
        return None
    year, month = int(match.group(1)), int(match.group(2))
    if not 1 <= month <= 12:
        return None
    return _fact('month_year', {'year': year, 'month': month}, f'Born in {MONTHS[month - 1].capitalize()} {year}.')


def _month_fact(date_text, label):
    match = re.match(r'(\d{4})-(\d{2})', str(date_text or ''))
    if not match:
        return None
    year, month = int(match.group(1)), int(match.group(2))
    return _fact('month_year', {'year': year, 'month': month, 'exact': True},
                 f'{label} {MONTHS[month - 1].capitalize()} {year}.')


def _choice(key, value):
    value = str(value).strip().lower()
    return _fact('choice', value, PHRASES.get(key, {}).get(value, value.replace('_', ' ').capitalize() + '.'))


def _parts_from_dates(medicare, as_of):
    """Only the unambiguous cases; a start date still ahead stays a say-only fact."""
    a, b = (medicare or {}).get('part_a_start_date'), (medicare or {}).get('part_b_start_date')
    if a is None and b is None:
        return _choice('parts', 'neither')
    if a and b and str(a) <= str(as_of) and str(b) <= str(as_of):
        return _choice('parts', 'both')
    if a and b is None and str(a) <= str(as_of):
        return _choice('parts', 'a_only')
    said = [f'Part {name} starts {value}' for name, value in (('A', a), ('B', b)) if value]
    return _fact('choice', None, '; '.join(said) + '.') if said else None


def _stop_from_text(text):
    match = re.search(r'after (\w+) typist messages', str(text or '').lower())
    if not match:
        return None
    word = match.group(1)
    return int(word) if word.isdigit() else NUMBER_WORDS.get(word)


def _who(helper, relation_words):
    if not helper:
        return _choice('who', 'self')
    return _fact('choice', 'someone', f"It's for my {relation_words}.")


def _relation(person, ground_truth):
    relation = str(person.get('relationship_to_typist') or 'self').lower()
    if relation == 'self':
        return ''
    sex = norm(ground_truth.get('sex_category') or '')
    if relation == 'parent':
        return {'female': 'mother', 'male': 'father'}.get(sex, 'parent')
    return relation


def _goal(opening):
    """The person's own ask: the last question in the opening, else its first words."""
    text = str(opening or '').strip()
    asks = [piece.strip() for piece in re.split(r'(?<=[.!?])\s+', text) if piece.strip().endswith('?')]
    said = asks[-1] if asks else _clip(text)
    return _fact('choice', None, said) if said else None


def _script(entries):
    out = []
    for item in entries or []:
        about = str(item.get('if_asked_about') or '')
        out.append({'about': about, 'reply': str(item.get('reply') or ''),
                    'unprompted': about.lower().startswith('unprompted')})
    return out


def _from_ground_truth(item, corpus):
    """plan-paths (16) and medicare-personas (20): `person`, `ground_truth`, `response_script`."""
    person, truth = item.get('person') or {}, item.get('ground_truth') or {}
    captured = (item.get('expected_sorting') or {}).get('inputs_to_capture') or {}
    relation = _relation(person, truth)
    helper = bool(relation)
    facts = {'who': _who(helper, relation)}
    if _goal(item.get('opening_message')):
        facts['goal'] = _goal(item.get('opening_message'))
    if person.get('zip'):
        facts['zip'] = _fact('number', str(person['zip']), f"ZIP {person['zip']}.")
    if person.get('age') is not None:
        facts['age'] = _fact('number', str(person['age']), f"{person['age']} years old.")
    for key, fact in (('birth', _birth(truth.get('date_of_birth'))),
                      ('parts', _parts_from_dates(truth.get('medicare'), truth.get('as_of_date'))),
                      ('part_b_start', _month_fact((truth.get('medicare') or {}).get('part_b_start_date'), 'Part B start:')),
                      ('medicines', _listing(truth.get('medicines'), 'No prescriptions.')),
                      ('doctors', _doctor_listing(truth.get('doctors')))):
        if fact:
            facts[key] = fact
    sex = captured.get('sex') or truth.get('sex_category')
    if sex and norm(sex) in ('female', 'male'):
        facts['sex'] = _choice('sex', norm(sex))
    if norm(captured.get('tobacco') or '') in ('yes', 'no'):
        facts['tobacco'] = _choice('tobacco', norm(captured['tobacco']))
    elif truth.get('tobacco'):
        facts['tobacco'] = _fact('choice', None, _first_sentence(truth['tobacco']))
    if captured.get('doctors') == 'none':
        facts['doctors'] = _fact('names', [], 'No doctors I need to keep.')
    if captured.get('medicines') == 'no':
        facts['medicines'] = _fact('names', [], 'No prescriptions.')
    travel = {'none': 'local'}.get(captured.get('travel'), captured.get('travel'))
    if travel in ALIASES['travel']:
        facts['travel'] = _choice('travel', travel)
    cost = {'none': 'no_preference'}.get(captured.get('cost_preference'), captured.get('cost_preference'))
    if cost in ALIASES['cost_preference']:
        facts['cost_preference'] = _choice('cost_preference', cost)
    wanted = [part.strip() for part in str(captured.get('priorities') or '').split(',') if part.strip()]
    preference_text = next((truth[k] for k in truth if 'preferences' in k and isinstance(truth[k], str)), '')
    if wanted and all(part in PRIORITY_IDS for part in wanted):
        facts['priorities'] = _fact('multi', wanted, ' and '.join(part.replace('_', ' ') for part in wanted).capitalize() + '.')
    elif preference_text:
        facts['priorities'] = _fact('multi', None, _clip(preference_text))
    covered = str(captured.get('current_coverage') or '')
    if covered:
        low = covered.lower()
        ids = ['none'] if low.startswith('none') else list(dict.fromkeys(
            choice for words, choice in COVERAGE_WORDS if words in low))
        facts['coverage'] = _fact('subset', ids or None, _first_sentence(truth.get('current_coverage'))
                                  or re.split(r'[;(]', covered)[0].strip().rstrip('.') + '.')
    elif truth.get('current_coverage'):
        facts['coverage'] = _fact('subset', None, _first_sentence(truth['current_coverage']))
    return {
        'id': item['id'], 'corpus': corpus, 'name': person.get('name') or item['id'],
        'typist': 'helper' if helper else 'self', 'relation': relation,
        'opening': item.get('opening_message') or '', 'facts': facts,
        'script': _script(item.get('response_script')),
        'stop': {'max_messages': _stop_from_text(item.get('stop_rule')), 'repeat_limit': None,
                 'text': item.get('stop_rule') or ''},
        'brief': {'situation': item.get('archetype') or '', 'private': copy.deepcopy(truth),
                  'disclosure': 'Answer the question asked, briefly, in this person\'s voice. '
                                'Say "I\'m not sure" when the profile does not say.'},
        # Kept for graders and reports only. Never placed in a person prompt.
        'answer_key': copy.deepcopy(item.get('answer_key') or {}),
    }


_BEAT_QUOTE = re.compile(r'[“"]([^”"]{3,})[”"]')


def _from_journey(item):
    """behavioral-journeys (12): `opening`, `private_facts`, `disclosure_policy`, `beats`."""
    private = item.get('private_facts') or {}
    helper = bool(private.get('helper')) or norm(private.get('subject') or 'self') != 'self'
    facts = {'who': _who(helper, 'mother' if any(k.startswith('mother') for k in private) else 'family member')}
    if _goal(item.get('opening')):
        facts['goal'] = _goal(item.get('opening'))

    def pick(*names):
        return next((private[name] for name in names if name in private), None)

    def declined(value):
        return isinstance(value, str) and norm(value) == 'declines'

    for key, value, make in (
            ('zip', pick('zip_corrected', 'zip'), lambda v: _fact('number', str(v), f'ZIP {v}.')),
            ('age', pick('age'), lambda v: _fact('number', str(v), f'{v} years old.')),
            ('sex', pick('pricing_sex', 'sex'), lambda v: _choice('sex', norm(v)) if norm(v) in ('female', 'male') else None),
            ('tobacco', pick('tobacco'), lambda v: _choice('tobacco', norm(v)) if norm(v) in ('yes', 'no') else None),
            ('plan_year', pick('requested_year'), lambda v: _fact('number', str(v), f'{v}.')),
            ('coverage', pick('coverage', 'current_coverage', 'current', 'mother_coverage'),
             lambda v: _fact('subset', None, str(v).rstrip('.') + '.')),
            ('priorities', pick('revised_priority', 'priority', 'mother_priority'),
             lambda v: _fact('multi', None, str(v).rstrip('.').capitalize() + '.'))):
        if value is None:
            continue
        if declined(value):
            facts[key] = {'kind': 'choice', 'value': None, 'say': DECLINE, 'declined': True}
            continue
        fact = make(value)
        if fact:
            facts[key] = fact
    parts = pick('parts')
    if isinstance(parts, str):
        low = parts.lower().strip()
        value = ('neither' if low.startswith('neither') else 'a_only' if low.startswith('part a only')
                 else 'both' if low.startswith('both active') else None)
        facts['parts'] = _choice('parts', value) if value else _fact('choice', None, parts.rstrip('.') + '.')
    for key, names, nothing, maker in (
            ('medicines', ('medicines', 'medicine', 'mother_medicine'), 'No prescriptions.', _listing),
            ('doctors', ('doctors', 'doctor'), 'No doctors I need to keep.', None)):
        value = pick(*names)
        if value is None:
            continue
        fact = _listing(value, nothing, doctors=maker is None)
        if fact:
            facts[key] = fact
    script = []
    for beat in item.get('beats') or []:
        quote = _BEAT_QUOTE.search(str(beat.get('action') or ''))
        script.append({'about': 'Unprompted, ' + str(beat.get('kind') or ''), 'reply': quote.group(1) if quote else '',
                       'unprompted': True, 'beat': beat.get('id'), 'typed': bool(quote)})
    budget = item.get('budget') or {}
    return {
        'id': item['id'], 'corpus': 'behavioral-journeys', 'name': item.get('name') or item['id'],
        'typist': 'helper' if helper else 'self', 'relation': 'family member' if helper else '',
        'opening': item.get('opening') or '', 'facts': facts,
        # Beats without typed words are screen actions; this typed-message harness cannot perform them.
        'script': [entry for entry in script if entry['typed']],
        'skipped_beats': [entry['beat'] for entry in script if not entry['typed']],
        'stop': {'max_messages': budget.get('user_actions_hard'),
                 'repeat_limit': budget.get('repeat_same_unanswered_request'), 'text': ''},
        'brief': {'situation': ' '.join(str(item.get(k) or '') for k in ('primary_behavior', 'coverage_context', 'goal')).strip(),
                  'private': copy.deepcopy(private),
                  'disclosure': item.get('disclosure_policy') or ''},
        'answer_key': {'finish': copy.deepcopy(item.get('finish') or {}),
                       'decision_policy': item.get('decision_policy') or ''},
    }


def normalise(item):
    """One corpus entry -> the internal profile shape."""
    if isinstance(item, dict) and 'facts' in item and 'opening' in item:
        profile = copy.deepcopy(item)                      # already internal (tests, hand-made profiles)
        profile.setdefault('corpus', 'internal')
        profile.setdefault('name', profile['id'])
        profile.setdefault('typist', 'self')
        profile.setdefault('relation', '')
        profile.setdefault('script', [])
        profile.setdefault('stop', {'max_messages': None, 'repeat_limit': None, 'text': ''})
        profile.setdefault('brief', {'situation': '', 'private': {}, 'disclosure': ''})
        profile.setdefault('answer_key', {})
        if 'goal' not in profile['facts'] and _goal(profile['opening']):
            profile['facts']['goal'] = _goal(profile['opening'])
        return profile
    if isinstance(item, dict) and 'private_facts' in item:
        return _from_journey(item)
    if isinstance(item, dict) and 'ground_truth' in item:
        return _from_ground_truth(item, 'plan-paths' if 'expected_sorting' in item else 'medicare-personas')
    raise ValueError('Unrecognised profile shape.')


def load_profiles(path):
    """Read a profile file (or its folder) and return internal profiles, in file order."""
    path = Path(path)
    if path.is_dir():
        path = next((path / name for name in ('profiles.json', 'personas.json') if (path / name).is_file()), path)
    data = json.loads(path.read_text(encoding='utf-8'))
    items = data.get('profiles') if isinstance(data, dict) else data
    if not isinstance(items, list) or not items:
        raise ValueError('The profile file holds no profiles.')
    return [normalise(item) for item in items]


def opening_states(profile):
    """Facts the opening message states, as far as code can tell without reading meaning.

    A profile may list them (`opening_states`). Otherwise only literal matches
    count: the ZIP, and the age when it follows words such as "I'm" or "is".
    """
    if isinstance(profile.get('opening_states'), list):
        return [key for key in profile['opening_states'] if key in profile['facts']]
    return _literal_states(profile, profile.get('opening') or '')


def _literal_states(profile, text):
    found = []
    zip_fact, age_fact = profile['facts'].get('zip'), profile['facts'].get('age')
    if zip_fact and zip_fact.get('value') and re.search(r'(?<!\d)' + re.escape(zip_fact['value']) + r'(?!\d)', text):
        found.append('zip')
    if age_fact and age_fact.get('value') and re.search(
            r"(?i)\b(?:i'm|i am|she's|he's|she is|he is|is|age|aged)\s+" + re.escape(age_fact['value']) + r'(?!\d)', text):
        found.append('age')
    return found


# ---------------------------------------------------------------------------
# Question reading
# ---------------------------------------------------------------------------

def read_question(question):
    """Any question shape -> {'id', 'text', 'choices': [(id, label)]} or None."""
    if not question:
        return None
    if isinstance(question, str):
        return {'id': None, 'text': question.strip(), 'choices': []} if question.strip() else None
    if not isinstance(question, dict):
        return None
    identifier = question.get('id') or question.get('target')
    text = str(question.get('question') or question.get('text') or '').strip()
    choices = []
    for choice in question.get('choices') or []:
        if isinstance(choice, (list, tuple)) and len(choice) >= 2:
            choices.append((str(choice[0]), str(choice[1])))
        elif isinstance(choice, dict) and choice.get('id') is not None:
            choices.append((str(choice['id']), str(choice.get('label') or choice['id'])))
    if not identifier and not text:
        return None
    return {'id': str(identifier) if identifier else None, 'text': text, 'choices': choices}


def _key_from_words(text):
    low = ' ' + str(text or '').lower() + ' '
    for key, words in FACT_WORDS.items():
        if any(word in low for word in words):
            return key
    return None


# ---------------------------------------------------------------------------
# The offline person
# ---------------------------------------------------------------------------

class ScriptedPerson:
    """Answers what was asked, from ground truth. No model, no network."""

    def __init__(self, profile, *, seed=0, style=None, max_messages=None):
        if style is not None and style not in STYLES:
            raise ValueError('Unknown style.')
        self.profile = profile
        self.seed = seed
        self.style = style or STYLES[seed % len(STYLES)]
        self.random = random.Random(f"{profile['id']}:{seed}")
        self.max_messages = max_messages
        self.sent = 0
        self.stated = set()                      # every fact key said so far
        self.last = {'kind': None, 'stated': [], 'answered': None}
        self.asked = {}                          # question key -> times answered
        self._unprompted = [entry for entry in profile.get('script') or [] if entry.get('unprompted') and entry.get('reply')]
        self._used_replies = set()
        self._idle = 0

    # -- public ----------------------------------------------------------
    def opening(self):
        text = self.profile.get('opening') or 'Hello.'
        return self._send(text, 'opening', opening_states(self.profile), None)

    def answer(self, reply_text, question):
        """The next thing this person types, or None when the person stops."""
        if self.max_messages is not None and self.sent >= self.max_messages:
            return None
        asked = read_question(question)
        remaining = None if self.max_messages is None else self.max_messages - self.sent
        if self._unprompted and remaining is not None and remaining <= len(self._unprompted):
            return self._say_unprompted()        # the profile's own questions always get sent
        if asked is None:
            return self._nothing_asked(reply_text)
        self._idle = 0
        key = asked['id'] or 'text:' + norm(asked['text'])
        limit = (self.profile.get('stop') or {}).get('repeat_limit')
        if limit and self.asked.get(key, 0) >= limit:
            return None                          # the same request, already answered that many times
        fact_key = QUESTION_FACTS.get(asked['id']) if asked['id'] else None
        if fact_key is None and not asked['id']:
            fact_key = _key_from_words(asked['text'])
            if fact_key is None:
                return self._send(UNCLEAR, 'unclear', [], key)
        fact = self.profile['facts'].get(fact_key) if fact_key else None
        if fact is None:
            given = (self.profile.get('answers') or {}).get(asked['id']) if asked['id'] else None
            if given is not None:
                tokens = {norm(given)}
                label = next((label for identifier, label in asked['choices']
                              if norm(identifier) in tokens or norm(label) in tokens), None)
                self.asked[key] = self.asked.get(key, 0) + 1
                return self._send(label or str(given), 'answer', [], key)
            scripted = self._scripted_reply(_key_from_words(asked['text']))
            if scripted:
                return self._send(scripted, 'answer', _literal_states(self.profile, scripted), key)
            return self._send(DONT_KNOW, 'unknown', [], key)
        if fact.get('declined'):
            return self._send(DECLINE, 'declined', [], key)
        if self.style == 'unsure' and self.random.random() < 0.3:
            return self._send(DONT_KNOW, 'unknown', [], key)
        self.asked[key] = self.asked.get(key, 0) + 1
        text, said = self._fact_answer(fact_key, fact, asked)
        if self.style == 'talkative':
            extra = self._extra_fact(exclude={fact_key, *said})
            if extra:
                text = text.rstrip() + ' Also: ' + self.profile['facts'][extra]['say']
                said = [*said, extra]
        return self._send(text, 'answer', said, key)

    # -- internals -------------------------------------------------------
    def _send(self, text, kind, stated, answered):
        self.sent += 1
        stated = list(dict.fromkeys(stated))
        self.stated.update(stated)
        self.last = {'kind': kind, 'stated': stated, 'answered': answered if kind == 'answer' else None}
        return text

    def _say_unprompted(self):
        entry = self._unprompted.pop(0)
        return self._send(entry['reply'], 'unprompted', _literal_states(self.profile, entry['reply']), None)

    def _nothing_asked(self, reply_text):
        if self._unprompted:
            self._idle = 0
            return self._say_unprompted()
        if self._idle >= 1:
            return None                          # nothing asked twice running and nothing left to say
        self._idle += 1
        if not str(reply_text or '').strip():
            return self._send(NO_REPLY, 'unclear', [], None)
        return self._send('Okay. What should I do next?', 'unclear', [], None)

    def _scripted_reply(self, fact_key):
        if not fact_key:
            return None
        for index, entry in enumerate(self.profile.get('script') or []):
            if entry.get('unprompted') or index in self._used_replies or not entry.get('reply'):
                continue
            if any(word in entry['about'].lower() for word in FACT_WORDS.get(fact_key, ())):
                self._used_replies.add(index)
                return entry['reply']
        return None

    def _fact_answer(self, fact_key, fact, asked):
        """(text, stated keys) for one fact, by choice when the question offers choices."""
        value = fact.get('value')
        if asked['choices'] and value is not None and fact['kind'] in ('choice', 'multi', 'subset', 'names'):
            wanted = value if isinstance(value, list) else [value]
            if fact['kind'] == 'names':
                wanted = ['none', 'no'] if not value else []
            labels = []
            for item in wanted:
                tokens = accepted_tokens(fact_key, item)
                label = next((label for identifier, label in asked['choices']
                              if norm(identifier) in tokens or norm(label) in tokens), None)
                if label and label not in labels:
                    labels.append(label)
                    if fact['kind'] == 'names':
                        break
            if labels and (fact['kind'] == 'names' or len(labels) == len(wanted)):
                return ' and '.join(labels), [fact_key]
        if self.style == 'talkative':
            scripted = self._scripted_reply(fact_key)
            if scripted:
                return scripted, [fact_key, *_literal_states(self.profile, scripted)]
        return fact['say'], [fact_key]

    def _extra_fact(self, exclude):
        open_keys = [key for key, fact in self.profile['facts'].items()
                     if key not in self.stated and key not in exclude and fact.get('value') is not None
                     and not fact.get('declined') and key != 'who']
        return self.random.choice(sorted(open_keys)) if open_keys else None


# ---------------------------------------------------------------------------
# The live person: refused unless the owner cleared it.
# ---------------------------------------------------------------------------

PERSON_SCHEMA_NAME = 'daylight_sim_person'
PERSON_SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['message', 'stated', 'stop'],
    'properties': {
        'message': {'type': 'string'},
        'stated': {'type': 'array', 'items': {'type': 'string', 'enum': sorted([*FACT_TARGETS, 'goal'])}},
        'stop': {'type': 'boolean'},
    },
}
PERSON_INSTRUCTIONS = (
    'You are playing one fictional person in a private software test. The other side is a coverage advisor.\n'
    'Type only what this person would type next: short, natural, in their own voice.\n'
    'Answer the question the advisor actually asked. Use only the private facts in the persona brief.\n'
    'If the brief does not hold the answer, say you do not know. If the brief says the person declines, decline.\n'
    'Do not volunteer the whole profile, do not repeat a fact to rescue the advisor, and do not invent facts.\n'
    'Do not act as an expert, grade the advisor or mention that this is a test.\n'
    'When the person would ask their own question from the brief, ask it at a natural pause.\n'
    'Set "stated" to the fact keys from the brief that this message discloses. '
    'Set "stop" to true, with an empty message, when this person would end the conversation.'
)


def persona_brief(profile):
    """What a model playing this person may see. The answer key is never part of it."""
    return {
        'name': profile.get('name'),
        'typing': 'a helper typing for someone else' if profile.get('typist') == 'helper' else 'the person themself',
        'relation_to_covered_person': profile.get('relation') or 'self',
        'situation': (profile.get('brief') or {}).get('situation') or '',
        'facts': {key: fact['say'] for key, fact in profile['facts'].items()},
        'private_facts': copy.deepcopy((profile.get('brief') or {}).get('private') or {}),
        'disclosure_style': (profile.get('brief') or {}).get('disclosure') or '',
        'own_questions': [entry['reply'] for entry in profile.get('script') or [] if entry.get('unprompted') and entry.get('reply')],
        'stop_rule': (profile.get('stop') or {}).get('text') or '',
    }


class ModelPerson:
    """A person played by a model. Construction is refused without the owner's clearance.

    There is no network code here: every request goes through `client.transport`,
    which the caller injects. Nothing in this package builds a live transport.
    """

    def __init__(self, profile, client, *, clearance=None, max_calls=40, seed=0):
        self.clearance = require_clearance(clearance)
        if not callable(getattr(client, 'transport', None)):
            raise ValueError('ModelPerson needs a client with an injected transport.')
        if not isinstance(max_calls, int) or max_calls < 1:
            raise ValueError('ModelPerson needs a positive call limit.')
        self.profile, self.client, self.max_calls, self.seed = profile, client, max_calls, seed
        self.style = 'model'
        self.calls = 0
        self.transcript = []
        self.last = {'kind': None, 'stated': [], 'answered': None}

    def opening(self):
        text = self.profile.get('opening') or 'Hello.'
        self.transcript.append({'role': 'person', 'text': text})
        self.last = {'kind': 'opening', 'stated': opening_states(self.profile), 'answered': None}
        return text

    def request(self, reply_text, question):
        """The exact request for the next message (also what a test inspects)."""
        asked = read_question(question)
        turn = {'persona': persona_brief(self.profile), 'transcript': self.transcript,
                'advisor_reply': str(reply_text or ''),
                'advisor_question': None if asked is None else {
                    'id': asked['id'], 'text': asked['text'], 'choices': [label for _, label in asked['choices']]}}
        return {'model': getattr(self.client, 'model', None), 'instructions': PERSON_INSTRUCTIONS,
                'input': [{'role': 'user', 'content': json.dumps(turn, sort_keys=True, ensure_ascii=False)}],
                'store': False, 'tools': [], 'max_output_tokens': 300,
                'text': {'format': {'type': 'json_schema', 'name': PERSON_SCHEMA_NAME, 'strict': True,
                                    'schema': PERSON_SCHEMA}}}

    def answer(self, reply_text, question):
        if self.calls >= self.max_calls:
            return None
        asked = read_question(question)
        self.transcript.append({'role': 'advisor', 'text': ' '.join(
            part for part in (str(reply_text or '').strip(), asked['text'] if asked else '') if part)})
        self.calls += 1
        result = self.client.transport(self.request(reply_text, question))
        try:
            text = next(part['text'] for item in result['output'] for part in item.get('content') or []
                        if part.get('type') == 'output_text')
            value = json.loads(text)
            message, stop = str(value['message']).strip(), bool(value['stop'])
            stated = [key for key in value['stated'] if key in self.profile['facts']]
        except (KeyError, TypeError, ValueError, StopIteration):
            raise RuntimeError('person_model_format') from None
        if stop or not message:
            return None
        self.transcript.append({'role': 'person', 'text': message})
        key = None if asked is None else asked['id'] or 'text:' + norm(asked['text'])
        self.last = {'kind': 'answer' if asked else 'unprompted', 'stated': stated,
                     'answered': key if stated else None}
        return message
