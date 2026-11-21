"""Permissioned conversation continuity held only in server memory.

D155 (owner, Nov 21, 2026): the whole visit chat is kept and sent to the AI each
turn, "just like a regular agent session". There is no exchange-count or
character cap on what the AI reads; compaction or caching comes later, only if
conversations get too long. HISTORY_RAM_BYTES is a server-memory guard against a
runaway visit, not a context limit: about 100x a long real conversation.

This is working conversation context, never profile authority or saved data. The
caller owns validation of explicit goal reports and question eligibility. Older
context permissions do not authorize this cross-topic visit memory.
"""
import copy
import re
import threading
import time
from collections import OrderedDict

from education import empty_record, validate_record
from learner_state import empty_record as empty_learner, validate_record as validate_learner
from task_work import empty_record as empty_work_record, validate_record as validate_work_record
from turn_contract import checked_continuation


CONTEXT_POLICY = 'natural-context-v3'
# RAM guard only (D155): evicts the oldest exchanges of a single runaway visit.
HISTORY_RAM_BYTES = 2_000_000
DISCOURSE_NOTES = 10
DISCOURSE_CHARS = 1200
HISTORY_TTL = 3600
VISIT_LIMIT = 128
_TARGET = re.compile(
    r'(?:T(?:0[1-9]|10)|RC(?:0[1-9]|1[0-9]|2[0-8])|'
    r'RC11\.C1|RC16\.C[12]|S_AGE65|S_RETIREMENT|MG_(?:AGE|SEX|TOBACCO))\Z')


class VisitMemory:
    """Owner-and-chain isolated, one-hour RAM-only dialogue and working brief."""

    def __init__(self, clock=None):
        self._clock = clock or time.monotonic
        self._visits = OrderedDict()
        self._lock = threading.RLock()

    @staticmethod
    def _key(owner, chain):
        # A missing visit cannot share a default/global memory slot.
        if (not isinstance(owner, str) or not owner or len(owner) > 256
                or not isinstance(chain, str) or not chain or len(chain) > 256):
            return None
        return owner, chain

    def _prune(self):
        now = self._clock()
        for key in list(self._visits):
            if self._visits[key]['expires'] <= now:
                del self._visits[key]

    def _permitted(self, owner, chain, policy):
        self._prune()
        key = self._key(owner, chain)
        if policy != CONTEXT_POLICY:
            if key is not None:
                self._visits.pop(key, None)
            return None
        return key

    def recent(self, owner, chain, policy):
        """Return complete chronological exchanges; reads do not renew expiry."""
        with self._lock:
            key = self._permitted(owner, chain, policy)
            return copy.deepcopy(self._visits.get(key, {}).get('exchanges', []))

    def display_inputs(self, owner, chain):
        """Match already-retained inputs to receipts for the authorized visit."""
        with self._lock:
            self._prune()
            visit = self._visits.get(self._key(owner, chain), {})
            return {key: item['user'] for key, item in
                    zip(visit.get('request_ids', []), visit.get('exchanges', [])) if key}

    def brief(self, owner, chain, policy):
        """Return a non-authoritative working brief, separate from the profile."""
        with self._lock:
            key = self._permitted(owner, chain, policy)
            return copy.deepcopy(self._visits.get(key, {}).get('brief', {}))

    def education(self, owner, chain, policy):
        """Delivered concepts only; same authority, expiry and deletion as dialogue."""
        with self._lock:
            key = self._permitted(owner, chain, policy)
            return copy.deepcopy(self._visits.get(key, {}).get('education', empty_record()))

    def task_work(self, owner, chain, policy):
        """Selected work identifiers only; same owner/visit/expiry as dialogue."""
        with self._lock:
            key = self._permitted(owner, chain, policy)
            return copy.deepcopy(self._visits.get(key, {}).get('task_work', empty_work_record()))

    def learner(self, owner, chain, policy):
        with self._lock:
            key = self._permitted(owner, chain, policy)
            return copy.deepcopy(self._visits.get(key, {}).get('learner', empty_learner()))

    def clear_task_work(self, owner, chain):
        """An explicit task switch drops selected work, retaining dialogue/help."""
        with self._lock:
            self._prune()
            key = self._key(owner, chain)
            if key in self._visits:
                self._visits[key].pop('task_work', None)

    def commit_education(self, owner, chain, policy, record):
        """Commit a delivered free lesson within an already permitted visit.

        An explicit lesson does not grant AI continuity permission, create a
        dialogue exchange, or renew expiry. A stale plan cannot roll back a
        later receipt. The controller calls this after the action succeeds.
        """
        with self._lock:
            key = self._permitted(owner, chain, policy)
            if key is None or key not in self._visits:
                return False
            checked = validate_record(record)
            current = self._visits[key].get('education', empty_record())
            if checked['revision'] <= current['revision'] and checked != current:
                return False
            self._visits[key]['education'] = checked
            return True

    @staticmethod
    def _text(value, limit, name):
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError('Invalid visit-memory ' + name + '.')
        return value

    @staticmethod
    def _target(value, candidate_ids):
        if value is None or value == '':
            return None
        if (not isinstance(value, str) or not _TARGET.fullmatch(value)
                or value not in candidate_ids):
            raise ValueError('Use a current approved question target.')
        return value

    def remember(self, owner, chain, policy, user, reply, question,
                 question_target=None, agenda_update=None, goal=None,
                 candidate_ids=(), education_record=None, task_work_record=None,
                 learner_record=None, continuation=None, discourse_note=None, request_id=None):
        """Remember one completed exchange after the caller validates its reports.

        ``goal`` is an optional explicit-user-report patch supplied by the caller;
        an empty string clears it. Model agenda updates can change only the
        current concern and pause state. A null/empty question target preserves
        the previous return point during an educational side answer. The caller
        must check that a remembered target remains eligible before using it.

        Every exchange is kept whole (D155); each field is already bounded by
        ``_text`` (8,000 characters per message or reply).
        """
        with self._lock:
            key = self._permitted(owner, chain, policy)
            if policy != CONTEXT_POLICY:
                return False
            if key is None:
                raise ValueError('Use an owner-bound active visit.')
            exchange = {
                'user': self._text(user, 8000, 'message'),
                'assistant': self._text(reply, 8000, 'reply'),
                'question': self._text(question, 2000, 'question'),
            }
            if not isinstance(candidate_ids, (list, tuple, set, frozenset)):
                raise ValueError('Use the current question candidate IDs.')
            target = self._target(question_target, candidate_ids)
            if agenda_update is None:
                agenda_update = {}
            if (not isinstance(agenda_update, dict)
                    or set(agenda_update) - {'current_concern', 'pause'}):
                raise ValueError('Use bounded conversation agenda updates.')
            if 'current_concern' in agenda_update:
                concern = agenda_update['current_concern']
                if concern is not None:
                    self._text(concern, 160, 'current concern')
            if 'pause' in agenda_update and type(agenda_update['pause']) is not bool:
                raise ValueError('Use an explicit boolean pause state.')
            if goal is not None:
                self._text(goal, 200, 'goal')
            education = validate_record(education_record) if education_record is not None else None
            task_work = validate_work_record(task_work_record) if task_work_record is not None else None
            learner = validate_learner(learner_record) if learner_record is not None else None
            continuation = checked_continuation(continuation) if continuation is not None else None

            # Validation is complete before mutating any active visit.
            memory = copy.deepcopy(self._visits.get(key, {
                'exchanges': [], 'brief': {}, 'expires': 0,
            }))
            brief = memory['brief']
            if continuation is not None:
                brief['continuation'] = continuation
            if education is not None:
                memory['education'] = education
            if task_work is not None:
                memory['task_work'] = task_work
            if learner is not None:
                memory['learner'] = learner
            if goal is not None:
                if goal:
                    brief['goal'] = goal
                else:
                    brief.pop('goal', None)
            if 'current_concern' in agenda_update:
                if agenda_update['current_concern']:
                    brief['current_concern'] = agenda_update['current_concern']
                else:
                    brief.pop('current_concern', None)
            if 'pause' in agenda_update:
                brief['paused'] = agenda_update['pause']
            if target is not None:
                brief['pending_question'] = target
            if discourse_note:
                # Rolling discourse brief: bounded, visit-only, never saved.
                note = self._text(discourse_note, 160, 'discourse note')
                notes = [item for item in brief.get('discourse', []) if item != note]
                notes.append(note)
                while len(notes) > DISCOURSE_NOTES or sum(map(len, notes)) > DISCOURSE_CHARS:
                    notes.pop(0)
                brief['discourse'] = notes

            exchanges = memory['exchanges']
            request_ids = memory.get('request_ids', [None] * len(exchanges))
            exchanges.append(exchange)
            request_ids.append(request_id)
            # D155: keep the whole visit. Only the RAM guard evicts, oldest first.
            while len(exchanges) > 1 and sum(len(text) for item in exchanges for text in item.values()) > HISTORY_RAM_BYTES:
                exchanges.pop(0)
            memory['request_ids'] = request_ids[-len(exchanges):]
            memory.update(exchanges=exchanges,
                          expires=self._clock() + HISTORY_TTL)
            self._visits.pop(key, None)
            self._visits[key] = memory
            while len(self._visits) > VISIT_LIMIT:
                self._visits.popitem(last=False)
            return True

    def clear(self, owner, chain):
        """Forget this visit without touching another owner or visit."""
        with self._lock:
            self._prune()
            self._visits.pop(self._key(owner, chain), None)

    def forget_owner(self, owner):
        """Forget every RAM-only visit belonging to an authenticated owner."""
        with self._lock:
            self._prune()
            if not isinstance(owner, str) or not owner or len(owner) > 256:
                return
            for key in [key for key in self._visits if key[0] == owner]:
                del self._visits[key]
