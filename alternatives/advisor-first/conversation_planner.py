"""D166: discussion-led planning for the unified demo only.

The interpreter proposes meaning and the composer selects a useful supported
question; this module validates their contracts. It neither ranks plans nor admits evidence.
Planning memory is bounded, visit-only and never part of a saved profile.
"""
from collections import OrderedDict
import copy
import hashlib
import json
import re
import threading
import time

from adaptive_flow import AdaptiveConversation, metadata
from advisor_memory import HISTORY_TTL, VISIT_LIMIT
import enrollment_flow
import medigap_profile
import part_d_profile
import journey_completion
import conversation_tasks
import question_progress

VERSION = 'discussion-planner-v1'
# D200: a pause ends intake. The interpreter's pause stays semantic (D173), but
# words about pace or purpose ("slow down", "why do you need that?") without a
# stop request are not a pause: Daylight answers, keeps the visit open and
# offers choices, one of which is to stop for today.
STOP_REQUEST = re.compile(
    r"(?i)\b(?:no more questions|stop (?:asking|the questions|here|for (?:now|today))|pause|that(?:'s| is) (?:all|enough|it) for (?:now|today)|"
    r"(?:i'm|i am|we're|we are) done|enough for (?:now|today)|let's stop|leave it (?:here|there)|talk (?:later|tomorrow)|"
    r"come back (?:later|tomorrow|another (?:day|time))|good(?:bye|night)|bye for now|don't ask (?:me )?(?:any ?more|another)|"
    r"no (?:more|further) questions)\b")
PACE_REQUEST = re.compile(
    r"(?i)\b(?:slow(?:er| down| it down| this down)|too (?:fast|quick(?:ly)?|much|many questions)|(?:a lot|lots|so many) of questions|"
    r"overwhelm\w*|why (?:do|would|does) (?:you|daylight|it) (?:need|want|ask)|why (?:are you|you're) asking|"
    r"what(?:'s| is) (?:that|this) for|why does (?:that|this|it) matter)")
PACE_CHOICES = (('Skip this question for now', 'Skip this question for now.'),
                ('Tell me my options first', 'Before more questions, tell me about my options.'),
                ('Explain more simply', 'Explain that more simply.'),
                ('Stop for today', "Let's stop for today."))


def pace_card():
    return {'kind': 'next_step_offer', 'title': 'What would help right now?', 'pace': True,
            'actions': [{'label': label, 'say': say} for label, say in PACE_CHOICES]}
DECISION_VERSION = 'intent.decisionVersion'
COMPONENT_VERSION = 'intent.componentDecisionVersion'
PURPOSES = ('none', 'understand', 'review', 'problem', 'compare', 'investigate')
FOCI = ('', 'coverage_paths', 'original', 'medigap', 'advantage', 'part_d', 'enrollment',
        'doctors', 'medicines', 'costs', 'flexibility')
INVESTIGATIONS = ('medigap', 'advantage', 'part_d', 'doctors', 'medicines')
PATHS = ('', 'original', 'original_medigap', 'medicare_advantage', 'original_only', 'keep_current', 'wait')
DISCUSSION_QUESTIONS = {
    'CP_PURPOSE': ('What would you like help working through today?', ''),
    'CP_REASON': ('What prompted you to look at your coverage now?',
                  'That helps connect the options to what you want to change or understand.'),
    'CP_REACTION': ('What feels most important or still unclear as you weigh those options?', ''),
    'CP_UNDERSTANDING': ('Which part would help to make clearer?', ''),
    'CP_INVESTIGATE': ('Which would you like to investigate: Original Medicare options, Medicare Advantage, or both?', ''),
    'CP_NEXT': ('What would help you make your next decision?', ''),
    'CP_RETRY': ('Would you like to rephrase that question or leave it open for now?', ''),
    'CP_PARTS': ('Your reports about Parts A and B conflict. Which parts are in effect now?', ''),
    'CP_COVERAGE': ('You reported an Advantage or Medigap policy and a Medicare part that is not in effect. Which coverage is current?', ''),
}
# Compatibility exports; each stage now uses this one complete prompt.
from conversation_prompts import INTERPRETATION, COMPOSITION


def enabled(flow):
    return bool(getattr(flow, 'd166', False))


def records_on(flow):
    return bool(getattr(flow, 'records_v1', False))


def enable(flow):
    node = next(node for node in flow.contract['nodes'] if node['id'] == 'R00')
    for field in (DECISION_VERSION, COMPONENT_VERSION):
        if field not in node['writes']:
            node['writes'].append(field)
    flow.d166 = True


def schema(make):
    return make({
        'purpose': {'type': 'string', 'enum': list(PURPOSES)},
        'focus': {'type': 'string', 'enum': list(FOCI)},
        'quote': {'type': 'string', 'maxLength': 600},
        'reason_quote': {'type': 'string', 'maxLength': 600},
        'question_quote': {'type': 'string', 'maxLength': 600},
        'investigate': {'type': 'array', 'maxItems': 5, 'items': {'type': 'string', 'enum': list(INVESTIGATIONS)}},
        'request_quote': {'type': 'string', 'maxLength': 600},
        'uncertain': {'type': 'boolean'},
        'guidance': conversation_tasks.schema(make),
        'decision': make({'stance': {'type': 'string', 'enum': ['none', 'leaning', 'chosen', 'undecided']},
                          'path': {'type': 'string', 'enum': list(PATHS)},
                          'quote': {'type': 'string', 'maxLength': 600}}),
    })


def empty_proposal():
    return dict(purpose='none', focus='', quote='', reason_quote='', question_quote='', investigate=[],
                request_quote='', uncertain=False, guidance=conversation_tasks.empty(), decision=dict(stance='none', path='', quote=''))


def supported(quote, message):
    return isinstance(quote, str) and 0 < len(quote.strip()) <= 600 and quote.casefold() in message.casefold()


# These are conservative action guards, not the semantic planner. An unfamiliar
# decision expression remains a discussion, rather than an unreviewed write.
UNREAL = re.compile(r"\b(?:if|suppose|hypothetically|for example|used to|might|maybe|wonder|considering)\b", re.I)
NEGATED = re.compile(r"\b(?:not|never|don['’]?t|do not|haven['’]?t|haven't|won['’]?t|without)\b", re.I)
LEARNING = re.compile(r'\b(?:understand|explain\w*|learn|mean|works?|difference|curious|explor\w*|tell me about)\b', re.I)
DECIDING = re.compile(r"\b(?:I(?:['’]m| am) (?:choosing|going with|keeping|waiting)|I (?:choose|pick|prefer|want|have decided)|"
                      r"I['’]ll (?:keep|wait|go with)|let['’]s (?:go with|choose)|we (?:choose|want))\b", re.I)


def explicit_components(message):
    """Validate component intentions separately from coverage ownership.

    Reuse the component vocabulary, but never its legacy have=keep shortcut.
    Questions, hypothetical decisions and attributed speech cannot write state.
    """
    found = {}
    for clause in re.split(r'(?<=[.!?])\s+|;', message.replace('’', "'")):
        if re.match(r'^\s*(?:please )?keep (?:my (?:current )?)?(?:plan [a-dfgk-n]|medigap|supplement)\b', clause, re.I):
            clause = 'I will ' + re.sub(r'^\s*please ', '', clause, flags=re.I).lstrip()
        if ('?' in clause or UNREAL.search(clause) or LEARNING.search(clause) or INVESTIGATING.search(clause)
                or re.search(r'\b(?:says?|said|should|could|would|whether)\b', clause, re.I)):
            continue
        if not re.search(r"\b(?:I|we)(?:'m|'re|'ll| am| are| will)?\s+(?:keep\w*|stay\w*|stick\w*|choose|chose|pick|picked|want|add|take|get|buy|decide|skip\w*|don'?t want|do not want|won'?t get)\b", clause, re.I):
            continue
        changes = enrollment_flow.choices_from_text(clause)['components']
        if re.search(r'\b(?:keep\w*|stay\w* with|stick\w* with)\b.{0,30}\bplan [a-dfgk-n]\b', clause, re.I):
            changes['medigap'] = 'keep_existing'
        # Choosing the Medigap category is not choosing an individual policy.
        if changes.get('medigap') == 'chosen' and not re.search(r'\bplan [a-dfgk-n]\b', clause, re.I):
            changes.pop('medigap')
        found.update(changes)
    return found
INVESTIGATING = re.compile(r'\b(?:prices?|pricing|premiums?|quotes?|how much|costs?|show|find|look at|see|compare|review|check|investigate)\b', re.I)
PRODUCTS = {
    'medigap': re.compile(r'\b(?:medigap|supplement|plan [a-n])\b', re.I),
    'advantage': re.compile(r'\b(?:advantage|part c|hmo|ppo)\b', re.I),
    'part_d': re.compile(r'\b(?:part d|drug plans?|prescription plans?)\b', re.I),
    'doctors': re.compile(r'\b(?:doctor|provider|hospital|specialist|network)\w*\b', re.I),
    'medicines': re.compile(r'\b(?:medicine|medication|prescription|drug|pharmacy)\w*\b', re.I),
}


def validate_proposal(value, message, focus=''):
    """Bound and ground hints; reject unsafe action/decision interpretations.

Quote matching proves provenance, not universal semantic entailment. The extra
action guards fail closed; a rejected hint never rejects independent reports.
"""
    out = empty_proposal()
    if not isinstance(value, dict) or set(value) != set(out):
        return out
    if value['purpose'] not in PURPOSES or value['focus'] not in FOCI or type(value['uncertain']) is not bool:
        return out
    if supported(value['quote'], message):
        out.update(purpose=value['purpose'], focus=value['focus'], quote=value['quote'], uncertain=value['uncertain'])
    if supported(value['question_quote'], message):
        out['question_quote'] = value['question_quote']
    if supported(value['reason_quote'], message):
        out['reason_quote'] = value['reason_quote']
    out['guidance'] = conversation_tasks.validate(value['guidance'], message)
    if value['uncertain']:
        out['guidance'] = conversation_tasks.empty()
    request, inv = value['request_quote'], value['investigate']
    if (isinstance(inv, list) and len(inv) <= 5
            and all(isinstance(k, str) and k in INVESTIGATIONS for k in inv)
            and supported(request, message) and not value['uncertain']):
        out.update(investigate=list(dict.fromkeys(inv)), request_quote=request)
    decision = value['decision']
    if (isinstance(decision, dict) and set(decision) == {'stance', 'path', 'quote'}
            and decision['stance'] in ('none', 'leaning', 'chosen', 'undecided') and decision['path'] in PATHS
            and supported(decision['quote'], message) and not value['uncertain']):
        text = decision['quote']
        if decision['stance'] == 'undecided' and re.search(r"not (?:sure|decided)|undecided|haven.t (?:chosen|decided)", text, re.I):
            out['decision'] = dict(stance='undecided', path='', quote=text)
        elif (decision['stance'] == 'chosen' and decision['path'] in ('keep_current', 'wait')
              and journey_completion.request(text) == decision['path']):
            # This validates a decision; it never routes conversational work.
            out['decision'] = copy.deepcopy(decision)
        elif (decision['path'] and '?' not in message and not UNREAL.search(message) and not NEGATED.search(message)
              and not LEARNING.search(message) and not re.search(r'\b(?:prices?|quotes?|pricing|premiums?|says?|said)\b', message, re.I)
              and (DECIDING.search(text) or decision['stance'] == 'leaning' and re.search(r"\bI(?:['’]m| am) leaning\b", text, re.I))):
            expected = {'original': r'\boriginal medicare\b', 'original_medigap': r'\bmedigap\b|\bsupplement\b',
                        'medicare_advantage': r'\badvantage\b', 'original_only': r'\b(?:parts? a and b|original medicare) only\b',
                        'keep_current': r'\bkeep(?:ing)?\b', 'wait': r'\bwait(?:ing)?\b'}[decision['path']]
            if re.search(expected, text, re.I):
                out['decision'] = copy.deepcopy(decision)
                if re.search(r'\b(?:prefer|leaning)\b', text, re.I):
                    out['decision']['stance'] = 'leaning'
    return out




class VisitPlans:
    """Same bounded visit boundary as conversation memory; no disk writes."""
    def __init__(self):
        self.visits = OrderedDict()
        self.lock = threading.RLock()

    def get(self, owner, chain):
        with self.lock:
            now = time.monotonic()
            for key in [k for k, v in self.visits.items() if v['expires'] <= now]:
                del self.visits[key]
            key = (owner, chain)
            if key not in self.visits:
                self.visits[key] = {'purpose': 'none', 'focus': '', 'investigate': [], 'exploring': [],
                    'decision': {'stance': 'undecided', 'path': ''}, 'latest': empty_proposal(),
                    'guidance': conversation_tasks.empty(), 'active_task': '', 'suggested_task': '', 'task_checks': [],
                    'question_progress': {}, 'open_requests': [], 'deferred': [], 'reason_known': False, 'cards': {}, 'plan': {}, 'expires': now + HISTORY_TTL}
            self.visits.move_to_end(key)
            while len(self.visits) > VISIT_LIMIT:
                self.visits.popitem(last=False)
            self.visits[key]['expires'] = now + HISTORY_TTL
            return self.visits[key]

    def clear(self, owner, chain=None):
        with self.lock:
            for key in [k for k in self.visits if k[0] == owner and (chain is None or k[1] == chain)]:
                del self.visits[key]


def state(flow, owner):
    if not hasattr(flow, 'discussion_visits'):
        flow.discussion_visits = VisitPlans()
    return flow.discussion_visits.get(owner, flow.current_chain.get(owner))


def question(identifier):
    if identifier not in DISCUSSION_QUESTIONS:
        return None
    words, why = DISCUSSION_QUESTIONS[identifier]
    q = dict(id=identifier, entity='profile', question=words, why=why, fields=[], choices=[],
             multi=False, signature=VERSION + ':' + identifier, conversational=True)
    return q


def pending_on(flow):
    if not records_on(flow):
        return False
    import conversation_records
    return conversation_records.pending_on(flow)


def observe(flow, owner, g, r, message, result, current=None, outcomes=()):
    s = state(flow, owner)
    s.pop('outcome', None)
    if (isinstance(message, str) and message.strip() == PACE_CHOICES[0][1] and isinstance(current, dict)
            and current.get('id') and current['id'] not in ('RC01', 'T03') and current['id'] not in s['deferred']):
        s['deferred'].append(current['id'])   # D200: the "Skip this question for now" tap sets it aside for this visit
    if records_on(flow):
        # D183: the interpreter's proposed next profile field(s); code validates on use.
        proposal = result.get('next_target') or {}
        s['next_target'] = list(proposal.get('ids') or []) if isinstance(proposal, dict) else list(proposal)
        s['next_target_reason'] = proposal.get('reason') if isinstance(proposal, dict) else None
    if pending_on(flow):
        # D188: what this reply did with the pending question (checked by structure),
        # and whether it is a tap on the offer button shown last turn.
        import conversation_records
        conversation_records.resolve_pending(flow, owner, g, r, s, result.get('pending_disposition'), outcomes)
        s['records_offer_task'] = conversation_records.accept_offer(s, message)
    p = validate_proposal(result.get('discussion'), message, s['focus'])
    words = message if isinstance(message, str) else ''
    pace = bool(PACE_REQUEST.search(words)) and not STOP_REQUEST.search(words)
    if pace and p['guidance']['mode'] == 'pause':
        p['guidance'] = {**p['guidance'], 'mode': 'detour'}
    s['pace_request'] = pace and p['guidance']['mode'] != 'finish'
    s['latest'] = p
    guide = p['guidance']
    # Invalid/missing interpretation cannot start a task or invent a response
    # meaning. Accepted reports still survive and the existing task is retained.
    if guide['quote']:
        s['guidance'] = copy.deepcopy(guide)
        mode = guide['mode']
        if mode == 'work':
            task = guide['task'] or s['active_task'] or s['suggested_task']
            if task:
                if task != s['active_task']:
                    s['task_checks'] = []
                    s['task_investigate'] = []
                    s['plans_products'] = []
                    s['focus'] = p['focus'] or conversation_tasks.FOCI[task]
                s['active_task'] = task
                s['task_checks'] = list(dict.fromkeys(s['task_checks'] + guide['checks']))
                s['suggested_task'] = ''
        elif mode == 'suggest':
            s['suggested_task'] = guide['task']
        s['education_only'] = mode in ('discuss', 'suggest', 'detour', 'pause')
    else:
        s['guidance'] = conversation_tasks.empty()
    s['finish_requested'] = (guide['finish'] or 'summary') if guide['mode'] == 'finish' else None
    # Finishing does not authorize a coverage decision.
    if s['finish_requested'] in ('keep_current', 'wait') and p['decision'].get('path') != s['finish_requested']:
        s['finish_requested'] = 'summary'
    if p['purpose'] != 'none': s['purpose'] = p['purpose']
    if p['focus']: s['focus'] = p['focus']
    if p['reason_quote']: s['reason_known'] = True
    if guide['mode'] == 'work' and s['active_task']:
        # The semantic task is separate from the conversational topic.
        allowed = conversation_tasks.INVESTIGATIONS[s['active_task']]
        s['investigate'] = [v for v in p['investigate'] if v in allowed]
        if not s['investigate']:
            s['investigate'] = [v for v in s.get('task_investigate', []) if v in allowed]
        if not s['investigate']:
            s['investigate'] = list(conversation_tasks.DEFAULT_INVESTIGATIONS.get(s['active_task'], []))
        s['task_investigate'] = list(s['investigate'])
        products = [v for v in s['investigate'] if v in ('medigap','advantage','part_d')]
        if products: s['plans_products'] = products
        s['exploring'] = list(dict.fromkeys(s['exploring'] + s['investigate']))[-5:]
        match = re.search(r'\b(?:standard )?plan ([a-dfgk-n])\b', p['request_quote'], re.I)
        if match and 'medigap' in s['investigate']:
            s['medigap_variant'] = ('HD' if re.search(r'high[ -]deductible', p['request_quote'], re.I) else '') + match.group(1).upper()
    else:
        s['investigate'] = []
    d = p['decision']
    if d['stance'] != 'none':
        s['decision'] = {k: d[k] for k in ('stance', 'path')}
        if d['stance'] in ('chosen', 'undecided') or d['stance'] == 'leaning' and flow.value(g, enrollment_flow.PATH_FIELD):
            enable(flow)
            flow.put(g, enrollment_flow.PATH_FIELD, d['path'] if d['stance'] == 'chosen' else 'undecided', 'user_text')
            flow.put(g, DECISION_VERSION, VERSION, 'user_text')
            if d['stance'] == 'chosen' and d['path'] == 'original_only':
                enrollment_flow._put_components(flow, g, {'medigap': 'not_needed', 'part_d': 'not_needed'}, 'user_text')
                flow.put(g, COMPONENT_VERSION, VERSION, 'user_text')
    components = explicit_components(message)
    if components:
        enrollment_flow._put_components(flow, g, components, 'user_text')
        flow.put(g, COMPONENT_VERSION, VERSION, 'user_text')
        # Adding Part D does not also buy Medigap; keeping a supplement does
        # not settle the drug-plan review or imply keeping all coverage.
        if flow.value(g, enrollment_flow.PATH_FIELD) == 'original_only' and any(
                value in ('chosen', 'keep_existing') for value in components.values()):
            flow.put(g, enrollment_flow.PATH_FIELD, 'original', 'user_text')
            flow.put(g, DECISION_VERSION, VERSION, 'user_text')
            s['decision'] = {'stance': 'chosen', 'path': 'original'}
    task = s['active_task'] if guide['mode'] == 'work' else ''
    report_task = 'compare' if task == 'advantage' else task
    if report_task in ('compare', 'review') and flow.value(g, 'intent.goal') != report_task:
        # This is a requested work goal, never an insurance choice. Use the
        # existing profile capture so review readiness and provenance agree.
        flow.capture(g, r, dict(id='T01', entity='profile', fields={'choice':report_task},
            quote=guide['quote'], scope='current', subject='learner'))
    metadata(r).update(task=report_task or 'learn', preparing=bool(task))
    if pending_on(flow) and s.get('records_offer_task'):
        # D188: the tap carries the task; the next question is that task's first open field.
        s['active_task'], s['suggested_task'] = s['records_offer_task'], ''


def path(flow, owner, g, r):
    s = state(flow, owner)
    d = s['decision']
    recorded = flow.value(g, enrollment_flow.PATH_FIELD)
    if (flow.value(g, DECISION_VERSION) == VERSION
            or g.get('fields', {}).get(enrollment_flow.PATH_FIELD, {}).get('source') == 'user_choice') and recorded in PATHS:
        d = {'stance': 'chosen', 'path': recorded}
    if d['stance'] in ('chosen', 'leaning') and d['path']:
        return {'state': d['stance'], 'path': d['path'], 'because': ['You chose this path.'] if d['stance'] == 'chosen' else ['You said you are leaning this way.']}
    return {'state': 'undecided', 'path': None, 'because': []}


def decision_guide(flow, g):
    """Old text heuristics have no decision authority. Keep original reports
    intact; project unconfirmed legacy choices out of enrollment guidance."""
    if not enabled(flow):
        return g
    fields = g.get('fields', {})
    unconfirmed = [key for key in (enrollment_flow.PATH_FIELD, enrollment_flow.COMPONENT_FIELD)
                   if key in fields and fields[key].get('source') != 'user_choice'
                   and flow.value(g, COMPONENT_VERSION if key == enrollment_flow.COMPONENT_FIELD else DECISION_VERSION) != VERSION]
    return {**g, 'fields': {key: value for key, value in fields.items() if key not in unconfirmed}} if unconfirmed else g


def candidate(flow, g, r, identifier, purpose='', priority=1):
    q = question(identifier) or flow.contextual_question(g, r, flow.question(identifier))
    return dict(id=identifier, question=copy.deepcopy(q), topic='', priority=priority, required=False,
                purpose=purpose or q.get('why') or 'Continue this discussion.') if q else None


def timing_ask(flow, owner, g, r, s, probe=False):
    """D181: details asked before the close: the birthday month when it lets code
    compute the sign-up window, then Medigap price details when the close will point
    to Medigap. Each is counted and parked like any other question; none blocks forever."""
    asks = [journey_completion.timing_question(flow, g, r)] + journey_completion.medigap_before_close(flow, g, r, s)
    asks = [ask for ask in asks if ask]
    dispositions = {**metadata(r).get('baselineDispositions', {}), **r.get('dispositions', {})}
    asks = [ask for ask in asks if ask not in dispositions and ask not in s.get('deferred', [])]
    if not asks or not journey_completion.readiness(g, r, pending=flow.pending_for(owner)).get('canReview'):
        return []
    ledger = s.setdefault('question_progress', {})
    if probe:
        ledger = copy.deepcopy(ledger)
    for ask in asks:
        picked = candidate(flow, g, r, ask)
        if not picked:
            continue
        found = question_progress.filter_candidates(flow, owner, g, r, [{**picked, 'required': True}], ledger)
        if found:
            return found
    return []


def refine(flow, owner, g, r, candidates):
    s = state(flow, owner)
    def checked(items):
        return question_progress.filter_candidates(flow,owner,g,r,items,s.setdefault('question_progress',{}))
    if s.get('finish_requested') or s['guidance']['mode'] == 'pause': return []
    if metadata(r).get('editing'): return checked(candidates)
    reports = [flow.value(g, field) or {} for field in enrollment_flow.PART_FIELDS.values()]
    if any(report.get('status') == 'conflicting' for report in reports):
        return checked([{**candidate(flow, g, r, 'CP_PARTS'), 'required':True}])
    if (set(flow.value(g, 'coverage.current') or []) & {'advantage','medigap'}
            and any(report.get('status') == 'not_enrolled' for report in reports)):
        return checked([{**candidate(flow, g, r, 'CP_COVERAGE'), 'required':True}])
    if records_on(flow):
        # D183: the profile drives the next question. Every open, unparked field is
        # available in any mode; the interpreter's target leads; no task/check gate.
        import conversation_records
        s['records_precedence'] = conversation_records.precedence(flow, owner, g, r)
        required = [c for c in candidates if c.get('required')]
        if required: return checked(required)
        if s['records_precedence']: return []      # the confirmation or correction is asked first
        if pending_on(flow) and conversation_records.standing_pending(flow, owner, g, r, s):
            # D188: a question still waiting for its answer comes before any new one.
            s['records_preclose'] = False
            return conversation_records.candidates(flow, owner, g, r, s, checked)
        timed = timing_ask(flow, owner, g, r, s)
        s['records_preclose'] = bool(timed)        # D190: a detail asked before the close
        if timed: return timed
        if journey_completion.closing_due(flow,owner,g,r,s): return []
        return conversation_records.candidates(flow, owner, g, r, s, checked)
    if s['guidance']['mode'] not in ('work', 'detour') or not s['active_task']:
        return []
    required = [c for c in candidates if c.get('required')]
    if required: return checked(required)
    timed = timing_ask(flow, owner, g, r, s)
    if timed: return timed
    if journey_completion.closing_due(flow,owner,g,r,s): return []
    selected = conversation_tasks.candidates(flow, g, r, s['active_task'], s['task_checks'])
    # Existing product profiles own their required inputs and supported scope.
    for product in s['investigate']:
        if product not in ('medigap','part_d','advantage'): continue
        view = medigap_profile.for_flow(flow, g, r) if product == 'medigap' else part_d_profile.profile(g, r)
        if view['status'] == 'unsupported':
            selected = []
            continue
        for identifier in view['missing']:
            if identifier not in view['held'] and not any(c['id'] == identifier for c in selected):
                c = candidate(flow, g, r, identifier)
                if c: selected.append(c)
    dispositions = {**metadata(r).get('baselineDispositions', {}), **r.get('dispositions', {})}
    return checked([c for c in selected if c['id'] not in dispositions and c['id'] not in s['deferred']])[:24]


def target(flow, owner, g, r, moves, required_id, required_reason):
    # Mandatory ambiguity is code-owned; otherwise the model selects a useful
    # approved meaning, not the first item in a fixed topic branch.
    required = next((m for m in moves if m.get('required')), None)
    return (required['id'], 'clarification') if required else (None, None)


def checks_relevant(flow, owner, g=None):
    s = state(flow, owner)
    return (not s.get('finish_requested') and not s.get('outcome')
        and s['guidance']['mode'] == 'work'
        and (bool(set(s['investigate']) & {'doctors','medicines','part_d','advantage'})
             # D207: matching an already reported doctor/medicine is part of
             # ordinary profile work, including an enrollment-timing journey.
             # The retained task must not hide the source-backed selectors.
             # Discuss/detour/finish gates above and source/scope gates in the
             # check controller still apply; this does not choose a plan.
             or bool(g and any(
                 flow.value(g, field) for field in ('needs.providers','needs.medications')))))


def note_message(flow, owner, g, message, submitted_answer=None, r=None):
    if r is not None:
        # Keep actual application/coverage capture, excluding legacy inferred
        # decisions. Current coverage remains separate from keeping it.
        enrollment_flow.capture(flow, g, r, message)
        # A changed report withdraws summary evidence too. The research
        # controller will supply fresh results through its ordinary checks.
        s = state(flow, owner)
        if s.get('last_check_signature') != report_signature(g, r):
            s.pop('last_check_results', None)
    if submitted_answer:
        s = state(flow, owner)
        s['latest'] = empty_proposal()


def action_done(flow, owner, out, action):
    """Free controls convey only what their labels actually authorize."""
    s = state(flow, owner)
    kind = action.get('type')
    if kind in ('choice', 'stage', 'unknown', 'defer') and s['active_task']:
        s['guidance'] = {**s['guidance'], 'mode':'work', 'task':s['active_task']}
        s['education_only'] = False
        s['investigate'] = list(s.get('task_investigate') or
                               conversation_tasks.DEFAULT_INVESTIGATIONS.get(s['active_task'], []))
    if kind == 'enrollment_decision':
        if 'start_with' in action:
            focus = {'original_medigap': 'original', 'medicare_advantage': 'advantage', 'both': 'coverage_paths'}[action['start_with']]
            s.update(purpose='understand', focus=focus, investigate=[], latest=empty_proposal())
            s['guidance'] = conversation_tasks.empty()
            s['exploring'] = list(dict.fromkeys(s['exploring'] + [focus]))[-5:]
        elif 'path' in action:
            s['decision'] = {'stance': 'undecided' if action['path'] == 'undecided' else 'chosen',
                             'path': '' if action['path'] == 'undecided' else action['path']}
    elif kind == 'task' or kind in ('choice', 'stage') and action.get('id') == 'T01':
        task = action.get('task') or action.get('fields', {}).get('choice')
        s['latest'] = empty_proposal()
        if kind == 'task' and pending_on(flow):
            import conversation_records
            conversation_records.release_pending(s)   # D188: a tapped task is a new subject; no pass
        if task in ('medigap', 'drug_pricing'):
            product = 'medigap' if task == 'medigap' else 'part_d'
            s.update(purpose='investigate', focus=product, investigate=[product])
        else:
            s.update(purpose={'learn': 'understand', 'review': 'review', 'compare': 'compare'}.get(task, 'problem'),
                     focus={'timing': 'enrollment', 'providers': 'doctors', 'drug_coverage': 'medicines'}.get(task, 'coverage_paths'),
                     investigate=[])
        if task in conversation_tasks.TASKS:
            s.update(active_task=task, guidance={**conversation_tasks.empty(), 'mode':'work','task':task}, education_only=False)
            s['investigate'] = list(conversation_tasks.DEFAULT_INVESTIGATIONS.get(task, []))
            s['task_investigate'] = list(s['investigate'])
        else:
            s['guidance'] = conversation_tasks.empty()
    elif kind in ('unknown', 'defer'):
        identifier = action.get('id')
        if identifier and identifier not in s['deferred']: s['deferred'].append(identifier)
    if kind in ('choice', 'stage', 'unknown', 'defer', 'task', 'enrollment_decision') and not out.get('generated'):
        moves = flow.eligible(owner, out['guide'], out['record'])
        if not metadata(out['record']).get('editing') and action.get('source') != 'plans_filter':
            out['assessment']['nextQuestion'] = copy.deepcopy(moves[0]['question']) if moves else None
            from natural_state import set_target
            set_target(out['record'], out['assessment']['nextQuestion'])


def educational_card(flow, s):
    if s['focus'] not in ('coverage_paths', 'costs', 'flexibility'):
        return None
    # Reuse the accepted statements without the old inferred lean, price
    # placeholders, completion counters or premature decision controls.
    return {'kind': 'discussion_paths', 'title': 'Two ways to get Medicare coverage',
        'columns': [
            {'title': 'Original Medicare', 'lines': [enrollment_flow.statement('original_what'),
                enrollment_flow.statement('trade_original_access'), enrollment_flow.statement('trade_medigap_helps')]},
            {'title': 'Medicare Advantage', 'lines': [enrollment_flow.statement('trade_ma_limit'),
                enrollment_flow.statement('trade_ma_network'), enrollment_flow.statement('trade_ma_drugs')]},
        ], 'sources': enrollment_flow._statement_sources('original_what', 'trade_original_access',
                    'trade_medigap_helps', 'trade_ma_limit', 'trade_ma_network', 'trade_ma_drugs'),
        'actions': [{'label': 'Explore Original Medicare', 'say': 'Help me understand Original Medicare and its options.'},
                    {'label': 'Explore Medicare Advantage', 'say': 'Help me understand Medicare Advantage.'}]}


def card_fingerprint(card):
    """D198: delivery identity follows facts, not a shortened say-once caveat."""
    value = card
    if card.get('kind') == 'enrollment_timing' and 'dates' in card and 'cobra' in card:
        value = {key: item for key, item in card.items() if key not in ('text', 'cobra')}
        value['cobra'] = bool(card['cobra'])
    return hashlib.sha256(repr(value).encode()).hexdigest()


def card_requested_again(card, context):
    education = context.get('education_context', {})
    if card.get('kind') != 'enrollment_timing':
        return bool(education.get('requested_revisit'))
    # A general enrollment explanation is not a request to redraw known dates.
    # These hints have already passed quote/concept validation in natural_flow.
    return bool(education.get('requested_revisit') and education.get('request_kind') == 'revisit'
                and set(education.get('revisit_concepts') or ())
                    & {'enrollment_timing', 'current_coverage_timing'})


def prepare(flow, owner, g, r, moves, context):
    s = state(flow, owner)
    cards = []
    card = educational_card(flow, s)
    if card and (s['latest']['question_quote'] or s['purpose'] == 'compare'):
        fingerprint = card_fingerprint(card)
        if s['cards'].get(card['kind']) != fingerprint or card_requested_again(card, context):
            cards.append(card)
    if s['focus'] == 'enrollment':
        import ux_flow
        timing = ux_flow._timing_card(flow, owner, g, r, s['latest']['question_quote'])
        if timing: cards.append(timing)
        cards.extend(enrollment_flow.cards(flow, owner, flow.current_chain.get(owner), g, r,
                                           s['latest']['question_quote'], cards, record_signup=not records_on(flow)))
        if s['guidance']['mode'] == 'work' and moves:
            # Do not put fulfillment ahead of the pending information request.
            cards = [c for c in cards if c['kind'] != 'signup_route']
    elif 'advantage' in (flow.value(g, 'coverage.current') or []) and (
            re.search(r'\btrial right\b', s['latest']['question_quote'], re.I)):
        trial = enrollment_flow.trial_right(flow, g, r, enrollment_flow._today())
        if trial:
            cards.append(trial)
    pages = flow.plans_pages(g, r)
    if s['guidance']['mode'] == 'work':
        names = {'medigap': ('See Medigap prices', 'supplement'), 'advantage': ('See Medicare Advantage plans', 'advantage'),
                 'part_d': ('See Part D plans', 'part-d')}
        for name in s['investigate']:
            if name not in names: continue
            ready = part_d_profile.profile(g, r)['status'] == 'ready' if name == 'advantage' else pages[name]['status'] == 'ready'
            if ready:
                label, view = names[name]
                cards.append({'kind': 'plans_ready', 'title': label, 'tab': name, 'button': {'label': label, 'view': view}})
    record = enrollment_flow.journey(flow, g, r, enrollment_flow._today())
    if record.get('finish'):
        line = enrollment_flow.status_line(record, {part: flow.value(g, field) for part, field in enrollment_flow.PART_FIELDS.items()},
            flow.value(g, enrollment_flow.PATH_FIELD), flow.value(g, 'coverage.socialBenefits') == 'yes', flow.value(g, 'coverage.current') or [])
        summary = enrollment_flow.finish_card(record, line) if line else None
        if summary: cards = [summary]
    if records_on(flow):
        # D183: the job-coverage window, computed by code from the person's own
        # dates, once, ahead of other cards. Dates never go in model prose.
        import conversation_records
        bundle = conversation_records.readiness(flow, owner, g, r, s)
        s['records_bundle'] = bundle
        work = conversation_records.work_card(bundle.get('work_window'))
        if work:
            cards.insert(0, work)
    # One conceptual card per turn; multiple requested result links share a row
    # in the frontend. Never stack an unrelated route or coverage card.
    cards = [c for c in cards if s['cards'].get(c['kind']) != card_fingerprint(c)
             or card_requested_again(c, context)]
    s['turn_cards'] = cards[:3] if all(c['kind'] == 'plans_ready' for c in cards) else cards[:1]
    plan = {'version': VERSION, 'purpose': s['purpose'], 'focus': s['focus'],
        'direction_version': 'conversation-contract-v3',
        'guidance': {k:copy.deepcopy(v) for k,v in s['guidance'].items() if k != 'quote'},
        'active_task': s['active_task'], 'suggested_task': s['suggested_task'],
        'require_structured': (bool(moves) and s['guidance']['mode'] not in ('pause', 'finish') and not s.get('finish_requested'))
                              if records_on(flow) else (s['guidance']['mode'] == 'work' and bool(moves)),
        'finish_requested': s.get('finish_requested'),
        'answer_first': bool(s['latest']['question_quote']), 'question_to_answer': s['latest']['question_quote'],
        'investigations': list(s['investigate']), 'exploring': list(s['exploring']),
        'decision': path(flow, owner, g, r),
        'next_question': (s.get('records_target') if records_on(flow) and any(m['id'] == s.get('records_target') for m in moves) else None),
        'available_questions': [m['id'] for m in moves],
        'deferred_questions': list(s['deferred']), 'software_cards': [c['kind'] for c in s['turn_cards']],
        'understanding_is_not_delivery': True}
    if records_on(flow):
        guide = next((c for c in s['turn_cards'] if c['kind'] == 'signup_route'), None)
        if guide:
            # D203: prepared is not delivered; the composer decides whether
            # this guide supports the conversation now and introduces it.
            plan['guide_presentation'] = {
                'title': guide['title'], 'route': guide['route'], 'guides': list(guide.get('guides') or []),
                'purpose': 'Preparation for the enrollment steps; the phone guide covers what to have ready, what to say and what to ask before hanging up.',
                'rule': ('Choose signup_route in education.visual only if useful now, otherwise none and continue '
                         'the conversation. Before showing it, give 2–3 short, natural sentences connecting the '
                         'current concern to why this guide helps and what using it will accomplish. Explain any '
                         'essential concept in plain language using supplied evidence. Frame it as available help, '
                         'not an instruction to call immediately or leave Daylight. If Medicare status is still '
                         'unknown, acknowledge that and connect the next question to choosing the right steps; '
                         'do not assume an application is needed. Keep detailed rules/contact details in the card, '
                         'not duplicated in prose. Do not announce a guide when choosing none.')}
    if s.get('pace_request'):
        plan['pace_request'] = {
            'rule': ('The person asked to slow down or why a detail is needed. Acknowledge it in one short sentence, '
                     'then say plainly why the open question matters for their next step, and that they can skip it. '
                     'Keep the visit open: no summary, no closing. Software shows choices to skip, see options first, '
                     'hear it more simply or stop for today.')}
    if pending_on(flow):
        # D188: mark the target as a return, with its delivery count.
        import conversation_records
        plan['pending_question'] = conversation_records.pending_plan(s, moves)
    if records_on(flow):
        import conversation_records
        detail = conversation_records.pre_close_plan(flow, s, moves)   # D190: answer first, then the detail
        if detail:
            plan['pre_close_detail'] = detail
    s['plan'] = plan
    context['discussion_plan'] = copy.deepcopy(plan)
    context['question_progress'] = question_progress.snapshot(flow,g,r,s.setdefault('question_progress',{}))
    context['open_requests'] = copy.deepcopy(s.get('open_requests', []))
    context['discussion_capabilities'] = conversation_tasks.context(flow, g, r)
    context['plans_pages']['purpose'] = (
        'Availability evidence only. Use the status and supplied limits for products '
        'in discussion_plan.investigations. Unrequested ready tabs do not trigger intake '
        'or a plan announcement. Listed prices and identities stay in deterministic views.')
    context['conversation_state'] = ({'software_cards': plan['software_cards']} if records_on(flow) else
        # D183 retires the word-pattern "already said" list on :8895; the education record replaces it.
        {'already_said': sorted(flow.ux.view(owner, flow.current_chain.get(owner))['points']),
         'software_cards': plan['software_cards']})
    context['enrollment'] = enrollment_flow.context(flow, g, r)
    if journey_completion.enabled(flow):
        context['closing_brief'] = (journey_completion.comparison_brief(flow,g,r,s)
            if journey_completion.closing_due(flow,owner,g,r,s) or s.get('finish_requested') or s['guidance']['mode']=='pause' else None)
    if not checks_relevant(flow, owner, g) and 'conversation_checks' in context:
        context['conversation_checks'].pop('current', None)
    if records_on(flow):
        import conversation_records
        bundle = s.get('records_bundle') or conversation_records.readiness(flow, owner, g, r, s)
        context['profile_record'] = conversation_records.compact_profile(
            conversation_records.profile_view(flow, owner, g, r, s.get('question_progress')))
        context['readiness'] = conversation_records.compact_readiness(bundle)
        education = conversation_records.education_view(s)
        context['education_record'] = education
        delivered = set(education['delivered_facts'])
        for item in context.get('evidence') or []:
            if isinstance(item, dict) and item.get('id') in delivered:
                item['delivered'] = True
        if bundle.get('work_window'):
            context['timing_result'] = {'shown_on_code_card': any(c['kind'] == 'enrollment_timing' for c in s['turn_cards']), 'basis': 'reported dates',
                                        'facts': bundle['work_window']['facts'],
                                        'rule': 'Refer to the timing card in one clause; never restate or compute its dates.'}
    return context


def finish(flow, owner, out, message, moves, **kwargs):
    s = state(flow, owner)
    if s['guidance']['mode'] == 'pause':
        out['assessment'].update(nextQuestion=None, intakePaused=True, conversationOpen=True)
    cards = copy.deepcopy(s.get('turn_cards', []))
    selected_card = out.pop('_selected_education_card', None)
    selectable = {'discussion_paths', 'signup_route'} if records_on(flow) else {'discussion_paths'}
    cards = [c for c in cards if c['kind'] not in selectable or selected_card == c['kind']]
    evidence = out.pop('_records_evidence', None)
    requested = out.pop('_records_requested', False)
    block_refs = out.pop('_records_block_refs', None)
    released = out.pop('_released_blocks', None)
    source_urls = out.pop('_records_source_urls', None)
    flagged = out.pop('_records_flagged', ())
    if records_on(flow) and out.get('generated', {}).get('status') == 'complete':
        # D183: say each fact once, per block. A block whose facts were all shown
        # is held back unless the person asked, was confused or asked to revisit
        # that concept; then record exactly what was shown (blocks, the facts the
        # kept blocks cite, code cards).
        import conversation_records
        kept, held, held_facts = conversation_records.filter_blocks(s, out.get('reply', ''), block_refs, requested, flagged,
                                                                    keep=released or ())
        if held and (kept.strip() or out['assessment'].get('nextQuestion')):
            out['reply'] = kept
            if block_refs:
                still = {f for b in kept.split('\n\n') for f in (block_refs or {}).get(' '.join(b.split()), [])}
                uncited = any(' '.join(b.split()) not in block_refs for b in kept.split('\n\n') if b.strip())
                evidence = {k: v for k, v in (evidence or {}).items() if k in still or uncited}
            else:
                evidence = {k: v for k, v in (evidence or {}).items() if kept.strip()}
        else:
            held, held_facts = 0, []
        s['records_held_back'] = held
        s['records_held_facts'] = held_facts
        advisor = out.get('advisor') if isinstance(out.get('advisor'), dict) else None
        if held and advisor is not None:
            # Links and teaching credit follow the blocks that were actually shown.
            shown_ids = set(evidence or {})
            keep = {url for identifier in shown_ids for url in (source_urls or {}).get(identifier, [])}
            advisor['sources'] = [x for x in advisor.get('sources') or [] if x.get('url') in keep] if out.get('reply', '').strip() else []
            advisor['teachingFactIds'] = [f for f in advisor.get('teachingFactIds') or [] if f in shown_ids]
        conversation_records.record_shown(s, out.get('reply', ''), evidence or {}, cards)
    if out.get('generated', {}).get('status') != 'complete':
        # Never pretend a failed answer satisfied the outstanding question.
        s['plan']['answer_state'] = 'unresolved'
        if not out.get('reply'):
            out['reply'] = 'I don’t have a checked answer to that question here yet, so I won’t guess.'
        # A generation failure is ours, not a request for the person to reword
        # a clear goal. Keep the approved next question and any useful controls.
        if not out['assessment'].get('intakePaused') and moves:
            out['assessment']['nextQuestion'] = copy.deepcopy(moves[0]['question'])
            suffix = '\n\nWhat would you like to understand next?'
            if out['reply'].endswith(suffix): out['reply'] = out['reply'][:-len(suffix)]
    else:
        s['plan']['answer_state'] = 'delivered' if s['latest']['question_quote'] else 'not_requested'
    if out.get('generated', {}).get('answer_state'):
        s['plan']['answer_state'] = out['generated']['answer_state']
    # Delivery bookkeeping, never profile facts or a reason to force a retry.
    # Only a complete checked answer may retire a model-selected open request.
    pending = s.setdefault('open_requests', [])
    addressed = out.pop('_addressed_requests', [])
    generated = out.get('generated', {})
    if (generated.get('status')=='complete' and out.get('reply','').strip()
            and not generated.get('validation_recovery')
            and generated.get('answer_state') not in {'partial','unanswered'}):
        pending[:] = [item for item in pending if item['id'] not in addressed]
    if s['plan']['answer_state'] in {'partial','unanswered','unresolved'}:
        request = s['latest'].get('question_quote') or (message if message and s['guidance']['mode'] in {'work','detour','discuss'} else '')
        if request and not any(item['request']==request[:600] for item in pending):
            request=request[:600]
            pending.append({'id':hashlib.sha256(request.encode()).hexdigest()[:12],
                'request':request,'task':s['active_task'],'state':s['plan']['answer_state']})
            del pending[:-4]
    for card in cards:
        if records_on(flow) and card['kind'] == 'signup_route':
            flow.ux.record(owner, flow.current_chain.get(owner), '', card='signup_route:' + card['route'])
        s['cards'][card['kind']] = card_fingerprint(card)
    if s.get('pace_request') and not s.get('finish_requested') and s['guidance']['mode'] != 'pause':
        cards = [c for c in cards if c['kind'] != 'next_step_offer'] + [pace_card()]   # D200
    if cards: out['cards'] = cards
    if s.get('finish_requested'):
        s['outcome'], card = journey_completion.summary(flow, owner, out['guide'], out['record'], s, out)
        out['cards'] = [card]
        # A failed generation cannot replace the concrete software summary
        # with a generic rephrase/intake loop.
        if out.get('generated', {}).get('status') != 'complete':
            out['reply'] = 'Your visit summary keeps the work performed, open checks and next action together below.'
    flow.ux.record(owner, flow.current_chain.get(owner), out.get('reply', ''))
    attach(flow, owner, out)


def report_signature(g, r):
    from conversation_checks import reported_fields
    return hashlib.sha256(json.dumps(reported_fields(g, r), sort_keys=True).encode()).hexdigest()


def attach(flow, owner, out):
    s = state(flow, owner)
    out['conversationPlanner'] = {k: copy.deepcopy(v) for k, v in s['plan'].items() if k != 'question_to_answer'}
    out['conversationPlanner'].setdefault('version', VERSION)
    out['conversationPlanner'].update(purpose=s['purpose'], focus=s['focus'], investigations=list(s['investigate']))
    products = s.get('plans_products', [p for p in s.get('task_investigate', s['investigate']) if p in ('medigap', 'part_d', 'advantage')])
    out['conversationPlanner']['plans_view'] = ({'medigap': 'supplement', 'part_d': 'part-d', 'advantage': 'advantage'}[products[0]]
        if len(products) == 1 else 'paths')
    if s['focus'] == 'enrollment': out['conversationPlanner']['plans_view'] = 'ab'
    out['conversationPlanner']['medigap_variant'] = s.get('medigap_variant')
    out['conversationPlanner']['education_only'] = s.get('education_only', False)
    out['coveragePath'] = path(flow, owner, out['guide'], out['record'])
    out['conversationPlanner'].update(decision=copy.deepcopy(out['coveragePath']), exploring=list(s['exploring']),
        next_question=(out['assessment'].get('nextQuestion') or {}).get('id'))
    out['whatsLeft'] = None
    if 'conversationCheck' in out and not out['conversationCheck'].get('paused'):
        s['last_check_results'] = copy.deepcopy(out['conversationCheck'].get('results', []))
        s['last_check_signature'] = report_signature(out['guide'], out['record'])
    if s.get('outcome'):
        out['conversationPlanner']['outcome'] = copy.deepcopy(s['outcome'])
        out['assessment']['nextQuestion'] = None
        out['assessment']['intakePaused'] = True
        out['conversationPlanner']['next_question'] = None
        if out.get('enrollment'):
            out['enrollment']['record']['outcome'] = copy.deepcopy(s['outcome'])
    # Enrollment status remains factual. During exploration it must not tell a
    # person their next conversational step is choosing/buying a path.
    enrollment = out.get('enrollment')
    if isinstance(enrollment, dict) and isinstance(enrollment.get('line'), dict):
        line = enrollment['line']
        if out['coveragePath']['state'] != 'chosen' and line.get('next', {}).get('id', '').startswith('choose_'):
            line['next'] = {**line['next'], 'text': ''}
            line['text'] = line['status']
    return out


def delivered_next(flow, owner, out, s, saved_ack=False, *, replay=False):
    """D205: choose one visible continuation after content/check/closing filters.

    Model language has already passed factual validation. Profile questions keep
    their existing eligibility/parking gates; clarification text never enters the
    education deduplicator. This is delivery arbitration, not an interview script.
    """
    import conversation_records
    proposed = out.pop('_records_next_move', None) or (out.get('conversationNext', {}) if replay else {})
    assessment = out['assessment']
    complete = out.get('generated', {}).get('status') == 'complete'
    paused = s['guidance']['mode'] in ('pause', 'finish') or s.get('outcome') or s.get('finish_requested')
    check = (out.get('conversationCheck') or {}).get('question')
    pace = (next((c for c in out.get('cards') or [] if c.get('pace') and c.get('actions')), None)
            if s['guidance']['mode'] == 'detour' else None)
    if paused and check:
        out['conversationCheck']['question'] = None
        check = None
    if paused or out.get('review') or out.get('preparation') or check or pace:
        # These surfaces own the input. Do not count an obscured profile question
        # as delivered or leave it pending behind another control.
        assessment['nextQuestion'] = None
    if not replay:
        question_progress.delivered(flow, owner, out, s.setdefault('question_progress', {}))
    q = assessment.get('nextQuestion')
    clarification = proposed.get('question') if complete and proposed.get('kind') == 'clarification' else None
    cards = out.get('cards') or []
    offered = False
    if out.get('review'):
        move = {'kind': 'action', 'action': 'review'}
    elif out.get('preparation'):
        move = {'kind': 'action', 'action': 'preparation'}
    elif paused:
        move = {'kind': 'finish'}
    elif check:
        move = {'kind': 'action', 'action': 'check'}
    elif pace:
        move = {'kind': 'action', 'action': 'card', 'card': pace['kind']}
    elif q:
        move = {'kind': 'profile_question', 'target': q['id']}
    elif clarification:
        move = {'kind': 'clarification', 'question': clarification}
        # Assemble only now, for existing chat/history consumers. The typed
        # field remains authoritative; this text is not teaching credit.
        if not replay:
            out['reply'] = '\n\n'.join(x for x in (out.get('reply', '').strip(), clarification) if x)
    elif ((out.get('comparisonClose') or {}).get('show') or
          (out.get('planReadiness', {}).get('canReview') and s['guidance']['mode'] == 'work'
           and not metadata(out['record']).get('editing')
           and not assessment.get('journey', {}).get('samplesVisible'))):
        move = {'kind': 'action', 'action': 'plan_review'}
    elif any(c.get('actions') for c in cards):
        card = next(c for c in cards if c.get('actions'))
        move = {'kind': 'action', 'action': 'card', 'card': card['kind']}
    elif replay and complete:
        # Replays cannot consume offers/ask counts or start new intake. If an
        # expired review disappeared, existing profile inspection is still usable.
        move = {'kind': 'action', 'action': 'profile_review'}
    elif complete or saved_ack:
        pending = conversation_records.pending_receipt(s.get('question_progress'))[1]
        offer = None if pending else conversation_records.next_offer(s, conversation_records.role_of(out))
        if offer:
            conversation_records.record_offer(s, offer['task'], offer['card'])
            out['cards'] = [*cards, offer['card']]
            offered = True
            move = {'kind': 'action', 'action': 'card', 'card': 'next_step_offer'}
        else:
            # A suppressed/consumed offer cannot end an active visit silently.
            # Reuse an eligible existing question, only as delivery recovery.
            moves = conversation_records.candidates(flow, owner, out['guide'], out['record'], s,
                lambda items: question_progress.filter_candidates(flow, owner, out['guide'], out['record'],
                    items, s.setdefault('question_progress', {})))
            assessment['nextQuestion'] = copy.deepcopy(moves[0]['question']) if moves else None
            question_progress.delivered(flow, owner, out, s.setdefault('question_progress', {}))
            q = assessment.get('nextQuestion')
            if q:
                from natural_state import set_target
                set_target(out['record'], q)
                move = {'kind': 'profile_question', 'target': q['id']}
            else:
                # Existing editable profile inspection remains usable even when
                # every question is addressed/parked and all offers are consumed.
                move = {'kind': 'action', 'action': 'profile_review'}
    else:
        # Opening/manual controls and provider/source failures have their own
        # presentation; never label an unavailable generation a successful finish.
        move = {'kind': 'opening' if assessment.get('narrative', {}).get('opener') else 'unavailable'}

    if move['kind'] != 'action' or move.get('action') != 'card':
        out['cards'] = [c for c in out.get('cards') or [] if c.get('kind') != 'next_step_offer']
    elif not replay and proposed.get('kind') == 'action' and proposed.get('question') and move.get('card') == 'next_step_offer':
        out['reply'] = '\n\n'.join(x for x in (out.get('reply', '').strip(), proposed['question']) if x)
    if move.get('action') != 'plan_review' and out.get('comparisonClose'):
        if not replay and out['comparisonClose'].get('show') and s.get('close_delivered') == out['comparisonClose'].get('revision'):
            s.pop('close_delivered', None)  # Preparation is not delivery.
        out['comparisonClose']['show'] = False
    if move['kind'] in ('profile_question', 'clarification'):
        assessment['intakePaused'] = False
        assessment['conversationOpen'] = move['kind'] == 'clarification'
    out['conversationNext'] = move
    out.get('conversationPlanner', {})['next_question'] = (assessment.get('nextQuestion') or {}).get('id')
    return offered


def valid_delivered_next(out):
    """Check actual output, not the model's pre-filter intention or a stale flag."""
    move = out.get('conversationNext') or {}
    kind = move.get('kind')
    q = (out.get('assessment') or {}).get('nextQuestion')
    check = (out.get('conversationCheck') or {}).get('question')
    offers = [c for c in out.get('cards') or [] if c.get('kind') == 'next_step_offer']
    close = (out.get('comparisonClose') or {}).get('show')
    if kind == 'profile_question':
        return bool(q and q.get('question') and q['id'] == move.get('target') and not (check or offers or close))
    if kind == 'clarification':
        return bool(move.get('question') and out.get('reply', '').endswith(move['question'])
                    and not (q or check or offers or close))
    if kind == 'action':
        action = move.get('action')
        available = {'review': bool(out.get('review')), 'preparation': bool(out.get('preparation')),
                     'check': bool(check), 'plan_review': bool(close or out.get('planReadiness', {}).get('canReview')),
                     'profile_review': True,
                     'card': any(c.get('kind') == move.get('card') and c.get('actions') for c in out.get('cards') or [])}
        return bool(available.get(action) and not q and len(offers) <= 1 and (not offers or action == 'card')
                    and (not check or action == 'check') and (not close or action == 'plan_review'))
    return kind in ('finish', 'opening', 'unavailable') and not (q or offers or close)


def records_finalize(flow, owner, out, action=None):
    """Finalize one delivered move, then record codes (never question text)."""
    import conversation_records
    s = state(flow, owner)
    out.pop('_records_evidence', None); out.pop('_records_requested', None); out.pop('_records_source_urls', None)
    saved_ack = out.pop('_records_saved_ack', False)
    offered = delivered_next(flow, owner, out, s, saved_ack)
    q = out['assessment'].get('nextQuestion')
    track = conversation_records.pending_on(flow)
    filtered = out.pop('_records_offer_filtered', None)
    bundle = s.get('records_bundle') or {}
    education = conversation_records.education_view(s)
    out.setdefault('metrics', {})['records'] = {
        'open_fields': s.get('records_open_count'), 'proposed_target': list(s.get('next_target') or []),
        'validated_target': s.get('records_target'), 'target_source': s.get('records_target_source'),
        'delivered_target': (q or {}).get('id'), 'precedence': s.get('records_precedence'),
        'confirmations_queued': bool(flow.pending_for(owner)), 'offer_button': offered,
        'offer_filtered': bool(filtered), 'held_back_blocks': s.get('records_held_back', 0),
        'held_back_facts': len(s.get('records_held_facts') or []), 'facts_delivered': len(education['delivered_facts']),
        'readiness': {name: len(item.get('needs') or []) for name, item in (bundle.get('outcomes') or {}).items()},
        'timing_card_ready': bool(bundle.get('work_window'))}
    out['metrics']['records']['delivered_move'] = out['conversationNext']['kind']
    out['metrics']['records']['delivered_action'] = out['conversationNext'].get('action')
    if track:
        out['metrics']['records'].update(conversation_records.pending_trace(s))
        s['records_pending_code'] = None; s['records_pending_proposed'] = None
        s['records_passed_now'] = None; s['records_offer_task'] = None; s['records_pending_return'] = None
    s['records_held_back'] = 0; s['records_held_facts'] = []; s['records_precedence'] = None


def pending_enforce(flow, owner, out):
    """D188 reply check: while a question is pending the turn ends on it, unless
    the person paused or finished. Runs before the delivery is recorded."""
    import conversation_records
    s = state(flow, owner)
    identifier = s.get('records_pending_return')
    if not identifier or out['assessment'].get('nextQuestion'):
        return
    if (s['guidance']['mode'] in ('pause', 'finish') or s.get('outcome') or s.get('finish_requested')
            or out.get('review') or metadata(out['record']).get('editing')
            or (out.get('conversationCheck') or {}).get('question')
            or (out.get('generated') or {}).get('status') != 'complete'):
        return
    question = conversation_records._question(flow, out['guide'], out['record'], identifier)
    if not question:
        return
    out['assessment'].update(nextQuestion=copy.deepcopy(question), intakePaused=False)
    from natural_state import set_target
    set_target(out['record'], out['assessment']['nextQuestion'])
