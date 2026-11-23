"""The one-call conversation: advisor-first's conversation with a different typed-message step.

``OneCallConversation`` subclasses advisor-first's ``NaturalConversation`` and
replaces only what happens to a typed message. Request validation, the
identifier check, consent, continuation binding, the turn journal, every button
and structured action, and the whole response post-processing are advisor-first's
own code, so the existing web interface works against this class unchanged.

A typed turn here is:

1. apply any facts the background record pass held for this visit;
2. reserve the turn's two budget stages;
3. send one model request that carries the whole visit, the saved profile and
   the tools (one more request follows only when the model called tools);
4. check the reply against grounding built from the whole visit;
5. keep the blocks that passed; when none did, show one reviewed statement and
   the next open question in its catalog wording, as advisor-first does for a
   failed generation;
6. commit what the tools saved and hand the response to advisor-first's own
   post-processing.

The visit transcript, the tool outputs and the concerns record live in server
RAM only, keyed by (owner, visit), under the permission rule advisor-first's
visit memory uses. Nothing here logs a message, a reply, a value or a tool
argument, and nothing here writes a Medicare fact.
"""
import _paths  # noqa: F401  (puts advisor-first on sys.path and registers the pinned engine)

from collections import OrderedDict
from contextvars import ContextVar
import copy
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import threading
import time

from adaptive_flow import metadata
from advisor_flow import ROW_LABELS, describe_situation
from advisor_memory import CONTEXT_POLICY, HISTORY_TTL, VISIT_LIMIT
from advisor_models import MODELS
from applicable_rules import applicable_rules, floor_statement
from ai_budget import BudgetError
from chat import ModelUnavailable
from education import catalog_context, concepts_for_evidence, learning_context, plan_update
from guest_profiles import ProfileError
from identifier_guard import IDENTIFIER_MESSAGE, find_identifiers
from log_guard import install as install_log_guard
from narrative_agent import provider_failure_message
from natural_flow import NaturalConversation, Q
from natural_state import ensure_state, record_advisor_move, set_target
from pilot_knowledge import HELD_MA_DEADLINE, held_deadline_claim
from profile_readiness import reject_sensitive
import conversation_planner
import conversation_records
import conversation_tasks
import enrollment_flow
import journey_completion
import turn_progress
import ux_flow

from one_call_agent import CODES as AGENT_CODES, OneCallAgent
from one_call_check import check_reply
from one_call_reconcile import Reconciler
from one_call_tools import TOOL_NAMES, ToolRunner
import one_call_prompt
import one_call_plan_checks
import one_call_context

LOGGER = logging.getLogger(__name__)
LOGGERS = ('one_call_flow', 'one_call_agent', 'one_call_tools', 'one_call_reconcile', 'one_call_server')
install_log_guard(LOGGERS)

# The whole request, as bytes of JSON. advisor-first's 96,000-byte bound is for a
# compacted context; this loop sends fixed instructions of about 48,000 characters
# plus the whole visit, and never trims the visit to fit.
ONE_CALL_REQUEST_BYTES = 400_000
# Appends stop (they are never trimmed) once a visit's transcript could no longer be sent.
MAX_VISIT_BYTES = 2 * ONE_CALL_REQUEST_BYTES
MAX_TOOL_OUTPUTS = 600
MAX_BLOCK_CHARS = 2500
MAX_REPLY_CHARS = 7000
MAX_QUESTION_CHARS = 600
CONCERN_ITEMS = 12
CONCERN_CHARS = 240

# The owner's stated setting for this loop. Pinned here, so a change to the reasoning
# setting advisor-first's agent holds never changes what a one-call request asks for.
ONE_CALL_REASONING_EFFORT = 'low'
# One JSON line per typed turn: codes, counts, token numbers, dollars and seconds. Never words.
TRACE_FILE = Path(__file__).resolve().parent / 'var' / 'one-call-turn-trace.jsonl'
TRACE_SWITCH = 'DAYLIGHT_ONE_CALL_TRACE'
MAX_TRACED_VISITS = 4096

EVAL_SWITCH = 'DAYLIGHT_ONE_CALL_EVAL'
POLICY_MESSAGE = 'This conversation needs your current sharing permission. Send your message again from the conversation.'
MODEL_MESSAGE = 'That AI model is unavailable. Choose another model to send this message.'
FLOOR_NOTICE = 'I couldn’t finish that answer. Here is the part I’m sure of.'
DETAIL_INVITATION = 'Would it be okay to ask a few questions about your situation?'
DISCOVERY_QUESTION = 'What would you like to talk through?'
SYNTHETIC_NOTICE = 'Synthetic mode: no model is connected, so this message was not read.'
RETRY_NOTE = ('Code withheld part of the first draft of this reply. Rejection codes: %s. Write the whole reply again '
              'without the withheld content, using only what the profile, the transcript and the fact library support.')
LOST_NOTE = ('The reply written after the tool results could not be used (code: %s). The tool results are in the input. '
             'Write the whole reply again in the reply format.')
# Failures a second attempt cannot change: the request is too large, or it could not be counted.
NO_RETRY_CODES = frozenset({'input_bound', 'input_token_verification'})
RECONCILED_NOTE = 'Code saved these profile fields from the previous message after the last reply: %s. They are in the profile now.'
CONFIRMED_NOTE = ('The person confirmed on screen what code asked them to confirm, and code saved these profile '
                  'fields: %s. They are in the profile now.')
# The confirmation is worded and drawn by code. The label and the value words are advisor-first's own.
CONFIRM_LABEL = 'Yes, that’s right'
CONFIRM_TEXT = 'I want to be sure before I save this. %s: %s. Is that right?'
CHECK_NOTE = ('The latest message answered a detail the doctor or medicine check was waiting for, and code recorded it. '
              'Call the matching check tool if the reply needs the result.')
# Flow-level rejection codes, beside one_call_check's own.
HELD_CLAIM = 'held_claim'
TOO_LONG = 'too_long'
EMPTY_BLOCK = 'empty_block'

# The ending is code's, so it never depends on a reply arriving. These two lines stand in for
# the model's lead-in when no reply could be shown on a turn that asked for plans.
PLANS_READY_LINE = 'You’re ready to look at plans. Here is a summary of what you’ve told me and where to start.'
PLANS_NOT_READY_LINE = 'Before we look at plans, I still need a detail from you.'
# advisor-first's offer buttons whose words ask for plans. The button sends words this server
# issued on the turn before (conversation_records.accept_offer), so no message is read for meaning.
PLAN_OFFERS = frozenset({'compare', 'medigap', 'advantage'})

ANSWER_ACTIONS = frozenset({'choice', 'stage', 'unknown', 'defer'})
# Saved fields that name a doctor or a medicine for advisor-first's check controller.
CHECKED_IDS = frozenset({'T06', 'T07', 'RC21', 'RC22', 'RC23'})
# On-screen controls that change what the person is doing. The words are a note
# for the model's transcript, never shown to the person.
CONTROL_NOTES = {
    'review_plans': 'asked to review the saved information before seeing plans',
    'confirm_plan_review': 'confirmed the saved information to see plans',
    'get_plan_handoff': 'opened the plans page',
    'before_enroll_ack': 'marked the topics to know before enrolling as read',
}


def eval_switch_on():
    return os.environ.get(EVAL_SWITCH, '').strip().lower() in {'1', 'on', 'true', 'yes'}


def trace_switch_on():
    return os.environ.get(TRACE_SWITCH, '1').strip().lower() not in {'0', 'off', 'false', 'no'}


# ---------------------------------------------------------------------------
# Visit-scoped RAM
# ---------------------------------------------------------------------------

class VisitStore:
    """The whole-visit transcript, tool outputs and concerns record. RAM only.

    Keyed like ``advisor_memory.VisitMemory`` and under its permission rule: a
    read with a context policy other than ``natural-context-v3`` deletes that
    visit's entry. Same time-to-live and visit cap. Entries are never trimmed;
    once a visit passes its byte cap, further appends are refused.
    """

    def __init__(self, clock=None, ttl=HISTORY_TTL, limit=VISIT_LIMIT, max_bytes=MAX_VISIT_BYTES):
        self._clock = clock or time.monotonic
        self.ttl, self.limit, self.max_bytes = ttl, limit, max_bytes
        self._visits = OrderedDict()
        self._lock = threading.RLock()

    @staticmethod
    def _key(owner, chain):
        if (not isinstance(owner, str) or not owner or len(owner) > 256
                or not isinstance(chain, str) or not chain or len(chain) > 256):
            return None
        return owner, chain

    def _prune(self):
        now = self._clock()
        for key in [key for key, value in self._visits.items() if value['expires'] <= now]:
            del self._visits[key]

    @staticmethod
    def _empty():
        return {'transcript': [], 'tool_outputs': [], 'concerns': {'why_now': None, 'worries': [], 'tried': []},
                'plans_asked': False, 'detail_permission': 'open', 'bytes': 0, 'expires': 0}

    def read(self, owner, chain, policy):
        """A copy of the visit's entry. Any other policy deletes the entry and returns an empty one."""
        with self._lock:
            self._prune()
            key = self._key(owner, chain)
            if policy != CONTEXT_POLICY:
                if key is not None:
                    self._visits.pop(key, None)
                return self._empty()
            return copy.deepcopy(self._visits.get(key) or self._empty())

    def exists(self, owner, chain):
        with self._lock:
            self._prune()
            return self._key(owner, chain) in self._visits

    def turns(self, owner, chain):
        """How many transcript entries the visit holds. A count; never content."""
        with self._lock:
            self._prune()
            return len((self._visits.get(self._key(owner, chain)) or {}).get('transcript', []))

    def add(self, owner, chain, policy, *, entries=(), tool_outputs=(), concerns=None, plans_asked=None,
            detail_permission=None):
        """Append to a visit. Returns whether anything was stored.

        A ``natural-context-v3`` request may create the entry. A free on-screen
        control (no policy) may only add to a visit that is already permitted;
        it never creates one and never deletes one.
        """
        with self._lock:
            self._prune()
            key = self._key(owner, chain)
            if key is None or (policy != CONTEXT_POLICY and key not in self._visits):
                return False
            visit = self._visits.pop(key, None) or self._empty()
            added = [{'role': item['role'], 'text': item['text']} for item in entries
                     if isinstance(item, dict) and item.get('role') in ('person', 'daylight')
                     and isinstance(item.get('text'), str) and item['text'].strip()]
            size = sum(len(item['text'].encode()) for item in added)
            stored = visit['bytes'] + size <= self.max_bytes
            if stored:
                visit['transcript'].extend(added)
                visit['bytes'] += size
                visit['tool_outputs'] = (visit['tool_outputs'] + copy.deepcopy(list(tool_outputs)))[-MAX_TOOL_OUTPUTS:]
                if concerns is not None:
                    visit['concerns'] = copy.deepcopy(concerns)
            if plans_asked is not None:
                # Whether the person asked for plans and the step to see them is still owed. A yes or no.
                visit['plans_asked'] = bool(plans_asked)
            if detail_permission is not None:
                visit['detail_permission'] = detail_permission
            elif added and visit.get('detail_permission') == 'invited':
                # A different on-screen exchange intervened. A later yes belongs to that exchange.
                visit['detail_permission'] = 'open'
            visit['expires'] = self._clock() + self.ttl
            self._visits[key] = visit
            while len(self._visits) > self.limit:
                self._visits.popitem(last=False)
            return stored

    def clear(self, owner, chain):
        with self._lock:
            self._prune()
            self._visits.pop(self._key(owner, chain), None)

    def forget_owner(self, owner):
        with self._lock:
            self._prune()
            for key in [key for key in self._visits if key[0] == owner]:
                del self._visits[key]


# ---------------------------------------------------------------------------
# What the chat shows of a doctor or medicine check
# ---------------------------------------------------------------------------

def _office_text(office):
    """An office as the interface prints it (conversation-checks.js ``officeParts``), folded for comparison."""
    code = str(office.get('zip5') or '')
    if code and office.get('zip4'):
        code += '-' + str(office['zip4'])
    parts = [office.get('line'), office.get('city'), ' '.join(str(part) for part in (office.get('state'), code) if part)]
    return ', '.join(' '.join(str(part).split()).casefold() for part in parts if part)


def _shown_choice(question, choice):
    """What the person would read on a picker button (conversation-checks.js ``shown``). Compared, never shown."""
    value = choice.get('value')
    candidates = [item for item in question.get('candidates') or [] if isinstance(item, dict)]
    candidate = next((item for item in candidates if item.get('candidate_id') == value), None)
    if candidate is not None:
        offices = [office for office in candidate.get('offices') or [] if isinstance(office, dict)]
        named = any(office.get('place_match') for item in candidates for office in item.get('offices') or []
                    if isinstance(office, dict))
        return ('candidate', ' '.join(str(candidate.get('label')).split()).casefold(),
                tuple(_office_text(office) for office in offices),
                named and not any(office.get('place_match') for office in offices))
    site = next((item for item in question.get('offices') or []
                 if isinstance(item, dict) and item.get('site_id') == value), None)
    if site is not None:
        return ('office', _office_text(site))
    return ('label', ' '.join(str(choice.get('label')).split()).casefold())


def _short_result(result, controller):
    """A check result as the chat shows it: the match, never a row for every plan.

    A doctor checked across every plan becomes advisor-first's own single-coverage doctor result
    (the shape ``doctor_step`` returns for one coverage): the doctor, the office, the date checked
    and the Medicare lines advisor-first wrote. Medicines checked across every plan become
    advisor-first's plain note with the products matched. Nothing here is new evidence or new
    wording; the rows for each plan stay in the controller for the Plans page and the engine.
    """
    if not isinstance(result, dict):
        return result
    if result.get('kind') == 'doctor_matrix':
        short = {key: copy.deepcopy(result[key]) for key in
                 ('key', 'name', 'office_parts', 'date', 'details', 'original_medicare', 'participant_release')
                 if key in result}
        return {'kind': 'doctor', **short, 'plan': controller.plan_name('original_medicare')}
    if result.get('kind') == 'formulary':
        plans = result.get('plans') if isinstance(result.get('plans'), dict) else {}
        first = next(iter(plans.values()), None) or {}
        names = [str(medicine['name']) for medicine in first.get('medicines') or []
                 if isinstance(medicine, dict) and medicine.get('name')]
        return {'kind': 'note', 'key': result.get('key', 'formulary'), 'name': result.get('name'),
                'details': list(dict.fromkeys(names)), 'products': copy.deepcopy(result.get('products') or []),
                'evidence_date': result.get('evidence_date'), 'participant_release': False}
    return result


def present_checks(view, controller):
    """The check view as the chat shows it. Returns a new view; the controller's own is untouched.

    Picker choices the person would read as the same line are one choice (the first is kept, and
    its value answers through advisor-first's own ``check_answer``). Results are shortened by
    ``_short_result``. Applying it twice changes nothing.
    """
    if not isinstance(view, dict):
        return view
    shown = dict(view)
    question = view.get('question')
    if isinstance(question, dict) and isinstance(question.get('choices'), list):
        seen, kept = set(), []
        for choice in question['choices']:
            key = _shown_choice(question, choice) if isinstance(choice, dict) else ('other', id(choice))
            if key not in seen:
                seen.add(key)
                kept.append(choice)
        if len(kept) != len(question['choices']):
            shown['question'] = {**question, 'choices': kept}
    if isinstance(view.get('results'), list):
        shown['results'] = [_short_result(result, controller) for result in view['results']]
        from conversation_checks import digest
        if any(row.get('kind') in ('doctor_matrix', 'formulary') for row in view['results'] if isinstance(row, dict)):
            shown['planEvidenceStamp'] = digest(view['results'])
        # Receipts keep just the version a person saw. Source-controlled results
        # come from the latest check, even when displayed at an earlier exchange.
        shown['chatResultStamps'] = {row['key']: digest(row) for row in shown['results'] if isinstance(row, dict)
                                     and (str(row.get('key', '')).startswith('doctor:') or row.get('key') == 'formulary')}
    return shown


class TypedChecks:
    """advisor-first's check controller, with one difference for typed text.

    advisor-first answers a typed reply to a check question (an office, a
    strength, a quantity) with a fixed sentence and no model call. Here the
    answer is still recorded by the same code, and the message still goes to
    the model. Everything else passes through untouched.
    """

    def __init__(self, checks, flow):
        object.__setattr__(self, '_checks', checks)
        object.__setattr__(self, '_flow', flow)

    def __getattr__(self, name):
        return getattr(self._checks, name)

    def __setattr__(self, name, value):
        setattr(self._checks, name, value)

    def text_answer(self, owner, guide, record, text):
        if self._checks.text_answer(owner, guide, record, text):
            scratch = self._flow._one_call_scratch.get()
            if scratch is not None:
                scratch['check_answered'] = True
        return False


# ---------------------------------------------------------------------------
# The conversation
# ---------------------------------------------------------------------------

class OneCallConversation(NaturalConversation):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._one_call_init()

    @classmethod
    def adopt(cls, flow):
        """Turn a conversation that advisor-first's server built into this class.

        advisor-first constructs ``NaturalConversation`` itself. The subclass adds
        state and overrides methods and changes no stored layout, so the built
        object is re-classed in place and its extra state is initialised here.
        """
        if type(flow) is not NaturalConversation:
            raise TypeError('Adopt an advisor-first NaturalConversation.')
        checks = flow.__dict__.pop('conversation_checks', None)
        flow.__class__ = cls
        flow._one_call_init()
        if checks is not None:
            flow.conversation_checks = checks
        return flow

    def _one_call_init(self):
        # The configuration the variant's tools and prompt were built on: Parts A and B
        # fields, the planner and both records, as the :8895 demo enables them.
        enrollment_flow.enable(self)
        conversation_planner.enable(self)
        conversation_records.enable(self)
        conversation_records.enable_pending(self)
        conversation_records.enable_fixes(self)
        for agent in {self.agent, *self.model_agents.values()}:
            agent.definitions = [{**d, 'options': self.question('T05')['choices']} if d['id'] == 'T05' else d
                                 for d in agent.definitions]
        self._one_call_scratch = ContextVar('daylight_one_call_turn', default=None)
        self.one_call_visits = VisitStore()
        self.one_call_request_bytes = ONE_CALL_REQUEST_BYTES
        self.plan_card_projection = one_call_plan_checks.project
        self.reuse_card_start_dates = True
        self.one_call_eval = eval_switch_on()
        self.one_call_recommendation = getattr(self, 'one_call_recommendation', None)
        self.reconciler = Reconciler(self)
        self.one_call_trace = None           # a path turns the content-free turn trace on
        self._one_call_turns = OrderedDict()
        self._one_call_agents = []
        self._one_call_fixed = {}
        self._one_call_lock = threading.Lock()

    def question(self, id, fields=None, entity='profile', text=None):
        question = super().question(id, fields, entity, text)
        if id == 'T05':
            choices = list(question['choices'])
            index = next((i for i, pair in enumerate(choices) if pair[0] in ('none', 'unknown')), len(choices))
            choices.insert(index, ['marketplace', 'Marketplace / individual health plan'])
            question['choices'] = choices
        return question

    def _apply(self, guide, record, update, source='user_choice'):
        if update['id'] == 'RC21' and self.value(guide, 'needs.providersStatus') in ('list', 'yes'):
            # A named doctor's office is detail on that list item. The base RC21
            # writer also projects a standalone practice into the doctor list.
            from conversation_checks import ConversationChecks, doctor_reports
            providers = doctor_reports(guide, record)
            target = update.get('entity')
            practice = update['fields'].get('practice', '')
            if practice and target in (None, '', 'new', 'profile'):
                quote = str(update.get('quote') or '').casefold()
                matches = [key for key, item in providers.items()
                           if ConversationChecks.doctor_name(item['name'])[0].casefold() in quote]
                if len(matches) == 1:
                    target = matches[0]
                elif re.match(r'(?i)^(?:(?:his|her|their|the)\s+)?office\b', practice):
                    if len(providers) != 1:
                        raise ProfileError('Which doctor does this office belong to?')
                    target = next(iter(providers))
            if target in providers and practice:
                original = copy.deepcopy(guide['fields']['needs.providers'])
                result = super()._apply(guide, record, {**update, 'entity': target}, source)
                guide['fields']['needs.providers'] = original
                return result
        # The pinned baseline knows the original T05 choices. Handle the additional
        # choice on this surface only, with the same confirmed profile and dependencies.
        if update['id'] != 'T05':
            return super()._apply(guide, record, update, source)
        fields = update['fields']
        choice = fields.get('choice', '')
        if not isinstance(choice, str):
            raise ProfileError('Choose the coverage types you have now.')
        choices = choice.split(',')
        if 'marketplace' not in choices:
            return super()._apply(guide, record, update, source)
        selected = set(choices)
        if (set(fields) != {'choice'} or len(choices) != len(selected)
                or not selected <= dict(self.question('T05')['choices']).keys()
                or selected & {'unknown', 'none'}
                or ('advantage' in selected and selected & {'original', 'medigap'})):
            raise ProfileError('Those current coverage choices need clarification.')
        meta = metadata(record)
        meta['baselineDispositions'].pop('T05', None)
        meta['skippedDetails'].pop('T05.profile.choice', None)
        meta['editing'] = ''
        if self.value(guide, 'coverage.current') != choices:
            self.invalidate(record, 'coverage.current')
            if self.value(guide, 'coverage.requestedStart') == 'after_coverage':
                guide['fields']['coverage.requestedStart']['status'] = 'stale'
                self.invalidate(record, 'coverage.requestedStart')
        self.put(guide, 'coverage.current', choices, source)

    # -- the check controller ------------------------------------------------------

    @property
    def conversation_checks(self):
        return self.__dict__.get('_one_call_checks')

    @conversation_checks.setter
    def conversation_checks(self, value):
        self.__dict__['_one_call_checks'] = None if value is None else TypedChecks(value, self)

    # -- no typed sentence is answered without the model ----------------------------

    def _typed(self, payload):
        scratch = self._one_call_scratch.get()
        return scratch is not None and payload is scratch.get('payload')

    def direct_disposition(self, owner, payload, g, r):
        # advisor-first also calls this for its own "leave open" buttons, with a payload it
        # builds itself. Only the person's own typed payload is declined here.
        if self._typed(payload):
            return None
        return super().direct_disposition(owner, payload, g, r)

    def direct_local_answer(self, owner, payload, g, r):
        return None

    def replay_response(self, owner, response):
        scratch = self._one_call_scratch.get()
        if scratch is not None:
            scratch['replayed'] = True
        out = super().replay_response(owner, response)
        self._show_checks(out)
        return out

    # -- what the chat shows of a check ---------------------------------------------------

    def shown_checks(self, view):
        """A check view as this variant puts it on screen (``present_checks``)."""
        controller = self.conversation_checks
        return present_checks(view, controller) if controller else view

    def _show_checks(self, out):
        """Shorten the check view of a finished response, after advisor-first's own post-processing.

        advisor-first's close, its closing options and the journal read the full results, so the
        response is shortened only as it leaves. The interface replaces what it shows with the
        answer of ``/api/conversation/checks`` every few seconds; the server shortens that answer
        the same way.
        """
        try:
            if isinstance(out, dict) and isinstance(out.get('conversationCheck'), dict):
                before = out['conversationCheck'].get('results')
                out['conversationCheck'] = self.shown_checks(out['conversationCheck'])
                close = out.get('comparisonClose')
                if isinstance(close, dict) and close.get('findings') and out['conversationCheck'].get('results') != before:
                    # advisor-first's close adds one line per full result saying it can be reopened
                    # "above". The chat no longer shows those rows, so the lines are not shown either.
                    out['comparisonClose'] = {**close, 'findings': []}
        except Exception as error:
            LOGGER.warning('Daylight one-call check view left as built error=%s', type(error).__name__)

    def forget_owner(self, owner):
        super().forget_owner(owner)
        self.one_call_visits.forget_owner(owner)
        self.reconciler.discard(owner)

    # -- one turn ---------------------------------------------------------------------

    def _turn(self, owner, payload):
        scratch = {'payload': payload, 'replayed': False, 'typed': None, 'check_answered': False, 'previous': None,
                   'trace': None}
        token = self._one_call_scratch.set(scratch)
        started = time.monotonic()
        out = None
        try:
            action = payload.get('action') if isinstance(payload, dict) else None
            if isinstance(action, dict) and action.get('type') != 'message':
                scratch['previous'] = self._head(owner, payload.get('continuation'))
            out = super()._turn(owner, payload)
            try:
                self._after_turn(owner, payload, out, scratch)
            except Exception as error:      # the reply is already final; bookkeeping never fails it
                LOGGER.warning('Daylight one-call visit bookkeeping skipped error=%s', type(error).__name__)
            self._show_checks(out)
            return out
        finally:
            self._trace(owner, scratch, out, started)
            self._one_call_scratch.reset(token)

    # -- the content-free turn trace ---------------------------------------------------

    def _trace(self, owner, scratch, out, started):
        """One line for a typed turn that reached the model step: codes, counts, tokens, dollars, seconds.

        Nothing a person or the model wrote is in it: no message, reply, value, name or tool
        argument. The visit id is a hash of the owner digest and the visit, never the owner token.
        Off unless a path is set (the live 8897 server sets one; ``DAYLIGHT_ONE_CALL_TRACE=0`` keeps it off).
        """
        seen = scratch.get('trace')
        if not self.one_call_trace or seen is None or scratch.get('replayed'):
            return
        try:
            chain = self.current_chain.get(owner) or ''
            visit = hashlib.sha256((str(owner) + ':' + str(chain)).encode()).hexdigest()[:12]
            with self._one_call_lock:
                number = self._one_call_turns.pop(visit, 0) + 1
                self._one_call_turns[visit] = number
                while len(self._one_call_turns) > MAX_TRACED_VISITS:
                    self._one_call_turns.popitem(last=False)
            one = ((out or {}).get('metrics') or {}).get('oneCall') or {}
            plans = one.get('plans') or {}
            usage = [item for item in seen.get('usage') or [] if isinstance(item, dict)]
            total = lambda key: sum(item[key] for item in usage if type(item.get(key)) is int)
            settled = seen.get('settled') or {}
            nano = settled.get('settled_nano_usd') if type(settled.get('settled_nano_usd')) is int else 0
            line = {'at': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'visit': visit, 'turn': number,
                    'requests': seen.get('requests', one.get('requests', 0)),
                    'tools': [name for name in seen.get('tools') or [] if name in TOOL_NAMES],
                    'rejected_codes': [code for code in one.get('rejectedCodes') or [] if isinstance(code, str)],
                    'fallback': bool(one.get('fallback')) if out is not None else True,
                    'fallback_reason': one.get('fallbackReason') if out is not None else 'turn_failed',
                    'fallback_detail': one.get('fallbackDetail') if out is not None else None,
                    'retry': bool(one.get('retry')), 'reconciled': one.get('reconciled', 0),
                    'plans_handoff': bool(one.get('plansHandoff')),
                    'can_review': bool(plans.get('canReview')), 'missing_count': plans.get('missingCount', 0),
                    'plans_requested': bool(plans.get('requested')), 'close_due': bool(plans.get('closeDue')),
                    'handoff_reason': plans.get('reason') if out is not None else 'turn_failed',
                    'input_tokens': total('input'), 'cached_tokens': total('cached'), 'output_tokens': total('output'),
                    'settled_nano_usd': nano, 'usd': round(nano / 1e9, 6),
                    'unresolved_attempts': settled.get('unresolved_attempts', 0),
                    'seconds': round(time.monotonic() - started, 2)}
            path = Path(self.one_call_trace)
            path.parent.mkdir(parents=True, exist_ok=True)
            with self._one_call_lock, open(path, 'a', encoding='utf-8') as handle:
                handle.write(json.dumps(line, sort_keys=True) + '\n')
        except Exception as error:
            LOGGER.warning('Daylight one-call turn trace skipped error=%s', type(error).__name__)

    def _head(self, owner, continuation):
        """What the screen showed before a button was pressed: the question and any check question."""
        if not isinstance(continuation, str) or not continuation:
            return None
        chain = continuation.split('.')[0]
        with self.lock:
            if self.current_chain.get(owner) != chain or self.state_heads.get((owner, chain)) != continuation:
                return None
            for (entry_owner, _), entry in reversed(list(self.turn_journal.items())):
                if (entry_owner == owner and entry['expires'] > time.time()
                        and entry['response'].get('continuation') == continuation):
                    response = entry['response']
                    return {'question': copy.deepcopy((response.get('assessment') or {}).get('nextQuestion')),
                            'check': copy.deepcopy((response.get('conversationCheck') or {}).get('question'))}
        return None

    def _after_turn(self, owner, payload, out, scratch):
        """After final assembly: add the exchange to the visit, then schedule the record pass."""
        if scratch['replayed'] or not isinstance(out, dict):
            return
        chain = self.current_chain.get(owner)
        action = payload.get('action') if isinstance(payload.get('action'), dict) else {}
        kind = action.get('type')
        if kind == 'start':
            self.one_call_visits.clear(owner, chain)
            self.reconciler.discard(owner, chain)
        typed = scratch.get('typed')
        if kind == 'message':
            if not typed:
                return
            self.reconciler.consume(owner, chain, typed['held_taken'])
            if not typed['keep']:
                return
            entries = [{'role': 'person', 'text': typed['message']},
                       {'role': 'daylight', 'text': self._delivered_text(out)}]
            # The request to see plans stays owed until the step to see them has been put on screen.
            shown = bool((out.get('comparisonClose') or {}).get('show'))
            permission = typed['permission']
            delivered = out.get('conversationNext') or {}
            if typed['invite'] and delivered.get('kind') == 'clarification' and delivered.get('question') == typed['invite']:
                permission = 'invited'
            self.one_call_visits.add(owner, chain, CONTEXT_POLICY, entries=entries,
                                     tool_outputs=typed['tool_outputs'], concerns=typed['concerns'],
                                     plans_asked=typed['plans_asked'] and not shown, detail_permission=permission)
            if typed['reconcile']:
                self.reconciler.schedule(owner, chain, message=typed['message'], guide=out['guide'],
                                         record=out['record'], asked=typed['asked'],
                                         request_id=payload.get('requestId', ''), today=typed['today'])
            return
        entries = self._button_entries(payload, out, scratch.get('previous'))
        if entries:
            offered = scratch.get('local_invite')
            move = out.get('conversationNext') or {}
            permission = 'invited' if offered and move.get('kind') == 'clarification' and move.get('question') == offered else None
            self.one_call_visits.add(owner, chain, payload.get('contextPolicy'), entries=entries, detail_permission=permission,
                                     plans_asked=False if move.get('action') == 'plan_review' else None)

    def opening_after_answer(self, owner, out, action):
        """Return to discovery after the person answers a scoped question or completes a lookup."""
        scratch = self._one_call_scratch.get() or {}
        kind = action.get('type')
        previous = (scratch.get('previous') or {}).get('question') or {}
        answered = kind in ANSWER_ACTIONS and previous.get('id') == action.get('id')
        if not answered and kind not in ('check_answer', 'check_back', 'check_edit'):
            return
        visit = self.one_call_visits.read(owner, self.current_chain.get(owner), CONTEXT_POLICY)
        if visit.get('detail_permission') == 'granted' or visit.get('plans_asked'):
            return
        q = out['assessment'].get('nextQuestion') or {}
        if (q.get('localCheck') or (q.get('clarification') or {}).get('confirmable') or
                (out.get('conversationCheck') or {}).get('question') or (out.get('comparisonClose') or {}).get('show')):
            return
        words = DISCOVERY_QUESTION if visit.get('detail_permission') == 'declined' else DETAIL_INVITATION
        out['assessment']['nextQuestion'] = None
        set_target(out['record'], None)
        out['_records_next_move'] = {'kind': 'clarification', 'question': words}
        out['_one_call_opening'] = DISCOVERY_QUESTION
        if words == DETAIL_INVITATION:
            scratch['local_invite'] = words

    @staticmethod
    def completed_choice_review(out, action):
        # Optional prose can fail after the button and its review both succeeded.
        # Keep generated.code for diagnostics. The review itself is the reply.
        if (action.get('type') == 'choice' and out.get('notice') == FLOOR_NOTICE
                and out.get('advisor', {}).get('reason') == 'recovery'
                and (out.get('comparisonClose') or {}).get('show')
                and out.get('conversationNext', {}).get('action') == 'plan_review'):
            out.pop('notice')
            out.update(reply='', facts=[])
            out['advisor']['sources'] = []

    @staticmethod
    def review_check_items(guide, record, checks):
        from conversation_checks import doctor_reports
        from natural_flow import list_items
        offices = {row['key']: row for row in checks if row.get('kind') in ('doctor_matrix', 'doctor')}
        items = []
        for key, provider in doctor_reports(guide, record).items():
            checked = offices.get('doctor:' + key)
            items.append((checked['name'] if checked else provider['name'], bool(checked)))
        matrix = next((row['plans'] for row in checks if row.get('kind') == 'formulary' and row.get('plans')), {})
        products = next(iter(matrix.values()), {}).get('medicines', [])
        if products:
            items.extend((product['name'], True) for product in products)
        elif guide['fields'].get('needs.medicinesStatus', {}).get('value') == 'yes':
            report = guide['fields'].get('needs.medications', {})
            if report.get('status') == 'reported':
                items.extend((name, False) for name in list_items(report.get('value')))
        return items

    @staticmethod
    def medicine_spelling_choices(service, name, strength):
        """Suggest retained products for a transposed letter pair. Selection is still explicit."""
        from daylight_data.serving.part_d_math import EstimateHold
        word = name.casefold()
        if not re.fullmatch(r'[a-z]{6,32}', word):
            return []
        spellings = {word[:i] + word[i:i+2][::-1] + word[i+2:] for i in range(len(word) - 1)}
        spellings.discard(word)
        # One adjacent swap leaves at least one of these disjoint end fragments intact.
        size = (len(word) - 1) // 2
        found = {}
        for fragment in dict.fromkeys((word[:size], word[-size:])):
            try:
                rows = turn_progress.run('medicines', service.products, [], name=(fragment + ' ' + strength).strip())
            except EstimateHold as error:
                if str(error) != 'narrow_search':
                    raise
                continue
            for row in rows:
                if spellings.intersection(re.findall(r'[a-z]+', row['name'].casefold())):
                    found[row['rxcui']] = row
        return list(found.values())

    @staticmethod
    def _delivered_text(out, previous=None):
        """What Daylight put in front of the person, for the model's transcript."""
        parts = []
        reply = str(out.get('reply') or '').strip()
        if reply:
            parts.append(reply)
        question = (out.get('assessment') or {}).get('nextQuestion') or {}
        earlier = (previous or {}).get('question') or {}
        words = question.get('question')
        if (isinstance(words, str) and words.strip() and not reply.endswith(words.strip())
                and (question.get('id'), words) != (earlier.get('id'), earlier.get('question'))):
            parts.append(words.strip())
        check = (out.get('conversationCheck') or {}).get('question') or {}
        earlier_check = (previous or {}).get('check') or {}
        if isinstance(check.get('question'), str) and check['question'].strip() and check.get('question') != earlier_check.get('question'):
            parts.append(check['question'].strip())
        titles = [str(card.get('title') or card.get('kind')) for card in out.get('cards') or []
                  if isinstance(card, dict) and (card.get('title') or card.get('kind'))]
        if titles:
            parts.append('[Shown on screen: %s]' % '; '.join(titles))
        if (out.get('comparisonClose') or {}).get('show'):
            parts.append('[Shown on screen: the step to review the saved information and see plans]')
        return '\n\n'.join(parts)

    def _button_entries(self, payload, out, previous):
        """A button's question, the answer given and any reply shown, as transcript entries."""
        action = payload.get('action') if isinstance(payload.get('action'), dict) else {}
        kind, identifier = action.get('type'), action.get('id')
        person = None
        if kind in ANSWER_ACTIONS and isinstance(identifier, str):
            shown = (previous or {}).get('question') or {}
            question = shown if shown.get('id') == identifier else self._catalog_question(identifier, out)
            person = 'Answered on screen. Question: %s Answer: %s' % (
                str(question.get('question') or identifier).strip(), self._answer_words(action, question))
        elif kind == 'explanation_preference' and isinstance(action.get('value'), str):
            question = self._catalog_question('T02', out)
            label = dict(question.get('choices') or []).get(action['value'], action['value'])
            person = 'Answered on screen. Question: %s Answer: %s' % (str(question.get('question') or 'T02').strip(), label)
        elif kind == 'check_answer':
            shown = (previous or {}).get('check') or {}
            if isinstance(shown.get('question'), str):
                label = next((choice.get('label') for choice in shown.get('choices') or []
                              if isinstance(choice, dict) and choice.get('value') == action.get('value')), None)
                person = 'Answered on screen. Question: %s Answer: %s' % (
                    shown['question'].strip(), label or 'left open for now')
        elif kind == 'enrollment_decision':
            chosen = '; '.join('%s: %s' % (key, value) for key, value in sorted(action.items())
                               if key != 'type' and isinstance(value, str))
            person = 'Chose on screen. %s' % chosen if chosen else None
        elif kind == 'task' and isinstance(action.get('task'), str):
            person = 'Chose on screen to work on: %s.' % action['task']
        elif kind in CONTROL_NOTES:
            person = 'On screen, the person %s.' % CONTROL_NOTES[kind]
        delivered = self._delivered_text(out, previous)
        if person is None and not str(out.get('reply') or '').strip():
            return []
        entries = [{'role': 'person', 'text': person}] if person else []
        if delivered:
            entries.append({'role': 'daylight', 'text': delivered})
        return entries

    def _catalog_question(self, identifier, out):
        try:
            return conversation_records._question(self, out['guide'], out['record'], identifier) or self.question(identifier) or {}
        except Exception:
            return {}

    @staticmethod
    def _answer_words(action, question):
        """The words of a tapped answer, as advisor-first words them for its own reply to one."""
        if action.get('type') == 'unknown':
            return 'I don’t know.'
        if action.get('type') == 'defer':
            return 'I’ll check later.'
        fields = action.get('fields') if isinstance(action.get('fields'), dict) else {}
        choices = dict((pair[0], pair[1]) for pair in (question or {}).get('choices') or []
                       if isinstance(pair, (list, tuple)) and len(pair) == 2)
        words = '; '.join(str(choices.get(value, value)) for value in str(fields.get('choice', '')).split(',') if value)
        details = '; '.join(str(value) for key, value in fields.items() if key != 'choice' and value not in (None, ''))
        return ('; '.join(part for part in (words, details) if part) or 'no answer given')[:1200]

    # -- pieces of the typed turn ------------------------------------------------------

    def _agent_for_turn(self):
        base = self.agent
        model = getattr(base.client, 'model', None)
        if model not in MODELS or MODELS[model].provider != 'OpenAI':
            # Function tools are sent in the OpenAI Responses shape only.
            raise ProfileError(MODEL_MESSAGE, 503)
        with self._one_call_lock:
            for known, agent in self._one_call_agents:
                if known is base and agent.max_request_bytes == self.one_call_request_bytes:
                    return agent
            agent = OneCallAgent(base, max_request_bytes=self.one_call_request_bytes,
                                 reasoning_effort=ONE_CALL_REASONING_EFFORT)
            self._one_call_agents = [*self._one_call_agents[-7:], (base, agent)]
            return agent

    def _fixed(self, today):
        """The fixed instructions and the fact texts they render, built once per day."""
        with self._one_call_lock:
            cached = self._one_call_fixed.get(today)
            if cached is None:
                cached = {'instructions': one_call_prompt.static_instructions(self),
                          'fact_texts': one_call_prompt.fact_texts(self)}
                self._one_call_fixed = {today: cached}
            return cached

    def _direction(self, owner, guide, record, *, pause=False, engaged=False):
        """The planner's visit state for a typed turn, from saved reports only.

        advisor-first's interpreter proposes a discussion mode from the message.
        This loop has no such reading, so a saved goal of finding or reviewing
        coverage is treated exactly as advisor-first treats that goal tapped as
        a button (``conversation_planner.action_done``): the visit is working on
        it. Pausing comes from the checked reply. Nothing is read from words.
        """
        s = conversation_planner.state(self, owner)
        s.pop('outcome', None)
        s['latest'] = conversation_planner.empty_proposal()
        s['finish_requested'] = None
        s['pace_request'] = False
        s['next_target'], s['next_target_reason'] = [], None
        goal = self.value(guide, 'intent.goal')
        task = goal if goal in ('compare', 'review') else ''
        if not task and (engaged or self.value(guide, 'needs.providers') or self.value(guide, 'needs.medications')):
            # Naming a doctor or a medicine, or asking to see plans, is comparison work whatever
            # words the goal was saved under. advisor-first hides the doctor and medicine pickers
            # and never reaches its close unless the visit is in working mode
            # (conversation_planner.checks_relevant, journey_completion.closing_due), so a goal
            # saved as anything else used to leave both switched off for the whole visit.
            task = s['active_task'] if s['active_task'] in ('compare', 'review') else 'compare'
        if task and task != s['active_task']:
            conversation_planner.action_done(self, owner, {'generated': {'status': 'held'}},
                                             {'type': 'choice', 'id': 'T01', 'fields': {'choice': task}})
        elif not task and s['active_task'] in ('compare', 'review'):
            s['active_task'] = ''
        if pause:
            s['guidance'] = {**conversation_tasks.empty(), 'mode': 'pause'}
        elif s['active_task']:
            s['guidance'] = {**conversation_tasks.empty(), 'mode': 'work', 'task': s['active_task']}
        else:
            s['guidance'] = conversation_tasks.empty()
        s['education_only'] = s['guidance']['mode'] != 'work'
        report_task = 'compare' if s['active_task'] == 'advantage' else s['active_task']
        metadata(record).update(task=report_task or 'learn', preparing=bool(s['active_task']))
        return s

    def _profile(self, owner, guide, record, state):
        """Every saved report with its state, plus the states by id that advisor-first gives its models."""
        view = conversation_records.profile_view(self, owner, guide, record, state.get('question_progress'))
        saved = [{'id': row['id'], 'label': row['label'], 'state': row['state'], 'value': row['value']}
                 for row in view['fields'] if row['state'] != 'open' or row['value'] not in (None, '', [], {})]
        return {'coverage_is_for': self.value(guide, 'subject.role'), 'saved': saved,
                'states': conversation_records.compact_profile(view)}

    def _open_items(self, owner, guide, record):
        """The questions advisor-first would offer now, each with its purpose. Its own selection code."""
        moves = conversation_planner.refine(self, owner, guide, record, [])
        return moves, [{'id': move['id'], 'asks': (move.get('question') or {}).get('question', ''),
                        'purpose': move.get('purpose') or ''} for move in moves]

    def _readiness(self, owner, guide, record, state, today):
        bundle = conversation_records.readiness(self, owner, guide, record, state, today)
        keep = ('needs', 'can_review', 'status', 'in_play', 'applies', 'timing_card_ready', 'chosen_plan')
        return {'goal_order': list(bundle['order']),
                'outcomes': {name: {key: value for key, value in item.items() if key in keep}
                             for name, item in bundle['outcomes'].items()},
                'age_65_or_older': bundle['age'].get('age_65_or_older')}

    def _rules(self, guide, record, concerns, today):
        """The general rules the saved reports make relevant, as advisor-first selects them."""
        concern = ' '.join(str(item) for item in [concerns.get('why_now') or '', *concerns.get('worries', [])])[:400]
        selected = applicable_rules(
            lambda identifier: self.report(record, identifier), lambda path: self.value(guide, path),
            focus='', today=today, concern=concern,
            trial_at_first_eligibility=enrollment_flow.trial_at_first_eligibility(self, guide, record),
            plans_view=bool(self._plans_context.get()),
            age_65_or_older=conversation_records.age_view(self, guide, today)['age_65_or_older'], day_precision=True)
        return [rule for rule in conversation_records.strip_flow_instructions(selected) if rule['fact_id'] in self.facts]

    def _sources(self, fact_ids):
        sources = []
        for identifier in fact_ids:
            fact = self.facts.get(identifier) or {}
            links = ([{'url': fact['source'], 'label': 'Medicare.gov: ' + fact.get('title', '')}] if fact.get('source')
                     else fact.get('sources', []))
            for source in links:
                if isinstance(source, dict) and source.get('url') and all(item['url'] != source['url'] for item in sources):
                    sources.append({'url': source['url'],
                                    'label': source.get('label') or source.get('title') or fact.get('title', '')})
        return sources

    @staticmethod
    def _merge_concerns(old, new):
        """The visit's concerns record: earlier entries stay, new ones are added, each bounded."""
        merged = {'why_now': old.get('why_now'), 'worries': list(old.get('worries') or []), 'tried': list(old.get('tried') or [])}
        if not isinstance(new, dict):
            return merged

        def clean(value):
            if not isinstance(value, str):
                return None
            value = ' '.join(value.split())[:CONCERN_CHARS]
            return value if value and not find_identifiers(value) else None

        why = clean(new.get('why_now'))
        if why:
            merged['why_now'] = why
        for key in ('worries', 'tried'):
            seen = {item.casefold() for item in merged[key]}
            for item in new.get(key) if isinstance(new.get(key), list) else []:
                item = clean(item)
                if item and item.casefold() not in seen:
                    merged[key].append(item)
                    seen.add(item.casefold())
            merged[key] = merged[key][-CONCERN_ITEMS:]
        return merged

    def _checked(self, reply, grounding, message):
        """``check_reply`` plus the two things it leaves to the conversation: advisor-first's
        held-claim guard and the bounds visit memory puts on a reply and a question."""
        result = check_reply(reply, grounding=grounding)
        kept, rejected = [], list(result['rejected'])
        total = 0
        for block in result['blocks']:
            text = block['text'].strip()
            cited = [item for item in block.get('fact_ids') or [] if isinstance(item, str)]
            code = None
            if not text:
                code = EMPTY_BLOCK
            elif len(text) > MAX_BLOCK_CHARS or total + len(text) > MAX_REPLY_CHARS:
                code = TOO_LONG
            elif held_deadline_claim(text, {**self.pilot_knowledge.response_limits(message, [{'id': item} for item in cited]),
                                            'held_claim_ids': [HELD_MA_DEADLINE]}):
                # advisor-first holds this claim on its accepted surfaces only. Here it is held always.
                code = HELD_CLAIM
            if code:
                rejected.append({'index': -1, 'code': code})
                continue
            total += len(text)
            kept.append({'text': text, 'fact_ids': list(dict.fromkeys(cited))})
        question, question_code = result['question'], result['question_code']
        if question is not None and (not question['text'].strip() or len(question['text']) > MAX_QUESTION_CHARS):
            question, question_code = None, TOO_LONG
        return {'blocks': kept, 'rejected': rejected, 'question': question, 'question_code': question_code,
                'pause': reply.get('pause') is True, 'concerns': reply.get('concerns'),
                'detail_step': reply.get('detail_step')}

    # -- the typed turn ------------------------------------------------------------------

    def message(self, owner, payload, g, r):
        action = payload['action']
        if set(action) != {'type', 'message'}:
            raise ProfileError('Use the current conversation message.')
        message = action.get('message', '')
        if not isinstance(message, str):
            raise ProfileError('Use a text message.')
        message = message.strip()
        if not 1 <= len(message) <= 1200:
            raise ProfileError('Use 1–1200 characters; longer lists can be added in several messages.')
        reject_sensitive(message)
        if find_identifiers(message):
            raise ProfileError(IDENTIFIER_MESSAGE)
        if payload.get('aiConsent') is not True and not self.fixture:
            raise ProfileError('AI transfer needs your permission. The choices and reviewed explanations still work.', 428)
        if not self.fixture and (not self.agent.enabled or not self.agent.client.available):
            raise ModelUnavailable('Live AI is unavailable. Your message is preserved; the choices and reviewed explanations still work.')
        policy = payload.get('contextPolicy')
        chain = self.current_chain[owner]
        # The same permission rule as advisor-first's visit memory: this read deletes the
        # visit's transcript when the request does not carry the current context policy.
        visit = self.one_call_visits.read(owner, chain, policy)
        keep = policy == CONTEXT_POLICY
        if not keep:
            self.reconciler.discard(owner, chain)
            if not self.fixture:
                # The one request carries the whole visit and the saved profile, which only
                # the current policy covers. An older policy is not served a reduced turn.
                raise ProfileError(POLICY_MESSAGE, 428)
        agent = None if self.fixture else self._agent_for_turn()
        scratch = self._one_call_scratch.get() or {}
        presentation = self.current_presentation(owner, payload.get('continuation'))
        asked = copy.deepcopy((presentation or {}).get('nextQuestion'))
        today = ux_flow.today()
        before = [g['stateVersion'], r['stateVersion']]
        state = conversation_planner.state(self, owner)
        if conversation_records.pending_on(self):
            # The model reads the whole visit and decides what to return to; the two-call
            # loop's standing "pending question" would narrow its choices to one.
            conversation_records.release_pending(state)
        # A report the gates held for confirmation is applied only by the person's own answer
        # to the code-built confirmation that was on screen. Anything else typed withdraws it.
        held_confirmation = copy.deepcopy(self.pending_for(owner))
        g, r, confirmed = self._confirmed(owner, message, g, r, asked, today, keep)
        # advisor-first's offer button sends words this server issued on the turn before. An exact
        # match is the tap (its own rule), so a request for plans made that way is known to code.
        offers = copy.deepcopy({key: state.get(key) for key in ('records_last_offer', 'records_offers')})
        tapped = conversation_records.accept_offer(state, message)
        out = reservation = runner = turn = None
        usage = []
        if not self.fixture:
            self.agent.local.one_call_usage = usage
        if isinstance(scratch, dict):
            scratch['trace'] = {'usage': usage, 'tools': [], 'requests': 0, 'settled': None}
        try:
            g, r, reconciled, held_taken = self.reconciler.apply(owner, chain, g, r, today=today)
            self._direction(owner, g, r)
            transcript = [*visit['transcript'], {'role': 'person', 'text': message}]
            concerns = visit['concerns']
            fixed = self._fixed(today)
            runner = ToolRunner(self, owner, g, r, message, today=today, asked=asked)
            if tapped in PLAN_OFFERS:
                runner.request_plans()
            turn = {'blocks': [], 'question': None, 'pause': False, 'concerns': None, 'rejected': [], 'question_code': None,
                    'tool_calls': 0, 'retry': False, 'failure': None, 'confirmed': confirmed, 'extra_requests': 0,
                    'extra_usage': None, 'permission_before': 'open' if 'RC01' in confirmed else visit.get('detail_permission', 'open')}
            reservation = None if self.fixture else self.agent.reserve_turn(stages=('extract', 'compose'))
            if self.fixture:
                turn['failure'] = {'code': 'synthetic_fixture', 'reason': '', 'notice': SYNTHETIC_NOTICE}
            else:
                self._model_turn(owner, payload, agent, reservation, runner, turn, fixed, transcript=transcript,
                                 concerns=concerns, guide=g, record=r, state=state, today=today, message=message,
                                 prior_outputs=visit['tool_outputs'], reconciled=reconciled,
                                 check_answered=bool(scratch.get('check_answered')), confirmed=confirmed)
            out = self._assemble(owner, payload, runner, turn, fixed, message=message, policy=policy, before=before,
                                 concerns=concerns, today=today, reservation=reservation, reconciled=reconciled,
                                 plans_asked=bool(visit.get('plans_asked')))
            if isinstance(scratch, dict):
                scratch['typed'] = {
                    'message': message, 'keep': keep, 'asked': asked, 'today': today, 'held_taken': held_taken,
                    'tool_outputs': [item['output'] for item in runner.results],
                    'concerns': self._merge_concerns(concerns, turn['concerns']) if turn['blocks'] else concerns,
                    'plans_asked': turn['plans_wanted'],
                    'permission': turn['permission_after'], 'invite': turn.get('invite'),
                    'reconcile': keep and not self.fixture}
            return out
        except BaseException:
            # Nothing was delivered, so the browser still holds the earlier state: the
            # confirmation that was on screen is still the one waiting.
            if held_confirmation:
                self.clarifications[(owner, chain)] = held_confirmation
            else:
                self.clear_pending(owner)
            for key, value in offers.items():      # the offer button on screen is still the one issued
                if value is None:
                    state.pop(key, None)
                else:
                    state[key] = value
            raise
        finally:
            if not self.fixture:
                self.agent.local.one_call_usage = None
            if reservation:
                reservation.close()
                if out is not None and self.turn_trace_enabled():
                    out.setdefault('metrics', {})['settledUsage'] = reservation.trace_usage()
            trace = scratch.get('trace') if isinstance(scratch, dict) else None
            if trace is not None:
                try:
                    trace['tools'] = [item['name'] for item in runner.results] if runner is not None else []
                    if reservation:
                        extra = (turn or {}).get('extra_usage') or {}
                        settled = reservation.trace_usage()
                        trace['requests'] = (sum(reservation.stage(name).attempts for name in ('extract', 'compose'))
                                             + (turn or {}).get('extra_requests', 0))
                        trace['settled'] = {key: settled.get(key, 0) + extra.get(key, 0)
                                            for key in ('settled_nano_usd', 'unresolved_attempts')}
                except Exception as error:
                    LOGGER.warning('Daylight one-call turn trace partly unavailable error=%s', type(error).__name__)

    # -- confirmations: held by code, asked by code, applied only by the person's answer ----

    def _confirmed(self, owner, message, guide, record, asked, today, keep):
        """Apply the pending report when this message answers its confirmation with a yes.

        advisor-first's own helpers decide what counts: the confirmation must be the question
        on screen at this exact state, and the reply must be a bare affirmative. Returns the
        guide, the record and the ids saved. In every other case the pending report is dropped
        and the message is read by the model like any other.
        """
        pending = self.pending_for(owner)
        if not pending:
            return guide, record, []
        target = pending['update']
        shown = (isinstance(asked, dict) and asked.get('id') == target.get('id')
                 and (asked.get('clarification') or {}).get('confirmable') is True)
        live = pending.get('revision') == [guide['stateVersion'], record['stateVersion']]
        saved = []
        if keep and shown and live:
            runner = ToolRunner(self, owner, guide, record, message, today=today, asked=asked)
            update = self.pending_confirmation(owner, message, [])
            situation = None if update is not None else self.pending_situation_confirmation(owner, message, {})
            if update is not None and runner.confirm(update) or situation is not None and runner.confirm_situation(*situation):
                saved = [target['id']]
                guide, record = runner.guide, runner.record
                self.resolve_pending(owner, target, guide, record)
        if not saved:
            self.clear_pending(owner)
        return guide, record, saved

    def _confirmable(self, owner):
        return (self.pending_confirmation(owner, CONFIRM_LABEL + '.', []) is not None
                or self.pending_situation_confirmation(owner, CONFIRM_LABEL + '.', {}) is not None)

    def _stage_confirmations(self, owner, staged, guide, record):
        """Queue what the gates held, in advisor-first's own pending store, when one tap can confirm it."""
        key = (owner, self.current_chain[owner])
        earlier = self.clarifications.pop(key, None)
        revision = [guide['stateVersion'], record['stateVersion']]
        kept = [earlier['update'], *earlier.get('remaining', [])] if earlier else []
        for item in staged:
            self.clarifications[key] = {'update': copy.deepcopy(item), 'remaining': [], 'revision': revision, 'chain': key[1]}
            if self._confirmable(owner):
                kept.append(item)
            self.clarifications.pop(key, None)
        if kept:
            self.queue_pending(owner, kept, guide, record)
        return len(kept)

    def _confirmation_question(self, owner, guide, record):
        """The pending report as a question code words itself, with advisor-first's yes and no buttons."""
        pending = self.pending_for(owner)
        if not pending or not self._confirmable(owner):
            return None
        update = pending['update']
        identifier = update['id']
        try:
            fields = [key for key in update.get('fields', {}) if key != 'choice']
            question = self.contextual_question(guide, record, self.question(identifier, fields or None, update.get('entity', 'profile')))
        except Exception:
            question = None
        if not question:
            return None
        if isinstance(update.get('proposed'), dict):
            kind = 'age65' if identifier == 'S_AGE65' else 'retirement'
            label, words = ('65th birthday' if kind == 'age65' else 'Work status'), describe_situation(kind, update['proposed'])
        else:
            choices = {str(pair[0]): str(pair[1]) for pair in (Q.get(identifier) or {}).get('choices') or []
                       if isinstance(pair, (list, tuple)) and len(pair) == 2}
            values = update.get('fields') or {}
            parts = [choices.get(value, value) for value in str(values.get('choice', '')).split(',') if value]
            parts += [str(value) for key, value in values.items() if key != 'choice' and value]
            label, words = ROW_LABELS.get(identifier) or (Q.get(identifier) or {}).get('question', identifier), ', '.join(parts)
        if not words:
            return None
        question = copy.deepcopy(question)
        question.update(question=CONFIRM_TEXT % (str(label).rstrip('?.: '), words.rstrip('. ')), why='', reopened=True,
                        clarification={'confirmable': True, 'confirmLabel': CONFIRM_LABEL})
        return question

    def _model_turn(self, owner, payload, agent, reservation, runner, turn, fixed, *, transcript, concerns, guide, record,
                    state, today, message, prior_outputs, reconciled, check_answered, confirmed=()):
        """One model request (two after tools), the check, and at most one retry. Fills ``turn``."""
        turn.setdefault('extra_requests', 0)
        base = self.agent
        base.local.block_tap = None       # advisor-first's block release reads its own reply format only
        _, open_items = self._open_items(owner, guide, record)
        notes = []
        if reconciled:
            notes.append(RECONCILED_NOTE % ', '.join(dict.fromkeys(reconciled)))
        if confirmed:
            notes.append(CONFIRMED_NOTE % ', '.join(dict.fromkeys(confirmed)))
        if check_answered:
            notes.append(CHECK_NOTE)
        plans_context, plan_evidence = one_call_context.plans(self, guide, record)
        research_context = one_call_context.research(self, owner, guide, record, plans_context)
        evidence_profile = one_call_context.input_digest(guide, record)
        turn['plan_evidence'] = plan_evidence
        values = {'transcript': transcript, 'profile': self._profile(owner, guide, record, state),
                  'open_items': open_items, 'readiness': self._readiness(owner, guide, record, state, today),
                  'education': conversation_records.education_view(state), 'concerns': concerns, 'today': today,
                  'stage': {**self._stage(concerns), 'detail_permission': turn['permission_before']},
                  'plans_context': plans_context, 'plan_evidence': plan_evidence,
                  'research_context': research_context}
        request = {'instructions': fixed['instructions'], 'runner': runner, 'request_id': payload['requestId'],
                   'reservation': reservation}

        def grounding():
            nonlocal evidence_profile, plans_context, plan_evidence, research_context
            current_profile = one_call_context.input_digest(runner.guide, runner.record)
            if current_profile != evidence_profile:
                # A tool may correct the quote profile in this same request.
                # Validate against the new evidence and use it in any repair.
                plans_context, plan_evidence = one_call_context.plans(self, runner.guide, runner.record)
                research_context = one_call_context.research(self, owner, runner.guide, runner.record, plans_context)
                values.update(plans_context=plans_context, plan_evidence=plan_evidence, research_context=research_context)
                turn['plan_evidence'] = plan_evidence
                evidence_profile = current_profile
            after = conversation_planner.state(self, owner)
            previous = [item for item in prior_outputs if research_context is None or
                        item.get('name') not in ('check_doctor', 'check_medicine')]
            return {'person_text': [item['text'] for item in transcript if item['role'] == 'person'],
                    'reports': self._profile(owner, runner.guide, runner.record, after),
                    'tool_outputs': [*previous, *runner.results, research_context or {}, plans_context or {}],
                    'fact_texts': {**fixed['fact_texts'], **{item['id']: item['text'] for item in plan_evidence}},
                    'open_ids': set(runner.open_ids()) | {
                        move['id'] for move in conversation_planner.refine(self, owner, runner.guide, runner.record, [])}}

        carry = []          # the tool calls and their results, once the tools have run
        checked = failure = None
        try:
            first = turn_progress.run('composing', agent.reply, owner, input_text=one_call_prompt.turn_input(
                **values, pending_note=' '.join(notes) or None), carry=carry, **request)
        except ModelUnavailable as error:
            failure = self._failure(error)
            turn['tool_calls'] = sum(1 for item in carry if item.get('type') == 'function_call_output')
            if not carry or failure['code'] in NO_RETRY_CODES:
                turn['failure'] = failure
                return
        else:
            turn['tool_calls'] = first['tool_calls']
            try:
                checked = self._checked(first['reply'], grounding(), message)
            except Exception as error:
                # A reply that could not be checked is never shown.
                LOGGER.warning('Daylight one-call reply check unavailable error=%s', type(error).__name__)
                turn['failure'] = {'code': 'reply_check_unavailable', 'reason': 'The reply could not be checked.', 'notice': None}
                return
            turn['rejected'] = list(checked['rejected'])
        if failure is not None or checked['rejected']:
            # One more request, tools off, told only which codes applied. A turn that made no tool
            # call pays for it with the turn's unused second stage. A turn that did has used both
            # stages, so the retry gets a reservation of its own, made the way the record pass
            # makes its own, with the tool results already in its input. Three requests at most.
            turn['retry'] = True
            if failure is not None:
                note = LOST_NOTE % failure['code']
            else:
                note = RETRY_NOTE % ', '.join(sorted({item['code'] for item in checked['rejected']}))
            again_input = one_call_prompt.turn_input(**values, pending_note=' '.join([*notes, note]))
            second, own = None, None
            try:
                if carry:
                    own = base.reserve_turn(stages=('compose',))
                second = turn_progress.run('composing', lambda: agent.reply(
                    owner, input_text=again_input, stage='compose', allow_tools=False, carried=carry,
                    **{**request, 'reservation': own or reservation}))
            except (ModelUnavailable, BudgetError, ProfileError):
                second = None
            finally:
                if own is not None:
                    own.close()         # settles what was sent and releases what was not
                    turn['extra_requests'] = own.stage('compose').attempts
                    turn['extra_usage'] = own.trace_usage()
            try:
                again = self._checked(second['reply'], grounding(), message) if second is not None else None
            except Exception as error:
                LOGGER.warning('Daylight one-call reply check unavailable error=%s', type(error).__name__)
                again = None
            if again is not None:
                turn['rejected'] += again['rejected']
                # The rewrite replaces the first draft when it is clean or keeps more of itself.
                if checked is None or again['blocks'] and (
                        not again['rejected'] or len(again['blocks']) > len(checked['blocks'])):
                    checked = again
            if checked is None:
                turn['failure'] = failure
                return
        turn.update(blocks=checked['blocks'], question=checked['question'], pause=checked['pause'],
                    concerns=checked['concerns'], question_code=checked['question_code'], detail_step=checked['detail_step'])
        if not turn['blocks']:
            turn['failure'] = {'code': 'reply_rejected', 'reason': 'The reply did not pass its check.', 'notice': None}

    def _failure(self, error):
        """A model failure as advisor-first reports one: a fixed code and, where it helps, a notice."""
        local = self.agent.local
        diagnostic = getattr(local, 'provider_failure', None)
        code = getattr(local, 'last_composition_error', None) or AGENT_CODES.get(str(error)) or (
            'provider_failure' if diagnostic else 'composition_unavailable')
        notice = FLOOR_NOTICE
        if diagnostic and diagnostic.get('provider_code') in {'credit_balance_exhausted', 'insufficient_quota'}:
            notice = provider_failure_message(diagnostic, accepted=True)
        if code == 'input_token_verification':
            notice = 'The AI connection check did not finish. Your reported details are kept.'
        elif code == 'transport_or_format':
            transport = getattr(local, 'last_transport_failure', {}) or {}
            if transport.get('http_status') == 429:
                notice = 'The selected AI provider is limiting requests. Your reported details are kept.'
            elif transport.get('http_status'):
                notice = 'The selected AI provider declined the request. Your reported details are kept.'
            elif transport.get('phase') == 'stream':
                notice = 'The AI connection ended before the reply arrived. Your reported details are kept.'
        LOGGER.warning('Daylight one-call reply unavailable code=%s', code)
        detail = None
        if diagnostic:
            # advisor-first's value-free provider diagnostic: a fixed event name and a bounded code.
            event = diagnostic.get('event')
            which = diagnostic.get('incomplete_reason') if event == 'response.incomplete' else diagnostic.get('provider_code')
            if isinstance(which, str) and re.fullmatch(r'[a-z0-9_]{1,60}', which):
                detail = '%s:%s' % (event if event in ('response.failed', 'response.incomplete', 'error') else 'unknown', which)
        return {'code': code, 'reason': str(error)[:220], 'notice': notice, 'detail': detail}

    @staticmethod
    def _stage(concerns):
        """Describe discovery coverage. Only the exchange with the person can authorize intake."""
        known = concerns or {}
        missing = [key for key in ('why_now', 'worries', 'tried') if not known.get(key)]
        return {'now': 'understand_the_person' if missing else 'direction_understood', 'still_to_learn': missing}

    def _noted(self, guide, record, saved, message):
        """One plain sentence naming what this message saved, or '' when there is nothing to repeat.

        Only words the person typed in this message are said back: a saved value is repeated when
        it occurs in the message, compared without regard to case. A choice label, a button's words
        or anything code derived is never echoed as if the person had said it.
        """
        wanted = {item['id'] for item in saved}
        typed = ' '.join(str(message or '').split()).casefold()
        said = []
        for row in self.rows(guide, record):
            value = row.get('value')
            if row.get('id') not in wanted or row.get('status') != 'reported':
                continue
            values = [value] if isinstance(value, str) else value if isinstance(value, list) else []
            for text in values:
                text = text.strip().rstrip('.') if isinstance(text, str) else ''
                if text and ' '.join(text.split()).casefold() in typed:
                    said.append(text)
        said = list(dict.fromkeys(said))
        return 'I’ve noted %s.' % '; '.join(said) if said else ''

    def _missing_question(self, guide, record, missing):
        """The first missing plan detail as a question in advisor-first's approved catalog wording."""
        for criterion in missing:
            identifier, fields = criterion.get('question_id'), criterion.get('fields')
            try:
                question = None if fields else conversation_records._question(self, guide, record, identifier)
                question = question or self.contextual_question(guide, record, self.question(identifier, fields or None))
            except Exception:
                question = None
            if question and str(question.get('question') or '').strip():
                return copy.deepcopy(question)
        return None

    def _plans(self, owner, runner, state, *, asked, pause):
        """How this turn stands with the step to review the details and see plans.

        The step is advisor-first's guided close with its one button. It is due by advisor-first's
        own rule (``journey_completion.closing_due``): the saved profile can be reviewed and the
        step has not been shown for these exact details. When the person asked for plans, the
        step is shown again even if it was shown before, and the details advisor-first would ask
        for first are set aside for this visit. When they asked and the profile cannot be reviewed
        yet, the turn ends on the first missing detail in its approved wording. Doctor and medicine
        check results are not read: an unchecked name is shown as not checked on the Plans page.

        Returns ``handoff`` (the close is put on this turn), ``question`` (the missing detail to
        ask, or None), ``canReview``, ``missingCount`` and a fixed ``reason`` code.
        """
        guide, record = runner.guide, runner.record
        plan = {'handoff': False, 'question': None, 'canReview': False, 'missingCount': 0, 'reason': 'unavailable'}
        try:
            status = runner.plans_readiness()
            missing = list(status.get('missing') or [])
            plan.update(canReview=bool(status.get('canReview')), missingCount=len(missing))
            if pause:
                plan['reason'] = 'paused'
            elif self.pending_for(owner):
                plan['reason'] = 'confirmation_pending'
            elif plan['canReview']:
                if asked:
                    state.pop('close_delivered', None)
                if asked or self.value(guide, 'subject.role') != 'self':
                    # advisor-first asks these in its approved wording, written to the person the
                    # coverage is for, and stops asking after a few turns. A helper is not asked
                    # them here, and nobody who asked for plans is made to wait for them.
                    waiting = [journey_completion.timing_question(self, guide, record),
                               *journey_completion.medigap_before_close(self, guide, record, state)]
                    deferred = state.setdefault('deferred', [])
                    deferred.extend(item for item in waiting if item and item not in deferred)
                plan['handoff'] = bool(journey_completion.closing_due(self, owner, guide, record, state))
                plan['reason'] = ('close_shown' if plan['handoff'] else 'editing' if metadata(record).get('editing')
                                  else 'detail_first' if conversation_planner.timing_ask(self, owner, guide, record, state,
                                                                                         probe=True)
                                  else 'already_shown')
            elif not asked:
                plan['reason'] = 'not_requested'
            else:
                plan['reason'] = 'not_ready' if status.get('active') else 'no_goal'
                plan['question'] = self._missing_question(guide, record, missing)
        except Exception as error:
            LOGGER.warning('Daylight one-call plans handoff unavailable error=%s', type(error).__name__)
            plan.update(handoff=False, question=None, reason='unavailable')
        return plan

    def _assemble(self, owner, payload, runner, turn, fixed, *, message, policy, before, concerns, today,
                  reservation, reconciled, plans_asked=False):
        """Commit the working copies and build the response advisor-first's post-processing expects."""
        chain = self.current_chain[owner]
        guide, record = runner.guide, runner.record
        complete = bool(turn['blocks']) and turn['failure'] is None
        pause = complete and turn['pause'] and turn['question'] is None
        state = self._direction(owner, guide, record, pause=pause, engaged=plans_asked or runner.plans_requested)
        # Reports the gates want confirmed go into advisor-first's pending store before the
        # next question is chosen: its own selection code then offers nothing else.
        staged = 0 if pause else self._stage_confirmations(owner, runner.confirmations, guide, record)
        # The ending is decided by code, whether or not the model called offer_plans and whether
        # or not its reply arrived: the close when the profile can be reviewed, and otherwise,
        # for a person who asked for plans, the first missing detail in its approved wording.
        prior_permission = turn['permission_before']
        step = turn.get('detail_step') if complete else None
        wanted = (plans_asked or runner.plans_requested) and not (step == 'later' or pause)
        turn['plans_wanted'] = wanted
        permission = 'open' if prior_permission == 'invited' else prior_permission
        if step == 'later' or pause:
            permission = 'declined'
        elif prior_permission == 'invited' and step == 'agree':
            permission = 'granted'
        turn['permission_after'] = permission
        details_allowed = permission == 'granted' or step == 'requested_work' or wanted
        conversational = not details_allowed and not pause
        named = bool(self.conversation_checks) and any(item['id'] in CHECKED_IDS for item in runner.saved)
        hold_checks = step == 'later' or (step == 'invite' and not named)
        if conversational and hold_checks:
            state['guidance'] = conversation_tasks.empty()
            state['education_only'] = True
        plan = self._plans(owner, runner, state, asked=wanted, pause=pause)
        handoff, needed = plan['handoff'], plan['question']
        moves = conversation_planner.refine(self, owner, guide, record, [])
        if handoff and complete and wanted:
            # The step the person asked for is on screen: the reply is the one short lead-in.
            turn['blocks'] = turn['blocks'][:1]
        requests = ((sum(reservation.stage(name).attempts for name in ('extract', 'compose')) if reservation else 0)
                    + turn.get('extra_requests', 0))
        codes = [item['code'] for item in turn['rejected']]
        cited = list(dict.fromkeys(fact for block in turn['blocks'] for fact in block['fact_ids'])) if complete else []
        one = {'requests': requests, 'toolCalls': turn['tool_calls'], 'rejected': len(codes), 'rejectedCodes': codes,
               'questionCode': turn['question_code'], 'fallback': not complete, 'retry': turn['retry'],
               'reconciled': len(reconciled), 'saved': len(runner.saved), 'factIds': cited,
               'confirmed': len(turn.get('confirmed') or ()), 'staged': staged, 'questionDelivery': None,
               'failure': (turn['failure'] or {}).get('code'),
               # A fixed code for why the reviewed fallback was shown in place of the model's reply.
               'fallbackReason': None if complete else (turn['failure'] or {}).get('code') or 'reply_rejected',
               'fallbackDetail': None if complete else (turn['failure'] or {}).get('detail'),
               'plansAsked': bool(runner.plans_requested), 'plansHandoff': bool(handoff),
               # Why the close was or was not put on this turn. Codes and counts only.
               'plans': {'canReview': plan['canReview'], 'missingCount': plan['missingCount'], 'requested': bool(wanted),
                         'closeDue': bool(handoff), 'reason': plan['reason']}}
        if self.one_call_eval:
            # Code-made values only (dates, statuses, card rows), for the offline graders.
            one['toolOutputs'] = [copy.deepcopy(item['output']) for item in runner.results]
        out = self.response(guide, record, facts=[], expectedStateVersion=before[0], expectedReadinessRevision=before[1],
                            metrics={'llmCalls': requests, 'synthetic': self.fixture, 'oneCall': one})
        assessment = out['assessment']
        assessment['narrative']['opener'] = False
        assessment['conversationOpen'] = True
        assessment['intakePaused'] = False
        by_id = {move['id']: move['question'] for move in moves}
        if complete:
            out['reply'] = '\n\n'.join(block['text'] for block in turn['blocks'])
            if turn.get('plan_evidence'):
                out['planEvidence'] = [item for item in turn['plan_evidence'] if item['id'] in cited]
            cards = copy.deepcopy(runner.cards)
            # On a handoff turn the step to see plans is the one thing asked of the person.
            question = None if handoff else turn['question']
            target = question.get('target') if question else None
            selected, preclose = None, False
            if needed:
                # The person asked for plans and a detail is missing: code asks for it, whatever
                # the model asked. The request stays owed and the close follows the last detail.
                selected = copy.deepcopy(needed)
            elif target:
                catalog = copy.deepcopy(by_id.get(target)) or conversation_records._question(self, guide, record, target)
                # Answer buttons appear only under wording code owns. The approved catalog question
                # is written to the person the coverage is for, so it is used, with its buttons,
                # when that person is the one typing. The model's wording is then not shown.
                if (catalog and catalog.get('choices') and str(catalog.get('question') or '').strip()
                        and self.value(guide, 'subject.role') == 'self'):
                    selected = catalog
            if not selected and not handoff and not pause and details_allowed and moves and state.get('records_preclose'):
                # The profile can be reviewed and advisor-first wants one detail first (the birthday
                # month, a Medigap price detail). Code asks it, in advisor-first's wording, so its own
                # count applies: after a few turns it stops asking and the step to see plans follows.
                # A question the model worded would never be counted, and the close would never come.
                selected, preclose = copy.deepcopy(moves[0]['question']), True
            if selected:
                assessment['nextQuestion'] = selected
                one['questionDelivery'] = 'plans_missing' if needed else 'pre_close' if preclose else 'catalog'
            else:
                assessment['nextQuestion'] = None
                if question and not pause:
                    # For a helper, an unknown person, a field with no choices or no target at all,
                    # the model's checked wording is a plain typed question with no buttons. The
                    # typed answer comes back through the model and the validated save.
                    # advisor-first's delivery step appends it to the reply when nothing else owns the turn.
                    out['_records_next_move'] = {'kind': 'clarification', 'question': question['text'].strip()}
                    one['questionDelivery'] = 'free_text'
            if pause:
                assessment.update(nextQuestion=None, intakePaused=True, conversationOpen=True)
            else:
                # advisor-first reads ``intakePaused`` as "ask nothing this turn", which also holds
                # back its doctor and medicine picker. Here a reply without a button question is
                # an open conversation, not a pause: a name saved this turn still gets its picker.
                assessment['intakePaused'] = False
                assessment['conversationOpen'] = bool(not selected)
            out['generated'] = {'status': 'complete', 'move': (selected or {}).get('id') or 'answer'}
            taught = [fact for fact in cited if fact in self.facts]
            out['advisor'] = {'kind': 'teach' if taught else 'ask' if selected else 'answer', 'topic': '',
                              'reason': 'contextual_teaching' if taught else 'missing_dependency',
                              'teachingFactIds': taught, 'sources': self._sources(taught), 'visual': 'none',
                              'educationFollowups': []}
            record_advisor_move(out['record'], out['advisor'])
            self._record_teaching(owner, chain, policy, out, state, cited, taught, cards, fixed, payload['requestId'])
            state['plan']['answer_state'] = 'not_requested'
            if cards:
                for card in cards:
                    if card.get('kind') == 'signup_route' and card.get('route'):
                        self.ux.record(owner, chain, '', card='signup_route:' + str(card['route']))
                    state['cards'][card['kind']] = conversation_planner.card_fingerprint(card)
                out['cards'] = cards
        else:
            failure = turn['failure'] or {'code': 'reply_rejected', 'reason': '', 'notice': None}
            try:
                rules = self._rules(guide, record, concerns, today)
            except Exception as error:      # the floor is the safety net; it never fails the turn
                LOGGER.warning('Daylight one-call floor rules unavailable error=%s', type(error).__name__)
                rules = []
            question = None if handoff else needed or (copy.deepcopy(moves[0]['question']) if moves else None)
            # advisor-first's never-blank floor: one reviewed statement the reports support,
            # then the next open question in its approved wording. Nothing the model wrote.
            out['reply'] = self.recovery_statement(
                rules, {'_owner': owner, '_person_asked': '?' in message, 'evidence': []}, question, None)
            floor = floor_statement(rules, None)
            out['advisor'] = {'visual': 'none', 'teachingFactIds': [], 'kind': 'answer', 'topic': '', 'reason': 'recovery',
                              'sources': self._sources([floor['fact_id']])[:1] if floor else []}
            # The ending a person asked for is code's own, so it stands without a reply: one fixed
            # line, then the close or the missing detail. No notice about the reply is needed.
            ending = PLANS_READY_LINE if handoff and wanted else PLANS_NOT_READY_LINE if needed else None
            # Otherwise, what this message saved is said back in the person's own words, one plain
            # sentence. Only plain text the person typed is repeated: never a structured value
            # (the detail rows advisor-first keeps as a dictionary) and never a choice label.
            saved = ending or self._noted(guide, record, runner.saved, message)
            if saved:
                out['reply'] = saved
                out['advisor']['sources'] = []
                out['_records_saved_ack'] = True
            assessment['nextQuestion'] = question
            out['generated'] = {'status': 'unavailable', 'retryable': False, 'code': failure['code'],
                                'reason': failure['reason']}
            if failure.get('notice') and (not ending or failure['code'] == 'synthetic_fixture'):
                out['notice'] = failure['notice']
            state['plan']['answer_state'] = 'unresolved'
        if handoff:
            # The close owns this turn: no profile question and no typed question. An open doctor
            # or medicine check never holds it back (advisor-first's own "ask nothing" reading
            # keeps its picker off this turn), with one exception: a name the person typed in
            # this very message gets its picker now, and the close follows it.
            assessment.update(nextQuestion=None, intakePaused=wanted or not named, conversationOpen=True)
            out.pop('_records_next_move', None)
            one['questionDelivery'] = 'plans_handoff'
        confirmation = None if pause else self._confirmation_question(owner, guide, record)
        if confirmation:
            # A held report is asked about before anything else, in code's words, with the
            # code-built yes and no buttons. Nothing is saved until the person answers it.
            assessment.update(nextQuestion=confirmation, intakePaused=False, conversationOpen=False)
            out.pop('_records_next_move', None)
            one['questionDelivery'] = 'confirmation'
            if complete:
                out['generated']['move'] = confirmation['id']
        elif self.pending_for(owner):
            self.clear_pending(owner)
        if conversational and not confirmation and not handoff:
            q = turn.get('question') if complete else None
            clarification = out.get('_records_next_move') or {}
            if q and q.get('target') is None and step == 'invite':
                turn['invite'] = q['text'].strip()
            # Let actual check choices, a ready close and reviewed work offers take their normal routes.
            # Replace only an unsolicited profile question, including one the recovery floor chose.
            if assessment.get('nextQuestion') or (q and q.get('target')) or not complete:
                if permission == 'declined' or not (concerns.get('why_now') or concerns.get('worries')):
                    words = DISCOVERY_QUESTION
                else:
                    words = DETAIL_INVITATION
                    turn['invite'] = words
                out['_records_next_move'] = {'kind': 'clarification', 'question': words}
                assessment.update(nextQuestion=None, conversationOpen=True)
                one['questionDelivery'] = 'free_text'
                if complete:
                    out['generated']['move'] = 'answer'
            elif clarification.get('question') and hold_checks:
                assessment['intakePaused'] = True
            out['_one_call_opening'] = DISCOVERY_QUESTION
        out['metrics']['stageMs'] = copy.deepcopy(getattr(self.agent.local, 'stage_timings', {}))
        out['metrics']['modelStages'] = copy.deepcopy(getattr(self.agent.local, 'model_stages', []))
        self.ux.record(owner, chain, out.get('reply', ''))
        # The delivery step re-reads its own candidates; the two-call loop's forced return
        # to a standing question does not apply to a reply the model chose itself.
        state['records_pending_return'] = None
        orientation = 'answered' if ensure_state(out['record'])['dialogue']['orientation'] == 'progress' else None
        set_target(out['record'], assessment.get('nextQuestion'), orientation=orientation)
        self.validate(out['guide'], out['record'])
        if self.pending_for(owner):
            self.pending_for(owner)['revision'] = [out['guide']['stateVersion'], out['record']['stateVersion']]
        out.setdefault('_advisor_memory', {})['agenda_update'] = {'pause': bool(pause)}
        self.remember_exchange(owner, message, out, policy, payload['requestId'])
        return out

    def _record_teaching(self, owner, chain, policy, out, state, cited, taught, cards, fixed, request_id):
        """Record what this reply showed: the records ledger, the visit's delivered-concept
        record (which the pre-enrollment checklist reads) and the profile's lesson markers."""
        texts = fixed['fact_texts']
        conversation_records.record_shown(state, out['reply'], {fact: texts.get(fact, '') for fact in cited}, cards)
        if policy == CONTEXT_POLICY and taught:
            prior = self.memory.education(owner, chain, policy)
            catalog = {item['concept_id']: item for item in catalog_context()['concepts']}
            updates = []
            for concept in concepts_for_evidence(taught)[:4]:
                known = (prior['concepts'].get(concept) or {}).get('depth', 'not_covered') != 'not_covered'
                updates.append({'concept_id': concept, 'depth': 'introduced',
                                'reason': 'requested_revisit' if known else 'new',
                                'evidence_refs': [fact for fact in taught if fact in catalog[concept]['evidence_refs']]})
            if updates:
                # The delivery receipt is authorised by the checked reply that stated the fact.
                planned = plan_update(prior, {'purpose': 'teach', 'updates': updates, 'visual': 'none'}, taught,
                                      requested_revisit=True, revisit_concepts=[item['concept_id'] for item in updates],
                                      event_id=request_id)
                out.setdefault('_advisor_memory', {})['education_record'] = planned['record']
                out['education'] = learning_context(planned['record'])
        if taught:
            meta = metadata(out['record'])
            # The inherited short-term context accepts three simple IDs. The teaching
            # ledger above and the response's sources keep the entire checked reply.
            topic_ids = [fact for fact in taught if re.fullmatch(r'[a-z_]{1,40}', fact)]
            meta['lastFactIds'] = topic_ids[:3]
            topics = out['record']['natural']['dialogue']['explainedTopics']
            for fact in taught:
                if fact in self.progress_fact_ids and fact not in meta['journey']['learningSeen']:
                    meta['journey']['learningSeen'].append(fact)
            for fact in topic_ids:
                if fact not in topics and len(topics) < 50:
                    topics.append(fact)
            out['record']['stateVersion'] += 1
