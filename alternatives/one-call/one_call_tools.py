"""Tools for the one-call loop: schemas and the runner that executes them.

Every tool wraps advisor-first's deterministic code. The model proposes what the
person reported; the existing gates (`classify_update`, `flow.capture`,
`classify_situation`, `validate_coverage_reports`) decide what is saved. Every
date, check and plan result is computed by existing code from the saved reports.
Nothing here writes a rule, an amount or a ranking of its own.

The runner works on its own copies of the guide and record. A save that the
gates refuse leaves both unchanged. Logs carry fixed text, a tool name from the
fixed list and an exception class name; never a message, value or argument.
"""
import _paths  # noqa: F401  (puts advisor-first on sys.path and registers the pinned engine)

import calendar
import copy
from datetime import date, datetime
from decimal import Decimal
import json
import logging
import os
import re

from adaptive_flow import LABELS as FIELD_LABELS, metadata, month as normal_month
from advisor_memory import CONTEXT_POLICY
from guest_profiles import ProfileError
from identifier_guard import find_identifiers
from natural_flow import FIELD, Q
from natural_state import FIELD_NAMES, classify_update, legacy_projection, record_capture
from contextual_capture import classify_situation
from situation import FIELDS as SITUATION_FIELDS, birthday_first_day
from turn_contract import question_binding
import conversation_planner
import conversation_records
import enrollment_flow
import enrollment_journey
import medigap_profile
import ux_flow
import ux_pass

LOGGER = logging.getLogger(__name__)

SITUATION_IDS = ('S_AGE65', 'S_RETIREMENT')
# Reports advisor-first keeps outside the question catalog (its "coverage reports").
COVERAGE_IDS = {'COV_PART_A': 'part_a', 'COV_PART_B': 'part_b', 'COV_PLAN': 'held_plan'}
# RC28 is advisor-first's own correction step, valid only while that step is the active question.
SAVE_IDS = tuple(identifier for identifier in conversation_records.PROFILE_FIELDS if identifier != 'RC28') + tuple(COVERAGE_IDS)
MULTI_CHOICE = frozenset({'T05', 'T08', 'T10', 'RC18'})
DATE_FIELDS = frozenset({'month', 'jobEnd', 'coverageEnd', 'eventDate', 'start'})
OPEN_VALUES = frozenset({'unknown', 'deferred', 'not sure', 'check later'})
SUBJECTS = ('beneficiary', 'learner', 'unclear')
SCOPES = ('current', 'intended', 'historical', 'unknown')
CARD_KINDS = ('enrollment_timing', 'medigap_window', 'two_paths', 'signup_route', 'coverage_now',
              'trade_off', 'trial_right', 'discussion_paths', 'finish_summary')
# Cards whose sentences come from advisor-first's enrollment-content.json. That file is awaiting the
# owner's sign-off and is marked for :8895 only, so these kinds are off here until the owner accepts
# the statements for this surface and sets the switch.
STATEMENT_CARD_KINDS = frozenset({'two_paths', 'signup_route', 'trade_off', 'discussion_paths', 'finish_summary'})
STATEMENTS_SWITCH = 'DAYLIGHT_ONE_CALL_ENROLLMENT_STATEMENTS_ACCEPTED'
# The only reasons for which code itself asks the person to confirm a report before saving it.
CONFIRMED_BY_CODE = frozenset({'subject_change', 'conflicting_report'})
# A goal that means the person wants coverage work done, as advisor-first's planner reads it.
WORK_GOALS = ('compare', 'review')
MAX_UPDATES = 24
MAX_TEXT = 1800
# A server may attach the deterministic engine here: callable(inputs, *, checks, expected_doctors, reported).
RECOMMENDATION_HOOK = 'one_call_recommendation'

BASIS = {
    'reported': 'Reported by the person.',
    'birthday': 'Estimated by code from the reported 65th-birthday month.',
    'job_dates': 'Computed by code from the reported job and coverage end dates.',
    'part_b_reported': 'Computed by code from the reported Part B start.',
}


# ---------------------------------------------------------------------------
# Tool schemas (Responses API function tools, strict)
# ---------------------------------------------------------------------------

def _object(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


def _tool(name, description, properties):
    return {'type': 'function', 'name': name, 'description': description,
            'parameters': _object(properties), 'strict': True}


TOOLS = [
    _tool('save_profile_fields',
          'Save what the person reported in their latest message. One update per meaning in the field catalog. '
          'quote is the exact words from that message that state it. Use the value "unknown" when the person says '
          'they do not know and "deferred" when they want to leave it for later. Set correction to true only when '
          'the person is changing something already on record. Returns one outcome per update (accepted, '
          'already_known, needs_confirmation or rejected, with a reason code) and the ids still open.',
          {'updates': {'type': 'array', 'items': _object({
              'id': {'type': 'string', 'enum': list(SAVE_IDS)},
              'entity': {'type': ['string', 'null'],
                         'description': 'null for the profile. For RC21, RC22 and RC23: an existing item id such as '
                                        'doctor-1 or medicine-2, or "new" for a newly named item.'},
              'fields': {'type': 'array', 'items': _object({'key': {'type': 'string'}, 'value': {'type': 'string'}})},
              'quote': {'type': 'string'},
              'subject': {'type': 'string', 'enum': list(SUBJECTS),
                          'description': 'beneficiary: the person the coverage is for. learner: the person typing, '
                                         'when that is someone else.'},
              'scope': {'type': 'string', 'enum': list(SCOPES)},
              'uncertain': {'type': 'boolean'},
              'correction': {'type': 'boolean'}})}}),
    _tool('get_signup_dates',
          'Dates computed by code from the saved reports: the sign-up window, Part A and Part B starts, the Medigap '
          'window and the job-coverage window, each with its basis. Call it after saving. A date this tool did not '
          'return is not known.', {}),
    _tool('check_doctor',
          'Run the configured doctor check for a doctor already saved in the profile. Returns the result, the one '
          'detail the check still needs, or an error code.',
          {'name': {'type': 'string'}, 'place': {'type': ['string', 'null']}}),
    _tool('check_medicine',
          'Run the configured medicine check for a medicine already saved in the profile. Returns the result, the '
          'one detail the check still needs, or an error code.',
          {'name': {'type': 'string'}}),
    _tool('get_plan_status',
          'What each outcome still needs from the profile and, when the sorting engine is connected, its result. '
          'It returns no plan list, plan name or number of plans. An order or pick this tool did not return does '
          'not exist.', {}),
    _tool('offer_plans',
          'Call this when the person asks to see plans, to compare plans or to move on to plans. Code decides. '
          'When the profile is ready, code puts the step to review their details and see plans on screen, and your '
          'reply is one short lead-in with no question. When it is not ready, this returns the details still '
          'missing, and you ask for the next one.', {}),
    _tool('show_card',
          'Show a card that code builds from the saved reports. Returns what the card shows, or an error code when '
          'it cannot be built yet.',
          {'kind': {'type': 'string', 'enum': list(CARD_KINDS)}}),
]
TOOL_NAMES = tuple(tool['name'] for tool in TOOLS)


# ---------------------------------------------------------------------------
# The field catalog
# ---------------------------------------------------------------------------

def _pairs(value):
    return [[str(item[0]), str(item[1])] for item in value or [] if isinstance(item, (list, tuple)) and len(item) == 2]


def _question(flow, identifier, fields=None):
    try:
        return flow.question(identifier, fields)
    except Exception:  # an unavailable meaning keeps its catalog data and gets no extra wording
        return {}


def _field(key, label, options=None, multi=False):
    row = {'key': key, 'label': label}
    if options:
        row['options'] = _pairs(options)
    if multi:
        row['multi'] = True
    return row


def _catalog_entry(flow, identifier):
    known = conversation_records.purposes()
    meta = conversation_records.PROFILE_FIELDS.get(identifier) or {}
    label = meta.get('label') or identifier
    entry = {'id': identifier, 'label': label, 'purpose': known.get(identifier) or label, 'choices': [], 'fields': []}
    if identifier == 'S_AGE65':
        relative = [[key, key.replace('_', ' ')] for key in conversation_records.RELATIVE_MONTHS if key != 'none']
        entry['fields'] = [
            _field('birthMonth', 'Birth month, 1 to 12'), _field('birthYear', 'Birth year'),
            _field('month', 'Month of the 65th birthday, 1 to 12, when that is what the person gave'),
            _field('year', 'Year of the 65th birthday'),
            _field('firstOfMonth', 'Whether the birthday is on the first day of the month', [['yes', 'Yes'], ['no', 'No']]),
            _field('relativeMonth', 'The 65th birthday placed relative to today when no month is named', relative)]
        return entry
    if identifier == 'S_RETIREMENT':
        entry['fields'] = [
            _field('status', 'Work status', [['retired', 'Retired'], ['retiring', 'Planning to retire'], ['working', 'Working']]),
            _field('when', 'When, in the person’s own words')]
        return entry
    if identifier in ('COV_PART_A', 'COV_PART_B'):
        part = identifier[-1]
        entry['label'] = entry['purpose'] = 'Part %s: where the sign-up stands' % part
        entry['fields'] = [
            _field('status', 'Status', [[value, value.replace('_', ' ')] for value in conversation_records.PART_STATUSES]),
            _field('month', 'Start or application month, 1 to 12, when stated'),
            _field('year', 'Start or application year, when stated')]
        return entry
    if identifier == 'COV_PLAN':
        entry['label'] = entry['purpose'] = conversation_records.RECORDED_FIELDS[conversation_records.REPORTED_FIELD]['label']
        entry['fields'] = [
            _field('product', 'Kind of plan', [[value, value.replace('_', ' ')] for value in conversation_records.PRODUCTS]),
            _field('name', 'Plan name, as the person wrote it'), _field('carrier', 'Insurer, as the person wrote it'),
            _field('letter', 'Medigap plan letter', [[value, value] for value in conversation_records.LETTERS])]
        return entry
    base = Q.get(identifier) or {}
    names = [key for key in dict.fromkeys([*base.get('fieldNames', []), 'text', 'month', 'zip', 'county'])
             if key in FIELD_NAMES.get(identifier, ())]
    extra = [key for key in names if key != 'choice']
    asked = _question(flow, identifier, extra or None)
    if identifier in FIELD or identifier in medigap_profile.FIELDS:
        choices = _pairs(asked.get('choices') or base.get('choices'))
        if identifier == 'T04':
            # The start-month choice travels with the month field; advisor-first's question hides it.
            choices += [pair for pair in _pairs(base.get('choices')) if pair[0] == 'month']
    else:
        # Readiness reports are validated against the flow's own content choices.
        choices = [pair for pair in _pairs((getattr(flow, 'content', {}).get(identifier) or {}).get('choices')
                                           or base.get('choices')) if pair[0] != 'partial']
    entry['choices'] = choices
    shown = {field['key']: field for field in asked.get('fields') or [] if isinstance(field, dict) and 'key' in field}
    rows = []
    if 'choice' in names:
        rows.append(_field('choice', 'One or more of choices, comma-separated' if identifier in MULTI_CHOICE
                           else 'One of choices' if choices else 'The reported value', multi=identifier in MULTI_CHOICE))
    for key in extra:
        rows.append(_field(key, (shown.get(key) or {}).get('label') or FIELD_LABELS.get(key, key),
                           (shown.get(key) or {}).get('options')))
    entry['fields'] = rows
    return entry


def field_catalog(flow):
    """Every profile meaning the model may save, in a stable order."""
    return [_catalog_entry(flow, identifier) for identifier in SAVE_IDS]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _fail(code):
    return {'ok': False, 'error': code}


def _plain(text):
    """Whitespace and typographic quotes only; the words are untouched."""
    if not isinstance(text, str):
        return ''
    for curly, straight in (('’', "'"), ('‘', "'"), ('“', '"'), ('”', '"')):
        text = text.replace(curly, straight)
    return re.sub(r'\s+', ' ', text).strip()


def _jsonable(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_jsonable(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(type(value).__name__)


_MONTHS = {name.lower(): index for index, name in enumerate(calendar.month_name) if name}
_MONTHS.update({name.lower(): index for index, name in enumerate(calendar.month_abbr) if name})


def _month_number(text):
    text = (text or '').strip().lower().rstrip('.')
    if re.fullmatch(r'0?[1-9]|1[0-2]', text):
        return int(text)
    return _MONTHS.get(text)


def _year_number(text):
    text = (text or '').strip()
    return int(text) if re.fullmatch(r'(?:19|20)\d{2}', text) else None


def _month_label(day):
    return '%s %d' % (ux_pass.MONTH_NAMES[day.month - 1], day.year)


def statement_cards_on():
    return os.environ.get(STATEMENTS_SWITCH, '').strip().lower() in {'1', 'on', 'true', 'yes'}


def _outcome(update, status, reason):
    # Nothing the model wrote is echoed: an outcome names its update by position (added by the
    # caller) and by a field id from the fixed list. Tool outputs ground later replies.
    return {'id': update['id'] if update['id'] in SAVE_IDS else None, 'status': status, 'reason': reason}


def _same_name(wanted, reported):
    a, b = _plain(wanted).casefold(), _plain(reported).casefold()
    return bool(a and b and (a in b or b in a))


class _Refused(Exception):
    """A gate refused one update. Carries the status and the fixed reason code."""

    def __init__(self, status, reason):
        super().__init__(reason)
        self.status, self.reason = status, reason


# ---------------------------------------------------------------------------
# The runner
# ---------------------------------------------------------------------------

class ToolRunner:
    def __init__(self, flow, owner, guide, record, message, *, today=None, asked=None):
        # ``asked`` is the code-worded question that was on screen when the message was written.
        self.flow, self.owner = flow, owner
        self.asked = copy.deepcopy(asked) if isinstance(asked, dict) else None
        self.confirmations = []       # reports the gates want confirmed, in advisor-first's pending shape
        self.guide, self.record = copy.deepcopy(guide), copy.deepcopy(record)
        self.message = message if isinstance(message, str) else ''
        self._message = _plain(self.message)
        self.today = today.date() if isinstance(today, datetime) else today or ux_flow.today()
        self.results, self.saved, self.cards = [], [], []
        # Set by offer_plans: the person asked for plans, and whether code found the profile ready.
        self.plans_requested = self.plans_offered = False
        self._catalog = None
        self._handlers = {'save_profile_fields': self._save, 'get_signup_dates': self._dates,
                          'check_doctor': self._check_doctor, 'check_medicine': self._check_medicine,
                          'get_plan_status': self._plan_status, 'offer_plans': self._offer_plans,
                          'show_card': self._show_card}

    def run(self, name, arguments):
        known = isinstance(name, str) and name in self._handlers
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except ValueError:
                arguments = None
        if not known:
            output = _fail('unknown_tool')
        elif not isinstance(arguments, dict):
            output = _fail('bad_arguments')
        else:
            try:
                output = _jsonable(self._handlers[name](arguments))
            except Exception as error:  # never let a model request fail the turn
                LOGGER.warning('Daylight one-call tool failed tool=%s error=%s', name, type(error).__name__)
                output = _fail('tool_failed')
        try:
            kept = json.loads(json.dumps(arguments))
        except (TypeError, ValueError):
            kept = None
        self.results.append({'name': name if isinstance(name, str) else '', 'arguments': kept, 'output': output})
        return output

    # -- save_profile_fields -------------------------------------------------

    def _entry(self, identifier):
        if self._catalog is None:
            self._catalog = {row['id']: row for row in field_catalog(self.flow)}
        return self._catalog[identifier]

    @staticmethod
    def _parse_update(raw):
        keys = {'id', 'entity', 'fields', 'quote', 'subject', 'scope', 'uncertain', 'correction'}
        if not isinstance(raw, dict) or set(raw) != keys:
            return None
        fields = raw['fields']
        if isinstance(fields, list):
            if any(not isinstance(item, dict) or set(item) != {'key', 'value'} for item in fields):
                return None
            pairs = [(item['key'], item['value']) for item in fields]
        elif isinstance(fields, dict):
            pairs = list(fields.items())
        else:
            return None
        entity = raw['entity']
        if (not isinstance(raw['id'], str) or not pairs or len({key for key, _ in pairs}) != len(pairs)
                or any(not isinstance(key, str) or not isinstance(value, str) or len(value) > MAX_TEXT for key, value in pairs)
                or not (entity is None or isinstance(entity, str) and len(entity) <= 40)
                or not isinstance(raw['quote'], str) or len(raw['quote']) > MAX_TEXT
                or not isinstance(raw['subject'], str) or not isinstance(raw['scope'], str)
                or type(raw['uncertain']) is not bool or type(raw['correction']) is not bool):
            return None
        return {'id': raw['id'], 'entity': entity or 'profile', 'fields': {key: value.strip() for key, value in pairs},
                'quote': _plain(raw['quote']), 'subject': raw['subject'], 'scope': raw['scope'],
                'uncertain': raw['uncertain'], 'correction': raw['correction']}

    def _merge_priorities(self, updates):
        """Several priorities named in one message are one multi-select answer (as advisor-first merges them)."""
        group = [u for u in updates if u['id'] == 'T10']
        positive = {pair[0] for pair in _pairs(Q['T10'].get('choices'))} - {'unknown', 'none'}
        if (len(group) < 2 or len({(u['entity'], u['subject'], u['scope']) for u in group}) != 1
                or any(set(u['fields']) != {'choice'} or u['correction'] or u['uncertain']
                       or not set(u['fields']['choice'].split(',')) <= positive for u in group)):
            return {}
        merged = copy.deepcopy(group[0])
        merged['fields']['choice'] = ','.join(dict.fromkeys(c for u in group for c in u['fields']['choice'].split(',')))
        folded = self._message.casefold()
        spans = [(folded.find(u['quote'].casefold()), len(u['quote'])) for u in group if u['quote']]
        if spans and len(spans) == len(group) and all(start >= 0 for start, _ in spans):
            start, end = min(s for s, _ in spans), max(s + n for s, n in spans)
            if end - start <= 600:
                merged['quote'] = self._message[start:end]
        return {id(u): merged for u in group}

    def _save(self, arguments):
        updates = arguments.get('updates')
        if set(arguments) != {'updates'} or not isinstance(updates, list) or len(updates) > MAX_UPDATES:
            return _fail('bad_arguments')
        parsed = [self._parse_update(raw) for raw in updates]
        if any(item is None for item in parsed):
            return _fail('bad_arguments')   # nothing is saved from a malformed call
        merged = self._merge_priorities(parsed)
        outcomes, done = [None] * len(parsed), {}
        # Dependencies first, as advisor-first orders them: who it is for, then the baseline answers.
        order = sorted(range(len(parsed)), key=lambda i: 0 if parsed[i]['id'] == 'RC01' else 1 if parsed[i]['id'] in FIELD else 2)
        for index in order:
            update = merged.get(id(parsed[index]), parsed[index])
            if id(update) not in done:
                done[id(update)] = self._save_one(update)
            outcomes[index] = {'index': index, **done[id(update)]}
        return {'ok': True, 'outcomes': outcomes, 'open': self._open_ids()}

    def _save_one(self, update):
        identifier = update['id']
        if identifier not in SAVE_IDS:
            return _outcome(update, 'rejected', 'unsupported_question')
        if find_identifiers(' '.join([update['quote'], *update['fields'].values()])):
            return _outcome(update, 'rejected', 'identifier_not_accepted')
        entry = self._entry(identifier)
        allowed = {field['key'] for field in entry['fields']}
        if set(update['fields']) - allowed:
            return _outcome(update, 'rejected', 'invalid_fields')
        try:
            before = self.flow.capture_values(self.guide, self.record)
            if identifier in SITUATION_IDS:
                reason = self._save_situation(update)
            elif identifier in COVERAGE_IDS:
                reason = self._save_coverage(update)
            else:
                reason = self._save_report(update, entry)
        except _Refused as refused:
            return _outcome(update, refused.status, refused.reason)
        except ProfileError:
            # advisor-first's own validators refused the value; it treats this as a clarification.
            return _outcome(update, 'needs_confirmation', 'capture_not_committed')
        except (ValueError, KeyError, TypeError):
            return _outcome(update, 'rejected', 'capture_not_committed')
        if before == self.flow.capture_values(self.guide, self.record):
            return _outcome(update, 'already_known', reason)
        self.saved.append({'id': identifier, 'entity': update['entity'], 'fields': dict(update['fields'])})
        return _outcome(update, 'accepted', reason)

    def _commit(self, guide, record):
        self.flow.validate(guide, record)
        self.guide.clear(); self.guide.update(guide)
        self.record.clear(); self.record.update(record)

    def _existing(self, identifier):
        old = self.guide['fields'].get(FIELD[identifier]) if identifier in FIELD else self.record['facts'].get(identifier)
        if old and identifier in ('T04', 'T06', 'T07'):
            key, path = {'T04': ('month', 'coverage.requestedStartMonth'), 'T06': ('text', 'needs.providers'),
                         'T07': ('text', 'needs.medications')}[identifier]
            old = copy.deepcopy(old)
            old['value'] = {'choice': old['value'], key: self.flow.value(self.guide, path)}
        return old

    # -- advisor-first's own interpreter validators --------------------------------

    def _turn_context(self):
        """What the extraction validators read: the reports on record, the switches and the question asked."""
        flow, guide, record = self.flow, self.guide, self.record
        asked = self.asked
        context = flow.context(guide, record, CONTEXT_POLICY, asked)
        identifier = (asked or {}).get('id')
        active = flow.permitted_question(asked, CONTEXT_POLICY)
        context.update(
            task=metadata(record)['task'], activeQuestion=active,
            discussion_enabled=conversation_planner.enabled(flow), discussion_context={'focus': ''},
            records_enabled=conversation_records.enabled(flow), fixes_enabled=conversation_records.fixes_on(flow),
            pending_enabled=conversation_records.pending_on(flow),
            answer_context=question_binding(
                active, flow.value(guide, 'subject.role'),
                {'S_AGE65': ['month', 'year', 'first_day'], 'S_RETIREMENT': ['status', 'when']}.get(identifier, ()),
                subject='learner' if identifier in ('T01', 'T02') else 'beneficiary'))
        return context

    def _interpreted(self, *, updates=(), situations=()):
        """Run ``NaturalAgent.validate_output`` on proposals, exactly as the two-call loop's first
        stage does before its controller sees them. Returns that validator's own result."""
        flow = self.flow
        agent = flow.agent
        guide, _ = legacy_projection(self.guide, self.record)
        import plans_fixes
        if plans_fixes.enabled(flow):
            guide, _ = plans_fixes.set_aside(flow, guide)
        value = {'updates': list(updates), 'requests': [], 'fact_ids': [],
                 'agenda': {'concerns': [], 'priorityReason': {}}, 'situation_proposals': list(situations),
                 'goal_quote': '', 'education_request': {'kind': 'none', 'concept_ids': [], 'quote': ''}}
        local = agent.local
        missing = object()
        kept = {name: getattr(local, name, missing) for name in ('turn_context', 'narrative')}
        local.turn_context = self._turn_context()
        local.narrative = {'eligibleMoves': ['ask', 'explain', 'prepare']}
        try:
            return agent.validate_output(value, self._message, guide, [], ['R00'], self.owner)
        finally:
            for name, old in kept.items():
                if old is missing:
                    if hasattr(local, name):
                        delattr(local, name)
                else:
                    setattr(local, name, old)

    def _validated(self, update):
        """One catalog update through advisor-first's extraction validators.

        Returns the fields as that validator left them. A report it drops is rejected here
        with one fixed code; its own reasons stay in advisor-first.
        """
        wire = {'id': update['id'], 'entity': update['entity'],
                'fields': [{'key': key, 'value': value} for key, value in update['fields'].items()],
                'quote': update['quote'], 'subject': update['subject'], 'scope': update['scope'],
                'uncertain': update['uncertain'], 'correction': update['correction']}
        try:
            result = self._interpreted(updates=[wire])
        except Exception as error:
            LOGGER.warning('Daylight one-call report validation unavailable error=%s', type(error).__name__)
            raise _Refused('rejected', 'unsupported_report') from None
        clean = result.get('updates') or []
        if len(clean) != 1 or clean[0].get('id') != update['id']:
            raise _Refused('rejected', 'unsupported_report')
        clean = clean[0]
        update['fields'] = {field['key']: field['value'] for field in clean['fields']}
        for key in ('subject', 'scope', 'uncertain', 'correction'):
            update[key] = clean[key]
        # A ZIP is five digits the person typed. advisor-first's validators exempt it from their
        # "value appears in the quote" rule; this loop does not save one the message never contained.
        zip_code = update['fields'].get('zip')
        if zip_code and zip_code.casefold() not in OPEN_VALUES and zip_code not in self._message:
            raise _Refused('rejected', 'unsupported_report')

    def _valid_situation(self, update, kind, first_day):
        """A birthday-month or work-status report through advisor-first's situation validator."""
        fields = update['fields']
        proposal = {'kind': kind, 'subject': update['subject'], 'scope': update['scope'], 'quote': update['quote'],
                    'uncertain': update['uncertain'], 'correction': update['correction'],
                    'month': _month_number(fields.get('month')) if kind == 'age65' else None,
                    'year': _year_number(fields.get('year')) if kind == 'age65' else None,
                    'status': fields.get('status', '') if kind == 'retirement' else '',
                    'when': fields.get('when', '') if kind == 'retirement' else ''}
        if kind == 'age65':
            if proposal['year'] and not conversation_records._grounded_year(update['quote'], proposal['year']):
                when = self._upcoming_birthday(update['quote'], proposal['month'])
                if when and when.year == proposal['year']:
                    proposal['year'] = None  # validate the literal, then compute its year locally
            proposal.update(first_day=first_day, first_day_quote=update['quote'] if first_day is not None else '')
            if fields.get('relativeMonth') is not None:
                proposal['relative_month'] = fields['relativeMonth']
        try:
            result = self._interpreted(situations=[proposal])
        except Exception as error:
            LOGGER.warning('Daylight one-call report validation unavailable error=%s', type(error).__name__)
            return False
        return len(result.get('situation_proposals') or []) == 1

    def _stage(self, update, reason, proposed=None):
        """Keep a report code will ask the person to confirm, in the shape advisor-first's pending
        question holds. Code asks only about a change to who the coverage is for and about a report
        that contradicts a value already saved. Any other doubt stays with the conversation."""
        if reason not in CONFIRMED_BY_CODE:
            return
        if proposed is not None:
            item = {'id': update['id'], 'fields': {}, 'entity': 'profile', 'proposed': copy.deepcopy(proposed)}
        else:
            item = {'id': update['id'], 'entity': update['entity'], 'fields': dict(update['fields']),
                    'quote': update['quote'], 'subject': update['subject'], 'scope': update['scope'],
                    'uncertain': False, 'correction': True}
        if len(self.confirmations) < MAX_UPDATES:
            self.confirmations.append(item)

    def _subject_change(self, update):
        """Whether this report would change who the coverage is for while personal reports exist.

        advisor-first's own apply refuses that change outright. It is asked on copies, so the
        answer is its rule and not a copy of it.
        """
        if update['id'] != 'RC01':
            return False
        prior = self.flow.value(self.guide, 'subject.role') or self.record['facts'].get('RC01', {}).get('value', {}).get('choice')
        new = update['fields'].get('choice')
        if prior not in ('self', 'someone') or new in (None, prior):
            return False
        guide, record = copy.deepcopy(self.guide), copy.deepcopy(self.record)
        try:
            self.flow.apply(guide, record, {**update, 'fields': dict(update['fields'])}, 'confirmed_agent_interpretation')
        except ProfileError:
            return True
        except (ValueError, KeyError, TypeError):
            return False
        return False

    def _save_report(self, update, entry):
        """One catalog report: advisor-first's extraction validators, its classify_update, then its capture."""
        identifier, fields = update['id'], update['fields']
        for key in DATE_FIELDS & set(fields):
            if fields[key].casefold() not in OPEN_VALUES:
                try:
                    fields[key] = normal_month(fields[key])
                except ProfileError:
                    pass
        if identifier == 'T04' and 'month' in fields and 'choice' not in fields:
            fields['choice'] = 'month'
        if identifier == 'T01' and 'choice' not in fields and fields.get('text'):
            # A goal given in the person's own words that names no listed category is the
            # catalog's own "Something else" answer, with those words kept.
            fields['choice'] = 'unresolved'
        if identifier == 'RC01' and update['subject'] == 'learner':
            # Who the visit is for is said by the person typing; advisor-first reads it the same way.
            update['subject'] = 'beneficiary'
        choice = fields.get('choice')
        if choice is not None and choice not in ('unknown', 'deferred'):
            offered = ({pair[0] for pair in entry['choices']} | {pair[0] for pair in _pairs((Q.get(identifier) or {}).get('choices'))}
                       | {pair[0] for pair in _pairs((getattr(self.flow, 'content', {}).get(identifier) or {}).get('choices'))})
            values = choice.split(',') if identifier in MULTI_CHOICE else [choice]
            if offered and any(value not in offered for value in values):
                raise _Refused('rejected', 'invalid_choice')
        if (identifier == 'T03' and set(fields) == {'county'}
                and not re.fullmatch(r'\d{5}', str(self.flow.value(self.guide, 'comparison.scope.zip') or ''))):
            raise _Refused('needs_confirmation', 'missing_dependency')
        # Structural refusals first, with their own codes; then advisor-first's extraction
        # validators, which its classify_update expects to have run; then the decision.
        early = classify_update(update, self._message, existing=self._existing(identifier))
        if early['decision'] == 'reject':
            raise _Refused('rejected', early['reason'])
        self._validated(update)
        if identifier == 'T01':
            # What the person wants help with is their own statement, in their own words: it has
            # no time scope to be unsure of, and mapping it to a coarse category is not a doubt
            # about a fact. advisor-first never restarts intake over a goal it could quote.
            update['scope'], update['uncertain'] = 'current', False
        result = classify_update(update, self._message, existing=self._existing(identifier))
        if identifier == 'T01' and result['decision'] == 'clarify' and result['reason'] == 'conflicting_report':
            old = (self._existing('T01') or {}).get('value')
            old = old.get('choice') if isinstance(old, dict) else old
            if fields.get('choice') in WORK_GOALS or fields.get('choice') == old:
                # A restated goal, or a request for coverage work, replaces the earlier goal as
                # advisor-first's planner replaces it (conversation_planner.observe): no question.
                update['correction'] = True
                result = classify_update(update, self._message, existing=self._existing(identifier))
        if result['decision'] == 'reject':
            raise _Refused('rejected', result['reason'])
        if self._subject_change(update):
            # Never on the model's say-so, a correction flag included: the person confirms it
            # through a code-built control, and only then is it applied.
            self._stage(update, 'subject_change')
            raise _Refused('needs_confirmation', 'subject_change')
        if result['decision'] == 'clarify':
            self._stage(update, result['reason'])
            raise _Refused('needs_confirmation', result['reason'])
        self.flow.capture(self.guide, self.record, update, method='direct_report')
        return result['reason']

    # -- a confirmation the person gave through the code-built control -----------------

    def confirm(self, update):
        """Apply a pending report the person confirmed. ``update`` is what advisor-first's
        ``pending_confirmation`` built from the held values. Returns whether it was saved."""
        try:
            identifier = update['id']
            if identifier not in SAVE_IDS or identifier in SITUATION_IDS or identifier in COVERAGE_IDS:
                return False
            update = {**update, 'fields': dict(update['fields']), 'entity': update.get('entity') or 'profile',
                      'quote': _plain(update.get('quote'))}
            before = self.flow.capture_values(self.guide, self.record)
            if self._subject_change(update):
                self._capture_subject_correction(update, method='explicit_confirmation')
            else:
                if classify_update(update, self._message, existing=self._existing(identifier))['decision'] != 'accept':
                    return False
                self.flow.capture(self.guide, self.record, update, method='explicit_confirmation')
            if before == self.flow.capture_values(self.guide, self.record):
                return False
            self.saved.append({'id': identifier, 'entity': update['entity'], 'fields': dict(update['fields'])})
            return True
        except (ProfileError, ValueError, KeyError, TypeError) as error:
            LOGGER.warning('Daylight one-call confirmation not applied error=%s', type(error).__name__)
            return False

    def confirm_situation(self, kind, value):
        """Apply a pending birthday-month or work-status value the person confirmed."""
        try:
            if kind not in SITUATION_FIELDS or not isinstance(value, dict):
                return False
            identifier = 'S_AGE65' if kind == 'age65' else 'S_RETIREMENT'
            before_guide, before_record = copy.deepcopy(self.guide), copy.deepcopy(self.record)
            guide, record = copy.deepcopy(self.guide), copy.deepcopy(self.record)
            self.flow.put(guide, SITUATION_FIELDS[kind], copy.deepcopy(value), 'user_text')
            record_capture(guide, record, before_guide, before_record,
                           {'id': identifier, 'fields': {}, 'entity': 'profile'}, method='explicit_confirmation')
            self._commit(guide, record)
            self.saved.append({'id': identifier, 'entity': 'profile', 'fields': {}})
            return True
        except (ProfileError, ValueError, KeyError, TypeError) as error:
            LOGGER.warning('Daylight one-call confirmation not applied error=%s', type(error).__name__)
            return False

    def _capture_subject_correction(self, update, method='explicit_confirmation'):
        """A confirmed correction of who the coverage is for keeps every report attached.

        advisor-first refuses to change RC01 once personal reports exist, because a
        different person needs a separate visit. A correction the person confirmed is
        not a different person: the reports were about this person all along. So the
        two RC01 envelopes are set aside on the working copies, advisor-first's own
        apply writes the corrected value, the earlier value goes into revision history
        as other corrections do, and provenance and validation run unchanged. Reached
        only through ``confirm``; a model's update never comes here.
        """
        before_guide, before_record = copy.deepcopy(self.guide), copy.deepcopy(self.record)
        guide, record = copy.deepcopy(self.guide), copy.deepcopy(self.record)
        earlier = record['facts'].pop('RC01', None)
        role = guide['fields'].pop('subject.role', None)
        previous = copy.deepcopy((earlier or {}).get('value')) or {'choice': (role or {}).get('value')}
        revision = record['stateVersion']
        self.flow.apply(guide, record, update, 'confirmed_agent_interpretation')
        record['history'].append({'triggerId': 'RC01', 'revision': revision, 'previous': previous})
        record_capture(guide, record, before_guide, before_record, update, method=method)
        self._commit(guide, record)

    def _situation_scope(self, update):
        if update['subject'] not in SUBJECTS or update['scope'] not in SCOPES:
            raise _Refused('rejected', 'missing_scope')
        if update['subject'] != 'beneficiary' or update['scope'] == 'unknown':
            if update['subject'] == 'unclear' and update['scope'] != 'unknown':
                raise _Refused('needs_confirmation', 'unclear_scope')
            raise _Refused('rejected', 'unresolved_subject_or_scope')
        if not update['quote'] or update['quote'].casefold() not in self._message.casefold():
            raise _Refused('rejected', 'missing_supporting_span')
        if update['uncertain']:
            raise _Refused('needs_confirmation', 'tentative')

    def _save_situation(self, update):
        """Birthday and work-status reports, as advisor-first resolves its situation proposals."""
        fields, quote = update['fields'], update['quote']
        kind = 'age65' if update['id'] == 'S_AGE65' else 'retirement'
        old = self.guide['fields'].get(SITUATION_FIELDS[kind])
        first_day = None
        try:
            self._situation_scope(update)
        except _Refused as refused:
            if refused.status == 'needs_confirmation' and 'birthMonth' not in fields and 'birthYear' not in fields:
                # An unclear or tentative reading is confirmed with one tap, as advisor-first does,
                # when its value passes the same validator a clear reading must pass.
                value = self._proposed_situation(update, kind, old)
                if value is not None:
                    self._stage(update, refused.reason, proposed=value)
            raise
        if kind == 'retirement':
            if fields.get('status') not in ('retired', 'retiring', 'working'):
                raise _Refused('rejected', 'invalid_situation_value')
            when = fields.get('when', '')
            if len(when) > 80 or when and when.casefold() not in quote.casefold():
                raise _Refused('rejected', 'missing_supporting_span')
            value = {'status': fields['status'], 'when': when}
        else:
            if fields.get('firstOfMonth') not in (None, 'yes', 'no'):
                raise _Refused('rejected', 'invalid_situation_value')
            first_day = {'yes': True, 'no': False}.get(fields.get('firstOfMonth'))
            if 'birthMonth' in fields or 'birthYear' in fields:
                return self._save_birth(update, first_day)
            if first_day is None:
                first_day = birthday_first_day(quote, _month_number(fields.get('month')))
            value = self._age65_value(fields, quote, old, first_day)
        if not self._valid_situation(update, kind, first_day):
            raise _Refused('rejected', 'unsupported_situation')
        role = self.flow.value(self.guide, 'subject.role')
        # The model read the meaning; the binding says which meaning this answer is for.
        binding = question_binding(_question(self.flow, update['id']), role, list(value))
        resolution = classify_situation(quote, kind, value, existing=old, answer_context=binding)
        if resolution['reason'] == 'conflicting_report' and update['correction']:
            resolution = classify_situation(quote, kind, value, answer_context=binding)
        if resolution['decision'] == 'reject':
            raise _Refused('rejected', resolution['reason'])
        if resolution['decision'] == 'clarify':
            proposed = copy.deepcopy(resolution.get('value') or value)
            if kind == 'age65' and first_day is not None:
                proposed['first_day'] = first_day
            self._stage(update, resolution['reason'], proposed=proposed)
            raise _Refused('needs_confirmation', resolution['reason'])
        value = resolution['value']
        if kind == 'age65':
            prior = (old or {}).get('value') or {}
            same = (value['month'], value['year']) == (prior.get('month'), prior.get('year'))
            kept = prior.get('first_day') if same else None
            if (first_day is not None and kept is not None and first_day != kept
                    and (old or {}).get('status') == 'reported' and not update['correction']):
                raise _Refused('needs_confirmation', 'conflicting_report')
            flag = kept if first_day is None else first_day
            if flag is not None:
                value['first_day'] = flag
        before_guide, before_record = copy.deepcopy(self.guide), copy.deepcopy(self.record)
        guide, record = copy.deepcopy(self.guide), copy.deepcopy(self.record)
        self.flow.put(guide, SITUATION_FIELDS[kind], value, 'user_text')
        record_capture(guide, record, before_guide, before_record,
                       {'id': update['id'], 'fields': {}, 'entity': 'profile'}, method='direct_report')
        self._commit(guide, record)
        return resolution['reason']

    def _proposed_situation(self, update, kind, old):
        """The value an unclear or tentative situation report proposes, or None when it is not valid."""
        fields, quote = update['fields'], update['quote']
        try:
            if kind == 'retirement':
                when = fields.get('when', '')
                if fields.get('status') not in ('retired', 'retiring', 'working') or len(when) > 80 \
                        or when and when.casefold() not in quote.casefold():
                    return None
                value, first_day = {'status': fields['status'], 'when': when}, None
            else:
                first_day = {'yes': True, 'no': False}.get(fields.get('firstOfMonth'))
                value = self._age65_value(fields, quote, old, first_day)
                if first_day is not None:
                    value['first_day'] = first_day
        except _Refused:
            return None
        if not quote or quote.casefold() not in self._message.casefold():
            return None
        # The validator is asked about the reading itself, apart from the doubt that staged it.
        clear = {**update, 'subject': 'beneficiary', 'uncertain': False}
        return value if self._valid_situation(clear, kind, first_day) else None

    def _upcoming_birthday(self, quote, month):
        if not month:
            return None
        match = re.search(r"\b(?:I (?:turn|will turn|am turning)|I['’](?:ll turn|m turning)) "
                          r"(?:65|sixty[- ]five) (?:on )?" + calendar.month_name[month]
                          + r"\s+(\d{1,2})(?:st|nd|rd|th)?\b", quote, re.I)
        if not match or re.match(r'\s*,?\s*(?:(?:19|20)\d\d|(?:of |in )?(?:next|last|this) year|in \d+ years)', quote[match.end():], re.I):
            return None
        day = int(match[1])
        year = self.today.year + ((month, day) < (self.today.month, self.today.day))
        try:
            return date(year, month, day)
        except ValueError:
            return None

    def _age65_value(self, fields, quote, old, first_day):
        month, year = _month_number(fields.get('month')), _year_number(fields.get('year'))
        if ('month' in fields and month is None) or ('year' in fields and year is None):
            raise _Refused('rejected', 'invalid_situation_value')
        relative = fields.get('relativeMonth')
        if relative is not None:
            if relative not in conversation_records.RELATIVE_MONTHS or relative == 'none' or month is not None:
                raise _Refused('rejected', 'invalid_situation_value')
            resolved = conversation_records.resolve_relative_month(
                {'kind': 'age65', 'month': None, 'year': year, 'relative_month': relative}, self.today)
            month, year = resolved.get('month'), resolved.get('year')
        elif month is not None and not conversation_records._grounded_month(quote, month):
            raise _Refused('rejected', 'ungrounded_report')
        if relative is None:
            when = self._upcoming_birthday(quote, month)
            if year is not None and not conversation_records._grounded_year(quote, year):
                if not when or when.year != year:
                    raise _Refused('rejected', 'ungrounded_report')
            if year is None and when:
                year = when.year
        if month is None:
            # Only the first-of-month detail was given: it belongs to the birthday already on record.
            known = (old or {}).get('value') if (old or {}).get('status') == 'reported' else None
            if first_day is None or not isinstance(known, dict) or year is not None:
                raise _Refused('rejected', 'invalid_situation_value')
            return {'month': known.get('month'), 'year': known.get('year')}
        return {'month': month, 'year': year}

    def _reports(self, items):
        accepted, confirm = conversation_records.validate_coverage_reports(items, self._message)
        if confirm:
            raise _Refused('needs_confirmation', 'needs_confirmation')
        if not accepted:
            raise _Refused('rejected', 'ungrounded_report')
        return accepted

    def _apply_reports(self, accepted, after=None, scope='current'):
        guide, record = copy.deepcopy(self.guide), copy.deepcopy(self.record)
        conversation_records.apply_coverage_reports(self.flow, guide, record, accepted, self.today)
        if after:
            after(guide)
        # Once both parts are reported, advisor-first writes the answer to "which parts do you
        # have" (RC04) itself and never asks it again. It writes that answer with no record of
        # who it is about, and plan readiness counts only an answer about the person the
        # coverage is for. Every coverage report that reaches this line passed the gate above
        # as that person's own (``_situation_scope``), so the derived answer is recorded as one.
        # Without this a visit that described the card in words could never reach the close.
        if record.get('facts', {}).get('RC04') != self.record.get('facts', {}).get('RC04'):
            record_capture(guide, record, guide, self.record,
                           {'id': 'RC04', 'entity': 'profile', 'fields': {}, 'subject': 'beneficiary',
                            'scope': scope if scope in ('current', 'intended') else 'current'}, method='direct_report')
        self._commit(guide, record)
        return 'semantic_report'

    def _report(self, update, kind, **values):
        return {'kind': kind, 'subject': update['subject'], 'quote': update['quote'], 'status': '', 'month': None,
                'year': None, 'product': '', 'name': '', 'carrier': '', 'letter': '', **values}

    def _save_birth(self, update, first_day):
        fields = update['fields']
        month, year = _month_number(fields.get('birthMonth')), _year_number(fields.get('birthYear'))
        if month is None or year is None or set(fields) - {'birthMonth', 'birthYear', 'firstOfMonth'}:
            raise _Refused('rejected', 'invalid_situation_value')
        accepted = self._reports([self._report(update, 'birth', month=month, year=year)])
        known = self.flow.value(self.guide, 'coverage.birth')
        if known and known != '%04d-%02d' % (year, month) and not update['correction']:
            raise _Refused('needs_confirmation', 'conflicting_report')

        def flag(guide):
            derived = self.flow.value(guide, SITUATION_FIELDS['age65'])
            if first_day is not None and isinstance(derived, dict) and derived.get('first_day') is not first_day:
                self.flow.put(guide, SITUATION_FIELDS['age65'], {**derived, 'first_day': first_day}, 'user_text')
        return self._apply_reports(accepted, flag)

    def _save_coverage(self, update):
        """Part A and Part B status and a plan already held, as advisor-first's coverage reports."""
        self._situation_scope(update)
        if update['scope'] == 'historical':
            raise _Refused('rejected', 'not_current_coverage')
        fields, kind = update['fields'], COVERAGE_IDS[update['id']]
        if kind == 'held_plan':
            item = self._report(update, kind, product=fields.get('product', ''), name=fields.get('name', ''),
                                carrier=fields.get('carrier', ''), letter=fields.get('letter', ''))
        else:
            month, year = _month_number(fields.get('month')), _year_number(fields.get('year'))
            if ('month' in fields and month is None) or ('year' in fields and year is None):
                raise _Refused('rejected', 'invalid_fields')
            item = self._report(update, kind, status=fields.get('status', ''), month=month, year=year)
        accepted = self._reports([item])
        if kind == 'held_plan' or item['status'] not in ('active', 'approved') or not (month and year):
            return self._apply_reports(accepted, scope=update['scope'])
        part = 'A' if kind == 'part_a' else 'B'
        path = enrollment_flow.PART_FIELDS[part]
        previous = self.flow.value(self.guide, path) or {}

        def retain_day(guide):
            report = self.flow.value(guide, path) or {}
            if report.get('date_kind') != 'start' or not report.get('date'):
                return
            dates = set()
            for clause in enrollment_flow._units(update['quote'], self.today):
                if part not in enrollment_flow._parts_in(clause):
                    continue
                # Split parts with different start dates, and use the date attached
                # to the start verb rather than another date mentioned in the clause.
                verb = enrollment_flow._STARTS.search(clause) or enrollment_flow._STARTED.search(clause)
                when = enrollment_flow.said_date(clause[verb.end():], self.today) if verb else None
                if when and (when.year, when.month) == (year, month):
                    dates.add(when.isoformat())
            exact = next(iter(dates)) if len(dates) == 1 else None
            if (not dates and previous.get('date_kind') == 'start' and previous.get('precision') != 'month'
                    and (previous.get('date') or '')[:7] == report['date'][:7]):
                exact = previous['date']
            if exact:
                self.flow.put(guide, path, {**report, 'date': exact, 'precision': 'day'}, 'user_text')
        return self._apply_reports(accepted, retain_day, scope=update['scope'])

    def open_ids(self):
        """The ids still open on the working copies; the same list a save returns as ``open``."""
        return self._open_ids()

    def _open_ids(self):
        try:
            view = conversation_records.profile_view(self.flow, self.owner, self.guide, self.record, None)
        except Exception as error:
            LOGGER.warning('Daylight one-call open fields unavailable error=%s', type(error).__name__)
            return []
        settled = set()
        try:
            # Two meanings the profile view cannot see as answered: the age anchor, read through
            # advisor-first's one age view, and a pricing detail its Medigap view already derives.
            if conversation_records.age_view(self.flow, self.guide, self.today)['turns_65']:
                settled.add('S_AGE65')
            pricing = medigap_profile.for_flow(self.flow, self.guide, self.record)
            settled |= {key for key in medigap_profile.FIELDS if key not in pricing.get('missing', [])}
        except Exception as error:
            LOGGER.warning('Daylight one-call open fields partly unavailable error=%s', type(error).__name__)
        return [row['id'] for row in view['fields'] if row['id'] in SAVE_IDS and row['id'] not in settled
                and row['id'] not in conversation_records.NEVER_ASK and row['state'] in ('open', 'pending')]

    # -- get_signup_dates ------------------------------------------------------

    def _timing(self):
        return ux_pass.enrollment_timing(self.flow.value(self.guide, SITUATION_FIELDS['age65']), self.today,
                                         self.flow.report(self.record, 'RC04').get('choice'))

    def _dates(self, arguments):
        if arguments:
            return _fail('bad_arguments')
        flow, guide, record = self.flow, self.guide, self.record
        journey = enrollment_journey.status(flow, guide, record, self.today)
        timing = self._timing()
        work = journey.get('work_window')
        supported = not journey['unsupported']
        needed = [part for part in ('A', 'B') if journey['parts'][part]['state'] == 'needed']
        out = {'ok': True, 'today': self.today.isoformat(), 'signup_window': None, 'part_a_start': None,
               'part_b_start': None, 'medigap_window': None, 'job_coverage_window': None, 'coverage_end': None}
        window = journey['window']
        # The same conditions advisor-first's coordinated dates use before it shows each one.
        if window and supported and window['phase'] != 'after' and needed:
            out['signup_window'] = {'start': window['start'], 'end': window['end'], 'phase': window['phase'],
                                    'basis': BASIS['birthday']}
        for part in ('A', 'B'):
            start = journey['parts'][part]['start']
            if start['date'] and start['basis'] == 'reported':
                out['part_%s_start' % part.lower()] = {'date': start['date'], 'basis': BASIS['reported']}
            elif start['date'] and timing:
                basis = BASIS['birthday']
                if part == 'B':
                    when = ('before %s' % _month_label(timing['eligibility_month'])
                            if timing['part_b_basis'] == 'signup_before_month' else 'in %s' % _month_label(timing['signup_month']))
                    basis = basis[:-1] + ', if sign-up happens %s.' % when
                out['part_%s_start' % part.lower()] = {'date': start['date'], 'basis': basis}
        # The Medigap window is advisor-first's to compute. Its own coordinated-dates builder is
        # asked, and the row it makes is relayed with the basis it states.
        age65 = flow.value(guide, SITUATION_FIELDS['age65'])
        row = next((item for item in enrollment_flow.coordinated_dates(journey, timing, age65)
                    if item.get('label') == 'Medigap window'), None)
        if row:
            out['medigap_window'] = {'months': row['value'],
                                     'basis': BASIS['part_b_reported'] if row.get('basis') == 'reported' else BASIS['birthday']}
            span = (timing or {}).get('medigap_window')
            if row.get('basis') != 'reported' and span:
                # An estimate advisor-first's timing helper already holds as dates.
                out['medigap_window'].update(start=span['start'].isoformat(), end=span['end'].isoformat(),
                                             basis=BASIS['birthday'][:-1] + ', if Part B starts %s.' % span['start'].isoformat())
        if work:
            out['job_coverage_window'] = {
                'first_end': work['first_end'], 'still_covered': work['still_covered'],
                'part_b_window': {'start_month': work['part_b_window'][0], 'end_month': work['part_b_window'][1],
                                  'open': work['part_b_window_open']},
                'part_b_start_if_signed_up_this_month': work['part_b_start_if_signed_now'],
                'later_start_can_be_requested': work['delay_allowed'],
                'plan_window_end_month': work['plan_window_end'],
                'medigap_window_if_signed_up_this_month': (
                    {'start_month': work['medigap_window_if_signed_now'][0], 'end_month': work['medigap_window_if_signed_now'][1]}
                    if work['medigap_window_if_signed_now'] else None),
                'basis': BASIS['job_dates']}
        end = journey.get('coverage_end')
        if end:
            out['coverage_end'] = {'date': end['date'], 'precision': end['precision'], 'basis': BASIS['reported']}
        step = journey['next_step']
        out['next_step'] = {'id': step['id'], 'by': step['by'],
                            'basis': {'reported': BASIS['reported'], 'estimated': BASIS['birthday'],
                                      'job_dates': BASIS['job_dates']}.get(step['basis'])}
        out['parts'] = {part: journey['parts'][part]['state'] for part in ('A', 'B')}
        # Situations where software shows the general rule and no personal estimate.
        out['held'] = list(journey['unsupported'])
        out['first_of_month_reported'] = None if not timing else not timing['first_day_assumed']
        missing = []
        waiting = any(journey['parts'][part]['state'] in ('needed', 'unknown') for part in ('A', 'B'))
        if not timing and not work and waiting:
            missing.append('S_AGE65')
        if not flow.report(record, 'RC04').get('choice') and not any(
                flow.value(guide, field) for field in enrollment_flow.PART_FIELDS.values()):
            missing.append('RC04')
        out['needs'] = missing
        return out

    # -- check_doctor / check_medicine ---------------------------------------

    @staticmethod
    def _compact_result(result):
        kept = {}
        for key in ('kind', 'name', 'office', 'plan', 'date', 'state', 'text', 'message'):
            value = result.get(key)
            if isinstance(value, (str, bool, int)) and len(str(value)) <= 300:
                kept[key] = value
        details = [line for line in result.get('details') or [] if isinstance(line, str)][:6]
        if details:
            kept['details'] = [line[:300] for line in details]
        return kept

    def _check(self, kind, name, place=None):
        checks = getattr(self.flow, 'conversation_checks', None)
        service = getattr(checks, 'doctors' if kind == 'doctor' else 'drugs', None) if checks else None
        if not checks or not service:
            return _fail('check_unavailable')
        if not isinstance(name, str) or not name.strip() or len(name) > 200 or not (place is None or isinstance(place, str)):
            return _fail('bad_arguments')
        guide, record = copy.deepcopy(self.guide), copy.deepcopy(self.record)
        try:
            if kind == 'doctor':
                from conversation_checks import doctor_reports
                reported = {item: (row.get('name'), row.get('location')) for item, row in doctor_reports(guide, record).items()}
            else:
                from part_d_visit import reported_fields
                reported = {item: ((row.get('identity') or {}).get('name'), None)
                            for item, row in reported_fields(guide, record)[1].items()}
            matches = [item for item, (label, _) in reported.items() if _same_name(name, label)]
            if not matches:
                return _fail('doctor_not_saved' if kind == 'doctor' else 'medicine_not_saved')
            view = checks.reconcile(self.owner, guide, record)
        except Exception as error:
            LOGGER.warning('Daylight one-call check failed tool=%s error=%s',
                           'check_doctor' if kind == 'doctor' else 'check_medicine', type(error).__name__)
            return _fail('check_failed')
        keys = {'doctor:' + item for item in matches} if kind == 'doctor' else None
        results = [self._compact_result(row) for row in view.get('results') or []
                   if isinstance(row, dict) and (row.get('key') in keys if keys is not None
                                                 else not str(row.get('key', '')).startswith('doctor:'))]
        question = view.get('question') or None
        needs = None
        if question:
            # Exact candidates stay in the interface; the model is told only what is still needed.
            needs = {'kind': question.get('kind'), 'field': question.get('field'), 'question': question.get('question'),
                     'choices_shown_in_interface': len(question.get('choices') or []),
                     'about_this_item': question.get('item') in matches if kind == 'doctor' else question.get('kind') == 'drug'}
        out = {'ok': True, 'kind': kind, 'name': reported[matches[0]][0],
               'status': 'result' if results else 'needs_detail' if needs else 'no_result',
               'results': results, 'needs': needs, 'participant_release': bool(view.get('participant_release'))}
        if kind == 'doctor':
            out['place_on_record'] = reported[matches[0]][1]
        return out

    def _check_doctor(self, arguments):
        if set(arguments) != {'name', 'place'}:
            return _fail('bad_arguments')
        return self._check('doctor', arguments['name'], arguments['place'])

    def _check_medicine(self, arguments):
        if set(arguments) != {'name'}:
            return _fail('bad_arguments')
        return self._check('medicine', arguments['name'])

    # -- get_plan_status -------------------------------------------------------

    def _try(self, section, read, missing):
        try:
            return read()
        except Exception as error:
            LOGGER.warning('Daylight one-call plan status section unavailable error=%s', type(error).__name__)
            missing.append(section)
            return None

    def _planner_state(self):
        # Read-only: never creates visit state for an owner that has none.
        visits = getattr(getattr(self.flow, 'discussion_visits', None), 'visits', None) or {}
        if not conversation_planner.enabled(self.flow) or (self.owner, self.flow.current_chain.get(self.owner)) not in visits:
            return {}
        return conversation_planner.state(self.flow, self.owner)

    @staticmethod
    def _compact_tab(tab):
        # The engine's result only. Group labels, the number of plans in a group and display
        # messages belong to the Plans page: the model cannot show a plan list, so it gets none.
        if not isinstance(tab, dict):
            return None
        return {'state': tab.get('state'), 'recommended_ids': list(tab.get('recommended_ids') or [])[:3],
                'no_pick_reason': tab.get('no_pick_reason')}

    def _recommendation(self, needs, missing):
        import part_d_profile
        import recommendation_engine
        hook = getattr(self.flow, RECOMMENDATION_HOOK, None)
        if not callable(hook):
            return {'available': False, 'reason': 'engine_not_configured', 'needs': needs}
        inputs = self._try('recommendation_inputs', lambda: recommendation_engine.inputs(
            self.guide, self.record, medigap_profile.for_flow(self.flow, self.guide, self.record),
            part_d_profile.profile(self.guide, self.record)), missing)
        if inputs is None:
            return {'available': False, 'reason': 'inputs_unavailable', 'needs': needs}
        guide, record = copy.deepcopy(self.guide), copy.deepcopy(self.record)
        checks, doctors = (), ()
        controller = getattr(self.flow, 'conversation_checks', None)
        try:
            if controller:
                from conversation_checks import doctor_reports
                checks = controller.reconcile(self.owner, guide, record)['results']
                doctors = doctor_reports(guide, record)
            reported = [key for key in ('RC21', 'RC22') if (record.get('facts') or {}).get(key)]
            result = hook(inputs, checks=checks, expected_doctors=doctors, reported=reported)
        except Exception as error:
            LOGGER.warning('Daylight one-call recommendation unavailable error=%s', type(error).__name__)
            return {'available': False, 'reason': 'engine_failed', 'needs': needs}
        if not isinstance(result, dict):
            return {'available': False, 'reason': 'engine_failed', 'needs': needs}
        return {'available': True, 'method': result.get('method'), 'evaluation_only': result.get('evaluation_only'),
                'needs': needs, **{name: self._compact_tab(result.get(name))
                                   for name in ('path', 'advantage', 'medigap', 'part_d')}}

    def _plan_status(self, arguments):
        if arguments:
            return _fail('bad_arguments')
        import plan_review
        flow, guide, record = self.flow, self.guide, self.record
        missing = []
        out = {'ok': True}
        review = self._try('plan_review', lambda: plan_review.readiness(guide, record), missing)
        if review is not None:
            out['plan_review'] = {'active': review['active'], 'can_review': review['canReview'],
                                  'needs': [item['question_id'] for item in review['missing']],
                                  'personal_recommendation_allowed': review.get('personalRecommendationAllowed', False)}
        bundle = self._try('outcomes', lambda: conversation_records.readiness(
            flow, self.owner, guide, record, self._planner_state(), self.today), missing)
        needs = []
        if bundle is not None:
            keep = ('needs', 'can_review', 'status', 'in_play', 'applies', 'timing_card_ready', 'chosen_plan')
            out['goal_order'] = list(bundle['order'])
            out['outcomes'] = {name: {key: value for key, value in item.items() if key in keep}
                               for name, item in bundle['outcomes'].items()}
            needs = list(bundle['outcomes']['recommendation']['needs'])
        pages = self._try('plans_pages', lambda: flow.plans_pages(guide, record), missing)
        if pages is not None:
            out['plans_pages'] = {name: {'status': pages[name]['status'], 'still_needed': list(pages[name]['still_needed'])}
                                  for name in ('medigap', 'part_d')}
        out['recommendation'] = self._recommendation(needs, missing)
        out['unavailable'] = missing
        if review is None and bundle is None and pages is None:
            return _fail('plan_status_unavailable')
        return out

    # -- offer_plans ---------------------------------------------------------------

    def plans_readiness(self):
        """advisor-first's plan readiness for the working copies, read for the saved goal.

        ``journey_completion.reviewed_status`` is the reading its own handoff uses. Check
        results are not an input: an unchecked doctor or medicine is shown as not checked on
        the Plans page and never holds the handoff back.
        """
        return conversation_planner.journey_completion.reviewed_status(self.flow, self.owner, self.guide, self.record)

    def request_plans(self):
        """Record that the person asked to see plans, and make sure there is a checklist to meet.

        advisor-first has a plan checklist only for a goal of finding or reviewing coverage. Its
        planner saves that goal itself when its reading of a message is that the person wants this
        work done (``conversation_planner.observe``). Here the request comes from the offer button
        or from the model's ``offer_plans`` call, and the goal is saved the same way.
        """
        self.plans_requested = True       # the conversation remembers it for this visit
        if self.flow.value(self.guide, 'intent.goal') in WORK_GOALS or not self._message:
            return
        try:
            before = self.flow.capture_values(self.guide, self.record)
            self.flow.capture(self.guide, self.record,
                              {'id': 'T01', 'entity': 'profile', 'fields': {'choice': 'compare'}, 'quote': self._message,
                               'subject': 'learner', 'scope': 'current', 'uncertain': False, 'correction': True},
                              method='direct_report')
            if before != self.flow.capture_values(self.guide, self.record):
                self.saved.append({'id': 'T01', 'entity': 'profile', 'fields': {'choice': 'compare'}})
        except (ProfileError, ValueError, KeyError, TypeError) as error:
            LOGGER.warning('Daylight one-call plans goal not saved error=%s', type(error).__name__)

    def _offer_plans(self, arguments):
        if arguments:
            return _fail('bad_arguments')
        self.request_plans()
        try:
            status = self.plans_readiness()
        except Exception as error:
            LOGGER.warning('Daylight one-call plan readiness unavailable error=%s', type(error).__name__)
            return _fail('plan_status_unavailable')
        if self.confirmations:
            # Something in this message is waiting for the person's own confirmation first.
            return {'ok': True, 'ready': False, 'missing': [], 'waiting_for': 'confirmation'}
        if status.get('canReview'):
            self.plans_offered = True
            return {'ok': True, 'ready': True, 'shown': 'review_and_see_plans'}
        if not status.get('active'):
            # No goal of finding or reviewing coverage is saved, so there is no checklist yet.
            return {'ok': True, 'ready': False, 'missing': [{'id': 'T01', 'label': self._entry('T01')['label']}]}
        missing = [{'id': item['question_id'], 'label': item['label']} for item in status.get('missing') or []
                   if item.get('question_id') in SAVE_IDS]
        return {'ok': True, 'ready': False, 'missing': list({item['id']: item for item in missing}.values())}

    # -- show_card ---------------------------------------------------------------

    def _build_card(self, kind):
        flow, guide, record, today = self.flow, self.guide, self.record, self.today
        chain = flow.current_chain.get(self.owner)
        coverage = set(flow.value(guide, 'coverage.current') or [])
        if kind == 'enrollment_timing':
            if conversation_records.enabled(flow):
                card = conversation_records.work_card(conversation_records.work_window(flow, guide, record, today), today)
                if card:
                    return card
            timing = self._timing()
            if not timing or coverage & ux_flow.ON_MEDICARE:
                return None
            said = [point for point in ('cobra_trap',) if flow.ux.said(self.owner, chain, point)]
            card = ux_pass.timing_card(timing, coverage, said)
            if card and timing['first_day_assumed']:
                # The same line advisor-first adds when the first-of-month detail is not on record.
                card['footnote'] = 'Born on the 1st of the month? Tell me and I’ll move these dates a month earlier.'
            return card
        if kind == 'medigap_window':
            timing = self._timing()
            line = ux_pass.medigap_window_line(timing, today) if timing else None
            if not line or not line.get('text'):
                return None
            # The card advisor-first attaches (ux_flow._cards); its text comes from ux_pass.
            return {'kind': 'medigap_window', 'title': 'Your Medigap window', 'text': line['text'],
                    'points': ['medigap_window'], 'statement_ids': ['medigap_window'],
                    'sources': [{'label': 'Medicare.gov: When can I buy a Medigap policy?',
                                 'url': 'https://www.medicare.gov/health-drug-plans/medigap/ready-to-buy/when'}]}
        if kind == 'two_paths':
            return ux_flow.two_paths(flow, self.owner, guide, record)
        if kind == 'trade_off':
            preference = ux_flow.cost_preference(flow, guide)
            return enrollment_flow.trade_off_card(flow, guide, preference) if preference else None
        if kind == 'trial_right':
            return enrollment_flow.trial_right(flow, guide, record, today)
        if kind == 'discussion_paths':
            return conversation_planner.educational_card(flow, {'focus': 'coverage_paths'})
        if kind == 'coverage_now':
            return self._have_card()
        journey = enrollment_flow.journey(flow, guide, record, today)
        reports = {part: flow.value(guide, field) for part, field in enrollment_flow.PART_FIELDS.items()}
        social = flow.value(guide, 'coverage.socialBenefits') == 'yes'
        line = enrollment_flow.status_line(journey, reports, flow.value(guide, enrollment_flow.PATH_FIELD), social,
                                           flow.value(guide, 'coverage.current') or [])
        if kind == 'signup_route':
            return enrollment_flow.route_card(journey, social) if line else enrollment_flow.general_signup_card()
        if kind == 'finish_summary':
            return enrollment_flow.finish_card(journey, line) if line else None
        return None

    def _have_card(self):
        # enrollment_flow.have_card reads the calendar through ux_flow. The module date is pinned
        # only when this runner was given a different day (tests); a live turn never touches it.
        if self.today == ux_flow.today():
            return enrollment_flow.have_card(self.flow, self.guide, self.record)
        pinned = ux_flow.TODAY
        ux_flow.TODAY = self.today
        try:
            return enrollment_flow.have_card(self.flow, self.guide, self.record)
        finally:
            ux_flow.TODAY = pinned

    def _show_card(self, arguments):
        kind = arguments.get('kind')
        if set(arguments) != {'kind'} or not isinstance(kind, str):
            return _fail('bad_arguments')
        if kind not in CARD_KINDS:
            return _fail('unknown_card_kind')
        if kind in STATEMENT_CARD_KINDS and not statement_cards_on():
            return _fail('card_needs_owner_acceptance')
        try:
            card = self._build_card(kind)
        except Exception as error:
            LOGGER.warning('Daylight one-call card unavailable error=%s', type(error).__name__)
            return _fail('card_not_available')
        if not isinstance(card, dict) or card.get('kind') != kind:
            return _fail('card_not_available')
        card = _jsonable(card)
        shown = any(item.get('kind') == kind for item in self.cards)
        if not shown:
            self.cards.append(card)
        summary = {'ok': True, 'kind': kind, 'title': card.get('title'), 'already_shown': shown,
                   'rows': [{'label': row.get('label'), 'value': row.get('value')}
                            for row in card.get('rows') or [] if isinstance(row, dict)][:8]}
        if isinstance(card.get('dates'), dict):
            summary['dates'] = card['dates']
        if kind == 'medigap_window' and isinstance(card.get('text'), str):
            summary['text'] = card['text'][:600]   # this card is one dated line and has no rows
        columns = [column.get('title') for column in card.get('columns') or [] if isinstance(column, dict)]
        if columns:
            summary['columns'] = columns
        paths = [{'name': item.get('name'), 'status': item.get('status'), 'still_needed': item.get('still_needed')}
                 for item in card.get('paths') or [] if isinstance(item, dict)]
        if paths:
            summary['paths'] = paths
        return summary
