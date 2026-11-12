"""D130 local reported pricing inputs; independent of the sealed 41 meanings.

No rates, eligibility, carrier definitions or demographic guesses are stored here.
D137: the person reports their age in ordinary words; the listed November 10 prices
are matched to that reported age, and a 64-year-old is shown age-65 prices.
"""
import copy
from datetime import datetime
import re
from zoneinfo import ZoneInfo

DATE = '2026-11-10'
FIELDS = {'MG_AGE': 'medigap.ageOn20261110', 'MG_SEX': 'medigap.pricingSex',
          'MG_TOBACCO': 'medigap.tobaccoCategory'}
LABELS = {'MG_AGE': 'Age reported for Medigap pricing', 'MG_SEX': 'Sex used for Medigap pricing',
          'MG_TOBACCO': 'Medigap tobacco category'}
DEFINITIONS = {
    'MG_AGE': ('How old are you?',
        'The pilot prices cover ages 65–74. Your age helps us match the listed prices. For someone who is 64, prices are shown for age 65.', []),
    'MG_SEX': ('Which sex category should we use for Medigap prices?',
        'The price source uses Female and Male categories. Choose the category to use for this lookup, or leave it unknown.',
        [['Female', 'Female'], ['Male', 'Male']]),
    'MG_TOBACCO': ('Which tobacco category should we use for Medigap prices?',
        'The source lists separate tobacco and non-tobacco prices. If you stopped recently or are unsure which category applies, choose I don’t know. Insurer requirements still need checking.',
        [['Non-Tobacco', 'Non-tobacco user'], ['Tobacco User', 'Tobacco user']]),
}
CATALOG = {key: {'id': key, 'question': text, 'why': why, 'choices': choices,
    'fieldNames': ['choice'], 'requiredness': why, 'kind': 'local_pricing'}
    for key, (text, why, choices) in DEFINITIONS.items()}


TURNING_65_NOTE = ('You reported age 64. These are the listed prices for age 65, '
                   'the age most people can first buy Medigap.')
_FEMALE, _MALE = r'(?:woman|lady)', r'(?:man|gentleman)'


def question(identifier, role=None):
    item = CATALOG[identifier]
    wording = ('How old is the person receiving coverage?'
               if identifier == 'MG_AGE' and role == 'someone' else item['question'])
    return {'id': identifier, 'entity': 'profile', 'question': wording,
            'why': item['why'], 'choices': copy.deepcopy(item['choices']),
            'fields': [], 'multi': False, 'signature': 'medigap-profile-v1:' + identifier}


def parse(identifier, fields):
    if not isinstance(fields, dict) or set(fields) != {'choice'}:
        raise ValueError('Answer only the Medigap detail being asked.')
    value = fields['choice']
    if not isinstance(value, str):
        raise ValueError('Use a supported Medigap answer.')
    if value in {'unknown', 'deferred'}:
        return value
    if identifier == 'MG_AGE' and re.fullmatch(r'\d{1,3}', value) and 0 <= int(value) <= 120:
        return int(value)
    if identifier != 'MG_AGE' and value in dict(CATALOG[identifier]['choices']):
        return value
    raise ValueError('Use an age from 0 to 120 or one of the displayed categories.')


def validate(guide):
    for identifier, name in FIELDS.items():
        item = guide.get('fields', {}).get(name)
        if item is None:
            continue
        value = item.get('value')
        if (identifier == 'MG_AGE' and type(value) is int and 0 <= value <= 120
                or isinstance(value, str) and parse(identifier, {'choice': value}) == value):
            continue
        raise ValueError('Use a supported reported Medigap profile value.')


def usable(guide, field):
    item = guide.get('fields', {}).get(field, {})
    value = item.get('value') if item.get('status') in {'reported', 'derived'} else None
    return None if value in ('unknown', 'deferred') else value


def birthday_source(guide):
    fields = guide.get('fields', {})
    name = max(('situation.age65', 'coverage.birth'), key=lambda key: fields.get(key, {}).get('revision', -1))
    revision = fields.get(name, {}).get('revision', 0)
    if name == 'coverage.birth':
        revision = max(revision, fields.get('coverage.birth.firstDay', {}).get('revision', 0))
    return name, revision


def birthday_age(guide):
    """Reuse the latest birthday report only when it proves an exact age."""
    name, _ = birthday_source(guide)
    value = usable(guide, name)
    if name == 'coverage.birth' and isinstance(value, str) and re.fullmatch(r'(?:19|20)\d{2}-(?:0[1-9]|1[0-2])', value):
        value = {'month': int(value[5:]), 'year': int(value[:4]) + 65,
                 'first_day': usable(guide, 'coverage.birth.firstDay') in (True, 'yes')}
    if not isinstance(value, dict) or type(value.get('year')) is not int:
        return None
    month = value.get('month')
    if type(month) is not int or not 1 <= month <= 12:
        return None
    if month == 11 and value.get('first_day') is not True:
        # A later November birthday may be before or after the 10th. Someone
        # turning 65 that month is priced at 65 either way (D137).
        return 64 if value['year'] == 2026 else None
    years = 65 + 2026 - value['year'] - (month > 11)
    return years if 0 <= years <= 120 else None


def profile(guide):
    role = usable(guide, 'subject.role')
    values = {key: usable(guide, name) for key, name in FIELDS.items()}
    # An explicit unknown/correction supersedes birthday arithmetic too.
    age_report = guide.get('fields', {}).get(FIELDS['MG_AGE'], {})
    _, birthday_revision = birthday_source(guide)
    if not age_report or (age_report.get('status') in {'reported', 'stale'}
            and birthday_revision > age_report.get('revision', 0)):
        values['MG_AGE'] = birthday_age(guide)
    zip_code = usable(guide, 'comparison.scope.zip')
    # D137: a 64-year-old turns 65 within the year, so the listed age-65
    # prices are the relevant reference. The reported age stays visible.
    turning = values['MG_AGE'] == 64 and type(values['MG_AGE']) is int
    inputs = {'zipcode': zip_code, 'age': 65 if turning else values['MG_AGE'],
              'gender': values['MG_SEX'], 'tobacco': values['MG_TOBACCO']}
    note = TURNING_65_NOTE if turning else ''
    message = ''
    if isinstance(values['MG_AGE'], int) and values['MG_AGE'] >= 75:
        message = 'Medigap pricing for ages 75+ is not supported in this pilot.'
    elif isinstance(values['MG_AGE'], int) and values['MG_AGE'] < 64:
        message = 'Medigap pricing in this pilot supports ages 65–74, and age 64 for people about to turn 65. Younger ages are not supported.'
    elif zip_code and zip_code not in {str(z) for z in range(34101, 34109)}:
        message = 'Medigap pricing in this pilot supports ZIP codes 34101–34108.'
    missing = []
    if role not in {'self', 'someone'}:
        missing.append('RC01')
    if not zip_code:
        missing.append('T03')
    missing.extend(key for key in FIELDS if values[key] is None)
    held = [key for key, name in FIELDS.items()
            if guide.get('fields', {}).get(name, {}).get('status') in {'unknown', 'skipped'}]
    return {'effective_date': DATE, 'inputs': inputs,
            'status': 'unsupported' if message else 'missing' if missing else 'ready',
            'message': message, 'note': '' if message else note, 'missing': missing, 'held': held,
            'questions': [question(key, role) for key in missing if key in FIELDS and key not in held] if not message else [],
            'edit_questions': [question(key, role) for key in FIELDS],
            'details': [{'id': key, 'label': LABELS[key], 'value': values[key],
                         'status': guide.get('fields', {}).get(name, {}).get('status', 'missing')}
                        for key, name in FIELDS.items()]}


def validate_proposal(update, message, role, active=None, today=None):
    """Validate a model proposal's literal support, never infer a category."""
    required = {'id', 'entity', 'fields', 'quote', 'subject', 'scope', 'uncertain', 'correction'}
    if not isinstance(update, dict) or set(update) != required or update['id'] not in FIELDS:
        raise ValueError('Unsupported Medigap report.')
    if update['entity'] != 'profile' or update['subject'] != 'beneficiary' or update['scope'] != 'current':
        raise ValueError('A Medigap report must concern the current beneficiary.')
    if type(update['uncertain']) is not bool or type(update['correction']) is not bool:
        raise ValueError('Use explicit report scope.')
    quote = update['quote']
    if not isinstance(quote, str) or not quote.strip() or len(quote) > 600 or quote.casefold() not in message.casefold():
        raise ValueError('Use the person’s exact supporting words.')
    fields = update['fields']
    if not isinstance(fields, list) or len(fields) != 1 or set(fields[0]) != {'key', 'value'} or fields[0]['key'] != 'choice':
        raise ValueError('Use one explicit Medigap answer.')
    value = parse(update['id'], {'choice': fields[0]['value']})
    text = quote.replace('’', "'").casefold()
    asked = bool(active and active.get('id') == update['id'] and role in {'self', 'someone'})
    if '?' in text or re.search(r'\b(?:if|suppose|hypothetically|for example)\b', text):
        raise ValueError('A question or example is not a report.')
    # Helper statements must explicitly name the beneficiary, or answer the
    # displayed beneficiary question without first-person helper attributes.
    named = bool(re.search(r"\b(?:my|the) (?:mother|father|mom|dad|parent|spouse|wife|husband|person|beneficiary)\b", text))
    first = bool(re.search(r"\b(?:i|i'm|my age|my sex|my tobacco)\b", text))
    if role not in {'self', 'someone'} or role == 'someone' and (first or not (named or asked)) or role == 'self' and named:
        raise ValueError('Establish whose pricing detail this is.')
    if value in {'unknown', 'deferred'}:
        named_field = re.search({'MG_AGE': r'\bage\b', 'MG_SEX': r'\bsex\b',
                                 'MG_TOBACCO': r'\btobacco\b'}[update['id']], text)
        if not (asked or named_field) or not re.search(r"don't know|do not know|not sure|unknown|later|skip|defer|prefer not", text):
            raise ValueError('Leave only the explicitly identified detail open.')
        return copy.deepcopy(update)
    if update['id'] == 'MG_AGE':
        number = r'(?<!\d)' + str(value) + r'(?!\d)'
        if not re.search(number, text):
            raise ValueError('Age must be stated exactly.')
        # D137: judge the construction around the number itself. Unrelated
        # words elsewhere in the quote ("retiring next month") are not a
        # reason to discard a plainly stated age.
        if (re.search(r"\b(?:turn|turning|turns|will be|about to be|going to be|almost|nearly|under|over)\s+(?:be\s+)?" + number, text)
                or re.search(r"\b(?:used to be|was)\s+" + number + r"\s+(?:when|back|last|in)\b", text)
                or re.search(number + r"\s+next\s+(?:year|month|week|birthday)\b", text)):
            raise ValueError('Do not turn future or past ages into the current age.')
        if not asked and not re.search(r"\b(?:age|aged|years? old|year[- ]old|i am|i'm|i was|turned|is|was)\b", text):
            raise ValueError('A number alone needs the active age question.')
    elif update['id'] == 'MG_SEX':
        literal = re.search(r'\b' + value.casefold() + r'\b', text)
        word = _FEMALE if value == 'Female' else _MALE
        # D137: "I'm a woman" is the person's own statement of the category.
        # Names, pronouns and relatives' roles still establish nothing.
        own = (re.search(r"\b(?:i'm|i am|she's|she is|he's|he is)\b[^.?!;]*\b" + word + r'\b', text)
               or asked and re.search(r'\b' + word + r'\b', text))
        if (not (literal or own) or re.search(r"\bnot\s+(?:an?\s+)?(?:" + value.casefold() + '|' + word + ')', text)):
            raise ValueError('Do not infer a pricing sex category from names, pronouns or gender identity.')
    else:
        negative = bool(re.search(r"\b(?:non[- ]tobacco|(?:don't|do not|doesn't|does not|never) (?:use|uses|used) (?:any )?tobacco|no tobacco"
                                  r"|non[- ]?smoker|(?:don't|do not|doesn't|does not) smoke|never smoked)\b", text))
        positive = bool(re.search(r"\b(?:tobacco user|(?:use|uses) tobacco)\b|(?<!non-)(?<!non )(?<!non)\bsmoker\b|\b(?:i|he|she) smokes?\b", text))
        if re.search(r'\b(?:quit|stopped|former|used to)\b', text) or not (negative if value == 'Non-Tobacco' else positive and not negative):
            raise ValueError('Smoking history alone does not establish a tobacco price category.')
    return copy.deepcopy(update)
