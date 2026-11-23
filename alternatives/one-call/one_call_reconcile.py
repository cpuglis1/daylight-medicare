"""The background record pass of the one-call loop.

The one model call of a typed turn is asked to save every fact the person
stated. When it forgets one, that fact would be lost until the person repeats
it. After a reply has been delivered, this pass runs advisor-first's EXISTING
extraction stage (``NaturalAgent.extract``, the first request of the two-call
loop) on the same message against the state the turn ended with. Anything it
proposes goes through the same gates the save tool uses; what those gates
accept and the profile does not already hold is kept in server RAM for the
start of that visit's next typed turn. The conversation applies a held fact
there only when its field is still open.

What this pass never does:

- change a guide or a record between turns (the browser holds both);
- raise into the request path (every failure ends in a counted category);
- log a message, a value or a proposal (fixed text, counts and class names);
- persist anything (RAM only, same time-to-live and visit cap as the dialogue).

The context the extraction stage needs is built on the request thread, after
the reply is final, because it reads visit state that the next turn may change.
Only the model request and the classification run on the worker.

Switch: ``DAYLIGHT_ONE_CALL_RECONCILE`` (default on; ``0`` turns it off).
"""
import _paths  # noqa: F401  (puts advisor-first on sys.path and registers the pinned engine)

from collections import Counter, OrderedDict
import copy
from contextvars import copy_context
import logging
import os
import threading
import time

from adaptive_flow import metadata
from advisor_memory import CONTEXT_POLICY, HISTORY_TTL, VISIT_LIMIT
from chat import ModelUnavailable
from education import catalog_context, learning_context
from guest_profiles import ProfileError
from log_guard import install as install_log_guard
from natural_state import legacy_projection
from turn_contract import question_binding
import conversation_planner
import conversation_records
import enrollment_flow
import learner_state

LOGGER = logging.getLogger(__name__)
install_log_guard((__name__,))

SWITCH = 'DAYLIGHT_ONE_CALL_RECONCILE'
MAX_HELD = 24            # facts held for one visit; the save tool's own bound on one call
MAX_WORKERS = 2          # background model requests running at once, across all visits
MAX_CLEARED = 4096       # visits and owners whose latest clearing is remembered
CATEGORIES = ('scheduled', 'switched_off', 'busy', 'context_failed', 'unavailable', 'failed', 'completed', 'withdrawn',
              'proposals', 'held', 'already_known', 'needs_confirmation', 'rejected', 'applied', 'not_open',
              'not_accepted')


def switch_on():
    return os.environ.get(SWITCH, '1').strip().lower() not in {'0', 'off', 'false', 'no'}


# ---------------------------------------------------------------------------
# Extraction proposals in the save tool's update shape
# ---------------------------------------------------------------------------

def _text(value):
    return value if isinstance(value, str) else '' if value is None else str(value)


def _update(identifier, fields, proposal, entity=None):
    return {'id': identifier, 'entity': entity,
            'fields': [{'key': key, 'value': _text(value)} for key, value in fields.items()],
            'quote': _text(proposal.get('quote')), 'subject': _text(proposal.get('subject')) or 'beneficiary',
            'scope': _text(proposal.get('scope')) or 'current',
            'uncertain': bool(proposal.get('uncertain')), 'correction': bool(proposal.get('correction'))}


def tool_updates(result):
    """Every report the extraction stage proposed, as ``save_profile_fields`` updates.

    Three kinds reach advisor-first's controller separately (catalog updates,
    situation proposals and coverage reports); the save tool takes all three
    through one shape. Nothing is decided here: the tool's gates decide.
    """
    from one_call_tools import COVERAGE_IDS
    by_kind = {kind: identifier for identifier, kind in COVERAGE_IDS.items()}
    updates = []
    if not isinstance(result, dict):
        return updates
    for item in result.get('updates') or []:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str):
            continue
        fields = item.get('fields')
        if isinstance(fields, list):
            fields = {field.get('key'): field.get('value') for field in fields if isinstance(field, dict)}
        if not isinstance(fields, dict) or not fields or any(not isinstance(key, str) for key in fields):
            continue
        entity = item.get('entity')
        updates.append(_update(item['id'], fields, item, None if entity in (None, 'profile') else _text(entity)))
    for proposal in result.get('situation_proposals') or []:
        if not isinstance(proposal, dict):
            continue
        if proposal.get('kind') == 'age65':
            fields = {}
            relative = proposal.get('relative_month')
            if isinstance(relative, str) and relative and relative != 'none':
                fields['relativeMonth'] = relative
            elif proposal.get('month') is not None:
                fields['month'] = proposal['month']
                if proposal.get('year') is not None:
                    fields['year'] = proposal['year']
            if proposal.get('first_day') in (True, False):
                fields['firstOfMonth'] = 'yes' if proposal['first_day'] else 'no'
            if fields:
                updates.append(_update('S_AGE65', fields, proposal))
        elif proposal.get('kind') == 'retirement' and proposal.get('status'):
            fields = {'status': proposal['status']}
            if proposal.get('when'):
                fields['when'] = proposal['when']
            updates.append(_update('S_RETIREMENT', fields, proposal))
    for report in result.get('coverage_reports') or []:
        if not isinstance(report, dict):
            continue
        kind = report.get('kind')
        if kind == 'birth' and report.get('month') is not None and report.get('year') is not None:
            updates.append(_update('S_AGE65', {'birthMonth': report['month'], 'birthYear': report['year']}, report))
        elif kind in ('part_a', 'part_b') and report.get('status'):
            fields = {'status': report['status']}
            for key in ('month', 'year'):
                if report.get(key) is not None:
                    fields[key] = report[key]
            updates.append(_update(by_kind[kind], fields, report))
        elif kind == 'held_plan':
            fields = {key: report[key] for key in ('product', 'name', 'carrier', 'letter') if report.get(key)}
            if fields:
                updates.append(_update(by_kind[kind], fields, report))
    return updates[:MAX_HELD]


def still_open(flow, runner, update):
    """Whether the field an update fills has no saved answer on the runner's working copies."""
    from one_call_tools import COVERAGE_IDS
    identifier = update.get('id')
    if identifier in COVERAGE_IDS:
        kind = COVERAGE_IDS[identifier]
        path = (conversation_records.REPORTED_FIELD if kind == 'held_plan'
                else enrollment_flow.PART_FIELDS['A' if kind == 'part_a' else 'B'])
        return flow.value(runner.guide, path) in (None, '', [], {})
    return update.get('entity') is None and identifier in runner.open_ids()


# ---------------------------------------------------------------------------
# The context advisor-first's typed-message step gives its extraction stage
# ---------------------------------------------------------------------------

def extraction_context(flow, owner, chain, guide, record, asked, message):
    """Mirror of the context ``natural_flow.NaturalConversation.message`` builds before ``agent.extract``.

    ``asked`` is the question that was on screen when the person wrote the
    message. The pending-question view is left empty: the question delivered
    by the turn that just ended was asked after this message.
    """
    policy = CONTEXT_POLICY
    g, r = guide, record
    context = flow.context(g, r, policy, asked)
    if conversation_planner.enabled(flow):
        context['discussion_enabled'] = True
        if not hasattr(flow, 'discussion_visits'):
            flow.discussion_visits = conversation_planner.VisitPlans()
        prior = flow.discussion_visits.get(owner, chain)
        context['discussion_context'] = {key: copy.deepcopy(prior[key])
            for key in ('purpose', 'focus', 'exploring', 'investigate', 'decision',
                        'active_task', 'suggested_task', 'task_checks')}
        context['discussion_capabilities'] = conversation_planner.conversation_tasks.context(flow, g, r)
        context['question_progress'] = conversation_planner.question_progress.snapshot(
            flow, g, r, prior.setdefault('question_progress', {}))
        context['open_requests'] = copy.deepcopy(prior.get('open_requests', []))
        if conversation_records.enabled(flow):
            context['records_enabled'] = True
            context['profile_record'] = conversation_records.compact_profile(conversation_records.profile_view(
                flow, owner, g, r, prior.get('question_progress')))
            context['readiness'] = conversation_records.compact_readiness(
                conversation_records.readiness(flow, owner, g, r, prior))
            context['education_record'] = conversation_records.education_view(prior)
            if conversation_records.fixes_on(flow):
                context['fixes_enabled'] = True
            if conversation_records.pending_on(flow):
                context['pending_enabled'] = True
                context['profile_record']['pending'] = None
    recent = flow.memory.recent(owner, chain, policy)
    if recent and recent[-1].get('user') == message:
        recent = recent[:-1]            # the exchange this pass re-reads is not its own history
    safe_reports = {x['id'][6:]: x['value'] for x in context['reports']
                    if x['id'] in {'guide.intent.goal', 'guide.knowledge.general', 'guide.subject.role', 'guide.coverage.current'}
                    and x['status'] in {'reported', 'derived'}}
    active = flow.permitted_question(asked, policy)
    meta = metadata(r)
    context.update(task=meta['task'], preparing=meta['preparing'], lastFactIds=meta['lastFactIds'],
                   activeQuestion=active, definitions=flow.agent.definitions, safeReports=safe_reports, pending=False)
    context['teachingCandidates'] = flow.teaching_candidates(g, r, asked)
    identifier = (asked or {}).get('id')
    context['answer_context'] = question_binding(
        active, flow.value(g, 'subject.role'),
        {'S_AGE65': ['month', 'year', 'first_day'], 'S_RETIREMENT': ['status', 'when']}.get(identifier, ()),
        subject='learner' if identifier in {'T01', 'T02'} else 'beneficiary')
    context['advisor_brief'] = flow.advisor_brief(owner, g, r, policy, flow.eligible(owner, g, r))
    context['recent_exchanges'] = recent
    context['education_context'] = {'learning': learning_context(flow.memory.education(owner, chain, policy)),
                                    'catalog': catalog_context()}
    context['learner_context'] = learner_state.context(flow.memory.learner(owner, chain, policy))
    return context


# ---------------------------------------------------------------------------
# The reconciler
# ---------------------------------------------------------------------------

def _thread(work):
    threading.Thread(target=work, name='daylight-one-call-reconcile', daemon=True).start()


class Reconciler:
    """Runs the record pass and holds what it found until the visit's next typed turn.

    ``executor`` is a callable that takes one no-argument function. The default
    starts a daemon thread; a test passes ``lambda work: work()`` to run it at once.
    ``enabled`` overrides the environment switch when it is not None.
    """

    def __init__(self, flow, *, executor=None, enabled=None, clock=None, ttl=HISTORY_TTL, limit=VISIT_LIMIT):
        self.flow = flow
        self.executor = executor or _thread
        self._enabled = enabled
        self._clock = clock or time.monotonic
        self.ttl, self.limit = ttl, limit
        self._held = OrderedDict()
        self._running = set()
        self._lock = threading.RLock()
        self.stats = Counter()
        # A pass belongs to the permission it was scheduled under. Every clearing of a visit or
        # an owner is stamped; a pass stamped earlier than a clearing is withdrawn before it
        # sends anything and before it holds anything.
        self._tick = 0
        self._cleared = OrderedDict()
        self._floor = 0

    @property
    def enabled(self):
        return switch_on() if self._enabled is None else bool(self._enabled)

    @enabled.setter
    def enabled(self, value):
        self._enabled = value

    def _count(self, category, amount=1):
        if category in CATEGORIES and amount:
            with self._lock:
                self.stats[category] += amount

    def _stamp(self):
        with self._lock:
            self._tick += 1
            return self._tick

    def _current(self, owner, chain, stamp):
        """Whether nothing cleared this visit or its owner since the pass was scheduled."""
        with self._lock:
            return (stamp > self._floor and stamp > self._cleared.get(owner, 0)
                    and stamp > self._cleared.get((owner, chain), 0))

    def _prune(self):
        now = self._clock()
        for key in [key for key, value in self._held.items() if value['expires'] <= now]:
            del self._held[key]

    # -- after a delivered reply ------------------------------------------------

    def schedule(self, owner, chain, *, message, guide, record, asked=None, request_id='', today=None, agent=None):
        """Queue one pass for the turn that just ended. Returns whether it was queued."""
        if not self.enabled:
            self._count('switched_off')
            return False
        key = (owner, chain)
        try:
            if (not isinstance(owner, str) or not owner or not isinstance(chain, str) or not chain
                    or not isinstance(message, str) or not message.strip()):
                return False
            flow = self.flow
            agent = agent or flow.agent
            if flow.fixture or not agent.enabled or not agent.client.available:
                return False
            with self._lock:
                if key in self._running or len(self._running) >= MAX_WORKERS:
                    self._count('busy')
                    return False
                self._running.add(key)
            try:
                guide, record = copy.deepcopy(guide), copy.deepcopy(record)
                extraction_guide, _ = legacy_projection(guide, record)
                import plans_fixes
                if plans_fixes.enabled(flow):
                    extraction_guide, _ = plans_fixes.set_aside(flow, extraction_guide)
                asked = copy.deepcopy(asked) if isinstance(asked, dict) else None
                job = {'owner': owner, 'chain': chain, 'message': message, 'guide': guide, 'record': record,
                       'extraction_guide': extraction_guide, 'agent': agent, 'today': today, 'asked': asked,
                       'stamp': self._stamp(),
                       'context': extraction_context(flow, owner, chain, guide, record, asked, message),
                       'request_id': 'rc-' + str(request_id)[:72]}
            except Exception as error:
                with self._lock:
                    self._running.discard(key)
                self._count('context_failed')
                LOGGER.warning('Daylight one-call reconcile context unavailable error=%s', type(error).__name__)
                return False
            self._count('scheduled')
            try:
                # Carry hosted invitation/consent accounting into the worker. A
                # fresh context per job also keeps simultaneous visitors isolated.
                context = copy_context()
                self.executor(lambda: context.run(self._work, job))
            except Exception as error:
                with self._lock:
                    self._running.discard(key)
                self._count('failed')
                LOGGER.warning('Daylight one-call reconcile not started error=%s', type(error).__name__)
                return False
            return True
        except Exception as error:      # never into the request path
            self._count('failed')
            LOGGER.warning('Daylight one-call reconcile not scheduled error=%s', type(error).__name__)
            return False

    def _work(self, job):
        key = (job['owner'], job['chain'])
        try:
            if not self._current(job['owner'], job['chain'], job['stamp']):
                # The visit was cleared after this pass was queued: the message is not sent.
                self._count('withdrawn')
                return
            result = self._extract(job)
            if result is None:
                return
            kept = self._classify(job, tool_updates(result))
            if kept:
                with self._lock:
                    if not self._current(job['owner'], job['chain'], job['stamp']):
                        # Cleared while the request was in flight: nothing from it is kept.
                        self._count('withdrawn')
                        return
                    self._prune()
                    entry = self._held.pop(key, {'items': []})
                    entry['items'] = (entry['items'] + [{'update': update, 'message': job['message'], 'asked': job['asked']}
                                                        for update in kept])[-MAX_HELD:]
                    entry['expires'] = self._clock() + self.ttl
                    self._held[key] = entry
                    while len(self._held) > self.limit:
                        self._held.popitem(last=False)
            self._count('completed')
            LOGGER.info('Daylight one-call reconcile completed held=%s', len(kept))
        except Exception as error:      # a worker has nowhere to raise to
            self._count('failed')
            LOGGER.warning('Daylight one-call reconcile failed error=%s', type(error).__name__)
        finally:
            with self._lock:
                self._running.discard(key)

    def _extract(self, job):
        """One request on its own reservation. None when the stage was unavailable."""
        agent = job['agent']
        reservation = None
        try:
            # A worker thread starts with empty per-thread agent state; set what a turn sets.
            for name, value in (('model_stages', []), ('stage_timings', {}), ('block_release', None),
                                ('block_guard', None), ('block_tap', None)):
                setattr(agent.local, name, value)
            reservation = agent.reserve_turn(stages=('extract',))
            return agent.extract(job['owner'], job['message'], job['extraction_guide'], job['context'],
                                 job['request_id'], reservation)
        except (ModelUnavailable, ProfileError) as error:
            self._count('unavailable')
            LOGGER.info('Daylight one-call reconcile unavailable error=%s', type(error).__name__)
            return None
        finally:
            if reservation:
                reservation.close()

    def _classify(self, job, proposals):
        """Keep what the save tool's gates accept on a copy of the post-turn state."""
        from one_call_tools import ToolRunner
        self._count('proposals', len(proposals))
        if not proposals:
            return []
        runner = ToolRunner(self.flow, job['owner'], job['guide'], job['record'], job['message'], today=job['today'],
                            asked=job['asked'])
        kept = []
        # Who the coverage is for first, as the tool orders one call's updates.
        for update in sorted(proposals, key=lambda item: item['id'] != 'RC01'):
            output = runner.run('save_profile_fields', {'updates': [update]})
            outcomes = output.get('outcomes') if isinstance(output, dict) and output.get('ok') else None
            status = outcomes[0].get('status') if outcomes else 'rejected'
            if status == 'accepted':
                kept.append(update)
                self._count('held')
            else:
                self._count(status if status in ('already_known', 'needs_confirmation') else 'rejected')
        return kept

    # -- at the start of the next typed turn ----------------------------------------

    def held(self, owner, chain):
        """How many facts are waiting for this visit."""
        with self._lock:
            self._prune()
            return len(self._held.get((owner, chain), {}).get('items', []))

    def apply(self, owner, chain, guide, record, *, today=None):
        """Apply this visit's held facts to copies, through the save tool's own path.

        Returns ``(guide, record, applied_ids, taken)``. Nothing is removed
        from the hold: the caller calls ``consume(owner, chain, taken)`` once
        the turn that used them has been delivered. A fact whose field is no
        longer open is skipped.
        """
        from one_call_tools import ToolRunner
        if not self.enabled:
            return guide, record, [], 0
        with self._lock:
            self._prune()
            items = copy.deepcopy(self._held.get((owner, chain), {}).get('items', []))
        applied = []
        for item in items:
            try:
                runner = ToolRunner(self.flow, owner, guide, record, item['message'], today=today, asked=item.get('asked'))
                if not still_open(self.flow, runner, item['update']):
                    self._count('not_open')
                    continue
                output = runner.run('save_profile_fields', {'updates': [item['update']]})
                outcomes = output.get('outcomes') if isinstance(output, dict) and output.get('ok') else None
                if outcomes and outcomes[0].get('status') == 'accepted':
                    guide, record = runner.guide, runner.record
                    applied.append(item['update']['id'])
                    self._count('applied')
                else:
                    self._count('not_accepted')
            except Exception as error:
                self._count('failed')
                LOGGER.warning('Daylight one-call reconcile fact not applied error=%s', type(error).__name__)
        return guide, record, applied, len(items)

    def consume(self, owner, chain, taken):
        """Drop the first ``taken`` held facts of a visit (the ones ``apply`` returned)."""
        with self._lock:
            entry = self._held.get((owner, chain))
            if not entry or taken <= 0:
                return
            entry['items'] = entry['items'][taken:]
            if not entry['items']:
                del self._held[(owner, chain)]

    def discard(self, owner, chain=None):
        """Forget what is held for a visit, or for every visit of an owner, and withdraw any
        pass still queued or in flight for it."""
        with self._lock:
            self._tick += 1
            self._cleared[owner if chain is None else (owner, chain)] = self._tick
            self._cleared.move_to_end(owner if chain is None else (owner, chain))
            while len(self._cleared) > MAX_CLEARED:
                # Forgetting a clearing must never revive an older pass.
                self._floor = max(self._floor, self._cleared.popitem(last=False)[1])
            for key in [key for key in self._held if key[0] == owner and (chain is None or key[1] == chain)]:
                del self._held[key]
